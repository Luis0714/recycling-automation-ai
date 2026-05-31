import logging
import threading
from collections.abc import Callable

_log = logging.getLogger("ras.arduino")

OnObjectDetected = Callable[[], None]
OnDepositComplete = Callable[[], None]

VALID_ARDUINO_COMMANDS = frozenset({"BLANCO", "NEGRO", "VERDE", "ROJO"})


class ArduinoSerialBridge:
    """Puente serial con el clasificador Arduino."""

    def __init__(
        self,
        *,
        port: str,
        baudrate: int = 9600,
        on_detected: OnObjectDetected,
        on_deposit_complete: OnDepositComplete | None = None,
        timeout_s: float = 1.0,
    ) -> None:
        if not port.strip():
            raise ValueError("El puerto serial no puede estar vacío.")

        self._port = port.strip()
        self._baudrate = baudrate
        self._on_detected = on_detected
        self._on_deposit_complete = on_deposit_complete
        self._timeout_s = timeout_s
        self._serial = None
        self._reader_thread: threading.Thread | None = None
        self._is_running = False

    def start(self) -> None:
        if self._is_running:
            return

        try:
            import serial
        except ImportError as exc:
            raise RuntimeError(
                "Falta pyserial. Instala con: pip install pyserial"
            ) from exc

        self._serial = serial.Serial(
            self._port,
            self._baudrate,
            timeout=self._timeout_s,
        )
        self._is_running = True
        self._reader_thread = threading.Thread(
            target=self._read_loop,
            name="arduino-serial-reader",
            daemon=True,
        )
        self._reader_thread.start()
        _log.info("Serial abierto en %s (%s baud)", self._port, self._baudrate)

    def stop(self) -> None:
        self._is_running = False
        if self._reader_thread is not None and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2.0)
        self._reader_thread = None
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def send_command(self, command: str) -> None:
        if self._serial is None or not self._serial.is_open:
            raise RuntimeError("Serial no está conectado.")

        normalized = command.strip().upper()
        if normalized not in VALID_ARDUINO_COMMANDS:
            raise ValueError(
                f"Comando inválido para Arduino: {command!r}. "
                f"Use uno de: {sorted(VALID_ARDUINO_COMMANDS)}"
            )

        payload = f"{normalized}\n".encode("ascii")
        self._serial.write(payload)
        self._serial.flush()
        _log.info("Enviado a Arduino: %s", normalized)

    def _read_loop(self) -> None:
        while self._is_running and self._serial is not None and self._serial.is_open:
            try:
                raw_line = self._serial.readline()
            except Exception as exc:
                _log.error("Error leyendo serial: %s", exc)
                break

            if not raw_line:
                continue

            line = raw_line.decode("ascii", errors="ignore").strip()
            if not line:
                continue

            self._handle_line(line)

    def _handle_line(self, line: str) -> None:
        if line == "ARDUINO_LISTO":
            _log.info("Arduino listo — esperando objeto en sensor HC-SR04")
            return

        if line == "DETECTED":
            _log.info("Arduino detectó objeto")
            self._on_detected()
            return

        if line.startswith("DEPOSITANDO:"):
            _log.info("Depósito iniciado: %s", line.split(":", maxsplit=1)[-1])
            return

        if line.startswith("DEPOSITO_COMPLETO:"):
            _log.info("Depósito completo: %s", line.split(":", maxsplit=1)[-1])
            if self._on_deposit_complete is not None:
                self._on_deposit_complete()
            return

        if line.startswith("ERROR:"):
            _log.error("Arduino: %s", line)
            return

        _log.debug("Serial Arduino: %s", line)
