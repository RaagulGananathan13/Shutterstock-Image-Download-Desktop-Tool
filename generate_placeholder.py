# hacky script to generate a placeholder png for the grid
from PIL import Image, ImageDraw, ImageFont
import os
WIDTH = 200
HEIGHT = 150
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
def generate():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(42, 42, 62))
    draw = ImageDraw.Draw(img)
    cx, cy = WIDTH // 2, HEIGHT // 2 - 10
    draw.rounded_rectangle(
        [cx - 35, cy - 18, cx + 35, cy + 22],
        radius=6,
        fill=(55, 55, 80),
        outline=(80, 80, 110),
        width=1,
    )
    draw.ellipse(
        [cx - 14, cy - 12, cx + 14, cy + 16],
        fill=(42, 42, 62),
        outline=(80, 80, 110),
        width=1,
    )
    draw.rectangle(
        [cx + 15, cy - 22, cx + 25, cy - 18],
        fill=(55, 55, 80),
        outline=(80, 80, 110),
        width=1,
    )
    text = "Loading..."
    try:
        font = ImageFont.truetype("segoeui.ttf", 13)
    except (OSError, IOError):
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    tx = (WIDTH - tw) // 2
    ty = cy + 30
    draw.text((tx, ty), text, fill=(140, 140, 180), font=font)
    output_path = os.path.join(OUTPUT_DIR, "placeholder.png")
    img.save(output_path, "PNG")
    print(f"Generated: {output_path}")
if __name__ == "__main__":
    generate()