"""Static panel hosting (mounts ``web/dist`` when present).

The previous v0.3a0 implementation used a hand-written ``Path / full_path``
read which was vulnerable to path traversal and returned every asset as
``text/html``. This module replaces it with:

* :class:`StaticFiles` for the built ``assets/`` directory (correct MIME + path
  safety guaranteed by the framework).
* An explicit SPA fallback route that resolves the request path against
  ``static_dir.resolve()`` and verifies it stays inside that directory.
* :class:`FileResponse` (which streams + sets ``Content-Type`` by extension)
  for matched files; ``index.html`` for everything else (so React Router can
  handle the URL client-side).

The configuration must be invoked **after** ``include_router`` for
``/api/v1`` so the SPA fallback does not shadow API routes.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from cf_aigw_analyzer.config import Settings

PLACEHOLDER_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Cloudflare AI Gateway Analyzer</title>
    <style>
      body { font-family: -apple-system, sans-serif; max-width: 720px; margin: 4rem auto; padding: 0 1rem; line-height: 1.6; color: #222; }
      code { background: #f1f1f1; padding: 0.1rem 0.3rem; border-radius: 3px; }
    </style>
  </head>
  <body>
    <h1>Cloudflare AI Gateway Analyzer</h1>
    <p>Panel is not built yet. Visit <a href="/docs">/docs</a> to explore the API.</p>
    <p>To build the panel, run:</p>
    <pre><code>cd web && npm ci && npm run build</code></pre>
  </body>
</html>
"""


def configure_static(app: FastAPI, settings: Settings) -> None:
    """Mount the built React panel or a placeholder when ``web/dist`` is absent."""

    static_dir = Path(settings.control.static_dir).expanduser().resolve()
    index_path = static_dir / "index.html"
    has_panel = static_dir.is_dir() and index_path.is_file()

    if has_panel:
        _mount_panel(app, static_dir, index_path)
    else:
        _mount_placeholder(app)


def _mount_panel(app: FastAPI, static_dir: Path, index_path: Path) -> None:
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="panel-assets")

    @app.get("/", include_in_schema=False)
    async def root_index() -> FileResponse:
        return FileResponse(index_path, media_type="text/html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str, request: Request) -> FileResponse:
        # Reject requests that try to escape static_dir via "..", absolute paths,
        # or any other normalisation trick. We do not rely on read_text() to be
        # safe; we explicitly verify the resolved path stays inside static_dir.
        candidate = (static_dir / full_path).resolve()
        try:
            candidate.relative_to(static_dir)
        except ValueError as exc:
            raise HTTPException(status_code=404) from exc

        if candidate.is_file():
            # FileResponse picks Content-Type from the suffix.
            return FileResponse(candidate)

        # SPA route — return index.html so the client router can pick it up.
        _ = request  # available for future audit hooks
        return FileResponse(index_path, media_type="text/html")


def _mount_placeholder(app: FastAPI) -> None:
    @app.get("/", include_in_schema=False)
    async def placeholder() -> HTMLResponse:
        return HTMLResponse(PLACEHOLDER_HTML)
