import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from encoder import Encoder, build_ffmpeg_passlog_path
from models import FFmpegPaths, H265EncodePlan, VideoInfo, VideoJob
from settings import (
    MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
    MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
    PROFILE_MAXIMUM_DETAIL_2PASS,
)


class EncoderTwoPassTests(unittest.TestCase):
    def test_h265_two_pass_mode_runs_two_ffmpeg_passes_and_cleans_passlogs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "source.mp4"
            output = temp_path / "out.mp4"
            source.write_bytes(b"source")
            output.write_bytes(b"encoded")
            info = VideoInfo(
                width=1080,
                height=1920,
                duration_sec=10.0,
                fps=30.0,
                video_codec="h264",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                has_audio=True,
                pix_fmt="yuv420p",
            )
            job = VideoJob(
                input_path=source,
                output_path=output,
                info=info,
                encoding_mode=MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
            )
            passlog = build_ffmpeg_passlog_path(output, source)
            passlog.write_text("passlog", encoding="utf-8")
            passlog.with_name(passlog.name + "-0.log").write_text("log", encoding="utf-8")
            passlog.with_name(passlog.name + "-0.log.mbtree").write_text("mbtree", encoding="utf-8")
            process_1 = fake_process(["out_time_ms=5000000\n", "progress=end\n"])
            process_2 = fake_process(["out_time_ms=5000000\n", "progress=end\n"])
            progress_values = []

            with patch("encoder.subprocess.Popen", side_effect=[process_1, process_2]) as popen_mock:
                with patch("encoder.probe_video", return_value=info):
                    with patch("encoder.validate_output_file", return_value=[]):
                        result = Encoder(
                            FFmpegPaths(ffmpeg=Path("ffmpeg.exe"), ffprobe=Path("ffprobe.exe"))
                        ).encode(
                            job,
                            overwrite=True,
                            cancel_event=MagicMock(is_set=MagicMock(return_value=False)),
                            progress_callback=lambda _job, progress: progress_values.append(progress),
                        )

        self.assertEqual(result.status, "success")
        self.assertEqual(popen_mock.call_count, 2)
        first_args = popen_mock.call_args_list[0].args[0]
        second_args = popen_mock.call_args_list[1].args[0]
        self.assertEqual(first_args[first_args.index("-pass") + 1], "1")
        self.assertEqual(second_args[second_args.index("-pass") + 1], "2")
        self.assertIn(0.25, progress_values)
        self.assertIn(0.75, progress_values)
        self.assertFalse(passlog.exists())
        self.assertFalse(passlog.with_name(passlog.name + "-0.log").exists())
        self.assertFalse(passlog.with_name(passlog.name + "-0.log.mbtree").exists())

    def test_h265_two_pass_mode_passes_job_encode_plan_to_ffmpeg_args(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "source.mp4"
            output = temp_path / "out.mp4"
            source.write_bytes(b"source")
            output.write_bytes(b"encoded")
            info = VideoInfo(
                width=1920,
                height=1440,
                duration_sec=10.0,
                fps=30.0,
                video_codec="hevc",
                audio_codec="aac",
                audio_sample_rate=48000,
                audio_channels=2,
                has_audio=True,
                pix_fmt="yuv420p",
            )
            plan = H265EncodePlan(
                selected_profile=PROFILE_MAXIMUM_DETAIL_2PASS,
                target_video_bitrate_kbps=3200,
                target_fps=30.0,
                gop=60,
                keyint_min=30,
                scenecut=40,
                maxrate_kbps=6400,
                bufsize_kbps=12800,
                x265_params=("aq-mode=3", "psy-rd=2.0"),
            )
            job = VideoJob(
                input_path=source,
                output_path=output,
                info=info,
                encoding_mode=MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
                h265_encode_plan=plan,
                target_fps=30.0,
            )
            process_1 = fake_process(["out_time_ms=5000000\n", "progress=end\n"])
            process_2 = fake_process(["out_time_ms=5000000\n", "progress=end\n"])

            with patch("encoder.subprocess.Popen", side_effect=[process_1, process_2]) as popen_mock:
                with patch("encoder.probe_video", return_value=info):
                    with patch("encoder.validate_output_file", return_value=[]) as validate_mock:
                        result = Encoder(
                            FFmpegPaths(ffmpeg=Path("ffmpeg.exe"), ffprobe=Path("ffprobe.exe"))
                        ).encode(
                            job,
                            overwrite=True,
                            cancel_event=MagicMock(is_set=MagicMock(return_value=False)),
                        )

        self.assertEqual(result.status, "success")
        second_args = popen_mock.call_args_list[1].args[0]
        self.assertEqual(second_args[second_args.index("-b:v") + 1], "3200k")
        self.assertEqual(second_args[second_args.index("-r") + 1], "30")
        validate_mock.assert_called()
        self.assertEqual(validate_mock.call_args.kwargs["expected_fps"], 30.0)


def fake_process(stdout_lines):
    process = MagicMock()
    process.stdout = stdout_lines
    process.stderr = []
    process.wait.return_value = 0
    process.poll.return_value = 0
    return process


if __name__ == "__main__":
    unittest.main()
