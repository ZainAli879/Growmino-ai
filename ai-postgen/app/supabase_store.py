from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import mimetypes
from pathlib import Path
from uuid import uuid4

from app.config import Settings
from app.schemas import GenerateRequest, GeneratedPostSummary, QAInfo, TraceInfo
from app.utils import sanitize_filename_part


@dataclass(frozen=True)
class PersistedPost:
    post_id: str = ""
    image_url: str = ""


def is_supabase_enabled(settings: Settings) -> bool:
    return bool(
        settings.supabase_url
        and settings.supabase_secret_key
        and settings.supabase_storage_bucket
    )


def _client(settings: Settings):
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is missing.")
    if not settings.supabase_secret_key:
        raise RuntimeError("SUPABASE_SECRET_KEY is missing.")
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError("Supabase package is not installed. Run: pip install supabase") from exc
    return create_client(settings.supabase_url, settings.supabase_secret_key)


def _upload_image(file_path: str, payload: GenerateRequest, settings: Settings) -> str:
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise RuntimeError(f"Generated image file not found: {file_path}")

    extension = path.suffix.lower() or ".png"
    object_name = (
        f"{datetime.now(timezone.utc).strftime('%Y/%m/%d')}/"
        f"{sanitize_filename_part(payload.business_name)}/"
        f"{sanitize_filename_part(payload.platform.value)}-"
        f"{uuid4().hex}{extension}"
    )
    content_type = mimetypes.guess_type(str(path))[0] or "image/png"

    client = _client(settings)
    bucket = client.storage.from_(settings.supabase_storage_bucket)
    with path.open("rb") as image_file:
        bucket.upload(
            path=object_name,
            file=image_file,
            file_options={
                "content-type": content_type,
                "cache-control": "3600",
                "upsert": "false",
            },
        )
    return bucket.get_public_url(object_name)


def persist_generated_post(
    *,
    payload: GenerateRequest,
    settings: Settings,
    caption: str,
    headline: str,
    image_model: str,
    image_size: str,
    image_prompt: str,
    image_file_path: str,
    fallback_public_url: str,
    alt_text: str,
    qa: QAInfo,
    trace: TraceInfo,
) -> PersistedPost:
    if not is_supabase_enabled(settings):
        return PersistedPost(image_url=fallback_public_url)

    image_url = _upload_image(image_file_path, payload, settings)
    record = {
        "scheduled_date": None,
        "platform": payload.platform.value,
        "day": payload.day.value,
        "content_type": payload.content_type.value,
        "topic": payload.weekly_focus_topic,
        "caption": caption,
        "headline": headline,
        "image_prompt": image_prompt,
        "image_url": image_url,
        "image_file_path": image_file_path,
        "alt_text": alt_text,
        "status": "completed",
        "error_message": None,
        "qa": qa.model_dump(mode="json"),
        "trace": {
            **trace.model_dump(mode="json"),
            "business_name": payload.business_name,
            "industry": payload.industry,
            "offer": payload.offer,
            "target_audience": payload.target_audience,
            "image_model": image_model,
            "image_size": image_size,
        },
    }

    response = _client(settings).table("generated_posts").insert(record).execute()
    data = getattr(response, "data", None)
    post_id = ""
    if isinstance(data, list) and data:
        post_id = str(data[0].get("id", "")).strip()
    elif isinstance(data, dict):
        post_id = str(data.get("id", "")).strip()

    return PersistedPost(post_id=post_id, image_url=image_url)


def list_generated_posts(settings: Settings, limit: int = 50) -> list[GeneratedPostSummary]:
    if not is_supabase_enabled(settings):
        raise RuntimeError("Supabase is not configured.")

    safe_limit = min(max(limit, 1), 100)
    response = (
        _client(settings)
        .table("generated_posts")
        .select(
            "id,platform,day,content_type,topic,caption,headline,image_url,"
            "image_file_path,alt_text,status,created_at,updated_at"
        )
        .order("created_at", desc=True)
        .limit(safe_limit)
        .execute()
    )
    data = getattr(response, "data", []) or []
    if not isinstance(data, list):
        return []

    posts: list[GeneratedPostSummary] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        posts.append(
            GeneratedPostSummary(
                id=str(item.get("id", "") or ""),
                platform=str(item.get("platform", "") or ""),
                day=str(item.get("day", "") or ""),
                content_type=str(item.get("content_type", "") or ""),
                topic=str(item.get("topic", "") or ""),
                caption=str(item.get("caption", "") or ""),
                headline=str(item.get("headline", "") or ""),
                image_url=str(item.get("image_url", "") or ""),
                image_file_path=str(item.get("image_file_path", "") or ""),
                alt_text=str(item.get("alt_text", "") or ""),
                status=str(item.get("status", "") or ""),
                created_at=str(item.get("created_at", "") or ""),
                updated_at=str(item.get("updated_at", "") or ""),
            )
        )
    return posts


def get_generated_post(settings: Settings, post_id: str) -> GeneratedPostSummary | None:
    if not is_supabase_enabled(settings):
        raise RuntimeError("Supabase is not configured.")

    response = (
        _client(settings)
        .table("generated_posts")
        .select(
            "id,platform,day,content_type,topic,caption,headline,image_url,"
            "image_file_path,alt_text,status,created_at,updated_at"
        )
        .eq("id", post_id)
        .limit(1)
        .execute()
    )
    data = getattr(response, "data", []) or []
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return None

    item = data[0]
    return GeneratedPostSummary(
        id=str(item.get("id", "") or ""),
        platform=str(item.get("platform", "") or ""),
        day=str(item.get("day", "") or ""),
        content_type=str(item.get("content_type", "") or ""),
        topic=str(item.get("topic", "") or ""),
        caption=str(item.get("caption", "") or ""),
        headline=str(item.get("headline", "") or ""),
        image_url=str(item.get("image_url", "") or ""),
        image_file_path=str(item.get("image_file_path", "") or ""),
        alt_text=str(item.get("alt_text", "") or ""),
        status=str(item.get("status", "") or ""),
        created_at=str(item.get("created_at", "") or ""),
        updated_at=str(item.get("updated_at", "") or ""),
    )
