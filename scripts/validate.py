#!/usr/bin/env python3
"""
Elo Cola -- automated acceptance tests.

Every test inspects the FILES THAT WERE ACTUALLY PRODUCED, not the source
code that produced them.  Tests 8 and 9 re-open the exported OBJ and the
saved .blend in separate, clean Blender processes.

    python3 scripts/validate.py

Writes docs/validation_results.json and docs/validation_report.md and exits
non-zero if anything fails.
"""

import json
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image

import bpy
import bmesh
import can_profile as CP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
RENDERS = os.path.join(ROOT, "renders")
DOCS = os.path.join(ROOT, "docs")
SCRIPTS = os.path.join(ROOT, "scripts")

F_OBJ = os.path.join(ASSETS, "elo_cola.obj")
F_MTL = os.path.join(ASSETS, "elo_cola.mtl")
F_TEX = os.path.join(ASSETS, "elo_cola_texture.png")
F_BLEND = os.path.join(ASSETS, "elo_cola.blend")
F_PROD = os.path.join(RENDERS, "elo_cola_product_512.png")
F_MANIFEST = os.path.join(ASSETS, "build_manifest.json")

REQUIRED = [F_OBJ, F_MTL, F_TEX, F_BLEND, F_PROD]
EXPECTED_SCALE = 0.01

RESULTS = []


class Test:
    def __init__(self, num, name):
        self.num, self.name = num, name
        self.checks = []
        self.ok = True

    def check(self, ok, label, detail=""):
        ok = bool(ok)
        self.checks.append({"ok": ok, "label": label, "detail": str(detail)})
        if not ok:
            self.ok = False
        return ok

    def info(self, label, detail):
        self.checks.append({"ok": None, "label": label, "detail": str(detail)})

    def done(self):
        RESULTS.append({"test": self.num, "name": self.name,
                        "passed": self.ok, "checks": self.checks})
        tag = "PASS" if self.ok else "FAIL"
        print(f"\n[{tag}] Test {self.num} -- {self.name}")
        for c in self.checks:
            mark = "  . " if c["ok"] is None else ("  + " if c["ok"] else "  X ")
            print(f"{mark}{c['label']}" + (f"  ({c['detail']})" if c["detail"] else ""))
        return self.ok


def run_subproc(script):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, script)],
                       capture_output=True, text=True, timeout=900)
    for line in r.stdout.splitlines():
        if line.startswith("@@JSON@@"):
            return json.loads(line[len("@@JSON@@"):]), r
    return None, r


# ===========================================================================

def test_1_files():
    t = Test(1, "Required files exist and are non-empty")
    for p in REQUIRED:
        ok = os.path.isfile(p) and os.path.getsize(p) > 0
        t.check(ok, os.path.relpath(p, ROOT),
                f"{os.path.getsize(p):,} bytes" if os.path.exists(p) else "MISSING")
    return t.done()


def load_blend_mesh():
    bpy.ops.wm.open_mainfile(filepath=F_BLEND)
    objs = [o for o in bpy.data.objects if o.type == "MESH"]
    return objs


def test_2_mesh_count(blend_info):
    t = Test(2, "The asset contains exactly one mesh object")
    t.check(blend_info["mesh_object_count"] == 1,
            "elo_cola.blend holds exactly 1 mesh object",
            f"{blend_info['mesh_object_count']}: {blend_info['mesh_objects']}")
    t.check(set(blend_info["object_types"]) <= {"MESH", "CAMERA", "LIGHT"},
            "every other object is a camera or a light (not exported)",
            blend_info["object_types"])
    with open(F_OBJ) as fh:
        obj_objects = [l.split(maxsplit=1)[1].strip()
                       for l in fh if l.startswith("o ")]
    t.check(len(obj_objects) == 1, "elo_cola.obj declares exactly 1 object",
            obj_objects)
    t.info("cameras / lights in the project",
           f"{blend_info['cameras']} / {blend_info['lights']}")
    return t.done()


