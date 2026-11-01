#!/usr/bin/env python3
"""
Elo Cola -- single UV texture atlas generator.

Produces exactly ONE 2048x2048 RGB PNG carrying every visible surface of the
can: the printed cobalt label (wrapped 360 degrees), the brushed aluminium
lid with its scored aperture and rivet, the concave base, the rolled rim and
the pull tab.

    python3 scripts/generate_texture.py                     # final design
    python3 scripts/generate_texture.py --concept A -o x.png # a concept

Three label directions are implemented:

  A  VERTICAL   oversized white letters stacked up the barrel, one red rule.
                (reference point: heavy vertical type on matte metal, as in
                 Studio Uzi's Nokta cans)
  B  MONOGRAM   an original geometric eclipse mark over a bold wordmark.
  C  LUXURY     small, widely letterspaced wordmark adrift in negative space.

Shared art direction, drawn from modern packaging practice:
  * ONE flat, deep cobalt field -- no diagonal pattern, no busy gradients.
    (United Sodas: a single matte colour per can plus white type, nothing else)
  * contrast carries the design, not ornament (the stated principle behind
    Pepsi's 2023 identity).
  * warm white type, a very small amount of vivid red, brushed aluminium.
  * minimal supporting copy; generous negative space.

Dependencies: Pillow + numpy only (no Blender needed).

ELO COLA is an original brand created for this project.  No third-party
beverage trademark, logo, typeface or artwork appears anywhere.  Type is set
in Outfit and Instrument Sans (SIL Open Font License, vendored in
scripts/fonts/ with their licences).
"""

import argparse
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import can_profile as CP

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

# ---------------------------------------------------------------------------
# Palette -- deep cobalt, warm white, a whisper of red, brushed aluminium
# ---------------------------------------------------------------------------

COBALT       = (9,   45, 143)      # the field
COBALT_DEEP  = (5,   28,  96)      # extremes of the barrel only
COBALT_SHADE = (8,   38, 121)
WHITE        = (247, 245, 240)     # warm white
WHITE_SOFT   = (214, 219, 232)
RED          = (211,  28,  34)     # vivid, used sparingly

ALU_BASE     = (196, 200, 206)
ALU_LIGHT    = (231, 234, 238)
ALU_MID      = (172, 177, 184)
ALU_DARK     = (138, 143, 151)
ALU_SHADOW   = (108, 113, 121)

SS = 3           # supersample factor for vector art


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def font(name, size):
    p = os.path.join(FONT_DIR, name + ".ttf")
    if os.path.exists(p):
        return ImageFont.truetype(p, size)
    for fb in ("/usr/share/fonts/opentype/inter/Inter-Bold.otf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(fb):
            return ImageFont.truetype(fb, size)
    raise RuntimeError("no usable font found")


def tracked(draw, xy, text, fnt, fill, tracking=0, anchor="mm"):
    """Draw text with extra letter spacing.  Returns the drawn width."""
    widths = [draw.textlength(ch, font=fnt) for ch in text]
    total = sum(widths) + tracking * max(0, len(text) - 1)
    x, y = xy
    if anchor[0] == "m":
        x -= total / 2.0
    elif anchor[0] == "r":
        x -= total
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=fnt, fill=fill, anchor="l" + anchor[1])
        x += w + tracking
    return total


def vgrad(w, h, stops):
    ys = np.linspace(0.0, 1.0, h)
    out = np.zeros((h, w, 3), dtype=np.float32)
    pos = [s[0] for s in stops]
    cols = np.array([s[1] for s in stops], dtype=np.float32)
    for c in range(3):
        out[:, :, c] = np.interp(ys, pos, cols[:, c])[:, None]
    return out


def seeded_noise(h, w, seed, blur=0):
    rng = np.random.default_rng(seed)
    n = rng.random((h, w)).astype(np.float32)
    if blur:
        img = Image.fromarray((n * 255).astype(np.uint8))
        img = img.filter(ImageFilter.GaussianBlur(blur))
        n = np.asarray(img, dtype=np.float32) / 255.0
    return n


def region_px(name):
    u0, v0, u1, v1 = CP.REGIONS[name]
    A = CP.ATLAS
    return (int(round(u0 * A)), int(round((1 - v1) * A)),
            int(round(u1 * A)), int(round((1 - v0) * A)))


