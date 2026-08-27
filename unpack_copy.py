"""Unpack concatenated WebP images stored in a .copy cache file."""

from __future__ import annotations

import argparse
import os
import struct
from pathlib import Path
from typing import Callable


RIFF_WEBP = b"RIFF"
WEBP_MARKER = b"WEBP"
HEADER_SIZE = 12


def settings_path() -> Path:
    app_data = os.environ.get("APPDATA")
    base_dir = Path(app_data) if app_data else Path.home()
    return base_dir / "CopyUnpacker" / "last-output.txt"


def load_last_output() -> str:
    try:
        return settings_path().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def save_last_output(output_dir: str) -> None:
    try:
        config_file = settings_path()
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(output_dir, encoding="utf-8")
    except OSError:
        pass


def find_webp_images(source: Path) -> list[bytes]:
    """Read every valid RIFF/WEBP container from a cache file."""
    data = source.read_bytes()
    images: list[bytes] = []
    offset = 0

    while offset + HEADER_SIZE <= len(data):
        marker = data.find(RIFF_WEBP, offset)
        if marker < 0:
            break
        if data[marker + 8 : marker + 12] != WEBP_MARKER:
            offset = marker + 4
            continue

        declared_size = struct.unpack_from("<I", data, marker + 4)[0]
        image_end = marker + 8 + declared_size
        if declared_size < 4 or image_end > len(data):
            offset = marker + 4
            continue

        images.append(data[marker:image_end])
        offset = image_end

    if not images:
        raise ValueError("没有找到有效的 RIFF/WEBP 图片")
    return images


def unpack_copy(
    source: Path,
    output_dir: Path | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Extract images and return the output directory."""
    if not source.is_file():
        raise FileNotFoundError(f"找不到文件: {source}")

    output_dir = output_dir or source.with_name(f"{source.stem}-webp")
    output_dir.mkdir(parents=True, exist_ok=True)
    images = find_webp_images(source)

    for index, image in enumerate(images, start=1):
        target = output_dir / f"{index:03d}.webp"
        target.write_bytes(image)
        if progress:
            progress(index, len(images))
    return output_dir


def run_gui() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title(".copy 漫画缓存解包器")
    root.geometry("680x300")
    root.minsize(620, 280)

    selected_file = tk.StringVar()
    selected_output = tk.StringVar(value=load_last_output())
    status = tk.StringVar(value="请选择一个 .copy 文件")

    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(5, weight=1)
    ttk.Label(frame, text=".copy 漫画缓存解包器", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(frame, text="当前版本导出为 WebP 图片，不改变原图质量。", padding=(0, 8, 0, 12)).grid(row=1, column=0, sticky="w")

    file_row = ttk.Frame(frame)
    file_row.grid(row=2, column=0, sticky="ew")
    file_row.columnconfigure(0, weight=1)
    ttk.Entry(file_row, textvariable=selected_file, state="readonly").grid(row=0, column=0, sticky="ew")

    def choose_file() -> None:
        path = filedialog.askopenfilename(
            title="选择 .copy 文件",
            filetypes=[("Copy cache", "*.copy"), ("所有文件", "*.*")],
        )
        if path:
            selected_file.set(path)
            status.set("已选择文件，点击“开始解包”")

    ttk.Button(file_row, text="选择文件...", command=choose_file).grid(row=0, column=1, padx=(8, 0))

    output_row = ttk.Frame(frame)
    output_row.grid(row=3, column=0, sticky="ew", pady=(10, 0))
    output_row.columnconfigure(0, weight=1)
    ttk.Entry(output_row, textvariable=selected_output, state="readonly").grid(row=0, column=0, sticky="ew")

    def choose_output() -> None:
        path = filedialog.askdirectory(title="选择图片输出目录")
        if path:
            selected_output.set(path)
            save_last_output(path)
            status.set("输出目录已选择，可以开始解包")

    ttk.Button(output_row, text="选择输出目录...", command=choose_output).grid(row=0, column=1, padx=(8, 0))
    progress = ttk.Progressbar(frame, mode="determinate")
    progress.grid(row=4, column=0, sticky="ew", pady=(18, 8))
    ttk.Label(frame, textvariable=status, wraplength=640).grid(row=5, column=0, sticky="nw")

    def start_unpack() -> None:
        if not selected_file.get():
            messagebox.showwarning("未选择文件", "请先选择一个 .copy 文件。")
            return
        if not selected_output.get():
            messagebox.showwarning("未选择输出目录", "请先选择图片输出目录。")
            return
        source = Path(selected_file.get())
        output_dir = Path(selected_output.get()) / source.stem
        save_last_output(selected_output.get())
        try:
            output = unpack_copy(
                source,
                output_dir,
                progress=lambda current, total: (progress.configure(value=current * 100 / total), status.set(f"正在导出 {current}/{total}")),
            )
        except (OSError, ValueError) as error:
            messagebox.showerror("解包失败", str(error))
            status.set("解包失败")
            return
        status.set(f"完成：共导出图片到 {output}")
        messagebox.showinfo("解包完成", f"已导出图片：{output}")

    ttk.Button(frame, text="开始解包", command=start_unpack).grid(row=6, column=0, sticky="e", pady=(12, 0))
    root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="解包《拷贝漫画》.copy 缓存中的 WebP 图片")
    parser.add_argument("file", nargs="?", type=Path, help=".copy 文件；不填则打开图形界面")
    parser.add_argument("-o", "--output", type=Path, help="输出目录")
    args = parser.parse_args()

    if args.file:
        output = unpack_copy(args.file, args.output)
        print(f"已导出 {len(list(output.glob('*.webp')))} 张图片到：{output}")
    else:
        run_gui()


if __name__ == "__main__":
    main()