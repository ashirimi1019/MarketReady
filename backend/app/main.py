from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.routes import auth, majors, user, proofs, readiness, timeline, admin, ai, market, meta
from app.core.config import settings

app = FastAPI(title="Career Pathways API", version="0.1.0")

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


app.include_router(auth.router, tags=["auth"])
app.include_router(majors.router, tags=["majors"])
app.include_router(user.router, tags=["user"])
app.include_router(proofs.router, tags=["proofs"])
app.include_router(readiness.router, tags=["readiness"])
app.include_router(timeline.router, tags=["timeline"])
app.include_router(admin.router, tags=["admin"])
app.include_router(ai.router, tags=["ai"])
app.include_router(market.router, tags=["market"])
app.include_router(meta.router, tags=["meta"])
