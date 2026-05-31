import logging

from adapters.arduino_serial import ArduinoSerialBridge
from adapters.scanning_tkinter import TkinterYoloScanner, attach_yolo_scanner
from adapters.ui_tkinter import RecyclingTkWindow

_log = logging.getLogger("ras.main")

_CAMERA_DEVICE_INDEX = 0
_YOLO_MODEL_PATH = "model/best.pt"
# None = auto (GPU si hay CUDA, si no CPU). También: 0, "cuda:0", "cpu"
_YOLO_DEVICE = None
# None = cámara continua (pruebas sin Arduino). Ejemplo: "COM4"
_ARDUINO_SERIAL_PORT: str | None = None
_ARDUINO_BAUDRATE = 9600


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    window = RecyclingTkWindow()
    arduino_triggered = _ARDUINO_SERIAL_PORT is not None

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
            arduino_triggered=arduino_triggered,
            on_shutdown=shutdown_arduino,
        )

        if not arduino_triggered:
            return

        def on_scan_complete(arduino_command: str | None) -> None:
            if arduino_bridge is None:
                return
            if arduino_command is None:
                _log.warning("Sin clasificación YOLO — no se envió comando al Arduino")
                return
            try:
                arduino_bridge.send_command(arduino_command)
            except Exception as exc:
                _log.error("No se pudo enviar categoría al Arduino: %s", exc)

        def on_arduino_detected() -> None:
            root.after(0, lambda: scanner.scan_once(on_complete=on_scan_complete))

        arduino_bridge = ArduinoSerialBridge(
            port=_ARDUINO_SERIAL_PORT,
            baudrate=_ARDUINO_BAUDRATE,
            on_detected=on_arduino_detected,
        )
        arduino_bridge.start()

    window.run(on_ready=on_window_ready)


if __name__ == "__main__":
    main()
