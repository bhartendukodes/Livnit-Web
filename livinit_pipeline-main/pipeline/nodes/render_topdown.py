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

BLENDER_SCRIPT = '''"""Batch render GLB files to top-down PNG images using pre-computed dimensions."""
import sys
import argparse
import json
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector, Euler

FRONT_VIEW_ROTATIONS = {0: 0, 1: -math.pi/2, 2: -math.pi, 3: math.pi/2}


def clean_scene():
    if bpy.context.object:
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for collection in bpy.data.collections:
        bpy.data.collections.remove(collection)
    bpy.ops.outliner.orphans_purge(do_recursive=True)


def setup_render_engine():
    scene = bpy.context.scene
    for eng in ['BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE']:
        try:
            scene.render.engine = eng
            break
        except:
            continue
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.resolution_x = 128
    scene.render.resolution_y = 128
    scene.render.resolution_percentage = 100
    if 'EEVEE' in scene.render.engine and hasattr(scene, 'eevee'):
        if hasattr(scene.eevee, 'taa_render_samples'):
            scene.eevee.taa_render_samples = 4


def import_model(glb_path):
    if not os.path.exists(glb_path):
        return []
    bpy.ops.import_scene.gltf(filepath=str(glb_path))
    return [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']


def center_objects(objects, center):
    """Center objects using pre-computed center from processed.json."""
    if not objects or not center:
        return
    move_vec = Vector((-center[0], -center[1], -center[2]))
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            obj.location += move_vec


def setup_camera_and_lighting(width, depth):
    """Setup camera using pre-computed dimensions."""
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
    bpy.context.active_object.data.energy = 5.0

    bpy.ops.object.light_add(type='AREA', location=(0, 0, 10))
    fill = bpy.context.active_object
    fill.data.energy = 200.0
    fill.data.size = 10.0

    bpy.ops.object.camera_add(location=(0, 0, 10))
    cam = bpy.context.active_object
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = max(width, depth) * 1.2
    bpy.context.scene.camera = cam


def render_single(task: dict) -> bool:
    """Render using pre-computed dimensions from processed.json."""
    try:
        clean_scene()
        objects = import_model(task["input"])
        if not objects:
            print(f"SKIP: No mesh in {task['input']}")
            return False

        if task.get("front_rotation", 0) != 0:
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH':
                    obj.rotation_euler = Euler((0, 0, task["front_rotation"]), 'XYZ')
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.transform_apply(rotation=True)

        center_objects(objects, task.get("center"))
        setup_camera_and_lighting(task.get("width", 1), task.get("depth", 1))
        bpy.context.scene.render.filepath = task["output"]
        bpy.ops.render.render(write_still=True)
        return Path(task["output"]).exists()
    except Exception as e:
        print(f"ERROR: {task['input']}: {e}")
        return False


def main():
    argv = sys.argv
    if "--" not in argv:
        print("ERROR: No arguments after '--'")
        sys.exit(1)

    args = argv[argv.index("--") + 1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", required=True, help="JSON file with tasks")
    opt = parser.parse_args(args)

    setup_render_engine()

    with open(opt.batch) as f:
        tasks = json.load(f)

    results = {"success": [], "failed": []}
    for i, task in enumerate(tasks):
        if render_single(task):
            results["success"].append(task["output"])
        else:
            results["failed"].append(task["input"])
        print(f"PROGRESS: {i + 1}/{len(tasks)}", flush=True)

    Path(opt.batch).with_suffix(".result.json").write_text(json.dumps(results))
    print(f"DONE: {len(results['success'])} success, {len(results['failed'])} failed")


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

    import math
    front_rotations = {0: 0, 1: -math.pi/2, 2: -math.pi, 3: math.pi/2}

    # Load asset dimensions from processed.json
    processed_path = Path("dataset/processed.json")
    assets_by_uid = {}
    if processed_path.exists():
        assets_by_uid = {a["uid"]: a for a in json.loads(processed_path.read_text())}

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

        uid = subdir.name
        asset = assets_by_uid.get(uid, {})
        front_rotation = front_rotations.get(asset.get("frontView", 0), 0)
        tasks.append({
            "input": str(glb_files[0]),
            "output": str(output_path),
            "front_rotation": front_rotation,
            "width": asset.get("width", 1),
            "depth": asset.get("depth", 1),
            "center": asset.get("center"),
        })

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
