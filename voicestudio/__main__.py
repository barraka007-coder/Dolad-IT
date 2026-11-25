import logging
from logging.handlers import RotatingFileHandler
from . import APP_TITLE
from .settings import data_directory


def main():
    directory = data_directory()
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / "voice-studio.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.info("Spouštím %s", APP_TITLE)
    from .gui import run_gui
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
