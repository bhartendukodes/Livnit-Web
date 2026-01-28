"""
python main_layoutvlm.py --room_usdz dataset/room/Project-2510280721.usdz
"""

import argparse
import json
import time
import warnings
from pathlib import Path
from typing import Tuple

from pipeline.core.asset_manager import AssetManager
from pipeline.nodes.extract_room import extract_room_node
from pipeline.nodes.initial_layout import generate_initial_layout_node
from pipeline.nodes.layout_preview import layout_preview_node
from pipeline.nodes.refine_layout import refine_layout_node
from src.blender_placer import run_blender_process
from src.constants import DEFAULT_BLENDER_PATH
from src.layout_vlm_adaptor import run_layoutvlm_pipeline

warnings.filterwarnings("ignore", category=UserWarning)


def setup_directories(base_output_dir: Path) -> Tuple[Path, str]:
    """Creates necessary directories for the run based on timestamp."""
    time_str = time.strftime("%Y%m%d_%H%M%S")
    runs_dir = base_output_dir / time_str
    runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir, time_str


def scene_creation(args):
    # 1. Setup Paths
    usdz_path = Path(args.room_usdz).resolve()
    assets_dir = Path("assets")
    assets_dir.mkdir(exist_ok=True)

    layoutvlm_root = Path("LayoutVLM")
    assets_root = Path("assets/objaverse_processed")
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)

    runs_dir, time_str = setup_directories(outputs_dir)
    out_scene_path = outputs_dir / time_str / "scene.json"

    # Create asset manager and extract room geometry
    manager = AssetManager(runs_dir)
    room_state = extract_room_node({"asset_manager": manager, "usdz_path": str(usdz_path)})

    # Build state for layout pipeline
    state = {
        "asset_manager": manager,
        "usdz_path": str(usdz_path),
        "user_intent": args.user_prompt,
        **room_state,
        "selected_assets": [],
    }

    # Generate initial layout -> preview -> refine
    state.update(generate_initial_layout_node(state))
    state.update(layout_preview_node(state))
    data = refine_layout_node(state)

    with open(out_scene_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"[OK] Scene JSON saved → {out_scene_path}")

    print("\n[INFO] Running LayoutVLM...")
    layout_json = run_layoutvlm_pipeline(
        scene_json_in=str(out_scene_path),
        layoutvlm_root=layoutvlm_root,
        save_dir=runs_dir,
        openai_model="gpt-4o",
    )
    print(f"[OK] Layout JSON generated → {layout_json}")

    blender_exe = Path(args.blender_path) if args.blender_path else DEFAULT_BLENDER_PATH

    final_usdz = run_blender_process(
        blender_exe=blender_exe,
        usdz_path=usdz_path,
        layout_json=layout_json,
        assets_root=assets_root,
        runs_dir=runs_dir,
        outputs_dir=outputs_dir,
    )

    print("\n[PIPELINE COMPLETE]")
    print(f"→ Scene JSON: {out_scene_path}")
    print(f"→ Layout JSON: {layout_json}")
    if final_usdz:
        print(f"→ Final USDZ: {final_usdz}")

    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Scene Creation Pipeline")
    parser.add_argument(
        "--room_usdz", type=str, default="dataset/room/Project-2510280721.usdz"
    )
    parser.add_argument(
        "--user_prompt",
        type=str,
        default="Large sofa centered in the room, coffee table in front of the sofa, entertainment center on one wall.",
    )
    parser.add_argument(
        "--blender_path", type=str, help="Path to Blender executable", default=None
    )
    args = parser.parse_args()

    scene_creation(args)
