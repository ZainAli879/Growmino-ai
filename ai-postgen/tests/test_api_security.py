from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ApiSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-openai-key",
                "TEXT_PROVIDER": "openai",
                "IMAGE_PROVIDER": "openai",
                "API_AUTH_REQUIRED": "false",
                "ALLOW_DEV_AUTH_HEADERS": "true",
                "API_RATE_LIMIT_ENABLED": "true",
                "API_RATE_LIMIT_REQUESTS": "120",
                "API_RATE_LIMIT_WINDOW_SECONDS": "60",
                "API_GENERATION_RATE_LIMIT_REQUESTS": "120",
                "API_GENERATION_RATE_LIMIT_WINDOW_SECONDS": "60",
                "CORS_ALLOW_ORIGINS": "http://localhost:3000",
                "EXPOSE_TEST_UI": "true",
                "ENVIRONMENT": "development",
            },
            clear=False,
        )
        self.env.start()
        from app.api import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.env.stop()

    def test_request_id_and_security_headers_are_returned(self) -> None:
        response = self.client.get("/api/v1/health", headers={"X-Request-Id": "test-request-123"})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["X-Request-Id"], "test-request-123")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")

    def test_error_response_has_stable_shape(self) -> None:
        response = self.client.get("/api/v1/not-found")

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["detail"], "Not Found")
        self.assertEqual(payload["error"]["code"], "NOT_FOUND")
        self.assertTrue(payload["request_id"])
        self.assertEqual(payload["request_id"], payload["error"]["request_id"])

    def test_request_body_size_is_limited(self) -> None:
        with patch.dict(os.environ, {"API_MAX_BODY_BYTES": "10"}, clear=False):
            response = self.client.post("/api/v1/posts", json={"data_url": "x" * 100})

        self.assertEqual(response.status_code, 413)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], "REQUEST_BODY_TOO_LARGE")

    def test_generation_endpoints_require_auth_when_auth_enabled(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "development",
                "API_AUTH_REQUIRED": "true",
                "ALLOW_DEV_AUTH_HEADERS": "false",
                "GROWMINO_JWT_SECRET": "x" * 40,
            },
            clear=False,
        ):
            posts_response = self.client.post("/api/v1/posts", json=_post_payload())
            plans_response = self.client.post("/api/v1/content-plans", json=_plan_payload())
            list_response = self.client.get("/api/v1/posts")

        self.assertEqual(posts_response.status_code, 401)
        self.assertEqual(plans_response.status_code, 401)
        self.assertEqual(list_response.status_code, 401)
        self.assertEqual(posts_response.json()["error"]["code"], "UNAUTHORIZED")

    def test_non_production_compatibility_routes_are_not_exposed(self) -> None:
        schema = self.client.app.openapi()
        self.assertNotIn("/api/v1/assets", schema["paths"])
        self.assertNotIn("/api/v1/publishing-jobs", schema["paths"])

    def test_rate_limit_returns_retry_after(self) -> None:
        user_id = f"user-{uuid4()}"
        headers = {"X-Growmino-User-Id": user_id, "X-Growmino-Business-Id": "business-1"}
        with patch.dict(
            os.environ,
            {
                "API_RATE_LIMIT_REQUESTS": "1",
                "API_RATE_LIMIT_WINDOW_SECONDS": "60",
                "API_GENERATION_RATE_LIMIT_REQUESTS": "1",
                "API_GENERATION_RATE_LIMIT_WINDOW_SECONDS": "60",
            },
            clear=False,
        ):
            first = self.client.get("/api/v1/posts?limit=1", headers=headers)
            second = self.client.get("/api/v1/posts?limit=1", headers=headers)

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["error"]["code"], "RATE_LIMIT_EXCEEDED")
        self.assertTrue(second.headers.get("Retry-After"))

    def test_dev_auth_headers_are_rejected_when_auth_is_required(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "development",
                "API_AUTH_REQUIRED": "true",
                "ALLOW_DEV_AUTH_HEADERS": "false",
                "GROWMINO_JWT_SECRET": "x" * 40,
            },
            clear=False,
        ):
            response = self.client.get(
                "/api/v1/integrations/linkedin/status",
                headers={"X-Growmino-User-Id": "local-user", "X-Growmino-Business-Id": "local-business"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "UNAUTHORIZED")

    def test_production_configuration_requires_secure_api_boundary(self) -> None:
        from app.config import get_settings

        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "API_AUTH_REQUIRED": "false",
                "ALLOW_DEV_AUTH_HEADERS": "false",
                "GROWMINO_JWT_SECRET": "x" * 40,
                "CORS_ALLOW_ORIGINS": "https://app.growmino.com",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(RuntimeError, "API_AUTH_REQUIRED"):
                get_settings()

    def test_production_configuration_rejects_public_outputs(self) -> None:
        from app.config import get_settings

        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "API_AUTH_REQUIRED": "true",
                "ALLOW_DEV_AUTH_HEADERS": "false",
                "GROWMINO_JWT_SECRET": "x" * 40,
                "CORS_ALLOW_ORIGINS": "https://app.growmino.com",
                "EXPOSE_OUTPUTS": "true",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(RuntimeError, "EXPOSE_OUTPUTS"):
                get_settings()

def _post_payload() -> dict:
    return {
        "business_id": str(uuid4()),
        "weekly_schedule_id": str(uuid4()),
        "platform": "linkedin",
    }


def _plan_payload() -> dict:
    return {
        "business_id": str(uuid4()),
        "week_start_date": "2026-09-01",
    }


if __name__ == "__main__":
    unittest.main()
