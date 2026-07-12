# Shutterstock Image Search & Download Desktop Tool

A Windows desktop application that lets you search for images on Shutterstock, preview them as clickable thumbnails in a grid, and download full-resolution versions to a local folder — all through the official Shutterstock API.

## Requirements to Run from Source

- **Python 3.10+**
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

## How to Run

```bash
python main.py
```

The application will open with a search interface. On first launch, the Settings dialog will open automatically so you can enter your API token.

## How to Get a Shutterstock API Token

1. Go to the [Shutterstock Developer Portal](https://www.shutterstock.com/developers/).
2. Create an account or sign in.
3. Create a new application to get your **API credentials** (client ID and client secret).
4. Subscribe to an API plan that includes licensing (required for full-resolution downloads).
5. Generate a **Bearer token** from your application dashboard, or use the OAuth flow with your client credentials.

## How to Swap in a Different API Key

### Via the UI (recommended):
1. Click the **⚙ Settings** button (gear icon) in the top-right corner.
2. Paste your new API token into the **API Token** field.
3. Click **Save**.
4. No restart or rebuild needed — the next search/download will use the new key immediately.

### Via config file (power users):
Edit the config file directly:
- **Windows**: `%APPDATA%\ShutterstockTool\config.json`
- Key: `"api_token": "your_token_here"`

## How to Change the Download Folder

1. Click the **⚙ Settings** button.
2. Click **Browse** next to the Download Folder field.
3. Choose your preferred folder.
4. Click **Save**.

Default download folder: `~/Downloads/ShutterstockImages`

## Known Limitations

- **Full-resolution download requires a paid Shutterstock API subscription** with licensing enabled. This is a Shutterstock account/billing requirement, not a limitation of this app.
- Search-only or free-tier API keys can browse and preview images (watermarked thumbnails) but cannot download full-resolution files. The app will show a clear error message in this case.
- Re-downloading already-licensed images via `POST /v2/images/licenses/{id}/downloads` is a possible future enhancement.

## How to Rebuild the .exe

On a **Windows** machine with Python installed:

```bash
pip install -r requirements.txt
pip install pyinstaller

pyinstaller --noconfirm --onefile --windowed ^
  --name "ShutterstockImageTool" ^
  --add-data "assets;assets" ^
  main.py
```

The output will be in `dist/ShutterstockImageTool.exe`. This is a self-contained executable that runs on any Windows machine without Python installed.

If you encounter Pillow-related errors in the packaged build, add `--collect-all Pillow` to the PyInstaller command.

## Libraries Used

| Library | Purpose |
|---|---|
| **requests** | HTTP client for Shutterstock API calls and image downloads with streaming support |
| **Pillow** (PIL) | Decodes thumbnail images (JPEG/PNG) into Tkinter-compatible PhotoImage objects |
| **tkinter** (stdlib) | GUI toolkit — ships with Python, no extra installation needed |
| **PyInstaller** | Packages the Python application into a single Windows .exe file |

## Project Structure

```
shutterstock_tool/
├── main.py                   # Entry point
├── config.py                 # Config persistence (%APPDATA%)
├── shutterstock_api.py       # API client with typed exceptions
├── downloader.py             # Streaming download with progress
├── gui/
│   ├── app_window.py         # Main window (search, grid, pagination, status)
│   ├── thumbnail_grid.py     # Scrollable thumbnail grid with async loading
│   ├── settings_dialog.py    # API token + folder picker dialog
│   └── widgets.py            # StatusBar, ProgressBar, Tooltip
├── assets/
│   └── placeholder.png       # Loading placeholder image
├── requirements.txt
└── README.md
```
