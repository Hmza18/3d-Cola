"""
Elo Cola -- shared, dependency-free definition of the can profile and the UV atlas.

This module is imported by BOTH:
  * scripts/generate_texture.py  (needs only Pillow / numpy)
  * scripts/generate.py          (needs bpy)
so that the painted texture and the generated UVs are guaranteed to agree.

UNITS
-----
Everything here is in CENTIMETRES.  One Blender unit == 1 cm.
The can is 11.5 cm tall and 6.6 cm in diameter (a standard 330 ml
beverage can).  The OBJ exporter is then run with global_scale = 0.01,
so the exported OBJ is expressed in METRES (0.115 m x 0.066 m x 0.066 m).

ORIENTATION
-----------
The can stands along +Z.  A vertex at profile radius r and angle theta is
placed at (r*cos(theta), r*sin(theta), z) with

    theta_j = THETA0 + j * 2*pi / NSEG          and   u = j / NSEG

THETA0 is chosen as +90 degrees so that u = 0.5 lands on theta = 270
degrees, i.e. exactly on the global -Y axis.  The centre of the label
artwork is painted at u = 0.5, therefore the label centre faces -Y.
"""

import math

# --------------------------------------------------------------------------
# Global constants
# --------------------------------------------------------------------------

ATLAS = 2048                 # texture is ATLAS x ATLAS pixels
NSEG = 128                   # angular segments of the body of revolution
THETA0 = math.pi / 2.0       # angle that maps to u = 0.0  (=> u=0.5 is -Y)
TAB_NSEG = 96                # angular segments of the pull tab

MIN_RING_RADIUS = 0.08       # profile points closer to the axis than this are
                             # dropped; the axis itself becomes a pole vertex

# --------------------------------------------------------------------------
# UV atlas regions:  name -> (u0, v0, u1, v1)   (v measured from image BOTTOM)
# Regions are deliberately separated by empty gutters so that no two regions
# can ever overlap and so mip/bilinear bleeding cannot cross between them.
# --------------------------------------------------------------------------

REGIONS = {
    # the wrap-around printed label: full 360 degrees, upper 60 % of the atlas
    "label":    (0.000, 0.400, 1.000, 1.000),
    # radial projections
    "lid":      (0.015, 0.085, 0.265, 0.335),
    "bottom":   (0.285, 0.085, 0.535, 0.335),
    # pull tab: top face, bottom face, and the chamfer/wall band
    "tab_top":  (0.555, 0.205, 0.680, 0.330),
    "tab_bot":  (0.690, 0.205, 0.805, 0.320),
    "tab_wall": (0.555, 0.140, 0.805, 0.165),
    # rolled rim: wraps 360 degrees across a narrow aluminium band
    "rim":      (0.825, 0.130, 0.995, 0.290),
}

# --------------------------------------------------------------------------
# The lathe profile.
#
# Each entry is a cubic Bezier segment, listed from the BOTTOM pole of the
# can to the TOP pole.  Tangents at the two poles are horizontal so that the
# surface closes smoothly on the axis.
#
#   (name, zone, p0, c0, c1, p1, samples)
#
# "zone" selects which atlas region the ring is textured from.
# --------------------------------------------------------------------------

# Dimensions follow a real 12 fl oz / 355 ml beverage can with a 202
# (52.4 mm) necked-in end:
#     overall height 122.5 mm, body diameter 66.0 mm  (aspect 1.856)
#     straight barrel from 8.5 mm to 107.0 mm -- 80 % of the height
#     neck-in over the top ~12 mm, rolled rim OD 52.4 mm
#     recessed lid panel diameter 46.0 mm, bottom dome depth 9.2 mm
SEGMENTS = [
    # ---- concave bottom dome + standing ring ---------------------------
    ("dome",       "bottom", (0.00,  0.92), (1.10,  0.92), (1.55,  0.77), (1.95,  0.54), 16),
    ("ring_in",    "bottom", (1.95,  0.54), (2.12,  0.40), (2.16,  0.27), (2.22,  0.13),  6),
    ("ring_foot",  "bottom", (2.22,  0.13), (2.26,  0.03), (2.33,  0.00), (2.45,  0.00),  7),
    ("ring_out",   "bottom", (2.45,  0.00), (2.57,  0.00), (2.64,  0.04), (2.70,  0.13),  7),
    # ---- printed area: lower shoulder, body, upper taper, neck ---------
    ("shoulder",   "label",  (2.70,  0.13), (2.98,  0.30), (3.30,  0.44), (3.30,  0.85), 13),
    ("body",       "label",  (3.30,  0.85), (3.30,  4.13), (3.30,  7.42), (3.30, 10.70), 30),
    ("taper",      "label",  (3.30, 10.70), (3.30, 11.14), (2.52, 11.30), (2.52, 11.72), 16),
    ("neck",       "label",  (2.52, 11.72), (2.52, 11.78), (2.51, 11.85), (2.51, 11.90),  4),
    # ---- rolled rim (OD 52.4 mm) ---------------------------------------
    ("rim_out",    "rim",    (2.51, 11.90), (2.66, 11.97), (2.68, 12.14), (2.58, 12.24), 12),
    ("rim_top",    "rim",    (2.58, 12.24), (2.52, 12.29), (2.43, 12.28), (2.38, 12.20), 10),
    # ---- recessed lid: countersink wall + slightly domed panel ---------
    ("countersink","lid",    (2.38, 12.20), (2.35, 12.06), (2.33, 11.92), (2.28, 11.84), 10),
    ("panel",      "lid",    (2.28, 11.84), (2.16, 11.78), (1.25, 11.90), (0.00, 11.94), 26),
]

