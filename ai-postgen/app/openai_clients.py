from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
import math
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from app.chains import CaptionGenerationResult, generate_caption_with_retry, generate_image_prompt_from_caption, generate_weekly_content_plan
from app.config import Settings
from app.schemas import ContentPlanResponse, GenerateRequest, WeeklyContentPlanRequest
from app.utils import build_alt_text, build_output_file_path, ensure_outputs_dir

_OPENAI_SUPPORTED_SIZES = {"1024x1024", "1024x1536", "1536x1024", "auto"}


@dataclass
class ImageGenerationResult:
    model: str
    size: str
    style: str
    prompt_used: str
    negative_prompt_used: str
    file_path: str
    alt_text: str


def _openrouter_headers(settings: Settings) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    if settings.openrouter_http_referer:
        headers["HTTP-Referer"] = settings.openrouter_http_referer
    if settings.openrouter_app_name:
        headers["X-Title"] = settings.openrouter_app_name
    return headers


def _text_generation_client_config(settings: Settings) -> tuple[str, str, str | None, dict[str, str] | None]:
    if settings.text_provider == "openrouter":
        return (
            "openrouter",
            settings.openrouter_text_model or settings.caption_model,
            settings.openrouter_base_url,
            {
                k: v
                for k, v in _openrouter_headers(settings).items()
                if k in {"HTTP-Referer", "X-Title"}
            },
        )
    return ("openai", settings.caption_model, settings.openai_base_url, None)


def _text_generation_api_key(settings: Settings, provider: str) -> str:
    return settings.openrouter_api_key if provider == "openrouter" else settings.openai_api_key


def _normalize_size_for_provider(size: str, provider: str) -> str:
    raw = (size or "").strip().lower()
    if provider != "openai":
        return raw or "1024x1024"
    if raw in _OPENAI_SUPPORTED_SIZES:
        return raw
    if raw in {"1080x1350", "1200x1500", "4:5"}:
        return "1024x1536"
    if raw in {"1200x630", "1200x628", "1.91:1"}:
        return "1536x1024"
    return "1024x1024"


