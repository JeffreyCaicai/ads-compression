# Signage Video Compressor Installation and User Guide

Version: V1.1  
Supported systems: Windows 10 / Windows 11  
Audience: build owners, delivery owners, operations staff, project execution staff, and media preparation staff

## 1. About This Guide

This guide has two parts:

- Build and delivery owners: install Python, prepare FFmpeg, and package the Windows executable.
- Regular users: unzip the delivery package and double-click the application. They do not need Python and do not need to use the command line.

The recommended delivery format is a complete folder or ZIP package, not a single `.exe` file.

## 2. Final Delivery Package Structure

Recommended package name:

```text
SignageVideoCompressor/
```

The package should contain:

```text
SignageVideoCompressor/
  SignageVideoCompressor.exe
  README.md
  tools/
    ffmpeg/
      bin/
        ffmpeg.exe
        ffprobe.exe
  logs/
```

Important:

- `ffmpeg.exe` and `ffprobe.exe` must be Windows binaries.
- Keep the `tools/ffmpeg/bin/` folder structure.
- Do not send only `SignageVideoCompressor.exe`.

## 3. Build Owner: Install Python

Regular users do not need Python. Python is only required when building the application from source.

### Option A: Install from the Official Website, Recommended

1. Open the official Python Windows download page:

```text
https://www.python.org/downloads/windows/
```

2. Download the latest stable `Windows installer (64-bit)`.
3. Run the installer.
4. On the first installer screen, enable:

```text
Add python.exe to PATH
```

5. Click `Install Now`.
6. After installation, open PowerShell and run:

```powershell
python --version
pip --version
```

If both commands show version numbers, Python is installed correctly.

### Option B: Install with winget

If Windows Package Manager is available, run this in PowerShell:

```powershell
winget install Python.Python.3.12
```

After installation, reopen PowerShell and verify:

```powershell
python --version
pip --version
```

If the company computer is locked down, ask IT to install Python.

## 4. Build Owner: Download and Prepare FFmpeg

This application requires two Windows executable files:

```text
ffmpeg.exe
ffprobe.exe
```

### 4.1 Recommended Download Entry Point

Open the official FFmpeg download page:

```text
https://ffmpeg.org/download.html
```

Find:

```text
Windows EXE Files
```

The FFmpeg page links to compiled Windows builds such as:

```text
Windows builds from gyan.dev
Windows builds by BtbN
```

The `gyan.dev` release build is a common choice. The downloaded file is usually named like:

```text
ffmpeg-release-full.7z
```

or:

```text
ffmpeg-release-essentials.7z
```

This tool only needs `ffmpeg.exe` and `ffprobe.exe`, so the `essentials` package is usually enough.

You can also open the gyan.dev FFmpeg Windows builds page directly:

```text
https://www.gyan.dev/ffmpeg/builds/
```

In the `release builds` section, download:

```text
ffmpeg-release-essentials.7z
```

If the computer cannot extract `.7z` files, install 7-Zip:

```text
https://www.7-zip.org/
```

### 4.2 Optional: Install FFmpeg with a Package Manager

If company policy allows package managers, use one of the following options:

```powershell
winget install "FFmpeg (Essentials Build)"
```

or:

```powershell
winget install ffmpeg
```

If using Chocolatey:

```powershell
choco install ffmpeg
```

If using Scoop:

```powershell
scoop install ffmpeg-essentials
```

Note: package managers usually install FFmpeg into a system or user directory. To make the delivery package run on other computers without extra setup, still copy `ffmpeg.exe` and `ffprobe.exe` into:

```text
tools/ffmpeg/bin/
```

### 4.3 Extract FFmpeg

Use 7-Zip or another archive tool to extract the `.7z` file.

The extracted folder usually looks like:

```text
ffmpeg-xxxx-release-essentials/
  bin/
    ffmpeg.exe
    ffplay.exe
    ffprobe.exe
```

Copy only:

```text
ffmpeg.exe
ffprobe.exe
```

into the project:

```text
signage_video_compressor/
  tools/
    ffmpeg/
      bin/
        ffmpeg.exe
        ffprobe.exe
```

### 4.4 Verify FFmpeg

In PowerShell, enter the FFmpeg bin folder:

```powershell
cd path\to\signage_video_compressor\tools\ffmpeg\bin
```

Run:

```powershell
.\ffmpeg.exe -version
.\ffprobe.exe -version
```

If both commands show version information, FFmpeg is ready.

## 5. Build Owner: Install Project Dependencies

Enter the project directory:

```powershell
cd path\to\signage_video_compressor
```

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Confirm PyInstaller is available:

```powershell
python -m PyInstaller --version
```

## 6. Build Owner: Run Tests

Before packaging, run:

```powershell
python -m unittest discover -s tests -v
```

If the result shows `OK`, the basic tests passed.

## 7. Build Owner: Package the Windows Application

From the project directory, run:

```powershell
.\build_windows.ps1
```

The packaged app will be generated in:

```text
dist/SignageVideoCompressor/
```

Check that it contains:

```text
SignageVideoCompressor.exe
README.md
tools/ffmpeg/bin/ffmpeg.exe
tools/ffmpeg/bin/ffprobe.exe
```

