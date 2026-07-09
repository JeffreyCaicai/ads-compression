from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from settings import DEFAULT_ENCODING_MODE, STATUS_PENDING


@dataclass
class VideoInfo:
    width: int
    height: int
    duration_sec: float
    fps: float
    video_codec: str
    audio_codec: Optional[str]
    audio_sample_rate: Optional[int]
    audio_channels: Optional[int]
    has_audio: bool
    pix_fmt: Optional[str] = None
    video_bit_rate_kbps: int | None = None
    audio_bit_rate_kbps: int | None = None
    format_bit_rate_kbps: int | None = None

    @property
    def resolution(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return ""


@dataclass(frozen=True)
class H265EncodePlan:
    selected_profile: str
    target_video_bitrate_kbps: int
    target_fps: float
    gop: int
    keyint_min: int
    scenecut: int
    maxrate_kbps: int
    bufsize_kbps: int
    x265_params: tuple[str, ...] = ()


@dataclass
class VideoJob:
    input_path: Path
    output_path: Path
    info: Optional[VideoInfo] = None
    audio_status: str = "unchecked"
    status: str = STATUS_PENDING
    error_message: str = ""
    original_size_bytes: int = 0
    output_size_bytes: int = 0
    progress: float = 0.0
    source_video_codec: str = ""
    source_audio_codec: str = ""
    encoding_mode: str = DEFAULT_ENCODING_MODE
    content_complexity: str = ""
    content_complexity_score: float = 0.0
    target_video_bitrate_kbps: int | None = None
    h265_encode_plan: Optional[H265EncodePlan] = None
    auto_selected_profile: str = ""
    auto_risk_score: float = 0.0
    auto_risk_reasons: str = ""
    source_video_bitrate_kbps: int | None = None
    source_fps: float = 0.0
    peak_complexity_score: float = 0.0
    small_detail_score: float = 0.0
    peak_motion_score: float = 0.0
    scene_change_rate: float = 0.0
    target_fps: float | None = None
    target_gop: int | None = None


@dataclass
class CompressionResult:
    job: VideoJob
    status: str
    error_message: str = ""
    output_info: Optional[VideoInfo] = None
    created_at: str = ""
    ffmpeg_stderr_tail: list[str] = field(default_factory=list)


@dataclass
class FFmpegPaths:
    ffmpeg: Path
    ffprobe: Path
