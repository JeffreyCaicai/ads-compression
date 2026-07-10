# 广告屏视频压缩工具设计文档

## 目标

本工具面向不熟悉命令行的运营同事，用 Windows 桌面 GUI 封装固定的 FFmpeg 压缩流程。用户选择文件或文件夹后，程序按已验证的 H.264 或 H.265 + AAC 96k 参数输出 MP4，并在完成后生成 CSV 报告。

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

每个文件使用固定参数顺序压缩，不支持云上传、剪辑、水印或自定义复杂参数。

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

V1.4 增加 H.265 Small File 三个手动复杂度模式，用于已确认支持 H.265 的新屏。它们按屏幕尺寸和素材复杂度选择目标视频码率，目标是接近云端压缩效果并减少数据传输成本：

```text
H.265 Small File - Simple/Static:
libx265, preset slow, Main Profile, yuv420p, 25fps,
GOP 250, min-keyint 25, scenecut 40, hvc1 MP4 tag,
AAC 96k, 48000Hz, stereo, MP4 faststart

H.265 Small File - Standard Content:
同上，使用标准素材目标码率，是新屏推荐模式。

H.265 Small File - Complex Motion:
同上，使用复杂/高运动素材目标码率。
```

H.265 目标视频码率表：

```text
1920x1080 横屏：Simple 450k / Standard 800k / Complex 1200k
1080x1920 竖屏：Simple 500k / Standard 1300k / Complex 1800k
1920x1440 或 1080x2560 高像素屏：Simple 600k / Standard 1400k / Complex 2200k
```

V1.5 增加 H.265 Smart Auto - Analyze Content。用户只选择一个自动模式，程序在正式转码前先用 FFmpeg 快速抽样视频内容：

```text
抽样：160x90 灰度帧，2fps，最多 30 秒
分析：空间细节、帧间运动、场景变化率
输出：simple / standard / complex、复杂度分数、目标视频码率
回退：如果分析失败，使用 standard 复杂度目标码率继续压缩
```

Smart Auto 使用同一张 H.265 目标码率表，只是复杂度由程序自动判断而不是用户手动选择。CSV 报告记录 `content_complexity`、`content_complexity_score` 和 `target_video_bitrate_kbps`，方便后续复盘不同素材的实际决策。

V1.6 增加 H.265 Production - Best Detail。该模式面向支持 H.265 的新屏正式广告投放，固定使用 Complex 目标码率，不执行 Smart Auto 内容分析，避免正式素材被自动判断到 Simple 或 Standard 导致细节损失：

```text
H.265 Production - Best Detail:
libx265, preset slow, Main Profile, yuv420p, 25fps,
GOP 250, min-keyint 25, scenecut 40, hvc1 MP4 tag,
固定使用 Complex 目标视频码率,
AAC 96k, 48000Hz, stereo, MP4 faststart
```

CSV 报告中 `encoding_mode` 记录为 `h265_production_best_detail`，`content_complexity` 记录为 `production_best_detail`，`target_video_bitrate_kbps` 仍按屏幕尺寸使用 Complex 档：1920x1080 为 1200k，1080x1920 为 1800k，1920x1440 / 1080x2560 为 2200k。

V1.7 增加 H.265 Production - Best Detail (2-pass)。该模式不替代 V1.6 的一遍生产模式，而是新增一个更重视码率分配的正式投放选项。它固定使用同一张 Complex 目标码率表，第一遍只分析视频并写入 passlog，第二遍正式输出 MP4 和 AAC 音频：

```text
H.265 Production - Best Detail (2-pass):
pass 1: libx265, -pass 1, -passlogfile, no audio, null output
pass 2: libx265, -pass 2, same passlog, hvc1 MP4 tag, AAC 96k
进度映射：第一遍 0%-50%，第二遍 50%-100%
清理：成功、失败或取消后删除 passlog 临时文件
```

