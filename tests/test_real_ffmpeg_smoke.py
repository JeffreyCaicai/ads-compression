import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = PROJECT_ROOT / "build_windows.ps1"
BIN_DIR = PROJECT_ROOT / "tools" / "ffmpeg" / "bin"
FFMPEG = BIN_DIR / "ffmpeg.exe"
FFPROBE = BIN_DIR / "ffprobe.exe"
HAS_WINDOWS_FFMPEG = os.name == "nt" and FFMPEG.exists() and FFPROBE.exists()

sys.path.insert(0, str(PROJECT_ROOT / "src"))

from auto_detail import build_best_detail_2pass_plan, build_maximum_detail_2pass_plan
from encoder import Encoder
from ffmpeg_utils import probe_video
from models import FFmpegPaths, VideoJob
from quality_check import QualityCheckResult, run_quality_check
from settings import (
    MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
    MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
    PROFILE_BEST_DETAIL_2PASS,
    PROFILE_MAXIMUM_DETAIL_2PASS,
    QUALITY_STATUS_PASSED,
    QUALITY_STATUS_WARNING,
)


class BuildWindowsPreflightTests(unittest.TestCase):
    def test_preflight_checks_bundled_binaries_and_required_capabilities_before_install(self):
        script = BUILD_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('$ffmpegPath = Join-Path $PSScriptRoot "tools\\ffmpeg\\bin\\ffmpeg.exe"', script)
        self.assertIn('$ffprobePath = Join-Path $PSScriptRoot "tools\\ffmpeg\\bin\\ffprobe.exe"', script)
        self.assertIn("Test-Path $ffmpegPath", script)
        self.assertIn("Test-Path $ffprobePath", script)
        self.assertIn('& $ffmpegPath -hide_banner -encoders 2>&1 | Out-String', script)
        self.assertIn('& $ffmpegPath -hide_banner -filters 2>&1 | Out-String', script)
        self.assertEqual(script.count("if ($LASTEXITCODE -ne 0)"), 2)

        encoder_command = script.index('& $ffmpegPath -hide_banner -encoders 2>&1 | Out-String')
        encoder_exit_guard = script.index("if ($LASTEXITCODE -ne 0)", encoder_command)
        encoder_capability_guard = script.index('if ($encoders -notmatch "libx265")', encoder_exit_guard)
        filter_command = script.index('& $ffmpegPath -hide_banner -filters 2>&1 | Out-String')
        filter_exit_guard = script.index("if ($LASTEXITCODE -ne 0)", filter_command)
        filter_capability_guard = script.index('if ($filters -notmatch "ssim")', filter_exit_guard)
        preflight_end = script.index("}", filter_capability_guard)

        self.assertLess(encoder_command, encoder_exit_guard)
        self.assertLess(encoder_exit_guard, encoder_capability_guard)
        self.assertLess(filter_command, filter_exit_guard)
        self.assertLess(filter_exit_guard, filter_capability_guard)
        self.assertNotEqual(encoder_exit_guard, filter_exit_guard)
        self.assertLess(preflight_end, script.index("python -m pip install -r requirements.txt"))
        self.assertLess(preflight_end, script.index("python -m PyInstaller"))


