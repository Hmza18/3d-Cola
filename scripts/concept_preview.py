#!/usr/bin/env python3
"""
Render a quick comparison of the three Elo Cola label concepts on the real
can geometry.  Writes renders/concepts.png (a contact sheet) plus one
preview per concept.  Nothing here touches the delivered assets.

    python3 scripts/concept_preview.py [--samples 96]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy
from PIL import Image, ImageDraw, ImageFont

import generate as G
import generate_texture as T
import render_product as RP

ROOT = G.ROOT
RENDERS = os.path.join(ROOT, "renders")
SCRATCH = os.environ.get("ELO_SCRATCH", os.path.join(ROOT, ".concept_tmp"))

TITLES = {
    "A": "A  VERTICAL",
    "B": "B  MONOGRAM",
    "C": "C  LUXURY",
    "D": "D  WAVE   (final)",
}


def render_concept(concept, samples, out_png):
    tex = os.path.join(SCRATCH, f"tex_{concept}.png")
    if not os.path.exists(tex):
        T.build(tex, concept)

    G.reset_scene()
    ob, _stats = G.make_mesh()
    G.make_material(ob, texture=tex)
    G.build_render_setup()
    RP.add_backdrop()

    sc = bpy.context.scene
    sc.cycles.samples = samples
    sc.render.resolution_x = 560
    sc.render.resolution_y = 760
    sc.render.filepath = out_png
    bpy.ops.render.render(write_still=True)
    print(f"[concept] {concept} -> {out_png}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=96)
    args = ap.parse_args()

    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(RENDERS, exist_ok=True)

    tiles = []
    for c in ("A", "B", "C", "D"):
        p = os.path.join(SCRATCH, f"preview_{c}.png")
        render_concept(c, args.samples, p)
        tiles.append((c, p))

    ims = [Image.open(p).convert("RGB") for _c, p in tiles]
    w, h = ims[0].size
    pad, lab = 16, 52
    sheet = Image.new("RGB", (len(ims) * w + (len(ims) + 1) * pad,
                              h + lab + 2 * pad), (22, 24, 28))
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype(os.path.join(G.ROOT, "scripts", "fonts",
                                            "InstrumentSans-Bold.ttf"), 24)
    except Exception:
        f = ImageFont.load_default()
    for i, (im, (c, _p)) in enumerate(zip(ims, tiles)):
        x = pad + i * (w + pad)
        sheet.paste(im, (x, pad))
        d.text((x + w // 2, pad + h + lab // 2), TITLES[c], font=f,
               fill=(232, 236, 242), anchor="mm")
    out = os.path.join(RENDERS, "concepts.png")
    sheet.save(out)
    print(f"[concept] contact sheet -> {out}  {sheet.size[0]}x{sheet.size[1]}")


if __name__ == "__main__":
    main()
