from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = ""
    infip_api_key: str = ""
    openrouter_api_key: str = ""
    port: int = 8000
    request_timeout_seconds: int = 300
    text_provider: str = "openai"
    caption_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_image_model: str = "gpt-image-1"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_text_model: str = "openai/gpt-4o-mini"
    openrouter_image_model: str = "openai/gpt-image-1"
    openrouter_http_referer: str = ""
    openrouter_app_name: str = "ai-postgen"
    image_provider: str = "infip"
    infip_base_url: str = "https://api.infip.pro/v1"
    infip_image_model: str = "img4"
    infip_image_response_format: str = "url"
    custom_image_base_url: str = ""
    custom_image_steps: int = 4
    custom_image_guidance: float = 0.0
    custom_image_n: int = 1
    custom_image_seed: int = 1
    image_size: str = "1024x1024"
    linkedin_image_size: str = "1200x1200"
    instagram_image_size: str = "1080x1350"
    facebook_image_size: str = "1200x630"
    outputs_dir: str = "./outputs"
    traces_file: str = "./outputs/traces/generation-traces.jsonl"
    google_credentials_json_path: str = ""
    google_auth_mode: str = "service_account"
    google_oauth_client_json_path: str = ""
    google_oauth_token_path: str = "oauth-token.json"
    google_sheets_auth_mode: str = ""
    google_drive_auth_mode: str = ""
    google_sheets_oauth_client_json_path: str = ""
    google_drive_oauth_client_json_path: str = ""
    google_sheets_oauth_token_path: str = "oauth-token-sheets.json"
    google_drive_oauth_token_path: str = "oauth-token-drive.json"
    google_spreadsheet_id: str = ""
    google_sheet_name: str = "Sheet1"
    google_drive_folder_id: str = ""
    default_company_logo_path: str = ""
    logo_input_mode: str = "overlay"
    headline_overlay_enabled: bool = True

    def image_size_for_platform(self, platform: str) -> str:
        platform_key = (platform or "").strip().lower()
        if platform_key == "linkedin":
            return self.linkedin_image_size
        if platform_key == "instagram":
            return self.instagram_image_size
        if platform_key == "facebook":
            return self.facebook_image_size
        return self.image_size


