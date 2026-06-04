"""Adaptadores de persistencia sobre Supabase (REST).

Estos adapters implementan los `Protocol`s definidos en `ports/`.
La capa de aplicación solo conoce los Protocols, no Supabase.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from domain.detection_event import DetectionEvent
from ports.persistence import DetectionRepository, ManualOpeningRepository

if TYPE_CHECKING:
    from supabase import Client

_log = logging.getLogger("ras.supabase.persistence")

_TABLE_DETECTIONS = "detections"
_TABLE_OPENINGS = "manual_bin_openings"


class SupabaseEventRepository(DetectionRepository):
    """INSERT en `detections` (vía REST `supabase-py`)."""

    def __init__(self, client: "Client") -> None:
        self._client = client

    def save(self, event: DetectionEvent) -> None:
        payload = event.to_payload()
        self._client.table(_TABLE_DETECTIONS).insert(payload).execute()

    def save_batch(self, events: list[DetectionEvent]) -> None:
        if not events:
            return
        payload = [event.to_payload() for event in events]
        self._client.table(_TABLE_DETECTIONS).insert(payload).execute()


class SupabaseManualOpeningRepository(ManualOpeningRepository):
    """UPDATE / SELECT sobre `manual_bin_openings`."""

    def __init__(self, client: "Client") -> None:
        self._client = client

    def mark_opened(self, opening_id: uuid.UUID, latency_ms: int) -> None:
        from datetime import datetime, timezone

        self._client.table(_TABLE_OPENINGS).update(
            {
                "status": "opened",
                "opened_at": datetime.now(timezone.utc).isoformat(),
                "latency_ms": int(latency_ms),
            }
        ).eq("id", str(opening_id)).execute()

    def mark_error(self, opening_id: uuid.UUID, error: str) -> None:
        self._client.table(_TABLE_OPENINGS).update(
            {
                "status": "error",
                "error_message": str(error)[:500],
            }
        ).eq("id", str(opening_id)).execute()

    def mark_timeout(self, opening_id: uuid.UUID) -> None:
        self._client.table(_TABLE_OPENINGS).update(
            {"status": "timeout"}
        ).eq("id", str(opening_id)).execute()

    def fetch_pending(
        self, station_id: str, max_age_minutes: int = 5
    ) -> list[dict]:
        from datetime import datetime, timedelta, timezone

        cutoff = (
            datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
        ).isoformat()

        result = (
            self._client.table(_TABLE_OPENINGS)
            .select("id, bin_type, station_id, client_request_id")
            .eq("station_id", station_id)
            .eq("status", "pending")
            .gte("requested_at", cutoff)
            .execute()
        )
        return list(result.data or [])
