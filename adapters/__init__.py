from typing import TYPE_CHECKING

__all__ = [
    "ArduinoSerialBridge",
    "RecyclingTkWindow",
    "TkinterCameraFeed",
]

_LAZY_IMPORTS = {
    "ArduinoSerialBridge": "adapters.arduino_serial_bridge",
    "RecyclingTkWindow": "adapters.ui_tkinter",
    "TkinterCameraFeed": "adapters.camera_tkinter",
}


def __getattr__(name: str):
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path = _LAZY_IMPORTS[name]
    module = __import__(module_path, fromlist=[name])
    return getattr(module, name)


if TYPE_CHECKING:
    from adapters.arduino_serial_bridge import ArduinoSerialBridge
    from adapters.camera_tkinter import TkinterCameraFeed
    from adapters.ui_tkinter import RecyclingTkWindow
