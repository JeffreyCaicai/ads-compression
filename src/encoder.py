from __future__ import annotations

import logging
import hashlib
import os
import subprocess
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from auto_detail import build_maximum_detail_2pass_plan
from content_analyzer import AnalysisCancelled
from ffmpeg_utils import FFmpegError, probe_video, startupinfo_for_windows, validate_output_file
from models import CompressionResult, FFmpegPaths, H265EncodePlan, VideoInfo, VideoJob
from quality_check import QualityCheckError, QualityCheckResult, run_quality_check
from settings import (
    DEFAULT_ENCODING_MODE,
    H265_GOP,
    H265_KEYINT_MIN,
    H265_SC_THRESHOLD,
    NO_AUDIO_MESSAGE,
    PROFILE_BEST_DETAIL_2PASS,
    PROFILE_MAXIMUM_DETAIL_2PASS,
    PROBE_ERROR_MESSAGE,
    QUALITY_STATUS_CHECK_FAILED,
    QUALITY_STATUS_RETRY_FAILED,
    STATUS_CANCELLED,
    STATUS_FAILED,
    STATUS_PROCESSING,
    STATUS_SUCCESS,
    encoding_preset,
    is_h265_auto_detail_mode,
    is_h265_mode,
    is_h265_two_pass_mode,
    target_video_bitrate_kbps,
)


ProgressCallback = Callable[[VideoJob, float], None]
QualityEventCallback = Callable[[VideoJob, str, dict[str, object]], None]


@dataclass(frozen=True)
class _RetainedOutputState:
    encode_plan: H265EncodePlan
    target_video_bitrate_kbps: int | None
    target_fps: float | None
    target_gop: int | None
    progress: float
    status: str
    error_message: str
    output_size_bytes: int
    final_selected_profile: str
    quality_check_status: str
    ssim_score: float | None
    detail_retention_percent: float | None


class _QualityBackupTransaction:
    def __init__(
        self,
        output_path: Path,
        backup_path: Path,
        restore_state: Callable[[], None],
    ) -> None:
        self.output_path = output_path
        self.backup_path = backup_path
        self.restore_state = restore_state
        self.owns_best = False
        self.restore_failed = False

    def move_best_to_backup(self) -> None:
        self.output_path.replace(self.backup_path)
        self.owns_best = True

    def restore_best(self) -> str:
        if not self.owns_best:
            return ""
        try:
            self.backup_path.replace(self.output_path)
        except OSError as exc:
            self.restore_failed = True
            return f"Unable to restore Best output after quality retry: {exc}"
        self.owns_best = False
        self.restore_state()
        return ""

    def retain_maximum(self) -> None:
        if not self.owns_best:
            return
        try:
            self.backup_path.unlink()
        except FileNotFoundError:
            pass
        self.owns_best = False


def build_output_path(
    input_path: Path,
    output_dir: Path,
    overwrite: bool,
    encoding_mode: str = DEFAULT_ENCODING_MODE,
) -> Path:
    base = f"{input_path.stem}.mp4"
    candidate = output_dir / base
    source_path = input_path.resolve()
    if candidate.resolve() != source_path and (overwrite or not candidate.exists()):
        return candidate
    counter = 2
    while True:
        candidate = output_dir / f"{input_path.stem}_{counter}.mp4"
        if candidate.resolve() != source_path and not candidate.exists():
            return candidate
        counter += 1


def build_ffmpeg_args(
    ffmpeg_path: Path,
    input_path: Path,
    output_path: Path,
    overwrite: bool = True,
    encoding_mode: str = DEFAULT_ENCODING_MODE,
    source_info: VideoInfo | None = None,
    target_video_bitrate_kbps: int | None = None,
    encode_plan: H265EncodePlan | None = None,
) -> list[str]:
    overwrite_flag = "-y" if overwrite else "-y"
    preset = encoding_preset(encoding_mode)
    args = [
        str(ffmpeg_path),
        overwrite_flag,
        "-hide_banner",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
    ]
    if is_h265_mode(encoding_mode):
        args.extend(
            _h265_video_args(
                preset,
                encoding_mode,
                source_info,
                target_video_bitrate_kbps,
                encode_plan=encode_plan,
            )
        )
    else:
        args.extend(_h264_video_args(preset))
    args.extend(
        [
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            "-progress",
            "pipe:1",
            "-nostats",
            str(output_path),
        ]
    )
    return args


