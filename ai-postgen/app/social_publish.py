from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from io import BytesIO
from time import sleep
import json

from PIL import Image, UnidentifiedImageError
import requests

from app.config import Settings
from app.schemas import PublishRequest

SOCIAL_IMAGE_FORMAT_TO_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "GIF": "image/gif", "WEBP": "image/webp"}
FACEBOOK_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
INSTAGRAM_IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}


@dataclass(frozen=True)
class PublishResult:
    platform: str
    published: bool
    post_id: str = ""
    creation_id: str = ""
    message: str = ""
    image_url_used: str = ""
    drive_image_url: str = ""
    image_urls_used: list[str] = field(default_factory=list)
    child_creation_ids: list[str] = field(default_factory=list)
    photo_ids: list[str] = field(default_factory=list)


class MetaPublishError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _graph_url(settings: Settings, resource: str) -> str:
    version = (settings.meta_graph_api_version or "v25.0").strip()
    return f"https://graph.facebook.com/{version}/{resource.lstrip('/')}"


def _post_form(url: str, data: dict[str, str], settings: Settings) -> dict:
    try:
        response = requests.post(url, data=data, timeout=settings.request_timeout_seconds)
        payload = response.json()
    except ValueError:
        payload = {"error": {"message": response.text.strip() or "Unknown Meta API error."}}
    except requests.RequestException as exc:
        raise RuntimeError("Meta publishing request failed.") from exc

    if not response.ok:
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = str(error.get("message", "")).strip() or f"Meta API request failed with status {response.status_code}."
        raise RuntimeError(message)
    return payload if isinstance(payload, dict) else {}


