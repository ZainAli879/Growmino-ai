from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from openai import OpenAIError

from app.config import Settings, get_settings
from app.openai_clients import generate_caption, generate_image
from app.schemas import ErrorResponse, GenerateRequest, GenerateResponse, MetaInfo, OpenAIImageInfo, QAInfo, TraceInfo
from app.utils import append_jsonl
from app.validators import (
    heuristic_no_fabricated_numbers_if_no_proof,
    validate_day_type_match,
    validate_has_hook_and_cta,
    validate_hashtag_count,
    validate_word_count,
)

app = FastAPI(title="AI Post Generator", version="1.0.0")


@app.post(
    "/generate",
    response_model=GenerateResponse,
    responses={400: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
)
async def generate_endpoint(payload: GenerateRequest) -> GenerateResponse:
    settings: Settings
    try:
        settings = get_settings()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Service configuration error.") from exc

    try:
        validate_day_type_match(payload.day, payload.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = await asyncio.wait_for(_run_generation(payload, settings), timeout=settings.request_timeout_seconds)
        return result
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=502, detail="Generation timed out. Please retry.") from exc
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail="OpenAI service error while generating content.") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unexpected generation error.") from exc


async def _run_generation(payload: GenerateRequest, settings: Settings) -> GenerateResponse:
    trace_id = str(uuid4())
    started_at = datetime.now(timezone.utc).isoformat()
    total_started = perf_counter()

    text_model = settings.openrouter_text_model if settings.text_provider == "openrouter" else settings.caption_model

    caption_started = perf_counter()
    caption_result = await asyncio.to_thread(generate_caption, payload, settings)
    caption_elapsed_ms = int((perf_counter() - caption_started) * 1000)

    image_started = perf_counter()
    image_result = await asyncio.to_thread(
        generate_image,
        payload,
        settings,
        caption_result.caption,
        caption_result.headline,
    )
    image_elapsed_ms = int((perf_counter() - image_started) * 1000)
    total_elapsed_ms = int((perf_counter() - total_started) * 1000)

    word_count, platform_limits_ok = validate_word_count(caption_result.caption, payload.platform)
    has_hook, _ = validate_has_hook_and_cta(caption_result.caption, payload.platform)
    no_fabricated_claims = heuristic_no_fabricated_numbers_if_no_proof(caption_result.caption, payload.proof_assets)
    hashtag_count, hashtag_count_ok = validate_hashtag_count(caption_result.caption, payload.platform)

    warnings: list[str] = []
    if not platform_limits_ok:
        warnings.append("Caption word count is outside platform limit.")
    if not has_hook:
        warnings.append("Caption hook is weak or missing in first lines.")
    if not no_fabricated_claims:
        warnings.append("Caption may include unverified numeric claim.")
    if not hashtag_count_ok:
        warnings.append("Hashtag count is outside platform range.")

    qa = QAInfo(
        word_count=word_count,
        platform_limits_ok=platform_limits_ok,
        has_hook=has_hook,
        no_fabricated_claims=no_fabricated_claims,
        safety_ok=True,
        image_has_no_text_requirement=False,
        hashtag_count=hashtag_count,
        hashtag_count_ok=hashtag_count_ok,
        warnings=warnings,
    )

    trace = TraceInfo(
        trace_id=trace_id,
        request_started_at=started_at,
        elapsed_ms_total=total_elapsed_ms,
        elapsed_ms_caption=caption_elapsed_ms,
        elapsed_ms_image_prompt_and_generation=image_elapsed_ms,
        text_provider=settings.text_provider,
        text_model=text_model,
        image_provider=settings.image_provider,
        image_model=image_result.model,
    )

    append_jsonl(
        settings.traces_file,
        {
            "trace_id": trace_id,
            "request_started_at": started_at,
            "meta": {
                "platform": payload.platform.value,
                "day": payload.day.value,
                "content_type": payload.content_type.value,
                "business_name": payload.business_name,
            },
            "caption": caption_result.caption,
            "headline": caption_result.headline,
            "image_prompt_used": image_result.prompt_used,
            "image_file_path": image_result.file_path,
            "qa": qa.model_dump(),
            "timings_ms": {
                "total": total_elapsed_ms,
                "caption": caption_elapsed_ms,
                "image_prompt_and_generation": image_elapsed_ms,
            },
            "provider": settings.image_provider,
            "model": image_result.model,
            "text_provider": settings.text_provider,
            "text_model": text_model,
        },
    )

    response = GenerateResponse(
        meta=MetaInfo(
            platform=payload.platform,
            day=payload.day,
            content_type=payload.content_type,
            business_name=payload.business_name,
        ),
        caption=caption_result.caption,
        headline=caption_result.headline,
        openai_image=OpenAIImageInfo(
            model=image_result.model,
            size=image_result.size,
            style=image_result.style,
            prompt_used=image_result.prompt_used,
            negative_prompt_used=image_result.negative_prompt_used,
            file_path=image_result.file_path,
            alt_text=image_result.alt_text,
        ),
        qa=qa,
        trace=trace,
    )
    return response
