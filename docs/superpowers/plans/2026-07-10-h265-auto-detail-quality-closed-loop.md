# H.265 Auto Detail Quality Closed Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make H.265 Production - Auto Detail (2-pass) orientation-aware, temporally stable, cancellable, and capable of one quality-driven Best-to-Maximum retry.

**Architecture:** Keep source decisioning in `content_analyzer.py` and `auto_detail.py`, add a focused `quality_check.py` module for SSIM/detail comparison, and let `Encoder` own safe retry/backup orchestration because it already owns two-pass process lifecycle and output validation. UI code supplies cancellation and analysis results; report/localization code exposes every decision without changing existing modes.

**Tech Stack:** Python 3.11+, standard library, Tkinter/ttk, FFmpeg/FFprobe with libx265 and SSIM, unittest, PyInstaller, PowerShell.

## Global Constraints

- Default UI language remains English.
- Standard, High Motion, Screen Safe, and every existing H.265 mode remain unchanged.
- Quality comparison and retry run only for `h265_production_auto_detail_2pass`.
- Output keeps the source stem, uses MP4, never overwrites the source, and preserves `_2`/`_3` collision handling.
- FFmpeg lookup continues to support PyInstaller `_internal`.
- Audio remains mandatory and output must remain AAC, 48 kHz, stereo.
- Auto Detail retries at most once and only promotes Best Detail to Maximum Detail.
- SSIM pass threshold is `0.94`; enforced detail-retention threshold is `80%` when source clustered detail is at least `20`.
- The required regression command is `python -m unittest discover -s tests -v` on Windows and `python3 -m unittest discover -s tests -v` on macOS.

---

### Task 1: Correct FFprobe Frame-Rate Fallback

**Files:**
- Modify: `src/ffmpeg_utils.py:129-155`
- Test: `tests/test_ffprobe_parse.py`

**Interfaces:**
- Produces: `parse_video_fps(video_stream: dict[str, Any]) -> float`
- Preserves: `parse_ffprobe_json(payload: dict[str, Any]) -> VideoInfo`

- [ ] **Step 1: Write failing FFprobe regression tests**

Add tests proving `0/0` falls back and a valid average remains preferred:

```python
def test_parse_ffprobe_json_falls_back_when_average_frame_rate_is_zero(self):
    payload = video_payload(avg_frame_rate="0/0", r_frame_rate="30/1")
    self.assertEqual(parse_ffprobe_json(payload).fps, 30.0)

def test_parse_ffprobe_json_prefers_positive_average_frame_rate(self):
    payload = video_payload(avg_frame_rate="30000/1001", r_frame_rate="30/1")
    self.assertAlmostEqual(parse_ffprobe_json(payload).fps, 30000 / 1001)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```text
python3 -m unittest tests.test_ffprobe_parse.FFprobeParseTests.test_parse_ffprobe_json_falls_back_when_average_frame_rate_is_zero -v
```

Expected: FAIL because current truthy `"0/0"` blocks `r_frame_rate`.

- [ ] **Step 3: Implement positive-value fallback**

Add and use:

```python
def parse_video_fps(video_stream: dict[str, Any]) -> float:
    average = parse_fraction(video_stream.get("avg_frame_rate"))
    if average > 0:
        return average
    return parse_fraction(video_stream.get("r_frame_rate"))
```

- [ ] **Step 4: Run focused and complete FFprobe tests**

Run:

```text
python3 -m unittest tests.test_ffprobe_parse -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```text
git add src/ffmpeg_utils.py tests/test_ffprobe_parse.py
git commit -m "Fix FFprobe frame rate fallback"
```

---

### Task 2: Add Orientation-Aware Geometry and Distributed Segments

**Files:**
- Modify: `src/content_analyzer.py`
- Test: `tests/test_content_analyzer.py`

**Interfaces:**
- Produces: `SampleSegment(start_sec: float, duration_sec: float)`
- Produces: `production_sample_dimensions(source_width: int, source_height: int) -> tuple[int, int]`
- Produces: `production_sample_segments(duration_sec: float) -> tuple[SampleSegment, ...]`
- Changes: `build_production_detail_sample_args(ffmpeg_path: Path, input_path: Path, source_width: int, source_height: int, segment: SampleSegment) -> list[str]`