def _meta_request(
    method: str,
    url: str,
    *,
    token: str,
    settings: Settings,
    data: dict[str, str] | None = None,
    files: dict | None = None,
) -> dict:
    try:
        response = requests.request(
            method,
            url,
            data=data,
            files=files,
            headers={"Authorization": f"Bearer {token}"},
            timeout=settings.request_timeout_seconds,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {"error": {"message": response.text.strip() or "Unknown Meta API error."}}
    except requests.RequestException as exc:
        raise MetaPublishError("Meta publishing request failed.", status_code=502) from exc

    if not response.ok:
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = str(error.get("message", "")).strip() or f"Meta API request failed with status {response.status_code}."
        status_code = response.status_code if response.status_code in {400, 401, 403, 429} else 502
        raise MetaPublishError(message, status_code=status_code)
    return payload if isinstance(payload, dict) else {}


def _get_meta(url: str, *, token: str, settings: Settings) -> dict:
    return _meta_request("GET", url, token=token, settings=settings)


def _post_meta_form(url: str, *, token: str, settings: Settings, data: dict[str, str], files: dict | None = None) -> dict:
    return _meta_request("POST", url, token=token, settings=settings, data=data, files=files)


def _resolve_facebook_credentials(payload: PublishRequest, settings: Settings) -> tuple[str, str]:
    page_id = payload.facebook_page_id.strip() or settings.facebook_page_id.strip()
    token = (
        payload.facebook_access_token.strip()
        or payload.access_token.strip()
        or settings.facebook_access_token.strip()
        or settings.meta_access_token.strip()
    )
    if not page_id:
        raise RuntimeError("Facebook Page ID is required.")
    if not token:
        raise RuntimeError("Facebook access token is required.")
    return page_id, token


def _resolve_instagram_credentials(payload: PublishRequest, settings: Settings) -> tuple[str, str]:
    account_id = payload.instagram_business_account_id.strip() or settings.instagram_business_account_id.strip()
    token = (
        payload.instagram_access_token.strip()
        or payload.access_token.strip()
        or settings.instagram_access_token.strip()
        or settings.meta_access_token.strip()
    )
    if not account_id:
        raise RuntimeError("Instagram business account ID is required.")
    if not token:
        raise RuntimeError("Instagram access token is required.")
    return account_id, token


def _resolve_image_inputs(payload: PublishRequest) -> str:
    image_url = payload.image_url.strip()
    if image_url:
        if not image_url.startswith(("http://", "https://")):
            raise RuntimeError("image_url must be a public HTTP or HTTPS URL.")
        return image_url
    if payload.image_file_path.strip():
        raise RuntimeError("image_file_path is no longer supported. Upload/store images on the client side and pass a public image_url.")
    return ""


def publish_to_meta(payload: PublishRequest, settings: Settings) -> PublishResult:
    platform = payload.platform.value
    image_url_used = _resolve_image_inputs(payload)

    if platform == "facebook":
        page_id, token = _resolve_facebook_credentials(payload, settings)
        if image_url_used:
            result = _post_form(
                _graph_url(settings, f"{page_id}/photos"),
                {
                    "published": "true",
                    "url": image_url_used,
                    "caption": payload.caption,
                    "access_token": token,
                },
                settings,
            )
            return PublishResult(
                platform=platform,
                published=True,
                post_id=str(result.get("post_id", "") or result.get("id", "")),
                message="Published image post to Facebook.",
                image_url_used=image_url_used,
            )

        result = _post_form(
            _graph_url(settings, f"{page_id}/feed"),
            {
                "message": payload.caption,
                "access_token": token,
            },
            settings,
        )
        return PublishResult(
            platform=platform,
            published=True,
            post_id=str(result.get("id", "")),
            message="Published text post to Facebook.",
        )

    if platform == "instagram":
        account_id, token = _resolve_instagram_credentials(payload, settings)
        if not image_url_used:
            raise RuntimeError("Instagram publishing requires a public image_url.")

        container = _post_form(
            _graph_url(settings, f"{account_id}/media"),
            {
                "image_url": image_url_used,
                "caption": payload.caption,
                "access_token": token,
            },
            settings,
        )
        creation_id = str(container.get("id", "")).strip()
        if not creation_id:
            raise RuntimeError("Instagram media container was created without an id.")

        published = _post_form(
            _graph_url(settings, f"{account_id}/media_publish"),
            {
                "creation_id": creation_id,
                "access_token": token,
            },
            settings,
        )
        return PublishResult(
            platform=platform,
            published=True,
            post_id=str(published.get("id", "")),
            creation_id=creation_id,
            message="Published image post to Instagram.",
            image_url_used=image_url_used,
        )

    raise RuntimeError("Only Facebook and Instagram publishing are currently supported.")


def publish_facebook_text(*, settings: Settings, page_id: str, page_access_token: str, caption: str) -> PublishResult:
    _require_value(page_id, "Facebook Page ID is required.")
    _require_value(page_access_token, "Facebook Page access token is required.")
    result = _post_meta_form(
        _graph_url(settings, f"{page_id}/feed"),
        token=page_access_token,
        settings=settings,
        data={"message": caption},
    )
    return PublishResult(platform="facebook", published=True, post_id=str(result.get("id", "")), message="Published text post to Facebook.")


def publish_facebook_image_url(
    *,
    settings: Settings,
    page_id: str,
    page_access_token: str,
    caption: str,
    image_url: str,
) -> PublishResult:
    _require_value(page_id, "Facebook Page ID is required.")
    _require_value(page_access_token, "Facebook Page access token is required.")
    _require_https_url(image_url)
    result = _post_meta_form(
        _graph_url(settings, f"{page_id}/photos"),
        token=page_access_token,
        settings=settings,
        data={"url": image_url, "caption": caption, "published": "true"},
    )
    return PublishResult(
        platform="facebook",
        published=True,
        post_id=str(result.get("post_id", "") or result.get("id", "")),
        message="Published image post to Facebook.",
        image_url_used=image_url,
        image_urls_used=[image_url],
    )


def publish_facebook_image_upload(
    *,
    settings: Settings,
    page_id: str,
    page_access_token: str,
    caption: str,
    image_bytes: bytes,
    mime_type: str,
    file_name: str,
) -> PublishResult:
    _require_value(page_id, "Facebook Page ID is required.")
    _require_value(page_access_token, "Facebook Page access token is required.")
    result = _post_facebook_photo_upload(
        settings=settings,
        page_id=page_id,
        page_access_token=page_access_token,
        caption=caption,
        image_bytes=image_bytes,
        mime_type=mime_type,
        file_name=file_name,
        published=True,
    )
    return PublishResult(
        platform="facebook",
        published=True,
        post_id=str(result.get("post_id", "") or result.get("id", "")),
        message="Published uploaded image post to Facebook.",
    )


def publish_facebook_multi_image_urls(
    *,
    settings: Settings,
    page_id: str,
    page_access_token: str,
    caption: str,
    image_urls: list[str],
) -> PublishResult:
    _validate_count(image_urls, minimum=2, maximum=20, label="Facebook multi-image posts")
    photo_ids = [
        _create_facebook_unpublished_photo_url(
            settings=settings,
            page_id=page_id,
            page_access_token=page_access_token,
            image_url=image_url,
        )
        for image_url in image_urls
    ]
    post_id = _publish_facebook_attached_media_post(
        settings=settings,
        page_id=page_id,
        page_access_token=page_access_token,
        caption=caption,
        photo_ids=photo_ids,
    )
    return PublishResult(
        platform="facebook",
        published=True,
        post_id=post_id,
        message="Published multi-image post to Facebook.",
        image_urls_used=image_urls,
        photo_ids=photo_ids,
    )


def publish_facebook_multi_image_uploads(
    *,
    settings: Settings,
    page_id: str,
    page_access_token: str,
    caption: str,
    images: list[tuple[bytes, str, str]],
) -> PublishResult:
    _validate_count(images, minimum=2, maximum=20, label="Facebook multi-image posts")
    photo_ids = [
        _post_facebook_photo_upload(
            settings=settings,
            page_id=page_id,
            page_access_token=page_access_token,
            caption="",
            image_bytes=image_bytes,
            mime_type=mime_type,
            file_name=file_name,
            published=False,
        ).get("id", "")
        for image_bytes, mime_type, file_name in images
    ]
    photo_ids = [str(photo_id) for photo_id in photo_ids if str(photo_id)]
    if len(photo_ids) != len(images):
        raise MetaPublishError("Facebook did not return every uploaded photo ID.", status_code=502)
    post_id = _publish_facebook_attached_media_post(
        settings=settings,
        page_id=page_id,
        page_access_token=page_access_token,
        caption=caption,
        photo_ids=photo_ids,
    )
    return PublishResult(platform="facebook", published=True, post_id=post_id, message="Published uploaded multi-image post to Facebook.", photo_ids=photo_ids)


def publish_instagram_image_url(
    *,
    settings: Settings,
    instagram_business_account_id: str,
    instagram_access_token: str,
    caption: str,
    image_url: str,
) -> PublishResult:
    _require_value(instagram_business_account_id, "Instagram business account ID is required.")
    _require_value(instagram_access_token, "Instagram access token is required.")
    _require_https_url(image_url)
    container_id = _create_instagram_image_container(
        settings=settings,
        account_id=instagram_business_account_id,
        token=instagram_access_token,
        image_url=image_url,
        caption=caption,
    )
    _wait_for_instagram_container(settings=settings, token=instagram_access_token, creation_id=container_id)
    post_id = _publish_instagram_container(settings=settings, account_id=instagram_business_account_id, token=instagram_access_token, creation_id=container_id)
    return PublishResult(
        platform="instagram",
        published=True,
        post_id=post_id,
        creation_id=container_id,
        message="Published image post to Instagram.",
        image_url_used=image_url,
        image_urls_used=[image_url],
    )


def publish_instagram_image_upload(
    *,
    settings: Settings,
    instagram_business_account_id: str,
    instagram_access_token: str,
    caption: str,
    image_bytes: bytes,
    mime_type: str,
) -> PublishResult:
    image_url = save_public_social_upload(settings, image_bytes=image_bytes, mime_type=mime_type)
    return publish_instagram_image_url(
        settings=settings,
        instagram_business_account_id=instagram_business_account_id,
        instagram_access_token=instagram_access_token,
        caption=caption,
        image_url=image_url,
    )


def publish_instagram_carousel_urls(
    *,
    settings: Settings,
    instagram_business_account_id: str,
    instagram_access_token: str,
    caption: str,
    image_urls: list[str],
) -> PublishResult:
    _validate_count(image_urls, minimum=2, maximum=10, label="Instagram carousel posts")
    child_ids = [
        _create_instagram_image_container(
            settings=settings,
            account_id=instagram_business_account_id,
            token=instagram_access_token,
            image_url=image_url,
            caption="",
            is_carousel_item=True,
        )
        for image_url in image_urls
    ]
    parent = _post_meta_form(
        _graph_url(settings, f"{instagram_business_account_id}/media"),
        token=instagram_access_token,
        settings=settings,
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "caption": caption,
        },
    )
    parent_id = str(parent.get("id", "")).strip()
    if not parent_id:
        raise MetaPublishError("Instagram carousel container was created without an id.", status_code=502)
    _wait_for_instagram_container(settings=settings, token=instagram_access_token, creation_id=parent_id)
    post_id = _publish_instagram_container(settings=settings, account_id=instagram_business_account_id, token=instagram_access_token, creation_id=parent_id)
    return PublishResult(
        platform="instagram",
        published=True,
        post_id=post_id,
        creation_id=parent_id,
        message="Published carousel post to Instagram.",
        image_urls_used=image_urls,
        child_creation_ids=child_ids,
    )


