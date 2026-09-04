from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from PIL import Image

from app.auth import AuthContext
from app.config import Settings
from app.database import (
    BusinessContextRepository,
    BusinessGenerationContext,
    DatabaseConfigurationError,
    DatabaseUnavailableError,
    PersistGeneratedPostInput,
    PostRepository,
    image_urls_json,
)
from app.openai_clients import generate_caption, generate_image
from app.schemas import ContentTypeEnum, CreatePostRequest, DayEnum, GenerateRequest, PlatformEnum, PublicGenerateResponse
from app.storage import StorageConfigurationError, StorageService, StorageUnavailableError, SupabaseStorageService
from app.validators import validate_day_type_match


class PostGenerationServiceError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True)
class _GeneratedImageUpload:
    public_url: str
    bucket: str
    object_path: str


DAY_BY_NUMBER = {
    1: DayEnum.monday,
    2: DayEnum.tuesday,
    3: DayEnum.wednesday,
    4: DayEnum.thursday,
    5: DayEnum.friday,
    6: DayEnum.saturday,
    7: DayEnum.sunday,
}

CONTENT_TYPE_ALIASES = {
    "educational": ContentTypeEnum.educational,
    "educational post": ContentTypeEnum.educational,
    "educational carousel post": ContentTypeEnum.educational_carousel_post,
    "educational post infographic": ContentTypeEnum.educational_post_infographic,
    "educational post + infographic": ContentTypeEnum.educational_post_infographic,
    "pain point": ContentTypeEnum.pain_point,
    "pain-point": ContentTypeEnum.pain_point,
    "pain point post": ContentTypeEnum.pain_point,
    "pain-point post": ContentTypeEnum.pain_point,
    "case study": ContentTypeEnum.case_study,
    "case study post": ContentTypeEnum.case_study_post,
    "industry insight": ContentTypeEnum.industry_insight,
    "founder authority": ContentTypeEnum.founder_authority,
    "authority post tips post": ContentTypeEnum.authority_post_tips_post,
    "authority post (tips post)": ContentTypeEnum.authority_post_tips_post,
    "automation tip": ContentTypeEnum.automation_tip,
    "client testimonial": ContentTypeEnum.client_testimonial,
    "testimonial post": ContentTypeEnum.testimonial_post,
}


