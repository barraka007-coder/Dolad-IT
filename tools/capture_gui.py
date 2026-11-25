"""Render the real application over generated demo media for README screenshots."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QCoreApplication, QEvent, QSignalBlocker
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from voicestudio.engine import Tools, run
from voicestudio.gui import MainWindow, configure_app
from voicestudio.settings import Store


def wait(app, window, condition, errors, seconds=90):
    deadline = time.monotonic() + seconds
    while not condition():
        app.processEvents()
        if errors:
            raise RuntimeError("\n".join(errors))
        if time.monotonic() > deadline:
            raise TimeoutError("Příprava okna pro screenshot nedoběhla.")
        time.sleep(.01)
    app.processEvents()


def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=root / "docs" / "images" / "gui-v1.0.png")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    font = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts" / "segoeui.ttf"
    if font.is_file():
        QFontDatabase.addApplicationFont(str(font))
    configure_app(app)
    tools = Tools.find()
    with tempfile.TemporaryDirectory(prefix="dolad-it-screenshot-") as workspace:
        work = Path(workspace)
        source, destination = work / "vstup", work / "hotove"
        source.mkdir()
        video = source / "01-zapojeni-senzoru.mp4"
        run([str(tools.ffmpeg), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=6",
             "-f", "lavfi", "-i", "sine=frequency=140:sample_rate=48000:duration=6", "-c:v", "libx264",
             "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(video)])
        run([str(tools.ffmpeg), "-v", "error", "-i", str(video), "-vn", str(source / "02-nastaveni-aplikace.wav")])
        window = MainWindow(Store(work / "settings"))
        errors = []
        window.show_error = errors.append
        window.audio_output.setMuted(True)
        window.resize(1190, 850)
        window.show()
        app.processEvents()
        wait(app, window, lambda: window.worker is None and window.tools is not None, errors)
        window.input_path.setText(str(source))
        window.output_path.setText(str(destination))
        window.scan_files(True)
        wait(app, window, lambda: window.worker is None and not window.is_batch, errors)
        assert len(list(destination.iterdir())) == 2, window.summary.text()
        window.table.selectRow(0)
        window.play_preview()
        wait(app, window, lambda: window.worker is None, errors)
        assert window.preview_paths, errors
        window.player.pause()
        # Presentation-only paths: generated files were really scanned and processed above.
        with QSignalBlocker(window.input_path), QSignalBlocker(window.output_path):
            window.input_path.setText(r"C:\Videa\Tutoriály")
            window.output_path.setText(r"C:\Videa\Hotové")
        for index, media in enumerate(window.media):
            name = media.path.with_stem(media.path.stem + "_voice").name
            window.row_status(index, "Hotovo · " + name, name, "done")
        window.status.setText("Ukázka připravena · Původní i upravená verze mají stejnou cílovou hlasitost.")
        app.processEvents()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if not window.grab().save(str(args.output)):
            raise RuntimeError("Screenshot se nepodařilo uložit.")
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
    print(f"Screenshot: {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
