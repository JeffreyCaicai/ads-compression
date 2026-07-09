# H.265 Production Auto Detail (2-pass) Design

## Objective

Add a new batch-friendly production mode:

```text
H.265 Production - Auto Detail (2-pass)
```

The goal is to let operators process 30 or more ad videos at once without manually inspecting every file and choosing a quality mode. The app should analyze each source video, decide whether normal production two-pass settings are enough, and automatically switch high-risk material to a stronger maximum-detail two-pass profile.

This mode should reduce human error while preserving the existing modes and the current safe rollback path.

## Current Problem

The current H.265 production modes work at the whole-file level:

- `H.265 Production - Best Detail` uses fixed Complex target bitrates.
- `H.265 Production - Best Detail (2-pass)` improves bitrate allocation at the same target bitrate.
- `H.265 Smart Auto - Analyze Content` estimates whole-file complexity and chooses Simple, Standard, or Complex target bitrate.

The issue is that some official ad videos have high-risk features that are not well represented by a whole-file average:

- QR codes.
- Small text.
- Logos.
- Fine product or vehicle edges.
- Hair, skin, clothing texture, and character detail.
- Large gradients.
- Fast motion or frequent scene changes.
- High source bitrate, such as 10 Mbps or more.
- High-pixel screen formats such as 1920x1440 or 1080x2560.

For example, a 1920x1440 Disney Cruise Adventure source was already H.265/hvc1 at about 11.8 Mbps video bitrate, 30 fps, and one keyframe per second. Compressing it to the current high-pixel Complex target of 2200k at 25 fps is too aggressive for QR and small-text detail, even with two-pass.

## Non-Goals

This first Auto Detail version will not:

- Replace existing Standard, High Motion, Screen Safe, H.265 Production, H.265 Smart Auto, or H.265 Small File modes.
- Perform real OCR or QR decoding.
- Split the output into multiple files and concatenate them.
- Apply different bitrates to different encoded segments through x265 zones.
- Guarantee parity with Aliyun cloud transcoding.
- Require operators to manually pick per-file settings after analysis.

True per-scene or per-GOP bitrate zoning can be considered after the app has collected enough real-world analysis data.

## User Experience

Add one new selectable quality mode:

```text
H.265 Production - Auto Detail (2-pass)
```

Default UI language remains English. Suggested labels:

```text
en_US: H.265 Production - Auto Detail (2-pass)
zh_CN: H.265 Production - 自动细节优化 (2-pass)
id_ID: H.265 Production - Auto Detail (2-pass)
```

Recommended usage:

- Batch official delivery for H.265-capable screens.
- Mixed folders where some videos are simple and some are high-risk.
- Operations teams that do not want to manually inspect every source file.

The app should log the decision for each file:

```text
filename.mp4: analyzing production detail risk...
filename.mp4: selected maximum_detail_2pass, risk score 82, target 3200k, fps 30, reasons: high_pixel_screen; source_bitrate_11759k; fps_30; small_detail_risk; peak_complexity_high.
```

If analysis fails:

```text
filename.mp4: auto detail analysis failed: <error>. Falling back to best_detail_2pass at 2200k.
```

## Internal Profiles

Auto Detail should choose between two internal profiles.

### Profile A: `best_detail_2pass`

This is the existing `H.265 Production - Best Detail (2-pass)` behavior.

Use it for ordinary official ads where the current Complex bitrate is sufficient.

Parameters:

```text
codec: libx265
preset: slow
profile: main
pix_fmt: yuv420p
fps: 25
GOP: 250
min-keyint: 25
scenecut: 40
target bitrate:
  1920x1080 landscape: 1200k
  1080x1920 portrait: 1800k
  high-pixel screens: 2200k
maxrate: target * 1.5
bufsize: target * 3
audio: AAC 96k, 48 kHz, stereo
container: MP4 with hvc1 tag
passes: 2
```

### Profile B: `maximum_detail_2pass`

Use it only for high-risk material. It trades larger file size and longer encode time for better detail retention.

Parameters:

