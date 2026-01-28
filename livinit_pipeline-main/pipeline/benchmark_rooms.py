"""
Benchmark script for testing asset selection and layout across different rooms.

Runs the pipeline from extract_room to initial_layout for all rooms in dataset/room.
"""

import argparse
import asyncio
import json
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from pipeline.core.asset_manager import AssetManager
from pipeline.core.pipeline_shared import STAGE_DIRS
from pipeline.nodes.extract_room import extract_room_node
from pipeline.nodes.init_vector_store import init_vector_store_node
from pipeline.nodes.initial_layout import generate_initial_layout_node
from pipeline.nodes.layout_preview import layout_preview_node
from pipeline.nodes.rag_scope_assets import rag_scope_assets_node
from pipeline.nodes.select_assets_llm import select_assets_llm_node
from pipeline.nodes.validate_and_cost import validate_and_cost_node

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


ROOM_STYLES = [
    "modern minimalist",
    "mid-century modern",
    "industrial",
    "scandinavian",
    "bohemian",
    "contemporary",
    "rustic farmhouse",
    "japandi",
]

ROOM_TYPES = [
    "living room",
    "bedroom",
    "home office",
    "studio apartment",
    "den",
    "guest room",
]

SPECIFIC_REQUESTS = [
    "with comfortable seating",
    "for working from home",
    "for entertaining guests",
    "with warm lighting",
    "with natural materials",
    "for relaxation",
    "with clean lines",
    "for a cozy atmosphere",
]


def generate_prompts(n: int, seed: int = 42) -> list[str]:
    """Generate n diverse design prompts."""
    random.seed(seed)
    prompts = []
    for _ in range(n):
        style = random.choice(ROOM_STYLES)
        room_type = random.choice(ROOM_TYPES)
        specific = random.choice(SPECIFIC_REQUESTS)
        prompts.append(f"{style} {room_type} {specific}")
    return prompts


def get_room_files(room_dir: Path) -> list[Path]:
    """Get all USDZ room files from directory."""
    return sorted(room_dir.glob("*.usdz"))


@dataclass
class RunMetrics:
    """Metrics for a single benchmark run."""
    room_file: str
    user_intent: str
    budget: float

    room_width: float = 0.0
    room_depth: float = 0.0
    room_area: float = 0.0
    num_doors: int = 0
    num_windows: int = 0
    num_voids: int = 0

    total_time_s: float = 0.0
    extract_room_time_s: float = 0.0
    rag_scope_time_s: float = 0.0
    select_assets_time_s: float = 0.0
    validate_cost_time_s: float = 0.0
    initial_layout_time_s: float = 0.0

    num_candidates: int = 0
    num_selected: int = 0
    categories_selected: list[str] = field(default_factory=list)

    actual_cost: float = 0.0
    budget_diff_pct: float = 0.0
    within_budget: bool = False

    layout_generated: bool = False
    all_assets_placed: bool = False
    assets_in_bounds: int = 0
    assets_out_of_bounds: int = 0

    error: str = ""
    success: bool = False


def check_layout_bounds(
    layout: dict[str, Any],
    selected_assets: list[dict[str, Any]],
    room_width: float,
    room_depth: float,
) -> dict[str, Any]:
    """Check how many assets are within room bounds."""
    assets_by_uid = {a["uid"]: a for a in selected_assets}
    in_bounds = out_of_bounds = 0
    placed_uids = set()

    for uid, placement in layout.items():
        placed_uids.add(uid)
        pos = placement.get("position", [0, 0, 0])
        x, y = pos[0], pos[1]
        asset = assets_by_uid.get(uid, {})
        hw, hd = asset.get("width", 0.5) / 2, asset.get("depth", 0.5) / 2

        # Asset center should be within room, with some tolerance for edges
        if -hw <= x <= room_width + hw and -hd <= y <= room_depth + hd:
            in_bounds += 1
        else:
            out_of_bounds += 1

    return {
        "in_bounds": in_bounds,
        "out_of_bounds": out_of_bounds,
        "all_placed": set(assets_by_uid.keys()) == placed_uids,
    }


