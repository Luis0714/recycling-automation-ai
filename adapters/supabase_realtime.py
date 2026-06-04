"""Suscriptor Realtime a `manual_bin_openings` (postgres_changes).

Cuando el web app inserta una fila en esa tabla, este adapter recibe el
evento y lo traduce a un `BinCommand` que se entrega al handler.
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import TYPE_CHECKING

from ports.persistence import ManualOpeningRepository
from ports.realtime import BinCommand, OnBinCommand

if TYPE_CHECKING:
    from supabase import Client

_log = logging.getLogger("ras.supabase.realtime")

_TABLE_OPENINGS = "manual_bin_openings"


class SupabaseBinCommandSubscriber:
    """Suscripción a `INSERT` en `manual_bin_openings` filtrada por `station_id`."""

    def __init__(
        self,
        client: "Client",
        station_id: str,
        opening_repo: ManualOpeningRepository,
    ) -> None:
        self._client = client
        self._station_id = station_id
        self._opening_repo = opening_repo
        self._channel = None
        self._on_command: OnBinCommand | None = None
        self._lock = threading.Lock()

    def start(self, on_command: OnBinCommand) -> None:
        with self._lock:
            if self._channel is not None:
                _log.warning("BinCommandSubscriber ya estaba activo")
                return
            self._on_command = on_command

        # 1) Replay: procesar filas pendientes que llegaron mientras
        #    estábamos offline (ventana de 5 minutos).
        try:
            pending = self._opening_repo.fetch_pending(
                self._station_id, max_age_minutes=5
            )
            for row in pending:
                self._dispatch(row)
        except Exception as exc:
            _log.warning("Recuperación de pending falló: %s", exc)

        # 2) Suscripción a INSERTs nuevos.
        def _on_insert(payload) -> None:
            try:
                new = payload.get("new") if isinstance(payload, dict) else None
                if not new:
                    return
                # Filtro defensivo por si Realtime publica filas de otras estaciones.
                if new.get("station_id") and new["station_id"] != self._station_id:
                    return
                self._dispatch(new)
            except Exception as exc:
                _log.error("Error procesando INSERT Realtime: %s", exc)

        try:
            self._channel = (
                self._client.realtime.channel(f"mbo-{self._station_id}")
                .on(
                    "postgres_changes",
                    event="INSERT",
                    schema="public",
                    table=_TABLE_OPENINGS,
                    filter=f"station_id=eq.{self._station_id}",
                    callback=_on_insert,
                )
                .subscribe()
            )
            _log.info("Suscrito a Realtime en %s", _TABLE_OPENINGS)
        except Exception as exc:
            _log.error("No se pudo suscribir a Realtime: %s", exc)
            self._channel = None

    def stop(self) -> None:
        with self._lock:
            if self._channel is not None:
                try:
                    self._client.remove_channel(self._channel)
                except Exception as exc:
                    _log.warning("Error cerrando canal Realtime: %s", exc)
                self._channel = None
            self._on_command = None

    def _dispatch(self, row: dict) -> None:
        try:
            cmd = BinCommand(
                opening_id=uuid.UUID(str(row["id"])),
                bin_type=str(row["bin_type"]),
                station_id=row.get("station_id"),
                client_request_id=row.get("client_request_id"),
            )
        except Exception as exc:
            _log.error("Fila inválida desde Realtime: %s (%s)", row, exc)
            return

        callback = self._on_command
        if callback is None:
            return
        try:
            callback(cmd)
        except Exception as exc:
            _log.error("Handler de BinCommand lanzó excepción: %s", exc)
