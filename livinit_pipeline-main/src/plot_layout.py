import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import math
import os

# Define paths
PROJECT_ROOT = '.'
SCENE_PATH = os.path.join(PROJECT_ROOT, 'outputs/20251215_121809/scene.json')
LAYOUT_PATH = os.path.join(PROJECT_ROOT, 'outputs/20251215_121809/initial_layout.json')

def get_asset_dimensions(asset_entry):
    """
    Reads dimensions from the data.json file associated with the asset.
    Returns (width, depth) corresponding to x and y in the bounding box.
    """
    rel_path = asset_entry.get('path', '')
    if not rel_path:
        return 0.5, 0.5 # Default fallback

    # Construct path to data.json
    asset_dir = os.path.dirname(rel_path)
    data_json_path = os.path.join(PROJECT_ROOT, asset_dir, 'data.json')
    
    if os.path.exists(data_json_path):
        try:
            with open(data_json_path, 'r') as f:
                data = json.load(f)
                # Based on data.json provided:
                # boundingBox x/y are footprint
                bbox = data.get('assetMetadata', {}).get('boundingBox', {})
                dim_x = bbox.get('x', 0.5)
                dim_y = bbox.get('y', 0.5)
                return dim_x, dim_y
        except Exception as e:
            print(f"Error reading {data_json_path}: {e}")
            return 0.5, 0.5
    else:
        # print(f"Warning: data.json not found at {data_json_path}")
        return 0.5, 0.5

def rotate_point(x, y, degrees):
    """Rotate point (x, y) around origin by given degrees."""
    radians = math.radians(degrees)
    cos_a = math.cos(radians)
    sin_a = math.sin(radians)
    x_new = x * cos_a - y * sin_a
    y_new = x * sin_a + y * cos_a
    return x_new, y_new

def get_color(category, index):
    """Assigns colors based on category and index."""
    if category == 'sofa': return 'pink'
    if category == 'rug': return 'gray'
    if category == 'tv': return 'purple'
    if category == 'tv_stand': return 'red'
    
    if category == 'accent_chair':
        if index == 0: return 'green'
        return 'olive'
        
    if category == 'storage_unit':
        if index == 0: return 'blue'
        return 'orange'
        
    return 'black'

def plot_room(scene_path, layout_path):
    if not os.path.exists(scene_path) or not os.path.exists(layout_path):
        print(f"Error: Files not found.\nChecked:\n{scene_path}\n{layout_path}")
        return

    # Load JSON data
    with open(scene_path, 'r') as f:
        scene_data = json.load(f)
    
    with open(layout_path, 'r') as f:
        layout_data = json.load(f)

    fig, ax = plt.subplots(figsize=(12, 8))

    # --- 1. Draw Room Boundary ---
    floor_vertices = scene_data['boundary']['floor_vertices']
    boundary_coords = [(v[0], v[1]) for v in floor_vertices]
    boundary_coords.append(boundary_coords[0]) # Close loop
    
    xs, ys = zip(*boundary_coords)
    ax.plot(xs, ys, 'k-', linewidth=3, label='Walls')
    ax.fill(xs, ys, 'whitesmoke')

    # --- 2. Draw Assets ---
    assets_info = scene_data.get('assets', {})
    print("layout_data keys:", layout_data.keys())

    for asset_id, transform in layout_data.items():
        # Retrieve asset metadata
        asset_entry = assets_info.get(asset_id)
        if not asset_entry:
            # Defaults when metadata/path is missing
            dim_x, dim_y = 0.5, 0.5
            object_length = dim_y
            object_width = dim_x
        else:
            dim_x, dim_y = get_asset_dimensions(asset_entry)
            # Standard assumption: Arrow points along the "Depth" dimension (local X)
            # dim_y is usually Depth, dim_x is usually Width
            object_length = dim_y 
            object_width = dim_x
        
        category = asset_entry.get('category', 'unknown') if asset_entry else 'unknown'
        instance_idx = asset_entry.get('instance_idx', 0) if asset_entry else 0
        
        # Position and rotation (support list-of-dict schema)
        pos, rot = [0, 0, 0], [0, 0, 0]
        if isinstance(transform, dict):
            pos = transform.get('position', pos)
            rot = transform.get('rotation', rot)
        elif isinstance(transform, (list, tuple)):
            # Expect: [ { "position": [...], "rotation": [...] }, ... ]
            if len(transform) > 0 and isinstance(transform[0], dict):
                d0 = transform[0]
                pos = d0.get('position', pos)
                rot = d0.get('rotation', rot)
            else:
                # Fallback: [position, rotation] or flat position
                if len(transform) >= 2 and isinstance(transform[0], (list, tuple)) and isinstance(transform[1], (list, tuple)):
                    pos, rot = transform[0], transform[1]
                else:
                    pos = list(transform)
                    rot = [0, 0, 0]
        # Dict position like {"x":..,"y":..}
        if isinstance(pos, dict):
            pos = [pos.get('x', 0.0), pos.get('y', 0.0), pos.get('z', 0.0)]
        if isinstance(rot, dict):
            rot = [rot.get('x', 0.0), rot.get('y', 0.0), rot.get('z', 0.0)]
        if len(pos) == 2:
            pos = [pos[0], pos[1], 0.0]
        if len(rot) < 3:
            rot = list(rot) + [0.0] * (3 - len(rot))

        pos_x, pos_y = float(pos[0]), float(pos[1])
        rotation_z = float(rot[2])

        # Define rectangle corners centered at (0,0)
        # We align 'object_length' (Depth) with the X-axis for Rotation 0
        corners = [
            (-object_length/2, -object_width/2),
            (object_length/2, -object_width/2),
            (object_length/2, object_width/2),
            (-object_length/2, object_width/2)
        ]
        
        # Rotate and translate corners
        transformed_corners = []
        for cx, cy in corners:
            rx, ry = rotate_point(cx, cy, rotation_z)
            transformed_corners.append((rx + pos_x, ry + pos_y))
            
        # Styling
        color = get_color(category, instance_idx)
        z_order = 10
        if category == 'rug': z_order = 5
        elif category == 'tv': z_order = 15
        
        # Draw Polygon (Outline only)
        poly = patches.Polygon(transformed_corners, closed=True, 
                               edgecolor=color, facecolor='none', 
                               linewidth=2, zorder=z_order)
        ax.add_patch(poly)
        
        # Label with ID and Rotation
        label_text = f"{asset_id}\n{rotation_z:.0f}°"
        ax.text(pos_x, pos_y, label_text, fontsize=6, ha='center', va='center', 
                clip_on=True, zorder=z_order+1, color=color, fontweight='bold')
        
        # Orientation Arrow
        arrow_len = object_length * 0.6 
        ax_x, ax_y = rotate_point(arrow_len, 0, rotation_z)
        ax.arrow(pos_x, pos_y, ax_x, ax_y, head_width=0.1, color=color, zorder=z_order)

    # --- 3. Plot Settings ---
    ax.set_aspect('equal')
    ax.set_xlabel('X (meters)')
    ax.set_ylabel('Y (meters)')
    ax.set_title('Room Layout Visualization')
    ax.grid(True, linestyle='--', alpha=0.3)
    
    pad = 1.0
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)
    
    plt.legend(loc='upper right')
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    plot_room(SCENE_PATH, LAYOUT_PATH)