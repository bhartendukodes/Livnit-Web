"""Refine layout node - analyzes layout, fixes issues, and generates constraints for solver."""
import base64
import logging
import math
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from shapely.geometry import Point, Polygon

from pipeline.core.pipeline_shared import log_duration
from pipeline.core.llm import extract_reasoning_trace

load_dotenv()
logger = logging.getLogger(__name__)

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


class AssetPlacement(BaseModel):
    position: list[float] = Field(description="[x, y, z] position in meters")
    rotation: list[float] = Field(description="[rx, ry, rz] rotation in radians")


class RefineLayoutResponse(BaseModel):
    refined_layout: dict[str, AssetPlacement] = Field(default_factory=dict, description="Asset UID to placement mapping")
    constraint_program: str = Field(default="", description="Python constraint code with \\n for newlines")

REFINE_CONFIG = types.GenerateContentConfig(
    temperature=1,
    response_mime_type="application/json",
    response_json_schema=RefineLayoutResponse.model_json_schema(),
    thinking_config=types.ThinkingConfig(thinking_level="low", include_thoughts=True),
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)


def _get_asset_by_uid(uid: str, assets: list[dict[str, Any]]) -> dict[str, Any]:
    asset_map = {a["uid"]: a for a in assets}
    if uid in asset_map:
        return asset_map[uid]
    return asset_map.get(re.sub(r"_\d+$", "", uid), {})


def _compute_overlaps(layout: dict[str, Any], assets: list[dict[str, Any]]) -> list[tuple[str, str]]:
    positions = []
    for uid, placement in layout.items():
        if uid.startswith("void_"):
            continue
        asset = _get_asset_by_uid(uid, assets)
        if "rug" in uid.lower() or "rug" in asset.get("category", "").lower():
            continue
        pos = placement.get("position", [0, 0, 0])
        rot = placement.get("rotation", [0, 0, 0])
        width, depth = asset.get("width", 0.5), asset.get("depth", 0.5)
        rot_z = rot[2] if len(rot) > 2 else 0
        cos_a, sin_a = math.cos(rot_z), math.sin(rot_z)
        corners = [(-width/2, -depth/2), (width/2, -depth/2), (width/2, depth/2), (-width/2, depth/2)]
        rotated = [(pos[0] + c[0]*cos_a - c[1]*sin_a, pos[1] + c[0]*sin_a + c[1]*cos_a) for c in corners]
        positions.append((uid, Polygon(rotated)))

    return [(positions[i][0], positions[j][0]) for i in range(len(positions)) for j in range(i + 1, len(positions)) if positions[i][1].intersects(positions[j][1])]


def _compute_boundary_violations(layout: dict[str, Any], assets: list[dict[str, Any]], boundary: list[list[float]]) -> list[str]:
    room_poly = Polygon([(b[0], b[1]) for b in boundary])
    violations = []
    for uid, placement in layout.items():
        if uid.startswith("void_"):
            continue
        asset = _get_asset_by_uid(uid, assets)
        pos = placement.get("position", [0, 0, 0])
        rot = placement.get("rotation", [0, 0, 0])
        width, depth = asset.get("width", 0.5), asset.get("depth", 0.5)
        rot_z = rot[2] if len(rot) > 2 else 0
        cos_a, sin_a = math.cos(rot_z), math.sin(rot_z)
        corners = [(-width/2, -depth/2), (width/2, -depth/2), (width/2, depth/2), (-width/2, depth/2)]
        for c in corners:
            x = pos[0] + c[0]*cos_a - c[1]*sin_a
            y = pos[1] + c[0]*sin_a + c[1]*cos_a
            if not room_poly.buffer(0.01).contains(Point(x, y)):
                violations.append(uid)
                break
    return violations


def _compute_door_violations(layout: dict[str, Any], assets: list[dict[str, Any]], doors: list[dict[str, Any]]) -> list[tuple[str, int]]:
    violations = []
    for uid, placement in layout.items():
        if uid.startswith("void_"):
            continue
        asset = _get_asset_by_uid(uid, assets)
        if "rug" in uid.lower() or "rug" in asset.get("category", "").lower():
            continue
        pos = placement.get("position", [0, 0, 0])
        for door_idx, door in enumerate(doors):
            door_center = door.get("center", [0, 0])
            dist = math.sqrt((pos[0] - door_center[0])**2 + (pos[1] - door_center[1])**2)
            if dist < door.get("width", 0.9)/2 + 0.5:
                violations.append((uid, door_idx))
                break
    return violations


def _analyze_issues(layout: dict[str, Any], assets: list[dict[str, Any]], boundary: list[list[float]], doors: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "overlaps": _compute_overlaps(layout, assets),
        "boundary_violations": _compute_boundary_violations(layout, assets, boundary),
        "door_violations": _compute_door_violations(layout, assets, doors),
    }


