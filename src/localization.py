from __future__ import annotations

import locale
from dataclasses import dataclass


DEFAULT_LANGUAGE = "zh_CN"
SUPPORTED_LANGUAGES = ("zh_CN", "en_US", "id_ID")


TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh_CN": {
        "app.title": "广告屏视频压缩工具",
        "language.zh_CN": "中文",
        "language.en_US": "English",
        "language.id_ID": "Bahasa Indonesia",
        "label.language": "界面语言",
        "button.add_files": "添加文件",
        "button.add_folder": "添加文件夹",
        "button.remove_selected": "移除选中",
        "button.clear": "清空列表",
        "button.browse": "浏览",
        "button.start": "开始压缩",
        "button.cancel": "取消",
        "button.open_output": "打开输出目录",
        "label.output_dir": "输出目录",
        "option.recursive": "递归扫描子文件夹",
        "option.overwrite": "覆盖已存在输出文件",
        "option.detect_silence": "检测疑似静音音轨",
        "column.name": "文件名",
        "column.resolution": "分辨率",
        "column.duration": "时长",
        "column.original": "原始大小",
        "column.output": "输出大小",
        "column.reduction": "节省比例",
        "column.audio": "音频状态",
        "column.status": "状态",
        "progress.current": "当前文件",
        "progress.total": "总进度",
        "label.log": "日志",
        "dialog.select_video_files": "选择视频文件",
        "dialog.video_files": "视频文件",
        "dialog.all_files": "所有文件",
        "dialog.select_video_folder": "选择视频文件夹",
        "dialog.select_output_dir": "选择输出目录",
        "dialog.select_ffmpeg_bin": "选择 FFmpeg bin 目录",
        "message.added_files": "已添加 {count} 个视频文件。",
        "message.need_files": "请先添加需要压缩的视频文件。",
        "message.cancelling": "正在取消任务...",
        "message.output_dir_missing": "输出目录还不存在。",
        "message.open_output_failed": "无法打开输出目录：{error}",
        "message.silent_detected": "{name}: 检测到疑似静音音轨。",
        "message.audio_check_failed": "{name}: 音频检测失败，继续压缩。",
        "message.report_written": "报告已生成：{path}",
        "message.done": "处理完成。\n成功：{success}\n失败：{failed}\n取消：{cancelled}\n输出目录：{output_dir}\n报告：{report}",
        "message.ffmpeg_not_selected": "未选择 FFmpeg bin 目录，压缩功能暂不可用。",
        "message.ffmpeg_bin_invalid": "所选目录中没有找到 ffmpeg 和 ffprobe。",
        "message.report_failed": "报告生成失败：{error}",
        "message.unhandled_error": "程序发生异常，但窗口会继续保留日志。\n{error}",
        "message.user_cancelled": "用户取消任务。",
        "error.no_audio": "源文件无音轨。当前生产规范要求保留音频，请更换带音频的源文件。",
        "error.probe": "无法读取视频信息，请确认文件未损坏，且格式受 FFmpeg 支持。",
        "error.ffmpeg_not_found": "未找到 FFmpeg。请确认程序目录下包含 tools/ffmpeg/bin/ffmpeg.exe 和 ffprobe.exe，或手动选择 FFmpeg bin 目录。",
        "status.pending": "等待中",
        "status.probing": "读取信息",
        "status.processing": "处理中",
        "status.success": "成功",
        "status.failed": "失败",
        "status.skipped": "已跳过",
        "status.cancelled": "已取消",
        "audio.unchecked": "未检测",
        "audio.normal": "正常",
        "audio.no_audio": "无音轨",
        "audio.probably_silent": "疑似静音",
        "audio.check_failed": "音频检测失败",
    },
    "en_US": {
        "app.title": "Signage Video Compressor",
        "language.zh_CN": "中文",
        "language.en_US": "English",
        "language.id_ID": "Bahasa Indonesia",
        "label.language": "Language",
        "button.add_files": "Add Files",
        "button.add_folder": "Add Folder",
        "button.remove_selected": "Remove Selected",
        "button.clear": "Clear List",
        "button.browse": "Browse",
        "button.start": "Start Compression",
        "button.cancel": "Cancel",
        "button.open_output": "Open Output Folder",
        "label.output_dir": "Output Folder",
        "option.recursive": "Scan Subfolders",
        "option.overwrite": "Overwrite Existing Output",
        "option.detect_silence": "Detect Probably Silent Audio",
        "column.name": "File Name",
        "column.resolution": "Resolution",
        "column.duration": "Duration",
        "column.original": "Original Size",
        "column.output": "Output Size",
        "column.reduction": "Saved",
        "column.audio": "Audio Status",
        "column.status": "Status",
        "progress.current": "Current File",
        "progress.total": "Total Progress",
        "label.log": "Log",
        "dialog.select_video_files": "Select Video Files",
        "dialog.video_files": "Video Files",
        "dialog.all_files": "All Files",
        "dialog.select_video_folder": "Select Video Folder",
        "dialog.select_output_dir": "Select Output Folder",
        "dialog.select_ffmpeg_bin": "Select FFmpeg bin Folder",
        "message.added_files": "Added {count} video file(s).",
        "message.need_files": "Please add video files first.",
        "message.cancelling": "Cancelling task...",
        "message.output_dir_missing": "The output folder does not exist yet.",
        "message.open_output_failed": "Unable to open output folder: {error}",
        "message.silent_detected": "{name}: probably silent audio detected.",
        "message.audio_check_failed": "{name}: audio check failed; continuing compression.",
        "message.report_written": "Report created: {path}",
        "message.done": "Processing complete.\nSuccess: {success}\nFailed: {failed}\nCancelled: {cancelled}\nOutput folder: {output_dir}\nReport: {report}",
        "message.ffmpeg_not_selected": "No FFmpeg bin folder selected. Compression is unavailable for now.",
        "message.ffmpeg_bin_invalid": "The selected folder does not contain both ffmpeg and ffprobe.",
        "message.report_failed": "Failed to create report: {error}",
        "message.unhandled_error": "The application encountered an error, but the log window will remain available.\n{error}",
        "message.user_cancelled": "Cancelled by user.",
        "error.no_audio": "The source file has no audio stream. Current production rules require audio. Please use a source file with audio.",
        "error.probe": "Unable to read video information. Please check whether the file is damaged or unsupported by FFmpeg.",
        "error.ffmpeg_not_found": "FFmpeg was not found. Make sure tools/ffmpeg/bin/ffmpeg.exe and ffprobe.exe exist, or select the FFmpeg bin folder manually.",
        "status.pending": "Pending",
        "status.probing": "Reading Info",
        "status.processing": "Processing",
        "status.success": "Success",
        "status.failed": "Failed",
        "status.skipped": "Skipped",
        "status.cancelled": "Cancelled",
        "audio.unchecked": "Not Checked",
        "audio.normal": "Normal",
        "audio.no_audio": "No Audio",
        "audio.probably_silent": "Probably Silent",
        "audio.check_failed": "Audio Check Failed",
    },
    "id_ID": {
        "app.title": "Kompresor Video Signage",
        "language.zh_CN": "中文",
        "language.en_US": "English",
        "language.id_ID": "Bahasa Indonesia",
        "label.language": "Bahasa",
        "button.add_files": "Tambah File",
        "button.add_folder": "Tambah Folder",
        "button.remove_selected": "Hapus Terpilih",
        "button.clear": "Bersihkan Daftar",
        "button.browse": "Pilih",
        "button.start": "Mulai Kompresi",
        "button.cancel": "Batal",
        "button.open_output": "Buka Folder Output",
        "label.output_dir": "Folder Output",
        "option.recursive": "Pindai Subfolder",
        "option.overwrite": "Timpa Output yang Ada",
        "option.detect_silence": "Deteksi Audio Diduga Senyap",
        "column.name": "Nama File",
        "column.resolution": "Resolusi",
        "column.duration": "Durasi",
        "column.original": "Ukuran Asli",
        "column.output": "Ukuran Output",
        "column.reduction": "Penghematan",
        "column.audio": "Status Audio",
        "column.status": "Status",
        "progress.current": "File Saat Ini",
        "progress.total": "Progres Total",
        "label.log": "Log",
        "dialog.select_video_files": "Pilih File Video",
        "dialog.video_files": "File Video",
        "dialog.all_files": "Semua File",
        "dialog.select_video_folder": "Pilih Folder Video",
        "dialog.select_output_dir": "Pilih Folder Output",
        "dialog.select_ffmpeg_bin": "Pilih Folder bin FFmpeg",
        "message.added_files": "{count} file video ditambahkan.",
        "message.need_files": "Tambahkan file video terlebih dahulu.",
        "message.cancelling": "Membatalkan tugas...",
        "message.output_dir_missing": "Folder output belum ada.",
        "message.open_output_failed": "Tidak dapat membuka folder output: {error}",
        "message.silent_detected": "{name}: audio diduga senyap terdeteksi.",
        "message.audio_check_failed": "{name}: pemeriksaan audio gagal; kompresi dilanjutkan.",
        "message.report_written": "Laporan dibuat: {path}",
        "message.done": "Proses selesai.\nBerhasil: {success}\nGagal: {failed}\nDibatalkan: {cancelled}\nFolder output: {output_dir}\nLaporan: {report}",
        "message.ffmpeg_not_selected": "Folder bin FFmpeg tidak dipilih. Kompresi belum tersedia.",
        "message.ffmpeg_bin_invalid": "Folder yang dipilih tidak berisi ffmpeg dan ffprobe.",
        "message.report_failed": "Gagal membuat laporan: {error}",
        "message.unhandled_error": "Aplikasi mengalami error, tetapi jendela log tetap tersedia.\n{error}",
        "message.user_cancelled": "Dibatalkan oleh pengguna.",
        "error.no_audio": "File sumber tidak memiliki audio. Aturan produksi saat ini mewajibkan audio. Gunakan file sumber yang memiliki audio.",
        "error.probe": "Tidak dapat membaca informasi video. Periksa apakah file rusak atau tidak didukung FFmpeg.",
        "error.ffmpeg_not_found": "FFmpeg tidak ditemukan. Pastikan tools/ffmpeg/bin/ffmpeg.exe dan ffprobe.exe tersedia, atau pilih folder bin FFmpeg secara manual.",
        "status.pending": "Menunggu",
        "status.probing": "Membaca Info",
        "status.processing": "Memproses",
        "status.success": "Berhasil",
        "status.failed": "Gagal",
        "status.skipped": "Dilewati",
        "status.cancelled": "Dibatalkan",
        "audio.unchecked": "Belum Diperiksa",
        "audio.normal": "Normal",
        "audio.no_audio": "Tanpa Audio",
        "audio.probably_silent": "Diduga Senyap",
        "audio.check_failed": "Pemeriksaan Audio Gagal",
    },
}


