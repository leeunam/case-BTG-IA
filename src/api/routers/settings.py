from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

router = APIRouter(prefix="/settings", tags=["settings"])

_REGULATORY_SOURCES = ["cvm_dados_abertos", "b3_listings", "bcb_sgs", "status_invest"]
_MARKET_SOURCES     = ["b3_ifix", "fundamentus", "funds_explorer"]


class RefreshRequest(BaseModel):
    source: str = "regulatory"
    # regulatory → CVM + BCB + B3 + Status Invest (batch diário)
    # market     → IFIX + Fundamentus + FundsExplorer (pregão)
    # <code>     → coletor específico pelo source_code


@router.post("/refresh")
def trigger_refresh(payload: RefreshRequest, background_tasks: BackgroundTasks):
    """Aciona o pipeline de coleta em background.

    - source="regulatory" → fontes batch diárias (CVM, BCB, B3, Status Invest)
    - source="market"     → fontes de pregão (IFIX, Fundamentus, FundsExplorer)
    - source="<code>"     → coletor específico
    """
    def _run(sources):
        from src.pipeline.run import run_pipeline
        run_pipeline(sources=sources)

    if payload.source == "regulatory":
        background_tasks.add_task(_run, _REGULATORY_SOURCES)
    elif payload.source == "market":
        background_tasks.add_task(_run, _MARKET_SOURCES)
    else:
        background_tasks.add_task(_run, [payload.source])

    return {"status": "started", "source": payload.source}


@router.post("/clear-cache")
def clear_cache():
    """Placeholder — cache invalidation handled by TanStack Query on the frontend."""
    return {"status": "ok", "message": "Frontend cache should be invalidated client-side."}
