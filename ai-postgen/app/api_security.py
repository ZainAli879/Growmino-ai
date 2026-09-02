from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import os
from time import monotonic
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp


REQUEST_ID_HEADER = "X-Request-Id"


@dataclass(frozen=True)
class RateLimitPolicy:
    requests: int
    window_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, policy: RateLimitPolicy) -> tuple[bool, int]:
        now = monotonic()
        hits = self._hits[key]
        cutoff = now - policy.window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= policy.requests:
            retry_after = max(1, int(policy.window_seconds - (now - hits[0])))
            return False, retry_after
        hits.append(now)
        return True, 0


class ApiSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._rate_limiter = InMemoryRateLimiter()

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = _request_id(request)
        request.state.request_id = request_id

        max_body_bytes = _int_env("API_MAX_BODY_BYTES", 25_000_000)
        content_length = request.headers.get("content-length")
        if content_length and _safe_int(content_length) > max_body_bytes:
            return _error_response(
                status_code=413,
                code="REQUEST_BODY_TOO_LARGE",
                message=f"Request body exceeds maximum size of {max_body_bytes} bytes.",
                request_id=request_id,
            )

        rate_limit_response = _rate_limit_response(request, request_id, self._rate_limiter)
        if rate_limit_response is not None:
            return rate_limit_response

        response = await call_next(request)
        _apply_security_headers(response, request_id)
        return response


def api_error_payload(*, code: str, message: str, request_id: str) -> dict:
    return {
        "detail": message,
        "request_id": request_id,
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        },
    }


def _error_response(*, status_code: int, code: str, message: str, request_id: str) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content=api_error_payload(code=code, message=message, request_id=request_id),
    )
    _apply_security_headers(response, request_id)
    if status_code == 429:
        response.headers.setdefault("Retry-After", "60")
    return response


def _rate_limit_response(
    request: Request,
    request_id: str,
    limiter: InMemoryRateLimiter,
) -> JSONResponse | None:
    if not _bool_env("API_RATE_LIMIT_ENABLED", True):
        return None
    if not request.url.path.startswith("/api/"):
        return None
    if request.url.path == "/api/v1/health":
        return None

    policy = _policy_for_path(request.url.path)
    key = _rate_limit_key(request)
    ok, retry_after = limiter.check(f"{request.url.path}:{key}", policy)
    if ok:
        return None

    response = _error_response(
        status_code=429,
        code="RATE_LIMIT_EXCEEDED",
        message="Too many requests. Please retry later.",
        request_id=request_id,
    )
    response.headers["Retry-After"] = str(retry_after)
    return response


def _policy_for_path(path: str) -> RateLimitPolicy:
    if path in {"/api/v1/posts", "/api/v1/content-plans"}:
        return RateLimitPolicy(
            requests=_int_env("API_GENERATION_RATE_LIMIT_REQUESTS", 10),
            window_seconds=_int_env("API_GENERATION_RATE_LIMIT_WINDOW_SECONDS", 3600),
        )
    if "/publish" in path or "/social/" in path or "/linkedin/" in path:
        return RateLimitPolicy(
            requests=_int_env("API_PUBLISH_RATE_LIMIT_REQUESTS", 60),
            window_seconds=_int_env("API_PUBLISH_RATE_LIMIT_WINDOW_SECONDS", 60),
        )
    return RateLimitPolicy(
        requests=_int_env("API_RATE_LIMIT_REQUESTS", 120),
        window_seconds=_int_env("API_RATE_LIMIT_WINDOW_SECONDS", 60),
    )


def _rate_limit_key(request: Request) -> str:
    user_id = request.headers.get("x-growmino-user-id", "").strip()
    business_id = request.headers.get("x-growmino-business-id", "").strip()
    authorization = request.headers.get("authorization", "").strip()
    if user_id and business_id:
        raw_key = f"user:{user_id}:business:{business_id}"
    elif authorization:
        raw_key = f"auth:{authorization}"
    else:
        raw_key = f"ip:{request.client.host if request.client else 'unknown'}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _request_id(request: Request) -> str:
    incoming = request.headers.get(REQUEST_ID_HEADER, "").strip()
    if incoming and len(incoming) <= 128 and all(char.isalnum() or char in "-_." for char in incoming):
        return incoming
    return str(uuid4())


def _apply_security_headers(response: Response, request_id: str) -> None:
    response.headers[REQUEST_ID_HEADER] = request_id
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cache-Control", "no-store")
    if _bool_env("SECURE_HSTS_ENABLED", False):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


def _bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return value if value > 0 else default


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0
