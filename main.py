from adapters.camera_tkinter import attach_camera_feed
from adapters.ui_tkinter import RecyclingTkWindow

_CAMERA_DEVICE_INDEX = 0


def main() -> None:
    window = RecyclingTkWindow()

    def on_window_ready(app_window: RecyclingTkWindow) -> None:
        attach_camera_feed(
            app_window,
            device_index=_CAMERA_DEVICE_INDEX,
            max_display_width=app_window.scaled_video_max_width,
        )

    window.run(on_ready=on_window_ready)


if __name__ == "__main__":
    main()
