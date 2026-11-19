#!/usr/bin/env python3
"""Compose the NIRUX boot look for one screen and one palette.

    compose.py --assets DIR --out DIR --width W --height H
               --background RRGGBB --foreground RRGGBB --muted RRGGBB
               --focus RRGGBB [--error RRGGBB] [--grub-fonts DIR]

Writes OUT/grub (a GRUB theme) and OUT/plymouth (a Plymouth script theme).
Standard library only: it runs on the machine being set up, as root, with
nothing but python3. The look follows nirulock's ascii layout: the NIRUX
banner in the accent, "A MINIMAL X11 DESKTOP" in the muted colour and a
block cursor, scanlines on a large banner.
"""
import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

BANNER = [
    "##    ##  ####  #######   ##    ##  ##    ##",
    "###   ##   ##   ##    ##  ##    ##   ##  ## ",
    "####  ##   ##   ##    ##  ##    ##    ####  ",
    "## ## ##   ##   #######   ##    ##     ##   ",
    "##  ####   ##   ##  ##    ##    ##    ####  ",
    "##   ###   ##   ##   ##   ##    ##   ##  ## ",
    "##    ##  ####  ##    ##   ######   ##    ##",
]
TAGLINE = "A MINIMAL X11 DESKTOP"
SCANLINE_MIN_ROW = 24

def _version():
    for p in (Path(__file__).with_name("VERSION"), Path(__file__).parent.parent / "VERSION"):
        if p.is_file():
            return p.read_text().strip()
    return "dev"


VERSION = _version()


# ── colours ────────────────────────────────────────────────────────────────
def rgb(value):
    v = value.strip().lstrip("#")
    if len(v) != 6 or any(c not in "0123456789abcdefABCDEF" for c in v):
        raise SystemExit(f"compose: not a colour: {value}")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def hexc(c):
    return "#%02x%02x%02x" % c


def luminance(c):
    def ch(x):
        x = x / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def banner_colour(focus, foreground, background):
    """nirulock's rule: the accent when it reads well, else the text colour."""
    return focus if contrast(focus, background) >= 4.5 else foreground


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


# ── pictures ───────────────────────────────────────────────────────────────
class Canvas:
    """RGBA pixels, straight alpha."""

    def __init__(self, w, h, fill=(0, 0, 0, 0)):
        self.w, self.h = max(1, w), max(1, h)
        self.px = bytearray(bytes(fill) * (self.w * self.h))

    def blend(self, x, y, colour, alpha):
        """Paint `colour` with coverage alpha (0..255) over the pixel."""
        if alpha <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        i = (y * self.w + x) * 4
        r, g, b, a = self.px[i:i + 4]
        sa = alpha / 255
        da = a / 255
        oa = sa + da * (1 - sa)
        if oa <= 0:
            return
        for k, c in enumerate(colour):
            d = (r, g, b)[k]
            self.px[i + k] = round((c * sa + d * da * (1 - sa)) / oa)
        self.px[i + 3] = round(oa * 255)

    def mask(self, x0, y0, w, h, data, colour):
        for y in range(h):
            row = y * w
            for x in range(w):
                a = data[row + x]
                if a:
                    self.blend(x0 + x, y0 + y, colour, a)

    def rect(self, x0, y0, w, h, colour, alpha=255):
        for y in range(max(0, y0), min(self.h, y0 + h)):
            for x in range(max(0, x0), min(self.w, x0 + w)):
                self.blend(x, y, colour, alpha)

    def png(self, path):
        raw = bytearray()
        stride = self.w * 4
        for y in range(self.h):
            raw.append(0)
            raw.extend(self.px[y * stride:(y + 1) * stride])

        def chunk(kind, data):
            body = kind + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

        out = b"\x89PNG\r\n\x1a\n"
        out += chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 6, 0, 0, 0))
        out += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        out += chunk(b"IEND", b"")
        Path(path).write_bytes(out)


