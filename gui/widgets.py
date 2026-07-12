"""
gui/widgets.py — Small reusable Tkinter widgets.

- StatusBar: label showing the last action outcome
- DownloadProgressBar: ttk.Progressbar that shows/hides dynamically
- Tooltip: hover tooltip for thumbnail descriptions
"""

import tkinter as tk
from tkinter import ttk


# ---------------------------------------------------------------------------
# StatusBar
# ---------------------------------------------------------------------------

class StatusBar(tk.Frame):
    """A single-line status bar at the bottom of the window."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._label = tk.Label(
            self,
            text="Ready",
            anchor="w",
            padx=8,
            pady=4,
            font=("Segoe UI", 9),
            fg="#e0e0e0",
            bg="#1e1e2e",
        )
        self._label.pack(fill="x", expand=True)
        self.configure(bg="#1e1e2e")

    def set_status(self, text: str, color: str = "#e0e0e0") -> None:
        """Update the status text and optionally the text color."""
        self._label.config(text=text, fg=color)

    def set_error(self, text: str) -> None:
        """Show an error message in red."""
        self.set_status(f"⚠ {text}", color="#ff6b6b")

    def set_success(self, text: str) -> None:
        """Show a success message in green."""
        self.set_status(f"✓ {text}", color="#51cf66")

    def set_info(self, text: str) -> None:
        """Show an info message in default color."""
        self.set_status(text, color="#e0e0e0")


# ---------------------------------------------------------------------------
# DownloadProgressBar
# ---------------------------------------------------------------------------

class DownloadProgressBar(tk.Frame):
    """A progress bar row that shows/hides as needed during downloads."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg="#1e1e2e")

        self._label = tk.Label(
            self,
            text="",
            anchor="w",
            padx=8,
            font=("Segoe UI", 9),
            fg="#b0b0d0",
            bg="#1e1e2e",
        )
        self._label.pack(fill="x", padx=(8, 8), pady=(2, 0))

        self._style = ttk.Style()
        self._style.theme_use("clam")
        self._style.configure(
            "Download.Horizontal.TProgressbar",
            troughcolor="#2a2a3e",
            background="#7c5cfc",
            thickness=18,
            borderwidth=0,
        )

        self._progress = ttk.Progressbar(
            self,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            style="Download.Horizontal.TProgressbar",
        )
        self._progress.pack(fill="x", padx=8, pady=(2, 6))

        # Start hidden
        self.pack_forget()

    def show(self, label_text: str = "Downloading...") -> None:
        """Make the progress bar visible."""
        self._label.config(text=label_text)
        self._progress["value"] = 0
        self.pack(fill="x", side="bottom")

    def hide(self) -> None:
        """Hide the progress bar."""
        self.pack_forget()

    def update_progress(self, bytes_downloaded: int, total_bytes: int) -> None:
        """Update the progress bar value."""
        if total_bytes > 0:
            pct = min(100, int(bytes_downloaded / total_bytes * 100))
            self._progress["value"] = pct
            mb_done = bytes_downloaded / (1024 * 1024)
            mb_total = total_bytes / (1024 * 1024)
            self._label.config(
                text=f"Downloading... {mb_done:.1f} / {mb_total:.1f} MB ({pct}%)"
            )
        else:
            # Unknown total — use indeterminate-like display
            mb_done = bytes_downloaded / (1024 * 1024)
            self._label.config(text=f"Downloading... {mb_done:.1f} MB")
            self._progress["mode"] = "indeterminate"
            self._progress.step(2)


# ---------------------------------------------------------------------------
# Tooltip
# ---------------------------------------------------------------------------

class Tooltip:
    """
    A lightweight hover tooltip for any Tkinter widget.

    Usage:
        Tooltip(some_widget, "This is the tooltip text")
    """

    def __init__(self, widget: tk.Widget, text: str):
        self._widget = widget
        self._text = text
        self._tip_window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def update_text(self, text: str) -> None:
        """Change the tooltip text."""
        self._text = text

    def _show(self, event=None):
        if self._tip_window or not self._text:
            return
        # Position slightly below and to the right of the widget
        x = self._widget.winfo_rootx() + 20
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 5

        self._tip_window = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)

        label = tk.Label(
            tw,
            text=self._text,
            justify="left",
            background="#2a2a3e",
            foreground="#e0e0e0",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
            wraplength=350,
        )
        label.pack()

    def _hide(self, event=None):
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None
