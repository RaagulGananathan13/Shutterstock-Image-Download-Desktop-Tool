# Shutterstock Image Search & Download Desktop Tool — Build Spec for Claude Code

> Feed this whole file to Claude Code as the project brief. It contains the tech decision, the exact Shutterstock API contract, full architecture, file-by-file implementation plan, packaging steps, and a QA/delivery checklist mapped to the freelance contest requirements.

---

## 1. Recommended stack (and why)

| Layer | Choice | Why this beats the alternatives |
|---|---|---|
| GUI toolkit | **Tkinter** (Python stdlib) | Ships with every standard Python install, zero extra runtime license/cost, smallest and most reliable PyInstaller output, no Qt licensing questions to explain to a client. PyQt/PySide would render nicer but adds ~40-80MB to the exe and LGPL/commercial licensing footguns that are irrelevant here — not worth it for a single-purpose utility. |
| HTTP client | `requests` | Simplest reliable HTTP library, handles streaming downloads with progress cleanly. |
| Image handling in-GUI | `Pillow` (PIL fork) | Needed to decode thumbnail bytes (JPEG) into `ImageTk.PhotoImage` for Tkinter. |
| Concurrency | `threading` + a `queue.Queue` | Keep network calls off the Tk main loop so the UI never freezes during search/download. No need for asyncio here — adds complexity without benefit in a Tkinter app. |
| Packaging | `PyInstaller` (`--onefile --windowed`) | Produces a single-file, no-console `.exe` that runs on a clean Windows machine with no Python installed. Industry-standard for this exact ask. |
| Config | `.env`-style `config.json` (or env var) for the API token, never hardcoded | Lets the client "swap in a different API key" per the contest requirement, without rebuilding the exe. |

This combination is the standard, boring, reliable choice for "small Windows utility that hits a REST API and shows a picker" — exactly what a contest reviewer expects to see, and it minimizes the chance of packaging failures which are the #1 way these contest deliverables go wrong.

---

## 2. Shutterstock API — exact contract to implement

Base URL: `https://api.shutterstock.com/v2`

### 2.1 Authentication
- The client supplies a **Shutterstock API access token** (Bearer token) they generate from their Shutterstock Developer account (or a client_id/client_secret pair exchanged via `POST /v2/oauth/access_token` with `grant_type=client_credentials` — support **both** input modes, see §2.4).
- Every request sends: `Authorization: Bearer <token>`.
- **Important reality to bake into the UI/README**: search works on any API subscription tier, but *downloading a full-resolution file requires licensing it first*, which requires a **paid Shutterstock API subscription** with a `subscription_id`. A free/trial API key can search and preview but the license/download call will return an error (typically 403). The app must catch this and show a clear, non-crashing message like *"This API key does not have an active licensing subscription. Search still works but full-resolution download is not available on this plan."*

### 2.2 Search endpoint
```
GET /v2/images/search
Headers: Authorization: Bearer <token>
Query params:
  query          (required) - URL-encoded keyword string
  page           (optional, default 1)
  per_page       (optional, default 20, max 50)
  sort           (optional) - relevance | popular | newest, etc.
  image_type     (optional) - photo | illustration | vector
```
Response shape (relevant fields):
```json
{
  "page": 1,
  "per_page": 20,
  "total_count": 583213,
  "data": [
    {
      "id": "1572478477",
      "description": "Cropped image of woman gardening",
      "assets": {
        "preview": { "url": "...watermarked 450px...", "width": 450, "height": 300 },
        "large_thumb": { "url": "...150px...", "width": 150, "height": 100 },
        "huge_thumb": { "url": "...260px, paid accounts only...", "width": 390, "height": 260 }
      }
    }
  ]
}
```
- Use `total_count` and `per_page` to compute total pages for the pagination controls.
- Use `assets.preview` (fallback to `large_thumb` if `preview` missing) as the thumbnail image shown in the grid — it's watermarked but that's expected/fine since it's just a picker.

