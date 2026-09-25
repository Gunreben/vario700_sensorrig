"""Auto-guess flat paint colours per mesh piece (loose part) of every link.

Usage (after assemble.py):
  blender -b -P tools/texture_roundtrip/paint_auto.py -- [--work texture_work] [--preview]

Writes texture_work/paint.blend: every link with the palette as material
slots and a guessed material per face. Open it in Blender to fix mistakes,
then run paint_export.py.
"""

import argparse
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blender_io import render_views, script_args  # noqa: E402

# name: sRGB colour (as picked from photos), roughness, metallic
PALETTE = {
    "dark_grey":     ((0.17, 0.17, 0.18), 0.6, 0.0),   # chassis, linkage, default
    "black_plastic": ((0.06, 0.06, 0.06), 0.7, 0.0),   # mudguards, grille, steps, mirrors
    "fendt_green":   ((0.30, 0.58, 0.17), 0.35, 0.0),
    "roof_white":    ((0.88, 0.87, 0.82), 0.4, 0.0),
    "glass":         ((0.12, 0.16, 0.18), 0.05, 0.0),
    "rim_red":       ((0.82, 0.12, 0.10), 0.4, 0.0),
    "tyre":          ((0.04, 0.04, 0.04), 0.9, 0.0),
    "metal":         ((0.55, 0.56, 0.57), 0.3, 1.0),   # bolts, hitch hooks, exhaust tip
    "aluminium":     ((0.72, 0.73, 0.75), 0.35, 1.0),  # sensor rig profiles
    "light_lens":    ((0.90, 0.90, 0.88), 0.1, 0.0),
    "amber":         ((0.95, 0.50, 0.05), 0.2, 0.0),
}


