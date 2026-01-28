import asyncio
import time
import logging
from pathlib import Path
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
import json
from mangum import Mangum
from dotenv import load_dotenv

from pipeline.core.asset_manager import AssetManager
from pipeline.core.pipeline_shared import STAGE_DIRS
from pipeline.nodes.init_vector_store import init_vector_store_node
from pipeline.nodes.rag_scope_assets import rag_scope_assets_node
from pipeline.nodes.select_assets_llm import select_assets_llm_node
from pipeline.nodes.download_assets import sync_assets_node, download_room_usdz
from pipeline.nodes.render_topdown import render_topdown_node
from pipeline.nodes.validate_and_cost import validate_and_cost_node
from pipeline.nodes.layout_preview import layout_preview_node
from pipeline.nodes.initial_layout import generate_initial_layout_node
from pipeline.nodes.refine_layout import refine_layout_node
from pipeline.nodes.generate_asset_descriptions import generate_asset_descriptions_node
from pipeline.mock_data import MOCK_SELECTED_ASSETS, MOCK_INITIAL_LAYOUT, MOCK_REFINED_LAYOUT, MOCK_ROOM_GEOMETRY, MOCK_CONSTRAINT_PROGRAM

# Optional imports - usd-core not available on all platforms
try:
    from pipeline.nodes.extract_room import extract_room_node
    from pipeline.nodes.run_layoutvlm import run_layoutvlm_node
    from pipeline.nodes.render_scene import render_scene_node
    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False
    extract_room_node = None
    run_layoutvlm_node = None
    render_scene_node = None

load_dotenv()
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

NODES = {
    "rag_scope_assets": rag_scope_assets_node,
    "select_assets": select_assets_llm_node,
    "validate_and_cost": validate_and_cost_node,
}
if USD_AVAILABLE:
    NODES["extract_room"] = extract_room_node
NODES["initial_layout"] = generate_initial_layout_node
NODES["layout_preview"] = lambda state: layout_preview_node(state, "layout_preview_path", "layout_preview.png", "initial_layout")
NODES["refine_layout"] = refine_layout_node
NODES["layout_preview_refine"] = lambda state: layout_preview_node(state, "layout_preview_refine_path", "layout_preview_refine.png", "refined_layout")
if USD_AVAILABLE:
    NODES["layoutvlm"] = run_layoutvlm_node
    NODES["render_scene"] = render_scene_node


class PipelineRequest(BaseModel):
    """Request body for running the full pipeline."""
    user_intent: str = Field(
        default="Modern minimalist living room",
        description="Natural language description of desired room style and furniture",
        json_schema_extra={"examples": ["Cozy reading nook with warm lighting", "Scandinavian living room under $3000"]}
    )
    budget: float = Field(
        default=5000.0,
        description="Maximum budget in USD for furniture selection",
        ge=0,
        json_schema_extra={"examples": [2500.0, 5000.0, 10000.0]}
    )
    usdz_path: str = Field(
        default="dataset/room/Project-2510280721.usdz",
        description="Path to room USDZ file (local or S3)",
        json_schema_extra={"examples": ["dataset/room/Project-2510280721.usdz", "s3://bucket/room.usdz"]}
    )
    run_rag_scope: bool = Field(default=False, description="Run RAG-based scoping of assets by user intent")
    run_select_assets: bool = Field(default=True, description="Run RAG-based asset selection (disable to use mock assets)")
    run_initial_layout: bool = Field(default=True, description="Run LLM-based initial layout generation")
    run_refine_layout: bool = Field(default=True, description="Refine layout and generate constraint program")
    run_layoutvlm: bool = Field(default=True, description="Run VLM-based layout optimization solver")
    run_render_scene: bool = Field(default=True, description="Render final USDZ scene with assets")

    model_config = {"json_schema_extra": {"examples": [{"user_intent": "Modern minimalist living room", "budget": 5000.0, "usdz_path": "dataset/room/Project-2510280721.usdz", "run_select_assets": True, "run_initial_layout": True, "run_refine_layout": True, "run_layoutvlm": True, "run_render_scene": True}]}}


