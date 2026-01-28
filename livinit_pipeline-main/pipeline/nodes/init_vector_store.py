import os
import json
import time
import logging
import threading
from pathlib import Path
from typing import Any
import torch
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from PIL import Image
from pipeline.core.pipeline_shared import log_duration

logger = logging.getLogger(__name__)

_DATASET_PATH = Path(__file__).resolve().parent.parent.parent / "dataset" / "processed.json"
_RENDER_DIR = Path(__file__).resolve().parent.parent.parent / "dataset" / "render"
TABLE_NAME = "asset_embeddings"
EMBEDDING_DIM = 768

_model = None
_processor = None
_model_lock = threading.Lock()
_BATCH_SIZE = 32


def _load_model():
    global _model, _processor
    if _model is not None:
        return _model, _processor
    with _model_lock:
        if _model is None:
            from transformers import AutoModel, AutoProcessor
            from huggingface_hub import try_to_load_from_cache
            model_name = "google/siglip2-base-patch16-224"
            is_cached = try_to_load_from_cache(model_name, "config.json") is not None
            logger.info("Loading %s (cached=%s)...", model_name, is_cached)
            _model = AutoModel.from_pretrained(model_name, local_files_only=is_cached).eval()
            _processor = AutoProcessor.from_pretrained(model_name, local_files_only=is_cached)
            logger.info("Model loaded")
    return _model, _processor


def embed_texts(texts: list[str]) -> np.ndarray:
    model, processor = _load_model()
    inputs = processor(text=texts, padding=True, truncation=True, return_tensors="pt")
    with torch.no_grad():
        emb = model.get_text_features(**inputs)
    emb = emb / emb.norm(dim=-1, keepdim=True)
    return emb.cpu().numpy()


def embed_images(image_paths: list[str]) -> np.ndarray:
    model, processor = _load_model()
    images = [Image.open(p).convert("RGB") for p in image_paths]
    inputs = processor(images=images, return_tensors="pt")
    with torch.no_grad():
        emb = model.get_image_features(**inputs)
    emb = emb / emb.norm(dim=-1, keepdim=True)
    return emb.cpu().numpy()


def get_pg_connection():
    user = os.environ["DB_POSTGRES_USER"]
    password = os.environ["DB_POSTGRES_PASSWORD"]
    host = os.environ.get("DB_HOST", "postgres")
    return psycopg2.connect(f"postgresql://{user}:{password}@{host}:5432/livinit")


def query_similar(conn, embedding: np.ndarray | list[float], top_k: int = 100) -> list[tuple[str, float]]:
    emb_list = embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT uid, 1 - dist as score FROM (SELECT uid, embedding <=> %s::vector as dist FROM {TABLE_NAME} ORDER BY dist LIMIT %s) sub",
            (emb_list, top_k),
        )
        return cur.fetchall()


def _table_exists(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name=%s)",
            (TABLE_NAME,),
        )
        return cur.fetchone()[0]


def _get_row_count(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        return cur.fetchone()[0]


def _create_vector_table(conn):
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                uid TEXT PRIMARY KEY,
                embedding vector({EMBEDDING_DIM}),
                category TEXT
            )
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS {TABLE_NAME}_embedding_idx
            ON {TABLE_NAME} USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)
    conn.commit()
    logger.info("Created vector table %s", TABLE_NAME)


def _insert_embeddings(conn, rows: list[tuple[str, list[float], str]]):
    with conn.cursor() as cur:
        execute_values(
            cur,
            f"INSERT INTO {TABLE_NAME} (uid, embedding, category) VALUES %s ON CONFLICT (uid) DO UPDATE SET embedding = EXCLUDED.embedding, category = EXCLUDED.category",
            rows,
            template="(%s, %s::vector, %s)",
        )
    conn.commit()


def _embed_assets_batch(assets: list[dict], render_dir: Path, batch_size: int = _BATCH_SIZE) -> list[tuple[str, list[float], str]]:
    results = []
    for i in range(0, len(assets), batch_size):
        batch = assets[i : i + batch_size]
        texts = [f"Category: {a['category']}. {a['description']}. Materials: {', '.join(a.get('materials', []))}" for a in batch]
        text_embs = embed_texts(texts)

        image_paths, image_indices = [], []
        for j, a in enumerate(batch):
            p = render_dir / f"{a['uid']}.png"
            if p.exists():
                image_paths.append(str(p))
                image_indices.append(j)

        if image_paths:
            img_embs = embed_images(image_paths)
            for idx, j in enumerate(image_indices):
                text_embs[j] = (text_embs[j] + img_embs[idx]) / 2

        results.extend((a["uid"], text_embs[j].tolist(), a["category"]) for j, a in enumerate(batch))
        logger.info("Embedded %d/%d assets", min(i + batch_size, len(assets)), len(assets))

    return results


def init_vector_store_node(state: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()

    with open(_DATASET_PATH) as f:
        assets = json.load(f)

    conn = get_pg_connection()

    if _table_exists(conn) and _get_row_count(conn) >= len(assets):
        log_duration("INIT VECTOR STORE (skipped)", start)
        conn.close()
        return {}

    _create_vector_table(conn)
    rows = _embed_assets_batch(assets, _RENDER_DIR)
    _insert_embeddings(conn, rows)
    conn.close()

    log_duration("INIT VECTOR STORE", start)
    return {}
