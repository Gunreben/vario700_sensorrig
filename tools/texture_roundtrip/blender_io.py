"""Blender helpers shared by the texture/paint scripts."""

import os
import re

import bpy
from mathutils import Vector


def script_args():
    import sys
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def select_only(objs, active):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


def world_bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def export_obj(obj, path):
    """Export one object in raw mesh coordinates (its object transform is ignored)."""
    saved = obj.matrix_world.copy()
    obj.matrix_world.identity()
    select_only([obj], obj)
    bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True,
                          forward_axis="Y", up_axis="Z",
                          export_uv=True, export_normals=True, export_materials=True,
                          path_mode="STRIP", apply_modifiers=False)
    obj.matrix_world = saved


def urdf_uri(old_uri, new_path, package_dir):
    rel = os.path.relpath(new_path, package_dir)
    if old_uri.startswith("package://") and not rel.startswith(".."):
        pkg = old_uri[len("package://"):].split("/", 1)[0]
        return f"package://{pkg}/{rel}"
    return f"file://{new_path}"


def write_urdf(urdf_in, urdf_out, new_uri):
    """Copy the URDF, pointing <visual> meshes at new files (collisions untouched)."""
    text = open(urdf_in).read()

    def fix_visual(m):
        block = m.group(0)
        for old, new in new_uri.items():
            block = block.replace(f'filename="{old}"', f'filename="{new}"')
        return block

    text = re.sub(r"<visual\b.*?</visual>", fix_visual, text, flags=re.S)
    with open(urdf_out, "w") as f:
        f.write(text)


# Camera directions from the model centre (base frame: x right, y forward, z up).
VIEWS = {
    "rear_right": (1.0, -1.2, 0.7),
    "front_left": (-1.0, 0.9, 0.35),
    "front_right": (1.0, 0.9, 0.35),
    "rear_left": (-1.0, -1.2, 0.5),
}


def render_views(objs, path_prefix, views=("rear_right",), color_type="MATERIAL",
                 resolution=(1600, 1000)):
    """Workbench renders of objs; writes <path_prefix>_<view>.png per view."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.color_type = color_type
    scene.display.shading.light = "STUDIO"
    scene.render.resolution_x, scene.render.resolution_y = resolution
    lo, hi = world_bbox(objs)
    center, radius = (lo + hi) / 2, (hi - lo).length / 2
    cam = bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam"))
    scene.collection.objects.link(cam)
    cam.data.lens = 35
    scene.camera = cam
    paths = []
    for view in views:
        cam.location = center + Vector(VIEWS[view]).normalized() * radius * 2.4
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = f"{path_prefix}_{view}.png" if len(views) > 1 else f"{path_prefix}.png"
        bpy.ops.render.render(write_still=True)
        paths.append(scene.render.filepath)
    bpy.data.objects.remove(cam)
    return paths
