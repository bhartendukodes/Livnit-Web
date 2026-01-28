"""
Benchmark script for the furniture selection and layout pipeline.

Runs 100 diverse test cases and collects metrics on:
- Budget vs actual cost accuracy
- Asset selection quality
- Layout generation performance
- LP optimization effectiveness
"""

import argparse
import asyncio
import json
import logging
import math
import os
import random
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

from core.asset_manager import AssetManager
from core.pipeline_shared import STAGE_DIRS
from main import PipelineState
from nodes.initial_layout import generate_initial_layout_node
from nodes.layout_preview import layout_preview_node
from nodes.refine_layout import refine_layout_node
from nodes.load_assets import load_assets_node
from nodes.select_assets_llm import select_assets_llm_node
from nodes.validate_and_cost import validate_and_cost_node

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Test Case Definitions
# =============================================================================

ROOM_STYLES = [
    "modern minimalist",
    "mid-century modern",
    "industrial",
    "scandinavian",
    "bohemian",
    "traditional",
    "contemporary",
    "rustic farmhouse",
    "art deco",
    "coastal",
    "japandi",
    "eclectic",
    "transitional",
]

ROOM_TYPES = [
    "living room",
    "bedroom",
    "home office",
    "studio apartment",
    "den",
    "guest room",
    "reading nook",
    "entertainment room",
    "open concept living space",
    "small apartment",
]

SPECIFIC_REQUESTS = [
    "with comfortable seating",
    "for working from home",
    "for entertaining guests",
    "with warm lighting",
    "with natural materials",
    "with storage solutions",
    "for relaxation",
    "with accent pieces",
    "for a cozy atmosphere",
    "with clean lines",
    "for small space living",
    "with bold colors",
    "with neutral tones",
    "for a young professional",
    "for a family",
]

COLOR_PREFERENCES = [
    "walnut tones",
    "white and grey",
    "earth tones",
    "black and white",
    "warm wood finishes",
    "cool blue accents",
    "green and natural",
    "muted pastels",
    "bold jewel tones",
    "",  # no color preference
]


def generate_test_cases(n: int = 100, seed: int = 42) -> list[dict[str, Any]]:
    """Generate n diverse test cases for benchmarking."""
    random.seed(seed)
    test_cases = []

    # Room size distributions (width, depth in meters)
    room_sizes = [
        # Small rooms
        {"min_w": 2.5, "max_w": 3.5, "min_d": 3.0, "max_d": 4.0, "label": "small"},
        # Medium rooms
        {"min_w": 3.5, "max_w": 5.0, "min_d": 4.0, "max_d": 6.0, "label": "medium"},
        # Large rooms
        {"min_w": 5.0, "max_w": 7.0, "min_d": 6.0, "max_d": 8.0, "label": "large"},
    ]

    # Budget distributions (100 to 100000)
    budget_ranges = [
        {"min": 100, "max": 500, "label": "budget"},
        {"min": 500, "max": 2000, "label": "low"},
        {"min": 2000, "max": 8000, "label": "medium"},
        {"min": 8000, "max": 30000, "label": "high"},
        {"min": 30000, "max": 100000, "label": "premium"},
    ]

    for i in range(n):
        # Select room style and type
        style = random.choice(ROOM_STYLES)
        room_type = random.choice(ROOM_TYPES)
        specific = random.choice(SPECIFIC_REQUESTS)
        color = random.choice(COLOR_PREFERENCES)

        # Build user intent
        if color:
            intent = f"{style} {room_type} {specific} with {color}"
        else:
            intent = f"{style} {room_type} {specific}"

        # Select room size
        size_cat = random.choice(room_sizes)
        width = round(random.uniform(size_cat["min_w"], size_cat["max_w"]), 2)
        depth = round(random.uniform(size_cat["min_d"], size_cat["max_d"]), 2)

        # Select budget (correlated with room size somewhat)
        if size_cat["label"] == "small":
            budget_cat = random.choice(budget_ranges[:3])  # lower budgets for small rooms
        elif size_cat["label"] == "large":
            budget_cat = random.choice(budget_ranges[2:])  # higher budgets for large rooms
        else:
            budget_cat = random.choice(budget_ranges)

        budget = round(random.uniform(budget_cat["min"], budget_cat["max"]), 2)

        test_cases.append({
            "id": i + 1,
            "user_intent": intent,
            "budget": budget,
            "room_width": width,
            "room_depth": depth,
            "room_size_category": size_cat["label"],
            "budget_category": budget_cat["label"],
        })

    return test_cases


