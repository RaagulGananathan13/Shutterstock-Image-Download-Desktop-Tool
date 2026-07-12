# stream the download so we dont blow up the ram
import os
import re
import requests
def make_safe_filename(description: str, image_id: str) -> str:
    if description and description.strip():
        safe = description.lower().strip()
        safe = safe.replace(" ", "-")
        safe = re.sub(r"[^a-z0-9\-]", "", safe)
        safe = re.sub(r"-{2,}", "-", safe)  
        safe = safe.strip("-")
        safe = safe[:50]
        if safe:
            return f"{safe}_{image_id}.jpg"
    return f"shutterstock_{image_id}.jpg"
def resolve_filename_collision(dest_path: str) -> str:
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
                    if chunk:  
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(bytes_downloaded, total_bytes)
        final_path = resolve_filename_collision(dest_path)
        if final_path != dest_path and os.path.exists(dest_path):
            os.rename(part_path, final_path)
        else:
            os.rename(part_path, dest_path)
            final_path = dest_path
        return final_path
    except Exception:
        if os.path.exists(part_path):
            try:
                os.remove(part_path)
            except OSError:
                pass
        raise