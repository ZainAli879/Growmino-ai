# GrowMino AI Backend API Endpoints

Base URL for local development:

```text
http://localhost:8000
```

Production should use your deployed API domain.

## Authentication

All user-owned endpoints support a temporary backend auth boundary:

```http
X-Growmino-User-Id: local-user
X-Growmino-Business-Id: local-business
```

Production should set:

```text
ENVIRONMENT=production
API_AUTH_REQUIRED=true
ALLOW_DEV_AUTH_HEADERS=false
GROWMINO_JWT_SECRET=<production-jwt-secret-or-replace-auth-dependency>
CORS_ALLOW_ORIGINS=https://your-frontend-domain.com
EXPOSE_TEST_UI=false
EXPOSE_API_DOCS=false
EXPOSE_OUTPUTS=false
```

LinkedIn tokens and provider secrets are never returned to the client.

## Production Guardrails

Every API response includes:

```http
X-Request-Id: request-id
```

Frontend clients may also send their own request id:

```http
X-Request-Id: frontend-generated-request-id
```

Security headers are added automatically:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy: camera=(), microphone=(), geolocation=()
Cache-Control: no-store
```

Error response format:

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

The `detail` field is kept for backward compatibility. New frontend work should use `error.code`, `error.message`, and `request_id`.

Default rate limits:

```text
General API: 120 requests / 60 seconds
Generation API: 10 requests / 3600 seconds
Publishing API: 60 requests / 60 seconds
Max request body: 25,000,000 bytes
```

Relevant environment variables:

```text
API_MAX_BODY_BYTES=25000000
API_RATE_LIMIT_ENABLED=true
API_RATE_LIMIT_REQUESTS=120
API_RATE_LIMIT_WINDOW_SECONDS=60
API_GENERATION_RATE_LIMIT_REQUESTS=10
API_GENERATION_RATE_LIMIT_WINDOW_SECONDS=3600
API_PUBLISH_RATE_LIMIT_REQUESTS=60
API_PUBLISH_RATE_LIMIT_WINDOW_SECONDS=60
SECURE_HSTS_ENABLED=true
```

In production, `ENVIRONMENT=production` validates the required auth/CORS settings at startup. The temporary `/test-ui` page and API docs are hidden unless explicitly exposed, and `/outputs` cannot be publicly exposed.

## Health

### `GET /api/v1/health`

Returns backend status.

Response:

```json
{
  "status": "ok"
}
```

## AI Content Generation

### `POST /api/v1/posts`

Generates one caption and one image from existing business/schedule records, uploads the generated image to Supabase Storage, stores the generated post in `public.posts`, and returns a clean URL-based response.

The frontend should no longer send the full business profile to this endpoint. Send identifiers only.

Request:

```json
{
  "business_id": "e450a91d-fb86-48de-a775-dab10b1749b7",
  "weekly_schedule_id": "30c4b1fb-93a8-40a7-a8dc-8a13948662f3",
  "platform": "instagram"
}
```

Backend DB mapping:

```text
business_name          = businesses.business_name
industry               = categories.title + " - " + subcategories.title
offer                  = business_weekly_schedules.offer
target_audience        = business_marketing_profiles.targeted_audience
audience_pain_points   = business_weekly_schedules.pain_point
weekly_focus_topic     = business_weekly_schedules.weekly_topic
day                    = business_weekly_schedules.day_of_week converted to weekday name
content_type           = business_weekly_schedules.content_type
tone                   = business_weekly_schedules.tone
brand_personality      = business_weekly_schedules.brand_personality
cta_preference         = business_weekly_schedules.cta_preferences
proof_assets           = business_weekly_schedules.proof_assets
company_logo_url       = businesses.logo when usable
platform               = request platform, validated against schedule platforms
```

Default response:

```json
{
  "post_id": "8cd5fd4e-71f8-4706-9ebe-4c590602f71a",
  "business_id": "e450a91d-fb86-48de-a775-dab10b1749b7",
  "weekly_schedule_id": "30c4b1fb-93a8-40a7-a8dc-8a13948662f3",
  "status": "generated",
  "platform": "instagram",
  "day": "Monday",
  "content_type": "Educational",
  "business_name": "Velmora Fashion",
  "caption": "Generated social media caption...",
  "headline": "Generated headline",
  "image_url": "https://xxxxx.supabase.co/storage/v1/object/public/post-media/businesses/e450a91d-fb86-48de-a775-dab10b1749b7/posts/8cd5fd4e-71f8-4706-9ebe-4c590602f71a/image-1.png",
  "image_urls": [
    "https://xxxxx.supabase.co/storage/v1/object/public/post-media/businesses/e450a91d-fb86-48de-a775-dab10b1749b7/posts/8cd5fd4e-71f8-4706-9ebe-4c590602f71a/image-1.png"
  ],
  "image_mime_type": "image/png",
  "alt_text": "Generated alt text"
}
```

This endpoint never returns `image_base64` or `image_data_url`. The canonical image field is `image_urls`; `image_url` is kept as the first image URL for frontend convenience.

Required environment variables:

```text
DATABASE_URL=postgresql://APP_USER:PASSWORD@127.0.0.1:5432/business-management
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_POST_MEDIA_BUCKET=post-media
SUPABASE_BUSINESS_ASSETS_BUCKET=business-assets
```

## Generated Posts

### `GET /api/v1/posts?limit=50`

Compatibility endpoint. Product-side persistence is handled by the web team, so this backend returns an empty list.

### `GET /api/v1/posts/{post_id}`

Returns either:

- a generated AI post, or
- a LinkedIn publishing job status if the id belongs to a LinkedIn job

## Weekly Content Plans

### `POST /api/v1/content-plans`

Generates all configured weekly schedule posts for a business.

The backend reads `businesses`, `categories`, `subcategories`, `business_marketing_profiles`, and all `business_weekly_schedules` rows for the supplied business. Each scheduled day uses its own schedule values for topic, content type, tone, pain point, offer, CTA, proof assets, and platforms.

For each configured schedule row and platform, the backend generates the caption/image, uploads the image to Supabase Storage, inserts the generated post into `public.posts`, then continues to the next schedule/platform.

Request:

```json
{
  "business_id": "e450a91d-fb86-48de-a775-dab10b1749b7",
  "week_start_date": "2026-09-09"
}
```

Default response:

```json
{
  "plan_id": "8e7fa4f2-5ef2-4dc9-9ff4-41c40499739b",
  "status": "generated",
  "week_start_date": "2026-09-09",
  "total_posts": 7,
  "posts": [
    {
      "position": 1,
      "post_id": "2ee39682-7460-4a65-b09f-4eaa5c3b0391",
      "status": "generated",
      "platform": "linkedin",
      "day": "Monday",
      "content_type": "Educational",
      "topic": "How to choose versatile wardrobe basics",
      "caption": "Generated social media caption...",
      "headline": "Generated headline",
      "image_url": "https://xxxxx.supabase.co/storage/v1/object/public/post-media/businesses/e450a91d-fb86-48de-a775-dab10b1749b7/posts/2ee39682-7460-4a65-b09f-4eaa5c3b0391/image-1.png",
      "image_urls": [
        "https://xxxxx.supabase.co/storage/v1/object/public/post-media/businesses/e450a91d-fb86-48de-a775-dab10b1749b7/posts/2ee39682-7460-4a65-b09f-4eaa5c3b0391/image-1.png"
      ],
      "image_mime_type": "image/png",
      "alt_text": "A visual representing Educational content in the AI content automation industry.",
      "error": ""
    }
  ]
}
```

This endpoint never returns `image_base64` or `image_data_url`. Each returned image is already stored in Supabase Storage and saved in `public.posts.image_urls`.

If one configured schedule/platform fails, the backend continues with the rest and returns `status: "partially_generated"` or `status: "failed"` with each failed post item containing an `error` value.

## Platform-Specific Publishing

These endpoints are the preferred production publishing API shape for the web team. Dynamic values such as Page IDs, Instagram account IDs, and access tokens are required in each request.

### Facebook Text

```http
POST /api/v1/social/facebook/posts/text
Content-Type: application/json
```

```json
{
  "page_id": "119504274583951",
  "page_access_token": "PAGE_ACCESS_TOKEN",
  "caption": "Testing Facebook text publishing from GrowMino.",
  "idempotency_key": "optional-client-key"
}
```

### Facebook Image URL

```http
POST /api/v1/social/facebook/posts/image-url
Content-Type: application/json
```

```json
{
  "page_id": "119504274583951",
  "page_access_token": "PAGE_ACCESS_TOKEN",
  "caption": "Testing Facebook image publishing from GrowMino.",
  "image_url": "https://cdn.example.com/post.jpg",
  "idempotency_key": "optional-client-key"
}
```

### Facebook Image Upload

```http
POST /api/v1/social/facebook/posts/image
Content-Type: multipart/form-data
```

Fields: `page_id`, `page_access_token`, `caption`, `idempotency_key`, and `file`.

### Facebook Multi-Image URL

```http
POST /api/v1/social/facebook/posts/multi-image-url
Content-Type: application/json
```

```json
{
  "page_id": "119504274583951",
  "page_access_token": "PAGE_ACCESS_TOKEN",
  "caption": "Testing Facebook multi-image publishing.",
  "image_urls": [
    "https://cdn.example.com/one.jpg",
    "https://cdn.example.com/two.jpg"
  ],
  "idempotency_key": "optional-client-key"
}
```

### Facebook Multi-Image Upload

```http
POST /api/v1/social/facebook/posts/multi-image
Content-Type: multipart/form-data
```

Fields: `page_id`, `page_access_token`, `caption`, `idempotency_key`, and `images` repeated 2 to 20 times.

### Instagram Image URL

```http
POST /api/v1/social/instagram/posts/image-url
Content-Type: application/json
```

```json
{
  "instagram_business_account_id": "17841462076814255",
  "instagram_access_token": "IG_ACCESS_TOKEN",
  "caption": "Testing Instagram publishing from GrowMino.",
  "image_url": "https://cdn.example.com/post.jpg",
  "idempotency_key": "optional-client-key"
}
```

### Instagram Image Upload

```http
POST /api/v1/social/instagram/posts/image
Content-Type: multipart/form-data
```

Fields: `instagram_business_account_id`, `instagram_access_token`, `caption`, `idempotency_key`, and `file`.

Instagram multipart uploads are disabled while server-side image storage is disabled. Upload images to product object storage first, then call `/api/v1/social/instagram/posts/image-url`.

### Instagram Carousel URL

```http
POST /api/v1/social/instagram/posts/carousel-url
Content-Type: application/json
```

```json
{
  "instagram_business_account_id": "17841462076814255",
  "instagram_access_token": "IG_ACCESS_TOKEN",
  "caption": "Testing Instagram carousel publishing.",
  "image_urls": [
    "https://cdn.example.com/one.jpg",
    "https://cdn.example.com/two.jpg"
  ],
  "idempotency_key": "optional-client-key"
}
```

### Instagram Carousel Upload

```http
POST /api/v1/social/instagram/posts/carousel
Content-Type: multipart/form-data
```

Fields: `instagram_business_account_id`, `instagram_access_token`, `caption`, `idempotency_key`, and `images` repeated 2 to 10 times.

Instagram carousel multipart uploads are disabled while server-side image storage is disabled. Upload images to product object storage first, then call `/api/v1/social/instagram/posts/carousel-url`.

There is no Instagram text-only endpoint because Instagram publishing requires media.

## LinkedIn Personal Profile Integration

LinkedIn products:

- OpenID Connect
- Share on LinkedIn

Scopes:

```text
openid profile email w_member_social
```

### `GET /api/v1/integrations/linkedin/connect`

Creates a secure, expiring, single-use OAuth state and returns LinkedIn’s authorization URL.

Response:

```json
{
  "authorization_url": "https://www.linkedin.com/oauth/v2/authorization?...",
  "expires_in_seconds": 600
}
```

### `GET /api/v1/integrations/linkedin/callback`

LinkedIn redirects here with `code` and `state`.

The backend:

- validates and consumes OAuth state
- exchanges the code for an access token
- calls `/v2/userinfo`
- uses `sub` as the personal profile id
- stores `urn:li:person:{sub}`
- encrypts the access token
- redirects to configured success/error URL

### `GET /api/v1/integrations/linkedin/status`

Returns whether the current GrowMino user/business has a LinkedIn profile connected.

### `DELETE /api/v1/integrations/linkedin/disconnect`

Disconnects the LinkedIn profile for the current GrowMino user/business.

### `POST /api/v1/posts/linkedin/publish-text`

Publishes a text post to the connected personal profile.

Request:

```json
{
  "caption": "LinkedIn text post",
  "idempotency_key": "unique-client-key"
}
```

Production alias:

```text
POST /api/v1/social/linkedin/posts/text
```

### `POST /api/v1/posts/linkedin/publish-image`

Publishes an immediate image post from multipart upload.

Form fields:

- `caption`
- `idempotency_key`
- `file`

Allowed image types:

- JPEG
- PNG
- WebP

The backend validates actual content, registers the LinkedIn asset, streams the binary to LinkedIn’s `uploadUrl`, then creates the UGC image post.

Production alias:

```text
POST /api/v1/social/linkedin/posts/image
```

### `POST /api/v1/posts/linkedin/publish-image-url`

Publishes an immediate image post from a durable HTTPS URL.

Request:

```json
{
  "caption": "LinkedIn image post",
  "image_url": "https://cdn.example.com/post.png",
  "idempotency_key": "unique-client-key"
}
```

Production alias:

```text
POST /api/v1/social/linkedin/posts/image-url
```

SSRF protection blocks non-HTTPS URLs, private IPs, localhost, link-local, multicast, reserved, unspecified addresses, URL credentials, and non-default HTTPS ports.

### `POST /api/v1/social/linkedin/posts/multi-image`

Publishes an immediate LinkedIn personal-profile post with 2 to 20 images.

Content type:

```http
multipart/form-data
```

Form fields:

- `caption`: required text, max 3000 characters
- `idempotency_key`: optional unique client key
- `images`: repeat this field for every uploaded image
- `alt_texts`: optional repeated field, one value per image in the same order

Allowed image types:

- JPG/JPEG
- PNG
- GIF

The backend validates actual file content and maximum size, initializes each LinkedIn image upload with `/rest/images?action=initializeUpload`, uploads each binary directly to LinkedIn, preserves image order, and creates the final post with `/rest/posts`.

Example cURL:

```bash
curl -X POST "http://localhost:8000/api/v1/social/linkedin/posts/multi-image" \
  -H "X-Growmino-User-Id: local-user" \
  -H "X-Growmino-Business-Id: local-business" \
  -F "caption=Multi-image post from GrowMino" \
  -F "idempotency_key=client-generated-key-123" \
  -F "alt_texts=First image description" \
  -F "alt_texts=Second image description" \
  -F "images=@C:/path/to/first.jpg;type=image/jpeg" \
  -F "images=@C:/path/to/second.png;type=image/png"