# =============================================================================
# Metrics Collection
# =============================================================================

@dataclass
class RunMetrics:
    """Metrics for a single benchmark run."""
    test_id: int
    user_intent: str
    budget: float
    room_width: float
    room_depth: float
    room_area: float = 0.0

    # Timing
    total_time_s: float = 0.0
    load_assets_time_s: float = 0.0
    select_assets_time_s: float = 0.0
    validate_cost_time_s: float = 0.0
    initial_layout_time_s: float = 0.0
    refine_layout_time_s: float = 0.0

    # Asset selection
    num_candidates: int = 0
    num_selected: int = 0
    categories_selected: list[str] = field(default_factory=list)

    # Cost metrics
    actual_cost: float = 0.0
    budget_diff: float = 0.0
    budget_diff_pct: float = 0.0
    within_budget: bool = False
    within_10pct: bool = False

    # LP optimization
    lp_success: bool = False
    lp_objective: float = 0.0

    # Preference score metrics
    total_preference_score: float = 0.0
    mean_preference_score: float = 0.0
    min_preference_score: float = 0.0
    max_preference_score: float = 0.0
    preference_scores: list[float] = field(default_factory=list)

    # Layout metrics
    layout_generated: bool = False
    all_assets_placed: bool = False
    assets_in_bounds: int = 0
    assets_out_of_bounds: int = 0

    # Errors
    error: str = ""
    success: bool = False


def calculate_layout_metrics(
    layout: dict[str, Any],
    selected_assets: list[dict[str, Any]],
    room_area: tuple[float, float],
) -> dict[str, Any]:
    """Calculate metrics about the generated layout."""
    width, depth = room_area
    assets_by_uid = {a["uid"]: a for a in selected_assets}

    in_bounds = 0
    out_of_bounds = 0
    placed_uids = set()

    for uid, placement in layout.items():
        placed_uids.add(uid)
        pos = placement.get("position", [0, 0, 0])
        if len(pos) >= 2:
            x, y = pos[0], pos[1]
            asset = assets_by_uid.get(uid, {})
            asset_w = asset.get("width", 0.5) / 2
            asset_d = asset.get("depth", 0.5) / 2

            # Check if asset center + half dimensions is within room
            if 0 <= x <= width and 0 <= y <= depth:
                in_bounds += 1
            else:
                out_of_bounds += 1

    all_placed = set(assets_by_uid.keys()) == placed_uids

    return {
        "in_bounds": in_bounds,
        "out_of_bounds": out_of_bounds,
        "all_placed": all_placed,
    }


# =============================================================================
# Pipeline Builder
# =============================================================================

def build_benchmark_graph() -> StateGraph:
    """Build pipeline graph that runs up to refine_layout."""
    graph = StateGraph(PipelineState)

    graph.add_node("load_assets", load_assets_node)
    graph.add_node("select_assets", select_assets_llm_node)
    graph.add_node("validate_and_cost", validate_and_cost_node)
    graph.add_node("generate_initial_layout", generate_initial_layout_node)
    graph.add_node("layout_preview", layout_preview_node)
    graph.add_node("refine_layout", refine_layout_node)

    graph.set_entry_point("load_assets")
    graph.add_edge("load_assets", "select_assets")
    graph.add_edge("select_assets", "validate_and_cost")
    graph.add_edge("validate_and_cost", "generate_initial_layout")
    graph.add_edge("generate_initial_layout", "layout_preview")
    graph.add_edge("layout_preview", "refine_layout")
    graph.add_edge("refine_layout", END)

    return graph.compile()


# =============================================================================
# Benchmark Runner
# =============================================================================

