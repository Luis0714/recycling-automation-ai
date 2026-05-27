from domain.models import WasteCategory


def category_to_open_command(category: WasteCategory) -> str:
    if category is WasteCategory.PLASTIC:
        return "BLANCO"
    if category is WasteCategory.METAL:
        return "NEGRO"
    if category is WasteCategory.ORGANIC:
        return "VERDE"
    return "DEFAULT"
