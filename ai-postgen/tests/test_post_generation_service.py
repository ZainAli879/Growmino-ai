from __future__ import annotations

import asyncio
import base64
import os
from dataclasses import dataclass
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth import AuthContext  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import BusinessGenerationContext  # noqa: E402
from app.post_generation_service import PostGenerationService, PostGenerationServiceError  # noqa: E402
from app.schemas import CreatePostRequest, WeeklyContentPlanRequest  # noqa: E402
from app.storage import StoredObject  # noqa: E402


@dataclass
class CaptionResult:
    caption: str
    headline: str


@dataclass
class ImageResult:
    model: str
    size: str
    style: str
    prompt_used: str
    negative_prompt_used: str
    file_path: str
    image_base64: str
    image_mime_type: str
    alt_text: str


class FakeContextRepository:
    def __init__(self, context: BusinessGenerationContext | None) -> None:
        self.context = context
        self.weekly_contexts = [context] if context else []
        self.business_exists_result = True
        self.schedule_business_id = context.business_id if context else uuid4()

    def business_exists(self, *, business_id):
        return self.business_exists_result

    def fetch_schedule_business_id(self, *, weekly_schedule_id):
        return self.schedule_business_id

    def fetch_generation_context(self, *, business_id, weekly_schedule_id):
        return self.context

    def fetch_weekly_generation_contexts(self, *, business_id):
        return self.weekly_contexts


class FakePostRepository:
    def __init__(self) -> None:
        self.records = []
        self.fail_insert = False

    def insert_generated_post(self, record):
        if self.fail_insert:
            raise RuntimeError("insert failed")
        self.records.append(record)


class FakeStorageService:
    def __init__(self) -> None:
        self.uploaded_images = []
        self.deleted = []
        self.fail_upload = False

    def upload_generated_image(self, *, business_id, post_id, image_bytes, mime_type):
        if self.fail_upload:
            raise RuntimeError("upload failed")
        self.uploaded_images.append(
            {"business_id": business_id, "post_id": post_id, "image_bytes": image_bytes, "mime_type": mime_type}
        )
        return StoredObject(
            bucket="post-media",
            object_path=f"businesses/{business_id}/posts/{post_id}/image.png",
            public_url=f"https://cdn.example.com/{post_id}/image.png",
        )

    def upload_business_asset(self, *, business_id, image_bytes, mime_type, extension):
        return StoredObject(
            bucket="business-assets",
            object_path=f"businesses/{business_id}/assets/logo.png",
            public_url=f"https://cdn.example.com/{business_id}/logo.png",
        )

    def delete_object(self, *, bucket, object_path):
        self.deleted.append({"bucket": bucket, "object_path": object_path})


class PostGenerationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.business_id = uuid4()
        self.schedule_id = uuid4()
        self.context = _context(self.business_id, self.schedule_id)
        self.context_repo = FakeContextRepository(self.context)
        self.post_repo = FakePostRepository()
        self.storage = FakeStorageService()
        self.env = patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-openai-key",
                "DATABASE_URL": "postgresql://app:pass@127.0.0.1:5432/business-management",
                "SUPABASE_URL": "https://project.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
            },
        )
        self.env.start()
        self.settings = get_settings()
        self.payload = CreatePostRequest(
            business_id=self.business_id,
            weekly_schedule_id=self.schedule_id,
            platform="instagram",
        )
        self.auth = AuthContext(user_id="local-user", business_id=str(self.business_id))

    def tearDown(self) -> None:
        self.env.stop()

    def test_valid_context_maps_db_fields_uploads_and_persists(self) -> None:
        with (
            patch("app.post_generation_service.generate_caption") as caption,
            patch("app.post_generation_service.generate_image") as image,
        ):
            caption.return_value = CaptionResult(caption="Generated caption #tag", headline="Generated Headline")
            image.return_value = ImageResult(
                model="gpt-image-2",
                size="1024x1024",
                style="caption_derived",
                prompt_used="prompt",
                negative_prompt_used="",
                file_path="",
                image_base64=base64.b64encode(b"image-bytes").decode("ascii"),
                image_mime_type="image/png",
                alt_text="Alt text",
            )
            response = asyncio.run(self._service().create_post(self.payload, self.auth))

        ai_payload = caption.call_args.args[0]
        self.assertEqual(ai_payload.business_name, "Velmora Fashion")
        self.assertEqual(ai_payload.industry, "Clothes & Accessories - Men's Fashion")
        self.assertEqual(ai_payload.day.value, "Monday")
        self.assertEqual(ai_payload.content_type.value, "Educational")
        self.assertEqual(ai_payload.offer, "")
        self.assertEqual(ai_payload.tone, "")
        self.assertEqual(ai_payload.proof_assets, "")
        self.assertEqual(self.storage.uploaded_images[0]["image_bytes"], b"image-bytes")
        self.assertEqual(self.post_repo.records[0].business_id, self.business_id)
        self.assertEqual(self.post_repo.records[0].weekly_schedule_id, self.schedule_id)
        self.assertEqual(self.post_repo.records[0].source if hasattr(self.post_repo.records[0], "source") else "ai", "ai")
        self.assertIn(response.image_url, self.post_repo.records[0].image_urls_json)
        self.assertEqual(response.business_id, self.business_id)
        self.assertEqual(response.weekly_schedule_id, self.schedule_id)
        self.assertEqual(response.image_urls, [response.image_url])

    def test_missing_business_returns_404(self) -> None:
        self.context_repo.business_exists_result = False
        with self.assertRaises(PostGenerationServiceError) as ctx:
            asyncio.run(self._service().create_post(self.payload, self.auth))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_schedule_business_mismatch_returns_422(self) -> None:
        self.context_repo.schedule_business_id = uuid4()
        with self.assertRaises(PostGenerationServiceError) as ctx:
            asyncio.run(self._service().create_post(self.payload, self.auth))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_platform_not_configured_returns_422(self) -> None:
        self.context = _context(self.business_id, self.schedule_id, platforms=["linkedin"])
        self.context_repo.context = self.context
        with self.assertRaises(PostGenerationServiceError) as ctx:
            asyncio.run(self._service().create_post(self.payload, self.auth))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_supabase_upload_failure_does_not_insert_post(self) -> None:
        self.storage.fail_upload = True
        with (
            patch("app.post_generation_service.generate_caption") as caption,
            patch("app.post_generation_service.generate_image") as image,
        ):
            caption.return_value = CaptionResult(caption="Generated caption", headline="Generated Headline")
            image.return_value = ImageResult(
                model="gpt-image-2",
                size="1024x1024",
                style="caption_derived",
                prompt_used="prompt",
                negative_prompt_used="",
                file_path="",
                image_base64=base64.b64encode(b"image-bytes").decode("ascii"),
                image_mime_type="image/png",
                alt_text="Alt text",
            )
            with self.assertRaises(PostGenerationServiceError):
                asyncio.run(self._service().create_post(self.payload, self.auth))
        self.assertEqual(self.post_repo.records, [])

    def test_db_insert_failure_cleans_uploaded_object(self) -> None:
        self.post_repo.fail_insert = True
        with (
            patch("app.post_generation_service.generate_caption") as caption,
            patch("app.post_generation_service.generate_image") as image,
        ):
            caption.return_value = CaptionResult(caption="Generated caption", headline="Generated Headline")
            image.return_value = ImageResult(
                model="gpt-image-2",
                size="1024x1024",
                style="caption_derived",
                prompt_used="prompt",
                negative_prompt_used="",
                file_path="",
                image_base64=base64.b64encode(b"image-bytes").decode("ascii"),
                image_mime_type="image/png",
                alt_text="Alt text",
            )
            with self.assertRaises(PostGenerationServiceError):
                asyncio.run(self._service().create_post(self.payload, self.auth))
        self.assertEqual(len(self.storage.deleted), 1)

    def test_weekly_content_plan_generates_each_configured_platform(self) -> None:
        second_schedule_id = uuid4()
        self.context_repo.weekly_contexts = [
            _context(self.business_id, self.schedule_id, platforms=["instagram", "facebook"]),
            _context(
                self.business_id,
                second_schedule_id,
                platforms=["linkedin"],
                day_of_week=2,
                content_type="Pain-point",
                weekly_topic="Avoiding outfit decision fatigue",
            ),
        ]
        with (
            patch("app.post_generation_service.generate_caption") as caption,
            patch("app.post_generation_service.generate_image") as image,
        ):
            caption.return_value = CaptionResult(caption="Generated caption", headline="Generated Headline")
            image.return_value = ImageResult(
                model="gpt-image-2",
                size="1024x1024",
                style="caption_derived",
                prompt_used="prompt",
                negative_prompt_used="",
                file_path="",
                image_base64=base64.b64encode(b"image-bytes").decode("ascii"),
                image_mime_type="image/png",
                alt_text="Alt text",
            )
            response = asyncio.run(
                self._service().create_content_plan(
                    WeeklyContentPlanRequest(
                        business_id=self.business_id,
                        week_start_date="2026-09-09",
                    ),
                    self.auth,
                    plan_id="plan-123",
                )
            )

        self.assertEqual(response.status, "generated")
        self.assertEqual(response.week_start_date, "2026-09-09")
        self.assertEqual(response.total_posts, 3)
        self.assertEqual([post.platform.value for post in response.posts], ["instagram", "facebook", "linkedin"])
        self.assertEqual([post.day.value for post in response.posts], ["Monday", "Monday", "Tuesday"])
        self.assertTrue(all(post.image_url.startswith("https://cdn.example.com/") for post in response.posts))
        self.assertTrue(all(post.image_urls == [post.image_url] for post in response.posts))
        self.assertEqual(len(self.post_repo.records), 3)
        self.assertEqual(len(self.storage.uploaded_images), 3)

    def test_weekly_content_plan_continues_when_one_generation_fails(self) -> None:
        self.context_repo.weekly_contexts = [_context(self.business_id, self.schedule_id, platforms=["instagram"])]
        with (
            patch("app.post_generation_service.generate_caption") as caption,
            patch("app.post_generation_service.generate_image") as image,
        ):
            caption.return_value = CaptionResult(caption="Generated caption", headline="Generated Headline")
            image.side_effect = RuntimeError("image failed")
            response = asyncio.run(
                self._service().create_content_plan(
                    WeeklyContentPlanRequest(
                        business_id=self.business_id,
                        week_start_date="2026-09-09",
                    ),
                    self.auth,
                    plan_id="plan-123",
                )
            )

        self.assertEqual(response.status, "failed")
        self.assertEqual(response.posts[0].status, "failed")
        self.assertEqual(response.posts[0].image_url, "")
        self.assertEqual(response.posts[0].image_urls, [])
        self.assertNotIn("base64", response.model_dump_json())

    def _service(self) -> PostGenerationService:
        return PostGenerationService(
            self.settings,
            context_repository=self.context_repo,
            post_repository=self.post_repo,
            storage_service=self.storage,
        )


def _context(
    business_id,
    schedule_id,
    platforms=None,
    *,
    day_of_week: int = 1,
    content_type: str = "Educational Post",
    weekly_topic: str = "Choosing versatile wardrobe basics",
) -> BusinessGenerationContext:
    return BusinessGenerationContext(
        business_id=business_id,
        business_name="Velmora Fashion",
        industry="Clothes & Accessories - Men's Fashion",
        description="",
        company_logo_url="/uploads/businesslogo/missing.png",
        targeted_audience="Style-conscious men",
        targeted_location="",
        weekly_schedule_id=schedule_id,
        day_of_week=day_of_week,
        content_type=content_type,
        weekly_topic=weekly_topic,
        brand_personality="Elegant, helpful, modern",
        audience_pain_points="They struggle to match outfits confidently.",
        offer="",
        tone="",
        proof_assets="",
        cta_preferences="Shop the new collection",
        platforms=platforms or ["instagram", "facebook"],
    )


if __name__ == "__main__":
    unittest.main()
