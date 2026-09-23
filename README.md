# GrowMino AI Backend

Backend-only FastAPI service for GrowMino AI content generation and social publishing.

This codebase intentionally does not include a frontend, Streamlit app, Google Sheets pipeline, or Google Drive upload flow. The web team should call these APIs directly.

## What This Backend Provides

- AI caption + image generation with OpenAI or OpenRouter
- Production generated-post creation from `business-management` PostgreSQL data
- Generated post image upload to Supabase Storage
- Generated post metadata persistence to `public.posts`
- Weekly content plan generation with automatic post generation
- Meta publishing for Facebook and Instagram using public image URLs
- LinkedIn personal-profile OAuth
- LinkedIn personal-profile text publishing
- LinkedIn immediate image upload publishing
- LinkedIn image URL publishing
- LinkedIn scheduling through the GrowMino worker
- API documentation and Postman collection for web-team handoff
- Production guardrails: request IDs, consistent errors, body-size limits, rate limits, security headers, explicit CORS, and production config validation

## Project Structure

```text
ai-postgen/
  app/
    api.py
    api_security.py
    auth.py
    chains.py
    config.py
    database.py
    linkedin_api.py
    linkedin_client.py
    linkedin_store.py
    main.py
    openai_clients.py
    post_generation_service.py
    prompt_library.py
    schemas.py
    social_api.py
    social_publish.py
    storage.py
    utils.py
    validators.py
  docs/
    api_endpoints.md
    linkedin_personal_profile_integration.md
    GrowMino_LinkedIn_Personal_Profile_Postman_Collection.json
    GrowMino_Social_Publishing_Postman_Collection.json
  scripts/
    generate_weekly_content.py
    process_linkedin_jobs.py
  deploy/
    systemd/
      growmino-weekly-generator.service
      growmino-weekly-generator.timer
  Dockerfile
  .dockerignore
  .env.example
  requirements.txt
```

## Setup