- [ ] **Step 1: Write failing geometry tests**

```python
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
```

- [ ] **Step 2: Write failing segment tests**

```python
def test_short_production_sample_uses_full_duration(self):
    self.assertEqual(production_sample_segments(15.0), (SampleSegment(0.0, 15.0),))

def test_long_production_sample_uses_start_middle_and_end(self):
    self.assertEqual(
        production_sample_segments(60.0),
        (SampleSegment(0.0, 10.0), SampleSegment(25.0, 10.0), SampleSegment(50.0, 10.0)),
    )
```

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```text
python3 -m unittest tests.test_content_analyzer.ContentAnalyzerTests.test_production_sample_dimensions_preserve_company_screen_orientations tests.test_content_analyzer.ContentAnalyzerTests.test_long_production_sample_uses_start_middle_and_end -v
```

Expected: ERROR because the new interfaces do not exist.

- [ ] **Step 4: Implement geometry and segments**

Use positive even dimensions:

```python
def _positive_even(value: float) -> int:
    rounded = max(2, int(round(value)))
    return rounded if rounded % 2 == 0 else rounded + 1

def production_sample_dimensions(source_width: int, source_height: int) -> tuple[int, int]:
    if source_width <= 0 or source_height <= 0:
        return 320, 180
    if source_width >= source_height:
        return 320, _positive_even(320 * source_height / source_width)
    return _positive_even(320 * source_width / source_height), 320
```

For long videos return start, centered midpoint, and end ten-second segments.
Build FFmpeg args with `-ss` before `-i`, `-t` after input, Lanczos scaling,
gray output, and no padding.

- [ ] **Step 5: Run content-analyzer tests**

```text
python3 -m unittest tests.test_content_analyzer -v
```

Expected: PASS after adapting existing argument tests to the new signature.

- [ ] **Step 6: Commit**

```text
git add src/content_analyzer.py tests/test_content_analyzer.py
git commit -m "Add orientation aware detail sampling"
```

---

### Task 3: Implement Temporal Windows, Percentiles, and Tile Clustering

**Files:**
- Modify: `src/content_analyzer.py`
- Modify: `src/models.py` only if shared metric typing is needed
- Test: `tests/test_content_analyzer.py`
- Test: `tests/test_auto_detail.py`

**Interfaces:**
- Produces: `percentile(values: list[float], percentile_value: float) -> float`
- Produces: `rolling_means(values: list[float], window_size: int) -> list[float]`
- Produces: `_clustered_detail_score(frame: bytes, width: int, height: int) -> float`
- Changes: `analyze_production_detail_raw_frames(raw_video: bytes, width: int, height: int) -> ProductionDetailAnalysis`
- Extends: `ProductionDetailAnalysis` with window and percentile audit values, all defaulting to `0.0` for backward-compatible construction.

- [ ] **Step 1: Write percentile and temporal-window tests**

```python
def test_percentile_uses_linear_interpolation(self):
    self.assertEqual(percentile([0.0, 10.0, 20.0, 30.0], 0.5), 15.0)

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
```

- [ ] **Step 2: Write tile-cluster tests**

```python
def test_local_qr_like_cluster_scores_above_sparse_distributed_noise(self):
    clustered = qr_cluster_frame(320, 180)
    sparse = sparse_noise_frame(320, 180, matching_edge_count=True)
    self.assertGreater(
        clustered_detail_score(clustered, 320, 180),
        clustered_detail_score(sparse, 320, 180),
    )
```

- [ ] **Step 3: Run tests and verify RED**

Run the new named tests. Expected: ERROR for missing helpers and fields.

- [ ] **Step 4: Implement deterministic percentile and rolling means**

```python
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
    return [sum(values[i:i + window_size]) / window_size for i in range(len(values) - window_size + 1)]
```

- [ ] **Step 5: Implement `8 x 8` tile clustering**

For each tile, calculate horizontal/vertical luma edge-hit ratio at threshold
40. Dense tiles require at least 12 percent hits. Use a four-neighbor flood
fill to find the largest dense cluster. Return:

