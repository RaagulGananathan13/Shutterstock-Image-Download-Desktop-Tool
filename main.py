# main entry point
# note to self: make sure assets dir is there or pyinstaller will cry
import sys
import os
import tkinter as tk
if getattr(sys, "frozen", False):
    _base_dir = sys._MEIPASS  
else:
    _base_dir = os.path.dirname(os.path.abspath(__file__))
if _base_dir not in sys.path:
    sys.path.insert(0, _base_dir)
from gui.app_window import AppWindow
def main():
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = AppWindow(root)  
    root.mainloop()
if __name__ == "__main__":
    main()