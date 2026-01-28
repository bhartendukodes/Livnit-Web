"""
Extract dimensions from GLB files using Blender.

Usage:
    # Run directly with Blender
    blender --background --python extract_glb.py -- path/to/model.glb
    
    # Or use the subprocess wrapper
    python extract_glb.py path/to/model.glb
"""

import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple, Dict, Any


def extract_glb_dimensions_blender(glb_path: str) -> Dict[str, Any]:
    """
    Extract dimensions from a GLB file using Blender's Python API.
    This function should be called from within Blender.
    
    Returns:
        Dict with width, depth, height, and bounding box info
    """
    import bpy
    from mathutils import Vector
    
    def clear_scene():
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
    
    def import_glb(path: str) -> list:
        """Import GLB file and return imported objects."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"GLB file not found: {path}")
        
        size = os.path.getsize(path)
        if size < 1000:
            raise ValueError(f"GLB file too small ({size} bytes), likely corrupt")
        
        with open(path, 'rb') as f:
            header = f.read(4)
        if header != b'glTF':
            raise ValueError("Invalid GLB file: missing glTF header")
        
        bpy.ops.import_scene.gltf(filepath=path)
        return list(bpy.context.selected_objects)
    
    def get_world_bounds(objects: list) -> Tuple[Vector, Vector]:
        """Get world-space bounding box of all mesh objects in hierarchy."""
        depsgraph = bpy.context.evaluated_depsgraph_get()
        mins = Vector((float('inf'), float('inf'), float('inf')))
        maxs = Vector((float('-inf'), float('-inf'), float('-inf')))
        
        def visit(obj):
            nonlocal mins, maxs
            evaluated = obj.evaluated_get(depsgraph)
            if evaluated.type == 'MESH' and evaluated.data:
                for vertex in evaluated.data.vertices:
                    world_pos = evaluated.matrix_world @ vertex.co
                    mins.x = min(mins.x, world_pos.x)
                    mins.y = min(mins.y, world_pos.y)
                    mins.z = min(mins.z, world_pos.z)
                    maxs.x = max(maxs.x, world_pos.x)
                    maxs.y = max(maxs.y, world_pos.y)
                    maxs.z = max(maxs.z, world_pos.z)
            for child in obj.children:
                visit(child)
        
        for obj in objects:
            visit(obj)
        
        if any(math.isinf(v) for v in (*mins, *maxs)):
            return Vector((0, 0, 0)), Vector((0, 0, 0))
        
        return mins, maxs
    
    clear_scene()
    imported_objects = import_glb(glb_path)
    
    if not imported_objects:
        raise ValueError("No objects imported from GLB file")
    
    bpy.context.view_layer.update()
    mins, maxs = get_world_bounds(imported_objects)
    
    width = maxs.x - mins.x
    depth = maxs.y - mins.y
    height = maxs.z - mins.z
    
    center = [
        (mins.x + maxs.x) / 2,
        (mins.y + maxs.y) / 2,
        (mins.z + maxs.z) / 2,
    ]
    
    result = {
        "file": os.path.basename(glb_path),
        "width": round(width, 4),
        "depth": round(depth, 4),
        "height": round(height, 4),
        "assetMetadata": {
            "boundingBox": {
                "min": [round(mins.x, 4), round(mins.y, 4), round(mins.z, 4)],
                "max": [round(maxs.x, 4), round(maxs.y, 4), round(maxs.z, 4)],
                "x": round(width, 4),
                "y": round(depth, 4),
                "z": round(height, 4),
                "center": [round(c, 4) for c in center],
            },
        }
    }

    return result


def extract_glb_dimensions(
    glb_path: str,
    blender_exe: str = "/Applications/Blender.app/Contents/MacOS/Blender"
) -> Optional[Dict[str, Any]]:
    """
    Extract dimensions from a GLB file by running Blender in background.
    
    Args:
        glb_path: Path to the GLB file
        blender_exe: Path to Blender executable
        
    Returns:
        Dict with dimensions or None if failed
    """
    glb_path = str(Path(glb_path).resolve())
    
    script = f'''
import sys
import json
sys.path.insert(0, "{Path(__file__).parent}")
from extract_glb import extract_glb_dimensions_blender

try:
    result = extract_glb_dimensions_blender(r"{glb_path}")
    print("__RESULT_START__")
    print(json.dumps(result))
    print("__RESULT_END__")
except Exception as e:
    print(f"__ERROR__: {{e}}")
'''
    
    temp_script = Path(__file__).parent / "_temp_extract_glb.py"
    temp_script.write_text(script)
    
    try:
        cmd = [blender_exe, "--background", "--python", str(temp_script)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        output = proc.stdout
        
        if "__RESULT_START__" in output and "__RESULT_END__" in output:
            start = output.index("__RESULT_START__") + len("__RESULT_START__")
            end = output.index("__RESULT_END__")
            json_str = output[start:end].strip()
            return json.loads(json_str)
        
        if "__ERROR__" in output:
            error_line = [l for l in output.split('\n') if "__ERROR__" in l][0]
            print(f"[ERROR] {error_line}")
            return None
            
        print(f"[ERROR] Unexpected output from Blender")
        if proc.stderr:
            print(proc.stderr)
        return None
        
    except subprocess.TimeoutExpired:
        print("[ERROR] Blender process timed out")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to run Blender: {e}")
        return None
    finally:
        if temp_script.exists():
            temp_script.unlink()


def extract_dimensions_batch(
    glb_dir: str,
    output_json: Optional[str] = None,
    blender_exe: str = "/Applications/Blender.app/Contents/MacOS/Blender"
) -> Dict[str, Dict[str, Any]]:
    """
    Extract dimensions from all GLB files in a directory.
    
    Args:
        glb_dir: Directory containing GLB files
        output_json: Optional path to save results as JSON
        blender_exe: Path to Blender executable
        
    Returns:
        Dict mapping filename to dimensions
    """
    results = {}
    glb_dir = Path(glb_dir)
    
    glb_files = list(glb_dir.rglob("*.glb"))
    print(f"Found {len(glb_files)} GLB files")
    
    for i, glb_path in enumerate(glb_files, 1):
        print(f"[{i}/{len(glb_files)}] Processing {glb_path.name}...")
        result = extract_glb_dimensions(str(glb_path), blender_exe)
        if result:
            results[glb_path.name] = result
            print(f"  → {result['width']:.3f} x {result['depth']:.3f} x {result['height']:.3f} m")
        else:
            print(f"  → Failed to extract dimensions")
    
    if output_json:
        with open(output_json, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {output_json}")
    
    return results


def extract_all_blobs_dimensions(
    blobs_dir: str = "dataset/blobs",
    output_json: str = "asset_dimension_blender.json",
    blender_exe: str = "/Applications/Blender.app/Contents/MacOS/Blender"
) -> Dict[str, Dict[str, Any]]:
    """
    Extract dimensions from all GLB files in blob subfolders.
    Each subfolder in blobs_dir is expected to contain a .glb file.
    
    Args:
        blobs_dir: Directory containing asset subfolders (e.g., dataset/blobs)
        output_json: Path to save results as JSON
        blender_exe: Path to Blender executable
        
    Returns:
        Dict mapping folder name to dimensions
    """
    results = {}
    blobs_path = Path(blobs_dir)
    
    if not blobs_path.exists():
        print(f"[ERROR] Directory not found: {blobs_dir}")
        return results
    
    # Get all subdirectories
    folders = sorted([f for f in blobs_path.iterdir() if f.is_dir()])
    print(f"Found {len(folders)} asset folders in {blobs_dir}")
    
    for i, folder in enumerate(folders, 1):
        folder_name = folder.name
        
        # Find GLB file in this folder
        glb_files = list(folder.glob("*.glb"))
        if not glb_files:
            print(f"[{i}/{len(folders)}] {folder_name}: No GLB file found, skipping")
            continue
        
        glb_path = glb_files[0]  # Use first GLB if multiple
        print(f"[{i}/{len(folders)}] Processing {folder_name}...")
        
        result = extract_glb_dimensions(str(glb_path), blender_exe)
        if result:
            results[folder_name] = result
            print(f"  → {result['width']:.3f} x {result['depth']:.3f} x {result['height']:.3f} m")
        else:
            print(f"  → Failed to extract dimensions")
    
    # Save results
    with open(output_json, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n{'='*50}")
    print(f"Processed {len(results)}/{len(folders)} assets")
    print(f"Results saved to {output_json}")
    print(f"{'='*50}")
    
    return results


if __name__ == "__main__":
    IN_BLENDER = "--" in sys.argv
    
    if IN_BLENDER:
        import bpy
        from mathutils import Vector
        argv = sys.argv
        if "--" in argv:
            args = argv[argv.index("--") + 1:]
            if args:
                glb_path = args[0]
                try:
                    result = extract_glb_dimensions_blender(glb_path)
                    print("\n" + "=" * 50)
                    print(f"GLB Dimensions: {glb_path}")
                    print("=" * 50)
                    print(f"  Width:  {result['width']:.4f} m")
                    print(f"  Depth:  {result['depth']:.4f} m")
                    print(f"  Height: {result['height']:.4f} m")
                    print(f"  Center: {result['assetMetadata']['boundingBox']['center']}")
                    print("=" * 50)
                    print("\nJSON output:")
                    print(json.dumps(result, indent=2))
                except Exception as e:
                    print(f"[ERROR] {e}")
                    sys.exit(1)
    else:
        if len(sys.argv) < 2:
            print("Usage:")
            print("  python extract_glb.py <glb_file>")
            print("  python extract_glb.py <glb_directory> [--output results.json]")
            print("  python extract_glb.py --all-blobs [--output asset_dimension_blender.json]")
            sys.exit(1)
        
        # Check for --all-blobs flag to process all blob folders
        if "--all-blobs" in sys.argv:
            output_json = "dataset/asset_dimension_blender.json"
            if "--output" in sys.argv:
                idx = sys.argv.index("--output")
                if idx + 1 < len(sys.argv):
                    output_json = sys.argv[idx + 1]
            extract_all_blobs_dimensions(
                blobs_dir="dataset/blobs",
                output_json=output_json
            )
            sys.exit(0)
        
        target = sys.argv[1]
        target_path = Path(target)
        
        output_json = None
        if "--output" in sys.argv:
            idx = sys.argv.index("--output")
            if idx + 1 < len(sys.argv):
                output_json = sys.argv[idx + 1]
        
        if target_path.is_dir():
            extract_dimensions_batch(target, output_json)
        else:
            result = extract_glb_dimensions(target)
            if result:
                print("\n" + "=" * 50)
                print(f"GLB Dimensions: {target}")
                print("=" * 50)
                print(f"  Width:  {result['width']:.4f} m")
                print(f"  Depth:  {result['depth']:.4f} m")
                print(f"  Height: {result['height']:.4f} m")
                print(f"  Center: {result['center']}")
                print("=" * 50)
                
                # If no output path specified, use input GLB directory with dimensions.json
                if not output_json:
                    output_json = str(target_path.parent / "dimensions.json")
                
                with open(output_json, 'w') as f:
                    json.dump(result, f, indent=2)
                print(f"\nResult saved to {output_json}")
            else:
                print("[ERROR] Failed to extract dimensions")
                sys.exit(1)
