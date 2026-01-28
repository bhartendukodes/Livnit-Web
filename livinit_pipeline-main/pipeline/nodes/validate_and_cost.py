import time
import logging
from typing import Any
from pipeline.core.asset_manager import AssetManager
from pipeline.core.pipeline_shared import STAGE_DIRS, log_duration

logger = logging.getLogger(__name__)


def validate_and_cost_node(state: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    selected_assets = state["selected_assets"]  # Already hydrated with full asset data

    for asset in selected_assets:
        logger.info("  %s: $%s", asset["uid"], asset.get("price", 0.0))

    total = sum(asset.get("price", 0.0) or 0.0 for asset in selected_assets)
    budget = state["budget"]
    logger.info("[VALIDATE] Selected %d assets, total: $%.2f (budget: $%.2f)", len(selected_assets), total, budget)
    if total > budget:
        logger.warning("[VALIDATE] Cost $%.2f exceeds budget $%.2f", total, budget)

    # Validate footprint (exclude rugs) against usable furniture area
    room_width, room_depth = state["room_area"]
    room_doors = state.get("room_doors", [])
    room_voids = state.get("room_voids", [])
    pathway_width = 0.8
    door_clearance = sum(d.get("width", 0.9) * pathway_width for d in room_doors)
    void_area = sum(v.get("width", 0) * v.get("depth", 0) for v in room_voids)
    total_area = room_width * room_depth
    usable = total_area - door_clearance - void_area
    furniture_area = usable * 0.7  # reserve 30% for circulation

    total_footprint = sum(
        (a.get("width", 0) or 0) * (a.get("depth", 0) or 0)
        for a in selected_assets
        if "rug" not in (a.get("type") or a.get("uid", "")).lower()
    )
    if total_footprint > furniture_area:
        logger.warning(
            "[VALIDATE] Footprint %.2f sqm exceeds furniture area %.2f sqm - insufficient pathway",
            total_footprint, furniture_area
        )

    manager: AssetManager = state["asset_manager"]
    manager.write_json(
        STAGE_DIRS["validate_and_cost"],
        "selected_assets.json",
        {
            "total_selected": len(selected_assets),
            "selected_assets": selected_assets,
            "selected_uids": [asset["uid"] for asset in selected_assets],
            "total_cost": total,
            "budget": budget,
            "budget_valid": total <= budget,
            "total_footprint_sqm": total_footprint,
            "furniture_area_sqm": furniture_area,
            "pathway_valid": total_footprint <= furniture_area,
        },
    )
    log_duration("VALIDATE & COST", start)

    return {
        "selected_assets": selected_assets,
        "selected_uids": [asset["uid"] for asset in selected_assets],
        "total_cost": total,
        "budget_valid": total <= budget,
        "total_footprint_sqm": total_footprint,
        "pathway_valid": total_footprint <= furniture_area,
    }
