"""Export the painted links (texture_work/paint.blend) as multi-material OBJs.

Usage:
  blender -b -P tools/texture_roundtrip/paint_export.py -- \
      [--work texture_work] [--out-dir meshes/painted] [--urdf urdf/*.urdf] [--preview]

Writes per link <out-dir>/<name>_visuals.obj + .mtl (plain colours, no
textures, raw file coordinates) and a URDF copy whose <visual> meshes point
at them. Materials you add in Blender that are not in the palette are
exported with their viewport colour.
"""

import argparse
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blender_io import export_obj, render_views, script_args, urdf_uri, write_urdf  # noqa: E402

MTL_TEMPLATE = """newmtl {name}
Kd {r:.4f} {g:.4f} {b:.4f}
Ka {r:.4f} {g:.4f} {b:.4f}
Ks {s:.3f} {s:.3f} {s:.3f}
Ns {ns:.1f}
d 1.000000
illum 2

"""


def linear_to_srgb(c):
    return tuple(12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055 for x in c)


def write_mtl(path, materials):
    """Plain sRGB colours: Blender writes linear values, which look too dark in RViz."""
    with open(path, "w") as f:
        f.write("# painted flat colours (sRGB)\n\n")
        for mat in materials:
            bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.use_nodes else None
            if bsdf:
                lin = bsdf.inputs["Base Color"].default_value[:3]
                rough = bsdf.inputs["Roughness"].default_value
            else:
                lin, rough = mat.diffuse_color[:3], 0.5
            r, g, b = linear_to_srgb(lin)
            f.write(MTL_TEMPLATE.format(name=mat.name, r=r, g=g, b=b,
                                        s=0.5 * (1 - rough) ** 2, ns=2 + 200 * (1 - rough) ** 2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--work", default="texture_work")
    p.add_argument("--out-dir", default=None, help="default: <package>/meshes/painted")
    p.add_argument("--urdf", nargs="*", default=None,
                   help="URDFs to write a <name>_painted.urdf copy of "
                        "(default: the one given to assemble.py; none with an empty list)")
    p.add_argument("--preview", action="store_true")
    args = p.parse_args(script_args())
    work = os.path.abspath(args.work)

    bpy.ops.wm.open_mainfile(filepath=os.path.join(work, "paint.blend"))
    scene = bpy.context.scene
    urdf, package_dir = scene["urdf_path"], scene["package_dir"]
    out_dir = os.path.abspath(args.out_dir or os.path.join(package_dir, "meshes", "painted"))
    os.makedirs(out_dir, exist_ok=True)

    objs = list(bpy.data.collections["originals"].objects)
    new_uri = {}
    for obj in objs:
        path = os.path.join(out_dir, f"{obj.name}_visuals.obj")
        export_obj(obj, path)
        used = sorted({poly.material_index for poly in obj.data.polygons})
        write_mtl(path[:-4] + ".mtl", [obj.data.materials[i] for i in used])
        new_uri[obj["mesh_uri"]] = urdf_uri(obj["mesh_uri"], path, package_dir)
        print(f"[export] {path} ({len(used)} materials)")

    for urdf_in in ([urdf] if args.urdf is None else [os.path.abspath(u) for u in args.urdf]):
        urdf_out = urdf_in.replace(".urdf", "_painted.urdf")
        write_urdf(urdf_in, urdf_out, new_uri)
        print(f"[export] {urdf_out}")

    if args.preview:
        for path in render_views(objs, os.path.join(work, "painted"),
                                 views=("front_left", "rear_right")):
            print(f"[export] {path}")


main()
