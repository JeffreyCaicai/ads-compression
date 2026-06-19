$ErrorActionPreference = "Stop"

Write-Host "Building 广告屏视频压缩工具 with PyInstaller..."

if (-not (Test-Path ".\src\main.py")) {
    throw "Please run this script from the signage_video_compressor project directory."
}

$appProcessName = "SignageVideoCompressor"
$runningApp = Get-Process -Name $appProcessName -ErrorAction SilentlyContinue
if ($runningApp) {
    throw "SignageVideoCompressor.exe is still running. Please close the app window, then run build_windows.ps1 again."
}

$distAppDir = ".\dist\SignageVideoCompressor"
if (Test-Path $distAppDir) {
    try {
        Remove-Item $distAppDir -Recurse -Force -ErrorAction Stop
    }
    catch {
        throw "Cannot remove $distAppDir. Close SignageVideoCompressor.exe, close any Explorer window opened inside dist, then run build_windows.ps1 again. Original error: $($_.Exception.Message)"
    }
}

python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --windowed --name SignageVideoCompressor `
    --add-data "tools;tools" `
    --add-data "README.md;." `
    src/main.py

Write-Host "Build complete: dist\SignageVideoCompressor\SignageVideoCompressor.exe"
