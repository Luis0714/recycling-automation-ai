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