该模式通常接近一遍编码的两倍耗时，适合重点正式投放、细节要求更高的素材，或与云转码输出做 A/B 对比。CSV 报告中 `encoding_mode` 记录为 `h265_production_best_detail_2pass`，`content_complexity` 记录为 `production_best_detail`。

V1.8 增加 H.265 Production - Auto Detail (2-pass)。该模式面向批量正式投放，先分析每个视频的生产细节风险，再自动选择 best_detail_2pass 或 maximum_detail_2pass。Best/Maximum 目标码率与 `portrait_screen` 风险按 DAR、SAR 和旋转元数据计算出的显示宽高选择；例如编码宽高为 1920x1080、显示宽高为 1080x1920 的素材使用竖屏 1800k/2600k 档位。它不会替代现有 Best Detail (2-pass)，而是减少运营同事一次处理大量视频时逐条判断模式的工作量。

```text
CSV 报告新增 auto_selected_profile、auto_risk_score、auto_risk_reasons、source_video_bitrate_kbps、source_fps、peak_complexity_score、small_detail_score、peak_motion_score、scene_change_rate、target_gop 等字段。
```

V1.9 为 Auto Detail 增加输出质量闭环。生产细节分析和质量检查都使用显示方向与宽高比感知的灰度抽样；显示几何由 FFprobe 的 DAR、SAR 和规范化到 0-359 度的旋转元数据确定。源文件编码宽高字段保留用于报告，但 FFmpeg 自动旋转为正向画面时，输出编码宽高可以互换；结构验证比较双方的有效显示宽高。横屏固定宽度 `320` 并按比例计算偶数高度；竖屏固定高度 `320` 并按比例计算偶数宽度；抽样频率为 `2fps`。源时长不超过 30 秒时分析一个从 0 秒开始的片段；更长的源文件取开头、中间和结尾各 10 秒，避免只用片头代表整支广告。生产分析在每个片段内计算空间细节、细节瓦片、运动和场景变化，使用 1 秒（2 帧）与 2 秒（4 帧）滚动窗口峰值，并记录空间细节、细节瓦片、运动的 P90/P95 指标。

输出质量检查对相同时间片段分别运行 SSIM，并按片段等权平均；FFmpeg 对源文件和输出文件分别应用自动旋转，再按有效显示几何缩放到同一抽样尺寸，同时重新分析输出细节。通过阈值为 SSIM `>= 0.94`。源文件细节分数 `>= 20` 时，输出细节保留率必须 `>= 80%`；低于该源细节下限时不以保留率判定警告。质量分析和 SSIM 子进程都会观察取消事件，先 terminate，必要时在 5 秒后 kill，随后返回取消状态。

Auto Detail 先完成结构验证的 Best Detail 或 Maximum Detail 两遍输出，再运行质量检查。Best Detail 的质量警告或质量检查错误最多触发一次 Maximum Detail 重试；初始 Maximum Detail 不会重试，重试后的 Maximum Detail 也绝不再重试。质量警告表示该输出已通过结构、HEVC、音频、尺寸、像素格式和时长验证，但需要人工复核，不等于压缩失败。质量检查错误同样会记录为检查失败；若当前文件已是 Maximum Detail，则保留其结构有效输出供人工复核。

重试是一个备份事务：开始 Maximum Detail 前，先将 Best Detail 输出移至同目录、隐藏的 `.quality-backup` 文件名。若重试编码失败、质量检查取消、取消发生在备份或重试期间，或发生意外异常，程序恢复 Best Detail 文件及选定的 Best 编码字段（计划、目标码率/FPS/GOP、进度、状态/错误、输出大小、最终 profile、初始 SSIM 和细节保留率）。`quality_retry_count` 和 `quality_retry_reason` 保留为重试审计事实；重试编码失败后 `quality_check_status` 标记为 `quality_retry_failed`。重试后的质量检查报错不会恢复 Best，而是记录为 `quality_check_failed` 并保留结构有效的 Maximum Detail 输出。恢复操作本身失败时才将任务标记为失败。Maximum Detail 被保留时会删除备份。此流程只适用于 Auto Detail；原有 H.265 两遍模式不运行质量检查。

