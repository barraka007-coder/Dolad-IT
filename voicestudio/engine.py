from __future__ import annotations

import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .settings import VoiceSettings

SUPPORTED = {".mp4", ".mov", ".mkv", ".m4a", ".wav", ".mp3"}
LOG = logging.getLogger(__name__)
Progress = Callable[[float, str], None]


class MediaError(RuntimeError):
    pass


@dataclass(frozen=True)
class Tools:
    ffmpeg: Path
    ffprobe: Path
    filters: frozenset[str]

    @classmethod
    def find(cls, folder: str = ""):
        roots = []
        if folder:
            roots.append(Path(folder))
        if os.environ.get("VOICE_STUDIO_FFMPEG"):
            roots.append(Path(os.environ["VOICE_STUDIO_FFMPEG"]))
        base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
        roots += [base / "tools" / "ffmpeg", base]
        if getattr(sys, "_MEIPASS", None):
            roots.append(Path(sys._MEIPASS) / "tools" / "ffmpeg")
        found = shutil.which("ffmpeg")
        if found:
            roots.append(Path(found).parent)
        extension = ".exe" if os.name == "nt" else ""
        for root in roots:
            ffmpeg, ffprobe = root / ("ffmpeg" + extension), root / ("ffprobe" + extension)
            if ffmpeg.is_file() and ffprobe.is_file():
                listing = run([str(ffmpeg), "-hide_banner", "-filters"], timeout=20)
                # FFmpeg 8 uses two capability columns; older builds use three.
                filters = frozenset(re.findall(r"^\s*[TSC\.A-Z|]{2,3}\s+(\w+)\s+\S*->", listing, re.M))
                needed = {"highpass", "equalizer", "bass", "acompressor", "loudnorm", "aresample", "alimiter"}
                if not needed <= filters:
                    raise MediaError("FFmpeg neobsahuje požadované filtry: " + ", ".join(sorted(needed - filters)))
                run([str(ffprobe), "-version"], timeout=20)
                return cls(ffmpeg, ffprobe, filters)
        raise MediaError("FFmpeg a FFprobe nebyly nalezeny. Vyberte složku se soubory ffmpeg.exe a ffprobe.exe, "
                         "vložte je do tools\\ffmpeg nebo přidejte jejich složku do PATH.")


def run(args: list[str], *, progress: Callable[[float], None] | None = None,
        duration: float = 0, timeout: int | None = None) -> str:
    """No shell, Unicode paths, bounded log storage, hidden Windows subprocesses."""
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    LOG.debug("Spouštím %r", args)
    if not progress:
        try:
            result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, encoding="utf-8", errors="replace",
                                    creationflags=flags, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MediaError(str(exc)) from exc
        output = result.stdout
        if result.returncode:
            LOG.error("FFmpeg/FFprobe: %s", output)
            raise MediaError(output[-3500:].strip())
        return output
    lines: list[str] = []
    try:
        with subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                              creationflags=flags) as process:
            try:
                for line in process.stdout:
                    lines.append(line)
                    if len(lines) > 500:
                        del lines[:100]
                    if line.startswith("out_time_us=") and duration > 0:
                        try:
                            progress(min(1.0, max(0.0, float(line.split("=", 1)[1]) / 1_000_000 / duration)))
                        except ValueError:
                            pass
                code = process.wait()
            except BaseException:
                process.kill()
                process.wait()
                raise
    except OSError as exc:
        raise MediaError(str(exc)) from exc
    output = "".join(lines)
    if code:
        LOG.error("FFmpeg: %s", output)
        raise MediaError(output[-3500:].strip())
    progress(1.0)
    return output


@dataclass
class Media:
    path: Path
    streams: list[dict] = field(default_factory=list)
    duration: float = 0
    error: str = ""

    @property
    def audio(self):
        return [s for s in self.streams if s.get("codec_type") == "audio"]

    @property
    def video(self):
        return [s for s in self.streams if s.get("codec_type") == "video"]

    def suggested_track(self) -> int | None:
        if len(self.audio) == 1:
            return 0
        defaults = [i for i, s in enumerate(self.audio) if s.get("disposition", {}).get("default") == 1]
        return defaults[0] if len(defaults) == 1 else None