def test_3_texture_count(blend_info):
    t = Test(3, "The exported model references exactly one PNG texture")
    mtl = open(F_MTL).read()
    maps = re.findall(r"^\s*(map_\w+|bump|norm|refl)\s+(.+)$", mtl, re.M)
    files = sorted({m[1].strip().split()[-1] for m in maps})
    t.check(len(files) == 1, "MTL references exactly one image file", files)
    if files:
        t.check(files[0].lower().endswith(".png"), "that image is a PNG", files[0])
        side = os.path.join(ASSETS, os.path.basename(files[0]))
        t.check(os.path.isfile(side), "the image sits beside the OBJ/MTL",
                os.path.relpath(side, ROOT))
    mtls = re.findall(r"^newmtl\s+(.+)$", mtl, re.M)
    t.check(len(mtls) == 1, "MTL declares exactly one material", mtls)
    t.check(blend_info["image_count"] == 1,
            ".blend holds exactly one image datablock",
            [i["name"] for i in blend_info["images"]])
    t.check(len(set(blend_info.get("image_texture_nodes", []))) == 1,
            "the material uses exactly one image-texture node",
            blend_info.get("image_texture_nodes"))
    im = Image.open(F_TEX)
    t.check(im.size == (CP.ATLAS, CP.ATLAS),
            f"texture is {CP.ATLAS}x{CP.ATLAS}", f"{im.size[0]}x{im.size[1]}")
    t.check(blend_info["images"][0]["packed"] if blend_info["images"] else False,
            "texture is packed inside the .blend",
            blend_info["images"][0] if blend_info["images"] else "none")
    return t.done()


def shells_of(bm):
    seen, comps = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, comp = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop(); comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index); stack.append(h)
        comps.append(comp)
    return comps


def test_4_closed(ob):
    t = Test(4, "Geometry is closed on every side (watertight, manifold)")
    me = ob.data
    bm = bmesh.new(); bm.from_mesh(me)
    bm.verts.index_update(); bm.edges.index_update(); bm.faces.index_update()

    boundary = [e for e in bm.edges if len(e.link_faces) == 1]
    nonman_e = [e for e in bm.edges if len(e.link_faces) != 2]
    loose_v = [v for v in bm.verts if not v.link_edges]
    loose_e = [e for e in bm.edges if not e.link_faces]
    degen = [f for f in bm.faces if f.calc_area() < 1e-10]

    t.check(len(boundary) == 0, "zero boundary edges", len(boundary))
    t.check(len(nonman_e) == 0, "zero non-manifold edges", len(nonman_e))
    t.check(len(loose_v) == 0, "zero loose vertices", len(loose_v))
    t.check(len(loose_e) == 0, "zero loose edges", len(loose_e))
    t.check(len(degen) == 0, "zero degenerate faces", len(degen))

    # non-manifold vertices: the faces around a vertex must form one fan/cycle
    bad_v = 0
    for v in bm.verts:
        nf = len(v.link_faces)
        if nf == 0:
            bad_v += 1
            continue
        adj = {f.index: set() for f in v.link_faces}
        for e in v.link_edges:
            lf = [f for f in e.link_faces if f.index in adj]
            if len(lf) == 2:
                adj[lf[0].index].add(lf[1].index)
                adj[lf[1].index].add(lf[0].index)
        start = next(iter(adj))
        seen = {start}; stack = [start]
        while stack:
            c = stack.pop()
            for n in adj[c]:
                if n not in seen:
                    seen.add(n); stack.append(n)
        if len(seen) != nf:
            bad_v += 1
    t.check(bad_v == 0, "zero non-manifold vertices", bad_v)

    # consistent winding: each edge is traversed in opposite directions
    flipped = 0
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        dirs = []
        for f in e.link_faces:
            vs = [l.vert.index for l in f.loops]
            n = len(vs)
            for k in range(n):
                if vs[k] == e.verts[0].index and vs[(k + 1) % n] == e.verts[1].index:
                    dirs.append(1); break
                if vs[k] == e.verts[1].index and vs[(k + 1) % n] == e.verts[0].index:
                    dirs.append(-1); break
        if len(dirs) == 2 and dirs[0] == dirs[1]:
            flipped += 1
    t.check(flipped == 0, "all faces consistently wound (orientable)", flipped)

    comps = shells_of(bm)
    t.info("disconnected shells", len(comps))
    all_ok = True
    for i, c in enumerate(comps):
        vs = {v.index for f in c for v in f.verts}
        es = {e.index for f in c for e in f.edges}
        V, E, F = len(vs), len(es), len(c)
        open_e = sum(1 for e in bm.edges if e.index in es and len(e.link_faces) != 2)
        vol = 0.0
        for f in c:
            vl = [v.co for v in f.verts]
            for k in range(1, len(vl) - 1):
                vol += vl[0].dot(vl[k].cross(vl[k + 1])) / 6.0
        chi = V - E + F
        genus = (2 - chi) // 2
        ok = (open_e == 0 and vol > 0)
        all_ok &= ok
        t.check(ok, f"shell {i} closed with outward normals",
                f"V={V} E={E} F={F} chi={chi} genus={genus} "
                f"volume={vol:.4f} cm^3 open_edges={open_e}")
    bm.free()
    return t.done()