def run_single_benchmark(
    test_case: dict[str, Any],
    graph,
    output_base: Path,
) -> RunMetrics:
    """Run a single benchmark test case and collect metrics."""
    metrics = RunMetrics(
        test_id=test_case["id"],
        user_intent=test_case["user_intent"],
        budget=test_case["budget"],
        room_width=test_case["room_width"],
        room_depth=test_case["room_depth"],
        room_area=test_case["room_width"] * test_case["room_depth"],
    )

    run_dir = output_base / f"test_{test_case['id']:03d}"
    manager = AssetManager(run_dir, max_runs=None)

    initial_state = {
        "run_dir": str(run_dir),
        "asset_manager": manager,
        "user_intent": test_case["user_intent"],
        "budget": test_case["budget"],
        "room_area": (test_case["room_width"], test_case["room_depth"]),
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
    }

    start_time = time.perf_counter()

    try:
        logger.debug("Invoking graph with state keys: %s", list(initial_state.keys()))
        final_state = graph.invoke(initial_state)
        logger.debug("Graph completed, final state keys: %s", list(final_state.keys()))
        metrics.total_time_s = time.perf_counter() - start_time

        # Extract metrics from final state
        selected_assets = final_state.get("selected_assets", [])
        metrics.num_selected = len(selected_assets)
        metrics.categories_selected = list(set(a.get("category", "unknown") for a in selected_assets))

        # Cost metrics
        metrics.actual_cost = final_state.get("total_cost", 0.0)
        metrics.budget_diff = metrics.actual_cost - metrics.budget
        if metrics.budget > 0:
            metrics.budget_diff_pct = (metrics.budget_diff / metrics.budget) * 100
        metrics.within_budget = metrics.actual_cost <= metrics.budget
        metrics.within_10pct = abs(metrics.budget_diff_pct) <= 10

        # Try to read LP optimization results
        lp_file = run_dir / STAGE_DIRS["select_assets"] / "lp_optimization.json"
        if lp_file.exists():
            with open(lp_file) as f:
                lp_data = json.load(f)
                metrics.lp_success = lp_data.get("status") == "success"
                metrics.lp_objective = lp_data.get("objective_value", 0.0)

        # Try to read candidates count and preference scores
        candidates_file = run_dir / STAGE_DIRS["select_assets"] / "candidates.json"
        if candidates_file.exists():
            with open(candidates_file) as f:
                cand_data = json.load(f)
                candidates = cand_data.get("candidates", [])
                metrics.num_candidates = len(candidates)

                # Get preference scores for selected assets
                selected_uids = set(final_state.get("selected_uids", []))
                selected_scores = [
                    c.get("preference_score", 0)
                    for c in candidates
                    if c.get("uid") in selected_uids
                ]
                if selected_scores:
                    metrics.preference_scores = selected_scores
                    metrics.total_preference_score = sum(selected_scores)
                    metrics.mean_preference_score = sum(selected_scores) / len(selected_scores)
                    metrics.min_preference_score = min(selected_scores)
                    metrics.max_preference_score = max(selected_scores)

        # Layout metrics (prefer refined_layout over initial_layout)
        layout = final_state.get("refined_layout") or final_state.get("initial_layout", {})
        if layout:
            metrics.layout_generated = True
            layout_metrics = calculate_layout_metrics(
                layout,
                selected_assets,
                (test_case["room_width"], test_case["room_depth"]),
            )
            metrics.all_assets_placed = layout_metrics["all_placed"]
            metrics.assets_in_bounds = layout_metrics["in_bounds"]
            metrics.assets_out_of_bounds = layout_metrics["out_of_bounds"]

        metrics.success = True

        # Save metrics to run directory
        manager.write_json(STAGE_DIRS["meta"], "benchmark_metrics.json", asdict(metrics))

    except Exception as e:
        metrics.total_time_s = time.perf_counter() - start_time
        metrics.error = str(e)
        metrics.success = False
        logger.error("Test %d failed: %s\n%s", test_case["id"], e, traceback.format_exc())

    return metrics


