import logging


class LoggingBinActuator:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._log = logger or logging.getLogger("ras.serial")

    def send_command(self, command: str) -> None:
        self._log.info("[simulated serial] %s", command)
