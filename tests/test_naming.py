import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from encoder import build_output_path, build_ffmpeg_args
from settings import MODE_HIGH_MOTION, MODE_SCREEN_SAFE_HIGH_MOTION, MODE_STANDARD


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


if __name__ == "__main__":
    unittest.main()
