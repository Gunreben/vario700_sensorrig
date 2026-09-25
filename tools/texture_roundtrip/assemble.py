"""Step 1: assemble all URDF mesh visuals into one model for AI texturing.

Usage:
  blender -b -P tools/texture_roundtrip/assemble.py -- \
      --urdf urdf/vario700_sensorrig_manual.urdf [--out texture_work] \
      [--decimate 0.5] [--preview]

Writes to --out:
  assembly.blend   original meshes placed in the base frame (used by bake_back.py)
  upload.glb       the combined model to upload to the texturing tool
  preview.png      (with --preview) a quick render to check the placement
"""

import argparse
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blender_io import render_views, script_args, select_only  # noqa: E402
from urdf_tree import mesh_visuals  # noqa: E402


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--urdf", required=True)
    p.add_argument("--package-dir", default=None,
                   help="package root for package:// URIs (default: parent of the urdf/ dir)")
    p.add_argument("--out", default="texture_work")
    p.add_argument("--decimate", type=float, default=1.0,
                   help="face ratio for the upload copy only (1.0 = full resolution)")
    p.add_argument("--preview", action="store_true")
    return p.parse_args(script_args())


def import_mesh(path):
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    # Keep raw file coordinates: URDF consumers do not re-orient OBJ/STL axes.
    if ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path, forward_axis="Y", up_axis="Z")
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=path, forward_axis="Y", up_axis="Z")
    else:
        raise RuntimeError(f"unsupported mesh format: {path}")
    new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    if len(new) > 1:
        select_only(new, new[0])
        bpy.ops.object.join()
    return new[0]



def main():
    args = parse_args()
    urdf = os.path.abspath(args.urdf)
    package_dir = args.package_dir or os.path.dirname(os.path.dirname(urdf))
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    originals = bpy.data.collections.new("originals")
    bpy.context.scene.collection.children.link(originals)

    objs = []
    for vis in mesh_visuals(urdf, package_dir):
        if not os.path.exists(vis.mesh_path):
            print(f"[assemble] skipping {vis.name}: {vis.mesh_path} not found")
            continue
        obj = import_mesh(vis.mesh_path)
        for c in obj.users_collection:
            c.objects.unlink(obj)
        originals.objects.link(obj)
        obj.name = obj.data.name = vis.name
        # Mesh data stays in raw file coordinates; placement lives in the object transform.
        obj.matrix_world = vis.matrix
        obj["urdf_link"] = vis.link
        obj["mesh_uri"] = vis.mesh_uri
        obj["mesh_path"] = vis.mesh_path
        objs.append(obj)
        print(f"[assemble] {vis.name:20s} {len(obj.data.polygons):7d} faces  <- {vis.mesh_uri}")

    bpy.context.scene["urdf_path"] = urdf
    bpy.context.scene["package_dir"] = package_dir
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "assembly.blend"))

    # Upload copy: optionally decimated, exported without touching the saved originals.
    bpy.ops.object.select_all(action="DESELECT")
    copies = []
    for obj in objs:
        c = obj.copy()
        c.data = obj.data.copy()
        bpy.context.scene.collection.objects.link(c)
        if args.decimate < 1.0:
            mod = c.modifiers.new("decimate", "DECIMATE")
            mod.ratio = args.decimate
        c.select_set(True)
        copies.append(c)
    bpy.context.view_layer.objects.active = copies[0]
    glb = os.path.join(out, "upload.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True,
                              export_apply=True, export_materials="NONE")
    faces = sum(len(c.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.polygons)
                for c in copies)
    print(f"[assemble] wrote {glb} ({os.path.getsize(glb) / 1e6:.1f} MB, ~{faces} faces)")
    for c in copies:
        bpy.data.objects.remove(c)

    if args.preview:
        path, = render_views(objs, os.path.join(out, "preview"), color_type="RANDOM")
        print(f"[assemble] wrote {path}")


main()
