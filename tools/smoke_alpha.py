"""Test our own packaged alpha in an isolated, temporary Windows profile."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import time


@contextmanager
def temporary_profile():
    directory = tempfile.TemporaryDirectory(prefix="dolad-it-smoke-")
    try:
        yield Path(directory.name)
    finally:
        # DLL handles and antivirus scanners can release files just after process exit.
        for attempt in range(40):
            try:
                directory.cleanup()
                break
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(.2)


def main():
    root = Path(__file__).resolve().parent.parent
    metadata = runpy.run_path(str(root / "voicestudio" / "__init__.py"))
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=root / "release" / (metadata["EXE_BASENAME"] + ".exe"))
    parser.add_argument("--report", type=Path, default=root / "reports" / "exe-startup.json")
    args = parser.parse_args()
    executable = args.exe.resolve(strict=True)
    import pefile
    pe = pefile.PE(str(executable))
    try:
        assert pe.VS_FIXEDFILEINFO[0].FileFlags & 0x2, "V EXE chybí příznak předběžného vydání."
        strings = {key.decode(): value.decode() for group in pe.FileInfo for table in group
                   if table.Key == b"StringFileInfo" for block in table.StringTable
                   for key, value in block.entries.items()}
        assert strings["ProductVersion"] == metadata["__version__"], strings
        assert strings["FileDescription"] == metadata["APP_TITLE"], strings
    finally:
        pe.close()
    with executable.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()

    with temporary_profile() as work:
        (work / "tmp").mkdir()
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["APPDATA"] = str(work / "profile")
        env["TEMP"] = env["TMP"] = str(work / "tmp")
        env.pop("VOICE_STUDIO_FFMPEG", None)
        windows = Path(env.get("SystemRoot", r"C:\Windows"))
        env["PATH"] = str(windows / "System32") + os.pathsep + str(windows)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        kernel.CreateJobObjectW.restype = ctypes.c_void_p
        kernel.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        kernel.QueryInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                                                      ctypes.c_ulong, ctypes.c_void_p]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        class Accounting(ctypes.Structure):
            _fields_ = [("user", ctypes.c_int64), ("kernel", ctypes.c_int64),
                        ("period_user", ctypes.c_int64), ("period_kernel", ctypes.c_int64),
                        ("faults", ctypes.c_ulong), ("total", ctypes.c_ulong),
                        ("active", ctypes.c_ulong), ("terminated", ctypes.c_ulong)]
        job = kernel.CreateJobObjectW(None, None)
        if not job:
            raise ctypes.WinError(ctypes.get_last_error())
        child = None
        with (work / "stdio.log").open("w", encoding="utf-8") as output:
            try:
                child = subprocess.Popen([str(executable)], cwd=work, env=env,
                                         stdin=subprocess.DEVNULL, stdout=output, stderr=output)
                if not kernel.AssignProcessToJobObject(job, int(child._handle)):
                    child.terminate()
                    raise ctypes.WinError(ctypes.get_last_error())
                log = work / "profile" / "VoiceStudio" / "voice-studio.log"
                deadline = time.monotonic() + 50
                text = ""
                ready = False
                while time.monotonic() < deadline and child.poll() is None:
                    if log.exists():
                        text = log.read_text(encoding="utf-8")
                        if "ERROR" in text:
                            break
                        if "FFmpeg připraveno:" in text:
                            ready = True
                            break
                    time.sleep(.2)
                if ready:
                    time.sleep(1)
                assert ready and child.poll() is None, (text, (work / "stdio.log").read_text(encoding="utf-8"))
                report = {"version": metadata["__version__"], "executable": executable.name,
                          "windows_prerelease_flag": True, "gui_started": True,
                          "bundled_ffmpeg_ready": True, "isolated_profile": True,
                          "sha256": checksum}
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(json.dumps(report, ensure_ascii=False), flush=True)
            finally:
                if child:
                    kernel.TerminateJobObject(job, 0)
                    child.wait(timeout=15)
                    deadline = time.monotonic() + 10
                    accounting = Accounting()
                    while time.monotonic() < deadline:
                        if not kernel.QueryInformationJobObject(job, 1, ctypes.byref(accounting),
                                                                 ctypes.sizeof(accounting), None):
                            raise ctypes.WinError(ctypes.get_last_error())
                        if accounting.active == 0:
                            break
                        time.sleep(.05)
                kernel.CloseHandle(job)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
