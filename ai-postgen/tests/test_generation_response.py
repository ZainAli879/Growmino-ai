from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas import (  # noqa: E402
    ContentPlanItem,
    ContentPlanResponse,
    ContentTypeEnum,
    DayEnum,
    GenerateResponse,
    MetaInfo,
    OpenAIImageInfo,
    PlatformEnum,
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
            },
        )
        self.env.start()
        from app.api import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.env.stop()

    def test_default_generate_response_is_clean_for_frontend(self) -> None:
        with patch("app.api._run_generation") as run_generation:
            run_generation.return_value = _generated_response()
            response = self.client.post("/api/v1/posts", json=_request_payload())

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(
            set(payload.keys()),
            {
                "post_id",
                "status",
                "platform",
                "day",
                "content_type",
                "business_name",
                "caption",
                "headline",
                "image_url",
                "image_data_url",
                "image_base64",
                "image_mime_type",
                "alt_text",
            },
        )
        self.assertEqual(payload["image_url"], "")
        self.assertEqual(payload["image_data_url"], "data:image/png;base64,aW1hZ2U=")
        self.assertEqual(payload["image_base64"], "aW1hZ2U=")
        self.assertEqual(payload["image_mime_type"], "image/png")
        self.assertNotIn("openai_image", payload)
        self.assertNotIn("trace", payload)
        self.assertNotIn("qa", payload)

    def test_debug_generate_response_keeps_internal_details(self) -> None:
        with patch("app.api._run_generation") as run_generation:
            run_generation.return_value = _generated_response()
            response = self.client.post("/api/v1/posts?debug=true", json=_request_payload())

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("openai_image", payload)
        self.assertEqual(payload["openai_image"]["public_url"], "")
        self.assertEqual(payload["openai_image"]["image_data_url"], "data:image/png;base64,aW1hZ2U=")

    def test_default_weekly_plan_response_is_clean_for_frontend(self) -> None:
        with (
            patch("app.api.generate_content_plan") as generate_plan,
            patch("app.api._run_generation") as run_generation,
        ):
            generate_plan.return_value = _weekly_plan()
            run_generation.return_value = _generated_response()
            response = self.client.post("/api/v1/content-plans", json=_weekly_request_payload())

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(
            set(payload.keys()),
            {
                "plan_id",
                "status",
                "week_start_date",
                "weekly_goal",
                "theme",
                "total_posts",
                "posts",
            },
        )
        self.assertNotIn("items", payload)
        self.assertEqual(payload["status"], "generated")
        self.assertEqual(len(payload["posts"]), 1)
        post = payload["posts"][0]
        self.assertEqual(
            set(post.keys()),
            {
                "position",
                "post_id",
                "status",
                "platform",
                "day",
                "content_type",
                "business_name",
                "topic",
                "caption",
                "headline",
                "image_url",
                "image_base64",
                "image_data_url",
                "image_mime_type",
                "alt_text",
                "error",
            },
        )
        self.assertEqual(post["post_id"], "post-123")
        self.assertEqual(post["image_url"], "")
        self.assertEqual(post["image_base64"], "aW1hZ2U=")
        self.assertEqual(post["image_data_url"], "data:image/png;base64,aW1hZ2U=")
        self.assertEqual(post["alt_text"], "Generated alt text.")
        self.assertNotIn("generated_caption", post)

    def test_debug_weekly_plan_response_keeps_internal_items(self) -> None:
        with (
            patch("app.api.generate_content_plan") as generate_plan,
            patch("app.api._run_generation") as run_generation,
        ):
            generate_plan.return_value = _weekly_plan()
            run_generation.return_value = _generated_response()
            response = self.client.post("/api/v1/content-plans?debug=true", json=_weekly_request_payload())

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("items", payload)
        self.assertNotIn("posts", payload)
        self.assertEqual(payload["items"][0]["generated_image_base64"], "aW1hZ2U=")
        self.assertEqual(payload["items"][0]["generated_alt_text"], "Generated alt text.")


def _request_payload() -> dict:
    return {
        "business_name": "GrowMino AI",
        "industry": "AI content automation",
        "offer": "AI-generated captions and visuals",
        "target_audience": "Founders",
        "audience_pain_points": "Inconsistent posting",
        "weekly_focus_topic": "Creating posts from one brief",
        "day": "Monday",
        "content_type": "Educational",
        "tone": "Clear",
        "brand_personality": "Modern",
        "platform": "linkedin",
    }


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


def _generated_response() -> GenerateResponse:
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
