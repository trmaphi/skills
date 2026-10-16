# Platform setup

Use 64-bit Python 3.13 and FFmpeg with `libx264`, including `ffprobe`. RAW development uses [rawpy/LibRaw](https://github.com/letmaik/rawpy), with binary wheels for macOS and Windows. No DJI software, `dcraw`, `cjpeg`, Bash or WSL is required.

The commands assume your current directory is the installed `dji-export` folder containing `SKILL.md`, `requirements.txt` and `scripts/`. Replace example media paths with your own. Keep the environment outside the skill so updates do not remove dependencies.

## macOS — Terminal (zsh or Bash)

With [Homebrew](https://brew.sh/) available:

```sh
brew install python@3.13 ffmpeg
python3.13 -m venv "$HOME/.venvs/dji-export"
"$HOME/.venvs/dji-export/bin/python" -m pip install -r requirements.txt
"$HOME/.venvs/dji-export/bin/python" scripts/export_timelapse.py --check
```

Preview, then export:

```sh
"$HOME/.venvs/dji-export/bin/python" scripts/export_timelapse.py "$HOME/Pictures/TIMELAPSE/DJI trip" --dry-run
"$HOME/.venvs/dji-export/bin/python" scripts/export_timelapse.py "$HOME/Pictures/TIMELAPSE/DJI trip"
```

Homebrew's [Python formula](https://formulae.brew.sh/formula/python@3.13) and [FFmpeg formula](https://formulae.brew.sh/formula/ffmpeg) document their installation paths. On older Macs, use a supported Python installer from [python.org](https://www.python.org/downloads/macos/) and an FFmpeg build linked from the [official download page](https://ffmpeg.org/download.html).

## Windows — PowerShell

Install with Windows Package Manager, or use an existing Python 3.13 and FFmpeg installation:

```powershell
winget install --exact --id Python.Python.3.13
winget install --exact --id Gyan.FFmpeg
```

Open a new PowerShell window so PATH updates take effect, then return to the installed `dji-export` folder:

```powershell
py -3.13 -m venv "$HOME\.venvs\dji-export"
$DjiPython = "$HOME\.venvs\dji-export\Scripts\python.exe"
& $DjiPython -m pip install -r requirements.txt
& $DjiPython scripts/export_timelapse.py --check
```

Continue only after dependency installation and `--check` succeed. If either fails, resolve the reported error and rerun it before exporting:

```powershell
& $DjiPython scripts/export_timelapse.py "C:\Users\Alex\Pictures\TIMELAPSE\DJI trip" --dry-run
& $DjiPython scripts/export_timelapse.py "C:\Users\Alex\Pictures\TIMELAPSE\DJI trip"
```

The call operator `&` runs a quoted executable path; no execution-policy changes or virtual-environment activation scripts are needed. If `py` is unavailable, confirm that `python` on PATH is 64-bit Python 3.13, then use `python -m venv` instead. Windows on ARM and 32-bit Python are not tested; use an x64 Python environment with available rawpy wheels.

[Gyan.FFmpeg is listed in Microsoft's winget manifests](https://github.com/microsoft/winget-pkgs/tree/master/manifests/g/Gyan/FFmpeg). FFmpeg's own [download page](https://ffmpeg.org/download.html) also links Windows build providers. If installing manually, add the directory containing both `ffmpeg.exe` and `ffprobe.exe` to PATH.

## Defaults and troubleshooting

- `--help` lists options. `--check` checks dependencies and encoder availability without reading media. `--dry-run` validates names and output availability without decoding media, checking dependencies or writing files.
- Without a source argument, scan `Path.home()/Pictures/TIMELAPSE`. OneDrive or relocated Pictures folders need an explicit `--root`. Only immediate subfolders are considered; invalid, completed and locked sequences are skipped.
- `--fps` overrides `TIMELAPSE_FPS`; default is 30. Frame rate must be a positive integer. `--root` overrides `TIMELAPSE_ROOT`.
- Close camera recording and finish copying the entire sequence before exporting. New or unsupported camera DNG variants may need a newer rawpy/LibRaw; an unreadable frame stops the export.
- Output defaults to a sibling `<folder>.mp4`. To read an SD card/exFAT volume while writing safely to local storage, use `--output-dir` with an existing APFS/NTFS folder. The temporary MP4 is created on that destination filesystem; hard-link support is required for atomic publication without overwriting.
- An existing current/legacy MP4 is preserved. Choose a different `--output-dir` to create a separate export; there is no overwrite flag.
- A `<output>.lock` directory prevents concurrent renders. On errors or Ctrl+C, owned locks and temporary files are cleaned. After a crash, power loss or forced termination, first confirm no exporter is running; then remove only the stale lock and matching `.dji-export-*` temporary directory. Never remove another active render's files.
- Camera white balance and fixed development settings reduce processing-induced flicker; they cannot remove exposure changes recorded by the camera. Both `no_auto_bright=True` and `adjust_maximum_thr=0.0` are needed to disable LibRaw's automatic brightness adjustments; see the [maintainer's explanation](https://www.libraw.org/node/2325). Color and image quality should still be reviewed on real footage.
- RAW decoding/encoding runs locally. No media is uploaded. Output has no audio or watermark.
