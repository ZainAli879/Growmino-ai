# GrowMino AI Backend

Backend-only FastAPI service for GrowMino AI content generation and social publishing.

This codebase intentionally does not include a frontend, Streamlit app, Supabase integration, Google Sheets pipeline, or Google Drive upload flow. The web team should call these APIs directly and handle product-side persistence/storage in their own application layer.

## What This Backend Provides

- AI caption + image generation with OpenAI or OpenRouter
- Weekly content plan generation with automatic post generation
- Generated images returned as base64/data URLs for product-side storage
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
    auth.py
    chains.py
    config.py
    linkedin_api.py
    linkedin_client.py
    linkedin_store.py
    main.py
    openai_clients.py
    prompt_library.py
    schemas.py
    social_api.py
    social_publish.py
    utils.py
    validators.py
  docs/
    api_endpoints.md
    linkedin_personal_profile_integration.md
    GrowMino_LinkedIn_Personal_Profile_Postman_Collection.json
    GrowMino_Social_Publishing_Postman_Collection.json
  tests/
    test_api_security.py
    test_generation_response.py
    test_linkedin_multi_image.py
    test_social_publishing_routes.py
  .env.example
  requirements.txt
```

## Setup

```powershell
cd C:\Users\User\OneDrive\Desktop\GrowMino\Digital_Product\ai-postgen
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Then edit `.env`.

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
TOKEN_ENCRYPTION_KEY=
```

Generate `TOKEN_ENCRYPTION_KEY`:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Run Backend

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

OpenAPI docs:

```text
http://localhost:8000/docs
```

Temporary local test UI files are ignored by Git and do not ship in the production deployment.

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
EXPOSE_TEST_UI=false
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

Postman collection:

```text
docs/GrowMino_LinkedIn_Personal_Profile_Postman_Collection.json
```

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

## Storage Policy

The backend does not persist generated posts to Supabase or any product database.

- `POST /api/v1/posts` returns generated content and image metadata directly.
- The web/product team should save generated captions, image URLs, post plans, user records, and business records on their side.
- LinkedIn OAuth state, encrypted profile tokens, and scheduled LinkedIn jobs use `LINKEDIN_STORE_FILE` for backend runtime state.
- For production, replace `app/linkedin_store.py` with the platform database implementation while keeping the same function contracts.

## Validation

```powershell
python -m compileall app tests
python -m unittest discover -s tests -v
```