```

Successful response:

```json
{
  "id": "growmino-job-id",
  "platform": "linkedin",
  "status": "published",
  "linkedin_post_id": "urn:li:share:...",
  "image_urns": ["urn:li:image:...", "urn:li:image:..."],
  "message": "LinkedIn multi-image post published.",
  "scheduled_for_utc": "",
  "display_timezone": ""
}
```

### `POST /api/v1/posts/linkedin/schedule`

Stores a scheduled LinkedIn post. GrowMino’s worker publishes it later.

Request:

```json
{
  "caption": "Scheduled LinkedIn post",
  "scheduled_for": "2026-08-24T10:00:00+05:00",
  "timezone": "Asia/Karachi",
  "image_url": "https://cdn.example.com/post.png",
  "idempotency_key": "unique-client-key"
}
```

If `image_url` is empty, the scheduled post is text-only.

### `GET /api/v1/posts/linkedin/jobs?limit=25`

Returns LinkedIn publishing jobs for the current GrowMino user/business.

### `POST /api/v1/posts/{post_id}/retry`

Retries a failed or scheduled LinkedIn job.

### `DELETE /api/v1/posts/{post_id}/schedule`

Cancels a scheduled or failed scheduled LinkedIn job.

## Worker

Run once:

```powershell
python scripts/process_linkedin_jobs.py --once
```

Run continuously:

```powershell
python scripts/process_linkedin_jobs.py --interval 60 --limit 5
```

## Local Backend Run

```powershell
cd C:\Users\User\OneDrive\Desktop\GrowMino\Digital_Product\ai-postgen
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Cloudflare callback test:

```powershell
cloudflared tunnel --url http://localhost:8000
```

Then set:

```text
LINKEDIN_REDIRECT_URI=https://generated.trycloudflare.com/api/v1/integrations/linkedin/callback
```

Add the exact same URL in the LinkedIn Developer Portal.
