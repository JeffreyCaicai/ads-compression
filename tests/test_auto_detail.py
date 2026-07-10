import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from auto_detail import (
    build_best_detail_2pass_plan,
    build_maximum_detail_2pass_plan,
    choose_auto_detail_plan,
    estimate_source_video_bitrate_kbps,
)
from content_analyzer import ProductionDetailAnalysis
from models import VideoInfo
from settings import PROFILE_BEST_DETAIL_2PASS, PROFILE_MAXIMUM_DETAIL_2PASS


def info(
    width=1920,
    height=1440,
    fps=30.0,
    video_bit_rate_kbps=None,
    audio_bit_rate_kbps=None,
    format_bit_rate_kbps=None,
    display_width=None,
    display_height=None,
    rotation_degrees=0,
):
    return VideoInfo(
        width=width,
        height=height,
        duration_sec=15.0,
        fps=fps,
        video_codec="hevc",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
        has_audio=True,
        video_bit_rate_kbps=video_bit_rate_kbps,
        audio_bit_rate_kbps=audio_bit_rate_kbps,
        format_bit_rate_kbps=format_bit_rate_kbps,
        display_width=display_width,
        display_height=display_height,
        rotation_degrees=rotation_degrees,
    )


class AutoDetailTests(unittest.TestCase):
    def test_simple_low_bitrate_content_selects_best_detail_profile(self):
        decision = choose_auto_detail_plan(
            info(width=1920, height=1080, fps=25.0, video_bit_rate_kbps=1800),
            ProductionDetailAnalysis(
                peak_complexity_score=20.0,
                small_detail_score=10.0,
                peak_motion_score=8.0,
                scene_change_rate=0.0,
                sampled_frames=10,
            ),
        )

        self.assertEqual(decision.selected_profile, PROFILE_BEST_DETAIL_2PASS)
        self.assertEqual(decision.encode_plan.target_video_bitrate_kbps, 1200)
        self.assertEqual(decision.encode_plan.target_fps, 25.0)
        self.assertLess(decision.risk_score, 65)

    def test_high_pixel_high_bitrate_30fps_detail_content_selects_maximum_detail_profile(self):
        decision = choose_auto_detail_plan(
            info(width=1920, height=1440, fps=30.0, video_bit_rate_kbps=11759),
            ProductionDetailAnalysis(
                peak_complexity_score=81.5,
                small_detail_score=70.0,
                peak_motion_score=48.0,
                scene_change_rate=0.4,
                sampled_frames=30,
            ),
        )

        self.assertEqual(decision.selected_profile, PROFILE_MAXIMUM_DETAIL_2PASS)
        self.assertEqual(decision.encode_plan.target_video_bitrate_kbps, 3200)
        self.assertEqual(decision.encode_plan.target_fps, 30.0)
        self.assertEqual(decision.encode_plan.gop, 60)
        self.assertEqual(decision.encode_plan.maxrate_kbps, 6400)
        self.assertEqual(decision.encode_plan.bufsize_kbps, 12800)
        self.assertIn("high_pixel_screen", decision.risk_reasons)
        self.assertIn("source_bitrate_11759k", decision.risk_reasons)
        self.assertGreaterEqual(decision.risk_score, 65)

    def test_rotated_portrait_uses_display_targets_and_portrait_risk(self):
        rotated = info(
            width=1920,
            height=1080,
            fps=25.0,
            video_bit_rate_kbps=1800,
            display_width=1080,
            display_height=1920,
            rotation_degrees=90,
        )
        analysis = ProductionDetailAnalysis(
            peak_complexity_score=20.0,
            small_detail_score=10.0,
            peak_motion_score=8.0,
            scene_change_rate=0.0,
            sampled_frames=10,
        )

        best_plan = build_best_detail_2pass_plan(rotated)
        maximum_plan = build_maximum_detail_2pass_plan(rotated)
        decision = choose_auto_detail_plan(rotated, analysis)

        self.assertEqual(best_plan.target_video_bitrate_kbps, 1800)
        self.assertEqual(maximum_plan.target_video_bitrate_kbps, 2600)
        self.assertIn("portrait_screen", decision.risk_reasons)
        self.assertEqual(decision.risk_score, 8.0)

    def test_missing_stream_bitrate_can_be_estimated_from_file_size_and_audio(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "source.mp4"
            path.write_bytes(b"0" * 12_000_000)

            bitrate = estimate_source_video_bitrate_kbps(
                info(audio_bit_rate_kbps=317),
                path,
            )

        self.assertEqual(bitrate, 6083)

    def test_format_bitrate_is_used_when_stream_and_file_size_are_missing(self):
        bitrate = estimate_source_video_bitrate_kbps(info(format_bit_rate_kbps=9000), None)

        self.assertEqual(bitrate, 9000)


if __name__ == "__main__":
    unittest.main()
