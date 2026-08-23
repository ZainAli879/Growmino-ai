from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import RedirectResponse

from app.auth import AuthContext, require_auth_context
from app.config import Settings, get_settings
from app.linkedin_client import (
    LinkedInAPIStatusError,
    LinkedInError,
    LinkedInRateLimitError,
    LinkedInTransientError,
    build_authorization_url,
    create_multi_image_rest_post,
    create_multi_image_rest_post_with_urns,
    create_state_token,
    decrypt_token,
    download_safe_https_image,
    encrypt_token,
    exchange_code_for_token,
    get_userinfo,
    hash_state,
    initialize_rest_image_upload,
    normalize_alt_texts,
    oauth_expiry,
    publish_image_post,
    publish_text_post,
    upload_rest_image_binary,
    validate_image_bytes,
    validate_multi_image_bytes,
)
from app.linkedin_store import (
    consume_oauth_state,
    create_publish_job,
    disconnect_connection,
    get_connection,
    get_publish_job,
    insert_oauth_state,
    list_publish_jobs,
    update_publish_job,
    upsert_connection,
)
from app.schemas import (
    ErrorResponse,
    LinkedInConnectResponse,
    LinkedInJobsResponse,
    LinkedInPostStatus,
    LinkedInPublishImageUrlRequest,
    LinkedInPublishResponse,
    LinkedInPublishTextRequest,
    LinkedInScheduleRequest,
    LinkedInStatusResponse,
)

router = APIRouter(prefix="/api/v1")


