from pathlib import Path
from typing import Literal

from pydantic import (
    Field,
    SecretStr,
    field_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):

    app_name: str = "DishCare AI"
    app_env: Literal[
        "development", "test", "production"
    ] = "development"

    database_path: Path = Path("data/dishcare.db")

    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"

    access_token_expire_minutes: int = Field(
        default=60,
        ge=1,
        le=1440,
    )

    seed_demo_data: bool = False

    # AI configuration

    ai_enabled: bool = False

    gemini_api_key: SecretStr = SecretStr("")
    groq_api_key: SecretStr = SecretStr("")

    gemini_model: str = "gemini-3.1-flash-lite"
    groq_model: str = "openai/gpt-oss-20b"

    llm_timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=120,
    )

    voice_enabled: bool = False
    whisper_model: str = "base"
    piper_english_model: Path = Path("models/en_US-lessac-medium.onnx")
    piper_hindi_model: Path = Path("models/hi_IN-pratham-medium.onnx")
    metrics_key: SecretStr = SecretStr("")
    llm_prices_per_million: dict[str, tuple[float, float]] = Field(default_factory=dict)

    # RAG configuration

    embedding_model: str = (
        "sentence-transformers/"
        "paraphrase-multilingual-MiniLM-L12-v2"
    )

    qdrant_path: Path = Path("data/qdrant")
    rag_top_k: int = Field(default=3, ge=1, le=10)

    # Persistent memory

    checkpoint_path: Path = Path(
        "data/checkpoints.sqlite"
    )

    prompt_version: str = Field(
        default="v1",
        pattern=r"^v[0-9]+$",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("jwt_secret")
    @classmethod
    def validate_secret(
        cls,
        value: SecretStr,
    ) -> SecretStr:

        secret = value.get_secret_value()

        if (
            len(secret) < 32
            or secret.startswith("REPLACE_")
        ):
            raise ValueError(
                "JWT_SECRET must be a generated secret "
                "of at least 32 characters"
            )

        return value