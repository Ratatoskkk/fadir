"""FastAPI application (SPEC §1, §7).

Local-only: bound to loopback by the run command, no auth, no cloud. In production mode
the built frontend is served as static files from `frontend/dist`; during development the
Vite dev server proxies `/api` here instead.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import PROJECT_ROOT, get_settings
from app.db import init_db, session_scope
from app.providers import market_hours
from app.services.portfolio import PortfolioService, load_instruments

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("fadir")

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


async def _auto_refresh() -> None:
    """Keep the price and FX caches warm in the background.

    Without this the dashboard is only as live as its last button press: `GET
    /api/portfolio` reads the caches and never fills them, so the sole path that
    actually reaches Yahoo is `POST /api/refresh`. Polling the read endpoint therefore
    re-rendered identical numbers indefinitely.

    Doing it here rather than inside the GET keeps every request a fast local read — a
    page load never waits on Yahoo — and means one refresh serves however many tabs are
    open instead of each of them triggering its own.

    Cadence follows the market: `default_interval_seconds` while any exchange is trading,
    `closed_market_interval_seconds` otherwise. It is deliberately not zero when
    everything is shut, because FX trades around the clock on weekdays and this
    portfolio is valued in lira — the TRY figure moves overnight even though no share
    price does.
    """
    settings = get_settings()

    while True:
        # Sleeping first means a short-lived process (a test client, `--reload` churn)
        # never reaches the network, and startup is not delayed by a fetch.
        now = datetime.now(timezone.utc)
        with session_scope() as session:
            exchanges = {i.exchange for i in load_instruments(session)}
        any_open = any(market_hours.is_open(e, now) for e in exchanges)
        delay = (
            settings.refresh.default_interval_seconds
            if any_open
            else settings.refresh.closed_market_interval_seconds
        )
        await asyncio.sleep(delay)

        try:
            # Blocking network and DB work, so it goes to the threadpool rather than
            # stalling the event loop and every in-flight request with it.
            report = await asyncio.to_thread(_refresh_once)
            if report:
                log.debug("auto-refresh wrote %d price rows", report)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a refresh failure must not end the loop
            log.warning("auto-refresh failed, will retry: %s", exc)


def _refresh_once() -> int:
    """One non-forced refresh. Returns rows written."""
    settings = get_settings()
    with session_scope() as session:
        report = PortfolioService(session, settings).refresh(force=False)
        return report.price_rows_written


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings = get_settings()
    log.info("fadir ready - db=%s", settings.db_path)

    task = asyncio.create_task(_auto_refresh())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="faðir",
    description="Multi-currency portfolio PnL tracker with TRY return attribution.",
    version="1.0.0",
    lifespan=lifespan,
)

# Money crosses the wire as full-precision Decimal strings, which is deliberate — the
# §6 identities are exact and quantizing each field independently would break them, since
# the difference of two rounded numbers is not the rounded difference. That makes the
# payloads long but extremely repetitive (mostly runs of trailing zeros), so compressing
# them costs nothing and returns 5-6x on the series endpoints.
app.add_middleware(GZipMiddleware, minimum_size=1024)

# The Vite dev server runs on a different port; loopback origins only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):  # pragma: no cover
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


#: The SPA shell names the hashed bundles, so a stale copy of it pins the whole app to
#: an old build. `FileResponse` sends no `Cache-Control` at all, which leaves the browser
#: free to apply *heuristic* freshness and serve `index.html` from cache without ever
#: asking — the dashboard then keeps rendering a previous build after a rebuild, with no
#: request reaching the server to show for it. `no-cache` means "revalidate every time",
#: not "do not store": the ETag still makes it a 304 when nothing changed.
SHELL_CACHE_HEADERS = {"Cache-Control": "no-cache"}


class ImmutableStaticFiles(StaticFiles):
    """Serves `/assets` with a one-year immutable cache.

    Safe precisely because Vite fingerprints these filenames: a changed file is a new
    URL, so it can never be served stale. This is the other half of the shell being
    `no-cache` — revalidate the one small file that names the others, then never ask
    about the 400 kB of hashed JavaScript again.
    """

    def file_response(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def mount_frontend(application: FastAPI) -> None:
    """Serve the built SPA, if it exists."""
    if not FRONTEND_DIST.exists():
        log.warning(
            "frontend/dist not found - API only. Run `make build` (or `npm run build` "
            "in frontend/) to serve the dashboard from this server."
        )

        @application.get("/")
        def _no_frontend() -> dict[str, str]:
            return {
                "status": "api only",
                "hint": "run `make build` to bundle the dashboard, or `make dev` for the Vite dev server",
                "docs": "/docs",
            }

        return

    assets = FRONTEND_DIST / "assets"
    if assets.exists():
        application.mount("/assets", ImmutableStaticFiles(directory=assets), name="assets")

    index = FRONTEND_DIST / "index.html"
    dist_root = FRONTEND_DIST.resolve()

    @application.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        # `full_path` is whatever the client sent, so it can contain `..` — and the DB
        # and config.yaml sit one directory above the bundle. Loopback-only binding is
        # not a substitute for the check: any page in the browser can issue requests to
        # 127.0.0.1. Anything that does not resolve inside the bundle falls through to
        # the SPA shell.
        if full_path:
            candidate = (FRONTEND_DIST / full_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(dist_root):
                return FileResponse(candidate, headers=SHELL_CACHE_HEADERS)
        return FileResponse(index, headers=SHELL_CACHE_HEADERS)


mount_frontend(app)