```python
min(100.0, dense_tile_percent * 0.6 + largest_cluster_percent * 0.4)
```

Scale both percentages onto 0-100 before weighting.

- [ ] **Step 6: Replace single-frame maxima with specified aggregates**

Set:

```text
peak_one_second_complexity = max(rolling_means(spatial_values, 2))
peak_two_second_complexity = max(rolling_means(spatial_values, 4))
peak_complexity_score = max(peak_one_second_complexity, peak_two_second_complexity)
small_detail_score = percentile(clustered_detail_values, 0.95)
peak_motion_score = percentile(motion_values, 0.95)
```

Preserve the current risk scorer inputs and add new audit fields without
changing the 65-point selection threshold.

- [ ] **Step 7: Run analyzer and decision tests**

```text
python3 -m unittest tests.test_content_analyzer tests.test_auto_detail -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```text
git add src/content_analyzer.py tests/test_content_analyzer.py tests/test_auto_detail.py
git commit -m "Stabilize Auto Detail risk analysis"
```

---

### Task 4: Make Production Analysis Promptly Cancellable

**Files:**
- Modify: `src/content_analyzer.py`
- Modify: `src/ui_main.py`
- Test: `tests/test_content_analyzer.py`
- Test: `tests/test_ui_main.py`

**Interfaces:**
- Produces: `AnalysisCancelled(ContentAnalysisError)`
- Produces: `_run_rawvideo_process(args: list[str], cancel_event: threading.Event | None) -> bytes`
- Changes: `analyze_production_detail(ffmpeg_path: Path, input_path: Path, source_width: int, source_height: int, duration_sec: float, cancel_event: threading.Event | None = None) -> ProductionDetailAnalysis`

- [ ] **Step 1: Write failing cancellation tests**

Use a fake `Popen` whose `poll()` remains `None` until `terminate()`:

```python
def test_production_analysis_cancel_terminates_process(self):
    cancel_event = threading.Event()
    cancel_event.set()
    with patch("content_analyzer.subprocess.Popen", return_value=fake_running_process()) as popen:
        with self.assertRaises(AnalysisCancelled):
            analyze_production_detail(Path("ffmpeg"), Path("input.mp4"), 1920, 1080, 15.0, cancel_event)
    popen.return_value.terminate.assert_called_once()
```

Add a UI worker-level test proving `encoder.encode` is not called after an
analysis cancellation.

- [ ] **Step 2: Run tests and verify RED**

Expected: current blocking `subprocess.run` cannot satisfy cancellation.

- [ ] **Step 3: Implement cancellable process execution**

Start FFmpeg with binary stdout/stderr pipes. Poll at a short interval. On
cancellation terminate, wait up to five seconds, then kill. Raise
`AnalysisCancelled`. On normal completion collect output and apply existing
error handling.

- [ ] **Step 4: Pass cancellation through UI**

Call production analysis with `self.cancel_event`, catch
`AnalysisCancelled` separately, mark the job cancelled, and check the event
again before `Encoder.encode`. Do not run the Best fallback for cancellation.

- [ ] **Step 5: Run focused and full UI tests**

```text
python3 -m unittest tests.test_content_analyzer tests.test_ui_main -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```text
git add src/content_analyzer.py src/ui_main.py tests/test_content_analyzer.py tests/test_ui_main.py
git commit -m "Make Auto Detail analysis cancellable"
```

---

### Task 5: Add SSIM and Detail-Retention Quality Checker

**Files:**
- Create: `src/quality_check.py`
- Create: `tests/test_quality_check.py`
- Modify: `src/settings.py`

**Interfaces:**
- Produces: `QualityCheckResult`
- Produces: `parse_ssim_score(stderr: str) -> float`
- Produces: `evaluate_quality(ssim_score: float, source_detail: float, output_detail: float) -> QualityCheckResult`
- Produces: `run_quality_check(ffmpeg_path: Path, source_path: Path, output_path: Path, source_info: VideoInfo, source_detail: float, cancel_event: threading.Event | None = None) -> QualityCheckResult`

- [ ] **Step 1: Write failing pure quality-decision tests**

