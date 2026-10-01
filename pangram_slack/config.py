import os
from typing import Self

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class Config(BaseModel):
    """Runtime configuration loaded from environment variables."""

    model_config = ConfigDict(hide_input_in_errors=True)

    allowed_user_ids: frozenset[str] = Field(min_length=1)
    pangram_api_key: SecretStr
    pangram_include_dashboard_link: bool
    pangram_model: str
    slack_app_token: SecretStr
    slack_bot_token: SecretStr

    @classmethod
    def default(cls) -> Self:
        """Load the default local configuration from the environment."""
        load_dotenv()
        allowed_user_ids = frozenset(
            user_id.strip()
            for user_id in _required_environment_variable("SLACK_ALLOWED_USER_IDS").split(
                ","
            )
            if user_id.strip()
        )
        return cls(
            allowed_user_ids=allowed_user_ids,
            pangram_api_key=_required_environment_variable("PANGRAM_API_KEY"),
            pangram_include_dashboard_link=_environment_flag(
                "PANGRAM_PUBLIC_DASHBOARD_LINK"
            ),
            pangram_model=os.getenv("PANGRAM_MODEL", "default"),
            slack_app_token=_required_environment_variable("SLACK_APP_TOKEN"),
            slack_bot_token=_required_environment_variable("SLACK_BOT_TOKEN"),
        )

    def is_user_allowed(self, user_id: str) -> bool:
        """Return whether a Slack user may invoke the app."""
        return user_id in self.allowed_user_ids

    @field_validator("pangram_model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Model must not be blank")
        return value.strip()

    @field_validator("pangram_api_key", "slack_app_token", "slack_bot_token")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("Credential must not be blank")
        return SecretStr(value.get_secret_value().strip())


def _environment_flag(name: str) -> bool:
    value = os.getenv(name, "false").strip().casefold()
    if value not in {"0", "1", "false", "true", "no", "yes"}:
        raise RuntimeError(f"Invalid boolean environment variable: {name}")
    return value in {"1", "true", "yes"}


def _required_environment_variable(name: str) -> str:
    value = os.getenv(name)
    if not value or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip()
