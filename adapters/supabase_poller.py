"""Polling de aperturas manuales (alternativa sync a Supabase Realtime).

Supabase-py v2 con `create_client()` retorna un cliente **sync**, y el
módulo Realtime del SDK solo funciona con el cliente **async**. Para no
refactorizar todo a asyncio, usamos polling sobre la tabla
`manual_bin_openings`: cada N segundos consultamos las filas en
`status='pending'` y las despachamos al handler. La latencia extra
(2 s por defecto) es trivial comparada con el tiempo de apertura de un
servo, y la web ya tiene un timeout de 10 s.
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

_log = logging.getLogger("ras.supabase.poller")


class SupabaseBinCommandPoller:
    """Sustituto sync de `SupabaseBinCommandSubscriber`."""

    def __init__(
        self,
        client: "Client",
        station_id: str,
        opening_repo: ManualOpeningRepository,
        *,
        poll_interval_s: float = 2.0,
        max_pending_minutes: int = 5,
    ) -> None:
        self._client = client
        self._station_id = station_id
        self._opening_repo = opening_repo
        self._poll_interval_s = max(0.5, poll_interval_s)
        self._max_pending_minutes = max_pending_minutes
        self._on_command: OnBinCommand | None = None
        self._seen_ids: set[str] = set()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, on_command: OnBinCommand) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._on_command = on_command
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="bin-poller", daemon=True
        )
        self._thread.start()
        _log.info(
            "Poller de aperturas manuales iniciado (cada %.1fs, ventana=%dmin)",
            self._poll_interval_s,
            self._max_pending_minutes,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        self._on_command = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception as exc:
                _log.warning("Error en el poll de aperturas: %s", exc)
            # wait() devuelve True si se seteó el evento; usamos esto
            # en vez de sleep() para que `stop()` sea casi instantáneo.
            if self._stop_event.wait(self._poll_interval_s):
                break

    def _poll_once(self) -> None:
        rows = self._opening_repo.fetch_pending(
            self._station_id, max_age_minutes=self._max_pending_minutes
        )
        if not rows:
            return
        new_rows = [r for r in rows if str(r.get("id", "")) not in self._seen_ids]
        if not new_rows:
            return
        _log.info("Poll encontró %d apertura(s) pendiente(s)", len(new_rows))
        for row in new_rows:
            row_id = str(row.get("id", ""))
            if row_id:
                self._seen_ids.add(row_id)
            self._dispatch(row)

    def _dispatch(self, row: dict) -> None:
        callback = self._on_command
        if callback is None:
            return
        try:
            cmd = BinCommand(
                opening_id=uuid.UUID(str(row["id"])),
                bin_type=str(row["bin_type"]),
                station_id=row.get("station_id"),
                client_request_id=row.get("client_request_id"),
            )
        except Exception as exc:
            _log.error("Fila inválida del poller: %s (%s)", row, exc)
            return
        try:
            callback(cmd)
        except Exception as exc:
            _log.error("Handler lanzó excepción en poller: %s", exc)
