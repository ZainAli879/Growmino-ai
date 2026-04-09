# AI Post Generator (Backend Only)

Backend-only FastAPI service that generates:
- One finalized social media caption + headline
- One provider-generated image aligned to that caption (`infip` by default)

Optional local Streamlit helper UI is included for easier testing.

## Tech Stack
- Python 3.11+
- FastAPI + Uvicorn
- LangChain (prompt templating + output parsing)
- Pydantic
- Official OpenAI Python SDK
- python-dotenv
- Pillow (installed, optional)

## Project Structure

```text
/ai-postgen
  /app
    main.py
    api.py
    schemas.py
    config.py
    chains.py
    openai_clients.py
    validators.py
    prompt_library.py
    utils.py
  /outputs
  streamlit_app.py
  requirements.txt
  .env.example
  README.md
```

`outputs/` is created automatically at runtime if missing.

## Setup

1. Create and activate a virtual environment:

```powershell
cd ai-postgen
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Configure environment variables:

```powershell
copy .env.example .env
# then edit .env and set provider keys/models
```

Required environment variables:
- `TEXT_PROVIDER` (`openai` or `openrouter`, default `openai`)
- `IMAGE_PROVIDER` (`infip`, `openai`, `openrouter`, or `custom`, default `infip`)
- `OPENAI_API_KEY` (required when `TEXT_PROVIDER=openai` or `IMAGE_PROVIDER=openai`)
- `OPENROUTER_API_KEY` (required when `TEXT_PROVIDER=openrouter` or `IMAGE_PROVIDER=openrouter`)
- `INFIP_API_KEY` (required when `IMAGE_PROVIDER=infip`)

Optional:
- `CAPTION_MODEL` (default: `gpt-4o-mini`, used for `TEXT_PROVIDER=openai`)
- `OPENAI_BASE_URL` (default: `https://api.openai.com/v1`)
- `OPENAI_IMAGE_MODEL` (default: `gpt-image-1`)
- `OPENROUTER_BASE_URL` (default: `https://openrouter.ai/api/v1`)
- `OPENROUTER_TEXT_MODEL` (default: `openai/gpt-4o-mini`)
- `OPENROUTER_IMAGE_MODEL` (default: `openai/gpt-image-1`)
- `OPENROUTER_HTTP_REFERER` (optional, recommended for OpenRouter)
- `OPENROUTER_APP_NAME` (optional title header for OpenRouter, default: `ai-postgen`)
- `INFIP_BASE_URL` (default: `https://api.infip.pro/v1`)
- `INFIP_IMAGE_MODEL` (default: `img4`)
- `IMAGE_SIZE` fallback size (default: `1024x1024`)
- `LINKEDIN_IMAGE_SIZE` (default: `1200x1200`)
- `INSTAGRAM_IMAGE_SIZE` (default: `1080x1350`)
- `FACEBOOK_IMAGE_SIZE` (default: `1200x630`)
- `REQUEST_TIMEOUT_SECONDS` (default: `300`)
- `UI_API_TIMEOUT_SECONDS` (default: `300` for Streamlit)
- `TRACES_FILE` (default: `./outputs/traces/generation-traces.jsonl`)
- `GOOGLE_CREDENTIALS_JSON_PATH` (service-account JSON path)
- `GOOGLE_SPREADSHEET_ID` (Google Sheet ID)
- `GOOGLE_SHEET_NAME` (tab name, default `Sheet1`)
- `GOOGLE_DRIVE_FOLDER_ID` (Drive folder for uploaded images)
- `DEFAULT_COMPANY_LOGO_PATH` (optional local logo fallback used when sheet `company_logo_url` is empty)
- `LOGO_INPUT_MODE` (`overlay`, `reference`, `both`; default `overlay`. `both` is recommended)
- `HEADLINE_OVERLAY_ENABLED` (`true`/`false`, default `true`; recommended `true` for crisp, typo-free headline text)

