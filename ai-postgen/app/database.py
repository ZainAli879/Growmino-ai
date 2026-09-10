from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
import json
from typing import Iterator
from uuid import UUID

try:
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
except Exception:  # pragma: no cover - exercised when dependency is not installed
    ConnectionPool = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]

from app.config import Settings


class DatabaseConfigurationError(RuntimeError):
    pass


class DatabaseUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class BusinessGenerationContext:
    business_id: UUID
    business_name: str
    industry: str
    description: str
    company_logo_url: str
    targeted_audience: str
    targeted_location: str
    weekly_schedule_id: UUID
    day_of_week: int
    content_type: str
    weekly_topic: str
    brand_personality: str
    audience_pain_points: str
    offer: str
    tone: str
    proof_assets: str
    cta_preferences: str
    platforms: list[str]


@dataclass(frozen=True)
class BusinessBaseContext:
    business_id: UUID
    business_name: str
    industry: str
    description: str
    company_logo_url: str
    targeted_audience: str
    targeted_location: str


@dataclass(frozen=True)
class WeeklyScheduleContext:
    weekly_schedule_id: UUID
    business_id: UUID
    day_of_week: int
    content_type: str
    weekly_topic: str
    brand_personality: str
    audience_pain_points: str
    offer: str
    tone: str
    proof_assets: str
    cta_preferences: str
    platforms: list[str]


@dataclass(frozen=True)
class PersistGeneratedPostInput:
    post_id: UUID
    business_id: UUID
    weekly_schedule_id: UUID
    platform: str
    title: str
    description: str
    hashtags: str
    image_urls_json: str
    content_type: str
    day_of_week: int
    tone: str
    offer: str
    target_audience: str
    audience_pain_points: str
    weekly_focus_topics: str
    brand_personality: str
    cta: str
    ai_prompt_meta_json: str
    created_by_user_id: UUID | None
    week_start_date: date | None = None


_pool: ConnectionPool | None = None
_pool_database_url: str = ""


def get_database_pool(settings: Settings) -> ConnectionPool:
    global _pool, _pool_database_url
    if ConnectionPool is None or dict_row is None:
        raise DatabaseConfigurationError("PostgreSQL dependency is not installed. Install psycopg[binary,pool].")
    if not settings.database_url:
        raise DatabaseConfigurationError("DATABASE_URL is required for production post generation.")
    if "business-management" not in settings.database_url:
        raise DatabaseConfigurationError("DATABASE_URL must point to the business-management database.")
    if _pool is None or _pool_database_url != settings.database_url:
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=settings.database_pool_min_size,
            max_size=settings.database_pool_max_size,
            kwargs={"row_factory": dict_row},
        )
        _pool_database_url = settings.database_url
    return _pool


@contextmanager
def database_connection(settings: Settings) -> Iterator:
    try:
        pool = get_database_pool(settings)
        with pool.connection() as conn:
            yield conn
    except DatabaseConfigurationError:
        raise
    except Exception as exc:
        raise DatabaseUnavailableError("Database is unavailable.") from exc


class BusinessContextRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch_generation_context(
        self,
        *,
        business_id: UUID,
        weekly_schedule_id: UUID,
    ) -> BusinessGenerationContext | None:
        query = """
            SELECT
                b.id AS business_id,
                b.business_name,
                CONCAT(c.title, ' - ', sc.title) AS industry,
                b.description,
                b.logo AS company_logo_url,
                bmp.targeted_audience,
                bmp.targeted_location,
                bws.id AS weekly_schedule_id,
                bws.day_of_week,
                bws.content_type,
                bws.weekly_topic,
                bws.brand_personality,
                bws.pain_point AS audience_pain_points,
                bws.offer,
                bws.tone,
                bws.proof_assets,
                bws.cta_preferences,
                bws.platforms
            FROM businesses b
            JOIN categories c
                ON c.id = b.category_id
            JOIN subcategories sc
                ON sc.id = b.subcategory_id
            LEFT JOIN business_marketing_profiles bmp
                ON bmp.business_id = b.id
            JOIN business_weekly_schedules bws
                ON bws.business_id = b.id
            WHERE b.id = %(business_id)s
              AND bws.id = %(weekly_schedule_id)s
        """
        with database_connection(self._settings) as conn:
            row = conn.execute(
                query,
                {"business_id": business_id, "weekly_schedule_id": weekly_schedule_id},
            ).fetchone()
        if row is None:
            return None
        return BusinessGenerationContext(
            **_generation_context_kwargs(row),
        )

    def fetch_weekly_generation_contexts(self, *, business_id: UUID) -> list[BusinessGenerationContext]:
        base_context = self.fetch_business_base_context(business_id=business_id, active_only=True)
        if base_context is None:
            return []
        schedules = self.fetch_weekly_schedule_contexts(business_id=business_id)
        return [_combine_business_and_schedule(base_context, schedule) for schedule in schedules]

    def fetch_business_base_context(self, *, business_id: UUID, active_only: bool = False) -> BusinessBaseContext | None:
        query = """
            SELECT
                b.id AS business_id,
                b.business_name,
                CONCAT(c.title, ' - ', sc.title) AS industry,
                b.description,
                b.logo AS company_logo_url,
                bmp.targeted_audience,
                bmp.targeted_location,
                bws.id AS weekly_schedule_id,
                bws.day_of_week,
                bws.content_type,
                bws.weekly_topic,
                bws.brand_personality,
                bws.pain_point AS audience_pain_points,
                bws.offer,
                bws.tone,
                bws.proof_assets,
                bws.cta_preferences,
                bws.platforms
            FROM businesses b
            JOIN categories c
                ON c.id = b.category_id
            JOIN subcategories sc
                ON sc.id = b.subcategory_id
            LEFT JOIN business_marketing_profiles bmp
                ON bmp.business_id = b.id
            WHERE b.id = %(business_id)s
        """
        if active_only:
            query += "\n              AND b.is_active = true"
        with database_connection(self._settings) as conn:
            rows = conn.execute(query, {"business_id": business_id}).fetchall()
        if not rows:
            return None
        return BusinessBaseContext(**_business_base_context_kwargs(rows[0]))

    def fetch_weekly_schedule_contexts(self, *, business_id: UUID) -> list[WeeklyScheduleContext]:
        query = """
            SELECT
                id AS weekly_schedule_id,
                business_id,
                day_of_week,
                content_type,
                weekly_topic,
                brand_personality,
                pain_point AS audience_pain_points,
                offer,
                tone,
                proof_assets,
                cta_preferences,
                platforms
            FROM business_weekly_schedules
            WHERE business_id = %(business_id)s
            ORDER BY day_of_week ASC
        """
        with database_connection(self._settings) as conn:
            rows = conn.execute(query, {"business_id": business_id}).fetchall()
        return [WeeklyScheduleContext(**_weekly_schedule_context_kwargs(row)) for row in rows]

    def fetch_active_business_ids(self) -> list[UUID]:
        query = """
            SELECT id
            FROM businesses
            WHERE is_active = true
            ORDER BY id ASC
        """
        with database_connection(self._settings) as conn:
            rows = conn.execute(query).fetchall()
        return [UUID(str(row["id"])) for row in rows]

    def business_exists(self, *, business_id: UUID) -> bool:
        with database_connection(self._settings) as conn:
            row = conn.execute(
                "SELECT 1 FROM businesses WHERE id = %(business_id)s",
                {"business_id": business_id},
            ).fetchone()
        return row is not None

    def schedule_exists(self, *, weekly_schedule_id: UUID) -> bool:
        with database_connection(self._settings) as conn:
            row = conn.execute(
                "SELECT business_id FROM business_weekly_schedules WHERE id = %(weekly_schedule_id)s",
                {"weekly_schedule_id": weekly_schedule_id},
            ).fetchone()
        return row is not None

    def fetch_schedule_business_id(self, *, weekly_schedule_id: UUID) -> UUID | None:
        with database_connection(self._settings) as conn:
            row = conn.execute(
                "SELECT business_id FROM business_weekly_schedules WHERE id = %(weekly_schedule_id)s",
                {"weekly_schedule_id": weekly_schedule_id},
            ).fetchone()
        if row is None:
            return None
        return UUID(str(row["business_id"]))


class PostRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def insert_generated_post(self, record: PersistGeneratedPostInput) -> None:
        query = """
            INSERT INTO posts (
                id,
                business_id,
                weekly_schedule_id,
                platform,
                title,
                description,
                hashtags,
                image_urls,
                status,
                content_type,
                day_of_week,
                tone,
                offer,
                target_audience,
                audience_pain_points,
                weekly_focus_topics,
                brand_personality,
                cta,
                source,
                ai_prompt_meta,
                week_start_date,
                is_active,
                created_by_user_id
            )
            VALUES (
                %(id)s,
                %(business_id)s,
                %(weekly_schedule_id)s,
                %(platform)s,
                %(title)s,
                %(description)s,
                %(hashtags)s,
                %(image_urls)s,
                'generated',
                %(content_type)s,
                %(day_of_week)s,
                %(tone)s,
                %(offer)s,
                %(target_audience)s,
                %(audience_pain_points)s,
                %(weekly_focus_topics)s,
                %(brand_personality)s,
                %(cta)s,
                'ai',
                %(ai_prompt_meta)s,
                %(week_start_date)s,
                true,
                %(created_by_user_id)s
            )
        """
        params = {
            "id": record.post_id,
            "business_id": record.business_id,
            "weekly_schedule_id": record.weekly_schedule_id,
            "platform": record.platform,
            "title": record.title,
            "description": record.description,
            "hashtags": record.hashtags,
            "image_urls": record.image_urls_json,
            "content_type": record.content_type,
            "day_of_week": record.day_of_week,
            "tone": record.tone,
            "offer": record.offer,
            "target_audience": record.target_audience,
            "audience_pain_points": record.audience_pain_points,
            "weekly_focus_topics": record.weekly_focus_topics,
            "brand_personality": record.brand_personality,
            "cta": record.cta,
            "ai_prompt_meta": record.ai_prompt_meta_json,
            "week_start_date": record.week_start_date,
            "created_by_user_id": record.created_by_user_id,
        }
        with database_connection(self._settings) as conn:
            with conn.transaction():
                conn.execute(query, params)

    def generated_post_exists(
        self,
        *,
        business_id: UUID,
        weekly_schedule_id: UUID,
        platform: str,
        week_start_date: str,
    ) -> bool:
        query = """
            SELECT 1
            FROM posts
            WHERE business_id = %(business_id)s
              AND weekly_schedule_id = %(weekly_schedule_id)s
              AND platform = %(platform)s
              AND source = 'ai'
              AND COALESCE(is_active, true) = true
              AND week_start_date = %(week_start_date)s
            LIMIT 1
        """
        params = {
            "business_id": business_id,
            "weekly_schedule_id": weekly_schedule_id,
            "platform": platform,
            "week_start_date": week_start_date,
        }
        with database_connection(self._settings) as conn:
            row = conn.execute(query, params).fetchone()
        return row is not None


