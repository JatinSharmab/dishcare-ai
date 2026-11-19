from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class ReliabilitySettings(BaseSettings):

    rate_limit_per_minute: int = Field(
        default=120,
        ge=1,
    )

    login_limit_per_minute: int = Field(
        default=10,
        ge=1,
    )

    upstream_timeout_seconds: float = Field(
        default=1,
        gt=0,
        le=60,
    )

    circuit_failure_threshold: int = Field(
        default=3,
        ge=1,
    )

    circuit_reset_seconds: float = Field(
        default=15,
        gt=0,
    )

    internal_service_key: SecretStr = SecretStr("")

    technician_failure_mode: Literal[
        "none",
        "timeout_after_commit",
        "always_fail",
    ] = "none"

    payment_webhook_secret: SecretStr = SecretStr("")

    whatsapp_enabled: bool = False
    whatsapp_app_secret: SecretStr = SecretStr("")
    whatsapp_verify_token: SecretStr = SecretStr("")
    whatsapp_access_token: SecretStr = SecretStr("")
    whatsapp_phone_id: str = Field(default="", pattern=r"^[0-9]*$")
    whatsapp_api_version: str = Field(default="v23.0", pattern=r"^v[0-9]+\.[0-9]+$")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )