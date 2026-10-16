#!/usr/bin/env python3
"""Export a DJI DNG sequence without changing originals or replacing an MP4."""

import argparse
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile


class ExportError(Exception):
    """An actionable export failure."""


def find_frames(source):
    if not source.is_dir():
        raise ExportError(f"Source folder not found: {source}")
    frames = []
    for path in source.iterdir():
        if path.suffix.lower() != ".dng":
            continue
        if not path.is_file() or not re.fullmatch(r"TIMELAPSE_[0-9]{4}\.DNG", path.name):
            raise ExportError(f"Malformed or non-DJI DNG filename: {path.name}")
        frames.append(path)
    frames.sort()
    if not frames:
        raise ExportError(f"No TIMELAPSE_####.DNG frames in {source}")
    for number, frame in enumerate(frames, 1):
        expected = f"TIMELAPSE_{number:04d}.DNG"
        if frame.name != expected:
            raise ExportError(f"Sequence is not contiguous; missing {expected}")
    return frames


def ensure_available(source, output):
    for path in (output, output.parent / f"timelapse_{source.name}_30fps.mp4"):
        if os.path.lexists(path):
            raise ExportError(f"Output already exists: {path}")


def make_plan(source, root, output_dir, fps):
    if fps <= 0:
        raise ExportError("Frame rate must be a positive integer")
    destination = Path(output_dir).expanduser().resolve() if output_dir else None
    if destination and not destination.is_dir():
        raise ExportError(f"Output directory not found: {destination}")
    if source is None:
        root = Path(root).expanduser().resolve()
        if not root.is_dir():
            raise ExportError(f"Timelapse root not found: {root}; pass a source folder or --root")
        for candidate in sorted(root.iterdir(), key=lambda p: p.name):
            if not candidate.is_dir():
                continue
            try:
                return make_plan(candidate, root, destination, fps)
            except ExportError:
                continue
        raise ExportError(f"No valid, unrendered, unlocked DJI sequence under {root}")
    source = Path(source).expanduser().resolve()
    frames = find_frames(source)
    output = (destination or source.parent) / f"{source.name}.mp4"
    ensure_available(source, output)
    if os.path.lexists(str(output) + ".lock"):
        raise ExportError(f"Render lock exists: {output}.lock")
    return {"source": source, "output": output, "frames": frames, "fps": fps}


def run_tool(arguments):
    result = subprocess.run(arguments, capture_output=True, text=True, encoding="utf-8",
                            errors="replace")
    if result.returncode:
        raise ExportError(f"{Path(arguments[0]).name} failed: {result.stderr.strip()[-4000:]}")
    return result.stdout


def check_dependencies():
    missing = [name for name in ("ffmpeg", "ffprobe") if not shutil.which(name)]
    if missing:
        raise ExportError(f"Missing on PATH: {', '.join(missing)}. See references/setup.md.")
    try:
        import rawpy
    except ImportError as exc:
        raise ExportError("Install the skill's requirements.txt using this Python interpreter") from exc
    encoders = run_tool(["ffmpeg", "-hide_banner", "-encoders"])
    if not re.search(r"\blibx264\b", encoders):
        raise ExportError("This FFmpeg build lacks libx264; install a build with H.264 encoding")
    run_tool(["ffprobe", "-version"])
    return {"rawpy": rawpy.__version__, "ffmpeg": shutil.which("ffmpeg"),
            "ffprobe": shutil.which("ffprobe"), "encoder": "libx264"}


def develop_frame(path):
    import rawpy

    try:
        with rawpy.imread(str(path)) as raw:
            return raw.postprocess(
                demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
                use_camera_wb=True, use_auto_wb=False, no_auto_bright=True,
                # LibRaw's separate maximum adjustment can brighten individual frames.
                adjust_maximum_thr=0.0,
                highlight_mode=rawpy.HighlightMode.Blend,
                output_color=rawpy.ColorSpace.sRGB, output_bps=8,
            )
    except Exception as exc:
        raise ExportError(f"Could not develop {path.name}: {exc}") from exc


