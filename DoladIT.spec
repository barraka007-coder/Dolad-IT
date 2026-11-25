from pathlib import Path
import runpy

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable,
    VarFileInfo, VarStruct, VSVersionInfo,
)

root = Path(SPECPATH)
metadata = runpy.run_path(str(root / 'voicestudio' / '__init__.py'))
ffmpeg_dir = root / 'tools' / 'ffmpeg'
required = [ffmpeg_dir / name for name in ('ffmpeg.exe', 'ffprobe.exe')]
if not all(path.is_file() for path in required):
    raise SystemExit('Pro samostatné EXE vložte ffmpeg.exe i ffprobe.exe do tools/ffmpeg.')
binaries = [(str(path), 'tools/ffmpeg') for path in required]

a = Analysis(['launch.py'], pathex=[str(root)], binaries=binaries, datas=[],
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['tkinter'], noarchive=False)
# Qt uses Windows 11's own unsuffixed ICU API. Exclude incompatible ICU DLLs
# discovered in unrelated programs on PATH (for example Poppler).
foreign_icu_roots = {Path(source).parent for destination, source, kind in a.binaries
                     if Path(destination).name.lower() == 'icuuc.dll'}
a.binaries = [(destination, source, kind) for destination, source, kind in a.binaries
              if not (Path(source).parent in foreign_icu_roots
                      and Path(source).name.lower().startswith('icu'))]

exe_name = metadata['EXE_BASENAME'] + '.exe'
version = VSVersionInfo(
    ffi=FixedFileInfo(filevers=metadata['VERSION_INFO'], prodvers=metadata['VERSION_INFO'],
                      mask=0x3f, flags=0x2, OS=0x40004, fileType=0x1,
                      subtype=0x0, date=(0, 0)),
    kids=[
        StringFileInfo([StringTable('040504B0', [
            StringStruct('FileDescription', metadata['APP_TITLE']),
            StringStruct('FileVersion', '.'.join(map(str, metadata['VERSION_INFO']))),
            StringStruct('InternalName', 'DoladITAlpha'),
            StringStruct('OriginalFilename', exe_name),
            StringStruct('ProductName', metadata['APP_NAME']),
            StringStruct('ProductVersion', metadata['__version__']),
            StringStruct('Comments', 'Alpha 1'),
        ])]),
        VarFileInfo([VarStruct('Translation', [0x0405, 1200])]),
    ],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name=metadata['EXE_BASENAME'],
          version=version, debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False)