def srgb_to_linear(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def palette_materials():
    mats = {}
    for name, (srgb, rough, metal) in PALETTE.items():
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        rgba = (*srgb_to_linear(srgb), 1.0)
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        mat.diffuse_color = rgba  # viewport solid-mode colour
        mat.use_fake_user = True
        mats[name] = mat
    return mats


class Pieces:
    """Loose parts of a mesh with per-piece features in the base frame (metres)."""

    def __init__(self, obj):
        me = obj.data
        nf, nv = len(me.polygons), len(me.vertices)
        m = np.array(obj.matrix_world)
        co = np.empty(nv * 3); me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        self.raw = co
        self.co = co @ m[:3, :3].T + m[:3, 3]
        ls = np.empty(nf, int); me.polygons.foreach_get("loop_start", ls)
        lt = np.empty(nf, int); me.polygons.foreach_get("loop_total", lt)
        lv = np.empty(len(me.loops), int); me.loops.foreach_get("vertex_index", lv)

        # Union-find over vertices shared by faces.
        parent = np.arange(nv)

        def find(a):
            root = a
            while parent[root] != root:
                root = parent[root]
            while parent[a] != root:
                parent[a], a = root, parent[a]
            return root

        for f in range(nf):
            vs = lv[ls[f]:ls[f] + lt[f]]
            r = find(vs[0])
            for v in vs[1:]:
                q = find(v)
                if q != r:
                    parent[q] = r
        roots = np.array([find(v) for v in range(nv)])
        _, self.face_piece = np.unique(roots[lv[ls]], return_inverse=True)
        P = self.n = self.face_piece.max() + 1
        fp = self.face_piece

        scale = np.linalg.norm(m[:3, 0])
        area = np.empty(nf); me.polygons.foreach_get("area", area)
        area *= scale ** 2
        nrm = np.empty(nf * 3); me.polygons.foreach_get("normal", nrm)
        nrm = nrm.reshape(-1, 3) @ m[:3, :3].T / scale
        self.faces = fp
        self.area = np.bincount(fp, area, P)
        self.count = np.bincount(fp, minlength=P)
        n_sum = np.stack([np.bincount(fp, nrm[:, i] * area, P) for i in range(3)], 1)
        self.flat = np.linalg.norm(n_sum, axis=1) / np.maximum(self.area, 1e-12)
        self.normal = n_sum / np.maximum(np.linalg.norm(n_sum, axis=1), 1e-12)[:, None]

        vp = np.zeros(nv, int)
        vp[lv] = np.repeat(fp, lt)
        self.lo = np.full((P, 3), np.inf)
        self.hi = np.full((P, 3), -np.inf)
        for i in range(3):
            np.minimum.at(self.lo[:, i], vp, self.co[:, i])
            np.maximum.at(self.hi[:, i], vp, self.co[:, i])
        self.vert_piece = vp
        self.center = (self.lo + self.hi) / 2
        self.ext = self.hi - self.lo


def box(p, x=None, y=None, z=None, ax=None):
    """Pieces whose bbox centre lies in the given ranges (ax = |x|)."""
    c = p.center
    ok = np.ones(p.n, bool)
    for rng, v in ((x, c[:, 0]), (y, c[:, 1]), (z, c[:, 2]), (ax, np.abs(c[:, 0]))):
        if rng is not None:
            ok &= (v >= rng[0]) & (v <= rng[1])
    return ok


def classify_wheel(p, obj):
    # Wheel meshes are in raw coordinates around the x axis: radius from y/z.
    r = np.hypot(p.raw[:, 1], p.raw[:, 2])
    r_min = np.full(p.n, np.inf)
    np.minimum.at(r_min, p.vert_piece, r)
    R = r.max()
    return np.where(r_min < 0.45 * R, "rim_red", "tyre")


def classify_body(p):
    cls = np.full(p.n, "dark_grey", dtype=object)
    A, flat, ext, lo, hi = p.area, p.flat, p.ext, p.lo, p.hi
    thin = ext.min(1)
    cab = box(p, ax=(0, 0.9), y=(-1.3, 0.45), z=(1.2, 3.0))

    # Mudguards over the front wheels, grille/nose, fuel tank and steps: black plastic.
    cls[box(p, ax=(0.5, 1.35), y=(0.75, 1.95), z=(0.35, 1.45)) & (A > 0.02)] = "black_plastic"
    cls[box(p, ax=(0, 0.45), y=(1.5, 2.35), z=(1.0, 1.95))] = "black_plastic"

    # Hood: top and side panels between cab and nose.
    hood = box(p, ax=(0, 0.5), y=(0.45, 2.25), z=(1.05, 2.05)) & (A > 0.03) & (lo[:, 1] < 1.55)
    cls[hood] = "fendt_green"

    # Rear fenders: large panels over the rear wheels.
    fender = box(p, ax=(0.45, 1.2), y=(-1.95, 0.0), z=(1.2, 2.0)) & (A > 0.05)
    cls[fender] = "fendt_green"

    # Cab pillars: long, slim, vertical pieces inside the cab box.
    pillar = cab & (ext[:, 2] > 0.8) & (np.maximum(ext[:, 0], ext[:, 1]) < 0.2) & (A > 0.02)
    cls[pillar] = "fendt_green"

    # Roof.
    cls[cab & (lo[:, 2] > 2.62) & (A > 0.02)] = "roof_white"

    # Windows: large, flat, thin sheets in the cab.
    glass = cab & (flat > 0.9) & (A > 0.15) & (thin < 0.2) & (hi[:, 2] < 2.9) & (ext[:, 2] > 0.3)
    cls[glass] = "glass"

    # Small shiny bits: bolts etc. stay dark grey; tiny pieces on the nose are lights.
    lights = box(p, ax=(0.1, 0.5), y=(1.9, 2.4), z=(1.1, 1.8)) & (A < 0.02) & (flat > 0.8)
    cls[lights] = "light_lens"
    return cls


def classify_rig(p):
    cls = np.full(p.n, "aluminium", dtype=object)
    # Compact, chunky pieces (camera/lidar housings) are black; profiles are long.
    compact = p.ext.max(1) < 3.0 * np.maximum(p.ext.min(1), 1e-6)
    cls[compact & (p.ext.max(1) > 0.03) & (p.ext.max(1) < 0.2)] = "black_plastic"
    return cls


def assign(obj, cls_per_piece, pieces, mats):
    me = obj.data
    me.materials.clear()
    names = list(PALETTE)
    for name in names:
        me.materials.append(mats[name])
    idx = np.array([names.index(c) for c in cls_per_piece])
    me.polygons.foreach_set("material_index", idx[pieces.faces])
    me.update()
    counts = {c: float(pieces.area[cls_per_piece == c].sum()) for c in set(cls_per_piece)}
    summary = ", ".join(f"{k} {v:.1f}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
    print(f"[paint] {obj.name}: {pieces.n} pieces | area m² {summary}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--work", default="texture_work")
    p.add_argument("--preview", action="store_true")
    args = p.parse_args(script_args())
    work = os.path.abspath(args.work)

    bpy.ops.wm.open_mainfile(filepath=os.path.join(work, "assembly.blend"))
    mats = palette_materials()
    objs = list(bpy.data.collections["originals"].objects)
    for obj in objs:
        pieces = Pieces(obj)
        if "wheel" in obj.name:
            cls = classify_wheel(pieces, obj)
        elif obj.name == "sensorrig":
            cls = classify_rig(pieces)
        else:
            cls = classify_body(pieces)
        assign(obj, cls, pieces, mats)

    out = os.path.join(work, "paint.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print(f"[paint] wrote {out}")
    if args.preview:
        for path in render_views(objs, os.path.join(work, "paint"),
                                 views=("front_left", "rear_right")):
            print(f"[paint] wrote {path}")


main()