def test_5_orientation(ob):
    t = Test(5, "Front label faces -Y and the can stands along +Z")
    me = ob.data
    uv = me.uv_layers.active.data
    bb = [v.co for v in me.vertices]
    zmin = min(p.z for p in bb); zmax = max(p.z for p in bb)
    xr = max(p.x for p in bb) - min(p.x for p in bb)
    yr = max(p.y for p in bb) - min(p.y for p in bb)

    t.check(abs(zmin) < 1e-6, "the can stands on z = 0", f"z_min={zmin:.9f}")
    t.check(zmax > xr and zmax > yr, "+Z is the long axis",
            f"z={zmax:.4f} x={xr:.4f} y={yr:.4f}")
    t.check(abs(xr - yr) < 1e-6, "circular in plan", f"|x-y|={abs(xr-yr):.2e}")

    # every loop painted at u = 0.5 of the label must sit exactly on -Y
    pts = []
    for poly in me.polygons:
        for li in range(poly.loop_start, poly.loop_start + poly.loop_total):
            u, v = uv[li].uv
            if abs(u - 0.5) < 1e-6 and v > CP.REGIONS["label"][1] + 1e-6:
                pts.append(me.vertices[me.loops[li].vertex_index].co)
    t.check(len(pts) > 0, "found loops at label u = 0.5", len(pts))
    if pts:
        mx = max(abs(p.x) for p in pts)
        my = max(p.y for p in pts)
        t.check(mx < 1e-6, "label centre lies on the x = 0 plane", f"max|x|={mx:.3e}")
        t.check(my < 0, "label centre points at -Y", f"max y={my:.6f} cm")

    # the modelled aperture / tab must also face -Y (it is the front detail)
    tab_y = [me.vertices[i].co.y for i in range(len(me.vertices))
             if me.vertices[i].co.z > CP.TAB["z_bot"] - 1e-6]
    if tab_y:
        t.info("pull-tab y extent (cm)", f"{min(tab_y):.3f} .. {max(tab_y):.3f}")
    t.info("native bounding box (cm)",
           f"{xr:.4f} x {yr:.4f} x {zmax - zmin:.4f}")

    # --- the same assertion made against the RAW OBJ TEXT, with no
    #     importer in the loop, so no axis convention can mask a flip ----
    V, VT, hits = [], [], []
    with open(F_OBJ) as fh:
        for ln in fh:
            if ln.startswith("v "):
                V.append(tuple(float(x) for x in ln.split()[1:4]))
            elif ln.startswith("vt "):
                VT.append(tuple(float(x) for x in ln.split()[1:3]))
            elif ln.startswith("f "):
                for tok in ln.split()[1:]:
                    a = tok.split("/")
                    if len(a) > 1 and a[1]:
                        u, vv = VT[int(a[1]) - 1]
                        if abs(u - 0.5) < 1e-5 and vv > 0.45:
                            hits.append(V[int(a[0]) - 1])
    t.check(len(hits) > 0, "raw OBJ text: found label-centre vertices", len(hits))
    if hits:
        t.check(max(abs(p[0]) for p in hits) < 1e-6,
                "raw OBJ text: label centre lies on x = 0",
                f"max|x|={max(abs(p[0]) for p in hits):.2e}")
        t.check(max(p[1] for p in hits) < 0,
                "raw OBJ text: label centre faces -Y (file is not axis-converted)",
                f"y {min(p[1] for p in hits):.6f} .. {max(p[1] for p in hits):.6f} m")
    ozs = [p[2] for p in V]
    t.check(abs(min(ozs)) < 1e-6 and max(ozs) > 0,
            "raw OBJ text: the can stands along +Z",
            f"z {min(ozs):.6f} .. {max(ozs):.6f} m")
    return t.done()


