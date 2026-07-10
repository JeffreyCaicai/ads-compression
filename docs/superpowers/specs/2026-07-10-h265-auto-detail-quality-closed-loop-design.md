# H.265 Auto Detail Quality Closed Loop Design

## Objective

Improve `H.265 Production - Auto Detail (2-pass)` so it can be trusted for
unattended mixed batches. The improved mode must make more stable source
decisions, verify the encoded result, and perform at most one quality-driven
retry without changing any existing encoding mode.

The feature addresses six confirmed gaps:

- FFprobe may expose `avg_frame_rate=0/0` while `r_frame_rate` is valid.
- A fixed landscape analysis canvas loses too much information for portrait
  and ultra-tall signage material.
- Single-frame maxima are too sensitive to noise and do not implement the
  documented one-second and two-second windows.
- Global edge counts do not distinguish a local QR/text/logo cluster from
  distributed random noise.
- Analysis cannot currently be cancelled promptly.
- The application validates output structure but does not compare encoded
  visual quality with the source.

## Compatibility Constraints

The following behavior must remain unchanged:

- Default UI language is English.
- Standard and High Motion remain available and unchanged.
- Screen Safe and all existing H.265 modes remain available and unchanged.
- The new quality closed loop applies only to
  `H.265 Production - Auto Detail (2-pass)`.
- Output filenames preserve the source stem, use MP4, never overwrite the
  source, and retain the existing `_2`, `_3` collision behavior.
- FFmpeg lookup continues to support PyInstaller `_internal`.
- Source and output audio remain mandatory and must satisfy the existing AAC,
  48 kHz, stereo validation.
- Windows packaging continues to include the complete `tools` directory.
- Auto Detail remains optional and Standard remains the default mode.

## Selected Approach

Use a hybrid quality workflow that relies only on the bundled FFmpeg build and
Python standard library:

1. Improve source analysis with orientation-aware sampling, temporal windows,
   percentiles, and tile-level detail clustering.
2. Keep the existing Best Detail and Maximum Detail two-pass profiles.
3. Compare source and encoded output with FFmpeg's built-in SSIM filter and a
   local detail-retention calculation.
4. Retry at most once, promoting Best Detail to Maximum Detail.

VMAF is not required because common Windows FFmpeg distributions do not always
include `libvmaf`. The build must include `libx265` and the built-in `ssim`
filter.

## Source Metadata Fix

FFprobe frame-rate parsing must prefer a positive parsed `avg_frame_rate`, then
fall back to a positive parsed `r_frame_rate`.

Examples:

```text
avg_frame_rate=30000/1001, r_frame_rate=30/1 -> 29.970
avg_frame_rate=0/0, r_frame_rate=30/1       -> 30.000
avg_frame_rate=N/A, r_frame_rate=25/1       -> 25.000
```

This avoids missing the Auto Detail 30 fps risk signal and prevents a valid
30 fps source from being incorrectly treated as unknown or zero fps.

## Orientation-Aware Sampling

Production-detail sampling must preserve comparable source detail for all
company screen orientations.

Use the source display aspect ratio to calculate the sample geometry:

```text
landscape or square:
  sample width = 320
  sample height = round(320 * source_height / source_width)

portrait:
  sample height = 320
  sample width = round(320 * source_width / source_height)
```

Round both dimensions to positive even integers. Do not pad the sample onto a
fixed landscape canvas. Use FFmpeg `scale=<width>:<height>:flags=lanczos` and
`format=gray`.

Expected examples:

```text
1920x1080 -> 320x180
1920x1440 -> 320x240
1080x1920 -> 180x320
1080x2560 -> 136x320
1920x360  -> 320x60
```

The raw-frame analyzer receives the calculated width and height rather than
depending on global fixed dimensions.

## Temporal Sampling

Continue sampling at 2 fps. For videos up to 30 seconds, analyze the full
duration. For videos longer than 30 seconds, sample three ten-second segments:

```text
segment 1: first 10 seconds
segment 2: 10 seconds centered around the midpoint
segment 3: final 10 seconds
```

