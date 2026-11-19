#!/usr/bin/env python3
"""Build the glyph tables nirusplash composes its pictures from.

    tools/build-assets.py FONT.ttf OUTDIR

Needs Pillow. Writes OUTDIR/glyphs.json and OUTDIR/glyphs.raw: every glyph
is an 8-bit alpha mask of one monospace cell (advance x line height, the
baseline at the ascent). The installer itself only needs the Python
standard library, so the pictures can be made on the machine for its own
screen and colours.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Text: printable ASCII and the bullet of the password prompt.
TEXT_CHARS = "".join(chr(c) for c in range(32, 127)) + "•"
TEXT_SIZES = range(10, 49)
# The banner's "#", from a small panel to a 4K monitor.
HASH_SIZES = range(6, 97)


def table(font_path, chars, sizes, raw):
    out = {}
    for size in sizes:
        font = ImageFont.truetype(font_path, size)
        ascent, descent = font.getmetrics()
        adv = round(font.getlength("M"))
        height = ascent + descent
        offset = len(raw)
        for ch in chars:
            img = Image.new("L", (adv, height), 0)
            ImageDraw.Draw(img).text((0, ascent), ch, fill=255, font=font, anchor="ls")
            raw.extend(img.tobytes())
        out[str(size)] = {"adv": adv, "height": height, "ascent": ascent, "offset": offset}
    return out


def main():
    font_path, outdir = sys.argv[1], Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    raw = bytearray()
    index = {
        "font": Path(font_path).name,
        "text": {"chars": TEXT_CHARS, "sizes": table(font_path, TEXT_CHARS, TEXT_SIZES, raw)},
        "hash": {"chars": "#", "sizes": table(font_path, "#", HASH_SIZES, raw)},
    }
    (outdir / "glyphs.raw").write_bytes(bytes(raw))
    (outdir / "glyphs.json").write_text(json.dumps(index, separators=(",", ":"), ensure_ascii=True))
    print(f"glyphs: {len(raw)} bytes")


if __name__ == "__main__":
    main()
