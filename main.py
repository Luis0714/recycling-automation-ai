import argparse
import logging
import sys
from pathlib import Path

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


def _build_simulated_dependencies(
    settings: Settings,
    *,
    skip_sensor_wait: bool,
) -> tuple[
    SimulatedProximitySensor | ImmediateProximitySensor,
    SimulatedImageCapture,
    StubWasteClassifier,
    LoggingBinActuator,
]:
    if skip_sensor_wait:
        sensor: SimulatedProximitySensor | ImmediateProximitySensor = ImmediateProximitySensor()
    else:
        sensor = SimulatedProximitySensor(prompt=settings.simulated_sensor_prompt)
    camera = SimulatedImageCapture(fixture_path=settings.simulated_image_fixture_path)
    classifier = StubWasteClassifier(category=settings.stub_waste_category)
    actuator = LoggingBinActuator()
    return sensor, camera, classifier, actuator


def main() -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(
        description="Recycling Automation System — pipeline simulado.",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Repite el ciclo tras cada ejecución (Ctrl+C para salir).",
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
        "--skip-wait",
        action="store_true",
        help="No usa input(); dispara el flujo al instante (pruebas/CI).",
    )
    args = parser.parse_args()

    settings = Settings()
    if args.category is not None:
        settings = settings.model_copy(update={"stub_waste_category": args.category})
    if args.fixture is not None:
        settings = settings.model_copy(update={"simulated_image_fixture_path": args.fixture})

    sensor, camera, classifier, actuator = _build_simulated_dependencies(
        settings,
        skip_sensor_wait=args.skip_wait,
    )

    while True:
        result = run_automatic_cycle(
            sensor=sensor,
            camera=camera,
            classifier=classifier,
            actuator=actuator,
        )
        print(result.model_dump_json(indent=2))
        if not args.loop:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
