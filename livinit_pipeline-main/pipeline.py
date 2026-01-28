import argparse
import logging
import time
from pathlib import Path
from typing import Any, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from pipeline.core.asset_manager import AssetManager
from pipeline.core.pipeline_shared import STAGE_DIRS
from pipeline.nodes.load_assets import load_assets_node
from pipeline.nodes.extract_room import extract_room_node
from pipeline.nodes.init_vector_store import init_vector_store_node
from pipeline.nodes.rag_scope_assets import rag_scope_assets_node
from pipeline.nodes.run_layoutvlm import run_layoutvlm_node
from pipeline.nodes.select_assets_llm import select_assets_llm_node
from pipeline.nodes.validate_and_cost import validate_and_cost_node
from pipeline.nodes.initial_layout import generate_initial_layout_node
from pipeline.nodes.layout_preview import layout_preview_node
from pipeline.nodes.refine_layout import refine_layout_node

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()


class PipelineState(TypedDict):
    run_dir: str
    asset_manager: Any
    user_intent: str
    usdz_path: str
    budget: float
    room_area: tuple[float, float]
    room_vertices: list[list[float]]
    room_doors: list[dict[str, Any]]
    room_windows: list[dict[str, Any]]
    room_voids: list[dict[str, Any]]
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
    # Flow: initial_layout -> layout_preview -> refine_layout -> layoutvlm
    nodes = {
        "load_assets": load_assets_node,
        "extract_room": extract_room_node,
        "init_vector_store": init_vector_store_node,
        "rag_scope_assets": rag_scope_assets_node,
        "select_assets": select_assets_llm_node,
        "validate_and_cost": validate_and_cost_node,
        "generate_initial_layout": generate_initial_layout_node,
        "layout_preview": layout_preview_node,
        "refine_layout": refine_layout_node,
        "run_layoutvlm": run_layoutvlm_node,
    }

    for name, func in nodes.items():
        graph.add_node(name, func)

    for i in range(len(nodes) - 1):
        if i == 0:
            graph.set_entry_point(list(nodes.keys())[i])
        graph.add_edge(list(nodes.keys())[i], list(nodes.keys())[i + 1])
    graph.add_edge(list(nodes.keys())[-1], END)

    return graph.compile()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactive", action="store_true", help="Prompt for inputs instead of using defaults.")
    args = parser.parse_args()

    default_intent = "Modern minimalist living room"
    default_budget = 5000.0
    default_usdz_path = "dataset/room/Project-2510280721.usdz"

    if args.interactive:
        user_intent = input(f"Enter your design intent [{default_intent}]: ") or default_intent
        budget = float(input(f"Enter budget ($) [{default_budget}]: ") or default_budget)
    else:
        user_intent = default_intent
        budget = default_budget

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    run_dir = Path("runs") / timestamp
    manager = AssetManager(run_dir)
    manager.write_json(STAGE_DIRS["meta"], "run_meta.json", {
        "timestamp": timestamp,
        "user_intent": user_intent,
        "budget": budget,
    })

    graph = build_graph()
    final_state = graph.invoke({
        "run_dir": str(run_dir),
        "asset_manager": manager,
        "user_intent": user_intent,
        "usdz_path": default_usdz_path,
        "budget": budget,
    })

    serializable_state = {k: v for k, v in final_state.items() if k != "asset_manager"}
    manager.write_json(STAGE_DIRS["meta"], "final_state.json", serializable_state)
    logger.info("Selected assets: %s", final_state["selected_uids"])
    logger.info("Room: %.2fm x %.2fm", final_state["room_area"][0], final_state["room_area"][1])
    logger.info("Refined layout: %s", final_state.get("refined_layout"))
    logger.info("LayoutVLM layout: %s", final_state.get("layoutvlm_layout"))
