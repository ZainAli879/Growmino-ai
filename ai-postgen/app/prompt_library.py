from __future__ import annotations

from app.schemas import ContentTypeEnum, DayEnum, PlatformEnum

DAY_CONTENT_MAPPING: dict[DayEnum, ContentTypeEnum] = {
    DayEnum.monday: ContentTypeEnum.educational,
    DayEnum.tuesday: ContentTypeEnum.pain_point,
    DayEnum.wednesday: ContentTypeEnum.case_study,
    DayEnum.thursday: ContentTypeEnum.industry_insight,
    DayEnum.friday: ContentTypeEnum.founder_authority,
    DayEnum.saturday: ContentTypeEnum.automation_tip,
    DayEnum.sunday: ContentTypeEnum.client_testimonial,
}

PLATFORM_RULES: dict[PlatformEnum, str] = {
    PlatformEnum.linkedin: """
You are writing for LinkedIn.
- 80-180 words (target 110-160).
- Strong hook in first 1-2 lines.
- Professional but conversational.
- Line breaks for mobile readability.
- Optional bullets: max 3-6 short bullets.
- 0-3 emojis max.
- Include one actionable takeaway (tip, step, or mini-framework).
- Avoid ad-like phrasing such as "shop now", "best ever", or hype claims.
- Add 3-6 relevant non-spammy hashtags at the end.
""".strip(),
    PlatformEnum.instagram: """
You are writing for Instagram.
- 60-140 words (target 80-120).
- Punchy relatable hook.
- 1-2 emojis per paragraph max.
- Add 5-10 relevant non-spammy hashtags at the end.
- Keep tone human and specific; avoid generic promotional copy.
""".strip(),
    PlatformEnum.facebook: """
You are writing for Facebook.
- 60-140 words.
- Friendly and direct tone.
- Minimal emojis.
- Keep it practical and clear, not overly salesy.
- Add 3-6 relevant non-spammy hashtags at the end.
""".strip(),
}

CONTENT_TYPE_RULES: dict[ContentTypeEnum, str] = {
    ContentTypeEnum.educational: "Provide a quick 3-step framework with practical actions.",
    ContentTypeEnum.educational_carousel_post: "Write as a carousel-style sequence with 3 concise learning points.",
    ContentTypeEnum.educational_post_infographic: "Teach with concise, data-friendly points suitable for an infographic-style visual.",
    ContentTypeEnum.pain_point: "Validate the pain point and provide 2 practical fixes.",
    ContentTypeEnum.case_study: "Use a story format. Do not invent proof. If missing, include '(client proof needed)'.",
    ContentTypeEnum.case_study_post: "Use a story format with concrete before/after framing. Do not invent proof. If missing, include '(client proof needed)'.",
    ContentTypeEnum.industry_insight: "Share a trend observation and what to do next.",
    ContentTypeEnum.founder_authority: "Use first-person lesson and one practical takeaway.",
    ContentTypeEnum.authority_post_tips_post: "Share authority-building practical tips with one clear action the reader can apply today.",
    ContentTypeEnum.automation_tip: "Provide a practical 3-step automation tip framework.",
    ContentTypeEnum.client_testimonial: "Use testimonial-style story. No invented proof. If missing, include '(client proof needed)'.",
    ContentTypeEnum.testimonial_post: "Use testimonial-style story. No invented proof. If missing, include '(client proof needed)'.",
}