def build_ffmpeg_passlog_path(output_path: Path, input_path: Path) -> Path:
    token = f"{input_path.resolve()}->{output_path.resolve()}".encode("utf-8")
    digest = hashlib.sha1(token).hexdigest()[:12]
    return output_path.parent / f".{output_path.stem}_{digest}_x265_2pass"


def build_quality_backup_path(output_path: Path) -> Path:
    candidate = output_path.with_name(f".{output_path.stem}.quality-backup{output_path.suffix}")
    counter = 2
    while candidate.exists():
        candidate = output_path.with_name(
            f".{output_path.stem}.quality-backup-{counter}{output_path.suffix}"
        )
        counter += 1
    return candidate


def build_ffmpeg_two_pass_args(
    ffmpeg_path: Path,
    input_path: Path,
    output_path: Path,
    pass_number: int,
    passlog_path: Path,
    overwrite: bool = True,
    encoding_mode: str = DEFAULT_ENCODING_MODE,
    source_info: VideoInfo | None = None,
    target_video_bitrate_kbps: int | None = None,
    encode_plan: H265EncodePlan | None = None,
) -> list[str]:
    if pass_number not in {1, 2}:
        raise ValueError("pass_number must be 1 or 2")

    overwrite_flag = "-y" if overwrite else "-y"
    preset = encoding_preset(encoding_mode)
    args = [
        str(ffmpeg_path),
        overwrite_flag,
        "-hide_banner",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
    ]
    if pass_number == 2:
        args.extend(["-map", "0:a:0?"])

    args.extend(
        _h265_video_args(
            preset,
            encoding_mode,
            source_info,
            target_video_bitrate_kbps,
            encode_plan=encode_plan,
            include_mp4_tag=pass_number == 2,
        )
    )
    args.extend(["-pass", str(pass_number), "-passlogfile", str(passlog_path)])

    if pass_number == 1:
        args.extend(["-an", "-progress", "pipe:1", "-nostats", "-f", "null", _null_output_target()])
    else:
        args.extend(
            [
                "-c:a",
                "aac",
                "-b:a",
                "96k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                "-progress",
                "pipe:1",
                "-nostats",
                str(output_path),
            ]
        )
    return args


def _null_output_target() -> str:
    return "NUL" if os.name == "nt" else "/dev/null"


def _h264_video_args(preset: dict[str, str]) -> list[str]:
    args = [
        "-c:v",
        "libx264",
        "-preset",
        preset["preset"],
        "-crf",
        preset["crf"],
        "-profile:v",
        preset["profile"],
        "-level:v",
        preset["level"],
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-g",
        preset["gop"],
        "-keyint_min",
        preset["keyint_min"],
        "-sc_threshold",
        preset["sc_threshold"],
        "-maxrate",
        preset["maxrate"],
        "-bufsize",
        preset["bufsize"],
    ]
    if preset.get("tune"):
        args.extend(["-tune", preset["tune"]])
    if preset.get("bf"):
        args.extend(["-bf", preset["bf"]])
    if preset.get("refs"):
        args.extend(["-refs", preset["refs"]])
    return args


