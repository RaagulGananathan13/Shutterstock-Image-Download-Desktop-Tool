# custom widgets because default ttk looks like windows 95
import tkinter as tk
from tkinter import ttk
class StatusBar(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._label = tk.Label(
            self,
            text="Ready",
            anchor="w",
            padx=8,
            pady=6,
            font=("Segoe UI", 10),
            fg="#a1a1aa",
            bg="#18181b",
        )
        self._label.pack(fill="x", expand=True)
        self.configure(bg="#18181b")
    def set_status(self, text: str, color: str = "#a1a1aa") -> None:
        self._label.config(text=text, fg=color)
    def set_error(self, text: str) -> None:
        self.set_status(f"⚠ {text}", color="#ef4444")
    def set_success(self, text: str) -> None:
        self.set_status(f"✓ {text}", color="#22c55e")
    def set_info(self, text: str) -> None:
        self.set_status(text, color="#f4f4f5")
class DownloadProgressBar(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg="#09090b")
        self._label = tk.Label(
            self,
            text="",
            anchor="w",
            padx=8,
            font=("Segoe UI", 10),
            fg="#a1a1aa",
            bg="#09090b",
        )
        self._label.pack(fill="x", padx=(8, 8), pady=(4, 0))
        self._style = ttk.Style()
        self._style.theme_use("clam")
        self._style.configure(
            "Download.Horizontal.TProgressbar",
            troughcolor="#27272a",
            background="#e11d48",
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
        self.pack_forget()
    def show(self, label_text: str = "Downloading...") -> None:
        self._label.config(text=label_text)
        self._progress["value"] = 0
        self.pack(fill="x", side="bottom")
    def hide(self) -> None:
        self.pack_forget()
    def update_progress(self, bytes_downloaded: int, total_bytes: int) -> None:
        if total_bytes > 0:
            pct = min(100, int(bytes_downloaded / total_bytes * 100))
            self._progress["value"] = pct
            mb_done = bytes_downloaded / (1024 * 1024)
            mb_total = total_bytes / (1024 * 1024)
            self._label.config(
                text=f"Downloading... {mb_done:.1f} / {mb_total:.1f} MB ({pct}%)"
            )
        else:
            mb_done = bytes_downloaded / (1024 * 1024)
            self._label.config(text=f"Downloading... {mb_done:.1f} MB")
            self._progress["mode"] = "indeterminate"
            self._progress.step(2)
class Tooltip:
    def __init__(self, widget: tk.Widget, text: str):
        self._widget = widget
        self._text = text
        self._tip_window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
    def update_text(self, text: str) -> None:
        self._text = text
    def _show(self, event=None):
        if self._tip_window or not self._text:
            return
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
            background="#18181b",
            foreground="#f4f4f5",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 10),
            padx=12,
            pady=8,
            wraplength=350,
        )
        label.pack()
    def _hide(self, event=None):
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None
class AutocompleteDropdown:
    MAX_VISIBLE = 8  
    def __init__(self, entry: tk.Entry, on_select=None):
        self._entry = entry
        self._on_select = on_select
        self._top: tk.Toplevel | None = None
        self._listbox: tk.Listbox | None = None
        self._suggestions: list[str] = []
        self._visible = False
        entry.bind("<Down>", self._on_key_down, add="+")
        entry.bind("<Up>", self._on_key_up, add="+")
        entry.bind("<Escape>", lambda e: self.hide(), add="+")
    def update_suggestions(self, suggestions: list[str]) -> None:
        self._suggestions = suggestions
        if not suggestions:
            self.hide()
            return
        if not self._top or not self._top.winfo_exists():
            self._create_dropdown()
        self._listbox.delete(0, tk.END)
        for s in suggestions:
            self._listbox.insert(tk.END, s)
        visible_count = min(len(suggestions), self.MAX_VISIBLE)
        self._listbox.config(height=visible_count)
        self._reposition()
        if not self._visible:
            self._top.deiconify()
            self._visible = True
    def hide(self) -> None:
        if self._top and self._top.winfo_exists():
            self._top.withdraw()
        self._visible = False
    def is_visible(self) -> bool:
        return self._visible
    def _create_dropdown(self):
        self._top = tk.Toplevel(self._entry)
        self._top.wm_overrideredirect(True)
        self._top.attributes("-topmost", True)
        self._top.configure(bg="#27272a")
        border_frame = tk.Frame(self._top, bg="#3f3f46", padx=1, pady=1)
        border_frame.pack(fill="both", expand=True)
        self._listbox = tk.Listbox(
            border_frame,
            font=("Segoe UI", 12),
            bg="#18181b",
            fg="#f4f4f5",
            selectbackground="#e11d48",
            selectforeground="#ffffff",
            activestyle="none",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self._listbox.pack(fill="both", expand=True)
        self._listbox.bind("<ButtonRelease-1>", self._on_click_select)
        self._listbox.bind("<Return>", self._on_enter_select)
        self._top.bind("<FocusOut>", lambda e: self._entry.after(150, self._check_focus))
    def _reposition(self):
        if not self._top or not self._entry.winfo_exists():
            return
        x = self._entry.winfo_rootx()
        y = self._entry.winfo_rooty() + self._entry.winfo_height()
        w = self._entry.winfo_width()
        self._top.geometry(f"{w}x{self._listbox.winfo_reqheight() + 2}+{x}+{y}")
    def _check_focus(self):
        if not self._top or not self._top.winfo_exists():
            return
        try:
            focused = self._entry.winfo_toplevel().focus_get()
            if focused != self._entry and focused != self._listbox:
                self.hide()
        except (tk.TclError, KeyError):
            self.hide()
    def _on_click_select(self, event=None):
        self._select_current()
    def _on_enter_select(self, event=None):
        self._select_current()
        return "break"
    def _on_key_down(self, event=None):
        if not self._visible or not self._listbox:
            return
        cur = self._listbox.curselection()
        if not cur:
            self._listbox.selection_set(0)
            self._listbox.see(0)
            self._listbox.focus_set()
        else:
            idx = cur[0]
            if idx < self._listbox.size() - 1:
                self._listbox.selection_clear(0, tk.END)
                self._listbox.selection_set(idx + 1)
                self._listbox.see(idx + 1)
        return "break"
    def _on_key_up(self, event=None):
        if not self._visible or not self._listbox:
            return
        cur = self._listbox.curselection()
        if cur:
            idx = cur[0]
            if idx > 0:
                self._listbox.selection_clear(0, tk.END)
                self._listbox.selection_set(idx - 1)
                self._listbox.see(idx - 1)
            else:
                self._listbox.selection_clear(0, tk.END)
                self._entry.focus_set()
        return "break"
    def _select_current(self):
        if not self._listbox:
            return
        cur = self._listbox.curselection()
        if cur:
            value = self._listbox.get(cur[0])
            self.hide()
            if self._on_select:
                self._on_select(value)
    def destroy(self):
        if self._top and self._top.winfo_exists():
            self._top.destroy()
            self._top = None