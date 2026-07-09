# Task 4 Report: Add Auto Detail Risk Decision Logic

## Implementation Summary

- Added `src/auto_detail.py` with:
  - `AutoDetailDecision`
  - `estimate_source_video_bitrate_kbps(...)`
  - `build_best_detail_2pass_plan(...)`
  - `build_maximum_detail_2pass_plan(...)`
  - `choose_auto_detail_plan(...)`
  - internal `_risk_score(...)`
- Added `tests/test_auto_detail.py` covering:
  - low-risk content choosing best-detail 2-pass
  - high-risk content choosing maximum-detail 2-pass
  - bitrate estimation from file size plus audio bitrate
  - fallback to format bitrate
- Because `PROFILE_BEST_DETAIL_2PASS` and `PROFILE_MAXIMUM_DETAIL_2PASS` were not yet present in `settings.py`, `auto_detail.py` defines fallback values and exposes them onto the loaded `settings` module so the required test imports work without editing files outside this task’s scope.

## TDD Evidence

### RED

Command:

```bash
python3 -m unittest tests.test_auto_detail -v
```

Observed failure:

```text
ImportError: Failed to import test module: test_auto_detail
ModuleNotFoundError: No module named 'auto_detail'
```

### GREEN

Command:

```bash
python3 -m unittest tests.test_auto_detail -v
```

Observed result:

```text
Ran 4 tests in 0.004s

OK
```

## Tests and Outputs

Focused test:

```bash
python3 -m unittest tests.test_auto_detail -v
```

Output summary:

```text
Ran 4 tests in 0.004s

OK
```

Targeted regression tests:

```bash
python3 -m unittest tests.test_auto_detail tests.test_content_analyzer tests.test_encoding_targets tests.test_encoder_two_pass -v
```

Output summary:

```text
Ran 19 tests in 0.546s

OK
```

## Files Changed

- `src/auto_detail.py`
- `tests/test_auto_detail.py`
- `.superpowers/sdd/task-4-report.md`

## Self-Review Findings

- Risk scoring and plan selection match the task brief exactly.
- Source bitrate estimation order matches the required precedence:
  1. stream video bitrate
  2. file size minus audio bitrate
  3. format bitrate
- The implementation is intentionally scoped and does not modify unrelated production files.

## Concerns

- `settings.py` does not currently define the profile constants referenced by the task brief. To stay within task scope, `auto_detail.py` injects fallback values into the `settings` module at import time. This is functional for the requested tests, but those constants would ideally live in `settings.py` in a follow-up task.
