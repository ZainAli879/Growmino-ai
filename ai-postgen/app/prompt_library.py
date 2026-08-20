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
You are writing for LinkedIn in 2026.
- 80-200 words (target 120-180).
- Scroll-stopping pattern-interrupt hook in first line.
- Creator-led, hyper-authentic, 'zero-click' value (no external links needed to get value).
- Use single-sentence paragraphs and generous line breaks for mobile skimming.
- Use a bold statement or contrarian take.
- 0-2 emojis max (keep it minimalist).
- Conclude with a high-converting, low-friction CTA.
- Add 3-5 hyper-niche hashtags at the end.
""".strip(),
    PlatformEnum.instagram: """
You are writing for Instagram (Feed/Carousel) in 2026.
- 60-150 words (target 80-120).
- Visual-first storytelling: hook them with text that perfectly complements the image.
- Raw, authentic, and aesthetic "photo-dump" or "carousel" vibe.
- 2-3 trendy emojis max.
- Add 4-7 relevant hashtags integrated seamlessly or at the end.
- Keep tone conversational, human, and community-driven. Avoid sterile corporate copy.
""".strip(),
    PlatformEnum.facebook: """
You are writing for Facebook in 2026.
- 60-140 words.
- Community-focused, highly relatable, story-driven tone.
- Minimal emojis.
- highly practical, zero fluff. Focus on relatable pain points.
- Add 3-5 relevant hashtags at the end.
""".strip(),
}

CONTENT_TYPE_RULES: dict[ContentTypeEnum, str] = {
    ContentTypeEnum.educational: "Deliver an ultra-specific, high-value micro-lesson. Focus on 'how' not just 'what'.",
    ContentTypeEnum.educational_carousel_post: "Structure as a high-retention carousel: Hook -> Concept -> 3 Steps -> Result -> CTA.",
    ContentTypeEnum.educational_post_infographic: "Design for 'saveable' content. Bullet-point deep value that users will want to screenshot.",
    ContentTypeEnum.pain_point: "Agitate a specific hyper-niche pain point, then offer a counter-intuitive, modern 2026 solution.",
    ContentTypeEnum.case_study: "Use a 'Hero's Journey' micro-story format. Emphasize the transformation. If missing, limit to '(client proof needed)'.",
    ContentTypeEnum.case_study_post: "Fast-paced Before/After story frame. Focus on exact metrics or emotional shift. If missing, use '(client proof needed)'.",
    ContentTypeEnum.industry_insight: "Share a bold prediction or tear-down of a current 2026 trend. Back it up with a unique perspective.",
    ContentTypeEnum.founder_authority: "Share a vulnerable, behind-the-scenes founder lesson. 'Build-in-public' raw transparency.",
    ContentTypeEnum.authority_post_tips_post: "High-signal, low-noise actionable tips. Speak like an absolute master of the craft.",
    ContentTypeEnum.automation_tip: "Provide a 'plug-and-play' AI/automation workflow. Name the tools and the exact trigger/action.",
    ContentTypeEnum.client_testimonial: "Frame the testimonial as an unboxing or raw reaction. No hype, just real results. '(client proof needed)' if empty.",
    ContentTypeEnum.testimonial_post: "Focus on the emotional relief the client felt. Use exact quotes if possible. '(client proof needed)' if empty.",
}

CAPTION_TEMPLATE = """
You are an elite, top-tier social media copywriter in 2026, creating native, algorithm-friendly content.
Create one finalized caption and one short hook/headline.
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
1) Hook: First sentence must instantly command attention (use curiosity gap, contrarian truth, or direct call-out).
2) Value/Body: Short, punchy sentences. High signal-to-noise ratio. Deliver the promise of the hook.
3) Optional micro-credibility line only when proof assets exist.
4) CTA: One clear, frictionless next step for the reader.

Global constraints:
- Use modern 2026 pacing: rhythmic, easy to skim, zero fluff.
- No outdated marketing speak ("synergy", "innovative", "shop now").
- No fabricated metrics, client names, or testimonials.
- If proof assets are empty and content type needs proof, include '(client proof needed)'.
- Avoid unsafe/prohibited content.

Platform rules:
{platform_rules}

Content-type rules:
{content_type_rules}

Formatting requirements:
- Use short sentences. Maximum 2 sentences per paragraph.
- Add white space (line breaks) for high readability on mobile.
- Always include hashtags (as per platform rules).
- Connect the pain point directly to the practical fix.
- Headline must completely differentiate from recent headlines.

Output JSON with exactly these keys:
- "caption": full post caption text
- "headline": one ultra-short hook/headline that summarizes the post and can be used as optional visual text.

Headline quality rules:
- 3-8 words ONLY. Hyper-concise.
- Title Case for major words.
- No hashtags, emojis, or trailing punctuation.
- Must be instantly readable in under 1 second.
""".strip()

NEGATIVE_IMAGE_PROMPT = "boring stock photo, generic corporate, 2010s aesthetic, flat lighting, artificial CGI look, AI artifacts, plastic skin, cluttered UI, messy text, watermarks, signature, cheesy models, low resolution, bad anatomy, overused marketing templates"

IMAGE_TEXT_LAYOUT_OPTIONS: list[str] = [
    "hyper-legible brutalist typography overlapping abstract 3D elements",
    "sleek semi-transparent dark-glass visor overlay with crisp white type",
    "fluid morphing typography deeply integrated into environmental shadows",
    "high-end editorial crop with floating oversized sans-serif letters",
    "minimalist Japanese magazine layout using vertical and horizontal text interplay",
    "cyber-chic glitch-art text frames with chromatic aberration",
    "elegant Bauhaus-inspired geometric text containment with striking primary colors",
    "translucent holographic badge with embossed chrome-finish lettering",
    "clean micro-typography style pushing the headline into deliberate negative space",
    "layered collage aesthetic masking text underneath textured paper edges",
    "bold anti-design layout using clashing hyper-saturated text blocks",
    "ultra-clean corporate tech lockup with a glowing neon accent underline",
    "cinematic golden-hour light illuminating embossed text naturally tracked into the scene",
    "monolithic metallic bold letters resting directly on surfaces in the scene",
    "minimal tech-HUD overlay with sharp monospaced data-driven typography",
    "editorial fashion-style ultra-thin serif type cascading over soft gradients"
]

IMAGE_PROMPT_FROM_CAPTION_TEMPLATE = """
You are a senior creative director for social media ads and organic business content.
Convert the post content and business context into one production-ready image generation prompt for a modern AI image model.
Output exactly ONE plain-text prompt only. No markdown. No labels. No explanations.