def test_6_scale(ob, manifest):
    t = Test(6, "OBJ exported with scale factor 0.01, applied exactly once")
    t.check(manifest["obj_export"]["global_scale"] == EXPECTED_SCALE,
            "build manifest records global_scale = 0.01",
            manifest["obj_export"]["global_scale"])
    t.check(manifest["obj_export"]["forward_axis"] == "Y"
            and manifest["obj_export"]["up_axis"] == "Z",
            "export used Blender's identity axis mapping (no axis rewrite)",
            f"forward={manifest['obj_export']['forward_axis']} "
            f"up={manifest['obj_export']['up_axis']}")

    xs, ys, zs = [], [], []
    with open(F_OBJ) as fh:
        for line in fh:
            if line.startswith("v "):
                a, b, c = line.split()[1:4]
                xs.append(float(a)); ys.append(float(b)); zs.append(float(c))
    obj_dim = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    native = tuple(ob.dimensions)
    ratios = [obj_dim[i] / native[i] for i in range(3)]

    t.check(all(abs(r - EXPECTED_SCALE) < 1e-7 for r in ratios),
            "exported/native dimension ratio is exactly 0.01",
            "  ".join(f"{r:.9f}" for r in ratios))
    t.check(all(abs(s - 1.0) < 1e-9 for s in ob.scale),
            "object transform scale is 1.0 (0.01 is NOT applied twice)",
            tuple(round(s, 9) for s in ob.scale))
    t.check(abs(min(zs)) < 1e-7, "exported mesh still stands on z = 0",
            f"{min(zs):.9f}")
    t.info("native dimensions (Blender units = cm)",
           f"{native[0]:.4f} x {native[1]:.4f} x {native[2]:.4f}")
    t.info("exported OBJ dimensions (metres)",
           f"{obj_dim[0]:.6f} x {obj_dim[1]:.6f} x {obj_dim[2]:.6f}")
    t.info("i.e. real-world size",
           f"{obj_dim[0]*1000:.1f} x {obj_dim[1]*1000:.1f} x {obj_dim[2]*1000:.1f} mm")
    return t.done()


def _isect(S, E, A, B):
    """Intersection of the segment S-E with the infinite line A-B."""
    dcx, dcy = A[0] - B[0], A[1] - B[1]
    dpx, dpy = S[0] - E[0], S[1] - E[1]
    n1 = A[0] * B[1] - A[1] * B[0]
    n2 = S[0] * E[1] - S[1] * E[0]
    den = dcx * dpy - dcy * dpx
    if abs(den) < 1e-18:
        return E
    return ((n1 * dpx - n2 * dcx) / den, (n1 * dpy - n2 * dcy) / den)


