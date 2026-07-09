import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from content_analyzer import (
    PRODUCTION_SAMPLE_FPS,
    PRODUCTION_SAMPLE_HEIGHT,
    PRODUCTION_SAMPLE_WIDTH,
    SampleSegment,
    SAMPLE_FPS,
    SAMPLE_HEIGHT,
    SAMPLE_WIDTH,
    analyze_production_detail_raw_frames,
    analyze_raw_frames,
    build_production_detail_sample_args,
    build_sample_args,
    production_sample_dimensions,
    production_sample_segments,
)
from settings import CONTENT_COMPLEX, CONTENT_SIMPLE, MODE_H265_SMART_AUTO


def solid_frames(value: int, count: int) -> bytes:
    frame = bytes([value]) * (SAMPLE_WIDTH * SAMPLE_HEIGHT)
    return frame * count


def alternating_frames(count: int) -> bytes:
    frames = []
    for index in range(count):
        value = 0 if index % 2 == 0 else 255
        frames.append(bytes([value]) * (SAMPLE_WIDTH * SAMPLE_HEIGHT))
    return b"".join(frames)


def production_solid_frames(value: int, count: int) -> bytes:
    frame = bytes([value]) * (PRODUCTION_SAMPLE_WIDTH * PRODUCTION_SAMPLE_HEIGHT)
    return frame * count


def production_checkerboard_frames(count: int) -> bytes:
    frames = []
    for frame_index in range(count):
        pixels = []
        phase = frame_index % 2
        for y in range(PRODUCTION_SAMPLE_HEIGHT):
            for x in range(PRODUCTION_SAMPLE_WIDTH):
                pixels.append(255 if ((x // 4 + y // 4 + phase) % 2) else 0)
        frames.append(bytes(pixels))
    return b"".join(frames)


class ContentAnalyzerTests(unittest.TestCase):
    def test_production_sample_dimensions_preserve_company_screen_orientations(self):
        self.assertEqual(production_sample_dimensions(1920, 1080), (320, 180))
        self.assertEqual(production_sample_dimensions(1920, 1440), (320, 240))
        self.assertEqual(production_sample_dimensions(1080, 1920), (180, 320))
        self.assertEqual(production_sample_dimensions(1080, 2560), (136, 320))
        self.assertEqual(production_sample_dimensions(1920, 360), (320, 60))

    def test_production_sample_args_use_lanczos_without_padding(self):
        segment = SampleSegment(0.0, 15.0)
        args = build_production_detail_sample_args(
            Path("ffmpeg.exe"), Path("portrait.mp4"), 1080, 1920, segment
        )
        vf = args[args.index("-vf") + 1]
        self.assertIn("scale=180:320:flags=lanczos", vf)
        self.assertNotIn("pad=", vf)

    def test_short_production_sample_uses_full_duration(self):
        self.assertEqual(production_sample_segments(15.0), (SampleSegment(0.0, 15.0),))

    def test_long_production_sample_uses_start_middle_and_end(self):
        self.assertEqual(
            production_sample_segments(60.0),
            (SampleSegment(0.0, 10.0), SampleSegment(25.0, 10.0), SampleSegment(50.0, 10.0)),
        )

    def test_static_low_detail_sample_is_simple(self):
        analysis = analyze_raw_frames(
            solid_frames(96, 10),
            source_width=1080,
            source_height=1920,
        )

        self.assertEqual(analysis.complexity, CONTENT_SIMPLE)
        self.assertEqual(analysis.target_video_bitrate_kbps, 500)
        self.assertEqual(analysis.sampled_frames, 10)

    def test_high_motion_sample_is_complex_and_uses_high_pixel_target(self):
        analysis = analyze_raw_frames(
            alternating_frames(10),
            source_width=1080,
            source_height=2560,
        )

        self.assertEqual(analysis.complexity, CONTENT_COMPLEX)
        self.assertEqual(analysis.target_video_bitrate_kbps, 2200)
        self.assertGreaterEqual(analysis.motion_score, 90)

    def test_sample_args_decode_small_gray_frames(self):
        args = build_sample_args(Path("ffmpeg.exe"), Path("input video.mp4"), duration_sec=15.0)

        self.assertEqual(args[:4], [str(Path("ffmpeg.exe")), "-hide_banner", "-loglevel", "error"])
        self.assertIn("-vf", args)
        self.assertIn(f"fps={SAMPLE_FPS}", args[args.index("-vf") + 1])
        self.assertIn(f"scale={SAMPLE_WIDTH}:{SAMPLE_HEIGHT}", args[args.index("-vf") + 1])
        self.assertEqual(args[args.index("-f") + 1], "rawvideo")
        self.assertEqual(args[-1], "pipe:1")

    def test_smart_auto_mode_defaults_to_standard_until_analysis_sets_target(self):
        analysis = analyze_raw_frames(
            solid_frames(96, 10),
            source_width=1920,
            source_height=1080,
            encoding_mode=MODE_H265_SMART_AUTO,
        )

        self.assertEqual(analysis.target_video_bitrate_kbps, 450)

    def test_production_detail_sample_args_use_larger_gray_frames(self):
        args = build_production_detail_sample_args(
            Path("ffmpeg.exe"), Path("input.mp4"), 1920, 1080, SampleSegment(0.0, 15.0)
        )

        self.assertIn("-vf", args)
        vf = args[args.index("-vf") + 1]
        self.assertIn(f"fps={PRODUCTION_SAMPLE_FPS}", vf)
        self.assertIn(f"scale={PRODUCTION_SAMPLE_WIDTH}:{PRODUCTION_SAMPLE_HEIGHT}", vf)
        self.assertEqual(args[args.index("-f") + 1], "rawvideo")
        self.assertEqual(args[-1], "pipe:1")

    def test_production_detail_static_frames_have_low_risk_scores(self):
        analysis = analyze_production_detail_raw_frames(production_solid_frames(96, 10))

        self.assertLess(analysis.peak_complexity_score, 10)
        self.assertLess(analysis.small_detail_score, 10)
        self.assertLess(analysis.peak_motion_score, 10)
        self.assertEqual(analysis.sampled_frames, 10)

    def test_production_detail_checkerboard_frames_have_high_small_detail_score(self):
        analysis = analyze_production_detail_raw_frames(production_checkerboard_frames(10))

        self.assertGreaterEqual(analysis.small_detail_score, 65)
        self.assertGreaterEqual(analysis.peak_complexity_score, 60)
        self.assertGreaterEqual(analysis.peak_motion_score, 30)

    def test_production_detail_segment_boundary_does_not_count_as_motion_or_scene_change(self):
        analysis = analyze_production_detail_raw_frames(
            production_solid_frames(0, 2) + production_solid_frames(255, 2),
            segment_frame_counts=(2, 2),
        )

        self.assertLess(analysis.peak_motion_score, 10)
        self.assertEqual(analysis.scene_change_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
