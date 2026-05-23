"""FastAPI application factory.

Auth gating notes:

* When ``settings.control.auth_token`` is empty, the default FastAPI docs/redoc
  and ``/openapi.json`` are exposed (subject to ``expose_docs``).
* When ``settings.control.auth_token`` is set, the default docs/redoc/openapi
  routes are disabled and replaced with Bearer-protected variants — matching
  ``docs/api-contract.md`` and ``docs/security-and-privacy.md``.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html

from cf_aigw_analyzer import __version__
from cf_aigw_analyzer.config import Settings, load_settings
from cf_aigw_analyzer.control.auth import require_auth
from cf_aigw_analyzer.control.lifecycle import AppState, create_state, lifespan
from cf_aigw_analyzer.control.middleware import configure_middleware
from cf_aigw_analyzer.control.routes import (
    analytics_route,
    config_route,
    events_route,
    health_route,
    scopes_route,
    status_route,
    sync_route,
)
from cf_aigw_analyzer.control.static import configure_static

API_PREFIX = "/api/v1"

PROTECTED_OPENAPI_PATH = "/openapi.json"
PROTECTED_DOCS_PATH = "/docs"
PROTECTED_REDOC_PATH = "/redoc"


def build_app(*, settings: Settings | None = None, state: AppState | None = None) -> FastAPI:
    """Construct a FastAPI application sharing settings + state across requests.

    Tests should pass a pre-built ``state`` (with a tmp-path database) to avoid
    touching the user's local SQLite file.
    """

    settings = settings or load_settings()
    state = state or create_state(settings)

    auth_required = bool(state.settings.control.auth_token)
    expose_docs = settings.control.expose_docs

    if auth_required or not expose_docs:
        docs_url: str | None = None
        redoc_url: str | None = None
        openapi_url: str | None = None
    else:
        docs_url = PROTECTED_DOCS_PATH
        redoc_url = PROTECTED_REDOC_PATH
        openapi_url = PROTECTED_OPENAPI_PATH

    app = FastAPI(
        title="Cloudflare AI Gateway Analyzer",
        version=__version__,
        description="Local analytics control plane for Cloudflare AI Gateway logs.",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    app.state.context = state

    configure_middleware(app, settings)

    dependencies = [Depends(require_auth)] if auth_required else []

    if auth_required and expose_docs:
        _register_protected_docs(app)

    app.include_router(health_route.router, prefix=API_PREFIX, dependencies=dependencies)
    app.include_router(scopes_route.router, prefix=API_PREFIX, dependencies=dependencies)
    app.include_router(analytics_route.router, prefix=API_PREFIX, dependencies=dependencies)
    app.include_router(events_route.router, prefix=API_PREFIX, dependencies=dependencies)
    app.include_router(status_route.router, prefix=API_PREFIX, dependencies=dependencies)
    app.include_router(config_route.router, prefix=API_PREFIX, dependencies=dependencies)
    app.include_router(sync_route.router, prefix=API_PREFIX, dependencies=dependencies)

    configure_static(app, settings)
    return app


def _register_protected_docs(app: FastAPI) -> None:
    """Mount Bearer-protected ``/docs``, ``/redoc`` and ``/openapi.json``."""

    @app.get(PROTECTED_OPENAPI_PATH, include_in_schema=False, dependencies=[Depends(require_auth)])
    async def protected_openapi() -> dict[str, Any]:
        return app.openapi()

    @app.get(PROTECTED_DOCS_PATH, include_in_schema=False, dependencies=[Depends(require_auth)])
    async def protected_docs() -> Any:
        return get_swagger_ui_html(openapi_url=PROTECTED_OPENAPI_PATH, title=f"{app.title} — docs")

    @app.get(PROTECTED_REDOC_PATH, include_in_schema=False, dependencies=[Depends(require_auth)])
    async def protected_redoc() -> Any:
        return get_redoc_html(openapi_url=PROTECTED_OPENAPI_PATH, title=f"{app.title} — redoc")