def refine_layout_node(state: dict[str, Any]) -> dict[str, Any]:
    """Analyze layout, fix issues if any, and generate constraints for gradient solver."""
    layout = state.get("initial_layout", {})
    if not layout:
        logger.warning("[REFINE LAYOUT] No layout to refine")
        return {"refined_layout": {}, "constraint_program": "", "task_description": ""}

    preview_path = state.get("layout_preview_path")
    if not preview_path or not Path(preview_path).exists():
        logger.warning("[REFINE LAYOUT] No layout preview image")
        return {"refined_layout": layout, "constraint_program": "", "task_description": ""}

    assets = state.get("selected_assets", [])
    room_width, room_depth = state["room_area"]
    room_vertices = state.get("room_vertices", [[0, 0], [room_width, 0], [room_width, room_depth], [0, room_depth]])
    room_doors = state.get("room_doors", [])
    user_intent = state.get("user_intent", "Modern living room")
    manager = state["asset_manager"]
    stage = "refine_layout"

    # Analyze issues
    issues = _analyze_issues(layout, assets, room_vertices, room_doors)
    has_issues = issues["overlaps"] or issues["boundary_violations"] or issues["door_violations"]

    # Build asset info from layout
    asset_info = []
    for uid, placement in layout.items():
        if uid.startswith("void_"):
            continue
        asset = _get_asset_by_uid(uid, assets)
        pos = placement.get("position", [0, 0, 0])
        rot = placement.get("rotation", [0, 0, 0])
        w, d, h = asset.get("width", 0.5), asset.get("depth", 0.5), asset.get("height", 0.5)
        fv = asset.get("frontView", 0)
        asset_info.append(f"- {uid}: {asset.get('category', uid)}, pos=[{pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}], rot_z={rot[2]:.2f}rad, size=[{w:.2f}, {d:.2f}, {h:.2f}], frontView={fv}")

    door_info = [f"- void_door_{i}: center={d['center']}, width={d['width']:.2f}m" for i, d in enumerate(room_doors)]

    # Build issues section if any
    issues_section = ""
    if has_issues:
        issues_desc = []
        if issues["overlaps"]:
            issues_desc.append(f"OVERLAPPING: {', '.join(f'{a}<->{b}' for a, b in issues['overlaps'])}")
        if issues["boundary_violations"]:
            issues_desc.append(f"OUTSIDE BOUNDARY: {', '.join(issues['boundary_violations'])}")
        if issues["door_violations"]:
            issues_desc.append(f"BLOCKING DOORS: {', '.join(f'{uid} blocks door_{idx}' for uid, idx in issues['door_violations'])}")
        issues_section = f"""
DETECTED ISSUES (must fix these):
{chr(10).join(issues_desc)}
"""

    prompt = f"""You are an expert interior designer. Analyze this layout image and refine it.

DESIGN INTENT: {user_intent}

ROOM: {room_width:.2f}m x {room_depth:.2f}m
Walls: walls[0]=right, walls[1]=top, walls[2]=left, walls[3]=bottom

DOORS:
{chr(10).join(door_info) if door_info else "None"}

ASSETS:
{chr(10).join(asset_info)}
{issues_section}
FRONTVIEW & ROTATION:
frontView indicates native facing direction (0=-Y, 1=+X, 2=+Y, 3=-X).
To face direction D: rotation_z = D * π/2 - frontView * π/2
where D: 0=-Y, 1=+X, 2=+Y, 3=-X

SOLVER API:
- solver.against_wall(asset, walls[i]) - asset touches wall i
- solver.on_top_of(a1, a2) - stack a1 on a2
- solver.align_with(a1, a2, angle=0) - parallel (0) or opposite (180) orientation
- solver.point_towards(a1, a2) - a1 faces a2
- solver.distance_constraint(a1, a2, min, max, weight=1) - distance range between assets

REQUIREMENTS:
- Fix all detected issues (overlaps, boundary violations, door blockages)
- Fix assets rotations to match design intent
- Keep 0.5m+ clearance from doors
- Use exact UIDs from ASSETS list
- No redundant constraints (e.g. both point_towards(a,b) and point_towards(b,a))
- CRITICAL: constraint_program MUST include at least one constraint for EVERY asset listed above. No asset should be left without constraints.

Use your interior design expertise to create a functional, aesthetically pleasing layout that matches the design intent. Consider traffic flow, focal points, conversation areas, and proper furniture relationships.

OUTPUT (valid JSON):
{{
  "refined_layout": {{"asset_uid": {{"position": [x, y, z], "rotation": [0, 0, rz]}}, ...}},
  "constraint_program": "solver calls separated by \\\\n"
}}
"""

    with open(preview_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    start = time.perf_counter()
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[{"text": prompt}, {"inline_data": {"mime_type": "image/png", "data": image_data}}],
        config=REFINE_CONFIG,
    )
    log_duration("REFINE LAYOUT", start, response.usage_metadata)

    reasoning, answer = extract_reasoning_trace(response)
    try:
        parsed = RefineLayoutResponse.model_validate_json(answer)
    except Exception:
        start_idx, end_idx = answer.find("{"), answer.rfind("}") + 1
        if start_idx == -1 or end_idx == 0:
            raise ValueError("No JSON object found in response")
        parsed = RefineLayoutResponse.model_validate_json(answer[start_idx:end_idx])

    # Merge refined positions into original layout
    refined_layout = dict(layout)
    for uid, placement in parsed.refined_layout.items():
        if uid in refined_layout:
            refined_layout[uid] = {
                "category": refined_layout[uid].get("category", ""),
                "position": placement.position,
                "rotation": placement.rotation,
            }

    constraint_program = parsed.constraint_program.replace("\\n", "\n").strip()
    task_desc = f"Layout optimization for: {user_intent}"

    logger.info("[REFINE LAYOUT] Fixed %d assets, %d constraint lines",
                len(parsed.refined_layout), constraint_program.count("\n") + 1 if constraint_program else 0)

    manager.write_text(stage, "prompt.txt", prompt)
    manager.write_text(stage, "response.txt", answer)
    manager.write_json(stage, "refined_layout.json", refined_layout)
    manager.write_text(stage, "constraint_program.py", constraint_program)
    manager.write_json(stage, "issues.json", issues)
    if reasoning:
        manager.write_text(stage, "reasoning.txt", reasoning)

    return {"refined_layout": refined_layout, "constraint_program": constraint_program, "task_description": task_desc, "layout_issues": issues}
