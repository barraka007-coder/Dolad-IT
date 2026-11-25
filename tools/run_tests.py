"""Run media tests without leaving generated audio, video or cache in the project."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parent.parent
    reports = root / "reports"
    reports.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix="dolad-it-tests-") as workspace:
        work = Path(workspace)
        (work / "tmp").mkdir()
        env["TMP"] = env["TEMP"] = str(work / "tmp")
        code = subprocess.run([
            sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "--basetemp", str(work / "media"), "--junitxml", str(reports / "pytest-results.xml"),
        ], cwd=root, env=env).returncode
        if code:
            return code
        subprocess.run([
            sys.executable, "-m", "tools.verification_report", str(work / "media"),
            "--output", str(reports / "verification.json"),
        ], cwd=root, env=env, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
