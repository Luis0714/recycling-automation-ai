from typing import TYPE_CHECKING

__all__ = [
    "ArduinoSerialBridge",
    "RecyclingTkWindow",
    "SupabaseBinCommandSubscriber",
    "SupabaseEventRepository",
    "SupabaseManualOpeningRepository",
    "TkinterYoloScanner",
]

_LAZY_IMPORTS = {
    "ArduinoSerialBridge": "adapters.arduino_serial",
    "RecyclingTkWindow": "adapters.ui_tkinter",
    "SupabaseBinCommandSubscriber": "adapters.supabase_realtime",
    "SupabaseEventRepository": "adapters.supabase_persistence",
    "SupabaseManualOpeningRepository": "adapters.supabase_persistence",
    "TkinterYoloScanner": "adapters.scanning_tkinter",
}


def __getattr__(name: str):
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path = _LAZY_IMPORTS[name]
    module = __import__(module_path, fromlist=[name])
    return getattr(module, name)


if TYPE_CHECKING:
    from adapters.arduino_serial import ArduinoSerialBridge
    from adapters.scanning_tkinter import TkinterYoloScanner
    from adapters.supabase_persistence import (
        SupabaseEventRepository,
        SupabaseManualOpeningRepository,
    )
    from adapters.supabase_realtime import SupabaseBinCommandSubscriber
    from adapters.ui_tkinter import RecyclingTkWindow
