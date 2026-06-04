"""Eventos de dominio: un `DetectionEvent` por cada clasificación del modelo."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

SourceType = Literal["yolo", "manual", "stub"]


@dataclass(frozen=True)
class DetectionEvent:
    """Snapshot inmutable de una detección de residuos.

    Mapea 1:1 con la fila de la tabla `detections` en Supabase (con la
    salvedad de que `id` lo asigna la base de datos al hacer INSERT).
    """

    detected_class: str
    confidence: float
    category: str | None = None
    arduino_command: str | None = None
    processing_time_ms: int | None = None
    image_identifier: str | None = None
    source_type: SourceType = "yolo"
    station_id: str | None = None
    arduino_delivered: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: uuid.UUID | None = None

    def to_payload(self) -> dict:
        """Convierte el evento al payload aceptado por la API de Supabase."""
        payload: dict = {
            "detected_class": self.detected_class,
            "confidence": round(float(self.confidence), 3),
            "source_type": self.source_type,
            "arduino_delivered": bool(self.arduino_delivered),
            "timestamp": self.timestamp.isoformat(),
        }
        if self.category is not None:
            payload["category"] = self.category
        if self.arduino_command is not None:
            payload["arduino_command"] = self.arduino_command
        if self.processing_time_ms is not None:
            payload["processing_time_ms"] = int(self.processing_time_ms)
        if self.image_identifier is not None:
            payload["image_identifier"] = self.image_identifier
        if self.station_id is not None:
            payload["station_id"] = self.station_id
        return payload
