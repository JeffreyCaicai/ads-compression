import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ffmpeg_utils import candidate_roots, executable_name, find_ffmpeg_paths, parse_ffprobe_json, parse_fraction


def video_payload(*, avg_frame_rate: str, r_frame_rate: str) -> dict:
    return {
        "format": {},
        "streams": [
            {
                "codec_type": "video",
                "avg_frame_rate": avg_frame_rate,
                "r_frame_rate": r_frame_rate,
            }
        ],
    }


class FFprobeParseTests(unittest.TestCase):
    def test_parse_fraction_handles_standard_ffprobe_rate(self):
        self.assertEqual(parse_fraction("30000/1001"), 30000 / 1001)
        self.assertEqual(parse_fraction("30/1"), 30.0)
        self.assertEqual(parse_fraction("0/0"), 0.0)

    def test_parse_ffprobe_json_extracts_video_audio_and_format_duration(self):
        payload = {
            "format": {"duration": "12.345"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "30/1",
                    "pix_fmt": "yuv420p",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2,
                },
            ],
        }

        info = parse_ffprobe_json(payload)

        self.assertEqual(info.width, 1920)
        self.assertEqual(info.height, 1080)
        self.assertEqual(info.duration_sec, 12.345)
        self.assertEqual(info.fps, 30.0)
        self.assertEqual(info.video_codec, "h264")
        self.assertEqual(info.audio_codec, "aac")
        self.assertEqual(info.audio_sample_rate, 48000)
        self.assertEqual(info.audio_channels, 2)
        self.assertIs(info.has_audio, True)
        self.assertEqual(info.pix_fmt, "yuv420p")
        self.assertEqual(getattr(info, "display_dimensions", None), (1920, 1080))

    def test_parse_ffprobe_json_uses_anamorphic_display_aspect_ratio(self):
        payload = {
            "format": {"duration": "10.0"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 720,
                    "height": 576,
                    "sample_aspect_ratio": "64:45",
                    "display_aspect_ratio": "16:9",
                    "avg_frame_rate": "25/1",
                }
            ],
        }

        info = parse_ffprobe_json(payload)

        self.assertEqual((info.width, info.height), (720, 576))
        self.assertEqual(getattr(info, "sample_aspect_ratio", None), "64:45")
        self.assertEqual(getattr(info, "display_aspect_ratio", None), "16:9")
        self.assertEqual(getattr(info, "display_dimensions", None), (1024, 576))

    def test_parse_ffprobe_json_applies_rotation_to_display_geometry(self):
        payload = {
            "format": {"duration": "10.0"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "sample_aspect_ratio": "1:1",
                    "display_aspect_ratio": "16:9",
                    "avg_frame_rate": "30/1",
                    "side_data_list": [{"side_data_type": "Display Matrix", "rotation": -90}],
                }
            ],
        }

        info = parse_ffprobe_json(payload)

        self.assertEqual((info.width, info.height), (1920, 1080))
        self.assertEqual(getattr(info, "rotation_degrees", None), 270)
        self.assertEqual(getattr(info, "display_dimensions", None), (1080, 1920))

    def test_parse_ffprobe_json_normalizes_rotation_sources_and_variants(self):
        cases = (
            ("tag_90", {"tags": {"rotate": "90"}}, 90),
            ("tag_270", {"tags": {"rotate": "270"}}, 270),
            ("tag_negative_90", {"tags": {"rotate": "-90"}}, 270),
            ("matrix_90", {"side_data_list": [{"rotation": 90}]}, 90),
            ("matrix_270", {"side_data_list": [{"rotation": 270}]}, 270),
            ("matrix_450", {"side_data_list": [{"rotation": 450}]}, 90),
        )
        for label, rotation_metadata, expected_rotation in cases:
            with self.subTest(label=label):
                video_stream = {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "sample_aspect_ratio": "1:1",
                    "display_aspect_ratio": "16:9",
                    "avg_frame_rate": "30/1",
                    **rotation_metadata,
                }

                info = parse_ffprobe_json({"format": {"duration": "10.0"}, "streams": [video_stream]})

                self.assertEqual(info.rotation_degrees, expected_rotation)
                self.assertEqual(info.display_dimensions, (1080, 1920))

    def test_parse_ffprobe_json_preserves_square_pixel_coded_dimensions(self):
        payload = {
            "format": {"duration": "10.0"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 854,
                    "height": 480,
                    "sample_aspect_ratio": "1:1",
                    "display_aspect_ratio": "16:9",
                    "avg_frame_rate": "30/1",
                }
            ],
        }

        info = parse_ffprobe_json(payload)

        self.assertEqual(info.display_dimensions, (854, 480))

    def test_parse_ffprobe_json_falls_back_when_average_frame_rate_is_zero(self):
        payload = video_payload(avg_frame_rate="0/0", r_frame_rate="30/1")

        self.assertEqual(parse_ffprobe_json(payload).fps, 30.0)

    def test_parse_ffprobe_json_prefers_positive_average_frame_rate(self):
        payload = video_payload(avg_frame_rate="30000/1001", r_frame_rate="30/1")

        self.assertAlmostEqual(parse_ffprobe_json(payload).fps, 30000 / 1001)

    def test_parse_ffprobe_json_marks_missing_audio(self):
        payload = {
            "format": {},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "mpeg4",
                    "width": 1080,
                    "height": 1920,
                    "avg_frame_rate": "25/1",
                    "duration": "3.5",
                }
            ],
        }

        info = parse_ffprobe_json(payload)

        self.assertIs(info.has_audio, False)
        self.assertIsNone(info.audio_codec)
        self.assertEqual(info.duration_sec, 3.5)

    def test_parse_ffprobe_json_extracts_stream_and_format_bitrates(self):
        payload = {
            "format": {"duration": "15.0", "bit_rate": "12000000"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "hevc",
                    "width": 1920,
                    "height": 1440,
                    "avg_frame_rate": "30/1",
                    "bit_rate": "11759000",
                    "pix_fmt": "yuv420p",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2,
                    "bit_rate": "317000",
                },
            ],
        }

        info = parse_ffprobe_json(payload)

        self.assertEqual(info.video_bit_rate_kbps, 11759)
        self.assertEqual(info.audio_bit_rate_kbps, 317)
        self.assertEqual(info.format_bit_rate_kbps, 12000)

    def test_find_ffmpeg_paths_supports_pyinstaller_internal_data_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app_dir = (Path(temp_dir) / "SignageVideoCompressor").resolve()
            bin_dir = app_dir / "_internal" / "tools" / "ffmpeg" / "bin"
            bin_dir.mkdir(parents=True)
            ffmpeg = bin_dir / executable_name("ffmpeg")
            ffprobe = bin_dir / executable_name("ffprobe")
            ffmpeg.write_text("", encoding="utf-8")
            ffprobe.write_text("", encoding="utf-8")

            with (
                patch("ffmpeg_utils.sys.executable", str(app_dir / "SignageVideoCompressor.exe")),
                patch("ffmpeg_utils.sys.frozen", True, create=True),
                patch("ffmpeg_utils.Path.cwd", return_value=Path(temp_dir) / "elsewhere"),
                patch("ffmpeg_utils.shutil.which", return_value=None),
            ):
                roots = candidate_roots()
                paths = find_ffmpeg_paths()

        self.assertIn(app_dir / "_internal", roots)
        self.assertIsNotNone(paths)
        self.assertEqual(paths.ffmpeg, ffmpeg)
        self.assertEqual(paths.ffprobe, ffprobe)


if __name__ == "__main__":
    unittest.main()
