from __future__ import annotations

import os
import re
import json
from datetime import datetime
from pathlib import Path

from app.prompt_library import NEGATIVE_IMAGE_PROMPT
from app.schemas import ContentTypeEnum

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


def ensure_outputs_dir(path: str = "./outputs") -> str:
    os.makedirs(path, exist_ok=True)
    return path


def append_jsonl(file_path: str, record: dict) -> None:
    directory = os.path.dirname(file_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")


def sanitize_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "item"


def build_output_file_path(outputs_dir: str, platform: str, day: str, content_type: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = (
        f"{timestamp}-"
        f"{sanitize_filename_part(platform)}-"
        f"{sanitize_filename_part(day)}-"
        f"{sanitize_filename_part(content_type)}.png"
    )
    return os.path.join(outputs_dir, filename)


def build_public_output_url(file_path: str) -> str:
    normalized = str(file_path).replace("\\", "/")
    marker = "/outputs/"
    if marker in normalized:
        return normalized.split(marker, 1)[1]

    path = Path(normalized)
    parts = [part for part in path.parts if part not in {"."}]
    if "outputs" in parts:
        index = parts.index("outputs")
        return "/".join(parts[index + 1 :])
    return path.name


def select_image_style(content_type: ContentTypeEnum) -> str:
    canonical_type = CANONICAL_CONTENT_TYPE[content_type]
    photo_types = {
        ContentTypeEnum.founder_authority,
        ContentTypeEnum.client_testimonial,
        ContentTypeEnum.case_study,
    }
    return "photo" if canonical_type in photo_types else "minimal_illustration"


def _compress_words(text: str, max_words: int = 6) -> str:
    words = re.findall(r"[A-Za-z0-9']+", text)
    return " ".join(words[:max_words]).strip()


def _normalize_headline(text: str) -> str:
    # Keep text simple to reduce spelling/rendering errors in generated images.
    text = re.sub(r"[^A-Za-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_image_headline(caption: str, weekly_focus_topic: str) -> str:
    for raw_line in caption.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if "client proof needed" in line.lower():
            continue
        headline = _normalize_headline(_compress_words(line, max_words=12))
        if len(headline.split()) >= 3:
            return headline.title()

    fallback = _normalize_headline(_compress_words(weekly_focus_topic, max_words=12))
    if len(fallback.split()) < 3:
        return "Respond Faster Win More Leads"
    return fallback.title()


def build_scene_prompt(
    industry: str,
    weekly_focus_topic: str,
    content_type: ContentTypeEnum,
    style: str,
) -> str:
    canonical_type = CANONICAL_CONTENT_TYPE[content_type]
    scene_by_type: dict[ContentTypeEnum, str] = {
        ContentTypeEnum.educational: "clean business workflow board, message flow icons, modern office",
        ContentTypeEnum.pain_point: "split-scene bottleneck vs smooth process, business dashboard, urgency mood",
        ContentTypeEnum.case_study: "professional team reviewing performance chart, laptop meeting table",
        ContentTypeEnum.industry_insight: "future trend dashboard, data visualization wall, strategic planning scene",
        ContentTypeEnum.founder_authority: "founder working at desk, focused lighting, premium workspace",
        ContentTypeEnum.automation_tip: "automation pipeline, connected tools, efficient task flow visual",
        ContentTypeEnum.client_testimonial: "happy client meeting moment, trust and outcomes visual tone",
    }
    scene = scene_by_type[canonical_type]
    topic = _normalize_headline(_compress_words(weekly_focus_topic, max_words=8)).lower()
    industry_text = _normalize_headline(_compress_words(industry, max_words=4)).lower()
    style_text = "illustration" if style == "minimal_illustration" else "photo"
    return (
        f"{scene}, {topic}, {industry_text}, {style_text}. "
        "Create a clean social media visual with no written text in the image. "
        "Do not render letters, words, labels, UI text, or typography. "
        f"Negative prompt: {NEGATIVE_IMAGE_PROMPT}"
    )


def build_image_prompt(
    business_name: str,
    industry: str,
    weekly_focus_topic: str,
    image_headline: str,
    content_type: ContentTypeEnum,
    platform: str,
    style: str,
) -> str:
    if style == "photo":
        style_block = (
            "Professional lifestyle business photo, natural human expressions, "
            "cinematic lighting, shallow depth of field, clean composition, "
            "premium modern aesthetic, scroll-stopping contrast."
        )
    else:
        style_block = (
            "Minimal modern vector-like illustration, clean gradients, abstract shapes, "
            "high contrast focal point, subtle symbolic elements, "
            "premium brand-like visual language."
        )

    prompt = (
        f"Create one square 1024x1024 {style} image for a social media post. "
        f"Theme: {content_type.value} for {business_name} in {industry}. "
        f"Topic focus: {weekly_focus_topic}. Platform context: {platform}. "
        "Scene should be safe and business-friendly, no weapons, no nudity, "
        "no political symbols, no medical scenes. "
        "Composition: centered subject, clean negative space, strong visual hierarchy, "
        "balanced framing, crisp details. "
        "Mood: optimistic, confident, practical. "
        "Text rules are flexible: include text only if it genuinely helps the image communicate faster. "
        "Do not force the provided headline into the image. If text is useful, use one or two short, natural phrases. "
        "Do not render instructions, labels, brand names, metadata, hashtags, CTA blocks, or extra captions. "
        "If perfect text rendering is uncertain, render no text at all. "
        f"Style direction: {style_block} "
        f"Negative prompt: {NEGATIVE_IMAGE_PROMPT}"
    )
    return prompt


def build_alt_text(content_type: str, industry: str, style: str) -> str:
    return f"A {style} visual representing {content_type} content in the {industry} industry."
