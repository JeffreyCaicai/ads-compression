# Codex Handover: Signage Video Compressor

Last updated: 2026-06-19  
Project: 广告屏视频压缩工具 / Signage Video Compressor  
GitHub repo: https://github.com/JeffreyCaicai/ads-compression  
Default branch: `main`

## Current Project State

This is a Python 3.11+ Tkinter/ttk Windows desktop app that wraps local FFmpeg/FFprobe for signage video compression.

The app is built for non-technical operations users. They select video files or folders, choose a quality mode, and click Start Compression. The app generates MP4 outputs, logs, and a CSV report.

Latest application code commit before this handoff document:

```text
0a45905 Preserve source filename for compressed output
```

Recent important application commits:

```text
0a45905 Preserve source filename for compressed output
463dde5 Add high motion quality mode
540ded6 Fix FFmpeg lookup in PyInstaller bundle
73eef8e Set English as default language
b57f800 Initial signage video compressor
```

## Repository Layout

```text
signage_video_compressor/
  README.md
  requirements.txt
  build_windows.ps1
  docs/
    design.md
    installation_user_guide_en.md
    installation_user_guide_zh.md
    codex_handover.md
  src/
    main.py
    app.py
    models.py
    ffmpeg_utils.py
    encoder.py
    audio_check.py
    report.py
    settings.py
    ui_main.py
    localization.py
  tests/
    test_ffprobe_parse.py
    test_localization.py
    test_naming.py
    test_report.py
  tools/
    ffmpeg/
      bin/
        .gitkeep
  logs/
    .gitkeep
```

Important: `ffmpeg.exe` and `ffprobe.exe` are intentionally not committed to GitHub. They are ignored by `.gitignore`. For Windows packaging and runtime, copy Windows versions into:

```text
tools\ffmpeg\bin\ffmpeg.exe
tools\ffmpeg\bin\ffprobe.exe
```

## How To Continue On A New Computer

### Option A: With Git Installed

Install Git for Windows if needed:

```text
https://git-scm.com/download/win
```

Clone the repo:

```powershell
git clone https://github.com/JeffreyCaicai/ads-compression.git
cd ads-compression
```

If the repo already exists:

```powershell
cd path\to\ads-compression
git pull
```

### Option B: Without Git

Open:

```text
https://github.com/JeffreyCaicai/ads-compression
```

Use:

```text
Code -> Download ZIP
```

Extract the ZIP and work in the extracted folder.

## Windows Build Environment

Install Python 3.11+ from:

```text
https://www.python.org/downloads/windows/
```

During installation, enable:

```text
Add python.exe to PATH
```

Verify:

```powershell
python --version
pip --version
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Prepare FFmpeg:

1. Open https://ffmpeg.org/download.html
2. Go to Windows EXE Files.
3. Use a Windows build source such as gyan.dev.
4. Download `ffmpeg-release-essentials.7z`.
5. Extract and copy:

```text
ffmpeg.exe
ffprobe.exe
```

into:

```text
tools\ffmpeg\bin\
```

Verify:

```powershell
.\tools\ffmpeg\bin\ffmpeg.exe -version
.\tools\ffmpeg\bin\ffprobe.exe -version
```

## Test And Build Commands

Run tests from repo root:

```powershell
python -m unittest discover -s tests -v
```

Expected current result:

```text
16 tests, OK
```

Build Windows app:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows.ps1
```

Build output:

```text
dist\SignageVideoCompressor\
```

Package this whole folder for colleagues:

```text
dist\SignageVideoCompressor\
```

Do not send only `SignageVideoCompressor.exe`.

## Current Product Behavior

### Default Language

Default GUI language is English. Users can switch to:

- Chinese
- English
- Bahasa Indonesia

Code:

```text
src/localization.py
src/ui_main.py
```

### Quality Modes

The GUI has a `Quality Mode` dropdown:

```text
Standard - General Compression
High Motion - Better Motion Quality
```

Standard mode:

```text
CRF 23
maxrate 3500k
bufsize 7000k
```

High Motion mode:

```text
CRF 21
maxrate 5500k
bufsize 11000k
```

High Motion was added because high-motion ads, such as cars moving quickly at the start of a clip, showed blurred outlines under the original 3500k cap.

