from __future__ import annotations

import json
import re
import threading
from collections import deque
from dataclasses import dataclass
from typing import Any

try:
    from langchain_core.prompts import PromptTemplate
except ImportError:  # Backward compatibility with older LangChain versions.
    from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from app.prompt_library import (
    CAPTION_TEMPLATE,
    CONTENT_TYPE_RULES,
    IMAGE_PROMPT_FROM_CAPTION_TEMPLATE,
    PLATFORM_RULES,
    WEEKLY_CONTENT_PLAN_TEMPLATE,
)
from app.schemas import ContentPlanItem, ContentPlanResponse, ContentTypeEnum, DayEnum, GenerateRequest, PlatformEnum, WeeklyContentPlanRequest

_headline_history_lock = threading.Lock()
_headline_history: deque[str] = deque(maxlen=60)


def _build_chain(
    model_name: str,
    api_key: str,
    temperature: float = 0.9,
    base_url: str | None = None,
    default_headers: dict[str, str] | None = None,
):
    kwargs: dict[str, Any] = {
        "model": model_name,
        "temperature": temperature,
        "api_key": api_key,
        "request_timeout": 30,
        "model_kwargs": {"response_format": {"type": "json_object"}},
    }
    if base_url:
        kwargs["base_url"] = base_url
    if default_headers:
        kwargs["default_headers"] = default_headers
    llm = ChatOpenAI(**kwargs)
    prompt = PromptTemplate.from_template(CAPTION_TEMPLATE)
    parser = StrOutputParser()
    return prompt | llm | parser


def _build_image_prompt_chain(
    model_name: str,
    api_key: str,
    base_url: str | None = None,
    default_headers: dict[str, str] | None = None,
):
    kwargs: dict[str, Any] = {
        "model": model_name, 
        "temperature": 0.2, 
        "api_key": api_key,
        "request_timeout": 30,
    }
    if base_url:
        kwargs["base_url"] = base_url
    if default_headers:
        kwargs["default_headers"] = default_headers
    llm = ChatOpenAI(**kwargs)
    prompt = PromptTemplate.from_template(IMAGE_PROMPT_FROM_CAPTION_TEMPLATE)
    parser = StrOutputParser()
    return prompt | llm | parser


def _build_weekly_plan_chain(
    model_name: str,
    api_key: str,
    base_url: str | None = None,
    default_headers: dict[str, str] | None = None,
):
    kwargs: dict[str, Any] = {
        "model": model_name,
        "temperature": 0.7,
        "api_key": api_key,
        "request_timeout": 45,
        "model_kwargs": {"response_format": {"type": "json_object"}},
    }
    if base_url:
        kwargs["base_url"] = base_url
    if default_headers:
        kwargs["default_headers"] = default_headers
    llm = ChatOpenAI(**kwargs)
    prompt = PromptTemplate.from_template(WEEKLY_CONTENT_PLAN_TEMPLATE)
    parser = StrOutputParser()
    return prompt | llm | parser


@dataclass(frozen=True)
class CaptionGenerationResult:
    caption: str
    headline: str


def _extract_json_object(raw: str) -> str | None:
    match = re.search(r"\{[\s\S]*\}", raw)
    return match.group(0) if match else None


def _normalize_text(value: str, max_words: int = 12) -> str:
    words = re.findall(r"[A-Za-z0-9']+", value or "")
    return " ".join(words[:max_words]).strip()


def _headline_title_case(value: str) -> str:
    small = {"and", "or", "for", "to", "of", "in", "on", "at", "a", "an", "the", "with"}
    words = [w for w in (value or "").split(" ") if w]
    out: list[str] = []
    for idx, word in enumerate(words):
        w = word.lower()
        if idx > 0 and w in small:
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out).strip()


def _sanitize_headline(value: str) -> str:
    # Keep overlay-safe characters only.
    text = re.sub(r"[^A-Za-z0-9 '\-]", " ", value or "")
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(" .,!?:;\"'`-")
    words = [w for w in text.split(" ") if w]
    if len(words) > 8:
        words = words[:8]
    text = " ".join(words)
    return _headline_title_case(text)


def _headline_is_overlay_quality(headline: str) -> bool:
    if not headline:
        return False
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 '\-]*", headline):
        return False
    words = [w for w in headline.split(" ") if w]
    if len(words) < 4 or len(words) > 8:
        return False
    if len(headline) > 48:
        return False
    # Avoid repetitive low-value openings.
    bad_starts = ("Discover ", "Learn About ", "Welcome To ", "Introducing ")
    if any(headline.startswith(prefix) for prefix in bad_starts):
        return False
    return True


