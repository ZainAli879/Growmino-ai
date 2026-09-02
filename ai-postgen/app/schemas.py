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


class PublishPlatformEnum(str, Enum):
    instagram = "instagram"
    facebook = "facebook"
    linkedin = "linkedin"


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


class WeeklyContentPlanRequest(BaseModel):
    business_name: str
    industry: str
    offer: str
    target_audience: str
    audience_pain_points: str
    tone: str
    brand_personality: str
    cta_preference: str = ""
    proof_assets: str = ""
    company_logo_url: str = ""
    week_start_date: str = ""
    weekly_goal: str
    theme: str
    platforms: list[PlatformEnum] = Field(default_factory=lambda: [PlatformEnum.linkedin])
    posts_count: int = Field(default=5, ge=1, le=7)

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("platforms", mode="before")
    @classmethod
    def normalize_platforms(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [item.strip().lower() if isinstance(item, str) else item for item in value]
        return value

    @model_validator(mode="after")
    def validate_weekly_plan_required(self) -> "WeeklyContentPlanRequest":
        required_fields = [
            "business_name",
            "industry",
            "offer",
            "target_audience",
            "audience_pain_points",
            "tone",
            "brand_personality",
            "weekly_goal",
            "theme",
        ]
        for field_name in required_fields:
            value = getattr(self, field_name, "")
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} is required and must be non-empty.")
        if not self.platforms:
            raise ValueError("platforms must include at least one platform.")
        return self


class ContentPlanItem(BaseModel):
    position: int
    day: DayEnum
    platform: PlatformEnum
    content_type: ContentTypeEnum
    topic: str
    angle: str
    hook_direction: str
    cta_direction: str
    visual_direction: str
    generation_status: str = "planned"
    generated_post_id: str = ""
    generated_caption: str = ""
    generated_headline: str = ""
    generated_image_url: str = ""
    generated_image_data_url: str = ""
    generated_image_base64: str = ""
    generated_image_mime_type: str = ""
    generated_alt_text: str = ""
    generation_error: str = ""


class ContentPlanResponse(BaseModel):
    plan_id: str
    status: str = "planned"
    week_start_date: str = ""
    weekly_goal: str
    theme: str
    total_posts: int
    items: list[ContentPlanItem]


class PublicContentPlanPost(BaseModel):
    position: int
    post_id: str = ""
    status: str
    platform: PlatformEnum
    day: DayEnum
    content_type: ContentTypeEnum
    business_name: str
    topic: str
    caption: str = ""
    headline: str = ""
    image_url: str = ""
    image_base64: str = ""
    image_data_url: str = ""
    image_mime_type: str = ""
    alt_text: str = ""
    error: str = ""


class PublicContentPlanResponse(BaseModel):
    plan_id: str
    status: str
    week_start_date: str = ""
    weekly_goal: str
    theme: str
    total_posts: int
    posts: list[PublicContentPlanPost]


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
    public_url: str = ""
    image_data_url: str = ""
    image_base64: str = ""
    image_mime_type: str = "image/png"
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
    post_id: str = ""
    meta: MetaInfo
    caption: str
    headline: str
    openai_image: OpenAIImageInfo
    qa: QAInfo | None = None
    trace: TraceInfo | None = None


class PublicGenerateResponse(BaseModel):
    post_id: str
    status: str = "generated"
    platform: PlatformEnum
    day: DayEnum
    content_type: ContentTypeEnum
    business_name: str
    caption: str
    headline: str
    image_url: str = ""
    image_base64: str
    image_data_url: str
    image_mime_type: str = "image/png"
    alt_text: str = ""


class GeneratedPostSummary(BaseModel):
    id: str
    platform: str = ""
    day: str = ""
    content_type: str = ""
    topic: str = ""
    caption: str = ""
    headline: str = ""
    image_url: str = ""
    image_file_path: str = ""
    alt_text: str = ""
    status: str = ""
    created_at: str = ""
    updated_at: str = ""


class GeneratedPostsResponse(BaseModel):
    posts: list[GeneratedPostSummary]


class PublishRequest(BaseModel):
    platform: PublishPlatformEnum
    caption: str
    image_url: str = ""
    image_file_path: str = ""
    access_token: str = ""
    facebook_page_id: str = ""
    facebook_access_token: str = ""
    instagram_business_account_id: str = ""
    instagram_access_token: str = ""

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_payload(self) -> "PublishRequest":
        if not self.caption.strip():
            raise ValueError("caption is required and must be non-empty.")
        if self.platform == PublishPlatformEnum.instagram and not (self.image_url.strip() or self.image_file_path.strip()):
            raise ValueError("Instagram publishing requires image_url or image_file_path.")
        return self


