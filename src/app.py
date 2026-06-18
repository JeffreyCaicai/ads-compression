from __future__ import annotations

import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

from localization import Localizer, detect_system_language
from settings import default_logs_dir
from ui_main import CompressorWindow


def configure_logging() -> Path:
    logs_dir = default_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    logging.info("Application started.")
    return log_path


def install_exception_hook() -> None:
    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.error(
            "Unhandled exception:\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
        )
        try:
            localizer = Localizer(detect_system_language())
            messagebox.showerror(
                localizer.t("app.title"),
                localizer.t("message.unhandled_error", error=exc_value),
            )
        except Exception:
            pass

    sys.excepthook = handle_exception


def run() -> None:
    configure_logging()
    install_exception_hook()
    app = CompressorWindow()
    app.mainloop()
