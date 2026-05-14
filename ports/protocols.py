from typing import Protocol

from domain.models import ClassificationOutput


class ObjectDetectionSensor(Protocol):
    def wait_until_object_detected(self) -> None:
        """Bloquea hasta que exista un evento equivalente a OBJECT_DETECTED."""


class WasteImageCapture(Protocol):
    def capture_image_bytes(self) -> bytes:
        """Devuelve la imagen cruda (p. ej. PNG/JPEG) para el clasificador."""


class WasteClassifier(Protocol):
    def classify_waste(self, image_bytes: bytes) -> ClassificationOutput:
        """Inferencia: imagen → categoría y confianza."""


class SerialBinActuator(Protocol):
    def send_command(self, command: str) -> None:
        """Envía línea de comando al Arduino (p. ej. OPEN_PLASTIC)."""
