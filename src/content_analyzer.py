from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from ffmpeg_utils import startupinfo_for_windows
from settings import (
    CONTENT_COMPLEX,
    CONTENT_SIMPLE,
    CONTENT_STANDARD,
    MODE_H265_SMART_AUTO,
    target_video_bitrate_kbps,
)


SAMPLE_WIDTH = 160
SAMPLE_HEIGHT = 90
SAMPLE_FPS = 2
SAMPLE_MAX_SECONDS = 30.0
PRODUCTION_SAMPLE_WIDTH = 320
PRODUCTION_SAMPLE_HEIGHT = 180
PRODUCTION_SAMPLE_FPS = 2
PRODUCTION_SAMPLE_MAX_SECONDS = 30.0
SAMPLE_TIMEOUT_SECONDS = 120
PROCESS_POLL_INTERVAL_SECONDS = 0.1
PROCESS_TERMINATE_TIMEOUT_SECONDS = 5


class ContentAnalysisError(RuntimeError):
    pass


class AnalysisCancelled(ContentAnalysisError):
    pass


@dataclass
class ContentAnalysis:
    complexity: str
    score: float
    motion_score: float
    spatial_score: float
    scene_change_rate: float
    sampled_frames: int
    target_video_bitrate_kbps: int


@dataclass
class ProductionDetailAnalysis:
    peak_complexity_score: float
    small_detail_score: float
    peak_motion_score: float
    scene_change_rate: float
    sampled_frames: int
    peak_one_second_complexity: float = 0.0
    peak_two_second_complexity: float = 0.0
    spatial_p90: float = 0.0
    spatial_p95: float = 0.0
    small_detail_p90: float = 0.0
    small_detail_p95: float = 0.0
    motion_p90: float = 0.0
    motion_p95: float = 0.0


@dataclass(frozen=True)
class SampleSegment:
    start_sec: float
    duration_sec: float


def build_sample_args(ffmpeg_path: Path, input_path: Path, duration_sec: float) -> list[str]:
    sample_seconds = max(1.0, min(duration_sec or SAMPLE_MAX_SECONDS, SAMPLE_MAX_SECONDS))
    return [
        str(ffmpeg_path),
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-t",
        f"{sample_seconds:.3f}",
        "-an",
        "-vf",
        (
            f"fps={SAMPLE_FPS},"
            f"scale={SAMPLE_WIDTH}:{SAMPLE_HEIGHT}:"
            "force_original_aspect_ratio=decrease:flags=fast_bilinear,"
            f"pad={SAMPLE_WIDTH}:{SAMPLE_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
            "format=gray"
        ),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "pipe:1",
    ]


def _positive_even(value: float) -> int:
    rounded = max(2, int(round(value)))
    return rounded if rounded % 2 == 0 else rounded + 1


def production_sample_dimensions(source_width: int, source_height: int) -> tuple[int, int]:
    if source_width <= 0 or source_height <= 0:
        return PRODUCTION_SAMPLE_WIDTH, PRODUCTION_SAMPLE_HEIGHT
    if source_width >= source_height:
        return PRODUCTION_SAMPLE_WIDTH, _positive_even(PRODUCTION_SAMPLE_WIDTH * source_height / source_width)
    return _positive_even(PRODUCTION_SAMPLE_WIDTH * source_width / source_height), PRODUCTION_SAMPLE_WIDTH


def production_sample_segments(duration_sec: float) -> tuple[SampleSegment, ...]:
    duration = max(0.0, duration_sec)
    if duration <= PRODUCTION_SAMPLE_MAX_SECONDS:
        return (SampleSegment(0.0, duration),)
    segment_duration = 10.0
    middle_start = max(0.0, duration / 2.0 - segment_duration / 2.0)
    end_start = max(0.0, duration - segment_duration)
    return (
        SampleSegment(0.0, segment_duration),
        SampleSegment(middle_start, segment_duration),
        SampleSegment(end_start, segment_duration),
    )


def build_production_detail_sample_args(
    ffmpeg_path: Path,
    input_path: Path,
    source_width: int,
    source_height: int,
    segment: SampleSegment,
) -> list[str]:
    sample_width, sample_height = production_sample_dimensions(source_width, source_height)
    return [
        str(ffmpeg_path),
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{segment.start_sec:.3f}",
        "-i",
        str(input_path),
        "-t",
        f"{segment.duration_sec:.3f}",
        "-an",
        "-vf",
        (
            f"fps={PRODUCTION_SAMPLE_FPS},"
            f"scale={sample_width}:{sample_height}:flags=lanczos,"
            "format=gray"
        ),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "pipe:1",
    ]


