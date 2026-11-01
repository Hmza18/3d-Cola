#!/usr/bin/env python3
"""Open assets/elo_cola.blend in a FRESH Blender process and report on it (JSON)."""
import json, os, sys
import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLEND = os.path.join(ROOT, "assets", "elo_cola.blend")

bpy.ops.wm.open_mainfile(filepath=BLEND)

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
imgs = [i for i in bpy.data.images if i.name not in ("Render Result", "Viewer Node")]
out = {
    "opened": True,
    "blender": bpy.app.version_string,
    "mesh_objects": [o.name for o in meshes],
    "mesh_object_count": len(meshes),
    "object_types": sorted({o.type for o in bpy.data.objects}),
    "images": [{"name": i.name, "size": list(i.size), "packed": bool(i.packed_file),
                "filepath": i.filepath} for i in imgs],
    "image_count": len(imgs),
}
if meshes:
    me = meshes[0].data
    out["uv_layers"] = [l.name for l in me.uv_layers]
    out["materials"] = [m.name for m in me.materials if m]
    out["vertices"] = len(me.vertices)
    out["polygons"] = len(me.polygons)
    out["dimensions"] = [round(d, 6) for d in meshes[0].dimensions]
    out["transform_scale"] = [round(v, 9) for v in meshes[0].scale]
    tex_nodes = []
    for m in me.materials:
        if m and m.node_tree:
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image:
                    tex_nodes.append(n.image.name)
    out["image_texture_nodes"] = tex_nodes
out["cameras"] = [o.name for o in bpy.data.objects if o.type == "CAMERA"]
out["lights"] = [o.name for o in bpy.data.objects if o.type == "LIGHT"]
out["render_engine"] = bpy.context.scene.render.engine
print("@@JSON@@" + json.dumps(out))
