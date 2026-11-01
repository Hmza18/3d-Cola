#!/usr/bin/env python3
"""
Elo Cola -- procedural generation of the complete can asset.

Run with the Blender Python module (bpy) available:

    python3 scripts/generate.py

Outputs
    assets/elo_cola.blend   native project (texture packed, render set-up)
    assets/elo_cola.obj     geometry, exported with global_scale = 0.01
    assets/elo_cola.mtl     material, references the single PNG
    assets/build_manifest.json

Design rules enforced here
    * ONE mesh object  -- the barrel-of-revolution and the pull tab are two
      disconnected but individually watertight shells inside a single mesh.
    * ONE image texture -- a single 2048x2048 PNG atlas, used as Base Color.
    * Watertight       -- every edge has exactly two faces, every shell is a
      closed orientable surface with outward normals.
    * -Y front         -- u = 0.5 of the label maps to theta = 270 deg.
    * +Z up            -- the can stands on z = 0.
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy
import bmesh
import addon_utils
from mathutils import Vector

import can_profile as CP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")

TEXTURE = os.path.join(ASSETS, "elo_cola_texture.png")
BLEND = os.path.join(ASSETS, "elo_cola.blend")
OBJ = os.path.join(ASSETS, "elo_cola.obj")
MANIFEST = os.path.join(ASSETS, "build_manifest.json")

OBJ_SCALE = 0.01                 # <-- the mandated OBJ export scale factor
MESH_NAME = "EloColaCan"
OBJ_NAME = "EloCola"
MAT_NAME = "EloColaSurface"
SHARP_ANGLE = math.radians(40.0)

# Chilled-can condensation in the Blender material only.  Built from
# procedural nodes, never a second image, so the exported asset still
# satisfies the one-texture requirement.
#
# Off by default: a realistic bead is 1-2 mm, which at the 512 x 512
# deliverable is well under a pixel, so it reads as shader noise rather
# than water.  Switch it on for close-up renders, where it does read.
CONDENSATION = False


# ===========================================================================
#  Geometry
# ===========================================================================

def smoothstep(e0, e1, x):
    if e1 == e0:
        return 0.0
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def lid_relief(x, y, z):
    """
    Stamped relief of the lid panel: circular stiffening bead, scored
    drinking aperture (a closed groove -- never an actual hole) and the
    central rivet that the pull tab is mounted on.
    """
    r = math.hypot(x, y)
    dz = 0.0

    # --- circular stiffening bead -------------------------------------
    b = CP.BEAD
    d = abs(r - b["r"])
    if d < b["w"]:
        dz -= b["d"] * math.cos(d / b["w"] * math.pi * 0.5)

    # --- scored aperture ----------------------------------------------
    ap = CP.APERTURE
    sd = CP.round_cone_sdf((x, y), ap["c1"], ap["r1"], ap["c2"], ap["r2"], 72)
    if sd < 0.0:                                   # inside: gently dished
        dz -= ap["dish"] * smoothstep(0.0, -0.25, sd)
    if abs(sd) < ap["score_w"]:                    # the score line itself
        dz -= ap["score_d"] * math.cos(abs(sd) / ap["score_w"] * math.pi * 0.5)

    # --- rivet ----------------------------------------------------------
    rv = CP.RIVET
    if r < rv["r_ring"] + rv["groove"]:
        dz += rv["h"] * smoothstep(rv["r_head"] + 0.05, rv["r_head"] * 0.55, r)
        g = abs(r - rv["r_ring"])
        if g < rv["groove"]:
            dz -= 0.012 * math.cos(g / rv["groove"] * math.pi * 0.5)

    return dz


def build_can_geometry():
    """
    Returns (verts, faces, uvs) where
        verts : list of (x, y, z)
        faces : list of vertex-index tuples
        uvs   : list of per-face lists of (u, v), parallel to `faces`
    """
    rings, pole_b, pole_t = CP.build_rings()
    spans = CP.zone_spans(rings)
    N = CP.NSEG
    R = len(rings)

    lid_rmax = rings[spans["lid"][0]]["r"]
    bot_rmax = rings[spans["bottom"][1]]["r"]

    thetas = [CP.THETA0 + 2.0 * math.pi * j / N for j in range(N)]
    cos_t = [math.cos(t) for t in thetas]
    sin_t = [math.sin(t) for t in thetas]

    # ---------------- vertices -----------------------------------------
    verts = [(0.0, 0.0, pole_b[1])]
    for ring in rings:
        r, z = ring["r"], ring["z"]
        for j in range(N):
            x, y = r * cos_t[j], r * sin_t[j]
            if ring["zone"] == "lid":
                z2 = z + lid_relief(x, y, z)
            else:
                z2 = z
            verts.append((x, y, z2))
    pole_t_z = pole_t[1] + lid_relief(0.0, 0.0, pole_t[1])
    verts.append((0.0, 0.0, pole_t_z))

    IDX_POLE_B = 0
    IDX_POLE_T = 1 + R * N

    def vid(i, j):
        return 1 + i * N + (j % N)

    # ---------------- UV helpers ---------------------------------------
    def zone_t(zone, i):
        a, b = spans[zone]
        s0, s1 = rings[a]["s"], rings[b]["s"]
        return (rings[i]["s"] - s0) / (s1 - s0)

    def uv_band(region, zone, i, j):
        u0, v0, u1, v1 = CP.REGIONS[region]
        return (u0 + (j / N) * (u1 - u0),
                v0 + zone_t(zone, i) * (v1 - v0))

    def uv_radial(region, r, j, rmax):
        u0, v0, u1, v1 = CP.REGIONS[region]
        cu, cv = 0.5 * (u0 + u1), 0.5 * (v0 + v1)
        hs = 0.5 * min(u1 - u0, v1 - v0)
        f = r / rmax
        return (cu + f * hs * cos_t[j % N], cv + f * hs * sin_t[j % N])

    def uv_of(zone, i, j):
        if zone == "label":
            return uv_band("label", "label", i, j)
        if zone == "rim":
            return uv_band("rim", "rim", i, j)
        if zone == "lid":
            return uv_radial("lid", rings[i]["r"], j, lid_rmax)
        if zone == "bottom":
            return uv_radial("bottom", rings[i]["r"], j, bot_rmax)
        raise KeyError(zone)

    def uv_centre(region):
        u0, v0, u1, v1 = CP.REGIONS[region]
        return (0.5 * (u0 + u1), 0.5 * (v0 + v1))

    faces, uvs = [], []

    # ---------------- bottom pole fan ------------------------------------
    for j in range(N):
        faces.append((IDX_POLE_B, vid(0, j + 1), vid(0, j)))
        uvs.append([uv_centre("bottom"),
                    uv_of("bottom", 0, j + 1),
                    uv_of("bottom", 0, j)])

    # ---------------- quad rows -------------------------------------------
    for i in range(R - 1):
        zone = rings[i]["zone"]
        for j in range(N):
            faces.append((vid(i, j), vid(i, j + 1),
                          vid(i + 1, j + 1), vid(i + 1, j)))
            uvs.append([uv_of(zone, i, j), uv_of(zone, i, j + 1),
                        uv_of(zone, i + 1, j + 1), uv_of(zone, i + 1, j)])

    # ---------------- top pole fan ----------------------------------------
    for j in range(N):
        faces.append((vid(R - 1, j), vid(R - 1, j + 1), IDX_POLE_T))
        uvs.append([uv_of("lid", R - 1, j),
                    uv_of("lid", R - 1, j + 1),
                    uv_centre("lid")])

    return verts, faces, uvs, dict(rings=R, lid_rmax=lid_rmax,
                                   bot_rmax=bot_rmax, nseg=N)


def build_tab_geometry(v_offset):
    """
    The pull tab: a closed, watertight genus-1 shell (a ring with a finger
    opening).  Both the outline and the opening are tapered capsules, which
    are convex, so both can be traced with one shared angular parameter --
    that is what guarantees a well-formed quad strip between them.
    """
    T = CP.TAB
    N = CP.TAB_NSEG
    cx, cy = T["center"]
    ch = T["chamfer"]
    z_top, z_bot = T["z_top"], T["z_bot"]

    outer_r, inner_r, dirs = [], [], []
    for j in range(N):
        a = 2.0 * math.pi * j / N
        d = (math.cos(a), math.sin(a))
        dirs.append(d)
        outer_r.append(CP.round_cone_ray((cx, cy), d, T["outer"], 0.0, 4.0))
        inner_r.append(CP.round_cone_ray((cx, cy), d, T["inner"], 0.0, 4.0))

    # four rings per loop: chamfer-top, wall-top, wall-bottom, chamfer-bottom
    loops = []
    for radii, sign in ((outer_r, -1.0), (inner_r, +1.0)):
        rings4 = []
        for rr, zz in ((ch, z_top), (0.0, z_top - ch),
                       (0.0, z_bot + ch), (ch, z_bot)):
            ring = []
            for j in range(N):
                rad = radii[j] + sign * rr
                ring.append((cx + dirs[j][0] * rad,
                             cy + dirs[j][1] * rad, zz))
            rings4.append(ring)
        loops.append(rings4)
    outer_rings, inner_rings = loops

    verts = []
    index = {}
    for which, rings4 in (("o", outer_rings), ("i", inner_rings)):
        for k, ring in enumerate(rings4):
            for j, p in enumerate(ring):
                index[(which, k, j)] = v_offset + len(verts)
                verts.append(p)

    xs = [p[0] for p in verts]
    ys = [p[1] for p in verts]
    bb = (min(xs), min(ys), max(xs), max(ys))

    def uv_planar(region, p):
        u0, v0, u1, v1 = CP.REGIONS[region]
        fx = (p[0] - bb[0]) / (bb[2] - bb[0])
        fy = (p[1] - bb[1]) / (bb[3] - bb[1])
        return (u0 + fx * (u1 - u0), v0 + fy * (v1 - v0))

    def uv_wall(j, k):
        u0, v0, u1, v1 = CP.REGIONS["tab_wall"]
        return (u0 + (j % N) / N * (u1 - u0), v0 + k * (v1 - v0))

    faces, uvs = [], []

    def quad(a, b, c, d, uv):
        faces.append((a, b, c, d))
        uvs.append(uv)

    for j in range(N):
        j2 = (j + 1) % N
        O = lambda k, jj: index[("o", k, jj)]
        I = lambda k, jj: index[("i", k, jj)]

        # ---- top annulus: outer ring 0 -> inner ring 0 ----------------
        quad(O(0, j), O(0, j2), I(0, j2), I(0, j),
             [uv_planar("tab_top", verts[O(0, j) - v_offset]),
              uv_planar("tab_top", verts[O(0, j2) - v_offset]),
              uv_planar("tab_top", verts[I(0, j2) - v_offset]),
              uv_planar("tab_top", verts[I(0, j) - v_offset])])

        # ---- outer wall (3 bands, downward) --------------------------
        for k in range(3):
            quad(O(k, j), O(k, j2), O(k + 1, j2), O(k + 1, j),
                 [uv_wall(j, k / 3.0), uv_wall(j + 1, k / 3.0),
                  uv_wall(j + 1, (k + 1) / 3.0), uv_wall(j, (k + 1) / 3.0)])

        # ---- bottom annulus (reverse winding) ------------------------
        quad(O(3, j2), O(3, j), I(3, j), I(3, j2),
             [uv_planar("tab_bot", verts[O(3, j2) - v_offset]),
              uv_planar("tab_bot", verts[O(3, j) - v_offset]),
              uv_planar("tab_bot", verts[I(3, j) - v_offset]),
              uv_planar("tab_bot", verts[I(3, j2) - v_offset])])

        # ---- inner wall (3 bands, reverse winding) -------------------
        for k in range(3):
            quad(I(k, j2), I(k, j), I(k + 1, j), I(k + 1, j2),
                 [uv_wall(j + 1, k / 3.0), uv_wall(j, k / 3.0),
                  uv_wall(j, (k + 1) / 3.0), uv_wall(j + 1, (k + 1) / 3.0)])

    return verts, faces, uvs


# ===========================================================================
#  Blender scene assembly
# ===========================================================================

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True, persistent=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 0.01      # 1 Blender unit displays as 1 cm
    sc.unit_settings.length_unit = "CENTIMETERS"


def make_mesh():
    can_v, can_f, can_uv, stats = build_can_geometry()
    tab_v, tab_f, tab_uv = build_tab_geometry(len(can_v))

    verts = can_v + tab_v
    faces = can_f + tab_f
    uvs = can_uv + tab_uv

    me = bpy.data.meshes.new(MESH_NAME)
    me.from_pydata(verts, [], faces)
    me.update()

    uv_layer = me.uv_layers.new(name="UVMap")
    li = 0
    for fi, poly in enumerate(me.polygons):
        for k in range(poly.loop_total):
            uv_layer.data[poly.loop_start + k].uv = uvs[fi][k]
        li += poly.loop_total

    ob = bpy.data.objects.new(OBJ_NAME, me)
    bpy.context.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)

    # ---- clean up: recalc outward normals, mark sharp edges ----------
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for e in bm.edges:
        e.smooth = True
        if len(e.link_faces) == 2:
            a = e.link_faces[0].normal
            b = e.link_faces[1].normal
            if a.length > 0 and b.length > 0:
                ang = a.angle(b, 0.0)
                if ang > SHARP_ANGLE:
                    e.smooth = False
    bm.to_mesh(me)
    bm.free()

    for p in me.polygons:
        p.use_smooth = True
    me.update()

    stats["verts"] = len(verts)
    stats["faces"] = len(faces)
    stats["tab_faces"] = len(tab_f)
    return ob, stats


def make_material(ob, texture=None):
    """
    One material, one image.  The PNG drives Base Color DIRECTLY so the OBJ
    exporter can emit `map_Kd`.  Metallic / roughness / coat are derived
    procedurally from the UV coordinate itself (no second image is used):
    everything below v = 0.37 in the atlas is bare aluminium, everything
    above it is printed, lacquered ink.
    """
    mat = bpy.data.materials.new(MAT_NAME)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (900, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (560, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    img = bpy.data.images.load(texture or TEXTURE, check_existing=True)
    img.name = "elo_cola_texture"
    img.colorspace_settings.name = "sRGB"

    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Cubic"
    tex.location = (-240, 240)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])

    # ---- printed / aluminium mask straight from the atlas layout -----
    coord = nt.nodes.new("ShaderNodeTexCoord"); coord.location = (-760, -140)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); sep.location = (-560, -140)
    nt.links.new(coord.outputs["UV"], sep.inputs["Vector"])

    mask = nt.nodes.new("ShaderNodeMath"); mask.location = (-380, -140)
    mask.operation = "GREATER_THAN"
    mask.inputs[1].default_value = 0.37
    nt.links.new(sep.outputs["Y"], mask.inputs[0])

    def mad(x, mul, add, loc):
        n = nt.nodes.new("ShaderNodeMath"); n.location = loc
        n.operation = "MULTIPLY_ADD"
        n.inputs[1].default_value = mul
        n.inputs[2].default_value = add
        nt.links.new(x, n.inputs[0])
        return n

    # Bare aluminium is a true metal with a brushed, satin finish; printed
    # ink over aluminium keeps a little metallic undertone but is far more
    # diffuse.  Neither is a mirror -- the old settings read as wet plastic.
    metallic = mad(mask.outputs[0], -0.78, 1.0, (-40, -40))     # 1.00 -> 0.22
    nt.links.new(metallic.outputs[0], bsdf.inputs["Metallic"])

    rough_base = mad(mask.outputs[0], 0.10, 0.22, (-40, -220))  # brushed metal -> satin ink

    # Two scales of imperfection: broad unevenness from the rolling and
    # printing process, and fine tooth in the lacquer.
    noise = nt.nodes.new("ShaderNodeTexNoise"); noise.location = (-380, -420)
    noise.inputs["Scale"].default_value = 11.0
    noise.inputs["Detail"].default_value = 4.0
    noise.inputs["Roughness"].default_value = 0.55

    fine = nt.nodes.new("ShaderNodeTexNoise"); fine.location = (-380, -560)
    fine.inputs["Scale"].default_value = 260.0
    fine.inputs["Detail"].default_value = 2.0

    nvar = mad(noise.outputs["Fac"], 0.024, -0.012, (-40, -420))
    nfine = mad(fine.outputs["Fac"], 0.016, -0.008, (-40, -560))
    nsum = nt.nodes.new("ShaderNodeMath"); nsum.location = (80, -490)
    nsum.operation = "ADD"
    nt.links.new(nvar.outputs[0], nsum.inputs[0])
    nt.links.new(nfine.outputs[0], nsum.inputs[1])
    nvar = nsum
    rough = nt.nodes.new("ShaderNodeMath"); rough.location = (200, -240)
    rough.operation = "ADD"
    rough.use_clamp = True
    nt.links.new(rough_base.outputs[0], rough.inputs[0])
    nt.links.new(nvar.outputs[0], rough.inputs[1])
    nt.links.new(rough.outputs[0], bsdf.inputs["Roughness"])

    if "Coat Weight" in bsdf.inputs:
        # a thin overprint varnish, not a wet gloss
        coat = mad(mask.outputs[0], 0.10, 0.015, (200, -60))
        nt.links.new(coat.outputs[0], bsdf.inputs["Coat Weight"])
        bsdf.inputs["Coat Roughness"].default_value = 0.26

    # a whisper of micro-texture so the aluminium is not glassy
    # micro-texture plus a trace of large-scale waviness, so highlights
    # travel over the barrel the way they do on real rolled sheet
    bump_n = nt.nodes.new("ShaderNodeTexNoise"); bump_n.location = (-380, -700)
    bump_n.inputs["Scale"].default_value = 760.0
    bump_n.inputs["Detail"].default_value = 2.0
    wav = nt.nodes.new("ShaderNodeTexNoise"); wav.location = (-380, -840)
    wav.inputs["Scale"].default_value = 5.5
    wav.inputs["Detail"].default_value = 2.0
    mixb = nt.nodes.new("ShaderNodeMath"); mixb.location = (-160, -770)
    mixb.operation = "MULTIPLY_ADD"
    mixb.inputs[1].default_value = 0.08
    mixb.inputs[2].default_value = 0.0
    nt.links.new(wav.outputs["Fac"], mixb.inputs[0])
    addb = nt.nodes.new("ShaderNodeMath"); addb.location = (20, -740)
    addb.operation = "ADD"
    nt.links.new(bump_n.outputs["Fac"], addb.inputs[0])
    nt.links.new(mixb.outputs[0], addb.inputs[1])
    bump = nt.nodes.new("ShaderNodeBump"); bump.location = (200, -700)
    bump.inputs["Strength"].default_value = 0.025
    bump.inputs["Distance"].default_value = 0.0015
    nt.links.new(addb.outputs[0], bump.inputs["Height"])

    # ---- condensation -------------------------------------------------
    # Chilled-can beading, built from two Voronoi cells: one supplies the
    # droplet profile, the other a per-cell random value so only some cells
    # actually carry a bead.  Purely procedural -- it adds no second image,
    # so the exported OBJ/MTL remain a one-PNG asset.
    if CONDENSATION:
        vor = nt.nodes.new("ShaderNodeTexVoronoi"); vor.location = (-760, -980)
        vor.voronoi_dimensions = "3D"
        vor.feature = "F1"
        vor.inputs["Scale"].default_value = 130.0
        if "Randomness" in vor.inputs:
            vor.inputs["Randomness"].default_value = 1.0

        prof = nt.nodes.new("ShaderNodeValToRGB"); prof.location = (-560, -980)
        prof.color_ramp.interpolation = "EASE"
        prof.color_ramp.elements[0].position = 0.02
        prof.color_ramp.elements[0].color = (1, 1, 1, 1)
        prof.color_ramp.elements[1].position = 0.30
        prof.color_ramp.elements[1].color = (0, 0, 0, 1)
        nt.links.new(vor.outputs["Distance"], prof.inputs["Fac"])

        pick = nt.nodes.new("ShaderNodeSeparateXYZ"); pick.location = (-560, -1160)
        nt.links.new(vor.outputs["Color"], pick.inputs["Vector"])
        keep = nt.nodes.new("ShaderNodeMath"); keep.location = (-380, -1160)
        keep.operation = "GREATER_THAN"
        keep.inputs[1].default_value = 0.52
        nt.links.new(pick.outputs["X"], keep.inputs[0])

        drops = nt.nodes.new("ShaderNodeMath"); drops.location = (-200, -1060)
        drops.operation = "MULTIPLY"
        nt.links.new(prof.outputs["Color"], drops.inputs[0])
        nt.links.new(keep.outputs[0], drops.inputs[1])

        # beads are smooth water: drop the roughness where they sit
        wet = nt.nodes.new("ShaderNodeMix"); wet.location = (380, -240)
        wet.data_type = "FLOAT"
        wet.inputs["A" if "A" in wet.inputs else 2].default_value = 0.0
        nt.links.new(drops.outputs[0], wet.inputs["Factor"])
        nt.links.new(rough.outputs[0], wet.inputs[2])
        wet.inputs[3].default_value = 0.055
        nt.links.new(wet.outputs[0], bsdf.inputs["Roughness"])

        dbump = nt.nodes.new("ShaderNodeBump"); dbump.location = (400, -760)
        dbump.inputs["Strength"].default_value = 0.42
        dbump.inputs["Distance"].default_value = 0.012
        nt.links.new(drops.outputs[0], dbump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], dbump.inputs["Normal"])
        nt.links.new(dbump.outputs["Normal"], bsdf.inputs["Normal"])
    else:
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    ob.data.materials.append(mat)
    return mat, img


def build_render_setup():
    """
    Camera, three-point studio softboxes and a gradient world.

    Deliberately contains NO extra mesh object, so elo_cola.blend keeps
    exactly one mesh.  scripts/render_product.py adds the backdrop sweep at
    render time without ever saving it back.
    """
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 256
    sc.render.film_transparent = False
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 16
    sc.cycles.transmission_bounces = 12
    sc.cycles.transparent_max_bounces = 16
    sc.render.resolution_x = 512
    sc.render.resolution_y = 512
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    # Khronos PBR Neutral keeps saturated brand colour intact while still
    # rolling off specular highlights -- the right transform for product viz.
    sc.view_settings.view_transform = "Khronos PBR Neutral"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0

    # ---- camera: three-quarter view, slightly above the mid-line ------
    cam_data = bpy.data.cameras.new("ProductCam")
    cam_data.lens = 120.0
    cam_data.sensor_width = 36.0
    cam = bpy.data.objects.new("ProductCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (-5.63, -53.53, 21.59)
    target = Vector((0.0, 0.0, 6.15))
    direction = target - Vector(cam.location)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = direction.length
    cam_data.dof.aperture_fstop = 9.0
    sc.camera = cam

    # ---- lights ---------------------------------------------------------
    def area(name, loc, look_at, size_x, size_y, power, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, type="AREA")
        ld.shape = "RECTANGLE"
        ld.size = size_x
        ld.size_y = size_y
        ld.energy = power
        ld.color = color
        ld.use_shadow = True
        o = bpy.data.objects.new(name, ld)
        bpy.context.collection.objects.link(o)
        o.location = loc
        d = Vector(look_at) - Vector(loc)
        o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        return o

    # A beverage can is a mirror: what you see on it is the set, not the
    # lights.  Hence large sources, and a very large overhead source so the
    # aluminium lid has something bright to reflect.
    # Tall narrow key -> the long vertical specular streak that makes a can
    # read as polished metal rather than painted plastic.
    # Large, close, low-powered sources: a can is a mirror, so softness
    # comes from the SIZE of what it reflects, not from dimming the lamps.
    # Broad panels give long gentle gradients instead of hot specular dots.
    # Dark studio: broad soft frontal sources for the label, plus two narrow
    # strips raking from behind.  On a cylinder a narrow source becomes a
    # long vertical specular -- that is what separates the can from a dark
    # ground and gives aluminium its edge.
    area("KeyPanel",    (-18, -24, 18), (0, 0, 6.3), 12, 30, 9500, (1.00, 0.97, 0.93))
    area("FillPanel",   (22, -28, 13), (0, 0, 5.8), 24, 32, 3800, (0.85, 0.92, 1.00))
    area("RimLeft",     (-18, 12, 16), (0, 0, 7.2), 3, 22, 4200, (0.68, 0.81, 1.00))
    area("RimRight",    (18, 9, 14), (0, 0, 6.8), 3, 24, 6500, (0.86, 0.93, 1.00))
    area("TopPanel",    (4, 8, 26), (0, 0, 12.1), 10, 16, 4200)
    area("LidFill",     (-12, -10, 24), (0, 0, 12.2), 8, 12, 1600, (0.96, 0.98, 1.00))
    area("FrontBounce", (0, -38, 8), (0, 0, 6.0), 28, 24, 2400, (0.98, 0.99, 1.00))

    # ---- world: soft vertical gradient ----------------------------------
    world = bpy.data.worlds.new("Studio")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    wout = nt.nodes.new("ShaderNodeOutputWorld"); wout.location = (400, 0)
    bg = nt.nodes.new("ShaderNodeBackground"); bg.location = (200, 0)
    bg.inputs["Strength"].default_value = 1.0
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (-80, 0)
    ramp.color_ramp.elements[0].position = 0.18
    ramp.color_ramp.elements[0].color = (0.010, 0.015, 0.028, 1.0)
    ramp.color_ramp.elements[1].position = 0.88
    ramp.color_ramp.elements[1].color = (0.070, 0.092, 0.140, 1.0)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); sep.location = (-300, 0)
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-520, 0)
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], wout.inputs["Surface"])
    return cam


# ===========================================================================
#  Export
# ===========================================================================

def export_obj(ob):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob

    bpy.ops.wm.obj_export(
        filepath=OBJ,
        check_existing=False,
        export_selected_objects=True,
        global_scale=OBJ_SCALE,          # <-- mandated 0.01
        # forward_axis="Y" + up_axis="Z" is Blender's IDENTITY mapping: the
        # file keeps the authored axes verbatim, so the exported OBJ really
        # does store the label centre on -Y with the can standing on +Z.
        # (NEGATIVE_Y would bake a 180 deg spin about Z into the file, and
        #  the default NEGATIVE_Z/Y would rewrite the asset as Y-up.)
        forward_axis="Y",
        up_axis="Z",
        apply_modifiers=True,
        export_eval_mode="DAG_EVAL_VIEWPORT",
        export_uv=True,
        export_normals=True,
        export_materials=True,
        export_triangulated_mesh=False,
        export_object_groups=False,
        export_material_groups=False,
        export_vertex_groups=False,
        export_smooth_groups=False,
        path_mode="STRIP",               # map_Kd elo_cola_texture.png
    )
    postprocess_mtl()


def postprocess_mtl():
    """
    Blender omits a scalar `Kd` when Base Color is driven by a texture.
    Most loaders then default the diffuse factor to white, but a few older
    OBJ readers default it to BLACK and render the can unlit.  Writing an
    explicit `Kd 1 1 1` (a no-op multiplier against map_Kd) removes that
    ambiguity without changing the appearance anywhere.
    """
    mtl = OBJ[:-4] + ".mtl"
    with open(mtl) as fh:
        lines = fh.read().splitlines()
    out, changed = [], False
    for line in lines:
        out.append(line)
        if line.startswith("newmtl ") and not any(
                l.startswith("Kd ") for l in lines):
            out.append("Kd 1.000000 1.000000 1.000000")
            changed = True
    if changed:
        with open(mtl, "w") as fh:
            fh.write("\n".join(out) + "\n")
        print("[gen] added explicit Kd to the MTL for loader compatibility")


# ===========================================================================
#  main
# ===========================================================================

def main():
    if not os.path.exists(TEXTURE):
        raise SystemExit(f"texture not found: {TEXTURE}\n"
                         f"run scripts/generate_texture.py first")

    reset_scene()
    ob, stats = make_mesh()
    mat, img = make_material(ob)
    build_render_setup()

    dims = tuple(ob.dimensions)
    print(f"[gen] mesh      : {stats['verts']} verts, {stats['faces']} faces "
          f"({stats['rings']} rings x {stats['nseg']} segments "
          f"+ {stats['tab_faces']} tab faces)")
    print(f"[gen] native dim: {dims[0]:.4f} x {dims[1]:.4f} x {dims[2]:.4f} "
          f"Blender units (cm)")
    print(f"[gen] exported  : {dims[0]*OBJ_SCALE:.6f} x {dims[1]*OBJ_SCALE:.6f} "
          f"x {dims[2]*OBJ_SCALE:.6f} (OBJ units, metres)")

    # ---- pack the texture, then save the native project ---------------
    img.filepath = TEXTURE
    img.pack()
    img.filepath = "//elo_cola_texture.png"
    os.makedirs(ASSETS, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
    print(f"[gen] wrote {BLEND}")

    export_obj(ob)
    print(f"[gen] wrote {OBJ}")
    print(f"[gen] wrote {OBJ[:-4]}.mtl")

    manifest = dict(
        blender_version=bpy.app.version_string,
        object_name=ob.name,
        mesh_name=ob.data.name,
        material=mat.name,
        texture=os.path.basename(TEXTURE),
        texture_size=[CP.ATLAS, CP.ATLAS],
        obj_export=dict(global_scale=OBJ_SCALE, forward_axis="Y",
                        up_axis="Z", path_mode="STRIP"),
        object_transform_scale=list(ob.scale),
        native_dimensions_cm=[round(d, 6) for d in dims],
        exported_dimensions=[round(d * OBJ_SCALE, 8) for d in dims],
        counts=dict(vertices=stats["verts"], faces=stats["faces"],
                    rings=stats["rings"], segments=stats["nseg"],
                    tab_faces=stats["tab_faces"]),
        atlas_regions=CP.REGIONS,
    )
    with open(MANIFEST, "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"[gen] wrote {MANIFEST}")


if __name__ == "__main__":
    main()
