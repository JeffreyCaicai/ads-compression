from __future__ import annotations

from pathlib import Path
import sys


APP_NAME = "广告屏视频压缩工具"
WINDOW_SIZE = "1180x760"

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}
COMPRESSED_SUFFIX = "_h264_crf23_aac96"
HIGH_MOTION_SUFFIX = "_h264_crf21_highmotion_aac96"
DEFAULT_OUTPUT_FOLDER_NAME = "compressed"

CRF = "23"
PRESET = "slow"
AUDIO_BITRATE = "96k"
AUDIO_SAMPLE_RATE = 48000
AUDIO_CHANNELS = 2
TARGET_FPS = 30.0
TARGET_PIX_FMT = "yuv420p"
SILENCE_MAX_VOLUME_DB = -55.0
DURATION_TOLERANCE_SEC = 0.5

COMMON_SCREEN_RESOLUTIONS = {(1920, 1080), (1080, 1920), (1920, 360)}

MODE_STANDARD = "standard"
MODE_HIGH_MOTION = "high_motion"
MODE_SCREEN_SAFE_HIGH_MOTION = "screen_safe_high_motion"
DEFAULT_ENCODING_MODE = MODE_STANDARD
SUPPORTED_ENCODING_MODES = (MODE_STANDARD, MODE_HIGH_MOTION, MODE_SCREEN_SAFE_HIGH_MOTION)

ENCODING_PRESETS = {
    MODE_STANDARD: {
        "suffix": COMPRESSED_SUFFIX,
        "crf": "23",
        "preset": "slow",
        "profile": "high",
        "level": "4.1",
        "gop": "60",
        "keyint_min": "60",
        "sc_threshold": "0",
        "maxrate": "3500k",
        "bufsize": "7000k",
    },
    MODE_HIGH_MOTION: {
        "suffix": HIGH_MOTION_SUFFIX,
        "crf": "21",
        "preset": "slow",
        "profile": "high",
        "level": "4.1",
        "gop": "60",
        "keyint_min": "60",
        "sc_threshold": "0",
        "maxrate": "5500k",
        "bufsize": "11000k",
    },
    MODE_SCREEN_SAFE_HIGH_MOTION: {
        "suffix": "_h264_crf21_screensafe_highmotion_aac96",
        "crf": "21",
        "preset": "slow",
        "profile": "main",
        "level": "4.1",
        "gop": "30",
        "keyint_min": "30",
        "sc_threshold": "40",
        "maxrate": "6500k",
        "bufsize": "12000k",
        "tune": "fastdecode",
        "bf": "0",
        "refs": "2",
    },
}


def encoding_preset(mode: str) -> dict[str, str]:
    return ENCODING_PRESETS.get(mode, ENCODING_PRESETS[DEFAULT_ENCODING_MODE])

STATUS_PENDING = "pending"
STATUS_PROBING = "probing"
STATUS_PROCESSING = "processing"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_CANCELLED = "cancelled"

AUDIO_UNCHECKED = "unchecked"
AUDIO_NORMAL = "normal"
AUDIO_NO_AUDIO = "no_audio"
AUDIO_PROBABLY_SILENT = "probably_silent"
AUDIO_CHECK_FAILED = "check_failed"

NO_AUDIO_MESSAGE = "源文件无音轨。当前生产规范要求保留音频，请更换带音频的源文件。"
PROBE_ERROR_MESSAGE = "无法读取视频信息，请确认文件未损坏，且格式受 FFmpeg 支持。"
FFMPEG_NOT_FOUND_MESSAGE = (
    "未找到 FFmpeg。请确认程序目录下包含 tools/ffmpeg/bin/ffmpeg.exe 和 ffprobe.exe，"
    "或手动选择 FFmpeg bin 目录。"
)


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def default_logs_dir() -> Path:
    return project_root() / "logs"
