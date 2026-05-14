import logging
import math
import time

import cv2
import numpy as np

from domain.models import ClassificationOutput

_PREVIEW_WINDOW = "RAS - Vista de camara"


def _draw_bbox_clamped(
    image_bgr: np.ndarray,
    bbox_xyxy: tuple[float, float, float, float],
    *,
    color: tuple[int, int, int] = (0, 220, 0),
    thickness: int = 3,
) -> None:
    height, width = image_bgr.shape[:2]
    x1, y1, x2, y2 = bbox_xyxy
    x1i = int(max(0, min(width - 1, round(x1))))
    y1i = int(max(0, min(height - 1, round(y1))))
    x2i = int(max(0, min(width - 1, round(x2))))
    y2i = int(max(0, min(height - 1, round(y2))))
    if x2i <= x1i or y2i <= y1i:
        return
    cv2.rectangle(image_bgr, (x1i, y1i), (x2i, y2i), color, thickness, lineType=cv2.LINE_AA)


def _compose_preview_frame(
    frame_bgr: np.ndarray,
    lines: tuple[str, ...],
    bbox_xyxy: tuple[float, float, float, float] | None,
) -> np.ndarray:
    vis = frame_bgr.copy()
    if bbox_xyxy is not None:
        _draw_bbox_clamped(vis, bbox_xyxy)
    y0 = 28
    for i, text in enumerate(lines):
        y = y0 + i * 32
        cv2.putText(
            vis,
            text,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (40, 40, 40),
            4,
            cv2.LINE_AA,
        )
        cv2.putText(
            vis,
            text,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (240, 240, 240),
            2,
            cv2.LINE_AA,
        )
    return vis


class OpenCvImageCapture:
    """Captura frames desde una cámara local vía OpenCV (`WasteImageCapture`)."""

    def __init__(
        self,
        device_index: int = 0,
        jpeg_quality: int = 85,
        *,
        show_preview: bool = True,
        preview_result_ms: int = 3500,
        placement_preview_ms: int = 5000,
    ) -> None:
        self._device_index = device_index
        self._jpeg_quality = max(1, min(100, jpeg_quality))
        self._show_preview = show_preview
        self._preview_result_ms = max(0, preview_result_ms)
        self._placement_preview_ms = max(0, placement_preview_ms)
        self._cap: cv2.VideoCapture | None = None
        self._last_bgr: np.ndarray | None = None
        self._log = logging.getLogger("ras.camera")
        self._preview_gui_broken = False

    def _ensure_capture(self) -> cv2.VideoCapture:
        if self._cap is not None and self._cap.isOpened():
            return self._cap
        self._log.info("Abriendo cámara índice %s", self._device_index)
        self._cap = cv2.VideoCapture(self._device_index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"No se pudo abrir la cámara en el índice {self._device_index}"
            )
        return self._cap

    def _run_placement_preview(self, cap: cv2.VideoCapture) -> None:
        if self._placement_preview_ms <= 0 or not self._show_preview or self._preview_gui_broken:
            return
        self._log.info(
            "Vista previa de colocacion: %s s (ESC = capturar antes)",
            self._placement_preview_ms / 1000.0,
        )
        end = time.monotonic() + self._placement_preview_ms / 1000.0
        try:
            cv2.namedWindow(_PREVIEW_WINDOW, cv2.WINDOW_AUTOSIZE)
        except cv2.error as exc:
            self._preview_gui_broken = True
            self._log.warning(
                "OpenCV sin soporte GUI: vista previa desactivada. Detalle: %s",
                exc,
            )
            return
        while time.monotonic() < end:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            remaining_s = max(0.0, end - time.monotonic())
            sec_left = max(0, int(math.ceil(remaining_s)))
            lines = (
                "Coloca el objeto frente a la camara",
                f"Se cerrara en: {sec_left}s (ESC = capturar ya)",
            )
            vis = _compose_preview_frame(frame, lines, None)
            try:
                cv2.imshow(_PREVIEW_WINDOW, vis)
                key = cv2.waitKey(30) & 0xFF
                if key == 27:
                    break
            except cv2.error as exc:
                self._preview_gui_broken = True
                self._log.warning("Error en ventana de colocacion: %s", exc)
                break
        try:
            cv2.destroyWindow(_PREVIEW_WINDOW)
        except cv2.error:
            pass

    def _pump_preview(
        self,
        frame_bgr: np.ndarray,
        lines: tuple[str, ...],
        bbox_xyxy: tuple[float, float, float, float] | None = None,
    ) -> None:
        if not self._show_preview or self._preview_gui_broken:
            return
        try:
            vis = _compose_preview_frame(frame_bgr, lines, bbox_xyxy)
            cv2.namedWindow(_PREVIEW_WINDOW, cv2.WINDOW_AUTOSIZE)
            cv2.imshow(_PREVIEW_WINDOW, vis)
            cv2.waitKey(1)
        except cv2.error as exc:
            self._preview_gui_broken = True
            self._log.warning(
                "OpenCV sin soporte GUI (p. ej. paquete headless): vista previa desactivada. "
                "Instala opencv-python o ejecuta con --no-preview. Detalle: %s",
                exc,
            )

    def _preview_recognizing(self, frame_bgr: np.ndarray) -> None:
        self._pump_preview(frame_bgr, ("Reconociendo objeto...",), None)

    def show_classification_preview(self, classification: ClassificationOutput) -> None:
        if not self._show_preview or self._preview_gui_broken or self._last_bgr is None:
            return
        lines: list[str] = [
            "Clasificacion lista",
            f"Categoria: {classification.category.value}",
            f"Confianza: {classification.confidence:.0%}",
        ]
        if classification.raw_label:
            lines.append(f"YOLO: {classification.raw_label}")
        self._pump_preview(self._last_bgr, tuple(lines), classification.bbox_xyxy)
        if self._preview_gui_broken:
            return
        if self._preview_result_ms > 0:
            try:
                cv2.waitKey(self._preview_result_ms)
            except cv2.error:
                self._preview_gui_broken = True
                return
        try:
            cv2.destroyWindow(_PREVIEW_WINDOW)
        except cv2.error:
            pass

    def capture_image_bytes(self) -> bytes:
        cap = self._ensure_capture()
        if self._show_preview and not self._preview_gui_broken and self._placement_preview_ms > 0:
            self._run_placement_preview(cap)
        ok, frame = cap.read()
        if not ok or frame is None:
            raise RuntimeError("Fallo al leer frame de la cámara")
        self._last_bgr = frame.copy()
        if self._show_preview and not self._preview_gui_broken:
            if self._placement_preview_ms <= 0:
                self._preview_recognizing(frame)
                for _ in range(12):
                    cv2.waitKey(50)
            else:
                self._pump_preview(frame, ("Capturando...",), None)
                cv2.waitKey(250)
        params = [int(cv2.IMWRITE_JPEG_QUALITY), self._jpeg_quality]
        success, buf = cv2.imencode(".jpg", frame, params)
        if not success or buf is None:
            raise RuntimeError("Fallo al codificar imagen JPEG")
        return buf.tobytes()

    def end_cycle_release_for_next_trigger(self) -> None:
        """Cierra la ventana OpenCV y suelta la camara hasta el proximo ciclo (tras ENTER / serial)."""
        try:
            cv2.destroyWindow(_PREVIEW_WINDOW)
        except cv2.error:
            pass
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._last_bgr = None

    def release(self) -> None:
        self.end_cycle_release_for_next_trigger()
