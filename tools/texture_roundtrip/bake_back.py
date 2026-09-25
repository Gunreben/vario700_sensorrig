"""Step 2: bake the AI-textured model back onto the original per-link meshes.

Usage:
  blender -b -P tools/texture_roundtrip/bake_back.py -- \
      --textured ~/Downloads/textured.glb [--work texture_work] \
      [--out-dir meshes/textured] [--res 4096] [--align bbox|none] [--preview]

The textured model may be remeshed, recentred or rescaled by the tool: the
colour is transferred by ray casting (Cycles "selected to active" bake), so
the original geometry, vertex positions and link frames are kept exactly.

Writes, per URDF mesh visual:
  <out-dir>/<name>_visuals.obj / .mtl   original geometry in raw file coordinates + UVs
  <out-dir>/<name>_albedo.png           baked colour
and a copy of the URDF whose <visual> meshes point at the textured files
(<collision> meshes are left untouched).
"""

import argparse
import os
import sys

import bpy
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blender_io import (export_obj, render_views, script_args, select_only,  # noqa: E402
                        urdf_uri, world_bbox, write_urdf)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--textured", required=True, help="GLB/FBX/OBJ returned by the AI tool")
    p.add_argument("--work", default="texture_work", help="--out dir used by assemble.py")
    p.add_argument("--out-dir", default=None,
                   help="where to write textured meshes (default: <package>/meshes/textured)")
    p.add_argument("--urdf-out", default=None,
                   help="textured URDF copy (default: <urdf>_textured.urdf, 'none' to skip)")
    p.add_argument("--res", type=int, default=0,
                   help="texture size for every link (default: 4096 for parts > 4 m, else 2048)")
    p.add_argument("--align", choices=["bbox", "none"], default="bbox",
                   help="fit the textured model's bounding box onto the originals")
    p.add_argument("--cage", type=float, default=0.02, help="cage extrusion in metres")
    p.add_argument("--max-dist", type=float, default=0.1, help="max ray distance in metres")
    p.add_argument("--samples", type=int, default=4)
    p.add_argument("--cpu", action="store_true", help="bake on CPU instead of GPU")
    p.add_argument("--preview", action="store_true")
    return p.parse_args(script_args())






def import_textured(path):
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    else:
        raise RuntimeError(f"unsupported format: {path}")
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"no meshes in {path}")
    # Join into one world-space source object for the bake.
    select_only(meshes, meshes[0])
    if len(meshes) > 1:
        bpy.ops.object.join()
    src = bpy.context.view_layer.objects.active
    src.parent = None
    src.matrix_world = src.matrix_world  # keep world pose after unparenting
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for o in new:
        if o != src and o.name in bpy.data.objects:
            bpy.data.objects.remove(o)
    src.name = "ai_textured"
    return src


def align_bbox(src, targets):
    lo_t, hi_t = world_bbox(targets)
    lo_s, hi_s = world_bbox([src])
    ext_t, ext_s = hi_t - lo_t, hi_s - lo_s
    ratios = [ext_t[i] / ext_s[i] if ext_s[i] > 1e-9 else 0.0 for i in range(3)]
    s = sum(ratios) / 3
    print(f"[bake] bbox extent ratio x/y/z = {ratios[0]:.3f} / {ratios[1]:.3f} / {ratios[2]:.3f}")
    if max(ratios) - min(ratios) > 0.05 * s:
        print("[bake] WARNING: non-uniform ratio -> the tool probably rotated/swapped axes. "
              "Fix the pose of 'ai_textured' in bake_scene.blend and rerun with --align none "
              "on that result, or check the axis settings.")
    m = (Matrix.Translation((lo_t + hi_t) / 2) @ Matrix.Scale(s, 4)
         @ Matrix.Translation(-(lo_s + hi_s) / 2))
    src.data.transform(m)
    src.data.update()


def setup_cycles(args):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = args.samples
    scene.cycles.device = "CPU"
    if not args.cpu:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
            try:
                prefs.compute_device_type = backend
            except TypeError:
                continue
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == backend]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == backend
                scene.cycles.device = "GPU"
                print(f"[bake] using {backend}: {', '.join(d.name for d in gpus)}")
                break
    bake = scene.render.bake
    bake.use_selected_to_active = True
    bake.cage_extrusion = args.cage
    bake.max_ray_distance = args.max_dist
    bake.margin = 16
    bake.use_clear = False
    bake.use_pass_direct = False
    bake.use_pass_indirect = False
    bake.use_pass_color = True


def unwrap(obj):
    select_only([obj], obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.002)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_target(obj, src, res, png_path):
    img = bpy.data.images.new(f"{obj.name}_albedo", res, res)
    img.generated_color = (0.5, 0.5, 0.5, 1.0)  # shows where no colour was found
    mat = bpy.data.materials.new(f"{obj.name}_mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = img
    nodes.active = tex
    obj.data.materials.clear()
    obj.data.materials.append(mat)

    select_only([src, obj], obj)
    bpy.ops.object.bake(type="DIFFUSE")

    img.filepath_raw = png_path
    img.file_format = "PNG"
    img.save()
    img.filepath = png_path
    bsdf = nodes.get("Principled BSDF")
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8








def main():
    args = parse_args()
    work = os.path.abspath(args.work)
    bpy.ops.wm.open_mainfile(filepath=os.path.join(work, "assembly.blend"))
    scene = bpy.context.scene
    urdf, package_dir = scene["urdf_path"], scene["package_dir"]
    out_dir = os.path.abspath(args.out_dir or os.path.join(package_dir, "meshes", "textured"))
    os.makedirs(out_dir, exist_ok=True)

    targets = list(bpy.data.collections["originals"].objects)
    # Bake in metres: move each mesh into the base frame, remember how to undo it.
    raw_from_world = {}
    for obj in targets:
        m = obj.matrix_world.copy()
        obj.data.transform(m)
        obj.matrix_world = Matrix.Identity(4)
        raw_from_world[obj.name] = m.inverted()

    src = import_textured(os.path.abspath(os.path.expanduser(args.textured)))
    if args.align == "bbox":
        align_bbox(src, targets)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(work, "bake_scene.blend"))

    setup_cycles(args)
    new_uri = {}
    for obj in targets:
        lo, hi = world_bbox([obj])
        res = args.res or (4096 if (hi - lo).length > 4.0 else 2048)
        print(f"[bake] {obj.name}: unwrap + bake {res}x{res}")
        unwrap(obj)
        png = os.path.join(out_dir, f"{obj.name}_albedo.png")
        bake_target(obj, src, res, png)

        # Back to raw file coordinates so the URDF scale/origins stay valid.
        obj.data.transform(raw_from_world[obj.name])
        obj_path = os.path.join(out_dir, f"{obj.name}_visuals.obj")
        export_obj(obj, obj_path)
        obj.data.transform(raw_from_world[obj.name].inverted())
        new_uri[obj["mesh_uri"]] = urdf_uri(obj["mesh_uri"], obj_path, package_dir)
        print(f"[bake] wrote {obj_path}")

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(work, "bake_result.blend"))

    if args.urdf_out != "none":
        urdf_out = args.urdf_out or urdf.replace(".urdf", "_textured.urdf")
        write_urdf(urdf, urdf_out, new_uri)
        print(f"[bake] wrote {urdf_out}")

    if args.preview:
        src.hide_render = True
        path, = render_views(targets, os.path.join(work, "textured_preview"), color_type="TEXTURE")
        print(f"[bake] wrote {path}")


main()
