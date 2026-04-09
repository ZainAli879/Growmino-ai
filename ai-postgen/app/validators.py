from __future__ import annotations

import re

from app.prompt_library import DAY_CONTENT_MAPPING
from app.schemas import ContentTypeEnum, DayEnum, PlatformEnum

CTA_VERBS = {
    "comment",
    "dm",
    "message",
    "share",
    "save",
    "click",
    "reply",
    "book",
    "join",
}

CANONICAL_CONTENT_TYPE: dict[ContentTypeEnum, ContentTypeEnum] = {
    ContentTypeEnum.educational: ContentTypeEnum.educational,
    ContentTypeEnum.educational_carousel_post: ContentTypeEnum.educational,
    ContentTypeEnum.educational_post_infographic: ContentTypeEnum.educational,
    ContentTypeEnum.pain_point: ContentTypeEnum.pain_point,
    ContentTypeEnum.case_study: ContentTypeEnum.case_study,
    ContentTypeEnum.case_study_post: ContentTypeEnum.case_study,
    ContentTypeEnum.industry_insight: ContentTypeEnum.industry_insight,
    ContentTypeEnum.founder_authority: ContentTypeEnum.founder_authority,
    ContentTypeEnum.authority_post_tips_post: ContentTypeEnum.founder_authority,
    ContentTypeEnum.automation_tip: ContentTypeEnum.automation_tip,
    ContentTypeEnum.client_testimonial: ContentTypeEnum.client_testimonial,
    ContentTypeEnum.testimonial_post: ContentTypeEnum.client_testimonial,
}


def validate_day_type_match(day: DayEnum, content_type: ContentTypeEnum) -> None:
    expected = DAY_CONTENT_MAPPING[day]
    normalized = CANONICAL_CONTENT_TYPE[content_type]
    if normalized != expected:
        raise ValueError(
            f"Invalid day/content_type mapping: {day.value} must use {expected.value}, "
            f"got {content_type.value}."
        )


def validate_word_count(caption: str, platform: PlatformEnum) -> tuple[int, bool]:
    words = re.findall(r"\b\w+[\w'-]*\b", caption)
    count = len(words)

    limits = {
        PlatformEnum.linkedin: (80, 180),
        PlatformEnum.instagram: (60, 140),
        PlatformEnum.facebook: (60, 140),
    }
    min_words, max_words = limits[platform]
    return count, min_words <= count <= max_words


def validate_has_hook_and_cta(caption: str, platform: PlatformEnum | None = None) -> tuple[bool, bool]:
    lines = [line.strip() for line in caption.splitlines() if line.strip()]
    if len(lines) < 3:
        return False, False

    hook_lines = lines[:2]
    hook_text = " ".join(hook_lines).lower()
    has_hook = (
        "?" in " ".join(hook_lines)
        or hook_text.startswith("if you")
        or "hot take" in hook_text
        or any(token in hook_text for token in ["most people", "we used to", "i used to", "contrary"])
    )

    candidate_lines = lines
    if platform == PlatformEnum.instagram:
        # Instagram can end with hashtags; CTA should be the last non-hashtag line.
        non_hashtag_lines = [line for line in lines if not line.strip().startswith("#")]
        if not non_hashtag_lines:
            return has_hook, False
        candidate_lines = non_hashtag_lines

    def _is_cta_like(line: str) -> bool:
        lw = line.lower().strip()
        word_count = len(re.findall(r"\b\w+[\w'-]*\b", lw))
        if word_count == 0 or word_count > 12:
            return False
        starts_with_cta_verb = any(re.match(rf"^(please\s+)?{verb}\b", lw) for verb in CTA_VERBS)
        direct_cta_phrase = any(
            phrase in lw
            for phrase in [
                "comment ",
                "dm me",
                "message me",
                "reply with",
                "click the",
                "save this",
                "share this",
            ]
        )
        intent_match = any(
            phrase in lw
            for phrase in [
                "let me know",
                "want the",
                "want this",
                "drop",
                "send me",
            ]
        )
        return starts_with_cta_verb or direct_cta_phrase or intent_match

    cta_like_indices = [idx for idx, line in enumerate(candidate_lines) if _is_cta_like(line)]
    if len(cta_like_indices) != 1:
        return has_hook, False

    # Accept CTA in the final two non-hashtag lines to avoid brittle failures.
    has_cta = cta_like_indices[0] >= max(0, len(candidate_lines) - 2)
    return has_hook, has_cta


def heuristic_no_fabricated_numbers_if_no_proof(caption: str, proof_assets: str) -> bool:
    if proof_assets.strip():
        return True

    metric_patterns = [
        r"\b\d+%\b",
        r"\b\d+x\b",
        r"\b\d+\s*(leads|sales|clients|revenue|roi|conversion|appointments)\b",
        r"\b(increased|reduced|boosted|grew)\s+\d+\b",
    ]
    lowered = caption.lower()
    for pattern in metric_patterns:
        if re.search(pattern, lowered):
            return False
    return True


def validate_instagram_hashtags(caption: str) -> bool:
    hashtags = re.findall(r"(?<!\w)#\w+", caption)
    if not hashtags:
        return False
    return 5 <= len(hashtags) <= 10


def validate_hashtag_count(caption: str, platform: PlatformEnum) -> tuple[int, bool]:
    hashtags = re.findall(r"(?<!\w)#\w+", caption)
    count = len(hashtags)
    limits = {
        PlatformEnum.linkedin: (3, 6),
        PlatformEnum.instagram: (5, 10),
        PlatformEnum.facebook: (3, 6),
    }
    min_count, max_count = limits[platform]
    return count, min_count <= count <= max_count