def probe(tools: Tools, path: Path) -> Media:
    raw = json.loads(run([str(tools.ffprobe), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], timeout=60))
    streams = raw.get("streams", [])
    durations = [raw.get("format", {}).get("duration", 0)] + [s.get("duration", 0) for s in streams]
    return Media(path, streams, max((float(d) for d in durations if d not in (None, "N/A")), default=0))


def validate_folders(source: Path, destination: Path):
    if not source.is_dir():
        raise MediaError("Vstupní složka neexistuje.")
    if source.resolve() == destination.resolve():
        raise MediaError("Vstupní a výstupní složka musí být různé.")
    if source.resolve().is_relative_to(destination.resolve()):
        raise MediaError("Výstupní složka nesmí být nadřazená vstupní složce.")


def scan(tools: Tools, source: Path, destination: Path, recursive: bool, notify=lambda *_: None) -> list[Media]:
    validate_folders(source, destination)
    paths = []
    for directory, dirs, files in os.walk(source, followlinks=False):
        root = Path(directory)
        dirs[:] = sorted(d for d in dirs if not (root / d).is_symlink()
                         and (root / d).resolve() != destination.resolve()
                         and not d.startswith(".voice-studio-")) if recursive else []
        paths.extend(root / f for f in sorted(files) if Path(f).suffix.lower() in SUPPORTED and not (root / f).is_symlink())
    results = []
    for i, path in enumerate(paths):
        notify(i / max(1, len(paths)), f"Načítám {path.name}")
        try:
            results.append(probe(tools, path))
        except Exception as exc:
            results.append(Media(path, error=str(exc)))
    return results


def voice_filters(settings: VoiceSettings, tools: Tools) -> str:
    filters = ["highpass=f=65:p=2"]
    for level, name in ((settings.clarity, "afftdn"), (settings.deessing, "deesser"), (settings.pitch, "rubberband")):
        if level and name not in tools.filters:
            raise MediaError(f"Tento FFmpeg nepodporuje filtr {name}. Vypněte příslušný posuvník nebo zvolte plnou sestavu FFmpegu.")
    if settings.clarity:
        filters.append(f"afftdn=nr={2 + settings.clarity * .1:.3f}:nf=-50:tn=1:gs=6")
    if settings.pitch:
        filters.append(f"rubberband=tempo=1:pitch={2 ** (settings.pitch / 12):.9f}:formant=preserved:pitchq=quality")
    if settings.fullness:
        filters += [f"bass=g={settings.fullness * .035:.3f}:f=150:w=0.6",
                    f"equalizer=f=320:t=q:w=1:g={-settings.fullness * .012:.3f}"]
    if settings.intelligibility:
        filters.append(f"equalizer=f=3000:t=q:w=0.8:g={settings.intelligibility * .03:.3f}")
    if settings.deessing:
        filters.append(f"deesser=i={settings.deessing * .006:.4f}:m={settings.deessing * .005:.4f}:f=0.5")
    if settings.compression:
        # Conservative soft knee; no automatic makeup gain. Loudnorm handles output gain.
        ratio = 1 + settings.compression * .035
        threshold = 10 ** ((-12 - settings.compression * .12) / 20)
        filters.append(f"acompressor=threshold={threshold:.6f}:ratio={ratio:.3f}:attack=15:release=180:knee=2.8:makeup=1")
    return ",".join(filters)


def loudnorm(target: float, tp=-1.5) -> str:
    return f"loudnorm=I={target}:TP={tp}:LRA=11"


def parse_loudness(output: str) -> dict:
    matches = re.findall(r'\{\s*"input_i".*?\}', output, re.S)
    if not matches:
        raise MediaError("FFmpeg nevrátil měření hlasitosti.")
    return json.loads(matches[-1])


