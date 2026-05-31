import logging
import os
import sys
from collections.abc import Callable

from adapters.arduino_serial import ArduinoSerialBridge
from adapters.scanning_tkinter import TkinterYoloScanner, attach_yolo_scanner
from adapters.ui_tkinter import RecyclingTkWindow

_log = logging.getLogger("ras.main")

_CAMERA_DEVICE_INDEX = 0
_YOLO_MODEL_PATH = "model/best.pt"
_YOLO_DEVICE = None
# Cambia al puerto de tu Arduino (Administrador de dispositivos → Puertos COM).
# También puedes usar la variable de entorno RAS_SERIAL_PORT.
_ARDUINO_SERIAL_PORT = "COM4"
_ARDUINO_BAUDRATE = 9600
_FALLBACK_ARDUINO_COMMAND = "ROJO"


def _list_serial_ports() -> list[str]:
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [port.device for port in list_ports.comports()]


def _resolve_arduino_port() -> str:
    env_port = os.environ.get("RAS_SERIAL_PORT", "").strip()
    if env_port:
        return env_port
    if _ARDUINO_SERIAL_PORT.strip():
        return _ARDUINO_SERIAL_PORT.strip()

    available_ports = _list_serial_ports()
    if len(available_ports) == 1:
        _log.info("Puerto serial autodetectado: %s", available_ports[0])
        return available_ports[0]

    ports_text = ", ".join(available_ports) if available_ports else "ninguno"
    raise RuntimeError(
        "Configura el puerto del Arduino en main.py (_ARDUINO_SERIAL_PORT) "
        f"o con la variable RAS_SERIAL_PORT. Puertos detectados: {ports_text}"
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    serial_port = _resolve_arduino_port()
    window = RecyclingTkWindow()
    scanner_ref: dict[str, TkinterYoloScanner | None] = {"scanner": None}
    arduino_ref: dict[str, ArduinoSerialBridge | None] = {"bridge": None}

    def on_window_ready(app_window: RecyclingTkWindow) -> None:
        arduino_bridge: ArduinoSerialBridge | None = None
        root = app_window.root

        def shutdown_arduino() -> None:
            if arduino_bridge is not None:
                arduino_bridge.stop()

        scanner = attach_yolo_scanner(
            app_window,
            model_path=_YOLO_MODEL_PATH,
            device_index=_CAMERA_DEVICE_INDEX,
            display_width=app_window.scaled_video_max_width,
            yolo_device=_YOLO_DEVICE,
            on_shutdown=shutdown_arduino,
        )
        scanner_ref["scanner"] = scanner

        def send_to_arduino(arduino_command: str | None) -> None:
            if arduino_bridge is None:
                return

            command = arduino_command or _FALLBACK_ARDUINO_COMMAND
            if arduino_command is None:
                _log.warning(
                    "YOLO sin categoría — enviando %s al Arduino", command
                )
            try:
                arduino_bridge.send_command(command)
            except Exception as exc:
                _log.error("No se pudo enviar categoría al Arduino: %s", exc)

        def on_arduino_detected() -> None:
            def run_scan_cycle() -> None:
                _log.info("Mostrando ventana y activando cámara")
                app_window.show()
                scanner.scan_once(on_complete=send_to_arduino)

            root.after(0, run_scan_cycle)

        def on_deposit_complete() -> None:
            def hide_window() -> None:
                _log.info("Depósito completo — ocultando ventana")
                scanner.clear_video()
                app_window.hide()

            root.after(0, hide_window)

        arduino_bridge = ArduinoSerialBridge(
            port=serial_port,
            baudrate=_ARDUINO_BAUDRATE,
            on_detected=on_arduino_detected,
            on_deposit_complete=on_deposit_complete,
        )
        arduino_bridge.start()
        arduino_ref["bridge"] = arduino_bridge
        _log.info(
            "Sistema en espera — ventana oculta hasta que Arduino envíe DETECTED"
        )

    window.run(on_ready=on_window_ready, start_hidden=True)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        _log.error("%s", exc)
        sys.exit(1)
