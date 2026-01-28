import asyncio
import json
import os
import logging
import random
import time
from pathlib import Path
from typing import Any

import psycopg2
import requests
from supabase import create_client

from pipeline.core.pipeline_shared import log_duration

logger = logging.getLogger(__name__)

_supabase = None
BASE_DIR = Path("dataset/blobs")
ROOMS_DIR = Path("dataset/room")
PROCESSED_JSON = Path("dataset/processed.json")


def _get_supabase():
    global _supabase
    if _supabase is None:
        _supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    return _supabase


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


def _add_download_flag(url: str) -> str:
    if not url:
        return ""
    if "supabase.co" in url and "download=" not in url:
        return f"{url}{'&' if '?' in url else '?'}download=1"
    return url


def _fetch(url: str, timeout: int):
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp


async def _download_file(url: str, path: Path, timeout: int, is_text: bool, semaphore):
    if not url:
        logger.debug("[DOWNLOAD] Skipping %s - no URL", path)
        return False
    if path.exists():
        logger.debug("[DOWNLOAD] Skipping %s - already exists", path)
        return False
    logger.debug("[DOWNLOAD] Fetching %s -> %s", url[:80], path)
    async with semaphore:
        resp = await asyncio.to_thread(_fetch, url, timeout)
    path.write_text(resp.text, encoding="utf-8") if is_text else path.write_bytes(resp.content)
    logger.debug("[DOWNLOAD] Saved %s (%d bytes)", path, len(resp.content))
    return True


async def _download_asset(asset: dict, semaphore) -> int:
    name = asset["name"]
    category = (name.rsplit("_", 1)[0]).lower()
    target_dir = BASE_DIR / name
    glb_path = target_dir / f"{category}.glb"
    json_path = target_dir / "data.json"

    if glb_path.exists() and json_path.exists():
        return 0

    target_dir.mkdir(parents=True, exist_ok=True)
    model_url = _add_download_flag(asset.get("model_url"))
    metadata_url = _add_download_flag(asset.get("metadata_url"))

    results = await asyncio.gather(
        _download_file(model_url, glb_path, 60, False, semaphore),
        _download_file(metadata_url, json_path, 30, True, semaphore),
    )
    if sum(results) > 0:
        logger.debug("[DOWNLOAD] Asset %s: %d files downloaded", name, sum(results))
    return sum(results)


async def _sync_all_assets():
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    table = os.getenv("SUPABASE_ASSETS_TABLE", "assets")

    def get_db_state():
        t = time.perf_counter()
        conn = _get_pg_connection()
        _init_download_tracking(conn)
        result = conn, _get_downloaded_names(conn)
        logger.info("\033[93m[SYNC ASSETS] Postgres: %.3fs\033[0m", time.perf_counter() - t)
        return result

    def get_all_names():
        t = time.perf_counter()
        client = _get_supabase()
        names, start, chunk = [], 0, 1000
        while True:
            resp = client.table(table).select("name").range(start, start + chunk - 1).execute()
            batch = resp.data or []
            names.extend(r["name"] for r in batch)
            if len(batch) < chunk:
                break
            start += chunk
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

    # Fetch full details only for missing assets
    resp = await asyncio.to_thread(
        lambda: _get_supabase().table(table).select("name,category,model_url,metadata_url").in_("name", missing_names).execute()
    )
    missing = resp.data or []

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
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with semaphore:
            r = await asyncio.to_thread(requests.get, model_url, timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
        logger.info("[DOWNLOAD ASSETS] Downloaded %s", uid)
        return True
    except Exception as e:
        logger.error("[DOWNLOAD ASSETS] Failed to download %s: %s", uid, e)
        return False


async def download_room_usdz(usdz_path: str) -> str:
    """Download room USDZ file if not present locally. Returns updated path in dataset/."""
    filename = Path(usdz_path).name
    local_path = ROOMS_DIR / filename
    if local_path.exists():
        logger.info("[DOWNLOAD ASSETS] Room file already present: %s", local_path)
        return str(local_path)

    ROOMS_DIR.mkdir(parents=True, exist_ok=True)
    bucket = os.getenv("SUPABASE_ROOMS_BUCKET", "rooms")
    client = _get_supabase()
    url = client.storage.from_(bucket).get_public_url(filename)
    url = _add_download_flag(url)

    logger.info("[DOWNLOAD ASSETS] Downloading room file: %s", filename)
    resp = await asyncio.to_thread(requests.get, url, timeout=60)
    resp.raise_for_status()
    local_path.write_bytes(resp.content)
    logger.info("[DOWNLOAD ASSETS] Downloaded room file to %s", local_path)
    return str(local_path)


async def download_assets_node(state: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    logger.debug("[DOWNLOAD ASSETS] Node started with state keys: %s", list(state.keys()))

    # Download room USDZ file
    usdz_path = state.get("usdz_path", "")
    logger.debug("[DOWNLOAD ASSETS] usdz_path=%s", usdz_path)
    updated_usdz_path = await download_room_usdz(usdz_path) if usdz_path else usdz_path

    selected_assets = state.get("selected_assets", [])
    logger.debug("[DOWNLOAD ASSETS] selected_assets count=%d", len(selected_assets))
    if not selected_assets:
        log_duration("DOWNLOAD ASSETS", start)
        return {"usdz_path": updated_usdz_path}

    missing = [(a["uid"], Path(a["path"])) for a in selected_assets if not Path(a["path"]).exists()]
    logger.debug("[DOWNLOAD ASSETS] Missing assets: %s", [uid for uid, _ in missing])
    if not missing:
        logger.info("[DOWNLOAD ASSETS] All %d assets already present", len(selected_assets))
        log_duration("DOWNLOAD ASSETS", start)
        return {"usdz_path": updated_usdz_path}

    logger.info("[DOWNLOAD ASSETS] Downloading %d missing assets", len(missing))
    table = os.getenv("SUPABASE_ASSETS_TABLE", "assets")
    logger.debug("[DOWNLOAD ASSETS] Querying table %s for %d assets", table, len(missing))
    resp = _get_supabase().table(table).select("name,model_url").in_("name", [uid for uid, _ in missing]).execute()
    url_map = {r["name"]: _add_download_flag(r["model_url"]) for r in (resp.data or [])}
    logger.debug("[DOWNLOAD ASSETS] Got URLs for %d assets", len(url_map))

    semaphore = asyncio.Semaphore(16)
    results = await asyncio.gather(*[_download_single_asset(uid, path, url_map.get(uid), semaphore) for uid, path in missing])
    downloaded = sum(results)

    log_duration("DOWNLOAD ASSETS", start)
    logger.info("[DOWNLOAD ASSETS] Downloaded %d/%d missing assets", downloaded, len(missing))
    return {"usdz_path": updated_usdz_path}
