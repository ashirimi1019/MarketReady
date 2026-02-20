from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    s3_presign_expiry_seconds: int = 900
    admin_token: str | None = None
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    ai_enabled: bool = False
    llm_provider: str = "groq"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    groq_api_base: str = "https://api.groq.com/openai/v1"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    openai_api_base: str = "https://api.openai.com/v1"
    openai_finetune_base_model: str = "gpt-4.1-nano-2025-04-14"
    local_upload_dir: str = "uploads"
    ai_proof_verify_threshold: float = 0.8
    auth_secret: str = "change-me-auth-secret"
    auth_token_ttl_seconds: int = 43200
    auth_refresh_token_ttl_seconds: int = 60 * 60 * 24 * 30
    auth_email_code_ttl_seconds: int = 60 * 30
    auth_password_reset_ttl_seconds: int = 60 * 20
    auth_login_max_attempts: int = 8
    auth_login_window_seconds: int = 60 * 10
    auth_dev_return_codes: bool = True
    auth_require_email_verification: bool = False
    public_app_base_url: str = "http://127.0.0.1:3000"
    mail_enabled: bool = False
    mail_from: str | None = None
    mail_provider_order: str = "smtp,resend,ses"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: int = 20
    resend_api_key: str | None = None
    resend_api_base: str = "https://api.resend.com"
    ses_region: str | None = None
    ses_access_key_id: str | None = None
    ses_secret_access_key: str | None = None
    ses_session_token: str | None = None
    ses_configuration_set: str | None = None
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    adzuna_country: str = "us"
    onet_username: str | None = None
    onet_password: str | None = None
    careeronestop_api_key: str | None = None
    careeronestop_user_id: str | None = None

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Render/Postgres providers often expose postgres:// URLs.
        if isinstance(value, str) and value.startswith("postgres://"):
            return "postgresql://" + value[len("postgres://"):]
        return value

settings = Settings()
