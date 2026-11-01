#!/usr/bin/env python3
"""
Elo Cola -- studio product rendering.

Opens assets/elo_cola.blend, adds a seamless backdrop sweep (a cyclorama and
a reflective floor) *in memory only*, and renders.  The backdrop is never
saved back, so the delivered elo_cola.blend keeps exactly one mesh object.

    python3 scripts/render_product.py                 # all outputs
    python3 scripts/render_product.py --only product  # just the 512x512
    python3 scripts/render_product.py --samples 48    # fast preview

Outputs
    renders/elo_cola_product_512.png   512 x 512   (mandatory deliverable)
    renders/hero.png                   1200 x 1200 portfolio render
    renders/turntable_front.png        front elevation, proves -Y label
    renders/orientation_check.png      front / right / back / left contact sheet
    renders/lid_detail.png             top-down detail of lid, score and tab
"""

import argparse
import math
import os
import sys

import bpy
import addon_utils
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLEND = os.path.join(ROOT, "assets", "elo_cola.blend")
RENDERS = os.path.join(ROOT, "renders")


def open_project():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    addon_utils.enable("cycles", default_set=True, persistent=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    return sc


def can_object():
    for o in bpy.data.objects:
        if o.type == "MESH":
            return o
    raise SystemExit("no mesh object in the project")


# ---------------------------------------------------------------------------
# backdrop (render-time only -- never saved)
# ---------------------------------------------------------------------------

def add_backdrop():
    """Curved cyclorama + subtly reflective floor, built from one grid each."""
    import bmesh

    # ---- floor -------------------------------------------------------
    me = bpy.data.meshes.new("StudioFloor")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=420.0)
    bm.to_mesh(me); bm.free()
    floor = bpy.data.objects.new("StudioFloor", me)
    bpy.context.collection.objects.link(floor)

    mat = bpy.data.materials.new("FloorMat")
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (600, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (300, 0)
    bsdf.inputs["Base Color"].default_value = (0.014, 0.028, 0.075, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.30
    bsdf.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.6
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    me.materials.append(mat)

    # ---- cyclorama: a vertical plane far behind, softly lit -----------
    me2 = bpy.data.meshes.new("Cyc")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=330.0)
    bm.to_mesh(me2); bm.free()
    cyc = bpy.data.objects.new("Cyc", me2)
    bpy.context.collection.objects.link(cyc)
    cyc.location = (0.0, 150.0, 120.0)
    cyc.rotation_euler = (math.radians(90.0), 0.0, 0.0)

    mat2 = bpy.data.materials.new("CycMat")
    mat2.use_nodes = True
    nt = mat2.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (600, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (300, 0)
    bsdf.inputs["Roughness"].default_value = 0.85
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (0, 0)
    ramp.color_ramp.elements[0].position = 0.12
    ramp.color_ramp.elements[0].color = (0.003, 0.009, 0.035, 1.0)
    ramp.color_ramp.elements[1].position = 0.80
    ramp.color_ramp.elements[1].color = (0.035, 0.12, 0.36, 1.0)
    grad = nt.nodes.new("ShaderNodeTexGradient"); grad.location = (-220, 0)
    grad.gradient_type = "QUADRATIC_SPHERE"
    mapn = nt.nodes.new("ShaderNodeMapping"); mapn.location = (-430, 0)
    mapn.inputs["Location"].default_value = (-18.0, -17.3, 0.0)
    mapn.inputs["Scale"].default_value = (36.0, 36.0, 1.0)
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-640, 0)
    nt.links.new(tc.outputs["UV"], mapn.inputs["Vector"])
    nt.links.new(mapn.outputs["Vector"], grad.inputs["Vector"])
    nt.links.new(grad.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 0.65
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    me2.materials.append(mat2)

    return [floor, cyc]


# ---------------------------------------------------------------------------
# cameras
# ---------------------------------------------------------------------------

def aim(cam, loc, target, lens=None, fstop=None):
    cam.location = loc
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if lens:
        cam.data.lens = lens
    cam.data.dof.focus_distance = d.length
    if fstop:
        cam.data.dof.aperture_fstop = fstop
    return cam


def render_to(sc, path, w, h, samples):
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "8"
    sc.cycles.samples = samples
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"[render] {path}  {w}x{h}  {samples} spp")


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=0,
                    help="override sample count for every output")
    ap.add_argument("--only", default="all",
                    choices=["all", "product", "hero", "ortho", "lid"])
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ([] if bpy.app.binary_path else sys.argv[1:])
    args = ap.parse_args(argv)

    os.makedirs(RENDERS, exist_ok=True)
    sc = open_project()
    can = can_object()
    add_backdrop()
    cam = sc.camera

    S = lambda n: args.samples if args.samples else n
    want = args.only

    # ---- 1. the mandatory 512 x 512 product shot ----------------------
    if want in ("all", "product"):
        aim(cam, (-5.63, -53.53, 21.59), (0.0, 0.0, 6.15), lens=120.0, fstop=9.0)
        render_to(sc, os.path.join(RENDERS, "elo_cola_product_512.png"),
                  512, 512, S(480))

    # ---- 2. large portfolio hero --------------------------------------
    if want in ("all", "hero"):
        aim(cam, (-8.40, -53.10, 23.00), (0.0, 0.0, 6.15), lens=116.0, fstop=7.0)
        render_to(sc, os.path.join(RENDERS, "hero.png"), 1200, 1200, S(340))

    # ---- 3. orientation proof: four elevations ------------------------
    if want in ("all", "ortho"):
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = 14.2
        cam.data.dof.use_dof = False
        views = [("front_-Y", (0.0, -60.0, 6.90)),
                 ("right_+X", (60.0, 0.0, 6.90)),
                 ("back_+Y", (0.0, 60.0, 6.90)),
                 ("left_-X", (-60.0, 0.0, 6.90))]
        tiles = []
        for name, loc in views:
            aim(cam, loc, (0.0, 0.0, 6.90))
            p = os.path.join(RENDERS, f"_ortho_{name}.png")
            render_to(sc, p, 420, 620, S(160))
            tiles.append((name, p))

        aim(cam, (0.0, -60.0, 6.90), (0.0, 0.0, 6.90))
        render_to(sc, os.path.join(RENDERS, "turntable_front.png"),
                  600, 900, S(220))

        _contact_sheet(tiles, os.path.join(RENDERS, "orientation_check.png"))
        for _n, p in tiles:
            os.remove(p)

        cam.data.type = "PERSP"
        cam.data.dof.use_dof = True

    # ---- 4. lid / tab detail ------------------------------------------
    if want in ("all", "lid"):
        aim(cam, (-8.5, -15.0, 25.8), (0.0, -0.4, 11.9), lens=120.0, fstop=6.0)
        render_to(sc, os.path.join(RENDERS, "lid_detail.png"), 900, 900, S(320))


def _contact_sheet(tiles, out_path):
    from PIL import Image, ImageDraw, ImageFont
    ims = [Image.open(p).convert("RGB") for _n, p in tiles]
    w, h = ims[0].size
    pad, label_h = 14, 42
    sheet = Image.new("RGB", (len(ims) * w + (len(ims) + 1) * pad,
                              h + label_h + 2 * pad), (16, 18, 24))
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", 24)
    except Exception:
        f = ImageFont.load_default()
    for i, (im, (name, _p)) in enumerate(zip(ims, tiles)):
        x = pad + i * (w + pad)
        sheet.paste(im, (x, pad))
        d.text((x + w // 2, pad + h + label_h // 2), name.replace("_", "  "),
               font=f, fill=(226, 232, 242), anchor="mm")
    sheet.save(out_path)
    print(f"[render] {out_path}  {sheet.size[0]}x{sheet.size[1]}")


if __name__ == "__main__":
    main()
