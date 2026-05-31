from domain.models import WasteCategory

_CUSTOM_RECYCLING_MAPPING: dict[str, WasteCategory] = {
    # Dataset custom esperado en model/best.pt
    "metal": WasteCategory.METAL,
    "glass": WasteCategory.PLASTIC,
    "plastic": WasteCategory.PLASTIC,
    "carton": WasteCategory.PLASTIC,
    "medical": WasteCategory.UNKNOWN,
}

def coco_class_name_to_waste_category(class_name: str) -> WasteCategory:
    key = class_name.strip().lower()
    return _CUSTOM_RECYCLING_MAPPING.get(key, WasteCategory.UNKNOWN)
