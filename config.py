from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from domain.models import WasteCategory


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RAS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    run_mode: Literal["simulation", "hardware"] = "simulation"
    stub_waste_category: WasteCategory = Field(default=WasteCategory.PLASTIC)
    simulated_image_fixture_path: Path | None = None
    simulated_sensor_prompt: str = Field(
        default="Objeto simulado: pulse ENTER para disparar la captura. "
    )
    camera_device_index: int = Field(default=0, ge=0)
    camera_jpeg_quality: int = Field(default=85, ge=1, le=100)
    camera_preview_enabled: bool = True
    camera_preview_result_ms: int = Field(default=3500, ge=0, le=60000)
    camera_placement_preview_ms: int = Field(
        default=5000,
        ge=0,
        le=120000,
        description="Tiempo en vivo para colocar el objeto antes de capturar (0 = desactivado).",
    )
    serial_port: str | None = None
    serial_baudrate: int = Field(default=115200, ge=1)
    serial_timeout_s: float = Field(default=0.5, gt=0, le=30)
    serial_object_line: str = "OBJECT_DETECTED"
    classifier_backend: Literal["stub", "yolo"] = "stub"
    yolo_model_path: str = "yolov8n.pt"
    yolo_confidence: float = Field(default=0.35, ge=0.0, le=1.0)
