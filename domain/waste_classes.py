# Clases del modelo custom (model/best.pt) — referencia Hugging Face recyclingAI
from dataclasses import dataclass

_DEFAULT_MODEL_PATH = "model/best.pt"


@dataclass(frozen=True)
class WasteClassStyle:
    class_id: int
    name: str
    bbox_color_rgb: tuple[int, int, int]


WASTE_CLASS_STYLES: tuple[WasteClassStyle, ...] = (
    WasteClassStyle(0, "Metal", (255, 255, 0)),
    WasteClassStyle(1, "Glass", (255, 255, 255)),
    WasteClassStyle(2, "Plastic", (0, 0, 255)),
    WasteClassStyle(3, "Carton", (150, 150, 150)),
    WasteClassStyle(4, "Medical", (255, 0, 0)),
)

WASTE_CLASS_BY_ID: dict[int, WasteClassStyle] = {
    style.class_id: style for style in WASTE_CLASS_STYLES
}