```python
def test_quality_passes_at_exact_thresholds(self):
    result = evaluate_quality(0.94, source_detail=40.0, output_detail=32.0)
    self.assertTrue(result.passed)
    self.assertEqual(result.detail_retention_percent, 80.0)

def test_low_detail_source_does_not_enforce_retention(self):
    result = evaluate_quality(0.95, source_detail=10.0, output_detail=1.0)
    self.assertTrue(result.passed)

def test_quality_fails_below_ssim_threshold(self):
    self.assertFalse(evaluate_quality(0.939, 40.0, 40.0).passed)
```

- [ ] **Step 2: Write failing SSIM parsing and argument tests**

```python
def test_parse_ssim_score_reads_finite_all_value(self):
    self.assertEqual(parse_ssim_score("SSIM Y:0.95 U:0.96 V:0.97 All:0.955 (13.4)"), 0.955)

def test_ssim_args_normalize_both_inputs_to_two_fps(self):
    args = build_ssim_args(
        Path("ffmpeg.exe"),
        Path("source.mp4"),
        Path("output.mp4"),
        width=320,
        height=180,
        segment=SampleSegment(0.0, 10.0),
    )
    graph = args[args.index("-lavfi") + 1]
    self.assertEqual(graph.count("fps=2"), 2)
    self.assertIn("ssim", graph)
```

- [ ] **Step 3: Run tests and verify RED**

Expected: import error because `quality_check.py` does not exist.

- [ ] **Step 4: Implement constants and result model**

Add settings constants:

```python
QUALITY_SSIM_THRESHOLD = 0.94
QUALITY_DETAIL_SOURCE_MIN = 20.0
QUALITY_DETAIL_RETENTION_THRESHOLD = 80.0
QUALITY_STATUS_NOT_RUN = "not_run"
QUALITY_STATUS_PASSED = "passed"
QUALITY_STATUS_WARNING = "quality_warning"
QUALITY_STATUS_CHECK_FAILED = "quality_check_failed"
QUALITY_STATUS_RETRY_FAILED = "quality_retry_failed"
```

Use a frozen dataclass with `passed`, `status`, `ssim_score`,
`detail_retention_percent`, `reason`, and `output_detail_score`.

- [ ] **Step 5: Implement SSIM execution and detail comparison**

Build one SSIM command per source segment, normalize both inputs to 2 fps,
orientation-aware dimensions, gray format, and reset PTS. Average finite
segment `All` values. Analyze output detail with the same production analyzer.
Raise `QualityCheckError` on invalid SSIM and `AnalysisCancelled` on cancel.

- [ ] **Step 6: Run quality tests**

```text
python3 -m unittest tests.test_quality_check -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```text
git add src/quality_check.py src/settings.py tests/test_quality_check.py
git commit -m "Add Auto Detail output quality checks"
```

---

### Task 6: Add Quality Audit State, CSV Columns, and Localization

**Files:**
- Modify: `src/models.py`
- Modify: `src/report.py`
- Modify: `src/localization.py`
- Test: `tests/test_report.py`
- Test: `tests/test_localization.py`

**Interfaces:**
- Extends `VideoJob` with: `quality_check_status`, `ssim_score`, `detail_retention_percent`, `quality_retry_count`, `quality_retry_reason`, `final_selected_profile`
- Extends CSV with the same stable fields.

- [ ] **Step 1: Write failing model/report tests**

Create Auto Detail results for passed, warning, and check-failed outcomes. Assert
that zero retry count is recorded as `0`, optional scores remain blank before a
check, and initial/final profiles are distinct.

- [ ] **Step 2: Write failing localization tests**

Require all supported languages to contain messages for quality passed,
quality retry started, retry retained Maximum, retry restored Best, quality
warning, and quality check failed.

- [ ] **Step 3: Run tests and verify RED**

```text
python3 -m unittest tests.test_report tests.test_localization -v
```

Expected: missing fields and message keys.

- [ ] **Step 4: Implement job defaults and report formatting**

Defaults:

```python
quality_check_status: str = QUALITY_STATUS_NOT_RUN
ssim_score: float | None = None
detail_retention_percent: float | None = None
quality_retry_count: int = 0
quality_retry_reason: str = ""
final_selected_profile: str = ""
```

Append report columns after `target_gop` and before `created_at`. Preserve
actual zeroes, and leave unexecuted optional metrics blank.

- [ ] **Step 5: Add concise zh/en/id log messages**

Keep internal status/profile codes untranslated; translate only user-facing
logs.

- [ ] **Step 6: Reset new fields before every batch rerun**

Update `start_compression()` reset logic in `src/ui_main.py` and extend the
existing reset coverage.

- [ ] **Step 7: Run report/localization/UI tests**

```text
python3 -m unittest tests.test_report tests.test_localization tests.test_ui_main -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```text
git add src/models.py src/report.py src/localization.py src/ui_main.py tests/test_report.py tests/test_localization.py tests/test_ui_main.py
git commit -m "Record Auto Detail quality audit results"
```

