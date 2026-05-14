from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class WasteCategory(StrEnum):
    PLASTIC = "plastic"
    METAL = "metal"
    ORGANIC = "organic"
    UNKNOWN = "unknown"


class ClassificationOutput(BaseModel):
    category: WasteCategory
    confidence: float = Field(ge=0.0, le=1.0)
    raw_label: str | None = None
    bbox_xyxy: tuple[float, float, float, float] | None = Field(
        default=None,
        description="Caja delimitadora en pixeles (x1, y1, x2, y2) en la imagen capturada.",
    )


class CycleResult(BaseModel):
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    classification: ClassificationOutput
    command_sent: str
