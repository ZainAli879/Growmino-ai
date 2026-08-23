from __future__ import annotations

from io import BytesIO
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from PIL import Image


class LinkedInMultiImageEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_file = os.path.join(self.temp_dir.name, "linkedin_store.json")
        self.env = patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-openai-key",
                "TEXT_PROVIDER": "openai",
                "IMAGE_PROVIDER": "openai",
                "TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode("utf-8"),
                "LINKEDIN_STORE_FILE": self.store_file,
                "LINKEDIN_REST_VERSION": "202608",
                "API_AUTH_REQUIRED": "false",
            },
        )
        self.env.start()

        from app.api import app
        from app.config import get_settings
        from app.linkedin_client import encrypt_token
        from app.linkedin_store import upsert_connection

        self.client = TestClient(app)
        self.settings = get_settings()
        upsert_connection(
            self.settings,
            user_id="local-user",
            business_id="local-business",
            linkedin_sub="linkedin-person-id",
            person_urn="urn:li:person:linkedin-person-id",
            encrypted_access_token=encrypt_token(self.settings, "test-access-token"),
            scopes="openid profile email w_member_social",
            expires_at="2099-01-01T00:00:00+00:00",
            profile={"name": "Test User", "email": "test@example.com"},
        )

    def tearDown(self) -> None:
        self.env.stop()
        self.temp_dir.cleanup()

    def test_successful_multi_image_upload_and_publish(self) -> None:
        with (
            patch("app.linkedin_api.initialize_rest_image_upload") as initialize_upload,
            patch("app.linkedin_api.upload_rest_image_binary") as upload_binary,
            patch("app.linkedin_api.create_multi_image_rest_post") as create_post,
        ):
            initialize_upload.side_effect = [
                {"upload_url": "https://upload.linkedin.example/one", "image_urn": "urn:li:image:one"},
                {"upload_url": "https://upload.linkedin.example/two", "image_urn": "urn:li:image:two"},
            ]
            create_post.return_value = "urn:li:share:published"

            response = self.client.post(
                "/api/v1/social/linkedin/posts/multi-image",
                data={
                    "caption": "A two image LinkedIn post.",
                    "idempotency_key": "multi-success",
                    "alt_texts": ["First image", "Second image"],
                },
                files=[
                    ("images", ("one.jpg", _image_bytes("JPEG"), "image/jpeg")),
                    ("images", ("two.png", _image_bytes("PNG"), "image/png")),
                ],
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "published")
        self.assertEqual(payload["linkedin_post_id"], "urn:li:share:published")
        self.assertEqual(payload["image_urns"], ["urn:li:image:one", "urn:li:image:two"])
        self.assertEqual(initialize_upload.call_count, 2)
        self.assertEqual(upload_binary.call_count, 2)
        create_post.assert_called_once()

    def test_existing_text_publish_route_still_works(self) -> None:
        with patch("app.linkedin_api.publish_text_post") as publish_text:
            publish_text.return_value = "urn:li:share:text"
            response = self.client.post(
                "/api/v1/posts/linkedin/publish-text",
                json={"caption": "Existing text route still works.", "idempotency_key": "text-route"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["linkedin_post_id"], "urn:li:share:text")
        publish_text.assert_called_once()

    def test_existing_single_image_publish_route_still_works(self) -> None:
        with patch("app.linkedin_api.publish_image_post") as publish_image:
            publish_image.return_value = "urn:li:share:image"
            response = self.client.post(
                "/api/v1/posts/linkedin/publish-image",
                data={"caption": "Existing image route still works.", "idempotency_key": "image-route"},
                files=[("file", ("one.jpg", _image_bytes("JPEG"), "image/jpeg"))],
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["linkedin_post_id"], "urn:li:share:image")
        publish_image.assert_called_once()

    def test_rejects_invalid_image_count(self) -> None:
        with patch("app.linkedin_api.initialize_rest_image_upload") as initialize_upload:
            response = self.client.post(
                "/api/v1/social/linkedin/posts/multi-image",
                data={"caption": "Only one image."},
                files=[("images", ("one.jpg", _image_bytes("JPEG"), "image/jpeg"))],
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("2 to 20 images", response.json()["detail"])
        initialize_upload.assert_not_called()

    def test_does_not_publish_when_any_upload_fails(self) -> None:
        from app.linkedin_client import LinkedInTransientError

        with (
            patch("app.linkedin_api.initialize_rest_image_upload") as initialize_upload,
            patch("app.linkedin_api.upload_rest_image_binary") as upload_binary,
            patch("app.linkedin_api.create_multi_image_rest_post") as create_post,
        ):
            initialize_upload.side_effect = [
                {"upload_url": "https://upload.linkedin.example/one", "image_urn": "urn:li:image:one"},
                {"upload_url": "https://upload.linkedin.example/two", "image_urn": "urn:li:image:two"},
            ]
            upload_binary.side_effect = [None, LinkedInTransientError("Upload failed.")]

            response = self.client.post(
                "/api/v1/social/linkedin/posts/multi-image",
                data={"caption": "Upload should fail.", "idempotency_key": "multi-upload-failure"},
                files=[
                    ("images", ("one.jpg", _image_bytes("JPEG"), "image/jpeg")),
                    ("images", ("two.jpg", _image_bytes("JPEG"), "image/jpeg")),
                ],
            )

        self.assertEqual(response.status_code, 502)
        create_post.assert_not_called()
        job = _latest_job(self.store_file)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["linkedin_post_id"], "")

    def test_saves_uploaded_urns_when_final_publish_fails(self) -> None:
        from app.linkedin_client import LinkedInAPIStatusError

        with (
            patch("app.linkedin_api.initialize_rest_image_upload") as initialize_upload,
            patch("app.linkedin_api.upload_rest_image_binary"),
            patch("app.linkedin_api.create_multi_image_rest_post") as create_post,
        ):
            initialize_upload.side_effect = [
                {"upload_url": "https://upload.linkedin.example/one", "image_urn": "urn:li:image:one"},
                {"upload_url": "https://upload.linkedin.example/two", "image_urn": "urn:li:image:two"},
            ]
            create_post.side_effect = LinkedInAPIStatusError(403, "LinkedIn rejected the request with status 403.")

            response = self.client.post(
                "/api/v1/social/linkedin/posts/multi-image",
                data={"caption": "Final publish should fail.", "idempotency_key": "multi-publish-failure"},
                files=[
                    ("images", ("one.jpg", _image_bytes("JPEG"), "image/jpeg")),
                    ("images", ("two.jpg", _image_bytes("JPEG"), "image/jpeg")),
                ],
            )

        self.assertEqual(response.status_code, 403)
        job = _latest_job(self.store_file)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["image_urns"], ["urn:li:image:one", "urn:li:image:two"])
        self.assertEqual(job["linkedin_post_id"], "")


def _image_bytes(format_name: str) -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (12, 12), color=(40, 90, 200))
    image.save(output, format=format_name)
    return output.getvalue()


def _latest_job(store_file: str) -> dict:
    with open(store_file, encoding="utf-8") as handle:
        data = json.load(handle)
    return data["jobs"][-1]


if __name__ == "__main__":
    unittest.main()
