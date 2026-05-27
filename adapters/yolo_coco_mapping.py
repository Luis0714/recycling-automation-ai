from domain.models import WasteCategory

_CUSTOM_RECYCLING_MAPPING: dict[str, WasteCategory] = {
    # Dataset custom esperado en model/best.pt
    "metal": WasteCategory.METAL,
    "glass": WasteCategory.PLASTIC,
    "plastic": WasteCategory.PLASTIC,
    "carton": WasteCategory.PLASTIC,
    "medical": WasteCategory.UNKNOWN,
}

_COCO_PLASTIC: frozenset[str] = frozenset(
    {
        "bottle",
        "cup",
        "wine glass",
        "bowl",
        "toothbrush",
        "book",
        "cell phone",
        "remote",
        "mouse",
        "keyboard",
        "laptop",
        "tv",
        "microwave",
        "oven",
        "toaster",
        "refrigerator",
        "sink",
    }
)
_COCO_METAL: frozenset[str] = frozenset(
    {
        "scissors",
        "fork",
        "knife",
        "spoon",
        "clock",
    }
)
_COCO_ORGANIC: frozenset[str] = frozenset(
    {
        "banana",
        "apple",
        "sandwich",
        "orange",
        "broccoli",
        "carrot",
        "hot dog",
        "pizza",
        "donut",
        "cake",
        "potted plant",
    }
)


def coco_class_name_to_waste_category(class_name: str) -> WasteCategory:
    key = class_name.strip().lower()
    mapped_custom = _CUSTOM_RECYCLING_MAPPING.get(key)
    if mapped_custom is not None:
        return mapped_custom
    if key in _COCO_PLASTIC:
        return WasteCategory.PLASTIC
    if key in _COCO_METAL:
        return WasteCategory.METAL
    if key in _COCO_ORGANIC:
        return WasteCategory.ORGANIC
    return WasteCategory.UNKNOWN
