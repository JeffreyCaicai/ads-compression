# 广告屏视频压缩工具

这是一个给运营、项目执行和素材整理同事使用的 Windows 桌面工具。它会把视频压缩为广告屏播放验证过的 MP4 格式，并保留源视频的显示比例、方向与结构分辨率。默认输出仍为 H.264 + AAC 96k；支持 H.265 Production、H.265 Production - Auto Detail (2-pass)、H.265 Small File 和 H.265 Smart Auto 模式，用于已确认支持 H.265 的新屏降低传输成本。

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
- 递归扫描时会自动跳过默认输出目录 `compressed`，避免把刚压缩出的文件再次加入列表。
- 旧版本生成的 `_h264_crf23_aac96` 或 `_h264_crf21_highmotion_aac96` 文件也会自动跳过。

## 画质模式

界面提供九种 Quality Mode：

```text
Standard - General Compression
CRF 23 / maxrate 3500k / bufsize 7000k
H.264，适合普通广告，兼容性高。

High Motion - Better Motion Quality
CRF 21 / maxrate 5500k / bufsize 11000k
H.264，适合汽车、运动、快切、复杂背景等高运动素材，画质更稳，文件会更大。

Screen Safe - High Motion
CRF 21 / maxrate 6500k / bufsize 12000k / GOP 30 / fastdecode
H.264，适合电脑播放正常、但广告屏开头约 1 秒出现花屏或块状异常的高运动素材。文件会更大，优先保证老屏或弱解码屏稳定。

H.265 Production - Best Detail
H.265 / 25fps / 固定使用 Complex 目标码率
适合支持 H.265 的新屏正式广告投放。优先保留人物、产品、字幕、logo 和车身线条等细节，文件通常大于 Smart Auto，但仍明显小于 H.264。

H.265 Production - Best Detail (2-pass)
H.265 / 25fps / 固定使用 Complex 目标码率 / 两遍编码
适合重点正式投放、与阿里云样片对比或对细节要求更高的素材。码率分配更充分，但压缩时间通常接近一遍编码的两倍。

H.265 Production - Auto Detail (2-pass)
H.265 / 自动分析细节风险 / 自动选择 Best Detail (2-pass) 或 Maximum Detail (2-pass)
适合批量正式投放场景。程序会先分析每个视频的生产细节风险，再自动选择普通 Best Detail (2-pass) 或 Maximum Detail (2-pass)，减少人工逐条判断和选错参数的风险。完成输出验证后，程序还会检查输出质量；如果从 Best Detail 开始且检查发现风险或检查无法完成，最多自动重试一次 Maximum Detail。

H.265 Smart Auto - Analyze Content
H.265 / 25fps / 先快速抽样分析画面复杂度，再自动选择目标码率
适合大多数已确认支持 H.265 的新屏，是优先推荐的小文件模式。

H.265 Small File - Standard Content
H.265 / 25fps / 按屏幕尺寸自动选择目标码率
适合已知属于普通复杂度的素材。

H.265 Small File - Complex Motion
H.265 / 25fps / 更高目标码率
适合汽车、运动、快切、复杂背景等高运动素材。

H.265 Small File - Simple/Static
H.265 / 25fps / 更低目标码率
适合静态画面、简单背景、文字或低运动素材。
```

默认使用 Standard，保留 H.264 兼容行为。新屏正式投放建议使用 H.265 Production - Best Detail；重点素材或需要更好码率分配时使用 H.265 Production - Best Detail (2-pass)。如果批量素材质量差异较大，优先使用 H.265 Production - Auto Detail (2-pass)。它不会把所有视频都强制压成大文件，只会对 QR code、小字、logo、高运动、高码率、高像素屏等高风险素材提高目标码率和保留 30fps。如果目标是进一步节省流量，可以使用 H.265 Smart Auto - Analyze Content，程序会自动判断素材复杂度并选择 Simple / Standard / Complex 目标码率。如果需要人工指定复杂度，可以使用三个 H.265 Small File 手动模式。75 块只支持 H.264 的老屏继续使用 Standard / High Motion / Screen Safe。

## 输出文件在哪里

默认输出到源文件同级的 `compressed` 文件夹。也可以在界面顶部“输出目录”中手动选择。

