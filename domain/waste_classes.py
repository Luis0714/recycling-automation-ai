# Modelo: kendrickfff/waste-classification-yolov8-ken (yolov8n-waste-12cls-best.pt)
from dataclasses import dataclass

_DEFAULT_MODEL_PATH = "model/yolov8n-waste-12cls-best.pt"
_HF_MODEL_REPO = "kendrickfff/waste-classification-yolov8-ken"
_HF_MODEL_FILENAME = "yolov8n-waste-12cls-best.pt"


@dataclass(frozen=True)
class WasteClassStyle:
    class_id: int
    name: str
    bbox_color_rgb: tuple[int, int, int]


WASTE_CLASS_STYLES: tuple[WasteClassStyle, ...] = (
    WasteClassStyle(0, "battery", (255, 0, 0)),
    WasteClassStyle(1, "biological", (0, 200, 80)),
    WasteClassStyle(2, "brown-glass", (180, 120, 60)),
    WasteClassStyle(3, "cardboard", (150, 150, 150)),
    WasteClassStyle(4, "clothes", (160, 80, 200)),
    WasteClassStyle(5, "green-glass", (0, 180, 120)),
    WasteClassStyle(6, "metal", (255, 255, 0)),
    WasteClassStyle(7, "paper", (220, 220, 180)),
    WasteClassStyle(8, "plastic", (0, 0, 255)),
    WasteClassStyle(9, "shoes", (120, 60, 180)),
    WasteClassStyle(10, "trash", (80, 80, 80)),
    WasteClassStyle(11, "white-glass", (255, 255, 255)),
)

WASTE_CLASS_BY_ID: dict[int, WasteClassStyle] = {
    style.class_id: style for style in WASTE_CLASS_STYLES
}

WASTE_CLASS_BY_NAME: dict[str, WasteClassStyle] = {
    style.name: style for style in WASTE_CLASS_STYLES
}