class NodeRequest(BaseModel):
    """Request body for running a single pipeline node."""
    node_name: str = Field(description="Name of the pipeline node to run")
    state: dict[str, Any] | None = Field(default=None, description="Custom state to pass to the node (overrides mock state)")
    use_mock: bool = Field(default=True, description="Use mock state for testing (set False for custom state)")

    model_config = {"json_schema_extra": {"examples": [{"node_name": "select_assets", "use_mock": True}, {"node_name": "initial_layout", "state": {"user_intent": "Cozy bedroom"}, "use_mock": False}]}}


async def _warmup_once():
    """Run sync, render_topdown, generate_asset_descriptions, and init_vector_store once."""
    state = {}
    logger.info("[warmup] Running sync_assets...")
    state.update(await sync_assets_node(state))
    logger.info("[warmup] Running render_topdown...")
    state.update(await render_topdown_node(state))
    logger.info("[warmup] Running generate_asset_descriptions...")
    state.update(await generate_asset_descriptions_node(state))
    logger.info("[warmup] Running init_vector_store...")
    state.update(await asyncio.to_thread(init_vector_store_node, state))
    logger.info("[warmup] Complete")


async def _warmup_daily():
    """Run warmup pipeline every 24 hours."""
    while True:
        try:
            await _warmup_once()
        except Exception as e:
            logger.warning(f"[warmup] Failed: {e}")
        await asyncio.sleep(24 * 60 * 60)  # 24 hours


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Preload embedding model then run warmup daily in background
    from pipeline.nodes.init_vector_store import _load_model
    await asyncio.to_thread(_load_model)
    logger.info("Embedding model preloaded")
    asyncio.create_task(_warmup_daily())
    yield