```text
codec: libx265
preset: slow
profile: main
pix_fmt: yuv420p
fps:
  if source fps >= 29: 30
  otherwise: 25
GOP:
  if target fps is 30: 60
  otherwise: 50
min-keyint:
  if target fps is 30: 30
  otherwise: 25
scenecut: 40
target bitrate:
  1920x1080 landscape: 2000k
  1080x1920 portrait: 2600k
  high-pixel screens: 3200k
maxrate: target * 2
bufsize: target * 4
x265 params:
  rc-lookahead=50
  aq-mode=3
  aq-strength=1.0
  psy-rd=2.0
  psy-rdoq=1.0
audio: AAC 96k, 48 kHz, stereo
container: MP4 with hvc1 tag
passes: 2
```

For the Disney Cruise Adventure example, high-pixel screen plus 30 fps plus source video bitrate around 11.8 Mbps should select `maximum_detail_2pass` with a 3200k target, 6400k maxrate, 12800k bufsize, 30 fps, and GOP 60.

## Analysis Inputs

Auto Detail needs more evidence than the current Smart Auto whole-file score.

### Probe Metadata

Extend probing data where available:

```text
source_video_bitrate_kbps
source_fps
source_video_codec
source_pixel_count
duration_sec
width
height
has_audio
```

If stream video bitrate is missing, estimate it from file size minus audio size when available, or from format bitrate as a fallback. Missing bitrate should not fail the job.

Audio remains mandatory. If the source has no audio, behavior stays the same as current production modes: fail the job with the existing no-audio message.

### Detail Sampling

The existing Smart Auto analyzer samples grayscale video at 160x90 and 2 fps. Auto Detail should add a production-detail analyzer path that samples more fine detail:

```text
sample size: 320x180 grayscale
sample fps: 2 fps
max sample duration: 30 seconds
```

This is still fast enough for batch use, but preserves more information about QR codes, logo edges, and small text than 160x90.

The analyzer should compute per-frame and per-window values:

```text
spatial complexity per frame
motion complexity between frames
small-detail edge density per frame
scene-change candidates
1-second peak complexity windows
2-second peak complexity windows
p90 and p95 scores
```

The analysis is still approximate. It does not need to understand that a region is a QR code. It only needs to detect dense, sharp, small-scale edges that are likely to become visibly damaged after aggressive compression.

## Risk Scoring

Auto Detail should compute a transparent risk score from 0 to 100 and record reasons.

Suggested scoring:

```text
screen pixel risk:
  high-pixel screen: +15
  full HD portrait: +8

source bitrate risk:
  source bitrate >= 10000k: +25
  source bitrate >= 8000k: +18
  source bitrate / best-detail target >= 5: +25
  source bitrate / best-detail target >= 4: +18
  use the highest applicable source bitrate value, capped at +25

fps risk:
  source fps >= 29 and best-detail would output 25 fps: +15

peak complexity risk:
  peak 1-second complexity >= 75: +25
  peak 1-second complexity >= 60: +15

small detail risk:
  small_detail_score >= 65: +25
  small_detail_score >= 45: +15

motion and scene-change risk:
  peak_motion_score >= 45: +15
  peak_motion_score >= 30: +8
  scene_change_rate >= 0.4 per second: +10
```

Clamp the final score to 100.

`small_detail_score` should be a 0 to 100 score derived from dense local edges in the 320x180 grayscale sample. It should favor clustered high-frequency edges, because QR codes, small text, and logos are more fragile than ordinary large object edges. The exact formula can be implementation-local, but it must be deterministic and covered by unit tests.

Decision rule:

```text
score >= 65:
  selected_profile = maximum_detail_2pass
otherwise:
  selected_profile = best_detail_2pass
```

The score should be deterministic. The same source file and same FFmpeg build should produce the same decision.

## Encoding Flow

For each job in Auto Detail mode:

1. Probe the video with ffprobe.
2. Enforce mandatory audio using the existing rule.
3. Run production detail analysis.
4. Compute risk score and reasons.
5. Select `best_detail_2pass` or `maximum_detail_2pass`.
6. Build two-pass FFmpeg arguments from the selected internal profile.
7. Run pass 1 and pass 2 using the existing two-pass process runner.
8. Validate the output with the existing validation path.
9. Clean passlog files in all success, failure, and cancellation paths.
10. Write report fields that explain the decision.

If analysis fails because FFmpeg cannot decode sample frames, times out, or returns invalid data:

```text
selected_profile = best_detail_2pass
risk_score = 0
risk_reasons = analysis_failed:<short error>
```

