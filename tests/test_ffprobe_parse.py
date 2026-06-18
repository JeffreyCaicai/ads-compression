import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ffmpeg_utils import parse_ffprobe_json, parse_fraction


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


if __name__ == "__main__":
    unittest.main()