@router.get(
    "/integrations/linkedin/connect",
    response_model=LinkedInConnectResponse,
    responses={401: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def connect_linkedin(auth: AuthContext = Depends(require_auth_context)) -> LinkedInConnectResponse:
    settings = _settings()
    state, state_hash = create_state_token()
    try:
        await asyncio.to_thread(
            insert_oauth_state,
            settings,
            state_hash=state_hash,
            user_id=auth.user_id,
            business_id=auth.business_id,
            expires_at=oauth_expiry(settings),
            redirect_after=settings.linkedin_frontend_success_url,
        )
        authorization_url = build_authorization_url(settings, state)
    except LinkedInError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not start LinkedIn OAuth.") from exc
    return LinkedInConnectResponse(
        authorization_url=authorization_url,
        expires_in_seconds=settings.linkedin_oauth_state_ttl_seconds,
    )


@router.get("/integrations/linkedin/callback")
async def linkedin_callback(
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
) -> RedirectResponse:
    settings = _settings()
    if error:
        return RedirectResponse(_with_error(settings.linkedin_frontend_error_url, error))
    if not code or not state:
        return RedirectResponse(_with_error(settings.linkedin_frontend_error_url, "missing_code_or_state"))

    try:
        stored_state = await asyncio.to_thread(consume_oauth_state, settings, state_hash=hash_state(state))
        if not stored_state:
            return RedirectResponse(_with_error(settings.linkedin_frontend_error_url, "invalid_or_replayed_state"))

        token_payload = await asyncio.to_thread(exchange_code_for_token, settings, code)
        access_token = str(token_payload.get("access_token") or "")
        if not access_token:
            return RedirectResponse(_with_error(settings.linkedin_frontend_error_url, "missing_access_token"))
        userinfo = await asyncio.to_thread(get_userinfo, settings, access_token)
        linkedin_sub = str(userinfo.get("sub") or "")
        if not linkedin_sub:
            return RedirectResponse(_with_error(settings.linkedin_frontend_error_url, "missing_linkedin_sub"))
        expires_in = int(token_payload.get("expires_in") or 0)
        expires_at = (
            datetime.now(timezone.utc).timestamp() + expires_in if expires_in > 0 else datetime.now(timezone.utc).timestamp()
        )
        await asyncio.to_thread(
            upsert_connection,
            settings,
            user_id=str(stored_state["user_id"]),
            business_id=str(stored_state["business_id"]),
            linkedin_sub=linkedin_sub,
            person_urn=f"urn:li:person:{linkedin_sub}",
            encrypted_access_token=encrypt_token(settings, access_token),
            scopes=str(token_payload.get("scope") or "openid profile email w_member_social"),
            expires_at=datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
            profile=userinfo,
        )
    except Exception:
        return RedirectResponse(_with_error(settings.linkedin_frontend_error_url, "callback_failed"))
    return RedirectResponse(settings.linkedin_frontend_success_url)


@router.get(
    "/integrations/linkedin/status",
    response_model=LinkedInStatusResponse,
    responses={401: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def linkedin_status(auth: AuthContext = Depends(require_auth_context)) -> LinkedInStatusResponse:
    settings = _settings()
    connection = await asyncio.to_thread(
        get_connection,
        settings,
        user_id=auth.user_id,
        business_id=auth.business_id,
    )
    if not connection:
        return LinkedInStatusResponse(connected=False)
    return LinkedInStatusResponse(
        connected=True,
        profile_name=connection.profile_name,
        email=connection.email,
        linkedin_sub=connection.linkedin_sub,
        person_urn=connection.person_urn,
        connected_at=connection.connected_at,
        expires_at=connection.expires_at,
    )


@router.delete(
    "/integrations/linkedin/disconnect",
    response_model=LinkedInStatusResponse,
    responses={401: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def linkedin_disconnect(auth: AuthContext = Depends(require_auth_context)) -> LinkedInStatusResponse:
    settings = _settings()
    await asyncio.to_thread(
        disconnect_connection,
        settings,
        user_id=auth.user_id,
        business_id=auth.business_id,
    )
    return LinkedInStatusResponse(connected=False)


@router.post(
    "/posts/linkedin/publish-text",
    response_model=LinkedInPublishResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def publish_linkedin_text(
    payload: LinkedInPublishTextRequest,
    auth: AuthContext = Depends(require_auth_context),
) -> LinkedInPublishResponse:
    settings = _settings()
    job = await asyncio.to_thread(
        create_publish_job,
        settings,
        user_id=auth.user_id,
        business_id=auth.business_id,
        post_type="text",
        caption=payload.caption,
        status="publishing",
        idempotency_key=payload.idempotency_key or str(uuid4()),
    )
    if job.linkedin_post_id or job.status == "published":
        return _publish_response(job, "Already published.")
    return await _publish_existing_job(settings, auth, job)


@router.post(
    "/posts/linkedin/publish-image",
    response_model=LinkedInPublishResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def publish_linkedin_image(
    caption: str = Form(..., min_length=1, max_length=3000),
    idempotency_key: str = Form(default=""),
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_auth_context),
) -> LinkedInPublishResponse:
    settings = _settings()
    image_bytes = await _read_upload(file, settings.linkedin_max_image_bytes)
    try:
        mime_type = validate_image_bytes(settings, image_bytes, file.content_type or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = await asyncio.to_thread(
        create_publish_job,
        settings,
        user_id=auth.user_id,
        business_id=auth.business_id,
        post_type="image",
        caption=caption,
        status="publishing",
        idempotency_key=idempotency_key or str(uuid4()),
    )
    if job.linkedin_post_id or job.status == "published":
        return _publish_response(job, "Already published.")
    return await _publish_existing_job(settings, auth, job, image_bytes=image_bytes, image_mime_type=mime_type)


@router.post(
    "/posts/linkedin/publish-image-url",
    response_model=LinkedInPublishResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def publish_linkedin_image_url(
    payload: LinkedInPublishImageUrlRequest,
    auth: AuthContext = Depends(require_auth_context),
) -> LinkedInPublishResponse:
    settings = _settings()
    try:
        image_bytes, mime_type = await asyncio.to_thread(download_safe_https_image, settings, payload.image_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job = await asyncio.to_thread(
        create_publish_job,
        settings,
        user_id=auth.user_id,
        business_id=auth.business_id,
        post_type="image",
        caption=payload.caption,
        image_url=payload.image_url,
        status="publishing",
        idempotency_key=payload.idempotency_key or str(uuid4()),
    )
    if job.linkedin_post_id or job.status == "published":
        return _publish_response(job, "Already published.")
    return await _publish_existing_job(settings, auth, job, image_bytes=image_bytes, image_mime_type=mime_type)


@router.post(
    "/social/linkedin/posts/multi-image",
    response_model=LinkedInPublishResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
async def publish_linkedin_multi_image(
    caption: str = Form(..., min_length=1, max_length=3000),
    idempotency_key: str = Form(default=""),
    alt_texts: list[str] | None = Form(default=None),
    images: list[UploadFile] = File(...),
    auth: AuthContext = Depends(require_auth_context),
) -> LinkedInPublishResponse:
    settings = _settings()
    if len(images) < 2 or len(images) > 20:
        raise HTTPException(status_code=400, detail="LinkedIn multi-image posts require 2 to 20 images.")

    try:
        normalized_alt_texts = normalize_alt_texts(len(images), alt_texts or [])
        validated_images: list[tuple[bytes, str]] = []
        for image in images:
            image_bytes = await _read_upload(image, settings.linkedin_max_image_bytes)
            mime_type = validate_multi_image_bytes(settings, image_bytes, image.content_type or "")
            validated_images.append((image_bytes, mime_type))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = await asyncio.to_thread(
        create_publish_job,
        settings,
        user_id=auth.user_id,
        business_id=auth.business_id,
        post_type="multi_image",
        caption=caption,
        status="publishing",
        alt_texts=normalized_alt_texts,
        idempotency_key=idempotency_key or str(uuid4()),
    )
    if job.linkedin_post_id or job.status == "published":
        return _publish_response(job, "Already published.")

    connection = await asyncio.to_thread(
        get_connection,
        settings,
        user_id=auth.user_id,
        business_id=auth.business_id,
    )
    if not connection:
        await asyncio.to_thread(
            update_publish_job,
            settings,
            post_id=job.id,
            values={"status": "failed", "error_message": "LinkedIn is not connected."},
        )
        raise HTTPException(status_code=401, detail="LinkedIn is not connected.")

    image_urns: list[str] = []
    try:
        access_token = decrypt_token(settings, connection.encrypted_access_token)
        for image_bytes, image_mime_type in validated_images:
            upload = await asyncio.to_thread(
                initialize_rest_image_upload,
                settings,
                access_token=access_token,
                owner_urn=connection.person_urn,
            )
            await asyncio.to_thread(
                upload_rest_image_binary,
                settings,
                access_token=access_token,
                upload_url=upload["upload_url"],
                image_bytes=image_bytes,
                image_mime_type=image_mime_type,
            )
            image_urns.append(upload["image_urn"])

        linkedin_post_id = await asyncio.to_thread(
            create_multi_image_rest_post,
            settings,
            access_token=access_token,
            author_urn=connection.person_urn,
            caption=caption,
            image_urns=image_urns,
            alt_texts=normalized_alt_texts,
        )
        published = await asyncio.to_thread(
            update_publish_job,
            settings,
            post_id=job.id,
            values={
                "status": "published",
                "linkedin_post_id": linkedin_post_id,
                "image_urns": image_urns,
                "alt_texts": normalized_alt_texts,
                "error_message": "",
            },
        )
        return _publish_response(published or job, "LinkedIn multi-image post published.")
    except Exception as exc:
        await asyncio.to_thread(
            update_publish_job,
            settings,
            post_id=job.id,
            values={
                "status": "failed",
                "image_urns": image_urns,
                "alt_texts": normalized_alt_texts,
                "error_message": str(exc),
            },
        )
        _raise_linkedin_http_exception(exc)


@router.post(
    "/posts/linkedin/schedule",
    response_model=LinkedInPublishResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def schedule_linkedin_post(
    payload: LinkedInScheduleRequest,
    auth: AuthContext = Depends(require_auth_context),
) -> LinkedInPublishResponse:
    settings = _settings()
    try:
        scheduled_utc = _parse_schedule_time(payload.scheduled_for)
        if payload.image_url:
            await asyncio.to_thread(download_safe_https_image, settings, payload.image_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = await asyncio.to_thread(
        create_publish_job,
        settings,
        user_id=auth.user_id,
        business_id=auth.business_id,
        post_type="image" if payload.image_url else "text",
        caption=payload.caption,
        image_url=payload.image_url,
        status="scheduled",
        scheduled_for_utc=scheduled_utc,
        display_timezone=payload.timezone or "UTC",
        idempotency_key=payload.idempotency_key or str(uuid4()),
    )
    return _publish_response(job, "LinkedIn post scheduled.")


@router.get("/posts/linkedin/jobs", response_model=LinkedInJobsResponse)
async def list_linkedin_jobs(
    limit: int = Query(default=25, ge=1, le=100),
    auth: AuthContext = Depends(require_auth_context),
) -> LinkedInJobsResponse:
    settings = _settings()
    jobs = await asyncio.to_thread(
        list_publish_jobs,
        settings,
        user_id=auth.user_id,
        business_id=auth.business_id,
        limit=limit,
    )
    return LinkedInJobsResponse(posts=jobs)


@router.post("/posts/{post_id}/retry", response_model=LinkedInPublishResponse)
async def retry_linkedin_post(post_id: str, auth: AuthContext = Depends(require_auth_context)) -> LinkedInPublishResponse:
    settings = _settings()
    job = await _owned_job(settings, auth, post_id)
    if job.status not in {"failed", "scheduled"}:
        raise HTTPException(status_code=400, detail="Only failed or scheduled LinkedIn jobs can be retried.")
    updated = await asyncio.to_thread(
        update_publish_job,
        settings,
        post_id=post_id,
        values={
            "status": "publishing",
            "error_message": "",
            "retry_count": job.retry_count + 1,
        },
    )
    if not updated:
        raise HTTPException(status_code=404, detail="LinkedIn post not found.")
    return await _publish_existing_job(settings, auth, updated)


@router.delete("/posts/{post_id}/schedule", response_model=LinkedInPostStatus)
async def cancel_linkedin_schedule(post_id: str, auth: AuthContext = Depends(require_auth_context)) -> LinkedInPostStatus:
    settings = _settings()
    job = await _owned_job(settings, auth, post_id)
    if job.status not in {"scheduled", "failed"}:
        raise HTTPException(status_code=400, detail="Only scheduled or failed scheduled jobs can be cancelled.")
    updated = await asyncio.to_thread(
        update_publish_job,
        settings,
        post_id=post_id,
        values={"status": "cancelled", "error_message": ""},
    )
    if not updated:
        raise HTTPException(status_code=404, detail="LinkedIn post not found.")
    return updated


async def _publish_existing_job(
    settings: Settings,
    auth: AuthContext,
    job: LinkedInPostStatus,
    *,
    image_bytes: bytes | None = None,
    image_mime_type: str = "",
) -> LinkedInPublishResponse:
    connection = await asyncio.to_thread(
        get_connection,
        settings,
        user_id=auth.user_id,
        business_id=auth.business_id,
    )
    if not connection:
        await asyncio.to_thread(update_publish_job, settings, post_id=job.id, values={"status": "failed", "error_message": "LinkedIn is not connected."})
        raise HTTPException(status_code=401, detail="LinkedIn is not connected.")
    try:
        access_token = decrypt_token(settings, connection.encrypted_access_token)
        if job.type == "image":
            if image_bytes is None and job.image_url:
                image_bytes, image_mime_type = download_safe_https_image(settings, job.image_url)
            if image_bytes is None:
                raise ValueError("Image content is required for image publishing.")
            linkedin_post_id = publish_image_post(
                settings,
                access_token=access_token,
                author_urn=connection.person_urn,
                caption=job.caption,
                image_bytes=image_bytes,
                image_mime_type=image_mime_type,
            )
        elif job.type == "multi_image":
            linkedin_post_id = create_multi_image_rest_post_with_urns(
                settings,
                access_token=access_token,
                author_urn=connection.person_urn,
                caption=job.caption,
                image_urns=job.image_urns,
                alt_texts=job.alt_texts,
            )
        else:
            linkedin_post_id = publish_text_post(
                settings,
                access_token=access_token,
                author_urn=connection.person_urn,
                caption=job.caption,
            )
        published = await asyncio.to_thread(
            update_publish_job,
            settings,
            post_id=job.id,
            values={"status": "published", "linkedin_post_id": linkedin_post_id, "error_message": ""},
        )
        return _publish_response(published or job, "LinkedIn post published.")
    except LinkedInRateLimitError as exc:
        await asyncio.to_thread(update_publish_job, settings, post_id=job.id, values={"status": "failed", "error_message": str(exc)})
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except LinkedInAPIStatusError as exc:
        await asyncio.to_thread(update_publish_job, settings, post_id=job.id, values={"status": "failed", "error_message": str(exc)})
        raise HTTPException(status_code=_linkedin_status_code(exc), detail=str(exc)) from exc
    except (LinkedInTransientError, LinkedInError, ValueError) as exc:
        await asyncio.to_thread(update_publish_job, settings, post_id=job.id, values={"status": "failed", "error_message": str(exc)})
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def _read_upload(file: UploadFile, max_bytes: int) -> bytes:
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail=f"Image exceeds maximum size of {max_bytes} bytes.")
    return content


def _settings() -> Settings:
    try:
        return get_settings()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Service configuration error.") from exc


async def _owned_job(settings: Settings, auth: AuthContext, post_id: str) -> LinkedInPostStatus:
    job = await asyncio.to_thread(
        get_publish_job,
        settings,
        post_id=post_id,
        user_id=auth.user_id,
        business_id=auth.business_id,
    )
    if not job:
        raise HTTPException(status_code=404, detail="LinkedIn post not found.")
    return job


def _parse_schedule_time(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("scheduled_for must be an ISO datetime.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    scheduled_utc = parsed.astimezone(timezone.utc)
    if scheduled_utc <= datetime.now(timezone.utc):
        raise ValueError("scheduled_for must be in the future.")
    return scheduled_utc.isoformat()


def _publish_response(job: LinkedInPostStatus, message: str) -> LinkedInPublishResponse:
    return LinkedInPublishResponse(
        id=job.id,
        status=job.status,
        linkedin_post_id=job.linkedin_post_id,
        image_urns=job.image_urns,
        message=message,
        scheduled_for_utc=job.scheduled_for_utc,
        display_timezone=job.display_timezone,
    )


def _linkedin_status_code(exc: LinkedInAPIStatusError) -> int:
    return exc.status_code if exc.status_code in {400, 401, 403, 429} else 502


def _raise_linkedin_http_exception(exc: Exception) -> None:
    if isinstance(exc, LinkedInRateLimitError):
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    if isinstance(exc, LinkedInAPIStatusError):
        raise HTTPException(status_code=_linkedin_status_code(exc), detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, (LinkedInTransientError, LinkedInError)):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise HTTPException(status_code=502, detail="Unexpected LinkedIn publishing error.") from exc


def _with_error(base_url: str, error: str) -> str:
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}error={error}"