Segments must remain inside the source duration and must not overlap after
normalization. FFmpeg may decode each segment separately; the analyzer combines
the raw frames in chronological order. This prevents an important ending QR or
legal-text section from being ignored.

## Temporal Metrics

At 2 fps:

- A one-second window contains two frames.
- A two-second window contains four frames.

Calculate per-frame spatial complexity, small-detail density, and motion. Then
calculate rolling means for the one-second and two-second windows. Record:

```text
peak one-second complexity
peak two-second complexity
p90 spatial complexity
p95 spatial complexity
p90 small-detail score
p95 small-detail score
p90 motion score
p95 motion score
scene-change rate
```

`peak_complexity_score` used by the existing risk scorer becomes the maximum of
the peak one-second and peak two-second rolling means. A single isolated frame
must not by itself create a high peak score.

Percentiles use deterministic linear interpolation over sorted values. Empty
collections produce zero.

## Tile-Level Detail Clustering

Divide every sampled frame into an `8 x 8` tile grid. For each tile, calculate
the ratio of local horizontal and vertical luma differences at or above 40.

Classify a tile as detail-dense when its edge ratio is at least 12 percent.
The frame's clustered-detail score combines:

```text
60%: percentage of detail-dense tiles
40%: largest four-connected cluster of detail-dense tiles
```

Scale the result to 0-100 and clamp it. The production `small_detail_score`
becomes the p95 clustered-detail score, not the global maximum edge count.

This favors sustained local QR, small-text, logo, hair, fabric, and product
detail while reducing sensitivity to one damaged frame or evenly distributed
random noise.

## Cancellable Analysis

Replace blocking production analysis execution with `subprocess.Popen` and a
polling loop that accepts the batch `cancel_event`.

Requirements:

- Clicking Cancel terminates the active analysis FFmpeg process.
- If termination does not complete within five seconds, kill the process.
- Cancelled analysis raises a dedicated cancellation result rather than
  falling back to Best Detail.
- The worker checks cancellation again before starting encoding.
- Existing Smart Auto behavior may continue using its current analyzer; this
  change is required for Production Auto Detail only.

## Encoding and Structural Validation

The existing Best Detail and Maximum Detail two-pass argument construction,
progress mapping, unique passlog names, passlog cleanup, `hvc1` tag, audio
encoding, and structural output validation remain unchanged.

Auto Detail first encodes with the profile selected by source analysis. After
the existing structural validation succeeds, it runs the quality comparison.

## Post-Encode Quality Comparison

### SSIM

Use FFmpeg's built-in `ssim` filter. Normalize source and output to 2 fps,
matching dimensions, grayscale, and reset timestamps before comparison. Compare
the same temporal segments used by source analysis.

Parse the aggregate `All` SSIM value from FFmpeg output. A missing, invalid, or
non-finite value is a quality-check error.

### Detail Retention

Run the same orientation-aware tile-detail analyzer on the encoded output. Use
the source and output p95 clustered-detail values:

```text
detail_retention_percent = output_p95 / source_p95 * 100
```

Only enforce detail retention when source p95 clustered detail is at least 20.
For lower-detail sources, report the ratio when meaningful but do not use it to
trigger a retry.

### Initial Thresholds

An output passes when:

```text
SSIM >= 0.94
and
source detail < 20 or detail retention >= 80 percent
```

Thresholds are constants, covered by boundary tests, and recorded in the
design. They can be tuned later using company corpus data without changing the
workflow.

## Retry and File Safety

Each video can be encoded at most twice.

```text
Best passes quality check:
  keep Best output

Best fails quality check:
  preserve the valid Best output as a sibling backup
  encode Maximum to the normal output path
  structurally validate and quality-check Maximum

Maximum passes:
  keep Maximum output and delete the Best backup

Maximum fails quality thresholds:
  keep Maximum output with quality_warning

Maximum encode or structural validation fails:
  restore the valid Best backup
  keep the job successful with quality_retry_failed warning

User cancels during retry:
  restore the valid Best backup
  mark the job cancelled and retain the usable output
```

