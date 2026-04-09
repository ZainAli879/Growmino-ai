from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DayEnum(str, Enum):
    monday = "Monday"
    tuesday = "Tuesday"
    wednesday = "Wednesday"
    thursday = "Thursday"
    friday = "Friday"
    saturday = "Saturday"
    sunday = "Sunday"


class ContentTypeEnum(str, Enum):
    educational = "Educational"
    educational_carousel_post = "Educational Carousel Post"
    educational_post_infographic = "Educational Post + Infographic"
    pain_point = "Pain-point"
    case_study = "Case Study"
    case_study_post = "Case Study Post"
    industry_insight = "Industry Insight"
    founder_authority = "Founder Authority"
    authority_post_tips_post = "Authority Post (Tips Post)"
    automation_tip = "Automation Tip"
    client_testimonial = "Client Testimonial"
    testimonial_post = "Testimonial Post"


class PlatformEnum(str, Enum):
    linkedin = "linkedin"
    instagram = "instagram"
    facebook = "facebook"


class GenerateRequest(BaseModel):
    business_name: str
    industry: str
    offer: str
    target_audience: str
    audience_pain_points: str
    weekly_focus_topic: str
    day: DayEnum
    content_type: ContentTypeEnum
    tone: str
    brand_personality: str
    cta_preference: str = ""
    proof_assets: str = ""
    company_logo_url: str = ""
    platform: PlatformEnum

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @model_validator(mode="after")
    def validate_non_empty_required(self) -> "GenerateRequest":
        required_fields = [
            "business_name",
            "industry",
            "offer",
            "target_audience",
            "audience_pain_points",
            "weekly_focus_topic",
            "tone",
            "brand_personality",
        ]
        for field_name in required_fields:
            value = getattr(self, field_name, "")
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} is required and must be non-empty.")
        return self


class MetaInfo(BaseModel):
    platform: PlatformEnum
    day: DayEnum
    content_type: ContentTypeEnum
    business_name: str


class OpenAIImageInfo(BaseModel):
    model: str
    size: str = "1024x1024"
    style: str
    prompt_used: str
    negative_prompt_used: str
    file_path: str
    alt_text: str


class QAInfo(BaseModel):
    word_count: int
    platform_limits_ok: bool
    has_hook: bool
    no_fabricated_claims: bool
    safety_ok: bool
    image_has_no_text_requirement: bool
    hashtag_count: int = 0
    hashtag_count_ok: bool = True
    warnings: list[str] = []


class TraceInfo(BaseModel):
    trace_id: str
    request_started_at: str
    elapsed_ms_total: int
    elapsed_ms_caption: int
    elapsed_ms_image_prompt_and_generation: int
    text_provider: str = "openai"
    text_model: str = "gpt-4o-mini"
    image_provider: str
    image_model: str


class GenerateResponse(BaseModel):
    meta: MetaInfo
    caption: str
    headline: str
    openai_image: OpenAIImageInfo
    qa: QAInfo | None = None
    trace: TraceInfo | None = None


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message")
