"""
gui/thumbnail_grid.py — Scrollable grid of clickable thumbnail images.

Loads thumbnails asynchronously via a ThreadPoolExecutor (max 6 workers).
Shows a placeholder while loading. Highlights on hover. Emits a callback on click.
"""

import io
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import requests
from PIL import Image, ImageTk, ImageDraw, ImageFont

from gui.widgets import Tooltip

# Thumbnail display size (pixels)
THUMB_WIDTH = 200
THUMB_HEIGHT = 150
THUMB_PADDING = 8


def _create_placeholder_image() -> Image.Image:
    """Create a simple gray placeholder image with 'Loading...' text."""
    img = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), color=(42, 42, 62))
    draw = ImageDraw.Draw(img)
    text = "Loading..."
    try:
        font = ImageFont.truetype("segoeui.ttf", 14)
    except (OSError, IOError):
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (THUMB_WIDTH - tw) // 2
    y = (THUMB_HEIGHT - th) // 2
    draw.text((x, y), text, fill=(160, 160, 200), font=font)
    return img


def _create_error_image() -> Image.Image:
    """Create an error placeholder for failed thumbnail loads."""
    img = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), color=(62, 30, 30))
    draw = ImageDraw.Draw(img)
    text = "Failed to load"
    try:
        font = ImageFont.truetype("segoeui.ttf", 12)
    except (OSError, IOError):
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (THUMB_WIDTH - tw) // 2
    y = (THUMB_HEIGHT - th) // 2
    draw.text((x, y), text, fill=(200, 100, 100), font=font)
    return img


def _create_no_results_image() -> Image.Image:
    """Create a 'No results' placeholder."""
    img = Image.new("RGB", (300, 200), color=(30, 30, 46))
    draw = ImageDraw.Draw(img)
    text = "No results found"
    try:
        font = ImageFont.truetype("segoeui.ttf", 16)
    except (OSError, IOError):
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (300 - tw) // 2
    y = (200 - th) // 2
    draw.text((x, y), text, fill=(160, 160, 200), font=font)
    return img


