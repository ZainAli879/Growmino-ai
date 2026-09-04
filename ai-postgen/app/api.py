from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAIError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api_security import ApiSecurityMiddleware, api_error_payload
from app.auth import AuthContext, require_auth_context
from app.config import Settings, get_settings
from app.linkedin_api import router as linkedin_router
from app.linkedin_client import build_authorization_url, create_state_token, oauth_expiry
from app.linkedin_store import get_publish_job
from app.linkedin_store import insert_oauth_state
from app.openai_clients import generate_caption, generate_content_plan, generate_image
from app.post_generation_service import PostGenerationService, PostGenerationServiceError
from app.schemas import (
    ContentPlanResponse,
    CreatePostRequest,
    ErrorResponse,
    GenerateRequest,
    GenerateResponse,
    GeneratedPostSummary,
    GeneratedPostsResponse,
    LinkedInPostStatus,
    MetaInfo,
    OpenAIImageInfo,
    PublicContentPlanResponse,
    PublicContentPlanPost,
    PublicGenerateResponse,
    QAInfo,
    TraceInfo,
    WeeklyContentPlanRequest,
)
from app.social_api import router as social_router
from app.utils import append_jsonl, ensure_outputs_dir
from app.validators import (
    heuristic_no_fabricated_numbers_if_no_proof,
    validate_day_type_match,
    validate_has_hook_and_cta,
    validate_hashtag_count,
    validate_word_count,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()
    yield


_api_docs_enabled = os.getenv("EXPOSE_API_DOCS", "").strip().lower()
if _api_docs_enabled:
    _api_docs_enabled_bool = _api_docs_enabled in {"1", "true", "yes", "on"}
else:
    _api_docs_enabled_bool = os.getenv("ENVIRONMENT", "development").strip().lower() != "production"

app = FastAPI(
    title="AI Post Generator",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if _api_docs_enabled_bool else None,
    redoc_url="/redoc" if _api_docs_enabled_bool else None,
    openapi_url="/openapi.json" if _api_docs_enabled_bool else None,
)

_cors_allow_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    if origin.strip()
]
_outputs_dir = ensure_outputs_dir(os.getenv("OUTPUTS_DIR", "./outputs").strip() or "./outputs")
app.add_middleware(ApiSecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if os.getenv("EXPOSE_OUTPUTS", "false").strip().lower() in {"1", "true", "yes", "on"}:
    app.mount("/outputs", StaticFiles(directory=_outputs_dir), name="outputs")
app.include_router(linkedin_router)
app.include_router(social_router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = _request_id_from_state(request)
    message = _error_message(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=api_error_payload(
            code=_error_code_for_status(exc.status_code),
            message=message,
            request_id=request_id,
        ),
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = _request_id_from_state(request)
    return JSONResponse(
        status_code=422,
        content=api_error_payload(
            code="VALIDATION_ERROR",
            message=_validation_error_message(exc),
            request_id=request_id,
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id_from_state(request)
    return JSONResponse(
        status_code=500,
        content=api_error_payload(
            code="INTERNAL_SERVER_ERROR",
            message="Unexpected server error.",
            request_id=request_id,
        ),
    )


@app.get("/test-ui", include_in_schema=False)
async def test_ui() -> FileResponse:
    if not _test_ui_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(Path(__file__).resolve().parent / "static" / "test-ui.html")


@app.get("/test-ui/linkedin/connect", include_in_schema=False)
async def test_ui_linkedin_connect(
    user_id: str = Query(default="local-user"),
    business_id: str = Query(default="local-business"),
) -> RedirectResponse:
    if not _test_ui_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    try:
        settings = get_settings()
        state, state_hash = create_state_token()
        await asyncio.to_thread(
            insert_oauth_state,
            settings,
            state_hash=state_hash,
            user_id=user_id.strip() or "local-user",
            business_id=business_id.strip() or "local-business",
            expires_at=oauth_expiry(settings),
            redirect_after=settings.linkedin_frontend_success_url,
        )
        return RedirectResponse(build_authorization_url(settings, state))
    except Exception:
        return RedirectResponse("/test-ui?linkedin=error")


@app.get("/api/v1/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/v1/posts",
    response_model=PublicGenerateResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def create_post_endpoint(
    payload: CreatePostRequest,
    auth: AuthContext = Depends(require_auth_context),
) -> PublicGenerateResponse:
    settings: Settings
    try:
        settings = get_settings()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Service configuration error.") from exc

    try:
        service = PostGenerationService(settings)
        return await asyncio.wait_for(service.create_post(payload, auth), timeout=settings.request_timeout_seconds)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=502, detail="Generation timed out. Please retry.") from exc
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail="OpenAI service error while generating content.") from exc
    except PostGenerationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unexpected generation error.") from exc


@app.get(
    "/api/v1/posts",
    response_model=GeneratedPostsResponse,
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def list_posts_endpoint(
    limit: int = Query(default=50, ge=1, le=100),
    auth: AuthContext = Depends(require_auth_context),
) -> GeneratedPostsResponse:
    return GeneratedPostsResponse(posts=[])


@app.get(
    "/api/v1/posts/{post_id}",
    response_model=GeneratedPostSummary | LinkedInPostStatus,
    responses={404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def get_post_endpoint(
    post_id: str,
    auth: AuthContext = Depends(require_auth_context),
) -> GeneratedPostSummary | LinkedInPostStatus:
    try:
        settings = get_settings()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Service configuration error.") from exc

    try:
        linkedin_post = await asyncio.to_thread(
            get_publish_job,
            settings,
            post_id=post_id,
            user_id=auth.user_id,
            business_id=auth.business_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not load LinkedIn post.") from exc

    if linkedin_post is not None:
        return linkedin_post

    raise HTTPException(status_code=404, detail="Post not found.")


@app.post(
    "/api/v1/content-plans",
    response_model=PublicContentPlanResponse | ContentPlanResponse,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def create_content_plan_endpoint(
    payload: WeeklyContentPlanRequest,
    request: Request,
    debug: bool = Query(default=False, description="Return internal planning and generated_* fields."),
    auth: AuthContext = Depends(require_auth_context),
) -> PublicContentPlanResponse | ContentPlanResponse:
    try:
        settings = get_settings()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Service configuration error.") from exc

    plan_id = str(uuid4())
    try:
        recent_posts = "none"
        plan = await asyncio.wait_for(
            asyncio.to_thread(generate_content_plan, payload, settings, plan_id, recent_posts),
            timeout=settings.request_timeout_seconds,
        )
        await _generate_posts_for_plan(plan, payload, settings)
        for item in plan.items:
            if item.generated_image_url:
                item.generated_image_url = _absolute_public_url(item.generated_image_url, request, settings)
        plan.status = "generated" if all(item.generation_status == "completed" for item in plan.items) else "partially_generated"
        if debug:
            return plan
        return _public_content_plan_response(plan, payload)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=502, detail="Content plan generation timed out. Please retry.") from exc
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail="OpenAI service error while generating content plan.") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unexpected content plan generation error.") from exc


async def _run_generation(payload: GenerateRequest, settings: Settings) -> GenerateResponse:
    trace_id = str(uuid4())
    started_at = datetime.now(timezone.utc).isoformat()
    total_started = perf_counter()

    text_model = settings.openrouter_text_model if settings.text_provider == "openrouter" else settings.caption_model

    caption_started = perf_counter()
    caption_result = await asyncio.to_thread(generate_caption, payload, settings)
    caption_elapsed_ms = int((perf_counter() - caption_started) * 1000)

    image_started = perf_counter()
    image_result = await asyncio.to_thread(
        generate_image,
        payload,
        settings,
        caption_result.caption,
        caption_result.headline,
    )
    image_elapsed_ms = int((perf_counter() - image_started) * 1000)
    total_elapsed_ms = int((perf_counter() - total_started) * 1000)

    word_count, platform_limits_ok = validate_word_count(caption_result.caption, payload.platform)
    has_hook, _ = validate_has_hook_and_cta(caption_result.caption, payload.platform)
    no_fabricated_claims = heuristic_no_fabricated_numbers_if_no_proof(caption_result.caption, payload.proof_assets)
    hashtag_count, hashtag_count_ok = validate_hashtag_count(caption_result.caption, payload.platform)

    warnings: list[str] = []
    if not platform_limits_ok:
        warnings.append("Caption word count is outside platform limit.")
    if not has_hook:
        warnings.append("Caption hook is weak or missing in first lines.")
    if not no_fabricated_claims:
        warnings.append("Caption may include unverified numeric claim.")
    if not hashtag_count_ok:
        warnings.append("Hashtag count is outside platform range.")

    qa = QAInfo(
        word_count=word_count,
        platform_limits_ok=platform_limits_ok,
        has_hook=has_hook,
        no_fabricated_claims=no_fabricated_claims,
        safety_ok=True,
        image_has_no_text_requirement=False,
        hashtag_count=hashtag_count,
        hashtag_count_ok=hashtag_count_ok,
        warnings=warnings,
    )

    trace = TraceInfo(
        trace_id=trace_id,
        request_started_at=started_at,
        elapsed_ms_total=total_elapsed_ms,
        elapsed_ms_caption=caption_elapsed_ms,
        elapsed_ms_image_prompt_and_generation=image_elapsed_ms,
        text_provider=settings.text_provider,
        text_model=text_model,
        image_provider=settings.image_provider,
        image_model=image_result.model,
    )

    image_data_url = f"{image_result.image_mime_type};base64,{image_result.image_base64}"
    image_data_url = f"data:{image_data_url}"
    append_jsonl(
        settings.traces_file,
        {
            "trace_id": trace_id,
            "request_started_at": started_at,
            "meta": {
                "platform": payload.platform.value,
                "day": payload.day.value,
                "content_type": payload.content_type.value,
                "business_name": payload.business_name,
            },
            "caption": caption_result.caption,
            "headline": caption_result.headline,
            "image_prompt_used": image_result.prompt_used,
            "qa": qa.model_dump(),
            "timings_ms": {
                "total": total_elapsed_ms,
                "caption": caption_elapsed_ms,
                "image_prompt_and_generation": image_elapsed_ms,
            },
            "provider": settings.image_provider,
            "model": image_result.model,
            "text_provider": settings.text_provider,
            "text_model": text_model,
            "post_id": trace_id,
            "image_mime_type": image_result.image_mime_type,
        },
    )

    response = GenerateResponse(
        post_id=trace_id,
        meta=MetaInfo(
            platform=payload.platform,
            day=payload.day,
            content_type=payload.content_type,
            business_name=payload.business_name,
        ),
        caption=caption_result.caption,
        headline=caption_result.headline,
        openai_image=OpenAIImageInfo(
            model=image_result.model,
            size=image_result.size,
            style=image_result.style,
            prompt_used=image_result.prompt_used,
            negative_prompt_used=image_result.negative_prompt_used,
            file_path=image_result.file_path,
            public_url="",
            image_data_url=image_data_url,
            image_base64=image_result.image_base64,
            image_mime_type=image_result.image_mime_type,
            alt_text=image_result.alt_text,
        ),
        qa=qa,
        trace=trace,
    )
    return response


async def _generate_posts_for_plan(
    plan: ContentPlanResponse,
    payload: WeeklyContentPlanRequest,
    settings: Settings,
) -> None:
    for item in plan.items:
        item.generation_status = "generating"
        generation_payload = GenerateRequest(
            business_name=payload.business_name,
            industry=payload.industry,
            offer=payload.offer,
            target_audience=payload.target_audience,
            audience_pain_points=payload.audience_pain_points,
            weekly_focus_topic=(
                f"{item.topic}. Angle: {item.angle}. "
                f"Hook direction: {item.hook_direction}. "
                f"Visual direction: {item.visual_direction}"
            ),
            day=item.day,
            content_type=item.content_type,
            tone=payload.tone,
            brand_personality=payload.brand_personality,
            cta_preference=item.cta_direction or payload.cta_preference,
            proof_assets=payload.proof_assets,
            company_logo_url=payload.company_logo_url,
            platform=item.platform,
        )

        try:
            generated = await _run_generation(generation_payload, settings)
            item.generation_status = "completed"
            item.generated_post_id = generated.post_id
            item.generated_caption = generated.caption
            item.generated_headline = generated.headline
            item.generated_image_url = generated.openai_image.public_url
            item.generated_image_data_url = generated.openai_image.image_data_url
            item.generated_image_base64 = generated.openai_image.image_base64
            item.generated_image_mime_type = generated.openai_image.image_mime_type
            item.generated_alt_text = generated.openai_image.alt_text
            item.generation_error = ""
        except Exception as exc:
            item.generation_status = "failed"
            item.generation_error = str(exc)


def _public_generate_response(
    result: GenerateResponse,
    request: Request,
    settings: Settings,
) -> PublicGenerateResponse:
    return PublicGenerateResponse(
        post_id=result.post_id,
        platform=result.meta.platform,
        day=result.meta.day,
        content_type=result.meta.content_type,
        business_name=result.meta.business_name,
        caption=result.caption,
        headline=result.headline,
        image_url=result.openai_image.public_url,
        image_data_url=result.openai_image.image_data_url,
        image_base64=result.openai_image.image_base64,
        image_mime_type=result.openai_image.image_mime_type,
        alt_text=result.openai_image.alt_text,
    )


def _public_content_plan_response(
    plan: ContentPlanResponse,
    payload: WeeklyContentPlanRequest,
) -> PublicContentPlanResponse:
    return PublicContentPlanResponse(
        plan_id=plan.plan_id,
        status=plan.status,
        week_start_date=plan.week_start_date,
        weekly_goal=plan.weekly_goal,
        theme=plan.theme,
        total_posts=plan.total_posts,
        posts=[
            PublicContentPlanPost(
                position=item.position,
                post_id=item.generated_post_id,
                status=item.generation_status,
                platform=item.platform,
                day=item.day,
                content_type=item.content_type,
                business_name=payload.business_name,
                topic=item.topic,
                caption=item.generated_caption,
                headline=item.generated_headline,
                image_url=item.generated_image_url,
                image_base64=item.generated_image_base64,
                image_data_url=item.generated_image_data_url,
                image_mime_type=item.generated_image_mime_type,
                alt_text=item.generated_alt_text,
                error=item.generation_error,
            )
            for item in plan.items
        ],
    )


def _absolute_public_url(value: str, request: Request, settings: Settings) -> str:
    if value.startswith(("http://", "https://")):
        return value
    base_url = settings.public_base_url or str(request.base_url).rstrip("/")
    return f"{base_url}/{value.lstrip('/')}"


def _request_id_from_state(request: Request) -> str:
    return str(getattr(request.state, "request_id", "") or uuid4())


def _error_message(detail: object) -> str:
    if isinstance(detail, str):
        return detail
    return "Request failed."


def _error_code_for_status(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "REQUEST_BODY_TOO_LARGE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_SERVER_ERROR",
        502: "UPSTREAM_SERVICE_ERROR",
        503: "SERVICE_UNAVAILABLE",
        504: "UPSTREAM_TIMEOUT",
    }.get(status_code, "REQUEST_FAILED")


def _validation_error_message(exc: RequestValidationError) -> str:
    first_error = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in first_error.get("loc", []) if part != "body")
    message = str(first_error.get("msg") or "Invalid request.")
    if location:
        return f"{location}: {message}"
    return message


def _test_ui_enabled() -> bool:
    try:
        return get_settings().expose_test_ui
    except Exception:
        explicit_value = os.getenv("EXPOSE_TEST_UI", "").strip().lower()
        if explicit_value:
            return explicit_value in {"1", "true", "yes", "on"}
        return os.getenv("ENVIRONMENT", "development").strip().lower() != "production"
