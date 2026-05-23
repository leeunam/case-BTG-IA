import os
import textwrap
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from src.api.deps import DbConn
from src.api.schemas.report import ReportJob

router = APIRouter(prefix="/reports", tags=["reports"])


def _ascii_safe(text: str) -> str:
    """Replace common Unicode characters that Helvetica can't encode."""
    replacements = {
        "—": "-", "–": "-",   # em dash, en dash
        "“": '"', "”": '"',   # curly double quotes
        "‘": "'", "’": "'",   # curly single quotes
        "…": "...",                # ellipsis
        "ç": "c", "ã": "a",  # ç, ã
        "õ": "o", "á": "a",  # õ, á
        "é": "e", "ê": "e",  # é, ê
        "í": "i", "ó": "o",  # í, ó
        "ú": "u", "ü": "u",  # ú, ü
        "Ç": "C", "Ã": "A",  # Ç, Ã
        "Õ": "O", "Á": "A",  # Õ, Á
        "É": "E", "Ê": "E",  # É, Ê
        "Í": "I", "Ó": "O",  # Í, Ó
        "Ú": "U",                  # Ú
        "à": "a", "â": "a",  # à, â
        "ô": "o",                  # ô
        "®": "(R)", "©": "(C)",
        "™": "(TM)",
        "°": "°",
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    # Replace any remaining non-latin-1 characters
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _write_pdf(
    job_id: str,
    fund_name: str,
    cvm_registration: str | None,
    offer_type: str,
    vol: str,
    status: str | None,
    coordinator: str | None,
    rite: str | None,
    start_date: str,
    registered_at: str,
    report_text: str,
    generated_at: datetime,
) -> str:
    from fpdf import FPDF

    out_dir = os.path.join("data", "reports")
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, f"{job_id}.pdf")

    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()

    # ── Header ──────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "BTG FII Analyzer", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, "Relatório Analítico de Oferta Primária", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # ── Offer identification table ───────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(240, 244, 255)
    pdf.cell(0, 8, "Identificação da Oferta", ln=True, fill=True)
    pdf.set_font("Helvetica", "", 10)

    fields = [
        ("Fundo",             _ascii_safe(fund_name)),
        ("Registro CVM",      _ascii_safe(cvm_registration or "N/D")),
        ("Tipo",              offer_type),
        ("Volume autorizado", vol),
        ("Status",            _ascii_safe(status or "N/D")),
        ("Coordenador lider", _ascii_safe(coordinator or "N/D")),
        ("Rito",              _ascii_safe(rite or "N/D")),
        ("Data de registro",  registered_at),
        ("Data de inicio",    start_date),
    ]
    col_w = 55
    for label, value in fields:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(col_w, 6, f"{label}:", border=0)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6, str(value)[:80], border=0, ln=True)

    pdf.ln(6)

    # ── Report body ──────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(240, 244, 255)
    pdf.cell(0, 8, "Análise", ln=True, fill=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(2)

    # Wrap text to fit page width
    effective_width = pdf.w - pdf.l_margin - pdf.r_margin
    for paragraph in report_text.split("\n"):
        paragraph = _ascii_safe(paragraph.strip())
        if not paragraph:
            pdf.ln(3)
            continue
        if paragraph.startswith("**") and paragraph.endswith("**"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(0, 5, paragraph.replace("**", ""))
            pdf.set_font("Helvetica", "", 10)
        else:
            pdf.multi_cell(0, 5, paragraph)

    pdf.ln(8)

    # ── Footer disclaimer ────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(
        0, 4,
        "Este relatorio e informativo e nao constitui recomendacao de investimento. "
        "Os dados apresentados sao de fontes publicas (CVM, BCB, Fundamentus). "
        "Metricas de mercado secundario (DY, P/VP) nao sao termos da oferta primaria.",
    )
    pdf.ln(2)
    pdf.cell(0, 4, f"Gerado em: {generated_at.strftime('%d/%m/%Y %H:%M UTC')}", ln=True)

    pdf.output(pdf_path)
    return pdf_path


def _generate_pdf_task(job_id: str, offer_id: int) -> None:
    """Background task: generate PDF report for one offer."""
    from src.db.connection import get_conn

    with get_conn() as db:
        db.execute(
            "UPDATE report_job SET status = 'processing', progress = 10, updated_at = NOW() WHERE id = %s",
            (job_id,),
        )
        db.commit()

    try:
        # Fetch offer data
        with get_conn() as db:
            row = db.execute("""
                SELECT o.cvm_registration, COALESCE(v.name,'?'), o.total_volume,
                       o.status, o.started_at, o.registered_at, o.is_ipo,
                       o.distribution_rite, p.name AS coordinator
                FROM offer o
                LEFT JOIN vehicle v ON v.id = o.vehicle_id
                LEFT JOIN participant_role pr ON pr.offer_id = o.id AND pr.role = 'coordinator_leader'
                LEFT JOIN participant p ON p.id = pr.participant_id
                WHERE o.id = %s
            """, (offer_id,)).fetchone()
            db.execute(
                "UPDATE report_job SET progress = 30, updated_at = NOW() WHERE id = %s", (job_id,)
            )
            db.commit()

        if not row:
            raise ValueError("Offer not found")

        # Generate report text with LLM
        from langchain_groq import ChatGroq
        from dotenv import load_dotenv
        load_dotenv()

        model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, max_tokens=2048)
        offer_type = "IPO" if row[6] else "Follow-on"
        vol = f"R${float(row[2])/1e6:.0f}M" if row[2] else "N/D"

        prompt = (
            f"Você é um analista de mercado de capitais. Gere um relatório analítico objetivo sobre "
            f"a seguinte oferta primária de FII:\n\n"
            f"Fundo: {row[1]}\nRegistro CVM: {row[0]}\nTipo: {offer_type}\n"
            f"Volume autorizado: {vol}\nStatus: {row[3]}\nCoord. Líder: {row[8] or 'N/D'}\n"
            f"Rito: {row[7] or 'N/D'}\nInício: {row[4]}\nRegistro: {row[5]}\n\n"
            f"O relatório deve:\n"
            f"- Descrever a estrutura da oferta de forma factual\n"
            f"- Contextualizar com o mercado primário de FIIs\n"
            f"- Listar limitações e dados não disponíveis\n"
            f"- NÃO fazer recomendação de investimento\n"
            f"- NÃO inventar dados que não estão presentes\n\n"
            f"Estruture em: Identificação, Estrutura da Oferta, Participantes, "
            f"Limitações dos Dados, Aviso Legal."
        )

        response = model.invoke(prompt)
        report_text = response.content

        with get_conn() as db:
            db.execute(
                "UPDATE report_job SET progress = 70, updated_at = NOW() WHERE id = %s", (job_id,)
            )
            db.commit()

        # Generate PDF with fpdf2
        pdf_path = _write_pdf(
            job_id=job_id,
            fund_name=row[1],
            cvm_registration=row[0],
            offer_type=offer_type,
            vol=vol,
            status=row[3],
            coordinator=row[8],
            rite=row[7],
            start_date=str(row[4] or "N/D"),
            registered_at=str(row[5] or "N/D"),
            report_text=report_text,
            generated_at=datetime.now(timezone.utc),
        )

        with get_conn() as db:
            db.execute(
                "UPDATE report_job SET status = 'completed', progress = 100, "
                "file_path = %s, updated_at = NOW() WHERE id = %s",
                (pdf_path, job_id),
            )
            db.commit()

    except Exception as exc:
        # Store a sanitized error — never store raw exception strings that may
        # contain DB connection strings or API keys from authentication errors.
        exc_type = type(exc).__name__
        safe_error = f"{exc_type}: falha na geração do relatório."
        with get_conn() as db:
            db.execute(
                "UPDATE report_job SET status = 'failed', error = %s, updated_at = NOW() WHERE id = %s",
                (safe_error, job_id),
            )
            db.commit()


