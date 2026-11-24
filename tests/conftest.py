import math
import os
import random
import struct
import wave
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from voicestudio.engine import Processor, Tools, run


@pytest.fixture(scope="session")
def tools():
    return Tools.find()


@pytest.fixture(scope="session")
def processor(tools):
    return Processor(tools)


@pytest.fixture(scope="session")
def sample(tmp_path_factory):
    path = tmp_path_factory.mktemp("ukázky s mezerou") / "Řeč žluťoučká.wav"
    rng = random.Random(42)
    rate = 48000
    frames = bytearray()
    for i in range(rate * 8):
        t = i / rate
        env = (.12 + .55 * math.sin(t * 2.3) ** 2) * (1 if int(t * 3) % 5 else .02)
        if t < .7:
            value = 0
        else:
            value = env * sum(math.sin(2 * math.pi * (125 + 6 * math.sin(t * 2)) * h * t) / h
                              for h in range(1, 15)) * .17 + rng.uniform(-.001, .001)
        frames.extend(struct.pack("<h", int(max(-1, min(1, value)) * 32767)))
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        output.writeframes(frames)
    return path


@pytest.fixture
def make_video(tools, sample):
    def make(path: Path, *, tracks=1, delay=0, stereo=False):
        args = [str(tools.ffmpeg), "-hide_banner", "-nostdin", "-v", "error", "-y",
                "-f", "lavfi", "-i", "testsrc2=size=256x144:rate=25:duration=8"]
        for _ in range(tracks):
            args += ["-itsoffset", str(delay), "-i", str(sample)]
        args += ["-map", "0:v"]
        for i in range(tracks):
            args += ["-map", f"{i+1}:a"]
        args += ["-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-b:a", "128k"]
        if stereo:
            args += ["-ac", "2"]
        for i in range(tracks):
            args += [f"-metadata:s:a:{i}", f"title=Stopa {i+1}", f"-disposition:a:{i}", "0"]
        args += [str(path)]
        run(args)
        return path
    return make
