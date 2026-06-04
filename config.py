"""Configuración central del sistema (Pydantic v2, prefijo `RAS_`).

Reemplaza el antiguo `config.py` (compilado a .pyc) con un modelo único
y extensible. Lee del entorno o del archivo `.env` en la raíz del
proyecto (`recycling-automation-ai/.env`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Configuración con prefijo `RAS_` (Recycling Automation System)."""

    # --- Hardware ----------------------------------------------------
    serial_port: str = Field(
        default="",
        description="Puerto serial del Arduino (ej. COM3, /dev/ttyUSB0). Vacío = autodetectar.",
    )
    serial_baudrate: int = Field(default=9600, ge=1200, le=115_200)
    serial_timeout_s: float = Field(default=1.0, gt=0)

    # --- Cámara / modelo --------------------------------------------
    camera_device_index: int = Field(default=0, ge=0)
    yolo_model_path: str = Field(default="model/yolov8n-waste-12cls-best.pt")
    yolo_device: str | int | None = Field(
        default=None,
        description="None = autodetectar CUDA/CPU. Pasar 'cpu' o 0 para forzar.",
    )
    yolo_confidence: float = Field(default=0.35, ge=0.0, le=1.0)
    yolo_category_confidence: float = Field(default=0.45, ge=0.0, le=1.0)

    # --- Estación / Supabase ----------------------------------------
    station_id: str = Field(default="station-001")
    supabase_url: str = Field(default="")
    supabase_service_key: str = Field(default="")

    # --- Buffers locales --------------------------------------------
    local_buffer_dir: str = Field(default="var")

    model_config = SettingsConfigDict(
        env_prefix="RAS_",
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("yolo_device", mode="before")
    @classmethod
    def _empty_string_to_none(cls, value: Any) -> Any:
        """Convierte strings vacíos (de un .env con `RAS_YOLO_DEVICE=`) a None."""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    def is_supabase_configured(self) -> bool:
        return bool(self.supabase_url.strip() and self.supabase_service_key.strip())


_settings: Settings | None = None


def get_settings() -> Settings:
    """Singleton lazy de la configuración."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