### 2.3 Get subscription ID (needed once per session, before any download)
```
GET /v2/user/subscriptions
Headers: Authorization: Bearer <token>
```
Returns a list; take the first active subscription's `id`. Cache it in memory for the session — don't re-fetch per download.

### 2.4 License + get the downloadable full-res URL
```
POST /v2/images/licenses
Headers: Authorization: Bearer <token>, Content-Type: application/json
Body:
{
  "images": [
    { "image_id": "<id>", "subscription_id": "<subscription_id>", "size": "huge" }
  ]
}
```
- `size` options include `small`, `medium`, `large`, `huge`, `vector` etc. — default to `huge` (largest raster size) unless the client wants a size picker; keep it simple, hardcode `"huge"` with a fallback to `"large"` if the response errors on size.
- Success response contains a `download` object with a signed `url` for the actual binary — that URL is what you stream to disk. It's typically short-lived, so download immediately after the license call, don't cache the URL.
- Already-licensed images can be re-downloaded via `POST /v2/images/licenses/{id}/downloads` — not required for v1 of this tool, note it in README as a "possible future enhancement."

### 2.5 Rate limits / errors to handle explicitly
- `401` — bad/expired token → show "Invalid or expired API token. Please check your key in Settings."
- `403` — token doesn't have the required scope/subscription (common on search-only or free keys) → message described in §2.1.
- `429` — rate limited → show "Too many requests, please wait a moment and try again," don't hammer retries automatically beyond one backoff retry.
- Network/timeout errors (`requests.exceptions.*`) → show "Network error: could not reach Shutterstock. Check your internet connection." Never let an unhandled exception reach the user as a raw traceback dialog or a frozen window.

---

## 3. Application architecture

```
shutterstock_tool/
├── main.py                  # entry point, builds and runs the Tk app
├── config.py                # loads/saves API token + default download folder (config.json in %APPDATA%)
├── shutterstock_api.py       # thin API client: search(), get_subscription_id(), license_and_get_url()
├── downloader.py             # threaded download-to-file logic with progress callback
├── gui/
│   ├── app_window.py         # main window: search bar, results grid, status bar, pagination controls
│   ├── thumbnail_grid.py     # scrollable canvas/frame of clickable thumbnail widgets
│   ├── settings_dialog.py    # API key entry + download folder picker, persisted via config.py
│   └── widgets.py            # small reusable pieces (progress bar row, toast/status label)
├── assets/
│   └── placeholder.png       # shown while a thumbnail is loading / on load failure
├── requirements.txt
├── build.spec                 # PyInstaller spec file (see §5)
└── README.md
```

### 3.1 Threading model
- Main thread: Tk event loop only.
- Search calls and thumbnail image fetches run in a background `threading.Thread`; results are pushed to a `queue.Queue` and drained on the main thread via `root.after(50, poll_queue)` — this is the standard safe pattern for Tkinter + network I/O and avoids "Tcl not thread-safe" crashes.
- Each download runs in its own background thread so the user can click multiple thumbnails without the UI blocking; show one status/progress row per active download (or a single active-download row if you want to keep v1 simple — recommend **one download at a time with a queue**, clearer UX and less code, mention "download several images" only if concurrent is explicitly required by client later).

### 3.2 UI layout (Tkinter, single window ~900x650)
```
┌─────────────────────────────────────────────────────────┐
│ [ Search box.....................] [Search] [Settings⚙] │
├─────────────────────────────────────────────────────────┤
│  scrollable grid of thumbnails, N columns, hover =        │
│  slight border highlight, click = trigger license+download│
│                                                             │
├─────────────────────────────────────────────────────────┤
│ ◀ Prev   Page 3 of 128   Next ▶        [per-page: 20 ▾]  │
├─────────────────────────────────────────────────────────┤
│ Status: Downloading "beautiful-sunset-1234567.jpg"...     │
│ [██████████░░░░░░░░] 62%                                  │
└─────────────────────────────────────────────────────────┘
```
- **Settings dialog** (gear icon) holds: API token field (masked, with show/hide), download folder picker (`filedialog.askdirectory`), Save/Cancel. Persisted to `%APPDATA%/ShutterstockTool/config.json`. This is the "swap API key" mechanism the client asked about — no code edit or rebuild needed.
- Thumbnail widgets: `tk.Label` holding a `PhotoImage`, bound to `<Button-1>` → starts license+download flow, plus a tooltip/status showing the image ID and description on hover.
- Status bar always shows the last action's outcome; progress bar only visible during an active download (`ttk.Progressbar` in determinate mode using `Content-Length` from the response headers streamed in chunks).

