import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from PIL import Image
from pipeline.core.llm import client, extract_reasoning_trace, log_reasoning_trace
from pipeline.core.asset_manager import AssetManager
from pipeline.core.pipeline_shared import STAGE_DIRS, log_duration
from google.genai import types

logger = logging.getLogger(__name__)

ASSET_SELECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "selected_assets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "uid": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["uid"],
            },
        },
        "total_cost": {"type": "number"},
        "total_footprint_sqm": {"type": "number"},
        "selection_strategy": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "higher_budget_additions": {"type": "string"},
                "lower_budget_savings": {"type": "string"},
                "gaps": {"type": "string"},
            },
        },
    },
    "required": ["selected_assets"],
}

ENABLE_ASSET_COLLAGE = os.getenv("ENABLE_ASSET_COLLAGE", "true").lower() == "true"
MAX_TURNS = 3

# --- UPDATE 1: Enhanced Tool Definition ---
VALIDATE_SELECTION_TOOL = types.FunctionDeclaration(
    name="validate_selection",
    description="Validate asset selection. Checks if Total Cost <= Budget AND Total Footprint <= 80% of furniture area. Returns validation status and specific error messages if limits are exceeded.",
    parameters={
        "type": "object",
        "properties": {
            "uids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of asset UIDs to validate",
            }
        },
        "required": ["uids"],
    },
)

LLM_SELECTOR_CONFIG = types.GenerateContentConfig(
    response_mime_type="application/json",
    temperature=1,
    thinking_config=types.ThinkingConfig(thinking_level="low", include_thoughts=True),
    tools=[types.Tool(function_declarations=[VALIDATE_SELECTION_TOOL])],
)

LLM_SELECTOR_ENDING_CONFIG = types.GenerateContentConfig(
    response_mime_type="application/json",
    response_json_schema=ASSET_SELECTION_SCHEMA,
    temperature=1,
    thinking_config=types.ThinkingConfig(thinking_level="low", include_thoughts=True),
)


THUMB_SIZE = 200
LABEL_HEIGHT = 20
HEADER_HEIGHT = 30
COLS = 6
ASSETS_PER_COLLAGE = 30


def extract_category_from_uid(uid: str) -> str:
    """Extract category from UID by removing trailing number."""
    import re
    match = re.match(r"(.+?)_\d+$", uid)
    return match.group(1).replace("_", " ").title() if match else uid