---

### Task 7: Orchestrate One Safe Best-to-Maximum Retry

**Files:**
- Modify: `src/encoder.py`
- Modify: `src/auto_detail.py`
- Test: `tests/test_encoder_two_pass.py`
- Test: `tests/test_naming.py`

**Interfaces:**
- Produces: `build_quality_backup_path(output_path: Path) -> Path`
- Produces: `Encoder._encode_auto_detail_with_quality(job: VideoJob, overwrite: bool, cancel_event: threading.Event, progress_callback: ProgressCallback | None) -> CompressionResult`
- Reuses: `build_maximum_detail_2pass_plan(info: VideoInfo) -> H265EncodePlan`
- Reuses: `run_quality_check(ffmpeg_path: Path, source_path: Path, output_path: Path, source_info: VideoInfo, source_detail: float, cancel_event: threading.Event | None = None) -> QualityCheckResult`

- [ ] **Step 1: Write failing no-retry and one-retry tests**

Patch real quality-check boundaries, not process internals:

```python
def test_best_quality_failure_retries_maximum_once(self):
    job = auto_detail_job(profile=PROFILE_BEST_DETAIL_2PASS)
    failed = QualityCheckResult(False, QUALITY_STATUS_WARNING, 0.93, 75.0, "ssim_below_threshold", 30.0)
    passed = QualityCheckResult(True, QUALITY_STATUS_PASSED, 0.96, 90.0, "", 36.0)
    with patch.object(Encoder, "_encode_h265_two_pass", side_effect=successful_attempts(job, 2)) as encode:
        with patch("encoder.run_quality_check", side_effect=[failed, passed]):
            result = encoder().encode(job, True, threading.Event())
    self.assertEqual(result.status, "success")
    self.assertEqual(encode.call_count, 2)
    self.assertEqual(job.quality_retry_count, 1)
    self.assertEqual(job.final_selected_profile, PROFILE_MAXIMUM_DETAIL_2PASS)

def test_initial_maximum_quality_failure_never_retries(self):
    job = auto_detail_job(profile=PROFILE_MAXIMUM_DETAIL_2PASS)
    warning = QualityCheckResult(False, QUALITY_STATUS_WARNING, 0.93, 75.0, "ssim_below_threshold", 30.0)
    with patch.object(Encoder, "_encode_h265_two_pass", side_effect=successful_attempts(job, 1)) as encode:
        with patch("encoder.run_quality_check", return_value=warning):
            result = encoder().encode(job, True, threading.Event())
    self.assertEqual(result.status, "success")
    self.assertEqual(encode.call_count, 1)
    self.assertEqual(job.quality_check_status, QUALITY_STATUS_WARNING)
```

- [ ] **Step 2: Write failing file-safety tests**