def run_single_benchmark(
    room_file: Path,
    user_intent: str,
    budget: float,
    output_base: Path,
    run_id: int,
) -> RunMetrics:
    """Run pipeline for a single room/prompt combination."""
    metrics = RunMetrics(
        room_file=room_file.name,
        user_intent=user_intent,
        budget=budget,
    )

    run_dir = output_base / f"run_{run_id:03d}"
    manager = AssetManager(run_dir, max_runs=None)

    state = {
        "run_dir": str(run_dir),
        "asset_manager": manager,
        "user_intent": user_intent,
        "usdz_path": str(room_file),
        "budget": budget,
        "selected_assets": [],
        "selected_uids": [],
        "total_cost": 0.0,
        "room_area": (0, 0),
        "room_vertices": [],
        "room_doors": [],
        "room_windows": [],
        "room_voids": [],
        "initial_layout": {},
        "layout_preview_path": "",
    }

    start_time = time.perf_counter()

    try:
        # Extract room geometry
        t0 = time.perf_counter()
        updates = extract_room_node(state)
        state.update(updates)
        metrics.extract_room_time_s = time.perf_counter() - t0

        room_w, room_d = state["room_area"]
        metrics.room_width = room_w
        metrics.room_depth = room_d
        metrics.room_area = room_w * room_d
        metrics.num_doors = len(state.get("room_doors", []))
        metrics.num_windows = len(state.get("room_windows", []))
        metrics.num_voids = len(state.get("room_voids", []))

        # RAG scope assets
        t0 = time.perf_counter()
        updates = rag_scope_assets_node(state)
        state.update(updates)
        metrics.rag_scope_time_s = time.perf_counter() - t0
        metrics.num_candidates = len(state.get("assets_data", []))

        # Select assets
        t0 = time.perf_counter()
        updates = select_assets_llm_node(state)
        state.update(updates)
        metrics.select_assets_time_s = time.perf_counter() - t0

        # Validate and cost
        t0 = time.perf_counter()
        updates = validate_and_cost_node(state)
        state.update(updates)
        metrics.validate_cost_time_s = time.perf_counter() - t0

        selected = state.get("selected_assets", [])
        metrics.num_selected = len(selected)
        metrics.categories_selected = list(set(a.get("category", "?") for a in selected))
        metrics.actual_cost = state.get("total_cost", 0.0)
        if budget > 0:
            metrics.budget_diff_pct = ((metrics.actual_cost - budget) / budget) * 100
        metrics.within_budget = metrics.actual_cost <= budget

        # Initial layout
        t0 = time.perf_counter()
        updates = generate_initial_layout_node(state)
        state.update(updates)
        metrics.initial_layout_time_s = time.perf_counter() - t0

        layout = state.get("initial_layout", {})
        if layout:
            metrics.layout_generated = True
            bounds = check_layout_bounds(layout, selected, room_w, room_d)
            metrics.all_assets_placed = bounds["all_placed"]
            metrics.assets_in_bounds = bounds["in_bounds"]
            metrics.assets_out_of_bounds = bounds["out_of_bounds"]

        # Layout preview
        layout_preview_node(state)

        metrics.total_time_s = time.perf_counter() - start_time
        metrics.success = True

        manager.write_json(STAGE_DIRS["meta"], "benchmark_metrics.json", asdict(metrics))

    except Exception as e:
        import traceback
        metrics.total_time_s = time.perf_counter() - start_time
        metrics.error = str(e)
        metrics.success = False
        logger.error("Run %d failed: %s\n%s", run_id, e, traceback.format_exc())

    return metrics


RUN_TIMEOUT_S = 360


