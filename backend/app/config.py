from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Infrastructure
    database_url: str = "sqlite:///./partingpal.db"
    frontend_origin: str = "http://localhost:5173"
    public_base_url: str = "http://localhost:5173"  # used to build interview links
    company_name: str = "our company"
    log_level: str = "INFO"

    # LLM providers. The first model in each list is that provider's default.
    default_provider: str = "gemini"
    openai_api_key: str | None = None
    openai_models: str = "gpt-4.1-mini,gpt-4.1"
    openai_transcription_model: str = "whisper-1"
    gemini_api_key: str | None = None
    gemini_models: str = "gemini-2.5-flash,gemini-2.5-pro"
    # Any OpenAI-compatible server: Ollama (http://localhost:11434/v1), vLLM, LM Studio, DashScope...
    oss_base_url: str | None = None
    oss_api_key: str = "not-needed"
    oss_models: str = "qwen2.5:7b-instruct"
    # openai | gemini; when unset the first configured one is used
    transcription_provider: str | None = None

    # Interview flow
    max_user_turns: int = 20
    max_followups_per_topic: int = 1
    max_message_chars: int = 4000
    max_audio_bytes: int = 10_000_000
    link_valid_days: int = 14

    # Admin (HR) authentication
    google_client_id: str | None = None
    admin_allowed_emails: str = ""
    admin_allowed_domains: str = ""
    auth_disabled: bool = False  # local development only, never in production

    # Optional SMTP for sending invitation emails
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

    @property
    def allowed_emails(self) -> set[str]:
        return {e.lower() for e in _split(self.admin_allowed_emails)}

    @property
    def allowed_domains(self) -> set[str]:
        return {d.lower().lstrip("@") for d in _split(self.admin_allowed_domains)}

    def models_for(self, provider: str) -> list[str]:
        return _split({"openai": self.openai_models, "gemini": self.gemini_models, "oss": self.oss_models}.get(provider, ""))


@lru_cache
def get_settings() -> Settings:
    return Settings()
