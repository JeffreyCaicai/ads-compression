Task 5 Review Fix Report

Changes
- Reset every Auto Detail `VideoJob` field in `start_compression()` before reusing queued jobs for another run.
- Cleared stale Auto Detail analysis metrics in `_analyze_job_auto_detail()` when analysis fails, while keeping fallback plan fields populated.

Verification
- Command: `python3 -m unittest discover -s tests -v`
- Result: PASS (`Ran 51 tests in 0.548s`, `OK`)

Concerns
- None.