def _clip_area(subject, clipper):
    """Exact area of the intersection of two convex polygons."""
    out = list(subject)
    cn = len(clipper)
    a = 0.0
    for k in range(cn):
        a += clipper[k][0] * clipper[(k + 1) % cn][1] - \
             clipper[(k + 1) % cn][0] * clipper[k][1]
    cl = clipper if a >= 0 else clipper[::-1]
    for k in range(cn):
        A, B = cl[k], cl[(k + 1) % cn]
        ex, ey = B[0] - A[0], B[1] - A[1]
        inp, out = out, []
        if not inp:
            return 0.0
        S = inp[-1]
        for E in inp:
            sIn = (ex * (S[1] - A[1]) - ey * (S[0] - A[0])) <= 0
            eIn = (ex * (E[1] - A[1]) - ey * (E[0] - A[0])) <= 0
            if eIn:
                if not sIn:
                    out.append(_isect(S, E, A, B))
                out.append(E)
            elif sIn:
                out.append(_isect(S, E, A, B))
            S = E
    if len(out) < 3:
        return 0.0
    a = 0.0
    for k in range(len(out)):
        a += out[k][0] * out[(k + 1) % len(out)][1] - \
             out[(k + 1) % len(out)][0] * out[k][1]
    return abs(a) * 0.5