class Glyphs:
    def __init__(self, assets):
        assets = Path(assets)
        self.index = json.loads((assets / "glyphs.json").read_text())
        self.raw = (assets / "glyphs.raw").read_bytes()

    def font(self, kind, size):
        t = self.index[kind]
        sizes = sorted(int(s) for s in t["sizes"])
        size = min(sizes, key=lambda s: (abs(s - size), s))
        return Font(self, t["chars"], t["sizes"][str(size)], size)


class Font:
    def __init__(self, glyphs, chars, meta, size):
        self.g, self.chars, self.size = glyphs, chars, size
        self.adv, self.height, self.ascent = meta["adv"], meta["height"], meta["ascent"]
        self.offset = meta["offset"]

    def cell(self, ch):
        i = self.chars.find(ch)
        if i < 0:
            i = self.chars.find("?")
        n = self.adv * self.height
        start = self.offset + i * n
        return self.g.raw[start:start + n]

    def width(self, text):
        return self.adv * len(text)

    def draw(self, canvas, x, y, text, colours):
        """Draw text with its top-left at (x, y); colours is one colour or a
        list per character."""
        for i, ch in enumerate(text):
            if ch == " ":
                continue
            c = colours[i] if isinstance(colours, list) else colours
            canvas.mask(x + i * self.adv, y, self.adv, self.height, self.cell(ch), c)


def text_png(font, text, colours, path, pad=0):
    c = Canvas(font.width(text) + 2 * pad, font.height + 2 * pad)
    font.draw(c, pad, pad, text, colours)
    c.png(path)
    return c.w, c.h


def solid_png(path, w, h, colour, alpha=255):
    c = Canvas(w, h, (*colour, alpha))
    c.png(path)


# ── layout (nirulock's ascii layout, without the music panel) ──────────────
class Layout:
    def __init__(self, glyphs, w, h):
        self.w, self.h = w, h
        # The text size: about what NIRUX uses at 1080p (20 px), scaled.
        self.text = glyphs.font("text", max(12, min(40, round(h / 54))))
        u = self.text.height
        self.u = u
        probe = glyphs.font("hash", 48)
        adv_ratio, line_ratio = probe.adv / 48, probe.height / 48
        cols, rows = len(BANNER[0]), len(BANNER)
        by_w = w * 0.5 / (cols * adv_ratio)
        by_h = h * 0.26 / (rows * line_ratio)
        self.hash = glyphs.font("hash", round(max(6, min(96, by_w, by_h))))
        self.banner_w = self.hash.adv * cols
        self.banner_h = self.hash.height * rows
        self.tag_w = self.text.width(TAGLINE)


def banner_picture(lay, accent, background):
    """The whole banner, typed: for GRUB, where nothing moves."""
    c = Canvas(lay.banner_w, lay.banner_h)
    cell = lay.hash.cell("#")
    for r, row in enumerate(BANNER):
        for col, ch in enumerate(row):
            if ch == "#":
                c.mask(col * lay.hash.adv, r * lay.hash.height, lay.hash.adv, lay.hash.height, cell, accent)
    if lay.hash.height >= SCANLINE_MIN_ROW:
        for y in range(2, c.h, 3):
            for x in range(c.w):
                i = (y * c.w + x) * 4
                if c.px[i + 3]:
                    c.blend(x, y, background, 255)
    return c


def scanline_picture(lay, background):
    c = Canvas(lay.banner_w, lay.banner_h)
    for y in range(2, c.h, 3):
        c.rect(0, y, c.w, 1, background)
    return c


