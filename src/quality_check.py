from __future__ import annotations

import math
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from content_analyzer import (
    AnalysisCancelled,
    ContentAnalysisError,
    PROCESS_POLL_INTERVAL_SECONDS,
    PROCESS_TERMINATE_TIMEOUT_SECONDS,
    SampleSegment,
    analyze_production_detail,
    production_sample_dimensions,
    production_sample_segments,
)
from ffmpeg_utils import startupinfo_for_windows
from models import VideoInfo
from settings import (
    QUALITY_DETAIL_RETENTION_THRESHOLD,
    QUALITY_DETAIL_SOURCE_MIN,
    QUALITY_SSIM_THRESHOLD,
    QUALITY_STATUS_PASSED,
    QUALITY_STATUS_WARNING,
)


_SSIM_ALL_PATTERN = re.compile(r"\bSSIM\b.*?\bAll:([^\s]+)")


class QualityCheckError(RuntimeError):
    pass


@dataclass(frozen=True)
class QualityCheckResult:
    passed: bool
    status: str
    ssim_score: float
    detail_retention_percent: float | None
    reason: str
    output_detail_score: float


def build_ssim_args(
    ffmpeg_path: Path,
    source_path: Path,
    output_path: Path,
    width: int,
    height: int,
    segment: SampleSegment,
) -> list[str]:
    normalized_input = (
        f"fps=2,scale={width}:{height}:flags=lanczos,format=gray,setpts=PTS-STARTPTS"
    )
    graph = (
        f"[0:v]{normalized_input}[source];"
        f"[1:v]{normalized_input}[output];"
        "[source][output]ssim"
    )
    return [
        str(ffmpeg_path),
        "-hide_banner",
        "-loglevel",
        "info",
        "-ss",
        f"{segment.start_sec:.3f}",
        "-i",
        str(source_path),
        "-ss",
        f"{segment.start_sec:.3f}",
        "-i",
        str(output_path),
        "-t",
        f"{segment.duration_sec:.3f}",
        "-an",
        "-lavfi",
        graph,
        "-f",
        "null",
        "-",
    ]


def parse_ssim_score(stderr: str) -> float:
    matches = _SSIM_ALL_PATTERN.findall(stderr)
    if not matches:
        raise QualityCheckError("FFmpeg SSIM output did not include an aggregate All score.")

    try:
        score = float(matches[-1])
    except ValueError as error:
        raise QualityCheckError("FFmpeg SSIM aggregate All score was invalid.") from error
    if not math.isfinite(score):
        raise QualityCheckError("FFmpeg SSIM aggregate All score was not finite.")
    return score


def evaluate_quality(
    ssim_score: float, source_detail: float, output_detail: float
) -> QualityCheckResult:
    if not math.isfinite(ssim_score):
        raise QualityCheckError("SSIM score was not finite.")

    detail_retention_percent = None
    if source_detail > 0:
        detail_retention_percent = output_detail / source_detail * 100.0

    reasons = []
    if ssim_score < QUALITY_SSIM_THRESHOLD:
        reasons.append("ssim_below_threshold")
    if (
        source_detail >= QUALITY_DETAIL_SOURCE_MIN
        and detail_retention_percent is not None
        and detail_retention_percent < QUALITY_DETAIL_RETENTION_THRESHOLD
    ):
        reasons.append("detail_retention_below_threshold")

    passed = not reasons
    return QualityCheckResult(
        passed=passed,
        status=QUALITY_STATUS_PASSED if passed else QUALITY_STATUS_WARNING,
        ssim_score=ssim_score,
        detail_retention_percent=detail_retention_percent,
        reason=";".join(reasons),
        output_detail_score=output_detail,
    )


def run_quality_check(
    ffmpeg_path: Path,
    source_path: Path,
    output_path: Path,
    source_info: VideoInfo,
    source_detail: float,
    cancel_event: threading.Event | None = None,
) -> QualityCheckResult:
    try:
        return _run_quality_check(
            ffmpeg_path,
            source_path,
            output_path,
            source_info,
            source_detail,
            cancel_event,
        )
    except AnalysisCancelled:
        raise
    except QualityCheckError:
        raise
    except (ContentAnalysisError, subprocess.TimeoutExpired, OSError) as exc:
        message = str(exc).strip() or exc.__class__.__name__
        raise QualityCheckError(message) from exc


def _run_quality_check(
    ffmpeg_path: Path,
    source_path: Path,
    output_path: Path,
    source_info: VideoInfo,
    source_detail: float,
    cancel_event: threading.Event | None,
) -> QualityCheckResult:
    width, height = production_sample_dimensions(source_info.width, source_info.height)
    segment_scores = []
    for segment in production_sample_segments(source_info.duration_sec):
        stderr = _run_ssim_process(
            build_ssim_args(ffmpeg_path, source_path, output_path, width, height, segment), cancel_event
        )
        segment_scores.append(parse_ssim_score(stderr))

    if not segment_scores:
        raise QualityCheckError("No SSIM segments were analyzed.")
    ssim_score = sum(segment_scores) / len(segment_scores)
    if not math.isfinite(ssim_score):
        raise QualityCheckError("Average SSIM score was not finite.")

    output_analysis = analyze_production_detail(
        ffmpeg_path,
        output_path,
        source_info.width,
        source_info.height,
        source_info.duration_sec,
        cancel_event=cancel_event,
    )
    return evaluate_quality(ssim_score, source_detail, output_analysis.small_detail_score)


def _run_ssim_process(args: list[str], cancel_event: threading.Event | None) -> str:
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=startupinfo_for_windows(),
    )
    _raise_if_ssim_cancelled(process, cancel_event)
    while True:
        try:
            _, stderr = process.communicate(timeout=PROCESS_POLL_INTERVAL_SECONDS)
            break
        except subprocess.TimeoutExpired:
            _raise_if_ssim_cancelled(process, cancel_event)

    _raise_if_ssim_cancelled(process, cancel_event)
    if process.returncode != 0:
        _raise_if_ssim_cancelled(process, cancel_event)
        error_message = stderr.decode("utf-8", errors="replace").strip()
        raise QualityCheckError(
            error_message or f"FFmpeg SSIM analysis failed with code {process.returncode}."
        )
    return stderr.decode("utf-8", errors="replace")


def _raise_if_ssim_cancelled(
    process: subprocess.Popen[bytes], cancel_event: threading.Event | None
) -> None:
    if cancel_event is not None and cancel_event.is_set():
        _terminate_ssim_process(process)
        raise AnalysisCancelled("SSIM quality analysis cancelled.")


def _terminate_ssim_process(process: subprocess.Popen[bytes]) -> None:
    process.terminate()
    try:
        process.communicate(timeout=PROCESS_TERMINATE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
