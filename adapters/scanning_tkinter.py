import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import cv2
import torch
from PIL import Image, ImageTk
from tkinter import Label, Tk
from ultralytics import YOLO

from domain.model_loader import resolve_yolo_model_path
from domain.waste_classes import WASTE_CLASS_BY_ID
from domain.waste_mapping import resolve_waste_mapping_by_id

_log = logging.getLogger("ras.scanning")
_DISPLAY_WIDTH = 1044
_FRAME_WIDTH = 1280
_FRAME_HEIGHT = 720
_WARMUP_FRAMES = 3
_SCAN_DURATION_S = 8.0
_SCAN_TICK_MS = 33
_YOLO_INTERVAL_S = 0.15
_MIN_DETECTION_CONFIDENCE = 0.35

OnScanResult = Callable[
    [str | None, int | None, str | None, str | None],
    None,
]
OnScanComplete = Callable[[str | None], None]


@dataclass
class _FrameDetection:
    class_id: int
    x1: int
    y1: int
    x2: int
    y2: int
    label_name: str
    confidence_percent: int
    model_class_name: str
    color_bgr: tuple[int, int, int]
    confidence: float


@dataclass
class _BestDetection:
    class_id: int
    model_class_name: str
    confidence_percent: int
    display_category: str
    arduino_command: str


def _resolve_yolo_device(yolo_device: str | int | None) -> str | int:
    if yolo_device is not None:
        return yolo_device
    if torch.cuda.is_available():
        return 0
    return "cpu"


def _log_yolo_device(yolo_device: str | int) -> None:
    if yolo_device == "cpu":
        _log.warning(
            "YOLO en CPU (CUDA no disponible). Instala PyTorch con CUDA para más velocidad."
        )
        return
    gpu_name = torch.cuda.get_device_name(int(yolo_device))
    _log.info("YOLO usando GPU cuda:%s (%s)", yolo_device, gpu_name)


def _resize_display_frame(frame_rgb, display_width: int):
    height, width = frame_rgb.shape[:2]
    if width <= display_width:
        return frame_rgb
    scale = display_width / width
    return cv2.resize(
        frame_rgb,
        (display_width, int(height * scale)),
        interpolation=cv2.INTER_LINEAR,
    )


def _open_capture(device_index: int) -> cv2.VideoCapture:
    if sys.platform == "win32":
        capture = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
    else:
        capture = cv2.VideoCapture(device_index)

    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"No se pudo abrir la cámara en el índice {device_index}")

    capture.set(cv2.CAP_PROP_FRAME_WIDTH, _FRAME_WIDTH)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, _FRAME_HEIGHT)
    return capture


