import logging
import time
from typing import Any

STAGE_DIRS = {
    "meta": "meta",
    "load_assets": "load_assets",
    "rag_scope": "rag_scope",
    "select_assets": "select_assets",
    "validate_and_cost": "validate_and_cost",
    "initial_layout": "initial_layout",
    "draw_layout_preview": "draw_layout_preview",
    "layoutvlm": "layoutvlm",
    "refine_layout": "refine_layout",
    "render_scene": "render_scene",
}

logger = logging.getLogger(__name__)


def log_duration(stage: str, start_time: float, usage: Any | None = None) -> None:
    elapsed = time.perf_counter() - start_time
    if usage is not None:
        logger.info("[%s] Time: %.2fs, Usage: %s", stage, elapsed, usage)
        return
    logger.info("[%s] Time: %.2fs", stage, elapsed)
