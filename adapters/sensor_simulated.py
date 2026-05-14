class SimulatedProximitySensor:
    def __init__(self, prompt: str) -> None:
        self._prompt = prompt

    def wait_until_object_detected(self) -> None:
        input(self._prompt)

    def release(self) -> None:
        return


class ImmediateProximitySensor:
    """Equivalente a OBJECT_DETECTED sin esperar (pruebas automatizadas, CI)."""

    def wait_until_object_detected(self) -> None:
        return

    def release(self) -> None:
        return