```python
def test_retry_encode_failure_restores_best_output(self):
    with tempfile.TemporaryDirectory() as temp_dir:
        job = auto_detail_job(Path(temp_dir), profile=PROFILE_BEST_DETAIL_2PASS)
        job.output_path.write_bytes(b"best-output")
        first = successful_result(job)
        second = failed_result(job, "maximum failed")
        with patch.object(Encoder, "_encode_h265_two_pass", side_effect=[first, second]):
            with patch("encoder.run_quality_check", return_value=failed_quality_result()):
                result = encoder().encode(job, True, threading.Event())
        self.assertEqual(result.status, "success")
        self.assertEqual(job.output_path.read_bytes(), b"best-output")
        self.assertEqual(job.quality_check_status, QUALITY_STATUS_RETRY_FAILED)

def test_retry_cancellation_restores_best_output_and_marks_cancelled(self):
    with tempfile.TemporaryDirectory() as temp_dir:
        job = auto_detail_job(Path(temp_dir), profile=PROFILE_BEST_DETAIL_2PASS)
        job.output_path.write_bytes(b"best-output")
        first = successful_result(job)
        second = cancelled_result(job)
        with patch.object(Encoder, "_encode_h265_two_pass", side_effect=[first, second]):
            with patch("encoder.run_quality_check", return_value=failed_quality_result()):
                result = encoder().encode(job, True, threading.Event())
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(job.output_path.read_bytes(), b"best-output")
```

- [ ] **Step 3: Run focused tests and verify RED**

Expected: current encoder returns after the first successful two-pass encode.

- [ ] **Step 4: Implement Auto Detail-specific dispatch**

In `Encoder.encode`, route only Auto Detail to
`_encode_auto_detail_with_quality`; keep normal Best two-pass on the existing
path.

The orchestration must:

1. Encode and structurally validate the selected plan.
2. Run quality check.
3. Return immediately when passed.
4. Return warning without retry when the selected plan is Maximum.
5. For Best failure/check error, move the valid output to a unique backup.
6. Set the Maximum plan and encode once more.
7. Keep Maximum on structural success, regardless of quality threshold.
8. Restore Best when retry encoding/validation fails or retry is cancelled.
9. Always clean backup and retry artifacts without deleting the only valid file.

- [ ] **Step 5: Preserve initial decision and update final decision**

Do not overwrite `auto_selected_profile`. Set
`final_selected_profile`, `quality_retry_count`, `quality_retry_reason`,
quality scores, and final target bitrate/fps/GOP according to the retained
output.

- [ ] **Step 6: Run encoder, naming, report, and UI tests**

```text
python3 -m unittest tests.test_encoder_two_pass tests.test_naming tests.test_report tests.test_ui_main -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```text
git add src/encoder.py src/auto_detail.py tests/test_encoder_two_pass.py tests/test_naming.py
git commit -m "Retry low quality Auto Detail outputs safely"
```

---

### Task 8: Add Windows FFmpeg Preflight and Gated Smoke Test

**Files:**
- Modify: `build_windows.ps1`
- Create: `tests/test_real_ffmpeg_smoke.py`
- Modify: `docs/installation_user_guide_en.md`
- Modify: `docs/installation_user_guide_zh.md`

**Interfaces:**
- PowerShell build exits before dependency installation when binaries,
  `libx265`, or `ssim` are missing.
- Smoke tests skip unless Windows bundled executables exist.

- [ ] **Step 1: Add a static build-script test or command assertion test**

Create a Python test that reads `build_windows.ps1` and asserts it checks both
binary paths, `libx265`, and `ssim` before the PyInstaller invocation. Run it
and verify RED.

- [ ] **Step 2: Implement PowerShell preflight**

Before `pip install`, check both files and run:

```powershell
$encoders = & $ffmpegPath -hide_banner -encoders 2>&1 | Out-String
if ($encoders -notmatch "libx265") { throw "Bundled FFmpeg does not include libx265." }
$filters = & $ffmpegPath -hide_banner -filters 2>&1 | Out-String
if ($filters -notmatch "ssim") { throw "Bundled FFmpeg does not include the ssim filter." }
```

Check `$LASTEXITCODE` after each command.

- [ ] **Step 3: Add gated real-FFmpeg smoke test**

Define module constants first, then decorate the test class:

```python
BIN_DIR = Path(__file__).resolve().parents[1] / "tools" / "ffmpeg" / "bin"
FFMPEG = BIN_DIR / "ffmpeg.exe"
FFPROBE = BIN_DIR / "ffprobe.exe"
HAS_WINDOWS_FFMPEG = os.name == "nt" and FFMPEG.exists() and FFPROBE.exists()

