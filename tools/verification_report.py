"""Summarize the real media left by pytest. Run from the project root."""
import argparse
import hashlib
import json
from pathlib import Path

from voicestudio.engine import Processor, Tools, probe, run


def packet_data(tools, path):
    raw = run([str(tools.ffprobe), "-v", "error", "-select_streams", "v:0", "-show_packets",
               "-show_data_hash", "sha256", "-of", "json", str(path)])
    return json.loads(raw)["packets"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default="test-output/pytest-final")
    args = parser.parse_args()
    tools = Tools.find()
    processor = Processor(tools)
    root = Path(args.root)
    report = {"ffmpeg": run([str(tools.ffmpeg), "-version"]).splitlines()[0], "videos": []}
    for directory in sorted(p for p in root.glob("test_video_bitstream_timestamp*") if p.name[-1].isdigit()):
        source = next(directory.glob("Původní*"))
        destination = next(directory.glob("Výstup*"))
        before, after = packet_data(tools, source), packet_data(tools, destination)
        info, output = probe(tools, source), probe(tools, destination)
        offset = lambda m: float(m.audio[0].get("start_time", 0)) - float(m.video[0].get("start_time", 0))
        measured = processor.measure(destination, 0, "", -16)
        packet_hash = lambda packets: hashlib.sha256("".join(p["data_hash"] for p in packets).encode()).hexdigest()
        report["videos"].append({"format": source.suffix, "packets": len(before),
                                  "video_packet_hash_before": packet_hash(before), "video_packet_hash_after": packet_hash(after),
                                  "max_pts_difference_seconds": max(abs(float(a["pts_time"]) - float(b["pts_time"])) for a, b in zip(before, after)),
                                  "input_av_offset_seconds": offset(info), "output_av_offset_seconds": offset(output),
                                  "input_duration": info.duration, "output_duration": output.duration,
                                  "LUFS": float(measured["input_i"]), "dBTP": float(measured["input_tp"])})
    preview = next(p for p in root.glob("test_preview_matching_loud*") if p.name[-1].isdigit())
    report["preview_LUFS"] = {name: float(processor.measure(preview / name, 0, "", -16)["input_i"])
                              for name in ("original.wav", "processed.wav")}
    destination = Path("test-output/verification.json")
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
