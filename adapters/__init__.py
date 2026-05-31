from typing import TYPE_CHECKING

__all__ = [
    "RecyclingTkWindow",
    "TkinterYoloScanner",
]

_LAZY_IMPORTS = {
    "RecyclingTkWindow": "adapters.ui_tkinter",
    "TkinterYoloScanner": "adapters.scanning_tkinter",
}


def __getattr__(name: str):
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path = _LAZY_IMPORTS[name]
    module = __import__(module_path, fromlist=[name])
    return getattr(module, name)


if TYPE_CHECKING:
    from adapters.scanning_tkinter import TkinterYoloScanner
    from adapters.ui_tkinter import RecyclingTkWindow