def run_benchmark(
    test_cases: list[dict[str, Any]],
    output_dir: Path,
    max_tests: int | None = None,
) -> list[RunMetrics]:
    """Run the full benchmark suite sequentially."""
    graph = build_benchmark_graph()
    results = []

    if max_tests:
        test_cases = test_cases[:max_tests]

    total = len(test_cases)
    logger.info("Starting benchmark with %d test cases (sequential)", total)

    for i, test_case in enumerate(test_cases):
        logger.info(
            "[%d/%d] Running test %d: %s (budget=$%.2f, room=%.1fx%.1f)",
            i + 1,
            total,
            test_case["id"],
            test_case["user_intent"][:50] + "...",
            test_case["budget"],
            test_case["room_width"],
            test_case["room_depth"],
        )

        metrics = run_single_benchmark(test_case, graph, output_dir)
        results.append(metrics)

        if metrics.success:
            logger.info(
                "  -> Success: cost=$%.2f (budget=$%.2f, diff=%.1f%%), %d assets selected",
                metrics.actual_cost,
                metrics.budget,
                metrics.budget_diff_pct,
                metrics.num_selected,
            )
        else:
            logger.warning("  -> Failed: %s", metrics.error[:100])

    return results


# =============================================================================
# Async Parallel Benchmark Runner
# =============================================================================

async def run_single_benchmark_async(
    test_case: dict[str, Any],
    graph,
    output_base: Path,
    semaphore: asyncio.Semaphore,
    executor: ThreadPoolExecutor,
    progress: dict[str, int],
) -> RunMetrics:
    """Run a single benchmark test case asynchronously."""
    async with semaphore:
        loop = asyncio.get_event_loop()

        # Log start
        progress["started"] += 1
        logger.info(
            "[%d/%d started, %d done] Test %d: %s (budget=$%.2f)",
            progress["started"],
            progress["total"],
            progress["done"],
            test_case["id"],
            test_case["user_intent"][:40] + "...",
            test_case["budget"],
        )

        # Run the synchronous benchmark in a thread pool
        metrics = await loop.run_in_executor(
            executor,
            run_single_benchmark,
            test_case,
            graph,
            output_base,
        )

        # Log completion
        progress["done"] += 1
        if metrics.success:
            logger.info(
                "[%d/%d done] Test %d: SUCCESS cost=$%.2f (diff=%.1f%%)",
                progress["done"],
                progress["total"],
                test_case["id"],
                metrics.actual_cost,
                metrics.budget_diff_pct,
            )
        else:
            logger.warning(
                "[%d/%d done] Test %d: FAILED - %s",
                progress["done"],
                progress["total"],
                test_case["id"],
                metrics.error[:60],
            )

        return metrics


async def run_benchmark_async(
    test_cases: list[dict[str, Any]],
    output_dir: Path,
    max_tests: int | None = None,
    concurrency: int = 5,
) -> list[RunMetrics]:
    """Run the full benchmark suite with parallel execution."""
    graph = build_benchmark_graph()

    if max_tests:
        test_cases = test_cases[:max_tests]

    total = len(test_cases)
    logger.info(
        "Starting benchmark with %d test cases (parallel, concurrency=%d)",
        total,
        concurrency,
    )

    # Semaphore to limit concurrency
    semaphore = asyncio.Semaphore(concurrency)

    # Thread pool for running sync code
    executor = ThreadPoolExecutor(max_workers=concurrency)

    # Progress tracking
    progress = {"total": total, "started": 0, "done": 0}

    # Create tasks for all test cases
    tasks = [
        run_single_benchmark_async(tc, graph, output_dir, semaphore, executor, progress)
        for tc in test_cases
    ]

    # Run all tasks concurrently
    start_time = time.perf_counter()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.perf_counter() - start_time

    # Handle any exceptions that were returned
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error("Test %d raised exception: %s", test_cases[i]["id"], result)
            metrics = RunMetrics(
                test_id=test_cases[i]["id"],
                user_intent=test_cases[i]["user_intent"],
                budget=test_cases[i]["budget"],
                room_width=test_cases[i]["room_width"],
                room_depth=test_cases[i]["room_depth"],
                error=str(result),
                success=False,
            )
            final_results.append(metrics)
        else:
            final_results.append(result)

    executor.shutdown(wait=False)

    logger.info(
        "Benchmark completed: %d tests in %.1fs (%.1fs avg, %.1fx speedup vs sequential)",
        total,
        elapsed,
        elapsed / total if total > 0 else 0,
        (sum(r.total_time_s for r in final_results) / elapsed) if elapsed > 0 else 1,
    )

    return final_results


