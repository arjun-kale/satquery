"""Environment-driven configuration for the local MVP backend."""

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings intentionally limited to Phase 0 infrastructure."""

    data_dir: Path = Path("./data")
    database_path: Path = Path("./data/satquery.db")
    # Real models by default (the demo path). "mock" is a developer fallback that returns
    # labelled placeholders without GPU cost; set SATQUERY_MODEL_MODE=mock to opt in.
    # "hf" calls the Hugging Face Inference Endpoint; "modal" the Modal worker.
    model_mode: Literal["mock", "local", "modal", "hf"] = "modal"
    cors_origins: str = "http://localhost:3000"

    # Hugging Face Inference Endpoint (model_mode="hf") and private asset repos for hosted runs.
    hf_endpoint_url: str | None = None
    hf_token: str | None = Field(None, validation_alias=AliasChoices("SATQUERY_HF_TOKEN", "HF_TOKEN"))
    # A scaled-to-zero endpoint answers 502/503 while it wakes; wait this long before giving up.
    hf_wait_s: int = 600
    hf_changeformer_repo: str | None = None  # e.g. arjun-kale/satquery-changeformer
    hf_samples_repo: str | None = None  # e.g. arjun-kale/satquery-samples (dataset)

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
