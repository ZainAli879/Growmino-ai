from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth import AuthContext, require_auth_context
from app.config import Settings, get_settings
from app.schemas import (
    ErrorResponse,
    FacebookImageUrlPublishRequest,
    FacebookMultiImageUrlPublishRequest,
    FacebookTextPublishRequest,
    InstagramCarouselUrlPublishRequest,
    InstagramImageUrlPublishRequest,
    PublishPlatformEnum,
    PublishResponse,
)
from app.social_publish import (
    MetaPublishError,
    publish_facebook_image_upload,
    publish_facebook_image_url,
    publish_facebook_multi_image_uploads,
    publish_facebook_multi_image_urls,
    publish_facebook_text,
    publish_instagram_carousel_uploads,
    publish_instagram_carousel_urls,
    publish_instagram_image_upload,
    publish_instagram_image_url,
    validate_social_image_bytes,
)

router = APIRouter(prefix="/api/v1")


@router.post(
    "/social/facebook/posts/text",
    response_model=PublishResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def publish_facebook_text_endpoint(
    payload: FacebookTextPublishRequest,
    auth: AuthContext = Depends(require_auth_context),
) -> PublishResponse:
    settings = _settings()
    try:
        result = await asyncio.to_thread(
            publish_facebook_text,
            settings=settings,
            page_id=payload.page_id,
            page_access_token=payload.page_access_token,
            caption=payload.caption,
        )
    except MetaPublishError as exc:
        _raise_meta_http_exception(exc)
    return _response(PublishPlatformEnum.facebook, result)


@router.post(
    "/social/facebook/posts/image-url",
    response_model=PublishResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def publish_facebook_image_url_endpoint(
    payload: FacebookImageUrlPublishRequest,
    auth: AuthContext = Depends(require_auth_context),
) -> PublishResponse:
    settings = _settings()
    try:
        result = await asyncio.to_thread(
            publish_facebook_image_url,
            settings=settings,
            page_id=payload.page_id,
            page_access_token=payload.page_access_token,
            caption=payload.caption,
            image_url=payload.image_url,
        )
    except MetaPublishError as exc:
        _raise_meta_http_exception(exc)
    return _response(PublishPlatformEnum.facebook, result)


@router.post(
    "/social/facebook/posts/image",
    response_model=PublishResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def publish_facebook_image_upload_endpoint(
    page_id: str = Form(..., min_length=1),
    page_access_token: str = Form(..., min_length=1),
    caption: str = Form(..., min_length=1, max_length=63206),
    idempotency_key: str = Form(default=""),
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_auth_context),
) -> PublishResponse:
    settings = _settings()
    try:
        image_bytes = await _read_upload(file, settings.social_max_image_bytes)
        mime_type = validate_social_image_bytes(settings, image_bytes, file.content_type or "", platform="facebook")
        result = await asyncio.to_thread(
            publish_facebook_image_upload,
            settings=settings,
            page_id=page_id,
            page_access_token=page_access_token,
            caption=caption,
            image_bytes=image_bytes,
            mime_type=mime_type,
            file_name=file.filename or "upload.jpg",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MetaPublishError as exc:
        _raise_meta_http_exception(exc)
    return _response(PublishPlatformEnum.facebook, result)


@router.post(
    "/social/facebook/posts/multi-image-url",
    response_model=PublishResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def publish_facebook_multi_image_url_endpoint(
    payload: FacebookMultiImageUrlPublishRequest,
    auth: AuthContext = Depends(require_auth_context),
) -> PublishResponse:
    settings = _settings()
    try:
        result = await asyncio.to_thread(
            publish_facebook_multi_image_urls,
            settings=settings,
            page_id=payload.page_id,
            page_access_token=payload.page_access_token,
            caption=payload.caption,
            image_urls=payload.image_urls,
        )
    except MetaPublishError as exc:
        _raise_meta_http_exception(exc)
    return _response(PublishPlatformEnum.facebook, result)


@router.post(
    "/social/facebook/posts/multi-image",
    response_model=PublishResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def publish_facebook_multi_image_upload_endpoint(
    page_id: str = Form(..., min_length=1),
    page_access_token: str = Form(..., min_length=1),
    caption: str = Form(..., min_length=1, max_length=63206),
    idempotency_key: str = Form(default=""),
    images: list[UploadFile] = File(...),
    auth: AuthContext = Depends(require_auth_context),
) -> PublishResponse:
    settings = _settings()
    if len(images) < 2 or len(images) > 20:
        raise HTTPException(status_code=400, detail="Facebook multi-image posts require 2 to 20 images.")
    try:
        validated = []
        for image in images:
            image_bytes = await _read_upload(image, settings.social_max_image_bytes)
            mime_type = validate_social_image_bytes(settings, image_bytes, image.content_type or "", platform="facebook")
            validated.append((image_bytes, mime_type, image.filename or "upload.jpg"))
        result = await asyncio.to_thread(
            publish_facebook_multi_image_uploads,
            settings=settings,
            page_id=page_id,
            page_access_token=page_access_token,
            caption=caption,
            images=validated,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MetaPublishError as exc:
        _raise_meta_http_exception(exc)
    return _response(PublishPlatformEnum.facebook, result)


@router.post(
    "/social/instagram/posts/image-url",
    response_model=PublishResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def publish_instagram_image_url_endpoint(
    payload: InstagramImageUrlPublishRequest,
    auth: AuthContext = Depends(require_auth_context),
) -> PublishResponse:
    settings = _settings()
    try:
        result = await asyncio.to_thread(
            publish_instagram_image_url,
            settings=settings,
            instagram_business_account_id=payload.instagram_business_account_id,
            instagram_access_token=payload.instagram_access_token,
            caption=payload.caption,
            image_url=payload.image_url,
        )
    except MetaPublishError as exc:
        _raise_meta_http_exception(exc)
    return _response(PublishPlatformEnum.instagram, result)


@router.post(
    "/social/instagram/posts/image",
    response_model=PublishResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def publish_instagram_image_upload_endpoint(
    instagram_business_account_id: str = Form(..., min_length=1),
    instagram_access_token: str = Form(..., min_length=1),
    caption: str = Form(..., min_length=1, max_length=2200),
    idempotency_key: str = Form(default=""),
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_auth_context),
) -> PublishResponse:
    settings = _settings()
    try:
        image_bytes = await _read_upload(file, settings.social_max_image_bytes)
        mime_type = validate_social_image_bytes(settings, image_bytes, file.content_type or "", platform="instagram")
        result = await asyncio.to_thread(
            publish_instagram_image_upload,
            settings=settings,
            instagram_business_account_id=instagram_business_account_id,
            instagram_access_token=instagram_access_token,
            caption=caption,
            image_bytes=image_bytes,
            mime_type=mime_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MetaPublishError as exc:
        _raise_meta_http_exception(exc)
    return _response(PublishPlatformEnum.instagram, result)


@router.post(
    "/social/instagram/posts/carousel-url",
    response_model=PublishResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def publish_instagram_carousel_url_endpoint(
    payload: InstagramCarouselUrlPublishRequest,
    auth: AuthContext = Depends(require_auth_context),
) -> PublishResponse:
    settings = _settings()
    try:
        result = await asyncio.to_thread(
            publish_instagram_carousel_urls,
            settings=settings,
            instagram_business_account_id=payload.instagram_business_account_id,
            instagram_access_token=payload.instagram_access_token,
            caption=payload.caption,
            image_urls=payload.image_urls,
        )
    except MetaPublishError as exc:
        _raise_meta_http_exception(exc)
    return _response(PublishPlatformEnum.instagram, result)


@router.post(
    "/social/instagram/posts/carousel",
    response_model=PublishResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def publish_instagram_carousel_upload_endpoint(
    instagram_business_account_id: str = Form(..., min_length=1),
    instagram_access_token: str = Form(..., min_length=1),
    caption: str = Form(..., min_length=1, max_length=2200),
    idempotency_key: str = Form(default=""),
    images: list[UploadFile] = File(...),
    auth: AuthContext = Depends(require_auth_context),
) -> PublishResponse:
    settings = _settings()
    if len(images) < 2 or len(images) > 10:
        raise HTTPException(status_code=400, detail="Instagram carousel posts require 2 to 10 images.")
    try:
        validated = []
        for image in images:
            image_bytes = await _read_upload(image, settings.social_max_image_bytes)
            mime_type = validate_social_image_bytes(settings, image_bytes, image.content_type or "", platform="instagram")
            validated.append((image_bytes, mime_type))
        result = await asyncio.to_thread(
            publish_instagram_carousel_uploads,
            settings=settings,
            instagram_business_account_id=instagram_business_account_id,
            instagram_access_token=instagram_access_token,
            caption=caption,
            images=validated,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MetaPublishError as exc:
        _raise_meta_http_exception(exc)
    return _response(PublishPlatformEnum.instagram, result)


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


def _response(platform: PublishPlatformEnum, result) -> PublishResponse:
    return PublishResponse(
        platform=platform,
        published=result.published,
        post_id=result.post_id,
        creation_id=result.creation_id,
        message=result.message,
        image_url_used=result.image_url_used,
        image_urls_used=result.image_urls_used,
        child_creation_ids=result.child_creation_ids,
        photo_ids=result.photo_ids,
    )


def _raise_meta_http_exception(exc: MetaPublishError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
