from __future__ import annotations

from dataclasses import dataclass

import requests

from app.config import Settings
from app.schemas import PublishRequest


@dataclass(frozen=True)
class PublishResult:
    platform: str
    published: bool
    post_id: str = ""
    creation_id: str = ""
    message: str = ""
    image_url_used: str = ""
    drive_image_url: str = ""


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
