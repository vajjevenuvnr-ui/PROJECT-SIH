"""YouTube thumbnail for the Kshetra demo video (1280 x 720 PNG).

Run from the project root:
    backend\\.venv\\Scripts\\python docs\\thumbnail\\make_thumbnail.py
Output: docs/thumbnail/kshetra_thumbnail.png

Edit the TEXT block below to change the wording. Colours match frontend/src/styles/theme.css.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "kshetra_thumbnail.png"
W, H = 1280, 720

# ---- TEXT -----------------------------------------------------------------------------------------
BADGE = "SIH 2026  ·  PS 26074"
KICKER = "MoES – IMD"
HEAD_1 = "WEATHER FOR"
HEAD_2 = "EVERY PANCHAYAT"
SUB = "Block forecast  →  panchayat forecast  →  crop advice"
TELUGU = "మీ ఊరి వాతావరణం"          # "your village's weather" (drawn only if Pillow can shape Telugu)
BLOCK_LABEL, BLOCK_VALUE = "BLOCK", "8 mm"
GP_LABEL = "PANCHAYATS: 0 – 38 mm"

# ---- COLOURS (theme.css) ----------------------------------------------------------------------------
PRIMARY = (11, 93, 75)
PRIMARY_DARK = (6, 52, 42)
ACCENT = (232, 163, 23)
INK = (29, 42, 48)
WHITE = (255, 255, 255)
RAIN = [(236, 244, 250), (191, 219, 242), (120, 180, 230), (50, 128, 205), (22, 78, 160), (18, 44, 110)]

FONTS = Path("C:/Windows/Fonts")


def font(name: str, size: int, index: int = 0) -> ImageFont.FreeTypeFont:
    for cand in (name, "segoeuib.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(str(FONTS / cand), size, index=index)
        except OSError:
            continue
    return ImageFont.load_default()


def rain_colour(mm: float) -> tuple[int, int, int]:
    # IMD rainfall categories: 0 / 2.5 / 15.6 / 64.5 / 115.6 mm (demo range stretched for contrast)
    for limit, col in zip((0.5, 2.5, 8, 15.6, 25), RAIN):
        if mm < limit:
            return col
    return RAIN[-1]


def background() -> Image.Image:
    img = Image.new("RGB", (W, H), PRIMARY_DARK)
    d = ImageDraw.Draw(img)
    for y in range(H):  # diagonal-ish vertical gradient
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(PRIMARY[i] * (1 - t) + PRIMARY_DARK[i] * t) for i in range(3)))
    # faint terrain contour rings (as on the login page)
    rings = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rings)
    for r in range(60, 700, 55):
        rd.ellipse([980 - r * 1.3, 380 - r, 980 + r * 1.3, 380 + r], outline=(255, 255, 255, 18), width=2)
    img.paste(rings, (0, 0), rings)
    return img


def split_map(img: Image.Image) -> None:
    """Right side: one flat block value vs a patchwork of panchayat values (the product's core idea)."""
    x0, y0, cw, ch, gap = 700, 150, 250, 400, 30
    d = ImageDraw.Draw(img)
    # card shadows
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    for i in range(2):
        x = x0 + i * (cw + gap)
        sd.rounded_rectangle([x + 8, y0 + 12, x + cw + 8, y0 + ch + 12], 28, fill=(0, 0, 0, 110))
    img.paste(sh.filter(ImageFilter.GaussianBlur(14)), (0, 0), sh.filter(ImageFilter.GaussianBlur(14)))

    # LEFT card: the block (one value)
    d.rounded_rectangle([x0, y0, x0 + cw, y0 + ch], 28, fill=rain_colour(8))
    d.text((x0 + cw / 2, y0 + 40), BLOCK_LABEL, font=font("segoeuib.ttf", 30), fill=INK, anchor="mm")
    d.text((x0 + cw / 2, y0 + ch / 2 + 10), BLOCK_VALUE, font=font("seguibl.ttf", 66), fill=INK, anchor="mm")
    d.text((x0 + cw / 2, y0 + ch - 42), "IMD", font=font("segoeuib.ttf", 26), fill=INK, anchor="mm")

    # RIGHT card: panchayats (Voronoi-like patchwork of rain values around a storm cell)
    xr = x0 + cw + gap
    card = Image.new("RGB", (cw, ch), WHITE)
    rnd = random.Random(26074)
    seeds = [(rnd.uniform(0, cw), rnd.uniform(0, ch)) for _ in range(26)]
    storm = (cw * 0.68, ch * 0.32)
    vals = [max(0.0, 38 * math.exp(-((sx - storm[0]) ** 2 + (sy - storm[1]) ** 2) / (2 * 95 ** 2)) + rnd.uniform(-2, 2))
            for sx, sy in seeds]
    px = card.load()
    for yy in range(ch):
        for xx in range(cw):
            k = min(range(len(seeds)), key=lambda i: (xx - seeds[i][0]) ** 2 + (yy - seeds[i][1]) ** 2)
            px[xx, yy] = rain_colour(vals[k])
    # panchayat borders
    edges = card.filter(ImageFilter.FIND_EDGES).convert("L").point(lambda v: 255 if v > 8 else 0)
    card.paste(Image.new("RGB", (cw, ch), WHITE), (0, 0), edges)
    mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw - 1, ch - 1], 28, fill=255)
    img.paste(card, (xr, y0), mask)
    # label chip under the cards
    f = font("segoeuib.ttf", 24)
    d.text((xr + cw / 2, y0 + ch + 34), GP_LABEL, font=f, fill=WHITE, anchor="mm")
    d.text((x0 + cw / 2, y0 + ch + 34), "ONE VALUE", font=f, fill=WHITE, anchor="mm")
    # arrow between cards
    ax, ay = x0 + cw + gap / 2, y0 + ch / 2
    d.ellipse([ax - 30, ay - 30, ax + 30, ay + 30], fill=ACCENT)
    d.polygon([(ax - 10, ay - 14), (ax + 14, ay), (ax - 10, ay + 14)], fill=INK)