### 3.3 Filenames on save
`f"{safe_title}_{image_id}.jpg"` where `safe_title` = description, lowercased, spaces→hyphens, stripped of non-alphanumeric chars, truncated to ~50 chars. Fallback to `f"shutterstock_{image_id}.jpg"` if description is empty. Always confirm the target folder exists (`os.makedirs(exist_ok=True)`) before writing, and if a filename collision occurs, append `_1`, `_2`, etc.

---

## 4. Build order for Claude Code (do these in sequence, verify each before moving on)

1. **Scaffold the project** with the file tree in §3, `requirements.txt` = `requests`, `Pillow`, `pyinstaller`.
2. **`config.py`** — read/write `config.json` in `%APPDATA%/ShutterstockTool/`, with keys `api_token`, `download_folder` (default `~/Downloads/ShutterstockImages`).
3. **`shutterstock_api.py`** — implement `search_images(query, page, per_page)`, `get_subscription_id()`, `license_image(image_id, size="huge")` exactly per §2, with typed exceptions (`AuthError`, `SubscriptionError`, `RateLimitError`, `NetworkError`) that the GUI layer catches to show friendly messages.
4. **`downloader.py`** — `download_file(url, dest_path, progress_callback)` streaming with `requests.get(..., stream=True)`, chunk size 8192, calling `progress_callback(bytes_downloaded, total_bytes)`.
5. **`gui/thumbnail_grid.py`** — grid rendering + async thumbnail image loading (own thread per visible thumbnail, capped concurrency e.g. `ThreadPoolExecutor(max_workers=6)`), placeholder image while loading.
6. **`gui/app_window.py`** — wire search bar → `shutterstock_api.search_images` → populate grid; wire pagination; wire thumbnail click → license → download with status/progress updates; wire Settings button → `settings_dialog`.
7. **`gui/settings_dialog.py`** and **`gui/widgets.py`** — small, straightforward.
8. **`main.py`** — construct root Tk window, load config, if no API token present on first run, open Settings dialog automatically before showing the main window.
9. **Manual test pass** against real API (see §6) — do this before packaging, it's far faster to fix bugs running as a plain script.
10. **Package with PyInstaller** (§5).
11. **Write README.md** (§7) and take the screenshots (§8).

---

## 5. Packaging into a single `.exe`

Run on a Windows machine (PyInstaller must build on the target OS; if developing on Mac/Linux, use a Windows VM, GitHub Actions `windows-latest` runner, or Wine — do not claim a Linux-built binary is a Windows exe).

```bash
pip install -r requirements.txt
pip install pyinstaller

pyinstaller --noconfirm --onefile --windowed ^
  --name "ShutterstockImageTool" ^
  --icon assets/app_icon.ico ^
  --add-data "assets;assets" ^
  main.py
```
- `--windowed` suppresses the console window (this is a GUI app).
- `--add-data "assets;assets"` bundles the placeholder image (Windows uses `;` as the separator, macOS/Linux use `:`).
- If Pillow-related DLL/image plugin errors show up in the frozen build, add `--collect-all Pillow`.
- Output lands in `dist/ShutterstockImageTool.exe` — this is deliverable #1. Test it on a clean Windows machine/VM without Python installed to make sure there's no hidden dependency.
- Optional but a nice touch for the reviewer: wrap it with **Inno Setup** to produce a proper installer (`Setup.exe`) that creates a Start Menu shortcut and an uninstaller — only do this if time allows, the bare `.exe` alone satisfies "Windows installer or self-contained .exe."

