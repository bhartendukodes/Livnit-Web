"""Subprocess-based Blender rendering for macOS compatibility.

On macOS, Blender's Cocoa/AppKit must run on the main thread. This module
provides a subprocess wrapper that avoids the threading issue by running
Blender as a separate process.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


BLENDER_SCRIPT = '''"""Standalone Blender script for LayoutVLM scene rendering.

Called via subprocess: blender -b -P script.py -- --input task.json --output result.json
"""
import sys
import argparse
import json
import os
import math
import numpy as np

import bpy
from mathutils import Vector


def reset_blender():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for collection in bpy.data.collections:
        bpy.data.collections.remove(collection)
    if "Collection" not in bpy.data.collections:
        bpy.ops.collection.create(name="Collection")
        bpy.context.scene.collection.children.link(bpy.data.collections["Collection"])
    bpy.ops.outliner.orphans_purge(do_recursive=True)


def setup_background():
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    nodes.clear()
    output_node = nodes.new(type='ShaderNodeOutputWorld')
    output_node.location = (200, 0)
    background_node = nodes.new(type='ShaderNodeBackground')
    background_node.location = (0, 0)
    background_node.inputs['Color'].default_value = (1, 1, 1, 1)
    background_node.inputs['Strength'].default_value = 1.0
    world.node_tree.links.new(background_node.outputs['Background'], output_node.inputs['Surface'])


def create_wall_mesh(name, vertices, height=3.0):
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    import bmesh
    bm = bmesh.new()
    verts = [bm.verts.new((v[0], v[1], 0)) for v in vertices]
    bmesh.ops.contextual_create(bm, geom=verts)
    bm.to_mesh(mesh)
    bm.free()
    return obj


def setup_camera(center_x, center_y, floor_width, wall_height, fov_multiplier=1.1):
    cam_data = bpy.data.cameras.new(name='Camera')
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = floor_width * fov_multiplier
    cam = bpy.data.objects.new('Camera', cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (center_x, center_y, max(wall_height * 2, 10))
    cam.rotation_euler = (0, 0, 0)
    bpy.context.scene.camera = cam
    return cam


def load_hdri():
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
    sun = bpy.context.active_object
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(45), 0, math.radians(45))


def set_rendering_settings(high_res=False):
    scene = bpy.context.scene
    engines = ['BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE', 'CYCLES']
    for eng in engines:
        try:
            scene.render.engine = eng
            break
        except:
            continue

    res = 1024 if high_res else 512
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'


def get_pixel_coordinates(scene, cam, world_coord):
    if isinstance(world_coord, (list, tuple)):
        world_coord = Vector(world_coord)

    from bpy_extras.object_utils import world_to_camera_view
    co = world_to_camera_view(scene, cam, world_coord)
    render = scene.render
    return int(co.x * render.resolution_x), int((1 - co.y) * render.resolution_y)


def get_visual_marks(floor_vertices, scene, cam, interval=1):
    visual_marks = {}
    min_v = np.min(floor_vertices, axis=0)
    max_v = np.max(floor_vertices, axis=0)
    for x in range(int(math.floor(min_v[0])), int(math.ceil(max_v[0])) + 2, interval):
        for y in range(int(math.floor(min_v[1])), int(math.ceil(max_v[1])) + 2, interval):
            world_coord = Vector((x, y, 0))
            px, py = get_pixel_coordinates(scene, cam, world_coord)
            visual_marks[f"{x},{y}"] = [px, py]
    return visual_marks


def get_obj_dimensions(obj):
    if obj.type != 'MESH':
        return [1.0, 1.0, 1.0]
    bbox = [Vector(corner) for corner in obj.bound_box]
    min_x = min(c.x for c in bbox)
    max_x = max(c.x for c in bbox)
    min_y = min(c.y for c in bbox)
    max_y = max(c.y for c in bbox)
    min_z = min(c.z for c in bbox)
    max_z = max(c.z for c in bbox)
    return [max_x - min_x, max_y - min_y, max_z - min_z]


def render_scene(task_data, save_dir, params):
    reset_blender()
    setup_background()

    placed_assets = task_data.get("placed_assets", {})
    task = task_data.get("task", {})

    floor_vertices = np.array(task["boundary"]["floor_vertices"])
    floor_x = [p[0] for p in floor_vertices]
    floor_y = [p[1] for p in floor_vertices]
    floor_center_x = (max(floor_x) + min(floor_x)) / 2
    floor_center_y = (max(floor_y) + min(floor_y)) / 2
    floor_width = max(max(floor_x) - min(floor_x), max(floor_y) - min(floor_y))
    wall_height = task["boundary"].get("wall_height", 3)

    # Create floor
    floor_obj = create_wall_mesh("floor", floor_vertices)

    # Import and place assets
    asset_dict = {}
    asset_count = 0

    for instance_id, asset in task.get("assets", {}).items():
        if instance_id not in placed_assets:
            continue

        file_path = asset.get("path", "")
        if not file_path or not os.path.exists(file_path):
            continue

        try:
            if file_path.endswith(('.gltf', '.glb')):
                bpy.ops.import_scene.gltf(filepath=file_path)
            elif file_path.endswith('.obj'):
                bpy.ops.wm.obj_import(filepath=file_path)
            else:
                continue
        except Exception as e:
            print(f"Failed to import {file_path}: {e}")
            continue

        loaded = bpy.context.view_layer.objects.active
        if not loaded:
            continue

        bpy.ops.object.select_all(action='DESELECT')
        loaded.select_set(True)

        if params.get("recenter_mesh", True):
            bpy.ops.object.origin_set(type='GEOMETRY_ORIGIN', center='BOUNDS')

        if params.get("rotate_90", True):
            bpy.ops.transform.rotate(value=-math.radians(90), orient_axis='Z')

        bpy.context.object.rotation_mode = "XYZ"

        placement = placed_assets[instance_id]
        if "scale" in placement:
            loaded.scale = placement["scale"]

        rotation = placement.get("rotation", [0, 0, 0])
        if isinstance(rotation, (int, float)):
            loaded.rotation_euler[-1] += math.radians(rotation)
        else:
            for i in range(min(3, len(rotation))):
                loaded.rotation_euler[i] += math.radians(rotation[i])

        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        position = placement.get("position", [0, 0, 0])
        if len(position) == 2:
            bbox = asset.get("assetMetadata", {}).get("boundingBox", {})
            z = placement.get("scale", 1.0) * bbox.get("z", 1.0) / 2
            position = [position[0], position[1], z]
        loaded.location = position

        if params.get("annotate_object", True):
            asset_name = f"{asset.get('asset_var_name', 'asset')}[{asset.get('instance_idx', 0)}]"
            asset_dict[asset_count] = {
                "position": list(position),
                "rotation": list(loaded.rotation_euler) if hasattr(loaded.rotation_euler, '__iter__') else [0, 0, rotation[-1] if isinstance(rotation, list) else rotation],
                "size": get_obj_dimensions(loaded),
                "name": asset_name,
                "category": asset.get("category", "")
            }
            asset_count += 1

    # Setup lighting
    if params.get("add_hdri", True):
        load_hdri()

    output_images = []
    visual_marks = {}

    set_rendering_settings(high_res=params.get("high_res", False))

    # Render top-down view
    if params.get("render_top_down", True):
        cam = setup_camera(floor_center_x, floor_center_y, floor_width, wall_height,
                          fov_multiplier=params.get("fov_multiplier", 1.1))

        render_path = os.path.join(save_dir, "top_down_rendering.png")
        bpy.context.scene.render.filepath = render_path
        bpy.ops.render.render(write_still=True)
        output_images.append(render_path)

        if params.get("add_coordinate_mark", True):
            visual_marks = get_visual_marks(floor_vertices, bpy.context.scene, cam, interval=2)

    # Render side views
    side_view_indices = params.get("side_view_indices", [3])
    side_view_phi = params.get("side_view_phi", 45)

    cam = setup_camera(floor_center_x, floor_center_y, floor_width, wall_height,
                      fov_multiplier=params.get("fov_multiplier", 1.1))
    original_z = cam.location.z

    for idx in side_view_indices:
        theta = (idx / 4) * math.pi * 2
        phi = math.radians(side_view_phi)
        cam.location = (
            floor_center_x + original_z * math.sin(phi) * math.cos(theta),
            floor_center_y + original_z * math.sin(phi) * math.sin(theta),
            original_z * math.cos(phi),
        )

        render_path = os.path.join(save_dir, f"side_rendering_{side_view_phi}_{idx}.png")
        bpy.context.scene.render.filepath = render_path
        bpy.ops.render.render(write_still=True)
        output_images.append(render_path)

    return {
        "output_images": output_images,
        "visual_marks": visual_marks,
        "asset_dict": asset_dict
    }


def main():
    argv = sys.argv
    if "--" not in argv:
        print("ERROR: No arguments passed after '--'")
        sys.exit(1)

    args = argv[argv.index("--") + 1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input JSON file with task data")
    parser.add_argument("--output", required=True, help="Output JSON file for results")
    opt = parser.parse_args(args)

    with open(opt.input, 'r') as f:
        input_data = json.load(f)

    task_data = input_data.get("task_data", {})
    save_dir = input_data.get("save_dir", "/tmp")
    params = input_data.get("params", {})

    os.makedirs(save_dir, exist_ok=True)

    try:
        result = render_scene(task_data, save_dir, params)
        result["success"] = True
    except Exception as e:
        import traceback
        result = {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

    with open(opt.output, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Render complete. Results saved to {opt.output}")


if __name__ == "__main__":
    main()
'''


def _get_blender_bin() -> str:
    if path := os.environ.get("BLENDER_PATH"):
        return path

    if shutil.which("blender"):
        return "blender"

    mac_paths = [
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/Applications/Blender 4.2.app/Contents/MacOS/Blender",
        "/Applications/Blender 4.1.app/Contents/MacOS/Blender",
    ]
    for p in mac_paths:
        if Path(p).exists():
            return p

    raise RuntimeError("Blender not found. Set BLENDER_PATH environment variable.")


def render_existing_scene_subprocess(
    placed_assets: dict,
    task: dict,
    save_dir: str,
    add_hdri: bool = True,
    add_coordinate_mark: bool = True,
    annotate_object: bool = True,
    annotate_wall: bool = True,
    render_top_down: bool = True,
    high_res: bool = False,
    rotate_90: bool = True,
    recenter_mesh: bool = True,
    fov_multiplier: float = 1.1,
    side_view_phi: int = 45,
    side_view_indices: list = None,
    **kwargs,
) -> tuple[list, dict]:
    """Render scene via Blender subprocess. Returns (output_images, visual_marks)."""
    if side_view_indices is None:
        side_view_indices = [3]

    blender_bin = _get_blender_bin()
    os.makedirs(save_dir, exist_ok=True)

    # Prepare input data
    input_data = {
        "task_data": {
            "placed_assets": placed_assets,
            "task": task,
        },
        "save_dir": save_dir,
        "params": {
            "add_hdri": add_hdri,
            "add_coordinate_mark": add_coordinate_mark,
            "annotate_object": annotate_object,
            "annotate_wall": annotate_wall,
            "render_top_down": render_top_down,
            "high_res": high_res,
            "rotate_90": rotate_90,
            "recenter_mesh": recenter_mesh,
            "fov_multiplier": fov_multiplier,
            "side_view_phi": side_view_phi,
            "side_view_indices": side_view_indices,
        },
    }

    # Write input to temp file
    input_file = os.path.join(save_dir, "_render_input.json")
    output_file = os.path.join(save_dir, "_render_output.json")

    with open(input_file, 'w') as f:
        json.dump(input_data, f)

    # Write blender script to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as script_file:
        script_file.write(BLENDER_SCRIPT)
        script_path = script_file.name

    try:
        cmd = [
            blender_bin, "-b",
            "-P", script_path,
            "--",
            "--input", input_file,
            "--output", output_file,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            print(f"Blender stderr: {result.stderr[-2000:]}")
            raise RuntimeError(f"Blender render failed: {result.stderr[-500:]}")

        if not os.path.exists(output_file):
            raise RuntimeError(f"Render output not found: {output_file}")

        with open(output_file) as f:
            output_data = json.load(f)

        if not output_data.get("success"):
            raise RuntimeError(f"Render failed: {output_data.get('error', 'unknown')}")

        # Convert string keys back to tuples: "x,y" -> (x, y)
        visual_marks_raw = output_data.get("visual_marks", {})
        visual_marks = {tuple(map(int, k.split(","))): v for k, v in visual_marks_raw.items()}

        return output_data.get("output_images", []), visual_marks
    finally:
        # Clean up temp files
        os.unlink(script_path)
        for f in [input_file, output_file]:
            if os.path.exists(f):
                os.remove(f)


def should_use_subprocess() -> bool:
    """Check if we should use subprocess rendering (bpy unavailable or macOS threading)."""
    try:
        import bpy  # noqa: F401
        return sys.platform == "darwin"  # Only use subprocess on macOS when bpy is available
    except ImportError:
        return True  # bpy not available in this Python, must use subprocess
