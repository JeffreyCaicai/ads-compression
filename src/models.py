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

    @property
    def resolution(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return ""


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