CAPTION_TEMPLATE = """
You are an expert social media copywriter.
Create one finalized caption and one headline/hook.
Output strict JSON only. No markdown fences.

Business context:
- Business: {business_name}
- Industry: {industry}
- Offer: {offer}
- Target audience: {target_audience}
- Audience pain points: {audience_pain_points}
- Weekly focus topic: {weekly_focus_topic}
- Day: {day}
- Content type: {content_type}
- Tone: {tone}
- Brand personality: {brand_personality}
- CTA preference: {cta_preference}
- Proof assets: {proof_assets}
- Platform: {platform}
- Recent headlines to avoid repeating: {recent_headlines}

Mandatory structure:
1) Hook (1-2 lines). Use one pattern: question, contrarian, "If you're doing X, you're losing Y", or micro-story opener.
2) Value (2-5 short lines) based on content type requirements.
3) Optional micro-credibility line only when proof assets exist.
4) One clear CTA line in the final 1-2 lines. Use CTA preference when provided.

Global constraints:
- Clear, practical, human.
- No buzzword soup.
- No long paragraphs.
- No fabricated metrics, client names, testimonials, or results.
- If proof assets are empty and content type needs proof, include '(client proof needed)'.
- Avoid unsafe content (hate, harassment, sexual content, violence, illegal instructions, medical/legal guarantees).

Platform rules:
{platform_rules}

Content-type rules:
{content_type_rules}

Formatting requirements:
- Use short lines with clean line breaks for readability.
- Keep one clear CTA near the end of caption.
- Always include hashtags in the final line(s):
  - LinkedIn/Facebook: 3-6 relevant hashtags
  - Instagram: 5-10 relevant hashtags
- Mention one concrete audience pain point and one practical fix or next step.
- Avoid generic claims and filler lines.
- Headline must be fresh and distinct from recent headlines. Avoid repeating wording patterns.

Output JSON with exactly these keys:
- "caption": full post caption text
- "headline": one short hook/headline aligned with the caption.
Headline quality rules:
- 4-8 words only.
- Title Case (except small connector words).
- No hashtags, no emojis, no quotation marks, no trailing punctuation.
- Plain ASCII only (letters, digits, spaces, hyphen, apostrophe).
- Must be easy to read on image overlay in under 2 seconds.
""".strip()

NEGATIVE_IMAGE_PROMPT = "no watermark, no signature, no brand names, no UI mockups, no cluttered layout, no blur, no artifacts"

IMAGE_TEXT_LAYOUT_OPTIONS: list[str] = [
    "top ribbon with high contrast",
    "bottom ribbon with high contrast",
    "top full-width solid ribbon with strong contrast",
    "bottom full-width solid ribbon with strong contrast",
    "top gradient ribbon with soft edge shadow",
    "bottom gradient ribbon with soft edge shadow",
    "top translucent ribbon with bold high-contrast text",
    "bottom translucent ribbon with bold high-contrast text",
    "top split-color ribbon with punchy contrast",
    "bottom split-color ribbon with punchy contrast",
    "ticker-style lower-third bar with bold headline lockup",
    "cinematic letterbox bars with headline inside lower bar",
    "angled full-width sash with horizontal headline",
    "offset headline band starting at 20 percent width",
    "highlight strip behind key words only with strong contrast",
    "top ribbon with subtle neon edge glow",
    "bottom ribbon with subtle neon edge glow",
    "top ribbon with minimal pattern texture and strong contrast",
    "bottom ribbon with minimal pattern texture and strong contrast",
    "top left anchored ribbon with asymmetric cut edge",
    "bottom right anchored ribbon with asymmetric cut edge",
    "floating center ribbon with high-contrast border",
    "top stepped ribbon with layered depth and clear headline",
    "bottom stepped ribbon with layered depth and clear headline",
    "top blueprint grid ribbon with strong contrast text",
    "bottom blueprint grid ribbon with strong contrast text",
    "top frosted ribbon with crisp dark text lockup",
    "bottom frosted ribbon with crisp light text lockup",
    "center horizon ribbon across middle third with bold headline",
]

IMAGE_PROMPT_FROM_CAPTION_TEMPLATE = """
You convert a social caption into a production-ready image generation prompt.
Output exactly ONE plain-text prompt only. No markdown. No labels. No explanations.

Caption:
{caption}

Prompt requirements:
- Keep only concrete visual requirements. No fluff adjectives.
- Include subject, scene, composition, style, lighting, and color direction.
- No visible text in scene.
- No logos or brand marks in scene.
- No watermark or signature.
- Align background and visual metaphors to the post value and pain point context.
- Visual direction should feel current (2026 social creative): clean, high-contrast, premium, and mobile-first.
- Do not output placeholder tokens (for example EXACT_TEXT, HEADLINE_TEXT, or TEMPLATE_TEXT).
- Keep prompt compact and directly usable by an image model.
""".strip()