```powershell
cd ai-postgen
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Then edit `.env`.

Local-only files are intentionally ignored by Git and should not be committed:

- `.env`
- `.venv/`
- `outputs/`
- runtime logs, caches, and generated images

Share real credentials through the team's secret-management process, not through GitHub.

## Required Provider Variables

For OpenAI:

```text
OPENAI_API_KEY=
TEXT_PROVIDER=openai
IMAGE_PROVIDER=openai
```

For OpenRouter text/image alternatives:

```text
OPENROUTER_API_KEY=
TEXT_PROVIDER=openrouter
IMAGE_PROVIDER=openrouter
```

For LinkedIn:

```text
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
LINKEDIN_REDIRECT_URI=
LINKEDIN_FRONTEND_SUCCESS_URL=
LINKEDIN_FRONTEND_ERROR_URL=
TOKEN_ENCRYPTION_KEY=
```

Generate `TOKEN_ENCRYPTION_KEY`:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

For generated post persistence:

```text
DATABASE_URL=postgresql://APP_USER:PASSWORD@127.0.0.1:5432/business-management
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_POST_MEDIA_BUCKET=post-media
SUPABASE_BUSINESS_ASSETS_BUCKET=business-assets
```

If image generation should use a company logo reference, provide the logo outside Git or place it in a tracked asset location and set:

```text
DEFAULT_COMPANY_LOGO_PATH=
LOGO_INPUT_MODE=overlay|reference|both
```

## Run Backend

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

OpenAPI docs:

```text
http://localhost:8000/docs
```

This repository is backend-only. Configure frontend URLs in `.env` for OAuth redirects.

For LinkedIn OAuth, `LINKEDIN_REDIRECT_URI` must point to this backend callback:

```text
https://your-api-domain.com/api/v1/integrations/linkedin/callback
```

`LINKEDIN_FRONTEND_SUCCESS_URL` and `LINKEDIN_FRONTEND_ERROR_URL` must point to frontend pages that handle the post-OAuth user experience.

## Docker

```powershell
docker build -t growmino-ai-backend .
docker run --env-file .env -p 8000:8000 growmino-ai-backend
```

## Production API Settings

Use these minimum settings before deployment:

```text
ENVIRONMENT=production
API_AUTH_REQUIRED=true
ALLOW_DEV_AUTH_HEADERS=false
GROWMINO_JWT_SECRET=<at-least-32-characters>
CORS_ALLOW_ORIGINS=https://your-frontend-domain.com
PUBLIC_BASE_URL=https://your-api-domain.com
EXPOSE_API_DOCS=false
EXPOSE_OUTPUTS=false
API_RATE_LIMIT_ENABLED=true
SECURE_HSTS_ENABLED=true
```

All API responses include `X-Request-Id`. Error responses keep the old `detail` field and also include a production-friendly error envelope:

```json
{
  "detail": "Authentication required.",
  "request_id": "request-id",
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Authentication required.",
    "request_id": "request-id"
  }
}
```

## API Handoff Docs

Main web-team endpoint guide:

```text
docs/api_endpoints.md
```

LinkedIn-specific guide:

```text
docs/linkedin_personal_profile_integration.md
```

Postman collections:

```text
docs/GrowMino_LinkedIn_Personal_Profile_Postman_Collection.json
docs/GrowMino_Social_Publishing_Postman_Collection.json
```

## Authentication

Production requests should use a signed GrowMino JWT:

```text
Authorization: Bearer <growmino-jwt>
```

The JWT must be signed with `GROWMINO_JWT_SECRET` and include the user/business context expected by `app/auth.py`. Development headers such as `X-Growmino-User-Id` and `X-Growmino-Business-Id` are only for local testing and must stay disabled in production with `ALLOW_DEV_AUTH_HEADERS=false`.

## API Routes

- `GET /api/v1/health`
- `POST /api/v1/posts`
- `GET /api/v1/posts`
- `GET /api/v1/posts/{post_id}`
- `POST /api/v1/content-plans`
- `POST /api/v1/social/facebook/posts/text`
- `POST /api/v1/social/facebook/posts/image-url`
- `POST /api/v1/social/facebook/posts/image`
- `POST /api/v1/social/facebook/posts/multi-image-url`
- `POST /api/v1/social/facebook/posts/multi-image`
- `POST /api/v1/social/instagram/posts/image-url`
- `POST /api/v1/social/instagram/posts/image`
- `POST /api/v1/social/instagram/posts/carousel-url`
- `POST /api/v1/social/instagram/posts/carousel`
- `GET /api/v1/integrations/linkedin/connect`
- `GET /api/v1/integrations/linkedin/callback`
- `GET /api/v1/integrations/linkedin/status`
- `DELETE /api/v1/integrations/linkedin/disconnect`
- `POST /api/v1/posts/linkedin/publish-text`
- `POST /api/v1/posts/linkedin/publish-image`
- `POST /api/v1/posts/linkedin/publish-image-url`
- `POST /api/v1/social/linkedin/posts/text`
- `POST /api/v1/social/linkedin/posts/image`
- `POST /api/v1/social/linkedin/posts/image-url`
- `POST /api/v1/social/linkedin/posts/multi-image`
- `POST /api/v1/posts/linkedin/schedule`
- `GET /api/v1/posts/linkedin/jobs`
- `POST /api/v1/posts/{post_id}/retry`
- `DELETE /api/v1/posts/{post_id}/schedule`

## Generated Post Persistence

`POST /api/v1/posts` is the production generated-post endpoint. It reads business, category, marketing profile, and one weekly schedule row from the `business-management` PostgreSQL database, generates the caption/image with the existing AI implementation, uploads the image to Supabase Storage, inserts the generated post into `public.posts`, and returns public image URL fields only.

- Request body: `business_id`, `weekly_schedule_id`, `platform`
- Response image fields: `image_url` and `image_urls`
- The API no longer returns Base64 for `POST /api/v1/posts`
- `POST /api/v1/content-plans` uses the same generation/storage/persistence pipeline for every configured row in `business_weekly_schedules`.
- Content plan request body: `business_id`, `week_start_date`
- Content plan responses return Supabase URLs only; they never return `image_base64` or `image_data_url`.
- Weekly automation skips incomplete schedule rows before any AI call when `content_type`, `weekly_topic`, or valid `platforms` are missing.
- Image prompts are business-aware: the creative direction uses the business category, offer, audience pain, topic, CTA preference, proof assets, caption, platform, and logo mode before calling the image model.
- `scripts/generate_weekly_content.py --once` generates the current week's configured posts for every active business and skips posts already generated for the same business/week/schedule/platform.
- LinkedIn OAuth state, encrypted profile tokens, and scheduled LinkedIn jobs use `LINKEDIN_STORE_FILE` for backend runtime state.
- For production, replace `app/linkedin_store.py` with the platform database implementation while keeping the same function contracts.

## Weekly Automation

Manual test:

```bash
cd /srv/growmino-ai-backend/app/ai-postgen
/srv/growmino-ai-backend/venv/bin/python scripts/generate_weekly_content.py --once --dry-run
/srv/growmino-ai-backend/venv/bin/python scripts/generate_weekly_content.py --once
```

Install and enable systemd:

```bash
sudo cp deploy/systemd/growmino-weekly-generator.service /etc/systemd/system/
sudo cp deploy/systemd/growmino-weekly-generator.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now growmino-weekly-generator.timer
```

Check schedule and logs:

```bash
systemctl list-timers growmino-weekly-generator.timer
journalctl -u growmino-weekly-generator.service -f
```

## LinkedIn Scheduled Worker

Scheduled LinkedIn posts are claimed and published by `scripts/process_linkedin_jobs.py`. Run it as a worker process in production if LinkedIn scheduling is enabled:

```bash
python scripts/process_linkedin_jobs.py --interval 60 --limit 5
```

For a one-off run:

```bash
python scripts/process_linkedin_jobs.py --once
```

The current local implementation stores OAuth state, profile tokens, and scheduled LinkedIn jobs in `LINKEDIN_STORE_FILE`. For production, replace `app/linkedin_store.py` with the platform database implementation while preserving the same function contracts.

## Handover Checklist

- Rotate all credentials before sharing access with a new team.
- Keep `.env`, `.venv/`, and `outputs/` out of GitHub.
- Set production frontend origins in `CORS_ALLOW_ORIGINS`.
- Set real LinkedIn frontend success/error URLs.
- Confirm `DATABASE_URL` points to the `business-management` database.
- Confirm Supabase buckets and service-role key are configured.
- Run `python -m compileall app scripts` after deployment changes.

## Validation

```powershell
python -m compileall app scripts
```
