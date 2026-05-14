import logging

import cv2
import numpy as np
from ultralytics import YOLO

from adapters.yolo_coco_mapping import coco_class_name_to_waste_category
from domain.models import ClassificationOutput, WasteCategory


class YoloWasteClassifier:
    """Clasificador de residuos con YOLOv8 (COCO) y mapeo heurístico a categorías de reciclaje."""

    def __init__(self, model_path: str, *, confidence_threshold: float = 0.35) -> None:
        self._log = logging.getLogger("ras.yolo")
        self._conf = max(0.0, min(1.0, confidence_threshold))
        self._model = YOLO(model_path)
        self._log.info("Modelo YOLO cargado: %s", model_path)

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
        best_idx = int(boxes.conf.argmax().item())
        conf = float(boxes.conf[best_idx].item())
        cls_id = int(boxes.cls[best_idx].item())
        names = results[0].names
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