def _load_font(size: int):
    for font_name in ("arial.ttf", "segoeui.ttf", "calibri.ttf"):
        try:
            return ImageFont.truetype(font_name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        width = draw.textbbox((0, 0), test, font=font)[2]
        if width <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _region_luma_stats(image: Image.Image, box: tuple[int, int, int, int]) -> tuple[float, float]:
    crop = image.crop(box).convert("RGB")
    pixels = list(crop.getdata())
    if not pixels:
        return (0.5, 0.0)
    lumas: list[float] = []
    for r, g, b in pixels:
        luma = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
        lumas.append(luma)
    mean = sum(lumas) / len(lumas)
    var = sum((x - mean) ** 2 for x in lumas) / len(lumas)
    return mean, math.sqrt(var)


def _pick_overlay_layout(image: Image.Image) -> str:
    w, h = image.size
    pad = int(w * 0.06)
    region_h = int(h * 0.24)
    top_box = (pad, pad, max(pad + 1, w - pad), min(h - pad, pad + region_h))
    bottom_box = (pad, max(pad, h - pad - region_h), max(pad + 1, w - pad), max(pad + 1, h - pad))
    center_box = (pad, int(h * 0.38), max(pad + 1, w - pad), int(h * 0.62))
    top_mean, top_std = _region_luma_stats(image, top_box)
    bottom_mean, bottom_std = _region_luma_stats(image, bottom_box)
    center_mean, center_std = _region_luma_stats(image, center_box)
    scores = {
        "top_ribbon": top_std + abs(top_mean - 0.5) * 0.15,
        "bottom_ribbon": bottom_std + abs(bottom_mean - 0.5) * 0.15,
        "center_glass": center_std + abs(center_mean - 0.5) * 0.20,
    }
    return min(scores, key=scores.get)


def _overlay_headline(image_bytes: bytes, headline: str) -> bytes:
    with Image.open(BytesIO(image_bytes)) as im:
        image = im.convert("RGBA")
        draw = ImageDraw.Draw(image, "RGBA")

        width, height = image.size
        pad = int(width * 0.06)
        max_text_width = int(width * 0.88)
        font_size = max(30, width // 18)
        min_font_size = 12
        layout = _pick_overlay_layout(image)

        while True:
            font = _load_font(font_size)
            spacing = max(6, font_size // 4)
            lines = _wrap_lines(draw, headline, font, max_text_width)
            if not lines:
                lines = [headline]
            if len(lines) > 2 and font_size > min_font_size:
                font_size -= 2
                continue

            line_heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
            text_h = sum(line_heights) + (len(lines) - 1) * spacing
            box_h = text_h + 24
            if layout == "top_ribbon":
                box_top = pad
            elif layout == "center_glass":
                box_top = max(pad, (height - box_h) // 2)
            else:
                box_top = height - box_h - pad
            if box_top >= pad or font_size <= min_font_size:
                break
            font_size -= 2

        box_left = pad
        box_right = width - pad
        box_bottom = box_top + box_h
        mean, _std = _region_luma_stats(image, (box_left, box_top, box_right, box_bottom))
        if mean >= 0.55:
            panel_fill = (8, 20, 48, 182)
            text_fill = (255, 255, 255, 255)
        else:
            panel_fill = (238, 244, 252, 186)
            text_fill = (7, 16, 32, 255)
        draw.rounded_rectangle(
            [(box_left, box_top), (box_right, box_bottom)],
            radius=22,
            fill=panel_fill,
        )

        y = box_top + 12
        for line in lines:
            line_w = draw.textbbox((0, 0), line, font=font)[2]
            x = box_left + max(16, (box_right - box_left - line_w) // 2)
            draw.text((x, y), line, font=font, fill=text_fill)
            y += draw.textbbox((0, 0), line, font=font)[3] + spacing

        out = BytesIO()
        image.convert("RGB").save(out, format="PNG")
        return out.getvalue()


def _assert_valid_image_bytes(data: bytes, source: str) -> None:
    try:
        with Image.open(BytesIO(data)) as im:
            im.verify()
    except Exception as exc:
        raise RuntimeError(f"Logo content from {source} is not a valid image.") from exc


def _load_logo_bytes(logo_ref: str, timeout_seconds: int) -> bytes:
    value = (logo_ref or "").strip()
    if not value:
        raise RuntimeError("Logo reference is empty.")

    if value.startswith("http://") or value.startswith("https://"):
        response = requests.get(value, timeout=timeout_seconds)
        response.raise_for_status()
        data = response.content
        _assert_valid_image_bytes(data, "url")
        return data

    if value.startswith("data:image") and "," in value:
        encoded = value.split(",", 1)[1]
        data = base64.b64decode(encoded)
        _assert_valid_image_bytes(data, "data_url")
        return data

    logo_path = Path(value)
    if not logo_path.exists() or not logo_path.is_file():
        raise RuntimeError(f"Company logo file not found: {value}")
    data = logo_path.read_bytes()
    _assert_valid_image_bytes(data, "local_file")
    return data


def _overlay_logo(image_bytes: bytes, logo_bytes: bytes) -> bytes:
    with Image.open(BytesIO(image_bytes)) as base_im, Image.open(BytesIO(logo_bytes)) as logo_im:
        base = base_im.convert("RGBA")
        logo = logo_im.convert("RGBA")

        base_w, base_h = base.size
        max_logo_w = max(80, int(base_w * 0.16))
        max_logo_h = max(80, int(base_h * 0.16))
        scale = min(max_logo_w / max(logo.width, 1), max_logo_h / max(logo.height, 1))
        new_w = max(1, int(logo.width * scale))
        new_h = max(1, int(logo.height * scale))
        logo = logo.resize((new_w, new_h), Image.Resampling.LANCZOS)

        margin = max(18, int(base_w * 0.04))
        x = base_w - logo.width - margin
        y = margin

        base.alpha_composite(logo, dest=(x, y))
        out = BytesIO()
        base.convert("RGB").save(out, format="PNG")
        return out.getvalue()


def _extract_openrouter_image_bytes(payload_json: dict) -> bytes | None:
    try:
        choices = payload_json.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        message = choices[0].get("message")
        if not isinstance(message, dict):
            return None
        images = message.get("images")
        if not isinstance(images, list) or not images:
            return None
        first = images[0]
        if not isinstance(first, dict):
            return None
        image_url_obj = first.get("image_url")
        if not isinstance(image_url_obj, dict):
            return None
        url = str(image_url_obj.get("url", "")).strip()
        if not url:
            return None
        if url.startswith("data:image") and "," in url:
            encoded = url.split(",", 1)[1]
            return base64.b64decode(encoded)
        download = requests.get(url, timeout=60)
        download.raise_for_status()
        return download.content
    except Exception:
        return None


def generate_caption(payload: GenerateRequest, settings: Settings) -> CaptionGenerationResult:
    provider, model_name, base_url, default_headers = _text_generation_client_config(settings)
    return generate_caption_with_retry(
        payload=payload,
        api_key=_text_generation_api_key(settings, provider),
        model_name=model_name,
        base_url=base_url,
        default_headers=default_headers,
    )


def generate_content_plan(request: WeeklyContentPlanRequest, settings: Settings, plan_id: str, recent_posts: str) -> ContentPlanResponse:
    provider, model_name, base_url, default_headers = _text_generation_client_config(settings)
    return generate_weekly_content_plan(
        request=request,
        plan_id=plan_id,
        recent_posts=recent_posts,
        api_key=_text_generation_api_key(settings, provider),
        model_name=model_name,
        base_url=base_url,
        default_headers=default_headers,
    )


def generate_image(payload: GenerateRequest, settings: Settings, caption: str, headline: str) -> ImageGenerationResult:
    style = "caption_derived"
    requested_size = settings.image_size_for_platform(payload.platform.value)
    selected_size = _normalize_size_for_provider(requested_size, settings.image_provider)
    used_size = selected_size

    text_provider, text_model, text_base_url, text_default_headers = _text_generation_client_config(settings)
    has_logo = bool((payload.company_logo_url or "").strip())
    logo_mode = (settings.logo_input_mode or "overlay").strip().lower()
    supports_reference_logo = settings.image_provider == "openrouter"
    use_reference_logo = has_logo and logo_mode in {"reference", "both"} and supports_reference_logo
    use_overlay_logo = has_logo and logo_mode in {"overlay", "both"}
    if has_logo and logo_mode == "reference" and not supports_reference_logo:
        # Provider path currently does not accept image-input wiring in this flow.
        # Fall back to overlay to guarantee brand mark appears.
        use_overlay_logo = True
    logo_bytes: bytes | None = None
    if has_logo:
        logo_bytes = _load_logo_bytes(payload.company_logo_url, settings.request_timeout_seconds)

    if use_reference_logo:
        logo_instruction = (
            "Logo handling: a real logo reference image is attached. Use only that exact provided logo "
            "as a small brand mark in the top-right corner. Do not invent, redraw, distort, recolor, "
            "repeat, stylize, or supplement it. Do not create any additional logo, company name, app name, "
            "initials, icon, badge, or wordmark anywhere in the image."
        )
    elif use_overlay_logo:
        logo_instruction = (
            "Logo handling: the system will add the real logo after image generation. Leave clean negative "
            "space in the top-right corner for that external overlay. Do not generate any logo, company name, "
            "app name, initials, icon, badge, wordmark, brand mark, or fake UI logo anywhere in the image."
        )
    else:
        logo_instruction = (
            "Logo handling: no logo was provided. Do not generate any logo, company name, app name, initials, "
            "icon, badge, wordmark, brand mark, or fake UI logo anywhere in the image. Keep the visual unbranded."
        )

    prompt = generate_image_prompt_from_caption(
        payload=payload,
        caption=caption,
        headline=headline,
        logo_instruction=logo_instruction,
        api_key=_text_generation_api_key(settings, text_provider),
        model_name=text_model,
        base_url=text_base_url,
        default_headers=text_default_headers,
    ).strip()

    if use_overlay_logo:
        prompt = (
            f"{prompt}\nFinal hard rule: do not create or draw any logo/wordmark/app name yourself. "
            "The only logo will be added externally after generation."
        )
    elif not has_logo:
        prompt = (
            f"{prompt}\nFinal hard rule: no logos, no company names, no app names, no initials, "
            "no brand marks, and no fake product UI branding anywhere."
        )

    outputs_dir = ensure_outputs_dir(settings.outputs_dir)
    file_path = build_output_file_path(
        outputs_dir=outputs_dir,
        platform=payload.platform.value,
        day=payload.day.value,
        content_type=payload.content_type.value,
    )

    if settings.image_provider == "openrouter":
        endpoint = f"{settings.openrouter_base_url}/chat/completions"
        headers = _openrouter_headers(settings)
        user_content: object = prompt
        if use_reference_logo and logo_bytes is not None:
            data_url = f"data:image/png;base64,{base64.b64encode(logo_bytes).decode('ascii')}"
            user_content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]
        body = {
            "model": settings.openrouter_image_model,
            "messages": [
                {"role": "user", "content": user_content},
            ],
            "modalities": ["image"],
            "stream": False,
        }
        provider_label = settings.openrouter_image_model
    else:
        endpoint = f"{settings.openai_base_url}/images/generations"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": settings.openai_image_model,
            "prompt": prompt,
            "size": selected_size,
        }
        provider_label = settings.openai_image_model

    def _extract_error_detail(resp: requests.Response) -> str:
        try:
            err_json = resp.json()
            if isinstance(err_json, dict):
                err = err_json.get("error")
                if isinstance(err, dict):
                    return str(err.get("message", ""))[:300]
                return str(err_json.get("message", "") or err_json.get("detail", ""))[:300]
        except Exception:
            pass
        return (resp.text or "").strip()[:300]

    try:
        def _post_current(request_body: dict):
            return requests.post(endpoint, headers=headers, json=request_body, timeout=settings.request_timeout_seconds)

        response = _post_current(body)

        if not response.ok:
            raise RuntimeError(
                f"Image generation failed ({response.status_code}) [{settings.image_provider}]: {_extract_error_detail(response)}"
            )
        payload_json = response.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"Image generation request failed [{settings.image_provider}].") from exc

    image_bytes: bytes | None = None
    if settings.image_provider == "openrouter":
        if not isinstance(payload_json, dict):
            raise RuntimeError("OpenRouter image response is not JSON.")
        image_bytes = _extract_openrouter_image_bytes(payload_json)
    else:
        data = payload_json.get("data") if isinstance(payload_json, dict) else None
        if not isinstance(data, list) or not data:
            raise RuntimeError(f"Image generation returned empty data [{settings.image_provider}].")

        first = data[0]
        b64_data = first.get("b64_json") or first.get("b64")
        if isinstance(b64_data, str) and b64_data.strip():
            image_bytes = base64.b64decode(b64_data)
        else:
            image_url = first.get("url")
            if isinstance(image_url, str) and image_url.strip():
                download = requests.get(image_url, timeout=settings.request_timeout_seconds)
                download.raise_for_status()
                image_bytes = download.content

    if not image_bytes:
        raise RuntimeError(f"Image response did not include an image payload [{settings.image_provider}].")

    if use_overlay_logo and logo_bytes is not None:
        image_bytes = _overlay_logo(image_bytes, logo_bytes)

    with open(file_path, "wb") as f:
        f.write(image_bytes)

    return ImageGenerationResult(
        model=provider_label,
        size=used_size,
        style=style,
        prompt_used=prompt,
        negative_prompt_used="",
        file_path=file_path.replace("\\", "/"),
        alt_text=build_alt_text(
            content_type=payload.content_type.value,
            industry=payload.industry,
            style=style,
        ),
    )
