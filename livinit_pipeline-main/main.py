import argparse
import logging
import time
from pathlib import Path
from typing import Any, TypedDict


from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from pipeline.core.asset_manager import AssetManager
from pipeline.core.pipeline_shared import STAGE_DIRS
from pipeline.nodes.initial_layout import generate_initial_layout_node
from pipeline.nodes.layout_preview import layout_preview_node
from pipeline.nodes.refine_layout import refine_layout_node
from pipeline.nodes.load_assets import load_assets_node
from pipeline.nodes.run_layoutvlm import run_layoutvlm_node
from pipeline.nodes.select_assets import select_assets_node
from pipeline.nodes.validate_and_cost import validate_and_cost_node

"""
LangGraph-based pipeline for furniture selection and layout generation.
"""

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

load_dotenv()


class PipelineState(TypedDict):
    run_dir: str
    asset_manager: Any
    user_intent: str
    budget: float
    room_area: tuple[float, float]
    assets_csv: str
    assets_data: list[dict[str, Any]]
    selected_assets: list[dict[str, Any]]
    selected_uids: list[str]
    total_cost: float
    task_description: str
    constraint_program: str
    layout_groups: list[dict[str, Any]]
    initial_layout: dict[str, Any]
    refined_layout: dict[str, Any]
    layoutvlm_layout: dict[str, Any]
    layout_preview_path: str
    boundary: dict[str, Any]
    assets: dict[str, Any]
    void_assets: dict[str, Any]


def build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("load_assets", load_assets_node)
    graph.add_node("select_assets", select_assets_node)
    graph.add_node("validate_and_cost", validate_and_cost_node)
    graph.add_node("generate_initial_layout", generate_initial_layout_node)
    graph.add_node("layout_preview", layout_preview_node)
    graph.add_node("refine_layout", refine_layout_node)
    graph.add_node("run_layoutvlm", run_layoutvlm_node)

    graph.set_entry_point("load_assets")
    graph.add_edge("load_assets", "select_assets")
    graph.add_edge("select_assets", "validate_and_cost")
    graph.add_edge("validate_and_cost", "generate_initial_layout")
    graph.add_edge("generate_initial_layout", "layout_preview")
    graph.add_edge("layout_preview", "refine_layout")
    graph.add_edge("refine_layout", "run_layoutvlm")
    graph.add_edge("run_layoutvlm", END)

    return graph.compile()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", action="store_true", help="Prompt for inputs instead of using defaults.")
    args = parser.parse_args()

    default_intent = "Modern minimalist living room"
    default_budget = 1500.0
    default_room_width = 5.0
    default_room_depth = 6.0

    if args.interactive:
        user_intent = input(f"Enter your design intent [{default_intent}]: ") or default_intent
        budget = float(input(f"Enter budget ($) [{default_budget}]: ") or default_budget)
        room_width = float(input(f"Enter room width (m) [{default_room_width}]: ") or default_room_width)
        room_depth = float(input(f"Enter room depth (m) [{default_room_depth}]: ") or default_room_depth)
    else:
        user_intent = default_intent
        budget = default_budget
        room_width = default_room_width
        room_depth = default_room_depth

    room_area = (room_width, room_depth)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    run_dir = Path("runs") / timestamp
    manager = AssetManager(run_dir)
    manager.write_json(
        STAGE_DIRS["meta"],
        "run_meta.json",
        {
            "timestamp": timestamp,
            "user_intent": user_intent,
            "budget": budget,
            "room_area": room_area,
        },
    )
    graph = build_graph()
    final_state = graph.invoke(
        {
            "run_dir": str(run_dir),
            "asset_manager": manager,
            "user_intent": user_intent,
            "budget": budget,
            "room_area": room_area,
            "assets_csv": "",
            "assets_data": [],
            "selected_assets": [],
            "selected_uids": [],
            "total_cost": 0.0,
            "task_description": "",
            "constraint_program": "",
            "layout_groups": [],
            "initial_layout": {},
            "refined_layout": {},
            "layoutvlm_layout": {},
            "layout_preview_path": "",
            "boundary": {},
            "assets": {},
            "void_assets": {},
        }
    )
    serializable_state = {k: v for k, v in final_state.items() if k != "asset_manager"}
    manager.write_json(STAGE_DIRS["meta"], "final_state.json", serializable_state)
    logger.info("Selected assets: %s", final_state["selected_uids"])
    logger.info("Task description: %s", final_state["task_description"])
    logger.info("Constraint program:\n%s", final_state.get("constraint_program", ""))
    logger.info("Layout groups: %s", final_state["layout_groups"])
    logger.info("Initial layout: %s", final_state["initial_layout"])
    logger.info("Refined layout: %s", final_state.get("refined_layout"))
    logger.info("Layout preview saved to: %s", final_state["layout_preview_path"])
    logger.info("LayoutVLM layout: %s", final_state.get("layoutvlm_layout"))