@router.post("/offers/{offer_id}", response_model=ReportJob, status_code=202)
def create_report(offer_id: int, background_tasks: BackgroundTasks, db: DbConn):
    offer = db.execute("SELECT id FROM offer WHERE id = %s", (offer_id,)).fetchone()
    if not offer:
        raise HTTPException(404, "Offer not found")

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.execute(
        "INSERT INTO report_job (id, offer_id, status, progress, created_at, updated_at) "
        "VALUES (%s, %s, 'queued', 0, %s, %s)",
        (job_id, offer_id, now, now),
    )
    db.commit()
    background_tasks.add_task(_generate_pdf_task, job_id, offer_id)

    return ReportJob(job_id=job_id, offer_id=offer_id, status="queued",
                     progress=0, download_url=None, error=None, created_at=now)


@router.get("/jobs/{job_id}", response_model=ReportJob)
def get_job(job_id: str, db: DbConn):
    row = db.execute(
        "SELECT id, offer_id, status, progress, file_path, error, created_at FROM report_job WHERE id = %s",
        (job_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    download_url = f"/api/reports/jobs/{job_id}/download" if row[2] == "completed" else None
    return ReportJob(job_id=str(row[0]), offer_id=row[1], status=row[2],
                     progress=row[3], download_url=download_url, error=row[5], created_at=row[6])


@router.get("/jobs/{job_id}/download")
def download_report(job_id: str, db: DbConn):
    import pathlib
    row = db.execute(
        "SELECT status, file_path FROM report_job WHERE id = %s", (job_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Job not found")
    if row[0] != "completed":
        raise HTTPException(400, f"Report not ready — status: {row[0]}")
    if not row[1]:
        raise HTTPException(500, "File path missing")

    # Path traversal guard: resolve the stored path and ensure it stays within
    # the expected reports directory before serving the file.
    reports_dir = pathlib.Path("data/reports").resolve()
    file_path   = pathlib.Path(row[1]).resolve()
    if not str(file_path).startswith(str(reports_dir)):
        raise HTTPException(400, "Invalid file path")
    if not file_path.exists():
        raise HTTPException(404, "Report file not found")

    return FileResponse(
        str(file_path),
        filename=f"relatorio_fii_{job_id[:8]}.pdf",
        media_type="application/pdf",
    )
