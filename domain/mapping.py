from domain.models import WasteCategory

NO_ACTION_COMMAND = "NO_ACTION"


def category_to_open_command(category: WasteCategory) -> str:
    # Operación con 3 canecas:
    # - Aprovechables: BLANCO (plastic + metal)
    # - Organicos: VERDE
    # - No aprovechables / no identificados: NEGRO
    if category is WasteCategory.PLASTIC:
        return "BLANCO"
    if category is WasteCategory.METAL:
        return "BLANCO"
    if category is WasteCategory.ORGANIC:
        return "VERDE"
    return NO_ACTION_COMMAND
