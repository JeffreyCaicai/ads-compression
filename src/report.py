from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from models import CompressionResult, VideoInfo, VideoJob
from settings import encoding_preset, is_h265_mode, target_fps_for_mode, target_video_bitrate_kbps


REPORT_FIELDS = [
    "source_file",
    "output_file",
    "status",
    "error_message",
    "duration_sec",
    "resolution",
    "original_size_mb",
    "output_size_mb",
    "size_reduction_percent",
    "source_video_codec",
    "output_video_codec",
    "source_audio_codec",
    "output_audio_codec",
    "audio_status",
    "encoding_mode",
    "crf",
    "preset",
    "target_video_bitrate_kbps",
    "target_fps",
    "content_complexity",
    "content_complexity_score",
    "created_at",
]


def mb(size_bytes: int) -> float:
    return round(size_bytes / 1024 / 1024, 2)


def reduction_percent(original_bytes: int, output_bytes: int) -> str:
    if original_bytes <= 0 or output_bytes <= 0:
        return ""
    return f"{round((1 - output_bytes / original_bytes) * 100, 1)}"


def row_from_result(result: CompressionResult) -> dict[str, str]:
    job = result.job
    source_info = job.info
    output_info = result.output_info
    preset = encoding_preset(job.encoding_mode)
    target_bitrate = ""
    if job.target_video_bitrate_kbps:
        target_bitrate = str(job.target_video_bitrate_kbps)
    elif source_info and is_h265_mode(job.encoding_mode):
        target_bitrate = str(target_video_bitrate_kbps(source_info.width, source_info.height, job.encoding_mode))
    return {
        "source_file": str(job.input_path),
        "output_file": str(job.output_path),
        "status": result.status,
        "error_message": result.error_message or job.error_message,
        "duration_sec": format_number(source_info.duration_sec if source_info else 0),
        "resolution": source_info.resolution if source_info else "",
        "original_size_mb": format_number(mb(job.original_size_bytes)),
        "output_size_mb": format_number(mb(job.output_size_bytes)) if job.output_size_bytes else "",
        "size_reduction_percent": reduction_percent(job.original_size_bytes, job.output_size_bytes),
        "source_video_codec": source_info.video_codec if source_info else job.source_video_codec,
        "output_video_codec": output_info.video_codec if output_info else "",
        "source_audio_codec": source_info.audio_codec if source_info and source_info.audio_codec else job.source_audio_codec,
        "output_audio_codec": output_info.audio_codec if output_info and output_info.audio_codec else "",
        "audio_status": job.audio_status,
        "encoding_mode": job.encoding_mode,
        "crf": preset["crf"],
        "preset": preset["preset"],
        "target_video_bitrate_kbps": target_bitrate,
        "target_fps": format_number(target_fps_for_mode(job.encoding_mode)),
        "content_complexity": job.content_complexity,
        "content_complexity_score": format_number(job.content_complexity_score) if job.content_complexity_score else "",
        "created_at": result.created_at or datetime.now().isoformat(timespec="seconds"),
    }


def format_number(value: float) -> str:
    if value == "":
        return ""
    if abs(value - int(value)) < 0.000001:
        return str(int(value))
    return str(round(value, 3)).rstrip("0").rstrip(".")


def write_report(output_dir: Path, results: list[CompressionResult]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"compression_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    report_path = output_dir / filename
    with report_path.open("w", encoding="utf-8-sig", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(row_from_result(result))
    return report_path