def _h265_video_args(
    preset: dict[str, str],
    encoding_mode: str,
    source_info: VideoInfo | None,
    target_video_bitrate_kbps_override: int | None,
    encode_plan: H265EncodePlan | None = None,
    include_mp4_tag: bool = True,
) -> list[str]:
    width = source_info.width if source_info else 1920
    height = source_info.height if source_info else 1080
    if encode_plan:
        target_kbps = encode_plan.target_video_bitrate_kbps
        fps = f"{encode_plan.target_fps:g}"
        maxrate_kbps = encode_plan.maxrate_kbps
        bufsize_kbps = encode_plan.bufsize_kbps
        x265_parts = [
            f"keyint={encode_plan.gop}",
            f"min-keyint={encode_plan.keyint_min}",
            f"scenecut={encode_plan.scenecut}",
            *encode_plan.x265_params,
        ]
    else:
        target_kbps = target_video_bitrate_kbps_override or target_video_bitrate_kbps(width, height, encoding_mode)
        fps = preset["fps"]
        maxrate_kbps = round(target_kbps * 1.5)
        bufsize_kbps = target_kbps * 3
        x265_parts = [
            f"keyint={H265_GOP}",
            f"min-keyint={H265_KEYINT_MIN}",
            f"scenecut={H265_SC_THRESHOLD}",
        ]
    x265_params = ":".join(x265_parts)
    args = [
        "-c:v",
        "libx265",
        "-preset",
        preset["preset"],
        "-profile:v",
        preset["profile"],
        "-pix_fmt",
        "yuv420p",
        "-r",
        fps,
        "-b:v",
        f"{target_kbps}k",
        "-maxrate",
        f"{maxrate_kbps}k",
        "-bufsize",
        f"{bufsize_kbps}k",
        "-x265-params",
        x265_params,
    ]
    if include_mp4_tag:
        args.extend(["-tag:v", "hvc1"])
    return args


