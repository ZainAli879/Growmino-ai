from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.auth import AuthContext
from app.config import get_settings
from app.database import BusinessContextRepository, DatabaseConfigurationError, DatabaseUnavailableError
from app.post_generation_service import PostGenerationService, PostGenerationServiceError
from app.schemas import PublicContentPlanPost, WeeklyContentPlanRequest


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("weekly-content-generator")


@dataclass(frozen=True)
class WeeklyGenerationSummary:
    businesses_total: int = 0
    businesses_succeeded: int = 0
    businesses_failed: int = 0
    posts_generated: int = 0
    posts_skipped: int = 0
    posts_failed: int = 0


def current_monday(today: date | None = None) -> date:
    current = today or datetime.now().date()
    return current - timedelta(days=current.weekday())


async def generate_for_all_active_businesses(
    *,
    week_start_date: date,
    dry_run: bool = False,
) -> WeeklyGenerationSummary:
    settings = get_settings()
    business_repository = BusinessContextRepository(settings)
    business_ids = await asyncio.to_thread(business_repository.fetch_active_business_ids)
    logger.info("Weekly generation started week_start_date=%s active_businesses=%s dry_run=%s", week_start_date, len(business_ids), dry_run)

    summary = WeeklyGenerationSummary(businesses_total=len(business_ids))
    succeeded = 0
    failed_businesses = 0
    generated_posts = 0
    skipped_posts = 0
    failed_posts = 0

    if dry_run:
        for business_id in business_ids:
            logger.info("Dry run: would generate configured weekly posts for business_id=%s", business_id)
        return WeeklyGenerationSummary(businesses_total=len(business_ids))

    service = PostGenerationService(settings)
    for business_id in business_ids:
        auth = AuthContext(user_id="", business_id=str(business_id))
        plan_id = str(uuid4())
        try:
            response = await service.create_content_plan(
                WeeklyContentPlanRequest(
                    business_id=business_id,
                    week_start_date=week_start_date,
                ),
                auth,
                plan_id=plan_id,
                skip_existing=True,
            )
            for post in response.posts:
                _log_post_result(business_id=str(business_id), post=post)
            business_generated = sum(1 for post in response.posts if post.status == "generated")
            business_skipped = sum(1 for post in response.posts if post.status == "skipped")
            business_failed = sum(1 for post in response.posts if post.status == "failed")
            generated_posts += business_generated
            skipped_posts += business_skipped
            failed_posts += business_failed
            succeeded += 1
            logger.info(
                "Weekly generation completed business_id=%s plan_id=%s status=%s generated=%s skipped=%s failed=%s",
                business_id,
                response.plan_id,
                response.status,
                business_generated,
                business_skipped,
                business_failed,
            )
        except PostGenerationServiceError as exc:
            if exc.status_code == 404 and "weekly schedules" in exc.message.lower():
                succeeded += 1
                logger.info("SKIPPED business_id=%s reason=no_configured_schedules", business_id)
                continue
            failed_businesses += 1
            logger.error("Weekly generation failed business_id=%s status_code=%s error=%s", business_id, exc.status_code, exc.message)
        except Exception as exc:
            failed_businesses += 1
            logger.exception("Weekly generation crashed business_id=%s error=%s", business_id, str(exc))

    summary = WeeklyGenerationSummary(
        businesses_total=len(business_ids),
        businesses_succeeded=succeeded,
        businesses_failed=failed_businesses,
        posts_generated=generated_posts,
        posts_skipped=skipped_posts,
        posts_failed=failed_posts,
    )
    logger.info(
        "Weekly generation finished businesses_total=%s businesses_succeeded=%s businesses_failed=%s posts_generated=%s posts_skipped=%s posts_failed=%s",
        summary.businesses_total,
        summary.businesses_succeeded,
        summary.businesses_failed,
        summary.posts_generated,
        summary.posts_skipped,
        summary.posts_failed,
    )
    return summary


def _log_post_result(*, business_id: str, post: PublicContentPlanPost) -> None:
    day = post.day.value if hasattr(post.day, "value") else str(post.day)
    platform = post.platform.value if hasattr(post.platform, "value") else str(post.platform or "")
    if post.status == "generated":
        logger.info("GENERATED business_id=%s day=%s platform=%s post_id=%s", business_id, day, platform, post.post_id)
    elif post.status == "skipped":
        if post.error == "incomplete_schedule":
            logger.info(
                "SKIPPED business_id=%s weekly_schedule_id=%s day=%s reason=incomplete_schedule",
                business_id,
                post.weekly_schedule_id,
                day,
            )
        else:
            logger.info("SKIPPED business_id=%s day=%s platform=%s reason=already_generated", business_id, day, platform)
    else:
        logger.error("FAILED business_id=%s day=%s platform=%s error=%s", business_id, day, platform, post.error)


def _parse_week_start(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use YYYY-MM-DD for --week-start-date.") from exc
    if parsed.weekday() != 0:
        raise argparse.ArgumentTypeError("--week-start-date must be a Monday.")
    return parsed


async def main() -> None:
    parser = argparse.ArgumentParser(description="Generate weekly GrowMino AI posts for every active business.")
    parser.add_argument("--once", action="store_true", help="Run one weekly generation pass and exit.")
    parser.add_argument("--week-start-date", type=_parse_week_start, default=None, help="Optional Monday date for manual testing, format YYYY-MM-DD.")
    parser.add_argument("--dry-run", action="store_true", help="List active businesses without generating posts.")
    args = parser.parse_args()

    if not args.once:
        parser.error("This script is intentionally one-shot. Use --once or run it from the systemd timer.")

    week_start_date = args.week_start_date or current_monday()
    try:
        await generate_for_all_active_businesses(week_start_date=week_start_date, dry_run=args.dry_run)
    except DatabaseConfigurationError as exc:
        logger.error("Database configuration error: %s", str(exc))
        raise SystemExit(2) from exc
    except DatabaseUnavailableError as exc:
        logger.error("Database unavailable: %s", str(exc))
        raise SystemExit(3) from exc


if __name__ == "__main__":
    asyncio.run(main())