# ---------------------------------------------------------------------------
# Label -- shared field, then one of three concepts
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Concept D helpers: the sweeping wave and the brush-script logotype
# ---------------------------------------------------------------------------

# The wave is a single sinusoid in u, so it closes at the u = 0 / u = 1
# seam.  It is then pushed toward its low side by a Mobius warp
#     s = (f + b) / (1 + b f)
# which is smooth everywhere (a gamma curve puts a cusp at the trough) and
# holds the boundary low around most of the circumference.  Cobalt
# therefore dominates the can and red is concentrated into one flank.
WAVE = dict(phase=0.47, bias=0.50, mid=645.0, amp=495.0,
            thick=60.0, thin_off=132.0, thin_scale=0.34)


def script_elo(size, colour, weight=0.037):
    """
    The Elo logotype: a brush script grown to display weight.

    The face is light, so the glyph coverage is blurred and re-ramped, which
    thickens the strokes while keeping the ends round -- a smoother result
    than a morphological dilate, and it keeps the script's own rhythm.
    Returns an RGBA image tightly cropped to the ink.
    """
    f = font("NothingYouCouldDo-Regular", size)
    pad = int(size * 0.55)
    w = int(f.getlength("Elo") + 2 * pad)
    h = int(size * 1.9)
    lay = Image.new("L", (w, h), 0)
    ImageDraw.Draw(lay).text((w // 2, h // 2), "Elo", font=f, fill=255,
                             anchor="mm")
    r = max(1.0, size * weight)
    lay = lay.filter(ImageFilter.GaussianBlur(r))
    a = np.asarray(lay, dtype=np.float32)
    lo, hi = 33.0, 47.0          # tight ramp -> crisp edge, not a soft glow
    a = np.clip((a - lo) / (hi - lo), 0.0, 1.0) * 255.0
    alpha = Image.fromarray(a.astype(np.uint8), "L")
    out = Image.new("RGBA", (w, h), colour + (0,))
    out.putalpha(alpha)
    return out.crop(out.getbbox())


def wave_field(W, H, rows):
    """
    The cobalt / white / red sweep.

    The boundary is a single-cycle sinusoid in u, so it closes seamlessly
    at the u = 0 / u = 1 seam.  The white band's VERTICAL thickness is
    scaled by sqrt(1 + slope^2) so that its width measured perpendicular to
    the curve stays constant, which is what makes it read as a drawn stroke
    rather than a squashed stripe.
    """
    cfg = WAVE
    y0 = rows["y0"]
    X, Y = np.meshgrid(np.arange(W, dtype=np.float32),
                       np.arange(H, dtype=np.float32))
    u = X / W
    ang = 2.0 * math.pi * (u - cfg["phase"])
    b = cfg["bias"]
    f = np.sin(ang)
    shaped = (f + b) / (1.0 + b * f)
    yb = (cfg["mid"] + cfg["amp"] * shaped) - y0
    # d(yb)/dX for the perpendicular-width correction
    dshaped = (1.0 - b * b) / np.square(1.0 + b * f)
    slope = cfg["amp"] * dshaped * np.cos(ang) * (2.0 * math.pi / W)
    t = cfg["thick"] * np.sqrt(1.0 + np.clip(slope * slope, 0.0, 36.0))

    img = np.zeros((H, W, 3), dtype=np.float32)
    img[:, :] = np.array(COBALT, dtype=np.float32)

    def band(centre, half, colour):
        d = Y - centre
        cov = np.clip((half + 0.75 - np.abs(d)) / 1.5, 0.0, 1.0)[:, :, None]
        return cov, np.array(colour, dtype=np.float32)

    # red everything below the stroke
    dred = np.clip((Y - (yb + t * 0.5) + 0.75) / 1.5, 0.0, 1.0)[:, :, None]
    img = img * (1 - dred) + np.array(RED, dtype=np.float32) * dred

    # the thin companion stroke, sitting inside the red
    cov, col = band(yb + cfg["thin_off"] * np.sqrt(1.0 + slope * slope),
                    t * 0.5 * cfg["thin_scale"], WHITE)
    img = img * (1 - cov) + col * cov

    # the main stroke
    cov, col = band(yb, t * 0.5, WHITE)
    img = img * (1 - cov) + col * cov
    return img


def label_field(W, H, rows):
    """
    The flat cobalt field.  Almost flat on purpose: the barrel's form comes
    from the 3D lighting, not from baked gradients.  Only the very top and
    bottom darken, the way real print does as it wraps out of sight, plus a
    trace of mottling so the ink is not mathematically uniform.
    """
    f = lambda row: (row - rows["y0"]) / H
    stops = sorted([
        (0.000, COBALT_DEEP),
        (max(0.001, f(rows["body_hi"]) * 0.55), COBALT_SHADE),
        (f(rows["body_hi"]), COBALT),
        (f(rows["body_lo"]), COBALT),
        (min(0.999, f(rows["body_lo"]) + 0.035), COBALT_SHADE),
        (1.000, COBALT_DEEP),
    ], key=lambda s: s[0])
    bg = vgrad(W, H, stops)

    # extremely gentle large-scale mottling (print is never perfectly even)
    mot = seeded_noise(H // 16, W // 16, 7, blur=2.2)
    mot = np.asarray(Image.fromarray((mot * 255).astype(np.uint8))
                     .resize((W, H), Image.BICUBIC), dtype=np.float32) / 255.0
    bg = np.clip(bg + (mot[:, :, None] - 0.5) * 4.0, 0, 255)
    # fine ink speckle
    bg = np.clip(bg + (seeded_noise(H, W, 13)[:, :, None] - 0.5) * 2.4, 0, 255)
    return bg


def monogram_mark(layer, cx, cy, r, white, red):
    """
    The Elo monogram: a bracket-shaped white 'E' built from three bars, with
    the top bar closed by a single red square.  Rectangles only -- entirely
    original, and with no resemblance to any existing symbol or flag.
    """
    d = ImageDraw.Draw(layer)
    S = SS
    bw = r * 0.235                       # bar weight
    half = r
    lx = cx - r * 0.78                   # stem left edge
    top, bot = cy - half, cy + half
    rx_long = cx + r * 0.62              # top / bottom bar right edge
    rx_mid = cx + r * 0.16               # middle bar is shorter
    d.rectangle([lx * S, top * S, (lx + bw) * S, bot * S], fill=white + (255,))
    d.rectangle([lx * S, top * S, rx_long * S, (top + bw) * S], fill=white + (255,))
    d.rectangle([lx * S, (cy - bw / 2) * S, rx_mid * S, (cy + bw / 2) * S],
                fill=white + (255,))
    d.rectangle([lx * S, (bot - bw) * S, rx_long * S, bot * S], fill=white + (255,))
    # the one red accent in the whole design
    d.rectangle([(rx_long - bw) * S, top * S, rx_long * S, (top + bw) * S],
                fill=red + (255,))


def concept_A(img, vec, W, H, rows, CXF, row):
    """
    VERTICAL -- the chosen direction.

    One oversized white letter stack running up the barrel, a single red
    rule locked to the left edge of the type, and nothing else above it.
    The stack is set letter by letter so each glyph is optically centred on
    the can's -Y axis, and the red rule is the only accent in the design.
    """
    d = ImageDraw.Draw(img)
    cap = 232
    gap = 24
    letters = "ELO"
    f = font("Outfit-Bold", int(cap * 1.36))
    total = len(letters) * cap + (len(letters) - 1) * gap
    mid = row((rows["body_hi"] + rows["body_lo"]) / 2)
    top = mid - total / 2 - 46
    for i, ch in enumerate(letters):
        d.text((CXF, top + i * (cap + gap) + cap / 2), ch, font=f,
               fill=WHITE, anchor="mm")
    bottom = top + total

    # the single red accent: a rule the exact height of the stack, set just
    # clear of the widest glyph so it reads as part of the lockup
    widest = max(d.textlength(ch, font=f) for ch in letters)
    rx = CXF - widest / 2 - 74
    vd = ImageDraw.Draw(vec)
    S = SS
    vd.rectangle([(rx - 2.5) * S, top * S, (rx + 2.5) * S, bottom * S],
                 fill=RED + (255,))

    tracked(d, (CXF, bottom + 56), "COLA",
            font("Outfit-Bold", 42), WHITE, tracking=34)
    tracked(d, (CXF, row(rows["body_lo"] - 35)), "355 ml   \u00b7   12 FL OZ",
            font("InstrumentSans-Regular", 24), WHITE_SOFT, tracking=6)


def concept_B(img, vec, W, H, rows, CXF, row):
    """MONOGRAM -- original eclipse mark above a bold wordmark."""
    monogram_mark(vec, CXF, row(rows["body_hi"] + 252), 96, WHITE, RED)
    vd = ImageDraw.Draw(vec)
    S = SS
    vd.rectangle([(CXF - 300) * S, row(rows["body_lo"] - 118) * S,
                  (CXF + 300) * S, (row(rows["body_lo"] - 118) + 3) * S],
                 fill=RED + (255,))

    d = ImageDraw.Draw(img)
    tracked(d, (CXF, row(rows["body_hi"] + 568)), "ELO",
            font("Outfit-Bold", 300), WHITE, tracking=-6)
    tracked(d, (CXF, row(rows["body_hi"] + 742)), "COLA",
            font("Outfit-Bold", 46), WHITE, tracking=34)
    tracked(d, (CXF, row(rows["body_lo"] - 64)), "355 ml   ·   12 FL OZ",
            font("InstrumentSans-Regular", 26), WHITE_SOFT, tracking=6)


def concept_C(img, vec, W, H, rows, CXF, row):
    """LUXURY -- small, widely spaced wordmark surrounded by cobalt."""
    vd = ImageDraw.Draw(vec)
    S = SS
    mid = row((rows["body_hi"] + rows["body_lo"]) / 2)
    vd.rectangle([(CXF - 172) * S, (mid + 62) * S,
                  (CXF + 172) * S, (mid + 64) * S], fill=WHITE + (220,))
    vd.rectangle([(CXF - 34) * S, (mid + 168) * S,
                  (CXF + 34) * S, (mid + 171) * S], fill=RED + (255,))

    d = ImageDraw.Draw(img)
    tracked(d, (CXF, mid - 20), "ELO", font("Outfit-Bold", 176),
            WHITE, tracking=26)
    tracked(d, (CXF, mid + 116), "COLA", font("InstrumentSans-Bold", 30),
            WHITE, tracking=38)
    tracked(d, (CXF, row(rows["body_hi"] + 118)), "ELO BEVERAGE CO.",
            font("InstrumentSans-Regular", 23), WHITE_SOFT, tracking=9)
    tracked(d, (CXF, row(rows["body_lo"] - 74)), "355 ml   ·   12 FL OZ",
            font("InstrumentSans-Regular", 24), WHITE_SOFT, tracking=6)


def concept_D(img, vec, W, H, rows, CXF, row):
    """
    WAVE -- the chosen direction.

    A deep cobalt can crossed by one sweeping white stroke with red beyond
    it, a brush-script Elo logotype in the blue field, and COLA letterspaced
    beneath.  The wave is a single-cycle sinusoid so it wraps seamlessly;
    the curve and the logotype are both drawn here from scratch.
    """
    d = ImageDraw.Draw(img)

    logo = script_elo(900, WHITE)
    # 470 px of a 2048 px wrap is ~82 deg of arc -- the proportion a real
    # can logotype occupies, and it stays clear of the silhouette.
    maxw = 470
    if logo.width > maxw:
        logo = logo.resize((maxw, int(logo.height * maxw / logo.width)),
                           Image.LANCZOS)
    ly = int(row(rows["body_hi"] + 355) - logo.height // 2)
    img.alpha_composite(logo, (int(CXF - logo.width // 2), ly))

    # the logotype's underswash: a tapered stroke, drawn not borrowed
    vd = ImageDraw.Draw(vec)
    S = SS
    y_sw = ly + logo.height + 6
    left, right = CXF - logo.width * 0.50, CXF + logo.width * 0.52
    pts_t, pts_b = [], []
    N = 120
    for i in range(N + 1):
        tpar = i / N
        x = left + (right - left) * tpar
        y = y_sw + 34.0 * math.sin(math.pi * tpar) - 16.0 * tpar
        hw = 4.0 + 21.0 * math.sin(math.pi * tpar) ** 0.55
        pts_t.append((x * S, (y - hw) * S))
        pts_b.append((x * S, (y + hw) * S))
    vd.polygon(pts_t + pts_b[::-1], fill=WHITE + (255,))

    tracked(d, (CXF, y_sw + 96), "COLA", font("Outfit-Bold", 40),
            WHITE, tracking=28)


def back_panel_wave(W, H, rows, row):
    """
    Back of the can for concept D: brand lockup, a short descriptor, the
    volume, and the nutrition set as a rotated strip -- the arrangement on
    the reference's rear view.  Everything sits inside the cobalt field.
    """
    back = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(back)
    bx = W // 2 - 120          # clear of the rising wave past the seam

    logo = script_elo(900, WHITE)
    tw = 230
    logo = logo.resize((tw, int(logo.height * tw / logo.width)), Image.LANCZOS)
    ly = int(row(rows["body_hi"] + 112))
    back.alpha_composite(logo, (int(bx - tw // 2), ly))
    tracked(bd, (bx, ly + logo.height + 26), "COLA",
            font("Outfit-Bold", 24), WHITE, tracking=14)

    y = ly + logo.height + 118
    for ln in ("CRISP", "REFRESHING", "COLA"):
        tracked(bd, (bx, y), ln, font("InstrumentSans-Regular", 32),
                WHITE, tracking=11)
        y += 46
    y += 26
    bd.rectangle([bx - 46, y, bx + 46, y + 4], fill=RED + (255,))
    y += 64
    tracked(bd, (bx, y), "355 mL   (12 FL OZ)",
            font("InstrumentSans-Regular", 27), WHITE, tracking=4)

    # rotated nutrition strip + barcode, as on the reference
    sw, sh = 430, 270
    strip = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip)
    tiny = font("InstrumentSans-Regular", 17)
    tinyb = font("InstrumentSans-Bold", 17)
    sd.text((0, 0), "NUTRITION PER 355 mL", font=tinyb, fill=WHITE)
    yy = 26
    for k, v in (("Energy", "150 kcal"), ("Fat / Saturates", "0 g / 0 g"),
                 ("Carbohydrate", "39 g"), ("of which sugars", "39 g"),
                 ("Protein", "0 g"), ("Salt", "0.02 g")):
        sd.text((0, yy), k, font=tiny, fill=WHITE_SOFT)
        sd.text((250, yy), v, font=tiny, fill=WHITE)
        yy += 23
    yy += 10
    sd.text((0, yy), "Carbonated water, sugar, colour (caramel E150d),",
            font=tiny, fill=WHITE_SOFT)
    sd.text((0, yy + 21), "phosphoric acid, natural flavourings, caffeine.",
            font=tiny, fill=WHITE_SOFT)
    rng = np.random.default_rng(20261101)
    byy = yy + 54
    sd.rectangle([0, byy, 232, byy + 62], fill=WHITE + (255,))
    x = 8
    while x < 222:
        w_ = int(rng.integers(2, 6))
        if rng.random() < 0.55:
            sd.rectangle([x, byy + 6, x + w_, byy + 50], fill=(14, 20, 40, 255))
        x += w_ + int(rng.integers(2, 5))
    sd.text((116, byy + 56), "0 000000 000000",
            font=font("InstrumentSans-Regular", 11), fill=(30, 38, 62, 255),
            anchor="mm")
    strip = strip.rotate(90, expand=True, resample=Image.BICUBIC)
    # placed well round the barrel from the seam, where cobalt runs deep
    back.alpha_composite(strip, (int(bx - 440), int(row(rows["body_hi"] + 150))))

    return Image.fromarray(np.roll(np.asarray(back), W // 2, axis=1), "RGBA")


def back_panel(W, H, rows, row, concept):
    """
    Minimal back-of-can copy, set straight onto the cobalt -- no white box.
    Drawn centred then rolled by W/2 so it straddles the u = 0 / u = 1 seam,
    i.e. it sits on +Y, directly opposite the brand face.
    """
    back = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(back)
    bx = W // 2
    small = font("InstrumentSans-Regular", 23)
    bold = font("InstrumentSans-Bold", 23)

    y = row(rows["body_hi"] + 150)
    tracked(bd, (bx, y), "NUTRITION PER 355 ml",
            font("InstrumentSans-Bold", 24), WHITE, tracking=7)
    y += 46
    bd.rectangle([bx - 300, y, bx + 300, y + 2], fill=WHITE_SOFT + (120,))
    y += 26
    for k, v in (("Energy", "150 kcal / 627 kJ"), ("Fat / Saturates", "0 g / 0 g"),
                 ("Carbohydrate", "39 g"), ("  of which sugars", "39 g"),
                 ("Protein", "0 g"), ("Salt", "0.02 g")):
        bd.text((bx - 300, y + 14), k, font=small, fill=WHITE_SOFT, anchor="lm")
        bd.text((bx + 300, y + 14), v, font=bold, fill=WHITE, anchor="rm")
        y += 36
    y += 20
    bd.text((bx - 300, y), "INGREDIENTS", font=bold, fill=WHITE)
    y += 32
    for ln in ("Carbonated water, sugar, colour (caramel E150d),",
               "phosphoric acid, natural flavourings including plant",
               "extracts, caffeine."):
        bd.text((bx - 300, y), ln, font=small, fill=WHITE_SOFT)
        y += 28

    # abstract, deliberately non-scannable barcode on a white chip
    y += 26
    rng = np.random.default_rng(20261101)
    bw = bx - 300
    bd.rectangle([bw - 10, y - 10, bw + 300, y + 104], fill=WHITE + (255,))
    x = bw
    while x < bw + 284:
        w_ = int(rng.integers(2, 7))
        if rng.random() < 0.55:
            bd.rectangle([x, y, x + w_, y + 78], fill=(14, 20, 40, 255))
        x += w_ + int(rng.integers(2, 6))
    bd.text((bw + 145, y + 92), "0 000000 000000",
            font=font("InstrumentSans-Regular", 18), fill=(30, 38, 62, 255),
            anchor="mm")

    bd.text((bx + 300, y + 36), "ELO BEVERAGE CO.", font=bold,
            fill=WHITE, anchor="rm")
    bd.text((bx + 300, y + 68), "Best before: see base", font=small,
            fill=WHITE_SOFT, anchor="rm")
    bd.text((bx + 300, y + 98), "Please recycle", font=small,
            fill=WHITE_SOFT, anchor="rm")
    return Image.fromarray(np.roll(np.asarray(back), W // 2, axis=1), "RGBA")


def paint_label(atlas, concept):
    reg = CP.REGIONS["label"]
    A = CP.ATLAS
    x0 = int(round(reg[0] * A)); x1 = int(round(reg[2] * A))
    y0 = int(round((1.0 - reg[3]) * A)); y1 = int(round((1.0 - reg[1]) * A))
    W, H = x1 - x0, y1 - y0

    b = CP.label_bands()
    rows = dict(y0=y0,
                body_hi=b["body"]["row_hi"], body_lo=b["body"]["row_lo"],
                taper_hi=b["taper"]["row_hi"], shoul_lo=b["shoulder"]["row_lo"])

    base = wave_field(W, H, rows) if concept == "D" else label_field(W, H, rows)
    img = Image.fromarray(base.astype(np.uint8), "RGB").convert("RGBA")
    vec = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    CXF = W // 2
    row = lambda r: (r - y0)

    {"A": concept_A, "B": concept_B,
     "C": concept_C, "D": concept_D}[concept](
        img, vec, W, H, rows, CXF, row)

    vec = vec.resize((W, H), Image.LANCZOS)
    img.alpha_composite(vec)
    if concept == "D":
        img.alpha_composite(back_panel_wave(W, H, rows, row))
    else:
        img.alpha_composite(back_panel(W, H, rows, row, concept))
    atlas[y0:y1, x0:x1, :] = np.asarray(img.convert("RGB"))


# ---------------------------------------------------------------------------
# Aluminium parts
# ---------------------------------------------------------------------------

def brushed_disc(size, cx, cy, rmax_px, seed, base, light, dark,
                 ring_period=9.0):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    dx, dy = xx - cx, yy - cy
    r = np.hypot(dx, dy)
    th = np.arctan2(dy, dx)
    t = np.clip(r / max(rmax_px, 1.0), 0, 1.6)
    out = np.zeros((size, size, 3), np.float32)
    for c in range(3):
        out[:, :, c] = np.interp(t, [0.0, 0.45, 0.80, 1.0, 1.6],
                                 [light[c], base[c], base[c], dark[c], dark[c]])
    rings = (np.sin(r / ring_period * 2 * math.pi) * 2.6
             + np.sin(r / (ring_period * 3.1) * 2 * math.pi) * 1.8)
    streak = (np.sin(th * 170.0) * 0.5 + np.sin(th * 61.0) * 0.5) * 2.6
    grain = (seeded_noise(size, size, seed, blur=0.6) - 0.5) * 6.0
    return np.clip(out + (rings + streak * np.clip(t, 0, 1))[:, :, None]
                   + grain[:, :, None], 0, 255)


def paint_lid(atlas, lid_rmax):
    x0, y0, x1, y1 = region_px("lid")
    n = x1 - x0
    cx = cy = n / 2.0
    hs = n / 2.0
    k = hs / lid_rmax
    r_panel = CP.SEGMENTS[-1][2][0]

    arr = brushed_disc(n, cx, cy, hs * (r_panel / lid_rmax), 11,
                       ALU_BASE, ALU_LIGHT, ALU_MID, ring_period=7.5)
    img = Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")
    lay = Image.new("RGBA", (n * SS, n * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)

    def P(x, y):
        return ((cx + x * k) * SS, (cy - y * k) * SS)

    def circle(rcm, col, width):
        a = P(-rcm, rcm); b = P(rcm, -rcm)
        d.ellipse([a[0], a[1], b[0], b[1]], outline=col,
                  width=max(1, int(width * SS)))

    circle(lid_rmax * 0.985, ALU_SHADOW + (200,), 3.0)
    circle(r_panel + 0.03, ALU_DARK + (165,), 4.0)
    circle(r_panel - 0.02, ALU_LIGHT + (130,), 2.0)
    circle(CP.BEAD["r"] + CP.BEAD["w"] * 0.5, ALU_DARK + (115,), 2.5)
    circle(CP.BEAD["r"],                      ALU_LIGHT + (115,), 3.0)
    circle(CP.BEAD["r"] - CP.BEAD["w"] * 0.5, ALU_DARK + (115,), 2.5)

    ap = CP.APERTURE
    spec = dict(c1=ap["c1"], r1=ap["r1"], c2=ap["c2"], r2=ap["r2"])
    org = (0.0, 0.5 * (ap["c1"][1] + ap["c2"][1]))
    pts_out, pts_mid, pts_in = [], [], []
    N = 240
    for i in range(N + 1):
        a = 2 * math.pi * i / N
        dirv = (math.cos(a), math.sin(a))
        t = CP.round_cone_ray(org, dirv, spec, 0.0, 3.0, 40)
        for lst, off in ((pts_out, ap["score_w"] * 1.5), (pts_mid, 0.0),
                         (pts_in, -ap["score_w"] * 1.5)):
            tt = max(0.02, t + off)
            lst.append(P(org[0] + dirv[0] * tt, org[1] + dirv[1] * tt))
    d.polygon(pts_out, fill=(184, 189, 196, 255))
    d.line(pts_out + [pts_out[0]], fill=ALU_LIGHT + (185,), width=max(1, int(2 * SS)))
    d.line(pts_mid + [pts_mid[0]], fill=(96, 102, 111, 255), width=max(1, int(2.6 * SS)))
    d.line(pts_in + [pts_in[0]], fill=(150, 156, 165, 195), width=max(1, int(1.6 * SS)))

    circle(CP.RIVET["r_ring"], ALU_DARK + (215,), 3.0)
    a = P(-CP.RIVET["r_head"], CP.RIVET["r_head"])
    b = P(CP.RIVET["r_head"], -CP.RIVET["r_head"])
    d.ellipse([a[0], a[1], b[0], b[1]], fill=(210, 214, 220, 255),
              outline=ALU_MID + (255,), width=max(1, int(1.6 * SS)))

    lay = lay.resize((n, n), Image.LANCZOS)
    img.alpha_composite(lay)
    atlas[y0:y1, x0:x1, :] = np.asarray(img.convert("RGB"))


def paint_bottom(atlas, bot_rmax):
    x0, y0, x1, y1 = region_px("bottom")
    n = x1 - x0
    cx = cy = n / 2.0
    k = (n / 2.0) / bot_rmax
    arr = brushed_disc(n, cx, cy, n / 2.0, 23, ALU_MID, ALU_DARK,
                       ALU_BASE, ring_period=6.0)
    img = Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")
    lay = Image.new("RGBA", (n * SS, n * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for rcm, col, w in ((1.95, ALU_SHADOW + (115,), 3.0),
                        (2.22, ALU_DARK + (165,), 3.0),
                        (2.45, ALU_LIGHT + (205,), 7.0),
                        (2.58, ALU_DARK + (145,), 3.0),
                        (bot_rmax * 0.99, ALU_SHADOW + (145,), 3.0)):
        d.ellipse([(cx - rcm * k) * SS, (cy - rcm * k) * SS,
                   (cx + rcm * k) * SS, (cy + rcm * k) * SS],
                  outline=col, width=max(1, int(w * SS)))
    lay = lay.resize((n, n), Image.LANCZOS)
    img.alpha_composite(lay)

    # viewed from underneath the radial projection reads mirrored, so the
    # base code is pre-mirrored here and is therefore legible on the part
    code = Image.new("RGBA", (int(2.6 * k), 70), (0, 0, 0, 0))
    cd = ImageDraw.Draw(code)
    tracked(cd, (code.width / 2, 20), "ELO COLA  ·  355 ml",
            font("InstrumentSans-Bold", 21), (104, 110, 119), tracking=3)
    tracked(cd, (code.width / 2, 50), "L2611  14:22  BB 11/2027",
            font("InstrumentSans-Regular", 18), (116, 122, 131), tracking=2)
    img.alpha_composite(code.transpose(Image.FLIP_LEFT_RIGHT),
                        (int(cx - code.width / 2), int(cy + 0.55 * k)))
    atlas[y0:y1, x0:x1, :] = np.asarray(img.convert("RGB"))


def paint_rim(atlas):
    x0, y0, x1, y1 = region_px("rim")
    w, h = x1 - x0, y1 - y0
    g = vgrad(w, h, [(0.00, ALU_MID), (0.22, ALU_LIGHT), (0.45, ALU_BASE),
                     (0.72, ALU_DARK), (1.00, ALU_SHADOW)])
    g = np.clip(g + (np.sin(np.arange(w) * 0.9)[None, :, None] * 1.8), 0, 255)
    g = np.clip(g + (seeded_noise(h, w, 31, blur=0.4)[:, :, None] - 0.5) * 7.0, 0, 255)
    atlas[y0:y1, x0:x1, :] = g.astype(np.uint8)


def paint_tab(atlas):
    for name, base, light, dark, seed in (
            ("tab_top", ALU_BASE, ALU_LIGHT, ALU_MID, 41),
            ("tab_bot", ALU_MID, ALU_BASE, ALU_DARK, 43)):
        x0, y0, x1, y1 = region_px(name)
        w, h = x1 - x0, y1 - y0
        g = vgrad(w, h, [(0.00, dark), (0.30, light), (0.62, base), (1.00, dark)])
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        g = np.clip(g + (np.sin(yy * 1.7 + np.sin(xx * 0.07) * 2.0) * 2.2)[:, :, None], 0, 255)
        g = np.clip(g + (seeded_noise(h, w, seed, blur=0.5)[:, :, None] - 0.5) * 8.0, 0, 255)
        g = np.clip(g + (np.exp(-((xx / w - 0.45) ** 2) / 0.035) * 12.0)[:, :, None], 0, 255)
        atlas[y0:y1, x0:x1, :] = g.astype(np.uint8)

    x0, y0, x1, y1 = region_px("tab_wall")
    w, h = x1 - x0, y1 - y0
    g = vgrad(w, h, [(0.0, ALU_LIGHT), (0.5, ALU_MID), (1.0, ALU_SHADOW)])
    g = np.clip(g + (np.sin(np.arange(w) * 2.3)[None, :, None] * 2.4), 0, 255)
    atlas[y0:y1, x0:x1, :] = g.astype(np.uint8)


# ---------------------------------------------------------------------------

def build(out_path, concept="D"):
    A = CP.ATLAS
    rings, _pb, _pt = CP.build_rings()
    spans = CP.zone_spans(rings)
    lid_rmax = rings[spans["lid"][0]]["r"]
    bot_rmax = rings[spans["bottom"][1]]["r"]

    atlas = np.zeros((A, A, 3), dtype=np.uint8)
    atlas[:, :, :] = np.array(ALU_BASE, dtype=np.uint8)
    atlas[int(A * 0.60):, :, :] = np.array(ALU_MID, dtype=np.uint8)

    paint_label(atlas, concept)
    paint_lid(atlas, lid_rmax)
    paint_bottom(atlas, bot_rmax)
    paint_rim(atlas)
    paint_tab(atlas)

    img = Image.fromarray(atlas, "RGB")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    print(f"[texture] concept {concept}: wrote {out_path}  "
          f"{img.size[0]}x{img.size[1]} ({os.path.getsize(out_path)/1024:.0f} KiB)")
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="assets/elo_cola_texture.png")
    ap.add_argument("-c", "--concept", default="D",
                    choices=["A", "B", "C", "D"])
    a = ap.parse_args()
    build(a.out, a.concept)
