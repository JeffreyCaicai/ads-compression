# 广告屏视频压缩工具安装与操作指导手册

版本：V1.5
适用系统：Windows 10 / Windows 11  
适用对象：打包交付人员、运营同事、项目执行同事、视频素材整理同事

## 1. 手册说明

本文档分为两部分：

- 打包交付人员：负责安装 Python、准备 FFmpeg、打包生成 Windows 可执行程序。
- 普通使用人员：只需要解压交付包并双击程序，不需要安装 Python，也不需要使用命令行。

推荐交付方式是发送一个完整文件夹或 ZIP 包，而不是只发送单独的 `.exe` 文件。

## 2. 最终交付包结构

建议交付包名称：

```text
SignageVideoCompressor/
```

交付包中应包含：

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

关键要求：

- `ffmpeg.exe` 和 `ffprobe.exe` 必须是 Windows 版本。
- 必须保留 `tools/ffmpeg/bin/` 目录结构。
- 不要只发送 `SignageVideoCompressor.exe`。

## 3. 打包人员：安装 Python

普通使用人员不需要安装 Python。只有需要从源码打包程序的人才需要安装。

### 方法 A：使用官方网站安装，推荐

1. 打开 Python Windows 官方下载页：

```text
https://www.python.org/downloads/windows/
```

2. 下载最新稳定版的 `Windows installer (64-bit)`。
3. 双击安装包。
4. 安装界面中必须勾选：

```text
Add python.exe to PATH
```

5. 点击 `Install Now`。
6. 安装完成后打开 PowerShell，执行：

```powershell
python --version
pip --version
```

如果能看到 Python 版本号和 pip 版本号，说明安装成功。

### 方法 B：使用 winget 安装

如果电脑支持 Windows Package Manager，可以在 PowerShell 中执行：

```powershell
winget install Python.Python.3.12
```

安装后重新打开 PowerShell，再验证：

```powershell
python --version
pip --version
```

如果公司电脑权限受限，请联系 IT 管理员安装。

## 4. 打包人员：下载并准备 FFmpeg

本程序依赖两个 Windows 可执行文件：

```text
ffmpeg.exe
ffprobe.exe
```

### 4.1 推荐下载入口

打开 FFmpeg 官方下载页：

```text
https://ffmpeg.org/download.html
```

在页面中找到：

```text
Windows EXE Files
```

FFmpeg 官方页面会列出 Windows 已编译版本来源，例如：

```text
Windows builds from gyan.dev
Windows builds by BtbN
```

推荐选择 `gyan.dev` 的 release build，通常下载文件名类似：

```text
ffmpeg-release-full.7z
```

或者：

```text
ffmpeg-release-essentials.7z
```

本工具需要 `ffmpeg.exe` 和 `ffprobe.exe`。V1.4 增加了 H.265 Small File 模式，因此 FFmpeg 版本必须包含 `libx265` 编码器。`gyan.dev` 的 essentials/release build 通常包含它，但打包前必须验证。

也可以直接打开 gyan.dev 的 FFmpeg Windows builds 页面：

```text
https://www.gyan.dev/ffmpeg/builds/
```

在 `release builds` 区域下载：

```text
ffmpeg-release-essentials.7z
```

如果电脑没有解压 `.7z` 的工具，可以安装 7-Zip：

```text
https://www.7-zip.org/
```

### 4.2 可选：用包管理器安装 FFmpeg

如果公司电脑允许使用包管理器，也可以选择以下方式之一安装 FFmpeg：

```powershell
winget install "FFmpeg (Essentials Build)"
```

或：

```powershell
winget install ffmpeg
```

如果使用 Chocolatey：

```powershell
choco install ffmpeg
```

如果使用 Scoop：

```powershell
scoop install ffmpeg-essentials
```

注意：包管理器安装通常会把 FFmpeg 放到系统目录或用户目录中。为了让交付包在其他同事电脑上也能直接运行，仍建议从安装位置找到 `ffmpeg.exe` 和 `ffprobe.exe`，复制到：

```text
tools/ffmpeg/bin/
```

### 4.3 解压 FFmpeg

下载后使用 7-Zip 或其他解压软件解压 `.7z` 文件。

解压后通常会看到类似目录：

```text
ffmpeg-xxxx-release-essentials/
  bin/
    ffmpeg.exe
    ffplay.exe
    ffprobe.exe
```

只需要复制：

```text
ffmpeg.exe
ffprobe.exe
```

到项目目录：

```text
signage_video_compressor/
  tools/
    ffmpeg/
      bin/
        ffmpeg.exe
        ffprobe.exe
```

### 4.4 验证 FFmpeg

在 PowerShell 中进入 FFmpeg bin 目录：

```powershell
cd path\to\signage_video_compressor\tools\ffmpeg\bin
```

执行：

```powershell
.\ffmpeg.exe -version
.\ffprobe.exe -version
```

