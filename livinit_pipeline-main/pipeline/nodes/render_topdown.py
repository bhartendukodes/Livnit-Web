import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from pipeline.core.pipeline_shared import log_duration

logger = logging.getLogger(__name__)

BLOBS_DIR = Path("dataset/blobs")
RENDER_DIR = Path("dataset/render")


def _crop_to_content(image_path: Path, padding: int = 4) -> None:
    """Crop image to tight bounding box around non-transparent pixels."""
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGBA':
                return
            bbox = img.getchannel('A').getbbox()
            if not bbox:
                return
            x1, y1, x2, y2 = bbox
            x1, y1 = max(0, x1 - padding), max(0, y1 - padding)
            x2, y2 = min(img.width, x2 + padding), min(img.height, y2 + padding)
            img.crop((x1, y1, x2, y2)).save(image_path)
    except Exception as e:
        logger.warning("Crop failed for %s: %s", image_path, e)

BLENDER_SCRIPT = '''"""Batch render GLB files to top-down PNG images in a single Blender process."""
import sys
import argparse
import json
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector, Euler

# frontView convention: 0=-Y, 1=+X, 2=+Y, 3=-X
# Rotation needed to normalize to face -Y (top-down shows front at bottom)
FRONT_VIEW_ROTATIONS = {0: 0, 1: -math.pi/2, 2: -math.pi, 3: math.pi/2}


def clean_scene():
    if bpy.context.object:
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for collection in bpy.data.collections:
        bpy.data.collections.remove(collection)
    # Clear orphan data to prevent memory bloat
    bpy.ops.outliner.orphans_purge(do_recursive=True)


def setup_render_engine():
    scene = bpy.context.scene
    for eng in ['BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE', 'CYCLES']:
        try:
            scene.render.engine = eng
            break
        except:
            continue

    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.resolution_x = 256
    scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100

    if scene.render.engine == 'CYCLES':
        scene.cycles.samples = 32
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.device = 'CPU'
    elif 'EEVEE' in scene.render.engine and hasattr(scene, 'eevee'):
        if hasattr(scene.eevee, 'taa_render_samples'):
            scene.eevee.taa_render_samples = 8


def import_model(glb_path):
    if not os.path.exists(glb_path):
        return []
    bpy.ops.import_scene.gltf(filepath=str(glb_path))
    return [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']


def normalize_scene(objects):
    if not objects:
        return Vector((0, 0, 0)), Vector((1, 1, 1))

    min_v = Vector((float('inf'), float('inf'), float('inf')))
    max_v = Vector((float('-inf'), float('-inf'), float('-inf')))

    for obj in objects:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        for corner in [obj.matrix_world @ Vector(bound) for bound in obj.bound_box]:
            min_v.x = min(min_v.x, corner.x)
            min_v.y = min(min_v.y, corner.y)
            min_v.z = min(min_v.z, corner.z)
            max_v.x = max(max_v.x, corner.x)
            max_v.y = max(max_v.y, corner.y)
            max_v.z = max(max_v.z, corner.z)

    center_x = (min_v.x + max_v.x) / 2
    center_y = (min_v.y + max_v.y) / 2
    move_vec = Vector((-center_x, -center_y, -min_v.z))

    for obj in bpy.context.scene.objects:
        obj.location += move_vec

    return min_v + move_vec, max_v + move_vec


def setup_camera_and_lighting(min_v, max_v):
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
    sun = bpy.context.active_object
    sun.data.energy = 5.0

    bpy.ops.object.light_add(type='AREA', location=(0, 0, 10))
    fill = bpy.context.active_object
    fill.data.energy = 200.0
    fill.data.size = 10.0

    
    bpy.ops.object.camera_add(location=(0, 0, 10))
    cam = bpy.context.active_object
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = max(max_v.x - min_v.x, max_v.y - min_v.y) * 1.2
    bpy.context.scene.camera = cam


def render_single(input_path: Path, output_path: Path, front_rotation: float = 0) -> bool:
    """Render a single GLB file. Returns True on success."""
    try:
        clean_scene()
        objects = import_model(str(input_path))
        if not objects:
            print(f"SKIP: No mesh in {input_path.name}")
            return False

        # Apply front rotation to normalize facing direction
        if front_rotation != 0:
            for obj in bpy.context.scene.objects:
                obj.rotation_euler = Euler((0, 0, front_rotation), 'XYZ')

        min_v, max_v = normalize_scene(objects)
        setup_camera_and_lighting(min_v, max_v)
        bpy.context.scene.render.filepath = str(output_path)
        bpy.ops.render.render(write_still=True)
        return output_path.exists()
    except Exception as e:
        print(f"ERROR: {input_path.name}: {e}")
        return False


def main():
    argv = sys.argv
    if "--" not in argv:
        print("ERROR: No arguments after '--'")
        sys.exit(1)

    args = argv[argv.index("--") + 1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="Single GLB input file")
    parser.add_argument("--output", help="Single PNG output file")
    parser.add_argument("--batch", help="JSON file with list of {input, output} tasks")
    opt = parser.parse_args(args)

    setup_render_engine()

    # Batch mode: process multiple files
    if opt.batch:
        with open(opt.batch) as f:
            tasks = json.load(f)

        results = {"success": [], "failed": []}
        total = len(tasks)
        for i, task in enumerate(tasks):
            inp, out = Path(task["input"]), Path(task["output"])
            front_rot = task.get("front_rotation", 0)
            if render_single(inp, out, front_rot):
                results["success"].append(str(out))
            else:
                results["failed"].append(str(inp))
            print(f"PROGRESS: {i + 1}/{total}", flush=True)

        # Write results back
        result_path = Path(opt.batch).with_suffix(".result.json")
        result_path.write_text(json.dumps(results))
        print(f"DONE: {len(results['success'])} success, {len(results['failed'])} failed")

    # Single file mode (backward compat)
    elif opt.input and opt.output:
        if render_single(Path(opt.input), Path(opt.output)):
            print(f"SUCCESS: {opt.output}")
        else:
            print(f"FAILED: {opt.input}")
            sys.exit(1)
    else:
        print("ERROR: Provide --batch or both --input and --output")
        sys.exit(1)


if __name__ == "__main__":
    main()
'''


