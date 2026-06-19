# 广告屏视频压缩工具

这是一个给运营、项目执行和素材整理同事使用的 Windows 桌面工具。它会把视频压缩为广告屏播放验证过的 MP4 格式：H.264 + AAC 96k，并保留源视频分辨率。

## 如何启动

双击 `SignageVideoCompressor.exe` 启动程序。

界面支持三种语言：

- 中文
- English
- Bahasa Indonesia

默认界面语言为 English。启动后可在窗口顶部右侧的“Language”下拉框中切换为中文或 Bahasa Indonesia。切换后按钮、表格列名、状态、弹窗和常用提示会立即更新。

如果是从源码运行，进入项目目录后执行：

```powershell
python src/main.py
```

程序启动时会优先查找随包携带的：

```text
tools/ffmpeg/bin/ffmpeg.exe
tools/ffmpeg/bin/ffprobe.exe
```

如果没有找到，会提示你手动选择 FFmpeg 的 `bin` 目录。

## 如何添加视频

- 点击“添加文件”可以选择一个或多个视频。
- 点击“添加文件夹”可以导入文件夹里的视频。
- 勾选“递归扫描子文件夹”后，会连同子文件夹里的视频一起导入。
- 支持输入格式：`.mp4`, `.mov`, `.m4v`, `.avi`, `.mkv`。
- 已经压缩过、文件名包含 `_h264_crf23_aac96` 或 `_h264_crf21_highmotion_aac96` 的视频会自动跳过。

## 画质模式

界面提供两种 Quality Mode：

```text
Standard - General Compression
CRF 23 / maxrate 3500k / bufsize 7000k
适合普通广告，文件更小。

High Motion - Better Motion Quality
CRF 21 / maxrate 5500k / bufsize 11000k
适合汽车、运动、快切、复杂背景等高运动素材，画质更稳，文件会更大。
```

默认使用 Standard。如果上屏发现车身轮廓、快速移动物体或复杂背景发糊，建议切换到 High Motion 后重新压缩。

## 输出文件在哪里

默认输出到源文件同级的 `compressed` 文件夹。也可以在界面顶部“输出目录”中手动选择。

输出文件名规则：

```text
Standard: 原文件名_h264_crf23_aac96.mp4
High Motion: 原文件名_h264_crf21_highmotion_aac96.mp4
```

如果输出文件已存在，且没有勾选“覆盖已存在输出文件”，程序会自动生成 `_2`, `_3` 这样的新文件名。

## 如何压缩

1. 添加视频文件或文件夹。
2. 确认输出目录。
3. 按需选择“递归扫描子文件夹”“覆盖已存在输出文件”“检测疑似静音音轨”。
4. 点击“开始压缩”。
5. 等待当前文件进度和总进度完成。

压缩过程中可以点击“取消”。当前 FFmpeg 任务会被终止，未处理的文件会标记为“已取消”。

## 如何判断成功

表格中状态显示“成功”代表该文件已压缩完成，并且通过了输出验证。程序会检查：

- 输出文件存在且大小大于 0；
- 视频编码为 H.264；
- 像素格式为 yuv420p；
- 分辨率与源文件一致；
- 帧率约为 30fps；
- 音频为 AAC / 48000Hz / 双声道；
- 输出时长与源文件差异不超过 0.5 秒。

每次任务结束后，输出目录会生成一份 CSV 报告：

```text
compression_report_YYYYMMDD_HHMMSS.csv
```

报告包含源文件、输出文件、状态、失败原因、压缩前后大小、节省比例、音频状态、encoding_mode、CRF、preset 等信息。

## 无音轨或疑似静音怎么办

公司当前生产规范要求保留音频。

- 如果源文件没有音轨，程序会标记失败，并提示更换带音频的源文件。
- 如果检测到疑似静音音轨，程序会在界面和 CSV 中标记“疑似静音”，但仍会继续压缩。
- 如果音频检测失败，程序会标记“音频检测失败”，但仍会继续压缩。

## 常见问题

### 提示未找到 FFmpeg

请确认程序目录中存在：

```text
tools/ffmpeg/bin/ffmpeg.exe
tools/ffmpeg/bin/ffprobe.exe
```

如果 FFmpeg 在其他位置，按提示选择包含这两个文件的 `bin` 目录。

### 某个文件显示失败

先看界面底部日志，再查看 `logs/app_YYYYMMDD.log`。常见原因包括源文件损坏、无音轨、FFmpeg 不支持该文件，或输出验证未通过。

### 输出目录打不开

确认已经至少开始过一次任务，或手动选择一个存在的输出目录。

## 压缩参数

本工具不提供 H.265、云上传、剪辑、水印等功能。视频输出统一为 H.264 / AAC / MP4，并提供两个固定模式：

```text
Standard:
H.264 / libx264, preset slow, CRF 23,
maxrate 3500k, bufsize 7000k,
AAC 96k, 48000 Hz, 双声道, MP4 + faststart

High Motion:
H.264 / libx264, preset slow, CRF 21,
maxrate 5500k, bufsize 11000k,
AAC 96k, 48000 Hz, 双声道, MP4 + faststart
```

## 打包 Windows 程序

开发人员可在项目目录运行：

```powershell
.\build_windows.ps1
```

打包结果位于：

```text
dist/SignageVideoCompressor/SignageVideoCompressor.exe
```