def analyze_content(
    ffmpeg_path: Path,
    input_path: Path,
    source_width: int,
    source_height: int,
    duration_sec: float,
) -> ContentAnalysis:
    args = build_sample_args(ffmpeg_path, input_path, duration_sec)
    completed = subprocess.run(
        args,
        capture_output=True,
        startupinfo=startupinfo_for_windows(),
        timeout=SAMPLE_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ContentAnalysisError(stderr or f"FFmpeg analysis failed with code {completed.returncode}.")
    return analyze_raw_frames(completed.stdout, source_width=source_width, source_height=source_height)


def analyze_production_detail(
    ffmpeg_path: Path,
    input_path: Path,
    source_width: int,
    source_height: int,
    duration_sec: float,
    cancel_event: threading.Event | None = None,
) -> ProductionDetailAnalysis:
    raw_segments = []
    segment_frame_counts = []
    sample_width, sample_height = production_sample_dimensions(source_width, source_height)
    frame_size = sample_width * sample_height
    for segment in production_sample_segments(duration_sec):
        args = build_production_detail_sample_args(
            ffmpeg_path, input_path, source_width, source_height, segment
        )
        raw_video = _run_rawvideo_process(args, cancel_event)
        raw_segments.append(raw_video)
        segment_frame_counts.append(len(raw_video) // frame_size)
    return analyze_production_detail_raw_frames(
        b"".join(raw_segments),
        width=sample_width,
        height=sample_height,
        segment_frame_counts=tuple(segment_frame_counts),
    )


def _run_rawvideo_process(args: list[str], cancel_event: threading.Event | None) -> bytes:
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=startupinfo_for_windows(),
    )
    started_at = time.monotonic()
    while True:
        try:
            stdout, stderr = process.communicate(timeout=PROCESS_POLL_INTERVAL_SECONDS)
            break
        except subprocess.TimeoutExpired:
            if cancel_event is not None and cancel_event.is_set():
                _terminate_rawvideo_process(process)
                raise AnalysisCancelled("Production detail analysis cancelled.")
            if time.monotonic() - started_at >= SAMPLE_TIMEOUT_SECONDS:
                _terminate_rawvideo_process(process)
                raise subprocess.TimeoutExpired(args, SAMPLE_TIMEOUT_SECONDS)

    if process.returncode != 0:
        error_message = stderr.decode("utf-8", errors="replace").strip()
        raise ContentAnalysisError(
            error_message or f"FFmpeg production detail analysis failed with code {process.returncode}."
        )
    return stdout


def _terminate_rawvideo_process(process: subprocess.Popen[bytes]) -> None:
    process.terminate()
    try:
        process.communicate(timeout=PROCESS_TERMINATE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()


def analyze_raw_frames(
    raw_video: bytes,
    source_width: int,
    source_height: int,
    encoding_mode: str = MODE_H265_SMART_AUTO,
) -> ContentAnalysis:
    frame_size = SAMPLE_WIDTH * SAMPLE_HEIGHT
    if len(raw_video) < frame_size:
        raise ContentAnalysisError("No sampled frames were decoded.")

    frame_count = len(raw_video) // frame_size
    frames = [
        raw_video[index * frame_size : (index + 1) * frame_size]
        for index in range(frame_count)
    ]
    spatial_values = [_spatial_complexity(frame) for frame in frames]
    motion_values = [
        _motion_complexity(previous, current)
        for previous, current in zip(frames, frames[1:])
    ]

    spatial_score = sum(spatial_values) / len(spatial_values) if spatial_values else 0.0
    motion_score = sum(motion_values) / len(motion_values) if motion_values else 0.0
    scene_changes = sum(1 for value in motion_values if value >= 60.0)
    sample_duration = max(frame_count / SAMPLE_FPS, 0.001)
    scene_change_rate = scene_changes / sample_duration
    score = min(100.0, motion_score * 0.75 + spatial_score * 0.5 + scene_change_rate * 18.0)
    complexity = classify_complexity(score)
    target = target_video_bitrate_kbps(source_width, source_height, encoding_mode, complexity=complexity)
    return ContentAnalysis(
        complexity=complexity,
        score=round(score, 1),
        motion_score=round(motion_score, 1),
        spatial_score=round(spatial_score, 1),
        scene_change_rate=round(scene_change_rate, 3),
        sampled_frames=frame_count,
        target_video_bitrate_kbps=target,
    )


def analyze_production_detail_raw_frames(
    raw_video: bytes,
    width: int = PRODUCTION_SAMPLE_WIDTH,
    height: int = PRODUCTION_SAMPLE_HEIGHT,
    segment_frame_counts: tuple[int, ...] | None = None,
) -> ProductionDetailAnalysis:
    frame_size = width * height
    if len(raw_video) < frame_size:
        raise ContentAnalysisError("No production detail frames were decoded.")

    frame_count = len(raw_video) // frame_size
    frames = [
        raw_video[index * frame_size : (index + 1) * frame_size]
        for index in range(frame_count)
    ]
    spatial_values = [_production_spatial_complexity(frame, width) for frame in frames]
    clustered_detail_values = [_clustered_detail_score(frame, width, height) for frame in frames]
    if segment_frame_counts is None:
        segment_frame_counts = (frame_count,)
    frame_segments = _frame_segments(frames, segment_frame_counts)
    spatial_segments = _frame_segments(spatial_values, segment_frame_counts)
    motion_values = []
    for segment_frames in frame_segments:
        motion_values.extend(
            _production_motion_complexity(previous, current)
            for previous, current in zip(segment_frames, segment_frames[1:])
        )

    peak_one_second_complexity = max(
        (mean for values in spatial_segments for mean in rolling_means(values, 2)),
        default=0.0,
    )
    peak_two_second_complexity = max(
        (mean for values in spatial_segments for mean in rolling_means(values, 4)),
        default=0.0,
    )
    peak_complexity = max(peak_one_second_complexity, peak_two_second_complexity)
    small_detail = percentile(clustered_detail_values, 0.95)
    peak_motion = percentile(motion_values, 0.95)
    scene_changes = sum(1 for value in motion_values if value >= 45.0)
    sample_duration = max(frame_count / PRODUCTION_SAMPLE_FPS, 0.001)
    scene_change_rate = scene_changes / sample_duration

    return ProductionDetailAnalysis(
        peak_complexity_score=round(min(100.0, peak_complexity), 1),
        small_detail_score=round(min(100.0, small_detail), 1),
        peak_motion_score=round(min(100.0, peak_motion), 1),
        scene_change_rate=round(scene_change_rate, 3),
        sampled_frames=frame_count,
        peak_one_second_complexity=round(min(100.0, peak_one_second_complexity), 1),
        peak_two_second_complexity=round(min(100.0, peak_two_second_complexity), 1),
        spatial_p90=round(min(100.0, percentile(spatial_values, 0.90)), 1),
        spatial_p95=round(min(100.0, percentile(spatial_values, 0.95)), 1),
        small_detail_p90=round(min(100.0, percentile(clustered_detail_values, 0.90)), 1),
        small_detail_p95=round(min(100.0, percentile(clustered_detail_values, 0.95)), 1),
        motion_p90=round(min(100.0, percentile(motion_values, 0.90)), 1),
        motion_p95=round(min(100.0, percentile(motion_values, 0.95)), 1),
    )


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * max(0.0, min(percentile_value, 1.0))
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def rolling_means(values: list[float], window_size: int) -> list[float]:
    if window_size <= 0 or len(values) < window_size:
        return []
    return [
        sum(values[index : index + window_size]) / window_size
        for index in range(len(values) - window_size + 1)
    ]


def _frame_segments(values: list[object], segment_counts: tuple[int, ...]) -> list[list[object]]:
    segments = []
    value_offset = 0
    for segment_count in segment_counts:
        segment_end = min(len(values), value_offset + max(0, segment_count))
        segments.append(values[value_offset:segment_end])
        value_offset = segment_end
    if value_offset < len(values):
        segments.append(values[value_offset:])
    return segments


def classify_complexity(score: float) -> str:
    if score < 25.0:
        return CONTENT_SIMPLE
    if score < 55.0:
        return CONTENT_STANDARD
    return CONTENT_COMPLEX


def _spatial_complexity(frame: bytes) -> float:
    count = len(frame)
    if count == 0:
        return 0.0
    mean = sum(frame) / count
    variance = sum((pixel - mean) ** 2 for pixel in frame) / count
    stdev_score = (variance ** 0.5) / 2.55

    horizontal_total = 0
    horizontal_count = 0
    for row_start in range(0, count, SAMPLE_WIDTH):
        row_end = row_start + SAMPLE_WIDTH
        row = frame[row_start:row_end]
        horizontal_total += sum(abs(row[i] - row[i - 1]) for i in range(1, len(row)))
        horizontal_count += max(len(row) - 1, 0)

    vertical_total = 0
    vertical_count = 0
    for offset in range(SAMPLE_WIDTH, count):
        vertical_total += abs(frame[offset] - frame[offset - SAMPLE_WIDTH])
        vertical_count += 1

    edge_average = (horizontal_total + vertical_total) / max(horizontal_count + vertical_count, 1)
    edge_score = edge_average / 2.55
    return min(100.0, stdev_score * 0.6 + edge_score * 1.4)


def _motion_complexity(previous: bytes, current: bytes) -> float:
    if not previous or not current:
        return 0.0
    pair_count = min(len(previous), len(current))
    diff = sum(abs(current[index] - previous[index]) for index in range(pair_count)) / pair_count
    return min(100.0, diff / 2.55)


def _production_spatial_complexity(frame: bytes, width: int = PRODUCTION_SAMPLE_WIDTH) -> float:
    return _spatial_complexity_with_width(frame, width)


def _production_motion_complexity(previous: bytes, current: bytes) -> float:
    return _motion_complexity(previous, current)


def _clustered_detail_score(
    frame: bytes,
    width: int = PRODUCTION_SAMPLE_WIDTH,
    height: int = PRODUCTION_SAMPLE_HEIGHT,
) -> float:
    if not frame or width <= 0 or height <= 0:
        return 0.0

    dense_tiles = set()
    for tile_y in range(8):
        y_start = tile_y * height // 8
        y_end = (tile_y + 1) * height // 8
        for tile_x in range(8):
            x_start = tile_x * width // 8
            x_end = (tile_x + 1) * width // 8
            edge_hits = 0
            checks = 0
            for y in range(y_start, y_end):
                row_start = y * width
                for x in range(x_start, x_end):
                    if x + 1 < x_end:
                        checks += 1
                        if abs(frame[row_start + x] - frame[row_start + x + 1]) >= 40:
                            edge_hits += 1
                    if y + 1 < y_end:
                        checks += 1
                        if abs(frame[row_start + x] - frame[row_start + width + x]) >= 40:
                            edge_hits += 1
            if edge_hits / max(checks, 1) >= 0.12:
                dense_tiles.add((tile_y, tile_x))

    dense_tile_percent = len(dense_tiles) / 64 * 100.0
    largest_cluster_percent = _largest_dense_cluster_size(dense_tiles) / 64 * 100.0
    return min(100.0, dense_tile_percent * 0.6 + largest_cluster_percent * 0.4)


def _largest_dense_cluster_size(dense_tiles: set[tuple[int, int]]) -> int:
    largest_cluster = 0
    unvisited = set(dense_tiles)
    while unvisited:
        cluster_size = 0
        pending = [unvisited.pop()]
        while pending:
            tile_y, tile_x = pending.pop()
            cluster_size += 1
            for neighbor in (
                (tile_y - 1, tile_x),
                (tile_y + 1, tile_x),
                (tile_y, tile_x - 1),
                (tile_y, tile_x + 1),
            ):
                if neighbor in unvisited:
                    unvisited.remove(neighbor)
                    pending.append(neighbor)
        largest_cluster = max(largest_cluster, cluster_size)
    return largest_cluster


def _edge_score(frame: bytes, width: int) -> float:
    count = len(frame)
    if count == 0:
        return 0.0
    horizontal_total = 0
    horizontal_count = 0
    for row_start in range(0, count, width):
        row = frame[row_start : row_start + width]
        horizontal_total += sum(abs(row[i] - row[i - 1]) for i in range(1, len(row)))
        horizontal_count += max(len(row) - 1, 0)
    vertical_total = 0
    vertical_count = 0
    for offset in range(width, count):
        vertical_total += abs(frame[offset] - frame[offset - width])
        vertical_count += 1
    edge_average = (horizontal_total + vertical_total) / max(horizontal_count + vertical_count, 1)
    return min(100.0, edge_average / 2.55)


def _spatial_complexity_with_width(frame: bytes, width: int) -> float:
    count = len(frame)
    if count == 0:
        return 0.0
    mean = sum(frame) / count
    variance = sum((pixel - mean) ** 2 for pixel in frame) / count
    stdev_score = (variance ** 0.5) / 2.55
    edge_score = _edge_score(frame, width)
    return min(100.0, stdev_score * 0.6 + edge_score * 1.4)
