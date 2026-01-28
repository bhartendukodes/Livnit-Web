"""Self-contained scene rendering node using Blender.

Coordinate conventions (consistent with all pipeline nodes):
- Origin: (0,0) at bottom-left of room
- X axis: rightward (+)
- Y axis: upward (+)
- Z axis: height above floor
- Rotation: radians, 0=facing -Y, π/2=+X, π=+Y, 3π/2=-X
- Anchor: center of bounding box
"""
import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from pipeline.core.asset_manager import AssetManager
from pipeline.core.pipeline_shared import STAGE_DIRS, log_duration

logger = logging.getLogger(__name__)

BLENDER_SCRIPT = '''
import argparse
import json
import math
import os
import re
import sys

import bpy
import numpy as np
from mathutils import Vector, Euler


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for c in bpy.data.collections:
        if c.name != "Collection":
            bpy.data.collections.remove(c)


def import_glb(path, name):
    bpy.ops.import_scene.gltf(filepath=path)
    imported = list(bpy.context.selected_objects)
    if not imported:
        return None
    for obj in imported:
        if obj.type == "MESH":
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    for obj in imported:
        obj.parent = root
    return root


def place_asset(root, pos, rot, floor_z, offset_x, offset_y, center_x, center_y, rotation_y=0):
    """Place asset with pipeline rotation convention: 0=-Y, π/2=+X"""
    x, y, z = pos
    x, y = transform_point(x - center_x, y - center_y, rotation_y)
    root.location = (x + offset_x, y - offset_y, floor_z + max(pos[2] if len(pos) > 2 else 0, 0.02))
    # Combine layout rotation with front-view correction
    rot_z = (rot[2] if rot and len(rot) > 2 else 0) + rotation_y
    root.rotation_euler = Euler((rot[0] if rot else 0, rot[1] if len(rot) > 1 else 0, rot_z), "XYZ")


def lift_to_floor(root, floor_z):
    bpy.context.view_layer.update()
    min_z = float("inf")
    for obj in root.children_recursive:
        if obj.type == "MESH":
            for v in obj.data.vertices:
                min_z = min(min_z, (obj.matrix_world @ v.co).z)
    if min_z != float("inf") and min_z < floor_z:
        root.location.z += floor_z - min_z + 0.02


def get_scene_bounds():
    mins = Vector((float("inf"), float("inf"), float("inf")))
    maxs = Vector((-float("inf"), -float("inf"), -float("inf")))
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        for v in obj.data.vertices:
            p = obj.matrix_world @ v.co
            mins.x, mins.y, mins.z = min(mins.x, p.x), min(mins.y, p.y), min(mins.z, p.z)
            maxs.x, maxs.y, maxs.z = max(maxs.x, p.x), max(maxs.y, p.y), max(maxs.z, p.z)
    if any(math.isinf(v) for v in (*mins, *maxs)):
        mins, maxs = Vector((0, 0, 0)), Vector((5, 5, 3))
    return mins, maxs


def create_floor_material(color=(0.65, 0.45, 0.3), roughness=0.4):
    """Create simple colored floor material."""
    mat = bpy.data.materials.new("FloorMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat


def apply_room_textures(floor_config, _wall_config=None):
    """Apply floor texture by name or geometry detection."""
    if not floor_config:
        return
    floor_mat = create_floor_material(**floor_config)

    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        name = obj.name.lower()
        is_floor = any(x in name for x in ("floor", "ground", "base"))

        # Fallback: detect flat horizontal surfaces
        if not is_floor and obj.data.vertices:
            bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
            height = max(v.z for v in bbox) - min(v.z for v in bbox)
            width = max(max(v.x for v in bbox) - min(v.x for v in bbox),
                       max(v.y for v in bbox) - min(v.y for v in bbox))
            is_floor = height < 0.1 and width > 0.5

        if is_floor:
            obj.data.materials.clear()
            obj.data.materials.append(floor_mat)


def setup_lighting(center, max_z, use_eevee=False):
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    bpy.context.scene.collection.objects.link(sun)
    sun.data.energy = 3 if not use_eevee else 2
    sun.location = (center.x, center.y, max_z + 10)
    sun.rotation_euler = Euler((math.radians(45), 0, math.radians(45)), "XYZ")
    if not use_eevee:
        sun.data.use_shadow = True

    if not use_eevee:
        # Fill light only for CYCLES (EEVEE handles ambient differently)
        fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", "AREA"))
        bpy.context.scene.collection.objects.link(fill)
        fill.data.energy = 500
        fill.data.size = 5
        fill.location = (center.x - 5, center.y - 5, max_z + 3)


def setup_render(resolution=1024, samples=32, use_gpu=False, use_eevee=False):
    scene = bpy.context.scene

    if use_eevee:
        # EEVEE - fast rasterization, good for low-end hardware
        try:
            scene.render.engine = "BLENDER_EEVEE_NEXT"
        except:
            scene.render.engine = "BLENDER_EEVEE"
        scene.eevee.taa_render_samples = min(samples, 16)
        scene.eevee.use_gtao = True
        scene.eevee.use_ssr = False  # disable for speed
        scene.eevee.use_bloom = False
    else:
        # CYCLES - ray tracing
        scene.render.engine = "CYCLES"
        if use_gpu:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            prefs.compute_device_type = "METAL"
            prefs.get_devices()
            for dev in prefs.devices:
                dev.use = True
            scene.cycles.device = "GPU"
        else:
            scene.cycles.device = "CPU"
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = 0.1
        scene.cycles.max_bounces = 4 if samples > 16 else 2
        scene.cycles.diffuse_bounces = 2 if samples > 16 else 1
        scene.cycles.glossy_bounces = 2 if samples > 16 else 1
        scene.cycles.transmission_bounces = 2 if samples > 16 else 1
        scene.cycles.transparent_max_bounces = 2
        scene.cycles.volume_bounces = 0
        scene.render.use_persistent_data = True

    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.film_transparent = False
    scene.render.image_settings.compression = 50

    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    if bg := world.node_tree.nodes.get("Background"):
        bg.inputs[0].default_value = (0.9, 0.9, 0.9, 1.0)


def render_top_view(center, size, max_z, output_path):
    cam = bpy.data.objects.new("TopCam", bpy.data.cameras.new("TopCam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(size.x, size.y) * 1.2
    cam.location = (center.x, center.y, max_z + 5)
    cam.rotation_euler = Euler((0, 0, 0), "XYZ")
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = output_path
    bpy.ops.render.render(write_still=True)
    return output_path


def render_perspective_view(center, size, output_path):
    cam = bpy.data.objects.new("PerspCam", bpy.data.cameras.new("PerspCam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.data.type = "PERSP"
    cam.data.lens = 35
    dist = max(size.x, size.y, size.z) * 2
    cam.location = (center.x + dist * 0.7, center.y - dist * 0.7, center.z + dist * 0.5)
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = output_path
    bpy.ops.render.render(write_still=True)
    return output_path

def get_floor_info(floor_obj):
    loc = floor_obj.location
    cx = loc.x
    cy = loc.z
    cz = loc.y
    rot_y = floor_obj.rotation_euler.y
    return cz, (cx, cy), rot_y

def transform_point(x, y, radian):
    cos_theta = math.cos(radian)
    sin_theta = math.sin(radian)
    x_new = x * cos_theta - y * sin_theta
    y_new = x * sin_theta + y * cos_theta
    return x_new, y_new

def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    opts = parser.parse_args(argv)

    with open(opts.input) as f:
        data = json.load(f)

    clear_scene()
    bpy.context.scene.unit_settings.system = "METRIC"

    # Import room if provided
    floor_z = 0.0
    offset_x, offset_y = 0.0, 0.0
    rotation_y = 0.0
    room_area = data.get("room_area") or [5.0, 5.0]
    center_x = room_area[0] / 2
    center_y = room_area[1] / 2
    if data.get("room_usdz") and os.path.exists(data["room_usdz"]):
        bpy.ops.wm.usd_import(filepath=data["room_usdz"])
        for obj in bpy.data.objects:
            if obj.type == "MESH" and "floor" in obj.name.lower():
                floor_z, (offset_x, offset_y), rotation_y = get_floor_info(obj)
                break
        # Apply floor color (warm wood by default)
        floor_cfg = data.get("floor_texture")
        if floor_cfg is None:
            floor_cfg = {"color": [0.65, 0.45, 0.3], "roughness": 0.4}
        if floor_cfg:
            apply_room_textures(floor_cfg, None)

    # Use room area for offset if no floor found
    if offset_x == 0 and offset_y == 0:
        offset_x = room_area[0] / 2
        offset_y = room_area[1] / 2

    # Place assets
    layout = data.get("layout", {})
    assets_dir = data.get("assets_dir", "")
    selected_assets = data.get("selected_assets", {})

    for idx, (uid, props) in enumerate(layout.items(), 1):
        if uid.startswith("void"):
            continue
            
        # Derive folder and base names from UID
        # e.g., accent_chair_14_1 -> folder=accent_chair_14, base=accent_chair
        match = re.match(r"^(.+_\d+)_\d+$", uid)
        folder_name = match.group(1) if match else uid
        base = re.sub(r"_\d+$", "", folder_name)
        
        # Find GLB file in asset directory
        glb_path = os.path.join(assets_dir, folder_name, f"{base}.glb")
        if not os.path.exists(glb_path):
            # Fallback: search recursively
            glb_path = None
            for root_dir, _, files in os.walk(assets_dir):
                if os.path.basename(root_dir) == folder_name and f"{base}.glb" in files:
                    glb_path = os.path.join(root_dir, f"{base}.glb")
                    break
        
        # Validate GLB file
        if not glb_path or not os.path.exists(glb_path):
            continue
        if os.path.getsize(glb_path) < 1000:
            continue
        with open(glb_path, "rb") as f:
            if f.read(4) != b"glTF":
                continue

        root = import_glb(glb_path, f"{base.upper()}_{idx:02d}")
        if not root:
            continue
            
        # Get position and rotation from layout
        pos = list(props.get("position", [0, 0, 0]))
        rot = props.get("rotation", [0, 0, 0])
        
        # Apply center offset from metadata if available
        metadata = selected_assets.get(uid, {}) or selected_assets.get(folder_name, {})
        center_offset = metadata.get("center", [0, 0, 0])
        pos[0] += center_offset[0]
        pos[1] += center_offset[1]
        
        place_asset(root, pos, rot, floor_z, offset_x, offset_y, center_x, center_y, rotation_y)
        lift_to_floor(root, floor_z)

    # Get scene bounds and setup rendering
    mins, maxs = get_scene_bounds()
    center = (mins + maxs) / 2
    size = maxs - mins

    setup_lighting(center, maxs.z, data.get("use_eevee", False))
    setup_render(
        resolution=data.get("resolution", 1024),
        samples=data.get("samples", 32),
        use_gpu=data.get("use_gpu", False),
        use_eevee=data.get("use_eevee", False),
    )

    os.makedirs(data["output_dir"], exist_ok=True)
    result = {"success": True}

    # Export USDZ
    if data.get("export_usdz", True):
        usdz_path = os.path.join(data["output_dir"], "room_with_assets_final.usdz")
        bpy.ops.wm.usd_export(filepath=usdz_path)
        result["usdz_path"] = usdz_path

    # Render views
    top_path = os.path.join(data["output_dir"], "render_top.png")
    render_top_view(center, size, maxs.z, top_path)
    result["top_view"] = top_path

    if data.get("render_perspective", True):
        persp_path = os.path.join(data["output_dir"], "render_perspective.png")
        render_perspective_view(center, size, persp_path)
        result["perspective_view"] = persp_path

    with open(opts.output, "w") as f:
        json.dump(result, f)


if __name__ == "__main__":
    main()
'''


