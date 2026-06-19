from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from models import FFmpegPaths, VideoInfo
from settings import (
    AUDIO_CHANNELS,
    AUDIO_SAMPLE_RATE,
    DURATION_TOLERANCE_SEC,
    FFMPEG_NOT_FOUND_MESSAGE,
    TARGET_FPS,
    TARGET_PIX_FMT,
)


class FFmpegError(RuntimeError):
    pass


def executable_name(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def candidate_roots() -> list[Path]:
    root = runtime_root()
    cwd = Path.cwd()
    candidates: list[Path] = []
    for candidate in [
        cwd,
        root,
        root / "_internal",
        Path(getattr(sys, "_MEIPASS", root)),
        root.parent,
    ]:
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def find_ffmpeg_paths() -> FFmpegPaths | None:
    for root in candidate_roots():
        bin_dir = root / "tools" / "ffmpeg" / "bin"
        ffmpeg = bin_dir / executable_name("ffmpeg")
        ffprobe = bin_dir / executable_name("ffprobe")
        if ffmpeg.exists() and ffprobe.exists():
            return FFmpegPaths(ffmpeg=ffmpeg, ffprobe=ffprobe)

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if ffmpeg_path and ffprobe_path:
        return FFmpegPaths(ffmpeg=Path(ffmpeg_path), ffprobe=Path(ffprobe_path))
    return None


def validate_ffmpeg_bin_dir(bin_dir: Path) -> FFmpegPaths | None:
    ffmpeg = bin_dir / executable_name("ffmpeg")
    ffprobe = bin_dir / executable_name("ffprobe")
    if ffmpeg.exists() and ffprobe.exists():
        return FFmpegPaths(ffmpeg=ffmpeg, ffprobe=ffprobe)
    return None


def require_ffmpeg_paths() -> FFmpegPaths:
    paths = find_ffmpeg_paths()
    if not paths:
        raise FFmpegError(FFMPEG_NOT_FOUND_MESSAGE)
    return paths


def startupinfo_for_windows() -> subprocess.STARTUPINFO | None:
    if os.name != "nt":
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return info


def parse_fraction(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        if "/" in value:
            numerator, denominator = value.split("/", 1)
            denominator_float = float(denominator)
            if denominator_float == 0:
                return 0.0
            return float(numerator) / denominator_float
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_ffprobe_json(payload: dict[str, Any]) -> VideoInfo:
    streams = payload.get("streams") or []
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if not video_stream:
        raise FFmpegError("No video stream found.")

    format_data = payload.get("format") or {}
    duration = parse_float(format_data.get("duration"))
    if duration <= 0:
        duration = parse_float(video_stream.get("duration"))

    return VideoInfo(
        width=int(video_stream.get("width") or 0),
        height=int(video_stream.get("height") or 0),
        duration_sec=duration,
        fps=parse_fraction(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")),
        video_codec=str(video_stream.get("codec_name") or ""),
        audio_codec=str(audio_stream.get("codec_name")) if audio_stream else None,
        audio_sample_rate=parse_int(audio_stream.get("sample_rate")) if audio_stream else None,
        audio_channels=parse_int(audio_stream.get("channels")) if audio_stream else None,
        has_audio=audio_stream is not None,
        pix_fmt=video_stream.get("pix_fmt"),
    )


def probe_video(ffprobe_path: Path, input_path: Path) -> VideoInfo:
    args = [
        str(ffprobe_path),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(input_path),
    ]
    logging.info("Running ffprobe: %s", args)
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        startupinfo=startupinfo_for_windows(),
        check=False,
    )
    if completed.returncode != 0:
        raise FFmpegError(completed.stderr.strip() or "ffprobe failed.")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise FFmpegError("ffprobe returned invalid JSON.") from exc
    return parse_ffprobe_json(payload)


def validate_output_file(output_path: Path, source_info: VideoInfo, output_info: VideoInfo) -> list[str]:
    errors: list[str] = []
    if not output_path.exists() or output_path.stat().st_size <= 0:
        errors.append("输出文件不存在或大小为 0。")
    if output_info.video_codec.lower() != "h264":
        errors.append(f"输出视频编码不是 h264：{output_info.video_codec}")
    if output_info.pix_fmt != TARGET_PIX_FMT:
        errors.append(f"输出像素格式不是 {TARGET_PIX_FMT}：{output_info.pix_fmt}")
    if (output_info.width, output_info.height) != (source_info.width, source_info.height):
        errors.append("输出分辨率与源文件不一致。")
    if abs(output_info.fps - TARGET_FPS) > 0.5:
        errors.append(f"输出帧率不是约 30fps：{output_info.fps:.3f}")
    if output_info.audio_codec != "aac":
        errors.append(f"输出音频编码不是 aac：{output_info.audio_codec}")
    if output_info.audio_sample_rate != AUDIO_SAMPLE_RATE:
        errors.append(f"输出采样率不是 48000Hz：{output_info.audio_sample_rate}")
    if output_info.audio_channels != AUDIO_CHANNELS:
        errors.append(f"输出声道数不是 2：{output_info.audio_channels}")
    if abs(output_info.duration_sec - source_info.duration_sec) > DURATION_TOLERANCE_SEC:
        errors.append("输出时长与源文件差异超过 0.5 秒。")
    return errors
