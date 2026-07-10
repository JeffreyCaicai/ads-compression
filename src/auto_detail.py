from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from content_analyzer import ProductionDetailAnalysis
from models import H265EncodePlan, VideoInfo
from settings import (
    H265_GOP,
    H265_KEYINT_MIN,
    H265_SC_THRESHOLD,
    MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
    PROFILE_BEST_DETAIL_2PASS,
    PROFILE_MAXIMUM_DETAIL_2PASS,
    maximum_detail_target_video_bitrate_kbps,
    target_video_bitrate_kbps,
)

AUTO_DETAIL_THRESHOLD = 65.0


@dataclass(frozen=True)
class AutoDetailDecision:
    selected_profile: str
    risk_score: float
    risk_reasons: str
    source_video_bitrate_kbps: int | None
    analysis: ProductionDetailAnalysis
    encode_plan: H265EncodePlan


def estimate_source_video_bitrate_kbps(info: VideoInfo, input_path: Path | None = None) -> int | None:
    if info.video_bit_rate_kbps:
        return info.video_bit_rate_kbps
    if input_path and input_path.exists() and info.duration_sec > 0:
        total_kbps = round(input_path.stat().st_size * 8 / info.duration_sec / 1000)
        if info.audio_bit_rate_kbps:
            return max(total_kbps - info.audio_bit_rate_kbps, 1)
        return total_kbps
    if info.format_bit_rate_kbps:
        return info.format_bit_rate_kbps
    return None


def build_best_detail_2pass_plan(info: VideoInfo) -> H265EncodePlan:
    display_width, display_height = info.display_dimensions
    target = target_video_bitrate_kbps(
        display_width,
        display_height,
        MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
    )
    return H265EncodePlan(
        selected_profile=PROFILE_BEST_DETAIL_2PASS,
        target_video_bitrate_kbps=target,
        target_fps=25.0,
        gop=int(H265_GOP),
        keyint_min=int(H265_KEYINT_MIN),
        scenecut=int(H265_SC_THRESHOLD),
        maxrate_kbps=round(target * 1.5),
        bufsize_kbps=target * 3,
        x265_params=(),
    )


def build_maximum_detail_2pass_plan(info: VideoInfo) -> H265EncodePlan:
    display_width, display_height = info.display_dimensions
    target = maximum_detail_target_video_bitrate_kbps(display_width, display_height)
    target_fps = 30.0 if info.fps >= 29.0 else 25.0
    gop = 60 if target_fps == 30.0 else 50
    keyint_min = 30 if target_fps == 30.0 else 25
    return H265EncodePlan(
        selected_profile=PROFILE_MAXIMUM_DETAIL_2PASS,
        target_video_bitrate_kbps=target,
        target_fps=target_fps,
        gop=gop,
        keyint_min=keyint_min,
        scenecut=40,
        maxrate_kbps=target * 2,
        bufsize_kbps=target * 4,
        x265_params=(
            "rc-lookahead=50",
            "aq-mode=3",
            "aq-strength=1.0",
            "psy-rd=2.0",
            "psy-rdoq=1.0",
        ),
    )


def choose_auto_detail_plan(
    info: VideoInfo,
    analysis: ProductionDetailAnalysis,
    input_path: Path | None = None,
) -> AutoDetailDecision:
    source_bitrate = estimate_source_video_bitrate_kbps(info, input_path)
    best_plan = build_best_detail_2pass_plan(info)
    score, reasons = _risk_score(info, analysis, source_bitrate, best_plan.target_video_bitrate_kbps)
    if score >= AUTO_DETAIL_THRESHOLD:
        encode_plan = build_maximum_detail_2pass_plan(info)
    else:
        encode_plan = best_plan
    return AutoDetailDecision(
        selected_profile=encode_plan.selected_profile,
        risk_score=round(min(score, 100.0), 1),
        risk_reasons=";".join(reasons),
        source_video_bitrate_kbps=source_bitrate,
        analysis=analysis,
        encode_plan=encode_plan,
    )


def _risk_score(
    info: VideoInfo,
    analysis: ProductionDetailAnalysis,
    source_bitrate: int | None,
    best_detail_target_kbps: int,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    display_width, display_height = info.display_dimensions
    pixels = display_width * display_height
    if pixels >= 2_500_000:
        score += 15
        reasons.append("high_pixel_screen")
    elif display_height > display_width:
        score += 8
        reasons.append("portrait_screen")

    source_bitrate_risk = 0
    if source_bitrate:
        if source_bitrate >= 10_000:
            source_bitrate_risk = max(source_bitrate_risk, 25)
        elif source_bitrate >= 8_000:
            source_bitrate_risk = max(source_bitrate_risk, 18)
        ratio = source_bitrate / max(best_detail_target_kbps, 1)
        if ratio >= 5:
            source_bitrate_risk = max(source_bitrate_risk, 25)
        elif ratio >= 4:
            source_bitrate_risk = max(source_bitrate_risk, 18)
        if source_bitrate_risk:
            score += source_bitrate_risk
            reasons.append(f"source_bitrate_{source_bitrate}k")

    if info.fps >= 29.0:
        score += 15
        reasons.append("fps_30")
    if analysis.peak_complexity_score >= 75:
        score += 25
        reasons.append("peak_complexity_high")
    elif analysis.peak_complexity_score >= 60:
        score += 15
        reasons.append("peak_complexity_medium")
    if analysis.small_detail_score >= 65:
        score += 25
        reasons.append("small_detail_high")
    elif analysis.small_detail_score >= 45:
        score += 15
        reasons.append("small_detail_medium")
    if analysis.peak_motion_score >= 45:
        score += 15
        reasons.append("motion_high")
    elif analysis.peak_motion_score >= 30:
        score += 8
        reasons.append("motion_medium")
    if analysis.scene_change_rate >= 0.4:
        score += 10
        reasons.append("scene_change_high")
    if not reasons:
        reasons.append("ordinary_detail_risk")
    return min(score, 100.0), reasons