def publish_instagram_carousel_uploads(
    *,
    settings: Settings,
    instagram_business_account_id: str,
    instagram_access_token: str,
    caption: str,
    images: list[tuple[bytes, str]],
) -> PublishResult:
    _validate_count(images, minimum=2, maximum=10, label="Instagram carousel posts")
    image_urls = [save_public_social_upload(settings, image_bytes=image_bytes, mime_type=mime_type) for image_bytes, mime_type in images]
    return publish_instagram_carousel_urls(
        settings=settings,
        instagram_business_account_id=instagram_business_account_id,
        instagram_access_token=instagram_access_token,
        caption=caption,
        image_urls=image_urls,
    )


def validate_social_image_bytes(
    settings: Settings,
    image_bytes: bytes,
    declared_content_type: str = "",
    *,
    platform: str,
) -> str:
    allowed = INSTAGRAM_IMAGE_MIME_TYPES if platform == "instagram" else FACEBOOK_IMAGE_MIME_TYPES
    if not image_bytes:
        raise ValueError("Uploaded image is empty.")
    if len(image_bytes) > settings.social_max_image_bytes:
        raise ValueError(f"Image exceeds maximum size of {settings.social_max_image_bytes} bytes.")
    declared = (declared_content_type or "").split(";", 1)[0].strip().lower()
    if declared and declared not in allowed:
        raise ValueError(f"Only {', '.join(sorted(allowed))} images are allowed for {platform}.")
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
            detected = SOCIAL_IMAGE_FORMAT_TO_MIME.get(str(image.format or "").upper(), "")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Uploaded file is not a valid image.") from exc
    if detected not in allowed:
        raise ValueError(f"Only {', '.join(sorted(allowed))} images are allowed for {platform}.")
    return detected


