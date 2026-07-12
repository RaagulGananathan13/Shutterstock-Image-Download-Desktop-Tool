"""
config.py — Loads and saves application configuration (API token, download folder)
from %APPDATA%/ShutterstockTool/config.json.
"""

import json
import os
import threading


_CONFIG_DIR_NAME = "ShutterstockTool"
_CONFIG_FILE_NAME = "config.json"
_lock = threading.Lock()

# Default download folder
_DEFAULT_DOWNLOAD_FOLDER = os.path.join(
    os.path.expanduser("~"), "Downloads", "ShutterstockImages"
)

# Default configuration values
_DEFAULTS = {
    "api_token": "",
    "download_folder": _DEFAULT_DOWNLOAD_FOLDER,
}


def _get_config_dir() -> str:
    """Return the path to the config directory in %APPDATA%."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        # Fallback for non-Windows or missing APPDATA
        appdata = os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(appdata, _CONFIG_DIR_NAME)


def _get_config_path() -> str:
    """Return the full path to config.json."""
    return os.path.join(_get_config_dir(), _CONFIG_FILE_NAME)


def load_config() -> dict:
    """
    Load configuration from disk. Returns a dict with at least
    'api_token' and 'download_folder' keys. If the config file
    doesn't exist or is corrupt, returns defaults.
    """
    with _lock:
        config_path = _get_config_path()
        config = dict(_DEFAULTS)
        if os.path.isfile(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                if isinstance(stored, dict):
                    # Merge stored values over defaults
                    for key in _DEFAULTS:
                        if key in stored and isinstance(stored[key], str):
                            config[key] = stored[key]
            except (json.JSONDecodeError, OSError, ValueError):
                # Corrupt or unreadable config — use defaults
                pass
        return config


def save_config(config: dict) -> None:
    """
    Save configuration to disk. Creates the config directory if needed.
    Only persists known keys defined in _DEFAULTS.
    """
    with _lock:
        config_dir = _get_config_dir()
        os.makedirs(config_dir, exist_ok=True)
        config_path = _get_config_path()
        # Only write known keys
        to_save = {}
        for key in _DEFAULTS:
            to_save[key] = config.get(key, _DEFAULTS[key])
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=2)


def get_config_path_for_display() -> str:
    """Return the config file path for display in the UI / README."""
    return _get_config_path()
