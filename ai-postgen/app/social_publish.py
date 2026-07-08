from __future__ import annotations

from dataclasses import dataclass
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.config import Settings
from app.schemas import PublishRequest

_GOOGLE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


@dataclass(frozen=True)
class PublishResult:
    platform: str
    published: bool
    post_id: str = ""
    creation_id: str = ""
    message: str = ""
    image_url_used: str = ""
    drive_image_url: str = ""


def _extract_google_drive_file_id(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or ""
    if "/file/d/" in path:
        candidate = path.split("/file/d/", 1)[1].split("/", 1)[0].strip()
        if candidate:
            return candidate
    query = parse_qs(parsed.query or "")
    for key in ("id", "file_id"):
        value = (query.get(key) or [""])[0].strip()
        if value:
            return value
    return ""


def _to_drive_download_url(url: str) -> str:
    file_id = _extract_google_drive_file_id(url)
    if not file_id:
        return url
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def _build_drive_credentials(settings: Settings):
    drive_auth_mode = (settings.google_drive_auth_mode or settings.google_auth_mode or "service_account").strip().lower()
    if drive_auth_mode == "oauth_user":
        client_json = (settings.google_drive_oauth_client_json_path or settings.google_oauth_client_json_path).strip()
        token_path = (settings.google_drive_oauth_token_path or settings.google_oauth_token_path or "oauth-token-drive.json").strip()
        if not client_json:
            raise RuntimeError("Google Drive OAuth client JSON path is missing.")

        token_file = Path(token_path)
        creds: UserCredentials | None = None
        if token_file.exists():
            creds = UserCredentials.from_authorized_user_file(str(token_file), _GOOGLE_SCOPES)
            if creds and not creds.has_scopes(_GOOGLE_SCOPES):
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(client_json, _GOOGLE_SCOPES)
                creds = flow.run_local_server(port=0)
            token_file.write_text(creds.to_json(), encoding="utf-8")
        return creds

    if not settings.google_credentials_json_path.strip():
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON_PATH is missing.")
    return ServiceAccountCredentials.from_service_account_file(
        settings.google_credentials_json_path,
        scopes=_GOOGLE_SCOPES,
    )


def _upload_local_image_to_drive(image_file_path: str, settings: Settings) -> tuple[str, str]:
    if not settings.google_drive_folder_id.strip():
        raise RuntimeError("GOOGLE_DRIVE_FOLDER_ID is missing.")

    file_path = Path(image_file_path)
    if not file_path.exists() or not file_path.is_file():
        raise RuntimeError(f"Image file not found: {image_file_path}")

    drive = build("drive", "v3", credentials=_build_drive_credentials(settings))
    metadata = {"name": file_path.name, "parents": [settings.google_drive_folder_id]}
    mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=False)
    created = (
        drive.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id, webViewLink",
            supportsAllDrives=True,
        )
        .execute()
    )
    file_id = str(created.get("id", "")).strip()
    if not file_id:
        raise RuntimeError("Google Drive upload succeeded but no file id was returned.")

    drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        supportsAllDrives=True,
    ).execute()

    drive_link = str(created.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view")
    return drive_link, _to_drive_download_url(drive_link)


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


def _resolve_image_inputs(payload: PublishRequest, settings: Settings) -> tuple[str, str]:
    image_url = payload.image_url.strip()
    image_file_path = payload.image_file_path.strip()
    if image_url:
        if "drive.google.com" in image_url or "docs.google.com" in image_url:
            return image_url, _to_drive_download_url(image_url)
        return "", image_url
    if not image_file_path:
        return "", ""
    drive_url, direct_url = _upload_local_image_to_drive(image_file_path, settings)
    return drive_url, direct_url


def publish_to_meta(payload: PublishRequest, settings: Settings) -> PublishResult:
    platform = payload.platform.value
    drive_image_url, image_url_used = _resolve_image_inputs(payload, settings)

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
                drive_image_url=drive_image_url,
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
            raise RuntimeError("Instagram publishing requires an image URL or local image file path.")

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
            drive_image_url=drive_image_url,
        )

    raise RuntimeError("Only Facebook and Instagram publishing are currently supported.")
