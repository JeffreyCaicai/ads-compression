import queue
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from content_analyzer import ContentAnalysisError
from localization import DEFAULT_LANGUAGE, Localizer
from models import FFmpegPaths, VideoInfo, VideoJob
from settings import MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS
from ui_main import CompressorWindow


class AutoDetailFallbackTests(unittest.TestCase):
    def test_auto_detail_analysis_failure_falls_back_to_best_detail_plan(self):
        window = CompressorWindow.__new__(CompressorWindow)
        window.ffmpeg_paths = FFmpegPaths(ffmpeg=Path("/tmp/ffmpeg"), ffprobe=Path("/tmp/ffprobe"))
        window.localizer = Localizer(DEFAULT_LANGUAGE)
        window.ui_queue = queue.Queue()

        info = VideoInfo(
            width=1920,
            height=1080,
            duration_sec=15.0,
            fps=30.0,
            video_codec="hevc",
            audio_codec="aac",
            audio_sample_rate=48000,
            audio_channels=2,
            has_audio=True,
            video_bit_rate_kbps=11759,
        )
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


if __name__ == "__main__":
    unittest.main()