def test_7_uv(ob):
    t = Test(7, "UV mapping is valid, correctly routed and not mirrored")
    me = ob.data
    t.check(len(me.uv_layers) == 1, "exactly one UV layer",
            [l.name for l in me.uv_layers])
    uvd = me.uv_layers.active.data
    uvs = np.array([tuple(d.uv) for d in uvd], dtype=np.float64)

    t.check(np.isfinite(uvs).all(), "all UV coordinates are finite (no NaN/inf)")
    t.check(uvs.min() >= -1e-6 and uvs.max() <= 1 + 1e-6,
            "all UVs inside [0, 1]",
            f"u {uvs[:,0].min():.6f}..{uvs[:,0].max():.6f}  "
            f"v {uvs[:,1].min():.6f}..{uvs[:,1].max():.6f}")

    # --- every face must sit inside exactly one declared atlas region ---
    regions = CP.REGIONS
    eps = 1e-6
    unassigned, multi = 0, 0
    per_region = {k: 0 for k in regions}
    face_region = []
    for poly in me.polygons:
        pu = uvs[poly.loop_start:poly.loop_start + poly.loop_total]
        hit = []
        for name, (u0, v0, u1, v1) in regions.items():
            if (pu[:, 0] >= u0 - eps).all() and (pu[:, 0] <= u1 + eps).all() \
               and (pu[:, 1] >= v0 - eps).all() and (pu[:, 1] <= v1 + eps).all():
                hit.append(name)
        if not hit:
            unassigned += 1
            face_region.append(None)
        else:
            if len(hit) > 1:
                multi += 1
            per_region[hit[0]] += 1
            face_region.append(hit[0])
    t.check(unassigned == 0, "every face lands inside a declared atlas region",
            f"{unassigned} stray faces")
    t.check(multi == 0, "atlas regions do not overlap each other", multi)
    t.info("faces per region",
           ", ".join(f"{k}={v}" for k, v in per_region.items() if v))

    # --- EXACT overlap test -------------------------------------------
    # Triangulate every face in UV space, then analytically intersect
    # (Sutherland-Hodgman) each pair of triangles whose PARENT FACES SHARE
    # NO VERTEX.  Faces that do share a vertex are edge/corner neighbours:
    # they touch along that edge but enclose no common area, so excluding
    # them removes the only legitimate source of contact and leaves genuine
    # unintended overlap as the only thing this can report.  Unlike a
    # raster test this has no resolution error -- thin faces are exact.
    tris = []
    total_area = 0.0
    for fi, poly in enumerate(me.polygons):
        loops = list(range(poly.loop_start, poly.loop_start + poly.loop_total))
        pu = [tuple(uvs[l]) for l in loops]
        vids = frozenset(me.loops[l].vertex_index for l in loops)
        n = len(pu)
        a = 0.0
        for k in range(n):
            a += pu[k][0] * pu[(k + 1) % n][1] - pu[(k + 1) % n][0] * pu[k][1]
        total_area += abs(a) * 0.5
        for k in range(1, n - 1):
            tris.append(((pu[0], pu[k], pu[k + 1]), fi, vids))

    CELL = 256
    buckets = {}
    for ti, (pts, fi, vids) in enumerate(tris):
        i0 = int(min(q[0] for q in pts) * CELL); i1 = int(max(q[0] for q in pts) * CELL)
        j0 = int(min(q[1] for q in pts) * CELL); j1 = int(max(q[1] for q in pts) * CELL)
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                buckets.setdefault((i, j), []).append(ti)

    worst, overlap_area, overlap_pairs, tested = 0.0, 0.0, 0, set()
    for ids in buckets.values():
        if len(ids) < 2:
            continue
        for ai in range(len(ids)):
            for bi in range(ai + 1, len(ids)):
                ta, tb = ids[ai], ids[bi]
                pa, fa, va = tris[ta]
                pb, fb, vb = tris[tb]
                if fa == fb or (va & vb):
                    continue
                key = (ta, tb) if ta < tb else (tb, ta)
                if key in tested:
                    continue
                tested.add(key)
                ar = _clip_area(pa, pb)
                if ar > 1e-12:
                    overlap_area += ar
                    overlap_pairs += 1
                    worst = max(worst, ar)
    t.check(overlap_pairs == 0,
            "exact test: no two non-adjacent faces overlap in UV space",
            f"{overlap_pairs} overlapping pairs, total {overlap_area:.3e}, "
            f"worst {worst:.3e} (atlas = 1.0)")
    t.info("UV area used / non-adjacent triangle pairs tested",
           f"{total_area:.5f} / {len(tested):,}")

    # --- mirroring: on the front of the can, +u must go to +x and +v to +z
    du_dx, dv_dz, n_front = 0, 0, 0
    for fi, poly in enumerate(me.polygons):
        if face_region[fi] != "label":
            continue
        c = poly.center
        if c.y > -0.8 * 3.0 or abs(c.x) > 1.0:
            continue
        loops = list(range(poly.loop_start, poly.loop_start + poly.loop_total))
        pu = [uvs[l] for l in loops]
        pv = [me.vertices[me.loops[l].vertex_index].co for l in loops]
        for a in range(len(loops)):
            for b in range(a + 1, len(loops)):
                if abs(pu[a][0] - pu[b][0]) > 1e-9:
                    du_dx += 1 if ((pu[a][0] - pu[b][0]) *
                                   (pv[a].x - pv[b].x) > 0) else -1
                if abs(pu[a][1] - pu[b][1]) > 1e-9:
                    dv_dz += 1 if ((pu[a][1] - pu[b][1]) *
                                   (pv[a].z - pv[b].z) > 0) else -1
        n_front += 1
    t.check(n_front > 0, "found front-facing label faces to test", n_front)
    t.check(du_dx > 0, "+u runs to +x on the front (artwork NOT mirrored)",
            f"score={du_dx}")
    t.check(dv_dz > 0, "+v runs up the can (artwork not flipped)",
            f"score={dv_dz}")

    # --- the atlas content under each region is the right kind of surface
    tex = np.asarray(Image.open(F_TEX).convert("RGB"), dtype=np.float64)

    def sample_all(region_name, limit=9000):
        cols = []
        for fi, poly in enumerate(me.polygons):
            if face_region[fi] != region_name:
                continue
            u, v = uvs[poly.loop_start:poly.loop_start + poly.loop_total].mean(axis=0)
            px = min(CP.ATLAS - 1, max(0, int(u * CP.ATLAS)))
            py = min(CP.ATLAS - 1, max(0, int((1 - v) * CP.ATLAS)))
            cols.append(tex[py, px])
            if len(cols) >= limit:
                break
        return np.array(cols) if cols else None

    def sample(region_name, limit=4000):
        a = sample_all(region_name, limit)
        return a.mean(axis=0) if a is not None else None

    # The printed barrel must carry saturated ink, and the three brand
    # colours must each actually land on geometry.  Stated this way the
    # check is about the mapping, not about one particular layout, so it
    # holds for every label concept in generate_texture.py.
    labs = sample_all("label")
    if labs is not None:
        spread = float((labs.max(axis=1) - labs.min(axis=1)).mean())
        t.check(spread > 40,
                "label faces sample saturated printed ink (not bare metal)",
                f"mean channel spread {spread:.1f}, mean RGB "
                f"{labs.mean(axis=0).round(1).tolist()}")
        n = len(labs)
        blue = float((labs[:, 2] > labs[:, 0] + 20).mean())
        red = float((labs[:, 0] > labs[:, 2] + 20).mean())
        white = float((labs.min(axis=1) > 200).mean())
        t.check(blue > 0.05 and red > 0.02 and white > 0.01,
                "cobalt, red and white artwork all land on the barrel",
                f"of {n} label faces: {blue*100:.1f}% cobalt, "
                f"{red*100:.1f}% red, {white*100:.1f}% white")
    for rn in ("lid", "bottom", "rim", "tab_top"):
        c = sample(rn)
        if c is not None:
            t.check(float(c.max() - c.min()) < 26,
                    f"{rn} faces sample neutral aluminium",
                    f"mean RGB {c.round(1).tolist()}")
    return t.done()


