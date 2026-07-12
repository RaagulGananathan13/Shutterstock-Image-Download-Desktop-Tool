"""
main.py — Entry point for the Shutterstock Image Search & Download Desktop Tool.

Constructs the root Tk window, loads configuration, and launches the main
application window. Opens the Settings dialog automatically on first run
if no API token is configured.
"""

import sys
import os
import tkinter as tk

# Ensure the project root is on the path (for PyInstaller compatibility)
if getattr(sys, "frozen", False):
    # Running as a PyInstaller bundle
    _base_dir = sys._MEIPASS  # type: ignore[attr-defined]
else:
    _base_dir = os.path.dirname(os.path.abspath(__file__))

if _base_dir not in sys.path:
    sys.path.insert(0, _base_dir)

from gui.app_window import AppWindow


def main():
    """Launch the Shutterstock Image Search & Download Desktop Tool."""
    root = tk.Tk()

    # Set DPI awareness on Windows for crisp rendering
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    # Create the application window
    app = AppWindow(root)  # noqa: F841 — held alive by root

    # Start the Tkinter event loop
    root.mainloop()


if __name__ == "__main__":
    main()
