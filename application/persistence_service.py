"""Orquestador de alto nivel.

Une `SupabaseEventRepository`, `SupabaseBinCommandPoller`,
`SupabaseEventWriter` y `BinCommandHandler` con los `ArduinoSerialBridge`
registrados por `station_id`. Es la fachada que usa `main.py`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from adapters.arduino_serial import ArduinoSerialBridge
from adapters.supabase_persistence import (
    SupabaseEventRepository,
    SupabaseManualOpeningRepository,
)
from adapters.supabase_poller import SupabaseBinCommandPoller
from application.bin_command_handler import BinCommandHandler, as_on_command
from application.event_writer import SupabaseEventWriter
from ports.realtime import BinCommand

if TYPE_CHECKING:
    from supabase import Client

_log = logging.getLogger("ras.application.service")


class PersistenceService:
    """Fachada que coordina Supabase + Arduino + writer async."""

    def __init__(
        self,
        supabase_client: "Client",
        fallback_dir: str,
    ) -> None:
        self._client = supabase_client
        self._detection_repo = SupabaseEventRepository(supabase_client)
        self._opening_repo = SupabaseManualOpeningRepository(supabase_client)
        self._writer = SupabaseEventWriter(self._detection_repo, fallback_dir)
        self._handler = BinCommandHandler(self._opening_repo)
        self._pollers: dict[str, SupabaseBinCommandPoller] = {}
        self._stations: dict[str, ArduinoSerialBridge] = {}
        self._started = False
        self._on_opened_hook: Callable[[BinCommand, int], None] | None = None
        self._on_error_hook: Callable[[BinCommand, str], None] | None = None

    # ---- Composición -------------------------------------------------

    def add_station(
        self,
        station_id: str,
        bridge: ArduinoSerialBridge,
    ) -> None:
        if not station_id:
            raise ValueError("station_id es obligatorio")
        if station_id in self._stations:
            raise ValueError(f"station_id {station_id!r} ya está registrado")
        self._stations[station_id] = bridge
        self._handler.register_bridge(station_id, bridge)
        poller = SupabaseBinCommandPoller(
            self._client, station_id, self._opening_repo
        )
        self._pollers[station_id] = poller
        _log.info("Estación registrada: %s", station_id)

    def on_opened(self, callback: Callable[[BinCommand, int], None]) -> None:
        self._on_opened_hook = callback

    def on_error(self, callback: Callable[[BinCommand, str], None]) -> None:
        self._on_error_hook = callback

    # ---- Ciclo de vida ----------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._writer.start()

        if self._on_opened_hook is not None:
            self._handler.on_opened(self._on_opened_hook)
        if self._on_error_hook is not None:
            self._handler.on_error(self._on_error_hook)

        for station_id, poller in self._pollers.items():
            _log.info("Iniciando poller de aperturas para %s", station_id)
            poller.start(as_on_command(self._handler))

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        for poller in self._pollers.values():
            poller.stop()
        self._writer.stop(drain=True, timeout_s=10.0)
        _log.info("PersistenceService detenido")

    # ---- API pública usada por main.py ------------------------------

    @property
    def writer(self) -> SupabaseEventWriter:
        return self._writer

    def queue_detection_event(self, event) -> None:
        self._writer.enqueue(event)
