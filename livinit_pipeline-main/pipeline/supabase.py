"""Centralized Supabase client and operations for rooms, assets, and outputs."""

import asyncio
import logging
import os
import uuid
from pathlib import Path

import requests
from supabase import create_client

logger = logging.getLogger(__name__)

_client = None


def get_client():
    global _client
    if _client is None:
        _client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    return _client


def _add_download_flag(url: str) -> str:
    if not url:
        return ""
    if "supabase.co" in url and "download=" not in url:
        return f"{url}{'&' if '?' in url else '?'}download=1"
    return url


# ============================================================
# Rooms
# ============================================================

def list_rooms() -> list[dict]:
    """List all rooms from supabase."""
    resp = get_client().table("rooms").select("*").order("created_at", desc=True).execute()
    return resp.data or []


def get_room(room_id: str) -> dict | None:
    """Get a room by ID."""
    resp = get_client().table("rooms").select("*").eq("id", room_id).single().execute()
    return resp.data


def get_room_by_filename(filename: str) -> dict | None:
    """Get a room by filename."""
    resp = get_client().table("rooms").select("*").eq("filename", filename).limit(1).execute()
    return resp.data[0] if resp.data else None


async def download_room(room_id_or_filename: str, target_dir: Path) -> tuple[str, str]:
    """Download room USDZ from supabase to target_dir. Returns (local_path, room_id).

    room_id_or_filename can be UUID or filename.
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    # Try as UUID first
    room = None
    try:
        uuid.UUID(room_id_or_filename)
        room = get_room(room_id_or_filename)
    except ValueError:
        pass

    # Try as filename
    if not room:
        filename = Path(room_id_or_filename).name if "/" in room_id_or_filename else room_id_or_filename
        room = get_room_by_filename(filename)

    if not room:
        raise ValueError(f"Room not found in Supabase: {room_id_or_filename}")

    room_id = room["id"]
    filename = room["filename"]
    storage_path = room["storage_path"]
    local_path = target_dir / filename

    bucket = os.getenv("SUPABASE_ROOMS_BUCKET", "rooms")
    url = get_client().storage.from_(bucket).get_public_url(storage_path)
    url = _add_download_flag(url)

    logger.info("[SUPABASE] Downloading room: %s", filename)
    resp = await asyncio.to_thread(requests.get, url, timeout=60)
    resp.raise_for_status()
    local_path.write_bytes(resp.content)
    logger.info("[SUPABASE] Room downloaded to: %s", local_path)

    return str(local_path), room_id


async def upload_room(filename: str, content: bytes) -> dict:
    """Upload room USDZ to Supabase storage and create database record. Returns room record."""
    room_id = str(uuid.uuid4())
    bucket = os.getenv("SUPABASE_ROOMS_BUCKET", "rooms")
    storage_path = filename
    client = get_client()

    logger.info("[SUPABASE] Uploading room: %s", filename)
    await asyncio.to_thread(
        client.storage.from_(bucket).upload,
        storage_path,
        content,
        {"content-type": "model/vnd.usdz+zip"}
    )

    record = {"id": room_id, "filename": filename, "storage_path": storage_path}
    await asyncio.to_thread(client.table("rooms").insert(record).execute)
    logger.info("[SUPABASE] Room uploaded: %s", room_id)

    return {"id": room_id, "filename": filename, "storage_path": storage_path}


# ============================================================
# Assets
# ============================================================

def get_assets_table() -> str:
    return os.getenv("SUPABASE_ASSETS_TABLE", "assets")


def fetch_asset_names(chunk_size: int = 1000) -> list[str]:
    """Fetch all asset names from supabase (paginated)."""
    client = get_client()
    table = get_assets_table()
    names, start = [], 0
    while True:
        resp = client.table(table).select("name").range(start, start + chunk_size - 1).execute()
        batch = resp.data or []
        names.extend(r["name"] for r in batch)
        if len(batch) < chunk_size:
            break
        start += chunk_size
    return names


def fetch_assets_by_names(names: list[str], fields: str = "name,model_url") -> list[dict]:
    """Fetch asset details by names."""
    if not names:
        return []
    resp = get_client().table(get_assets_table()).select(fields).in_("name", names).execute()
    return resp.data or []


def fetch_asset_full(name: str) -> dict | None:
    """Fetch full asset details by name."""
    resp = get_client().table(get_assets_table()).select("*").eq("name", name).limit(1).execute()
    return resp.data[0] if resp.data else None


async def download_asset_file(url: str, path: Path, semaphore: asyncio.Semaphore | None = None, is_text: bool = False) -> bool:
    """Download a single file from URL."""
    if not url or path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    url = _add_download_flag(url)

    async def do_download():
        resp = await asyncio.to_thread(requests.get, url, timeout=60)
        resp.raise_for_status()
        if is_text:
            path.write_text(resp.text, encoding="utf-8")
        else:
            path.write_bytes(resp.content)
        return True

    if semaphore:
        async with semaphore:
            return await do_download()
    return await do_download()


# ============================================================
# Room Outputs
# ============================================================

async def upload_room_output(
    room_id: str | None,
    run_dir: str,
    usdz_path: str,
    glb_path: str | None,
    selected_assets: list[dict],
    user_intent: str | None = None,
    budget: float | None = None,
    layoutvlm_layout: dict | None = None,
) -> str:
    """Upload room output files and create database record. Returns output ID."""
    output_id = str(uuid.uuid4())
    bucket = os.getenv("SUPABASE_OUTPUTS_BUCKET", "room_outputs")
    client = get_client()

    # Upload USDZ
    usdz_file = Path(usdz_path)
    if not usdz_file.exists():
        raise FileNotFoundError(f"USDZ file not found: {usdz_path}")

    usdz_storage = f"{run_dir}/{usdz_file.name}"
    logger.info("[SUPABASE] Uploading USDZ: %s (%d bytes)", usdz_storage, usdz_file.stat().st_size)
    usdz_content = usdz_file.read_bytes()
    await asyncio.to_thread(
        client.storage.from_(bucket).upload,
        usdz_storage,
        usdz_content,
        {"content-type": "model/vnd.usdz+zip"}
    )
    logger.info("[SUPABASE] USDZ uploaded successfully")

    # Upload GLB if provided
    glb_storage = None
    if glb_path and Path(glb_path).exists():
        glb_file = Path(glb_path)
        glb_storage = f"{run_dir}/{glb_file.name}"
        logger.info("[SUPABASE] Uploading GLB: %s (%d bytes)", glb_storage, glb_file.stat().st_size)
        glb_content = glb_file.read_bytes()
        await asyncio.to_thread(
            client.storage.from_(bucket).upload,
            glb_storage,
            glb_content,
            {"content-type": "model/gltf-binary"}
        )
        logger.info("[SUPABASE] GLB uploaded successfully")

    # Insert database record
    record = {
        "id": output_id,
        "room_id": room_id,
        "run_dir": run_dir,
        "filename": usdz_file.name,
        "storage_path": usdz_storage,
        "storage_path_glb": glb_storage or "",
        "selected_assets": selected_assets,
        "user_intent": user_intent,
        "budget": budget,
        "layoutvlm_layout": layoutvlm_layout or {},
    }
    logger.info("[SUPABASE] Creating room_outputs record: %s", output_id)
    await asyncio.to_thread(client.table("room_outputs").insert(record).execute)
    logger.info("[SUPABASE] Room output record created successfully")

    return output_id


def get_room_output(output_id: str) -> dict | None:
    """Get room output by ID."""
    resp = get_client().table("room_outputs").select("*").eq("id", output_id).single().execute()
    return resp.data


def get_room_output_by_run_dir(run_dir: str) -> dict | None:
    """Get room output by run_dir."""
    resp = get_client().table("room_outputs").select("*").eq("run_dir", run_dir).limit(1).execute()
    return resp.data[0] if resp.data else None


def list_room_outputs(room_id: str | None = None, limit: int = 50) -> list[dict]:
    """List room outputs, optionally filtered by room_id."""
    query = get_client().table("room_outputs").select("*").order("created_at", desc=True).limit(limit)
    if room_id:
        query = query.eq("room_id", room_id)
    return query.execute().data or []


def get_output_download_url(storage_path: str) -> str:
    """Get public download URL for an output file."""
    bucket = os.getenv("SUPABASE_OUTPUTS_BUCKET", "room_outputs")
    url = get_client().storage.from_(bucket).get_public_url(storage_path)
    return _add_download_flag(url)
