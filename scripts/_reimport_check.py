#!/usr/bin/env python3
"""
Re-import assets/elo_cola.obj into a CLEAN, EMPTY Blender scene in a fresh
process and report everything the round trip has to preserve (JSON).
"""
import json, math, os, sys
import bpy, bmesh

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBJ = os.path.join(ROOT, "assets", "elo_cola.obj")

bpy.ops.wm.read_factory_settings(use_empty=True)

kw = dict(filepath=OBJ)
rna = bpy.ops.wm.obj_import.get_rna_type().properties.keys()
# Import with exactly the axes the file was written with -> identity round
# trip, and (because Y/Z is Blender's identity mapping) an identity object
# transform, so local coordinates equal world coordinates.
if "forward_axis" in rna:
    kw["forward_axis"] = "Y"
if "up_axis" in rna:
    kw["up_axis"] = "Z"
if "global_scale" in rna:
    kw["global_scale"] = 1.0
if "validate_meshes" in rna:
    kw["validate_meshes"] = True
bpy.ops.wm.obj_import(**kw)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
out = {"imported": True, "mesh_object_count": len(meshes),
       "mesh_objects": [o.name for o in meshes]}

if meshes:
    ob = meshes[0]
    me = ob.data
    out["dimensions"] = [round(d, 9) for d in ob.dimensions]
    mw = ob.matrix_world
    out["matrix_world"] = [[round(mw[r][c], 9) for c in range(4)] for r in range(4)]
    out["transform_is_identity"] = all(
        abs(mw[r][c] - (1.0 if r == c else 0.0)) < 1e-6
        for r in range(4) for c in range(4))
    bb = [ob.matrix_world @ v.co for v in me.vertices]
    out["bbox_min"] = [round(min(p[i] for p in bb), 9) for i in range(3)]
    out["bbox_max"] = [round(max(p[i] for p in bb), 9) for i in range(3)]
    out["vertices"] = len(me.vertices)
    out["polygons"] = len(me.polygons)
    out["uv_layers"] = [l.name for l in me.uv_layers]
    out["materials"] = [m.name for m in me.materials if m]

    # --- material / texture resolution --------------------------------
    imgs, missing = [], []
    for m in me.materials:
        if not m or not m.node_tree:
            continue
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image:
                fp = bpy.path.abspath(n.image.filepath)
                ok = os.path.exists(fp)
                try:
                    n.image.reload()
                    loaded = tuple(n.image.size) != (0, 0)
                except Exception:
                    loaded = False
                imgs.append({"name": n.image.name, "filepath": n.image.filepath,
                             "resolved": os.path.basename(fp), "exists": ok,
                             "loaded": loaded, "size": list(n.image.size)})
                if not ok:
                    missing.append(fp)
    out["textures"] = imgs
    out["texture_count"] = len(imgs)
    out["missing_textures"] = missing

    # --- watertight after the round trip -------------------------------
    bm = bmesh.new(); bm.from_mesh(me)
    out["boundary_edges"] = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    out["non_manifold_edges"] = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    out["loose_verts"] = sum(1 for v in bm.verts if not v.link_edges)
    out["degenerate_faces"] = sum(1 for f in bm.faces if f.calc_area() < 1e-12)

    # --- orientation: the label centre (u = 0.5) must sit on -Y --------
    uv = bm.loops.layers.uv.active
    front = []
    if uv:
        for f in bm.faces:
            for l in f.loops:
                u, v = l[uv].uv
                if abs(u - 0.5) < 1e-5 and v > 0.45:
                    front.append(tuple(ob.matrix_world @ l.vert.co))
    out["front_loop_count"] = len(front)
    if front:
        out["front_max_abs_x"] = round(max(abs(p[0]) for p in front), 9)
        out["front_max_y"] = round(max(p[1] for p in front), 9)
        out["front_min_y"] = round(min(p[1] for p in front), 9)

    # per-shell closure
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
    shells = []
    for c in comps:
        vol = 0.0
        for f in c:
            vl = [v.co for v in f.verts]
            for k in range(1, len(vl) - 1):
                vol += vl[0].dot(vl[k].cross(vl[k + 1])) / 6.0
        es = {e.index for f in c for e in f.edges}
        shells.append({"faces": len(c), "volume": round(vol, 12),
                       "open_edges": sum(1 for e in bm.edges
                                         if e.index in es and len(e.link_faces) != 2)})
    out["shells"] = shells
    bm.free()

print("@@JSON@@" + json.dumps(out))
