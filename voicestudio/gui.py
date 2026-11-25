from __future__ import annotations

import json
import logging
import tempfile
import threading
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QColor
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSlider,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import APP_NAME, APP_TITLE, __version__
from .engine import Job, Media, MediaError, Processor, Tools, run_batch, scan, validate_folders
from .settings import Store, VoiceSettings

LOG = logging.getLogger(__name__)


class Worker(QThread):
    event = Signal(object)

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.value = None
        self.error = None

    def run(self):
        try:
            self.value = self.task(lambda *args: self.event.emit(args))
        except Exception as exc:
            LOG.exception("Úloha selhala")
            self.error = str(exc)


class MainWindow(QMainWindow):
    def __init__(self, store: Store | None = None):
        super().__init__()
        self.store = store or Store()
        self.tools: Tools | None = None
        self.worker: Worker | None = None
        self.media: list[Media] = []
        self.stop_event = threading.Event()
        self.is_batch = False
        self.close_requested = False
        self.preview_dir = None
        self.preview_paths = None
        self.preview_key = None
        self.pending_position = 0
        self.autoplay = False
        self.setWindowTitle(APP_TITLE)
        self.resize(1190, 850)
        self.setMinimumSize(930, 700)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(.8)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.mediaStatusChanged.connect(self.player_ready)
        self.player.errorOccurred.connect(lambda *_: self.status.setText("Přehrávač: " + self.player.errorString()))
        self.build_ui()
        self.load_preferences()
        QTimer.singleShot(0, self.initialize_tools)

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 16, 20, 16)
        title = QLabel(APP_TITLE)
        title.setStyleSheet("font-size: 26px; font-weight: 650; color: #163d45;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Nastavte svůj hlas. Další videa upravíte jedním kliknutím."))
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)
        input_box = QGroupBox("1 · Vstup a výstup")
        left = QVBoxLayout(input_box)
        self.input_path, self.output_path = QLineEdit(), QLineEdit()
        self.input_path.setPlaceholderText("Složka s původními videi nebo nahrávkami")
        self.output_path.setPlaceholderText("Samostatná složka pro hotové soubory")
        self.path_buttons = []
        for label, edit in (("Vstupní složka", self.input_path), ("Výstupní složka", self.output_path)):
            left.addWidget(QLabel(label))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            button = QPushButton("Vybrat…")
            button.clicked.connect(lambda checked=False, e=edit: self.choose_folder(e))
            self.path_buttons.append(button)
            row.addWidget(button)
            left.addLayout(row)
            edit.textChanged.connect(self.paths_changed)
        options = QHBoxLayout()
        self.recursive = QCheckBox("Včetně podsložek")
        self.recursive.toggled.connect(self.paths_changed)
        options.addWidget(self.recursive)
        options.addStretch()
        self.scan_button = QPushButton("Načíst soubory")
        self.scan_button.clicked.connect(lambda: self.scan_files(False))
        options.addWidget(self.scan_button)
        left.addLayout(options)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Soubor", "Stav / výsledek"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.table.setAlternatingRowColors(True)
        left.addWidget(self.table, 1)
        left.addWidget(QLabel("Zvuková stopa vybraného souboru"))
        self.track = QComboBox()
        self.track.currentIndexChanged.connect(self.invalidate_preview)
        left.addWidget(self.track)
        collision_row = QHBoxLayout()
        collision_row.addWidget(QLabel("Pokud výstup existuje:"))
        self.collision = QComboBox()
        self.collision.addItem("Přidat číselnou příponu", "suffix")
        self.collision.addItem("Přeskočit soubor", "skip")
        collision_row.addWidget(self.collision, 1)
        left.addLayout(collision_row)
        note = QLabel("MP4 · MOV · MKV · M4A · WAV · MP3\nOriginály zůstávají zachované. Obraz se kopíruje bez rekomprese.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #50666d; font-size: 11px;")
        left.addWidget(note)
        splitter.addWidget(input_box)

        settings_box = QGroupBox("2 · Nastavení hlasu")
        settings_layout = QVBoxLayout(settings_box)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        knobs = QVBoxLayout(inner)
        knobs.setContentsMargins(2, 2, 8, 2)
        self.sliders = {}
        self.value_labels = {}
        descriptions = [
            ("pitch", "Hloubka hlasu", "Jemná změna výšky se zachováním formantů. Záporná hodnota hlas prohloubí."),
            ("fullness", "Plnost hlasu", "Jemné přidání basů a ubrání zahuhlaných středů."),
            ("clarity", "Čistota hlasu", "Potlačení stálého šumu pomocí FFT. Neodstraňuje cizí řeč ani ozvěnu."),
            ("intelligibility", "Srozumitelnost", "Mírné zvýraznění pásma okolo 3 kHz."),
            ("compression", "Vyrovnání hlasitosti", "Měkká komprese hlasitějších pasáží řeči."),
            ("deessing", "Sykavky", "Jemné potlačení ostrých sykavek. Vyšší hodnota znamená silnější útlum."),
        ]
        for key, name, description in descriptions:
            row = QHBoxLayout()
            text = QLabel(name)
            text.setToolTip(description)
            row.addWidget(text)
            row.addStretch()
            value = QLabel()
            value.setMinimumWidth(70)
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(value)
            knobs.addLayout(row)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(-20, 20) if key == "pitch" else slider.setRange(0, 100)
            slider.setToolTip(description)
            slider.setAccessibleName(name)
            slider.valueChanged.connect(lambda v, k=key: self.slider_changed(k, v))
            self.sliders[key] = slider
            self.value_labels[key] = value
            knobs.addWidget(slider)
        form = QFormLayout()
        self.loudness = QComboBox()
        for text, value in (("Automaticky: mono −16 / stereo −14 LUFS", "auto"), ("−16 LUFS", "-16"),
                            ("−14 LUFS", "-14"), ("−18 LUFS", "-18")):
            self.loudness.addItem(text, value)
        self.loudness.currentIndexChanged.connect(self.invalidate_preview)
        form.addRow("Cílová hlasitost", self.loudness)
        knobs.addLayout(form)
        peak = QLabel("Ochrana špiček: nejvýše −1 dBTP\nDvouprůchodová normalizace a kontrola hotového zvuku.")
        peak.setWordWrap(True)
        peak.setStyleSheet("color: #50666d; font-size: 11px;")
        knobs.addWidget(peak)
        knobs.addStretch()
        scroll.setWidget(inner)
        settings_layout.addWidget(scroll)
        splitter.addWidget(settings_box)
        splitter.setSizes([650, 450])

        bottom = QGroupBox("3 · Presety a zpracování")
        box = QVBoxLayout(bottom)
        presets = QHBoxLayout()
        presets.addWidget(QLabel("Preset"))
        self.preset = QComboBox()
        self.preset.currentIndexChanged.connect(self.apply_preset)
        presets.addWidget(self.preset, 1)
        self.new_preset = QPushButton("Uložit jako nový…")
        self.new_preset.clicked.connect(self.save_preset)
        self.rename_preset = QPushButton("Přejmenovat…")
        self.rename_preset.clicked.connect(self.rename_current)
        self.delete_preset = QPushButton("Odstranit")
        self.delete_preset.clicked.connect(self.delete_current)
        for button in (self.new_preset, self.rename_preset, self.delete_preset):
            presets.addWidget(button)
        box.addLayout(presets)
        self.preset_note = QLabel("Změny posuvníků použijete hned; uložíte je jako nový preset.")
        self.preset_note.setStyleSheet("color: #50666d; font-size: 11px;")
        box.addWidget(self.preset_note)
        playback = QHBoxLayout()
        playback.addWidget(QLabel("Začátek ukázky (s)"))
        self.preview_start = QDoubleSpinBox()
        self.preview_start.setRange(0, 86400)
        self.preview_start.setDecimals(1)
        self.preview_start.valueChanged.connect(self.invalidate_preview)
        playback.addWidget(self.preview_start)
        self.preview_button = QPushButton("Přehrát ukázku · 15 s")
        self.preview_button.clicked.connect(self.play_preview)
        playback.addWidget(self.preview_button)
        self.compare = QPushButton("Poslech: Upravený")
        self.compare.setCheckable(True)
        self.compare.setChecked(True)
        self.compare.toggled.connect(self.switch_preview)
        self.compare.setToolTip("Přepne původní a upravenou ukázku se stejnou cílovou hlasitostí.")
        playback.addWidget(self.compare)
        self.pause = QPushButton("Pozastavit")
        self.pause.clicked.connect(self.player.pause)
        playback.addWidget(self.pause)
        playback.addStretch()
        box.addLayout(playback)
        actions = QHBoxLayout()
        self.batch_button = QPushButton("Zpracovat složku")
        self.batch_button.setObjectName("primary")
        self.batch_button.clicked.connect(lambda: self.scan_files(True))
        self.stop_button = QPushButton("Zastavit po aktuálním souboru")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.request_stop)
        self.tools_button = QPushButton("FFmpeg…")
        self.tools_button.clicked.connect(self.choose_tools)
        actions.addWidget(self.batch_button)
        actions.addWidget(self.stop_button)
        actions.addStretch()
        actions.addWidget(self.tools_button)
        box.addLayout(actions)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        box.addWidget(self.progress)
        self.status = QLabel("Kontroluji FFmpeg…")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(self.status)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        box.addWidget(self.summary)
        layout.addWidget(bottom)
        self.refresh_presets()
        self.update_enabled()

    def load_preferences(self):
        prefs = self.store.preferences
        self.input_path.setText(str(prefs.get("input", "")))
        self.output_path.setText(str(prefs.get("output", "")))
        self.recursive.setChecked(bool(prefs.get("recursive", False)))
        self.collision.setCurrentIndex(max(0, self.collision.findData(prefs.get("collision", "suffix"))))
        index = self.preset.findData(prefs.get("last_preset", "natural"))
        self.preset.setCurrentIndex(max(0, index))
        self.apply_preset()
        # Restore unsaved working values as well as the selected named preset.
        try:
            if "working_settings" in prefs:
                self.set_voice(VoiceSettings.from_dict(prefs["working_settings"]))
        except (ValueError, TypeError):
            pass

    def save_preferences(self):
        self.store.preferences.update({"input": self.input_path.text(), "output": self.output_path.text(),
                                       "recursive": self.recursive.isChecked(), "collision": self.collision.currentData(),
                                       "last_preset": self.preset.currentData(), "working_settings": asdict(self.voice())})
        self.store.save()

    def voice(self):
        data = {key: slider.value() / 10 if key == "pitch" else slider.value() for key, slider in self.sliders.items()}
        return VoiceSettings(**data, loudness=self.loudness.currentData())

    def set_voice(self, settings):
        for key, slider in self.sliders.items():
            slider.setValue(round(getattr(settings, key) * (10 if key == "pitch" else 1)))
            self.slider_changed(key, slider.value())
        self.loudness.setCurrentIndex(self.loudness.findData(settings.loudness))

    def slider_changed(self, key, value):
        self.value_labels[key].setText(f"{value / 10:+.1f} půlt." if key == "pitch" else f"{value} %")
        self.invalidate_preview()

    def refresh_presets(self, selected=None):
        self.preset.blockSignals(True)
        self.preset.clear()
        for preset in self.store.presets:
            self.preset.addItem(preset["name"], preset["id"])
        self.preset.setCurrentIndex(max(0, self.preset.findData(selected or self.store.preferences.get("last_preset", "natural"))))
        self.preset.blockSignals(False)

    def apply_preset(self, *_):
        preset = next((p for p in self.store.presets if p["id"] == self.preset.currentData()), None)
        if preset:
            self.set_voice(VoiceSettings.from_dict(preset["settings"]))
            self.store.preferences["last_preset"] = preset["id"]

    def save_preset(self):
        name, ok = QInputDialog.getText(self, "Nový preset", "Název presetu:")
        if ok:
            try:
                selected = self.store.add(name, self.voice())
                self.refresh_presets(selected)
                self.save_preferences()
            except (ValueError, OSError) as exc:
                self.show_error(str(exc))

    def rename_current(self):
        name, ok = QInputDialog.getText(self, "Přejmenovat preset", "Nový název:", text=self.preset.currentText())
        if ok:
            try:
                current = self.preset.currentData()
                self.store.rename(current, name)
                self.refresh_presets(current)
            except (ValueError, OSError) as exc:
                self.show_error(str(exc))

    def delete_current(self):
        if QMessageBox.question(self, "Odstranit preset", f"Odstranit preset „{self.preset.currentText()}“?") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.remove(self.preset.currentData())
            self.refresh_presets()
            self.apply_preset()
        except (ValueError, OSError) as exc:
            self.show_error(str(exc))

    def choose_folder(self, edit):
        folder = QFileDialog.getExistingDirectory(self, "Vyberte složku", edit.text())
        if folder:
            edit.setText(folder)

    def paths_changed(self, *_):
        self.media = []
        self.table.setRowCount(0)
        self.selection_changed()

    def initialize_tools(self):
        folder = str(self.store.preferences.get("ffmpeg_folder", ""))
        self.start_task(lambda emit: Tools.find(folder), self.tools_ready)

    def choose_tools(self):
        folder = QFileDialog.getExistingDirectory(self, "Složka s ffmpeg.exe a ffprobe.exe", str(self.store.preferences.get("ffmpeg_folder", "")))
        if folder:
            self.store.preferences["ffmpeg_folder"] = folder
            self.initialize_tools()

    def tools_ready(self, tools):
        self.tools = tools
        LOG.info("FFmpeg připraveno: %s", tools.ffmpeg)
        missing = [name for name in ("rubberband", "afftdn", "deesser") if name not in tools.filters]
        self.status.setText("Připraveno · " + str(tools.ffmpeg) + (" · Chybí volitelné filtry: " + ", ".join(missing) if missing else ""))
        self.status.setToolTip(self.status.text())
        for key, name in (("pitch", "rubberband"), ("clarity", "afftdn"), ("deessing", "deesser")):
            self.sliders[key].setToolTip(self.sliders[key].toolTip().split("\n")[0] +
                                         ("\nNedostupné v této sestavě FFmpeg; nastavte 0 nebo vyberte jiný FFmpeg." if name not in tools.filters else ""))
        self.update_enabled()
        if self.store.warnings:
            QMessageBox.warning(self, "Obnovení nastavení", "\n".join(self.store.warnings))

    def start_task(self, task, success, event=None):
        if self.worker:
            return
        self.worker = Worker(task, self)
        worker = self.worker
        if event:
            worker.event.connect(event)
        worker.finished.connect(lambda: self.task_finished(worker, success))
        self.update_enabled()
        worker.start()

    def task_finished(self, worker, success):
        self.worker = None
        worker.deleteLater()
        self.update_enabled()
        if worker.error:
            self.is_batch = False
            self.update_enabled()
            self.status.setText("Úloha selhala: " + worker.error[:350])
            if not self.close_requested:
                self.show_error(worker.error)
        else:
            success(worker.value)
        if self.close_requested:
            self.close()

    def folders(self):
        if not self.input_path.text().strip() or not self.output_path.text().strip():
            raise MediaError("Vyberte vstupní i výstupní složku.")
        source = Path(self.input_path.text()).resolve()
        destination = Path(self.output_path.text()).resolve()
        validate_folders(source, destination)
        return source, destination

    def scan_files(self, then_batch=False):
        try:
            source, destination = self.folders()
            self.save_preferences()
            # Validate actual filter support before a long batch.
            from .engine import voice_filters
            if then_batch:
                voice_filters(self.voice(), self.tools)
        except (MediaError, OSError) as exc:
            self.show_error(str(exc))
            return
        remembered = {m.path: self.track.currentData() for m in self.media if self.table.currentRow() >= 0 and m is self.media[self.table.currentRow()]}
        self.invalidate_preview()
        self.summary.clear()
        self.progress.setValue(0)
        def ready(items):
            self.media = items
            self.fill_table()
            self.status.setText(f"Nalezeno souborů: {len(items)}")
            if items:
                self.table.selectRow(0)
            if then_batch and items and not self.close_requested:
                self.begin_batch(source, destination, remembered)
        recursive = self.recursive.isChecked()
        self.start_task(lambda emit: scan(self.tools, source, destination, recursive,
                                         lambda p, s: emit(p, s)), ready, self.simple_progress)

    def fill_table(self):
        self.table.setRowCount(len(self.media))
        source = Path(self.input_path.text())
        for row, media in enumerate(self.media):
            try:
                name = str(media.path.relative_to(source))
            except ValueError:
                name = media.path.name
            item = QTableWidgetItem(name)
            item.setToolTip(str(media.path))
            self.table.setItem(row, 0, item)
            if media.error:
                self.row_status(row, "Chyba při načtení", media.error, "errors")
            elif not media.audio:
                self.row_status(row, "Bez zvukové stopy", "Soubor bude přeskočen.", "skipped")
            else:
                suggested = media.suggested_track()
                label = "Vyberte zvukovou stopu" if suggested is None else f"Připraveno · stopa {suggested + 1}"
                self.row_status(row, label, f"Délka: {media.duration:.1f} s · Zvukové stopy: {len(media.audio)}")

    def selection_changed(self):
        self.invalidate_preview()
        self.track.blockSignals(True)
        self.track.clear()
        row = self.table.currentRow()
        if 0 <= row < len(self.media):
            media = self.media[row]
            self.track.addItem("Vyberte stopu…", None)
            for i, stream in enumerate(media.audio):
                self.track.addItem(self.track_label(i, stream), i)
            suggested = media.suggested_track()
            self.track.setCurrentIndex(self.track.findData(suggested) if suggested is not None else 0)
            self.preview_start.setMaximum(max(0, media.duration - .1))
        self.track.blockSignals(False)
        self.update_enabled()

    @staticmethod
    def track_label(index, stream):
        tags = stream.get("tags", {})
        return (f"{index + 1}: {tags.get('language', 'jazyk neuveden')} · {stream.get('channels', '?')} kan. · "
                f"{stream.get('codec_name', '?')}" + (f" · {tags['title']}" if tags.get("title") else "") +
                (" · výchozí" if stream.get("disposition", {}).get("default") else ""))

    def begin_batch(self, source, destination, remembered):
        jobs = []
        for row, media in enumerate(self.media):
            selected = remembered.get(media.path, media.suggested_track())
            if media.audio and not media.error and selected is None:
                labels = [self.track_label(i, s) for i, s in enumerate(media.audio)]
                labels.append("Přeskočit tento soubor")
                answer, ok = QInputDialog.getItem(self, "Výběr zvukové stopy", str(media.path) + "\nKterou stopu upravit? Ostatní budou zkopírovány.", labels, 0, False)
                if not ok:
                    self.status.setText("Dávka nebyla spuštěna. Výběr stopy byl zrušen.")
                    return
                selected = labels.index(answer) if answer != labels[-1] else None
            jobs.append(Job(media, selected))
            if selected is not None:
                self.row_status(row, f"Čeká · stopa {selected + 1}")
        self.is_batch = True
        self.stop_event.clear()
        settings, collision = self.voice(), self.collision.currentData()
        # Snapshot all GUI state on the GUI thread.
        self.start_task(lambda emit: run_batch(Processor(self.tools), jobs, source, destination, settings,
                                               self.stop_event, collision, lambda *args: emit(*args)),
                        self.batch_done, self.batch_event)

    def batch_event(self, args):
        kind, row, data = args
        total = max(1, len(self.media))
        if kind == "started":
            self.row_status(row, "Zpracovávám…")
            self.status.setText(f"{row + 1}/{total} · {data}")
        elif kind == "progress":
            fraction, stage = data
            value = int((row + fraction) / total * 100)
            self.progress.setValue(max(self.progress.value(), value))
            self.status.setText(f"Dokončeno {row}/{total} · {self.media[row].path.name} · {stage}")
        elif kind == "result":
            status, message = data
            labels = {"done": "Hotovo", "errors": "Chyba", "skipped": "Přeskočeno"}
            self.row_status(row, labels[status] + " · " + message.replace("\n", " "), message, status)

    def batch_done(self, result):
        self.is_batch = False
        self.update_enabled()
        if result["pending"] == 0:
            self.progress.setValue(100)
        self.status.setText("Zastaveno po dokončení souboru." if result["stopped"] else "Dávka dokončena.")
        self.summary.setText(f"Hotovo: {result['done']} · Chyby: {result['errors']} · Přeskočeno: {result['skipped']} · "
                             f"Nezpracováno: {result['pending']}. Podrobnosti jsou v seznamu souborů (najeďte na stav).")

    def request_stop(self):
        self.stop_event.set()
        self.stop_button.setEnabled(False)
        self.status.setText("Zastavuji po aktuálním souboru…")

    def row_status(self, row, text, tooltip="", state=""):
        item = QTableWidgetItem(text)
        item.setToolTip(tooltip or text)
        color = {"done": "#167052", "errors": "#b22b36", "skipped": "#806419"}.get(state)
        if color:
            item.setForeground(QColor(color))
        self.table.setItem(row, 1, item)

    def simple_progress(self, args):
        fraction, text = args
        self.progress.setValue(int(fraction * 100))
        self.status.setText(text)

    def invalidate_preview(self, *_):
        self.preview_key = None
        self.preview_paths = None
        self.autoplay = False
        self.player.stop()
        self.player.setSource(QUrl())
        if hasattr(self, "compare"):
            self.update_enabled()

    def play_preview(self):
        row = self.table.currentRow()
        track = self.track.currentData()
        if row < 0 or track is None:
            self.show_error("Vyberte soubor a zvukovou stopu.")
            return
        media, settings, start = self.media[row], self.voice(), self.preview_start.value()
        try:
            key = (str(media.path), media.path.stat().st_mtime_ns, track, settings, start)
        except OSError as exc:
            self.show_error("Vstupní soubor není dostupný. Načtěte seznam znovu.\n" + str(exc))
            return
        if key == self.preview_key and self.preview_paths:
            if self.player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                self.player.setPosition(0)
            self.player.play()
            return
        self.invalidate_preview()
        if self.preview_dir:
            self.preview_dir.cleanup()
        self.preview_dir = tempfile.TemporaryDirectory(prefix="voice-studio-preview-", ignore_cleanup_errors=True)
        folder = Path(self.preview_dir.name)
        def ready(paths):
            self.preview_paths = paths
            self.preview_key = key
            self.progress.setValue(100)
            self.status.setText("Připravená ukázka · Původní i upravená verze mají stejnou cílovou hlasitost.")
            self.load_playback(0, True)
            self.update_enabled()
        self.start_task(lambda emit: Processor(self.tools).preview(media, track, settings, folder, start,
                                                                  notify=lambda p, s: emit(p, s)), ready, self.simple_progress)

    def load_playback(self, position, autoplay):
        if not self.preview_paths:
            return
        self.pending_position = position
        self.autoplay = autoplay
        self.player.setSource(QUrl.fromLocalFile(str(self.preview_paths[1 if self.compare.isChecked() else 0])))

    def player_ready(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.player.setPosition(self.pending_position)
            if self.autoplay:
                self.player.play()
            self.autoplay = False

    def switch_preview(self, checked):
        self.compare.setText("Poslech: Upravený" if checked else "Poslech: Původní")
        if self.preview_paths:
            self.load_playback(self.player.position(), self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState)

    def update_enabled(self):
        busy = self.worker is not None
        ready = self.tools is not None and not busy
        for widget in [self.input_path, self.output_path, self.recursive, self.collision, self.preset, self.new_preset,
                       self.rename_preset, self.delete_preset, self.tools_button, self.preview_start,
                       *self.path_buttons, *self.sliders.values(), self.loudness, self.table, self.track]:
            widget.setEnabled(not busy)
        self.scan_button.setEnabled(ready)
        self.batch_button.setEnabled(ready)
        self.preview_button.setEnabled(ready and self.table.currentRow() >= 0 and self.track.currentData() is not None)
        self.compare.setEnabled(not busy and self.preview_paths is not None)
        self.pause.setEnabled(not busy and self.preview_paths is not None)
        self.stop_button.setEnabled(busy and self.is_batch and not self.stop_event.is_set())

    def show_error(self, message):
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(APP_NAME)
        dialog.setText(message[:500])
        if len(message) > 500:
            dialog.setDetailedText(message)
        dialog.exec()

    def closeEvent(self, event):
        if self.worker:
            self.close_requested = True
            self.stop_event.set()
            self.status.setText("Dokončuji aktuální úlohu a poté zavřu aplikaci…")
            event.ignore()
            return
        try:
            self.save_preferences()
        except OSError as exc:
            self.show_error("Nastavení se nepodařilo uložit: " + str(exc))
        self.player.stop()
        self.player.setSource(QUrl())
        if self.preview_dir:
            self.preview_dir.cleanup()
        event.accept()


def configure_app(app):
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("VoiceStudio")
    app.setStyle("Fusion")
    app.setStyleSheet("""
        QWidget { font-family: 'Segoe UI'; font-size: 12px; }
        QMainWindow { background: #f3f6f7; }
        QGroupBox { font-weight: 600; border: 1px solid #cfdbdf; border-radius: 7px; margin-top: 12px; padding-top: 12px; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #264e57; }
        QPushButton { padding: 7px 12px; }
        QPushButton#primary { background: #176d73; color: white; border: 1px solid #176d73; border-radius: 4px; font-weight: 600; }
        QPushButton#primary:disabled { background: #aec2c5; border-color: #aec2c5; }
        QLineEdit, QComboBox { padding: 4px; }
        QProgressBar { text-align: center; height: 18px; border: 1px solid #cfdbdf; border-radius: 3px; }
        QProgressBar::chunk { background: #33928e; }
    """)
    return app


def run_gui():
    app = configure_app(QApplication.instance() or QApplication([]))
    window = MainWindow()
    window.show()
    return app.exec()