def normalize_language(language: str | None) -> str:
    if not language:
        return DEFAULT_LANGUAGE
    language = language.replace("-", "_")
    if language in SUPPORTED_LANGUAGES:
        return language
    prefix = language.split("_", 1)[0].lower()
    if prefix == "zh":
        return "zh_CN"
    if prefix == "en":
        return "en_US"
    if prefix in {"id", "in"}:
        return "id_ID"
    return DEFAULT_LANGUAGE


def detect_system_language() -> str:
    language, _ = locale.getlocale()
    return normalize_language(language)


@dataclass
class Localizer:
    language: str = DEFAULT_LANGUAGE

    def __post_init__(self) -> None:
        self.language = normalize_language(self.language)

    def set_language(self, language: str) -> None:
        self.language = normalize_language(language)

    def t(self, key: str, **kwargs: object) -> str:
        value = TRANSLATIONS.get(self.language, {}).get(key)
        if value is None:
            value = TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
        if kwargs:
            return value.format(**kwargs)
        return value

    def language_name(self, language: str) -> str:
        return self.t(f"language.{normalize_language(language)}")

    def status(self, status_code: str) -> str:
        return self.t(f"status.{status_code}")

    def audio(self, audio_status: str) -> str:
        return self.t(f"audio.{audio_status}")
