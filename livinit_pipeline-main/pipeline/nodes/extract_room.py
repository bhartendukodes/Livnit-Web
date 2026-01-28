import logging
import time
from typing import Any

import numpy as np
from pxr import Usd, UsdGeom
from shapely.geometry import Polygon, box

from pipeline.core.asset_manager import AssetManager
from pipeline.core.pipeline_shared import STAGE_DIRS, log_duration

logger = logging.getLogger(__name__)


def extract_room_node(state: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    manager: AssetManager = state["asset_manager"]
    stage = Usd.Stage.Open(state["usdz_path"])

    # Find largest floor mesh
    floor_prim, floor_pts = None, None
    for prim in stage.Traverse():
        if prim.GetTypeName() != "Mesh":
            continue
        name = prim.GetName().lower()
        path_str = prim.GetPath().pathString.lower()
        is_floor = "floor" in name or "floor" in path_str or "ground" in name or "ground" in path_str
        if not is_floor:
            continue
        pts = np.array(UsdGeom.Mesh(prim).GetPointsAttr().Get() or [], dtype=float)
        if pts.size == 0:
            continue
        area = np.ptp(pts[:, 0]) * np.ptp(pts[:, 1])
        if floor_pts is None or area > np.ptp(floor_pts[:, 0]) * np.ptp(floor_pts[:, 1]):
            floor_prim, floor_pts = prim, pts

    # Fallback: find the largest horizontal mesh if no floor was found
    if floor_prim is None:
        logger.warning("[EXTRACT ROOM] No floor mesh found by name, searching for largest horizontal mesh...")
        for prim in stage.Traverse():
            if prim.GetTypeName() != "Mesh":
                continue
            pts = np.array(UsdGeom.Mesh(prim).GetPointsAttr().Get() or [], dtype=float)
            if pts.size == 0:
                continue
    
            z_range = np.ptp(pts[:, 2]) if pts.shape[1] > 2 else 0
            xy_extent = max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1]))
            if z_range < 0.3 and xy_extent > 1.0:  # Horizontal and reasonably sized
                area = np.ptp(pts[:, 0]) * np.ptp(pts[:, 1])
                if floor_pts is None or area > np.ptp(floor_pts[:, 0]) * np.ptp(floor_pts[:, 1]):
                    floor_prim, floor_pts = prim, pts
                    logger.info(f"[EXTRACT ROOM] Using mesh '{prim.GetPath()}' as floor (area={area:.2f})")

    if floor_prim is None:
        raise ValueError(f"No floor mesh found in USD file: {state['usdz_path']}. "
                        "The file must contain a mesh with 'floor' or 'ground' in its name, "
                        "or a large horizontal mesh.")

    xc = UsdGeom.XformCache(Usd.TimeCode.Default())
    floor_inv = np.linalg.inv(np.array(xc.GetLocalToWorldTransform(floor_prim)))

    # Build floor polygon and fit rectangle
    pts_2d = floor_pts[:, :2]
    center = pts_2d.mean(axis=0)
    angles = np.arctan2(pts_2d[:, 1] - center[1], pts_2d[:, 0] - center[0])
    poly = Polygon(pts_2d[np.argsort(angles)]).buffer(-0.4).buffer(0.2)
    if poly.is_empty:
        poly = Polygon(pts_2d[np.argsort(angles)])

    minx, miny, maxx, maxy = poly.bounds
    step = 0.005
    for _ in range(300):
        if not poly.contains(box(minx - step, miny, maxx + step, maxy)):
            break
        minx -= step
        maxx += step
    for _ in range(300):
        if not poly.contains(box(minx, miny, maxx, maxy + step)):
            break
        maxy += step

    rect = box(minx + step, miny + step, maxx - step, maxy - step)
    rect_coords = np.array(rect.exterior.coords)[:-1]
    offset_x, offset_y = rect_coords.min(axis=0)

    width = float(maxx - minx - 2 * step)
    depth = float(maxy - miny - 2 * step)
    vertices = [[float(x - offset_x), float(y - offset_y)] for x, y in rect_coords]

    # Extract voids
    void_geom = rect.difference(poly)
    voids = []
    for g in (void_geom.geoms if void_geom.geom_type == "MultiPolygon" else [void_geom] if not void_geom.is_empty else []):
        b = g.bounds
        if b[2] - b[0] > 0.2 and b[3] - b[1] > 0.2:
            voids.append({"center": [(b[0] + b[2]) / 2 - offset_x, (b[1] + b[3]) / 2 - offset_y], "width": b[2] - b[0], "depth": b[3] - b[1]})

    # Extract doors and windows from walls
    def collect_pts(root):
        all_pts = []
        for p in Usd.PrimRange(root):
            if p.GetTypeName() != "Mesh":
                continue
            pts = np.array(UsdGeom.Mesh(p).GetPointsAttr().Get() or [], dtype=float)
            if pts.size == 0:
                continue
            wt = np.array(xc.GetLocalToWorldTransform(p))
            pts_h = np.hstack([pts, np.ones((pts.shape[0], 1))])
            all_pts.append((pts_h @ wt @ floor_inv)[:, :2])
        return np.vstack(all_pts) if all_pts else np.empty((0, 2))

    doors, windows = [], []
    for prim in stage.Traverse():
        name = prim.GetName().lower()
        path = prim.GetPath().pathString.lower()
        if "wall" not in name and "/walls/" not in path:
            continue
        for child in Usd.PrimRange(prim):
            cname, cpath = child.GetName().lower(), child.GetPath().pathString.lower()
            if "door" in cname or "door" in cpath:
                pts = collect_pts(child)
                if pts.shape[0]:
                    doors.append({"center": [pts.mean(0)[0] - offset_x, pts.mean(0)[1] - offset_y], "width": float(max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1])))})
            elif "window" in cname or "window" in cpath:
                pts = collect_pts(child)
                if pts.shape[0]:
                    windows.append({"center": [pts.mean(0)[0] - offset_x, pts.mean(0)[1] - offset_y], "width": float(np.ptp(pts[:, 0])), "depth": float(np.ptp(pts[:, 1]))})

    room = {"vertices": vertices, "width": width, "depth": depth, "area": width * depth, "doors": doors, "windows": windows, "voids": voids}
    manager.write_json(STAGE_DIRS["meta"], "room_geometry.json", room)
    log_duration("EXTRACT ROOM", start)
    logger.info("[EXTRACT ROOM] %.2fm x %.2fm, %d doors, %d windows, %d voids", width, depth, len(doors), len(windows), len(voids))

    return {"room_area": (width, depth), "room_vertices": vertices, "room_doors": doors, "room_windows": windows, "room_voids": voids}
