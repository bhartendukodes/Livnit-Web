import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import bpy
import mathutils
import numpy as np
from mathutils import Vector


def place_assets_and_export(
    roomplan_usdz: str,
    layout_json: str,
    assets_dir: str,
    output_dir: str,
    yaw_offset: float = np.pi / 2,
):
    """
    Places assets from layout.json into the RoomPlan USDZ scene in Blender,
    scales and aligns them correctly, and exports the final composed USDZ file.
    Automatically skips corrupt .glb files.
    """

    # ============================================================
    # SCENE HELPERS
    # ============================================================
    def get_asset_dimensions_from_json(asset_base_name, assets_root_dir):
        """
        Tries to find data.json for the given asset and returns (width, depth, height).
        Returns None if not found or error.
        """
        # Search for the asset folder
        asset_folder = None
        for root, dirs, files in os.walk(assets_root_dir):
            if asset_base_name in dirs:
                asset_folder = os.path.join(root, asset_base_name)
                break
            # Fallback: sometimes the folder name matches the base name exactly
            if os.path.basename(root) == asset_base_name:
                asset_folder = root
                break

        if not asset_folder:
            return None

        data_json_path = os.path.join(asset_folder, "data.json")
        if not os.path.exists(data_json_path):
            return None

        try:
            with open(data_json_path, "r") as f:
                data = json.load(f)
                bbox = data.get("assetMetadata", {}).get("boundingBox", {})
                # data.json usually has x=width, y=depth, z=height
                x = bbox.get("x")
                y = bbox.get("y")
                z = bbox.get("z")
                if x and y and z:
                    return (x, y, z)
        except Exception as e:
            print(f"[WARN] Failed to read dimensions for {asset_base_name}: {e}")

        return None

    def configure_scene_units():
        s = bpy.context.scene
        s.unit_settings.system = "METRIC"
        s.unit_settings.scale_length = 1.0

    def clear_scene():
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        print("[INFO] Cleared Blender scene.")

    def import_usdz(path):
        bpy.ops.wm.usd_import(filepath=path)
        print(f"[INFO] Imported RoomPlan: {os.path.basename(path)}")

    def import_glb(path):
        """Safely import GLB, skipping invalid/corrupt files."""
        # --- Validation ---
        if not os.path.exists(path):
            print(f"[MISSING] {path}")
            return []

        size = os.path.getsize(path)
        if size < 1000:
            print(
                f"[CORRUPT] {os.path.basename(path)} too small ({size} bytes). Skipped."
            )
            return []

        try:
            with open(path, "rb") as f:
                header = f.read(4)
            if header != b"glTF":
                print(
                    f"[CORRUPT] {os.path.basename(path)} missing glTF header. Skipped."
                )
                return []
        except Exception as e:
            print(f"[ERROR] Failed to validate {path}: {e}")
            return []

        # --- Try importing ---
        try:
            bpy.ops.import_scene.gltf(filepath=path)
            return [o for o in bpy.context.selected_objects]
        except Exception as e:
            print(f"[IMPORT ERROR] {path} → {e}")
            return []

    def get_floor_mesh():
        for o in bpy.data.objects:
            if o.type == "MESH" and "floor" in o.name.lower():
                return o
        return None

    def get_floor_info(floor_obj):
        depsgraph = bpy.context.evaluated_depsgraph_get()
        ev = floor_obj.evaluated_get(depsgraph)
        verts = [ev.matrix_world @ v.co for v in ev.data.vertices]
        zmin = min(v.z for v in verts)
        cx = sum(v.x for v in verts) / len(verts)
        cy = sum(v.y for v in verts) / len(verts)
        return zmin, (cx, cy)

    def world_bbox_of_hierarchy(objs):
        depsgraph = bpy.context.evaluated_depsgraph_get()
        mins = Vector((float("inf"), float("inf"), float("inf")))
        maxs = Vector((-float("inf"), -float("inf"), -float("inf")))

        def visit(o):
            eo = o.evaluated_get(depsgraph)
            if eo.type == "MESH" and eo.data:
                for v in eo.data.vertices:
                    p = eo.matrix_world @ v.co
                    mins.x = min(mins.x, p.x)
                    mins.y = min(mins.y, p.y)
                    mins.z = min(mins.z, p.z)
                    maxs.x = max(maxs.x, p.x)
                    maxs.y = max(maxs.y, p.y)
                    maxs.z = max(maxs.z, p.z)
            for c in o.children:
                visit(c)

        for root in objs:
            visit(root)
        if any(math.isinf(v) for v in (*mins, *maxs)):
            return Vector((0, 0, 0)), Vector((0, 0, 0))
        return mins, maxs

    def dims_from_bbox(mins, maxs):
        return (maxs.x - mins.x, maxs.y - mins.y, maxs.z - mins.z)

    def make_root_group(name, imported_objs):
        root = bpy.data.objects.new(name, None)
        bpy.context.scene.collection.objects.link(root)
        for o in imported_objs:
            o.parent = root
        bpy.context.view_layer.update()
        return root

    def lift_to_floor(root, floor_z, pad=0.02):
        bpy.context.view_layer.update()
        mins, _ = world_bbox_of_hierarchy([root])
        if mins.z < floor_z:
            offset = floor_z - mins.z + pad
            root.location.z += offset
            bpy.context.view_layer.update()

    # ============================================================
    # EXECUTION
    # ============================================================
    configure_scene_units()
    clear_scene()
    import_usdz(roomplan_usdz)

    floor = get_floor_mesh()
    if floor:
        floor_z, (cx, cy) = get_floor_info(floor)
        print(
            f"[INFO] Floor mesh found: {floor.name} (Z={floor_z:.3f}), center=({cx:.2f}, {cy:.2f})"
        )
    else:
        floor_z, (cx, cy) = 0.0, (0.0, 0.0)
        print("[WARN] No floor mesh found — using Z=0, center=(0,0)")

    layout = json.load(open(layout_json))
    positions = [props.get("position", [0, 0, 0]) for props in layout.values()]
    avg_x = sum(p[0] for p in positions) / len(positions) if positions else 0.0
    avg_y = sum(p[1] for p in positions) / len(positions) if positions else 0.0
    print(f"[INFO] Centering assets around ({cx:.2f}, {cy:.2f})")

    # ---------- Import all GLBs recursively ----------
    for idx, (key, props) in enumerate(layout.items(), 1):
        base = key.split("-")[0]
        glb_path = None
        for root_dir, _, files in os.walk(assets_dir):
            for f in files:
                if f.lower() == f"{base}.glb":
                    glb_path = os.path.join(root_dir, f)
                    break
            if glb_path:
                break

        if not glb_path:
            print(f"[MISSING] No GLB for '{base}' in {assets_dir}")
            continue

        imported = import_glb(glb_path)
        if not imported:
            continue  # skip corrupt

        root = make_root_group(f"{base.upper()}_{idx:02d}_ROOT", imported)

        # target_dims = get_asset_dimensions_from_json(base, assets_dir)
        # if target_dims:
        #     # Get current dimensions of the imported hierarchy
        #     mins, maxs = world_bbox_of_hierarchy([root])
        #     curr_dims = dims_from_bbox(mins, maxs)

        #     # Calculate scale factors (target / current)
        #     # Use a small epsilon to prevent division by zero
        #     sx = target_dims[0] / curr_dims[0] if curr_dims[0] > 1e-5 else 1.0
        #     sy = target_dims[1] / curr_dims[1] if curr_dims[1] > 1e-5 else 1.0
        #     sz = target_dims[2] / curr_dims[2] if curr_dims[2] > 1e-5 else 1.0

        #     root.scale = (sx, sy, sz)
        #     bpy.context.view_layer.update()
        #     print(f"[INFO] Scaled {base} to match data.json dimensions: {target_dims}")

        # if base in ASSET_CORR:
        #     k = ASSET_CORR[base]
        #     root.scale = [c * k for c in root.scale]
        #     bpy.context.view_layer.update()

        pos = props.get("position", [0, 0, 0])
        rot = props.get("rotation", [0, 0, 0])
        x, y, z = pos
        rx = rot[0]
        ry = rot[1]
        rz = rot[2] + yaw_offset

        root.location = ((x - avg_x) + cx, (y - avg_y) + cy, floor_z + max(z, 0.05))
        root.rotation_euler = (rx, ry, rz)
        lift_to_floor(root, floor_z)

        print(f"[Placed] {base} → {tuple(round(v, 3) for v in root.location)}")

    # bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # ---------- EXPORT ----------
    os.makedirs(output_dir, exist_ok=True)
    output_usdz = os.path.join(output_dir, "room_with_assets_final.usdz")
    bpy.ops.wm.usd_export(filepath=output_usdz)
    print(f"[SUCCESS] Exported → {output_usdz}")
    return output_usdz


