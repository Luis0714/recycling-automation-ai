from datetime import UTC, datetime

from domain.mapping import category_to_open_command
from domain.models import ClassificationOutput, CycleResult
from ports.protocols import (
    ObjectDetectionSensor,
    SerialBinActuator,
    WasteClassifier,
    WasteImageCapture,
)


def _notify_classification_preview_if_supported(
    camera: WasteImageCapture,
    classification: ClassificationOutput,
) -> None:
    method = getattr(camera, "show_classification_preview", None)
    if callable(method):
        method(classification)


def run_automatic_cycle(
    sensor: ObjectDetectionSensor,
    camera: WasteImageCapture,
    classifier: WasteClassifier,
    actuator: SerialBinActuator,
) -> CycleResult:
    started_at = datetime.now(UTC)
    sensor.wait_until_object_detected()
    image_bytes = camera.capture_image_bytes()
    classification = classifier.classify_waste(image_bytes)
    _notify_classification_preview_if_supported(camera, classification)
    command_sent = category_to_open_command(classification.category)
    actuator.send_command(command_sent)
    finished_at = datetime.now(UTC)
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    return CycleResult(
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        classification=classification,
        command_sent=command_sent,
    )