如果能显示版本信息，再检查是否支持 H.265 编码：

```powershell
.\ffmpeg.exe -hide_banner -encoders | findstr libx265
```

如果命令输出中能看到 `libx265` 编码器，说明 FFmpeg 可用于 H.264 和 H.265 模式。如果没有，请下载包含 `libx265` 的 full/release FFmpeg build。

## 5. 打包人员：安装项目依赖

进入项目目录：

```powershell
cd path\to\signage_video_compressor
```

建议先升级 pip：

```powershell
python -m pip install --upgrade pip
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

确认 PyInstaller 可用：

```powershell
python -m PyInstaller --version
```

## 6. 打包人员：运行测试

打包前建议先运行测试：

```powershell
python -m unittest discover -s tests -v
```

如果显示 `OK`，说明基础功能测试通过。

## 7. 打包人员：生成 Windows 程序

在项目目录运行：

```powershell
.\build_windows.ps1
```

打包完成后，输出目录为：

```text
dist/SignageVideoCompressor/
```

请检查该目录中是否包含：

```text
SignageVideoCompressor.exe
README.md
tools/ffmpeg/bin/ffmpeg.exe
tools/ffmpeg/bin/ffprobe.exe
```

然后把整个 `dist/SignageVideoCompressor/` 文件夹压缩成 ZIP，发给同事。

## 8. 普通使用人员：安装程序

收到 ZIP 后：

1. 右键 ZIP 文件，选择“全部解压”。
2. 将解压后的文件夹放到固定位置，例如：

```text
C:\Tools\SignageVideoCompressor\
```

3. 打开文件夹。
4. 双击：

```text
SignageVideoCompressor.exe
```

如果 Windows 出现安全提示：

1. 点击“更多信息”。
2. 点击“仍要运行”。

这是未做企业代码签名时的常见提示。

## 9. 首次启动检查

程序启动时会优先查找：

```text
tools/ffmpeg/bin/ffmpeg.exe
tools/ffmpeg/bin/ffprobe.exe
```

如果提示未找到 FFmpeg，请检查：

- 是否完整解压了 ZIP；
- 是否移动或删除了 `tools` 文件夹；
- `ffmpeg.exe` 和 `ffprobe.exe` 是否存在于 `tools/ffmpeg/bin/`。

如果 FFmpeg 安装在其他目录，也可以按提示手动选择 FFmpeg 的 `bin` 目录。

## 10. 界面语言

程序支持：

- 中文
- English
- Bahasa Indonesia

默认界面语言为 English。可在窗口顶部右侧的语言下拉框中切换为中文或 Bahasa Indonesia。切换后按钮、表格列名、状态、弹窗和常用提示会立即更新。

## 11. 添加视频

支持输入格式：

```text
.mp4, .mov, .m4v, .avi, .mkv
```

### 添加单个或多个视频

1. 点击“添加文件”。
2. 选择一个或多个视频文件。
3. 点击“打开”。
4. 视频会出现在文件列表中。

### 添加文件夹

1. 点击“添加文件夹”。
2. 选择包含视频素材的文件夹。
3. 程序会把该文件夹中的视频加入列表。

如需扫描子文件夹，请先勾选“递归扫描子文件夹”。

## 12. 选择输出目录

默认情况下，程序会在源文件同级目录创建：

```text
compressed
```

也可以点击“浏览”手动选择输出目录。

输出文件名规则：

```text
输入：Car Ad.mp4
输出：Car Ad.mp4