Zip the entire `dist/SignageVideoCompressor/` folder and send it to users.

## 8. Regular User: Install the Application

After receiving the ZIP package:

1. Right-click the ZIP file and select “Extract All”.
2. Move the extracted folder to a stable location, for example:

```text
C:\Tools\SignageVideoCompressor\
```

3. Open the folder.
4. Double-click:

```text
SignageVideoCompressor.exe
```

If Windows shows a security warning:

1. Click “More info”.
2. Click “Run anyway”.

This is common when an application is not signed with an enterprise code-signing certificate.

## 9. First Launch Check

On startup, the app looks first for:

```text
tools/ffmpeg/bin/ffmpeg.exe
tools/ffmpeg/bin/ffprobe.exe
```

If FFmpeg is not found, check:

- the ZIP was fully extracted;
- the `tools` folder was not moved or deleted;
- `ffmpeg.exe` and `ffprobe.exe` exist in `tools/ffmpeg/bin/`.

If FFmpeg is installed somewhere else, the user can manually select the FFmpeg `bin` folder when prompted.

## 10. Interface Language

The application supports:

- Chinese
- English
- Bahasa Indonesia

The default interface language is English. Use the language dropdown at the top right of the window to switch to Chinese or Bahasa Indonesia. Buttons, table headers, status labels, dialogs, and common messages update immediately.

## 11. Add Videos

Supported input formats:

```text
.mp4, .mov, .m4v, .avi, .mkv
```

### Add One or More Video Files

1. Click “Add Files”.
2. Select one or more video files.
3. Click “Open”.
4. The videos will appear in the file list.

### Add a Folder

1. Click “Add Folder”.
2. Select a folder that contains video assets.
3. The app will add supported videos from that folder.

To include subfolders, enable “Scan Subfolders” before adding the folder.

## 12. Choose the Output Folder

By default, the app creates this folder next to the source file:

```text
compressed
```

Users can also click “Browse” and choose another output folder.

Output filename rule:

```text
original_filename_h264_crf23_aac96.mp4
```

If the target file already exists and “Overwrite Existing Output” is not enabled, the app creates a numbered filename:

```text
original_filename_h264_crf23_aac96_2.mp4
original_filename_h264_crf23_aac96_3.mp4
```

## 13. Start Compression

1. Add video files or a folder.
2. Confirm the output folder.
3. Select options if needed:
   - Scan Subfolders;
   - Overwrite Existing Output;
   - Detect Probably Silent Audio.
4. Click “Start Compression”.
5. Wait for the progress bars to finish.

During processing, users can check:

- current file progress;
- total progress;
- table status;
- log messages at the bottom.

## 14. Cancel a Task

Click “Cancel” during compression.

The app will:

- stop the current FFmpeg process;
- mark the current file as cancelled;
- mark remaining files as cancelled;
- keep files that were already compressed successfully.

## 15. How to Confirm Success

If the table status shows “Success”, the file has been compressed and passed output validation.

The app checks:

- output file exists and is larger than 0 bytes;
- video codec is H.264;
- pixel format is yuv420p;
- resolution matches the source file;
- frame rate is approximately 30fps;
- audio codec is AAC;
- sample rate is 48000Hz;
- channel count is 2;
- duration difference from the source is no more than 0.5 seconds.

## 16. Audio Rules

Current production rules require audio to be preserved.

### Source File Has No Audio

If the source file has no audio stream, the app marks it as failed and asks the user to use a source file with audio.

This case is not treated as a successful output.

### Probably Silent Audio

“Detect Probably Silent Audio” is enabled by default.

If probably silent audio is detected, the app will:

- mark the file as “Probably Silent” in the UI;
- write `probably_silent` in the CSV report;
- continue compression.

## 17. CSV Report

After each batch finishes, the output folder contains:

```text
compression_report_YYYYMMDD_HHMMSS.csv
```

The report includes source path, output path, status, error message, duration, resolution, original size, output size, size reduction, codec information, and audio status.

## 18. Troubleshooting

### The App Does Not Open

Check:

- the computer is running Windows 10 or Windows 11;
- the ZIP was fully extracted;
- the app is not being run directly from inside the ZIP file;
- antivirus software did not block the app.

### FFmpeg Was Not Found

Confirm this folder exists:

```text
tools/ffmpeg/bin/ffmpeg.exe
tools/ffmpeg/bin/ffprobe.exe
```

### A File Shows Failed

Check the bottom log area and:

```text
logs/app_YYYYMMDD.log
```

Common causes:

- source file is damaged;
- source file has no audio stream;
- file format is not supported by FFmpeg;
- output validation failed;
- output folder has no write permission.

### The Output Has No Sound

If the app shows “Success”, the output file has already passed AAC audio validation. Check whether the media player or signage device is muted.

If the source file itself contains silent audio, the app may mark it as “Probably Silent” while still allowing compression.

## 19. Fixed Compression Parameters

The app always uses:

```text
H.264 / libx264
CRF 23
preset slow
profile high
level 4.1
yuv420p
30 fps
GOP 60
maxrate 3500k
bufsize 7000k
AAC 96k
48000 Hz
2 channels
MP4 faststart
```

It does not support H.265, cloud upload, editing, watermarking, or advanced custom encoding parameters.