class Encoder:
    def __init__(self, paths: FFmpegPaths) -> None:
        self.paths = paths
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    def cancel(self) -> None:
        with self._lock:
            process = self._process
        if process and process.poll() is None:
            logging.info("Terminating ffmpeg process.")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    def encode(
        self,
        job: VideoJob,
        overwrite: bool,
        cancel_event: threading.Event,
        progress_callback: ProgressCallback | None = None,
        quality_event_callback: QualityEventCallback | None = None,
    ) -> CompressionResult:
        if not job.info:
            return self._fail(job, PROBE_ERROR_MESSAGE)
        if not job.info.has_audio:
            return self._fail(job, NO_AUDIO_MESSAGE)
        if is_h265_auto_detail_mode(job.encoding_mode):
            return self._encode_auto_detail_with_quality(
                job,
                overwrite,
                cancel_event,
                progress_callback,
                quality_event_callback,
            )
        if is_h265_two_pass_mode(job.encoding_mode):
            return self._encode_h265_two_pass(job, overwrite, cancel_event, progress_callback)

        job.status = STATUS_PROCESSING
        job.output_path.parent.mkdir(parents=True, exist_ok=True)
        args = build_ffmpeg_args(
            self.paths.ffmpeg,
            job.input_path,
            job.output_path,
            overwrite=overwrite,
            encoding_mode=job.encoding_mode,
            source_info=job.info,
            target_video_bitrate_kbps=job.target_video_bitrate_kbps,
            encode_plan=job.h265_encode_plan,
        )
        logging.info("Running ffmpeg: %s", args)
        try:
            return_code, stderr_tail, cancelled = self._run_ffmpeg_process(
                args,
                job,
                cancel_event,
                progress_callback=progress_callback,
            )
        except FFmpegError as exc:
            return self._fail(job, str(exc))
        return self._complete_after_ffmpeg(job, return_code, stderr_tail, cancelled)

    def _encode_auto_detail_with_quality(
        self,
        job: VideoJob,
        overwrite: bool,
        cancel_event: threading.Event,
        progress_callback: ProgressCallback | None,
        quality_event_callback: QualityEventCallback | None = None,
    ) -> CompressionResult:
        assert job.info is not None
        initial_plan = job.h265_encode_plan
        if initial_plan is None:
            return self._fail(job, "Auto Detail encode plan is missing.")

        initial_result = self._encode_h265_two_pass(
            job,
            overwrite,
            cancel_event,
            progress_callback,
        )
        if initial_result.status != "success":
            return initial_result

        initial_profile = initial_plan.selected_profile
        job.final_selected_profile = initial_profile
        try:
            initial_quality = self._run_quality_check(job, cancel_event)
        except AnalysisCancelled:
            return self._cancelled_result(job, initial_result.ffmpeg_stderr_tail)
        except QualityCheckError as exc:
            retry_reason = str(exc)
            self._record_quality_check_error(job)
            job.quality_retry_reason = retry_reason
            self._emit_quality_event(
                quality_event_callback,
                job,
                "message.quality_check_failed",
                reason=retry_reason,
            )
            if initial_profile != PROFILE_BEST_DETAIL_2PASS:
                return initial_result
        else:
            self._record_quality_result(job, initial_quality)
            if initial_quality.passed:
                job.quality_retry_reason = ""
                self._emit_quality_result(
                    quality_event_callback,
                    job,
                    "message.quality_passed",
                    initial_quality,
                )
                return initial_result
            retry_reason = initial_quality.reason
            job.quality_retry_reason = retry_reason
            if initial_profile != PROFILE_BEST_DETAIL_2PASS:
                self._emit_quality_result(
                    quality_event_callback,
                    job,
                    "message.quality_warning",
                    initial_quality,
                )
                return initial_result

        initial_state = _RetainedOutputState(
            encode_plan=initial_plan,
            target_video_bitrate_kbps=job.target_video_bitrate_kbps,
            target_fps=job.target_fps,
            target_gop=job.target_gop,
            progress=job.progress,
            status=job.status,
            error_message=job.error_message,
            output_size_bytes=job.output_size_bytes,
            final_selected_profile=initial_profile,
            quality_check_status=job.quality_check_status,
            ssim_score=job.ssim_score,
            detail_retention_percent=job.detail_retention_percent,
        )
        job.quality_retry_reason = retry_reason
        self._emit_quality_event(
            quality_event_callback,
            job,
            "message.quality_retry_started",
            reason=retry_reason,
        )
        if cancel_event.is_set():
            return self._cancelled_result(job, initial_result.ffmpeg_stderr_tail)

        backup = _QualityBackupTransaction(
            job.output_path,
            build_quality_backup_path(job.output_path),
            lambda: self._restore_retained_state(job, initial_state),
        )
        if cancel_event.is_set():
            return self._cancelled_result(job, initial_result.ffmpeg_stderr_tail)
        try:
            backup.move_best_to_backup()
        except OSError as exc:
            logging.warning("Unable to back up Best output before quality retry: %s", exc)
            self._restore_retained_state(job, initial_state)
            job.quality_check_status = QUALITY_STATUS_RETRY_FAILED
            self._emit_quality_event(
                quality_event_callback,
                job,
                "message.quality_retry_restored_best",
            )
            return initial_result

        try:
            maximum_plan = build_maximum_detail_2pass_plan(job.info)
            self._apply_encode_plan(job, maximum_plan)
            if cancel_event.is_set():
                restore_error = backup.restore_best()
                if restore_error:
                    return self._fail(job, restore_error)
                self._emit_quality_event(
                    quality_event_callback,
                    job,
                    "message.quality_retry_restored_best",
                )
                return self._cancelled_result(job, initial_result.ffmpeg_stderr_tail)

            job.quality_retry_count = 1
            retry_result = self._encode_h265_two_pass(
                job,
                overwrite,
                cancel_event,
                progress_callback,
            )
            if retry_result.status != "success":
                restore_error = backup.restore_best()
                if restore_error:
                    return self._fail(job, restore_error, retry_result.ffmpeg_stderr_tail)
                self._emit_quality_event(
                    quality_event_callback,
                    job,
                    "message.quality_retry_restored_best",
                )
                if retry_result.status == "cancelled":
                    return self._cancelled_result(job, retry_result.ffmpeg_stderr_tail)
                job.quality_check_status = QUALITY_STATUS_RETRY_FAILED
                return initial_result

            job.final_selected_profile = PROFILE_MAXIMUM_DETAIL_2PASS
            try:
                retry_quality = self._run_quality_check(job, cancel_event)
            except AnalysisCancelled:
                restore_error = backup.restore_best()
                if restore_error:
                    return self._fail(job, restore_error, retry_result.ffmpeg_stderr_tail)
                self._emit_quality_event(
                    quality_event_callback,
                    job,
                    "message.quality_retry_restored_best",
                )
                return self._cancelled_result(job, retry_result.ffmpeg_stderr_tail)
            except QualityCheckError as exc:
                self._record_quality_check_error(job)
                self._emit_quality_event(
                    quality_event_callback,
                    job,
                    "message.quality_check_failed",
                    reason=str(exc),
                )
            else:
                self._record_quality_result(job, retry_quality)
                self._emit_quality_result(
                    quality_event_callback,
                    job,
                    "message.quality_passed" if retry_quality.passed else "message.quality_warning",
                    retry_quality,
                )

            backup.retain_maximum()
            self._emit_quality_event(
                quality_event_callback,
                job,
                "message.quality_retry_kept_maximum",
            )
            return retry_result
        except Exception:
            restore_error = backup.restore_best()
            if restore_error:
                return self._fail(job, restore_error)
            job.quality_check_status = QUALITY_STATUS_RETRY_FAILED
            self._emit_quality_event(
                quality_event_callback,
                job,
                "message.quality_retry_restored_best",
            )
            raise
        finally:
            if backup.owns_best and not backup.restore_failed:
                restore_error = backup.restore_best()
                if restore_error:
                    logging.error("Quality retry cleanup could not restore Best: %s", restore_error)

    def _run_quality_check(
        self,
        job: VideoJob,
        cancel_event: threading.Event,
    ) -> QualityCheckResult:
        assert job.info is not None
        return run_quality_check(
            self.paths.ffmpeg,
            job.input_path,
            job.output_path,
            job.info,
            job.small_detail_score,
            cancel_event=cancel_event,
        )

    @staticmethod
    def _apply_encode_plan(job: VideoJob, plan: H265EncodePlan) -> None:
        job.h265_encode_plan = plan
        job.target_video_bitrate_kbps = plan.target_video_bitrate_kbps
        job.target_fps = plan.target_fps
        job.target_gop = plan.gop

    @staticmethod
    def _restore_retained_state(job: VideoJob, state: _RetainedOutputState) -> None:
        job.h265_encode_plan = state.encode_plan
        job.target_video_bitrate_kbps = state.target_video_bitrate_kbps
        job.target_fps = state.target_fps
        job.target_gop = state.target_gop
        job.progress = state.progress
        job.status = state.status
        job.error_message = state.error_message
        job.output_size_bytes = state.output_size_bytes
        job.final_selected_profile = state.final_selected_profile
        job.quality_check_status = state.quality_check_status
        job.ssim_score = state.ssim_score
        job.detail_retention_percent = state.detail_retention_percent

    @staticmethod
    def _record_quality_result(job: VideoJob, result: QualityCheckResult) -> None:
        job.quality_check_status = result.status
        job.ssim_score = result.ssim_score
        job.detail_retention_percent = result.detail_retention_percent

    @staticmethod
    def _record_quality_check_error(job: VideoJob) -> None:
        job.quality_check_status = QUALITY_STATUS_CHECK_FAILED
        job.ssim_score = None
        job.detail_retention_percent = None

    @classmethod
    def _emit_quality_result(
        cls,
        callback: QualityEventCallback | None,
        job: VideoJob,
        key: str,
        result: QualityCheckResult,
    ) -> None:
        detail = "n/a" if result.detail_retention_percent is None else f"{result.detail_retention_percent:.1f}"
        cls._emit_quality_event(
            callback,
            job,
            key,
            ssim=f"{result.ssim_score:.3f}",
            detail=detail,
            reason=result.reason,
        )

    @staticmethod
    def _emit_quality_event(
        callback: QualityEventCallback | None,
        job: VideoJob,
        key: str,
        **values: object,
    ) -> None:
        if callback:
            try:
                callback(job, key, {"name": job.input_path.name, **values})
            except Exception as exc:
                logging.warning(
                    "Quality event callback failed for %s (%s): %s",
                    job.input_path,
                    key,
                    exc,
                    exc_info=True,
                )

    def _encode_h265_two_pass(
        self,
        job: VideoJob,
        overwrite: bool,
        cancel_event: threading.Event,
        progress_callback: ProgressCallback | None,
    ) -> CompressionResult:
        assert job.info is not None
        job.status = STATUS_PROCESSING
        job.output_path.parent.mkdir(parents=True, exist_ok=True)
        passlog_path = build_ffmpeg_passlog_path(job.output_path, job.input_path)
        stderr_tail: list[str] = []
        try:
            first_pass_args = build_ffmpeg_two_pass_args(
                self.paths.ffmpeg,
                job.input_path,
                job.output_path,
                pass_number=1,
                passlog_path=passlog_path,
                overwrite=overwrite,
                encoding_mode=job.encoding_mode,
                source_info=job.info,
                target_video_bitrate_kbps=job.target_video_bitrate_kbps,
                encode_plan=job.h265_encode_plan,
            )
            logging.info("Running ffmpeg first pass: %s", first_pass_args)
            try:
                return_code, first_stderr, cancelled = self._run_ffmpeg_process(
                    first_pass_args,
                    job,
                    cancel_event,
                    progress_callback=progress_callback,
                    progress_base=0.0,
                    progress_scale=0.5,
                )
            except FFmpegError as exc:
                return self._fail(job, str(exc), stderr_tail=stderr_tail)
            stderr_tail.extend(first_stderr)
            if cancelled:
                return self._cancelled_result(job, stderr_tail)
            if return_code != 0:
                return self._fail(job, self._ffmpeg_error_message(return_code, first_stderr), stderr_tail=stderr_tail)

            second_pass_args = build_ffmpeg_two_pass_args(
                self.paths.ffmpeg,
                job.input_path,
                job.output_path,
                pass_number=2,
                passlog_path=passlog_path,
                overwrite=overwrite,
                encoding_mode=job.encoding_mode,
                source_info=job.info,
                target_video_bitrate_kbps=job.target_video_bitrate_kbps,
                encode_plan=job.h265_encode_plan,
            )
            logging.info("Running ffmpeg second pass: %s", second_pass_args)
            try:
                return_code, second_stderr, cancelled = self._run_ffmpeg_process(
                    second_pass_args,
                    job,
                    cancel_event,
                    progress_callback=progress_callback,
                    progress_base=0.5,
                    progress_scale=0.5,
                )
            except FFmpegError as exc:
                return self._fail(job, str(exc), stderr_tail=stderr_tail)
            stderr_tail.extend(second_stderr)
            return self._complete_after_ffmpeg(job, return_code, stderr_tail, cancelled)
        finally:
            cleanup_passlog_files(passlog_path)

    def _run_ffmpeg_process(
        self,
        args: list[str],
        job: VideoJob,
        cancel_event: threading.Event,
        progress_callback: ProgressCallback | None = None,
        progress_base: float = 0.0,
        progress_scale: float = 1.0,
    ) -> tuple[int, list[str], bool]:
        stderr_tail: deque[str] = deque(maxlen=100)

        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo_for_windows(),
                bufsize=1,
            )
        except OSError as exc:
            raise FFmpegError(f"无法启动 FFmpeg：{exc}") from exc

        with self._lock:
            self._process = process

        def read_stderr() -> None:
            assert process.stderr is not None
            for line in process.stderr:
                line = line.rstrip()
                if line:
                    stderr_tail.append(line)
                    logging.debug("ffmpeg stderr: %s", line)

        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stderr_thread.start()

        try:
            assert process.stdout is not None
            for line in process.stdout:
                if cancel_event.is_set():
                    self.cancel()
                    break
                key, _, value = line.strip().partition("=")
                if key == "out_time_ms":
                    raw_progress = parse_progress(value, job.info.duration_sec if job.info else 0)
                    progress = progress_base + raw_progress * progress_scale
                    job.progress = progress
                    if progress_callback:
                        progress_callback(job, progress)
            return_code = process.wait()
            stderr_thread.join(timeout=2)
        finally:
            with self._lock:
                if self._process is process:
                    self._process = None

        return return_code, list(stderr_tail), cancel_event.is_set()

    def _complete_after_ffmpeg(
        self,
        job: VideoJob,
        return_code: int,
        stderr_tail: list[str],
        cancelled: bool,
    ) -> CompressionResult:
        if cancelled:
            return self._cancelled_result(job, stderr_tail)
        if return_code != 0:
            return self._fail(job, self._ffmpeg_error_message(return_code, stderr_tail), stderr_tail=stderr_tail)

        job.output_size_bytes = job.output_path.stat().st_size if job.output_path.exists() else 0
        try:
            output_info = probe_video(self.paths.ffprobe, job.output_path)
            validation_errors = validate_output_file(
                job.output_path,
                job.info,
                output_info,
                encoding_mode=job.encoding_mode,
                expected_fps=job.target_fps,
            )
        except FFmpegError as exc:
            return self._fail(job, f"输出验证失败：{exc}", stderr_tail=list(stderr_tail))

        if validation_errors:
            return self._fail(job, "输出验证失败：" + "；".join(validation_errors), stderr_tail=list(stderr_tail))

        job.status = STATUS_SUCCESS
        job.progress = 1.0
        return CompressionResult(
            job=job,
            status="success",
            output_info=output_info,
            created_at=datetime.now().isoformat(timespec="seconds"),
            ffmpeg_stderr_tail=stderr_tail,
        )

    def _cancelled_result(self, job: VideoJob, stderr_tail: list[str]) -> CompressionResult:
        job.status = STATUS_CANCELLED
        return CompressionResult(
            job=job,
            status="cancelled",
            error_message="Cancelled by user.",
            created_at=datetime.now().isoformat(timespec="seconds"),
            ffmpeg_stderr_tail=stderr_tail,
        )

    def _fail(self, job: VideoJob, message: str, stderr_tail: list[str] | None = None) -> CompressionResult:
        job.status = STATUS_FAILED
        job.error_message = message
        logging.error("%s: %s", job.input_path, message)
        return CompressionResult(
            job=job,
            status="failed",
            error_message=message,
            created_at=datetime.now().isoformat(timespec="seconds"),
            ffmpeg_stderr_tail=stderr_tail or [],
        )

    @staticmethod
    def _ffmpeg_error_message(return_code: int, stderr_tail: list[str]) -> str:
        error = "\n".join(stderr_tail[-5:]) or f"FFmpeg 退出码：{return_code}"
        return f"压缩失败：{error}"


def parse_progress(value: str, duration_sec: float) -> float:
    if duration_sec <= 0:
        return 0.0
    try:
        seconds = float(value) / 1_000_000
    except ValueError:
        return 0.0
    return max(0.0, min(seconds / duration_sec, 1.0))


def cleanup_passlog_files(passlog_path: Path) -> None:
    candidates = [
        passlog_path,
        passlog_path.with_name(passlog_path.name + "-0.log"),
        passlog_path.with_name(passlog_path.name + "-0.log.mbtree"),
        passlog_path.with_name(passlog_path.name + ".log"),
        passlog_path.with_name(passlog_path.name + ".log.mbtree"),
    ]
    for candidate in candidates:
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            logging.warning("Unable to remove passlog file: %s", candidate)
