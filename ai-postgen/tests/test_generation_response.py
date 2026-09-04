from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas import (  # noqa: E402
    ContentPlanItem,
    ContentPlanResponse,
    ContentTypeEnum,
    DayEnum,
    PlatformEnum,
    PublicGenerateResponse,
)


class GenerationResponseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-openai-key",
                "TEXT_PROVIDER": "openai",
                "IMAGE_PROVIDER": "openai",
                "API_AUTH_REQUIRED": "false",
                "PUBLIC_BASE_URL": "https://api.example.com",
                "DATABASE_URL": "postgresql://app:pass@127.0.0.1:5432/business-management",
                "SUPABASE_URL": "https://project.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
            },
        )
        self.env.start()
        from app.api import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.env.stop()

    def test_generate_response_is_id_driven_and_url_based(self) -> None:
        business_id = uuid4()
        schedule_id = uuid4()
        post_id = uuid4()
        with patch("app.api.PostGenerationService") as service_class:
            service_class.return_value.create_post = AsyncMock(
                return_value=PublicGenerateResponse(
                    post_id=post_id,
                    business_id=business_id,
                    weekly_schedule_id=schedule_id,
                    status="generated",
                    platform=PlatformEnum.linkedin,
                    day=DayEnum.monday,
                    content_type=ContentTypeEnum.educational,
                    business_name="Velmora Fashion",
                    caption="Generated caption.",
                    headline="Generated Headline",
                    image_url="https://project.supabase.co/storage/v1/object/public/post-media/image.png",
                    image_urls=["https://project.supabase.co/storage/v1/object/public/post-media/image.png"],
                    image_mime_type="image/png",
                    alt_text="Generated alt text.",
                )
            )
            response = self.client.post(
                "/api/v1/posts",
                json={
                    "business_id": str(business_id),
                    "weekly_schedule_id": str(schedule_id),
                    "platform": "linkedin",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(
            set(payload.keys()),
            {
                "post_id",
                "business_id",
                "weekly_schedule_id",
                "status",
                "platform",
                "day",
                "content_type",
                "business_name",
                "caption",
                "headline",
                "image_url",
                "image_urls",
                "image_mime_type",
                "alt_text",
            },
        )
        self.assertEqual(payload["post_id"], str(post_id))
        self.assertEqual(payload["business_id"], str(business_id))
        self.assertEqual(payload["weekly_schedule_id"], str(schedule_id))
        self.assertEqual(payload["image_url"], payload["image_urls"][0])
        self.assertNotIn("image_base64", payload)
        self.assertNotIn("image_data_url", payload)
        self.assertNotIn("openai_image", payload)
        self.assertNotIn("trace", payload)
        self.assertNotIn("qa", payload)

    def test_default_weekly_plan_response_still_generates_posts(self) -> None:
        with (
            patch("app.api.generate_content_plan") as generate_plan,
            patch("app.api._run_generation") as run_generation,
        ):
            generate_plan.return_value = _weekly_plan()
            run_generation.return_value = _generated_response_for_weekly()
            response = self.client.post("/api/v1/content-plans", json=_weekly_request_payload())

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "generated")
        self.assertEqual(len(payload["posts"]), 1)
        self.assertEqual(payload["posts"][0]["image_base64"], "aW1hZ2U=")


def _weekly_request_payload() -> dict:
    return {
        "business_name": "GrowMino AI",
        "industry": "AI content automation",
        "offer": "AI-generated captions and visuals",
        "target_audience": "Founders",
        "audience_pain_points": "Inconsistent posting",
        "tone": "Clear",
        "brand_personality": "Modern",
        "week_start_date": "2026-09-01",
        "weekly_goal": "Educate prospects",
        "theme": "AI social media automation",
        "platforms": ["linkedin"],
        "posts_count": 1,
    }


def _weekly_plan() -> ContentPlanResponse:
    return ContentPlanResponse(
        plan_id="plan-123",
        status="planned",
        week_start_date="2026-09-01",
        weekly_goal="Educate prospects",
        theme="AI social media automation",
        total_posts=1,
        items=[
            ContentPlanItem(
                position=1,
                day=DayEnum.monday,
                platform=PlatformEnum.linkedin,
                content_type=ContentTypeEnum.educational,
                topic="One brief to one week of content",
                angle="Teach the workflow",
                hook_direction="Start with posting pain",
                cta_direction="Ask for a demo",
                visual_direction="Show one brief becoming posts",
            )
        ],
    )


def _generated_response_for_weekly():
    from app.schemas import GenerateResponse, MetaInfo, OpenAIImageInfo

    return GenerateResponse(
        post_id="post-123",
        meta=MetaInfo(
            platform=PlatformEnum.linkedin,
            day=DayEnum.monday,
            content_type=ContentTypeEnum.educational,
            business_name="GrowMino AI",
        ),
        caption="Generated caption.",
        headline="Generated Headline",
        openai_image=OpenAIImageInfo(
            model="gpt-image-2",
            size="1024x1024",
            style="caption_derived",
            prompt_used="internal prompt",
            negative_prompt_used="",
            file_path="",
            public_url="",
            image_data_url="data:image/png;base64,aW1hZ2U=",
            image_base64="aW1hZ2U=",
            image_mime_type="image/png",
            alt_text="Generated alt text.",
        ),
    )


if __name__ == "__main__":
    unittest.main()