def _get_blender_bin() -> str:
    if path := os.environ.get("BLENDER_PATH"):
        return path
    if shutil.which("blender"):
        return "blender"
    for p in [
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/Applications/Blender 4.2.app/Contents/MacOS/Blender",
    ]:
        if Path(p).exists():
            return p
    raise RuntimeError("Blender not found. Set BLENDER_PATH.")


async def render_topdown_node(state: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    progress_cb: Callable[[int, int], None] | None = state.get("progress_callback")

    # frontView convention: 0=-Y, 1=+X, 2=+Y, 3=-X
    import math
    front_view_rotations = {0: 0, 1: -math.pi/2, 2: -math.pi, 3: math.pi/2}

    # Collect all pending render tasks
    tasks = []
    for subdir in BLOBS_DIR.iterdir():
        if not subdir.is_dir():
            continue
        glb_files = list(subdir.glob("*.glb"))
        if not glb_files:
            continue
        output_path = RENDER_DIR / f"{subdir.name}.png"
        if output_path.exists():
            continue
        # Read frontView from data.json
        front_rotation = 0
        data_json = subdir / "data.json"
        if data_json.exists():
            data = json.loads(data_json.read_text())
            front_view = data.get("annotations", {}).get("frontView", 0)
            front_rotation = front_view_rotations.get(front_view, 0)
        tasks.append({"input": str(glb_files[0]), "output": str(output_path), "front_rotation": front_rotation})

    if not tasks:
        logger.info("[RENDER TOPDOWN] All renders up to date.")
        log_duration("RENDER TOPDOWN", start)
        return {}

    try:
        blender_bin = _get_blender_bin()
    except RuntimeError as e:
        logger.error(str(e))
        return {}

    total = len(tasks)
    logger.info("[RENDER TOPDOWN] Rendering %d assets in batches of 50, max 4 concurrent", total)
    if progress_cb:
        await progress_cb(0, total)

    # Write blender script to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as script_file:
        script_file.write(BLENDER_SCRIPT)
        script_path = script_file.name

    # Split into batches of 50
    batches = [tasks[i:i + 50] for i in range(0, len(tasks), 50)]
    semaphore = asyncio.Semaphore(4)
    completed = {"rendered": 0, "failed": 0}
    lock = asyncio.Lock()

    async def run_batch(batch_idx: int, batch_tasks: list[dict]) -> None:
        batch_file = RENDER_DIR / f"_batch_{batch_idx}.json"
        batch_file.write_text(json.dumps(batch_tasks))

        async with semaphore:
            cmd = [blender_bin, "-b", "-P", script_path, "--", "--batch", str(batch_file)]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            while line := await proc.stdout.readline():
                text = line.decode().strip()
                if text.startswith("PROGRESS:"):
                    parts = text.split(":")[1].strip().split("/")
                    if len(parts) == 2:
                        batch_progress = int(parts[0])
                        logger.info("[RENDER TOPDOWN] Batch %d: %s/%s", batch_idx, parts[0], parts[1])
                        # Send progress for each render within batch to prevent timeout
                        async with lock:
                            current_total = completed["rendered"] + batch_progress
                            if progress_cb:
                                await progress_cb(current_total, total)

            await proc.wait()

            result_file = batch_file.with_suffix(".result.json")
            if result_file.exists():
                results = json.loads(result_file.read_text())
                for img_path in results.get("success", []):
                    _crop_to_content(Path(img_path))
                async with lock:
                    completed["rendered"] += len(results.get("success", []))
                    completed["failed"] += len(results.get("failed", []))
                    if progress_cb:
                        await progress_cb(completed["rendered"], total)
                result_file.unlink()
            batch_file.unlink(missing_ok=True)

            if proc.returncode != 0:
                stderr = await proc.stderr.read()
                logger.error("[RENDER TOPDOWN] Batch %d error: %s", batch_idx, stderr.decode()[-500:])

    try:
        await asyncio.gather(*[run_batch(i, batch) for i, batch in enumerate(batches)])
        log_duration("RENDER TOPDOWN", start)
        logger.info("[RENDER TOPDOWN] Complete: %d rendered, %d failed", completed["rendered"], completed["failed"])
        return {}
    finally:
        os.unlink(script_path)
