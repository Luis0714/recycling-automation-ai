import logging
from collections import defaultdict
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
        category_confidence_threshold: float = 0.45,
        skip_class_names: str = "person",
    ) -> None:
        self._log = logging.getLogger("ras.yolo")
        self._conf = max(0.0, min(1.0, confidence_threshold))
        self._category_conf = max(0.0, min(1.0, category_confidence_threshold))
        self._skip = _parse_skip_class_names(skip_class_names)
        self._model = YOLO(model_path)
        self._log.info("Modelo YOLO cargado: %s", model_path)
        self._log.info("Umbral minimo de categoria: %.2f", self._category_conf)
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
        winning_category = WasteCategory.UNKNOWN
        category_scores: dict[WasteCategory, float] = defaultdict(float)
        category_best_idx: dict[WasteCategory, int] = {}
        for j in order:
            idx = int(j.item())
            cls_id = int(boxes.cls[idx].item())
            raw_name = str(names[cls_id])
            if raw_name.strip().lower() in self._skip:
                continue
            best_idx = idx
            mapped_category = coco_class_name_to_waste_category(raw_name)
            if mapped_category is WasteCategory.UNKNOWN:
                continue
            conf = float(boxes.conf[idx].item())
            category_scores[mapped_category] += conf
            previous_idx = category_best_idx.get(mapped_category)
            if previous_idx is None:
                category_best_idx[mapped_category] = idx
                continue
            previous_conf = float(boxes.conf[previous_idx].item())
            if conf > previous_conf:
                category_best_idx[mapped_category] = idx
        if best_idx is None:
            return ClassificationOutput(
                category=WasteCategory.UNKNOWN,
                confidence=0.0,
                raw_label="only_skipped_classes",
            )
        if category_scores:
            winning_category = max(category_scores.items(), key=lambda item: item[1])[0]
            best_idx = category_best_idx[winning_category]
        conf = float(boxes.conf[best_idx].item())
        cls_id = int(boxes.cls[best_idx].item())
        raw_name = str(names[cls_id])
        if conf < self._category_conf:
            return ClassificationOutput(
                category=WasteCategory.UNKNOWN,
                confidence=conf,
                raw_label=f"low_confidence:{raw_name}",
            )
        waste = (
            winning_category
            if winning_category is not WasteCategory.UNKNOWN
            else coco_class_name_to_waste_category(raw_name)
        )
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
