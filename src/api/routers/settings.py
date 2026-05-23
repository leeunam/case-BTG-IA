from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from src.api.deps import DbConn

router = APIRouter(prefix="/settings", tags=["settings"])


class RefreshRequest(BaseModel):
    source: str = "all"   # all | cvm_dados_abertos | bcb_sgs | fundamentus | b3_ifix | ...


@router.post("/refresh")
def trigger_refresh(payload: RefreshRequest, background_tasks: BackgroundTasks):
    """Trigger a data pipeline refresh for one or all sources."""
    def _run(sources):
        from src.pipeline.run import run_pipeline
        run_pipeline(sources=sources if sources != ["all"] else None)

    sources = [payload.source] if payload.source != "all" else ["all"]
    background_tasks.add_task(_run, sources)
    return {"status": "started", "source": payload.source}


@router.post("/clear-cache")
def clear_cache():
    """Placeholder — cache invalidation handled by TanStack Query on the frontend."""
    return {"status": "ok", "message": "Frontend cache should be invalidated client-side."}