---

## 6. QA checklist before delivery

- [ ] First run with no config → Settings dialog opens automatically, token can be entered and saved.
- [ ] Search with a valid keyword → thumbnails populate within a few seconds, no UI freeze.
- [ ] Search with a keyword yielding 0 results → clear "No results found" message, no crash.
- [ ] Pagination Next/Prev correctly changes page and re-renders grid; boundaries (page 1 and last page) disable the appropriate button.
- [ ] Clicking a thumbnail on a valid paid-subscription key → progress bar animates → file appears in the configured folder with a sane filename.
- [ ] Clicking a thumbnail on a search-only/free key → friendly "no licensing subscription" message, app doesn't crash.
- [ ] Invalid API token → friendly 401 message on first search attempt.
- [ ] Disconnect network mid-download → friendly network-error message, partial file cleaned up (don't leave a corrupt 0-byte or half file with the final filename — write to a `.part` temp name and rename on success).
- [ ] Change download folder in Settings → next download goes to the new folder.
- [ ] Swap to a different API key in Settings without restarting the app → next search/download uses the new key.
- [ ] Run the packaged `.exe` on a Windows machine with no Python installed → app launches and works identically to the dev version.

---

## 7. README.md — required content

Include, in the actual deliverable README (not this planning doc):
1. **What this is** — one paragraph.
2. **Requirements to run from source**: Python 3.10+, `pip install -r requirements.txt`.
3. **How to run**: `python main.py`.
4. **How to get a Shutterstock API token**: brief pointer to the Shutterstock Developer Portal, create an app, subscribe to an API plan, generate a token (or client_id/secret).
5. **How to swap in a different API key**: open the app → Settings (gear icon) → paste new token → Save. No rebuild needed. (Also mention the `config.json` path for power users.)
6. **How to change the download folder**: same Settings dialog.
7. **Known limitation**: full-resolution download requires a Shutterstock API subscription with licensing enabled; search-only/free keys can browse but not download.
8. **How to rebuild the .exe**: the exact PyInstaller command from §5.
9. **Libraries used**: requests, Pillow, tkinter (stdlib), PyInstaller — one line each on why.

---

## 8. Proof-of-work deliverable (screen capture)

Record a 60–90 second screen capture (or 4-5 screenshots) showing, in order:
1. Empty app on launch.
2. Typing a keyword and clicking Search → grid populates.
3. Paging to page 2.
4. Clicking a thumbnail → progress bar → completion status.
5. The downloaded file open in Windows Explorer/File Explorer in the target folder, filename visible.

This directly proves the "search, preview, and download flow" the contest asks for.

---

## 9. Contest deliverables → spec mapping (sanity check before submitting)

| Contest requirement | Where it's covered |
|---|---|
| Type keyword, press Search, pull matching images via official API | §2.2, §4 step 6 |
| Results as clickable thumbnails in the GUI | §3.2, §3.3, §4 step 5 |
| Click → full-res download to a chosen local folder | §2.4, §3.3, Settings folder picker |
| Any Python GUI toolkit, packaged to .exe | §1, §5 |
| Handle pagination beyond page 1 | §2.2, §3.2 |
| Clear status/progress during download | §3.2, §3.3, downloader.py progress_callback |
| Sensible filenames with Shutterstock ID/title | §3.3 |
| Graceful API/network error handling | §2.5, §6 |
| Windows installer or self-contained .exe | §5 |
| Source + README (setup, libraries, swapping API key) | §7 |
| Screenshots/screen capture of the flow | §8 |

---

## 10. One thing to flag to the client up front

Full-resolution download only works with a **paid Shutterstock API subscription** tied to their key — this is a Shutterstock account/billing fact, not a limitation of this app. Say this plainly in the proposal/README so there's no dispute at delivery time if they test with a free-tier key and only get previews.
