from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ffmpeg_utils import startupinfo_for_windows
from settings import AUDIO_CHECK_FAILED, AUDIO_NORMAL, AUDIO_PROBABLY_SILENT, SILENCE_MAX_VOLUME_DB


VOLUME_RE = re.compile(r"(mean_volume|max_volume):\s*(-?inf|-?\d+(?:\.\d+)?)\s*dB")


@dataclass
class VolumeDetectResult:
    audio_status: str
    mean_volume: float | None = None
    max_volume: float | None = None
    raw_output: str = ""


def parse_db(value: str) -> float:
    if value == "-inf":
        return float("-inf")
    return float(value)


def parse_volumedetect_output(output: str) -> VolumeDetectResult:
    values: dict[str, float] = {}
    for key, value in VOLUME_RE.findall(output):
        values[key] = parse_db(value)
    max_volume = values.get("max_volume")
    mean_volume = values.get("mean_volume")
    if max_volume is None:
        return VolumeDetectResult(audio_status=AUDIO_CHECK_FAILED, raw_output=output)
    if max_volume <= SILENCE_MAX_VOLUME_DB:
        status = AUDIO_PROBABLY_SILENT
    else:
        status = AUDIO_NORMAL
    return VolumeDetectResult(status, mean_volume=mean_volume, max_volume=max_volume, raw_output=output)


def null_device() -> str:
    return "NUL" if os.name == "nt" else "/dev/null"


def detect_volume(ffmpeg_path: Path, input_path: Path) -> VolumeDetectResult:
    args = [
        str(ffmpeg_path),
        "-hide_banner",
        "-i",
        str(input_path),
        "-af",
        "volumedetect",
        "-f",
        "null",
        null_device(),
    ]
    logging.info("Running volumedetect: %s", args)
    completed = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        startupinfo=startupinfo_for_windows(),
        check=False,
    )
    output = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
    return parse_volumedetect_output(output)
