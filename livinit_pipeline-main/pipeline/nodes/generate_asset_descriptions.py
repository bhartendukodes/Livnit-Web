import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from google.genai import types

from pipeline.core.llm import client
from pipeline.core.pipeline_shared import log_duration

logger = logging.getLogger(__name__)

RENDER_DIR = Path("dataset/render")
PROCESSED_JSON = Path("dataset/processed.json")

CONFIG  = types.GenerateContentConfig(
    response_mime_type="application/json",
    temperature=1,
    thinking_config=types.ThinkingConfig(thinking_level="low", include_thoughts=True),
)



DESCRIBE_PROMPT = """Analyze this furniture item and return JSON with these fields:
- description: One sentence describing the item (style, material, color, type)
- color: Primary color(s), e.g. "beige", "dark brown", "white and gold"
- style: Design style, e.g. "modern", "traditional", "mid-century", "industrial", "minimalist"
- shape: General form, e.g. "rectangular", "round", "L-shaped", "curved", "angular"

Example: {"description": "A modern beige fabric sofa with clean lines", "color": "beige", "style": "modern", "shape": "rectangular"}"""


def _describe_image_sync(image_path: Path) -> dict | None:
    try:
        resp = client.models.generate_content(
            model="gemini-3-flash-preview",
            config=CONFIG,
            contents=[
                types.Part.from_text(text=DESCRIBE_PROMPT),
                types.Part.from_bytes(data=image_path.read_bytes(), mime_type="image/png"),
            ],
        )
        return json.loads(resp.text.strip())
    except Exception as e:
        logger.warning("[DESCRIBE] Failed %s: %s", image_path.stem, e)
        return None


async def _describe_image(uid: str, image_path: Path, semaphore: asyncio.Semaphore) -> tuple[str, dict | None]:
    async with semaphore:
        return uid, await asyncio.to_thread(_describe_image_sync, image_path)


async def generate_asset_descriptions_node(_state: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()

    if not PROCESSED_JSON.exists():
        logger.warning("[DESCRIBE] No processed.json found")
        return {}

    assets = json.loads(PROCESSED_JSON.read_text())
    assets_by_uid = {a["uid"]: a for a in assets}

    pending = [(a["uid"], RENDER_DIR / f"{a['uid']}.png") for a in assets
               if (not a.get("asset_color") or not a.get("asset_style") or not a.get("asset_shape"))
               and (RENDER_DIR / f"{a['uid']}.png").exists()]

    if not pending:
        logger.info("[DESCRIBE] All assets already have descriptions")
        log_duration("DESCRIBE ASSETS", start)
        return {}

    logger.info("[DESCRIBE] Generating descriptions for %d assets", len(pending))

    semaphore = asyncio.Semaphore(8)
    results = await asyncio.gather(*[_describe_image(uid, path, semaphore) for uid, path in pending])

    added = 0
    for uid, meta in results:
        if meta and uid in assets_by_uid:
            assets_by_uid[uid]["asset_description"] = meta.get("description", "")
            assets_by_uid[uid]["asset_color"] = meta.get("color", "")
            assets_by_uid[uid]["asset_style"] = meta.get("style", "")
            assets_by_uid[uid]["asset_shape"] = meta.get("shape", "")
            added += 1

    PROCESSED_JSON.write_text(json.dumps(assets, indent=2) + "\n")
    logger.info("[DESCRIBE] Added descriptions to %d assets", added)
    log_duration("DESCRIBE ASSETS", start)
    return {}
