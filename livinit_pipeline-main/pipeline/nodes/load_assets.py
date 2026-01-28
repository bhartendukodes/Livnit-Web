import json
import time
from pathlib import Path
from typing import Any
from pipeline.core.asset_manager import AssetManager
from pipeline.core.pipeline_shared import STAGE_DIRS, log_duration

_DATASET_PATH = Path(__file__).resolve().parent.parent.parent / "dataset" / "processed.json"


def load_assets_node(state: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    with open(_DATASET_PATH) as f:
        assets = json.load(f)

    lines = ["uid,category,price,width,depth,height,materials,color,style,shape,asset_description,description"]
    for asset in assets:
        lines.append(
            f'{asset["uid"]},{asset["category"]},{asset["price"]},'
            f'{asset["width"]},{asset["depth"]},{asset["height"]},"{asset["materials"]}",'
            f'{asset.get("asset_color","")},{asset.get("asset_style","")},{asset.get("asset_shape","")},'
            f'"{asset.get("asset_description","")}","{asset["description"][:100]}"'
        )

    csv_content = "\n".join(lines)
    manager: AssetManager = state["asset_manager"]
    stage = STAGE_DIRS["load_assets"]
    manager.write_text(stage, "assets.csv", csv_content)
    manager.write_json(stage, "assets_data.json", assets)
    log_duration("LOAD ASSETS", start)

    return {"assets_csv": csv_content, "assets_data": assets}