def test_8_reimport(ob, manifest):
    t = Test(8, "Exported OBJ re-imports cleanly into an empty Blender scene")
    info, proc = run_subproc("_reimport_check.py")
    if info is None:
        t.check(False, "re-import subprocess produced a report",
                proc.stderr.strip()[-400:])
        return t.done()
    t.check(info["mesh_object_count"] == 1, "exactly one mesh imported",
            info["mesh_objects"])
    t.check(info["vertices"] == len(ob.data.vertices),
            "vertex count survives the round trip",
            f"{info['vertices']} vs {len(ob.data.vertices)}")
    t.check(info["polygons"] == len(ob.data.polygons),
            "face count survives the round trip",
            f"{info['polygons']} vs {len(ob.data.polygons)}")
    t.check(len(info["uv_layers"]) == 1, "UV layer present", info["uv_layers"])
    t.check(len(info["materials"]) == 1, "material reference resolves",
            info["materials"])
    t.check(info["texture_count"] == 1, "exactly one texture referenced",
            [x["resolved"] for x in info["textures"]])
    t.check(not info["missing_textures"], "texture file resolves on disk",
            info["missing_textures"])
    t.check(all(x["loaded"] and tuple(x["size"]) == (CP.ATLAS, CP.ATLAS)
                for x in info["textures"]),
            "texture loads at full resolution",
            [x["size"] for x in info["textures"]])

    expect = [round(d * EXPECTED_SCALE, 9) for d in ob.dimensions]
    got = info["dimensions"]
    # OBJ writes coordinates with 6 decimals, so a round trip can only be
    # faithful to 1e-6 in the exported (metre) units
    t.check(all(abs(got[i] - expect[i]) < 2e-6 for i in range(3)),
            "dimensions are native x 0.01 (to the OBJ's 1e-6 m precision)",
            f"{got} vs expected {expect}")
    t.check(info.get("transform_is_identity"),
            "re-import needs no corrective transform (identity axes)",
            info.get("matrix_world"))
    t.check(abs(info["bbox_min"][2]) < 1e-7, "still standing on z = 0",
            info["bbox_min"][2])
    t.check(info["front_loop_count"] > 0 and
            info["front_max_abs_x"] < 1e-6 and info["front_max_y"] < 0,
            "label centre still faces -Y after the round trip",
            f"loops={info['front_loop_count']} max|x|={info.get('front_max_abs_x')} "
            f"max_y={info.get('front_max_y')}")
    t.check(info["boundary_edges"] == 0 and info["non_manifold_edges"] == 0
            and info["loose_verts"] == 0 and info["degenerate_faces"] == 0,
            "geometry is still watertight after the round trip",
            f"boundary={info['boundary_edges']} nonmanifold={info['non_manifold_edges']} "
            f"loose={info['loose_verts']} degenerate={info['degenerate_faces']}")
    t.check(all(s["open_edges"] == 0 and s["volume"] > 0 for s in info["shells"]),
            "every shell still closed with outward normals",
            info["shells"])
    return t.done()


