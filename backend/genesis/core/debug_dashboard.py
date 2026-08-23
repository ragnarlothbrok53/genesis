import time
from collections import deque
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from genesis.core.config import settings

_MAX_ENTRIES = 200
_requests: deque[dict[str, Any]] = deque(maxlen=_MAX_ENTRIES)

_PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Genesis local dev dashboard</title>
<style>
body { font-family: monospace; margin: 2rem; background: #111; color: #eee; }
h1 { font-size: 1.1rem; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: 4px 10px; border-bottom: 1px solid #333; }
th { color: #888; font-weight: normal; }
.status-2 { color: #6f6; }
.status-4 { color: #fc6; }
.status-5 { color: #f66; }
</style>
</head>
<body>
<h1>Genesis local dev dashboard &mdash; last 200 requests</h1>
<table>
<thead>
<tr><th>Time</th><th>Method</th><th>Path</th><th>Status</th><th>Duration (ms)</th></tr>
</thead>
<tbody id="rows"></tbody>
</table>
<script>
async function refresh() {
  const res = await fetch("/api/_debug/requests");
  const rows = await res.json();
  const body = document.getElementById("rows");
  body.innerHTML = rows.map(function (row) {
    const time = new Date(row.timestamp * 1000).toLocaleTimeString();
    const statusClass = "status-" + String(row.status)[0];
    const cells = [time, row.method, row.path];
    return "<tr><td>" + cells.join("</td><td>") + "</td><td class=\\"" + statusClass +
      "\\">" + row.status + "</td><td>" + row.duration_ms + "</td></tr>";
  }).join("");
}
refresh();
setInterval(refresh, 1000);
</script>
</body>
</html>
"""


def _enabled() -> bool:
    return settings.CACHE_BACKEND == "embedded"


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _enabled():
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        _requests.append(
            {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                "timestamp": time.time(),
            }
        )
        return response


def setup_debug_dashboard(app: FastAPI) -> None:
    app.add_middleware(RequestLogMiddleware)

    @app.get("/api/_debug/requests", include_in_schema=False)
    async def debug_requests():
        if not _enabled():
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        return list(reversed(_requests))

    @app.get("/api/_debug", include_in_schema=False)
    async def debug_dashboard():
        if not _enabled():
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        return HTMLResponse(_PAGE)