def finite_measurement(data: dict) -> bool:
    return all(math.isfinite(float(data[k])) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset"))


def second_pass(target: float, measurement: dict, tp=-1.5) -> str:
    if not finite_measurement(measurement):
        # FFmpeg loudnorm may produce non-finite samples for digital silence.
        # Never feed these to a PCM encoder. Keep silence/short clips at unity gain.
        return f"alimiter=limit={10 ** (tp / 20):.9f}:level=false:latency=true"
    return (loudnorm(target, tp) + f":measured_I={measurement['input_i']}:measured_TP={measurement['input_tp']}"
            f":measured_LRA={measurement['input_lra']}:measured_thresh={measurement['input_thresh']}"
            f":offset={measurement['target_offset']}:linear=true")


class Processor:
    def __init__(self, tools: Tools):
        self.tools = tools

    def ff(self):
        return [str(self.tools.ffmpeg), "-hide_banner", "-nostdin", "-nostats", "-progress", "pipe:1"]

    def measure(self, path: Path, track: int, chain: str, target: float, notify: Progress = lambda *_: None,
                duration=0, tp=-1.5):
        graph = (chain + "," if chain else "") + loudnorm(target, tp) + ":print_format=json"
        output = run(self.ff() + ["-i", str(path), "-map", f"0:a:{track}", "-vn", "-sn", "-dn", "-af", graph,
                                  "-f", "null", "-"], progress=lambda p: notify(p, "Měřím hlasitost"), duration=duration)
        return parse_loudness(output)

    def process(self, media: Media, track: int, settings: VoiceSettings, destination: Path,
                collision="suffix", notify: Progress = lambda *_: None) -> Path | None:
        if track < 0 or track >= len(media.audio):
            raise MediaError("Neplatný výběr zvukové stopy.")
        if collision not in ("suffix", "skip"):
            raise MediaError("Neplatné řešení kolize názvu.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.resolve() == media.path.resolve():
            raise MediaError("Výstup nesmí přepsat vstup.")
        if destination.exists() and collision == "skip":
            return None
        chain = voice_filters(settings, self.tools)
        channels = int(media.audio[track].get("channels", 2))
        if channels > 2:
            raise MediaError("Vybraná stopa má více než dva kanály. Podporován je mono a stereo hlas.")
        target = settings.target(channels)
        measurement = self.measure(media.path, track, chain, target,
                                   lambda p, s: notify(p * .35, s), media.duration)
        # Same filesystem as final output. A crashed render never appears under the final name.
        with tempfile.TemporaryDirectory(prefix=".voice-studio-", dir=destination.parent) as work:
            temp = Path(work) / ("render" + destination.suffix)
            tp = -1.5
            for attempt in range(3):
                if attempt:
                    measurement = self.measure(media.path, track, chain, target, duration=media.duration, tp=tp)
                args = self.ff() + ["-y", "-copyts", "-start_at_zero", "-i", str(media.path), "-map", "0", "-map_metadata", "0",
                                    "-map_chapters", "0", "-c", "copy", "-c:v", "copy"]
                codec = {".wav": "pcm_s24le", ".mp3": "libmp3lame"}.get(destination.suffix.lower(), "aac")
                args += [f"-c:a:{track}", codec, f"-filter:a:{track}", chain + "," + second_pass(target, measurement, tp),
                         f"-ar:a:{track}", "48000"]
                if codec != "pcm_s24le":
                    args += [f"-b:a:{track}", "256k" if channels > 1 else "192k"]
                if destination.suffix.lower() in (".mp4", ".mov", ".m4a"):
                    args += ["-movflags", "+faststart", "-use_editlist", "1"]
                args += ["-avoid_negative_ts", "disabled", str(temp)]
                run(args, progress=lambda p: notify(.35 + p * .45, "Upravuji zvuk a kopíruji obraz"), duration=media.duration)
                rendered = probe(self.tools, temp)
                if len(rendered.audio) != len(media.audio) or len(rendered.video) != len(media.video):
                    raise MediaError("Počet zvukových nebo obrazových stop se změnil.")
                check = self.measure(temp, track, "", target, lambda p, s: notify(.8 + p * .18, "Kontroluji výstupní špičky"), rendered.duration)
                peak = float(check["input_tp"])
                if peak <= -1.0:
                    break
                tp -= peak + 1.0 + .3
            else:
                raise MediaError("Nepodařilo se dodržet maximální true peak −1 dBTP. Výstup nebyl publikován.")
            # Windows rename never replaces an existing name. POSIX link is an atomic no-clobber publish.
            candidate = destination
            count = 2
            while True:
                try:
                    if os.name == "nt":
                        os.rename(temp, candidate)
                    else:
                        os.link(temp, candidate)
                        temp.unlink()
                    break
                except FileExistsError:
                    if collision == "skip":
                        return None
                    candidate = destination.with_stem(destination.stem + f"_{count}")
                    count += 1
            notify(1.0, "Hotovo")
            return candidate

    def preview(self, media: Media, track: int, settings: VoiceSettings, folder: Path, start=0.0, seconds=15.0,
                notify: Progress = lambda *_: None) -> tuple[Path, Path]:
        if track < 0 or track >= len(media.audio):
            raise MediaError("Neplatná zvuková stopa.")
        if int(media.audio[track].get("channels", 2)) > 2:
            raise MediaError("Náhled podporuje mono a stereo.")
        folder.mkdir(parents=True, exist_ok=True)
        raw, original, processed = (folder / n for n in ("segment.wav", "original.wav", "processed.wav"))
        run(self.ff() + ["-y", "-ss", str(start), "-i", str(media.path), "-t", str(seconds), "-map", f"0:a:{track}",
                         "-vn", "-c:a", "pcm_f32le", "-ar", "48000", str(raw)],
            progress=lambda p: notify(p * .1, "Připravuji ukázku"), duration=seconds)
        # Both versions independently normalized to the same LUFS target; original otherwise unfiltered.
        target = settings.target(int(media.audio[track].get("channels", 2)))
        for i, (chain, path) in enumerate((("", original), (voice_filters(settings, self.tools), processed))):
            measurement = self.measure(raw, 0, chain, target,
                                       lambda p, s: notify(.1 + i * .4 + p * .2, s), seconds)
            graph = (chain + "," if chain else "") + second_pass(target, measurement) + ",aresample=48000"
            run(self.ff() + ["-y", "-i", str(raw), "-af", graph, "-c:a", "pcm_s24le", str(path)],
                progress=lambda p: notify(.3 + i * .4 + p * .2, "Vyrovnávám hlasitost ukázek"), duration=seconds)
        notify(1.0, "Ukázka připravena")
        return original, processed


@dataclass
class Job:
    media: Media
    track: int | None


def run_batch(processor: Processor, jobs: list[Job], source: Path, destination: Path,
              settings: VoiceSettings, stop: threading.Event, collision="suffix", event=lambda *_: None):
    validate_folders(source, destination)
    summary = {"done": 0, "errors": 0, "skipped": 0, "pending": len(jobs), "stopped": False}
    for index, job in enumerate(jobs):
        if stop.is_set():
            summary["stopped"] = True
            break
        media = job.media
        event("started", index, media.path.name)
        try:
            if media.error:
                raise MediaError(media.error)
            if not media.audio:
                status, message = "skipped", "Soubor nemá zvukovou stopu."
            elif job.track is None:
                status, message = "skipped", "Přeskočeno při výběru zvukové stopy."
            else:
                relative = media.path.relative_to(source)
                output = destination / relative.with_stem(relative.stem + "_voice")
                result = processor.process(media, job.track, settings, output, collision,
                                           lambda p, s: event("progress", index, (p, s)))
                status, message = ("done", str(result)) if result else ("skipped", "Výstup již existuje.")
            summary[status] += 1
        except Exception as exc:
            LOG.exception("Chyba při zpracování %s", media.path)
            status, message = "errors", str(exc)
            summary[status] += 1
        summary["pending"] -= 1
        event("result", index, (status, message))
        event("progress", index, (1.0, "Soubor dokončen"))
    summary["stopped"] = summary["stopped"] or (stop.is_set() and summary["pending"] > 0)
    return summary
