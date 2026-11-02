from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    web_chat_password: SecretStr = Field(default=SecretStr(""), repr=False)
    app_env: str = "local"
    pilot_db_path: str = ""
    app_api_key: str = ""
    database_url: str = "postgresql+psycopg://leap:leap@localhost:5432/leap"
    redis_url: str = "redis://localhost:6379/0"
    groq_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    llm_provider: str = "disabled"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_timeout_seconds: float = 15
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
