import csv
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from models import CompressionResult, VideoInfo, VideoJob
from report import REPORT_FIELDS, write_report


class ReportTests(unittest.TestCase):
    def test_write_report_creates_required_csv_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "source.mp4"
            output = temp_path / "out.mp4"
            info = VideoInfo(
                width=1920,
                height=1080,
                duration_sec=10.0,
                fps=30.0,
                video_codec="h264",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                has_audio=True,
            )
            job = VideoJob(
                input_path=source,
                output_path=output,
                info=info,
                audio_status="normal",
                status="success",
                original_size_bytes=10_000_000,
                output_size_bytes=5_000_000,
            )
            result = CompressionResult(
                job=job,
                status="success",
                output_info=info,
                created_at="2026-06-18T10:00:00",
            )

            report_path = write_report(temp_path, [result])

            with report_path.open("r", encoding="utf-8-sig", newline="") as file_obj:
                rows = list(csv.DictReader(file_obj))

        self.assertTrue(report_path.name.startswith("compression_report_"))
        self.assertEqual(set(rows[0].keys()), set(REPORT_FIELDS))
        self.assertEqual(rows[0]["source_file"], str(source))
        self.assertEqual(rows[0]["output_file"], str(output))
        self.assertEqual(rows[0]["status"], "success")
        self.assertEqual(rows[0]["resolution"], "1920x1080")
        self.assertEqual(rows[0]["size_reduction_percent"], "50.0")
        self.assertEqual(rows[0]["output_video_codec"], "h264")
        self.assertEqual(rows[0]["output_audio_codec"], "aac")
        self.assertEqual(rows[0]["crf"], "23")
        self.assertEqual(rows[0]["preset"], "slow")


if __name__ == "__main__":
    unittest.main()
