"""Protocolos (puertos) de persistencia.

Estos contratos permiten reemplazar Supabase por otro backend (tests
con SQLite, Postgres local, etc.) sin tocar la lógica de aplicación.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from domain.detection_event import DetectionEvent


class DetectionRepository(Protocol):
    """Persiste detecciones de residuos."""

    def save(self, event: DetectionEvent) -> None:
        """Inserta un `DetectionEvent`. Puede ser síncrono o encolar async."""
        ...

    def save_batch(self, events: list[DetectionEvent]) -> None:
        """Inserta varios eventos en una sola operación."""
        ...


class ManualOpeningRepository(Protocol):
    """Gestiona filas de `manual_bin_openings` desde el lado servidor."""

    def mark_opened(self, opening_id: uuid.UUID, latency_ms: int) -> None:
        """Marca la fila como abierta con éxito."""
        ...

    def mark_error(self, opening_id: uuid.UUID, error: str) -> None:
        """Marca la fila como fallida con un mensaje."""
        ...

    def mark_timeout(self, opening_id: uuid.UUID) -> None:
        """Marca la fila como timed-out (expirada sin acción)."""
        ...

    def fetch_pending(
        self, station_id: str, max_age_minutes: int = 5
    ) -> list[dict]:
        """Recupera filas en `pending` para la estación dada, dentro de la ventana de tiempo."""
        ...