@unittest.skipUnless(HAS_WINDOWS_FFMPEG, "bundled Windows FFmpeg is unavailable")
class RealFFmpegSmokeTests(unittest.TestCase):
    def test_real_two_pass_profiles_preserve_required_output_properties_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp4"
            subprocess.run(
                [
                    str(FFMPEG),
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=320x180:rate=30",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=1000:sample_rate=48000",
                    "-t",
                    "2",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-ac",
                    "2",
                    "-shortest",
                    str(source),
                ],
                check=True,
                capture_output=True,
            )
            source_info = probe_video(FFPROBE, source)
            maximum_plan = build_maximum_detail_2pass_plan(source_info)
            jobs = [
                (
                    VideoJob(
                        input_path=source,
                        output_path=root / "best.mp4",
                        info=source_info,
                        encoding_mode=MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
                    ),
                    25.0,
                ),
                (
                    VideoJob(
                        input_path=source,
                        output_path=root / "maximum.mp4",
                        info=source_info,
                        encoding_mode=MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
                        h265_encode_plan=maximum_plan,
                        auto_selected_profile=PROFILE_MAXIMUM_DETAIL_2PASS,
                        small_detail_score=0.0,
                    ),
                    maximum_plan.target_fps,
                ),
            ]
            encoder = Encoder(FFmpegPaths(FFMPEG, FFPROBE))

            for job, expected_fps in jobs:
                result = encoder.encode(job, overwrite=True, cancel_event=threading.Event())
                self.assertEqual(result.status, "success", result.error_message)

                output_info = probe_video(FFPROBE, job.output_path)
                self.assertEqual(output_info.video_codec, "hevc")
                self.assertAlmostEqual(output_info.fps, expected_fps, delta=0.01)
                self.assertEqual(output_info.audio_codec, "aac")
                self.assertEqual(output_info.audio_sample_rate, 48000)
                self.assertEqual(output_info.audio_channels, 2)
                self.assertEqual(self._video_codec_tag(job.output_path), "hvc1")

                quality = run_quality_check(
                    FFMPEG,
                    source,
                    job.output_path,
                    source_info,
                    source_detail=0.0,
                )
                self.assertTrue(math.isfinite(quality.ssim_score))

            self.assertFalse(any(root.glob("*x265_2pass*")))
            self.assertFalse(any(root.glob(".*.quality-backup*")))

    def test_auto_detail_retry_runs_real_two_pass_profiles_and_cleans_observed_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp4"
            subprocess.run(
                [
                    str(FFMPEG),
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=320x180:rate=30",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=1000:sample_rate=48000",
                    "-t",
                    "2",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-ac",
                    "2",
                    "-shortest",
                    str(source),
                ],
                check=True,
                capture_output=True,
            )
            source_info = probe_video(FFPROBE, source)
            best_plan = build_best_detail_2pass_plan(source_info)
            job = VideoJob(
                input_path=source,
                output_path=root / "retry.mp4",
                info=source_info,
                encoding_mode=MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
                h265_encode_plan=best_plan,
                auto_selected_profile=PROFILE_BEST_DETAIL_2PASS,
                small_detail_score=0.0,
            )
            quality_results = [
                QualityCheckResult(
                    passed=False,
                    status=QUALITY_STATUS_WARNING,
                    ssim_score=0.93,
                    detail_retention_percent=None,
                    reason="ssim_below_threshold",
                    output_detail_score=0.0,
                ),
                QualityCheckResult(
                    passed=True,
                    status=QUALITY_STATUS_PASSED,
                    ssim_score=0.99,
                    detail_retention_percent=None,
                    reason="",
                    output_detail_score=0.0,
                ),
            ]
            encoder = Encoder(FFmpegPaths(FFMPEG, FFPROBE))
            original_encode = encoder._encode_h265_two_pass
            original_replace = Path.replace
            encoded_profiles = []
            observed_backups = []

            def observe_two_pass(current_job, *args, **kwargs):
                encoded_profiles.append(current_job.h265_encode_plan.selected_profile)
                return original_encode(current_job, *args, **kwargs)

            def observe_replace(path, target):
                target_path = Path(target)
                result = original_replace(path, target)
                if ".quality-backup" in target_path.name:
                    self.assertTrue(target_path.exists())
                    observed_backups.append(target_path)
                return result

            with patch.object(encoder, "_encode_h265_two_pass", side_effect=observe_two_pass):
                with patch.object(Encoder, "_run_quality_check", side_effect=quality_results) as quality_check:
                    with patch.object(Path, "replace", new=observe_replace):
                        result = encoder.encode(job, overwrite=True, cancel_event=threading.Event())

            self.assertEqual(result.status, "success", result.error_message)
            self.assertEqual(encoded_profiles, [PROFILE_BEST_DETAIL_2PASS, PROFILE_MAXIMUM_DETAIL_2PASS])
            self.assertEqual(quality_check.call_count, 2)
            self.assertEqual(job.quality_retry_count, 1)
            self.assertEqual(job.final_selected_profile, PROFILE_MAXIMUM_DETAIL_2PASS)
            self.assertEqual(len(observed_backups), 1)
            self.assertFalse(observed_backups[0].exists())
            self.assertFalse(any(root.glob("*x265_2pass*")))
            self.assertFalse(any(root.glob(".*.quality-backup*")))

    def _video_codec_tag(self, output_path: Path) -> str:
        completed = subprocess.run(
            [
                str(FFPROBE),
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        streams = json.loads(completed.stdout)["streams"]
        video_stream = next(stream for stream in streams if stream["codec_type"] == "video")
        return str(video_stream.get("codec_tag_string") or "")


if __name__ == "__main__":
    unittest.main()
