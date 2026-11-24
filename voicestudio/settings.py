from __future__ import annotations

import json
import math
import os
import uuid
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass(frozen=True)
class VoiceSettings:
    pitch: float = 0.0
    fullness: int = 25
    clarity: int = 20
    intelligibility: int = 25
    compression: int = 35
    deessing: int = 15
    loudness: str = "auto"

    def __post_init__(self):
        if not math.isfinite(self.pitch) or not -2 <= self.pitch <= 2:
            raise ValueError("Hloubka hlasu musí být mezi −2 a +2 půltóny.")
        for key in ("fullness", "clarity", "intelligibility", "compression", "deessing"):
            value = getattr(self, key)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError(f"Neplatná hodnota {key}.")
        if self.loudness not in ("auto", "-16", "-14", "-18"):
            raise ValueError("Neplatná cílová hlasitost.")

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("Neplatný preset.")
        return cls(**{f.name: data[f.name] for f in fields(cls) if f.name in data})

    def target(self, channels: int) -> float:
        return float(self.loudness) if self.loudness != "auto" else (-16.0 if channels == 1 else -14.0)


def default_presets():
    return [
        {"id": "natural", "name": "Přirozený", "settings": asdict(VoiceSettings())},
        {"id": "deep", "name": "Hlubší", "settings": asdict(VoiceSettings(pitch=-1, fullness=40))},
        {"id": "documentary", "name": "Dokumentární", "settings": asdict(VoiceSettings(
            pitch=-0.5, fullness=35, intelligibility=40, compression=50, deessing=25))},
    ]


def data_directory() -> Path:
    return Path(os.environ.get("APPDATA", str(Path.home() / ".config"))) / "VoiceStudio"


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class Store:
    def __init__(self, root: Path | None = None):
        self.root = root or data_directory()
        self.warnings: list[str] = []
        self.presets = self._read("presets.json", default_presets())
        try:
            if not isinstance(self.presets, list) or not self.presets:
                raise ValueError("Prázdný seznam presetů")
            ids = set()
            for preset in self.presets:
                if not isinstance(preset["id"], str) or preset["id"] in ids:
                    raise ValueError("Neplatné ID presetu")
                ids.add(preset["id"])
                if not isinstance(preset["name"], str) or not preset["name"].strip():
                    raise ValueError("Neplatný název presetu")
                VoiceSettings.from_dict(preset["settings"])
        except (KeyError, TypeError, ValueError):
            self._backup("presets.json")
            self.presets = default_presets()
        self.preferences = self._read("settings.json", {})
        if not isinstance(self.preferences, dict):
            self._backup("settings.json")
            self.preferences = {}

    def _backup(self, name):
        path = self.root / name
        if path.exists():
            backup = path.with_name(name + ".damaged-" + uuid.uuid4().hex[:8])
            path.rename(backup)
            self.warnings.append(f"Poškozený soubor {name} byl zálohován jako {backup.name}.")

    def _read(self, name, fallback):
        try:
            return json.loads((self.root / name).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return fallback
        except (ValueError, UnicodeError):
            self._backup(name)
            return fallback

    def save(self):
        atomic_json(self.root / "presets.json", self.presets)
        atomic_json(self.root / "settings.json", self.preferences)

    def add(self, name: str, settings: VoiceSettings):
        name = name.strip()
        if not name or any(p["name"].casefold() == name.casefold() for p in self.presets):
            raise ValueError("Zadejte neprázdný, jedinečný název presetu.")
        preset = {"id": uuid.uuid4().hex, "name": name, "settings": asdict(settings)}
        self.presets.append(preset)
        self.preferences["last_preset"] = preset["id"]
        self.save()
        return preset["id"]

    def rename(self, preset_id: str, name: str):
        name = name.strip()
        if not name or any(p["id"] != preset_id and p["name"].casefold() == name.casefold() for p in self.presets):
            raise ValueError("Zadejte neprázdný, jedinečný název presetu.")
        next(p for p in self.presets if p["id"] == preset_id)["name"] = name
        self.save()

    def remove(self, preset_id: str):
        if len(self.presets) == 1:
            raise ValueError("Alespoň jeden preset musí zůstat uložený.")
        self.presets = [p for p in self.presets if p["id"] != preset_id]
        if self.preferences.get("last_preset") == preset_id:
            self.preferences["last_preset"] = self.presets[0]["id"]
        self.save()