The job should continue unless normal probing, audio validation, or encoding fails.

## Data Model and Report Fields

Extend the job/report model with fields that make decisions auditable:

```text
auto_selected_profile
auto_risk_score
auto_risk_reasons
source_video_bitrate_kbps
source_fps
source_video_codec
peak_complexity_score
small_detail_score
peak_motion_score
scene_change_rate
target_video_bitrate_kbps
target_fps
target_gop
```

For current non-Auto modes, these fields can be blank except for fields that already exist, such as `target_video_bitrate_kbps` and `target_fps`.

CSV examples:

```text
encoding_mode=h265_production_auto_detail_2pass
auto_selected_profile=maximum_detail_2pass
auto_risk_score=82
auto_risk_reasons=high_pixel_screen;source_bitrate_11759k;fps_30;small_detail_risk;peak_complexity_high
source_video_bitrate_kbps=11759
source_fps=30
target_video_bitrate_kbps=3200
target_fps=30
target_gop=60
```

## Settings and Naming

Add a new mode constant:

```python
MODE_H265_PRODUCTION_AUTO_DETAIL_2PASS = "h265_production_auto_detail_2pass"
```

Add it to supported H.265 modes and UI supported modes near the other production modes.

Suggested output suffix:

```text
_h265_production_auto_detail_2pass_aac96
```

Output filename behavior must stay unchanged:

- Preserve the source stem.
- Output MP4.
- Never overwrite the source file.
- Increment with `_2`, `_3`, etc. when needed.

## Compatibility Constraints

Preserve current behavior:

- Default English UI.
- Existing Standard and High Motion modes.
- Existing Screen Safe mode.
- Existing H.265 Production Best Detail mode.
- Existing H.265 Production Best Detail (2-pass) mode.
- Existing H.265 Smart Auto and Small File modes.
- Output filename preserves source stem.
- FFmpeg lookup supports PyInstaller `_internal`.
- Audio is mandatory.
- Windows packaging continues to include `tools`.

The new mode requires FFmpeg with `libx265`, same as existing H.265 modes.

## Performance Expectations

Auto Detail adds an analysis pass before two-pass encoding. For a batch of 30 videos, the analysis should be small compared with full encoding time.

Expected overhead:

```text
analysis: usually seconds per file
best_detail_2pass encode: close to current two-pass time
maximum_detail_2pass encode: may be slower and larger than best_detail_2pass
```

The mode intentionally increases size only for high-risk files. It should not force all videos to 3200k or 30 fps.

## Testing Plan

Add unit tests for:

- New mode appears in supported encoding modes.
- Localization labels exist for English, Chinese, and Indonesian.
- Risk scoring chooses `best_detail_2pass` for simple low-bitrate content.
- Risk scoring chooses `maximum_detail_2pass` for high-pixel, high-bitrate, 30 fps, high-detail content.
- Missing source bitrate does not fail analysis.
- Analysis failure falls back to `best_detail_2pass`.
- Maximum Detail FFmpeg args use 30 fps, GOP 60, higher target bitrate, 2x maxrate, 4x bufsize, and detail-preserving x265 params.
- Best Detail path still uses existing two-pass args.
- Report writes auto decision fields.
- Existing Standard, High Motion, output naming, PyInstaller FFmpeg lookup, and audio-mandatory tests continue passing.

Required verification:

```text
python -m unittest discover -s tests -v
```

On this Mac development environment, use:

```text
python3 -m unittest discover -s tests -v
```

## Rollout

This mode should be introduced as an additional option, not as the default.

Recommended internal guidance:

- Use `H.265 Production - Auto Detail (2-pass)` for mixed production batches.
- Use `H.265 Production - Best Detail (2-pass)` when the team wants predictable size and already knows the material is ordinary.
- Use `H.265 Smart Auto` when the priority is small files rather than maximum official-delivery quality.
- Keep H.264 modes for the old screens that do not support H.265.

## Rollback

If the mode causes issues:

1. Operators can immediately choose the existing `H.265 Production - Best Detail (2-pass)` mode.
2. Code rollback can revert the implementation commit for Auto Detail.
3. Existing modes and previous encoding behavior remain available.

The design must not require removing or changing the current two-pass implementation.