def save_public_social_upload(settings: Settings, *, image_bytes: bytes, mime_type: str) -> str:
    raise MetaPublishError(
        "Instagram multipart publishing is disabled because server-side image storage is disabled. Upload the image to product object storage first, then use the image-url or carousel-url endpoint.",
        status_code=400,
    )


def _create_facebook_unpublished_photo_url(*, settings: Settings, page_id: str, page_access_token: str, image_url: str) -> str:
    _require_https_url(image_url)
    result = _post_meta_form(
        _graph_url(settings, f"{page_id}/photos"),
        token=page_access_token,
        settings=settings,
        data={"url": image_url, "published": "false"},
    )
    photo_id = str(result.get("id", "")).strip()
    if not photo_id:
        raise MetaPublishError("Facebook did not return an unpublished photo ID.", status_code=502)
    return photo_id


def _post_facebook_photo_upload(
    *,
    settings: Settings,
    page_id: str,
    page_access_token: str,
    caption: str,
    image_bytes: bytes,
    mime_type: str,
    file_name: str,
    published: bool,
) -> dict:
    return _post_meta_form(
        _graph_url(settings, f"{page_id}/photos"),
        token=page_access_token,
        settings=settings,
        data={"caption": caption, "published": "true" if published else "false"},
        files={"source": (file_name or "upload.jpg", BytesIO(image_bytes), mime_type)},
    )


