from domain.models import ClassificationOutput, WasteCategory


class StubWasteClassifier:
    def __init__(
        self,
        category: WasteCategory,
        confidence: float = 0.99,
        raw_label: str | None = "stub",
    ) -> None:
        self._category = category
        self._confidence = confidence
        self._raw_label = raw_label

    def classify_waste(self, image_bytes: bytes) -> ClassificationOutput:
        return ClassificationOutput(
            category=self._category,
            confidence=self._confidence,
            raw_label=self._raw_label,
        )
