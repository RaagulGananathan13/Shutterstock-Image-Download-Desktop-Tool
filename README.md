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

If you want to package the app into a standalone `.exe` (so you can run it on Windows machines without Python installed), you can use PyInstaller.

Here are the bulletproof commands to run from your terminal (this avoids those annoying "pyinstaller is not recognized" PATH errors):

```bash
# 1. Make sure you have the required packages
python -m pip install -r requirements.txt
python -m pip install pyinstaller

# 2. Make sure the assets folder and placeholder exist
python generate_placeholder.py

# 3. Build the executable
python -m PyInstaller --noconfirm --onefile --windowed --name "ShutterstockImageTool" --add-data "assets;assets" main.py
```

Once it finishes, you'll find your compiled, self-contained executable sitting right in the `dist` folder (`dist/ShutterstockImageTool.exe`). Just double-click it to run!

*(Note: If you run into Pillow-related issues later down the road, you can tack on `--collect-all Pillow` to that PyInstaller command).*
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
