from dataclasses import replace
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from auto_detail import build_best_detail_2pass_plan, build_maximum_detail_2pass_plan
from content_analyzer import AnalysisCancelled
from encoder import Encoder, build_ffmpeg_passlog_path, cleanup_passlog_files
from models import CompressionResult, FFmpegPaths, H265EncodePlan, VideoInfo, VideoJob
from quality_check import QualityCheckError, QualityCheckResult
from settings import (
    MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
    MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
    MODE_STANDARD,
    NO_AUDIO_MESSAGE,
    PROFILE_BEST_DETAIL_2PASS,
    PROFILE_MAXIMUM_DETAIL_2PASS,
    QUALITY_STATUS_CHECK_FAILED,
    QUALITY_STATUS_NOT_RUN,
    QUALITY_STATUS_PASSED,
    QUALITY_STATUS_RETRY_FAILED,
    QUALITY_STATUS_WARNING,
)


class EncoderTwoPassTests(unittest.TestCase):
    def test_encode_rejects_source_without_audio_before_starting_ffmpeg(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            job = VideoJob(
                input_path=root / "no-audio.mp4",
                output_path=root / "out.mp4",
                info=VideoInfo(
                    width=1920,
                    height=1080,
                    duration_sec=10.0,
                    fps=30.0,
                    video_codec="h264",
                    audio_codec=None,
                    audio_sample_rate=None,
                    audio_channels=None,
                    has_audio=False,
                ),
                encoding_mode=MODE_STANDARD,
            )

            with patch("encoder.subprocess.Popen") as popen:
                result = Encoder(
                    FFmpegPaths(ffmpeg=Path("ffmpeg.exe"), ffprobe=Path("ffprobe.exe"))
                ).encode(job, overwrite=True, cancel_event=threading.Event())

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_message, NO_AUDIO_MESSAGE)
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.error_message, NO_AUDIO_MESSAGE)
        popen.assert_not_called()

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

    def test_cleanup_passlog_files_removes_all_unique_prefix_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            passlog = root / ".out_123456789abc_x265_2pass"
            artifacts = [
                passlog,
                passlog.with_name(passlog.name + "-0.log"),
                passlog.with_name(passlog.name + "-0.log.mbtree"),
                passlog.with_name(passlog.name + "-0.log.cutree"),
                passlog.with_name(passlog.name + "-0.log.temp"),
            ]
            unrelated = root / ".other_x265_2pass-0.log.cutree"
            for artifact in [*artifacts, unrelated]:
                artifact.write_text("temporary", encoding="utf-8")

            cleanup_passlog_files(passlog)

            self.assertFalse(any(artifact.exists() for artifact in artifacts))
            self.assertTrue(unrelated.exists())

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
            )
            process_1 = fake_process(["out_time_ms=5000000\n", "progress=end\n"])
            process_2 = fake_process(["out_time_ms=5000000\n", "progress=end\n"])

            with patch("encoder.subprocess.Popen", side_effect=[process_1, process_2]) as popen_mock:
                with patch("encoder.probe_video", return_value=info):
                    with patch("encoder.validate_output_file", return_value=[]) as validate_mock:
                        with patch("encoder.run_quality_check", return_value=passed_quality()):
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
        self.assertEqual(job.target_fps, 30.0)
        validate_mock.assert_called()
        self.assertEqual(validate_mock.call_args.kwargs["expected_fps"], 30.0)