def _get_blender_bin() -> str:
    if path := os.environ.get("BLENDER_PATH"):
        return path
    if shutil.which("blender"):
        return "blender"
    for p in ["/Applications/Blender.app/Contents/MacOS/Blender", "/Applications/Blender 4.2.app/Contents/MacOS/Blender"]:
        if Path(p).exists():
            return p
    raise RuntimeError("Blender not found")


def render_scene_node(
    state: dict[str, Any],
    resolution: int = 1024,
    samples: int = 32,
    use_gpu: bool = False,
    use_eevee: bool = False,
    low_quality: bool = False,
    floor_texture: dict | None = None,
) -> dict[str, Any]:
    """Render the scene layout using Blender.

    Args:
        state: Pipeline state
        resolution: Output image size (default 1024)
        samples: Render samples (default 32, lower = faster)
        use_gpu: Use GPU for CYCLES (default False)
        use_eevee: Use EEVEE instead of CYCLES (faster, for low-end hardware)
        low_quality: Preset for fast server rendering (512px, 8 samples, EEVEE)
        floor_texture: {"color": [r,g,b], "roughness": float}. Set False to disable.
    """
    if low_quality:
        resolution, samples, use_eevee = 512, 8, True
    start = time.perf_counter()

    layout = state.get("layoutvlm_layout") or state.get("initial_layout")
    if not layout:
        print("[RENDER SCENE] No layout available")
        return {}

    manager: AssetManager = state["asset_manager"]
    output_dir = Path(manager.stage_path(STAGE_DIRS["render_scene"]))
    output_dir.mkdir(parents=True, exist_ok=True)  # ensure stage dir exists

    input_data = {
        "layout": layout,
        "assets_dir": str(Path("dataset/blobs").resolve()),
        "output_dir": str(output_dir),
        "room_area": state.get("room_area"),
        "resolution": resolution,
        "samples": samples,
        "use_gpu": use_gpu,
        "use_eevee": use_eevee,
        "floor_texture": floor_texture,
        "render_perspective": True,
        "export_usdz": True,
    }

    if usdz_path := state.get("usdz_path"):
        if Path(usdz_path).exists():
            input_data["room_usdz"] = str(Path(usdz_path).resolve())

    input_file = output_dir / "_render_input.json"
    output_file = output_dir / "_render_output.json"
    script_file = output_dir / "_blender_script.py"
    input_file.write_text(json.dumps(input_data, indent=2))
    script_file.write_text(BLENDER_SCRIPT)

    cmd = [_get_blender_bin(), "-b", "-P", str(script_file), "--", "--input", str(input_file), "--output", str(output_file)]
    logger.info("[RENDER SCENE] Running: %s", " ".join(cmd))

    # Stream output in real-time instead of capturing
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output_lines = []
    for line in process.stdout:
        line = line.rstrip()
        output_lines.append(line)
        logger.info("[BLENDER] %s", line)
    returncode = process.wait()

    if returncode != 0:
        logger.error("[RENDER SCENE] Blender failed (code=%d)", returncode)
        raise RuntimeError(f"Blender render failed (code={returncode}): {output_lines[-10:] if output_lines else 'no output'}")

    if not output_file.exists():
        logger.error("[RENDER SCENE] No output file")
        raise RuntimeError(f"Blender did not write output JSON: {output_file}")

    output_data = json.loads(output_file.read_text())
    if not output_data.get("success"):
        raise RuntimeError(f"Render failed: {output_data}")

    log_duration("RENDER SCENE", start)
    logger.info("[RENDER SCENE] USDZ: %s", output_data.get("usdz_path"))
    logger.info("[RENDER SCENE] Top: %s, Persp: %s", output_data.get("top_view"), output_data.get("perspective_view"))

    return {
        "final_usdz_path": output_data.get("usdz_path"),
        "render_top_view": output_data.get("top_view"),
        "render_perspective_view": output_data.get("perspective_view"),
    }
