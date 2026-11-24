import hashlib
import json
import shutil
import threading
from dataclasses import replace

import pytest
from voicestudio.engine import (Job, Media, MediaError, Tools, probe, run, run_batch, scan,
                                validate_folders, voice_filters)
from voicestudio.settings import VoiceSettings


def packets(tools, path, selector):
    return json.loads(run([str(tools.ffprobe), "-v", "error", "-select_streams", selector,
                           "-show_packets", "-show_data_hash", "sha256", "-of", "json", str(path)]))["packets"]


@pytest.mark.parametrize("extension", [".mp4", ".mov", ".mkv"])
def test_video_bitstream_timestamps_and_loudness(tmp_path, tools, processor, make_video, extension):
    source = make_video(tmp_path / ("Původní žluťoučký" + extension), delay=.32)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    info = probe(tools, source)
    out = processor.process(info, 0, VoiceSettings(pitch=-1), tmp_path / ("Výstup" + extension))
    before, after = packets(tools, source, "v:0"), packets(tools, out, "v:0")
    assert [p["data_hash"] for p in before] == [p["data_hash"] for p in after]
    assert len(before) == 200
    for first, second in zip(before, after):
        assert abs(float(first["pts_time"]) - float(second["pts_time"])) < .002
        assert abs(float(first["dts_time"]) - float(second["dts_time"])) < .002
    output = probe(tools, out)
    for key in ("width", "height", "r_frame_rate", "codec_name"):
        assert info.video[0][key] == output.video[0][key]
    input_offset = float(info.audio[0].get("start_time", 0)) - float(info.video[0].get("start_time", 0))
    output_offset = float(output.audio[0].get("start_time", 0)) - float(output.video[0].get("start_time", 0))
    assert abs(input_offset - output_offset) <= .045
    assert abs(output.duration - info.duration) < .08
    measured = processor.measure(out, 0, "", -16)
    assert abs(float(measured["input_i"]) - -16) < .7
    assert float(measured["input_tp"]) <= -1
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash


def test_stereo_target(tmp_path, tools, processor, make_video):
    path = make_video(tmp_path / "stereo.mp4", stereo=True)
    out = processor.process(probe(tools, path), 0, VoiceSettings(), tmp_path / "stereo_voice.mp4")
    assert probe(tools, out).audio[0]["channels"] == 2
    assert abs(float(processor.measure(out, 0, "", -14)["input_i"]) + 14) < .7


def test_multiple_tracks_preserved(tmp_path, tools, processor, make_video):
    path = make_video(tmp_path / "Více stop.mkv", tracks=2)
    info = probe(tools, path)
    assert info.suggested_track() is None
    out = processor.process(info, 1, VoiceSettings(), tmp_path / "Více stop_voice.mkv")
    assert len(probe(tools, out).audio) == 2
    assert [p["data_hash"] for p in packets(tools, path, "a:0")] == [p["data_hash"] for p in packets(tools, out, "a:0")]
    assert [p["data_hash"] for p in packets(tools, path, "a:1")] != [p["data_hash"] for p in packets(tools, out, "a:1")]
    assert probe(tools, out).audio[0]["tags"]["title"] == "Stopa 1"


def test_batch_continues_on_error_and_skips_silent_video(tmp_path, tools, processor, sample, make_video):
    source, destination = tmp_path / "in", tmp_path / "out"
    source.mkdir()
    (source / "01 rozbitý.mp4").write_text("not a movie")
    shutil.copy(sample, source / "02 funkční.wav")
    make_video(source / "03 bez zvuku.mp4", tracks=0)
    found = scan(tools, source, destination, False)
    summary = run_batch(processor, [Job(m, m.suggested_track()) for m in found], source, destination,
                        VoiceSettings(), threading.Event())
    assert summary == {"done": 1, "errors": 1, "skipped": 1, "pending": 0, "stopped": False}
    assert (destination / "02 funkční_voice.wav").is_file()
    assert not list(destination.glob(".voice-studio-*"))


def test_stop_after_current_file(tmp_path, tools, processor, sample):
    source, dest = tmp_path / "in", tmp_path / "out"
    source.mkdir()
    for name in ("a.wav", "b.wav"):
        shutil.copy(sample, source / name)
    jobs = [Job(m, 0) for m in scan(tools, source, dest, False)]
    stop = threading.Event()
    def event(kind, _, data):
        if kind == "started":
            stop.set()
    result = run_batch(processor, jobs, source, dest, VoiceSettings(), stop, event=event)
    assert result["done"] == 1 and result["pending"] == 1 and result["stopped"]
    assert len(list(dest.glob("*.wav"))) == 1


