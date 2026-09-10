from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.post_generation_service import PostGenerationServiceError  # noqa: E402
from app.schemas import ContentTypeEnum, DayEnum, PlatformEnum, PublicContentPlanPost, PublicContentPlanResponse  # noqa: E402
from scripts.generate_weekly_content import current_monday, generate_for_all_active_businesses  # noqa: E402


class FakeBusinessRepository:
    business_ids = []

    def __init__(self, settings) -> None:
        self.settings = settings

    def fetch_active_business_ids(self):
        return self.business_ids


class WeeklyContentGeneratorTests(unittest.TestCase):
    def test_current_monday(self) -> None:
        self.assertEqual(current_monday(date(2026, 9, 9)), date(2026, 9, 7))
        self.assertEqual(current_monday(date(2026, 9, 7)), date(2026, 9, 7))

    def test_multiple_businesses_continue_after_failure(self) -> None:
        first_business = uuid4()
        second_business = uuid4()
        FakeBusinessRepository.business_ids = [first_business, second_business]
        first_response = _plan_response(first_business, generated=2, skipped=1, failed=0)
        service = AsyncMock()
        service.create_content_plan.side_effect = [
            first_response,
            PostGenerationServiceError(503, "Database is unavailable."),
        ]

        with (
            patch("scripts.generate_weekly_content.get_settings"),
            patch("scripts.generate_weekly_content.BusinessContextRepository", FakeBusinessRepository),
            patch("scripts.generate_weekly_content.PostGenerationService", return_value=service),
        ):
            summary = asyncio.run(
                generate_for_all_active_businesses(
                    week_start_date=date(2026, 9, 7),
                )
            )

        self.assertEqual(summary.businesses_total, 2)
        self.assertEqual(summary.businesses_succeeded, 1)
        self.assertEqual(summary.businesses_failed, 1)
        self.assertEqual(summary.posts_generated, 2)
        self.assertEqual(summary.posts_skipped, 1)
        self.assertEqual(summary.posts_failed, 0)
        self.assertEqual(service.create_content_plan.call_count, 2)
        self.assertTrue(all(call.kwargs["skip_existing"] for call in service.create_content_plan.call_args_list))

    def test_incomplete_schedule_skip_is_counted(self) -> None:
        business_id = uuid4()
        FakeBusinessRepository.business_ids = [business_id]
        service = AsyncMock()
        service.create_content_plan.return_value = _plan_response(business_id, generated=0, skipped=1, failed=0)

        with (
            patch("scripts.generate_weekly_content.get_settings"),
            patch("scripts.generate_weekly_content.BusinessContextRepository", FakeBusinessRepository),
            patch("scripts.generate_weekly_content.PostGenerationService", return_value=service),
        ):
            summary = asyncio.run(
                generate_for_all_active_businesses(
                    week_start_date=date(2026, 9, 7),
                )
            )

        self.assertEqual(summary.businesses_total, 1)
        self.assertEqual(summary.businesses_succeeded, 1)
        self.assertEqual(summary.posts_generated, 0)
        self.assertEqual(summary.posts_skipped, 1)

    def test_no_configured_schedules_is_safe_skip(self) -> None:
        business_id = uuid4()
        FakeBusinessRepository.business_ids = [business_id]
        service = AsyncMock()
        service.create_content_plan.side_effect = PostGenerationServiceError(404, "No weekly schedules found for this business.")

        with (
            patch("scripts.generate_weekly_content.get_settings"),
            patch("scripts.generate_weekly_content.BusinessContextRepository", FakeBusinessRepository),
            patch("scripts.generate_weekly_content.PostGenerationService", return_value=service),
        ):
            summary = asyncio.run(
                generate_for_all_active_businesses(
                    week_start_date=date(2026, 9, 7),
                )
            )

        self.assertEqual(summary.businesses_total, 1)
        self.assertEqual(summary.businesses_succeeded, 1)
        self.assertEqual(summary.businesses_failed, 0)
        self.assertEqual(summary.posts_generated, 0)
        self.assertEqual(summary.posts_skipped, 0)

    def test_dry_run_does_not_call_generation_service(self) -> None:
        FakeBusinessRepository.business_ids = [uuid4(), uuid4()]
        with (
            patch("scripts.generate_weekly_content.get_settings"),
            patch("scripts.generate_weekly_content.BusinessContextRepository", FakeBusinessRepository),
            patch("scripts.generate_weekly_content.PostGenerationService") as service_class,
        ):
            summary = asyncio.run(
                generate_for_all_active_businesses(
                    week_start_date=date(2026, 9, 7),
                    dry_run=True,
                )
            )

        self.assertEqual(summary.businesses_total, 2)
        service_class.assert_not_called()


def _plan_response(business_id, *, generated: int, skipped: int, failed: int) -> PublicContentPlanResponse:
    posts = []
    position = 1
    for _ in range(generated):
        posts.append(_post(position=position, status="generated", post_id=uuid4()))
        position += 1
    for _ in range(skipped):
        posts.append(_post(position=position, status="skipped", error="Already generated for this week."))
        position += 1
    for _ in range(failed):
        posts.append(_post(position=position, status="failed", error="Generation failed."))
        position += 1
    return PublicContentPlanResponse(
        plan_id=str(uuid4()),
        status="generated",
        week_start_date="2026-09-07",
        total_posts=len(posts),
        posts=posts,
    )


def _post(*, position: int, status: str, post_id=None, error: str = "") -> PublicContentPlanPost:
    return PublicContentPlanPost(
        position=position,
        post_id=post_id,
        status=status,
        platform=PlatformEnum.instagram,
        day=DayEnum.monday,
        content_type=ContentTypeEnum.educational,
        topic="Configured topic",
        caption="Generated caption" if status == "generated" else "",
        headline="Generated headline" if status == "generated" else "",
        image_url="https://cdn.example.com/post.png" if status == "generated" else "",
        image_urls=["https://cdn.example.com/post.png"] if status == "generated" else [],
        image_mime_type="image/png" if status == "generated" else "",
        alt_text="Alt text" if status == "generated" else "",
        error=error,
    )


if __name__ == "__main__":
    unittest.main()