V1.9 CSV 追加以下质量闭环字段：`quality_check_status`、`ssim_score`、`detail_retention_percent`、`quality_retry_count`、`quality_retry_reason`、`final_selected_profile`。它们与既有的 `auto_selected_profile`、风险、源码率/帧率、峰值复杂度、细节、运动、场景变化和 `target_gop` 字段共同记录决策、重试和最终保留的输出。

Standard 为默认模式，保持原有 H.264 兼容行为。High Motion 用于老屏或 H.264 流程中的汽车、运动、快切、复杂背景等高运动素材，减少快速运动画面中的轮廓发糊和细节损失。Screen Safe - High Motion 不替代 High Motion，它优先降低广告屏硬件解码压力：更短 GOP、允许场景切换关键帧、Main Profile、fastdecode、禁用 B 帧并限制参考帧数量，因此文件可能更大，但更适合屏端开头解码不稳定的素材。H.265 Production - Best Detail 面向支持 H.265 的新屏正式投放，优先保证细节；H.265 Production - Best Detail (2-pass) 面向重点正式投放，优先改善码率分配；H.265 Production - Auto Detail (2-pass) 面向批量正式投放，优先减少人工逐条判断；H.265 Smart Auto / Small File 面向支持 H.265 的新屏，优先降低文件体积；75 块仅支持 H.264 的老屏继续使用 H.264 模式。

输出文件名默认保持原文件名，只把输出容器统一为 `.mp4`：

```text
输入：Car Ad.mp4 -> 输出：Car Ad.mp4
输入：Car Ad.mov -> 输出：Car Ad.mp4
```

如目标文件已存在且未启用覆盖，输出自动使用 `_2`、`_3` 递增命名。若输出目录与源文件目录相同，并且源文件本身是 MP4，程序永远不会直接覆盖源文件，而是输出 `_2.mp4`。CSV 报告使用 `encoding_mode` 字段区分 Standard / High Motion / Screen Safe - High Motion / H.265 Production - Best Detail / H.265 Production - Best Detail (2-pass) / H.265 Production - Auto Detail (2-pass) / H.265 Smart Auto / H.265 Small File，并根据模式记录对应 `crf`、`preset`、`target_video_bitrate_kbps`、`target_fps`、`content_complexity` 和 `content_complexity_score`。

所有 subprocess 调用必须使用 list 参数，支持中文路径、英文路径、印尼语文件名、空格路径和长文件名。

## 测试策略

当前自动化测试覆盖：

- 输出命名规则；
- FFmpeg 参数列表；
- Standard / High Motion / Screen Safe - High Motion / H.265 Production - Best Detail / H.265 Production - Best Detail (2-pass) / H.265 Production - Auto Detail (2-pass) / H.265 Smart Auto / H.265 Small File 编码模式；
- ffprobe JSON 解析；
- CSV 报告字段；
- 本地化语言 fallback、语言名称和关键翻译。
- Auto Detail 的方向感知与三段抽样、窗口/P90/P95 指标、SSIM/细节阈值、取消、单次重试、警告/检查失败和备份恢复；
- Windows 构建前置检查，以及受 Windows 与随包二进制条件限制的真实 FFmpeg smoke 测试。

GUI 仍需在 Windows 环境结合真实 FFmpeg 和样例视频做人工验收，包括文件选择、语言切换、取消任务、压缩进度、无音轨失败、疑似静音标记，以及 Auto Detail 的质量警告、重试和恢复路径。真实 FFmpeg smoke 受 Windows 和随包 `ffmpeg.exe`/`ffprobe.exe` 门控；在 macOS 或二进制未准备好时会跳过，不能替代 Windows 人工验收。

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