def image_urls_json(urls: list[str]) -> str:
    return json.dumps(urls, ensure_ascii=True)


def _parse_platforms(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        text = str(value).strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            raw_items = parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            raw_items = [item.strip() for item in text.split(",")]
    return [str(item).strip().lower() for item in raw_items if str(item).strip()]


def _text(value: object) -> str:
    return str(value or "").strip()


def _generation_context_kwargs(row: dict) -> dict:
    return {
        "business_id": UUID(str(row["business_id"])),
        "business_name": _text(row.get("business_name")),
        "industry": _text(row.get("industry")),
        "description": _text(row.get("description")),
        "company_logo_url": _text(row.get("company_logo_url")),
        "targeted_audience": _text(row.get("targeted_audience")),
        "targeted_location": _text(row.get("targeted_location")),
        "weekly_schedule_id": UUID(str(row["weekly_schedule_id"])),
        "day_of_week": int(row.get("day_of_week") or 0),
        "content_type": _text(row.get("content_type")),
        "weekly_topic": _text(row.get("weekly_topic")),
        "brand_personality": _text(row.get("brand_personality")),
        "audience_pain_points": _text(row.get("audience_pain_points")),
        "offer": _text(row.get("offer")),
        "tone": _text(row.get("tone")),
        "proof_assets": _text(row.get("proof_assets")),
        "cta_preferences": _text(row.get("cta_preferences")),
        "platforms": _parse_platforms(row.get("platforms")),
    }


def _business_base_context_kwargs(row: dict) -> dict:
    return {
        "business_id": UUID(str(row["business_id"])),
        "business_name": _text(row.get("business_name")),
        "industry": _text(row.get("industry")),
        "description": _text(row.get("description")),
        "company_logo_url": _text(row.get("company_logo_url")),
        "targeted_audience": _text(row.get("targeted_audience")),
        "targeted_location": _text(row.get("targeted_location")),
    }


def _weekly_schedule_context_kwargs(row: dict) -> dict:
    return {
        "weekly_schedule_id": UUID(str(row["weekly_schedule_id"])),
        "business_id": UUID(str(row["business_id"])),
        "day_of_week": int(row.get("day_of_week") or 0),
        "content_type": _text(row.get("content_type")),
        "weekly_topic": _text(row.get("weekly_topic")),
        "brand_personality": _text(row.get("brand_personality")),
        "audience_pain_points": _text(row.get("audience_pain_points")),
        "offer": _text(row.get("offer")),
        "tone": _text(row.get("tone")),
        "proof_assets": _text(row.get("proof_assets")),
        "cta_preferences": _text(row.get("cta_preferences")),
        "platforms": _parse_platforms(row.get("platforms")),
    }


def _combine_business_and_schedule(
    business: BusinessBaseContext,
    schedule: WeeklyScheduleContext,
) -> BusinessGenerationContext:
    return BusinessGenerationContext(
        business_id=business.business_id,
        business_name=business.business_name,
        industry=business.industry,
        description=business.description,
        company_logo_url=business.company_logo_url,
        targeted_audience=business.targeted_audience,
        targeted_location=business.targeted_location,
        weekly_schedule_id=schedule.weekly_schedule_id,
        day_of_week=schedule.day_of_week,
        content_type=schedule.content_type,
        weekly_topic=schedule.weekly_topic,
        brand_personality=schedule.brand_personality,
        audience_pain_points=schedule.audience_pain_points,
        offer=schedule.offer,
        tone=schedule.tone,
        proof_assets=schedule.proof_assets,
        cta_preferences=schedule.cta_preferences,
        platforms=schedule.platforms,
    )
