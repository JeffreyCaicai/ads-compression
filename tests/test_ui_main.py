import queue
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from content_analyzer import AnalysisCancelled, ContentAnalysisError, ProductionDetailAnalysis
from localization import DEFAULT_LANGUAGE, Localizer
from models import FFmpegPaths, VideoInfo, VideoJob
from settings import MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS
from ui_main import CompressorWindow


class AutoDetailFallbackTests(unittest.TestCase):
    def make_window(self) -> CompressorWindow:
        window = CompressorWindow.__new__(CompressorWindow)
        window.ffmpeg_paths = FFmpegPaths(ffmpeg=Path("/tmp/ffmpeg"), ffprobe=Path("/tmp/ffprobe"))
        window.localizer = Localizer(DEFAULT_LANGUAGE)
        window.ui_queue = queue.Queue()
        window.cancel_event = threading.Event()
        window.results = []
        return window

    @staticmethod
    def make_info() -> VideoInfo:
        return VideoInfo(
            width=1080,
            height=1920,
            duration_sec=15.0,
            fps=30.0,
            video_codec="hevc",
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            has_audio=True,
            video_bit_rate_kbps=11759,
        )

    def test_auto_detail_analysis_failure_falls_back_to_best_detail_plan(self):
        window = self.make_window()

        info = self.make_info()
        job = VideoJob(
            input_path=Path("/tmp/source.mp4"),
            output_path=Path("/tmp/out.mp4"),
            info=info,
            encoding_mode=MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
            auto_risk_score=91.0,
            auto_risk_reasons="stale-risk",
            peak_complexity_score=88.0,
            small_detail_score=77.0,
            peak_motion_score=66.0,
            scene_change_rate=0.5,
        )

        with patch("ui_main.analyze_production_detail", side_effect=ContentAnalysisError("sample failed")):
            window._analyze_job_auto_detail(job)

        self.assertIsNotNone(job.h265_encode_plan)
        self.assertEqual(job.h265_encode_plan.selected_profile, "best_detail_2pass")
        self.assertEqual(job.auto_selected_profile, "best_detail_2pass")
        self.assertTrue(job.auto_risk_reasons.startswith("analysis_failed:sample failed"))
        self.assertEqual(job.target_video_bitrate_kbps, job.h265_encode_plan.target_video_bitrate_kbps)
        self.assertEqual(job.target_fps, job.h265_encode_plan.target_fps)
        self.assertEqual(job.target_gop, job.h265_encode_plan.gop)
        self.assertEqual(job.auto_risk_score, 0.0)
        self.assertEqual(job.peak_complexity_score, 0.0)
        self.assertEqual(job.small_detail_score, 0.0)
        self.assertEqual(job.peak_motion_score, 0.0)
        self.assertEqual(job.scene_change_rate, 0.0)

    def test_cancelled_auto_detail_analysis_receives_job_geometry_and_skips_encode(self):
        window = self.make_window()
        info = self.make_info()
        encoder = Mock()

        with tempfile.TemporaryDirectory() as temporary_directory:
            source_path = Path(temporary_directory) / "source.mp4"
            source_path.touch()
            job = VideoJob(
                input_path=source_path,
                output_path=Path(temporary_directory) / "out.mp4",
                encoding_mode=MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
            )

            def cancel_analysis(*args, **kwargs):
                window.cancel_event.set()
                raise AnalysisCancelled("cancelled")

            with (
                patch("ui_main.Encoder", return_value=encoder),
                patch("ui_main.probe_video", return_value=info),
                patch("ui_main.analyze_production_detail", side_effect=cancel_analysis) as analyze,
                patch("ui_main.build_best_detail_2pass_plan") as fallback,
                patch("ui_main.write_report", return_value=Path(temporary_directory) / "report.csv"),
            ):
                window._worker([job], Path(temporary_directory), overwrite=False, detect_silence_enabled=False)

        analyze.assert_called_once_with(
            window.ffmpeg_paths.ffmpeg,
            source_path,
            source_width=info.width,
            source_height=info.height,
            duration_sec=info.duration_sec,
            cancel_event=window.cancel_event,
        )
        fallback.assert_not_called()
        encoder.encode.assert_not_called()
        self.assertEqual(job.status, "cancelled")
        self.assertEqual(window.results[0].status, "cancelled")

    def test_cancel_after_auto_detail_analysis_skips_encode(self):
        window = self.make_window()
        info = self.make_info()
        encoder = Mock()
        analysis = ProductionDetailAnalysis(0.0, 0.0, 0.0, 0.0, 1)

        with tempfile.TemporaryDirectory() as temporary_directory:
            source_path = Path(temporary_directory) / "source.mp4"
            source_path.touch()
            job = VideoJob(
                input_path=source_path,
                output_path=Path(temporary_directory) / "out.mp4",
                encoding_mode=MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
            )

            def finish_analysis_then_cancel(*args, **kwargs):
                window.cancel_event.set()
                return analysis

            with (
                patch("ui_main.Encoder", return_value=encoder),
                patch("ui_main.probe_video", return_value=info),
                patch("ui_main.analyze_production_detail", side_effect=finish_analysis_then_cancel),
                patch("ui_main.write_report", return_value=Path(temporary_directory) / "report.csv"),
            ):
                window._worker([job], Path(temporary_directory), overwrite=False, detect_silence_enabled=False)

        encoder.encode.assert_not_called()
        self.assertEqual(job.status, "cancelled")


if __name__ == "__main__":
    unittest.main()
