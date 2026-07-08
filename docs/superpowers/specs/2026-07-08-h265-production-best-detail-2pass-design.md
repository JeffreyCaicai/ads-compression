# H.265 Production Best Detail 2-Pass Design

## Goal

Add a new `H.265 Production - Best Detail (2-pass)` quality mode for official ad delivery on H.265-capable signage screens. The mode must improve bitrate allocation and visual detail retention versus the current one-pass production mode while preserving the current behavior and fallback path.

## Current Baseline

The current production mode is:

```text
H.265 Production - Best Detail
```

It uses the H.265 Complex target bitrate table:

```text
1920x1080: 1200k
1080x1920: 1800k
1920x1440 / 1080x2560: 2200k
```

It runs one FFmpeg process, writes the final MP4 directly, keeps AAC 96k audio, and validates HEVC/H.265 output at 25fps. This existing mode must remain unchanged.

## Decision

Create a separate mode instead of changing the current mode:

```text
Internal code: h265_production_best_detail_2pass
UI label: H.265 Production - Best Detail (2-pass)
```

This mode uses the same resolution-based Complex target bitrate as the existing production mode, but performs two FFmpeg passes:

```text
Pass 1: analyze video only, no final output, no audio encoding
Pass 2: encode final MP4 with video + AAC audio
```

The one-pass production mode stays available for faster normal delivery. The two-pass mode becomes the high-detail option for important ads, comparison against Aliyun output, and cases where production quality matters more than encoding speed.

## User Experience

The Quality Mode dropdown should include:

```text
H.265 Production - Best Detail
H.265 Production - Best Detail (2-pass)
H.265 Smart Auto - Analyze Content
```

Recommended usage:

```text
H.265 Production - Best Detail: official delivery, faster
H.265 Production - Best Detail (2-pass): official delivery, best bitrate allocation
H.265 Smart Auto - Analyze Content: smaller files / traffic-saving workflows
```

Progress behavior:

```text
Pass 1 analysis: 0% to 50%
Pass 2 final output: 50% to 100%
```

Log behavior:

```text
filename.mp4: starting H.265 2-pass analysis, target video bitrate 1800k.
filename.mp4: starting H.265 2-pass final encode.
```

If the user cancels during either pass, the active FFmpeg process is terminated and the job is marked cancelled using the existing cancellation behavior.

## Encoding Parameters

Both passes should use the same H.265 video settings unless FFmpeg requires pass-specific output options:

```text
Video codec: libx265
Preset: slow
Profile: main
Pixel format: yuv420p
Frame rate: 25fps
GOP: 250
Min keyint: 25
Scene cut: 40
MP4 tag on final pass: hvc1
Rate control: target bitrate
Maxrate: target * 1.5
Bufsize: target * 3
```

Pass 1:

```text
-pass 1
-passlogfile <unique temp passlog path>
-an
-f null
NUL on Windows, /dev/null elsewhere
```

Pass 2:

```text
-pass 2
-passlogfile <same unique temp passlog path>
-c:a aac -b:a 96k -ar 48000 -ac 2
-movflags +faststart
final output.mp4
```

The passlog path must be unique per job to avoid collisions when users process files with the same stem in different folders. It should live in the output folder or a temporary folder and be cleaned after success, failure, or cancellation.

## FFmpeg Argument Design

Keep the existing `build_ffmpeg_args()` one-pass behavior intact. Add separate helper functions for two-pass arguments so tests can validate each pass independently.

Suggested interfaces:

```python
def is_h265_two_pass_mode(mode: str) -> bool
def build_ffmpeg_passlog_path(output_path: Path, input_path: Path) -> Path
def build_ffmpeg_two_pass_args(
    ffmpeg_path: Path,
    input_path: Path,
    output_path: Path,
    pass_number: int,
    passlog_path: Path,
    overwrite: bool = True,
    encoding_mode: str = DEFAULT_ENCODING_MODE,
    source_info: VideoInfo | None = None,
    target_video_bitrate_kbps: int | None = None,
) -> list[str]
```

`is_h265_two_pass_mode()` returns `True` only for `MODE_H265_PRODUCTION_BEST_DETAIL_2PASS`.
`build_ffmpeg_passlog_path()` returns a unique path derived from both input and output identity.
`build_ffmpeg_two_pass_args()` returns the complete FFmpeg command list for the requested pass.
`pass_number` must accept only `1` or `2`; any other value should raise `ValueError` in tests and code.

## Encoder Flow

`Encoder.encode()` should route two-pass jobs through a new internal method:

```python
if is_h265_two_pass_mode(job.encoding_mode):
    return self._encode_h265_two_pass(job, overwrite, cancel_event, progress_callback)
```

The two-pass method should:

1. Validate `job.info` and audio exactly like the existing one-pass method.
2. Set `job.status = STATUS_PROCESSING`.
3. Create the output folder.
4. Build a unique passlog path.
5. Run pass 1 with progress mapped to 0.0-0.5.
6. Stop immediately if cancelled or pass 1 fails.
7. Run pass 2 with progress mapped to 0.5-1.0.
8. Probe and validate final output using existing validation logic.
9. Clean passlog files in a `finally` block.

The existing one-pass path should be factored just enough to avoid duplicating process execution and progress parsing. Do not refactor unrelated encoding behavior.

## Report Fields

The existing CSV fields should continue to work. For the new mode:

```text
encoding_mode = h265_production_best_detail_2pass
target_video_bitrate_kbps = 1200 / 1800 / 2200
target_fps = 25
content_complexity = production_best_detail
content_complexity_score = empty
```

Add a new field only if implementation cost is low and the report remains backward-compatible:

```text
encoding_passes = 1 or 2
```

If adding `encoding_passes` risks disrupting existing CSV consumers, skip it for the first implementation and rely on `encoding_mode`.

## Localization

Add labels for all supported languages:

```text
zh_CN: H.265 Production - 最佳细节 (2-pass)
en_US: H.265 Production - Best Detail (2-pass)
id_ID: H.265 Production - Best Detail (2-pass)
```

Default UI language remains English.

## Documentation

Update:

```text
README.md
docs/design.md
docs/installation_user_guide_zh.md
docs/installation_user_guide_en.md
```

Documentation should clearly say two-pass produces better bitrate allocation but takes longer, usually close to twice the encoding time.

## Validation

Automated tests must cover:

```text
target bitrate matches Complex production target
mode appears in supported encoding modes
two-pass pass 1 args use -pass 1, no audio, null output, passlog
two-pass pass 2 args use -pass 2, AAC audio, final MP4, same passlog
invalid pass number raises ValueError
localization returns the new UI label
CSV report records target bitrate and production_best_detail
existing one-pass production mode remains unchanged
```

Full verification command:

```bash
python -m unittest discover -s tests -v
```

On this Mac workspace, `python` may not exist, so local verification can use:

```bash
python3 -m unittest discover -s tests -v
```

Windows build machines should continue using:

```powershell
python -m unittest discover -s tests -v
```

## Rollback

The current stable production mode remains available. If the two-pass mode has problems, users can immediately choose:

```text
H.265 Production - Best Detail
```

For code rollback after release, revert the two-pass implementation commit:

```bash
git revert <two-pass-commit>
git push origin main
```

## Out Of Scope

This feature does not add:

```text
per-scene / per-GOP bitrate allocation
VMAF / SSIM scoring
preprocessing such as denoise or sharpen
custom bitrate controls in the GUI
replacement of existing H.264 or H.265 modes
```

Those remain later optimization steps.
