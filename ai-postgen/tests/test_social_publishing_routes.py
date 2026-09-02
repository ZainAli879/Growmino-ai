from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from PIL import Image
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class SocialPublishingRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-openai-key",
                "TEXT_PROVIDER": "openai",
                "IMAGE_PROVIDER": "openai",
                "API_AUTH_REQUIRED": "false",
                "PUBLIC_BASE_URL": "https://public.example.com",
            },
        )
        self.env.start()
        from app.api import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.env.stop()

    def test_social_routes_are_exposed_and_instagram_text_is_skipped(self) -> None:
        schema = self.client.app.openapi()
        paths = schema["paths"]
        self.assertIn("/api/v1/social/facebook/posts/text", paths)
        self.assertIn("/api/v1/social/facebook/posts/image", paths)
        self.assertIn("/api/v1/social/facebook/posts/image-url", paths)
        self.assertIn("/api/v1/social/facebook/posts/multi-image", paths)
        self.assertIn("/api/v1/social/facebook/posts/multi-image-url", paths)
        self.assertIn("/api/v1/social/instagram/posts/image", paths)
        self.assertIn("/api/v1/social/instagram/posts/image-url", paths)
        self.assertIn("/api/v1/social/instagram/posts/carousel", paths)
        self.assertIn("/api/v1/social/instagram/posts/carousel-url", paths)
        self.assertIn("/api/v1/social/linkedin/posts/text", paths)
        self.assertIn("/api/v1/social/linkedin/posts/image", paths)
        self.assertIn("/api/v1/social/linkedin/posts/image-url", paths)
        self.assertIn("/api/v1/social/linkedin/posts/multi-image", paths)
        self.assertNotIn("/api/v1/social/instagram/posts/text", paths)

    def test_facebook_text_requires_dynamic_page_credentials(self) -> None:
        response = self.client.post(
            "/api/v1/social/facebook/posts/text",
            json={"page_id": "page-id", "caption": "Missing token."},
        )
        self.assertEqual(response.status_code, 422)

    def test_facebook_text_publishes_with_dynamic_credentials(self) -> None:
        from app.social_publish import PublishResult

        with patch("app.social_api.publish_facebook_text") as publish:
            publish.return_value = PublishResult(
                platform="facebook",
                published=True,
                post_id="page_post_id",
                message="Published text post to Facebook.",
            )
            response = self.client.post(
                "/api/v1/social/facebook/posts/text",
                json={
                    "page_id": "page-id",
                    "page_access_token": "page-token",
                    "caption": "Testing Facebook text.",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["post_id"], "page_post_id")
        publish.assert_called_once()

    def test_facebook_multi_image_upload_rejects_one_image(self) -> None:
        response = self.client.post(
            "/api/v1/social/facebook/posts/multi-image",
            data={"page_id": "page-id", "page_access_token": "page-token", "caption": "One image."},
            files=[("images", ("one.jpg", _image_bytes("JPEG"), "image/jpeg"))],
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("2 to 20", response.json()["detail"])

    def test_instagram_image_upload_is_disabled_without_server_storage(self) -> None:
        response = self.client.post(
            "/api/v1/social/instagram/posts/image",
            data={
                "instagram_business_account_id": "ig-user-id",
                "instagram_access_token": "ig-token",
                "caption": "Testing Instagram image.",
            },
            files=[("file", ("one.jpg", _image_bytes("JPEG"), "image/jpeg"))],
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("server-side image storage is disabled", response.json()["detail"].lower())


def _image_bytes(format_name: str) -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (12, 12), color=(30, 120, 160))
    image.save(output, format=format_name)
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()