def _headline_key(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", (value or "").lower())).strip()


def _token_set(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", (value or "").lower()))


def _recent_headlines_for_prompt(limit: int = 12) -> str:
    with _headline_history_lock:
        items = list(_headline_history)[-limit:]
    return " | ".join(items) if items else "none"


def _headline_is_too_similar(candidate: str) -> bool:
    candidate_key = _headline_key(candidate)
    if not candidate_key:
        return True
    candidate_tokens = _token_set(candidate_key)
    with _headline_history_lock:
        recent = list(_headline_history)
    for prev in recent:
        prev_key = _headline_key(prev)
        if candidate_key == prev_key:
            return True
        prev_tokens = _token_set(prev_key)
        if not prev_tokens:
            continue
        overlap = len(candidate_tokens & prev_tokens) / max(len(candidate_tokens | prev_tokens), 1)
        if overlap >= 0.72:
            return True
    return False


def _remember_headline(headline: str) -> None:
    with _headline_history_lock:
        _headline_history.append(headline.strip())


def _parse_caption_result(raw: str) -> CaptionGenerationResult:
    payload: dict[str, object] | None = None
    text = raw.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            payload = parsed
    except json.JSONDecodeError:
        candidate = _extract_json_object(text)
        if candidate:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = None

    if payload is None:
        return CaptionGenerationResult(caption="", headline="")

    caption = str(payload.get("caption", "")).strip()
    headline = _sanitize_headline(str(payload.get("headline", "")).strip())
    if not caption or not headline:
        return CaptionGenerationResult(caption="", headline="")
    return CaptionGenerationResult(caption=caption, headline=headline)


def _coerce_enum(enum_cls, value: object, fallback):
    raw = str(value or "").strip()
    for item in enum_cls:
        if raw == item.value:
            return item
        if raw.lower() == item.value.lower():
            return item
    return fallback


def _canonical_content_type_for_day(day: DayEnum) -> ContentTypeEnum:
    mapping = {
        DayEnum.monday: ContentTypeEnum.educational,
        DayEnum.tuesday: ContentTypeEnum.pain_point,
        DayEnum.wednesday: ContentTypeEnum.case_study,
        DayEnum.thursday: ContentTypeEnum.industry_insight,
        DayEnum.friday: ContentTypeEnum.founder_authority,
        DayEnum.saturday: ContentTypeEnum.automation_tip,
        DayEnum.sunday: ContentTypeEnum.client_testimonial,
    }
    return mapping[day]


def _parse_weekly_plan(raw: str, request: WeeklyContentPlanRequest, plan_id: str) -> ContentPlanResponse:
    payload: dict[str, object] | None = None
    text = raw.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            payload = parsed
    except json.JSONDecodeError:
        candidate = _extract_json_object(text)
        if candidate:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = None

    raw_items = payload.get("items", []) if payload else []
    if not isinstance(raw_items, list):
        raw_items = []

    default_platform = request.platforms[0] if request.platforms else PlatformEnum.linkedin
    used_days: set[DayEnum] = set()
    items: list[ContentPlanItem] = []
    for idx, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, dict):
            continue
        day = _coerce_enum(DayEnum, raw_item.get("day"), DayEnum.monday)
        if day in used_days:
            continue
        used_days.add(day)
        platform = _coerce_enum(PlatformEnum, raw_item.get("platform"), default_platform)
        if platform not in request.platforms:
            platform = default_platform
        content_type = _canonical_content_type_for_day(day)
        item = ContentPlanItem(
            position=len(items) + 1,
            day=day,
            platform=platform,
            content_type=content_type,
            topic=str(raw_item.get("topic", "") or request.theme).strip(),
            angle=str(raw_item.get("angle", "") or request.weekly_goal).strip(),
            hook_direction=str(raw_item.get("hook_direction", "") or "Open with the clearest audience pain point.").strip(),
            cta_direction=str(raw_item.get("cta_direction", "") or request.cta_preference or "Invite the reader to ask for help.").strip(),
            visual_direction=str(raw_item.get("visual_direction", "") or "Create a clean, platform-ready visual aligned to the topic.").strip(),
        )
        items.append(item)
        if len(items) >= request.posts_count:
            break

    fallback_days = [
        DayEnum.monday,
        DayEnum.tuesday,
        DayEnum.wednesday,
        DayEnum.thursday,
        DayEnum.friday,
        DayEnum.saturday,
        DayEnum.sunday,
    ]
    while len(items) < request.posts_count:
        day = next((candidate for candidate in fallback_days if candidate not in used_days), fallback_days[len(items) % len(fallback_days)])
        used_days.add(day)
        items.append(
            ContentPlanItem(
                position=len(items) + 1,
                day=day,
                platform=request.platforms[len(items) % len(request.platforms)] if request.platforms else PlatformEnum.linkedin,
                content_type=_canonical_content_type_for_day(day),
                topic=f"{request.theme}: {day.value} angle",
                angle=f"Connect {request.weekly_goal} to a specific {request.target_audience} problem.",
                hook_direction="Open with a specific pain point or contrarian truth.",
                cta_direction=request.cta_preference or "Invite the reader to ask for the next step.",
                visual_direction="Use a clean, differentiated visual concept tied to the post angle.",
            )
        )

    return ContentPlanResponse(
        plan_id=plan_id,
        status="planned",
        week_start_date=request.week_start_date,
        weekly_goal=request.weekly_goal,
        theme=request.theme,
        total_posts=len(items),
        items=items,
    )


def generate_caption_with_retry(
    payload: GenerateRequest,
    api_key: str,
    model_name: str,
    base_url: str | None = None,
    default_headers: dict[str, str] | None = None,
) -> CaptionGenerationResult:
    chain = _build_chain(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        default_headers=default_headers,
    )

    base_inputs = {
        "business_name": payload.business_name,
        "industry": payload.industry,
        "offer": payload.offer,
        "target_audience": payload.target_audience,
        "audience_pain_points": payload.audience_pain_points,
        "weekly_focus_topic": payload.weekly_focus_topic,
        "day": payload.day.value,
        "content_type": payload.content_type.value,
        "tone": payload.tone,
        "brand_personality": payload.brand_personality,
        "cta_preference": payload.cta_preference,
        "proof_assets": payload.proof_assets or "",
        "platform": payload.platform.value,
        "platform_rules": PLATFORM_RULES[payload.platform],
        "content_type_rules": CONTENT_TYPE_RULES[payload.content_type],
        "recent_headlines": _recent_headlines_for_prompt(),
    }

    retry_template = PromptTemplate.from_template(
        """
Your previous output either did not follow the required format OR repeated a recent headline.
Return strict JSON only with exactly these keys:
- "caption": full post caption text
- "headline": short hook/headline aligned with caption (4-10 words)
- Headline must be new and meaningfully different from these recent headlines:
{recent_headlines}

Previous output:
{previous_output}

Headlines must pass these strict rules:
- 4-8 words
- Title Case
- No hashtags/emojis/quotes
- ASCII letters, digits, spaces, hyphen, apostrophe only
""".strip()
    )

    retry_kwargs: dict[str, Any] = {
        "model": model_name,
        "temperature": 0.2,
        "api_key": api_key,
        "request_timeout": 30,
    }
    if base_url:
        retry_kwargs["base_url"] = base_url
    if default_headers:
        retry_kwargs["default_headers"] = default_headers
    retry_chain = retry_template | ChatOpenAI(**retry_kwargs) | StrOutputParser()

    raw = chain.invoke(base_inputs).strip()
    result = _parse_caption_result(raw)
    if (
        result.caption
        and result.headline
        and _headline_is_overlay_quality(result.headline)
        and not _headline_is_too_similar(result.headline)
    ):
        _remember_headline(result.headline)
        return result

    for _ in range(5):
        raw = retry_chain.invoke(
            {
                "previous_output": raw,
                "recent_headlines": _recent_headlines_for_prompt(),
            }
        ).strip()
        result = _parse_caption_result(raw)
        if (
            result.caption
            and result.headline
            and _headline_is_overlay_quality(result.headline)
            and not _headline_is_too_similar(result.headline)
        ):
            _remember_headline(result.headline)
            return result

    raise RuntimeError("Caption model did not return a valid and sufficiently unique headline/caption.")


def generate_weekly_content_plan(
    request: WeeklyContentPlanRequest,
    plan_id: str,
    recent_posts: str,
    api_key: str,
    model_name: str,
    base_url: str | None = None,
    default_headers: dict[str, str] | None = None,
) -> ContentPlanResponse:
    chain = _build_weekly_plan_chain(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        default_headers=default_headers,
    )
    raw = chain.invoke(
        {
            "business_name": request.business_name,
            "industry": request.industry,
            "offer": request.offer,
            "target_audience": request.target_audience,
            "audience_pain_points": request.audience_pain_points,
            "tone": request.tone,
            "brand_personality": request.brand_personality,
            "cta_preference": request.cta_preference,
            "proof_assets": request.proof_assets,
            "week_start_date": request.week_start_date or "not specified",
            "weekly_goal": request.weekly_goal,
            "theme": request.theme,
            "platforms": ", ".join(platform.value for platform in request.platforms),
            "posts_count": request.posts_count,
            "recent_posts": recent_posts or "none",
        }
    ).strip()
    return _parse_weekly_plan(raw, request, plan_id)


def generate_image_prompt_from_caption(
    payload: GenerateRequest,
    caption: str,
    headline: str,
    logo_instruction: str,
    api_key: str,
    model_name: str,
    base_url: str | None = None,
    default_headers: dict[str, str] | None = None,
) -> str:
    chain = _build_image_prompt_chain(
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        default_headers=default_headers,
    )
    prompt = chain.invoke(
        {
            "business_name": payload.business_name,
            "industry": payload.industry,
            "offer": payload.offer,
            "target_audience": payload.target_audience,
            "audience_pain_points": payload.audience_pain_points,
            "weekly_focus_topic": payload.weekly_focus_topic,
            "content_type": payload.content_type.value,
            "platform": payload.platform.value,
            "tone": payload.tone,
            "brand_personality": payload.brand_personality,
            "caption": caption,
            "logo_instruction": logo_instruction,
        }
    ).strip()
    return prompt
