import logging

import serial


class SerialProximitySensor:
    """Espera la línea acordada (p. ej. OBJECT_DETECTED) desde Arduino por serial."""

    def __init__(
        self,
        port: str,
        baudrate: int,
        *,
        object_line: str = "OBJECT_DETECTED",
        timeout_s: float = 0.5,
    ) -> None:
        self._port = port.strip()
        self._baudrate = baudrate
        self._object_line = object_line.strip()
        self._timeout_s = timeout_s
        self._ser: serial.Serial | None = None
        self._log = logging.getLogger("ras.serial_sensor")

    def _open(self) -> serial.Serial:
        if self._ser is not None and self._ser.is_open:
            return self._ser
        self._log.info("Abriendo serial %s a %s baud", self._port, self._baudrate)
        candidates = [self._port]
        port_upper = self._port.upper()
        if port_upper.startswith("COM") and not self._port.startswith("\\\\.\\"):
            candidates.append(rf"\\.\{self._port}")
        last_exc: serial.SerialException | None = None
        for candidate in candidates:
            try:
                self._ser = serial.Serial(candidate, self._baudrate, timeout=self._timeout_s)
                if candidate != self._port:
                    self._log.info("Puerto abierto como %s", candidate)
                return self._ser
            except serial.SerialException as exc:
                last_exc = exc
                self._ser = None
        assert last_exc is not None
        raise RuntimeError(
            f"No se pudo abrir el puerto serie {self._port!r} (también se probó el nombre extendido de Windows). "
            f"Detalle: {last_exc}. "
            "Cierra el Monitor Serie del Arduino IDE, PuTTY u otra app que use el mismo COM; "
            "desconecta y reconecta el USB; vuelve a comprobar en Administrador de dispositivos "
            "que el número COM no haya cambiado."
        ) from last_exc

    def wait_until_object_detected(self) -> None:
        ser = self._open()
        needle = self._object_line
        while True:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            if line == needle or needle in line:
                self._log.info("Evento recibido: %s", line)
                return

    def release(self) -> None:
        if self._ser is None:
            return
        try:
            if self._ser.is_open:
                self._ser.close()
        except OSError:
            pass
        self._ser = None
