---
name: dji-export
description: Use when exporting DJI Action TIMELAPSE_####.DNG sequences to MP4 on macOS or Windows, including folders under Pictures/TIMELAPSE.
---

# DJI Export

Export a DJI Action DNG timelapse to a watermark-free H.264 MP4 using one Python workflow on macOS and Windows. Read originals in place and publish only a verified video.

## Setup

Resolve paths below relative to this `SKILL.md`. Follow [platform setup](references/setup.md) for Python 3.13, rawpy, FFmpeg/ffprobe and a dedicated virtual environment. Use that environment's Python for every command; no Bash, WSL or PowerShell activation is required on Windows.

Run `python scripts/export_timelapse.py --check` before rendering. If dependencies are missing, follow the setup instructions for the host platform.

## Workflow

1. Use the user's source folder, or scan `~/Pictures/TIMELAPSE` (`--root` or `TIMELAPSE_ROOT` overrides it). Automatic selection chooses the first sorted, valid, unrendered, unlocked immediate subfolder. Invalid or completed folders are skipped.
2. Preview with `--dry-run`. Review the selected source, output, frame count, fps and expected duration. Preview reads filenames only; it does not decode RAW files or validate dependencies.
3. Render with the same arguments, omitting `--dry-run`.
4. Report the JSON result's output path, verified frame count, dimensions, fps and duration. A nonzero exit is a failure; do not claim an MP4 was created.

Examples below assume `python` resolves to the prepared environment; platform-specific full commands are in setup.

| Need | Command |
|---|---|
| Preview next sequence | `python scripts/export_timelapse.py --dry-run` |
| Specific folder, including spaces | `python scripts/export_timelapse.py "path/to/DJI trip"` |
| Change frame rate | `python scripts/export_timelapse.py "path/to/DJI trip" --fps 24` |
| Scan another root | `python scripts/export_timelapse.py --root "path/to/TIMELAPSE"` |
| Keep output on a local disk | `python scripts/export_timelapse.py "path/to/DJI trip" --output-dir "path/to/Exports"` |

## Output and boundaries

- Require uppercase `TIMELAPSE_0001.DNG` through a contiguous four-digit sequence; reject gaps, malformed extra DNG names and empty folders. Other DJI video/photo formats are outside this skill's scope.
- Default output is sibling `<source-folder>.mp4`; `--output-dir` changes its directory, never its filename. Refuse existing current or legacy `timelapse_<folder>_30fps.mp4` exports.
- Develop RAW using camera white balance, AHD demosaicing and highlight blending, with automatic brightness, per-frame maximum adjustment and automatic white balance disabled. Stream RGB frames to FFmpeg; no intermediate image collection is needed.
- Encode H.264/yuv420p, CRF 18, fast preset, fast-start metadata, 30 fps by default (`--fps` or `TIMELAPSE_FPS`). Preserve native dimensions, cropping at most one row/column to make them even.
- Verify metadata, frame count, duration and full decode before atomic publication. Use a unique temporary directory and output lock. Never modify, rename or delete source DNG files.
- Publication requires hard-link support (normally APFS/NTFS); for SD cards, exFAT or restricted network volumes, choose an existing local `--output-dir`. See setup for interrupted-render recovery.

Do not feed DNG files directly to FFmpeg or bypass verification to produce a final file.
