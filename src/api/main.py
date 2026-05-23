"""
BTG FII Analyzer — FastAPI backend.

Run:
    uvicorn src.api.main:app --reload --port 8000

Set ENV=production to disable /docs and /redoc in production.
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import (
    dashboard, offers, alerts, documents,
    reports, agent, general_scenario, settings,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


_is_prod = os.getenv("ENV", "development").lower() == "production"

app = FastAPI(
    title="BTG FII Analyzer API",
    version="1.0.0",
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_prefix = "/api"
app.include_router(dashboard.router,        prefix=_prefix)
app.include_router(offers.router,           prefix=_prefix)
app.include_router(alerts.router,           prefix=_prefix)
app.include_router(documents.router,        prefix=_prefix)
app.include_router(reports.router,          prefix=_prefix)
app.include_router(agent.router,            prefix=_prefix)
app.include_router(general_scenario.router, prefix=_prefix)
app.include_router(settings.router,         prefix=_prefix)


@app.get("/api/health")
def health():
    return {"status": "ok"}