@unittest.skipUnless(HAS_WINDOWS_FFMPEG, "bundled Windows FFmpeg is unavailable")
class RealFFmpegSmokeTests(unittest.TestCase):
    def test_real_two_pass_and_quality_check(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp4"
            subprocess.run(
                [
                    str(FFMPEG), "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30",
                    "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=48000",
                    "-t", "2", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(source),
                ],
                check=True,
                capture_output=True,
            )
            source_info = probe_video(FFPROBE, source)
            jobs = [
                VideoJob(
                    input_path=source,
                    output_path=root / "best.mp4",
                    info=source_info,
                    encoding_mode=MODE_H265_PRODUCTION_BEST_DETAIL_2PASS,
                ),
                VideoJob(
                    input_path=source,
                    output_path=root / "maximum.mp4",
                    info=source_info,
                    encoding_mode=MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS,
                    h265_encode_plan=build_maximum_detail_2pass_plan(source_info),
                    auto_selected_profile=PROFILE_MAXIMUM_DETAIL_2PASS,
                    small_detail_score=0.0,
                ),
            ]
            for job in jobs:
                result = Encoder(FFmpegPaths(FFMPEG, FFPROBE)).encode(
                    job, overwrite=True, cancel_event=threading.Event()
                )
                self.assertEqual(result.status, "success")
                quality = run_quality_check(
                    FFMPEG, source, job.output_path, source_info, source_detail=0.0
                )
                self.assertTrue(math.isfinite(quality.ssim_score))
            self.assertFalse(any(root.glob("*x265_2pass*")))
```

Generate a two-second test source with `testsrc2` and `sine`, run real Best and
Maximum two-pass encoding through `Encoder`, call `run_quality_check`, and
assert finite SSIM, expected output properties, and no passlog/backup files.

- [ ] **Step 4: Run the full suite on macOS**

```text
python3 -m unittest discover -s tests -v
```

Expected: all unit tests pass; real Windows smoke test is explicitly skipped.

- [ ] **Step 5: Update both installation guides**

Document automatic build preflight and the expected Windows smoke-test result.

- [ ] **Step 6: Commit**

```text
git add build_windows.ps1 tests/test_real_ffmpeg_smoke.py docs/installation_user_guide_en.md docs/installation_user_guide_zh.md
git commit -m "Verify bundled FFmpeg production capabilities"
```

---

### Task 9: Update Product Documentation and Run Final Regression

**Files:**
- Modify: `README.md`
- Modify: `docs/design.md`
- Modify: `docs/codex_handover.md`
- Test: all tests

**Interfaces:**
- Documents the exact source-analysis, quality thresholds, retry ceiling,
  warning semantics, report fields, and rollback path.

- [ ] **Step 1: Update user-facing mode guidance**

Explain that Auto Detail now checks the output and may retry once. State that a
quality warning means the structurally valid Maximum output was kept for human
review; it does not mean compression failed.

- [ ] **Step 2: Update technical design and handover**

Record orientation-aware dimensions, three-segment sampling for long sources,
temporal/window metrics, SSIM `0.94`, detail retention `80%`, source detail
minimum `20`, backup/restore behavior, Windows preflight, and new CSV fields.

- [ ] **Step 3: Run complete verification**

```text
python3 -m unittest discover -s tests -v
git diff --check
```

Expected: all tests pass, Windows-only smoke test skips on macOS, and no
whitespace errors.

- [ ] **Step 4: Inspect compatibility-sensitive tests explicitly**

Confirm passing coverage for:

```text
default English
Standard and High Motion arguments
source-stem output naming and source overwrite prevention
PyInstaller _internal FFmpeg lookup
mandatory audio
all existing H.265 modes
```

- [ ] **Step 5: Commit documentation**

```text
git add README.md docs/design.md docs/codex_handover.md
git commit -m "Document Auto Detail quality closed loop"
```

- [ ] **Step 6: Request final code review**

Review the complete range from the design commit through HEAD. Fix every
Critical or Important issue, rerun the full suite, and only then prepare the
branch for GitHub.
