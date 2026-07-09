import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import content_analyzer

from content_analyzer import (
    AnalysisCancelled,
    PRODUCTION_SAMPLE_FPS,
    PRODUCTION_SAMPLE_HEIGHT,
    PRODUCTION_SAMPLE_WIDTH,
    SampleSegment,
    SAMPLE_FPS,
    SAMPLE_HEIGHT,
    SAMPLE_WIDTH,
    _clustered_detail_score,
    _run_rawvideo_process,
    analyze_production_detail,
    analyze_production_detail_raw_frames,
    analyze_raw_frames,
    build_production_detail_sample_args,
    build_sample_args,
    percentile,
    production_sample_dimensions,
    production_sample_segments,
    rolling_means,
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


def production_solid_frames(
    value: int,
    count: int,
    width: int = PRODUCTION_SAMPLE_WIDTH,
    height: int = PRODUCTION_SAMPLE_HEIGHT,
) -> bytes:
    frame = bytes([value]) * (width * height)
    return frame * count


def production_checkerboard_frame(
    width: int = PRODUCTION_SAMPLE_WIDTH,
    height: int = PRODUCTION_SAMPLE_HEIGHT,
    phase: int = 0,
) -> bytes:
    pixels = []
    for y in range(height):
        for x in range(width):
            pixels.append(255 if ((x // 4 + y // 4 + phase) % 2) else 0)
    return bytes(pixels)


def production_checkerboard_frames(
    count: int,
    width: int = PRODUCTION_SAMPLE_WIDTH,
    height: int = PRODUCTION_SAMPLE_HEIGHT,
) -> bytes:
    frames = []
    for frame_index in range(count):
        frames.append(production_checkerboard_frame(width, height, phase=frame_index % 2))
    return b"".join(frames)


def replace_frame(raw: bytes, frame_index: int, replacement: bytes) -> bytes:
    frame_size = len(replacement)
    start = frame_index * frame_size
    return raw[:start] + replacement + raw[start + frame_size :]


def detail_tile_frame(width: int, height: int, tile_coordinates: set[tuple[int, int]]) -> bytes:
    pixels = bytearray(width * height)
    for tile_y, tile_x in tile_coordinates:
        y_start = tile_y * height // 8
        y_end = (tile_y + 1) * height // 8
        x_start = tile_x * width // 8
        x_end = (tile_x + 1) * width // 8
        for y in range(y_start, y_end):
            for x in range(x_start, x_end):
                pixels[y * width + x] = 255 if ((x + y) % 2) else 0
    return bytes(pixels)


def qr_cluster_frame(width: int, height: int) -> bytes:
    return detail_tile_frame(width, height, {(3, 3), (3, 4), (4, 3), (4, 4)})


def sparse_noise_frame(width: int, height: int, matching_edge_count: bool = True) -> bytes:
    del matching_edge_count
    return detail_tile_frame(width, height, {(0, 0), (0, 7), (7, 0), (7, 7)})


def fake_running_process() -> Mock:
    process = Mock()
    process.poll.return_value = None
    process.returncode = -15

    def terminate() -> None:
        process.poll.return_value = -15

    process.terminate.side_effect = terminate
    process.communicate.side_effect = [
        subprocess.TimeoutExpired(["ffmpeg"], 0.1),
        (b"", b""),
    ]
    return process


class ContentAnalyzerTests(unittest.TestCase):
    def test_pre_set_cancellation_beats_fast_nonzero_process(self):
        cancel_event = threading.Event()
        cancel_event.set()
        process = Mock(returncode=1)
        process.communicate.return_value = (b"", b"FFmpeg failed")

        with patch("content_analyzer.subprocess.Popen", return_value=process):
            with self.assertRaises(AnalysisCancelled):
                _run_rawvideo_process(["ffmpeg"], cancel_event)

        self.assertEqual(process.communicate.call_args_list, [call(timeout=5)])
        process.terminate.assert_called_once()

    def test_cancellation_after_fast_nonzero_process_completes_beats_analysis_error(self):
        cancel_event = threading.Event()
        process = Mock(returncode=1)

        def complete_process(**kwargs):
            cancel_event.set()
            return b"", b"FFmpeg failed"

        process.communicate.side_effect = complete_process
        with patch("content_analyzer.subprocess.Popen", return_value=process):
            with self.assertRaises(AnalysisCancelled):
                _run_rawvideo_process(["ffmpeg"], cancel_event)

        self.assertEqual(process.communicate.call_args_list[0], call(timeout=0.1))
        process.terminate.assert_called_once()

    def test_pre_set_cancellation_kills_after_terminate_timeout(self):
        cancel_event = threading.Event()
        cancel_event.set()
        process = Mock()
        process.communicate.side_effect = [
            subprocess.TimeoutExpired(["ffmpeg"], 5),
            (b"", b""),
        ]

        with patch("content_analyzer.subprocess.Popen", return_value=process):
            with self.assertRaises(AnalysisCancelled):
                _run_rawvideo_process(["ffmpeg"], cancel_event)

        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(
            process.communicate.call_args_list,
            [call(timeout=5), call()],
        )

    def test_production_analysis_cancel_terminates_process(self):
        cancel_event = threading.Event()
        cancel_event.set()

        with patch("content_analyzer.subprocess.Popen", return_value=fake_running_process()) as popen:
            with self.assertRaises(AnalysisCancelled):
                analyze_production_detail(
                    Path("ffmpeg"), Path("input.mp4"), 1920, 1080, 15.0, cancel_event
                )

        popen.return_value.terminate.assert_called_once()

    def test_rawvideo_process_times_out_after_sample_timeout(self):
        process = Mock()
        process.communicate.side_effect = [
            subprocess.TimeoutExpired(["ffmpeg"], 0.1),
            (b"", b""),
        ]

        with (
            patch("content_analyzer.subprocess.Popen", return_value=process),
            patch.object(
                content_analyzer,
                "time",
                Mock(monotonic=Mock(side_effect=[0.0, 121.0])),
                create=True,
            ),
        ):
            with self.assertRaises(subprocess.TimeoutExpired):
                _run_rawvideo_process(["ffmpeg"], cancel_event=None)

        process.terminate.assert_called_once()

    def test_percentile_uses_linear_interpolation(self):
        self.assertEqual(percentile([0.0, 10.0, 20.0, 30.0], 0.5), 15.0)

    def test_rolling_means_rejects_incomplete_windows(self):
        self.assertEqual(rolling_means([10.0, 20.0, 30.0], 4), [])

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

    def test_isolated_detail_frame_does_not_define_temporal_peak(self):
        raw = production_solid_frames(96, 8, width=320, height=180)
        raw = replace_frame(raw, 4, production_checkerboard_frame(320, 180))

        analysis = analyze_production_detail_raw_frames(raw, 320, 180)

        self.assertLess(analysis.peak_complexity_score, analysis.spatial_p95)

    def test_sustained_two_second_detail_raises_temporal_peak(self):
        raw = production_solid_frames(96, 4, width=320, height=180)
        raw += production_checkerboard_frames(4, width=320, height=180)

        analysis = analyze_production_detail_raw_frames(raw, 320, 180)

        self.assertGreaterEqual(analysis.peak_two_second_complexity, 60.0)

    def test_temporal_windows_do_not_cross_production_sample_boundaries(self):
        analysis = analyze_production_detail_raw_frames(
            production_solid_frames(96, 1) + production_checkerboard_frames(1),
            segment_frame_counts=(1, 1),
        )

        self.assertEqual(analysis.peak_one_second_complexity, 0.0)
        self.assertEqual(analysis.peak_two_second_complexity, 0.0)

    def test_local_qr_like_cluster_scores_above_sparse_distributed_noise(self):
        clustered = qr_cluster_frame(320, 180)
        sparse = sparse_noise_frame(320, 180, matching_edge_count=True)

        self.assertGreater(
            _clustered_detail_score(clustered, 320, 180),
            _clustered_detail_score(sparse, 320, 180),
        )

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
