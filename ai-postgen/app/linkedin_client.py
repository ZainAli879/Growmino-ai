from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
import hashlib
import ipaddress
import logging
import secrets
import socket
from typing import Any
from urllib.parse import urlencode, urlparse

from cryptography.fernet import Fernet, InvalidToken
from PIL import Image, UnidentifiedImageError
import requests

from app.config import Settings

logger = logging.getLogger(__name__)

LINKEDIN_AUTHORIZATION_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
LINKEDIN_UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
LINKEDIN_ASSETS_URL = "https://api.linkedin.com/v2/assets?action=registerUpload"
LINKEDIN_REST_IMAGES_URL = "https://api.linkedin.com/rest/images?action=initializeUpload"
LINKEDIN_REST_POSTS_URL = "https://api.linkedin.com/rest/posts"
LINKEDIN_SCOPES = "openid profile email w_member_social"
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_MULTI_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif"}
IMAGE_FORMAT_TO_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
MULTI_IMAGE_FORMAT_TO_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "GIF": "image/gif"}


class LinkedInError(RuntimeError):
    pass


class LinkedInTransientError(LinkedInError):
    pass


class LinkedInRateLimitError(LinkedInTransientError):
    pass


class LinkedInAPIStatusError(LinkedInError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def create_state_token() -> tuple[str, str]:
    state = secrets.token_urlsafe(48)
    return state, hash_state(state)


def hash_state(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


def oauth_expiry(settings: Settings) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=settings.linkedin_oauth_state_ttl_seconds)).isoformat()


def build_authorization_url(settings: Settings, state: str) -> str:
    require_linkedin_config(settings)
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.linkedin_client_id,
            "redirect_uri": settings.linkedin_redirect_uri,
            "state": state,
            "scope": LINKEDIN_SCOPES,
        }
    )
    return f"{LINKEDIN_AUTHORIZATION_URL}?{query}"


def require_linkedin_config(settings: Settings) -> None:
    missing = [
        name
        for name, value in {
            "LINKEDIN_CLIENT_ID": settings.linkedin_client_id,
            "LINKEDIN_CLIENT_SECRET": settings.linkedin_client_secret,
            "LINKEDIN_REDIRECT_URI": settings.linkedin_redirect_uri,
            "TOKEN_ENCRYPTION_KEY": settings.token_encryption_key,
        }.items()
        if not value
    ]
    if missing:
        raise LinkedInError(f"LinkedIn integration is not configured. Missing: {', '.join(missing)}.")