def text_side(img: Image.Image) -> None:
    d = ImageDraw.Draw(img)
    # logo
    logo = Image.open(ROOT / "frontend/public/brand/logo-dark.png").convert("RGBA")
    logo = logo.resize((int(logo.width * 70 / logo.height), 70), Image.LANCZOS)
    img.paste(logo, (60, 48), logo)

    # SIH badge (accent pill)
    fb = font("seguibl.ttf", 34)
    bw = d.textlength(BADGE, font=fb) + 48
    d.rounded_rectangle([60, 150, 60 + bw, 208], 29, fill=ACCENT)
    d.text((60 + bw / 2, 179), BADGE, font=fb, fill=INK, anchor="mm")
    d.text((60 + bw + 18, 179), KICKER, font=font("segoeuib.ttf", 28), fill=(210, 235, 228), anchor="lm")

    # headline with a soft shadow
    for line, y, size, col in ((HEAD_1, 250, 70, WHITE), (HEAD_2, 330, 70, ACCENT)):
        f = font("seguibl.ttf", size)
        size_fit = size
        while d.textlength(line, font=f) > 610 and size_fit > 40:
            size_fit -= 2
            f = font("seguibl.ttf", size_fit)
        d.text((64, y + 4), line, font=f, fill=(0, 0, 0))
        d.text((60, y), line, font=f, fill=col)

    d.text((62, 438), SUB, font=font("segoeuib.ttf", 27), fill=(220, 238, 232))

    if features.check("raqm"):  # Telugu needs complex-script shaping
        ft = ImageFont.truetype(str(FONTS / "Nirmala.ttc"), 44, index=0, layout_engine=ImageFont.Layout.RAQM)
        d.text((62, 496), TELUGU, font=ft, fill=WHITE)

    # bottom strip: languages
    langs = "తెలుగు  ·  हिंदी  ·  English" if features.check("raqm") else "Telugu  ·  Hindi  ·  English"
    fl = (ImageFont.truetype(str(FONTS / "Nirmala.ttc"), 28, index=0, layout_engine=ImageFont.Layout.RAQM)
          if features.check("raqm") else font("segoeuib.ttf", 28))
    d.rounded_rectangle([60, 600, 60 + d.textlength(langs, font=fl) + 40, 652], 26, outline=(255, 255, 255), width=2)
    d.text((80, 626), langs, font=fl, fill=WHITE, anchor="lm")


def main() -> None:
    img = background()
    split_map(img)
    text_side(img)
    img.save(OUT, optimize=True)
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB, {W}x{H}); Telugu shaping: {features.check('raqm')}")


if __name__ == "__main__":
    main()
