from adapters.actuator_logging import LoggingBinActuator
from adapters.camera_simulated import SimulatedImageCapture
from adapters.classifier_stub import StubWasteClassifier
from adapters.sensor_simulated import (
    ImmediateProximitySensor,
    SimulatedProximitySensor,
)

__all__ = [
    "SimulatedProximitySensor",
    "ImmediateProximitySensor",
    "SimulatedImageCapture",
    "StubWasteClassifier",
    "LoggingBinActuator",
]
