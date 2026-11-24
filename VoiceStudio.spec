from pathlib import Path

root = Path(SPECPATH)
ffmpeg_dir = root / 'tools' / 'ffmpeg'
binaries = [(str(ffmpeg_dir / name), 'tools/ffmpeg')
            for name in ('ffmpeg.exe', 'ffprobe.exe') if (ffmpeg_dir / name).is_file()]
a = Analysis(['launch.py'], pathex=[str(root)], binaries=binaries, datas=[],
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['tkinter'], noarchive=False)
# Qt 6.12 uses the ICU API provided by Windows 11 itself. PyInstaller can
# accidentally pick an unrelated icuuc.dll from another program on PATH
# (e.g. Poppler); those DLLs expose version-suffixed, incompatible symbols.
# Never redistribute that unsuffixed system dependency or its foreign ICU data.
foreign_icu_roots = {Path(source).parent for destination, source, kind in a.binaries
                     if Path(destination).name.lower() == 'icuuc.dll'}
a.binaries = [(destination, source, kind) for destination, source, kind in a.binaries
              if not (Path(source).parent in foreign_icu_roots
                      and Path(source).name.lower().startswith('icu'))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='Dolaď-IT', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False)
