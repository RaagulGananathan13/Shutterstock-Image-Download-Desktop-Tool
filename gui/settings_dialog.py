"""
gui/settings_dialog.py — Modal dialog for API token and download folder configuration.

Shows a masked token field with show/hide toggle, a folder picker,
and Save/Cancel buttons. Persists changes via config.py.
"""

import tkinter as tk
from tkinter import filedialog

from config import load_config, save_config, get_config_path_for_display


class SettingsDialog(tk.Toplevel):
    """
    Modal settings dialog for configuring the Shutterstock API token
    and download folder.

    Parameters:
        parent: parent Tk window
        on_save: callback(config_dict) called after the user clicks Save
    """

    def __init__(self, parent, on_save=None):
        super().__init__(parent)
        self._on_save = on_save

        self.title("Settings")
        self.configure(bg="#09090b")
        self.resizable(False, False)

        # Center the dialog over the parent
        dialog_w, dialog_h = 560, 360
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        x = parent_x + (parent_w - dialog_w) // 2
        y = parent_y + (parent_h - dialog_h) // 2
        self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Load current config
        self._config = load_config()

        self._build_ui()

        # Focus on token field
        self._token_entry.focus_set()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_ui(self):
        """Build the settings form UI."""
        # ---- Title ----
        title_label = tk.Label(
            self,
            text="⚙ Settings",
            font=("Segoe UI Semibold", 18),
            fg="#f4f4f5",
            bg="#09090b",
            anchor="w",
        )
        title_label.pack(fill="x", padx=32, pady=(24, 20))

        # ---- API Token ----
        token_frame = tk.Frame(self, bg="#09090b")
        token_frame.pack(fill="x", padx=32, pady=(0, 16))

        tk.Label(
            token_frame,
            text="Shutterstock API Token",
            font=("Segoe UI", 11),
            fg="#a1a1aa",
            bg="#09090b",
            anchor="w",
        ).pack(fill="x")

        token_input_frame = tk.Frame(token_frame, bg="#09090b")
        token_input_frame.pack(fill="x", pady=(6, 0))

        self._token_var = tk.StringVar(value=self._config.get("api_token", ""))
        self._show_token = False

        self._token_entry = tk.Entry(
            token_input_frame,
            textvariable=self._token_var,
            show="•",
            font=("Consolas", 12),
            bg="#18181b",
            fg="#f4f4f5",
            insertbackground="#e11d48",
            relief="flat",
            bd=0,
            highlightthickness=2,
            highlightcolor="#e11d48",
            highlightbackground="#27272a",
        )
        self._token_entry.pack(side="left", fill="x", expand=True, ipady=8)

        self._toggle_btn = tk.Button(
            token_input_frame,
            text="Show",
            font=("Segoe UI", 10),
            bg="#27272a",
            fg="#a1a1aa",
            activebackground="#3f3f46",
            activeforeground="#f4f4f5",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._toggle_token_visibility,
            width=6,
        )
        self._toggle_btn.pack(side="right", padx=(8, 0), ipady=6)

        # ---- Download Folder ----
        folder_frame = tk.Frame(self, bg="#09090b")
        folder_frame.pack(fill="x", padx=32, pady=(0, 16))

        tk.Label(
            folder_frame,
            text="Download Folder",
            font=("Segoe UI", 11),
            fg="#a1a1aa",
            bg="#09090b",
            anchor="w",
        ).pack(fill="x")

        folder_input_frame = tk.Frame(folder_frame, bg="#09090b")
        folder_input_frame.pack(fill="x", pady=(6, 0))

        self._folder_var = tk.StringVar(value=self._config.get("download_folder", ""))

        self._folder_entry = tk.Entry(
            folder_input_frame,
            textvariable=self._folder_var,
            font=("Segoe UI", 11),
            bg="#18181b",
            fg="#f4f4f5",
            insertbackground="#e11d48",
            relief="flat",
            bd=0,
            highlightthickness=2,
            highlightcolor="#e11d48",
            highlightbackground="#27272a",
        )
        self._folder_entry.pack(side="left", fill="x", expand=True, ipady=8)

        browse_btn = tk.Button(
            folder_input_frame,
            text="Browse",
            font=("Segoe UI", 10),
            bg="#27272a",
            fg="#a1a1aa",
            activebackground="#3f3f46",
            activeforeground="#f4f4f5",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._browse_folder,
            width=8,
        )
        browse_btn.pack(side="right", padx=(8, 0), ipady=6)

        # ---- Config path info ----
        config_path = get_config_path_for_display()
        info_label = tk.Label(
            self,
            text=f"Config stored at: {config_path}",
            font=("Segoe UI", 9),
            fg="#71717a",
            bg="#09090b",
            anchor="w",
        )
        info_label.pack(fill="x", padx=32, pady=(4, 16))

        # ---- Buttons ----
        btn_frame = tk.Frame(self, bg="#09090b")
        btn_frame.pack(fill="x", padx=32, pady=(12, 24))

        cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            font=("Segoe UI", 11),
            bg="#27272a",
            fg="#a1a1aa",
            activebackground="#3f3f46",
            activeforeground="#f4f4f5",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._on_cancel,
            width=10,
        )
        cancel_btn.pack(side="right", ipady=6, padx=(12, 0))

        save_btn = tk.Button(
            btn_frame,
            text="Save",
            font=("Segoe UI Semibold", 11),
            bg="#e11d48",
            fg="#ffffff",
            activebackground="#be123c",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._on_save_click,
            width=10,
        )
        save_btn.pack(side="right", ipady=6)

    def _toggle_token_visibility(self):
        """Toggle between showing and hiding the API token."""
        self._show_token = not self._show_token
        if self._show_token:
            self._token_entry.config(show="")
            self._toggle_btn.config(text="Hide")
        else:
            self._token_entry.config(show="•")
            self._toggle_btn.config(text="Show")

    def _browse_folder(self):
        """Open a folder picker dialog."""
        current = self._folder_var.get()
        folder = filedialog.askdirectory(
            parent=self,
            initialdir=current if current else None,
            title="Choose Download Folder",
        )
        if folder:
            self._folder_var.set(folder)

    def _on_save_click(self):
        """Save the config and close the dialog."""
        self._config["api_token"] = self._token_var.get().strip()
        self._config["download_folder"] = self._folder_var.get().strip()
        save_config(self._config)
        if self._on_save:
            self._on_save(self._config)
        self.destroy()

    def _on_cancel(self):
        """Close without saving."""
        self.destroy()
