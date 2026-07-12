# handle config in appdata. windows permissions are a nightmare otherwise
import json
import os
import threading
_CONFIG_DIR_NAME = "ShutterstockTool"
_CONFIG_FILE_NAME = "config.json"
_lock = threading.Lock()
_DEFAULT_DOWNLOAD_FOLDER = os.path.join(
    os.path.expanduser("~"), "Downloads", "ShutterstockImages"
)
_DEFAULTS = {
    "api_token": "",
    "download_folder": _DEFAULT_DOWNLOAD_FOLDER,
}
def _get_config_dir() -> str:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(appdata, _CONFIG_DIR_NAME)
def _get_config_path() -> str:
    return os.path.join(_get_config_dir(), _CONFIG_FILE_NAME)
def load_config() -> dict:
    with _lock:
        config_path = _get_config_path()
        config = dict(_DEFAULTS)
        if os.path.isfile(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                if isinstance(stored, dict):
                    for key in _DEFAULTS:
                        if key in stored and isinstance(stored[key], str):
                            config[key] = stored[key]
            except (json.JSONDecodeError, OSError, ValueError):
                pass
        return config
def save_config(config: dict) -> None:
    with _lock:
        config_dir = _get_config_dir()
        os.makedirs(config_dir, exist_ok=True)
        config_path = _get_config_path()
        to_save = {}
        for key in _DEFAULTS:
            to_save[key] = config.get(key, _DEFAULTS[key])
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=2)
def get_config_path_for_display() -> str:
    return _get_config_path()