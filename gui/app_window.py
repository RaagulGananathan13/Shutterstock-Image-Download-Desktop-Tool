# god i hate tkinter sometimes but it gets the job done
# main window logic
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from config import load_config, save_config
from shutterstock_api import (
    ShutterstockAPI,
    AuthError,
    SubscriptionError,
    RateLimitError,
    NetworkError,
    ShutterstockAPIError,
)
from downloader import download_file, make_safe_filename, resolve_filename_collision
from gui.thumbnail_grid import ThumbnailGrid
from gui.settings_dialog import SettingsDialog
from gui.widgets import StatusBar, DownloadProgressBar, AutocompleteDropdown
_MSG_SEARCH_RESULTS = "search_results"
_MSG_SEARCH_ERROR = "search_error"
_MSG_DOWNLOAD_PROGRESS = "download_progress"
_MSG_DOWNLOAD_DONE = "download_done"
_MSG_DOWNLOAD_ERROR = "download_error"
_MSG_SUGGESTIONS = "suggestions"
class AppWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Shutterstock Studio Hub")
        self.root.geometry("1024x768")
        self.root.minsize(800, 600)
        self.root.configure(bg="#09090b")
        try:
            icon_path = self._resource_path("assets", "app_icon.ico")
            if os.path.isfile(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            pass
        self._config = load_config()
        self._api: ShutterstockAPI | None = None
        self._init_api()
        self._current_query = ""
        self._current_page = 1
        self._per_page = 20
        self._total_count = 0
        self._total_pages = 0
        self._is_searching = False
        self._is_downloading = False
        self._suggest_after_id = None  
        self._search_history: list[str] = []  
        self._queue: queue.Queue = queue.Queue()
        self._build_ui()
        self._poll_queue()
        if not self._config.get("api_token"):
            self.root.after(300, self._open_settings)
    @staticmethod
    def _resource_path(*parts) -> str:
        import sys
        if getattr(sys, "frozen", False):
            base = sys._MEIPASS  
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, *parts)
    def _init_api(self):
        token = self._config.get("api_token", "")
        if token:
            if self._api:
                self._api.update_token(token)
            else:
                self._api = ShutterstockAPI(token)
        else:
            self._api = None
    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background="#09090b", foreground="#f4f4f5")
        top_frame = tk.Frame(self.root, bg="#18181b", padx=24, pady=20)
        top_frame.pack(fill="x")
        tk.Frame(self.root, bg="#27272a", height=1).pack(fill="x")
        self._search_var = tk.StringVar()
        self._search_entry = tk.Entry(
            top_frame,
            textvariable=self._search_var,
            font=("Segoe UI", 12),
            bg="#27272a",
            fg="#f4f4f5",
            insertbackground="#e11d48",
            relief="flat",
            bd=0,
            highlightthickness=2,
            highlightcolor="#e11d48",
            highlightbackground="#27272a",
        )
        self._search_entry.pack(side="left", fill="x", expand=True, ipady=10)
        self._search_entry.bind("<Return>", self._on_search_enter)
        self._search_entry.bind("<KeyRelease>", self._on_search_key_release)
        self._search_btn = tk.Button(
            top_frame,
            text="Search",
            font=("Segoe UI Semibold", 11),
            bg="#e11d48",
            fg="#ffffff",
            activebackground="#be123c",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._on_search,
            padx=24,
        )
        self._search_btn.pack(side="left", padx=(16, 0), ipady=8)
        settings_btn = tk.Button(
            top_frame,
            text="⚙",
            font=("Segoe UI", 15),
            bg="#18181b",
            fg="#a1a1aa",
            activebackground="#27272a",
            activeforeground="#f4f4f5",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._open_settings,
            width=3,
        )
        settings_btn.pack(side="left", padx=(12, 0), ipady=6)
        self._grid = ThumbnailGrid(
            self.root,
            on_click=self._on_thumbnail_click,
        )
        self._grid.pack(fill="both", expand=True, padx=4, pady=(2, 0))
        self._grid.show_message(
            "Find your next masterpiece.\nEnter a keyword to search Shutterstock."
        )
        self._autocomplete = AutocompleteDropdown(
            self._search_entry,
            on_select=self._on_suggestion_selected,
        )
        tk.Frame(self.root, bg="#27272a", height=1).pack(fill="x")
        self._pagination_frame = tk.Frame(self.root, bg="#09090b", pady=16)
        self._pagination_frame.pack(fill="x")
        self._prev_btn = tk.Button(
            self._pagination_frame,
            text="◀ Prev",
            font=("Segoe UI", 10),
            bg="#18181b",
            fg="#f4f4f5",
            activebackground="#27272a",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._prev_page,
            state="disabled",
            disabledforeground="#3f3f46",
        )
        self._prev_btn.pack(side="left", padx=(24, 8), ipady=6, ipadx=8)
        self._page_label = tk.Label(
            self._pagination_frame,
            text="",
            font=("Segoe UI", 10),
            fg="#a1a1aa",
            bg="#09090b",
        )
        self._page_label.pack(side="left", padx=12)
        self._next_btn = tk.Button(
            self._pagination_frame,
            text="Next ▶",
            font=("Segoe UI", 10),
            bg="#18181b",
            fg="#f4f4f5",
            activebackground="#27272a",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._next_page,
            state="disabled",
            disabledforeground="#3f3f46",
        )
        self._next_btn.pack(side="left", padx=8, ipady=6, ipadx=8)
        per_page_label = tk.Label(
            self._pagination_frame,
            text="Per page:",
            font=("Segoe UI", 10),
            fg="#a1a1aa",
            bg="#09090b",
        )
        per_page_label.pack(side="right", padx=(0, 8))
        self._per_page_var = tk.StringVar(value="20")
        style.configure("PerPage.TCombobox",
                        fieldbackground="#18181b",
                        background="#27272a",
                        foreground="#f4f4f5",
                        bordercolor="#27272a",
                        arrowcolor="#a1a1aa")
        self._per_page_combo = ttk.Combobox(
            self._pagination_frame,
            textvariable=self._per_page_var,
            values=["10", "20", "30", "50"],
            state="readonly",
            width=5,
            font=("Segoe UI", 10),
            style="PerPage.TCombobox",
        )
        self._per_page_combo.pack(side="right", padx=(0, 24))
        self._per_page_combo.bind("<<ComboboxSelected>>", self._on_per_page_change)
        self._progress_bar = DownloadProgressBar(self.root)
        self._status_bar = StatusBar(self.root)
        self._status_bar.pack(fill="x", side="bottom")
    def _poll_queue(self):
        try:
            while True:
                msg_type, payload = self._queue.get_nowait()
                if msg_type == _MSG_SEARCH_RESULTS:
                    self._handle_search_results(payload)
                elif msg_type == _MSG_SEARCH_ERROR:
                    self._handle_search_error(payload)
                elif msg_type == _MSG_DOWNLOAD_PROGRESS:
                    self._handle_download_progress(payload)
                elif msg_type == _MSG_DOWNLOAD_DONE:
                    self._handle_download_done(payload)
                elif msg_type == _MSG_DOWNLOAD_ERROR:
                    self._handle_download_error(payload)
                elif msg_type == _MSG_SUGGESTIONS:
                    self._handle_suggestions(payload)
        except queue.Empty:
            pass
        self.root.after(50, self._poll_queue)
    def _on_search_key_release(self, event=None):
        if event and event.keysym in ("Return", "Up", "Down", "Escape",
                                       "Shift_L", "Shift_R", "Control_L",
                                       "Control_R", "Alt_L", "Alt_R", "Tab"):
            return
        if self._suggest_after_id is not None:
            self.root.after_cancel(self._suggest_after_id)
        self._suggest_after_id = self.root.after(300, self._fetch_suggestions)
    def _fetch_suggestions(self):
        self._suggest_after_id = None
        query = self._search_var.get().strip()
        if len(query) < 2:
            self._autocomplete.hide()
            return
        history_matches = [
            h for h in self._search_history
            if h.lower().startswith(query.lower()) and h.lower() != query.lower()
        ]
        if history_matches:
            self._autocomplete.update_suggestions(history_matches[:5])
        if self._api:
            thread = threading.Thread(
                target=self._suggestions_worker,
                args=(query,),
                daemon=True,
            )
            thread.start()
    def _suggestions_worker(self, query: str):
        suggestions = self._api.get_suggestions(query, limit=10)
        self._queue.put((_MSG_SUGGESTIONS, {
            "query": query,
            "suggestions": suggestions,
        }))
    def _handle_suggestions(self, payload: dict):
        query = payload["query"]
        suggestions = payload["suggestions"]
        current_text = self._search_var.get().strip()
        if not current_text.lower().startswith(query.lower()[:2]):
            return  
        if suggestions:
            history_matches = [
                h for h in self._search_history
                if h.lower().startswith(current_text.lower())
                and h.lower() != current_text.lower()
            ]
            combined = []
            seen = set()
            for s in suggestions + history_matches:
                if s.lower() not in seen and s.lower() != current_text.lower():
                    combined.append(s)
                    seen.add(s.lower())
            self._autocomplete.update_suggestions(combined[:10])
        else:
            if not self._autocomplete.is_visible():
                self._autocomplete.hide()
    def _on_suggestion_selected(self, value: str):
        self._search_var.set(value)
        self._search_entry.icursor(tk.END)
        self._search_entry.focus_set()
        self._autocomplete.hide()
        self._on_search()
    def _on_search_enter(self, event=None):
        self._autocomplete.hide()
        self._on_search()
    def _on_search(self):
        query = self._search_var.get().strip()
        if not query:
            self._status_bar.set_info("Please enter a search keyword.")
            return
        if not self._api:
            self._status_bar.set_error("No API token configured. Click ⚙ Settings to add one.")
            self._open_settings()
            return
        if self._is_searching:
            return
        if query not in self._search_history:
            self._search_history.insert(0, query)
            self._search_history = self._search_history[:50]  
        self._autocomplete.hide()
        self._current_query = query
        self._current_page = 1
        self._do_search()
    def _do_search(self):
        self._is_searching = True
        self._search_btn.config(state="disabled", text="Searching...")
        self._status_bar.set_info(f"Searching for \"{self._current_query}\"...")
        self._grid.show_message("⏳  Searching...")
        thread = threading.Thread(
            target=self._search_worker,
            args=(self._current_query, self._current_page, self._per_page),
            daemon=True,
        )
        thread.start()
    def _search_worker(self, query: str, page: int, per_page: int):
        try:
            result = self._api.search_images(query, page=page, per_page=per_page)
            self._queue.put((_MSG_SEARCH_RESULTS, result))
        except ShutterstockAPIError as e:
            self._queue.put((_MSG_SEARCH_ERROR, str(e)))
        except Exception as e:
            self._queue.put((_MSG_SEARCH_ERROR, f"Unexpected error: {e}"))
    def _handle_search_results(self, result: dict):
        self._is_searching = False
        self._search_btn.config(state="normal", text="🔍 Search")
        images = result.get("data", [])
        self._total_count = result.get("total_count", 0)
        self._per_page = result.get("per_page", self._per_page)
        self._current_page = result.get("page", self._current_page)
        if self._total_count > 0 and self._per_page > 0:
            self._total_pages = -(-self._total_count // self._per_page)  
        else:
            self._total_pages = 0
        self._grid.populate(images)
        self._update_pagination()
        if images:
            self._status_bar.set_success(
                f"Found {self._total_count:,} images for \"{self._current_query}\" "
                f"(page {self._current_page} of {self._total_pages})"
            )
        else:
            self._status_bar.set_info(f"No results found for \"{self._current_query}\".")
    def _handle_search_error(self, error_msg: str):
        self._is_searching = False
        self._search_btn.config(state="normal", text="🔍 Search")
        self._status_bar.set_error(error_msg)
        self._grid.show_message(f"⚠  {error_msg}")
    def _update_pagination(self):
        if self._total_pages <= 0:
            self._page_label.config(text="")
            self._prev_btn.config(state="disabled")
            self._next_btn.config(state="disabled")
            return
        self._page_label.config(
            text=f"Page {self._current_page} of {self._total_pages}"
        )
        if self._current_page > 1:
            self._prev_btn.config(state="normal")
        else:
            self._prev_btn.config(state="disabled")
        if self._current_page < self._total_pages:
            self._next_btn.config(state="normal")
        else:
            self._next_btn.config(state="disabled")
    def _prev_page(self):
        if self._current_page > 1 and not self._is_searching:
            self._current_page -= 1
            self._do_search()
    def _next_page(self):
        if self._current_page < self._total_pages and not self._is_searching:
            self._current_page += 1
            self._do_search()
    def _on_per_page_change(self, event=None):
        try:
            new_per_page = int(self._per_page_var.get())
        except ValueError:
            return
        if new_per_page != self._per_page and self._current_query:
            self._per_page = new_per_page
            self._current_page = 1  
            self._do_search()
    def _on_thumbnail_click(self, image_data: dict):
        if self._is_downloading:
            self._status_bar.set_info("A download is already in progress. Please wait.")
            return
        if not self._api:
            self._status_bar.set_error("No API token configured.")
            return
        image_id = image_data.get("id", "")
        description = image_data.get("description", "")
        if not image_id:
            self._status_bar.set_error("Invalid image data.")
            return
        self._is_downloading = True
        filename = make_safe_filename(description, image_id)
        self._status_bar.set_info(f"Licensing image {image_id}...")
        self._progress_bar.show(f"Preparing download: {filename}")
        thread = threading.Thread(
            target=self._download_worker,
            args=(image_id, description, filename),
            daemon=True,
        )
        thread.start()
    def _download_worker(self, image_id: str, description: str, filename: str):
        try:
            sub_id = self._api.get_subscription_id()
            download_url = self._api.license_image(image_id, sub_id)
            download_folder = self._config.get("download_folder", "")
            if not download_folder:
                download_folder = os.path.join(
                    os.path.expanduser("~"), "Downloads", "ShutterstockImages"
                )
            dest_path = os.path.join(download_folder, filename)
            dest_path = resolve_filename_collision(dest_path)
            def progress_cb(bytes_done, total):
                self._queue.put((_MSG_DOWNLOAD_PROGRESS, {
                    "bytes_downloaded": bytes_done,
                    "total_bytes": total,
                }))
            final_path = download_file(download_url, dest_path, progress_callback=progress_cb)
            self._queue.put((_MSG_DOWNLOAD_DONE, {"path": final_path, "image_id": image_id}))
        except ShutterstockAPIError as e:
            self._queue.put((_MSG_DOWNLOAD_ERROR, str(e)))
        except Exception as e:
            self._queue.put((_MSG_DOWNLOAD_ERROR, f"Download failed: {e}"))
    def _handle_download_progress(self, payload: dict):
        self._progress_bar.update_progress(
            payload["bytes_downloaded"],
            payload["total_bytes"],
        )
    def _handle_download_done(self, payload: dict):
        self._is_downloading = False
        self._progress_bar.hide()
        path = payload["path"]
        basename = os.path.basename(path)
        self._status_bar.set_success(f"Downloaded: {basename}")
    def _handle_download_error(self, error_msg: str):
        self._is_downloading = False
        self._progress_bar.hide()
        self._status_bar.set_error(error_msg)
    def _open_settings(self):
        SettingsDialog(self.root, on_save=self._on_settings_saved)
    def _on_settings_saved(self, new_config: dict):
        self._config = new_config
        self._init_api()
        self._status_bar.set_success("Settings saved.")