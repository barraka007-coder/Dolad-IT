import json
from dataclasses import asdict

import pytest
from voicestudio.settings import Store, VoiceSettings


def test_presets_roundtrip_rename_delete_restore(tmp_path):
    store = Store(tmp_path)
    settings = VoiceSettings(pitch=-1.2, fullness=37, loudness="-18")
    identifier = store.add("Můj hlas – návod", settings)
    store.preferences["working_settings"] = asdict(settings)
    store.save()
    restored = Store(tmp_path)
    assert restored.preferences["last_preset"] == identifier
    assert VoiceSettings.from_dict(restored.presets[-1]["settings"]) == settings
    assert "Můj hlas" in (tmp_path / "presets.json").read_text(encoding="utf-8")
    restored.rename(identifier, "Přejmenovaný")
    assert Store(tmp_path).presets[-1]["name"] == "Přejmenovaný"
    restored.remove(identifier)
    assert identifier not in [p["id"] for p in Store(tmp_path).presets]
    assert Store(tmp_path).preferences["last_preset"] != identifier


def test_invalid_json_is_preserved(tmp_path):
    (tmp_path / "presets.json").write_text("{broken", encoding="utf-8")
    store = Store(tmp_path)
    assert len(store.presets) == 3
    assert store.warnings
    assert next(tmp_path.glob("*.damaged-*")).read_text() == "{broken"


@pytest.mark.parametrize("kwargs", [{"pitch": 3}, {"pitch": float("nan")}, {"fullness": -1}, {"deessing": 101}, {"loudness": "0"}])
def test_safe_ranges(kwargs):
    with pytest.raises(ValueError):
        VoiceSettings(**kwargs)


def test_no_duplicate_or_empty_presets(tmp_path):
    store = Store(tmp_path)
    for name in ("", "přirozený"):
        with pytest.raises(ValueError):
            store.add(name, VoiceSettings())


def test_invalid_schema_is_recovered(tmp_path):
    (tmp_path / "presets.json").write_text(json.dumps([{"id": 4}]), encoding="utf-8")
    store = Store(tmp_path)
    assert store.presets[0]["name"] == "Přirozený"


def test_automatic_targets():
    assert VoiceSettings().target(1) == -16
    assert VoiceSettings().target(2) == -14
