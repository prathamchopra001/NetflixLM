"""Pillow-rendered keyframes: light text on a dark frame, one text per line."""

import io

from PIL import Image, ImageDraw, ImageFont


def render(lines: list[str], size: tuple[int, int] = (1280, 720), font_px: int = 44) -> bytes:
    img = Image.new("RGB", size, (28, 32, 40))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=font_px)
    for i, text in enumerate(lines):
        draw.text((60, 60 + i * (font_px * 2)), text, fill=(240, 240, 240), font=font)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
