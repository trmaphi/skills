---
name: creating-dji-action-timelapses
description: Use when converting numbered DJI Action DNG or RAW timelapse folders into watermark-free MP4 videos, especially under a TIMELAPSE directory.
---

# Creating DJI Action Timelapses

## Overview

Create a high-quality H.264 video from a DJI Action `TIMELAPSE_####.DNG` sequence. Preserve every source file and name the MP4 **exactly after its source folder**.

## Workflow

1. Resolve `scripts/create_timelapse.sh` relative to this `SKILL.md`, then run it with an optional source folder.
2. If no folder is supplied, scan `${HOME}/Pictures/TIMELAPSE` (or `TIMELAPSE_ROOT`) in sorted folder order and select the first DNG sequence without either `<folder>.mp4` or the legacy `timelapse_<folder>_30fps.mp4` output.
3. Report the final path and verified frame count, dimensions, frame rate, and duration.

Example: source folder `001_0068` always produces sibling file `001_0068.mp4`.

## Guarantees and Boundaries

- Use `dcraw` camera white balance and highlight recovery consistently across all frames; do not apply per-frame automatic exposure.
- Encode at native even dimensions, 30 fps by default, H.264/yuv420p, CRF 18, with fast-start metadata and no watermark.
- Require the DJI Action uppercase `TIMELAPSE_0001.DNG`-starting convention and refuse gaps, malformed extras, an existing current or legacy output, missing dependencies, or an empty/non-DJI sequence.
- Write intermediates and the incomplete MP4 only in a unique hidden directory beside the final output so publication is an atomic rename. Publish only after metadata and full-decode verification; always clean temporary files.
- Never rename, modify, move, or delete the DNG originals.

## Quick Reference

| Need | Command |
|---|---|
| Next unrendered sequence | `scripts/create_timelapse.sh` |
| Specific sequence | `scripts/create_timelapse.sh /path/to/001_0068` |
| Different frame rate | `TIMELAPSE_FPS=24 scripts/create_timelapse.sh /path/to/001_0068` |
| Different root | `TIMELAPSE_ROOT=/path/to/TIMELAPSE scripts/create_timelapse.sh` |

## Common Mistakes

- Do not name outputs `timelapse_<folder>_30fps.mp4`; use `<folder>.mp4`.
- Do not encode DNG files directly with FFmpeg; that bypasses useful RAW development and can look severely underexposed.
- Do not publish before the frame-count and full-decode checks pass.
