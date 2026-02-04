# Slack message: Pipeline 400 – usdz_path required

Copy-paste below (adjust if needed):

---

**Pipeline 400 – usdz_path required**

We're seeing a 400 from `POST pipeline.livinit.ai/pipeline` when starting the design pipeline from the web app:

```
Failed to start pipeline: usdz_path is required (or provide output_id to iterate)
```

**What we do today**
1. User uploads a USDZ via `POST /upload/room`.
2. We use the response to get the room path and send it as `usdz_path` in the pipeline request body.
3. Pipeline request is: `{ user_intent, budget, usdz_path, export_glb, run_* flags }`.

**Questions**
- Did the **upload/room** response shape change? We currently expect something like `data.usdz_path` or `data.path` (we now support multiple shapes). If the backend returns a different key (e.g. `output_id` only), we need to know so we can send the right field to `/pipeline`.
- For **/pipeline**, does the backend now require `output_id` instead of (or in addition to) `usdz_path` when the file comes from upload? If we should send `output_id` from the upload response, what’s the exact field name in the upload JSON?

**Temporary fix on our side**
- We’ve updated the frontend to:
  - Normalize upload response and accept `data.usdz_path`, `data.path`, or top-level `usdz_path` / `path`.
  - Validate that we have a non-empty path before calling `/pipeline`.
  - Throw a clear error if upload doesn’t return a path.

If the backend contract for upload and pipeline has changed, can you share the current request/response examples for `POST /upload/room` and `POST /pipeline`? Then we can align the web app 100%.

---
