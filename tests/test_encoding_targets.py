import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ffmpeg_utils import validate_output_file
from models import VideoInfo
from settings import (
    COMMON_SCREEN_RESOLUTIONS,
    MODE_H265_PRODUCTION_BEST_DETAIL,
    MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
    MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
    MODE_H265_SMALL_FILE,
    MODE_H265_SMALL_FILE_COMPLEX,
    MODE_H265_SMALL_FILE_SIMPLE,
    PROFILE_BEST_DETAIL_2PASS,
    PROFILE_MAXIMUM_DETAIL_2PASS,
    SUPPORTED_ENCODING_MODES,
    H265_ENCODING_MODES,
    is_h265_auto_detail_mode,
    is_h265_two_pass_mode,
    maximum_detail_target_video_bitrate_kbps,
    target_video_bitrate_kbps,
)


class EncodingTargetTests(unittest.TestCase):
    def test_auto_detail_profile_constants_are_defined_in_settings(self):
        self.assertEqual(PROFILE_BEST_DETAIL_2PASS, "best_detail_2pass")
        self.assertEqual(PROFILE_MAXIMUM_DETAIL_2PASS, "maximum_detail_2pass")

    def test_h265_target_bitrate_uses_screen_size_and_content_complexity(self):
        self.assertEqual(target_video_bitrate_kbps(1920, 1080, MODE_H265_SMALL_FILE_SIMPLE), 450)
        self.assertEqual(target_video_bitrate_kbps(1080, 1920, MODE_H265_SMALL_FILE), 1300)
        self.assertEqual(target_video_bitrate_kbps(1080, 2560, MODE_H265_SMALL_FILE_COMPLEX), 2200)

    def test_h265_production_best_detail_uses_complex_target_bitrate(self):
        self.assertEqual(target_video_bitrate_kbps(1920, 1080, MODE_H265_PRODUCTION_BEST_DETAIL), 1200)
        self.assertEqual(target_video_bitrate_kbps(1080, 1920, MODE_H265_PRODUCTION_BEST_DETAIL), 1800)
        self.assertEqual(target_video_bitrate_kbps(1080, 2560, MODE_H265_PRODUCTION_BEST_DETAIL), 2200)

    def test_h265_production_best_detail_2pass_uses_complex_target_bitrate(self):
        self.assertIn(MODE_H265_PRODUCTION_BEST_DETAIL_2PASS, SUPPORTED_ENCODING_MODES)
        self.assertTrue(is_h265_two_pass_mode(MODE_H265_PRODUCTION_BEST_DETAIL_2PASS))
        self.assertFalse(is_h265_two_pass_mode(MODE_H265_PRODUCTION_BEST_DETAIL))
        self.assertEqual(target_video_bitrate_kbps(1920, 1080, MODE_H265_PRODUCTION_BEST_DETAIL_2PASS), 1200)
        self.assertEqual(target_video_bitrate_kbps(1080, 1920, MODE_H265_PRODUCTION_BEST_DETAIL_2PASS), 1800)
        self.assertEqual(target_video_bitrate_kbps(1080, 2560, MODE_H265_PRODUCTION_BEST_DETAIL_2PASS), 2200)

    def test_h265_auto_detail_mode_is_supported_and_two_pass(self):
        self.assertIn(MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS, SUPPORTED_ENCODING_MODES)
        self.assertIn(MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS, H265_ENCODING_MODES)
        self.assertTrue(is_h265_auto_detail_mode(MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS))
        self.assertTrue(is_h265_two_pass_mode(MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS))

    def test_maximum_detail_target_bitrates_use_screen_size(self):
        self.assertEqual(maximum_detail_target_video_bitrate_kbps(1920, 1080), 2000)
        self.assertEqual(maximum_detail_target_video_bitrate_kbps(1080, 1920), 2600)
        self.assertEqual(maximum_detail_target_video_bitrate_kbps(1920, 1440), 3200)
        self.assertEqual(maximum_detail_target_video_bitrate_kbps(1080, 2560), 3200)

    def test_h265_output_validation_accepts_hevc_25fps_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "output.mp4"
            output_path.write_bytes(b"video")
            source_info = VideoInfo(
                width=1080,
                height=1920,
                duration_sec=15.0,
                fps=30.0,
                video_codec="h264",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                has_audio=True,
                pix_fmt="yuv420p",
            )
            output_info = VideoInfo(
                width=1080,
                height=1920,
                duration_sec=15.0,
                fps=25.0,
                video_codec="hevc",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                has_audio=True,
                pix_fmt="yuv420p",
            )

            errors = validate_output_file(output_path, source_info, output_info, encoding_mode=MODE_H265_SMALL_FILE)

        self.assertEqual(errors, [])

    def test_output_validation_accepts_autorotated_matching_display_geometry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "output.mp4"
            output_path.write_bytes(b"video")
            source_info = VideoInfo(
                width=1920,
                height=1080,
                duration_sec=15.0,
                fps=30.0,
                video_codec="h264",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                has_audio=True,
                pix_fmt="yuv420p",
                rotation_degrees=90,
                display_width=1080,
                display_height=1920,
            )
            output_info = VideoInfo(
                width=1080,
                height=1920,
                duration_sec=15.0,
                fps=25.0,
                video_codec="hevc",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                has_audio=True,
                pix_fmt="yuv420p",
            )

            errors = validate_output_file(
                output_path,
                source_info,
                output_info,
                encoding_mode=MODE_H265_SMALL_FILE,
            )

        self.assertEqual(errors, [])

    def test_output_validation_accepts_square_pixel_output_for_anamorphic_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "output.mp4"
            output_path.write_bytes(b"video")
            source_info = VideoInfo(
                width=720,
                height=576,
                duration_sec=15.0,
                fps=25.0,
                video_codec="h264",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                has_audio=True,
                pix_fmt="yuv420p",
                sample_aspect_ratio="64:45",
                display_aspect_ratio="16:9",
                display_width=1024,
                display_height=576,
            )
            output_info = VideoInfo(
                width=1024,
                height=576,
                duration_sec=15.0,
                fps=25.0,
                video_codec="hevc",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                has_audio=True,
                pix_fmt="yuv420p",
                sample_aspect_ratio="1:1",
            )

            errors = validate_output_file(
                output_path,
                source_info,
                output_info,
                encoding_mode=MODE_H265_SMALL_FILE,
            )

        self.assertEqual(errors, [])

    def test_current_company_screen_resolutions_are_common(self):
        self.assertIn((1920, 1440), COMMON_SCREEN_RESOLUTIONS)
        self.assertIn((1080, 2560), COMMON_SCREEN_RESOLUTIONS)


if __name__ == "__main__":
    unittest.main()
