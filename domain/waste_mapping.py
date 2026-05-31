"""Mapeo: clases YOLO waste-classification-yolov8-ken → UI y Arduino."""

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
    class_id: int
    model_name: str
    display_category: DisplayCategory
    arduino_command: ArduinoCommand


# kendrickfff/waste-classification-yolov8-ken — 12 clases
# Arduino: BLANCO=envases | NEGRO=residuo general | VERDE=orgánico/vidrio | ROJO=peligroso
WASTE_CATEGORY_MAPPINGS: tuple[WasteCategoryMapping, ...] = (
    WasteCategoryMapping(0, "battery", "No aprovechables", "ROJO"),
    WasteCategoryMapping(1, "biological", "Orgánicos", "VERDE"),
    WasteCategoryMapping(2, "brown-glass", "Orgánicos", "VERDE"),
    WasteCategoryMapping(3, "cardboard", "Aprovechables", "BLANCO"),
    WasteCategoryMapping(4, "clothes", "No aprovechables", "NEGRO"),
    WasteCategoryMapping(5, "green-glass", "Orgánicos", "VERDE"),
    WasteCategoryMapping(6, "metal", "Aprovechables", "BLANCO"),
    WasteCategoryMapping(7, "paper", "Aprovechables", "BLANCO"),
    WasteCategoryMapping(8, "plastic", "Aprovechables", "BLANCO"),
    WasteCategoryMapping(9, "shoes", "No aprovechables", "NEGRO"),
    WasteCategoryMapping(10, "trash", "No aprovechables", "NEGRO"),
    WasteCategoryMapping(11, "white-glass", "Orgánicos", "VERDE"),
)

WASTE_MAPPING_BY_CLASS_ID: dict[int, WasteCategoryMapping] = {
    mapping.class_id: mapping for mapping in WASTE_CATEGORY_MAPPINGS
}

WASTE_MAPPING_BY_MODEL_NAME: dict[str, WasteCategoryMapping] = {
    mapping.model_name: mapping for mapping in WASTE_CATEGORY_MAPPINGS
}


def resolve_waste_mapping_by_id(class_id: int) -> WasteCategoryMapping | None:
    return WASTE_MAPPING_BY_CLASS_ID.get(class_id)


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


def to_arduino_command_by_id(class_id: int) -> ArduinoCommand | None:
    mapping = resolve_waste_mapping_by_id(class_id)
    return mapping.arduino_command if mapping else None