def _rgb_to_bgr(color_rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    red, green, blue = color_rgb
    return blue, green, red


def _draw_detection(
    frame_bgr,
    *,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    class_name: str,
    confidence_percent: int,
    color_bgr: tuple[int, int, int],
) -> None:
    text = f"{class_name} {confidence_percent}%"
    (text_width, text_height), baseline = cv2.getTextSize(
        text,
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        2,
    )
    cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), color_bgr, 2)
    cv2.rectangle(
        frame_bgr,
        (x1, y1 - text_height - baseline),
        (x1 + text_width, y1 + baseline),
        (0, 0, 0),
        cv2.FILLED,
    )
    cv2.putText(
        frame_bgr,
        text,
        (x1, y1 - 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        color_bgr,
        2,
    )


class TkinterYoloScanner:
    """YOLO disparado por Arduino: un ciclo de cámara por cada DETECTED."""

    def __init__(
        self,
        *,
        video_label: Label,
        root: Tk,
        on_result: OnScanResult,
        model_path: str | Path | None = None,
        device_index: int = 0,
        display_width: int = _DISPLAY_WIDTH,
        yolo_device: str | int | None = None,
    ) -> None:
        resolved_model_path = resolve_yolo_model_path(model_path)

        self._video_label = video_label
        self._root = root
        self._on_result = on_result
        self._device_index = device_index
        self._display_width = display_width
        self._yolo_device = _resolve_yolo_device(yolo_device)
        self._model = YOLO(str(resolved_model_path))
        self._photo_ref: ImageTk.PhotoImage | None = None
        self._is_running = False
        self._is_scanning = False
        self._scan_job: str | None = None
        self._scan_capture: cv2.VideoCapture | None = None
        self._scan_on_complete: OnScanComplete | None = None
        self._scan_started_at: float = 0.0
        self._scan_last_yolo_at: float = 0.0
        self._scan_best: _BestDetection | None = None
        self._scan_last_detections: list[_FrameDetection] = []
        self._scan_class_scores: dict[int, float] = {}
        self._scan_class_peak_confidence: dict[int, float] = {}
        _log.info("Modelo YOLO cargado: %s", resolved_model_path)
        _log.info("Clases del modelo: %s", self._model.names)
        _log_yolo_device(self._yolo_device)
        _log.info("Cámara inactiva — esperando DETECTED del Arduino")

    def start(self) -> None:
        if self._is_running:
            return
        self._is_running = True

    def stop(self) -> None:
        self._is_running = False
        self._cancel_scan_job()
        self._close_scan_capture()

    def release(self) -> None:
        self.stop()
        self.clear_video()
        self._on_result(None, None, None, None)

    def clear_video(self) -> None:
        self._photo_ref = None
        self._video_label.configure(image="")

    def scan_once(self, *, on_complete: OnScanComplete | None = None) -> None:
        """Abre cámara 8 s, detecta en vivo con bbox y cierra. Disparado por Arduino."""
        if not self._is_running or self._is_scanning:
            return

        self._is_scanning = True
        self._scan_on_complete = on_complete
        self._scan_best = None
        self._scan_last_detections = []
        self._scan_class_scores = {}
        self._scan_class_peak_confidence = {}

        try:
            _log.info("Abriendo cámara — escaneo de %.0f s", _SCAN_DURATION_S)
            self._scan_capture = _open_capture(self._device_index)
            self._warmup_capture(self._scan_capture)
            self._scan_started_at = time.monotonic()
            self._scan_last_yolo_at = 0.0
            self._scan_tick()
        except Exception as exc:
            _log.error("Error iniciando escaneo: %s", exc)
            self._finish_scan_session(arduino_command=None)

    def _warmup_capture(self, capture: cv2.VideoCapture) -> None:
        for _ in range(_WARMUP_FRAMES):
            capture.read()

    def _cancel_scan_job(self) -> None:
        if self._scan_job is not None:
            try:
                self._root.after_cancel(self._scan_job)
            except Exception:
                pass
            self._scan_job = None

    def _close_scan_capture(self) -> None:
        if self._scan_capture is not None:
            self._scan_capture.release()
            self._scan_capture = None

    def _scan_tick(self) -> None:
        if not self._is_scanning or self._scan_capture is None:
            return

        elapsed_s = time.monotonic() - self._scan_started_at
        if elapsed_s >= _SCAN_DURATION_S:
            self._finalize_best_from_votes()
            self._finish_scan_session(
                arduino_command=(
                    self._scan_best.arduino_command if self._scan_best else None
                ),
            )
            return

        has_frame, frame_bgr = self._scan_capture.read()
        if not has_frame or frame_bgr is None:
            self._schedule_scan_tick()
            return

        frame_to_show = frame_bgr.copy()
        now = time.monotonic()
        did_run_yolo = now - self._scan_last_yolo_at >= _YOLO_INTERVAL_S
        if did_run_yolo:
            self._scan_last_yolo_at = now
            self._scan_last_detections = self._detect_on_frame(frame_bgr)
            self._update_best_detection(self._scan_last_detections)

        if self._scan_last_detections:
            self._draw_detections(frame_to_show, self._scan_last_detections)
        self._show_frame(frame_to_show)
        self._update_live_result()
        self._schedule_scan_tick()

    def _schedule_scan_tick(self) -> None:
        if not self._is_scanning:
            return
        self._scan_job = self._root.after(_SCAN_TICK_MS, self._scan_tick)

    def _finish_scan_session(self, *, arduino_command: str | None) -> None:
        self._cancel_scan_job()
        self._close_scan_capture()
        self._is_scanning = False

        if self._scan_best is not None:
            best = self._scan_best
            self._on_result(
                best.model_class_name,
                best.confidence_percent,
                best.display_category,
                best.arduino_command,
            )
            _log.info(
                "Clasificación final: %s → %s (%s%%) | votos=%s",
                best.model_class_name,
                best.arduino_command,
                best.confidence_percent,
                {
                    resolve_waste_mapping_by_id(class_id).model_name: round(score, 2)
                    for class_id, score in self._scan_class_scores.items()
                    if resolve_waste_mapping_by_id(class_id) is not None
                },
            )
            arduino_command = best.arduino_command
        else:
            self._clear_detection_state()
            _log.warning("YOLO no detectó ningún objeto en %.0f s", _SCAN_DURATION_S)

        _log.info("Cámara cerrada — escaneo finalizado")
        on_complete = self._scan_on_complete
        self._scan_on_complete = None
        if on_complete is not None:
            on_complete(arduino_command)

        _log.info("Esperando próxima detección Arduino")

    def _detect_on_frame(self, frame_bgr) -> list[_FrameDetection]:
        detections: list[_FrameDetection] = []

        results = self._model(
            frame_bgr,
            stream=True,
            verbose=False,
            device=self._yolo_device,
            conf=_MIN_DETECTION_CONFIDENCE,
        )
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                class_id = int(box.cls[0])
                category_mapping = resolve_waste_mapping_by_id(class_id)
                class_style = WASTE_CLASS_BY_ID.get(class_id)
                if category_mapping is None or class_style is None:
                    continue

                confidence = float(box.conf[0])
                if confidence < _MIN_DETECTION_CONFIDENCE:
                    continue

                model_class_name = self._model.names.get(class_id, class_style.name)
                x1, y1, x2, y2 = box.xyxy[0]
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                x1, y1, x2, y2 = max(0, x1), max(0, y1), max(0, x2), max(0, y2)

                confidence_percent = int(confidence * 100)
                detections.append(
                    _FrameDetection(
                        class_id=class_id,
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                        label_name=category_mapping.display_category,
                        confidence_percent=confidence_percent,
                        model_class_name=model_class_name,
                        color_bgr=_rgb_to_bgr(class_style.bbox_color_rgb),
                        confidence=confidence,
                    )
                )

        return detections

    def _draw_detections(
        self,
        frame_bgr,
        detections: list[_FrameDetection],
    ) -> None:
        for detection in detections:
            _draw_detection(
                frame_bgr,
                x1=detection.x1,
                y1=detection.y1,
                x2=detection.x2,
                y2=detection.y2,
                class_name=detection.label_name,
                confidence_percent=detection.confidence_percent,
                color_bgr=detection.color_bgr,
            )

    def _update_best_detection(self, detections: list[_FrameDetection]) -> None:
        for detection in detections:
            category_mapping = resolve_waste_mapping_by_id(detection.class_id)
            if category_mapping is None:
                continue

            class_id = detection.class_id
            self._scan_class_scores[class_id] = (
                self._scan_class_scores.get(class_id, 0.0) + detection.confidence
            )
            peak = self._scan_class_peak_confidence.get(class_id, 0.0)
            if detection.confidence > peak:
                self._scan_class_peak_confidence[class_id] = detection.confidence

        self._finalize_best_from_votes()

    def _finalize_best_from_votes(self) -> None:
        if not self._scan_class_scores:
            self._scan_best = None
            return

        best_class_id = max(
            self._scan_class_scores,
            key=lambda class_id: (
                self._scan_class_scores[class_id],
                self._scan_class_peak_confidence.get(class_id, 0.0),
            ),
        )
        category_mapping = resolve_waste_mapping_by_id(best_class_id)
        if category_mapping is None:
            self._scan_best = None
            return

        peak_confidence = self._scan_class_peak_confidence.get(best_class_id, 0.0)
        self._scan_best = _BestDetection(
            class_id=best_class_id,
            model_class_name=category_mapping.model_name,
            confidence_percent=int(peak_confidence * 100),
            display_category=category_mapping.display_category,
            arduino_command=category_mapping.arduino_command,
        )

    def _update_live_result(self) -> None:
        if self._scan_best is None:
            return
        best = self._scan_best
        self._on_result(
            best.model_class_name,
            best.confidence_percent,
            best.display_category,
            best.arduino_command,
        )

    def _clear_detection_state(self) -> None:
        self._on_result(None, None, None, None)

    def _show_frame(self, frame_bgr) -> None:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_rgb = _resize_display_frame(frame_rgb, self._display_width)
        photo = ImageTk.PhotoImage(
            Image.fromarray(frame_rgb),
            master=self._root,
        )
        self._photo_ref = photo
        self._video_label.configure(image=photo)


def attach_yolo_scanner(
    window: object,
    *,
    model_path: str | Path | None = None,
    device_index: int = 0,
    display_width: int = _DISPLAY_WIDTH,
    yolo_device: str | int | None = None,
    on_shutdown: Callable[[], None] | None = None,
) -> TkinterYoloScanner:
    root = window.root

    def on_result(
        model_class_name: str | None,
        confidence_percent: int | None,
        display_category: str | None,
        arduino_command: str | None,
    ) -> None:
        if (
            display_category is None
            or confidence_percent is None
            or model_class_name is None
        ):
            window.clear_detection()
            return
        window.set_detection(
            display_category,
            confidence_percent,
            arduino_command=arduino_command,
        )

    scanner = TkinterYoloScanner(
        video_label=window.video_label,
        root=root,
        on_result=on_result,
        model_path=model_path,
        device_index=device_index,
        display_width=display_width,
        yolo_device=yolo_device,
    )
    scanner.start()
    root.protocol(
        "WM_DELETE_WINDOW",
        _build_close_handler(root, scanner, on_shutdown),
    )
    return scanner


def _build_close_handler(
    root: Tk,
    scanner: TkinterYoloScanner,
    on_shutdown: Callable[[], None] | None = None,
) -> Callable[[], None]:
    def on_close() -> None:
        if on_shutdown is not None:
            on_shutdown()
        scanner.release()
        root.destroy()

    return on_close
