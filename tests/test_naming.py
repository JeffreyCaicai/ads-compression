import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from encoder import build_output_path, build_ffmpeg_args


class NamingTests(unittest.TestCase):
    def test_build_output_path_appends_required_suffix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "中文 素材.mov"
            output_dir = temp_path / "out"

            result = build_output_path(source, output_dir, overwrite=False)

        self.assertEqual(result, output_dir / "中文 素材_h264_crf23_aac96.mp4")

    def test_build_output_path_uses_increment_when_output_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "ad.mp4"
            output_dir = temp_path / "out"
            output_dir.mkdir()
            (output_dir / "ad_h264_crf23_aac96.mp4").write_bytes(b"old")

            result = build_output_path(source, output_dir, overwrite=False)

        self.assertEqual(result, output_dir / "ad_h264_crf23_aac96_2.mp4")

    def test_build_ffmpeg_args_uses_list_and_fixed_encoding_parameters(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "input with space.mp4"
            output = temp_path / "out.mp4"

            args = build_ffmpeg_args(Path("ffmpeg.exe"), source, output, overwrite=True)

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


if __name__ == "__main__":
    unittest.main()
