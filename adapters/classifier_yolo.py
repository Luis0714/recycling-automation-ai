import logging
from typing import FrozenSet

import cv2
import numpy as np
from ultralytics import YOLO

from adapters.yolo_coco_mapping import coco_class_name_to_waste_category
from domain.models import ClassificationOutput, WasteCategory


def _parse_skip_class_names(raw: str) -> FrozenSet[str]:
    return frozenset(p.strip().lower() for p in raw.split(",") if p.strip())


class YoloWasteClassifier:
    """Clasificador de residuos con YOLOv8 (COCO) y mapeo heurístico a categorías de reciclaje."""

    def __init__(
        self,
        model_path: str,
        *,
        confidence_threshold: float = 0.35,
        skip_class_names: str = "person",
    ) -> None:
        self._log = logging.getLogger("ras.yolo")
        self._conf = max(0.0, min(1.0, confidence_threshold))
        self._skip = _parse_skip_class_names(skip_class_names)
        self._model = YOLO(model_path)
        self._log.info("Modelo YOLO cargado: %s", model_path)
        if self._skip:
            self._log.info("Clases YOLO ignoradas: %s", ", ".join(sorted(self._skip)))

    def classify_waste(self, image_bytes: bytes) -> ClassificationOutput:
        decoded = np.frombuffer(image_bytes, dtype=np.uint8)
        image_bgr = cv2.imdecode(decoded, cv2.IMREAD_COLOR)
        if image_bgr is None:
            return ClassificationOutput(
                category=WasteCategory.UNKNOWN,
                confidence=0.0,
                raw_label="imdecode_failed",
            )
        results = self._model.predict(
            source=image_bgr,
            verbose=False,
            conf=self._conf,
        )
        if not results:
            return ClassificationOutput(
                category=WasteCategory.UNKNOWN,
                confidence=0.0,
                raw_label="no_results",
            )
        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return ClassificationOutput(
                category=WasteCategory.UNKNOWN,
                confidence=0.0,
                raw_label="no_detection",
            )
        names = results[0].names
        order = boxes.conf.argsort(descending=True)
        best_idx: int | None = None
        for j in order:
            idx = int(j.item())
            cls_id = int(boxes.cls[idx].item())
            raw_name = str(names[cls_id])
            if raw_name.strip().lower() in self._skip:
                continue
            best_idx = idx
            break
        if best_idx is None:
            return ClassificationOutput(
                category=WasteCategory.UNKNOWN,
                confidence=0.0,
                raw_label="only_skipped_classes",
            )
        conf = float(boxes.conf[best_idx].item())
        cls_id = int(boxes.cls[best_idx].item())
        raw_name = str(names[cls_id])
        waste = coco_class_name_to_waste_category(raw_name)
        xyxy_tensor = boxes.xyxy[best_idx]
        bbox_xyxy = (
            float(xyxy_tensor[0].item()),
            float(xyxy_tensor[1].item()),
            float(xyxy_tensor[2].item()),
            float(xyxy_tensor[3].item()),
        )
        return ClassificationOutput(
            category=waste,
            confidence=conf,
            raw_label=raw_name,
            bbox_xyxy=bbox_xyxy,
        )
