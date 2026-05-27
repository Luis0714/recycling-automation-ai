import logging
import math
import time
from pathlib import Path

import cv2
import numpy as np

from domain.models import ClassificationOutput

_PREVIEW_WINDOW = "RAS - Vista de camara"
_DASHBOARD_PATH = Path("asset/dashboard.png")
_FEED_TOP_LEFT = (20, 80)
_FEED_SIZE = (980, 560)  # width, height
_CLASS_BLOCK_POS = (1048, 168)
_CLASS_BLOCK_LINE_HEIGHT = 40
_CONF_BLOCK_POS = (1048, 338)
_INFO_BLOCK_POS = (1038, 428)
_INFO_BLOCK_LINE_HEIGHT = 42
_HISTORY_BLOCK_POS = (1038, 700)
_HISTORY_BLOCK_LINE_HEIGHT = 34


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


def _draw_dashboard_text(
    image_bgr: np.ndarray,
    text: str,
    position: tuple[int, int],
    *,
    font_scale: float = 0.75,
    color: tuple[int, int, int] = (230, 240, 255),
    shadow_color: tuple[int, int, int] = (20, 20, 20),
    thickness: int = 2,
) -> None:
    x, y = position
    cv2.putText(
        image_bgr,
        text,
        (x + 2, y + 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        shadow_color,
        thickness + 2,
        cv2.LINE_AA,
    )
    cv2.putText(
        image_bgr,
        text,
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


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
        self._dashboard_template: np.ndarray | None = None
        self._log = logging.getLogger("ras.camera")
        self._preview_gui_broken = False
        self._load_dashboard_template()

    def _load_dashboard_template(self) -> None:
        if not _DASHBOARD_PATH.exists():
            self._log.warning(
                "No se encontró el fondo de dashboard en %s. Se usará vista simple.",
                _DASHBOARD_PATH,
            )
            return
        template = cv2.imread(str(_DASHBOARD_PATH))
        if template is None:
            self._log.warning(
                "No se pudo cargar %s. Se usará vista simple.",
                _DASHBOARD_PATH,
            )
            return
        self._dashboard_template = template

    def _compose_dashboard_frame(
        self,
        frame_bgr: np.ndarray,
        lines: tuple[str, ...],
        bbox_xyxy: tuple[float, float, float, float] | None,
    ) -> np.ndarray:
        if self._dashboard_template is None:
            vis = frame_bgr.copy()
            if bbox_xyxy is not None:
                _draw_bbox_clamped(vis, bbox_xyxy)
            for index, line in enumerate(lines):
                _draw_dashboard_text(vis, line, (12, 32 + 34 * index))
            return vis

        dashboard = self._dashboard_template.copy()
        dashboard_h, dashboard_w = dashboard.shape[:2]
        feed_x, feed_y = _FEED_TOP_LEFT
        feed_w, feed_h = _FEED_SIZE
        feed_w = min(feed_w, max(1, dashboard_w - feed_x - 20))
        feed_h = min(feed_h, max(1, dashboard_h - feed_y - 20))
        feed = frame_bgr.copy()
        if bbox_xyxy is not None:
            _draw_bbox_clamped(feed, bbox_xyxy)
        feed = cv2.resize(feed, (feed_w, feed_h), interpolation=cv2.INTER_AREA)
        dashboard[feed_y : feed_y + feed_h, feed_x : feed_x + feed_w] = feed

        status_line = lines[0] if len(lines) > 0 else "Estado: --"
        class_line = lines[1] if len(lines) > 1 else "Clase detectada: --"
        category_line = lines[2] if len(lines) > 2 else "Categoria: --"
        confidence_line = lines[3] if len(lines) > 3 else "Confianza: --%"
        destination_line = lines[4] if len(lines) > 4 else "Destino: --"
        history_line = lines[5] if len(lines) > 5 else "Historial: esperando deteccion..."

        _draw_dashboard_text(
            dashboard,
            class_line,
            _CLASS_BLOCK_POS,
            font_scale=0.65,
        )
        _draw_dashboard_text(
            dashboard,
            category_line,
            (_CLASS_BLOCK_POS[0], _CLASS_BLOCK_POS[1] + _CLASS_BLOCK_LINE_HEIGHT),
            font_scale=0.6,
            color=(180, 225, 255),
        )

        _draw_dashboard_text(
            dashboard,
            confidence_line,
            _CONF_BLOCK_POS,
            font_scale=0.72,
        )

        info_lines = (
            status_line,
            destination_line,
            f"Objetos detectados: {1 if bbox_xyxy is not None else 0}",
            f"Resolucion: {frame_bgr.shape[1]}x{frame_bgr.shape[0]}",
        )
        for index, info_line in enumerate(info_lines):
            _draw_dashboard_text(
                dashboard,
                info_line,
                (_INFO_BLOCK_POS[0], _INFO_BLOCK_POS[1] + index * _INFO_BLOCK_LINE_HEIGHT),
                font_scale=0.58,
                color=(205, 225, 245),
            )

        history_lines = (
            history_line,
            f"Etiqueta YOLO: {class_line.split(':', 1)[-1].strip() or '--'}",
        )
        for index, history_text in enumerate(history_lines):
            _draw_dashboard_text(
                dashboard,
                history_text,
                (_HISTORY_BLOCK_POS[0], _HISTORY_BLOCK_POS[1] + index * _HISTORY_BLOCK_LINE_HEIGHT),
                font_scale=0.5,
                color=(175, 205, 235),
                thickness=1,
            )
        return dashboard

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
                "Estado: Colocando objeto",
                "Clase detectada: --",
                "Categoria: --",
                "Confianza: --%",
                f"Destino: Esperando captura ({sec_left}s)",
                "Historial: vista previa activa (ESC para capturar)",
            )
            vis = self._compose_dashboard_frame(frame, lines, None)
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
            vis = self._compose_dashboard_frame(frame_bgr, lines, bbox_xyxy)
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
        self._pump_preview(
            frame_bgr,
            (
                "Estado: Reconociendo objeto...",
                "Clase detectada: --",
                "Categoria: --",
                "Confianza: --%",
                "Destino: Evaluando",
                "Historial: inferencia en progreso",
            ),
            None,
        )

    def show_classification_preview(self, classification: ClassificationOutput) -> None:
        if not self._show_preview or self._preview_gui_broken or self._last_bgr is None:
            return
        destino = {
            "plastic": "BLANCO (Aprovechables)",
            "metal": "BLANCO (Aprovechables)",
            "organic": "VERDE (Organicos)",
            "unknown": "SIN APERTURA",
        }.get(classification.category.value, "SIN APERTURA")
        lines: list[str] = [
            "Estado: Clasificacion lista",
            f"Clase detectada: {classification.raw_label or '--'}",
            f"Categoria: {classification.category.value}",
            f"Confianza: {classification.confidence:.0%}",
            f"Destino: {destino}",
            "Historial: ultima deteccion completada",
        ]
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
                self._pump_preview(
                    frame,
                    (
                        "Estado: Capturando frame...",
                        "Clase detectada: --",
                        "Categoria: --",
                        "Confianza: --%",
                        "Destino: Pendiente",
                        "Historial: captura en curso",
                    ),
                    None,
                )
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
