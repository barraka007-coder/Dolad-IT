import time
from dataclasses import asdict

from PySide6.QtWidgets import QApplication

from voicestudio.gui import MainWindow
from voicestudio.settings import Store, VoiceSettings


def wait_until(app, condition, seconds=30):
    deadline = time.monotonic() + seconds
    while not condition():
        app.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("GUI worker timed out")
        time.sleep(.01)
    app.processEvents()


def test_gui_scans_batches_and_restores(tmp_path, sample):
    import shutil
    app = QApplication.instance() or QApplication([])
    source, dest = tmp_path / "vstup", tmp_path / "výstup"
    source.mkdir()
    shutil.copy(sample, source / "České jméno.wav")
    store = Store(tmp_path / "settings")
    window = MainWindow(store)
    errors = []
    window.show_error = errors.append
    window.show()
    wait_until(app, lambda: window.worker is None and window.tools is not None)
    window.input_path.setText(str(source))
    window.output_path.setText(str(dest))
    ticks = []
    from PySide6.QtCore import QTimer
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(5)
    window.scan_files()
    wait_until(app, lambda: window.worker is None)
    assert window.table.rowCount() == 1
    assert window.preview_button.isEnabled()
    assert window.track.currentData() == 0
    window.play_preview()
    wait_until(app, lambda: window.worker is None)
    assert window.preview_paths and all(p.exists() for p in window.preview_paths)
    assert window.compare.isEnabled()
    window.player.pause()
    window.compare.setChecked(False)
    assert window.player.source().toLocalFile().endswith("original.wav")
    window.compare.setChecked(True)
    assert window.player.source().toLocalFile().endswith("processed.wav")
    window.scan_files(True)
    wait_until(app, lambda: window.worker is None and not window.is_batch)
    assert (dest / "České jméno_voice.wav").exists()
    assert "Hotovo: 1" in window.summary.text()
    assert ticks  # GUI event loop continues while FFmpeg runs.
    assert not errors
    window.sliders["pitch"].setValue(-12)
    window.close()
    restored = MainWindow(Store(store.root))
    restored.show_error = errors.append
    wait_until(app, lambda: restored.worker is None and restored.tools is not None)
    assert restored.sliders["pitch"].value() == -12
    assert restored.input_path.text() == str(source)
    restored.scan_files()
    wait_until(app, lambda: restored.worker is None)
    (source / "České jméno.wav").unlink()
    restored.play_preview()
    assert errors and "není dostupný" in errors[-1]
    restored.close()
    timer.stop()