Business context:
- Business: {business_name}
- Industry: {industry}
- Offer: {offer}
- Target audience: {target_audience}
- Audience pain points: {audience_pain_points}
- Weekly focus topic: {weekly_focus_topic}
- Content type: {content_type}
- Platform: {platform}
- Tone: {tone}
- Brand personality: {brand_personality}

Caption:
{caption}

Optional post hook:
{headline}

Prompt requirements:
- First infer the core message of the caption, the audience pain, the promised transformation, and the best scroll-stopping visual angle.
- Decide the strongest visual format for this specific post: realistic editorial scene, lifestyle photo, productized workflow visual, infographic, comparison graphic, symbolic metaphor, clean brand image, or hybrid photo-plus-graphic layout.
- Do not force the optional hook into the image. Use it only if it is genuinely the best visual text.
- Only include text when it improves comprehension or stopping power. If text is useful, choose 1-2 very short text elements derived from the caption/business context; no paragraphs, no hashtags, no CTA blocks, no made-up claims.
- If this is educational, tactical, automation, or process-driven content, an infographic, simple diagram, workflow map, before/after comparison, or annotated visual is allowed.
- If this is founder authority, testimonial, or case-study content, prioritize realistic human/editorial imagery unless a compact proof-style graphic is clearly stronger.
- If proof assets are missing, do not invent numbers, client names, testimonials, awards, charts, dashboards, or outcomes.
- The image MUST be highly relevant to the business, audience, platform, and caption. Avoid generic office stock imagery and unrelated abstract scenes.
- Include concrete visual direction: subject, setting, foreground/background, camera angle or graphic layout, lighting, color mood, focal hierarchy, and negative space.
- Use this optional 2026 layout inspiration only when text, diagram, or infographic elements are appropriate: "{text_layout_style}".
- {logo_instruction}
- Business name is context only. Do not render the business name, app name, company wordmark, initials, icon, badge, or fake logo unless it is part of an exact externally provided logo instruction.
- Do not add random UI text, fake app screens, fake metrics, fake client names, fake awards, watermarks, signatures, or unrelated labels.
- Create an image that feels like premium, top-tier agency creative work, not a cheap stock photo or generic template.
- Prefer powerful visual metaphors, realistic high-end lifestyle imagery, or clean business graphics that communicate the caption's value at a glance.
- Emphasize rich textures, dynamic color grading, natural lighting, high-end commercial art direction, and platform-ready composition.
- Keep composition balanced, readable on mobile, and free of clutter.
- Choose camera modifiers and rendering language only when they fit the chosen format: photorealistic editorial photography, clean vector infographic, premium SaaS graphic, cinematic lifestyle image, or polished brand campaign visual.
- Do not output placeholder tokens.

Return only the final image generation prompt.
""".strip()

WEEKLY_CONTENT_PLAN_TEMPLATE = """
You are a senior social media strategist planning a one-week content calendar in 2026.
Create a non-repetitive weekly plan before any captions or images are generated.
Output strict JSON only. No markdown fences. No commentary.

Business profile:
- Business: {business_name}
- Industry: {industry}
- Offer: {offer}
- Target audience: {target_audience}
- Audience pain points: {audience_pain_points}
- Tone: {tone}
- Brand personality: {brand_personality}
- CTA preference: {cta_preference}
- Proof assets: {proof_assets}

Weekly campaign:
- Week start date: {week_start_date}
- Weekly goal: {weekly_goal}
- Theme: {theme}
- Platforms: {platforms}
- Number of posts: {posts_count}

Recent generated posts to avoid repeating:
{recent_posts}

Content calendar rules:
- Use only these day/content-type mappings:
  Monday -> Educational
  Tuesday -> Pain-point
  Wednesday -> Case Study
  Thursday -> Industry Insight
  Friday -> Founder Authority
  Saturday -> Automation Tip
  Sunday -> Client Testimonial
- If posts_count is under 7, choose the strongest days for this campaign.
- Each item must have a unique topic, angle, hook direction, CTA direction, and visual direction.
- Do not repeat previous hooks, claims, visual concepts, or CTAs from recent posts.
- Do not invent client results, testimonials, numbers, awards, or case-study metrics.
- If proof assets are weak or empty, case-study/testimonial angles must ask for proof rather than inventing it.
- Plan for strategic variety: education, pain agitation, authority, practical workflow, proof/testimonial only when supported.
- Keep topics specific enough that generating posts from them will not feel generic.

Output JSON with exactly this shape:
{{
  "items": [
    {{
      "position": 1,
      "day": "Monday",
      "platform": "linkedin",
      "content_type": "Educational",
      "topic": "Specific post topic",
      "angle": "Specific strategic angle",
      "hook_direction": "How the hook should open",
      "cta_direction": "What the reader should do next",
      "visual_direction": "What the image should communicate"
    }}
  ]
}}
""".strip()
