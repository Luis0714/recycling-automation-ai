import logging
import sys
from collections.abc import Callable

import cv2
import numpy as np
from PIL import Image, ImageTk
from tkinter import Label, Tk

_log = logging.getLogger("ras.camera_tkinter")
_DEFAULT_FRAME_WIDTH = 1280
_DEFAULT_FRAME_HEIGHT = 720
_DEFAULT_MAX_DISPLAY_WIDTH = 840
_DEFAULT_UPDATE_INTERVAL_MS = 10


def _resize_rgb_frame(frame_rgb: np.ndarray, max_width: int) -> np.ndarray:
    height, width = frame_rgb.shape[:2]
    if width <= max_width:
        return frame_rgb
    scale = max_width / width
    return cv2.resize(
        frame_rgb,
        (max_width, int(height * scale)),
        interpolation=cv2.INTER_AREA,
    )


def _open_video_capture(device_index: int) -> cv2.VideoCapture:
    if sys.platform == "win32":
        capture = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
    else:
        capture = cv2.VideoCapture(device_index)

    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"No se pudo abrir la cámara en el índice {device_index}")

    capture.set(cv2.CAP_PROP_FRAME_WIDTH, _DEFAULT_FRAME_WIDTH)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, _DEFAULT_FRAME_HEIGHT)
    return capture


class TkinterCameraFeed:
    """Captura video con OpenCV y lo muestra en un Label de Tkinter."""

    def __init__(
        self,
        *,
        video_label: Label,
        root: Tk,
        device_index: int = 0,
        max_display_width: int = _DEFAULT_MAX_DISPLAY_WIDTH,
        update_interval_ms: int = _DEFAULT_UPDATE_INTERVAL_MS,
    ) -> None:
        if max_display_width <= 0:
            raise ValueError("max_display_width debe ser mayor que 0")
        if update_interval_ms <= 0:
            raise ValueError("update_interval_ms debe ser mayor que 0")

        self._video_label = video_label
        self._root = root
        self._device_index = device_index
        self._max_display_width = max_display_width
        self._update_interval_ms = update_interval_ms
        self._capture: cv2.VideoCapture | None = None
        self._photo_ref: ImageTk.PhotoImage | None = None
        self._last_frame_bgr: np.ndarray | None = None
        self._is_running = False
        self._update_job: str | None = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def last_frame_bgr(self) -> np.ndarray | None:
        return None if self._last_frame_bgr is None else self._last_frame_bgr.copy()

    def start(self) -> None:
        if self._is_running:
            return

        self._capture = _open_video_capture(self._device_index)
        self._is_running = True
        _log.info("Cámara iniciada en índice %s", self._device_index)
        self._schedule_next_frame()

    def stop(self) -> None:
        self._is_running = False
        if self._update_job is not None:
            try:
                self._root.after_cancel(self._update_job)
            except Exception:
                pass
            self._update_job = None

    def release(self) -> None:
        self.stop()
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._last_frame_bgr = None
        self._photo_ref = None
        self._video_label.configure(image="")
        _log.info("Cámara liberada")

    def _schedule_next_frame(self) -> None:
        if not self._is_running:
            return
        self._update_job = self._root.after(
            self._update_interval_ms,
            self._update_frame,
        )

    def _update_frame(self) -> None:
        if not self._is_running or self._capture is None:
            return

        has_frame, frame_bgr = self._capture.read()
        if not has_frame or frame_bgr is None:
            _log.warning("No se pudo leer frame de la cámara")
            self._schedule_next_frame()
            return

        self._last_frame_bgr = frame_bgr
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_rgb = _resize_rgb_frame(frame_rgb, self._max_display_width)
        photo = ImageTk.PhotoImage(Image.fromarray(frame_rgb))

        self._photo_ref = photo
        self._video_label.configure(image=photo)

        self._schedule_next_frame()


def attach_camera_feed(
    window: object,
    *,
    device_index: int = 0,
    max_display_width: int = _DEFAULT_MAX_DISPLAY_WIDTH,
    update_interval_ms: int = _DEFAULT_UPDATE_INTERVAL_MS,
) -> TkinterCameraFeed:
    """Conecta la cámara al label de video de una ventana Tkinter."""
    root = window.root
    feed = TkinterCameraFeed(
        video_label=window.video_label,
        root=root,
        device_index=device_index,
        max_display_width=max_display_width,
        update_interval_ms=update_interval_ms,
    )
    feed.start()
    root.protocol("WM_DELETE_WINDOW", _build_close_handler(root, feed))
    return feed


def _build_close_handler(root: Tk, feed: TkinterCameraFeed) -> Callable[[], None]:
    def on_close() -> None:
        feed.release()
        root.destroy()

    return on_close
