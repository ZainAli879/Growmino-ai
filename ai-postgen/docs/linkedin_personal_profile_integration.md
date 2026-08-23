# GrowMino LinkedIn Personal Profile Integration

This integration supports personal LinkedIn profiles only. It does not publish to LinkedIn Company Pages.

## LinkedIn App Setup

Enable these products in the LinkedIn Developer Portal:

- OpenID Connect
- Share on LinkedIn

Use these OAuth scopes:

```text
openid profile email w_member_social
```

For local callback testing with Cloudflare:

```powershell
cloudflared tunnel --url http://localhost:8000
```

Set the backend environment variable to the generated tunnel callback and add the exact same callback URL in the LinkedIn Developer Portal:

```text
LINKEDIN_REDIRECT_URI=https://generated.trycloudflare.com/api/v1/integrations/linkedin/callback
```

## Required Environment Variables

```text
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
LINKEDIN_REDIRECT_URI=
LINKEDIN_FRONTEND_SUCCESS_URL=https://app.example.com/integrations/linkedin/success
LINKEDIN_FRONTEND_ERROR_URL=https://app.example.com/integrations/linkedin/error
TOKEN_ENCRYPTION_KEY=
CORS_ALLOW_ORIGINS=https://app.example.com
```

Generate `TOKEN_ENCRYPTION_KEY`:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Auth Headers For Local/Postman Testing

Until the production JWT verifier is connected, API clients can send:

```text
X-Growmino-User-Id: local-user
X-Growmino-Business-Id: local-business
```

In production, set:

```text
API_AUTH_REQUIRED=true
GROWMINO_JWT_SECRET=<shared HS256 JWT secret>
```

## Endpoints

### Connect

```http
GET /api/v1/integrations/linkedin/connect
```

Returns:

```json
{
  "authorization_url": "https://www.linkedin.com/oauth/v2/authorization?...",
  "expires_in_seconds": 600
}
```

The web app redirects the browser to `authorization_url`.

### Callback

```http
GET /api/v1/integrations/linkedin/callback?code=...&state=...
```

The backend exchanges the code, calls `/v2/userinfo`, stores `urn:li:person:{sub}`, encrypts the access token, and redirects to the configured web-app success/error URL.

### Status

```http
GET /api/v1/integrations/linkedin/status
```

### Disconnect

```http
DELETE /api/v1/integrations/linkedin/disconnect
```

### Publish Text

```http
POST /api/v1/posts/linkedin/publish-text
Content-Type: application/json
```

```json
{
  "caption": "Text post content",
  "idempotency_key": "unique-client-key"
}
```

### Publish Image Upload

```http
POST /api/v1/posts/linkedin/publish-image
Content-Type: multipart/form-data
```

Fields:

- `caption`
- `idempotency_key`
- `file` as JPEG, PNG, or WebP

Do not manually set multipart `Content-Type` in browser code.

### Publish Image URL

```http
POST /api/v1/posts/linkedin/publish-image-url
Content-Type: application/json
```

```json
{
  "caption": "Image post content",
  "image_url": "https://cdn.example.com/image.png",
  "idempotency_key": "unique-client-key"
}
```

The URL must be HTTPS and must not resolve to private, loopback, link-local, multicast, reserved, or unspecified networks.

### Publish Multi-Image

```http
POST /api/v1/social/linkedin/posts/multi-image
Content-Type: multipart/form-data
```

Fields:

- `caption`
- `idempotency_key`
- `images` repeated 2 to 20 times as JPG/JPEG, PNG, or GIF
- `alt_texts` optionally repeated in the same order as `images`

The backend uses the existing encrypted OAuth token and `w_member_social` permission. It initializes every image upload with LinkedIn `/rest/images?action=initializeUpload`, streams each image binary directly to the returned upload URL, collects the returned image URNs, then creates the final `/rest/posts` multi-image post.

The final LinkedIn post is created only after every image upload succeeds. The stored GrowMino job keeps the caption, publish status, `linkedin_post_id`, and uploaded image URNs.

Example cURL:

```bash
curl -X POST "http://localhost:8000/api/v1/social/linkedin/posts/multi-image" \
  -H "X-Growmino-User-Id: local-user" \
  -H "X-Growmino-Business-Id: local-business" \
  -F "caption=Multi-image post from GrowMino" \
  -F "idempotency_key=unique-client-key" \
  -F "alt_texts=First image alt text" \
  -F "alt_texts=Second image alt text" \
  -F "images=@C:/path/to/first.jpg;type=image/jpeg" \
  -F "images=@C:/path/to/second.png;type=image/png"
```

### Schedule

```http
POST /api/v1/posts/linkedin/schedule
Content-Type: application/json
```

```json
{
  "caption": "Scheduled post",
  "scheduled_for": "2026-08-21T10:00:00+05:00",
  "timezone": "Asia/Karachi",
  "image_url": "https://cdn.example.com/image.png",
  "idempotency_key": "unique-client-key"
}
```

If `image_url` is empty, the scheduled post is text-only. Scheduled images require a durable HTTPS `image_url`.

### Status, Retry, Cancel

```http
GET /api/v1/posts/{post_id}
POST /api/v1/posts/{post_id}/retry
DELETE /api/v1/posts/{post_id}/schedule
GET /api/v1/posts/linkedin/jobs
```

## Worker

Run due scheduled jobs:

```powershell
python scripts/process_linkedin_jobs.py --once
```

Run continuously:

```powershell
python scripts/process_linkedin_jobs.py --interval 60 --limit 5
```

## Security Notes

- Access tokens are encrypted with Fernet before backend state storage.
- OAuth state is random, hashed in backend state storage, expiring, and single-use.
- LinkedIn tokens and client secrets are never returned to API clients.
- Image uploads are validated by actual content using Pillow.
- URL image publishing uses HTTPS-only SSRF checks.
- `x-restli-id` is saved as `linkedin_post_id`.
- Idempotency is enforced with `(user_id, business_id, idempotency_key)`.