ZONE_ORDER = ["bottom", "label", "rim", "lid"]

# --------------------------------------------------------------------------
# Lid relief (scored drinking aperture + rivet).  Lid-local XY, centimetres.
# The aperture points toward -Y, i.e. toward the front of the can, so that it
# is visible in the three-quarter product render.
# --------------------------------------------------------------------------

APERTURE = dict(
    c1=(0.00, -1.48), r1=0.48,     # wide lobe, close to the rim
    c2=(0.00, -0.70), r2=0.28,     # narrow lobe, toward the rivet
    score_w=0.030,                 # half-width of the scored groove
    score_d=0.016,                 # groove depth
    dish=0.010,                    # extra dishing inside the score line
)

RIVET = dict(r_head=0.17, r_ring=0.26, h=0.035, groove=0.012)

BEAD = dict(r=2.12, w=0.10, d=0.018)   # circular stiffening bead on the lid

# --------------------------------------------------------------------------
# Pull tab.  Both the outline and the finger hole are tapered capsules
# ("round cones"), which are convex, hence star-shaped about TAB_CENTER.
# That lets both loops be sampled with one shared angular parameter, which in
# turn guarantees a valid, watertight quad strip between them.
# --------------------------------------------------------------------------

TAB = dict(
    center=(0.00, 0.55),
    outer=dict(c1=(0.00, -1.00), r1=0.33, c2=(0.00, 0.85), r2=0.60),
    inner=dict(c1=(0.00,  0.34), r1=0.17, c2=(0.00, 0.88), r2=0.42),
    z_top=12.032,
    z_bot=11.987,
    chamfer=0.012,
)

# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------


def bezier(p0, c0, c1, p1, t):
    """Cubic Bezier point at parameter t."""
    mt = 1.0 - t
    a = mt * mt * mt
    b = 3.0 * mt * mt * t
    c = 3.0 * mt * t * t
    d = t * t * t
    return (
        a * p0[0] + b * c0[0] + c * c1[0] + d * p1[0],
        a * p0[1] + b * c0[1] + c * c1[1] + d * p1[1],
    )


def round_cone_sdf(p, c1, r1, c2, r2, steps=96):
    """
    Signed distance from p to the convex hull of circle(c1,r1) and circle(c2,r2).
    Negative inside.  Sampled numerically -- exact enough for mesh generation
    and far easier to get right than the closed form.
    """
    best = 1e30
    for i in range(steps + 1):
        t = i / steps
        cx = c1[0] + (c2[0] - c1[0]) * t
        cy = c1[1] + (c2[1] - c1[1]) * t
        rr = r1 + (r2 - r1) * t
        d = math.hypot(p[0] - cx, p[1] - cy) - rr
        if d < best:
            best = d
    return best


def round_cone_ray(origin, direction, spec, lo=0.0, hi=4.0, iters=60):
    """Distance along `direction` from `origin` to the hull boundary (sdf == 0)."""
    c1, r1 = spec["c1"], spec["r1"]
    c2, r2 = spec["c2"], spec["r2"]

    def f(t):
        return round_cone_sdf(
            (origin[0] + direction[0] * t, origin[1] + direction[1] * t),
            c1, r1, c2, r2,
        )

    a, b = lo, hi
    for _ in range(iters):
        m = 0.5 * (a + b)
        if f(m) < 0.0:
            a = m
        else:
            b = m
    return 0.5 * (a + b)


# --------------------------------------------------------------------------
# Profile construction
# --------------------------------------------------------------------------


