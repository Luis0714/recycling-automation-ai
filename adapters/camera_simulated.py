from pathlib import Path


class SimulatedImageCapture:
    def __init__(self, fixture_path: Path | None = None) -> None:
        self._fixture_path = fixture_path

    def capture_image_bytes(self) -> bytes:
        if self._fixture_path is not None and self._fixture_path.is_file():
            return self._fixture_path.read_bytes()
        return b"SIMULATED_IMAGE_BYTES"
