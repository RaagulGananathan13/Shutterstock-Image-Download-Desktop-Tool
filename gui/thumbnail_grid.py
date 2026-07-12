# thread pool for images so the ui doesnt freeze up
import io
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from typing import Callable
import requests
from PIL import Image, ImageTk, ImageDraw, ImageFont
from gui.widgets import Tooltip
THUMB_WIDTH = 200
THUMB_HEIGHT = 150
THUMB_PADDING = 8
def _create_placeholder_image() -> Image.Image:
    img = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), color=(24, 24, 27))
    draw = ImageDraw.Draw(img)
    text = "Loading..."
    try:
        font = ImageFont.truetype("segoeui.ttf", 15)
    except (OSError, IOError):
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (THUMB_WIDTH - tw) // 2
    y = (THUMB_HEIGHT - th) // 2
    draw.text((x, y), text, fill=(161, 161, 170), font=font)
    return img
def _create_error_image() -> Image.Image:
    img = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), color=(69, 10, 10))
    draw = ImageDraw.Draw(img)
    text = "Failed to load"
    try:
        font = ImageFont.truetype("segoeui.ttf", 13)
    except (OSError, IOError):
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (THUMB_WIDTH - tw) // 2
    y = (THUMB_HEIGHT - th) // 2
    draw.text((x, y), text, fill=(248, 113, 113), font=font)
    return img
def _create_no_results_image() -> Image.Image:
    img = Image.new("RGB", (300, 200), color=(9, 9, 11))
    draw = ImageDraw.Draw(img)
    text = "No results found"
    try:
        font = ImageFont.truetype("segoeui.ttf", 18)
    except (OSError, IOError):
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (300 - tw) // 2
    y = (200 - th) // 2
    draw.text((x, y), text, fill=(161, 161, 170), font=font)
    return img
class ThumbnailGrid(tk.Frame):
    def __init__(self, parent, on_click: Callable | None = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg="#09090b")
        self._on_click = on_click
        self._executor = ThreadPoolExecutor(max_workers=6)
        self._photo_refs: list[ImageTk.PhotoImage] = []  
        self._thumb_labels: list[tk.Label] = []
        self._tooltips: list[Tooltip] = []
        self._placeholder_pil = _create_placeholder_image()
        self._error_pil = _create_error_image()
        self._canvas = tk.Canvas(self, bg="#09090b", highlightthickness=0, bd=0)
        self._scrollbar = tk.Scrollbar(
            self, orient="vertical", command=self._canvas.yview
        )
        self._inner_frame = tk.Frame(self._canvas, bg="#09090b")
        self._inner_frame.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._inner_frame, anchor="nw"
        )
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._canvas.bind("<Enter>", self._bind_mousewheel)
        self._canvas.bind("<Leave>", self._unbind_mousewheel)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
    def _bind_mousewheel(self, event=None):
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
    def _unbind_mousewheel(self, event=None):
        self._canvas.unbind_all("<MouseWheel>")
    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(-1 * (event.delta // 120), "units")
    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)
    def clear(self):
        self._photo_refs.clear()
        self._thumb_labels.clear()
        self._tooltips.clear()
        for widget in self._inner_frame.winfo_children():
            widget.destroy()
        self._canvas.yview_moveto(0)
    def show_no_results(self):
        self.clear()
        no_results_img = _create_no_results_image()
        photo = ImageTk.PhotoImage(no_results_img)
        self._photo_refs.append(photo)
        label = tk.Label(
            self._inner_frame,
            image=photo,
            bg="#09090b",
            bd=0,
        )
        label.pack(pady=50)
    def show_message(self, text: str):
        self.clear()
        label = tk.Label(
            self._inner_frame,
            text=text,
            bg="#09090b",
            fg="#a1a1aa",
            font=("Segoe UI", 15),
            wraplength=400,
            justify="center",
        )
        label.pack(pady=80)
    def populate(self, images: list[dict]):
        self.clear()
        if not images:
            self.show_no_results()
            return
        canvas_width = self._canvas.winfo_width()
        if canvas_width < 100:
            canvas_width = 880  
        num_cols = max(1, canvas_width // (THUMB_WIDTH + THUMB_PADDING * 2))
        for idx, img_data in enumerate(images):
            row = idx // num_cols
            col = idx % num_cols
            cell_frame = tk.Frame(
                self._inner_frame,
                bg="#09090b",
                padx=THUMB_PADDING,
                pady=THUMB_PADDING,
            )
            cell_frame.grid(row=row, column=col, sticky="nsew")
            placeholder_photo = ImageTk.PhotoImage(self._placeholder_pil)
            self._photo_refs.append(placeholder_photo)
            label = tk.Label(
                cell_frame,
                image=placeholder_photo,
                bg="#18181b",
                cursor="hand2",
                bd=2,
                relief="flat",
                highlightthickness=0,
            )
            label.pack()
            description = img_data.get("description", "") or ""
            image_id = img_data.get("id", "unknown")
            tooltip_text = f"ID: {image_id}\n{description[:120]}"
            tooltip = Tooltip(label, tooltip_text)
            self._tooltips.append(tooltip)
            label.bind("<Enter>", lambda e, lbl=label: lbl.config(relief="solid", bd=2, highlightbackground="#e11d48"))
            label.bind("<Leave>", lambda e, lbl=label: lbl.config(relief="flat", bd=2, highlightbackground="#18181b"))
            if self._on_click:
                label.bind(
                    "<Button-1>",
                    lambda e, data=img_data: self._on_click(data),
                )
            self._thumb_labels.append(label)
            thumb_url = self._get_thumbnail_url(img_data)
            if thumb_url:
                self._executor.submit(
                    self._load_thumbnail, thumb_url, label, idx
                )
        for c in range(num_cols):
            self._inner_frame.columnconfigure(c, weight=1)
    def _get_thumbnail_url(self, img_data: dict) -> str | None:
        assets = img_data.get("assets", {})
        preview = assets.get("preview", {})
        if preview and preview.get("url"):
            return preview["url"]
        large_thumb = assets.get("large_thumb", {})
        if large_thumb and large_thumb.get("url"):
            return large_thumb["url"]
        huge_thumb = assets.get("huge_thumb", {})
        if huge_thumb and huge_thumb.get("url"):
            return huge_thumb["url"]
        return None
    def _load_thumbnail(self, url: str, label: tk.Label, index: int):
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
            img.thumbnail((THUMB_WIDTH, THUMB_HEIGHT), Image.Resampling.LANCZOS)
            padded = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), (24, 24, 27))
            offset_x = (THUMB_WIDTH - img.width) // 2
            offset_y = (THUMB_HEIGHT - img.height) // 2
            padded.paste(img, (offset_x, offset_y))
            photo = ImageTk.PhotoImage(padded)
            label.after(0, self._update_label_image, label, photo)
        except Exception:
            error_photo = ImageTk.PhotoImage(self._error_pil)
            label.after(0, self._update_label_image, label, error_photo)
    def _update_label_image(self, label: tk.Label, photo: ImageTk.PhotoImage):
        try:
            label.config(image=photo)
            self._photo_refs.append(photo)
        except tk.TclError:
            pass
    def destroy(self):
        self._executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()