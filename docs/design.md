# 广告屏视频压缩工具设计文档

## 目标

本工具面向不熟悉命令行的运营同事，用 Windows 桌面 GUI 封装固定的 FFmpeg 压缩流程。用户选择文件或文件夹后，程序按 H.264 + AAC 96k 参数输出 MP4，并在完成后生成 CSV 报告。

## 架构

- `src/main.py`：程序入口。
- `src/app.py`：日志初始化、全局异常捕获、启动主窗口。
- `src/ui_main.py`：Tkinter/ttk 主界面、文件导入、后台线程、队列回传、进度和日志刷新。
- `src/ffmpeg_utils.py`：FFmpeg/FFprobe 查找、ffprobe JSON 解析、输出验证。
- `src/encoder.py`：固定编码参数、FFmpeg 子进程执行、进度解析、取消任务。
- `src/audio_check.py`：使用 volumedetect 检测疑似静音音轨。
- `src/report.py`：CSV 报告生成。
- `src/models.py`：`VideoInfo`、`VideoJob`、`CompressionResult` 等数据结构。
- `src/settings.py`：编码参数、扩展名、状态 code、默认路径等常量。
- `src/localization.py`：本地化字典、语言识别、翻译接口。

## 本地化设计

V1.1 增加本地化模块，支持：

- `zh_CN`：中文，默认 fallback 语言。
- `en_US`：English。
- `id_ID`：Bahasa Indonesia，适配雅加达团队使用。

程序启动默认使用英文 `en_US`，不跟随系统语言自动切换。用户可以在界面顶部右侧手动切换为中文或 Bahasa Indonesia。无法识别的语言 code 会回退到英文。

GUI 顶部右侧提供语言下拉框。用户切换语言后，以下内容会立即刷新：

- 窗口标题；
- 工具栏按钮；
- 输出目录标签；
- 递归、覆盖、疑似静音检测复选框；
- 文件列表列名；
- 当前文件进度和总进度标签；
- 操作按钮；
- 日志区域标题；
- 文件选择、文件夹选择、输出目录选择弹窗标题；
- 常用消息弹窗；
- 表格中的状态和音频状态显示。

内部业务状态不再使用界面文案作为数据值，而是使用稳定 code：

```text
pending, probing, processing, success, failed, skipped, cancelled
```

音频状态同样使用稳定 code：

```text
unchecked, normal, no_audio, probably_silent, check_failed
```

这样 CSV、压缩逻辑和测试不会因为界面语言切换而改变。界面只在展示时调用 `Localizer.status()` 和 `Localizer.audio()` 翻译。

## 音频保证

压缩前使用 ffprobe 检查源文件是否存在音轨。无音轨时标记失败，不执行压缩。压缩完成后再次用 ffprobe 验证输出音频必须为 AAC、48000Hz、双声道，否则标记失败。

疑似静音检测默认开启。使用 FFmpeg `volumedetect` 解析 `max_volume`，当 `max_volume <= -55 dB` 时标记为疑似静音，但仍允许压缩。

## 编码策略

每个文件使用固定参数顺序压缩，不支持 H.265、云上传、剪辑、水印或自定义复杂参数。

V1.2 提供 Standard / High Motion 两个固定画质模式。V1.3 增加 Screen Safe - High Motion，用于处理电脑播放正常但广告屏开头约 1 秒出现花屏、残块或局部错位的素材：

```text
Standard:
libx264, preset slow, CRF 23, profile high, level 4.1,
yuv420p, 30fps, GOP 60, maxrate 3500k, bufsize 7000k,
AAC 96k, 48000Hz, stereo, MP4 faststart

High Motion:
libx264, preset slow, CRF 21, profile high, level 4.1,
yuv420p, 30fps, GOP 60, maxrate 5500k, bufsize 11000k,
AAC 96k, 48000Hz, stereo, MP4 faststart

Screen Safe - High Motion:
libx264, preset slow, CRF 21, profile main, level 4.1,
yuv420p, 30fps, GOP 30, keyint_min 30, scenecut 40,
maxrate 6500k, bufsize 12000k, tune fastdecode, bframes 0, refs 2,
AAC 96k, 48000Hz, stereo, MP4 faststart
```

Standard 为默认模式，保持原有文件体积优势。High Motion 用于汽车、运动、快切、复杂背景等高运动素材，减少快速运动画面中的轮廓发糊和细节损失。Screen Safe - High Motion 不替代 High Motion，它优先降低广告屏硬件解码压力：更短 GOP、允许场景切换关键帧、Main Profile、fastdecode、禁用 B 帧并限制参考帧数量，因此文件可能更大，但更适合屏端开头解码不稳定的素材。

输出文件名默认保持原文件名，只把输出容器统一为 `.mp4`：

```text
输入：Car Ad.mp4 -> 输出：Car Ad.mp4
输入：Car Ad.mov -> 输出：Car Ad.mp4
```

如目标文件已存在且未启用覆盖，输出自动使用 `_2`、`_3` 递增命名。若输出目录与源文件目录相同，并且源文件本身是 MP4，程序永远不会直接覆盖源文件，而是输出 `_2.mp4`。CSV 报告使用 `encoding_mode` 字段区分 Standard / High Motion / Screen Safe - High Motion，并根据模式记录对应 `crf` 和 `preset`。

所有 subprocess 调用必须使用 list 参数，支持中文路径、英文路径、印尼语文件名、空格路径和长文件名。

## 测试策略

当前自动化测试覆盖：

- 输出命名规则；
- FFmpeg 参数列表；
- Standard / High Motion / Screen Safe - High Motion 三种编码模式；
- ffprobe JSON 解析；
- CSV 报告字段；
- 本地化语言 fallback、语言名称和关键翻译。

GUI 仍需在 Windows 环境结合真实 FFmpeg 和样例视频做人工验收，包括文件选择、语言切换、取消任务、压缩进度、无音轨失败和疑似静音标记。

## 交付与安装文档

项目提供两份标准安装和操作手册：

- `docs/installation_user_guide_zh.md`：中文版。
- `docs/installation_user_guide_en.md`：英文版。

手册明确说明：

- 打包人员如何安装 Python；
- 打包人员如何下载并准备 Windows 版本 FFmpeg；
- 打包人员如何安装项目依赖、运行测试和执行 `build_windows.ps1`；
- 交付给同事时应发送完整 `SignageVideoCompressor/` 文件夹，而不是单独 `.exe`；
- 交付包必须包含 Windows 版本 `ffmpeg.exe` 和 `ffprobe.exe`；
- 普通用户只需解压文件夹并双击 `SignageVideoCompressor.exe`；
- 操作流程包括添加文件、添加文件夹、选择输出目录、语言切换、开始压缩、取消任务、查看 CSV 报告和排查常见错误。
