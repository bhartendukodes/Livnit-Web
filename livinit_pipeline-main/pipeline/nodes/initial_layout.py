import json
import logging
import os
import time
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from pipeline.core.asset_manager import AssetManager
from pipeline.core.pipeline_shared import STAGE_DIRS, log_duration

load_dotenv()
logger = logging.getLogger(__name__)

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
INITIAL_LAYOUT_CONFIG = types.GenerateContentConfig(
    temperature=1,
    response_mime_type="application/json",
    thinking_config=types.ThinkingConfig(thinking_level="low", include_thoughts=True),
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)


def generate_initial_layout_node(state: dict[str, Any]) -> dict[str, Any]:
    """Generate initial furniture layout via LLM."""
    selected_assets = state.get("selected_assets", [])
    if not selected_assets:
        logger.warning("[INITIAL LAYOUT] No assets selected.")
        return {"initial_layout": {}}

    room_width, room_depth = state["room_area"]
    room_vertices = state.get("room_vertices", [[0, 0], [room_width, 0], [room_width, room_depth], [0, room_depth]])
    user_intent = state.get("user_intent", "Modern living room")

    # Iteration mode: check for previous layout
    previous_layout = state.get("initial_layout") or {}
    is_revision = bool(state.get("asset_revision_prompt")) and previous_layout

    asset_lines = [
        f"- {a['uid']} ({a.get('category', 'unknown')}), {a.get('width', 0):.2f}x{a.get('depth', 0):.2f}x{a.get('height', 0):.2f}m, frontView={a.get('frontView', 0)}"
        for a in selected_assets
    ]

    void_lines = []
    for i, d in enumerate(state.get("room_doors", [])):
        void_lines.append(f"- door-{i}: center={d['center']}, width={d['width']:.2f}m")
    for i, w in enumerate(state.get("room_windows", [])):
        void_lines.append(f"- window-{i}: center={w['center']}, width={w['width']:.2f}m, depth={w['depth']:.2f}m")
    for i, v in enumerate(state.get("room_voids", [])):
        void_lines.append(f"- void-{i}: center={v['center']}, width={v['width']:.2f}m, depth={v['depth']:.2f}m")

    # Build revision context if applicable
    revision_context = ""
    if is_revision:
        # Find assets that exist in previous layout
        prev_uids = set(previous_layout.keys())
        current_uids = {a["uid"] for a in selected_assets}
        unchanged_uids = prev_uids & current_uids
        new_uids = current_uids - prev_uids
        removed_uids = prev_uids - current_uids

        prev_layout_lines = [f"- {uid}: position={v.get('position')}, rotation={v.get('rotation')}" for uid, v in previous_layout.items() if uid in unchanged_uids]
        new_asset_lines = [f"- {uid}" for uid in new_uids]
        revision_context = f"""
=== ITERATION MODE (ASSET SWAP) ===
User requested: {state.get('asset_revision_prompt', '')}

PREVIOUS LAYOUT (copy EXACT values for assets that remain):
{chr(10).join(prev_layout_lines) if prev_layout_lines else "None"}

NEW ASSETS TO PLACE:
{chr(10).join(new_asset_lines) if new_asset_lines else "None"}

REMOVED ASSETS: {list(removed_uids) if removed_uids else "None"}

CRITICAL RULES FOR ITERATION:
1. For unchanged assets: COPY the exact position and rotation values above - do NOT modify them
2. For new assets replacing removed ones: place in similar location to the removed asset of same category
3. Only compute fresh positions for truly new asset categories
"""
        logger.info("[INITIAL LAYOUT] Iteration mode: %d unchanged, %d new, %d removed", len(unchanged_uids), len(new_uids), len(removed_uids))

    # Build example using first asset
    example_uid = selected_assets[0]["uid"] if selected_assets else "asset_1"
    example_cat = selected_assets[0].get("category", "furniture") if selected_assets else "furniture"

    prompt = f"""You are an expert interior designer creating a 2D furniture layout.
{revision_context}

COORDINATE SYSTEM:
- Origin (0,0) at bottom-left corner
- +X points right, +Y points up, +Z is height
- Room bounds: x=[0, {room_width:.2f}], y=[0, {room_depth:.2f}]
- Walls: walls[0] to walls[{len(room_vertices)-1}]. Walls[0] are on the right, walls[1] are above, walls[2] are on the left, walls[3] are below.

DESIGN INTENT: {user_intent}

VOIDS (keep 0.6m clearance):
{chr(10).join(void_lines) if void_lines else "None"}

ASSETS ({len(selected_assets)} items, ALL must be placed):
{chr(10).join(asset_lines)}

FRONTVIEW (native facing direction of 3D model):
- 0 = faces -Y, 1 = faces +X, 2 = faces +Y, 3 = faces -X

ROTATION (radians around Z-axis):
- To face -Y: rotation = 0 - frontView * π/2
- To face +X: rotation = π/2 - frontView * π/2
- To face +Y: rotation = π - frontView * π/2
- To face -X: rotation = 3π/2 - frontView * π/2

ROTATION TIPS:
- Sofas: face room center or TV
- TV and TV stands: face seating
- Chairs: angle toward tables
- Beds: headboard against wall
- Desks: face away from wall

RULES:
- All assets within bounds, no overlaps
- 0.6m clearance from voids
- z: floor=0, on-table=0.5, wall-mounted=1.4
- IMPORTANT: Use uid EXACTLY as provided, do not add suffixes

OUTPUT (JSON array ordered bottom-to-top for correct rendering):
- Order: rugs first, then floor furniture, then items on furniture, then wall-mounted
[
  {{"uid": "{example_uid}", "category": "{example_cat}", "position": [x, y, z], "rotation": [0, 0, radians]}}
]"""

    manager: AssetManager = state["asset_manager"]
    stage = STAGE_DIRS["initial_layout"]
    manager.write_text(stage, "prompt.txt", prompt)

    # Build contents - no image needed for iteration, JSON layout positions are passed in prompt
    contents = [types.Part.from_text(text=prompt)]

    allowed_uids = {a["uid"] for a in selected_assets}

    for attempt in range(3):
        start = time.perf_counter()
        resp = client.models.generate_content(model="gemini-3-flash-preview", contents=contents, config=INITIAL_LAYOUT_CONFIG)
        log_duration("INITIAL LAYOUT", start, resp.usage_metadata)

        layout = json.loads(resp.text)
        manager.write_json(stage, f"response{'_retry' + str(attempt) if attempt else ''}.json", layout)

        layout = {item["uid"]: item for item in layout}

        missing = [uid for uid in allowed_uids if uid not in layout or not isinstance(layout.get(uid), dict)]
        if not missing:
            break

        if attempt < 2:
            logger.warning("[INITIAL LAYOUT] Retry %d: missing %s", attempt + 1, missing)
            contents[0] = types.Part.from_text(text=contents[0].text + f"\n\nMISSING: {', '.join(missing)}. Include ALL assets!")
        else:
            raise ValueError(f"Missing placements: {missing}")

    result = {}
    for uid, p in layout.items():  # Preserve order from LLM response
        if uid not in allowed_uids:
            continue
        pos = p.get("position") or p.get("position_m") or [0, 0, 0]
        rot = p.get("rotation", [0, 0, 0])
        if not isinstance(rot, list) or len(rot) < 3:
            rot = [0, 0, float(p.get("rotation_rad", 0))]
        result[uid] = {"category": p.get("category", ""), "position": [float(x) for x in pos], "rotation": [float(r) for r in rot]}

    manager.write_json(stage, "layout.json", result)
    return {"initial_layout": result}