class ThumbnailGrid(tk.Frame):
    """
    A scrollable frame containing a grid of clickable thumbnail images.

    Parameters:
        parent: parent Tkinter widget
        on_click: callback(image_data: dict) called when a thumbnail is clicked
    """

    def __init__(self, parent, on_click: Callable | None = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg="#1e1e2e")
        self._on_click = on_click
        self._executor = ThreadPoolExecutor(max_workers=6)
        self._photo_refs: list[ImageTk.PhotoImage] = []  # prevent GC
        self._thumb_labels: list[tk.Label] = []
        self._tooltips: list[Tooltip] = []

        # Placeholder and error images (created once, reused)
        self._placeholder_pil = _create_placeholder_image()
        self._error_pil = _create_error_image()

        # Scrollable canvas setup
        self._canvas = tk.Canvas(self, bg="#1e1e2e", highlightthickness=0, bd=0)
        self._scrollbar = tk.Scrollbar(
            self, orient="vertical", command=self._canvas.yview
        )
        self._inner_frame = tk.Frame(self._canvas, bg="#1e1e2e")

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

        # Bind mousewheel scrolling
        self._canvas.bind("<Enter>", self._bind_mousewheel)
        self._canvas.bind("<Leave>", self._unbind_mousewheel)

        # Resize columns on canvas width change
        self._canvas.bind("<Configure>", self._on_canvas_configure)

    def _bind_mousewheel(self, event=None):
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event=None):
        self._canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _on_canvas_configure(self, event):
        # Make inner frame fill the canvas width
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    def clear(self):
        """Remove all thumbnails from the grid."""
        self._photo_refs.clear()
        self._thumb_labels.clear()
        self._tooltips.clear()
        for widget in self._inner_frame.winfo_children():
            widget.destroy()
        self._canvas.yview_moveto(0)

    def show_no_results(self):
        """Display a 'No results found' message in the grid area."""
        self.clear()
        no_results_img = _create_no_results_image()
        photo = ImageTk.PhotoImage(no_results_img)
        self._photo_refs.append(photo)
        label = tk.Label(
            self._inner_frame,
            image=photo,
            bg="#1e1e2e",
            bd=0,
        )
        label.pack(pady=50)

    def show_message(self, text: str):
        """Display a custom text message in the grid area."""
        self.clear()
        label = tk.Label(
            self._inner_frame,
            text=text,
            bg="#1e1e2e",
            fg="#b0b0d0",
            font=("Segoe UI", 14),
            wraplength=400,
            justify="center",
        )
        label.pack(pady=80)

    def populate(self, images: list[dict]):
        """
        Populate the grid with image data from the API response.

        Each dict in `images` should have:
          - 'id': str
          - 'description': str
          - 'assets': dict with 'preview' or 'large_thumb' containing 'url'
        """
        self.clear()

        if not images:
            self.show_no_results()
            return

        # Calculate number of columns based on current canvas width
        canvas_width = self._canvas.winfo_width()
        if canvas_width < 100:
            canvas_width = 880  # fallback before first render
        num_cols = max(1, canvas_width // (THUMB_WIDTH + THUMB_PADDING * 2))

        for idx, img_data in enumerate(images):
            row = idx // num_cols
            col = idx % num_cols

            # Create a frame for each thumbnail cell
            cell_frame = tk.Frame(
                self._inner_frame,
                bg="#1e1e2e",
                padx=THUMB_PADDING,
                pady=THUMB_PADDING,
            )
            cell_frame.grid(row=row, column=col, sticky="nsew")

            # Placeholder image
            placeholder_photo = ImageTk.PhotoImage(self._placeholder_pil)
            self._photo_refs.append(placeholder_photo)

            label = tk.Label(
                cell_frame,
                image=placeholder_photo,
                bg="#2a2a3e",
                cursor="hand2",
                bd=2,
                relief="flat",
                highlightthickness=0,
            )
            label.pack()

            # Description and ID for tooltip
            description = img_data.get("description", "") or ""
            image_id = img_data.get("id", "unknown")
            tooltip_text = f"ID: {image_id}\n{description[:120]}"
            tooltip = Tooltip(label, tooltip_text)
            self._tooltips.append(tooltip)

            # Hover effects
            label.bind("<Enter>", lambda e, lbl=label: lbl.config(relief="solid", bd=2, highlightbackground="#7c5cfc"))
            label.bind("<Leave>", lambda e, lbl=label: lbl.config(relief="flat", bd=2, highlightbackground="#2a2a3e"))

            # Click handler
            if self._on_click:
                label.bind(
                    "<Button-1>",
                    lambda e, data=img_data: self._on_click(data),
                )

            self._thumb_labels.append(label)

            # Start async thumbnail loading
            thumb_url = self._get_thumbnail_url(img_data)
            if thumb_url:
                self._executor.submit(
                    self._load_thumbnail, thumb_url, label, idx
                )

        # Configure column weights for centering
        for c in range(num_cols):
            self._inner_frame.columnconfigure(c, weight=1)

    def _get_thumbnail_url(self, img_data: dict) -> str | None:
        """Extract the best available thumbnail URL from image data."""
        assets = img_data.get("assets", {})
        # Prefer preview (watermarked 450px), fallback to large_thumb (150px)
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
        """Download a thumbnail image and update the label (called from thread pool)."""
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
            img.thumbnail((THUMB_WIDTH, THUMB_HEIGHT), Image.Resampling.LANCZOS)

            # Pad to exact THUMB_WIDTH x THUMB_HEIGHT with dark background
            padded = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), (42, 42, 62))
            offset_x = (THUMB_WIDTH - img.width) // 2
            offset_y = (THUMB_HEIGHT - img.height) // 2
            padded.paste(img, (offset_x, offset_y))

            photo = ImageTk.PhotoImage(padded)

            # Schedule UI update on main thread
            label.after(0, self._update_label_image, label, photo)
        except Exception:
            # Show error placeholder
            error_photo = ImageTk.PhotoImage(self._error_pil)
            label.after(0, self._update_label_image, label, error_photo)

    def _update_label_image(self, label: tk.Label, photo: ImageTk.PhotoImage):
        """Update a label's image on the main thread."""
        try:
            label.config(image=photo)
            # Keep a reference to prevent garbage collection
            self._photo_refs.append(photo)
        except tk.TclError:
            # Widget was destroyed (e.g. user navigated away)
            pass

    def destroy(self):
        """Clean up the thread pool on widget destruction."""
        self._executor.shutdown(wait=False, cancel_futures=True)
        super().destroy()