输入：Car Ad.mov
输出：Car Ad.mp4
```

如果目标文件已存在，且未勾选“覆盖已存在输出文件”，程序会自动生成：

```text
Car Ad_2.mp4
Car Ad_3.mp4
```

如果输出目录与源文件目录相同，并且源文件本身是 MP4，程序也会自动使用 `_2`，避免覆盖源文件。

## 13. 开始压缩

1. 添加视频文件或文件夹。
2. 确认输出目录。
3. 根据需要勾选：
   - 递归扫描子文件夹；
   - 覆盖已存在输出文件；
   - 检测疑似静音音轨。
4. 根据素材选择 Quality Mode：
   - Standard：普通广告，文件更小；
   - High Motion：汽车、运动、快切、复杂背景等素材，运动画面更清晰，文件更大；
   - Screen Safe - High Motion：压缩文件在电脑播放正常，但广告屏开头约 1 秒出现花屏、块状异常或局部错位时使用；
   - H.265 Smart Auto - Analyze Content：推荐给支持 H.265 的新屏使用。程序会抽样分析视频复杂度，并自动选择目标码率；
   - H.265 Small File 手动模式：只有在操作员明确要手动选择 Simple、Standard 或 Complex 时使用。
5. 点击“开始压缩”。
6. 等待进度条完成。

压缩过程中可以查看：

- 当前文件进度；
- 总任务进度；
- 表格中的状态；
- 底部日志。

## 14. 取消任务

压缩过程中点击“取消”。

程序会：

- 停止当前 FFmpeg 压缩进程；
- 将当前文件标记为“已取消”；
- 将未处理文件标记为“已取消”；
- 保留已经成功输出的文件。

## 15. 如何确认压缩成功

表格中状态显示“成功”，代表该文件已压缩完成，并通过输出验证。

程序会自动检查：

- 输出文件存在且大小大于 0；
- H.264 模式下视频编码为 H.264，H.265 模式下视频编码为 HEVC/H.265；
- 像素格式为 yuv420p；
- 分辨率与源文件一致；
- H.264 模式帧率约为 30fps，H.265 模式帧率约为 25fps；
- 音频为 AAC；
- 采样率为 48000Hz；
- 声道数为 2；
- 输出时长与源文件差异不超过 0.5 秒。

## 16. 音频规则

公司当前生产规范要求保留音频。

### 源文件无音轨

如果源文件没有音轨，程序会标记失败，并提示更换带音频的源文件。

这种情况不会输出成功结果。

### 疑似静音音轨

默认开启“检测疑似静音音轨”。

如果检测到音轨疑似静音，程序会：

- 在界面中标记“疑似静音”；
- 在 CSV 报告中标记 `probably_silent`；
- 继续压缩，不会自动失败。

## 17. CSV 报告

每次批量处理完成后，输出目录会生成报告：

```text
compression_report_YYYYMMDD_HHMMSS.csv
```

报告包含源文件路径、输出文件路径、处理状态、失败原因、时长、分辨率、压缩前后大小、节省比例、encoding_mode、编码信息和音频状态。

## 18. 常见问题

### 程序打不开

请确认：

- 使用的是 Windows 10 或 Windows 11；
- 已经完整解压 ZIP；
- 没有从 ZIP 压缩包内部直接运行；
- 杀毒软件没有拦截程序。

### 提示找不到 FFmpeg

请确认完整目录存在：

```text
tools/ffmpeg/bin/ffmpeg.exe
tools/ffmpeg/bin/ffprobe.exe
```

### 文件显示失败

请查看底部日志和：

```text
logs/app_YYYYMMDD.log
```

常见原因：

- 源文件损坏；
- 源文件无音轨；
- 文件格式不被 FFmpeg 支持；
- 输出验证不通过；
- 输出目录没有写入权限。

### 输出文件没有声音

如果程序显示“成功”，输出文件已经通过 AAC 音频验证。请再检查播放软件是否静音，或广告屏设备是否关闭音量。

如果源文件本身是静音音轨，程序会标记“疑似静音”，但仍允许压缩。

### 打包时报 Access is denied

如果运行 `.\build_windows.ps1` 时提示：

```text
PermissionError: [WinError 5] Access is denied: '...\dist\SignageVideoCompressor'
```

通常是旧版 `SignageVideoCompressor.exe` 还在运行，或资源管理器正在打开 `dist\SignageVideoCompressor` 目录。处理方式：

1. 关闭已经打开的 Signage Video Compressor 程序窗口。
2. 关闭正在查看 `dist` 或 `dist\SignageVideoCompressor` 的资源管理器窗口。
3. 重新运行：

```powershell
.\build_windows.ps1
```

如果仍然失败，可在任务管理器中结束 `SignageVideoCompressor.exe` 后再打包。

## 19. 压缩参数

本工具提供 H.264 兼容模式和 H.265 小文件模式：

```text
Standard:
H.264 / libx264, CRF 23, preset slow,
profile high, level 4.1, yuv420p, 30 fps,
GOP 60, maxrate 3500k, bufsize 7000k,
AAC 96k, 48000 Hz, 2 channels, MP4 faststart

High Motion:
H.264 / libx264, CRF 21, preset slow,
profile high, level 4.1, yuv420p, 30 fps,
GOP 60, maxrate 5500k, bufsize 11000k,
AAC 96k, 48000 Hz, 2 channels, MP4 faststart

Screen Safe - High Motion:
H.264 / libx264, CRF 21, preset slow,
profile main, level 4.1, yuv420p, 30 fps,
GOP 30, maxrate 6500k, bufsize 12000k,
tune fastdecode, 禁用 B 帧, refs 2,
AAC 96k, 48000 Hz, 2 channels, MP4 faststart

H.265 Smart Auto - Analyze Content:
HEVC / libx265, preset slow, Main Profile,
25 fps, GOP 250, hvc1 MP4 tag,
压缩前抽样 160x90 / 2fps 灰度帧,
自动选择 Simple / Standard / Complex 目标码率,
AAC 96k, 48000 Hz, 2 channels, MP4 faststart

H.265 Small File 手动模式:
使用同一套 H.265 参数，但由操作员手动选择 Simple、Standard 或 Complex。
```

不支持云上传、剪辑、水印或自定义复杂参数。