Code:

```text
src/settings.py
src/encoder.py
src/ui_main.py
tests/test_naming.py
```

### Output Filename Rule

Current rule preserves the source filename stem:

```text
Input:  Car Ad.mp4
Output: Car Ad.mp4

Input:  Car Ad.mov
Output: Car Ad.mp4
```

If output already exists and overwrite is off:

```text
Car Ad_2.mp4
Car Ad_3.mp4
```

If the output folder is the same as the source folder and the source is already MP4, the app will not overwrite the source file. It uses `_2.mp4`.

This was changed because operations colleagues did not want to rename files after compression.

Code:

```text
src/encoder.py
tests/test_naming.py
```

### FFmpeg Lookup Rule

The app looks for FFmpeg/FFprobe in:

```text
tools/ffmpeg/bin/
_internal/tools/ffmpeg/bin/
PyInstaller _MEIPASS/tools/ffmpeg/bin/
system PATH
```

This was fixed after PyInstaller placed bundled data under `_internal` in the packaged folder.

Code:

```text
src/ffmpeg_utils.py
tests/test_ffprobe_parse.py
```

### Audio Rules

Audio is mandatory.

- Source with no audio stream: fail.
- Probably silent audio: mark warning, continue compression.
- Output validation requires AAC, 48000Hz, 2 channels.

Code:

```text
src/audio_check.py
src/ffmpeg_utils.py
src/encoder.py
```

## CSV Report

CSV report includes:

```text
source_file
output_file
status
error_message
duration_sec
resolution
original_size_mb
output_size_mb
size_reduction_percent
source_video_codec
output_video_codec
source_audio_codec
output_audio_codec
audio_status
encoding_mode
crf
preset
created_at
```

`encoding_mode` distinguishes:

```text
standard
high_motion
```

Code:

```text
src/report.py
tests/test_report.py
```

## Known Operational Notes

1. If PowerShell says `git` is not recognized, install Git for Windows or download the repo as ZIP from GitHub.
2. If the app says FFmpeg is missing after packaging, first check the packaged folder:

```text
dist\SignageVideoCompressor\_internal\tools\ffmpeg\bin\
```

and:

```text
dist\SignageVideoCompressor\tools\ffmpeg\bin\
```

3. If users run the app from the source directory instead of `dist`, logs may appear in the source `logs/` folder.
4. When recursively adding folders, the app skips the default `compressed` directory to avoid importing output files again.
5. High Motion improves motion detail but creates larger files.

## Recommended Manual QA Before Sending A Build

On Windows after packaging:

1. Launch:

```text
dist\SignageVideoCompressor\SignageVideoCompressor.exe
```

2. Confirm the app starts without FFmpeg warning.
3. Confirm default language is English.
4. Add a small video with audio.
5. Compress in Standard mode.
6. Compress a high-motion video in High Motion mode.
7. Confirm output filenames preserve original names.
8. Confirm CSV has `encoding_mode`, `crf`, and `preset`.
9. Confirm output audio is present.
10. Confirm no-audio source fails clearly.

## Suggested Next Development Tasks

These are not required immediately, but are likely useful:

1. Add an About/Version label in the GUI so users can tell which build they are running.
2. Add a small tooltip or helper text explaining when to use High Motion.
3. Add a runtime self-check panel showing detected FFmpeg path.
4. Add a version number to CSV reports.
5. Add a sample test video workflow for QA if sample media can be stored internally.

## Useful Commands For Codex

Check status:

```powershell
git status --short --branch
git log --oneline -6
```

Run tests:

```powershell
python -m unittest discover -s tests -v
```

Build:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\build_windows.ps1
```

Push changes:

```powershell
git add .
git commit -m "Your message"
git push
```

## Good Starting Prompt For New Codex Session

```text
We are continuing development on JeffreyCaicai/ads-compression, a Python Tkinter Windows desktop app for signage video compression. Please read docs/codex_handover.md, docs/design.md, README.md, then inspect git status and recent commits before making changes. Preserve the current behavior: default English UI, Standard and High Motion quality modes, output filename preserves source stem, FFmpeg lookup supports PyInstaller _internal, audio is mandatory, and tests should pass with python -m unittest discover -s tests -v.
```