app = FastAPI(
    title="Livinit Pipeline API",
    description="""
Interior design automation pipeline that selects furniture based on user intent,
generates optimal layouts using VLM, and renders 3D scenes.

## Pipeline Flow
1. **Asset Selection** - RAG-based furniture selection matching user intent and budget
2. **Layout Generation** - LLM generates initial furniture placement
3. **Layout Optimization** - VLM-based constraint solver optimizes positions
4. **3D Rendering** - Final USDZ scene with top and perspective views

## Event Streaming
The `/pipeline` endpoint uses Server-Sent Events (SSE) for real-time progress.
""",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FRONTEND_DIR = Path(__file__).parent / "frontend"


@app.get("/", summary="Serve frontend UI", tags=["Frontend"], include_in_schema=False)
async def serve_ui():
    """Serve the pipeline frontend interface."""
    return FileResponse(FRONTEND_DIR / "index.html")


def create_run_context(usdz_path: str) -> AssetManager:
    if not USD_AVAILABLE:
        raise HTTPException(status_code=501, detail="Full pipeline requires usd-core (not available in Docker). Use /nodes endpoints with mock data.")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return AssetManager(Path("runs") / timestamp)


def build_initial_state(req: PipelineRequest, manager: AssetManager) -> dict[str, Any]:
    return {
        "run_dir": str(manager.run_dir),
        "asset_manager": manager,
        "user_intent": req.user_intent,
        "usdz_path": req.usdz_path,
        "budget": req.budget,
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
        "layout_preview_refine_path": "",
        "layout_preview_post_path": "",
        "boundary": {},
        "assets": {},
        "void_assets": {},
    }


def build_nodes(req: PipelineRequest) -> dict:
    """Build node list based on request parameters."""
    nodes = {}
    if USD_AVAILABLE:
        nodes["extract_room"] = extract_room_node
    if req.run_rag_scope:
        nodes["rag_scope_assets"] = rag_scope_assets_node
    if req.run_select_assets:
        nodes["select_assets"] = select_assets_llm_node
        nodes["validate_and_cost"] = validate_and_cost_node
    if req.run_initial_layout:
        nodes["initial_layout"] = generate_initial_layout_node
    nodes["layout_preview"] = lambda state: layout_preview_node(state, "layout_preview_path", "layout_preview.png", "initial_layout")
    if req.run_refine_layout:
        nodes["refine_layout"] = refine_layout_node
        nodes["layout_preview_refine"] = lambda state: layout_preview_node(state, "layout_preview_refine_path", "layout_preview_refine.png", "refined_layout")
    if USD_AVAILABLE and req.run_layoutvlm:
        nodes["layoutvlm"] = run_layoutvlm_node
        nodes["layout_preview_post"] = lambda state: layout_preview_node(state, "layout_preview_post_path", "layout_preview_post.png", "layoutvlm_layout")
    if USD_AVAILABLE and req.run_render_scene:
        nodes["render_scene"] = render_scene_node
    return nodes


async def pipeline_stream_generator(req: PipelineRequest):
    """Generator that yields SSE events for pipeline progress."""
    pipeline_nodes = build_nodes(req)
    node_names = list(pipeline_nodes.keys())
    logger.info("=" * 60)
    logger.info("Pipeline starting")
    logger.info(f"  Intent: {req.user_intent}")
    logger.info(f"  Budget: ${req.budget}")
    logger.info(f"  USDZ: {req.usdz_path}")
    logger.info(f"  Run rag_scope: {req.run_rag_scope}")
    logger.info(f"  Run select_assets: {req.run_select_assets}")
    logger.info(f"  Run initial_layout: {req.run_initial_layout}")
    logger.info(f"  Run render_scene: {req.run_render_scene}")
    logger.info(f"  Run refine_layout: {req.run_refine_layout}")
    logger.info(f"  Run layoutvlm: {req.run_layoutvlm}")
    logger.info(f"  Nodes: {node_names}")
    logger.info("=" * 60)

    def send_event(event_type: str, data: dict):
        return f"data: {json.dumps({'type': event_type, **data})}\n\n"

    yield send_event("start", {"nodes": node_names, "total": len(node_names)})

    current_idx = 0
    progress_queue: asyncio.Queue = asyncio.Queue()

    try:
        usdz_path = await download_room_usdz(req.usdz_path)
        manager = await asyncio.to_thread(create_run_context, usdz_path)
        state = build_initial_state(req, manager)
        state["usdz_path"] = usdz_path
        manager.write_json(STAGE_DIRS["meta"], "run_meta.json", {
            "timestamp": time.strftime("%Y%m%d_%H%M%S"),
            "user_intent": req.user_intent,
            "budget": req.budget,
        })

        # Inject full asset catalog when rag_scope is disabled (for select_assets_llm to choose from)
        if not req.run_rag_scope:
            dataset_path = Path(__file__).parent / "dataset" / "processed.json"
            with open(dataset_path) as f:
                all_assets = json.load(f)
            render_dir = Path(__file__).parent / "dataset" / "render"
            for a in all_assets:
                a["score"] = 0.0
                a["image_path"] = str(render_dir / f"{a['uid']}.png")
            csv_lines = ["uid,category,price,width,depth,height,materials,color,style,shape,asset_description,description,score,image_path"]
            for a in all_assets:
                csv_lines.append(
                    f'{a["uid"]},{a["category"]},{a["price"]},{a["width"]},{a["depth"]},{a["height"]},'
                    f'"{a["materials"]}",{a.get("asset_color","")},{a.get("asset_style","")},{a.get("asset_shape","")},'
                    f'"{a.get("asset_description","")}","{a["description"][:100]}",{a["score"]:.4f},{a["image_path"]}'
                )
            state["assets_csv"] = "\n".join(csv_lines)
            state["assets_data"] = all_assets
            logger.info(f"[FULL CATALOG] Injected {len(all_assets)} assets (RAG scope disabled)")

        # Inject mock assets when select_assets is disabled
        if not req.run_select_assets:
            state["assets_data"] = MOCK_SELECTED_ASSETS
            state["selected_assets"] = MOCK_SELECTED_ASSETS
            state["selected_uids"] = [a["uid"] for a in MOCK_SELECTED_ASSETS]
            state["total_cost"] = sum(a.get("price", 0) for a in MOCK_SELECTED_ASSETS)
            logger.info(f"[MOCK] Injected {len(MOCK_SELECTED_ASSETS)} mock assets, total cost=${state['total_cost']}")

        # Inject mock layout when initial_layout is disabled
        if not req.run_initial_layout:
            state["initial_layout"] = MOCK_INITIAL_LAYOUT
            logger.info(f"[MOCK] Injected mock layout with {len(MOCK_INITIAL_LAYOUT)} placements")

        for current_idx, (name, node_fn) in enumerate(pipeline_nodes.items()):
            yield send_event("node_start", {"node": name, "index": current_idx})
            logger.info(f"[{name}] Starting...")
            start_time = time.time()

            # Progress callback for nodes that support it
            async def progress_callback(current: int, total: int):
                await progress_queue.put(("progress", current, total))

            state["progress_callback"] = progress_callback

            if asyncio.iscoroutinefunction(node_fn):
                # Run node and drain progress queue concurrently
                node_task = asyncio.create_task(node_fn(state))
                last_heartbeat = time.time()
                heartbeat_interval = 10
                while not node_task.done():
                    try:
                        event = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
                        if event[0] == "progress":
                            yield send_event("node_progress", {"node": name, "index": current_idx, "current": event[1], "total": event[2]})
                            last_heartbeat = time.time()
                    except asyncio.TimeoutError:
                        # Send heartbeat if no progress for a while
                        if time.time() - last_heartbeat >= heartbeat_interval:
                            yield send_event("heartbeat", {"node": name, "index": current_idx, "elapsed": round(time.time() - start_time, 1)})
                            last_heartbeat = time.time()
                updates = await node_task
                # Drain remaining progress events
                while not progress_queue.empty():
                    event = await progress_queue.get()
                    if event[0] == "progress":
                        yield send_event("node_progress", {"node": name, "index": current_idx, "current": event[1], "total": event[2]})
            else:
                # Run sync node in thread with periodic heartbeats to prevent SSE timeout
                loop = asyncio.get_event_loop()
                node_future = loop.run_in_executor(None, node_fn, state)
                heartbeat_interval = 10  # seconds
                while not node_future.done():
                    try:
                        updates = await asyncio.wait_for(asyncio.shield(node_future), timeout=heartbeat_interval)
                        break
                    except asyncio.TimeoutError:
                        yield send_event("heartbeat", {"node": name, "index": current_idx, "elapsed": round(time.time() - start_time, 1)})
                else:
                    updates = node_future.result()
            state.update(updates)

            elapsed = round(time.time() - start_time, 2)
            logger.info(f"[{name}] Completed in {elapsed}s")
            for k, v in updates.items():
                if k == "asset_manager":
                    continue
                if isinstance(v, list) and len(v) > 3:
                    logger.info(f"[{name}]   {k}: [{len(v)} items]")
                elif isinstance(v, dict) and len(v) > 3:
                    logger.info(f"[{name}]   {k}: {{{len(v)} keys}}")
                elif isinstance(v, str) and len(v) > 200:
                    logger.info(f"[{name}]   {k}: {v[:200]}...")
                else:
                    logger.info(f"[{name}]   {k}: {v}")
            # Serialize node result (exclude non-serializable objects)
            result_preview = {}
            for k, v in updates.items():
                if k == "asset_manager":
                    continue
                try:
                    json.dumps(v)
                    result_preview[k] = v
                except (TypeError, ValueError):
                    result_preview[k] = str(type(v).__name__)
            yield send_event("node_complete", {"node": name, "index": current_idx, "elapsed": elapsed, "result": result_preview})

        result = {k: v for k, v in state.items() if k not in ("asset_manager", "progress_callback")}
        manager.write_json(STAGE_DIRS["meta"], "final_state.json", result)

        # Build gif path from run directory
        layoutvlm_gif_path = str(Path(state["run_dir"]) / STAGE_DIRS["layoutvlm"] / "optimization.gif")
        if not Path(layoutvlm_gif_path).exists():
            layoutvlm_gif_path = None

        logger.info("=" * 60)
        logger.info("Pipeline complete!")
        logger.info(f"  Run dir: {state['run_dir']}")
        logger.info(f"  Selected assets: {state.get('selected_uids', [])}")
        logger.info(f"  Total cost: ${state.get('total_cost', 0):.2f}")
        logger.info(f"  Layout preview: {state.get('layout_preview_path', 'N/A')}")
        logger.info(f"  Layout preview refine: {state.get('layout_preview_refine_path', 'N/A')}")
        logger.info(f"  Layout preview post: {state.get('layout_preview_post_path', 'N/A')}")
        logger.info(f"  LayoutVLM gif: {layoutvlm_gif_path or 'N/A'}")
        logger.info(f"  Final USDZ: {state.get('final_usdz_path', 'N/A')}")
        logger.info(f"  Render top: {state.get('render_top_view', 'N/A')}")
        logger.info(f"  Render perspective: {state.get('render_perspective_view', 'N/A')}")
        logger.info("=" * 60)

        yield send_event("complete", {
            "status": "success",
            "message": "Pipeline completed successfully",
            "data": {
                "run_dir": Path(state["run_dir"]).name,
                "selected_uids": state["selected_uids"],
                "total_cost": state["total_cost"],
                "layoutvlm_layout": state.get("layoutvlm_layout"),
                "layout_preview_path": state.get("layout_preview_path"),
                "layout_preview_refine_path": state.get("layout_preview_refine_path"),
                "layout_preview_post_path": state.get("layout_preview_post_path"),
                "layoutvlm_gif_path": layoutvlm_gif_path,
                "final_usdz_path": state.get("final_usdz_path"),
                "render_top_view": state.get("render_top_view"),
                "render_perspective_view": state.get("render_perspective_view"),
            },
        })
    except Exception as e:
        import traceback
        logger.error(f"Pipeline error: {e}\n{traceback.format_exc()}")
        yield send_event("error", {"index": current_idx, "message": str(e)})


@app.post(
    "/pipeline",
    summary="Run full pipeline",
    description="""
Execute the complete interior design pipeline with real-time progress via SSE.

**Pipeline stages:**
- `extract_room` - Extract room geometry from USDZ
- `rag_scope_assets` - Load and scope assets by user intent via RAG
- `select_assets` - LLM selects furniture within budget
- `validate_and_cost` - Validate selection and compute cost
- `initial_layout` - LLM generates furniture placement
- `layout_preview` - Render layout preview image
- `refine_layout` - Analyze issues, fix layout, generate constraints
- `layout_preview_refine` - Render layout preview after refinement
- `layoutvlm` - VLM-based layout optimization
- `render_scene` - Render final 3D scene

**Note:** Asset sync, topdown renders, descriptions, and vector store are handled by daily warmup.

**SSE Event Types:**
- `start` - Pipeline started, includes node list
- `node_start` - Node execution started
- `node_progress` - Node progress update (current/total)
- `node_complete` - Node finished with results
- `heartbeat` - Keep-alive during long operations
- `complete` - Pipeline finished successfully
- `error` - Pipeline failed with error message

**Sample `complete` event output:**
```json
{
  "type": "complete",
  "status": "success",
  "message": "Pipeline completed successfully",
  "data": {
    "run_dir": "20260109_142522",
    "selected_uids": ["sectional_sofa_165", "coffee_table_1"],
    "total_cost": 706.0,
    "layoutvlm_layout": {},
    "layout_preview_path": "runs/20260109_142522/draw_layout_preview/layout_preview.png",
    "layout_preview_refine_path": "runs/20260109_142522/draw_layout_preview/layout_preview_refine.png",
    "layout_preview_post_path": "runs/20260109_142522/draw_layout_preview/layout_preview_post.png",
    "layoutvlm_gif_path": "runs/20260109_142522/layoutvlm/optimization.gif",
    "final_usdz_path": "runs/20260109_142522/render_scene/room_with_assets_final.usdz",
    "render_top_view": "runs/20260109_142522/render_scene/render_top.png",
    "render_perspective_view": "runs/20260109_142522/render_scene/render_perspective.png"
  }
}
```
""",
    tags=["Pipeline"],
    response_description="Server-Sent Events stream with pipeline progress"
)
async def run_pipeline(req: PipelineRequest):
    """Run the full pipeline with streaming progress updates."""
    return StreamingResponse(
        pipeline_stream_generator(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.post(
    "/nodes/{node_name}",
    summary="Run single node",
    description="""
Execute a single pipeline node for testing or debugging.

**Available nodes:** `extract_room`, `rag_scope_assets`,
`select_assets`, `validate_and_cost`, `initial_layout`, `layout_preview`,
`refine_layout`, `layout_preview_refine`, `layoutvlm`, `render_scene`

Use `use_mock=True` (default) for testing without real data.
Provide custom `state` with `use_mock=False` for actual execution.
""",
    tags=["Nodes"],
    responses={404: {"description": "Node not found"}, 400: {"description": "State required when use_mock=False"}}
)
async def run_node(node_name: str, req: NodeRequest | None = None):
    """Run a single pipeline node with mock or custom state."""
    if node_name not in NODES:
        raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found. Available: {list(NODES.keys())}")

    use_mock = req.use_mock if req else True
    custom_state = req.state if req and req.state else {}

    if use_mock:
        state = get_mock_state(node_name)
        state.update(custom_state)
    else:
        if not custom_state:
            raise HTTPException(status_code=400, detail="Must provide state when use_mock=False")
        state = custom_state
        if "asset_manager" not in state:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            state["asset_manager"] = AssetManager(Path("runs") / f"debug_{timestamp}")

    node_fn = NODES[node_name]
    updates = await node_fn(state) if asyncio.iscoroutinefunction(node_fn) else node_fn(state)
    state.update(updates)

    # Run layout_preview after initial_layout to return image with JSON
    if node_name == "initial_layout":
        preview_updates = layout_preview_node(state, "layout_preview_path", "layout_preview.png", "initial_layout")
        updates.update(preview_updates)

    return {"node": node_name, "result": {k: v for k, v in updates.items() if k != "asset_manager"}}


def get_mock_state(node_name: str) -> dict[str, Any]:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    run_dir = Path("runs") / f"mock_{timestamp}"
    manager = AssetManager(run_dir)

    base = {
        "run_dir": str(run_dir),
        "asset_manager": manager,
        "user_intent": "Modern minimalist living room",
        "usdz_path": "dataset/room/Project-2510280721.usdz",
        "budget": 5000.0,
        **MOCK_ROOM_GEOMETRY,
    }

    if node_name in ("extract_room", "rag_scope_assets"):
        return base

    if node_name == "select_assets":
        csv_lines = ["uid,category,price,width,depth,height,materials,description"]
        for a in MOCK_SELECTED_ASSETS:
            csv_lines.append(f'{a["uid"]},{a["category"]},{a["price"]},{a["width"]},{a["depth"]},{a["height"]},"{a["materials"]}","{a["description"]}"')
        return {**base, "assets_csv": "\n".join(csv_lines), "assets_data": MOCK_SELECTED_ASSETS}

    if node_name == "validate_and_cost":
        return {**base, "assets_data": MOCK_SELECTED_ASSETS, "selected_assets": MOCK_SELECTED_ASSETS[:3], "selected_uids": [a["uid"] for a in MOCK_SELECTED_ASSETS[:3]]}

    if node_name == "initial_layout":
        return {**base, "assets_data": MOCK_SELECTED_ASSETS, "selected_assets": MOCK_SELECTED_ASSETS}

    if node_name == "refine_layout":
        return {
            **base,
            "assets_data": MOCK_SELECTED_ASSETS,
            "selected_assets": MOCK_SELECTED_ASSETS,
            "selected_uids": [a["uid"] for a in MOCK_SELECTED_ASSETS],
            "initial_layout": MOCK_INITIAL_LAYOUT,
            "layout_preview_path": "",
        }

    if node_name == "layoutvlm":
        w, d = MOCK_ROOM_GEOMETRY["room_area"]
        return {
            **base,
            "assets_data": MOCK_SELECTED_ASSETS,
            "selected_assets": MOCK_SELECTED_ASSETS,
            "task_description": "Layout optimization for: Modern minimalist living room",
            "constraint_program": MOCK_CONSTRAINT_PROGRAM,
            "layout_groups": [],
            "initial_layout": MOCK_INITIAL_LAYOUT,
            "boundary": {"floor_vertices": [[0, 0, 0], [w, 0, 0], [w, d, 0], [0, d, 0]], "wall_height": 3.0},
            "assets": {},
            "void_assets": {},
        }

    if node_name in ("layout_preview", "layout_preview_refine", "layout_preview_post"):
        return {
            **base,
            "assets_data": MOCK_SELECTED_ASSETS,
            "selected_assets": MOCK_SELECTED_ASSETS,
            "initial_layout": MOCK_INITIAL_LAYOUT,
            "refined_layout": MOCK_REFINED_LAYOUT,
            "layoutvlm_layout": MOCK_INITIAL_LAYOUT,
        }

    if node_name == "render_scene":
        return {
            **base,
            "assets_data": MOCK_SELECTED_ASSETS,
            "initial_layout": MOCK_INITIAL_LAYOUT,
            "layoutvlm_layout": MOCK_INITIAL_LAYOUT,
            "final_usdz_path": None,
        }

    return base


@app.get(
    "/nodes",
    summary="List available nodes",
    description="Get list of all pipeline nodes available for execution.",
    tags=["Nodes"]
)
async def list_nodes():
    """List all available pipeline nodes."""
    return {"nodes": list(NODES.keys())}


@app.get(
    "/nodes/{node_name}/mock",
    summary="Get node mock state",
    description="Get the mock state used for testing a specific node. Useful for understanding expected input format.",
    tags=["Nodes"],
    responses={404: {"description": "Node not found"}}
)
async def get_node_mock(node_name: str):
    """Get mock state for a specific node."""
    if node_name not in NODES:
        raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found")
    state = get_mock_state(node_name)
    return {k: v for k, v in state.items() if k not in ("asset_manager", "run_dir")}


@app.get(
    "/health",
    summary="Health check",
    description="Simple health check endpoint for load balancers and monitoring.",
    tags=["System"]
)
async def health():
    """Check API health status."""
    return {"status": "ok"}


UPLOAD_DIR = Path("dataset/room")


@app.post(
    "/upload/room",
    summary="Upload USDZ room plan",
    description="Upload a USDZ room file. Returns the path to use with the `/pipeline` endpoint.",
    tags=["System"]
)
async def upload_room(file: UploadFile):
    """Upload USDZ room file and return path for pipeline."""
    if not file.filename.endswith(".usdz"):
        raise HTTPException(status_code=400, detail="File must be a .usdz file")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    file_path = UPLOAD_DIR / filename
    content = await file.read()
    file_path.write_bytes(content)
    return {
        "status": "success",
        "message": "Room uploaded successfully",
        "data": {"usdz_path": str(file_path)},
    }


@app.get(
    "/preview/{run_dir:path}",
    summary="Get layout preview",
    description="Serve the initial layout preview PNG image for a pipeline run.",
    tags=["Results"],
    responses={404: {"description": "Preview not found"}}
)
async def serve_preview(run_dir: str):
    """Serve layout preview image for a run."""
    preview_path = Path("runs") / run_dir / STAGE_DIRS["draw_layout_preview"] / "layout_preview.png"
    if not preview_path.exists():
        raise HTTPException(status_code=404, detail="Preview not found")
    return FileResponse(preview_path, media_type="image/png")


@app.get(
    "/download/usdz/{run_dir:path}",
    summary="Download final USDZ",
    description="Download the final rendered USDZ file with furniture placed in the room. Compatible with iOS AR Quick Look.",
    tags=["Results"],
    responses={404: {"description": "USDZ file not found"}}
)
async def download_usdz(run_dir: str):
    """Download final USDZ scene file."""
    usdz_path = Path("runs") / run_dir / STAGE_DIRS["render_scene"] / "room_with_assets_final.usdz"
    if not usdz_path.exists():
        raise HTTPException(status_code=404, detail="USDZ file not found")
    return FileResponse(
        usdz_path,
        media_type="model/vnd.usdz+zip",
        filename="room_with_assets.usdz",
        headers={"Content-Disposition": "attachment; filename=room_with_assets.usdz"}
    )


@app.get(
    "/render/{run_dir:path}/{view}",
    summary="Get rendered view",
    description="Serve rendered PNG image of the final scene. View can be 'top' (bird's eye) or 'perspective' (3D camera view).",
    tags=["Results"],
    responses={400: {"description": "Invalid view type"}, 404: {"description": "Render not found"}}
)
async def serve_render(run_dir: str, view: str):
    """Serve rendered scene view (top or perspective)."""
    if view not in ("top", "perspective"):
        raise HTTPException(status_code=400, detail="View must be 'top' or 'perspective'")
    render_path = Path("runs") / run_dir / STAGE_DIRS["render_scene"] / f"render_{view}.png"
    if not render_path.exists():
        raise HTTPException(status_code=404, detail=f"{view} view render not found")
    return FileResponse(render_path, media_type="image/png")


@app.get(
    "/layoutvlm-gif/{run_dir:path}",
    summary="Get optimization GIF",
    description="Serve animated GIF showing the LayoutVLM optimization process iterating furniture positions.",
    tags=["Results"],
    responses={404: {"description": "Optimization GIF not found"}}
)
async def serve_layoutvlm_gif(run_dir: str):
    """Serve LayoutVLM optimization animation."""
    gif_path = Path("runs") / run_dir / STAGE_DIRS["layoutvlm"] / "optimization.gif"
    if not gif_path.exists():
        raise HTTPException(status_code=404, detail="LayoutVLM gif not found")
    return FileResponse(gif_path, media_type="image/gif")


@app.get(
    "/preview-refine/{run_dir:path}",
    summary="Get post-refine preview",
    description="Serve layout preview PNG after refine_layout. Shows the layout after LLM refinement, before layoutvlm optimization.",
    tags=["Results"],
    responses={404: {"description": "Post-refine preview not found"}}
)
async def serve_preview_refine(run_dir: str):
    """Serve post-refine layout preview."""
    preview_path = Path("runs") / run_dir / STAGE_DIRS["draw_layout_preview"] / "layout_preview_refine.png"
    if not preview_path.exists():
        raise HTTPException(status_code=404, detail="Post-refine preview not found")
    return FileResponse(preview_path, media_type="image/png")


@app.get(
    "/preview-post/{run_dir:path}",
    summary="Get post-optimization preview",
    description="Serve layout preview PNG after LayoutVLM optimization. Compare with initial preview to see improvements.",
    tags=["Results"],
    responses={404: {"description": "Post-optimization preview not found"}}
)
async def serve_preview_post(run_dir: str):
    """Serve post-LayoutVLM layout preview."""
    preview_path = Path("runs") / run_dir / STAGE_DIRS["draw_layout_preview"] / "layout_preview_post.png"
    if not preview_path.exists():
        raise HTTPException(status_code=404, detail="Post-layoutvlm preview not found")
    return FileResponse(preview_path, media_type="image/png")


handler = Mangum(app, lifespan="off")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
