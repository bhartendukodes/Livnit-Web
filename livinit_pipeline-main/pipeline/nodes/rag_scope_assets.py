import json
import time
from pathlib import Path
from typing import Any
from pipeline.core.asset_manager import AssetManager
from pipeline.core.pipeline_shared import STAGE_DIRS, log_duration
from pipeline.nodes.init_vector_store import get_pg_connection, query_similar, embed_texts, _RENDER_DIR

TOP_K = 150
_DATASET_PATH = Path(__file__).resolve().parent.parent.parent / "dataset" / "processed.json"


def rag_scope_assets_node(state: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()

    with open(_DATASET_PATH) as f:
        all_assets = json.load(f)
    assets_by_uid = {a["uid"]: a for a in all_assets}

    query = f'{state["user_intent"]}'
    query_emb = embed_texts([query])[0]
    conn = get_pg_connection()
    results = query_similar(conn, query_emb, TOP_K)
    conn.close()

    scoped_data = []
    for uid, score in results:
        if uid in assets_by_uid:
            a = assets_by_uid[uid]
            a["score"] = score
            a["image_path"] = str(_RENDER_DIR / f"{uid}.png")
            scoped_data.append(a)

    csv_lines = ["uid,category,price,width,depth,height,materials,color,style,shape,asset_description,description"]
    for a in scoped_data:
        csv_lines.append(
            f'{a["uid"]},{a["category"]},{a["price"]},{a["width"]},{a["depth"]},{a["height"]},'
            f'"{a["materials"]}",{a.get("asset_color","")},{a.get("asset_style","")},{a.get("asset_shape","")},'
            f'"{a.get("asset_description","")}","{a["description"][:100]}"'
        )
    scoped_csv = "\n".join(csv_lines)

    manager: AssetManager = state["asset_manager"]
    stage = STAGE_DIRS["rag_scope"]
    manager.write_text(stage, "scoped_assets.csv", scoped_csv)
    manager.write_json(stage, "scoped_assets.json", scoped_data)

    log_duration("RAG SCOPE ASSETS", start)
    return {"assets_csv": scoped_csv, "assets_data": scoped_data}
