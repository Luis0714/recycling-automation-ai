from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from adapters import (
    ImmediateProximitySensor,
    LoggingBinActuator,
    SimulatedImageCapture,
    SimulatedProximitySensor,
    StubWasteClassifier,
)
from application.pipeline import run_automatic_cycle
from config import Settings
from domain.models import WasteCategory

if TYPE_CHECKING:
    from adapters.camera_opencv import OpenCvImageCapture
    from adapters.classifier_yolo import YoloWasteClassifier
    from adapters.sensor_serial import SerialProximitySensor


def _parse_category(value: str) -> WasteCategory:
    normalized = value.strip().lower()
    for member in WasteCategory:
        if member.value == normalized:
            return member
    raise argparse.ArgumentTypeError(
        f"categoría inválida: {value!r}. Use: {', '.join(m.value for m in WasteCategory)}"
    )


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


_log = logging.getLogger("ras.main")


def _build_dependencies(
    settings: Settings,
    *,
    sensor_mode: Literal["enter", "immediate", "serial"],
    camera_backend: Literal["simulated", "opencv"],
    classifier_backend: Literal["stub", "yolo"],
) -> tuple[
    SimulatedProximitySensor | ImmediateProximitySensor | SerialProximitySensor,
    SimulatedImageCapture | OpenCvImageCapture,
    StubWasteClassifier | YoloWasteClassifier,
    LoggingBinActuator,
]:
    if sensor_mode == "serial":
        from adapters.sensor_serial import SerialProximitySensor

        if not settings.serial_port or not str(settings.serial_port).strip():
            raise ValueError(
                "Modo --sensor serial: hace falta un puerto (RAS_SERIAL_PORT en .env o --serial-port COMx). "
                "Si aun no tienes Arduino, no uses serial: ejecuta sin --sensor (ENTER) o --sensor immediate."
            )
        sensor: (
            SimulatedProximitySensor | ImmediateProximitySensor | SerialProximitySensor
        ) = SerialProximitySensor(
            settings.serial_port,
            settings.serial_baudrate,
            object_line=settings.serial_object_line,
            timeout_s=settings.serial_timeout_s,
        )
    elif sensor_mode == "immediate":
        sensor = ImmediateProximitySensor()
    else:
        sensor = SimulatedProximitySensor(prompt=settings.simulated_sensor_prompt)
    if camera_backend == "opencv":
        from adapters.camera_opencv import OpenCvImageCapture

        camera: SimulatedImageCapture | OpenCvImageCapture = OpenCvImageCapture(
            device_index=settings.camera_device_index,
            jpeg_quality=settings.camera_jpeg_quality,
            show_preview=settings.camera_preview_enabled,
            preview_result_ms=settings.camera_preview_result_ms,
            placement_preview_ms=settings.camera_placement_preview_ms,
        )
    else:
        camera = SimulatedImageCapture(fixture_path=settings.simulated_image_fixture_path)
    if classifier_backend == "yolo":
        from adapters.classifier_yolo import YoloWasteClassifier

        classifier: StubWasteClassifier | YoloWasteClassifier = YoloWasteClassifier(
            settings.yolo_model_path,
            confidence_threshold=settings.yolo_confidence,
        )
    else:
        classifier = StubWasteClassifier(category=settings.stub_waste_category)
    actuator = LoggingBinActuator()
    return sensor, camera, classifier, actuator


