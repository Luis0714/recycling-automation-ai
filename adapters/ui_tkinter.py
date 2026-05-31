from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageTk
from tkinter import Label, Tk

_DEFAULT_BACKGROUND = Path("asset/dashboard.png")
_WINDOW_TITLE = "RECICLAJE INTELIGENTE"
_SCREEN_MARGIN_PX = 48
_TASKBAR_RESERVE_PX = 64
_VIDEO_LABEL_POS = (54, 210)
_DETECTION_IMAGE_POS = (1100, 580)
_CLASSIFICATION_TEXT_POS = (1180, 280)
_CONFIDENCE_TEXT_POS = (1180, 430)
_VIDEO_DISPLAY_MAX_WIDTH = 1044


def _fit_window_to_content(root: Tk, content_width: int, content_height: int) -> None:
    """Ajusta el tamaño exterior para que el área útil coincida con la imagen."""
    root.geometry(f"{content_width}x{content_height}")
    root.update_idletasks()

    for _ in range(8):
        client_width = root.winfo_width()
        client_height = root.winfo_height()
        if client_width >= content_width and client_height >= content_height:
            return

        extra_width = max(0, content_width - client_width)
        extra_height = max(0, content_height - client_height)
        outer_size = root.geometry().split("+", maxsplit=1)[0]
        outer_width, outer_height = (int(value) for value in outer_size.split("x"))
        root.geometry(f"{outer_width + extra_width}x{outer_height + extra_height}")
        root.update_idletasks()


def _resolve_display_size(
    image_width: int,
    image_height: int,
    *,
    screen_width: int,
    screen_height: int,
) -> tuple[int, int]:
    max_width = max(320, screen_width - _SCREEN_MARGIN_PX)
    max_height = max(240, screen_height - _SCREEN_MARGIN_PX - _TASKBAR_RESERVE_PX)
    if image_width <= max_width and image_height <= max_height:
        return image_width, image_height

    scale = min(max_width / image_width, max_height / image_height)
    return int(image_width * scale), int(image_height * scale)


class RecyclingTkWindow:
    """Ventana principal Tkinter para la interfaz de reciclaje."""

    def __init__(
        self,
        *,
        background_path: Path | str = _DEFAULT_BACKGROUND,
        title: str = _WINDOW_TITLE,
    ) -> None:
        self._background_path = Path(background_path)
        self._title = title
        self._root: Tk | None = None
        self._background_ref: ImageTk.PhotoImage | None = None
        self._content_width = 0
        self._content_height = 0
        self._layout_scale = 1.0
        self._video_label: Label | None = None
        self._detection_label: Label | None = None
        self._classification_label: Label | None = None
        self._confidence_label: Label | None = None

    @property
    def root(self) -> Tk:
        if self._root is None:
            raise RuntimeError("La ventana no está abierta. Llama a run() primero.")
        return self._root

    @property
    def content_size(self) -> tuple[int, int]:
        return self._content_width, self._content_height

    @property
    def layout_scale(self) -> float:
        return self._layout_scale

    @property
    def scaled_video_max_width(self) -> int:
        return max(160, int(_VIDEO_DISPLAY_MAX_WIDTH * self._layout_scale))

    @property
    def video_label(self) -> Label:
        return self._video_label or self.root

    @property
    def detection_label(self) -> Label:
        return self._detection_label or self.root

    @property
    def classification_label(self) -> Label:
        return self._classification_label or self.root

    @property
    def confidence_label(self) -> Label:
        return self._confidence_label or self.root

    def run(
        self,
        *,
        on_ready: Callable[["RecyclingTkWindow"], None] | None = None,
    ) -> None:
        """Crea la ventana, monta el layout base y entra en mainloop()."""
        root = Tk()
        self._root = root
        root.title(self._title)
        root.resizable(False, False)

        self._mount_background(root)
        self._mount_content_labels(root)
        _fit_window_to_content(root, self._content_width, self._content_height)

        if on_ready is not None:
            on_ready(self)

        root.mainloop()

    def _load_background_pil_image(self) -> Image.Image:
        if not self._background_path.is_file():
            raise FileNotFoundError(
                f"No se encontró la imagen de fondo: {self._background_path.resolve()}"
            )
        return Image.open(self._background_path).convert("RGB")

    def _mount_background(self, root: Tk) -> None:
        pil_image = self._load_background_pil_image()
        image_width, image_height = pil_image.size
        display_width, display_height = _resolve_display_size(
            image_width,
            image_height,
            screen_width=root.winfo_screenwidth(),
            screen_height=root.winfo_screenheight(),
        )

        if (display_width, display_height) != (image_width, image_height):
            pil_image = pil_image.resize(
                (display_width, display_height),
                Image.Resampling.LANCZOS,
            )

        self._content_width = display_width
        self._content_height = display_height
        self._layout_scale = display_width / image_width

        background_image = ImageTk.PhotoImage(pil_image)
        self._background_ref = background_image

        background = Label(root, image=background_image, borderwidth=0)
        background.place(x=0, y=0, width=display_width, height=display_height)

    def _mount_content_labels(self, root: Tk) -> None:
        video_x, video_y = _VIDEO_LABEL_POS
        detection_x, detection_y = _DETECTION_IMAGE_POS
        classification_x, classification_y = _CLASSIFICATION_TEXT_POS
        confidence_x, confidence_y = _CONFIDENCE_TEXT_POS
        scale = self._layout_scale

        self._video_label = Label(root, borderwidth=0, bg="#0b0d0b")
        self._video_label.place(x=int(video_x * scale), y=int(video_y * scale))

        self._detection_label = Label(root, borderwidth=0, bg="#0b0d0b")
        self._detection_label.place(x=int(detection_x * scale), y=int(detection_y * scale))

        self._classification_label = Label(
            root,
            borderwidth=0,
            bg="#0b0d0b",
            fg="#4ade80",
            font=("Segoe UI", max(12, int(18 * scale)), "bold"),
        )
        self._classification_label.place(x=int(classification_x * scale), y=int(classification_y * scale))

        self._confidence_label = Label(
            root,
            borderwidth=0,
            bg="#0b0d0b",
            fg="#4ade80",
            font=("Segoe UI", max(12, int(18 * scale)), "bold"),
        )
        self._confidence_label.place(x=int(confidence_x * scale), y=int(confidence_y * scale))
