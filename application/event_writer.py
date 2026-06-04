"""Writer asíncrono de detecciones: queue.Queue + worker thread.

El productor (hilo de YOLO / main thread) encola eventos en < 1 ms.
El consumidor (daemon thread) hace batch INSERT cada 1 s o cada 10
eventos. Si Supabase está caído, los eventos se persisten en
`var/detection_buffer.jsonl` y se reintentan al reconectar.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from collections.abc import Iterable
from pathlib import Path

from domain.detection_event import DetectionEvent
from ports.persistence import DetectionRepository

_log = logging.getLogger("ras.application.event_writer")

_BATCH_MAX_SIZE = 10
_BATCH_MAX_WAIT_S = 1.0
_QUEUE_MAX_SIZE = 1000
_FALLBACK_FILENAME = "detection_buffer.jsonl"


class SupabaseEventWriter:
    """Productor/consumidor desacoplado para `detections`."""

    def __init__(
        self,
        repository: DetectionRepository,
        fallback_dir: str | Path = "var",
        *,
        batch_max_size: int = _BATCH_MAX_SIZE,
        batch_max_wait_s: float = _BATCH_MAX_WAIT_S,
        queue_max_size: int = _QUEUE_MAX_SIZE,
    ) -> None:
        self._repo = repository
        self._fallback_dir = Path(fallback_dir)
        self._fallback_path = self._fallback_dir / _FALLBACK_FILENAME
        self._batch_max_size = batch_max_size
        self._batch_max_wait_s = batch_max_wait_s
        self._queue: queue.Queue[DetectionEvent] = queue.Queue(maxsize=queue_max_size)
        self._stop_event = threading.Event()
        self._dropped_counter = 0
        self._worker: threading.Thread | None = None

    def start(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._stop_event.clear()
        self._fallback_dir.mkdir(parents=True, exist_ok=True)
        self._worker = threading.Thread(
            target=self._run, name="supabase-event-writer", daemon=True
        )
        self._worker.start()
        _log.info("SupabaseEventWriter iniciado")

    def stop(self, *, drain: bool = False, timeout_s: float = 5.0) -> None:
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=timeout_s)
            self._worker = None
        if drain:
            self._flush_remaining()
        _log.info("SupabaseEventWriter detenido (dropped=%s)", self._dropped_counter)

    def enqueue(self, event: DetectionEvent) -> bool:
        """Productor: encola un evento. Devuelve False si la cola está llena."""
        try:
            self._queue.put_nowait(event)
            return True
        except queue.Full:
            self._dropped_counter += 1
            if self._dropped_counter % 50 == 1:
                _log.warning(
                    "Cola de detecciones llena — %s eventos descartados",
                    self._dropped_counter,
                )
            return False

    # ---- internals ----------------------------------------------------

    def _run(self) -> None:
        # Reintentar pendientes del archivo de fallback antes del loop normal.
        self._drain_fallback()
        while not self._stop_event.is_set():
            batch = self._collect_batch()
            if not batch:
                continue
            self._flush_batch(batch)

    def _collect_batch(self) -> list[DetectionEvent]:
        batch: list[DetectionEvent] = []
        deadline = time.monotonic() + self._batch_max_wait_s
        while len(batch) < self._batch_max_size:
            remaining = max(0.0, deadline - time.monotonic())
            if not batch and remaining > 0:
                try:
                    event = self._queue.get(timeout=remaining)
                except queue.Empty:
                    break
            else:
                try:
                    event = self._queue.get_nowait()
                except queue.Empty:
                    break
            batch.append(event)
        return batch

    def _flush_batch(self, batch: Iterable[DetectionEvent]) -> None:
        events = list(batch)
        try:
            self._repo.save_batch(events)
            return
        except Exception as exc:
            _log.warning(
                "INSERT batch falló (%s eventos): %s — guardando en fallback",
                len(events),
                exc,
            )
        self._append_to_fallback(events)

    def _append_to_fallback(self, events: list[DetectionEvent]) -> None:
        try:
            self._fallback_dir.mkdir(parents=True, exist_ok=True)
            with self._fallback_path.open("a", encoding="utf-8") as fh:
                for event in events:
                    fh.write(json.dumps(event.to_payload(), ensure_ascii=False) + "\n")
        except Exception as exc:
            _log.error("No se pudo escribir fallback: %s", exc)

    def _drain_fallback(self) -> None:
        if not self._fallback_path.exists():
            return
        try:
            with self._fallback_path.open("r", encoding="utf-8") as fh:
                lines = [line for line in fh if line.strip()]
        except Exception as exc:
            _log.error("No se pudo leer fallback: %s", exc)
            return
        if not lines:
            return
        _log.info("Recuperando %s eventos desde %s", len(lines), self._fallback_path)

        events: list[DetectionEvent] = []
        for line in lines:
            try:
                payload = json.loads(line)
                events.append(
                    DetectionEvent(
                        detected_class=payload["detected_class"],
                        confidence=float(payload["confidence"]),
                        category=payload.get("category"),
                        arduino_command=payload.get("arduino_command"),
                        processing_time_ms=payload.get("processing_time_ms"),
                        image_identifier=payload.get("image_identifier"),
                        source_type=payload.get("source_type", "yolo"),
                        station_id=payload.get("station_id"),
                        arduino_delivered=bool(payload.get("arduino_delivered", False)),
                    )
                )
            except Exception as exc:
                _log.warning("Línea inválida en fallback ignorada: %s (%s)", line, exc)
        if not events:
            return
        try:
            self._repo.save_batch(events)
            # Si tuvo éxito, truncar el archivo.
            self._fallback_path.write_text("", encoding="utf-8")
            _log.info("Recuperados %s eventos del fallback", len(events))
        except Exception as exc:
            _log.warning("Reintento de fallback falló: %s — se mantienen los datos", exc)

    def _flush_remaining(self) -> None:
        events: list[DetectionEvent] = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if events:
            self._flush_batch(events)
