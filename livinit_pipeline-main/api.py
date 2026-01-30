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
    export_glb: bool = Field(default=False, description="Export GLB file in addition to USDZ")
    pause_for_review: bool = Field(default=False, description="Pause after initial layout. Sends review_pause event with selected_assets and layout_preview_path. Resume via POST /pipeline/resume with optional revision_prompt.")

    model_config = {"json_schema_extra": {"examples": [{"user_intent": "Modern minimalist living room", "budget": 5000.0, "usdz_path": "dataset/room/Project-2510280721.usdz", "run_select_assets": True, "run_initial_layout": True, "run_refine_layout": True, "run_layoutvlm": True, "run_render_scene": True, "export_glb": False}]}}


class ResumeRequest(BaseModel):
    """Request body for resuming a paused pipeline with optional asset revision."""
    run_dir: str = Field(
        description="Run directory name from the paused pipeline (from review_pause event)",
        json_schema_extra={"examples": ["20260109_142522"]}
    )
    revision_prompt: str | None = Field(
        default=None,
        description="Natural language instruction to modify asset selection. When provided, re-runs select_assets with the revision context.",
        json_schema_extra={"examples": [
            "change the sofa to a green one",
            "remove the floor lamp",
            "use a smaller coffee table",
            "add a reading chair near the window"
        ]}
    )
    export_glb: bool = Field(default=False, description="Export GLB file in addition to USDZ")

    model_config = {"json_schema_extra": {"examples": [
        {"run_dir": "20260109_142522"},
        {"run_dir": "20260109_142522", "revision_prompt": "change the sofa to a green velvet one"},
        {"run_dir": "20260109_142522", "export_glb": True}
    ]}}


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
4. **3D Rendering** - Final USDZ/GLB scene with top and perspective views

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


def build_nodes(req: PipelineRequest, phase: str = "full") -> dict:
    """Build node list based on request parameters.

    phase: "full" for complete pipeline, "before_review" for up to layout_preview, "after_review" for rest
    """
    nodes = {}

    if phase in ("full", "before_review"):
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

    if phase in ("full", "after_review"):
        if req.run_refine_layout:
            nodes["refine_layout"] = refine_layout_node
            nodes["layout_preview_refine"] = lambda state: layout_preview_node(state, "layout_preview_refine_path", "layout_preview_refine.png", "refined_layout")
        if USD_AVAILABLE and req.run_layoutvlm:
            nodes["layoutvlm"] = run_layoutvlm_node
            nodes["layout_preview_post"] = lambda state: layout_preview_node(state, "layout_preview_post_path", "layout_preview_post.png", "layoutvlm_layout")
        if USD_AVAILABLE and req.run_render_scene:
            nodes["render_scene"] = lambda state, glb=req.export_glb: render_scene_node(state, export_glb=glb)

    return nodes


# In-memory store for paused pipeline states (in production, use Redis or similar)
_paused_pipelines: dict[str, dict] = {}


