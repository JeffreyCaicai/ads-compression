import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from encoder import build_output_path, build_ffmpeg_args, build_ffmpeg_passlog_path, build_ffmpeg_two_pass_args
from models import VideoInfo
from settings import (
    MODE_H265_PRODUCTION_BEST_DETAIL,
    MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
    MODE_H265_SMALL_FILE,
    MODE_H265_SMART_AUTO,
    MODE_HIGH_MOTION,
    MODE_SCREEN_SAFE_HIGH_MOTION,
    MODE_STANDARD,
)


class NamingTests(unittest.TestCase):
    def test_build_output_path_preserves_original_name_with_mp4_extension(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "中文 素材.mov"
            output_dir = temp_path / "out"

            result = build_output_path(source, output_dir, overwrite=False, encoding_mode=MODE_STANDARD)

        self.assertEqual(result, output_dir / "中文 素材.mp4")

    def test_build_output_path_uses_increment_when_output_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "ad.mp4"
            output_dir = temp_path / "out"
            output_dir.mkdir()
            (output_dir / "ad.mp4").write_bytes(b"old")

            result = build_output_path(source, output_dir, overwrite=False, encoding_mode=MODE_STANDARD)

        self.assertEqual(result, output_dir / "ad_2.mp4")

    def test_build_ffmpeg_args_uses_list_and_fixed_encoding_parameters(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "input with space.mp4"
            output = temp_path / "out.mp4"

            args = build_ffmpeg_args(Path("ffmpeg.exe"), source, output, overwrite=True, encoding_mode=MODE_STANDARD)

        self.assertIsInstance(args, list)
        self.assertEqual(args[:5], [str(Path("ffmpeg.exe")), "-y", "-hide_banner", "-i", str(source)])
        self.assertIn("-c:v", args)
        self.assertEqual(args[args.index("-c:v") + 1], "libx264")
        self.assertEqual(args[args.index("-crf") + 1], "23")
        self.assertEqual(args[args.index("-preset") + 1], "slow")
        self.assertEqual(args[args.index("-c:a") + 1], "aac")
        self.assertEqual(args[args.index("-b:a") + 1], "96k")
        self.assertEqual(args[args.index("-progress") + 1], "pipe:1")
        self.assertEqual(args[-1], str(output))

    def test_high_motion_output_path_preserves_original_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "car.mp4"
            output_dir = temp_path / "out"

            result = build_output_path(source, output_dir, overwrite=False, encoding_mode=MODE_HIGH_MOTION)

        self.assertEqual(result, output_dir / "car.mp4")

    def test_output_path_never_overwrites_source_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "ad.mp4"
            source.write_bytes(b"source")

            result = build_output_path(source, temp_path, overwrite=True, encoding_mode=MODE_STANDARD)

        self.assertEqual(result, temp_path / "ad_2.mp4")

    def test_high_motion_ffmpeg_args_use_higher_quality_rate_cap(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "car.mp4"
            output = temp_path / "out.mp4"

            args = build_ffmpeg_args(Path("ffmpeg.exe"), source, output, overwrite=True, encoding_mode=MODE_HIGH_MOTION)

        self.assertEqual(args[args.index("-crf") + 1], "21")
        self.assertEqual(args[args.index("-maxrate") + 1], "5500k")
        self.assertEqual(args[args.index("-bufsize") + 1], "11000k")

    def test_screen_safe_high_motion_args_reduce_signage_decoder_pressure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "screen-start-glitch.mp4"
            output = temp_path / "out.mp4"

            args = build_ffmpeg_args(
                Path("ffmpeg.exe"),
                source,
                output,
                overwrite=True,
                encoding_mode=MODE_SCREEN_SAFE_HIGH_MOTION,
            )

        self.assertEqual(args[args.index("-crf") + 1], "21")
        self.assertEqual(args[args.index("-profile:v") + 1], "main")
        self.assertEqual(args[args.index("-g") + 1], "30")
        self.assertEqual(args[args.index("-keyint_min") + 1], "30")
        self.assertEqual(args[args.index("-sc_threshold") + 1], "40")
        self.assertEqual(args[args.index("-maxrate") + 1], "6500k")
        self.assertEqual(args[args.index("-bufsize") + 1], "12000k")
        self.assertEqual(args[args.index("-tune") + 1], "fastdecode")
        self.assertEqual(args[args.index("-bf") + 1], "0")
        self.assertEqual(args[args.index("-refs") + 1], "2")

    def test_h265_small_file_args_use_target_bitrate_for_source_resolution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "portrait.mp4"
            output = temp_path / "out.mp4"
            info = VideoInfo(
                width=1080,
                height=1920,
                duration_sec=15.0,
                fps=30.0,
                video_codec="h264",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                has_audio=True,
            )

            args = build_ffmpeg_args(
                Path("ffmpeg.exe"),
                source,
                output,
                overwrite=True,
                encoding_mode=MODE_H265_SMALL_FILE,
                source_info=info,
            )

        self.assertEqual(args[args.index("-c:v") + 1], "libx265")
        self.assertEqual(args[args.index("-profile:v") + 1], "main")
        self.assertEqual(args[args.index("-tag:v") + 1], "hvc1")
        self.assertEqual(args[args.index("-r") + 1], "25")
        self.assertEqual(args[args.index("-b:v") + 1], "1300k")
        self.assertEqual(args[args.index("-maxrate") + 1], "1950k")
        self.assertEqual(args[args.index("-bufsize") + 1], "3900k")
        self.assertIn("keyint=250", args[args.index("-x265-params") + 1])
        self.assertEqual(args[args.index("-c:a") + 1], "aac")
        self.assertEqual(args[args.index("-b:a") + 1], "96k")

    def test_h265_smart_auto_args_use_analyzed_target_bitrate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "auto.mp4"
            output = temp_path / "out.mp4"
            info = VideoInfo(
                width=1080,
                height=1920,
                duration_sec=15.0,
                fps=30.0,
                video_codec="h264",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                has_audio=True,
            )

            args = build_ffmpeg_args(
                Path("ffmpeg.exe"),
                source,
                output,
                overwrite=True,
                encoding_mode=MODE_H265_SMART_AUTO,
                source_info=info,
                target_video_bitrate_kbps=1800,
            )

        self.assertEqual(args[args.index("-c:v") + 1], "libx265")
        self.assertEqual(args[args.index("-b:v") + 1], "1800k")
        self.assertEqual(args[args.index("-maxrate") + 1], "2700k")
        self.assertEqual(args[args.index("-bufsize") + 1], "5400k")

    def test_h265_production_best_detail_args_use_complex_target_bitrate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "best-detail.mp4"
            output = temp_path / "out.mp4"
            info = VideoInfo(
                width=1080,
                height=1920,
                duration_sec=15.0,
                fps=30.0,
                video_codec="h264",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                has_audio=True,
            )

            args = build_ffmpeg_args(
                Path("ffmpeg.exe"),
                source,
                output,
                overwrite=True,
                encoding_mode=MODE_H265_PRODUCTION_BEST_DETAIL,
                source_info=info,
            )

        self.assertEqual(args[args.index("-c:v") + 1], "libx265")
        self.assertEqual(args[args.index("-profile:v") + 1], "main")
        self.assertEqual(args[args.index("-tag:v") + 1], "hvc1")
        self.assertEqual(args[args.index("-r") + 1], "25")
        self.assertEqual(args[args.index("-b:v") + 1], "1800k")
        self.assertEqual(args[args.index("-maxrate") + 1], "2700k")
        self.assertEqual(args[args.index("-bufsize") + 1], "5400k")
        self.assertEqual(
            args[args.index("-x265-params") + 1],
            "keyint=250:min-keyint=25:scenecut=40",
        )

    def test_h265_two_pass_passlog_path_is_unique_per_source_and_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output = temp_path / "out.mp4"
            first = build_ffmpeg_passlog_path(output, temp_path / "a" / "same-name.mp4")
            second = build_ffmpeg_passlog_path(output, temp_path / "b" / "same-name.mp4")

        self.assertEqual(first.parent, output.parent)
        self.assertNotEqual(first, second)
        self.assertTrue(first.name.startswith(".out_"))
        self.assertTrue(first.name.endswith("_x265_2pass"))

    def test_h265_two_pass_first_pass_args_analyze_video_to_null_without_audio(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "best-detail.mp4"
            output = temp_path / "out.mp4"
            passlog = temp_path / ".out_x265_2pass"
            info = VideoInfo(
                width=1080,
                height=1920,
                duration_sec=15.0,
                fps=30.0,
                video_codec="h264",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                has_audio=True,
            )

            args = build_ffmpeg_two_pass_args(
                Path("ffmpeg.exe"),
                source,
                output,
                pass_number=1,
                passlog_path=passlog,
                overwrite=True,
                encoding_mode=MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
                source_info=info,
            )

        self.assertEqual(args[args.index("-c:v") + 1], "libx265")
        self.assertEqual(args[args.index("-b:v") + 1], "1800k")
        self.assertEqual(args[args.index("-pass") + 1], "1")
        self.assertEqual(args[args.index("-passlogfile") + 1], str(passlog))
        self.assertIn("-an", args)
        self.assertEqual(args[args.index("-f") + 1], "null")
        self.assertIn(args[-1], {"NUL", "/dev/null"})
        self.assertNotIn("-tag:v", args)
        self.assertNotIn("-c:a", args)
        self.assertNotIn(str(output), args)

    def test_h265_two_pass_second_pass_args_write_final_mp4_with_audio(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "best-detail.mp4"
            output = temp_path / "out.mp4"
            passlog = temp_path / ".out_x265_2pass"
            info = VideoInfo(
                width=1080,
                height=1920,
                duration_sec=15.0,
                fps=30.0,
                video_codec="h264",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                has_audio=True,
            )

            args = build_ffmpeg_two_pass_args(
                Path("ffmpeg.exe"),
                source,
                output,
                pass_number=2,
                passlog_path=passlog,
                overwrite=True,
                encoding_mode=MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
                source_info=info,
            )

        self.assertEqual(args[args.index("-c:v") + 1], "libx265")
        self.assertEqual(args[args.index("-b:v") + 1], "1800k")
        self.assertEqual(args[args.index("-tag:v") + 1], "hvc1")
        self.assertEqual(args[args.index("-pass") + 1], "2")
        self.assertEqual(args[args.index("-passlogfile") + 1], str(passlog))
        self.assertEqual(args[args.index("-c:a") + 1], "aac")
        self.assertEqual(args[args.index("-b:a") + 1], "96k")
        self.assertEqual(args[args.index("-movflags") + 1], "+faststart")
        self.assertEqual(args[args.index("-progress") + 1], "pipe:1")
        self.assertEqual(args[-1], str(output))

    def test_h265_two_pass_args_reject_invalid_pass_number(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with self.assertRaises(ValueError):
                build_ffmpeg_two_pass_args(
                    Path("ffmpeg.exe"),
                    temp_path / "in.mp4",
                    temp_path / "out.mp4",
                    pass_number=3,
                    passlog_path=temp_path / ".passlog",
                    overwrite=True,
                    encoding_mode=MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
                )


if __name__ == "__main__":
    unittest.main()