def build_rings():
    """
    Sample the Bezier profile into a bottom-to-top list of rings.

    Returns (rings, pole_bottom, pole_top) where `rings` is a list of dicts:
        r     : radius            (cm, always > MIN_RING_RADIUS)
        z     : height            (cm)
        zone  : atlas region key
        seg   : originating segment name
        s     : cumulative arc length along the profile (cm)
    and the poles are (0.0, z) tuples.
    """
    pts = []
    for name, zone, p0, c0, c1, p1, n in SEGMENTS:
        for i in range(n + 1):
            if i == 0 and pts:
                continue                      # shared with previous segment
            r, z = bezier(p0, c0, c1, p1, i / n)
            pts.append(dict(r=r, z=z, zone=zone, seg=name))

    pole_bottom = (0.0, pts[0]["z"])
    pole_top = (0.0, pts[-1]["z"])

    rings = [p for p in pts if p["r"] > MIN_RING_RADIUS]

    # drop coincident neighbours (would create degenerate faces)
    cleaned = [rings[0]]
    for p in rings[1:]:
        q = cleaned[-1]
        if math.hypot(p["r"] - q["r"], p["z"] - q["z"]) > 1e-5:
            cleaned.append(p)
    rings = cleaned

    s = 0.0
    rings[0]["s"] = 0.0
    for i in range(1, len(rings)):
        s += math.hypot(rings[i]["r"] - rings[i - 1]["r"],
                        rings[i]["z"] - rings[i - 1]["z"])
        rings[i]["s"] = s

    return rings, pole_bottom, pole_top


def zone_spans(rings):
    """
    Map each zone to the inclusive ring index range it owns, EXTENDED by one
    ring into the following zone.

    Face row i spans ring i -> ring i+1 and is textured with the zone of
    ring i.  Extending each zone by one ring means the transition face row is
    parameterised over a range that actually reaches the end of its own atlas
    region, so no UV ever lands in a gutter and no face row is degenerate in
    UV space.
    """
    spans = {}
    for i, ring in enumerate(rings):
        z = ring["zone"]
        if z not in spans:
            spans[z] = [i, i]
        spans[z][1] = i
    # extend upward by one ring (except for the topmost zone)
    for z in ZONE_ORDER:
        if z not in spans:
            continue
        end = spans[z][1]
        if end + 1 < len(rings):
            spans[z][1] = end + 1
    return {k: tuple(v) for k, v in spans.items()}


def label_bands():
    """
    v coordinates (0..1 over the whole atlas) of the printed-label landmarks,
    plus the pixel rows they correspond to.  generate_texture.py uses this so
    that the wordmark is painted exactly on the straight part of the barrel.
    """
    rings, _pb, _pt = build_rings()
    spans = zone_spans(rings)
    a, b = spans["label"]
    s0, s1 = rings[a]["s"], rings[b]["s"]
    u0, v0, u1, v1 = REGIONS["label"]

    def v_of(i):
        return v0 + (rings[i]["s"] - s0) / (s1 - s0) * (v1 - v0)

    def row(v):
        return (1.0 - v) * ATLAS

    marks = {}
    # first and last ring index belonging to each named profile segment
    for seg in ("shoulder", "body", "taper", "neck"):
        idx = [i for i in range(a, b + 1) if rings[i]["seg"] == seg]
        if not idx:
            continue
        marks[seg] = dict(
            v_lo=v_of(idx[0]), v_hi=v_of(idx[-1]),
            row_lo=row(v_of(idx[0])), row_hi=row(v_of(idx[-1])),
        )
    marks["_label"] = dict(v_lo=v0, v_hi=v1, row_lo=row(v0), row_hi=row(v1))
    marks["_rings"] = len(rings)
    return marks


def can_dimensions():
    """Native Blender dimensions of the can in cm (x, y, z)."""
    rings, pb, pt = build_rings()
    rmax = max(r["r"] for r in rings)
    zs = [r["z"] for r in rings] + [pb[1], pt[1]]
    return (2.0 * rmax, 2.0 * rmax, max(zs) - min(zs))


if __name__ == "__main__":
    rings, pb, pt = build_rings()
    print(f"rings            : {len(rings)}")
    print(f"bottom pole      : {pb}")
    print(f"top pole         : {pt}")
    print(f"native dims (cm) : %.4f x %.4f x %.4f" % can_dimensions())
    print(f"z range (cm)     : {min(r['z'] for r in rings):.4f} .. "
          f"{max(r['z'] for r in rings):.4f}")
    print(f"faces (approx)   : {2*NSEG + (len(rings)-1)*NSEG + 8*TAB_NSEG}")
    print("zone spans       :", zone_spans(rings))
    lb = label_bands()
    for k in ("shoulder", "body", "taper", "neck"):
        if k in lb:
            m = lb[k]
            print(f"  {k:9s} v {m['v_lo']:.4f}..{m['v_hi']:.4f}  "
                  f"rows {m['row_hi']:7.1f}..{m['row_lo']:7.1f}")
