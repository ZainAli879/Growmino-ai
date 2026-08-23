from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import json

from fastapi import Header, HTTPException, Request

from app.config import get_settings


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    business_id: str


def _decode_base64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _verify_hs256_jwt(token: str, secret: str) -> dict:
    try:
        header_raw, payload_raw, signature_raw = token.split(".")
        header = json.loads(_decode_base64url(header_raw))
        if header.get("alg") != "HS256":
            raise ValueError("Unsupported JWT algorithm.")
        expected = hmac.new(
            secret.encode("utf-8"),
            f"{header_raw}.{payload_raw}".encode("ascii"),
            hashlib.sha256,
        ).digest()
        signature = _decode_base64url(signature_raw)
        if not hmac.compare_digest(expected, signature):
            raise ValueError("JWT signature mismatch.")
        return json.loads(_decode_base64url(payload_raw))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid authorization token.") from exc


async def require_auth_context(
    request: Request,
    authorization: str = Header(default=""),
    x_growmino_user_id: str = Header(default=""),
    x_growmino_business_id: str = Header(default=""),
) -> AuthContext:
    settings = get_settings()
    auth_header = authorization.strip()

    if auth_header.lower().startswith("bearer ") and settings.growmino_jwt_secret:
        claims = _verify_hs256_jwt(auth_header.split(" ", 1)[1].strip(), settings.growmino_jwt_secret)
        user_id = str(claims.get("sub") or claims.get("user_id") or "").strip()
        business_id = str(claims.get("business_id") or claims.get("workspace_id") or "").strip()
        if user_id and business_id:
            return AuthContext(user_id=user_id, business_id=business_id)

    user_id = (x_growmino_user_id or "").strip()
    business_id = (x_growmino_business_id or "").strip()
    if user_id and business_id:
        return AuthContext(user_id=user_id, business_id=business_id)

    if not settings.api_auth_required:
        return AuthContext(
            user_id=settings.auth_dev_user_id,
            business_id=settings.auth_dev_business_id,
        )

    raise HTTPException(status_code=401, detail="Authentication required.")
