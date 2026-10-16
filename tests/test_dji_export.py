"""Safety checks and a real, synthetic DNG → H.264 integration test."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "dji-export/scripts/export_timelapse.py"
spec = importlib.util.spec_from_file_location("dji_export", SCRIPT)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def make_dng(path, offset=0, pixels=None):
    """Create our own tiny Bayer DNG; no camera photos or downloaded fixtures."""
    import numpy as np
    import tifffile

    if pixels is None:
        pixels = (np.arange(96 * 64).reshape(64, 96) % 3000 + 128 + offset).astype("uint16")
    identity = (1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1)
    tifffile.imwrite(path, pixels, photometric=32803, metadata=None, extratags=[
        (50706, "B", 4, (1, 4, 0, 0), False),
        (50707, "B", 4, (1, 1, 0, 0), False),
        (50708, "s", 0, "Synthetic DJI Export Test", False),
        (33421, "H", 2, (2, 2), False),
        (33422, "B", 4, (0, 1, 1, 2), False),
        (50721, "2i", 9, identity, False),
        (50728, "2I", 3, (1, 1, 1, 1, 1, 1), False),
        (50714, "H", 1, 64, False),
        (50717, "I", 1, 4095, False),
        (50778, "H", 1, 21, False),
    ])


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "DJI trip ü with spaces"
        self.source.mkdir()

    def sequence(self, numbers=(1, 2, 3)):
        for number in numbers:
            (self.source / f"TIMELAPSE_{number:04d}.DNG").write_bytes(b"raw-placeholder")

    def test_contiguous_sequence_in_numeric_order(self):
        self.sequence((3, 1, 2))
        self.assertEqual([p.name for p in exporter.find_frames(self.source)],
                         [f"TIMELAPSE_{n:04d}.DNG" for n in (1, 2, 3)])

    def test_reject_empty_gaps_and_malformed_extras(self):
        with self.assertRaises(exporter.ExportError):
            exporter.find_frames(self.source)
        self.sequence((1, 3))
        with self.assertRaisesRegex(exporter.ExportError, "0002"):
            exporter.find_frames(self.source)
        self.sequence((2,))
        (self.source / "other.dng").touch()
        with self.assertRaisesRegex(exporter.ExportError, "filename"):
            exporter.find_frames(self.source)

    def test_existing_current_or_legacy_export_is_refused(self):
        self.sequence()
        output = self.root / f"{self.source.name}.mp4"
        for target in (output, self.root / f"timelapse_{self.source.name}_30fps.mp4"):
            target.write_bytes(b"keep")
            with self.assertRaisesRegex(exporter.ExportError, "exists"):
                exporter.make_plan(self.source, self.root, None, 30)
            self.assertEqual(target.read_bytes(), b"keep")
            target.unlink()

    def test_broken_output_symlink_is_not_overwritten(self):
        self.sequence()
        output = self.root / f"{self.source.name}.mp4"
        try:
            output.symlink_to(self.root / "missing.mp4")
        except OSError:
            self.skipTest("symlink creation is not permitted on this runner")
        with self.assertRaisesRegex(exporter.ExportError, "exists"):
            exporter.make_plan(self.source, self.root, None, 30)

    def test_scan_skips_invalid_completed_and_locked_folders(self):
        self.source.rename(self.root / "a-empty")
        for name in ("b-done", "c-locked", "d-next"):
            folder = self.root / name
            folder.mkdir()
            (folder / "TIMELAPSE_0001.DNG").touch()
        (self.root / "b-done.mp4").touch()
        (self.root / "c-locked.mp4.lock").mkdir()
        plan = exporter.make_plan(None, self.root, None, 24)
        self.assertEqual(plan["source"].name, "d-next")
        self.assertEqual(plan["fps"], 24)

    def test_invalid_frame_rates(self):
        self.sequence()
        for rate in (0, -1):
            with self.assertRaises(exporter.ExportError):
                exporter.make_plan(self.source, self.root, None, rate)

    def test_remote_highlights_do_not_change_constant_region_exposure(self):
        import numpy as np

        developed = []
        for number, maximum in enumerate((2500, 3500), 1):
            pixels = np.full((64, 96), 1000, dtype=np.uint16)
            pixels[:16, :16] = maximum
            path = self.source / f"TIMELAPSE_{number:04d}.DNG"
            make_dng(path, pixels=pixels)
            developed.append(exporter.develop_frame(path))
        # The distant highlight changes; this region's RAW values and metadata do not.
        np.testing.assert_array_equal(developed[0][32:48, 48:64], developed[1][32:48, 48:64])

    def test_custom_destination_preserves_folder_name(self):
        self.sequence()
        destination = self.root / "Local exports"
        destination.mkdir()
        plan = exporter.make_plan(self.source, self.root, destination, 30)
        self.assertEqual(plan["output"], destination.resolve() / f"{self.source.name}.mp4")
        with self.assertRaisesRegex(exporter.ExportError, "directory"):
            exporter.make_plan(self.source, self.root, self.root / "missing", 30)

    def test_publication_refuses_racing_output(self):
        temporary = self.root / "temporary.mp4"
        output = self.root / "existing.mp4"
        temporary.write_bytes(b"new")
        output.write_bytes(b"old")
        with self.assertRaises(exporter.ExportError):
            exporter.publish_video(temporary, output)
        self.assertEqual(output.read_bytes(), b"old")
        self.assertEqual(temporary.read_bytes(), b"new")

    def test_development_failure_cleans_temp_and_owned_lock(self):
        self.sequence()
        plan = exporter.make_plan(self.source, self.root, None, 30)
        with patch.object(exporter, "check_dependencies"), patch.object(
            exporter, "encode_video", side_effect=exporter.ExportError("bad RAW")
        ):
            with self.assertRaisesRegex(exporter.ExportError, "bad RAW"):
                exporter.export(plan)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [self.source.name])

    def test_foreign_lock_is_preserved(self):
        self.sequence()
        plan = exporter.make_plan(self.source, self.root, None, 30)
        lock = self.root / f"{self.source.name}.mp4.lock"
        lock.mkdir()
        (lock / "owner").write_text("someone else")
        with patch.object(exporter, "check_dependencies"):
            with self.assertRaisesRegex(exporter.ExportError, "lock"):
                exporter.export(plan)
        self.assertEqual((lock / "owner").read_text(), "someone else")

    def test_preview_requires_no_decoder_or_encoder_and_writes_nothing(self):
        self.sequence()
        result = subprocess.run([os.sys.executable, str(SCRIPT), str(self.source),
                                 "--dry-run", "--fps", "24"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        preview = json.loads(result.stdout)
        self.assertEqual(preview["frames"], 3)
        self.assertEqual(preview["fps"], 24)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [self.source.name])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_corrupt_raw_leaves_no_video_lock_or_temporary_files(self):
        self.sequence()
        originals = {p.name: p.read_bytes() for p in self.source.iterdir()}
        result = subprocess.run([os.sys.executable, str(SCRIPT), str(self.source)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Could not develop", result.stderr)
        self.assertEqual(originals, {p.name: p.read_bytes() for p in self.source.iterdir()})
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [self.source.name])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_real_dng_export_decode_source_preservation_and_no_overwrite(self):
        for number in (1, 2, 3):
            make_dng(self.source / f"TIMELAPSE_{number:04d}.DNG", number * 10)
        originals = {p.name: p.read_bytes() for p in self.source.iterdir()}
        command = [os.sys.executable, str(SCRIPT), str(self.source), "--fps", "24"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["frames"], 3)
        self.assertEqual(report["fps"], 24)
        self.assertEqual(report["codec"], "h264")
        self.assertGreater(report["width"], 0)
        self.assertGreater(report["height"], 0)
        self.assertAlmostEqual(report["duration"], 3 / 24, delta=0.05)
        self.assertEqual(originals, {p.name: p.read_bytes() for p in self.source.iterdir()})
        output = Path(report["output"])
        with self.assertRaisesRegex(exporter.ExportError, "verification"):
            exporter.verify_video(output, 4, 24, (report["width"], report["height"]))
        before = output.read_bytes()
        rerun = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(rerun.returncode, 0)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),
                         sorted([self.source.name, output.name]))


if __name__ == "__main__":
    unittest.main()
