from __future__ import annotations

import logging
import subprocess
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable

from ffmpeg_utils import FFmpegError, probe_video, startupinfo_for_windows, validate_output_file
from models import CompressionResult, FFmpegPaths, VideoInfo, VideoJob
from settings import (
    DEFAULT_ENCODING_MODE,
    H265_GOP,
    H265_KEYINT_MIN,
    H265_SC_THRESHOLD,
    NO_AUDIO_MESSAGE,
    PROBE_ERROR_MESSAGE,
    STATUS_CANCELLED,
    STATUS_FAILED,
    STATUS_PROCESSING,
    STATUS_SUCCESS,
    encoding_preset,
    is_h265_mode,
    target_video_bitrate_kbps,
)


ProgressCallback = Callable[[VideoJob, float], None]


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
        args.extend(_h265_video_args(preset, encoding_mode, source_info, target_video_bitrate_kbps))
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
) -> list[str]:
    width = source_info.width if source_info else 1920
    height = source_info.height if source_info else 1080
    target_kbps = target_video_bitrate_kbps_override or target_video_bitrate_kbps(width, height, encoding_mode)
    maxrate_kbps = round(target_kbps * 1.5)
    bufsize_kbps = target_kbps * 3
    x265_params = (
        f"keyint={H265_GOP}:"
        f"min-keyint={H265_KEYINT_MIN}:"
        f"scenecut={H265_SC_THRESHOLD}"
    )
    return [
        "-c:v",
        "libx265",
        "-preset",
        preset["preset"],
        "-profile:v",
        preset["profile"],
        "-tag:v",
        "hvc1",
        "-pix_fmt",
        "yuv420p",
        "-r",
        preset["fps"],
        "-b:v",
        f"{target_kbps}k",
        "-maxrate",
        f"{maxrate_kbps}k",
        "-bufsize",
        f"{bufsize_kbps}k",
        "-x265-params",
        x265_params,
    ]


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
    ) -> CompressionResult:
        if not job.info:
            return self._fail(job, PROBE_ERROR_MESSAGE)
        if not job.info.has_audio:
            return self._fail(job, NO_AUDIO_MESSAGE)

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
        )
        logging.info("Running ffmpeg: %s", args)
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
            return self._fail(job, f"无法启动 FFmpeg：{exc}")

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
                    progress = parse_progress(value, job.info.duration_sec)
                    job.progress = progress
                    if progress_callback:
                        progress_callback(job, progress)
            return_code = process.wait()
            stderr_thread.join(timeout=2)
        finally:
            with self._lock:
                if self._process is process:
                    self._process = None

        if cancel_event.is_set():
            job.status = STATUS_CANCELLED
            return CompressionResult(
                job=job,
                status="cancelled",
                error_message="Cancelled by user.",
                created_at=datetime.now().isoformat(timespec="seconds"),
                ffmpeg_stderr_tail=list(stderr_tail),
            )
        if return_code != 0:
            error = "\n".join(list(stderr_tail)[-5:]) or f"FFmpeg 退出码：{return_code}"
            return self._fail(job, f"压缩失败：{error}", stderr_tail=list(stderr_tail))

        job.output_size_bytes = job.output_path.stat().st_size if job.output_path.exists() else 0
        try:
            output_info = probe_video(self.paths.ffprobe, job.output_path)
            validation_errors = validate_output_file(
                job.output_path,
                job.info,
                output_info,
                encoding_mode=job.encoding_mode,
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
            ffmpeg_stderr_tail=list(stderr_tail),
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


def parse_progress(value: str, duration_sec: float) -> float:
    if duration_sec <= 0:
        return 0.0
    try:
        seconds = float(value) / 1_000_000
    except ValueError:
        return 0.0
    return max(0.0, min(seconds / duration_sec, 1.0))
