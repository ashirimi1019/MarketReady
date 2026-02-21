from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from app.api.routes import auth, majors, user, proofs, readiness, timeline, admin, ai, market, meta
from app.api.routes import github, mri, sentinel, kanban, simulator, public_profile
from app.core.config import settings
from app.services.market_automation import start_market_scheduler, stop_market_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    await start_market_scheduler()
    try:
        yield
    finally:
        await stop_market_scheduler()


app = FastAPI(title="Career Pathways API", version="0.1.0", lifespan=lifespan)

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "X-Auth-Token",
        "X-User-Id",
        "X-Admin-Token",
        "X-Request-Id",
    ],
)

upload_dir = Path(settings.local_upload_dir)
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


def _register_routes(prefix: str = "") -> None:
    app.include_router(auth.router, tags=["auth"], prefix=prefix)
    app.include_router(majors.router, tags=["majors"], prefix=prefix)
    app.include_router(user.router, tags=["user"], prefix=prefix)
    app.include_router(proofs.router, tags=["proofs"], prefix=prefix)
    app.include_router(readiness.router, tags=["readiness"], prefix=prefix)
    app.include_router(timeline.router, tags=["timeline"], prefix=prefix)
    app.include_router(admin.router, tags=["admin"], prefix=prefix)
    app.include_router(ai.router, tags=["ai"], prefix=prefix)
    app.include_router(market.router, tags=["market"], prefix=prefix)
    app.include_router(meta.router, tags=["meta"], prefix=prefix)
    app.include_router(github.router, tags=["github"], prefix=prefix)
    app.include_router(mri.router, tags=["mri"], prefix=prefix)
    app.include_router(sentinel.router, tags=["sentinel"], prefix=prefix)
    app.include_router(kanban.router, tags=["kanban"], prefix=prefix)
    app.include_router(simulator.router, tags=["simulator"], prefix=prefix)
    app.include_router(public_profile.router, tags=["public"], prefix=prefix)


_register_routes("")
_register_routes("/api")
