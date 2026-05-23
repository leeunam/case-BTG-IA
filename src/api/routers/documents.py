from fastapi import APIRouter, HTTPException
from src.api.deps import DbConn
from src.api.schemas.agent import DocumentItem

router = APIRouter(prefix="/offers", tags=["documents"])

_TYPE_LABELS = {
    "prospecto_preliminar":  "Prospecto Preliminar",
    "prospecto_definitivo":  "Prospecto Definitivo",
    "lamina":                "Lâmina",
    "anuncio_inicio":        "Anúncio de Início",
    "anuncio_encerramento":  "Anúncio de Encerramento",
    "fato_relevante":        "Fato Relevante",
    "comunicado":            "Comunicado",
    "complementar":          "Documento Complementar",
}


@router.get("/{offer_id}/documents", response_model=list[DocumentItem])
def get_documents(offer_id: int, db: DbConn):
    offer = db.execute("SELECT id FROM offer WHERE id = %s", (offer_id,)).fetchone()
    if not offer:
        raise HTTPException(404, "Offer not found")

    rows = db.execute("""
        SELECT id, offer_id, type, source_url, local_path, extraction_status
        FROM document
        WHERE offer_id = %s
        ORDER BY type
    """, (offer_id,)).fetchall()

    items = []
    for r in rows:
        doc_type = r[2] or "complementar"
        title = _TYPE_LABELS.get(doc_type, doc_type.replace("_", " ").title())
        download_url = f"/api/offers/{offer_id}/documents/{r[0]}/download" if r[4] else None
        items.append(DocumentItem(
            id=r[0], offer_id=r[1], type=doc_type, title=title,
            source_url=r[3], download_url=download_url,
            available=bool(r[3] or r[4]),
            extraction_status=r[5] or "pending",
        ))
    return items
