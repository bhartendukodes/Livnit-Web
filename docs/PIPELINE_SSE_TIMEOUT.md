# Pipeline SSE Connection Timeout

## Issue

`net::ERR_INCOMPLETE_CHUNKED_ENCODING` during pipeline execution, typically when `render_scene` is running (last step, ~15+ seconds).

## Cause

The server or a proxy (nginx, load balancer) closes the connection before the SSE stream finishes. The full pipeline can take 2+ minutes; `render_scene` alone takes ~15 seconds at 512 resolution.

## Backend/Infrastructure Fix

Increase timeouts for the pipeline SSE endpoint:

### Nginx
```nginx
location /pipeline {
    proxy_read_timeout 300s;   # 5 minutes
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
}
```

### Load balancer (e.g. AWS ALB)
- Idle timeout: 300 seconds (default is often 60s)

### FastAPI / Uvicorn
- Ensure no connection timeout in the ASGI server config

## Frontend Mitigations (Applied)

1. Added `Connection: keep-alive` and `Cache-Control: no-cache` headers
2. `keepalive: true` on fetch
3. Clearer error message with retry guidance