## Run

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or use `PORT` from env:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port $env:PORT --reload
```

## Optional Streamlit UI

In a second terminal (with the same venv active):

```powershell
streamlit run streamlit_app.py
```

Open:

```text
http://localhost:8501
```

By default the UI calls:

```text
http://127.0.0.1:8000/generate
```

## API

### POST `/generate`

Generates one caption and one image, saves the image locally, and returns JSON.
Response now includes:
- `caption`
- `headline`
- `openai_image`
- `qa` (non-blocking checks + warnings)
- `trace` (timings, provider/model, trace id)

### LinkedIn cURL example

```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "business_name": "FlowOps Studio",
    "industry": "B2B Automation",
    "offer": "Workflow automation sprints",
    "target_audience": "Operations managers at SMBs",
    "audience_pain_points": "Manual follow-ups, inconsistent handoffs",
    "weekly_focus_topic": "Reducing bottlenecks in lead handoff",
    "day": "Monday",
    "content_type": "Educational",
    "tone": "Practical and confident",
    "brand_personality": "Direct, modern, helpful",
    "cta_preference": "Ask readers to comment 'PLAYBOOK'",
    "proof_assets": "",
    "company_logo_url": "https://example.com/logo.png",
    "platform": "linkedin"
  }'
```

### Instagram cURL example

```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "business_name": "FlowOps Studio",
    "industry": "B2B Automation",
    "offer": "Workflow automation sprints",
    "target_audience": "Service business owners",
    "audience_pain_points": "Too many repetitive admin tasks",
    "weekly_focus_topic": "Automating repetitive client onboarding tasks",
    "day": "Saturday",
    "content_type": "Automation Tip",
    "tone": "Friendly and practical",
    "brand_personality": "Clear, energetic, no fluff",
    "cta_preference": "Invite people to DM for checklist",
    "proof_assets": "",
    "company_logo_url": "https://example.com/logo.png",
    "platform": "instagram"
  }'
```

## Output files
Generated images are saved to:

```text
./outputs/<timestamp>-<platform>-<day>-<content_type>.png
```

Example:

```text
./outputs/20260219-141530-linkedin-monday-educational.png
```

## Golden Smoke Checks

Run the backend first, then execute:

```powershell
python scripts/run_golden_smoke.py --api http://127.0.0.1:8000/generate
```

Golden test inputs are in `tests/golden_requests.json`.

## Google Sheets + Drive Pipeline

You can process pending rows from a Google Sheet, generate caption/image, upload image to Drive, and write outputs back to the same row.

### 1. Enable APIs and share resources with service account

- Enable **Google Sheets API** and **Google Drive API** in your Google Cloud project.
- Create/download a service-account JSON key.
- Share your target Google Sheet with the service-account email as Editor.
- Share your target Drive folder with the same service-account email as Editor.

Note for private Drive logo links in `company_logo_url`:
- If using `GOOGLE_DRIVE_AUTH_MODE=oauth_user`, ensure your Drive OAuth token was granted full Drive scope.
- If you previously authorized with narrower scope, delete `oauth-token-drive.json` and rerun the script to re-authorize.

### 2. Sheet columns

Header row must include these input columns (case-insensitive):

- `business_name`
- `industry`
- `offer`
- `target_audience`
- `audience_pain_points`
- `weekly_focus_topic`
- `day` (e.g. `Monday`)
- `content_type` (e.g. `Educational`, `Pain-point`, `Case Study`)
- `tone`
- `brand_personality`
- `cta_preference`
- `proof_assets`
- `company_logo_url` (optional, URL/local path/data URL of brand logo to overlay on final image; Google Drive file links are supported with configured Drive auth)
- `platform`:
  - single platform: `linkedin`, `instagram`, `facebook` (case-insensitive, e.g. `LinkedIn`)
  - multi-platform in one row: `all` or comma-separated list like `linkedin,instagram,facebook`

The script auto-adds output columns if missing:
- `status`
- `caption`
- `headline`
- `image_file_path`
- `drive_image_url`
- `error`
- `processed_at_utc`
- `trace_id`
- `caption_linkedin`, `caption_instagram`, `caption_facebook`
- `headline_linkedin`, `headline_instagram`, `headline_facebook`
- `image_file_path_linkedin`, `image_file_path_instagram`, `image_file_path_facebook`
- `drive_image_url_linkedin`, `drive_image_url_instagram`, `drive_image_url_facebook`
- `trace_id_linkedin`, `trace_id_instagram`, `trace_id_facebook`
- `error_linkedin`, `error_instagram`, `error_facebook`

Rows where `status` is empty (or not `done`/`processing`) are treated as pending.

### 3. Run the processor

From `ai-postgen` directory:

```powershell
python scripts/process_sheet_rows.py --max-rows 5
```

What it does per row:
- Marks `status=processing`
- Runs generation for each requested platform in the row
- Saves image locally under `outputs/`
- Uploads image to Drive folder
- Writes platform-specific caption/headline/paths/drive URL columns
- Marks `status=done` (all success), `status=partial` (some success), or `status=error` (all failed)
- On failure, writes `status=error` and error details