def create_asset_collages(assets: list[dict], manager: AssetManager, stage: str) -> list[Image.Image]:
    """Create one collage per category, max 30 assets each, spill to new image if needed."""
    from io import BytesIO
    from collections import defaultdict
    from PIL import ImageDraw

    # Group assets by category
    by_category = defaultdict(list)
    for asset in assets:
        category = extract_category_from_uid(asset["uid"])
        by_category[category].append(asset)

    collages = []
    cell_h = THUMB_SIZE + LABEL_HEIGHT
    collage_width = COLS * THUMB_SIZE

    for cat in sorted(by_category.keys()):
        cat_assets = by_category[cat]

        # Split into batches of 30
        for batch_idx in range(0, len(cat_assets), ASSETS_PER_COLLAGE):
            batch = cat_assets[batch_idx : batch_idx + ASSETS_PER_COLLAGE]
            rows = (len(batch) + COLS - 1) // COLS
            collage_height = HEADER_HEIGHT + rows * cell_h
            collage = Image.new("RGB", (collage_width, collage_height), (255, 255, 255))
            draw = ImageDraw.Draw(collage)

            # Draw category header
            part = f" (part {batch_idx // ASSETS_PER_COLLAGE + 1})" if len(cat_assets) > ASSETS_PER_COLLAGE else ""
            draw.rectangle([0, 0, collage_width, HEADER_HEIGHT], fill=(70, 130, 180))
            draw.text((10, (HEADER_HEIGHT - 12) // 2), f"{cat} ({len(batch)}){part}", fill=(255, 255, 255))

            # Draw assets
            for i, asset in enumerate(batch):
                img_path = Path(asset.get("image_path", ""))
                col, row = i % COLS, i // COLS
                x, y = col * THUMB_SIZE, HEADER_HEIGHT + row * cell_h

                if img_path.exists():
                    with Image.open(img_path) as img:
                        img = img.convert("RGB")
                        img.thumbnail((THUMB_SIZE, THUMB_SIZE))
                        offset_x = (THUMB_SIZE - img.width) // 2
                        offset_y = (THUMB_SIZE - img.height) // 2
                        collage.paste(img, (x + offset_x, y + offset_y))

                draw.rectangle([x, y + THUMB_SIZE, x + THUMB_SIZE, y + cell_h], fill=(240, 240, 240))
                draw.text((x + 4, y + THUMB_SIZE + 2), asset["uid"][:25], fill=(0, 0, 0))

            buf = BytesIO()
            collage.save(buf, format="JPEG", quality=85)
            safe_cat = cat.lower().replace(" ", "_")
            manager.write_bytes(stage, f"collage_{safe_cat}_{batch_idx // ASSETS_PER_COLLAGE}.jpg", buf.getvalue())
            collages.append(collage)

    logger.info("Created %d category collages for %d categories", len(collages), len(by_category))
    return collages


def select_assets_llm_node(state: dict[str, Any]) -> dict[str, Any]:
    """Pure LLM-based asset selection optimizing for budget and room size.

    Supports revision mode when `asset_revision_prompt` is provided in state.
    """
    room_width, room_depth = state["room_area"]
    room_doors = state.get("room_doors", [])
    room_voids = state.get("room_voids", [])
    budget = state["budget"]

    total_area = room_width * room_depth
    door_clearance = sum(d.get("width", 0.9) * 0.8 for d in room_doors)
    void_area = sum(v.get("width", 0) * v.get("depth", 0) for v in room_voids)
    furniture_area = (total_area - door_clearance - void_area) * 0.7

    manager: AssetManager = state["asset_manager"]
    stage = STAGE_DIRS["select_assets"]

    # Revision mode: user wants to modify previous selection
    revision_prompt = state.get("asset_revision_prompt")
    previous_assets = state.get("selected_assets", [])

    # Build lookup for tool calls
    assets_by_uid = {a["uid"]: a for a in state["assets_data"]}

    # --- UPDATE 2: Strict Logic for Budget and 80% Footprint ---
    def validate_selection(uids: list[str]) -> dict:
        total_cost = 0
        total_footprint = 0
        not_found = []

        # Calculate totals (exclude rugs/carpets from footprint)
        for uid in uids:
            asset = assets_by_uid.get(uid)
            if asset:
                total_cost += asset.get("price", 0)
                if "rug" not in uid.lower() and "carpet" not in uid.lower():
                    total_footprint += asset.get("width", 0) * asset.get("depth", 0)
            else:
                not_found.append(uid)

        # Logic: Budget and 80% Area Limit
        max_allowed_footprint = furniture_area * 0.80
        is_over_budget = total_cost > budget
        is_over_crowded = total_footprint > max_allowed_footprint
        
        errors = []
        if is_over_budget:
            errors.append(f"OVER BUDGET: Selection costs ${total_cost:.2f} (Limit: ${budget:.2f}).")
        if is_over_crowded:
            errors.append(f"OVER CROWDED: Footprint is {total_footprint:.2f}m² (Limit: {max_allowed_footprint:.2f}m²).")

        is_valid = not (is_over_budget or is_over_crowded)

        return {
            "valid": is_valid,
            "status": "PASS" if is_valid else "FAIL - ADJUST SELECTION",
            "errors": errors,
            "metrics": {
                "total_cost": round(total_cost, 2),
                "remaining_budget": round(budget - total_cost, 2),
                "total_footprint": round(total_footprint, 2),
                "footprint_limit_80pct": round(max_allowed_footprint, 2)
            },
            "assets_not_found": not_found,
        }

    # Create collages from asset images (if enabled)
    collages = create_asset_collages(state["assets_data"], manager, stage) if ENABLE_ASSET_COLLAGE else []

    # Build previous selection context for revision mode
    previous_selection_context = ""
    if revision_prompt and previous_assets:
        prev_list = "\n".join(f"- {a['uid']}: {a.get('reason', '')}" for a in previous_assets)
        previous_selection_context = f"""
=== REVISION MODE ===
PREVIOUS SELECTION (DO NOT CHANGE unless explicitly requested):
{prev_list}

USER REVISION REQUEST: {revision_prompt}

CRITICAL REVISION RULES:
1. ONLY modify/replace assets that the user explicitly mentions in their request
2. PRESERVE ALL OTHER ASSETS EXACTLY as they were - same UIDs, same quantities
3. If user says "change the sofa", only change sofa items - keep all chairs, tables, rugs, etc. unchanged
4. If user says "add a plant", keep ALL existing items and add the plant
5. If user says "remove the rug", remove only rug items - keep everything else

Start with the PREVIOUS SELECTION as your base and make MINIMAL targeted changes.
"""
        logger.info("[ASSET SELECTOR LLM] Revision mode: %s", revision_prompt)

    prompt = f"""You are a furniture curator. Select assets for this room.
Use the attached collage images to visualize assets.

ROOM DATA:
- Dimensions: {room_width:.2f}m x {room_depth:.2f}m
- Usable furniture area: {furniture_area:.2f} sqm
- **MAXIMUM FOOTPRINT (80%): {furniture_area * 0.8:.2f} sqm** (Strict Limit)

BUDGET: ${budget:.2f} (Strict Limit)

USER INTENT: {state["user_intent"]}
{previous_selection_context}
ASSET CATALOG:
{state["assets_csv"]}

CRITICAL VALIDATION RULES:
1. **Total Cost MUST be <= ${budget:.2f}**
2. **Total Footprint MUST be <= {furniture_area * 0.8:.2f} sqm** (Do not overcrowd the room)
3. You MUST use the `validate_selection` tool to check your list.
4. **Important** Use the asset metadata columns to match user preferences:
   - `color`: Match colors mentioned in user intent (e.g. "beige", "white", "dark wood")
   - `style`: Match style preferences (e.g. "modern", "minimalist", "traditional")
   - `shape`: Consider shape when user mentions preferences (e.g. "round table", "L-shaped sofa")
   - `asset_description`: Full description for additional context

PROCESS:
1. Select essential items matching the user intent.
2. Call `validate_selection` with your list.
3. **IF THE TOOL RETURNS `valid: false`**:
   - Read the "errors" list.
   - If "OVER BUDGET": Remove least needed items.
   - If "OVER CROWDED": Remove least needed large items or switch to smaller alternatives.
   - **Call `validate_selection` again** with the updated list.
4. **IF THE TOOL RETURNS `valid: true` BUT `remaining_budget` is > 30% of original budget**:
   - You are under-utilizing the budget. Add more complementary items (decor, lighting, plants, rugs, accent pieces).
   - **Call `validate_selection` again** to verify the expanded selection still passes.
5. Repeat until `valid: true` and budget is well utilized.
6. You can select the same asset multiple times (e.g., 2x accent_chair_5 for a matching pair).
7. Output final JSON only when valid.

OUTPUT JSON FORMAT:
{{
  "selected_assets": [{{"uid": "...", "reason": "..."}}],
  "total_cost": number,
  "total_footprint_sqm": number,
  "selection_strategy": {{
    "summary": "Overall approach and rationale for the selection",
    "higher_budget_additions": "Suggested additions if user has more budget (e.g., upgrade sofa, add accent chairs, premium lighting)",
    "lower_budget_savings": "What to remove or swap for cheaper alternatives if user needs to save money",
    "gaps": "List each selected item where color/style/shape does NOT match user intent, with reason why (e.g. 'rug_15: grey instead of green - no green rugs available'). null only if ALL selected items match the intent"
  }}
}}"""

    manager.write_text(stage, "prompt_llm.txt", prompt)

    def pil_to_part(img: Image.Image) -> types.Part:
        from io import BytesIO
        buf = BytesIO()
        img.save(buf, format="JPEG")
        return types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")

    contents = [types.Part.from_text(text=prompt)] + [pil_to_part(c) for c in collages]

    start = time.perf_counter()

    # Agentic loop to handle tool calls
    for _ in range(MAX_TURNS):
        response = client.models.generate_content(
            model="gemini-3-flash-preview", contents=contents, config=LLM_SELECTOR_CONFIG
        )

        has_function_call = False
        parts = response.candidates[0].content.parts or []
        for part in parts:
            if part.function_call:
                has_function_call = True
                fc = part.function_call
                logger.info("[ASSET SELECTOR LLM] Tool call: %s", fc.name)

                if fc.name == "validate_selection":
                    result = validate_selection(fc.args.get("uids", []))
                    
                    # Enhanced logging for the new validation logic
                    status_log = "VALID" if result["valid"] else "INVALID"
                    logger.info("[ASSET SELECTOR LLM] Validation %s. Cost: $%.2f, Footprint: %.2fm²", 
                                status_log, result["metrics"]["total_cost"], result["metrics"]["total_footprint"])
                    
                    if not result["valid"]:
                        logger.warning("[ASSET SELECTOR LLM] Validation Errors: %s", result["errors"])

                    # Add assistant response and tool result to contents
                    contents.append(response.candidates[0].content)
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(
                            name=fc.name,
                            response=result
                        )]
                    ))
                break

        if not has_function_call:
            break

    # Force final text response if loop ended with function call
    if has_function_call:
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text="Provide your final JSON output now.")]
        ))
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=contents,
            config=LLM_SELECTOR_ENDING_CONFIG,
        )

    log_duration("ASSET SELECTOR LLM", start, response.usage_metadata)

    reasoning_trace, final_answer = extract_reasoning_trace(response)
    log_reasoning_trace(stage, reasoning_trace, manager, "reasoning_trace_llm.txt")

    text_content = final_answer
    if not text_content:
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                text_content = part.text
                break

    if not text_content:
        logger.warning("[ASSET SELECTOR LLM] No text response from LLM")
        manager.write_text(stage, "llm_response_error.txt", "No text response - LLM ended with function call")
        return {"selected_assets": []}

    try:
        parsed = json.loads(text_content)
    except Exception:
        manager.write_text(stage, "llm_response_error.json", text_content)
        return {"selected_assets": []}

    llm_selections = parsed.get("selected_assets", [])

    # Count duplicate UIDs
    uid_counts = {}
    for item in llm_selections:
        uid = item.get("uid")
        if uid:
            uid_counts[uid] = uid_counts.get(uid, 0) + 1

    # Hydrate to full asset objects and suffix duplicates
    selected_assets = []
    uid_instance = {}
    for item in llm_selections:
        uid = item.get("uid")
        if not uid or uid not in assets_by_uid:
            continue
        base_asset = assets_by_uid[uid]

        if uid_counts[uid] > 1:
            instance = uid_instance.get(uid, 0) + 1
            uid_instance[uid] = instance
            asset = {**base_asset, "uid": f"{uid}_{instance}", "reason": item.get("reason", "")}
        else:
            asset = {**base_asset, "reason": item.get("reason", "")}
        selected_assets.append(asset)

    parsed["total_selected"] = len(selected_assets)
    parsed["collages_sent"] = len(collages)
    manager.write_json(stage, "llm_selection.json", parsed)
    logger.info("[ASSET SELECTOR LLM] Selected %d assets using %d collages", len(selected_assets), len(collages))

    # Clear revision prompt after processing so graph doesn't loop indefinitely
    return {"selected_assets": selected_assets, "selection_strategy": parsed.get("selection_strategy", {}), "asset_revision_prompt": None}