class PostGenerationService:
    def __init__(
        self,
        settings: Settings,
        *,
        context_repository: BusinessContextRepository | None = None,
        post_repository: PostRepository | None = None,
        storage_service: StorageService | None = None,
    ) -> None:
        self._settings = settings
        self._context_repository = context_repository or BusinessContextRepository(settings)
        self._post_repository = post_repository or PostRepository(settings)
        self._storage_service = storage_service or SupabaseStorageService(settings)

    async def create_post(self, payload: CreatePostRequest, auth: AuthContext) -> PublicGenerateResponse:
        context = await asyncio.to_thread(self._load_and_validate_context, payload)
        ai_payload = await asyncio.to_thread(self._build_ai_payload, context, payload.platform)
        caption_result = await asyncio.to_thread(generate_caption, ai_payload, self._settings)
        image_result = await asyncio.to_thread(
            generate_image,
            ai_payload,
            self._settings,
            caption_result.caption,
            caption_result.headline,
        )

        try:
            image_bytes = base64.b64decode(image_result.image_base64, validate=True)
        except Exception as exc:
            raise PostGenerationServiceError(502, "Generated image payload was invalid.") from exc

        post_id = uuid4()
        upload = await asyncio.to_thread(
            self._upload_generated_image,
            business_id=payload.business_id,
            post_id=post_id,
            image_bytes=image_bytes,
            mime_type=image_result.image_mime_type,
        )

        try:
            await asyncio.to_thread(
                self._insert_post_record,
                post_id=post_id,
                payload=payload,
                context=context,
                auth=auth,
                caption=caption_result.caption,
                headline=caption_result.headline,
                image_url=upload.public_url,
                image_mime_type=image_result.image_mime_type,
                alt_text=image_result.alt_text,
                image_model=image_result.model,
            )
        except Exception as exc:
            await asyncio.to_thread(
                self._storage_service.delete_object,
                bucket=upload.bucket,
                object_path=upload.object_path,
            )
            if isinstance(exc, PostGenerationServiceError):
                raise
            raise PostGenerationServiceError(503, "Generated post could not be saved.") from exc

        return PublicGenerateResponse(
            post_id=post_id,
            business_id=payload.business_id,
            weekly_schedule_id=payload.weekly_schedule_id,
            status="generated",
            platform=payload.platform,
            day=DAY_BY_NUMBER[context.day_of_week],
            content_type=_parse_content_type(context.content_type),
            business_name=context.business_name,
            caption=caption_result.caption,
            headline=caption_result.headline,
            image_url=upload.public_url,
            image_urls=[upload.public_url],
            image_mime_type=image_result.image_mime_type,
            alt_text=image_result.alt_text,
        )

    def _load_and_validate_context(self, payload: CreatePostRequest) -> BusinessGenerationContext:
        try:
            if not self._context_repository.business_exists(business_id=payload.business_id):
                raise PostGenerationServiceError(404, "Business not found.")
            schedule_business_id = self._context_repository.fetch_schedule_business_id(
                weekly_schedule_id=payload.weekly_schedule_id,
            )
            if schedule_business_id is None:
                raise PostGenerationServiceError(404, "Weekly schedule not found.")
            if schedule_business_id != payload.business_id:
                raise PostGenerationServiceError(422, "Weekly schedule does not belong to business.")
            context = self._context_repository.fetch_generation_context(
                business_id=payload.business_id,
                weekly_schedule_id=payload.weekly_schedule_id,
            )
        except PostGenerationServiceError:
            raise
        except DatabaseConfigurationError as exc:
            raise PostGenerationServiceError(503, str(exc)) from exc
        except DatabaseUnavailableError as exc:
            raise PostGenerationServiceError(503, "Database is unavailable.") from exc

        if context is None:
            raise PostGenerationServiceError(422, "Business generation context is incomplete.")
        if payload.platform.value not in context.platforms:
            raise PostGenerationServiceError(422, "Selected platform is not configured for this weekly schedule.")
        if context.day_of_week not in DAY_BY_NUMBER:
            raise PostGenerationServiceError(422, "Weekly schedule day_of_week must be between 1 and 7.")
        if not context.business_name:
            raise PostGenerationServiceError(422, "Business generation context is missing business_name.")
        if not context.targeted_audience:
            raise PostGenerationServiceError(422, "Business generation context is missing targeted_audience.")
        if not context.audience_pain_points:
            raise PostGenerationServiceError(422, "Business generation context is missing pain_point.")
        if not context.weekly_topic:
            raise PostGenerationServiceError(422, "Business generation context is missing weekly_topic.")
        if not context.brand_personality:
            raise PostGenerationServiceError(422, "Business generation context is missing brand_personality.")
        content_type = _parse_content_type(context.content_type)
        validate_day_type_match(DAY_BY_NUMBER[context.day_of_week], content_type)
        return context

    def _build_ai_payload(self, context: BusinessGenerationContext, platform: PlatformEnum) -> GenerateRequest:
        return GenerateRequest(
            business_name=context.business_name,
            industry=context.industry,
            offer=context.offer,
            target_audience=context.targeted_audience,
            audience_pain_points=context.audience_pain_points,
            weekly_focus_topic=context.weekly_topic,
            day=DAY_BY_NUMBER[context.day_of_week],
            content_type=_parse_content_type(context.content_type),
            tone=context.tone,
            brand_personality=context.brand_personality,
            cta_preference=context.cta_preferences,
            proof_assets=context.proof_assets,
            company_logo_url=self._resolve_logo_url(context),
            platform=platform,
        )

    def _resolve_logo_url(self, context: BusinessGenerationContext) -> str:
        logo = context.company_logo_url.strip()
        if not logo:
            return ""
        if logo.startswith(("http://", "https://", "data:image")):
            return logo
        if not logo.startswith("/uploads/"):
            return ""

        file_path = _find_local_upload(logo, self._settings.local_uploads_root)
        if file_path is None:
            return ""
        try:
            image_bytes = file_path.read_bytes()
            with Image.open(file_path) as image:
                image.verify()
            mime_type = _mime_type_for_extension(file_path.suffix)
            stored = self._storage_service.upload_business_asset(
                business_id=context.business_id,
                image_bytes=image_bytes,
                mime_type=mime_type,
                extension=file_path.suffix or ".png",
            )
            return stored.public_url
        except Exception:
            return ""

    def _upload_generated_image(
        self,
        *,
        business_id: UUID,
        post_id: UUID,
        image_bytes: bytes,
        mime_type: str,
    ) -> _GeneratedImageUpload:
        try:
            stored = self._storage_service.upload_generated_image(
                business_id=business_id,
                post_id=post_id,
                image_bytes=image_bytes,
                mime_type=mime_type,
            )
        except StorageConfigurationError as exc:
            raise PostGenerationServiceError(503, str(exc)) from exc
        except StorageUnavailableError as exc:
            raise PostGenerationServiceError(503, "Supabase Storage is unavailable.") from exc
        except Exception as exc:
            raise PostGenerationServiceError(503, "Supabase Storage is unavailable.") from exc
        return _GeneratedImageUpload(
            public_url=stored.public_url,
            bucket=stored.bucket,
            object_path=stored.object_path,
        )

    def _insert_post_record(
        self,
        *,
        post_id: UUID,
        payload: CreatePostRequest,
        context: BusinessGenerationContext,
        auth: AuthContext,
        caption: str,
        headline: str,
        image_url: str,
        image_mime_type: str,
        alt_text: str,
        image_model: str,
    ) -> None:
        try:
            self._post_repository.insert_generated_post(
                PersistGeneratedPostInput(
                    post_id=post_id,
                    business_id=payload.business_id,
                    weekly_schedule_id=payload.weekly_schedule_id,
                    platform=payload.platform.value,
                    title=headline,
                    description=caption,
                    hashtags="",
                    image_urls_json=image_urls_json([image_url]),
                    content_type=context.content_type,
                    day_of_week=context.day_of_week,
                    tone=context.tone,
                    offer=context.offer,
                    target_audience=context.targeted_audience,
                    audience_pain_points=context.audience_pain_points,
                    weekly_focus_topics=context.weekly_topic,
                    brand_personality=context.brand_personality,
                    cta=context.cta_preferences,
                    ai_prompt_meta_json=json.dumps(
                        {
                            "provider": self._settings.image_provider,
                            "model": image_model,
                            "alt_text": alt_text,
                            "image_mime_type": image_mime_type,
                            "generation_version": "db-context-v1",
                        },
                        ensure_ascii=True,
                    ),
                    created_by_user_id=_uuid_or_none(auth.user_id),
                )
            )
        except DatabaseConfigurationError as exc:
            raise PostGenerationServiceError(503, str(exc)) from exc
        except DatabaseUnavailableError as exc:
            raise PostGenerationServiceError(503, "Database is unavailable.") from exc


def _parse_content_type(value: str) -> ContentTypeEnum:
    normalized = " ".join(value.replace("-", " ").split()).strip().lower()
    normalized = normalized.replace(" + ", " ")
    content_type = CONTENT_TYPE_ALIASES.get(normalized)
    if content_type is None:
        raise PostGenerationServiceError(422, "Unsupported content type configured on weekly schedule.")
    return content_type


def _find_local_upload(logo_path: str, uploads_root: str) -> Path | None:
    root = Path(uploads_root).resolve()
    relative = logo_path.strip().lstrip("/\\")
    candidates = [
        root / relative,
        root / relative.removeprefix("uploads/").removeprefix("uploads\\"),
    ]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if root in resolved.parents or resolved == root:
            if resolved.is_file():
                return resolved
    return None


def _mime_type_for_extension(extension: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(extension.lower(), "image/png")


def _uuid_or_none(value: str) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None