class AutoDetailQualityRetryTests(unittest.TestCase):
    def test_quality_check_delegates_source_info_to_public_geometry_normalization(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            job.info.width = 1920
            job.info.height = 1080
            job.info.display_width = 1080
            job.info.display_height = 1920

            with patch("encoder.run_quality_check", return_value=passed_quality()) as quality_check:
                result = make_encoder()._run_quality_check(job, threading.Event())

        sampling_info = quality_check.call_args.args[3]
        self.assertTrue(result.passed)
        self.assertIs(sampling_info, job.info)
        self.assertEqual((job.info.width, job.info.height), (1920, 1080))

    def test_best_quality_pass_returns_without_retry_and_emits_pass(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            output_info = replace(job.info, video_codec="best-output")
            events = []
            attempt = scripted_attempts(job, [("success", b"best-output", output_info)])

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt) as encode,
                patch("encoder.run_quality_check", return_value=passed_quality()) as quality_check,
            ):
                result = make_encoder().encode(
                    job,
                    True,
                    threading.Event(),
                    quality_event_callback=collect_events(events),
                )

        self.assertEqual(result.status, "success")
        self.assertIs(result.output_info, output_info)
        self.assertEqual(encode.call_count, 1)
        self.assertEqual(quality_check.call_count, 1)
        self.assertEqual(job.quality_check_status, QUALITY_STATUS_PASSED)
        self.assertEqual(job.ssim_score, 0.96)
        self.assertEqual(job.detail_retention_percent, 90.0)
        self.assertEqual(job.quality_retry_count, 0)
        self.assertEqual(job.quality_retry_reason, "")
        self.assertEqual(job.final_selected_profile, PROFILE_BEST_DETAIL_2PASS)
        self.assertEqual(event_keys(events), ["message.quality_passed"])
        self.assertEqual(events[0][2]["name"], job.input_path.name)

    def test_initial_maximum_quality_warning_never_retries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_MAXIMUM_DETAIL_2PASS)
            events = []
            attempt = scripted_attempts(job, [("success", b"maximum-output", job.info)])

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt) as encode,
                patch("encoder.run_quality_check", return_value=failed_quality()),
            ):
                result = make_encoder().encode(
                    job,
                    True,
                    threading.Event(),
                    quality_event_callback=collect_events(events),
                )

        self.assertEqual(result.status, "success")
        self.assertEqual(encode.call_count, 1)
        self.assertEqual(job.quality_check_status, QUALITY_STATUS_WARNING)
        self.assertEqual(job.quality_retry_count, 0)
        self.assertEqual(job.quality_retry_reason, "ssim_below_threshold")
        self.assertEqual(job.final_selected_profile, PROFILE_MAXIMUM_DETAIL_2PASS)
        self.assertEqual(event_keys(events), ["message.quality_warning"])

    def test_best_quality_failure_retries_maximum_once_and_keeps_retry_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            initial_plan = job.h265_encode_plan
            maximum_info = replace(job.info, video_codec="maximum-output")
            events = []
            attempt = scripted_attempts(
                job,
                [
                    ("success", b"best-output", replace(job.info, video_codec="best-output")),
                    ("success", b"maximum-output", maximum_info),
                ],
            )

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt) as encode,
                patch("encoder.run_quality_check", side_effect=[failed_quality(), passed_quality()]) as check,
            ):
                result = make_encoder().encode(
                    job,
                    True,
                    threading.Event(),
                    quality_event_callback=collect_events(events),
                )

            backup_files = list(Path(temp_dir).glob(".*.quality-backup*.mp4"))
            retained_bytes = job.output_path.read_bytes()

        maximum_plan = build_maximum_detail_2pass_plan(job.info)
        self.assertEqual(result.status, "success")
        self.assertIs(result.output_info, maximum_info)
        self.assertEqual(encode.call_count, 2)
        self.assertEqual(check.call_count, 2)
        self.assertEqual(retained_bytes, b"maximum-output")
        self.assertEqual(backup_files, [])
        self.assertEqual(job.auto_selected_profile, PROFILE_BEST_DETAIL_2PASS)
        self.assertIsNot(job.h265_encode_plan, initial_plan)
        self.assertEqual(job.h265_encode_plan, maximum_plan)
        self.assertEqual(job.target_video_bitrate_kbps, maximum_plan.target_video_bitrate_kbps)
        self.assertEqual(job.target_fps, maximum_plan.target_fps)
        self.assertEqual(job.target_gop, maximum_plan.gop)
        self.assertEqual(job.quality_retry_count, 1)
        self.assertEqual(job.quality_retry_reason, "ssim_below_threshold")
        self.assertEqual(job.final_selected_profile, PROFILE_MAXIMUM_DETAIL_2PASS)
        self.assertEqual(job.quality_check_status, QUALITY_STATUS_PASSED)
        self.assertEqual(
            event_keys(events),
            [
                "message.quality_retry_started",
                "message.quality_passed",
                "message.quality_retry_kept_maximum",
            ],
        )

    def test_best_technical_quality_error_retries_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            events = []
            attempt = scripted_attempts(
                job,
                [
                    ("success", b"best-output", job.info),
                    ("success", b"maximum-output", job.info),
                ],
            )

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt) as encode,
                patch(
                    "encoder.run_quality_check",
                    side_effect=[QualityCheckError("ssim unavailable"), passed_quality()],
                ),
            ):
                result = make_encoder().encode(
                    job,
                    True,
                    threading.Event(),
                    quality_event_callback=collect_events(events),
                )

        self.assertEqual(result.status, "success")
        self.assertEqual(encode.call_count, 2)
        self.assertEqual(job.quality_retry_count, 1)
        self.assertEqual(job.quality_retry_reason, "ssim unavailable")
        self.assertEqual(job.quality_check_status, QUALITY_STATUS_PASSED)
        self.assertEqual(
            event_keys(events),
            [
                "message.quality_check_failed",
                "message.quality_retry_started",
                "message.quality_passed",
                "message.quality_retry_kept_maximum",
            ],
        )

    def test_initial_maximum_technical_quality_error_warns_without_retry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_MAXIMUM_DETAIL_2PASS)
            events = []
            attempt = scripted_attempts(job, [("success", b"maximum-output", job.info)])

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt) as encode,
                patch("encoder.run_quality_check", side_effect=QualityCheckError("ssim unavailable")),
            ):
                result = make_encoder().encode(
                    job,
                    True,
                    threading.Event(),
                    quality_event_callback=collect_events(events),
                )

        self.assertEqual(result.status, "success")
        self.assertEqual(encode.call_count, 1)
        self.assertEqual(job.quality_check_status, QUALITY_STATUS_CHECK_FAILED)
        self.assertEqual(job.quality_retry_count, 0)
        self.assertEqual(job.quality_retry_reason, "ssim unavailable")
        self.assertEqual(job.final_selected_profile, PROFILE_MAXIMUM_DETAIL_2PASS)
        self.assertEqual(event_keys(events), ["message.quality_check_failed"])

    def test_retry_maximum_quality_warning_keeps_maximum(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            events = []
            attempt = scripted_attempts(
                job,
                [
                    ("success", b"best-output", job.info),
                    ("success", b"maximum-output", job.info),
                ],
            )

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt),
                patch("encoder.run_quality_check", side_effect=[failed_quality(), failed_quality(0.92, 70.0)]),
            ):
                result = make_encoder().encode(
                    job,
                    True,
                    threading.Event(),
                    quality_event_callback=collect_events(events),
                )

        self.assertEqual(result.status, "success")
        self.assertEqual(job.quality_check_status, QUALITY_STATUS_WARNING)
        self.assertEqual(job.ssim_score, 0.92)
        self.assertEqual(job.detail_retention_percent, 70.0)
        self.assertEqual(job.quality_retry_reason, "ssim_below_threshold")
        self.assertEqual(job.final_selected_profile, PROFILE_MAXIMUM_DETAIL_2PASS)
        self.assertEqual(
            event_keys(events),
            [
                "message.quality_retry_started",
                "message.quality_warning",
                "message.quality_retry_kept_maximum",
            ],
        )

    def test_retry_maximum_technical_quality_error_keeps_maximum_without_another_encode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            events = []
            attempt = scripted_attempts(
                job,
                [
                    ("success", b"best-output", job.info),
                    ("success", b"maximum-output", job.info),
                ],
            )

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt) as encode,
                patch(
                    "encoder.run_quality_check",
                    side_effect=[failed_quality(), QualityCheckError("maximum check failed")],
                ),
            ):
                result = make_encoder().encode(
                    job,
                    True,
                    threading.Event(),
                    quality_event_callback=collect_events(events),
                )

            retained_bytes = job.output_path.read_bytes()

        self.assertEqual(result.status, "success")
        self.assertEqual(encode.call_count, 2)
        self.assertEqual(retained_bytes, b"maximum-output")
        self.assertEqual(job.quality_check_status, QUALITY_STATUS_CHECK_FAILED)
        self.assertIsNone(job.ssim_score)
        self.assertIsNone(job.detail_retention_percent)
        self.assertEqual(job.quality_retry_count, 1)
        self.assertEqual(job.quality_retry_reason, "ssim_below_threshold")
        self.assertEqual(job.final_selected_profile, PROFILE_MAXIMUM_DETAIL_2PASS)
        self.assertEqual(
            event_keys(events),
            [
                "message.quality_retry_started",
                "message.quality_check_failed",
                "message.quality_retry_kept_maximum",
            ],
        )

    def test_retry_encode_failure_restores_best_file_plan_targets_and_output_info(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            best_plan = job.h265_encode_plan
            best_targets = (job.target_video_bitrate_kbps, job.target_fps, job.target_gop)
            best_info = replace(job.info, video_codec="best-output")
            events = []
            attempt = scripted_attempts(
                job,
                [
                    ("success", b"best-output", best_info),
                    ("failed", b"partial-maximum", None),
                ],
            )

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt),
                patch("encoder.run_quality_check", return_value=failed_quality()),
            ):
                result = make_encoder().encode(
                    job,
                    True,
                    threading.Event(),
                    quality_event_callback=collect_events(events),
                )

            retained_bytes = job.output_path.read_bytes()
            backup_files = list(Path(temp_dir).glob(".*.quality-backup*.mp4"))

        self.assertEqual(result.status, "success")
        self.assertIs(result.output_info, best_info)
        self.assertEqual(retained_bytes, b"best-output")
        self.assertEqual(backup_files, [])
        self.assertEqual(job.status, "success")
        self.assertEqual(job.error_message, "")
        self.assertEqual(job.output_size_bytes, len(b"best-output"))
        self.assertIs(job.h265_encode_plan, best_plan)
        self.assertEqual(
            (job.target_video_bitrate_kbps, job.target_fps, job.target_gop),
            best_targets,
        )
        self.assertEqual(job.auto_selected_profile, PROFILE_BEST_DETAIL_2PASS)
        self.assertEqual(job.final_selected_profile, PROFILE_BEST_DETAIL_2PASS)
        self.assertEqual(job.quality_check_status, QUALITY_STATUS_RETRY_FAILED)
        self.assertEqual(job.ssim_score, 0.93)
        self.assertEqual(job.detail_retention_percent, 75.0)
        self.assertEqual(event_keys(events), ["message.quality_retry_started", "message.quality_retry_restored_best"])

    def test_retry_encode_cancellation_restores_best_and_returns_cancelled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            best_plan = job.h265_encode_plan
            events = []
            attempt = scripted_attempts(
                job,
                [
                    ("success", b"best-output", job.info),
                    ("cancelled", b"partial-maximum", None),
                ],
            )

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt),
                patch("encoder.run_quality_check", return_value=failed_quality()),
            ):
                result = make_encoder().encode(
                    job,
                    True,
                    threading.Event(),
                    quality_event_callback=collect_events(events),
                )

            retained_bytes = job.output_path.read_bytes()

        self.assertEqual(result.status, "cancelled")
        self.assertEqual(retained_bytes, b"best-output")
        self.assertIs(job.h265_encode_plan, best_plan)
        self.assertEqual(job.final_selected_profile, PROFILE_BEST_DETAIL_2PASS)
        self.assertEqual(event_keys(events), ["message.quality_retry_started", "message.quality_retry_restored_best"])

    def test_initial_quality_check_cancellation_retains_output_without_retry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            events = []
            attempt = scripted_attempts(job, [("success", b"best-output", job.info)])

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt) as encode,
                patch("encoder.run_quality_check", side_effect=AnalysisCancelled("cancelled")),
            ):
                result = make_encoder().encode(
                    job,
                    True,
                    threading.Event(),
                    quality_event_callback=collect_events(events),
                )

            retained_bytes = job.output_path.read_bytes()

        self.assertEqual(result.status, "cancelled")
        self.assertEqual(encode.call_count, 1)
        self.assertEqual(retained_bytes, b"best-output")
        self.assertEqual(job.quality_check_status, QUALITY_STATUS_NOT_RUN)
        self.assertEqual(job.quality_retry_count, 0)
        self.assertEqual(job.final_selected_profile, PROFILE_BEST_DETAIL_2PASS)
        self.assertEqual(events, [])

    def test_retry_quality_check_cancellation_restores_best_and_returns_cancelled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            best_plan = job.h265_encode_plan
            events = []
            attempt = scripted_attempts(
                job,
                [
                    ("success", b"best-output", job.info),
                    ("success", b"maximum-output", job.info),
                ],
            )

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt) as encode,
                patch(
                    "encoder.run_quality_check",
                    side_effect=[failed_quality(), AnalysisCancelled("cancelled")],
                ),
            ):
                result = make_encoder().encode(
                    job,
                    True,
                    threading.Event(),
                    quality_event_callback=collect_events(events),
                )

            retained_bytes = job.output_path.read_bytes()

        self.assertEqual(result.status, "cancelled")
        self.assertEqual(encode.call_count, 2)
        self.assertEqual(retained_bytes, b"best-output")
        self.assertIs(job.h265_encode_plan, best_plan)
        self.assertEqual(job.final_selected_profile, PROFILE_BEST_DETAIL_2PASS)
        self.assertEqual(event_keys(events), ["message.quality_retry_started", "message.quality_retry_restored_best"])

    def test_unexpected_maximum_plan_exception_restores_best_as_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            best_plan = job.h265_encode_plan
            attempt = scripted_attempts(job, [("success", b"best-output", job.info)])

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt),
                patch("encoder.run_quality_check", return_value=failed_quality()),
                patch(
                    "encoder.build_maximum_detail_2pass_plan",
                    side_effect=RuntimeError("maximum plan failed"),
                ),
                patch("encoder.logging.warning"),
            ):
                result = make_encoder().encode(job, True, threading.Event())

            self.assertEqual(result.status, "success")
            self.assertTrue(job.output_path.exists())
            self.assertEqual(job.output_path.read_bytes(), b"best-output")
            self.assertIs(job.h265_encode_plan, best_plan)
            self.assertEqual(job.quality_check_status, QUALITY_STATUS_RETRY_FAILED)
            self.assertEqual(list(Path(temp_dir).glob(".*.quality-backup*.mp4")), [])

    def test_unexpected_retry_encode_exception_restores_best_as_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            best_plan = job.h265_encode_plan
            calls = 0

            def encode_attempt(*_args, **_kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    job.output_path.write_bytes(b"best-output")
                    job.output_size_bytes = len(b"best-output")
                    job.status = "success"
                    job.progress = 1.0
                    return CompressionResult(job=job, status="success", output_info=job.info)
                job.output_path.write_bytes(b"partial-maximum")
                job.output_size_bytes = len(b"partial-maximum")
                job.status = "processing"
                job.progress = 0.25
                raise RuntimeError("retry crashed")

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=encode_attempt),
                patch("encoder.run_quality_check", return_value=failed_quality()),
                patch("encoder.logging.warning"),
            ):
                result = make_encoder().encode(job, True, threading.Event())

            self.assertEqual(result.status, "success")
            self.assertEqual(job.output_path.read_bytes(), b"best-output")
            self.assertIs(job.h265_encode_plan, best_plan)
            self.assertEqual(job.progress, 1.0)
            self.assertEqual(job.quality_check_status, QUALITY_STATUS_RETRY_FAILED)
            self.assertEqual(list(Path(temp_dir).glob(".*.quality-backup*.mp4")), [])

    def test_unexpected_retry_quality_exception_restores_best_as_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            best_plan = job.h265_encode_plan
            attempt = scripted_attempts(
                job,
                [
                    ("success", b"best-output", job.info),
                    ("success", b"maximum-output", job.info),
                ],
            )

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt),
                patch(
                    "encoder.run_quality_check",
                    side_effect=[failed_quality(), RuntimeError("unexpected quality failure")],
                ),
                patch("encoder.logging.warning"),
            ):
                result = make_encoder().encode(job, True, threading.Event())

            self.assertEqual(result.status, "success")
            self.assertEqual(job.output_path.read_bytes(), b"best-output")
            self.assertIs(job.h265_encode_plan, best_plan)
            self.assertEqual(job.quality_check_status, QUALITY_STATUS_RETRY_FAILED)
            self.assertEqual(list(Path(temp_dir).glob(".*.quality-backup*.mp4")), [])

    def test_quality_event_callback_exception_does_not_break_retry_transaction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            attempt = scripted_attempts(
                job,
                [
                    ("success", b"best-output", job.info),
                    ("success", b"maximum-output", job.info),
                ],
            )

            def raising_callback(*_args, **_kwargs):
                raise RuntimeError("event consumer failed")

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt) as encode,
                patch("encoder.run_quality_check", side_effect=[failed_quality(), passed_quality()]),
                patch("encoder.logging.warning") as warning,
            ):
                result = make_encoder().encode(
                    job,
                    True,
                    threading.Event(),
                    quality_event_callback=raising_callback,
                )

            self.assertEqual(result.status, "success")
            self.assertEqual(encode.call_count, 2)
            self.assertEqual(job.output_path.read_bytes(), b"maximum-output")
            self.assertEqual(job.final_selected_profile, PROFILE_MAXIMUM_DETAIL_2PASS)
            self.assertGreaterEqual(warning.call_count, 1)

    def test_cancellation_immediately_before_backup_retains_best_without_retry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            cancel_event = threading.Event()
            attempt = scripted_attempts(
                job,
                [
                    ("success", b"best-output", job.info),
                    ("success", b"unexpected-maximum", job.info),
                ],
            )

            def cancel_on_retry_event(_job, key, _values):
                if key == "message.quality_retry_started":
                    cancel_event.set()

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt) as encode,
                patch("encoder.run_quality_check", return_value=failed_quality()),
            ):
                result = make_encoder().encode(
                    job,
                    True,
                    cancel_event,
                    quality_event_callback=cancel_on_retry_event,
                )

            self.assertEqual(result.status, "cancelled")
            self.assertEqual(encode.call_count, 1)
            self.assertEqual(job.output_path.read_bytes(), b"best-output")
            self.assertEqual(job.quality_retry_count, 0)
            self.assertEqual(list(Path(temp_dir).glob(".*.quality-backup*.mp4")), [])

    def test_cancellation_during_backup_path_selection_is_checked_before_move(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            cancel_event = threading.Event()
            attempt = scripted_attempts(
                job,
                [
                    ("success", b"best-output", job.info),
                    ("success", b"unexpected-maximum", job.info),
                ],
            )

            def backup_path_then_cancel(output_path):
                cancel_event.set()
                return output_path.with_name(".output.quality-backup.mp4")

            replace_calls = []
            original_replace = Path.replace

            def track_replace(path, target):
                replace_calls.append((path, target))
                return original_replace(path, target)

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt) as encode,
                patch("encoder.run_quality_check", return_value=failed_quality()),
                patch("encoder.build_quality_backup_path", side_effect=backup_path_then_cancel),
                patch.object(Path, "replace", autospec=True, side_effect=track_replace),
            ):
                result = make_encoder().encode(job, True, cancel_event)

            self.assertEqual(result.status, "cancelled")
            self.assertEqual(encode.call_count, 1)
            self.assertEqual(replace_calls, [])
            self.assertEqual(job.output_path.read_bytes(), b"best-output")
            self.assertEqual(list(Path(temp_dir).glob(".*.quality-backup*.mp4")), [])

    def test_cancellation_immediately_before_retry_restores_best_without_new_process(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            best_plan = job.h265_encode_plan
            cancel_event = threading.Event()
            attempt = scripted_attempts(
                job,
                [
                    ("success", b"best-output", job.info),
                    ("success", b"unexpected-maximum", job.info),
                ],
            )

            def plan_then_cancel(info):
                cancel_event.set()
                return build_maximum_detail_2pass_plan(info)

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt) as encode,
                patch("encoder.run_quality_check", return_value=failed_quality()),
                patch("encoder.build_maximum_detail_2pass_plan", side_effect=plan_then_cancel),
            ):
                result = make_encoder().encode(job, True, cancel_event)

            self.assertEqual(result.status, "cancelled")
            self.assertEqual(encode.call_count, 1)
            self.assertEqual(job.output_path.read_bytes(), b"best-output")
            self.assertIs(job.h265_encode_plan, best_plan)
            self.assertEqual(job.quality_retry_count, 0)
            self.assertEqual(list(Path(temp_dir).glob(".*.quality-backup*.mp4")), [])

    def test_restore_failure_preserves_best_backup_and_returns_failed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            attempt = scripted_attempts(
                job,
                [
                    ("success", b"best-output", job.info),
                    ("failed", b"partial-maximum", None),
                ],
            )
            original_replace = Path.replace

            def replace_with_restore_failure(path, target):
                if path.name.startswith(".output.quality-backup"):
                    raise OSError("restore denied")
                return original_replace(path, target)

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt),
                patch("encoder.run_quality_check", return_value=failed_quality()),
                patch.object(Path, "replace", autospec=True, side_effect=replace_with_restore_failure),
            ):
                result = make_encoder().encode(job, True, threading.Event())

            backups = list(Path(temp_dir).glob(".*.quality-backup*.mp4"))
            self.assertEqual(result.status, "failed")
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), b"best-output")

    def test_backup_cleanup_exception_returns_restored_best_as_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            best_plan = job.h265_encode_plan
            best_targets = (job.target_video_bitrate_kbps, job.target_fps, job.target_gop)
            events = []
            attempt = scripted_attempts(
                job,
                [
                    ("success", b"best-output", job.info),
                    ("success", b"maximum-output", job.info),
                ],
            )

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt),
                patch("encoder.run_quality_check", side_effect=[failed_quality(), passed_quality()]),
                patch.object(Path, "unlink", autospec=True, side_effect=OSError("cleanup denied")),
                patch("encoder.logging.warning") as warning,
            ):
                result = make_encoder().encode(
                    job,
                    True,
                    threading.Event(),
                    quality_event_callback=collect_events(events),
                )

            self.assertEqual(result.status, "success")
            self.assertIs(result.output_info, job.info)
            warning.assert_called_once()
            self.assertEqual(job.output_path.read_bytes(), b"best-output")
            self.assertIs(job.h265_encode_plan, best_plan)
            self.assertEqual(
                (job.target_video_bitrate_kbps, job.target_fps, job.target_gop),
                best_targets,
            )
            self.assertEqual(job.final_selected_profile, PROFILE_BEST_DETAIL_2PASS)
            self.assertEqual(job.quality_check_status, QUALITY_STATUS_RETRY_FAILED)
            self.assertEqual(job.ssim_score, 0.93)
            self.assertEqual(job.detail_retention_percent, 75.0)
            self.assertEqual(job.quality_retry_reason, "ssim_below_threshold")
            self.assertEqual(
                event_keys(events),
                [
                    "message.quality_retry_started",
                    "message.quality_passed",
                    "message.quality_retry_restored_best",
                ],
            )
            self.assertEqual(list(Path(temp_dir).glob(".*.quality-backup*.mp4")), [])

    def test_retry_failure_restores_first_success_progress_status_error_and_size(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            calls = 0

            def encode_attempt(*_args, **_kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    job.output_path.write_bytes(b"best-output")
                    job.output_size_bytes = len(b"best-output")
                    job.status = "success"
                    job.error_message = ""
                    job.progress = 1.0
                    return CompressionResult(job=job, status="success", output_info=job.info)
                job.output_path.write_bytes(b"partial-maximum")
                job.output_size_bytes = len(b"partial-maximum")
                job.status = "failed"
                job.error_message = "maximum failed"
                job.progress = 0.25
                return CompressionResult(job=job, status="failed", error_message=job.error_message)

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=encode_attempt),
                patch("encoder.run_quality_check", return_value=failed_quality()),
            ):
                result = make_encoder().encode(job, True, threading.Event())

            self.assertEqual(result.status, "success")
            self.assertEqual(job.output_path.read_bytes(), b"best-output")
            self.assertEqual(job.progress, 1.0)
            self.assertEqual(job.status, "success")
            self.assertEqual(job.error_message, "")
            self.assertEqual(job.output_size_bytes, len(b"best-output"))

    def test_non_auto_two_pass_mode_never_runs_quality_check(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            job = auto_detail_job(Path(temp_dir), PROFILE_BEST_DETAIL_2PASS)
            job.encoding_mode = MODE_H265_PRODUCTION_BEST_DETAIL_2PASS
            attempt = scripted_attempts(job, [("success", b"best-output", job.info)])

            with (
                patch.object(Encoder, "_encode_h265_two_pass", side_effect=attempt) as encode,
                patch("encoder.run_quality_check") as quality_check,
            ):
                result = make_encoder().encode(job, True, threading.Event())

        self.assertEqual(result.status, "success")
        self.assertEqual(encode.call_count, 1)
        quality_check.assert_not_called()


def fake_process(stdout_lines):
    process = MagicMock()
    process.stdout = stdout_lines
    process.stderr = []
    process.wait.return_value = 0
    process.poll.return_value = 0
    return process


def make_info() -> VideoInfo:
    return VideoInfo(
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


def auto_detail_job(temp_dir: Path, profile: str) -> VideoJob:
    source = temp_dir / "source.mp4"
    source.write_bytes(b"source")
    info = make_info()
    if profile == PROFILE_BEST_DETAIL_2PASS:
        plan = build_best_detail_2pass_plan(info)
    else:
        plan = build_maximum_detail_2pass_plan(info)
    return VideoJob(
        input_path=source,
        output_path=temp_dir / "output.mp4",
        info=info,
        encoding_mode=MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
        h265_encode_plan=plan,
        auto_selected_profile=profile,
        small_detail_score=40.0,
        target_video_bitrate_kbps=plan.target_video_bitrate_kbps,
        target_fps=plan.target_fps,
        target_gop=plan.gop,
    )


def make_encoder() -> Encoder:
    return Encoder(FFmpegPaths(ffmpeg=Path("ffmpeg.exe"), ffprobe=Path("ffprobe.exe")))


def scripted_attempts(job: VideoJob, outcomes):
    remaining = list(outcomes)

    def run(*_args, **_kwargs):
        status, output_bytes, output_info = remaining.pop(0)
        if output_bytes is not None:
            job.output_path.write_bytes(output_bytes)
            job.output_size_bytes = len(output_bytes)
        job.status = status
        if status == "success":
            job.error_message = ""
            return CompressionResult(job=job, status="success", output_info=output_info)
        if status == "cancelled":
            return CompressionResult(job=job, status="cancelled", error_message="Cancelled by user.")
        job.error_message = "maximum failed"
        return CompressionResult(job=job, status="failed", error_message=job.error_message)

    return run


def passed_quality() -> QualityCheckResult:
    return QualityCheckResult(True, QUALITY_STATUS_PASSED, 0.96, 90.0, "", 36.0)


def failed_quality(ssim: float = 0.93, detail: float = 75.0) -> QualityCheckResult:
    return QualityCheckResult(
        False,
        QUALITY_STATUS_WARNING,
        ssim,
        detail,
        "ssim_below_threshold",
        30.0,
    )


def collect_events(events):
    def callback(job: VideoJob, key: str, values: dict[str, object]) -> None:
        events.append((job, key, values))

    return callback


def event_keys(events) -> list[str]:
    return [event[1] for event in events]


if __name__ == "__main__":
    unittest.main()
