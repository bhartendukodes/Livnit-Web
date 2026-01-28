"""
Update asset dimensions in processed.json from Blender-extracted dimensions.

This script:
1. Reads asset_dimensions_blender.json (extracted from GLB files)
2. Updates width, depth, height in dataset/processed.json
3. Adds center coordinates from bounding box
4. Saves the updated processed.json

Usage:
    python scripts/update_dimension.py
"""

import json
from pathlib import Path


def update_dimensions(
    blender_dimensions_path: str = "asset_dimensions_blender.json",
    processed_json_path: str = "dataset/processed.json",
):
    """
    Update dimensions in processed.json from Blender-extracted data.
    
    Args:
        blender_dimensions_path: Path to asset_dimensions_blender.json
        processed_json_path: Path to dataset/processed.json
    """
    # Load Blender dimensions
    blender_path = Path(blender_dimensions_path)
    if not blender_path.exists():
        print(f"[ERROR] Blender dimensions file not found: {blender_dimensions_path}")
        return False
    
    with open(blender_path, 'r') as f:
        blender_dims = json.load(f)
    
    print(f"Loaded {len(blender_dims)} assets from {blender_dimensions_path}")
    
    # Load processed.json
    processed_path = Path(processed_json_path)
    if not processed_path.exists():
        print(f"[ERROR] Processed JSON file not found: {processed_json_path}")
        return False
    
    with open(processed_path, 'r') as f:
        processed = json.load(f)
    
    print(f"Loaded {len(processed)} assets from {processed_json_path}")
    
    # Update dimensions
    updated_count = 0
    not_found = []
    
    for asset in processed:
        uid = asset.get("uid")
        if not uid:
            continue
        
        if uid in blender_dims:
            blender_data = blender_dims[uid]
            
            # Update width, depth, height
            old_dims = (asset.get("width"), asset.get("depth"), asset.get("height"))
            
            asset["width"] = round(blender_data["width"], 4)
            asset["depth"] = round(blender_data["depth"], 4)
            asset["height"] = round(blender_data["height"], 4)
            
            # Add center from bounding box
            bbox = blender_data.get("assetMetadata", {}).get("boundingBox", {})
            if "center" in bbox:
                asset["center"] = [round(c, 4) for c in bbox["center"]]
            
            new_dims = (asset["width"], asset["depth"], asset["height"])
            
            if old_dims != new_dims:
                print(f"  [{uid}] {old_dims} → {new_dims}")
            
            updated_count += 1
        else:
            not_found.append(uid)
    
    # Save updated processed.json
    with open(processed_path, 'w') as f:
        json.dump(processed, f, indent=2)
    
    print(f"\n{'='*50}")
    print(f"Updated {updated_count}/{len(processed)} assets")
    print(f"Saved to {processed_json_path}")
    
    if not_found:
        print(f"\n[WARNING] {len(not_found)} assets not found in Blender dimensions:")
        for uid in not_found[:10]:  # Show first 10
            print(f"  - {uid}")
        if len(not_found) > 10:
            print(f"  ... and {len(not_found) - 10} more")
    
    print(f"{'='*50}")
    return True


if __name__ == "__main__":
    import sys
    
    # Allow custom paths from command line
    blender_path = "asset_dimensions_blender.json"
    processed_path = "dataset/processed.json"
    
    if len(sys.argv) > 1:
        blender_path = sys.argv[1]
    if len(sys.argv) > 2:
        processed_path = sys.argv[2]
    
    success = update_dimensions(blender_path, processed_path)
    sys.exit(0 if success else 1)