def encrypt_token(settings: Settings, token: str) -> str:
    try:
        return Fernet(settings.token_encryption_key.encode("utf-8")).encrypt(token.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        raise LinkedInError("Token encryption failed. Check TOKEN_ENCRYPTION_KEY.") from exc


def decrypt_token(settings: Settings, encrypted_token: str) -> str:
    try:
        return Fernet(settings.token_encryption_key.encode("utf-8")).decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise LinkedInError("Stored LinkedIn token could not be decrypted.") from exc


def exchange_code_for_token(settings: Settings, code: str) -> dict[str, Any]:
    require_linkedin_config(settings)
    response = _request(
        settings,
        "POST",
        LINKEDIN_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.linkedin_redirect_uri,
            "client_id": settings.linkedin_client_id,
            "client_secret": settings.linkedin_client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return response.json()


def get_userinfo(settings: Settings, access_token: str) -> dict[str, Any]:
    response = _request(
        settings,
        "GET",
        LINKEDIN_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    return response.json()


def publish_text_post(settings: Settings, *, access_token: str, author_urn: str, caption: str) -> str:
    body = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": caption},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    response = _linkedin_post(settings, access_token, LINKEDIN_UGC_POSTS_URL, body)
    return response.headers.get("x-restli-id") or response.headers.get("X-RestLi-Id") or ""


def publish_image_post(
    settings: Settings,
    *,
    access_token: str,
    author_urn: str,
    caption: str,
    image_bytes: bytes,
    image_mime_type: str,
) -> str:
    asset = register_image_upload(settings, access_token=access_token, owner_urn=author_urn)
    upload_image_binary(
        settings,
        access_token=access_token,
        upload_url=asset["upload_url"],
        image_bytes=image_bytes,
        image_mime_type=image_mime_type,
    )
    return create_image_ugc_post(
        settings,
        access_token=access_token,
        author_urn=author_urn,
        caption=caption,
        asset_urn=asset["asset_urn"],
    )


def publish_multi_image_post(
    settings: Settings,
    *,
    access_token: str,
    author_urn: str,
    caption: str,
    images: list[tuple[bytes, str]],
    alt_texts: list[str] | None = None,
) -> tuple[str, list[str]]:
    if len(images) < 2 or len(images) > 20:
        raise ValueError("LinkedIn multi-image posts require 2 to 20 images.")
    normalized_alt_texts = normalize_alt_texts(len(images), alt_texts or [])
    image_urns: list[str] = []
    for image_bytes, image_mime_type in images:
        image_urn = initialize_rest_image_upload(settings, access_token=access_token, owner_urn=author_urn)
        upload_rest_image_binary(
            settings,
            access_token=access_token,
            upload_url=image_urn["upload_url"],
            image_bytes=image_bytes,
            image_mime_type=image_mime_type,
        )
        image_urns.append(image_urn["image_urn"])
    linkedin_post_id = create_multi_image_rest_post(
        settings,
        access_token=access_token,
        author_urn=author_urn,
        caption=caption,
        image_urns=image_urns,
        alt_texts=normalized_alt_texts,
    )
    return linkedin_post_id, image_urns


def create_multi_image_rest_post_with_urns(
    settings: Settings,
    *,
    access_token: str,
    author_urn: str,
    caption: str,
    image_urns: list[str],
    alt_texts: list[str] | None = None,
) -> str:
    if len(image_urns) < 2 or len(image_urns) > 20:
        raise ValueError("LinkedIn multi-image posts require 2 to 20 image URNs.")
    return create_multi_image_rest_post(
        settings,
        access_token=access_token,
        author_urn=author_urn,
        caption=caption,
        image_urns=image_urns,
        alt_texts=normalize_alt_texts(len(image_urns), alt_texts or []),
    )


def register_image_upload(settings: Settings, *, access_token: str, owner_urn: str) -> dict[str, str]:
    body = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": owner_urn,
            "serviceRelationships": [
                {
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }
            ],
            "supportedUploadMechanism": ["SYNCHRONOUS_UPLOAD"],
        }
    }
    response = _linkedin_post(settings, access_token, LINKEDIN_ASSETS_URL, body)
    value = response.json().get("value", {})
    mechanism = value.get("uploadMechanism", {}).get("com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest", {})
    upload_url = str(mechanism.get("uploadUrl") or "")
    asset_urn = str(value.get("asset") or "")
    if not upload_url or not asset_urn:
        raise LinkedInError("LinkedIn did not return an upload URL and asset URN.")
    return {"upload_url": upload_url, "asset_urn": asset_urn}


def initialize_rest_image_upload(settings: Settings, *, access_token: str, owner_urn: str) -> dict[str, str]:
    body = {"initializeUploadRequest": {"owner": owner_urn}}
    response = _linkedin_rest_post(settings, access_token, LINKEDIN_REST_IMAGES_URL, body)
    value = response.json().get("value", {})
    upload_url = str(value.get("uploadUrl") or "")
    image_urn = str(value.get("image") or "")
    if not upload_url or not image_urn:
        raise LinkedInError("LinkedIn did not return an image upload URL and image URN.")
    return {"upload_url": upload_url, "image_urn": image_urn}


def upload_image_binary(
    settings: Settings,
    *,
    access_token: str,
    upload_url: str,
    image_bytes: bytes,
    image_mime_type: str,
) -> None:
    response = _request(
        settings,
        "PUT",
        upload_url,
        data=image_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": image_mime_type,
        },
    )
    if response.status_code not in {200, 201, 202}:
        raise LinkedInError("LinkedIn image binary upload failed.")


