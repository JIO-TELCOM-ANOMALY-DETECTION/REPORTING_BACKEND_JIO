from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=DEFAULT_ROOT / ".env", extra="ignore")

    reporting_app_name: str = "Telecom Reporting Backend"
    reporting_environment: str = "local"
    reporting_debug: bool = False
    reporting_host: str = "127.0.0.1"
    reporting_port: int = Field(default=8001, ge=1, le=65535)
    reporting_api_prefix: str = "/api/v1"
    ml_runs_root: Path = DEFAULT_ROOT / "ML_backend" / "runs"
    ml_registry_root: Path | None = None
    report_output_root: Path = DEFAULT_ROOT / "report_outputs"
    default_file_encoding: str = "utf-8"
    max_csv_preview_rows: int = Field(default=20, ge=0, le=500)
    cors_allowed_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )

    @field_validator("ml_runs_root", "report_output_root", "ml_registry_root", mode="before")
    @classmethod
    def normalize_path(cls, value: str | Path | None) -> Path | None:
        return None if value is None else Path(value).expanduser().resolve()

    @field_validator("reporting_api_prefix")
    @classmethod
    def prefix(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        return value if value.startswith("/") else f"/{value}"

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def origins(cls, value: object) -> tuple[str, ...]:
        if value is None or value == "":
            return ()
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = [item.strip() for item in value.split(",") if item.strip()]
        return tuple(str(item).strip() for item in value if str(item).strip())


settings = Settings()