输出文件名规则：

```text
输入：Car Ad.mp4
输出：Car Ad.mp4

输入：Car Ad.mov
输出：Car Ad.mp4
```

如果输出文件已存在，且没有勾选“覆盖已存在输出文件”，程序会自动生成 `_2`, `_3` 这样的新文件名。若输出目录与源文件目录相同，并且源文件本身是 MP4，程序也会自动使用 `_2`，避免覆盖源文件。

## 如何压缩

1. 添加视频文件或文件夹。
2. 确认输出目录。
3. 按需选择“递归扫描子文件夹”“覆盖已存在输出文件”“检测疑似静音音轨”。
4. 点击“开始压缩”。
5. 等待当前文件进度和总进度完成。

压缩过程中可以点击“取消”。当前 FFmpeg 任务会被终止，未处理的文件会标记为“已取消”。

Auto Detail 的抽样分析和输出质量检查也支持取消。若取消发生在为 Maximum Detail 重试期间，程序会恢复已保留的 Best Detail 输出；不会继续发起下一次重试。

## 如何判断成功

表格中状态显示“成功”代表该文件已压缩完成，并且通过了输出验证。程序会按所选模式检查：

- 输出文件存在且大小大于 0；
- H.264 模式下视频编码为 H.264；
- H.265 Production / Auto Detail / Small File / Smart Auto 模式下视频编码为 HEVC/H.265；
- 像素格式为 yuv420p；
- 按 DAR/SAR 和旋转元数据计算的显示方向一致、宽高比相对误差不超过 1%，且输出编码像素总数不得低于源文件；FFmpeg 自动旋转或转换变形像素时，输出显示宽高不必逐项相等；
- H.264 模式帧率约为 30fps；
- H.265 Production - Auto Detail (2-pass) 在 30fps 源上优先保留 30fps；H.265 Production / Small File / Smart Auto 模式帧率约为 25fps；
- 音频为 AAC / 48000Hz / 双声道；
- 输出时长与源文件差异不超过 0.5 秒。

Auto Detail 还会在输出验证后比较源文件与输出文件。质量检查按 DAR/SAR 和旋转元数据确定的显示方向与宽高比，使用横屏 `320x按比例高度` 或竖屏 `按比例宽度x320` 的灰度抽样；长于 30 秒的视频取开头、中间和结尾各 10 秒。SSIM 必须达到 `0.94`。源文件细节分数达到 `20` 时，输出还必须保留至少 `80%` 的细节。若 Best Detail 未达到这些条件，或质量检查本身失败，程序只会重试一次 Maximum Detail。

“质量警告”不表示压缩失败：它表示输出已通过结构、编码、音频、分辨率和时长验证，但质量检查仍有警告，Maximum Detail 输出会被保留以供人工复核。Maximum Detail 重试后的质量检查报错也会记录为“质量检查失败”，并保留该结构有效输出供人工复核。重试编码失败、取消或意外异常时会恢复先前的 Best Detail 输出并保留成功结果与重试失败审计；只有恢复本身失败才会标记失败。

每次任务结束后，输出目录会生成一份 CSV 报告：

```text
compression_report_YYYYMMDD_HHMMSS.csv
```

报告包含源文件、输出文件、状态、失败原因、压缩前后大小、节省比例、音频状态、`encoding_mode`、CRF、preset、`target_video_bitrate_kbps`、`target_fps`、`content_complexity`、`content_complexity_score` 等信息。Auto Detail 还记录 `auto_selected_profile`、风险和源文件指标、峰值/细节/运动分析指标、`target_gop`、`quality_check_status`、`ssim_score`、`detail_retention_percent`、`quality_retry_count`、`quality_retry_reason` 与 `final_selected_profile`，方便人工复核。

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

本工具不提供云上传、剪辑、水印等功能。视频输出统一为 MP4 + AAC 96k，并提供 H.264 兼容模式和 H.265 小文件模式：

