import logging
import sys
from collections.abc import Callable
from pathlib import Path

import cv2
import torch
from PIL import Image, ImageTk
from tkinter import Label, Tk
from ultralytics import YOLO

from domain.waste_classes import WASTE_CLASS_BY_ID, _DEFAULT_MODEL_PATH
from domain.waste_mapping import resolve_waste_mapping, to_arduino_command

_log = logging.getLogger("ras.scanning")
_SCAN_INTERVAL_MS = 10
_DISPLAY_WIDTH = 1044
_FRAME_WIDTH = 1280
_FRAME_HEIGHT = 720
_WARMUP_FRAMES = 3

OnScanResult = Callable[
    [str | None, int | None, str | None, str | None],
    None,
]
OnScanComplete = Callable[[str | None], None]


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
    """YOLO + Tkinter. Modo continuo o disparado por Arduino (un ciclo por detección)."""

    def __init__(
        self,
        *,
        video_label: Label,
        root: Tk,
        on_result: OnScanResult,
        model_path: str | Path = _DEFAULT_MODEL_PATH,
        device_index: int = 0,
        display_width: int = _DISPLAY_WIDTH,
        yolo_device: str | int | None = None,
        arduino_triggered: bool = False,
    ) -> None:
        if not Path(model_path).is_file():
            raise FileNotFoundError(f"No se encontró el modelo YOLO: {model_path}")

        self._video_label = video_label
        self._root = root
        self._on_result = on_result
        self._device_index = device_index
        self._display_width = display_width
        self._yolo_device = _resolve_yolo_device(yolo_device)
        self._arduino_triggered = arduino_triggered
        self._model = YOLO(str(model_path))
        self._capture: cv2.VideoCapture | None = None
        self._photo_ref: ImageTk.PhotoImage | None = None
        self._is_running = False
        self._is_scanning = False
        self._scan_job: str | None = None
        self._latest_model_class: str | None = None
        self._latest_display_category: str | None = None
        self._latest_arduino_command: str | None = None
        _log.info("Modelo YOLO cargado: %s", model_path)
        _log_yolo_device(self._yolo_device)
        if self._arduino_triggered:
            _log.info("Modo Arduino: cámara inactiva hasta recibir DETECTED")

    def start(self) -> None:
        if self._is_running:
            return
        self._is_running = True
        if not self._arduino_triggered:
            self._capture = _open_capture(self._device_index)
            self._scan_continuous()

    def stop(self) -> None:
        self._is_running = False
        if self._scan_job is not None:
            try:
                self._root.after_cancel(self._scan_job)
            except Exception:
                pass
            self._scan_job = None

    def release(self) -> None:
        self.stop()
        self._release_capture()
        self._photo_ref = None
        self._video_label.configure(image="")
        self._latest_model_class = None
        self._latest_display_category = None
        self._latest_arduino_command = None
        self._on_result(None, None, None, None)

    def scan_once(self, *, on_complete: OnScanComplete | None = None) -> None:
        """Abre cámara, clasifica un frame y cierra. Disparado por Arduino."""
        if not self._is_running or self._is_scanning:
            return

        self._is_scanning = True
        arduino_command: str | None = None

        try:
            capture = _open_capture(self._device_index)
            frame_bgr = self._read_scan_frame(capture)
            capture.release()

            if frame_bgr is None:
                _log.warning("No se pudo capturar frame para clasificación")
                self._clear_detection_state()
                return

            arduino_command = self._classify_and_show(frame_bgr)
        except Exception as exc:
            _log.error("Error en escaneo disparado: %s", exc)
            self._clear_detection_state()
        finally:
            self._is_scanning = False
            if on_complete is not None:
                on_complete(arduino_command)

        _log.info("Escaneo finalizado — esperando próxima detección Arduino")

    def _release_capture(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def _read_scan_frame(self, capture: cv2.VideoCapture):
        for _ in range(_WARMUP_FRAMES):
            capture.read()

        has_frame, frame_bgr = capture.read()
        if not has_frame or frame_bgr is None:
            return None
        return frame_bgr

    def _clear_detection_state(self) -> None:
        self._latest_model_class = None
        self._latest_display_category = None
        self._latest_arduino_command = None
        self._on_result(None, None, None, None)

    def _classify_and_show(self, frame_bgr) -> str | None:
        has_detection = False
        best_class_name: str | None = None
        best_confidence_percent = 0

        results = self._model(
            frame_bgr,
            stream=True,
            verbose=False,
            device=self._yolo_device,
        )
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                class_id = int(box.cls[0])
                class_style = WASTE_CLASS_BY_ID.get(class_id)
                if class_style is None:
                    continue

                confidence = float(box.conf[0])
                if confidence <= 0:
                    continue

                x1, y1, x2, y2 = box.xyxy[0]
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                x1, y1, x2, y2 = max(0, x1), max(0, y1), max(0, x2), max(0, y2)

                confidence_percent = int(confidence * 100)
                category_mapping = resolve_waste_mapping(class_style.name)
                label_name = (
                    category_mapping.display_category
                    if category_mapping is not None
                    else class_style.name
                )
                _draw_detection(
                    frame_bgr,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    class_name=label_name,
                    confidence_percent=confidence_percent,
                    color_bgr=_rgb_to_bgr(class_style.bbox_color_rgb),
                )
                has_detection = True
                if confidence_percent > best_confidence_percent:
                    best_confidence_percent = confidence_percent
                    best_class_name = class_style.name

        arduino_command: str | None = None
        if has_detection and best_class_name is not None:
            category_mapping = resolve_waste_mapping(best_class_name)
            display_category = (
                category_mapping.display_category
                if category_mapping is not None
                else best_class_name
            )
            arduino_command = to_arduino_command(best_class_name)
            self._latest_model_class = best_class_name
            self._latest_display_category = display_category
            self._latest_arduino_command = arduino_command
            self._on_result(
                best_class_name,
                best_confidence_percent,
                display_category,
                arduino_command,
            )
        else:
            self._clear_detection_state()

        self._show_frame(frame_bgr)
        return arduino_command

    def _show_frame(self, frame_bgr) -> None:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_rgb = _resize_display_frame(frame_rgb, self._display_width)
        photo = ImageTk.PhotoImage(
            Image.fromarray(frame_rgb),
            master=self._root,
        )
        self._photo_ref = photo
        self._video_label.configure(image=photo)

    def _scan_continuous(self) -> None:
        if not self._is_running or self._capture is None:
            return

        has_frame, frame_bgr = self._capture.read()
        if not has_frame or frame_bgr is None:
            self._schedule_next_continuous_scan()
            return

        self._classify_and_show(frame_bgr)
        self._schedule_next_continuous_scan()

    def _schedule_next_continuous_scan(self) -> None:
        if not self._is_running:
            return
        self._scan_job = self._root.after(_SCAN_INTERVAL_MS, self._scan_continuous)


def attach_yolo_scanner(
    window: object,
    *,
    model_path: str | Path = _DEFAULT_MODEL_PATH,
    device_index: int = 0,
    display_width: int = _DISPLAY_WIDTH,
    yolo_device: str | int | None = None,
    arduino_triggered: bool = False,
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
        arduino_triggered=arduino_triggered,
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
