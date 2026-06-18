$ErrorActionPreference = "Stop"

Write-Host "Building 广告屏视频压缩工具 with PyInstaller..."

if (-not (Test-Path ".\src\main.py")) {
    throw "Please run this script from the signage_video_compressor project directory."
}

python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --windowed --name SignageVideoCompressor `
    --add-data "tools;tools" `
    --add-data "README.md;." `
    src/main.py

Write-Host "Build complete: dist\SignageVideoCompressor\SignageVideoCompressor.exe"
