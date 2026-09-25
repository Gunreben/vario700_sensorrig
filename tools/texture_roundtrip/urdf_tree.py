"""Resolve URDF mesh visuals to their pose in the base frame.

Only uses the stdlib and Blender's bundled ``mathutils``, so it can be
imported from scripts run with ``blender -b -P``.
"""

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from mathutils import Euler, Matrix, Vector


@dataclass
class MeshVisual:
    link: str
    name: str                 # unique object name, e.g. "base_link" or "base_link_1"
    mesh_path: str            # absolute path to the mesh file
    mesh_uri: str             # filename attribute as written in the URDF
    scale: Vector
    matrix: Matrix            # base frame <- raw mesh coordinates (incl. scale)


def _origin_matrix(elem):
    origin = elem.find("origin") if elem is not None else None
    xyz = [0.0, 0.0, 0.0]
    rpy = [0.0, 0.0, 0.0]
    if origin is not None:
        xyz = [float(v) for v in origin.get("xyz", "0 0 0").split()]
        rpy = [float(v) for v in origin.get("rpy", "0 0 0").split()]
    # URDF rpy is fixed-axis X, then Y, then Z == Blender Euler 'XYZ'.
    return Matrix.Translation(Vector(xyz)) @ Euler(rpy, "XYZ").to_matrix().to_4x4()


def resolve_uri(uri, package_dir):
    if uri.startswith("package://"):
        # package://<pkg>/<rel> -> assume <pkg> is the package this URDF lives in.
        rel = uri[len("package://"):].split("/", 1)[1]
        return os.path.join(package_dir, rel)
    if uri.startswith("file://"):
        return uri[len("file://"):]
    return uri


def mesh_visuals(urdf_path, package_dir):
    root = ET.parse(urdf_path).getroot()

    parent_of = {}
    for joint in root.findall("joint"):
        child = joint.find("child").get("link")
        parent = joint.find("parent").get("link")
        parent_of[child] = (parent, _origin_matrix(joint))

    cache = {}

    def link_matrix(link):
        if link not in cache:
            if link in parent_of:
                parent, m = parent_of[link]
                cache[link] = link_matrix(parent) @ m
            else:
                cache[link] = Matrix.Identity(4)
        return cache[link]

    result = []
    for link in root.findall("link"):
        lname = link.get("name")
        visuals = [v for v in link.findall("visual") if v.find("geometry/mesh") is not None]
        for i, visual in enumerate(visuals):
            mesh = visual.find("geometry/mesh")
            uri = mesh.get("filename")
            scale = Vector([float(v) for v in mesh.get("scale", "1 1 1").split()])
            m_scale = Matrix.Diagonal((*scale, 1.0))
            result.append(MeshVisual(
                link=lname,
                name=lname if len(visuals) == 1 else f"{lname}_{i}",
                mesh_path=resolve_uri(uri, package_dir),
                mesh_uri=uri,
                scale=scale,
                matrix=link_matrix(lname) @ _origin_matrix(visual) @ m_scale,
            ))
    return result
