"""Punto de entrada del sistema de reciclaje (Tkinter + YOLO + Arduino + Supabase).

Orquesta la cámara, el modelo YOLO, el bridge serial del Arduino y la
persistencia desacoplada en Supabase. La capa de aplicación vive en
`application/`; este archivo solo compone y cablea.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING

from adapters.arduino_serial import ArduinoSerialBridge
from adapters.scanning_tkinter import (
    BestDetection,
    TkinterYoloScanner,
    attach_yolo_scanner,
)
from adapters.ui_tkinter import RecyclingTkWindow
from application.persistence_service import PersistenceService
from config import Settings, get_settings
from domain.detection_event import DetectionEvent

if TYPE_CHECKING:
    from tkinter import Tk

_log = logging.getLogger("ras.main")


def _list_serial_ports() -> list[str]:
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [port.device for port in list_ports.comports()]


def _resolve_arduino_port(settings: Settings) -> str:
    if settings.serial_port.strip():
        return settings.serial_port.strip()

    available_ports = _list_serial_ports()
    if len(available_ports) == 1:
        port = available_ports[0]
        _log.info("Puerto serial autodetectado: %s", port)
        return port

    ports_text = ", ".join(available_ports) if available_ports else "ninguno"
    raise RuntimeError(
        "Configura el puerto del Arduino en .env (RAS_SERIAL_PORT). "
        f"Puertos detectados: {ports_text}"
    )


def _create_supabase_client(settings: Settings):
    if not settings.is_supabase_configured():
        _log.warning(
            "Supabase no configurado (RAS_SUPABASE_URL / RAS_SUPABASE_SERVICE_KEY). "
            "Las detecciones NO se persistirán."
        )
        return None
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError(
            "Falta el cliente supabase-py. Instala con: pip install -r requirements.txt"
        ) from exc
    return create_client(settings.supabase_url, settings.supabase_service_key)


def _build_send_to_arduino(
    *,
    arduino_bridge_provider: Callable[[], ArduinoSerialBridge | None],
    persistence: PersistenceService | None,
    station_id: str,
) -> Callable[[BestDetection | None], None]:
    """Devuelve el callback `on_complete` del scanner.

    Orden: Arduino primero (rápido, síncrono), Supabase después (encolado).
    """

    def send_to_arduino(best: BestDetection | None) -> None:
        arduino_bridge = arduino_bridge_provider()
        if arduino_bridge is None or best is None:
            return

        arduino_delivered = _try_send(arduino_bridge, best.arduino_command)
        if persistence is not None:
            persistence.queue_detection_event(
                DetectionEvent(
                    detected_class=best.model_class_name,
                    confidence=best.confidence_percent / 100.0,
                    category=best.display_category,
                    arduino_command=best.arduino_command,
                    processing_time_ms=best.processing_time_ms,
                    source_type="yolo",
                    station_id=station_id,
                    arduino_delivered=arduino_delivered,
                )
            )

    return send_to_arduino


def _try_send(arduino_bridge: ArduinoSerialBridge, command: str) -> bool:
    try:
        arduino_bridge.send_command(command)
        return True
    except Exception as exc:
        _log.exception("No se pudo enviar categoría al Arduino: %s", exc)
        return False


def _make_on_deposit_complete(
    root: Tk, window: RecyclingTkWindow, scanner: TkinterYoloScanner
) -> Callable[[], None]:
    def on_deposit_complete() -> None:
        def hide_window() -> None:
            _log.info("Depósito completo — ocultando ventana")
            scanner.clear_video()
            window.hide()

        root.after(0, hide_window)

    return on_deposit_complete


def _on_command_result(bin_type: str, status: str, error: str | None) -> None:
    _log.info(
        "Comando manual Arduino: bin=%s status=%s error=%s",
        bin_type,
        status,
        error,
    )


def _wire_persistence(
    persistence: PersistenceService | None,
    settings: Settings,
    arduino_bridge: ArduinoSerialBridge,
) -> None:
    if persistence is None:
        return
    persistence.add_station(settings.station_id, arduino_bridge)
    persistence.start()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = get_settings()
    serial_port = _resolve_arduino_port(settings)
    supabase_client = _create_supabase_client(settings)
    window = RecyclingTkWindow()

    persistence: PersistenceService | None = None
    if supabase_client is not None:
        persistence = PersistenceService(
            supabase_client=supabase_client,
            fallback_dir=settings.local_buffer_dir,
        )

    arduino_ref: dict[str, ArduinoSerialBridge | None] = {"bridge": None}

    def on_window_ready(app_window: RecyclingTkWindow) -> None:
        root = app_window.root

        def shutdown() -> None:
            if persistence is not None:
                persistence.stop()
            bridge = arduino_ref["bridge"]
            if bridge is not None:
                bridge.stop()

        scanner = attach_yolo_scanner(
            app_window,
            model_path=settings.yolo_model_path,
            device_index=settings.camera_device_index,
            display_width=app_window.scaled_video_max_width,
            yolo_device=settings.yolo_device,
            on_shutdown=shutdown,
        )

        send_to_arduino = _build_send_to_arduino(
            arduino_bridge_provider=lambda: arduino_ref["bridge"],
            persistence=persistence,
            station_id=settings.station_id,
        )

        on_deposit_complete = _make_on_deposit_complete(root, app_window, scanner)

        def on_arduino_detected() -> None:
            def run_scan_cycle() -> None:
                _log.info("Mostrando ventana y activando cámara")
                app_window.show()
                scanner.scan_once(on_complete=send_to_arduino)

            root.after(0, run_scan_cycle)

        arduino_bridge = ArduinoSerialBridge(
            port=serial_port,
            station_id=settings.station_id,
            baudrate=settings.serial_baudrate,
            timeout_s=settings.serial_timeout_s,
            on_detected=on_arduino_detected,
            on_deposit_complete=on_deposit_complete,
            on_command_result=_on_command_result,
        )
        arduino_bridge.start()
        arduino_ref["bridge"] = arduino_bridge

        _wire_persistence(persistence, settings, arduino_bridge)
        _log.info(
            "Sistema en espera — estación=%s, ventana oculta hasta DETECTED",
            settings.station_id,
        )

    window.run(on_ready=on_window_ready, start_hidden=True)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        _log.error("%s", exc)
        sys.exit(1)
