import asyncio
import json
import os
import logging
import random
import time
from pathlib import Path
from typing import Any

import psycopg2

from pipeline.core.pipeline_shared import log_duration
from pipeline import supabase

logger = logging.getLogger(__name__)

BASE_DIR = Path("dataset/blobs")
PROCESSED_JSON = Path("dataset/processed.json")


def _get_pg_connection():
    user = os.environ["DB_POSTGRES_USER"]
    password = os.environ["DB_POSTGRES_PASSWORD"]
    host = os.environ.get("DB_HOST", "postgres")
    return psycopg2.connect(f"postgresql://{user}:{password}@{host}:5432/livinit")


def _init_download_tracking(conn):
    with conn.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS downloaded_assets (name TEXT PRIMARY KEY)")
    conn.commit()


def _get_downloaded_names(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM downloaded_assets")
        return {row[0] for row in cur.fetchall()}


def _mark_downloaded(conn, names: list[str]):
    if not names:
        return
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO downloaded_assets (name) VALUES (%s) ON CONFLICT DO NOTHING", [(n,) for n in names])
    conn.commit()


async def _download_asset(asset: dict, semaphore) -> int:
    name = asset["name"]
    category = (name.rsplit("_", 1)[0]).lower()
    target_dir = BASE_DIR / name
    glb_path = target_dir / f"{category}.glb"
    json_path = target_dir / "data.json"

    if glb_path.exists() and json_path.exists():
        return 0

    target_dir.mkdir(parents=True, exist_ok=True)
    model_url = asset.get("model_url")
    metadata_url = asset.get("metadata_url")

    results = await asyncio.gather(
        supabase.download_asset_file(model_url, glb_path, semaphore),
        supabase.download_asset_file(metadata_url, json_path, semaphore, is_text=True),
    )
    if sum(results) > 0:
        logger.debug("[DOWNLOAD] Asset %s: %d files downloaded", name, sum(results))
    return sum(results)


async def _sync_all_assets():
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    def get_db_state():
        t = time.perf_counter()
        conn = _get_pg_connection()
        _init_download_tracking(conn)
        result = conn, _get_downloaded_names(conn)
        logger.info("\033[93m[SYNC ASSETS] Postgres: %.3fs\033[0m", time.perf_counter() - t)
        return result

    def get_all_names():
        t = time.perf_counter()
        names = supabase.fetch_asset_names()
        logger.info("\033[93m[SYNC ASSETS] Supabase: %.3fs (%d names)\033[0m", time.perf_counter() - t, len(names))
        return names

    (conn, downloaded_names), all_names = await asyncio.gather(
        asyncio.to_thread(get_db_state),
        asyncio.to_thread(get_all_names),
    )
    logger.info("[SYNC ASSETS] %d assets already tracked in DB", len(downloaded_names))

    missing_names = [n for n in all_names if n not in downloaded_names]
    logger.info("[SYNC ASSETS] %d/%d assets need download", len(missing_names), len(all_names))

    if not missing_names:
        conn.close()
        return 0

    missing = supabase.fetch_assets_by_names(missing_names, "name,category,model_url,metadata_url")

    semaphore = asyncio.Semaphore(16)
    results = await asyncio.gather(*[_download_asset(a, semaphore) for a in missing])

    newly_downloaded = [a["name"] for a, r in zip(missing, results) if r > 0]
    _mark_downloaded(conn, newly_downloaded)
    conn.close()
    return sum(results)


def _generate_processed_json():
    existing = json.loads(PROCESSED_JSON.read_text()) if PROCESSED_JSON.exists() else []
    existing_uids = {e["uid"] for e in existing}
    added = 0
    for json_file in sorted(BASE_DIR.glob("*/data.json")):
        uid = json_file.parent.name
        if uid in existing_uids:
            continue
        try:
            annotations = json.loads(json_file.read_text())["annotations"]
            glb_file = next(json_file.parent.glob("*.glb"), None)
            if not glb_file:
                continue
            existing.append({
                "uid": uid,
                "description": annotations["description"],
                "category": annotations["category"],
                "width": annotations["width"],
                "depth": annotations["depth"],
                "height": annotations["height"],
                "materials": annotations["materials"],
                "path": str(glb_file.relative_to(BASE_DIR.parent.parent)),
                "price": random.randint(100, 2000),
                "frontView": annotations.get("frontView", 0),
            })
            added += 1
        except Exception as e:
            logger.warning("[SYNC ASSETS] Skipping %s: %s", json_file, e)
    PROCESSED_JSON.write_text(json.dumps(existing, indent=2) + "\n")
    logger.info("[SYNC ASSETS] Appended %d new entries to %s (total: %d)", added, PROCESSED_JSON, len(existing))


async def sync_assets_node(_state: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    downloaded = await _sync_all_assets()
    if downloaded > 0:
        _generate_processed_json()
    else:
        logger.info("[SYNC ASSETS] No new assets, skipping processed.json regeneration")
    log_duration("SYNC ASSETS", start)
    logger.info("[SYNC ASSETS] Downloaded %d new files", downloaded)
    return {}


async def _download_single_asset(uid: str, path: Path, model_url: str, semaphore) -> bool:
    if not model_url:
        logger.warning("[DOWNLOAD ASSETS] No model_url for %s", uid)
        return False
    return await supabase.download_asset_file(model_url, path, semaphore)


async def download_assets_node(state: dict[str, Any]) -> dict[str, Any]:
    """Download missing furniture assets. Room USDZ is already downloaded by API before pipeline starts."""
    start = time.perf_counter()

    selected_assets = state.get("selected_assets", [])
    if not selected_assets:
        log_duration("DOWNLOAD ASSETS", start)
        return {}

    missing = [(a["uid"], Path(a["path"])) for a in selected_assets if not Path(a["path"]).exists()]
    if not missing:
        logger.info("[DOWNLOAD ASSETS] All %d assets already present", len(selected_assets))
        log_duration("DOWNLOAD ASSETS", start)
        return {}

    logger.info("[DOWNLOAD ASSETS] Downloading %d missing assets", len(missing))
    assets = supabase.fetch_assets_by_names([uid for uid, _ in missing], "name,model_url")
    url_map = {r["name"]: r["model_url"] for r in assets}

    semaphore = asyncio.Semaphore(16)
    results = await asyncio.gather(*[_download_single_asset(uid, path, url_map.get(uid), semaphore) for uid, path in missing])
    downloaded = sum(results)

    log_duration("DOWNLOAD ASSETS", start)
    logger.info("[DOWNLOAD ASSETS] Downloaded %d/%d missing assets", downloaded, len(missing))
    return {}
