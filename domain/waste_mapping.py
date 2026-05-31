"""Mapeo: clases del modelo YOLO → categoría de UI y comando Arduino."""

from dataclasses import dataclass
from typing import Literal

DisplayCategory = Literal["Aprovechables", "No aprovechables", "Orgánicos"]
ArduinoCommand = Literal["BLANCO", "NEGRO", "VERDE", "ROJO"]

DISPLAY_CATEGORIES: tuple[DisplayCategory, ...] = (
    "Aprovechables",
    "No aprovechables",
    "Orgánicos",
)

ARDUINO_COMMANDS: tuple[ArduinoCommand, ...] = (
    "BLANCO",
    "NEGRO",
    "VERDE",
    "ROJO",
)


@dataclass(frozen=True)
class WasteCategoryMapping:
    model_name: str
    display_category: DisplayCategory
    arduino_command: ArduinoCommand


# Clases de model/best.pt → UI (3 categorías) + caneca Arduino (4 colores).
# Arduino: BLANCO=plástico/envases, NEGRO=residuo general, VERDE=orgánico/vidrio, ROJO=peligroso.
WASTE_CATEGORY_MAPPINGS: tuple[WasteCategoryMapping, ...] = (
    WasteCategoryMapping("Plastic", "Aprovechables", "BLANCO"),
    WasteCategoryMapping("Metal", "Aprovechables", "BLANCO"),
    WasteCategoryMapping("Carton", "Aprovechables", "BLANCO"),
    WasteCategoryMapping("Glass", "Aprovechables", "VERDE"),
    WasteCategoryMapping("Medical", "No aprovechables", "ROJO"),
)

WASTE_MAPPING_BY_MODEL_NAME: dict[str, WasteCategoryMapping] = {
    mapping.model_name: mapping for mapping in WASTE_CATEGORY_MAPPINGS
}


def resolve_waste_mapping(model_class_name: str) -> WasteCategoryMapping | None:
    if not model_class_name:
        return None
    normalized = model_class_name.strip()
    if not normalized:
        return None
    direct = WASTE_MAPPING_BY_MODEL_NAME.get(normalized)
    if direct is not None:
        return direct
    lowered = normalized.casefold()
    for mapping in WASTE_CATEGORY_MAPPINGS:
        if mapping.model_name.casefold() == lowered:
            return mapping
    return None


def to_display_category(model_class_name: str) -> str | None:
    mapping = resolve_waste_mapping(model_class_name)
    return mapping.display_category if mapping else None


def to_arduino_command(model_class_name: str) -> ArduinoCommand | None:
    mapping = resolve_waste_mapping(model_class_name)
    return mapping.arduino_command if mapping else None
