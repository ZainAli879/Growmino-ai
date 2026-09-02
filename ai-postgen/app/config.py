from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    environment: str = "development"
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    port: int = 8000
    request_timeout_seconds: int = 300
    text_provider: str = "openai"
    caption_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_image_model: str = "gpt-image-2"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_text_model: str = "openai/gpt-4o-mini"
    openrouter_image_model: str = "openai/gpt-image-1"
    openrouter_http_referer: str = ""
    openrouter_app_name: str = "ai-postgen"
    image_provider: str = "openai"
    image_size: str = "1024x1024"
    linkedin_image_size: str = "1200x1200"
    instagram_image_size: str = "1080x1350"
    facebook_image_size: str = "1200x630"
    outputs_dir: str = "./outputs"
    traces_file: str = "./outputs/traces/generation-traces.jsonl"
    default_company_logo_path: str = ""
    logo_input_mode: str = "overlay"
    meta_graph_api_version: str = "v25.0"
    meta_access_token: str = ""
    facebook_page_id: str = ""
    facebook_access_token: str = ""
    instagram_business_account_id: str = ""
    instagram_access_token: str = ""
    api_auth_required: bool = False
    growmino_jwt_secret: str = ""
    allow_dev_auth_headers: bool = True
    auth_dev_user_id: str = "local-user"
    auth_dev_business_id: str = "local-business"
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_uri: str = "http://localhost:8000/api/v1/integrations/linkedin/callback"
    linkedin_frontend_success_url: str = "http://localhost:8000/test-ui?linkedin=connected"
    linkedin_frontend_error_url: str = "http://localhost:8000/test-ui?linkedin=error"
    linkedin_oauth_state_ttl_seconds: int = 600
    token_encryption_key: str = ""
    linkedin_max_image_bytes: int = 5_000_000
    linkedin_request_timeout_seconds: int = 30
    linkedin_user_agent: str = "GrowMino-AI/1.0"
    linkedin_store_file: str = "./outputs/linkedin_store.json"
    linkedin_rest_version: str = "202608"
    public_base_url: str = ""
    social_max_image_bytes: int = 10_000_000
    cors_allow_origins: tuple[str, ...] = ()
    expose_test_ui: bool = True
    expose_api_docs: bool = True
    expose_outputs: bool = False
    api_max_body_bytes: int = 25_000_000
    api_rate_limit_enabled: bool = True
    api_rate_limit_requests: int = 120
    api_rate_limit_window_seconds: int = 60
    api_generation_rate_limit_requests: int = 10
    api_generation_rate_limit_window_seconds: int = 3600
    api_publish_rate_limit_requests: int = 60
    api_publish_rate_limit_window_seconds: int = 60
    secure_hsts_enabled: bool = False

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

    environment = os.getenv("ENVIRONMENT", "development").strip().lower() or "development"
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    text_provider = os.getenv("TEXT_PROVIDER", "openai").strip().lower() or "openai"
    caption_model = os.getenv("CAPTION_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip() or "https://api.openai.com/v1"
    openai_image_model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2").strip() or "gpt-image-2"
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip() or "https://openrouter.ai/api/v1"
    openrouter_text_model = os.getenv("OPENROUTER_TEXT_MODEL", "openai/gpt-4o-mini").strip() or "openai/gpt-4o-mini"
    openrouter_image_model = os.getenv("OPENROUTER_IMAGE_MODEL", "openai/gpt-image-1").strip() or "openai/gpt-image-1"
    openrouter_http_referer = os.getenv("OPENROUTER_HTTP_REFERER", "").strip()
    openrouter_app_name = os.getenv("OPENROUTER_APP_NAME", "ai-postgen").strip() or "ai-postgen"

    image_provider = os.getenv("IMAGE_PROVIDER", "openai").strip().lower() or "openai"

    port_value = os.getenv("PORT", "8000").strip() or "8000"
    port = int(port_value)
    timeout_value = os.getenv("REQUEST_TIMEOUT_SECONDS", "300").strip() or "300"
    request_timeout_seconds = int(timeout_value)

    if text_provider not in {"openai", "openrouter"}:
        raise RuntimeError("TEXT_PROVIDER must be either 'openai' or 'openrouter'.")
    if image_provider not in {"openai", "openrouter"}:
        raise RuntimeError("IMAGE_PROVIDER must be either 'openai' or 'openrouter'.")
    if text_provider == "openai" and not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to your environment or .env file.")
    if text_provider == "openrouter" and not openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is missing. Add it to your environment or .env file.")
    if image_provider == "openai" and not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to your environment or .env file.")
    if image_provider == "openrouter" and not openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is missing. Add it to your environment or .env file.")
    image_size = os.getenv("IMAGE_SIZE", "1024x1024").strip() or "1024x1024"
    linkedin_image_size = os.getenv("LINKEDIN_IMAGE_SIZE", "1200x1200").strip() or "1200x1200"
    instagram_image_size = os.getenv("INSTAGRAM_IMAGE_SIZE", "1080x1350").strip() or "1080x1350"
    facebook_image_size = os.getenv("FACEBOOK_IMAGE_SIZE", "1200x630").strip() or "1200x630"
    outputs_dir = os.getenv("OUTPUTS_DIR", "./outputs").strip() or "./outputs"
    traces_file = os.getenv("TRACES_FILE", "./outputs/traces/generation-traces.jsonl").strip() or "./outputs/traces/generation-traces.jsonl"
    default_company_logo_path = os.getenv("DEFAULT_COMPANY_LOGO_PATH", "").strip()
    logo_input_mode = os.getenv("LOGO_INPUT_MODE", "overlay").strip().lower() or "overlay"
    meta_graph_api_version = os.getenv("META_GRAPH_API_VERSION", "v25.0").strip() or "v25.0"
    meta_access_token = os.getenv("META_ACCESS_TOKEN", "").strip()
    facebook_page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip()
    facebook_access_token = os.getenv("FACEBOOK_ACCESS_TOKEN", "").strip()
    instagram_business_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip()
    instagram_access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    api_auth_required = os.getenv("API_AUTH_REQUIRED", "false").strip().lower() in {"1", "true", "yes", "on"}
    growmino_jwt_secret = os.getenv("GROWMINO_JWT_SECRET", "").strip()
    allow_dev_auth_headers_value = os.getenv("ALLOW_DEV_AUTH_HEADERS", "").strip().lower()
    allow_dev_auth_headers = (
        allow_dev_auth_headers_value in {"1", "true", "yes", "on"}
        if allow_dev_auth_headers_value
        else environment != "production"
    )
    auth_dev_user_id = os.getenv("AUTH_DEV_USER_ID", "local-user").strip() or "local-user"
    auth_dev_business_id = os.getenv("AUTH_DEV_BUSINESS_ID", "local-business").strip() or "local-business"
    linkedin_client_id = os.getenv("LINKEDIN_CLIENT_ID", "").strip()
    linkedin_client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "").strip()
    linkedin_redirect_uri = (
        os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8000/api/v1/integrations/linkedin/callback").strip()
        or "http://localhost:8000/api/v1/integrations/linkedin/callback"
    )
    linkedin_frontend_success_url = (
        os.getenv("LINKEDIN_FRONTEND_SUCCESS_URL", "http://localhost:8000/test-ui?linkedin=connected").strip()
        or "http://localhost:8000/test-ui?linkedin=connected"
    )
    linkedin_frontend_error_url = (
        os.getenv("LINKEDIN_FRONTEND_ERROR_URL", "http://localhost:8000/test-ui?linkedin=error").strip()
        or "http://localhost:8000/test-ui?linkedin=error"
    )
    linkedin_oauth_state_ttl_seconds = int(os.getenv("LINKEDIN_OAUTH_STATE_TTL_SECONDS", "600").strip() or "600")
    token_encryption_key = os.getenv("TOKEN_ENCRYPTION_KEY", "").strip()
    linkedin_max_image_bytes = int(os.getenv("LINKEDIN_MAX_IMAGE_BYTES", "5000000").strip() or "5000000")
    linkedin_request_timeout_seconds = int(os.getenv("LINKEDIN_REQUEST_TIMEOUT_SECONDS", "30").strip() or "30")
    linkedin_user_agent = os.getenv("LINKEDIN_USER_AGENT", "GrowMino-AI/1.0").strip() or "GrowMino-AI/1.0"
    linkedin_store_file = os.getenv("LINKEDIN_STORE_FILE", "./outputs/linkedin_store.json").strip() or "./outputs/linkedin_store.json"
    linkedin_rest_version = os.getenv("LINKEDIN_REST_VERSION", "202608").strip() or "202608"
    public_base_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    social_max_image_bytes = int(os.getenv("SOCIAL_MAX_IMAGE_BYTES", "10000000").strip() or "10000000")
    expose_test_ui_value = os.getenv("EXPOSE_TEST_UI", "").strip().lower()
    expose_test_ui = (
        expose_test_ui_value in {"1", "true", "yes", "on"}
        if expose_test_ui_value
        else environment != "production"
    )
    expose_api_docs_value = os.getenv("EXPOSE_API_DOCS", "").strip().lower()
    expose_api_docs = (
        expose_api_docs_value in {"1", "true", "yes", "on"}
        if expose_api_docs_value
        else environment != "production"
    )
    expose_outputs = os.getenv("EXPOSE_OUTPUTS", "false").strip().lower() in {"1", "true", "yes", "on"}
    api_max_body_bytes = int(os.getenv("API_MAX_BODY_BYTES", "25000000").strip() or "25000000")
    api_rate_limit_enabled = os.getenv("API_RATE_LIMIT_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
    api_rate_limit_requests = int(os.getenv("API_RATE_LIMIT_REQUESTS", "120").strip() or "120")
    api_rate_limit_window_seconds = int(os.getenv("API_RATE_LIMIT_WINDOW_SECONDS", "60").strip() or "60")
    api_generation_rate_limit_requests = int(os.getenv("API_GENERATION_RATE_LIMIT_REQUESTS", "10").strip() or "10")
    api_generation_rate_limit_window_seconds = int(os.getenv("API_GENERATION_RATE_LIMIT_WINDOW_SECONDS", "3600").strip() or "3600")
    api_publish_rate_limit_requests = int(os.getenv("API_PUBLISH_RATE_LIMIT_REQUESTS", "60").strip() or "60")
    api_publish_rate_limit_window_seconds = int(os.getenv("API_PUBLISH_RATE_LIMIT_WINDOW_SECONDS", "60").strip() or "60")
    secure_hsts_enabled = os.getenv("SECURE_HSTS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    raw_cors_allow_origins = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "",
    ).strip()
    cors_allow_origins = tuple(origin.strip() for origin in raw_cors_allow_origins.split(",") if origin.strip())
    if logo_input_mode not in {"overlay", "reference", "both"}:
        raise RuntimeError("LOGO_INPUT_MODE must be one of: overlay, reference, both.")
    if environment == "production":
        if not api_auth_required:
            raise RuntimeError("API_AUTH_REQUIRED must be true in production.")
        if allow_dev_auth_headers:
            raise RuntimeError("ALLOW_DEV_AUTH_HEADERS must be false in production.")
        if len(growmino_jwt_secret) < 32:
            raise RuntimeError("GROWMINO_JWT_SECRET must be at least 32 characters in production.")
        if not cors_allow_origins:
            raise RuntimeError("CORS_ALLOW_ORIGINS must include explicit frontend origins in production.")
        if public_base_url and not public_base_url.startswith("https://"):
            raise RuntimeError("PUBLIC_BASE_URL must use HTTPS in production.")
        if expose_outputs:
            raise RuntimeError("EXPOSE_OUTPUTS must be false in production.")
        if linkedin_client_id or linkedin_client_secret:
            if not linkedin_client_id or not linkedin_client_secret or not token_encryption_key:
                raise RuntimeError("LinkedIn production configuration requires client id, client secret, and TOKEN_ENCRYPTION_KEY.")
            if not linkedin_redirect_uri.startswith("https://"):
                raise RuntimeError("LINKEDIN_REDIRECT_URI must use HTTPS in production.")

    return Settings(
        environment=environment,
        openai_api_key=openai_api_key,
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
        image_size=image_size,
        linkedin_image_size=linkedin_image_size,
        instagram_image_size=instagram_image_size,
        facebook_image_size=facebook_image_size,
        outputs_dir=outputs_dir,
        traces_file=traces_file,
        default_company_logo_path=default_company_logo_path,
        logo_input_mode=logo_input_mode,
        meta_graph_api_version=meta_graph_api_version,
        meta_access_token=meta_access_token,
        facebook_page_id=facebook_page_id,
        facebook_access_token=facebook_access_token,
        instagram_business_account_id=instagram_business_account_id,
        instagram_access_token=instagram_access_token,
        api_auth_required=api_auth_required,
        growmino_jwt_secret=growmino_jwt_secret,
        allow_dev_auth_headers=allow_dev_auth_headers,
        auth_dev_user_id=auth_dev_user_id,
        auth_dev_business_id=auth_dev_business_id,
        linkedin_client_id=linkedin_client_id,
        linkedin_client_secret=linkedin_client_secret,
        linkedin_redirect_uri=linkedin_redirect_uri,
        linkedin_frontend_success_url=linkedin_frontend_success_url,
        linkedin_frontend_error_url=linkedin_frontend_error_url,
        linkedin_oauth_state_ttl_seconds=linkedin_oauth_state_ttl_seconds,
        token_encryption_key=token_encryption_key,
        linkedin_max_image_bytes=linkedin_max_image_bytes,
        linkedin_request_timeout_seconds=linkedin_request_timeout_seconds,
        linkedin_user_agent=linkedin_user_agent,
        linkedin_store_file=linkedin_store_file,
        linkedin_rest_version=linkedin_rest_version,
        public_base_url=public_base_url,
        social_max_image_bytes=social_max_image_bytes,
        cors_allow_origins=cors_allow_origins,
        expose_test_ui=expose_test_ui,
        expose_api_docs=expose_api_docs,
        expose_outputs=expose_outputs,
        api_max_body_bytes=api_max_body_bytes,
        api_rate_limit_enabled=api_rate_limit_enabled,
        api_rate_limit_requests=api_rate_limit_requests,
        api_rate_limit_window_seconds=api_rate_limit_window_seconds,
        api_generation_rate_limit_requests=api_generation_rate_limit_requests,
        api_generation_rate_limit_window_seconds=api_generation_rate_limit_window_seconds,
        api_publish_rate_limit_requests=api_publish_rate_limit_requests,
        api_publish_rate_limit_window_seconds=api_publish_rate_limit_window_seconds,
        secure_hsts_enabled=secure_hsts_enabled,
    )
