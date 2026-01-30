import logging
import math
import os
import re
import time
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.transforms import Affine2D

from pipeline.core.asset_manager import AssetManager
from pipeline.core.pipeline_shared import STAGE_DIRS, log_duration

logger = logging.getLogger(__name__)

_RENDER_DIR = Path("dataset/render")
_PALETTE = ["#ef4444", "#f59e0b", "#10b981", "#3b82f6", "#8b5cf6", "#ec4899", "#14b8a6"]
_CATEGORY_COLORS = {
    "rug": _PALETTE[5], "sofa": _PALETTE[0], "tv_stand": _PALETTE[3], "tv": _PALETTE[4],
    "accent_chair": _PALETTE[2], "lighting": _PALETTE[1], "coffee_table": _PALETTE[6],
}


def _rotate_point(x, y, radians):
    cos_a, sin_a = math.cos(radians), math.sin(radians)
    return x * cos_a - y * sin_a, x * sin_a + y * cos_a


def _pick_dims(asset, placement):
    # Use scale from placement if available (layoutvlm format)
    scale = placement.get("scale")
    if scale and len(scale) >= 2:
        return float(scale[0]), float(scale[1])
    # Fall back to asset metadata
    bbox = (asset or {}).get("assetMetadata", {}).get("boundingBox", {})
    if bbox:
        return float(bbox.get("x", 0.5)), float(bbox.get("y", 0.5))
    return float((asset or {}).get("width", 0.5)), float((asset or {}).get("depth", 0.5))


def _to_placements(layout):
    if isinstance(layout, dict) and "placements" in layout:
        return layout["placements"]
    if isinstance(layout, dict):
        placements = []
        for uid, data in layout.items():
            if not isinstance(data, dict):
                continue
            category = data.get("category") or uid.rsplit("-", 1)[0].replace("_", " ")
            placements.append({
                "uid": uid,
                "category": category,
                "position": data.get("position"),
                "rotation": data.get("rotation"),
                "scale": data.get("scale"),
            })
        return placements
    return []


def _color_for(category, uid):
    key = (category or uid or "").lower()
    return _CATEGORY_COLORS.get(key, _PALETTE[hash(key) % len(_PALETTE)])


