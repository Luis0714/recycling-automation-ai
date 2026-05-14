from domain.models import WasteCategory


def category_to_open_command(category: WasteCategory) -> str:
    if category is WasteCategory.PLASTIC:
        return "OPEN_PLASTIC"
    if category is WasteCategory.METAL:
        return "OPEN_METAL"
    if category is WasteCategory.ORGANIC:
        return "OPEN_ORGANIC"
    return "OPEN_UNKNOWN"
