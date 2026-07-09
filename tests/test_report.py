import csv
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from models import CompressionResult, VideoInfo, VideoJob
from report import REPORT_FIELDS, write_report
from settings import (
    MODE_H265_PRODUCTION_BEST_DETAIL,
    MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
    MODE_H265_SMALL_FILE,
    MODE_H265_SMART_AUTO,
    MODE_HIGH_MOTION,
)


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
                encoding_mode=MODE_HIGH_MOTION,
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
        self.assertEqual(rows[0]["encoding_mode"], "high_motion")
        self.assertEqual(rows[0]["crf"], "21")
        self.assertEqual(rows[0]["preset"], "slow")
        self.assertEqual(rows[0]["target_video_bitrate_kbps"], "")
        self.assertEqual(rows[0]["target_fps"], "30")

    def test_write_report_records_h265_target_bitrate_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "source.mp4"
            output = temp_path / "out.mp4"
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
            )
            job = VideoJob(
                input_path=source,
                output_path=output,
                info=source_info,
                audio_status="normal",
                status="success",
                original_size_bytes=10_000_000,
                output_size_bytes=2_000_000,
                encoding_mode=MODE_H265_SMALL_FILE,
            )
            result = CompressionResult(
                job=job,
                status="success",
                output_info=output_info,
                created_at="2026-06-18T10:00:00",
            )

            report_path = write_report(temp_path, [result])

            with report_path.open("r", encoding="utf-8-sig", newline="") as file_obj:
                rows = list(csv.DictReader(file_obj))

        self.assertEqual(rows[0]["encoding_mode"], "h265_small_file")
        self.assertEqual(rows[0]["output_video_codec"], "hevc")
        self.assertEqual(rows[0]["crf"], "")
        self.assertEqual(rows[0]["target_video_bitrate_kbps"], "1300")
        self.assertEqual(rows[0]["target_fps"], "25")

    def test_write_report_records_smart_auto_analysis_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "source.mp4"
            output = temp_path / "out.mp4"
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
            )
            job = VideoJob(
                input_path=source,
                output_path=output,
                info=source_info,
                audio_status="normal",
                status="success",
                original_size_bytes=10_000_000,
                output_size_bytes=2_000_000,
                encoding_mode=MODE_H265_SMART_AUTO,
                content_complexity="complex",
                content_complexity_score=72.5,
                target_video_bitrate_kbps=1800,
            )
            result = CompressionResult(
                job=job,
                status="success",
                output_info=source_info,
                created_at="2026-06-18T10:00:00",
            )

            report_path = write_report(temp_path, [result])

            with report_path.open("r", encoding="utf-8-sig", newline="") as file_obj:
                rows = list(csv.DictReader(file_obj))

        self.assertEqual(rows[0]["encoding_mode"], "h265_smart_auto")
        self.assertEqual(rows[0]["target_video_bitrate_kbps"], "1800")
        self.assertEqual(rows[0]["content_complexity"], "complex")
        self.assertEqual(rows[0]["content_complexity_score"], "72.5")

    def test_write_report_records_h265_production_best_detail_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "source.mp4"
            output = temp_path / "out.mp4"
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
            )
            job = VideoJob(
                input_path=source,
                output_path=output,
                info=source_info,
                audio_status="normal",
                status="success",
                original_size_bytes=10_000_000,
                output_size_bytes=2_000_000,
                encoding_mode=MODE_H265_PRODUCTION_BEST_DETAIL,
            )
            result = CompressionResult(
                job=job,
                status="success",
                output_info=output_info,
                created_at="2026-06-18T10:00:00",
            )

            report_path = write_report(temp_path, [result])

            with report_path.open("r", encoding="utf-8-sig", newline="") as file_obj:
                rows = list(csv.DictReader(file_obj))

        self.assertEqual(rows[0]["encoding_mode"], "h265_production_best_detail")
        self.assertEqual(rows[0]["target_video_bitrate_kbps"], "1800")
        self.assertEqual(rows[0]["target_fps"], "25")
        self.assertEqual(rows[0]["content_complexity"], "production_best_detail")
        self.assertEqual(rows[0]["content_complexity_score"], "")

    def test_write_report_records_h265_production_best_detail_2pass_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "source.mp4"
            output = temp_path / "out.mp4"
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
            )
            job = VideoJob(
                input_path=source,
                output_path=output,
                info=source_info,
                audio_status="normal",
                status="success",
                original_size_bytes=10_000_000,
                output_size_bytes=2_000_000,
                encoding_mode=MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
            )
            result = CompressionResult(
                job=job,
                status="success",
                output_info=output_info,
                created_at="2026-06-18T10:00:00",
            )

            report_path = write_report(temp_path, [result])

            with report_path.open("r", encoding="utf-8-sig", newline="") as file_obj:
                rows = list(csv.DictReader(file_obj))

        self.assertEqual(rows[0]["encoding_mode"], "h265_production_best_detail_2pass")
        self.assertEqual(rows[0]["target_video_bitrate_kbps"], "1800")
        self.assertEqual(rows[0]["target_fps"], "25")
        self.assertEqual(rows[0]["content_complexity"], "production_best_detail")
        self.assertEqual(rows[0]["content_complexity_score"], "")

    def test_write_report_records_auto_detail_decision_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "source.mp4"
            output = temp_path / "out.mp4"
            source_info = VideoInfo(
                width=1920,
                height=1440,
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
                input_path=source,
                output_path=output,
                info=source_info,
                audio_status="normal",
                status="success",
                original_size_bytes=22_839_430,
                output_size_bytes=6_200_000,
                encoding_mode="h265_production_auto_detail_2pass",
                target_video_bitrate_kbps=3200,
                target_fps=30.0,
                target_gop=60,
                auto_selected_profile="maximum_detail_2pass",
                auto_risk_score=82.0,
                auto_risk_reasons="high_pixel_screen;source_bitrate_11759k;fps_30",
                source_video_bitrate_kbps=11759,
                source_fps=30.0,
                peak_complexity_score=81.5,
                small_detail_score=70.0,
                peak_motion_score=48.0,
                scene_change_rate=0.4,
            )
            result = CompressionResult(
                job=job,
                status="success",
                output_info=source_info,
                created_at="2026-07-09T10:00:00",
            )

            report_path = write_report(temp_path, [result])

            with report_path.open("r", encoding="utf-8-sig", newline="") as file_obj:
                rows = list(csv.DictReader(file_obj))

        self.assertEqual(rows[0]["auto_selected_profile"], "maximum_detail_2pass")
        self.assertEqual(rows[0]["auto_risk_score"], "82")
        self.assertEqual(rows[0]["auto_risk_reasons"], "high_pixel_screen;source_bitrate_11759k;fps_30")
        self.assertEqual(rows[0]["source_video_bitrate_kbps"], "11759")
        self.assertEqual(rows[0]["source_fps"], "30")
        self.assertEqual(rows[0]["peak_complexity_score"], "81.5")
        self.assertEqual(rows[0]["small_detail_score"], "70")
        self.assertEqual(rows[0]["peak_motion_score"], "48")
        self.assertEqual(rows[0]["scene_change_rate"], "0.4")
        self.assertEqual(rows[0]["target_fps"], "30")
        self.assertEqual(rows[0]["target_gop"], "60")

    def test_write_report_keeps_zero_auto_detail_scores_for_auto_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "source.mp4"
            output = temp_path / "out.mp4"
            source_info = VideoInfo(
                width=1920,
                height=1080,
                duration_sec=15.0,
                fps=25.0,
                video_codec="hevc",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                has_audio=True,
            )
            job = VideoJob(
                input_path=source,
                output_path=output,
                info=source_info,
                audio_status="normal",
                status="success",
                original_size_bytes=22_839_430,
                output_size_bytes=6_200_000,
                encoding_mode="h265_production_auto_detail_2pass",
                target_video_bitrate_kbps=1800,
                target_fps=25.0,
                target_gop=50,
                auto_selected_profile="best_detail_2pass",
                auto_risk_score=0.0,
                auto_risk_reasons="analysis_failed:probe timeout",
                source_fps=25.0,
                peak_complexity_score=0.0,
                small_detail_score=0.0,
                peak_motion_score=0.0,
                scene_change_rate=0.0,
            )
            result = CompressionResult(
                job=job,
                status="success",
                output_info=source_info,
                created_at="2026-07-09T10:00:00",
            )

            report_path = write_report(temp_path, [result])

            with report_path.open("r", encoding="utf-8-sig", newline="") as file_obj:
                rows = list(csv.DictReader(file_obj))

        self.assertEqual(rows[0]["auto_risk_score"], "0")
        self.assertEqual(rows[0]["peak_complexity_score"], "0")
        self.assertEqual(rows[0]["small_detail_score"], "0")
        self.assertEqual(rows[0]["peak_motion_score"], "0")
        self.assertEqual(rows[0]["scene_change_rate"], "0")

    def test_write_report_leaves_preanalysis_auto_detail_metrics_blank(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "source.mp4"
            output = temp_path / "out.mp4"
            source_info = VideoInfo(
                width=1920,
                height=1080,
                duration_sec=15.0,
                fps=25.0,
                video_codec="hevc",
                audio_codec=None,
                audio_sample_rate=None,
                audio_channels=None,
                has_audio=False,
            )
            job = VideoJob(
                input_path=source,
                output_path=output,
                info=source_info,
                audio_status="failed",
                status="failed",
                error_message="probe failed before analysis",
                original_size_bytes=22_839_430,
                output_size_bytes=0,
                encoding_mode="h265_production_auto_detail_2pass",
                target_video_bitrate_kbps=1800,
                target_fps=25.0,
                target_gop=50,
            )
            result = CompressionResult(
                job=job,
                status="failed",
                error_message="probe failed before analysis",
                created_at="2026-07-09T10:00:00",
            )

            report_path = write_report(temp_path, [result])

            with report_path.open("r", encoding="utf-8-sig", newline="") as file_obj:
                rows = list(csv.DictReader(file_obj))

        self.assertEqual(rows[0]["auto_selected_profile"], "")
        self.assertEqual(rows[0]["auto_risk_score"], "")
        self.assertEqual(rows[0]["auto_risk_reasons"], "")
        self.assertEqual(rows[0]["source_video_bitrate_kbps"], "")
        self.assertEqual(rows[0]["source_fps"], "")
        self.assertEqual(rows[0]["peak_complexity_score"], "")
        self.assertEqual(rows[0]["small_detail_score"], "")
        self.assertEqual(rows[0]["peak_motion_score"], "")
        self.assertEqual(rows[0]["scene_change_rate"], "")


if __name__ == "__main__":
    unittest.main()
