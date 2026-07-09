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

COMMON_SCREEN_RESOLUTIONS = {
    (1920, 1080),
    (1080, 1920),
    (1920, 1440),
    (1080, 2560),
    (1920, 360),
}

MODE_STANDARD = "standard"
MODE_HIGH_MOTION = "high_motion"
MODE_SCREEN_SAFE_HIGH_MOTION = "screen_safe_high_motion"
MODE_H265_SMALL_FILE_SIMPLE = "h265_small_file_simple"
MODE_H265_SMALL_FILE = "h265_small_file"
MODE_H265_SMALL_FILE_COMPLEX = "h265_small_file_complex"
MODE_H265_PRODUCTION_BEST_DETAIL = "h265_production_best_detail"
MODE_H265_PRODUCTION_BEST_DETAIL_2PASS = "h265_production_best_detail_2pass"
MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS = "h265_production_auto_detail_2pass"
MODE_H265_SMART_AUTO = "h265_smart_auto"
PROFILE_BEST_DETAIL_2PASS = "best_detail_2pass"
PROFILE_MAXIMUM_DETAIL_2PASS = "maximum_detail_2pass"
DEFAULT_ENCODING_MODE = MODE_STANDARD
H265_ENCODING_MODES = (
    MODE_H265_SMALL_FILE_SIMPLE,
    MODE_H265_SMALL_FILE,
    MODE_H265_SMALL_FILE_COMPLEX,
    MODE_H265_PRODUCTION_BEST_DETAIL,
    MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
    MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
    MODE_H265_SMART_AUTO,
)
SUPPORTED_ENCODING_MODES = (
    MODE_STANDARD,
    MODE_HIGH_MOTION,
    MODE_SCREEN_SAFE_HIGH_MOTION,
    MODE_H265_PRODUCTION_BEST_DETAIL,
    MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
    MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
    MODE_H265_SMART_AUTO,
    MODE_H265_SMALL_FILE,
    MODE_H265_SMALL_FILE_COMPLEX,
    MODE_H265_SMALL_FILE_SIMPLE,
)

CONTENT_SIMPLE = "simple"
CONTENT_STANDARD = "standard"
CONTENT_COMPLEX = "complex"
CONTENT_PRODUCTION_BEST_DETAIL = "production_best_detail"

H265_TARGET_FPS = 25.0
H265_GOP = "250"
H265_KEYINT_MIN = "25"
H265_SC_THRESHOLD = "40"

H265_COMPLEXITY_BY_MODE = {
    MODE_H265_SMALL_FILE_SIMPLE: CONTENT_SIMPLE,
    MODE_H265_SMALL_FILE: CONTENT_STANDARD,
    MODE_H265_SMALL_FILE_COMPLEX: CONTENT_COMPLEX,
    MODE_H265_PRODUCTION_BEST_DETAIL: CONTENT_COMPLEX,
    MODE_H265_PRODUCTION_BEST_DETAIL_2PASS: CONTENT_COMPLEX,
    MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS: CONTENT_COMPLEX,
    MODE_H265_SMART_AUTO: CONTENT_STANDARD,
}

H265_TARGET_BITRATES_KBPS = {
    "full_hd_landscape": {
        CONTENT_SIMPLE: 450,
        CONTENT_STANDARD: 800,
        CONTENT_COMPLEX: 1200,
    },
    "full_hd_portrait": {
        CONTENT_SIMPLE: 500,
        CONTENT_STANDARD: 1300,
        CONTENT_COMPLEX: 1800,
    },
    "high_pixel": {
        CONTENT_SIMPLE: 600,
        CONTENT_STANDARD: 1400,
        CONTENT_COMPLEX: 2200,
    },
}

H265_MAXIMUM_DETAIL_TARGET_BITRATES_KBPS = {
    "full_hd_landscape": 2000,
    "full_hd_portrait": 2600,
    "high_pixel": 3200,
}

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
    MODE_H265_SMALL_FILE_SIMPLE: {
        "suffix": "_h265_smallfile_simple_aac96",
        "crf": "",
        "preset": "slow",
        "profile": "main",
        "codec": "libx265",
        "fps": "25",
        "rate_control": "target_bitrate",
    },
    MODE_H265_SMALL_FILE: {
        "suffix": "_h265_smallfile_aac96",
        "crf": "",
        "preset": "slow",
        "profile": "main",
        "codec": "libx265",
        "fps": "25",
        "rate_control": "target_bitrate",
    },
    MODE_H265_SMALL_FILE_COMPLEX: {
        "suffix": "_h265_smallfile_complex_aac96",
        "crf": "",
        "preset": "slow",
        "profile": "main",
        "codec": "libx265",
        "fps": "25",
        "rate_control": "target_bitrate",
    },
    MODE_H265_PRODUCTION_BEST_DETAIL: {
        "suffix": "_h265_production_best_detail_aac96",
        "crf": "",
        "preset": "slow",
        "profile": "main",
        "codec": "libx265",
        "fps": "25",
        "rate_control": "target_bitrate",
    },
    MODE_H265_PRODUCTION_BEST_DETAIL_2PASS: {
        "suffix": "_h265_production_best_detail_2pass_aac96",
        "crf": "",
        "preset": "slow",
        "profile": "main",
        "codec": "libx265",
        "fps": "25",
        "rate_control": "target_bitrate_2pass",
    },
    MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS: {
        "suffix": "_h265_production_auto_detail_2pass_aac96",
        "crf": "",
        "preset": "slow",
        "profile": "main",
        "codec": "libx265",
        "fps": "25",
        "rate_control": "auto_detail_2pass",
    },
    MODE_H265_SMART_AUTO: {
        "suffix": "_h265_smart_auto_aac96",
        "crf": "",
        "preset": "slow",
        "profile": "main",
        "codec": "libx265",
        "fps": "25",
        "rate_control": "smart_target_bitrate",
    },
}


def encoding_preset(mode: str) -> dict[str, str]:
    return ENCODING_PRESETS.get(mode, ENCODING_PRESETS[DEFAULT_ENCODING_MODE])


def is_h265_mode(mode: str) -> bool:
    return mode in H265_ENCODING_MODES


def is_h265_smart_auto_mode(mode: str) -> bool:
    return mode == MODE_H265_SMART_AUTO


def is_h265_auto_detail_mode(mode: str) -> bool:
    return mode == MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS


def is_h265_two_pass_mode(mode: str) -> bool:
    return mode in {
        MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
        MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
    }


def target_fps_for_mode(mode: str) -> float:
    return H265_TARGET_FPS if is_h265_mode(mode) else TARGET_FPS


def h265_screen_class(width: int, height: int) -> str:
    pixels = width * height
    if pixels >= 2_500_000:
        return "high_pixel"
    if height > width:
        return "full_hd_portrait"
    return "full_hd_landscape"


def h265_content_complexity(mode: str) -> str:
    return H265_COMPLEXITY_BY_MODE.get(mode, CONTENT_STANDARD)


def target_video_bitrate_kbps(width: int, height: int, mode: str, complexity: str | None = None) -> int:
    screen_class = h265_screen_class(width, height)
    selected_complexity = complexity or h265_content_complexity(mode)
    if selected_complexity not in H265_TARGET_BITRATES_KBPS[screen_class]:
        selected_complexity = CONTENT_STANDARD
    return H265_TARGET_BITRATES_KBPS[screen_class][selected_complexity]


def maximum_detail_target_video_bitrate_kbps(width: int, height: int) -> int:
    return H265_MAXIMUM_DETAIL_TARGET_BITRATES_KBPS[h265_screen_class(width, height)]

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
