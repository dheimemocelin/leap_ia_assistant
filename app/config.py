from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    web_chat_password: SecretStr = Field(default=SecretStr(""), repr=False)
    evolution_enabled: bool = False
    evolution_send_enabled: bool = False
    evolution_typing_delay_ms: int = Field(default=0, ge=0, le=2000)
    evolution_url: str = "http://127.0.0.1:8081"
    evolution_instance: str = "leap-pilot"
    evolution_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    evolution_webhook_secret: SecretStr = Field(default=SecretStr(""), repr=False)
    evolution_identity_key: SecretStr = Field(default=SecretStr(""), repr=False)
    evolution_allowed_numbers: str = ""
    evolution_audio_enabled: bool = False
    audio_max_bytes: int = Field(default=2_000_000, gt=0, le=5_000_000)
    audio_max_seconds: int = Field(default=120, gt=0, le=300)
    stt_provider: str = "disabled"
    stt_model: str = "whisper-large-v3-turbo"
    stt_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    stt_timeout_seconds: float = Field(default=30, gt=0, le=60)
    stt_usd_per_audio_hour: float | None = Field(default=None, gt=0)
    app_env: str = "local"
    pilot_db_path: str = ""
    app_api_key: str = ""
    database_url: str = "postgresql+psycopg://leap:leap@localhost:5432/leap"
    redis_url: str = "redis://localhost:6379/0"
    groq_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    llm_provider: str = "disabled"
    lia_orchestration_enabled: bool = False
    lia_sales_focus_enabled: bool = False
    lia_showroom_name: str = ""
    lia_showroom_location: str = ""
    lia_showroom_landmarks: str = ""
    lia_showroom_hours: str = ""
    lia_knowledge_enabled: bool = False
    lia_knowledge_model_dir: str = ".local/knowledge-models/e5-small"
    lia_knowledge_cache_path: str = ".local/knowledge-runtime.sqlite3"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_timeout_seconds: float = 15
    llm_input_usd_per_million: float | None = Field(default=None, ge=0)
    llm_output_usd_per_million: float | None = Field(default=None, ge=0)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
