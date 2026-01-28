#!/usr/bin/env python3
"""Generate markdown report for benchmark results."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
BENCHMARK_DIR = ROOT / "benchmark_room_outputs"
REPORTS_DIR = ROOT / "reports"

# Get latest run or use provided path
if len(sys.argv) > 1:
    BASE = Path(sys.argv[1])
else:
    BASE = sorted(BENCHMARK_DIR.iterdir())[-1]

RESULTS = json.loads((BASE / "results.json").read_text())
CONFIG = json.loads((BASE / "config.json").read_text())
REPORT = json.loads((BASE / "report.json").read_text())

# Parse date from folder name (format: YYYYMMDD_HHMMSS)
folder_name = BASE.name
date_str = f"{folder_name[:4]}-{folder_name[4:6]}-{folder_name[6:8]} {folder_name[9:11]}:{folder_name[11:13]}:{folder_name[13:15]}"

md = []
md.append("# Room Benchmark Report")
md.append(f"\n**Date:** {date_str}\n")

# Summary
s = REPORT["summary"]
md.append("## Summary\n")
md.append(f"| Metric | Value |")
md.append(f"|--------|-------|")
md.append(f"| Total Runs | {s['total']} |")
md.append(f"| Successful | {s['success']} |")
md.append(f"| Failed | {s['failed']} |")
md.append(f"| Success Rate | {s['success_rate_pct']:.1f}% |")

# Inputs
md.append("\n## Inputs\n")
md.append("### Rooms")
for r in CONFIG["rooms"]:
    md.append(f"- `{Path(r).name}`")

md.append("\n### Design Prompts")
for i, p in enumerate(CONFIG["prompts"], 1):
    md.append(f"{i}. {p}")

md.append("\n### Budgets")
md.append(", ".join(f"${int(b):,}" for b in CONFIG["budgets"]))

# Stats
md.append("\n## Performance Stats\n")
t = REPORT["timing"]
md.append(f"| Timing | Value |")
md.append(f"|--------|-------|")
md.append(f"| Mean | {t['mean_s']:.1f}s |")
md.append(f"| Min | {t['min_s']:.1f}s |")
md.append(f"| Max | {t['max_s']:.1f}s |")
md.append(f"| Total | {t['total_s']/60:.1f} min |")

b = REPORT["budget"]
md.append(f"\n| Budget | Value |")
md.append(f"|--------|-------|")
md.append(f"| Within Budget | {b['within_budget_pct']:.1f}% |")
md.append(f"| Mean Diff | {b['mean_diff_pct']:+.1f}% |")

ly = REPORT["layout"]
md.append(f"\n| Layout | Value |")
md.append(f"|--------|-------|")
md.append(f"| Generated | {ly['generated_pct']:.0f}% |")
md.append(f"| All Placed | {ly['all_placed_pct']:.0f}% |")
md.append(f"| In Bounds | {ly['mean_in_bounds']:.1f} avg |")

# Room vs asset footprint stats
footprint_ratios = []
for i, r in enumerate(RESULTS):
    llm_file = BASE / f"run_{i:03d}" / "select_assets" / "llm_selection.json"
    if llm_file.exists():
        llm = json.loads(llm_file.read_text())
        footprint = llm.get("total_footprint_sqm", 0)
        if footprint > 0 and r["room_area"] > 0:
            footprint_ratios.append(footprint / r["room_area"] * 100)

md.append(f"\n| Footprint Coverage | Value |")
md.append(f"|-------------------|-------|")
if footprint_ratios:
    md.append(f"| Mean | {sum(footprint_ratios)/len(footprint_ratios):.1f}% |")
    md.append(f"| Min | {min(footprint_ratios):.1f}% |")
    md.append(f"| Max | {max(footprint_ratios):.1f}% |")

# Individual Runs
md.append("\n---\n## Individual Runs\n")

for i, r in enumerate(RESULTS):
    run_dir = BASE / f"run_{i:03d}"
    llm_file = run_dir / "select_assets" / "llm_selection.json"
    preview = run_dir / "draw_layout_preview" / "layout_preview.png"

    status = "✓" if r["success"] else "✗"
    budget_status = "✓" if r["within_budget"] else "over"

    md.append(f"### Run {i:03d} {status}\n")

    # Build config column
    config = []
    config.append(f"**Room:** `{r['room_file']}` ({r['room_width']:.1f}m × {r['room_depth']:.1f}m = {r['room_area']:.1f}m²)<br>")
    config.append(f"**Prompt:** {r['user_intent']}<br>")
    config.append(f"**Budget:** ${r['budget']:,.0f} → ${r['actual_cost']:,.0f} ({r['budget_diff_pct']:+.1f}%, {budget_status})<br>")
    config.append(f"**Time:** {r['total_time_s']:.1f}s | **Assets:** {r['num_selected']} / {r['num_candidates']}<br>")
    if r["error"]:
        config.append(f"<br>**Error:** {r['error']}")
    if llm_file.exists():
        llm = json.loads(llm_file.read_text())
        footprint = llm.get("total_footprint_sqm", 0)
        coverage = footprint / r["room_area"] * 100 if r["room_area"] > 0 else 0
        config.append(f"<br>**Footprint:** {footprint:.1f}m² / {r['room_area']:.1f}m² ({coverage:.0f}%)")

    # Build image column
    img_col = ""
    if preview.exists():
        rel_path = f"../benchmark_room_outputs/{BASE.name}/run_{i:03d}/draw_layout_preview/layout_preview.png"
        img_col = f'<img src="{rel_path}" width="100%">'

    md.append('<table width="100%"><tr><td width="50%" valign="top">')
    md.append("".join(config))
    md.append('</td><td width="50%" valign="top">')
    md.append(img_col)
    md.append('</td></tr></table>\n')
    md.append("---\n")

# Write report
REPORTS_DIR.mkdir(exist_ok=True)
output_file = REPORTS_DIR / f"benchmark_{BASE.name}.md"
output_file.write_text("\n".join(md))
print(f"Report written to {output_file}")
