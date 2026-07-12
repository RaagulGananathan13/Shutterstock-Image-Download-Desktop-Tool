"""
gui/app_window.py — Main application window.

Wires together: search bar, thumbnail grid, pagination, settings,
status bar, and download progress. All network I/O runs in background
threads; results come back through a queue polled by root.after().
"""

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


# Message types for the inter-thread queue
_MSG_SEARCH_RESULTS = "search_results"
_MSG_SEARCH_ERROR = "search_error"
_MSG_DOWNLOAD_PROGRESS = "download_progress"
_MSG_DOWNLOAD_DONE = "download_done"
_MSG_DOWNLOAD_ERROR = "download_error"
_MSG_SUGGESTIONS = "suggestions"


class AppWindow:
    """
    The main Shutterstock Image Search & Download window.

    Usage:
        root = tk.Tk()
        app = AppWindow(root)
        root.mainloop()
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Shutterstock Image Search & Download")
        self.root.geometry("920x680")
        self.root.minsize(700, 500)
        self.root.configure(bg="#1e1e2e")

        # Try to set the window icon
        try:
            icon_path = self._resource_path("assets", "app_icon.ico")
            if os.path.isfile(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            pass

        # ---- State ----
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

        # Autocomplete state
        self._suggest_after_id = None  # for debouncing
        self._search_history: list[str] = []  # local history for fast suggestions

        # Thread-safe message queue
        self._queue: queue.Queue = queue.Queue()

        # ---- Build UI ----
        self._build_ui()

        # Start polling the message queue
        self._poll_queue()

        # If no API token, open settings on first run
        if not self._config.get("api_token"):
            self.root.after(300, self._open_settings)

    # ------------------------------------------------------------------
    # Resource path helper (works both in dev and PyInstaller bundle)
    # ------------------------------------------------------------------

    @staticmethod
    def _resource_path(*parts) -> str:
        """Get absolute path to a resource, works for dev and for PyInstaller."""
        import sys
        if getattr(sys, "frozen", False):
            base = sys._MEIPASS  # type: ignore[attr-defined]
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, *parts)

    # ------------------------------------------------------------------
    # API initialization
    # ------------------------------------------------------------------

    def _init_api(self):
        """Initialize or re-initialize the API client with the current token."""
        token = self._config.get("api_token", "")
        if token:
            if self._api:
                self._api.update_token(token)
            else:
                self._api = ShutterstockAPI(token)
        else:
            self._api = None

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Build all UI components."""
        # Configure dark theme for ttk
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background="#1e1e2e", foreground="#e0e0e0")

        # ---- Top bar (search + settings) ----
        top_frame = tk.Frame(self.root, bg="#1e1e2e", padx=12, pady=10)
        top_frame.pack(fill="x")

        # Search entry
        self._search_var = tk.StringVar()
        self._search_entry = tk.Entry(
            top_frame,
            textvariable=self._search_var,
            font=("Segoe UI", 12),
            bg="#2a2a3e",
            fg="#e0e0e0",
            insertbackground="#7c5cfc",
            relief="flat",
            bd=0,
            highlightthickness=2,
            highlightcolor="#7c5cfc",
            highlightbackground="#3a3a4e",
        )
        self._search_entry.pack(side="left", fill="x", expand=True, ipady=8)
        self._search_entry.bind("<Return>", self._on_search_enter)
        self._search_entry.bind("<KeyRelease>", self._on_search_key_release)

        # Search button
        self._search_btn = tk.Button(
            top_frame,
            text="🔍 Search",
            font=("Segoe UI Semibold", 11),
            bg="#7c5cfc",
            fg="#ffffff",
            activebackground="#6a4ce0",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._on_search,
            padx=16,
        )
        self._search_btn.pack(side="left", padx=(10, 0), ipady=6)

        # Settings button
        settings_btn = tk.Button(
            top_frame,
            text="⚙",
            font=("Segoe UI", 14),
            bg="#2a2a3e",
            fg="#b0b0d0",
            activebackground="#3a3a4e",
            activeforeground="#e0e0e0",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._open_settings,
            width=3,
        )
        settings_btn.pack(side="left", padx=(8, 0), ipady=3)

        # ---- Thumbnail grid (center) ----
        self._grid = ThumbnailGrid(
            self.root,
            on_click=self._on_thumbnail_click,
        )
        self._grid.pack(fill="both", expand=True, padx=4, pady=(2, 0))

        # Show welcome message
        self._grid.show_message(
            "🔍  Enter a keyword above and click Search\nto find Shutterstock images"
        )

        # ---- Autocomplete dropdown ----
        self._autocomplete = AutocompleteDropdown(
            self._search_entry,
            on_select=self._on_suggestion_selected,
        )

        # ---- Pagination bar ----
        self._pagination_frame = tk.Frame(self.root, bg="#252538", pady=6)
        self._pagination_frame.pack(fill="x")

        self._prev_btn = tk.Button(
            self._pagination_frame,
            text="◀ Prev",
            font=("Segoe UI", 10),
            bg="#3a3a4e",
            fg="#b0b0d0",
            activebackground="#4a4a5e",
            activeforeground="#e0e0e0",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._prev_page,
            state="disabled",
        )
        self._prev_btn.pack(side="left", padx=(12, 8), ipady=4)

        self._page_label = tk.Label(
            self._pagination_frame,
            text="",
            font=("Segoe UI", 10),
            fg="#b0b0d0",
            bg="#252538",
        )
        self._page_label.pack(side="left", padx=8)

        self._next_btn = tk.Button(
            self._pagination_frame,
            text="Next ▶",
            font=("Segoe UI", 10),
            bg="#3a3a4e",
            fg="#b0b0d0",
            activebackground="#4a4a5e",
            activeforeground="#e0e0e0",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._next_page,
            state="disabled",
        )
        self._next_btn.pack(side="left", padx=8, ipady=4)

        # Per-page dropdown
        per_page_label = tk.Label(
            self._pagination_frame,
            text="Per page:",
            font=("Segoe UI", 9),
            fg="#888898",
            bg="#252538",
        )
        per_page_label.pack(side="right", padx=(0, 4))

        self._per_page_var = tk.StringVar(value="20")
        style.configure("PerPage.TCombobox",
                        fieldbackground="#2a2a3e",
                        background="#3a3a4e",
                        foreground="#e0e0e0")
        self._per_page_combo = ttk.Combobox(
            self._pagination_frame,
            textvariable=self._per_page_var,
            values=["10", "20", "30", "50"],
            state="readonly",
            width=4,
            font=("Segoe UI", 9),
            style="PerPage.TCombobox",
        )
        self._per_page_combo.pack(side="right", padx=(0, 12))
        self._per_page_combo.bind("<<ComboboxSelected>>", self._on_per_page_change)

        # ---- Download progress bar ----
        self._progress_bar = DownloadProgressBar(self.root)

        # ---- Status bar ----
        self._status_bar = StatusBar(self.root)
        self._status_bar.pack(fill="x", side="bottom")

    # ------------------------------------------------------------------
    # Queue polling (thread-safe UI updates)
    # ------------------------------------------------------------------

    def _poll_queue(self):
        """Drain the message queue and dispatch to handlers. Runs on the main thread."""
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
        # Schedule next poll
        self.root.after(50, self._poll_queue)

    # ------------------------------------------------------------------
    # Autocomplete / suggestions
    # ------------------------------------------------------------------

    def _on_search_key_release(self, event=None):
        """Debounced handler for keystrokes in the search entry."""
        # Ignore navigation and modifier keys
        if event and event.keysym in ("Return", "Up", "Down", "Escape",
                                       "Shift_L", "Shift_R", "Control_L",
                                       "Control_R", "Alt_L", "Alt_R", "Tab"):
            return

        # Cancel previous pending request
        if self._suggest_after_id is not None:
            self.root.after_cancel(self._suggest_after_id)

        # Schedule a new suggestion fetch after 300ms debounce
        self._suggest_after_id = self.root.after(300, self._fetch_suggestions)

    def _fetch_suggestions(self):
        """Fetch suggestions in a background thread."""
        self._suggest_after_id = None
        query = self._search_var.get().strip()

        if len(query) < 2:
            self._autocomplete.hide()
            return

        # Show local history matches immediately (instant feedback)
        history_matches = [
            h for h in self._search_history
            if h.lower().startswith(query.lower()) and h.lower() != query.lower()
        ]
        if history_matches:
            self._autocomplete.update_suggestions(history_matches[:5])

        # Fetch API suggestions in background
        if self._api:
            thread = threading.Thread(
                target=self._suggestions_worker,
                args=(query,),
                daemon=True,
            )
            thread.start()

    def _suggestions_worker(self, query: str):
        """Background thread: fetch suggestions from the API."""
        suggestions = self._api.get_suggestions(query, limit=10)
        # Only send if the entry still has the same prefix
        self._queue.put((_MSG_SUGGESTIONS, {
            "query": query,
            "suggestions": suggestions,
        }))

    def _handle_suggestions(self, payload: dict):
        """Process suggestions on the main thread."""
        query = payload["query"]
        suggestions = payload["suggestions"]

        # Only show if the entry text still starts with the query
        current_text = self._search_var.get().strip()
        if not current_text.lower().startswith(query.lower()[:2]):
            return  # user has typed something else

        if suggestions:
            # Merge with history, dedup, API results first
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
            # No API results — check if we already have history showing
            if not self._autocomplete.is_visible():
                self._autocomplete.hide()

    def _on_suggestion_selected(self, value: str):
        """Handle selection of a suggestion from the dropdown."""
        self._search_var.set(value)
        self._search_entry.icursor(tk.END)
        self._search_entry.focus_set()
        self._autocomplete.hide()
        # Trigger search
        self._on_search()

    def _on_search_enter(self, event=None):
        """Handle Enter key — hide autocomplete and search."""
        self._autocomplete.hide()
        self._on_search()

    # ------------------------------------------------------------------
    # Search flow
    # ------------------------------------------------------------------

    def _on_search(self):
        """Handle the Search button click or Enter key."""
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

        # Add to search history
        if query not in self._search_history:
            self._search_history.insert(0, query)
            self._search_history = self._search_history[:50]  # cap at 50

        self._autocomplete.hide()
        self._current_query = query
        self._current_page = 1
        self._do_search()

    def _do_search(self):
        """Launch a search in a background thread."""
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
        """Background thread: perform the API search."""
        try:
            result = self._api.search_images(query, page=page, per_page=per_page)
            self._queue.put((_MSG_SEARCH_RESULTS, result))
        except ShutterstockAPIError as e:
            self._queue.put((_MSG_SEARCH_ERROR, str(e)))
        except Exception as e:
            self._queue.put((_MSG_SEARCH_ERROR, f"Unexpected error: {e}"))

    def _handle_search_results(self, result: dict):
        """Process search results on the main thread."""
        self._is_searching = False
        self._search_btn.config(state="normal", text="🔍 Search")

        images = result.get("data", [])
        self._total_count = result.get("total_count", 0)
        self._per_page = result.get("per_page", self._per_page)
        self._current_page = result.get("page", self._current_page)

        if self._total_count > 0 and self._per_page > 0:
            self._total_pages = -(-self._total_count // self._per_page)  # ceiling division
        else:
            self._total_pages = 0

        # Update grid
        self._grid.populate(images)

        # Update pagination
        self._update_pagination()

        # Update status
        if images:
            self._status_bar.set_success(
                f"Found {self._total_count:,} images for \"{self._current_query}\" "
                f"(page {self._current_page} of {self._total_pages})"
            )
        else:
            self._status_bar.set_info(f"No results found for \"{self._current_query}\".")

    def _handle_search_error(self, error_msg: str):
        """Show search error on the main thread."""
        self._is_searching = False
        self._search_btn.config(state="normal", text="🔍 Search")
        self._status_bar.set_error(error_msg)
        self._grid.show_message(f"⚠  {error_msg}")

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _update_pagination(self):
        """Update pagination buttons and label based on current state."""
        if self._total_pages <= 0:
            self._page_label.config(text="")
            self._prev_btn.config(state="disabled")
            self._next_btn.config(state="disabled")
            return

        self._page_label.config(
            text=f"Page {self._current_page} of {self._total_pages}"
        )

        # Prev button
        if self._current_page > 1:
            self._prev_btn.config(state="normal")
        else:
            self._prev_btn.config(state="disabled")

        # Next button
        if self._current_page < self._total_pages:
            self._next_btn.config(state="normal")
        else:
            self._next_btn.config(state="disabled")

    def _prev_page(self):
        """Navigate to the previous page."""
        if self._current_page > 1 and not self._is_searching:
            self._current_page -= 1
            self._do_search()

    def _next_page(self):
        """Navigate to the next page."""
        if self._current_page < self._total_pages and not self._is_searching:
            self._current_page += 1
            self._do_search()

    def _on_per_page_change(self, event=None):
        """Handle per-page dropdown change."""
        try:
            new_per_page = int(self._per_page_var.get())
        except ValueError:
            return
        if new_per_page != self._per_page and self._current_query:
            self._per_page = new_per_page
            self._current_page = 1  # reset to page 1
            self._do_search()

    # ------------------------------------------------------------------
    # Download flow
    # ------------------------------------------------------------------

    def _on_thumbnail_click(self, image_data: dict):
        """Handle a thumbnail click — start the license + download flow."""
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
        """Background thread: license the image, then download it."""
        try:
            # Step 1: Get subscription ID
            sub_id = self._api.get_subscription_id()

            # Step 2: License the image and get the download URL
            download_url = self._api.license_image(image_id, sub_id)

            # Step 3: Determine destination path
            download_folder = self._config.get("download_folder", "")
            if not download_folder:
                download_folder = os.path.join(
                    os.path.expanduser("~"), "Downloads", "ShutterstockImages"
                )
            dest_path = os.path.join(download_folder, filename)
            dest_path = resolve_filename_collision(dest_path)

            # Step 4: Download the file
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
        """Update the progress bar on the main thread."""
        self._progress_bar.update_progress(
            payload["bytes_downloaded"],
            payload["total_bytes"],
        )

    def _handle_download_done(self, payload: dict):
        """Download completed successfully."""
        self._is_downloading = False
        self._progress_bar.hide()
        path = payload["path"]
        basename = os.path.basename(path)
        self._status_bar.set_success(f"Downloaded: {basename}")

    def _handle_download_error(self, error_msg: str):
        """Download failed."""
        self._is_downloading = False
        self._progress_bar.hide()
        self._status_bar.set_error(error_msg)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self):
        """Open the settings dialog."""
        SettingsDialog(self.root, on_save=self._on_settings_saved)

    def _on_settings_saved(self, new_config: dict):
        """Called when the user saves settings."""
        self._config = new_config
        self._init_api()
        self._status_bar.set_success("Settings saved.")