```text
Standard:
H.264 / libx264, preset slow, CRF 23,
maxrate 3500k, bufsize 7000k,
AAC 96k, 48000 Hz, 双声道, MP4 + faststart

High Motion:
H.264 / libx264, preset slow, CRF 21,
maxrate 5500k, bufsize 11000k,
AAC 96k, 48000 Hz, 双声道, MP4 + faststart

Screen Safe - High Motion:
H.264 / libx264, preset slow, CRF 21,
profile main, GOP 30, maxrate 6500k, bufsize 12000k,
tune fastdecode, no B-frames, refs 2,
AAC 96k, 48000 Hz, 双声道, MP4 + faststart

H.265 Production - Best Detail:
H.265 / libx265, preset slow, Main Profile,
25fps, GOP 250, hvc1 MP4 tag,
固定使用 Complex 目标视频码率,
AAC 96k, 48000 Hz, 双声道, MP4 + faststart

H.265 Production - Best Detail (2-pass):
H.265 / libx265, preset slow, Main Profile,
25fps, GOP 250, hvc1 MP4 tag,
第一遍分析视频，第二遍正式输出 MP4,
固定使用 Complex 目标视频码率,
AAC 96k, 48000 Hz, 双声道, MP4 + faststart

H.265 Production - Auto Detail (2-pass):
H.265 / libx265, preset slow, Main Profile,
自动选择 best_detail_2pass 或 maximum_detail_2pass，
best_detail_2pass 使用现有 Best Detail (2-pass) 参数。
maximum_detail_2pass 使用 2000k / 2600k / 3200k 目标视频码率，30fps 源优先保留 30fps，GOP 60，maxrate=target*2，bufsize=target*4，并启用 rc-lookahead=50, aq-mode=3, psy-rd=2.0 等细节保护参数。
生产细节分析按 DAR/SAR 和旋转元数据确定的显示方向与宽高比，使用 320 像素长边的等比例灰度帧、2fps；长源取开头/中间/结尾三段。Auto Detail 的 Best/Maximum 目标码率和 `portrait_screen` 风险也按该显示几何选择，因此编码为横屏尺寸但带 90/270 度旋转的素材使用竖屏档位。结构验证要求显示方向与宽高比等价（相对误差不超过 1%），并禁止降低编码像素总数；输出质量检查使用相同的显示几何，SSIM 对 FFmpeg 自动旋转后的正向画面进行统一尺寸比较。分析空间细节、细节瓦片、运动和场景变化，并使用 1 秒/2 秒窗口峰值及 P90/P95 指标选择档位。输出检查要求 SSIM >= 0.94；源细节 >= 20 时要求细节保留率 >= 80%。Best Detail 警告或检查失败最多重试一次 Maximum Detail；Maximum Detail 的警告或检查失败只保留其结构有效输出供人工复核。

H.265 Small File:
H.265 / libx265, preset slow, Main Profile,
25fps, GOP 250, hvc1 MP4 tag,
按分辨率和素材复杂度选择目标视频码率,
AAC 96k, 48000 Hz, 双声道, MP4 + faststart

H.265 Smart Auto:
H.265 / libx265, preset slow, Main Profile,
先用 FFmpeg 抽样成 160x90 / 2fps 灰度帧,
计算空间细节、帧间运动和场景变化,
自动映射到 Simple / Standard / Complex 目标码率,
AAC 96k, 48000 Hz, 双声道, MP4 + faststart
```

H.265 Production / Small File / Smart Auto 目标视频码率：

```text
1920x1080 横屏：Simple 450k / Standard 800k / Complex 1200k
1080x1920 竖屏：Simple 500k / Standard 1300k / Complex 1800k
1920x1440 或 1080x2560 高像素屏：Simple 600k / Standard 1400k / Complex 2200k
```

## 打包 Windows 程序

开发人员可在项目目录运行：

```powershell
.\build_windows.ps1
```

构建脚本会在安装依赖和运行 PyInstaller 前确认随包的 `ffmpeg.exe`、`ffprobe.exe` 存在，并确认 FFmpeg 包含 `libx265` 编码器和 `ssim` 过滤器。Windows 专用的真实 FFmpeg smoke test 只会在 Windows 且这两个随包二进制可用时运行；其他系统会跳过该测试，不能据此推断 Windows smoke 已运行。

打包结果位于：

```text
dist/SignageVideoCompressor/SignageVideoCompressor.exe
```
