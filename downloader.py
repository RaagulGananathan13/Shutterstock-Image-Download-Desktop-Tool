"""
downloader.py — Threaded file download logic with progress callback and safe file handling.

Downloads to a .part temp file, renames on success, cleans up on failure.
Generates safe filenames from image descriptions with collision handling.
"""

import os
import re

import requests


def make_safe_filename(description: str, image_id: str) -> str:
    """
    Create a safe filename from the image description and Shutterstock ID.

    Format: ``safe_title_imageid.jpg``
    - Lowercased, spaces→hyphens, non-alphanumeric chars stripped
    - Truncated to ~50 chars
    - Falls back to ``shutterstock_imageid.jpg`` if description is empty
    """
    if description and description.strip():
        safe = description.lower().strip()
        safe = safe.replace(" ", "-")
        safe = re.sub(r"[^a-z0-9\-]", "", safe)
        safe = re.sub(r"-{2,}", "-", safe)  # collapse multiple hyphens
        safe = safe.strip("-")
        safe = safe[:50]
        if safe:
            return f"{safe}_{image_id}.jpg"
    return f"shutterstock_{image_id}.jpg"


def resolve_filename_collision(dest_path: str) -> str:
    """
    If dest_path already exists, append _1, _2, ... until a free name is found.
    """
    if not os.path.exists(dest_path):
        return dest_path
    base, ext = os.path.splitext(dest_path)
    counter = 1
    while True:
        candidate = f"{base}_{counter}{ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def download_file(
    url: str,
    dest_path: str,
    progress_callback=None,
) -> str:
    """
    Stream-download a file from `url` to `dest_path`.

    - Writes to ``dest_path + '.part'`` while in progress.
    - Renames to final name on success.
    - Deletes partial file on failure.
    - Calls ``progress_callback(bytes_downloaded, total_bytes)`` after each chunk.
      ``total_bytes`` may be 0 if Content-Length is absent.

    Returns the final file path (which may differ from dest_path if collision
    handling was applied before calling this function).

    Raises:
        requests.exceptions.RequestException on network errors.
        OSError on filesystem errors.
    """
    # Ensure target directory exists
    dest_dir = os.path.dirname(dest_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    part_path = dest_path + ".part"
    bytes_downloaded = 0

    try:
        with requests.get(url, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            total_bytes = int(resp.headers.get("Content-Length", 0))

            with open(part_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:  # filter out keep-alive empty chunks
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(bytes_downloaded, total_bytes)

        # Success — rename .part to final filename
        # Handle collision one more time in case another download landed in the meantime
        final_path = resolve_filename_collision(dest_path)
        if final_path != dest_path and os.path.exists(dest_path):
            # dest_path was taken, use the resolved path
            os.rename(part_path, final_path)
        else:
            os.rename(part_path, dest_path)
            final_path = dest_path

        return final_path

    except Exception:
        # Clean up partial file on any failure
        if os.path.exists(part_path):
            try:
                os.remove(part_path)
            except OSError:
                pass
        raise
