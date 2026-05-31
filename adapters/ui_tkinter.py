from pathlib import Path
from tkinter import Label, Tk
from tkinter import PhotoImage as TkPhotoImage

from PIL import Image, ImageTk

_DEFAULT_BACKGROUND = Path("asset/dashboard.png")
_WINDOW_TITLE = "RECICLAJE INTELIGENTE"
_WINDOW_GEOMETRY = "1280x720"
_VIDEO_LABEL_POS = (320, 180)
_DETECTION_IMAGE_POS = (75, 260)
_CLASSIFICATION_TEXT_POS = (995, 310)


class RecyclingTkWindow:
    """Ventana principal Tkinter para la interfaz de reciclaje."""

    def __init__(
        self,
        *,
        background_path: Path | str = _DEFAULT_BACKGROUND,
        title: str = _WINDOW_TITLE,
        geometry: str = _WINDOW_GEOMETRY,
    ) -> None:
        self._background_path = Path(background_path)
        self._title = title
        self._geometry = geometry
        self._root: Tk | None = None
        self._background_ref: TkPhotoImage | ImageTk.PhotoImage | None = None
        self._video_label: Label | None = None
        self._detection_label: Label | None = None
        self._classification_label: Label | None = None

    @property
    def root(self) -> Tk:
        if self._root is None:
            raise RuntimeError("La ventana no está abierta. Llama a run() primero.")
        return self._root

    @property
    def video_label(self) -> Label:
        return self._video_label or self.root

    @property
    def detection_label(self) -> Label:
        return self._detection_label or self.root

    @property
    def classification_label(self) -> Label:
        return self._classification_label or self.root

    def run(self) -> None:
        """Crea la ventana, monta el layout base y entra en mainloop()."""
        root = Tk()
        self._root = root
        root.title(self._title)
        root.geometry(self._geometry)
        root.resizable(False, False)

        self._mount_background(root)
        self._mount_content_labels(root)

        root.mainloop()

    def _mount_background(self, root: Tk) -> None:
        if not self._background_path.is_file():
            raise FileNotFoundError(
                f"No se encontró la imagen de fondo: {self._background_path.resolve()}"
            )

        suffix = self._background_path.suffix.lower()
        if suffix == ".png":
            background_image = TkPhotoImage(file=str(self._background_path))
            self._background_ref = background_image
        else:
            pil_image = Image.open(self._background_path)
            background_image = ImageTk.PhotoImage(pil_image)
            self._background_ref = background_image

        background = Label(root, image=background_image)
        background.place(x=0, y=0, relwidth=1, relheight=1)

    def _mount_content_labels(self, root: Tk) -> None:
        video_x, video_y = _VIDEO_LABEL_POS
        detection_x, detection_y = _DETECTION_IMAGE_POS
        classification_x, classification_y = _CLASSIFICATION_TEXT_POS

        self._video_label = Label(root)
        self._video_label.place(x=video_x, y=video_y)

        self._detection_label = Label(root)
        self._detection_label.place(x=detection_x, y=detection_y)

        self._classification_label = Label(root)
        self._classification_label.place(x=classification_x, y=classification_y)