def _publish_facebook_attached_media_post(*, settings: Settings, page_id: str, page_access_token: str, caption: str, photo_ids: list[str]) -> str:
    data = {"message": caption}
    for index, photo_id in enumerate(photo_ids):
        data[f"attached_media[{index}]"] = json.dumps({"media_fbid": photo_id})
    result = _post_meta_form(_graph_url(settings, f"{page_id}/feed"), token=page_access_token, settings=settings, data=data)
    post_id = str(result.get("id", "")).strip()
    if not post_id:
        raise MetaPublishError("Facebook did not return a feed post ID.", status_code=502)
    return post_id


def _create_instagram_image_container(
    *,
    settings: Settings,
    account_id: str,
    token: str,
    image_url: str,
    caption: str,
    is_carousel_item: bool = False,
) -> str:
    _require_https_url(image_url)
    data = {"image_url": image_url}
    if caption:
        data["caption"] = caption
    if is_carousel_item:
        data["is_carousel_item"] = "true"
    result = _post_meta_form(_graph_url(settings, f"{account_id}/media"), token=token, settings=settings, data=data)
    creation_id = str(result.get("id", "")).strip()
    if not creation_id:
        raise MetaPublishError("Instagram media container was created without an id.", status_code=502)
    return creation_id


def _wait_for_instagram_container(*, settings: Settings, token: str, creation_id: str) -> None:
    for _ in range(5):
        status = _get_meta(_graph_url(settings, f"{creation_id}?fields=id,status_code,status"), token=token, settings=settings)
        status_code = str(status.get("status_code", "")).upper()
        if status_code == "FINISHED":
            return
        if status_code == "ERROR":
            raise MetaPublishError(str(status.get("status", "") or "Instagram media container failed."), status_code=400)
        sleep(1)


def _publish_instagram_container(*, settings: Settings, account_id: str, token: str, creation_id: str) -> str:
    result = _post_meta_form(
        _graph_url(settings, f"{account_id}/media_publish"),
        token=token,
        settings=settings,
        data={"creation_id": creation_id},
    )
    post_id = str(result.get("id", "")).strip()
    if not post_id:
        raise MetaPublishError("Instagram media_publish response did not include a post ID.", status_code=502)
    return post_id


def _require_value(value: str, message: str) -> None:
    if not str(value or "").strip():
        raise MetaPublishError(message, status_code=400)


def _require_https_url(value: str) -> None:
    if not str(value or "").strip().lower().startswith("https://"):
        raise MetaPublishError("image_url must be a public HTTPS URL.", status_code=400)


def _validate_count(values: list, *, minimum: int, maximum: int, label: str) -> None:
    if len(values) < minimum or len(values) > maximum:
        raise MetaPublishError(f"{label} require {minimum} to {maximum} images.", status_code=400)