def test_collisions_never_overwrite(tmp_path, processor, tools, sample):
    destination = tmp_path / "voice.wav"
    destination.write_bytes(b"existing output")
    info = probe(tools, sample)
    assert processor.process(info, 0, VoiceSettings(), destination, "skip") is None
    result = processor.process(info, 0, VoiceSettings(), destination)
    assert result.name == "voice_2.wav"
    assert destination.read_bytes() == b"existing output"


def test_no_finished_output_after_failure(tmp_path, processor, tools, sample):
    out = tmp_path / "impossible.mp4"
    broken = replace(tools, ffmpeg=tmp_path / "missing.exe")
    with pytest.raises(MediaError):
        type(processor)(broken).process(probe(tools, sample), 0, VoiceSettings(), out)
    assert not out.exists()
    assert not list(tmp_path.glob(".voice-studio-*"))


def test_render_failure_cleans_staging_folder(tmp_path, processor, tools, sample):
    out = tmp_path / "unavailable.unknown_muxer"
    with pytest.raises(MediaError):
        processor.process(probe(tools, sample), 0, VoiceSettings(), out)
    assert not out.exists()
    assert not list(tmp_path.glob(".voice-studio-*"))


def test_variable_frame_rate_and_rotation(tmp_path, tools, processor, sample):
    base = tmp_path / "vfr.mp4"
    source = tmp_path / "phone.mp4"
    run([str(tools.ffmpeg), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=256x144:rate=30:duration=8",
         "-i", str(sample), "-vf", "select='if(lt(t,4),not(mod(n,2)),1)'", "-fps_mode", "vfr",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(base)])
    run([str(tools.ffmpeg), "-v", "error", "-display_rotation:v:0", "90", "-i", str(base), "-c", "copy", str(source)])
    info = probe(tools, source)
    result = processor.process(info, 0, VoiceSettings(), tmp_path / "phone_voice.mp4")
    before, after = packets(tools, source, "v:0"), packets(tools, result, "v:0")
    assert [p["data_hash"] for p in before] == [p["data_hash"] for p in after]
    assert [p["pts_time"] for p in before] == [p["pts_time"] for p in after]
    assert info.video[0]["side_data_list"] == probe(tools, result).video[0]["side_data_list"]


def test_preview_matching_loudness_and_duration(tmp_path, tools, processor, sample):
    info = probe(tools, sample)
    original, processed = processor.preview(info, 0, VoiceSettings(pitch=-2, fullness=70, compression=70), tmp_path, seconds=6)
    first = float(processor.measure(original, 0, "", -16)["input_i"])
    second = float(processor.measure(processed, 0, "", -16)["input_i"])
    assert abs(first - second) < .5
    assert abs(probe(tools, original).duration - probe(tools, processed).duration) < .02


@pytest.mark.parametrize("extension", [".wav", ".mp3", ".m4a"])
def test_audio_formats(tmp_path, tools, processor, sample, extension):
    source = tmp_path / ("Vstup" + extension)
    run([str(tools.ffmpeg), "-v", "error", "-i", str(sample), str(source)])
    out = processor.process(probe(tools, source), 0, VoiceSettings(), tmp_path / ("Výstup" + extension))
    assert out.exists()
    assert abs(probe(tools, out).duration - probe(tools, source).duration) < .08


def test_silence_and_missing_optional_filters(tmp_path, tools, processor):
    source = tmp_path / "silence.wav"
    run([str(tools.ffmpeg), "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "2", str(source)])
    output = processor.process(probe(tools, source), 0, VoiceSettings(), tmp_path / "silent_voice.wav")
    assert float(processor.measure(output, 0, "", -16)["input_tp"]) == float("-inf")
    limited = Tools(tools.ffmpeg, tools.ffprobe, tools.filters - {"rubberband"})
    with pytest.raises(MediaError, match="rubberband"):
        voice_filters(VoiceSettings(pitch=-1), limited)
    assert voice_filters(VoiceSettings(pitch=0), limited)


def test_recursive_scan_excludes_output(tmp_path, tools, sample):
    sub, out = tmp_path / "podsložka", tmp_path / "hotové"
    sub.mkdir()
    out.mkdir()
    for path in (tmp_path / "a.WAV", sub / "b.wav", out / "already.wav"):
        shutil.copy(sample, path)
    assert len(scan(tools, tmp_path, out, False)) == 1
    assert len(scan(tools, tmp_path, out, True)) == 2
    with pytest.raises(MediaError):
        validate_folders(tmp_path, tmp_path)
    with pytest.raises(MediaError):
        validate_folders(sub, tmp_path)