def get_settings() -> Settings:
    load_dotenv()

    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    text_provider = os.getenv("TEXT_PROVIDER", "openai").strip().lower() or "openai"
    caption_model = os.getenv("CAPTION_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip() or "https://api.openai.com/v1"
    openai_image_model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip() or "gpt-image-1"
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip() or "https://openrouter.ai/api/v1"
    openrouter_text_model = os.getenv("OPENROUTER_TEXT_MODEL", "openai/gpt-4o-mini").strip() or "openai/gpt-4o-mini"
    openrouter_image_model = os.getenv("OPENROUTER_IMAGE_MODEL", "openai/gpt-image-1").strip() or "openai/gpt-image-1"
    openrouter_http_referer = os.getenv("OPENROUTER_HTTP_REFERER", "").strip()
    openrouter_app_name = os.getenv("OPENROUTER_APP_NAME", "ai-postgen").strip() or "ai-postgen"

    image_provider = os.getenv("IMAGE_PROVIDER", "infip").strip().lower() or "infip"
    infip_api_key = os.getenv("INFIP_API_KEY", "").strip()

    port_value = os.getenv("PORT", "8000").strip() or "8000"
    port = int(port_value)
    timeout_value = os.getenv("REQUEST_TIMEOUT_SECONDS", "300").strip() or "300"
    request_timeout_seconds = int(timeout_value)

    if text_provider not in {"openai", "openrouter"}:
        raise RuntimeError("TEXT_PROVIDER must be either 'openai' or 'openrouter'.")
    if image_provider not in {"infip", "openai", "openrouter", "custom"}:
        raise RuntimeError("IMAGE_PROVIDER must be one of: infip, openai, openrouter, custom.")
    if text_provider == "openai" and not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to your environment or .env file.")
    if text_provider == "openrouter" and not openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is missing. Add it to your environment or .env file.")
    if image_provider == "openai" and not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to your environment or .env file.")
    if image_provider == "openrouter" and not openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is missing. Add it to your environment or .env file.")
    if image_provider == "infip" and not infip_api_key:
        raise RuntimeError("INFIP_API_KEY is missing. Add it to your environment or .env file.")

    infip_base_url = os.getenv("INFIP_BASE_URL", "https://api.infip.pro/v1").strip() or "https://api.infip.pro/v1"
    infip_image_model = os.getenv("INFIP_IMAGE_MODEL", "img4").strip() or "img4"
    infip_image_response_format = os.getenv("INFIP_IMAGE_RESPONSE_FORMAT", "url").strip().lower() or "url"
    custom_image_base_url = os.getenv("CUSTOM_IMAGE_BASE_URL", "").strip().rstrip("/")
    custom_image_steps = int(os.getenv("CUSTOM_IMAGE_STEPS", "4").strip() or "4")
    custom_image_guidance = float(os.getenv("CUSTOM_IMAGE_GUIDANCE", "0.0").strip() or "0.0")
    custom_image_n = int(os.getenv("CUSTOM_IMAGE_N", "1").strip() or "1")
    custom_image_seed = int(os.getenv("CUSTOM_IMAGE_SEED", "1").strip() or "1")
    image_size = os.getenv("IMAGE_SIZE", "1024x1024").strip() or "1024x1024"
    linkedin_image_size = os.getenv("LINKEDIN_IMAGE_SIZE", "1200x1200").strip() or "1200x1200"
    instagram_image_size = os.getenv("INSTAGRAM_IMAGE_SIZE", "1080x1350").strip() or "1080x1350"
    facebook_image_size = os.getenv("FACEBOOK_IMAGE_SIZE", "1200x630").strip() or "1200x630"
    traces_file = os.getenv("TRACES_FILE", "./outputs/traces/generation-traces.jsonl").strip() or "./outputs/traces/generation-traces.jsonl"
    google_credentials_json_path = os.getenv("GOOGLE_CREDENTIALS_JSON_PATH", "").strip()
    google_auth_mode = os.getenv("GOOGLE_AUTH_MODE", "service_account").strip().lower() or "service_account"
    google_oauth_client_json_path = os.getenv("GOOGLE_OAUTH_CLIENT_JSON_PATH", "").strip()
    google_oauth_token_path = os.getenv("GOOGLE_OAUTH_TOKEN_PATH", "oauth-token.json").strip() or "oauth-token.json"
    google_sheets_auth_mode = os.getenv("GOOGLE_SHEETS_AUTH_MODE", "").strip().lower()
    google_drive_auth_mode = os.getenv("GOOGLE_DRIVE_AUTH_MODE", "").strip().lower()
    google_sheets_oauth_client_json_path = os.getenv("GOOGLE_SHEETS_OAUTH_CLIENT_JSON_PATH", "").strip()
    google_drive_oauth_client_json_path = os.getenv("GOOGLE_DRIVE_OAUTH_CLIENT_JSON_PATH", "").strip()
    google_sheets_oauth_token_path = os.getenv("GOOGLE_SHEETS_OAUTH_TOKEN_PATH", "oauth-token-sheets.json").strip() or "oauth-token-sheets.json"
    google_drive_oauth_token_path = os.getenv("GOOGLE_DRIVE_OAUTH_TOKEN_PATH", "oauth-token-drive.json").strip() or "oauth-token-drive.json"
    google_spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID", "").strip()
    google_sheet_name = os.getenv("GOOGLE_SHEET_NAME", "Sheet1").strip() or "Sheet1"
    google_drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    default_company_logo_path = os.getenv("DEFAULT_COMPANY_LOGO_PATH", "").strip()
    logo_input_mode = os.getenv("LOGO_INPUT_MODE", "overlay").strip().lower() or "overlay"
    headline_overlay_enabled = (os.getenv("HEADLINE_OVERLAY_ENABLED", "true").strip().lower() or "true") in {"1", "true", "yes", "on"}

    if image_provider == "custom" and not custom_image_base_url:
        raise RuntimeError("CUSTOM_IMAGE_BASE_URL is missing. Add it to your environment or .env file.")
    if logo_input_mode not in {"overlay", "reference", "both"}:
        raise RuntimeError("LOGO_INPUT_MODE must be one of: overlay, reference, both.")

    return Settings(
        openai_api_key=openai_api_key,
        infip_api_key=infip_api_key,
        openrouter_api_key=openrouter_api_key,
        port=port,
        request_timeout_seconds=request_timeout_seconds,
        text_provider=text_provider,
        caption_model=caption_model,
        openai_base_url=openai_base_url.rstrip("/"),
        openai_image_model=openai_image_model,
        openrouter_base_url=openrouter_base_url.rstrip("/"),
        openrouter_text_model=openrouter_text_model,
        openrouter_image_model=openrouter_image_model,
        openrouter_http_referer=openrouter_http_referer,
        openrouter_app_name=openrouter_app_name,
        image_provider=image_provider,
        infip_base_url=infip_base_url.rstrip("/"),
        infip_image_model=infip_image_model,
        infip_image_response_format=infip_image_response_format,
        custom_image_base_url=custom_image_base_url,
        custom_image_steps=custom_image_steps,
        custom_image_guidance=custom_image_guidance,
        custom_image_n=custom_image_n,
        custom_image_seed=custom_image_seed,
        image_size=image_size,
        linkedin_image_size=linkedin_image_size,
        instagram_image_size=instagram_image_size,
        facebook_image_size=facebook_image_size,
        traces_file=traces_file,
        google_credentials_json_path=google_credentials_json_path,
        google_auth_mode=google_auth_mode,
        google_oauth_client_json_path=google_oauth_client_json_path,
        google_oauth_token_path=google_oauth_token_path,
        google_sheets_auth_mode=google_sheets_auth_mode,
        google_drive_auth_mode=google_drive_auth_mode,
        google_sheets_oauth_client_json_path=google_sheets_oauth_client_json_path,
        google_drive_oauth_client_json_path=google_drive_oauth_client_json_path,
        google_sheets_oauth_token_path=google_sheets_oauth_token_path,
        google_drive_oauth_token_path=google_drive_oauth_token_path,
        google_spreadsheet_id=google_spreadsheet_id,
        google_sheet_name=google_sheet_name,
        google_drive_folder_id=google_drive_folder_id,
        default_company_logo_path=default_company_logo_path,
        logo_input_mode=logo_input_mode,
        headline_overlay_enabled=headline_overlay_enabled,
    )