def encode_video(frames, fps, temporary):
    first = develop_frame(frames[0])
    original_shape = first.shape
    height, width = (first.shape[0] // 2 * 2, first.shape[1] // 2 * 2)
    if not height or not width:
        raise ExportError("Developed frame dimensions are too small")
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{width}x{height}",
        "-framerate", str(fps), "-i", "pipe:0", "-an",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(temporary),
    ]
    # A file for diagnostics prevents a full stderr pipe from deadlocking the encoder.
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                   stderr=errors)
        try:
            for index, path in enumerate(frames):
                rgb = first if index == 0 else develop_frame(path)
                if rgb.shape != original_shape:
                    raise ExportError(f"Frame dimensions changed at {path.name}")
                process.stdin.write(rgb[:height, :width].tobytes())
                print(f"Developed {index + 1}/{len(frames)}: {path.name}", file=sys.stderr)
            process.stdin.close()
            if process.wait():
                errors.seek(0)
                raise ExportError(f"FFmpeg encoding failed: {errors.read().decode(errors='replace')[-4000:]}")
        except BrokenPipeError as exc:
            process.wait()
            errors.seek(0)
            raise ExportError(f"FFmpeg stopped: {errors.read().decode(errors='replace')[-4000:]}") from exc
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            if not process.stdin.closed:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
    return width, height


def verify_video(path, frame_count, fps, dimensions):
    try:
        probe = json.loads(run_tool([
            "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,pix_fmt,r_frame_rate,nb_read_frames:format=duration",
            "-of", "json", str(path),
        ]))
        stream = probe["streams"][0]
        width, height = stream["width"], stream["height"]
        duration = float(probe["format"]["duration"])
        valid = (stream["codec_name"] == "h264" and stream["pix_fmt"] == "yuv420p"
                 and int(stream["nb_read_frames"]) == frame_count
                 and Fraction(stream["r_frame_rate"]) == fps
                 and (width, height) == dimensions and width % 2 == height % 2 == 0
                 and math.isfinite(duration) and abs(duration - frame_count / fps) <= 0.05)
    except (KeyError, IndexError, ValueError, TypeError, ZeroDivisionError) as exc:
        raise ExportError(f"Invalid video metadata: {exc}") from exc
    if not valid:
        raise ExportError("Video verification failed (codec, frames, dimensions, rate or duration)")
    run_tool(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-i", str(path), "-f", "null", "-"])
    return {"frames": frame_count, "width": width, "height": height,
            "fps": fps, "duration": duration, "codec": "h264", "pixel_format": "yuv420p"}


def publish_video(temporary, output):
    # link() is an atomic no-replace operation on APFS/NTFS and keeps incomplete
    # videos private. An exists()+replace() pair would have an overwrite race.
    try:
        os.link(temporary, output)
    except FileExistsError as exc:
        raise ExportError(f"Output appeared during rendering: {output}") from exc
    except OSError as exc:
        raise ExportError("Cannot publish atomically. Use --output-dir on a local APFS/NTFS "
                          f"disk that supports hard links: {exc}") from exc
    temporary.unlink()


def export(plan):
    check_dependencies()
    source, output = plan["source"], plan["output"]
    lock = Path(str(output) + ".lock")
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise ExportError(f"Render lock exists: {lock}") from exc
    try:
        ensure_available(source, output)
        with tempfile.TemporaryDirectory(prefix=".dji-export-", dir=output.parent) as work:
            temporary = Path(work) / "render.mp4"
            dimensions = encode_video(plan["frames"], plan["fps"], temporary)
            report = verify_video(temporary, len(plan["frames"]), plan["fps"], dimensions)
            ensure_available(source, output)
            publish_video(temporary, output)
        return {"output": str(output), **report}
    finally:
        lock.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", help="Folder containing TIMELAPSE_0001.DNG onwards")
    parser.add_argument("--root", default=os.environ.get("TIMELAPSE_ROOT", str(Path.home() / "Pictures/TIMELAPSE")),
                        help="Scan immediate subfolders if no source is given")
    parser.add_argument("--fps", type=int, default=os.environ.get("TIMELAPSE_FPS", "30"))
    parser.add_argument("--output-dir", type=Path, help="Existing destination directory; default: beside source")
    parser.add_argument("--dry-run", action="store_true", help="Validate and preview without dependencies or writes")
    parser.add_argument("--check", action="store_true", help="Check dependencies without rendering")
    args = parser.parse_args()
    try:
        if args.check:
            report = check_dependencies()
        else:
            plan = make_plan(args.source, args.root, args.output_dir, args.fps)
            if args.dry_run:
                report = {"source": str(plan["source"]), "output": str(plan["output"]),
                          "frames": len(plan["frames"]), "fps": plan["fps"],
                          "duration": len(plan["frames"]) / plan["fps"]}
            else:
                report = export(plan)
        print(json.dumps(report, indent=2, ensure_ascii=True))
        return 0
    except (ExportError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Export cancelled; source files preserved.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(130))
    sys.exit(main())
