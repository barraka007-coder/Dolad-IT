"""Build the self-contained Windows alpha; discard intermediate files automatically."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone


def main():
    root = Path(__file__).resolve().parent.parent
    metadata = runpy.run_path(str(root / "voicestudio" / "__init__.py"))
    release = root / "release"
    name = metadata["EXE_BASENAME"] + ".exe"
    with tempfile.TemporaryDirectory(prefix="dolad-it-build-") as workspace:
        work = Path(workspace)
        subprocess.run([
            sys.executable, "-m", "PyInstaller", "--noconfirm",
            "--workpath", str(work / "work"), "--distpath", str(work / "output"),
            str(root / "DoladIT.spec"),
        ], cwd=root, check=True)
        built = work / "output" / name
        release.mkdir(parents=True, exist_ok=True)
        descriptor, staged_name = tempfile.mkstemp(prefix=".dolad-it-", suffix=".partial", dir=release)
        os.close(descriptor)
        staged = Path(staged_name)
        try:
            shutil.copyfile(built, staged)
            os.replace(staged, release / name)
        finally:
            staged.unlink(missing_ok=True)
    with (release / name).open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    (release / "SHA256SUMS.txt").write_text(f"{checksum}  {name}\n", encoding="utf-8")
    info = {
        "name": metadata["APP_NAME"], "version": metadata["__version__"],
        "display_version": metadata["DISPLAY_VERSION"], "channel": "alpha",
        "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "executable": name, "sha256": checksum, "ffmpeg_bundled": True,
    }
    (release / "release-info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Hotovo: {release / name}", flush=True)


if __name__ == "__main__":
    main()