async def run_single_async(
    room_file: Path,
    user_intent: str,
    budget: float,
    output_base: Path,
    run_id: int,
    semaphore: asyncio.Semaphore,
    executor: ThreadPoolExecutor,
) -> RunMetrics:
    """Run single pipeline asynchronously."""
    async with semaphore:
        logger.info("[start] run_%03d %s: %s...", run_id, room_file.stem[:15], user_intent[:30])
        loop = asyncio.get_event_loop()
        try:
            metrics = await asyncio.wait_for(
                loop.run_in_executor(
                    executor, run_single_benchmark, room_file, user_intent, budget, output_base, run_id
                ),
                timeout=RUN_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            logger.warning("[timeout] run_%03d exceeded %ds", run_id, RUN_TIMEOUT_S)
            return RunMetrics(room_file=room_file.name, user_intent=user_intent, budget=budget, error=f"Timeout after {RUN_TIMEOUT_S}s", success=False)
        status = "OK" if metrics.success else f"FAIL: {metrics.error[:40]}"
        logger.info("[done] run_%03d %s: %s", run_id, room_file.stem[:15], status)
        return metrics


async def run_benchmark_async(
    room_files: list[Path],
    prompts: list[str],
    budgets: list[float],
    output_dir: Path,
    concurrency: int = 3,
) -> list[RunMetrics]:
    """Run pipelines concurrently using asyncio."""
    test_cases = [
        (room, prompt, budget, rid)
        for rid, (room, prompt, budget) in enumerate(
            (r, p, b) for r in room_files for p in prompts for b in budgets
        )
    ]

    total = len(test_cases)
    logger.info(
        "Starting benchmark: %d rooms x %d prompts x %d budgets = %d pipeline runs (concurrency=%d)",
        len(room_files), len(prompts), len(budgets), total, concurrency,
    )

    semaphore = asyncio.Semaphore(concurrency)
    executor = ThreadPoolExecutor(max_workers=concurrency)

    start = time.perf_counter()
    tasks = [
        run_single_async(room, prompt, budget, output_dir, rid, semaphore, executor)
        for room, prompt, budget, rid in test_cases
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.perf_counter() - start

    executor.shutdown(wait=False)

    final = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            room, prompt, budget, rid = test_cases[i]
            final.append(RunMetrics(room_file=room.name, user_intent=prompt, budget=budget, error=str(r), success=False))
        else:
            final.append(r)

    logger.info("Benchmark done: %d pipelines in %.1fs (%.1fs avg)", total, elapsed, elapsed / total if total else 0)
    return final


def generate_report(results: list[RunMetrics]) -> dict[str, Any]:
    """Generate summary report."""
    ok = [r for r in results if r.success]
    fail = [r for r in results if not r.success]

    if not ok:
        return {"error": "No successful runs", "failed": len(fail)}

    budget_diffs = [r.budget_diff_pct for r in ok]
    times = [r.total_time_s for r in ok]
    in_bounds = [r.assets_in_bounds for r in ok if r.layout_generated]
    out_bounds = [r.assets_out_of_bounds for r in ok if r.layout_generated]

    return {
        "summary": {
            "total": len(results),
            "success": len(ok),
            "failed": len(fail),
            "success_rate_pct": len(ok) / len(results) * 100,
        },
        "rooms": {
            "unique_rooms": len(set(r.room_file for r in ok)),
            "mean_area_m2": sum(r.room_area for r in ok) / len(ok),
        },
        "budget": {
            "within_budget_pct": sum(1 for r in ok if r.within_budget) / len(ok) * 100,
            "mean_diff_pct": sum(budget_diffs) / len(budget_diffs),
            "max_over_pct": max(budget_diffs),
            "max_under_pct": min(budget_diffs),
        },
        "assets": {
            "mean_selected": sum(r.num_selected for r in ok) / len(ok),
            "min_selected": min(r.num_selected for r in ok),
            "max_selected": max(r.num_selected for r in ok),
        },
        "layout": {
            "generated_pct": sum(1 for r in ok if r.layout_generated) / len(ok) * 100,
            "all_placed_pct": sum(1 for r in ok if r.all_assets_placed) / len(ok) * 100,
            "mean_in_bounds": sum(in_bounds) / len(in_bounds) if in_bounds else 0,
            "mean_out_of_bounds": sum(out_bounds) / len(out_bounds) if out_bounds else 0,
        },
        "timing": {
            "mean_s": sum(times) / len(times),
            "min_s": min(times),
            "max_s": max(times),
            "total_s": sum(times),
        },
        "by_room": {
            room: {
                "count": len([r for r in ok if r.room_file == room]),
                "mean_area": sum(r.room_area for r in ok if r.room_file == room) / max(1, len([r for r in ok if r.room_file == room])),
                "success_rate": len([r for r in ok if r.room_file == room]) / max(1, len([r for r in results if r.room_file == room])) * 100,
            }
            for room in set(r.room_file for r in results)
        },
    }


def print_report(report: dict[str, Any]) -> None:
    """Print formatted report."""
    print("\n" + "=" * 60)
    print("ROOM BENCHMARK REPORT")
    print("=" * 60)

    if "error" in report:
        print(f"\nERROR: {report['error']}")
        return

    s = report["summary"]
    print(f"\nSUMMARY: {s['success']}/{s['total']} runs ({s['success_rate_pct']:.0f}% success)")

    r = report["rooms"]
    print(f"\nROOMS: {r['unique_rooms']} unique, mean area {r['mean_area_m2']:.1f}m²")

    b = report["budget"]
    print(f"\nBUDGET: {b['within_budget_pct']:.0f}% within budget, mean diff {b['mean_diff_pct']:+.1f}%")

    a = report["assets"]
    print(f"\nASSETS: mean {a['mean_selected']:.1f} selected (range {a['min_selected']}-{a['max_selected']})")

    ly = report["layout"]
    print(f"\nLAYOUT: {ly['generated_pct']:.0f}% generated, {ly['all_placed_pct']:.0f}% all placed")
    print(f"  In bounds: {ly['mean_in_bounds']:.1f}, Out: {ly['mean_out_of_bounds']:.1f}")

    t = report["timing"]
    print(f"\nTIMING: mean {t['mean_s']:.1f}s, total {t['total_s']:.0f}s ({t['total_s']/60:.1f}min)")

    print("\nBY ROOM:")
    for room, data in report.get("by_room", {}).items():
        print(f"  {room[:30]:30} n={data['count']:2} area={data['mean_area']:.1f}m² ok={data['success_rate']:.0f}%")

    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark asset selection across rooms")
    parser.add_argument("--room-dir", type=str, default="dataset/room", help="Room USDZ directory")
    parser.add_argument("--num-prompts", type=int, default=3, help="Prompts per room")
    parser.add_argument("--budgets", type=str, default="3000,5000,10000", help="Comma-separated budgets")
    parser.add_argument("--output-dir", type=str, default="benchmark_room_outputs", help="Output directory")
    parser.add_argument("--concurrency", type=int, default=3, help="Parallel runs")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    room_files = get_room_files(Path(args.room_dir))
    if not room_files:
        print(f"No USDZ files in {args.room_dir}")
        exit(1)

    prompts = generate_prompts(args.num_prompts, args.seed)
    budgets = [float(b) for b in args.budgets.split(",")]

    output_dir = Path(args.output_dir) / time.strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save config
    config = {"rooms": [str(r) for r in room_files], "prompts": prompts, "budgets": budgets}
    with open(output_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    logger.info("Rooms: %s", [r.name for r in room_files])
    logger.info("Prompts: %s", prompts)
    logger.info("Budgets: %s", budgets)

    # Initialize vector store once before all runs
    init_vector_store_node({})

    results = asyncio.run(run_benchmark_async(room_files, prompts, budgets, output_dir, args.concurrency))

    # Save results
    with open(output_dir / "results.json", "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    report = generate_report(results)
    with open(output_dir / "report.json", "w") as f:
        json.dump(report, f, indent=2)

    print_report(report)
    logger.info("Results saved to %s", output_dir)
