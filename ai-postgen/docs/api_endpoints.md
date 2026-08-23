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
API_AUTH_REQUIRED=true
GROWMINO_JWT_SECRET=<production-jwt-secret-or-replace-auth-dependency>
```

LinkedIn tokens and provider secrets are never returned to the client.

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

Generates one caption and one image, then returns the generated content directly. Product-side persistence is handled by the web team.

Request:

```json
{
  "business_name": "GrowMino AI",
  "industry": "AI content automation",
  "offer": "AI-generated captions and visuals for businesses",
  "target_audience": "Founders and marketing teams",
  "audience_pain_points": "They struggle to create consistent social content",
  "weekly_focus_topic": "Turning one business brief into ready-to-post content",
  "day": "Monday",
  "content_type": "Educational",
  "tone": "Confident and practical",
  "brand_personality": "Modern, sharp, reliable",
  "cta_preference": "Invite readers to request a demo",
  "proof_assets": "Used to speed up weekly content planning",
  "company_logo_url": "https://example.com/logo.png",
  "platform": "linkedin"
}
```

Response includes:

- `post_id`
- `caption`
- `headline`
- `openai_image.public_url`
- `qa`
- `trace`

## Generated Posts

### `GET /api/v1/posts?limit=50`

Compatibility endpoint. Product-side persistence is handled by the web team, so this backend returns an empty list.

### `GET /api/v1/posts/{post_id}`

Returns either:

- a generated AI post, or
- a LinkedIn publishing job status if the id belongs to a LinkedIn job

## Weekly Content Plans

### `POST /api/v1/content-plans`

Creates a weekly content plan and automatically generates the planned posts.

Request:

```json
{
  "business_name": "GrowMino AI",
  "industry": "AI content automation",
  "offer": "AI-generated captions and visuals",
  "target_audience": "Founders and small marketing teams",
  "audience_pain_points": "Inconsistent posting and slow design workflows",
  "tone": "Confident and practical",
  "brand_personality": "Modern, sharp, reliable",
  "cta_preference": "Book a demo",
  "proof_assets": "Helps create weekly post batches",
  "company_logo_url": "",
  "week_start_date": "2026-08-24",
  "weekly_goal": "Educate prospects and drive qualified conversations",
  "theme": "AI social media automation",
  "platforms": ["linkedin"],
  "posts_count": 5
}
```

Response includes planned items plus generated caption/image output for each item.

## Assets

### `POST /api/v1/assets`

Accepts a base64 data URL and stores it under local `outputs/manual_uploads`.

Request:

```json
{
  "file_name": "post.png",
  "data_url": "data:image/png;base64,..."
}
```

Response:

```json
{
  "file_path": "outputs/manual_uploads/...",
  "public_url": "/outputs/manual_uploads/..."
}
```

Note: generated/manual uploaded files are not product storage. The web team should persist assets on their side. LinkedIn immediate image publishing should use `multipart/form-data` on `/api/v1/posts/linkedin/publish-image`. Scheduled LinkedIn image posts require a durable HTTPS `image_url`.

## Meta Publishing

### `POST /api/v1/publishing-jobs`

Publishes to Facebook or Instagram through the existing Meta flow.

Use `image_url` for image posts. `image_file_path` is kept only for backward schema compatibility and is rejected because storage/uploading is handled outside this backend.

Request:

```json
{
  "platform": "facebook",
  "caption": "Post caption",
  "image_url": "https://example.com/image.png",
  "image_file_path": "",
  "access_token": "",
  "facebook_page_id": "",
  "facebook_access_token": "",
  "instagram_business_account_id": "",
  "instagram_access_token": ""
}
```

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