class PublishResponse(BaseModel):
    platform: PublishPlatformEnum
    published: bool
    post_id: str = ""
    creation_id: str = ""
    message: str = ""
    image_url_used: str = ""
    drive_image_url: str = ""
    image_urls_used: list[str] = Field(default_factory=list)
    child_creation_ids: list[str] = Field(default_factory=list)
    photo_ids: list[str] = Field(default_factory=list)


class FacebookTextPublishRequest(BaseModel):
    page_id: str = Field(..., min_length=1)
    page_access_token: str = Field(..., min_length=1)
    caption: str = Field(..., min_length=1, max_length=63206)
    idempotency_key: str = ""

    model_config = ConfigDict(str_strip_whitespace=True)


class FacebookImageUrlPublishRequest(BaseModel):
    page_id: str = Field(..., min_length=1)
    page_access_token: str = Field(..., min_length=1)
    caption: str = Field(..., min_length=1, max_length=63206)
    image_url: str = Field(..., min_length=1)
    idempotency_key: str = ""

    model_config = ConfigDict(str_strip_whitespace=True)


class FacebookMultiImageUrlPublishRequest(BaseModel):
    page_id: str = Field(..., min_length=1)
    page_access_token: str = Field(..., min_length=1)
    caption: str = Field(..., min_length=1, max_length=63206)
    image_urls: list[str] = Field(..., min_length=2, max_length=20)
    idempotency_key: str = ""

    model_config = ConfigDict(str_strip_whitespace=True)


class InstagramImageUrlPublishRequest(BaseModel):
    instagram_business_account_id: str = Field(..., min_length=1)
    instagram_access_token: str = Field(..., min_length=1)
    caption: str = Field(..., min_length=1, max_length=2200)
    image_url: str = Field(..., min_length=1)
    idempotency_key: str = ""

    model_config = ConfigDict(str_strip_whitespace=True)


class InstagramCarouselUrlPublishRequest(BaseModel):
    instagram_business_account_id: str = Field(..., min_length=1)
    instagram_access_token: str = Field(..., min_length=1)
    caption: str = Field(..., min_length=1, max_length=2200)
    image_urls: list[str] = Field(..., min_length=2, max_length=10)
    idempotency_key: str = ""

    model_config = ConfigDict(str_strip_whitespace=True)


class UploadImageResponse(BaseModel):
    file_path: str
    public_url: str


class UploadImageRequest(BaseModel):
    file_name: str = "upload.png"
    data_url: str

    model_config = ConfigDict(str_strip_whitespace=True)


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str = ""


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Backward-compatible error message")
    request_id: str = ""
    error: ErrorBody | None = None


class LinkedInConnectResponse(BaseModel):
    authorization_url: str
    expires_in_seconds: int


class LinkedInStatusResponse(BaseModel):
    connected: bool
    profile_name: str = ""
    email: str = ""
    linkedin_sub: str = ""
    person_urn: str = ""
    connected_at: str = ""
    expires_at: str = ""


class LinkedInPublishTextRequest(BaseModel):
    caption: str = Field(..., min_length=1, max_length=3000)
    idempotency_key: str = ""

    model_config = ConfigDict(str_strip_whitespace=True)


class LinkedInPublishImageUrlRequest(BaseModel):
    caption: str = Field(..., min_length=1, max_length=3000)
    image_url: str
    idempotency_key: str = ""

    model_config = ConfigDict(str_strip_whitespace=True)


class LinkedInScheduleRequest(BaseModel):
    caption: str = Field(..., min_length=1, max_length=3000)
    scheduled_for: str
    timezone: str = "UTC"
    image_url: str = ""
    idempotency_key: str = ""

    model_config = ConfigDict(str_strip_whitespace=True)


class LinkedInPostStatus(BaseModel):
    id: str
    user_id: str = ""
    business_id: str = ""
    platform: str = "linkedin"
    type: str = "text"
    status: str
    caption: str = ""
    image_url: str = ""
    image_urns: list[str] = Field(default_factory=list)
    alt_texts: list[str] = Field(default_factory=list)
    scheduled_for_utc: str = ""
    display_timezone: str = ""
    linkedin_post_id: str = ""
    error_message: str = ""
    retry_count: int = 0
    created_at: str = ""
    updated_at: str = ""


class LinkedInPublishResponse(BaseModel):
    id: str
    platform: str = "linkedin"
    status: str
    linkedin_post_id: str = ""
    image_urns: list[str] = Field(default_factory=list)
    message: str
    scheduled_for_utc: str = ""
    display_timezone: str = ""


class LinkedInJobsResponse(BaseModel):
    posts: list[LinkedInPostStatus]