async def pipeline_stream_generator(req: PipelineRequest, phase: str = "full", resume_state: dict | None = None):
    """Generator that yields SSE events for pipeline progress."""
    pipeline_nodes = build_nodes(req, phase)
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
        if resume_state:
            # Resuming from paused state
            state = resume_state
            manager = state["asset_manager"]
            usdz_path = state["usdz_path"]
        else:
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
            csv_lines = ["uid,category,price,width,depth,height,materials,color,style,shape,asset_description,description"]
            for a in all_assets:
                csv_lines.append(
                    f'{a["uid"]},{a["category"]},{a["price"]},{a["width"]},{a["depth"]},{a["height"]},'
                    f'"{a["materials"]}",{a.get("asset_color","")},{a.get("asset_style","")},{a.get("asset_shape","")},'
                    f'"{a.get("asset_description","")}","{a["description"][:100]}"'
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

            # Pause for review after layout_preview if requested
            if name == "layout_preview" and req.pause_for_review and phase == "before_review":
                run_name = Path(state["run_dir"]).name
                _paused_pipelines[run_name] = state
                selected_assets = [{"uid": a["uid"], "category": a.get("category", ""), "price": a.get("price", 0)} for a in state.get("selected_assets", [])]
                yield send_event("review_pause", {
                    "run_dir": run_name,
                    "layout_preview_path": state.get("layout_preview_path"),
                    "selected_assets": selected_assets,
                    "total_cost": state.get("total_cost", 0),
                    "message": "Review layout and optionally revise assets. Call /pipeline/resume to continue."
                })
                return

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
        logger.info(f"  Final GLB: {state.get('final_glb_path', 'N/A')}")
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
                "final_glb_path": state.get("final_glb_path"),
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
- `render_scene` - Render final 3D scene (USDZ, optionally GLB)

**Note:** Asset sync, topdown renders, descriptions, and vector store are handled by daily warmup.

**Review Mode:** Set `pause_for_review: true` to pause after initial layout for user review.

**SSE Event Types:**
- `start` - Pipeline started, includes node list
- `node_start` - Node execution started
- `node_progress` - Node progress update (current/total)
- `node_complete` - Node finished with results
- `heartbeat` - Keep-alive during long operations
- `review_pause` - Pipeline paused for review (see below)
- `complete` - Pipeline finished successfully
- `error` - Pipeline failed with error message

**Sample `review_pause` event (when pause_for_review=true):**
```json
{
  "type": "review_pause",
  "run_dir": "20260109_142522",
  "layout_preview_path": "runs/20260109_142522/draw_layout_preview/layout_preview.png",
  "selected_assets": [
    {"uid": "sofa_123", "category": "sofa", "price": 599.0},
    {"uid": "table_45", "category": "coffee_table", "price": 199.0}
  ],
  "total_cost": 798.0,
  "message": "Review layout and optionally revise assets. Call /pipeline/resume to continue."
}
```
To continue, call `POST /pipeline/resume` with `{"run_dir": "20260109_142522"}` or include `revision_prompt` to modify assets.

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
    "final_glb_path": "runs/20260109_142522/render_scene/room_with_assets_final.glb",
    "render_top_view": "runs/20260109_142522/render_scene/render_top.png",
    "render_perspective_view": "runs/20260109_142522/render_scene/render_perspective.png"
  }
}
```
Note: `final_glb_path` is only present when `export_glb=true` is set in the request.
""",
    tags=["Pipeline"],
    response_description="Server-Sent Events stream with pipeline progress"
)
async def run_pipeline(req: PipelineRequest):
    """Run the full pipeline with streaming progress updates."""
    phase = "before_review" if req.pause_for_review else "full"
    return StreamingResponse(
        pipeline_stream_generator(req, phase=phase),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.post(
    "/pipeline/resume",
    summary="Resume paused pipeline",
    description="""
Resume a pipeline that was paused for review (when `pause_for_review=true` was set).

## Usage

**Continue without changes:**
```json
{"run_dir": "20260109_142522"}
```

**Revise assets before continuing:**
```json
{"run_dir": "20260109_142522", "revision_prompt": "change the sofa to a green velvet one"}
```

**Export GLB in addition to USDZ:**
```json
{"run_dir": "20260109_142522", "export_glb": true}
```

## Revision Behavior

When `revision_prompt` is provided:
1. **Asset Re-selection** - LLM re-runs asset selection with revision context
2. **Layout Decision** - If asset categories change, regenerates layout; otherwise swaps UIDs in existing layout
3. **Continue Pipeline** - Runs remaining stages (refine_layout, layoutvlm, render_scene)

## SSE Event Types

Same as `/pipeline` endpoint, plus:
- `start` with `mode: "revision"` indicates revision mode
- Node list dynamically includes/excludes `initial_layout` based on whether categories changed

**Sample revision `start` event:**
```json
{
  "type": "start",
  "nodes": ["select_assets", "validate_and_cost", "initial_layout", "layout_preview", "refine_layout", "layoutvlm", "render_scene"],
  "mode": "revision"
}
```

**Sample `complete` event:**
```json
{
  "type": "complete",
  "status": "success",
  "message": "Pipeline completed with revision",
  "data": {
    "run_dir": "20260109_142522",
    "selected_uids": ["green_sofa_42", "coffee_table_1"],
    "total_cost": 850.0,
    "layout_preview_path": "runs/20260109_142522/draw_layout_preview/layout_preview.png",
    "layout_preview_refine_path": "runs/20260109_142522/draw_layout_preview/layout_preview_refine.png",
    "final_usdz_path": "runs/20260109_142522/render_scene/room_with_assets_final.usdz",
    "final_glb_path": "runs/20260109_142522/render_scene/room_with_assets_final.glb",
    "render_top_view": "runs/20260109_142522/render_scene/render_top.png",
    "render_perspective_view": "runs/20260109_142522/render_scene/render_perspective.png"
  }
}
```
Note: `final_glb_path` is only present when `export_glb=true` is set.
""",
    tags=["Pipeline"],
    response_description="Server-Sent Events stream with pipeline progress",
    responses={404: {"description": "No paused pipeline found for the given run_dir"}}
)
async def resume_pipeline(req: ResumeRequest):
    """Resume a paused pipeline, optionally with asset revision."""
    if req.run_dir not in _paused_pipelines:
        raise HTTPException(status_code=404, detail=f"No paused pipeline found for run_dir: {req.run_dir}")

    state = _paused_pipelines.pop(req.run_dir)

    if req.revision_prompt:
        # Re-run from select_assets with revision
        state["asset_revision_prompt"] = req.revision_prompt
        # Build a new request with same parameters
        pipeline_req = PipelineRequest(
            user_intent=state.get("user_intent", "Modern minimalist living room"),
            budget=state.get("budget", 5000.0),
            usdz_path=state.get("usdz_path", ""),
            run_select_assets=True,
            run_initial_layout=True,
            run_refine_layout=True,
            run_layoutvlm=True,
            run_render_scene=True,
        )

        async def revision_generator():
            """Run revision: select_assets -> (maybe initial_layout) -> layout_preview -> rest."""
            # Start new revision in same run folder
            manager = state["asset_manager"]
            rev_num = manager.start_revision()
            logger.info(f"[REVISION] Starting revision {rev_num} in {manager.run_dir}")

            def send_event(event_type: str, data: dict):
                return f"data: {json.dumps({'type': event_type, **data})}\n\n"

            def get_category_counts(assets):
                from collections import Counter
                return Counter(a.get("category", "") for a in assets)

            # Store previous assets for comparison
            prev_assets = state.get("selected_assets", [])
            prev_layout = state.get("initial_layout", {})
            prev_counts = get_category_counts(prev_assets)

            node_names = ["select_assets", "validate_and_cost"]

            # Run select_assets first to determine if we need relayout
            start_time = time.time()
            updates = select_assets_llm_node(state)
            state.update(updates)
            select_elapsed = round(time.time() - start_time, 2)

            start_time = time.time()
            updates = validate_and_cost_node(state)
            state.update(updates)
            validate_elapsed = round(time.time() - start_time, 2)

            # Check if we need relayout
            new_assets = state.get("selected_assets", [])
            new_counts = get_category_counts(new_assets)
            needs_relayout = prev_counts != new_counts

            # Build remaining node list
            if needs_relayout:
                node_names.append("initial_layout")
            node_names.append("layout_preview")
            node_names.extend(["refine_layout", "layout_preview_refine"])
            if USD_AVAILABLE:
                node_names.extend(["layoutvlm", "layout_preview_post", "render_scene"])

            # Now send start with complete node list
            yield send_event("start", {"nodes": node_names, "mode": "revision"})

            # Emit already-completed nodes
            yield send_event("node_start", {"node": "select_assets", "index": 0})
            yield send_event("node_complete", {"node": "select_assets", "index": 0, "elapsed": select_elapsed, "result": {k: v for k, v in state.items() if k not in ("asset_manager", "progress_callback") and k.startswith("selected")}})
            yield send_event("node_start", {"node": "validate_and_cost", "index": 1})
            yield send_event("node_complete", {"node": "validate_and_cost", "index": 1, "elapsed": validate_elapsed, "result": {"selected_uids": state.get("selected_uids", []), "total_cost": state.get("total_cost", 0)}})

            current_idx = 2
            if needs_relayout:
                logger.info("[REVISION] Asset categories changed, re-running initial_layout")
                yield send_event("node_start", {"node": "initial_layout", "index": current_idx})
                start_time = time.time()
                updates = generate_initial_layout_node(state)
                state.update(updates)
                elapsed = round(time.time() - start_time, 2)
                yield send_event("node_complete", {"node": "initial_layout", "index": current_idx, "elapsed": elapsed, "result": {k: v for k, v in updates.items() if k != "asset_manager"}})
                current_idx += 1
            else:
                logger.info("[REVISION] Asset categories unchanged, swapping UIDs in layout")
                prev_by_cat = {}
                for a in prev_assets:
                    prev_by_cat.setdefault(a.get("category", ""), []).append(a["uid"])
                new_by_cat = {}
                for a in new_assets:
                    new_by_cat.setdefault(a.get("category", ""), []).append(a["uid"])
                uid_map = {old: new for cat in prev_by_cat for old, new in zip(prev_by_cat[cat], new_by_cat.get(cat, []))}
                state["initial_layout"] = {uid_map.get(uid, uid): p for uid, p in prev_layout.items()}

            # Run layout_preview
            yield send_event("node_start", {"node": "layout_preview", "index": current_idx})
            start_time = time.time()
            updates = layout_preview_node(state, "layout_preview_path", "layout_preview.png", "initial_layout")
            state.update(updates)
            elapsed = round(time.time() - start_time, 2)
            yield send_event("node_complete", {"node": "layout_preview", "index": current_idx, "elapsed": elapsed, "result": {k: v for k, v in updates.items() if k != "asset_manager"}})
            current_idx += 1

            # Run remaining nodes
            remaining = [
                ("refine_layout", refine_layout_node),
                ("layout_preview_refine", lambda s: layout_preview_node(s, "layout_preview_refine_path", "layout_preview_refine.png", "refined_layout")),
            ]
            if USD_AVAILABLE:
                remaining.extend([
                    ("layoutvlm", run_layoutvlm_node),
                    ("layout_preview_post", lambda s: layout_preview_node(s, "layout_preview_post_path", "layout_preview_post.png", "layoutvlm_layout")),
                    ("render_scene", lambda s: render_scene_node(s, export_glb=req.export_glb)),
                ])
            for name, node_fn in remaining:
                yield send_event("node_start", {"node": name, "index": current_idx})
                start_time = time.time()
                if asyncio.iscoroutinefunction(node_fn):
                    updates = await node_fn(state)
                else:
                    updates = await asyncio.to_thread(node_fn, state)
                state.update(updates)
                elapsed = round(time.time() - start_time, 2)
                yield send_event("node_complete", {"node": name, "index": current_idx, "elapsed": elapsed, "result": {k: v for k, v in updates.items() if k != "asset_manager"}})
                current_idx += 1

            # Complete - match main pipeline output format
            run_name = Path(state["run_dir"]).name
            layoutvlm_gif_path = str(Path(state["run_dir"]) / STAGE_DIRS["layoutvlm"] / "optimization.gif")
            if not Path(layoutvlm_gif_path).exists():
                layoutvlm_gif_path = None
            yield send_event("complete", {
                "status": "success",
                "message": "Pipeline completed with revision",
                "data": {
                    "run_dir": run_name,
                    "selected_uids": [a["uid"] for a in state.get("selected_assets", [])],
                    "total_cost": state.get("total_cost", 0),
                    "layoutvlm_layout": state.get("layoutvlm_layout"),
                    "layout_preview_path": state.get("layout_preview_path"),
                    "layout_preview_refine_path": state.get("layout_preview_refine_path"),
                    "layout_preview_post_path": state.get("layout_preview_post_path"),
                    "layoutvlm_gif_path": layoutvlm_gif_path,
                    "final_usdz_path": state.get("final_usdz_path"),
                    "final_glb_path": state.get("final_glb_path"),
                    "render_top_view": state.get("render_top_view"),
                    "render_perspective_view": state.get("render_perspective_view"),
                }
            })

        return StreamingResponse(
            revision_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )
    else:
        # Continue without revision - just run remaining nodes
        pipeline_req = PipelineRequest(
            user_intent=state.get("user_intent", "Modern minimalist living room"),
            budget=state.get("budget", 5000.0),
            usdz_path=state.get("usdz_path", ""),
            run_refine_layout=True,
            run_layoutvlm=True,
            run_render_scene=True,
        )
        return StreamingResponse(
            pipeline_stream_generator(pipeline_req, phase="after_review", resume_state=state),
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
    "/download/glb/{run_dir:path}",
    summary="Download final GLB",
    description="Download the final rendered GLB file. Only available if export_glb=true was set.",
    tags=["Results"],
    responses={404: {"description": "GLB file not found"}}
)
async def download_glb(run_dir: str):
    """Download final GLB scene file."""
    glb_path = Path("runs") / run_dir / STAGE_DIRS["render_scene"] / "room_with_assets_final.glb"
    if not glb_path.exists():
        raise HTTPException(status_code=404, detail="GLB file not found")
    return FileResponse(
        glb_path,
        media_type="model/gltf-binary",
        filename="room_with_assets.glb",
        headers={"Content-Disposition": "attachment; filename=room_with_assets.glb"}
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
