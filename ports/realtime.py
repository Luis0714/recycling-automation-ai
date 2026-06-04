"""Protocolos para suscriptores de comandos de apertura de canecas en tiempo real.

El lado web inserta filas en `manual_bin_openings`; el lado Python se
suscribe vía Supabase Realtime (`postgres_changes`) y traduce cada
INSERT en un comando al Arduino.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable, Protocol

BinType = str  # "BLANCO" | "NEGRO" | "VERDE" | "ROJO"


@dataclass(frozen=True)
class BinCommand:
    """Comando para abrir una caneca, recibido vía Realtime."""

    opening_id: uuid.UUID
    bin_type: BinType
    station_id: str | None
    client_request_id: str | None = None


OnBinCommand = Callable[[BinCommand], None]


class BinCommandSubscriber(Protocol):
    """Suscriptor al canal Realtime de aperturas manuales."""

    def start(self, on_command: OnBinCommand) -> None:
        """Inicia la suscripción; `on_command` se invoca por cada INSERT nuevo."""
        ...

    def stop(self) -> None:
        """Cancela la suscripción y libera recursos."""
        ...