Backup and retry paths must be unique, hidden-style sibling names derived from
the final output path, and cleaned after success, failure, or cancellation.
Never delete the only structurally valid output.

If the first selected profile is already Maximum, do not retry. A failed
quality threshold is recorded as a warning.

## Quality-Check Failure Handling

If SSIM or output-detail analysis fails for a technical reason:

- A Best result is treated as insufficient evidence and gets one Maximum
  retry.
- A Maximum result is retained with `quality_check_failed`.
- The batch continues.
- A quality-check failure does not convert a structurally valid output into a
  failed compression result.

Analysis failure before encoding keeps the existing fallback to Best Detail,
but source bitrate estimation must reuse the existing file-size/duration
fallback so the CSV audit remains complete.

## Data Model and Report

Add quality audit fields to `VideoJob` and the CSV report:

```text
quality_check_status
ssim_score
detail_retention_percent
quality_retry_count
quality_retry_reason
final_selected_profile
```

Stable status values:

```text
not_run
passed
quality_warning
quality_check_failed
quality_retry_failed
```

`auto_selected_profile` continues to represent the source-analysis decision.
`final_selected_profile` represents the profile whose output was ultimately
kept. Existing report columns remain in their current order; new columns are
added after the current Auto Detail audit columns and before `created_at`.

Log messages must explain the source decision, quality result, retry start,
retry outcome, and retained profile in Chinese, English, and Indonesian.

## Windows Build Preflight

Before installing/building with PyInstaller, `build_windows.ps1` must fail with
a clear message unless all of the following pass:

```text
tools/ffmpeg/bin/ffmpeg.exe exists
tools/ffmpeg/bin/ffprobe.exe exists
ffmpeg.exe -hide_banner -encoders contains libx265
ffmpeg.exe -hide_banner -filters contains ssim
```

The build retains the existing running-application check and `tools;tools`
PyInstaller data inclusion.

## Testing Strategy

### Unit Tests

- `avg_frame_rate=0/0` falls back to `r_frame_rate=30/1`.
- Valid positive average frame rate remains preferred.
- All company screen sizes produce the expected even sample dimensions.
- Production sample arguments use Lanczos and no fixed-canvas padding.
- One isolated noisy frame does not create a high temporal peak.
- Sustained one-second and two-second detail creates the expected peak.
- p90 and p95 calculations are deterministic at boundaries.
- A QR-like local cluster scores above distributed sparse noise.
- Quality thresholds pass at exactly 0.94 SSIM and 80 percent retention.
- Low-detail sources do not enforce retention.

### Workflow Tests

- Cancelling during analysis terminates the process and does not start encode.
- Best quality failure triggers exactly one Maximum retry.
- An initially selected Maximum profile never retries.
- Maximum quality warning keeps the Maximum output.
- Retry encode failure restores the Best output.
- Retry cancellation restores the Best output and marks cancellation.
- Quality-check technical failure follows the confirmed retry rules.

### Report and Localization Tests

- New CSV fields record pass, warning, check failure, and retry failure states.
- Initial and final profiles remain distinguishable.
- New log messages exist in English, Chinese, and Indonesian.

### Gated Real-FFmpeg Smoke Test

When bundled Windows FFmpeg and FFprobe exist, generate a short synthetic video
with AAC audio and execute real Best and Maximum two-pass encodes. Verify:

- HEVC/H.265 output with `hvc1` tag.
- Expected fps and audio properties.
- SSIM can run and produce a finite aggregate score.
- Passlog and retry temporary files are removed.

The normal cross-platform unit suite must skip this integration test when the
Windows executables are unavailable. The required command remains:

```text
python -m unittest discover -s tests -v
```

## Rollout

The feature remains on the optional Auto Detail mode. Before broad company
rollout, run a representative corpus containing landscape, portrait,
ultra-tall, QR, small legal text, cars, faces, gradients, static cards, and fast
cuts. Review:

```text
Best versus Maximum selection rate
quality retry rate
quality warning rate
SSIM distribution
detail-retention distribution
output size and encode time
screen playback results
```

Use those CSV results to tune thresholds. Existing modes provide immediate
operational rollback throughout the pilot.
