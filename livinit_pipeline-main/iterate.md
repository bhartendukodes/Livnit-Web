# Iteration API

Iterate on previous designs by providing an `output_id` and describing changes via `user_intent`.

## Endpoint

```
POST /pipeline
```

## Request

```json
{
  "output_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "user_intent": "change the sofa to green"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `output_id` | string | Yes | UUID from a previous pipeline run |
| `user_intent` | string | No | Describe changes (default: inherit previous intent) |
| `budget` | float | No | Override previous budget (default: inherit) |
| `export_glb` | bool | No | Export GLB in addition to USDZ |

## How It Works

1. **Load Previous State** - Fetches assets and layout from `output_id`
2. **Select New Assets** - LLM selects assets based on `user_intent`
3. **Smart Relayout** - Compares old vs new asset categories:
   - **Categories unchanged**: Swaps UIDs in existing layout (fast)
   - **Categories changed**: Regenerates layout from scratch
4. **Optimize & Render** - Runs refine_layout, layoutvlm, and render_scene

## Examples

```json
// Swap furniture
{"output_id": "...", "user_intent": "change the sofa to a blue velvet one"}

// Add items
{"output_id": "...", "user_intent": "add a floor lamp near the reading chair"}

// Remove items
{"output_id": "...", "user_intent": "remove the coffee table"}

// Style change
{"output_id": "...", "user_intent": "make it more minimalist, remove decorations"}

// Re-run with GLB export (no changes)
{"output_id": "...", "export_glb": true}
```

## Response

Same SSE stream as normal pipeline, with additional fields:

```json
{
  "type": "complete",
  "data": {
    "output_id": "new-output-uuid",
    "previous_output_id": "original-output-uuid",
    ...
  }
}
```

## Database Schema

```
┌─────────────────────────────────────┐
│              rooms                  │
├─────────────────────────────────────┤
│ id            UUID (PK)             │
│ filename      TEXT                  │
│ storage_path  TEXT                  │
│ created_at    TIMESTAMPTZ           │
└─────────────────────────────────────┘
                 │
                 │ 1:N
                 ▼
┌─────────────────────────────────────┐
│          room_outputs               │
├─────────────────────────────────────┤
│ id              UUID (PK)           │
│ room_id         UUID (FK → rooms)   │
│ run_dir         TEXT                │
│ filename        TEXT                │
│ storage_path    TEXT                │
│ storage_path_glb TEXT               │
│ selected_assets JSONB               │
│ user_intent     TEXT                │
│ budget          FLOAT               │
│ layoutvlm_layout JSONB              │
│ created_at      TIMESTAMPTZ         │
└─────────────────────────────────────┘
```

**selected_assets** (JSONB array):
```json
[
  {"uid": "sofa_12", "category": "sofa", "price": 1200, "width": 2.1, "depth": 0.9, "height": 0.8, ...},
  {"uid": "coffee_table_5", "category": "coffee_table", "price": 450, ...}
]
```

**layoutvlm_layout** (JSONB object):
```json
{
  "sofa_12": {"x": 2.5, "y": 1.0, "rotation": 0},
  "coffee_table_5": {"x": 2.5, "y": 2.2, "rotation": 0}
}
```

## Getting output_id

Query previous outputs:

```bash
# List all outputs
curl http://localhost:8000/outputs

# Filter by room
curl http://localhost:8000/outputs?room_id=ROOM_UUID

# Get specific output
curl http://localhost:8000/outputs/OUTPUT_UUID
```

## GLB Export

Enable GLB output by setting `export_glb: true`:

```json
{
  "output_id": "...",
  "user_intent": "add more plants",
  "export_glb": true
}
```

Works for both new designs and iterations:

```json
// New design with GLB
{
  "usdz_path": "room-id",
  "user_intent": "Modern living room",
  "export_glb": true
}
```

### Download GLB

```bash
# Via run_dir (from SSE complete event)
curl -L http://localhost:8000/download/glb/20250202_143052 -o scene.glb

# Via output details (includes pre-signed URL)
curl http://localhost:8000/outputs/OUTPUT_UUID
# Response includes "glb_url" field
```

The `/download/glb/{run_dir}` endpoint redirects to a pre-signed Supabase URL.

## Chaining Iterations

Each iteration produces a new `output_id`. Chain multiple revisions:

```
Original → output_id_1
    ↓ "add plants"
Iteration 1 → output_id_2
    ↓ "change sofa color"
Iteration 2 → output_id_3
```
