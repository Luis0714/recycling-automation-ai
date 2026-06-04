"""Handler para comandos de apertura de caneca recibidos vía Realtime.

Serializa por `station_id` para evitar que dos aperturas rápidas
interleaven en el puerto serial del Arduino.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from adapters.arduino_serial import ArduinoSerialBridge
from ports.persistence import ManualOpeningRepository
from ports.realtime import BinCommand, OnBinCommand

_log = logging.getLogger("ras.application.bin_command_handler")


@dataclass
class _StationBridges:
    bridge: ArduinoSerialBridge
    lock: threading.Lock


class BinCommandHandler:
    """Despacha `BinCommand` al Arduino correcto y actualiza la fila en Supabase."""

    def __init__(
        self,
        opening_repo: ManualOpeningRepository,
    ) -> None:
        self._opening_repo = opening_repo
        self._stations: dict[str, _StationBridges] = {}
        self._stations_lock = threading.Lock()
        self._on_opened: Callable[[BinCommand, int], None] | None = None
        self._on_error: Callable[[BinCommand, str], None] | None = None

    def register_bridge(self, station_id: str, bridge: ArduinoSerialBridge) -> None:
        if not station_id:
            raise ValueError("station_id es obligatorio para registrar un bridge")
        with self._stations_lock:
            self._stations[station_id] = _StationBridges(bridge=bridge, lock=threading.Lock())

    def on_opened(self, callback: Callable[[BinCommand, int], None]) -> None:
        self._on_opened = callback

    def on_error(self, callback: Callable[[BinCommand, str], None]) -> None:
        self._on_error = callback

    def handle(self, cmd: BinCommand) -> None:
        station_id = cmd.station_id or ""
        with self._stations_lock:
            entry = self._stations.get(station_id)

        if entry is None:
            msg = f"No hay bridge registrado para station_id={station_id!r}"
            _log.error(msg)
            self._mark_error(cmd, msg)
            return

        # Serializar aperturas para la misma estación.
        with entry.lock:
            self._execute(cmd, entry.bridge)

    def _execute(self, cmd: BinCommand, bridge: ArduinoSerialBridge) -> None:
        started = time.monotonic()
        try:
            bridge.request_open(cmd.bin_type)
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            _log.error(
                "Apertura manual FALLIDA (%s, station=%s, latency=%sms): %s",
                cmd.bin_type,
                cmd.station_id,
                latency_ms,
                exc,
            )
            self._mark_error(cmd, str(exc))
            if self._on_error is not None:
                try:
                    self._on_error(cmd, str(exc))
                except Exception as cb_exc:
                    _log.debug("on_error callback lanzó: %s", cb_exc)
            return

        latency_ms = int((time.monotonic() - started) * 1000)
        _log.info(
            "Apertura manual OK (%s, station=%s, latency=%sms, opening_id=%s)",
            cmd.bin_type,
            cmd.station_id,
            latency_ms,
            cmd.opening_id,
        )
        try:
            self._opening_repo.mark_opened(cmd.opening_id, latency_ms)
        except Exception as exc:
            _log.warning("No se pudo marcar la fila como opened: %s", exc)
        if self._on_opened is not None:
            try:
                self._on_opened(cmd, latency_ms)
            except Exception as cb_exc:
                _log.debug("on_opened callback lanzó: %s", cb_exc)

    def _mark_error(self, cmd: BinCommand, message: str) -> None:
        try:
            self._opening_repo.mark_error(cmd.opening_id, message)
        except Exception as exc:
            _log.warning("No se pudo marcar la fila como error: %s", exc)


# Alias para que `OnBinCommand` se use con la firma esperada por el subscriber.
def as_on_command(handler: BinCommandHandler) -> OnBinCommand:
    def _call(cmd: BinCommand) -> None:
        handler.handle(cmd)

    return _call
