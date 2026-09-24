"""Environment-driven configuration for the local MVP backend."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings intentionally limited to Phase 0 infrastructure."""

    data_dir: Path = Path("./data")
    database_path: Path = Path("./data/satquery.db")
    # Real models by default (the demo path). "mock" is a developer fallback that returns
    # labelled placeholders without GPU cost; set SATQUERY_MODEL_MODE=mock to opt in.
    model_mode: Literal["mock", "local", "modal"] = "modal"
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SATQUERY_",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        """Return trimmed origin values without accepting an implicit wildcard."""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
