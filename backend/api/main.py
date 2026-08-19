"""FastAPI app entrypoint.

    uvicorn backend.api.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import funnel, unit_economics
from backend.models.ddl import connect

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "warehouse.duckdb"


@asynccontextmanager
async def lifespan(app: FastAPI):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    app.state.db = connect(str(DB_PATH))
    yield
    app.state.db.close()


app = FastAPI(title="Hayah Care Growth Analytics", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(unit_economics.router)
app.include_router(funnel.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