def upload_rest_image_binary(
    settings: Settings,
    *,
    access_token: str,
    upload_url: str,
    image_bytes: bytes,
    image_mime_type: str,
) -> None:
    response = _request(
        settings,
        "PUT",
        upload_url,
        data=image_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": image_mime_type,
        },
    )
    if response.status_code not in {200, 201, 202}:
        raise LinkedInError("LinkedIn multi-image binary upload failed.")


def create_image_ugc_post(
    settings: Settings,
    *,
    access_token: str,
    author_urn: str,
    caption: str,
    asset_urn: str,
) -> str:
    body = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": caption},
                "shareMediaCategory": "IMAGE",
                "media": [
                    {
                        "status": "READY",
                        "media": asset_urn,
                    }
                ],
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    response = _linkedin_post(settings, access_token, LINKEDIN_UGC_POSTS_URL, body)
    return response.headers.get("x-restli-id") or response.headers.get("X-RestLi-Id") or ""


def create_multi_image_rest_post(
    settings: Settings,
    *,
    access_token: str,
    author_urn: str,
    caption: str,
    image_urns: list[str],
    alt_texts: list[str],
) -> str:
    body = {
        "author": author_urn,
        "commentary": caption,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {
            "multiImage": {
                "images": [
                    {"id": image_urn, "altText": alt_text}
                    for image_urn, alt_text in zip(image_urns, alt_texts, strict=True)
                ]
            }
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    response = _linkedin_rest_post(settings, access_token, LINKEDIN_REST_POSTS_URL, body)
    return response.headers.get("x-restli-id") or response.headers.get("X-RestLi-Id") or ""


def validate_image_bytes(settings: Settings, image_bytes: bytes, declared_content_type: str = "") -> str:
    if not image_bytes:
        raise ValueError("Uploaded image is empty.")
    if len(image_bytes) > settings.linkedin_max_image_bytes:
        raise ValueError(f"Image exceeds maximum size of {settings.linkedin_max_image_bytes} bytes.")
    declared = (declared_content_type or "").split(";", 1)[0].strip().lower()
    if declared and declared not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValueError("Only JPEG, PNG, or WebP images are allowed.")
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
            detected = IMAGE_FORMAT_TO_MIME.get(str(image.format or "").upper(), "")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Uploaded file is not a valid image.") from exc
    if detected not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValueError("Only JPEG, PNG, or WebP images are allowed.")
    return detected


def validate_multi_image_bytes(settings: Settings, image_bytes: bytes, declared_content_type: str = "") -> str:
    if not image_bytes:
        raise ValueError("Uploaded image is empty.")
    if len(image_bytes) > settings.linkedin_max_image_bytes:
        raise ValueError(f"Image exceeds maximum size of {settings.linkedin_max_image_bytes} bytes.")
    declared = (declared_content_type or "").split(";", 1)[0].strip().lower()
    if declared and declared not in ALLOWED_MULTI_IMAGE_MIME_TYPES:
        raise ValueError("Only JPG, PNG, or GIF images are allowed.")
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
            detected = MULTI_IMAGE_FORMAT_TO_MIME.get(str(image.format or "").upper(), "")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Uploaded file is not a valid image.") from exc
    if detected not in ALLOWED_MULTI_IMAGE_MIME_TYPES:
        raise ValueError("Only JPG, PNG, or GIF images are allowed.")
    return detected


def normalize_alt_texts(image_count: int, alt_texts: list[str]) -> list[str]:
    if len(alt_texts) > image_count:
        raise ValueError("alt_texts cannot contain more items than uploaded images.")
    normalized = [str(value or "").strip()[:300] for value in alt_texts]
    while len(normalized) < image_count:
        normalized.append("")
    return normalized


def download_safe_https_image(settings: Settings, image_url: str) -> tuple[bytes, str]:
    current_url = image_url
    for _ in range(4):
        _assert_safe_https_url(current_url)
        response = requests.get(
            current_url,
            stream=True,
            timeout=settings.linkedin_request_timeout_seconds,
            allow_redirects=False,
            headers={"User-Agent": settings.linkedin_user_agent},
        )
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location", "")
            if not location:
                raise ValueError("Image URL redirect is missing Location header.")
            current_url = requests.compat.urljoin(current_url, location)
            continue
        if response.status_code >= 400:
            raise ValueError("Image URL could not be downloaded.")
        content_length = int(response.headers.get("Content-Length") or "0")
        if content_length and content_length > settings.linkedin_max_image_bytes:
            raise ValueError(f"Image exceeds maximum size of {settings.linkedin_max_image_bytes} bytes.")
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > settings.linkedin_max_image_bytes:
                raise ValueError(f"Image exceeds maximum size of {settings.linkedin_max_image_bytes} bytes.")
            chunks.append(chunk)
        image_bytes = b"".join(chunks)
        mime_type = validate_image_bytes(settings, image_bytes, response.headers.get("Content-Type", ""))
        return image_bytes, mime_type
    raise ValueError("Image URL redirected too many times.")


def _assert_safe_https_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        raise ValueError("Image URL must use HTTPS.")
    if parsed.username or parsed.password:
        raise ValueError("Image URL credentials are not allowed.")
    host = parsed.hostname
    if not host:
        raise ValueError("Image URL host is required.")
    if parsed.port not in {None, 443}:
        raise ValueError("Image URL must use the default HTTPS port.")
    try:
        addresses = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError("Image URL host could not be resolved.") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError("Image URL host resolves to a blocked network address.")


def _linkedin_post(settings: Settings, access_token: str, url: str, body: dict) -> requests.Response:
    return _request(
        settings,
        "POST",
        url,
        json=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        },
    )


def _linkedin_rest_post(settings: Settings, access_token: str, url: str, body: dict) -> requests.Response:
    return _request(
        settings,
        "POST",
        url,
        json=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Linkedin-Version": settings.linkedin_rest_version,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        },
    )


def _request(settings: Settings, method: str, url: str, **kwargs) -> requests.Response:
    headers = {**kwargs.pop("headers", {}), "User-Agent": settings.linkedin_user_agent}
    try:
        response = requests.request(
            method,
            url,
            timeout=settings.linkedin_request_timeout_seconds,
            headers=headers,
            **kwargs,
        )
    except requests.RequestException as exc:
        safe_error = _redact(str(exc))[:500]
        logger.warning("LinkedIn network error method=%s url=%s error=%s", method, _safe_url(url), safe_error)
        raise LinkedInTransientError(f"LinkedIn network error: {exc.__class__.__name__}: {safe_error}") from exc

    if response.status_code == 429:
        raise LinkedInRateLimitError("LinkedIn rate limit reached. Please retry later.")
    if 500 <= response.status_code <= 599:
        raise LinkedInTransientError("LinkedIn service returned a transient error.")
    if response.status_code >= 400:
        safe_body = _redact(response.text[:500])
        logger.warning("LinkedIn API error status=%s body=%s", response.status_code, safe_body)
        raise LinkedInAPIStatusError(
            response.status_code,
            f"LinkedIn rejected the request with status {response.status_code}: {safe_body}",
        )
    return response


def _redact(value: str) -> str:
    return (
        value.replace("access_token", "redacted_token")
        .replace("client_secret", "redacted_secret")
        .replace("uploadUrl", "redacted_upload_url")
    )


def _safe_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc.endswith("linkedin.com"):
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return "[signed-upload-url-redacted]"