def _render(layout, assets, room_area, room_doors, room_windows, output_path):
    placements = _to_placements(layout)
    width, depth = room_area

    fig, ax = plt.subplots(figsize=(8, 8))

    # Draw room boundary (0-based coordinates, bottom-left origin)
    room_corners = [(0, 0), (width, 0), (width, depth), (0, depth)]
    xs, ys = zip(*(room_corners + [room_corners[0]]))
    ax.plot(xs, ys, "k-", linewidth=2)
    ax.fill(xs, ys, "whitesmoke")

    # Draw doors
    for door in room_doors:
        cx, cy = door["center"]
        w = door["width"]
        ax.add_patch(patches.Rectangle((cx - w/2, cy - 0.1), w, 0.2, color="brown", alpha=0.7))
        ax.text(cx, cy, "D", fontsize=8, ha="center", va="center", color="white", fontweight="bold")

    # Draw windows
    for window in room_windows:
        cx, cy = window["center"]
        w, d = window.get("width", 1.0), window.get("depth", 0.1)
        ax.add_patch(patches.Rectangle((cx - w/2, cy - d/2), w, d, color="lightblue", alpha=0.7, edgecolor="blue"))

    # Prepare and sort assets by z-height
    normalized = []
    for placement in placements:
        uid = placement.get("uid")
        if not uid:
            continue
        asset = assets.get(uid, {})
        category = placement.get("category") or asset.get("category", "unknown")
        pos = placement.get("position") or []
        if not isinstance(pos, list) or len(pos) < 2:
            continue
        pos_x, pos_y = float(pos[0]), float(pos[1])
        rot_list = placement.get("rotation") or [0.0, 0.0, 0.0]
        rotation_z = float(rot_list[2] if len(rot_list) >= 3 else rot_list[-1])
        dim_x, dim_y = _pick_dims(asset, placement)
        height = float(pos[2]) if len(pos) >= 3 else 0.0
        normalized.append({
            "uid": uid, "category": category, "pos_x": pos_x, "pos_y": pos_y,
            "height": height, "rotation_z": rotation_z, "dim_x": dim_x, "dim_y": dim_y,
            "color": _color_for(category, uid)
        })

    normalized.sort(key=lambda item: item["height"])

    # Draw assets
    for item in normalized:
        uid, pos_x, pos_y, rotation_z = item["uid"], item["pos_x"], item["pos_y"], item["rotation_z"]
        dim_x, dim_y, color = item["dim_x"], item["dim_y"], item["color"]
        corners = [(-dim_x/2, -dim_y/2), (dim_x/2, -dim_y/2), (dim_x/2, dim_y/2), (-dim_x/2, dim_y/2)]
        transformed = [(_rotate_point(cx, cy, rotation_z)[0] + pos_x, _rotate_point(cx, cy, rotation_z)[1] + pos_y) for cx, cy in corners]
        poly = patches.Polygon(transformed, closed=True, edgecolor=color, facecolor=color, alpha=0.15, linewidth=1.5)
        ax.add_patch(poly)

        # Overlay asset image if exists (strip instance suffix for lookup)
        base_uid = re.sub(r"_\d+$", "", uid) if re.search(r"_\d+_\d+$", uid) else uid
        img_path = _RENDER_DIR / f"{base_uid}.png"
        if img_path.exists():
            img = plt.imread(img_path)
            extent = (pos_x - dim_x/2, pos_x + dim_x/2, pos_y - dim_y/2, pos_y + dim_y/2)
            ax.imshow(img, extent=extent, transform=Affine2D().rotate_deg_around(pos_x, pos_y, math.degrees(rotation_z)) + ax.transData, zorder=2)

        ax.text(pos_x, pos_y, f"{uid}\n{rotation_z:.2f}rad", fontsize=6, ha="center", va="center", color=color, fontweight="bold")

    # Draw direction arrows
    for item in normalized:
        pos_x, pos_y, rotation_z, color = item["pos_x"], item["pos_y"], item["rotation_z"], item["color"]
        ax.arrow(pos_x, pos_y, math.sin(rotation_z) * 0.5, -math.cos(rotation_z) * 0.5,
                 head_width=0.1, color=color, length_includes_head=True, zorder=10)

    ax.set_aspect("equal")
    ax.set_xlim(-0.5, width + 0.5)
    ax.set_ylim(-0.5, depth + 0.5)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title(f"Layout Preview ({width:.1f}m x {depth:.1f}m)")
    ax.grid(True, linestyle="--", alpha=0.3)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def layout_preview_node(state: dict[str, Any], output_key: str = "layout_preview_path", filename: str = "layout_preview.png", layout_key: str | None = None) -> dict[str, Any]:
    start = time.perf_counter()
    if layout_key:
        layout = state.get(layout_key)
    else:
        layoutvlm = state.get("layoutvlm_layout") or {}
        layout = layoutvlm if len(layoutvlm) > 0 else state.get("initial_layout")
    if not layout:
        logger.info("[LAYOUT PREVIEW] No layout to render")
        return {}

    assets = {a["uid"]: a for a in state.get("selected_assets", [])}
    room_area = state.get("room_area", (5.0, 6.0))
    room_doors = state.get("room_doors", [])
    room_windows = state.get("room_windows", [])
    manager: AssetManager = state["asset_manager"]
    preview_path = manager.stage_path(STAGE_DIRS["draw_layout_preview"]) / filename

    _render(layout, assets, room_area, room_doors, room_windows, preview_path)
    log_duration("LAYOUT PREVIEW", start)
    logger.info("[LAYOUT PREVIEW] Saved to %s", preview_path)
    return {output_key: str(preview_path)}