def box(dirname, prefix, centre, west=None, bar=0, space=0):
    """A GRUB styled box: nine pictures, everything transparent but the
    centre and an optional bar on the left, `space` pixels before the text."""
    d = Path(dirname)
    west_w = bar + space
    for part in ("n", "ne", "e", "se", "s"):
        solid_png(d / f"{prefix}_{part}.png", 1, 1, (0, 0, 0), 0)
    if west:
        for part in ("nw", "sw"):
            solid_png(d / f"{prefix}_{part}.png", west_w, 1, (0, 0, 0), 0)
        w = Canvas(west_w, 1, (*(centre or (0, 0, 0)), 255 if centre else 0))
        w.rect(0, 0, bar, 1, west)
        w.png(d / f"{prefix}_w.png")
    else:
        for part in ("nw", "sw", "w"):
            solid_png(d / f"{prefix}_{part}.png", 1, 1, (0, 0, 0), 0)
    if centre:
        solid_png(d / f"{prefix}_c.png", 1, 1, centre)
    else:
        solid_png(d / f"{prefix}_c.png", 1, 1, (0, 0, 0), 0)


# ── GRUB ───────────────────────────────────────────────────────────────────
def grub_theme(out, glyphs, lay, pal, fonts_dir):
    out.mkdir(parents=True, exist_ok=True)
    bg, fg, muted, accent, err = pal["background"], pal["foreground"], pal["muted"], pal["accent"], pal["error"]
    u = lay.u
    banner_picture(lay, accent, bg).png(out / "banner.png")
    # The tagline with the cursor resting after it, as nirulock ends.
    tag = Canvas(lay.tag_w + 2 * lay.text.adv, lay.text.height)
    lay.text.draw(tag, 0, 0, TAGLINE, muted)
    tag.rect(lay.tag_w + lay.text.adv, 0, lay.text.adv, lay.text.height, accent)
    tag.png(out / "tagline.png")

    # One GRUB font for everything, in the size of the text.
    size = lay.text.size
    font_name = f"NIRUX Mono Regular {size}"
    if fonts_dir:
        src = Path(fonts_dir) / f"nirux-mono-{size}.pf2"
        if not src.is_file():
            raise SystemExit(f"compose: no GRUB font {src}")
        (out / src.name).write_bytes(src.read_bytes())

    selected = mix(bg, fg, 0.09)
    bar = max(3, u // 6)
    box(out, "select", selected, accent, bar, u // 2 + 2)
    box(out, "thumb", mix(bg, fg, 0.35))
    box(out, "frame", None)
    # GRUB's own terminal (e and c): a dark box with a hairline.
    term = out
    for part in ("n", "s"):
        solid_png(term / f"term_{part}.png", 1, 1, mix(bg, fg, 0.18))
    for part in ("e", "w"):
        solid_png(term / f"term_{part}.png", 1, 1, mix(bg, fg, 0.18))
    for part in ("ne", "nw", "se", "sw"):
        solid_png(term / f"term_{part}.png", 1, 1, mix(bg, fg, 0.18))
    solid_png(term / "term_c.png", 1, 1, bg)

    item_h = round(u * 1.55)
    rows = 7
    menu_w = max(lay.banner_w, lay.text.adv * 56)
    menu_w = min(menu_w, lay.w - 4 * u)
    menu_h = item_h * rows
    gap = u * 3 // 4
    block = lay.banner_h + gap + lay.text.height + 2 * u + menu_h + u + lay.text.height
    top = max(u, lay.h * 46 // 100 - block // 2)
    tag_y = top + lay.banner_h + gap
    menu_y = tag_y + lay.text.height + 2 * u
    count_y = menu_y + menu_h + u
    hint_y = lay.h - 2 * u - lay.text.height

    def x_centre(width):
        return f"50%-{width // 2}"

    lines = [
        "# NIRUX boot menu, made by nirusplash " + VERSION + " for this screen.",
        "# nirusplash remove (or nirux boot off) brings back the plain menu.",
        'title-text: ""',
        f'desktop-color: "{hexc(bg)}"',
        f'terminal-font: "{font_name}"',
        'terminal-box: "term_*.png"',
        f"terminal-left: \"{2 * u}\"",
        f"terminal-top: \"{2 * u}\"",
        f"terminal-width: \"100%-{4 * u}\"",
        f"terminal-height: \"100%-{4 * u}\"",
        "terminal-border: \"1\"",
        "",
        "+ image {",
        f"  left = {x_centre(lay.banner_w)}",
        f"  top = {top}",
        f"  width = {lay.banner_w}",
        f"  height = {lay.banner_h}",
        '  file = "banner.png"',
        "}",
        "+ image {",
        f"  left = {x_centre(lay.tag_w)}",
        f"  top = {tag_y}",
        f"  width = {tag.w}",
        f"  height = {tag.h}",
        '  file = "tagline.png"',
        "}",
        "+ boot_menu {",
        f"  left = {x_centre(menu_w)}",
        f"  top = {menu_y}",
        f"  width = {menu_w}",
        f"  height = {menu_h}",
        f'  item_font = "{font_name}"',
        f'  selected_item_font = "{font_name}"',
        f'  item_color = "{hexc(muted)}"',
        f'  selected_item_color = "{hexc(fg)}"',
        f"  item_height = {item_h}",
        "  item_padding = 0",
        "  item_spacing = 0",
        "  icon_width = 0",
        "  icon_height = 0",
        "  item_icon_space = 0",
        '  selected_item_pixmap_style = "select_*.png"',
        '  menu_pixmap_style = "frame_*.png"',
        "  scrollbar = true",
        f"  scrollbar_width = {max(2, u // 8)}",
        '  scrollbar_thumb = "thumb_*.png"',
        '  scrollbar_frame = "frame_*.png"',
        "}",
        "+ label {",
        '  id = "__timeout__"',
        f"  left = {x_centre(menu_w)}",
        f"  top = {count_y}",
        f"  width = {menu_w}",
        f"  height = {lay.text.height}",
        '  align = "left"',
        f'  font = "{font_name}"',
        f'  color = "{hexc(muted)}"',
        '  text = "[ .. ] starting in %d s"',
        "}",
        "+ label {",
        "  left = 0",
        f"  top = {hint_y}",
        "  width = 100%",
        f"  height = {lay.text.height}",
        '  align = "center"',
        f'  font = "{font_name}"',
        f'  color = "{hexc(mix(bg, muted, 0.7))}"',
        '  text = "up/down choose   enter start   e edit   c console"',
        "}",
        "",
    ]
    (out / "theme.txt").write_text("\n".join(lines))
    return {"font": font_name, "size": size}


# ── Plymouth ───────────────────────────────────────────────────────────────
def plymouth_theme(out, glyphs, lay, pal, template):
    out.mkdir(parents=True, exist_ok=True)
    bg, fg, muted, accent, err = pal["background"], pal["foreground"], pal["muted"], pal["accent"], pal["error"]
    u = lay.u
    t = lay.text
    cell = lay.hash.cell("#")
    for name, colour in (("hash", accent), ("hash-hot", fg)):
        c = Canvas(lay.hash.adv, lay.hash.height)
        c.mask(0, 0, lay.hash.adv, lay.hash.height, cell, colour)
        c.png(out / f"{name}.png")
    scanline_picture(lay, bg).png(out / "scan.png")
    # The line, one picture per character: typed by showing them in turn.
    for i, ch in enumerate(TAGLINE):
        text_png(t, ch, muted, out / f"tag-{i:02d}.png")
    solid_png(out / "cursor.png", t.adv, t.height, accent)
    solid_png(out / "cursor-hot.png", t.adv, t.height, fg)
    solid_png(out / "hash-cursor.png", lay.hash.adv, lay.hash.height, fg)
    prompt = "$ unlock disk "
    text_png(t, prompt, [accent] + [muted] * (len(prompt) - 1), out / "prompt.png")
    text_png(t, "•", fg, out / "bullet.png")
    working = "[ .. ] unlocking"
    text_png(t, working, [muted, muted, accent, accent, muted, muted] + [muted] * (len(working) - 6), out / "working.png")
    fail = "[ fail ] wrong password, try again"
    text_png(t, fail, [muted, muted] + [err] * 4 + [muted] * (len(fail) - 6), out / "fail.png")

    hashes = [(r, c) for r, row in enumerate(BANNER) for c, ch in enumerate(row) if ch == "#"]
    gap = u * 3 // 4
    block = lay.banner_h + gap + t.height + u * 5 // 2 + t.height + u * 3
    top = max(u, lay.h * 46 // 100 - block // 2)
    values = {
        "VERSION": VERSION,
        "W": lay.w, "H": lay.h,
        "BG_R": "%.4f" % (bg[0] / 255), "BG_G": "%.4f" % (bg[1] / 255), "BG_B": "%.4f" % (bg[2] / 255),
        "TOP": top,
        "BANNER_W": lay.banner_w, "BANNER_H": lay.banner_h,
        "ADV": lay.hash.adv, "ROW": lay.hash.height,
        "SCAN": 1 if lay.hash.height >= SCANLINE_MIN_ROW else 0,
        "GAP": gap, "U": u,
        "TAG_W": lay.tag_w, "TAG_ADV": t.adv, "TAG_LEN": len(TAGLINE), "TAG_H": t.height,
        "PROMPT_W": t.width(prompt),
        "N": len(hashes),
        "HASH_SET": "\n".join(f"global.hr[{i}] = {r}; global.hc[{i}] = {c};" for i, (r, c) in enumerate(hashes)),
    }
    script = template
    for k, v in values.items():
        script = script.replace("@" + k + "@", str(v))
    left = [w for w in script.replace("(", " ").replace(")", " ").replace(";", " ").split()
            if len(w) > 2 and w.startswith("@") and w.endswith("@")]
    if left:
        raise SystemExit(f"compose: unfilled template values {left[:3]}")
    (out / "nirux.script").write_text(script)
    (out / "nirux.plymouth").write_text(
        "[Plymouth Theme]\n"
        "Name=NIRUX\n"
        "Description=NIRUX: the banner typed in, a password prompt in the same style\n"
        "ModuleName=script\n\n"
        "[script]\n"
        "ImageDir=/usr/share/plymouth/themes/nirux\n"
        "ScriptFile=/usr/share/plymouth/themes/nirux/nirux.script\n"
    )


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--assets", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--width", type=int, required=True)
    p.add_argument("--height", type=int, required=True)
    p.add_argument("--background", default="0f0f10")
    p.add_argument("--foreground", default="e5e5e5")
    p.add_argument("--muted", default="a8a8a8")
    p.add_argument("--focus", default="5a5a60")
    p.add_argument("--error", default="d77a7a")
    p.add_argument("--grub-fonts")
    p.add_argument("--template")
    p.add_argument("--only", choices=("grub", "plymouth"))
    a = p.parse_args(argv)
    if not (320 <= a.width <= 16384 and 200 <= a.height <= 16384):
        raise SystemExit(f"compose: unlikely screen {a.width}x{a.height}")
    pal = {k: rgb(getattr(a, k)) for k in ("background", "foreground", "muted", "focus", "error")}
    pal["accent"] = banner_colour(pal["focus"], pal["foreground"], pal["background"])
    glyphs = Glyphs(a.assets)
    lay = Layout(glyphs, a.width, a.height)
    out = Path(a.out)
    info = {"width": a.width, "height": a.height, "banner": lay.hash.size, "text": lay.text.size}
    if a.only != "plymouth":
        info["grub"] = grub_theme(out / "grub", glyphs, lay, pal, a.grub_fonts)
    if a.only != "grub":
        template = Path(a.template or Path(__file__).with_name("nirux.script.in")).read_text()
        plymouth_theme(out / "plymouth", glyphs, lay, pal, template)
    print(json.dumps(info))


if __name__ == "__main__":
    sys.exit(main())
