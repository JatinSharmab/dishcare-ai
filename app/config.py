from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DishCare AI"
    app_env: Literal["development", "test", "production"] = "development"

    database_path: Path = Path("data/dishcare.db")

    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(
        default=60,
        ge=1,
        le=1440,
    )

    seed_demo_data: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("jwt_secret")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()

        if len(secret) < 32 or secret.startswith("REPLACE_"):
            raise ValueError(
                "JWT_SECRET must be a generated secret "
                "of at least 32 characters"
            )

        return value