def main() -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(
        description="Recycling Automation System — pipeline simulado.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Un solo ciclo y termina. Por defecto el programa repite: ENTER/serial -> captura -> ... hasta Ctrl+C.",
    )
    parser.add_argument(
        "--category",
        type=_parse_category,
        default=None,
        help="Categoría del stub (plastic|metal|organic|unknown). Por defecto: env o plastic.",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="Ruta a imagen para SimulatedImageCapture (opcional).",
    )
    parser.add_argument(
        "--sensor",
        choices=("enter", "immediate", "serial"),
        default="enter",
        help="enter: espera ENTER (simula proximidad; recomendado sin Arduino). immediate: sin espera. "
        "serial: solo con Arduino y RAS_SERIAL_PORT / --serial-port.",
    )
    parser.add_argument(
        "--serial-port",
        type=str,
        default=None,
        help="Puerto serie (p. ej. COM3). Sobrescribe RAS_SERIAL_PORT.",
    )
    parser.add_argument(
        "--serial-baud",
        type=int,
        default=None,
        help="Baudios (por defecto RAS_SERIAL_BAUDRATE, 115200).",
    )
    parser.add_argument(
        "--skip-wait",
        action="store_true",
        help="Equivalente a --sensor immediate (compatibilidad). Ignorado si --sensor serial.",
    )
    parser.add_argument(
        "--camera",
        choices=("simulated", "opencv"),
        default=None,
        help="simulated: bytes fijos o --fixture. opencv: captura JPEG desde webcam. "
        "Si se omite: opencv si RAS_RUN_MODE=hardware, si no simulated.",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=None,
        help="Índice de dispositivo OpenCV (sobrescribe RAS_CAMERA_DEVICE_INDEX / config).",
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Sin ventana OpenCV (servidor / CI).",
    )
    parser.add_argument(
        "--preview-ms",
        type=int,
        default=None,
        help="Milisegundos mostrando el resultado final (RAS_CAMERA_PREVIEW_RESULT_MS).",
    )
    parser.add_argument(
        "--placement-preview-ms",
        type=int,
        default=None,
        help="Milisegundos de vista en vivo para colocar el objeto antes de capturar (0=off). "
        "RAS_CAMERA_PLACEMENT_PREVIEW_MS (por defecto 5000 = 5 s).",
    )
    parser.add_argument(
        "--classifier",
        choices=("stub", "yolo"),
        default=None,
        help="stub: categoría fija (RAS_STUB_WASTE_CATEGORY / --category). yolo: YOLOv8 + mapeo COCO.",
    )
    parser.add_argument(
        "--yolo-model",
        type=str,
        default=None,
        help="Ruta o nombre del modelo (.pt). Por defecto RAS_YOLO_MODEL_PATH (yolov8n.pt).",
    )
    parser.add_argument(
        "--yolo-conf",
        type=float,
        default=None,
        help="Umbral de confianza YOLO (0-1). Por defecto RAS_YOLO_CONFIDENCE.",
    )
    args = parser.parse_args()

    settings = Settings()
    if args.category is not None:
        settings = settings.model_copy(update={"stub_waste_category": args.category})
    if args.fixture is not None:
        settings = settings.model_copy(update={"simulated_image_fixture_path": args.fixture})
    if args.camera_index is not None:
        settings = settings.model_copy(update={"camera_device_index": args.camera_index})
    if args.no_preview:
        settings = settings.model_copy(update={"camera_preview_enabled": False})
    if args.preview_ms is not None:
        settings = settings.model_copy(update={"camera_preview_result_ms": args.preview_ms})
    if args.placement_preview_ms is not None:
        settings = settings.model_copy(update={"camera_placement_preview_ms": args.placement_preview_ms})
    if args.serial_port is not None:
        settings = settings.model_copy(update={"serial_port": args.serial_port})
    if args.serial_baud is not None:
        settings = settings.model_copy(update={"serial_baudrate": args.serial_baud})
    if args.classifier is not None:
        settings = settings.model_copy(update={"classifier_backend": args.classifier})
    if args.yolo_model is not None:
        settings = settings.model_copy(update={"yolo_model_path": args.yolo_model})
    if args.yolo_conf is not None:
        settings = settings.model_copy(update={"yolo_confidence": args.yolo_conf})

    if args.sensor == "serial":
        sensor_mode: Literal["enter", "immediate", "serial"] = "serial"
    elif args.skip_wait or args.sensor == "immediate":
        sensor_mode = "immediate"
    else:
        sensor_mode = "enter"

    if args.camera is not None:
        camera_backend: Literal["simulated", "opencv"] = args.camera
    elif settings.run_mode == "hardware":
        camera_backend = "opencv"
    else:
        camera_backend = "simulated"

    classifier_backend: Literal["stub", "yolo"] = settings.classifier_backend

    try:
        sensor, camera, classifier, actuator = _build_dependencies(
            settings,
            sensor_mode=sensor_mode,
            camera_backend=camera_backend,
            classifier_backend=classifier_backend,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    try:
        while True:
            result = run_automatic_cycle(
                sensor=sensor,
                camera=camera,
                classifier=classifier,
                actuator=actuator,
            )
            print(result.model_dump_json(indent=2))
            camera.end_cycle_release_for_next_trigger()
            if args.once:
                break
            if sensor_mode == "enter":
                _log.info(
                    "Camara cerrada. Pulse ENTER para simular otro objeto cerca (sensor de cercania)."
                )
            elif sensor_mode == "serial":
                _log.info(
                    "Camara cerrada. Esperando la siguiente linea desde Arduino (p. ej. OBJECT_DETECTED)."
                )
            else:
                _log.info("Camara cerrada. Siguiente ciclo inmediato (--sensor immediate).")
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario (Ctrl+C).", file=sys.stderr)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        sensor_release = getattr(sensor, "release", None)
        if callable(sensor_release):
            sensor_release()
        camera.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
