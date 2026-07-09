Implementation Summary
- Wired Auto Detail analysis into the batch worker flow in `src/ui_main.py`.
- Added the new Auto Detail imports for `build_best_detail_2pass_plan`, `choose_auto_detail_plan`, `analyze_production_detail`, and `is_h265_auto_detail_mode`.
- Routed H.265 Auto Detail jobs ahead of Smart Auto jobs in the worker loop so Smart Auto behavior stays unchanged.
- Added `_apply_auto_detail_decision()` to copy the selected plan, risk metadata, source metrics, detail metrics, and target encode fields onto `VideoJob`.
- Added `_analyze_job_auto_detail()` to run production detail analysis, select the encode plan, emit localized success logs, and fall back to the best-detail 2-pass plan with failure metadata when analysis fails.

Tests and Outputs
- Command: `python3 -m unittest tests.test_localization tests.test_content_analyzer tests.test_auto_detail -v`
  - Result: PASS
  - Output summary: `Ran 17 tests in 0.548s` and `OK`
- Command: `python3 -c 'import sys; sys.path.insert(0, "src"); import ui_main'`
  - Result: PASS
  - Output summary: no output, exit code 0

Files Changed
- `src/ui_main.py`
- `.superpowers/sdd/task-5-report.md`

self-review Findings
- The worker now routes Auto Detail before Smart Auto exactly as required by the task brief.
- Auto Detail success and fallback paths both populate the new `VideoJob` fields needed by downstream encoding and reporting.
- The change stays within the requested task scope and does not modify unrelated files.

Concerns
- No additional concerns at this slice. I did not add tests beyond the brief because this task intentionally defers direct UI worker coverage.

Review Fix Follow-up
- Fixed the stale Auto Detail job-state issue in `start_compression()` by resetting every Auto Detail field before a queued `VideoJob` is reused: `h265_encode_plan`, `auto_selected_profile`, `auto_risk_score`, `auto_risk_reasons`, `source_video_bitrate_kbps`, `source_fps`, `peak_complexity_score`, `small_detail_score`, `peak_motion_score`, `scene_change_rate`, `target_fps`, and `target_gop`.
- Fixed the Auto Detail analysis failure path in `_analyze_job_auto_detail()` so failed analyses now clear the untrusted detail metrics (`peak_complexity_score`, `small_detail_score`, `peak_motion_score`, `scene_change_rate`) while still populating the fallback best-detail 2-pass plan fields.

Mac Verification
- Command: `python3 -m unittest discover -s tests -v`
  - Result: PASS
  - Output summary: `Ran 51 tests in 0.548s` and `OK`

Files Updated for Review Fix
- `src/ui_main.py`
- `.superpowers/sdd/task-5-report.md`
- `.superpowers/sdd/task-5-fix-report.md`

Review Fix Concerns
- No additional concerns. The fix is scoped to the reviewer findings and the full requested unit test suite passed.
