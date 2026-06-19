from __future__ import annotations

import logging
import os
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from audio_check import detect_volume
from encoder import Encoder, build_output_path
from ffmpeg_utils import (
    FFmpegError,
    find_ffmpeg_paths,
    probe_video,
    validate_ffmpeg_bin_dir,
)
from localization import DEFAULT_LANGUAGE, Localizer
from models import CompressionResult, FFmpegPaths, VideoJob
from report import write_report
from settings import (
    AUDIO_CHECK_FAILED,
    AUDIO_NO_AUDIO,
    AUDIO_NORMAL,
    AUDIO_PROBABLY_SILENT,
    COMMON_SCREEN_RESOLUTIONS,
    DEFAULT_ENCODING_MODE,
    DEFAULT_OUTPUT_FOLDER_NAME,
    ENCODING_PRESETS,
    MODE_HIGH_MOTION,
    MODE_STANDARD,
    STATUS_CANCELLED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROBING,
    STATUS_SUCCESS,
    SUPPORTED_EXTENSIONS,
    WINDOW_SIZE,
)


class CompressorWindow(tk.Tk):
    def __init__(self, ffmpeg_paths: FFmpegPaths | None = None) -> None:
        super().__init__()
        self.localizer = Localizer(DEFAULT_LANGUAGE)
        self.title(self.localizer.t("app.title"))
        self.geometry(WINDOW_SIZE)
        self.minsize(1000, 660)

        self.ffmpeg_paths = ffmpeg_paths or find_ffmpeg_paths()
        self.encoder = Encoder(self.ffmpeg_paths) if self.ffmpeg_paths else None
        self.jobs_by_path: dict[Path, VideoJob] = {}
        self.item_by_path: dict[Path, str] = {}
        self.results: list[CompressionResult] = []
        self.ui_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker_thread: threading.Thread | None = None
        self.report_path: Path | None = None
        self.encoding_mode_code = DEFAULT_ENCODING_MODE

        self.output_dir_var = tk.StringVar()
        self.language_var = tk.StringVar()
        self.encoding_mode_var = tk.StringVar()
        self.recursive_var = tk.BooleanVar(value=False)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.detect_silence_var = tk.BooleanVar(value=True)
        self.current_progress_var = tk.DoubleVar(value=0)
        self.total_progress_var = tk.DoubleVar(value=0)

        self._build_widgets()
        self._apply_language()
        self._set_running(False)
        self.after(100, self._poll_queue)
        if not self.ffmpeg_paths:
            self.after(300, self._prompt_ffmpeg_dir)
        else:
            self._log(f"FFmpeg: {self.ffmpeg_paths.ffmpeg}")
            self._log(f"FFprobe: {self.ffmpeg_paths.ffprobe}")

    def _build_widgets(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(outer)
        toolbar.pack(fill=tk.X)

        self.add_files_btn = ttk.Button(toolbar, command=self.add_files)
        self.add_folder_btn = ttk.Button(toolbar, command=self.add_folder)
        self.remove_btn = ttk.Button(toolbar, command=self.remove_selected)
        self.clear_btn = ttk.Button(toolbar, command=self.clear_jobs)
        for button in [self.add_files_btn, self.add_folder_btn, self.remove_btn, self.clear_btn]:
            button.pack(side=tk.LEFT, padx=(0, 8))

        self.language_combo = ttk.Combobox(toolbar, state="readonly", width=18)
        self.language_combo.pack(side=tk.RIGHT)
        self.language_combo.bind("<<ComboboxSelected>>", self._on_language_selected)
        self.language_label = ttk.Label(toolbar)
        self.language_label.pack(side=tk.RIGHT, padx=(0, 8))

        output_frame = ttk.Frame(outer)
        output_frame.pack(fill=tk.X, pady=(10, 8))
        self.output_label = ttk.Label(output_frame)
        self.output_label.pack(side=tk.LEFT)
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_dir_var)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.browse_output_btn = ttk.Button(output_frame, command=self.choose_output_dir)
        self.browse_output_btn.pack(side=tk.LEFT)

        options = ttk.Frame(outer)
        options.pack(fill=tk.X, pady=(0, 8))
        self.quality_mode_label = ttk.Label(options)
        self.quality_mode_label.pack(side=tk.LEFT, padx=(0, 8))
        self.quality_mode_combo = ttk.Combobox(options, state="readonly", width=34)
        self.quality_mode_combo.pack(side=tk.LEFT, padx=(0, 18))
        self.quality_mode_combo.bind("<<ComboboxSelected>>", self._on_quality_mode_selected)
        self.recursive_check = ttk.Checkbutton(options, variable=self.recursive_var)
        self.overwrite_check = ttk.Checkbutton(options, variable=self.overwrite_var)
        self.silence_check = ttk.Checkbutton(options, variable=self.detect_silence_var)
        for check in [self.recursive_check, self.overwrite_check, self.silence_check]:
            check.pack(side=tk.LEFT, padx=(0, 18))

        columns = ("name", "resolution", "duration", "original", "output", "reduction", "audio", "status")
        self.tree = ttk.Treeview(outer, columns=columns, show="headings", height=14)
        widths = {
            "name": 280,
            "resolution": 100,
            "duration": 80,
            "original": 90,
            "output": 90,
            "reduction": 90,
            "audio": 110,
            "status": 170,
        }
        for col in columns:
            self.tree.column(col, width=widths[col], anchor=tk.W)
        self.tree.tag_configure("failed", foreground="#a40000")
        self.tree.tag_configure("warning", foreground="#8a5a00")
        self.tree.tag_configure("success", foreground="#106b21")

        tree_scroll = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        tree_scroll.place(in_=self.tree, relx=1.0, rely=0, relheight=1.0, anchor="ne")

        progress_frame = ttk.Frame(outer)
        progress_frame.pack(fill=tk.X, pady=(10, 8))
        self.current_progress_label = ttk.Label(progress_frame)
        self.current_progress_label.grid(row=0, column=0, sticky="w")
        ttk.Progressbar(progress_frame, variable=self.current_progress_var, maximum=100).grid(
            row=0, column=1, sticky="ew", padx=8
        )
        self.total_progress_label = ttk.Label(progress_frame)
        self.total_progress_label.grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Progressbar(progress_frame, variable=self.total_progress_var, maximum=100).grid(
            row=1, column=1, sticky="ew", padx=8, pady=(6, 0)
        )
        progress_frame.columnconfigure(1, weight=1)

        action_frame = ttk.Frame(outer)
        action_frame.pack(fill=tk.X)
        self.start_btn = ttk.Button(action_frame, command=self.start_compression)
        self.cancel_btn = ttk.Button(action_frame, command=self.cancel_compression)
        self.open_output_btn = ttk.Button(action_frame, command=self.open_output_dir)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.cancel_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.open_output_btn.pack(side=tk.LEFT)

        self.log_frame = ttk.LabelFrame(outer)
        self.log_frame.pack(fill=tk.BOTH, expand=False, pady=(10, 0))
        self.log_text = tk.Text(self.log_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def add_files(self) -> None:
        filenames = filedialog.askopenfilenames(
            title=self.localizer.t("dialog.select_video_files"),
            filetypes=[
                (self.localizer.t("dialog.video_files"), "*.mp4 *.mov *.m4v *.avi *.mkv"),
                (self.localizer.t("dialog.all_files"), "*.*"),
            ],
        )
        self._add_paths([Path(name) for name in filenames])

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title=self.localizer.t("dialog.select_video_folder"))
        if not folder:
            return
        root = Path(folder)
        iterator = root.rglob("*") if self.recursive_var.get() else root.glob("*")
        paths = [path for path in iterator if path.is_file()]
        self._add_paths(paths)

    def _add_paths(self, paths: list[Path]) -> None:
        added = 0
        for path in paths:
            normalized = path.resolve()
            if normalized.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            if any(preset["suffix"] in normalized.stem for preset in ENCODING_PRESETS.values()):
                continue
            if normalized in self.jobs_by_path:
                continue
            output_dir = self._effective_output_dir(normalized)
            job = VideoJob(
                input_path=normalized,
                output_path=build_output_path(
                    normalized,
                    output_dir,
                    self.overwrite_var.get(),
                    encoding_mode=self.encoding_mode_code,
                ),
                original_size_bytes=normalized.stat().st_size if normalized.exists() else 0,
                encoding_mode=self.encoding_mode_code,
            )
            self.jobs_by_path[normalized] = job
            item = self.tree.insert("", tk.END, values=self._row_values(job))
            self.item_by_path[normalized] = item
            added += 1
        if added:
            self._log(self.localizer.t("message.added_files", count=added))
            if not self.output_dir_var.get() and self.jobs_by_path:
                first = next(iter(self.jobs_by_path.values()))
                self.output_dir_var.set(str(first.input_path.parent / DEFAULT_OUTPUT_FOLDER_NAME))

    def remove_selected(self) -> None:
        for item in self.tree.selection():
            path = self._path_for_item(item)
            if path:
                self.jobs_by_path.pop(path, None)
                self.item_by_path.pop(path, None)
            self.tree.delete(item)

    def clear_jobs(self) -> None:
        self.jobs_by_path.clear()
        self.item_by_path.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.current_progress_var.set(0)
        self.total_progress_var.set(0)
        self.results.clear()

    def choose_output_dir(self) -> None:
        folder = filedialog.askdirectory(title=self.localizer.t("dialog.select_output_dir"))
        if folder:
            self.output_dir_var.set(folder)

    def start_compression(self) -> None:
        if not self.jobs_by_path:
            messagebox.showwarning(self.localizer.t("app.title"), self.localizer.t("message.need_files"))
            return
        if not self.ffmpeg_paths:
            self._prompt_ffmpeg_dir()
            if not self.ffmpeg_paths:
                return
        output_dir_text = self.output_dir_var.get().strip()
        if not output_dir_text:
            first = next(iter(self.jobs_by_path.values()))
            output_dir_text = str(first.input_path.parent / DEFAULT_OUTPUT_FOLDER_NAME)
            self.output_dir_var.set(output_dir_text)

        output_dir = Path(output_dir_text)
        self.results.clear()
        self.report_path = None
        self.cancel_event.clear()
        self.current_progress_var.set(0)
        self.total_progress_var.set(0)
        self._set_running(True)

        jobs = list(self.jobs_by_path.values())
        for job in jobs:
            job.encoding_mode = self.encoding_mode_code
            job.output_path = build_output_path(
                job.input_path,
                output_dir,
                self.overwrite_var.get(),
                encoding_mode=job.encoding_mode,
            )
            job.status = STATUS_PENDING
            job.error_message = ""
            job.output_size_bytes = 0
            job.progress = 0
            self._refresh_job(job)

        self.worker_thread = threading.Thread(
            target=self._worker,
            args=(jobs, output_dir, self.overwrite_var.get(), self.detect_silence_var.get()),
            daemon=True,
        )
        self.worker_thread.start()

    def cancel_compression(self) -> None:
        self.cancel_event.set()
        if self.encoder:
            self.encoder.cancel()
        self._log(self.localizer.t("message.cancelling"))

    def open_output_dir(self) -> None:
        folder = Path(self.output_dir_var.get()) if self.output_dir_var.get() else None
        if not folder or not folder.exists():
            messagebox.showinfo(self.localizer.t("app.title"), self.localizer.t("message.output_dir_missing"))
            return
        try:
            if os.name == "nt":
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys_platform() == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as exc:
            messagebox.showerror(
                self.localizer.t("app.title"),
                self.localizer.t("message.open_output_failed", error=exc),
            )

    def _worker(self, jobs: list[VideoJob], output_dir: Path, overwrite: bool, detect_silence_enabled: bool) -> None:
        assert self.ffmpeg_paths is not None
        self.encoder = Encoder(self.ffmpeg_paths)
        completed_count = 0
        total = len(jobs)

        for index, job in enumerate(jobs):
            if self.cancel_event.is_set():
                self._mark_cancelled(job)
                self.ui_queue.put(("job", job))
                self.results.append(
                    CompressionResult(
                        job=job,
                        status="cancelled",
                        error_message=self.localizer.t("message.user_cancelled"),
                    )
                )
                completed_count += 1
                self.ui_queue.put(("total", completed_count / total * 100))
                continue

            try:
                job.status = STATUS_PROBING
                self.ui_queue.put(("job", job))
                info = probe_video(self.ffmpeg_paths.ffprobe, job.input_path)
                job.info = info
                job.source_video_codec = info.video_codec
                job.source_audio_codec = info.audio_codec or ""
                job.original_size_bytes = job.input_path.stat().st_size
                self.ui_queue.put(("job", job))

                if not info.has_audio:
                    job.audio_status = AUDIO_NO_AUDIO
                    job.status = STATUS_FAILED
                    job.error_message = self.localizer.t("error.no_audio")
                    result = CompressionResult(job=job, status="failed", error_message=job.error_message)
                    self.results.append(result)
                    self.ui_queue.put(("job", job))
                    self.ui_queue.put(("log", f"{job.input_path.name}: {job.error_message}"))
                    continue

                if detect_silence_enabled:
                    volume = detect_volume(self.ffmpeg_paths.ffmpeg, job.input_path)
                    job.audio_status = volume.audio_status
                    if volume.audio_status == AUDIO_PROBABLY_SILENT:
                        self.ui_queue.put(("log", self.localizer.t("message.silent_detected", name=job.input_path.name)))
                    elif volume.audio_status == AUDIO_CHECK_FAILED:
                        self.ui_queue.put(("log", self.localizer.t("message.audio_check_failed", name=job.input_path.name)))
                else:
                    job.audio_status = AUDIO_NORMAL
                self.ui_queue.put(("job", job))

                result = self.encoder.encode(
                    job,
                    overwrite=overwrite,
                    cancel_event=self.cancel_event,
                    progress_callback=lambda active_job, progress, base=index: self._progress_from_worker(
                        active_job, progress, base, total
                    ),
                )
                self.results.append(result)
                self.ui_queue.put(("job", job))
                if result.status == "failed":
                    self.ui_queue.put(("log", f"{job.input_path.name}: {result.error_message}"))
            except FFmpegError as exc:
                job.status = STATUS_FAILED
                job.error_message = self.localizer.t("error.probe")
                result = CompressionResult(job=job, status="failed", error_message=f"{job.error_message} {exc}")
                self.results.append(result)
                self.ui_queue.put(("job", job))
                self.ui_queue.put(("log", f"{job.input_path.name}: {result.error_message}"))
            except Exception as exc:  # GUI tools must keep running after unexpected file failures.
                logging.exception("Unexpected compression error")
                job.status = STATUS_FAILED
                job.error_message = str(exc)
                self.results.append(CompressionResult(job=job, status="failed", error_message=str(exc)))
                self.ui_queue.put(("job", job))
                self.ui_queue.put(("log", f"{job.input_path.name}: {exc}"))
            finally:
                completed_count += 1
                self.ui_queue.put(("current", 0))
                self.ui_queue.put(("total", completed_count / total * 100))

        try:
            report_path = write_report(output_dir, self.results)
            self.ui_queue.put(("done", report_path))
        except Exception as exc:
            logging.exception("Failed to write report")
            self.ui_queue.put(("error", self.localizer.t("message.report_failed", error=exc)))

    def _progress_from_worker(self, job: VideoJob, progress: float, completed_base: int, total: int) -> None:
        self.ui_queue.put(("current", progress * 100))
        self.ui_queue.put(("total", (completed_base + progress) / total * 100))
        self.ui_queue.put(("job", job))

    def _poll_queue(self) -> None:
        try:
            while True:
                event, payload = self.ui_queue.get_nowait()
                if event == "job":
                    self._refresh_job(payload)  # type: ignore[arg-type]
                elif event == "log":
                    self._log(str(payload))
                elif event == "current":
                    self.current_progress_var.set(float(payload))
                elif event == "total":
                    self.total_progress_var.set(float(payload))
                elif event == "done":
                    self.report_path = Path(payload)  # type: ignore[arg-type]
                    self._set_running(False)
                    self._log(self.localizer.t("message.report_written", path=self.report_path))
                    success = sum(1 for result in self.results if result.status == "success")
                    failed = sum(1 for result in self.results if result.status == "failed")
                    cancelled = sum(1 for result in self.results if result.status == "cancelled")
                    messagebox.showinfo(
                        self.localizer.t("app.title"),
                        self.localizer.t(
                            "message.done",
                            success=success,
                            failed=failed,
                            cancelled=cancelled,
                            output_dir=self.output_dir_var.get(),
                            report=self.report_path,
                        ),
                    )
                elif event == "error":
                    self._set_running(False)
                    messagebox.showerror(self.localizer.t("app.title"), str(payload))
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _prompt_ffmpeg_dir(self) -> None:
        messagebox.showwarning(self.localizer.t("app.title"), self.localizer.t("error.ffmpeg_not_found"))
        folder = filedialog.askdirectory(title=self.localizer.t("dialog.select_ffmpeg_bin"))
        if not folder:
            self._log(self.localizer.t("message.ffmpeg_not_selected"))
            return
        paths = validate_ffmpeg_bin_dir(Path(folder))
        if not paths:
            messagebox.showerror(self.localizer.t("app.title"), self.localizer.t("message.ffmpeg_bin_invalid"))
            return
        self.ffmpeg_paths = paths
        self.encoder = Encoder(paths)
        self._log(f"FFmpeg: {paths.ffmpeg}")
        self._log(f"FFprobe: {paths.ffprobe}")

    def _set_running(self, running: bool) -> None:
        state = tk.DISABLED if running else tk.NORMAL
        for widget in [
            self.add_files_btn,
            self.add_folder_btn,
            self.remove_btn,
            self.clear_btn,
            self.output_entry,
            self.browse_output_btn,
            self.recursive_check,
            self.overwrite_check,
            self.silence_check,
            self.quality_mode_combo,
            self.start_btn,
        ]:
            widget.configure(state=state)
        self.cancel_btn.configure(state=tk.NORMAL if running else tk.DISABLED)

    def _refresh_job(self, job: VideoJob) -> None:
        item = self.item_by_path.get(job.input_path)
        if not item:
            return
        tags: tuple[str, ...] = ()
        if job.status == STATUS_FAILED:
            tags = ("failed",)
        elif job.status == STATUS_SUCCESS:
            tags = ("success",)
        elif job.audio_status in {AUDIO_PROBABLY_SILENT, AUDIO_CHECK_FAILED}:
            tags = ("warning",)
        self.tree.item(item, values=self._row_values(job), tags=tags)

    def _row_values(self, job: VideoJob) -> tuple[str, str, str, str, str, str, str, str]:
        info = job.info
        resolution = info.resolution if info else ""
        if info and (info.width, info.height) not in COMMON_SCREEN_RESOLUTIONS:
            resolution = f"{resolution} *"
        duration = f"{info.duration_sec:.1f}s" if info and info.duration_sec else ""
        original = self._format_mb(job.original_size_bytes)
        output = self._format_mb(job.output_size_bytes) if job.output_size_bytes else ""
        reduction = self._format_reduction(job.original_size_bytes, job.output_size_bytes)
        audio = self.localizer.audio(job.audio_status)
        status_label = self.localizer.status(job.status)
        status = status_label if not job.error_message else f"{status_label}: {job.error_message}"
        return (job.input_path.name, resolution, duration, original, output, reduction, audio, status)

    def _path_for_item(self, item: str) -> Path | None:
        for path, item_id in self.item_by_path.items():
            if item_id == item:
                return path
        return None

    def _effective_output_dir(self, input_path: Path) -> Path:
        if self.output_dir_var.get().strip():
            return Path(self.output_dir_var.get().strip())
        return input_path.parent / DEFAULT_OUTPUT_FOLDER_NAME

    def _mark_cancelled(self, job: VideoJob) -> None:
        job.status = STATUS_CANCELLED
        job.error_message = self.localizer.t("message.user_cancelled")

    def _log(self, message: str) -> None:
        logging.info(message)
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    @staticmethod
    def _format_mb(size_bytes: int) -> str:
        if size_bytes <= 0:
            return ""
        return f"{size_bytes / 1024 / 1024:.2f} MB"

    @staticmethod
    def _format_reduction(original_bytes: int, output_bytes: int) -> str:
        if original_bytes <= 0 or output_bytes <= 0:
            return ""
        return f"{(1 - output_bytes / original_bytes) * 100:.1f}%"

    def _on_language_selected(self, _event: object | None = None) -> None:
        selected = self.language_var.get()
        for language_code in ("zh_CN", "en_US", "id_ID"):
            if selected == self.localizer.language_name(language_code):
                self.localizer.set_language(language_code)
                break
        self._apply_language()
        for job in self.jobs_by_path.values():
            self._refresh_job(job)

    def _on_quality_mode_selected(self, _event: object | None = None) -> None:
        selected = self.encoding_mode_var.get()
        for mode in (MODE_STANDARD, MODE_HIGH_MOTION):
            if selected == self.localizer.encoding_mode(mode):
                self.encoding_mode_code = mode
                break
        for job in self.jobs_by_path.values():
            if job.status == STATUS_PENDING:
                job.encoding_mode = self.encoding_mode_code
                job.output_path = build_output_path(
                    job.input_path,
                    self._effective_output_dir(job.input_path),
                    self.overwrite_var.get(),
                    encoding_mode=job.encoding_mode,
                )

    def _apply_language(self) -> None:
        t = self.localizer.t
        self.title(t("app.title"))
        self.add_files_btn.configure(text=t("button.add_files"))
        self.add_folder_btn.configure(text=t("button.add_folder"))
        self.remove_btn.configure(text=t("button.remove_selected"))
        self.clear_btn.configure(text=t("button.clear"))
        self.language_label.configure(text=t("label.language"))
        language_values = [self.localizer.language_name(code) for code in ("zh_CN", "en_US", "id_ID")]
        self.language_combo.configure(values=language_values)
        self.language_var.set(self.localizer.language_name(self.localizer.language))
        self.language_combo.configure(textvariable=self.language_var)
        self.output_label.configure(text=t("label.output_dir"))
        self.browse_output_btn.configure(text=t("button.browse"))
        self.quality_mode_label.configure(text=t("label.quality_mode"))
        quality_values = [self.localizer.encoding_mode(mode) for mode in (MODE_STANDARD, MODE_HIGH_MOTION)]
        self.quality_mode_combo.configure(values=quality_values)
        self.encoding_mode_var.set(self.localizer.encoding_mode(self.encoding_mode_code))
        self.quality_mode_combo.configure(textvariable=self.encoding_mode_var)
        self.recursive_check.configure(text=t("option.recursive"))
        self.overwrite_check.configure(text=t("option.overwrite"))
        self.silence_check.configure(text=t("option.detect_silence"))
        for col in self.tree["columns"]:
            self.tree.heading(col, text=t(f"column.{col}"))
        self.current_progress_label.configure(text=t("progress.current"))
        self.total_progress_label.configure(text=t("progress.total"))
        self.start_btn.configure(text=t("button.start"))
        self.cancel_btn.configure(text=t("button.cancel"))
        self.open_output_btn.configure(text=t("button.open_output"))
        self.log_frame.configure(text=t("label.log"))


def sys_platform() -> str:
    import sys

    return sys.platform
