"""Daily insight generation service — called by scheduler, not by API requests."""
from datetime import date, datetime, timezone


def generate_daily_insight() -> None:
    from dotenv import load_dotenv
    load_dotenv()
    from langchain_groq import ChatGroq
    from src.db.connection import get_conn

    today = date.today()

    with get_conn() as db:
        db.execute(
            """INSERT INTO daily_insight (insight_date, status, created_at)
               VALUES (%s, 'generating', NOW())
               ON CONFLICT (insight_date) DO UPDATE SET status = 'generating'""",
            (today,),
        )
        db.commit()

        # Gather context
        new_offers = db.execute(
            "SELECT COUNT(*) FROM offer WHERE registered_at = %s", (today,)
        ).fetchone()[0]

        active_offers = db.execute(
            "SELECT COUNT(*) FROM offer WHERE status IN ('active','pending')"
        ).fetchone()[0]

        macro = {r[0]: float(r[1]) for r in db.execute(
            "SELECT code, value FROM market_metric WHERE (code, metric_date) IN "
            "(SELECT code, MAX(metric_date) FROM market_metric GROUP BY code)"
        ).fetchall()}

    try:
        model = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3, max_tokens=400)
        selic = macro.get("SELIC_META") or macro.get("CDI_PROJ", 0)
        ipca  = macro.get("IPCA_PROJ", 0)
        ifix  = macro.get("IFIX", 0)

        prompt = (
            f"Você é analista do mercado primário de FIIs. Escreva um panorama do dia de até 3 parágrafos.\n\n"
            f"Dados do dia {today.strftime('%d/%m/%Y')}:\n"
            f"- Novas ofertas registradas hoje: {new_offers}\n"
            f"- Ofertas ativas no mercado: {active_offers}\n"
            f"- Selic/meta: {selic:.2f}% a.a.\n"
            f"- IPCA projetado: {ipca:.2f}% a.a.\n"
            f"- IFIX: {ifix:,.0f} pts\n\n"
            f"Regras:\n"
            f"- Foque nos dados disponíveis\n"
            f"- NÃO faça recomendação de investimento\n"
            f"- NÃO invente dados\n"
            f"- Seja objetivo e factual\n"
            f"- Se não houver novas ofertas, diga isso claramente"
        )

        response = model.invoke(prompt)
        text = response.content

        with get_conn() as db:
            db.execute(
                "UPDATE daily_insight SET status='generated', text=%s, "
                "generated_at=%s, model_used=%s WHERE insight_date=%s",
                (text, datetime.now(timezone.utc), "llama-3.3-70b-versatile", today),
            )
            db.commit()

    except Exception as exc:
        with get_conn() as db:
            db.execute(
                "UPDATE daily_insight SET status='failed', error=%s WHERE insight_date=%s",
                (str(exc)[:500], today),
            )
            db.commit()
