import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from content_analyzer import (
    AnalysisCancelled,
    ContentAnalysisError,
    ProductionDetailAnalysis,
    SampleSegment,
)
from models import VideoInfo
from quality_check import (
    QualityCheckError,
    QualityCheckResult,
    _run_ssim_process,
    build_ssim_args,
    evaluate_quality,
    parse_ssim_score,
    run_quality_check,
)
from settings import QUALITY_STATUS_PASSED, QUALITY_STATUS_WARNING


def make_video_info(duration_sec: float = 60.0) -> VideoInfo:
    return VideoInfo(
        width=1920,
        height=1080,
        duration_sec=duration_sec,
        fps=30.0,
        video_codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
        has_audio=True,
    )


def production_detail(score: float) -> ProductionDetailAnalysis:
    return ProductionDetailAnalysis(
        peak_complexity_score=0.0,
        small_detail_score=score,
        peak_motion_score=0.0,
        scene_change_rate=0.0,
        sampled_frames=1,
    )


class QualityCheckTests(unittest.TestCase):
    def test_quality_check_result_field_order_is_stable(self):
        self.assertEqual(
            tuple(QualityCheckResult.__dataclass_fields__),
            (
                "passed",
                "status",
                "ssim_score",
                "detail_retention_percent",
                "reason",
                "output_detail_score",
            ),
        )

    def test_quality_passes_at_exact_thresholds(self):
        result = evaluate_quality(0.94, source_detail=40.0, output_detail=32.0)

        self.assertTrue(result.passed)
        self.assertEqual(result.status, QUALITY_STATUS_PASSED)
        self.assertEqual(result.detail_retention_percent, 80.0)

    def test_low_detail_source_does_not_enforce_retention(self):
        result = evaluate_quality(0.95, source_detail=10.0, output_detail=1.0)

        self.assertTrue(result.passed)
        self.assertEqual(result.detail_retention_percent, 10.0)

    def test_quality_fails_below_ssim_threshold(self):
        result = evaluate_quality(0.939, 40.0, 40.0)

        self.assertFalse(result.passed)
        self.assertEqual(result.status, QUALITY_STATUS_WARNING)
        self.assertEqual(result.reason, "ssim_below_threshold")

    def test_quality_fails_below_detail_retention_threshold_for_detailed_source(self):
        result = evaluate_quality(0.95, source_detail=40.0, output_detail=31.9)

        self.assertFalse(result.passed)
        self.assertEqual(result.reason, "detail_retention_below_threshold")

    def test_parse_ssim_score_reads_finite_all_value(self):
        self.assertEqual(
            parse_ssim_score("SSIM Y:0.95 U:0.96 V:0.97 All:0.955 (13.4)"),
            0.955,
        )

    def test_parse_ssim_score_rejects_missing_or_nonfinite_aggregate_value(self):
        for stderr in ("SSIM Y:0.95 U:0.96 V:0.97", "SSIM Y:nan U:nan V:nan All:nan (inf)", "SSIM Y:inf U:inf V:inf All:inf (inf)"):
            with self.subTest(stderr=stderr):
                with self.assertRaises(QualityCheckError):
                    parse_ssim_score(stderr)

    def test_ssim_args_normalize_both_inputs_to_two_fps(self):
        args = build_ssim_args(
            Path("ffmpeg.exe"),
            Path("source.mp4"),
            Path("output.mp4"),
            width=320,
            height=180,
            segment=SampleSegment(0.0, 10.0),
        )

        graph = args[args.index("-lavfi") + 1]
        self.assertEqual(graph.count("fps=2"), 2)
        self.assertEqual(graph.count("setpts=PTS-STARTPTS"), 2)
        self.assertIn("scale=320:180:flags=lanczos", graph)
        self.assertIn("format=gray", graph)
        self.assertIn("ssim", graph)

    def test_run_quality_check_averages_equal_duration_segment_scores(self):
        with (
            patch("quality_check._run_ssim_process", side_effect=["SSIM All:0.90", "SSIM All:0.96", "SSIM All:0.99"]),
            patch("quality_check.analyze_production_detail", return_value=production_detail(36.0)) as analyze,
        ):
            result = run_quality_check(
                Path("ffmpeg"),
                Path("source.mp4"),
                Path("output.mp4"),
                make_video_info(),
                source_detail=40.0,
            )

        self.assertAlmostEqual(result.ssim_score, 0.95)
        self.assertEqual(result.output_detail_score, 36.0)
        analyze.assert_called_once_with(
            Path("ffmpeg"), Path("output.mp4"), 1920, 1080, 60.0, cancel_event=None
        )

    def test_run_quality_check_rejects_nonfinite_segment_score(self):
        with patch("quality_check._run_ssim_process", return_value="SSIM All:nan"):
            with self.assertRaises(QualityCheckError):
                run_quality_check(
                    Path("ffmpeg"),
                    Path("source.mp4"),
                    Path("output.mp4"),
                    make_video_info(duration_sec=10.0),
                    source_detail=40.0,
                )

    def test_run_quality_check_normalizes_output_content_analysis_error(self):
        error = ContentAnalysisError("output detail failed")
        with (
            patch("quality_check._run_ssim_process", return_value="SSIM All:0.96"),
            patch("quality_check.analyze_production_detail", side_effect=error),
        ):
            with self.assertRaises(QualityCheckError) as raised:
                run_quality_check(
                    Path("ffmpeg"),
                    Path("source.mp4"),
                    Path("output.mp4"),
                    make_video_info(duration_sec=10.0),
                    source_detail=40.0,
                )

        self.assertIs(raised.exception.__cause__, error)

    def test_run_quality_check_normalizes_output_analysis_timeout(self):
        error = subprocess.TimeoutExpired(["ffmpeg"], 5)
        with (
            patch("quality_check._run_ssim_process", return_value="SSIM All:0.96"),
            patch("quality_check.analyze_production_detail", side_effect=error),
        ):
            with self.assertRaises(QualityCheckError) as raised:
                run_quality_check(
                    Path("ffmpeg"),
                    Path("source.mp4"),
                    Path("output.mp4"),
                    make_video_info(duration_sec=10.0),
                    source_detail=40.0,
                )

        self.assertIs(raised.exception.__cause__, error)

    def test_run_quality_check_normalizes_ssim_os_error(self):
        error = OSError("unable to start SSIM")
        with patch("quality_check._run_ssim_process", side_effect=error):
            with self.assertRaises(QualityCheckError) as raised:
                run_quality_check(
                    Path("ffmpeg"),
                    Path("source.mp4"),
                    Path("output.mp4"),
                    make_video_info(duration_sec=10.0),
                    source_detail=40.0,
                )

        self.assertIs(raised.exception.__cause__, error)

    def test_run_quality_check_preserves_analysis_cancelled(self):
        error = AnalysisCancelled("cancelled")
        with (
            patch("quality_check._run_ssim_process", return_value="SSIM All:0.96"),
            patch("quality_check.analyze_production_detail", side_effect=error),
        ):
            with self.assertRaises(AnalysisCancelled) as raised:
                run_quality_check(
                    Path("ffmpeg"),
                    Path("source.mp4"),
                    Path("output.mp4"),
                    make_video_info(duration_sec=10.0),
                    source_detail=40.0,
                )

        self.assertIs(raised.exception, error)

    def test_ssim_process_cancellation_terminates_then_waits_five_seconds(self):
        cancel_event = threading.Event()
        cancel_event.set()
        process = Mock(returncode=1)
        process.communicate.return_value = (b"", b"FFmpeg failed")

        with patch("quality_check.subprocess.Popen", return_value=process):
            with self.assertRaises(AnalysisCancelled):
                _run_ssim_process(["ffmpeg"], cancel_event)

        process.terminate.assert_called_once()
        self.assertEqual(process.communicate.call_args_list, [call(timeout=5)])

    def test_ssim_process_cancellation_kills_after_terminate_timeout(self):
        cancel_event = threading.Event()
        cancel_event.set()
        process = Mock()
        process.communicate.side_effect = [
            subprocess.TimeoutExpired(["ffmpeg"], 5),
            (b"", b""),
        ]

        with patch("quality_check.subprocess.Popen", return_value=process):
            with self.assertRaises(AnalysisCancelled):
                _run_ssim_process(["ffmpeg"], cancel_event)

        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(process.communicate.call_args_list, [call(timeout=5), call()])


if __name__ == "__main__":
    unittest.main()
