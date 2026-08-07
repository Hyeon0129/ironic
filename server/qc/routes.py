"""FastAPI routes for the Windows QC dashboard (ex-"sangsang", server-side
integration added 2026-08-06).

web/app.js (unmodified, copied verbatim from the original standalone app)
expects exactly two things from its server:
  - `POST /api/<method>` — call Backend.<method>(*args), args being whatever
    JSON array the client posted. This mirrors server_app.py's do_POST
    (a BaseHTTPRequestHandler) 1:1, just reimplemented on FastAPI/Starlette.
  - `GET /events` — a Server-Sent-Events stream of Backend's log/push
    messages (Backend.subscribe()/unsubscribe(), a queue.Queue pub-sub —
    unchanged from the original).

The actual web/ static assets (index.html/app.js/style.css/...) are served by
mounting StaticFiles(..., html=True) at /qc in server/main.py, not from here.
"""

import asyncio
import json
import queue as queue_module

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .backend import backend

router = APIRouter()


@router.post("/api/{method_name}")
async def qc_rpc(method_name: str, request: Request):
    method = getattr(backend, method_name, None)
    if method is None or method_name.startswith("_") or not callable(method):
        return JSONResponse({"ok": False, "error": f"unknown method {method_name}"}, status_code=404)

    raw = await request.body()
    try:
        args = json.loads(raw.decode("utf-8")) if raw else []
    except Exception:
        args = []
    if not isinstance(args, list):
        args = [args]

    try:
        # Backend's methods are synchronous (subprocess ping, pywinrm calls that
        # block for seconds) — offload to a worker thread so one slow WinRM call
        # doesn't stall the same event loop serving the rest of this dashboard
        # (Ironic polling, other users' requests, etc.).
        result = await asyncio.to_thread(method, *args)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    return JSONResponse(result)


@router.get("/events")
async def qc_events():
    async def gen():
        q = backend.subscribe()
        try:
            while True:
                try:
                    msg = await asyncio.to_thread(q.get, True, 15)
                    yield f"data: {msg}\n\n"
                except queue_module.Empty:
                    yield ": ping\n\n"  # keep-alive, matches original
        finally:
            backend.unsubscribe(q)

    return StreamingResponse(
        gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
