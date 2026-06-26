from pathlib import Path
import sys

from app.core.app_context import AppContext
from app.ui.main_window import MainWindow


def get_app_dir() -> Path:
    if getattr(
        sys,
        "frozen",
        False,
    ):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


def main():

    base_dir = get_app_dir()

    context = AppContext(
        base_dir=base_dir,
        settings_path=base_dir / "settings.json",
    )

    window = MainWindow(context)

    window.mainloop()


if __name__ == "__main__":
    main()
