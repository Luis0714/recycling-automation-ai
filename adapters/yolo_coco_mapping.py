from domain.models import WasteCategory

_COCO_PLASTIC: frozenset[str] = frozenset(
    {
        "bottle",
        "cup",
        "wine glass",
        "bowl",
        "toothbrush",
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
    }
)


def coco_class_name_to_waste_category(class_name: str) -> WasteCategory:
    key = class_name.strip().lower()
    if key in _COCO_PLASTIC:
        return WasteCategory.PLASTIC
    if key in _COCO_METAL:
        return WasteCategory.METAL
    if key in _COCO_ORGANIC:
        return WasteCategory.ORGANIC
    return WasteCategory.UNKNOWN