# =============================================================================
# Report Generation
# =============================================================================

def generate_report(results: list[RunMetrics], output_dir: Path) -> dict[str, Any]:
    """Generate aggregate benchmark report."""
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    if not successful:
        return {
            "summary": {
                "total_tests": len(results),
                "successful": 0,
                "failed": len(failed),
                "success_rate_pct": 0,
            },
            "error": "No successful runs",
            "failed_tests": [
                {"id": r.test_id, "error": r.error[:200]} for r in failed
            ],
        }

    # Budget accuracy metrics
    budget_diffs = [r.budget_diff_pct for r in successful]
    abs_budget_diffs = [abs(d) for d in budget_diffs]
    within_budget_count = sum(1 for r in successful if r.within_budget)
    within_10pct_count = sum(1 for r in successful if r.within_10pct)

    # Asset selection metrics
    num_selected = [r.num_selected for r in successful]
    num_candidates = [r.num_candidates for r in successful if r.num_candidates > 0]

    # LP metrics
    lp_success_count = sum(1 for r in successful if r.lp_success)
    lp_objectives = [r.lp_objective for r in successful if r.lp_objective > 0]

    # Preference score metrics
    total_pref_scores = [r.total_preference_score for r in successful if r.total_preference_score > 0]
    mean_pref_scores = [r.mean_preference_score for r in successful if r.mean_preference_score > 0]
    all_pref_scores = [score for r in successful for score in r.preference_scores]

    # Layout metrics
    layout_generated_count = sum(1 for r in successful if r.layout_generated)
    all_placed_count = sum(1 for r in successful if r.all_assets_placed)

    # Timing metrics
    total_times = [r.total_time_s for r in successful]

    report = {
        "summary": {
            "total_tests": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate_pct": (len(successful) / len(results)) * 100 if results else 0,
        },
        "budget_accuracy": {
            "within_budget_count": within_budget_count,
            "within_budget_pct": (within_budget_count / len(successful)) * 100,
            "within_10pct_count": within_10pct_count,
            "within_10pct_pct": (within_10pct_count / len(successful)) * 100,
            "mean_diff_pct": sum(budget_diffs) / len(budget_diffs),
            "mean_abs_diff_pct": sum(abs_budget_diffs) / len(abs_budget_diffs),
            "median_abs_diff_pct": sorted(abs_budget_diffs)[len(abs_budget_diffs) // 2],
            "max_over_budget_pct": max(budget_diffs),
            "max_under_budget_pct": min(budget_diffs),
        },
        "asset_selection": {
            "mean_candidates": sum(num_candidates) / len(num_candidates) if num_candidates else 0,
            "mean_selected": sum(num_selected) / len(num_selected),
            "min_selected": min(num_selected),
            "max_selected": max(num_selected),
        },
        "lp_optimization": {
            "success_count": lp_success_count,
            "success_rate_pct": (lp_success_count / len(successful)) * 100,
            "mean_objective": sum(lp_objectives) / len(lp_objectives) if lp_objectives else 0,
        },
        "preference_scores": {
            "mean_total_score": sum(total_pref_scores) / len(total_pref_scores) if total_pref_scores else 0,
            "mean_per_asset_score": sum(mean_pref_scores) / len(mean_pref_scores) if mean_pref_scores else 0,
            "overall_mean_score": sum(all_pref_scores) / len(all_pref_scores) if all_pref_scores else 0,
            "min_score": min(all_pref_scores) if all_pref_scores else 0,
            "max_score": max(all_pref_scores) if all_pref_scores else 0,
            "score_distribution": {
                "1-3 (low)": sum(1 for s in all_pref_scores if 1 <= s <= 3),
                "4-6 (medium)": sum(1 for s in all_pref_scores if 4 <= s <= 6),
                "7-10 (high)": sum(1 for s in all_pref_scores if 7 <= s <= 10),
            } if all_pref_scores else {},
        },
        "layout_generation": {
            "layout_generated_count": layout_generated_count,
            "layout_generated_pct": (layout_generated_count / len(successful)) * 100,
            "all_assets_placed_count": all_placed_count,
            "all_assets_placed_pct": (all_placed_count / len(successful)) * 100 if successful else 0,
        },
        "timing": {
            "mean_total_time_s": sum(total_times) / len(total_times),
            "min_total_time_s": min(total_times),
            "max_total_time_s": max(total_times),
            "total_benchmark_time_s": sum(total_times),
        },
        "by_budget_category": {},
        "by_room_size": {},
        "failed_tests": [
            {"id": r.test_id, "error": r.error[:200]} for r in failed
        ],
    }

    # Breakdown by budget category
    budget_categories = set()
    for tc in test_cases_global:
        budget_categories.add(tc.get("budget_category", "unknown"))

    for cat in budget_categories:
        cat_results = [
            r for r, tc in zip(results, test_cases_global)
            if tc.get("budget_category") == cat and r.success
        ]
        if cat_results:
            cat_diffs = [r.budget_diff_pct for r in cat_results]
            report["by_budget_category"][cat] = {
                "count": len(cat_results),
                "mean_diff_pct": sum(cat_diffs) / len(cat_diffs),
                "within_10pct_pct": sum(1 for r in cat_results if r.within_10pct) / len(cat_results) * 100,
            }

    # Breakdown by room size
    room_sizes = set()
    for tc in test_cases_global:
        room_sizes.add(tc.get("room_size_category", "unknown"))

    for size in room_sizes:
        size_results = [
            r for r, tc in zip(results, test_cases_global)
            if tc.get("room_size_category") == size and r.success
        ]
        if size_results:
            size_selected = [r.num_selected for r in size_results]
            report["by_room_size"][size] = {
                "count": len(size_results),
                "mean_selected": sum(size_selected) / len(size_selected),
            }

    return report


def print_report(report: dict[str, Any]) -> None:
    """Print a formatted benchmark report."""
    print("\n" + "=" * 70)
    print("BENCHMARK REPORT")
    print("=" * 70)

    s = report.get("summary", {})
    print(f"\nSUMMARY")
    print(f"  Total tests:    {s.get('total_tests', 0)}")
    print(f"  Successful:     {s.get('successful', 0)}")
    print(f"  Failed:         {s.get('failed', 0)}")
    print(f"  Success rate:   {s.get('success_rate_pct', 0):.1f}%")

    if report.get("error"):
        print(f"\nERROR: {report['error']}")

    if b := report.get("budget_accuracy"):
        print(f"\nBUDGET ACCURACY")
        print(f"  Within budget:      {b['within_budget_count']} ({b['within_budget_pct']:.1f}%)")
        print(f"  Within ±10%:        {b['within_10pct_count']} ({b['within_10pct_pct']:.1f}%)")
        print(f"  Mean diff:          {b['mean_diff_pct']:+.1f}%")
        print(f"  Mean |diff|:        {b['mean_abs_diff_pct']:.1f}%")
        print(f"  Median |diff|:      {b['median_abs_diff_pct']:.1f}%")
        print(f"  Max over budget:    {b['max_over_budget_pct']:+.1f}%")
        print(f"  Max under budget:   {b['max_under_budget_pct']:+.1f}%")

    if a := report.get("asset_selection"):
        print(f"\nASSET SELECTION")
        print(f"  Mean candidates:    {a['mean_candidates']:.1f}")
        print(f"  Mean selected:      {a['mean_selected']:.1f}")
        print(f"  Range selected:     {a['min_selected']} - {a['max_selected']}")

    if lp := report.get("lp_optimization"):
        print(f"\nLP OPTIMIZATION")
        print(f"  Success rate:       {lp['success_rate_pct']:.1f}%")
        print(f"  Mean objective:     {lp.get('mean_objective', 0):.2f}")

    if ps := report.get("preference_scores"):
        print(f"\nPREFERENCE SCORES")
        print(f"  Mean total/run:     {ps['mean_total_score']:.2f}")
        print(f"  Mean per asset:     {ps['mean_per_asset_score']:.2f}")
        print(f"  Overall mean:       {ps['overall_mean_score']:.2f}")
        print(f"  Range:              {ps['min_score']:.0f} - {ps['max_score']:.0f}")
        if dist := ps.get("score_distribution"):
            print(f"  Distribution:")
            print(f"    Low (1-3):        {dist.get('1-3 (low)', 0)}")
            print(f"    Medium (4-6):     {dist.get('4-6 (medium)', 0)}")
            print(f"    High (7-10):      {dist.get('7-10 (high)', 0)}")

    if ly := report.get("layout_generation"):
        print(f"\nLAYOUT GENERATION")
        print(f"  Generated:          {ly['layout_generated_count']} ({ly['layout_generated_pct']:.1f}%)")
        print(f"  All assets placed:  {ly['all_assets_placed_count']} ({ly['all_assets_placed_pct']:.1f}%)")

    if t := report.get("timing"):
        print(f"\nTIMING")
        print(f"  Mean time/test:     {t['mean_total_time_s']:.2f}s")
        print(f"  Min time:           {t['min_total_time_s']:.2f}s")
        print(f"  Max time:           {t['max_total_time_s']:.2f}s")
        print(f"  Total time:         {t['total_benchmark_time_s']:.1f}s ({t['total_benchmark_time_s']/60:.1f}min)")

    if report.get("by_budget_category"):
        print(f"\nBY BUDGET CATEGORY")
        for cat, data in sorted(report["by_budget_category"].items()):
            print(f"  {cat:12}: n={data['count']:2}, mean_diff={data['mean_diff_pct']:+.1f}%, within_10%={data['within_10pct_pct']:.0f}%")

    if report.get("by_room_size"):
        print(f"\nBY ROOM SIZE")
        for size, data in sorted(report["by_room_size"].items()):
            print(f"  {size:8}: n={data['count']:2}, mean_selected={data['mean_selected']:.1f}")

    if report.get("failed_tests"):
        print(f"\nFAILED TESTS")
        for f in report["failed_tests"][:10]:
            print(f"  Test {f['id']}: {f['error'][:80]}...")
        if len(report["failed_tests"]) > 10:
            print(f"  ... and {len(report['failed_tests']) - 10} more")

    print("\n" + "=" * 70)


# Global for report generation (set during benchmark run)
test_cases_global: list[dict[str, Any]] = []


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run pipeline benchmark")
    parser.add_argument(
        "--num-tests",
        type=int,
        default=100,
        help="Number of test cases to run (default: 100)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for test case generation (default: 42)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="benchmark_outputs",
        help="Output directory for benchmark results",
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Only generate test cases, don't run benchmark",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Number of parallel tests to run (default: 5, use 1 for sequential)",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Run tests sequentially instead of in parallel",
    )
    args = parser.parse_args()

    # Generate test cases
    test_cases = generate_test_cases(n=args.num_tests, seed=args.seed)
    test_cases_global = test_cases

    output_dir = Path(args.output_dir) / time.strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save test cases
    with open(output_dir / "test_cases.json", "w") as f:
        json.dump(test_cases, f, indent=2)

    if args.generate_only:
        print(f"Generated {len(test_cases)} test cases to {output_dir / 'test_cases.json'}")
        for tc in test_cases[:5]:
            print(f"  {tc['id']}: {tc['user_intent'][:60]}... (${tc['budget']}, {tc['room_width']}x{tc['room_depth']}m)")
        print(f"  ... and {len(test_cases) - 5} more")
    else:
        # Run benchmark
        if args.sequential or args.concurrency == 1:
            results = run_benchmark(test_cases, output_dir, max_tests=args.num_tests)
        else:
            results = asyncio.run(
                run_benchmark_async(
                    test_cases,
                    output_dir,
                    max_tests=args.num_tests,
                    concurrency=args.concurrency,
                )
            )

        # Save raw results
        results_data = [asdict(r) for r in results]
        with open(output_dir / "results.json", "w") as f:
            json.dump(results_data, f, indent=2)

        # Generate and save report
        report = generate_report(results, output_dir)
        with open(output_dir / "report.json", "w") as f:
            json.dump(report, f, indent=2)

        # Print report
        print_report(report)

        logger.info("Benchmark complete. Results saved to %s", output_dir)