def test_9_blend(blend_info):
    t = Test(9, "Saved .blend opens in a separate Blender process")
    t.check(blend_info.get("opened"), "file opened without error")
    t.check(blend_info["mesh_object_count"] == 1, "one mesh object present",
            blend_info["mesh_objects"])
    t.check(len(blend_info.get("uv_layers", [])) == 1, "UV map present",
            blend_info.get("uv_layers"))
    t.check(len(blend_info.get("materials", [])) == 1, "material present",
            blend_info.get("materials"))
    t.check(blend_info["image_count"] == 1 and blend_info["images"][0]["packed"],
            "single texture present and packed (no missing dependency)",
            blend_info["images"])
    t.check(blend_info["render_engine"] == "CYCLES", "render set-up saved (Cycles)",
            blend_info["render_engine"])
    t.check(len(blend_info["cameras"]) >= 1 and len(blend_info["lights"]) >= 1,
            "camera and studio lights saved with the project",
            f"{len(blend_info['cameras'])} camera(s), "
            f"{len(blend_info['lights'])} light(s)")
    return t.done()


def test_10_product_image():
    t = Test(10, "Final product image is exactly 512 x 512 PNG")
    im = Image.open(F_PROD)
    t.check(im.format == "PNG", "format is PNG", im.format)
    t.check(im.size == (512, 512), "resolution is 512 x 512",
            f"{im.size[0]} x {im.size[1]}")
    a = np.asarray(im.convert("RGB"))
    t.check(a.std() > 8, "image is not blank", f"stddev={a.std():.2f}")
    t.info("file size", f"{os.path.getsize(F_PROD):,} bytes")
    return t.done()


# ===========================================================================

def main():
    print("=" * 74)
    print("  ELO COLA -- asset validation")
    print(f"  Blender {bpy.app.version_string}")
    print("=" * 74)

    ok = test_1_files()
    if not ok:
        print("\nAborting: required files are missing.")
        sys.exit(1)

    manifest = json.load(open(F_MANIFEST))
    blend_info, proc = run_subproc("_blend_check.py")
    if blend_info is None:
        print("could not open the .blend in a subprocess:\n", proc.stderr[-2000:])
        sys.exit(1)

    objs = load_blend_mesh()
    ob = objs[0]

    results = [ok]
    results.append(test_2_mesh_count(blend_info))
    results.append(test_3_texture_count(blend_info))
    results.append(test_4_closed(ob))
    results.append(test_5_orientation(ob))
    results.append(test_6_scale(ob, manifest))
    results.append(test_7_uv(ob))
    results.append(test_8_reimport(ob, manifest))
    results.append(test_9_blend(blend_info))
    results.append(test_10_product_image())

    passed = sum(1 for r in results if r)
    print("\n" + "=" * 74)
    print(f"  {passed}/{len(results)} tests passed")
    print("=" * 74)

    os.makedirs(DOCS, exist_ok=True)
    with open(os.path.join(DOCS, "validation_results.json"), "w") as fh:
        json.dump({"blender": bpy.app.version_string,
                   "passed": passed, "total": len(results),
                   "tests": RESULTS}, fh, indent=2)
    write_report(passed, len(results))
    sys.exit(0 if passed == len(results) else 1)


def write_report(passed, total):
    lines = ["# Elo Cola -- validation report", "",
             f"Blender **{bpy.app.version_string}** &nbsp;|&nbsp; "
             f"**{passed}/{total} tests passed**", ""]
    for r in RESULTS:
        lines.append(f"### Test {r['test']} &mdash; {r['name']}")
        lines.append("")
        lines.append(f"**{'PASS' if r['passed'] else 'FAIL'}**")
        lines.append("")
        lines.append("| | check | detail |")
        lines.append("|---|---|---|")
        for c in r["checks"]:
            mark = "i" if c["ok"] is None else ("PASS" if c["ok"] else "FAIL")
            det = c["detail"].replace("|", "\\|")
            lines.append(f"| {mark} | {c['label']} | `{det}` |" if det
                         else f"| {mark} | {c['label']} | |")
        lines.append("")
    with open(os.path.join(DOCS, "validation_report.md"), "w") as fh:
        fh.write("\n".join(lines))
    print(f"wrote {os.path.join(DOCS,'validation_report.md')}")


if __name__ == "__main__":
    main()