def run_blender_process(
    blender_exe: Path,
    usdz_path: Path,
    layout_json: str,
    assets_root: Path,
    runs_dir: Path,
    outputs_dir: Path,
):
    """Generates a temporary Blender script and executes it to place assets and export USDZ."""
    print("\n[INFO] Launching Blender for placement and export...")

    blender_output_dir = runs_dir / "final_usdz_output"
    blender_output_dir.mkdir(exist_ok=True)

    blender_script = outputs_dir / "run_blender_temp.py"

    usdz_path_str = str(usdz_path)
    layout_json_str = str(layout_json)
    assets_root_str = str(assets_root)
    blender_output_dir_str = str(blender_output_dir)

    script_content = f"""import sys
sys.path.append("src")
from blender_placer import place_assets_and_export

place_assets_and_export(
    roomplan_usdz=r"{usdz_path_str}",
    layout_json=r"{layout_json_str}",
    assets_dir=r"{assets_root_str}",
    output_dir=r"{blender_output_dir_str}",
)
"""

    with open(blender_script, "w", encoding="utf-8") as f:
        f.write(script_content)

    # Convert paths to strings for subprocess
    cmd = [str(blender_exe), "--background", "--python", str(blender_script)]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.stdout.strip():
            print("---- Blender stdout ----")
            print(proc.stdout)
        if proc.stderr.strip():
            print("---- Blender stderr ----")
            print(proc.stderr)

        if proc.returncode != 0:
            raise RuntimeError(f"Blender exited with code {proc.returncode}")

        final_usdz_path = blender_output_dir / "room_with_assets_final.usdz"
        if not final_usdz_path.exists():
            raise FileNotFoundError(f"Expected export not found: {final_usdz_path}")

        print("[SUCCESS] Blender export complete:", final_usdz_path)
        return final_usdz_path

    except Exception as e:
        print(f"[ERROR] Blender execution failed: {e}")
        return None


# ============================================================
# STANDALONE TEST
# ============================================================
if __name__ == "__main__":
    from pathlib import Path

    final = run_blender_process(
        blender_exe=Path("/Applications/Blender.app/Contents/MacOS/Blender"),
        usdz_path=Path("dataset/room/Project-2510280721.usdz").resolve(),
        layout_json=Path("outputs/20251204_225736/layout.json").resolve(),
        assets_root=Path("assets/objaverse_processed").resolve(),
        runs_dir=Path("outputs/20251204_225736").resolve(),
        outputs_dir=Path("outputs/20251204_225736").resolve(),
    )
