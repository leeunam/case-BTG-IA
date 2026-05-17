"""Macro — CDI, IPCA, Selic histórico e projeções Focus."""
import sys
from pathlib import Path
from datetime import date, timedelta

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.db import get_macro_history, get_latest_macro, get_cdi_history, get_ipca_history

st.set_page_config(page_title="Macro | BTG FII", layout="wide")

# ─── Sidebar ─────────────────────────────────────────────────────────────────

st.sidebar.header("Filtros")
period_opts = {
    "12 meses":  365,
    "24 meses":  730,
    "36 meses":  1095,
    "Desde 2022": (date.today() - date(2022, 1, 1)).days,
}
period_label = st.sidebar.selectbox("Período", list(period_opts.keys()), index=1)
since = date.today() - timedelta(days=period_opts[period_label])

st.sidebar.markdown("---")
st.sidebar.caption("⚠️ Esta aplicação não gera recomendação de investimento.")

# ─── Header ──────────────────────────────────────────────────────────────────

st.title("📈 Indicadores Macroeconômicos")
st.caption("Selic, IPCA e CDI — histórico e projeções Focus (BCB) | Referência para análise de DY de FIIs")

# ─── KPIs actuais ────────────────────────────────────────────────────────────

try:
    macro = get_latest_macro()

    cdi_diario  = macro.get("CDI",       {}).get("value")
    selic_proj  = macro.get("CDI_PROJ",  {}).get("value")
    ipca_proj   = macro.get("IPCA_PROJ", {}).get("value")
    ipca_latest = macro.get("IPCA",      {}).get("value")
    focus_date  = macro.get("CDI_PROJ",  {}).get("date", "")

    # Annualize daily CDI: (1 + r/100)^252 - 1
    cdi_anual = ((1 + (cdi_diario or 0) / 100) ** 252 - 1) * 100 if cdi_diario else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "CDI diário",
        f"{cdi_diario:.4f}%/dia" if cdi_diario else "—",
        help="Última taxa CDI over/Selic da série SGS 12 (BCB)"
    )
    c2.metric(
        "CDI anualizado (252 du)",
        f"{cdi_anual:.2f}% a.a." if cdi_anual else "—",
        help="Calculado a partir do CDI diário: (1+r)^252 - 1"
    )
    c3.metric(
        "Selic projetada (Focus)",
        f"{selic_proj:.2f}% a.a." if selic_proj else "—",
        help=f"Mediana do mercado em {focus_date} — BCB Relatório Focus"
    )
    c4.metric(
        "IPCA projetado (Focus)",
        f"{ipca_proj:.2f}% a.a." if ipca_proj else "—",
        help=f"Mediana do mercado em {focus_date} — BCB Relatório Focus"
    )

except Exception as e:
    st.error(f"Erro ao carregar macro: {e}")
    macro = {}
    cdi_anual = selic_proj = ipca_proj = None

st.markdown("---")

# ─── Selic projetada vs IPCA projetado ───────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    st.subheader("🏦 Projeções de mercado (Focus)")
    try:
        df_proj = get_macro_history(["CDI_PROJ", "IPCA_PROJ"], since)
        if not df_proj.empty:
            label_map = {"CDI_PROJ": "Selic Projetada", "IPCA_PROJ": "IPCA Projetado"}
            df_proj["indicator"] = df_proj["code"].map(label_map)
            fig = px.line(
                df_proj, x="metric_date", y="value", color="indicator",
                labels={"metric_date": "", "value": "% a.a.", "indicator": ""},
                color_discrete_map={
                    "Selic Projetada": "#1f4e79",
                    "IPCA Projetado":  "#ed7d31",
                },
            )
            fig.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=10, b=0),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(gridcolor="rgba(128,128,128,0.2)")
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Fonte: BCB Relatório Focus — mediana das expectativas do mercado")
        else:
            st.info("Dados de projeções não disponíveis.")
    except Exception as e:
        st.error(f"Erro: {e}")

with col2:
    st.subheader("📊 IPCA mensal acumulado (histórico)")
    try:
        df_ipca = get_ipca_history(since)
        if not df_ipca.empty:
            # Rolling 12-month accumulated IPCA
            df_ipca["ipca_monthly"] = pd.to_numeric(df_ipca["ipca_monthly"], errors="coerce")
            df_ipca = df_ipca.sort_values("metric_date")
            df_ipca["acum_12m"] = df_ipca["ipca_monthly"].rolling(12).apply(
                lambda x: ((1 + x / 100).prod() - 1) * 100
            )
            fig_ipca = px.bar(
                df_ipca.dropna(subset=["acum_12m"]),
                x="metric_date", y="acum_12m",
                labels={"metric_date": "", "acum_12m": "IPCA 12m (%)"},
                color_discrete_sequence=["#ed7d31"],
            )
            if selic_proj:
                fig_ipca.add_hline(
                    y=float(selic_proj),
                    line_dash="dash", line_color="#1f4e79",
                    annotation_text=f"Selic proj. {selic_proj:.1f}%",
                    annotation_position="bottom right",
                )
            fig_ipca.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=10, b=0),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_ipca, use_container_width=True)
            st.caption("IPCA acumulado 12 meses (janela móvel). Linha tracejada: Selic projetada (Focus).")
        else:
            st.info("Dados de IPCA não disponíveis para o período.")
    except Exception as e:
        st.error(f"Erro: {e}")

# ─── CDI diário histórico ────────────────────────────────────────────────────

st.markdown("---")
st.subheader("💰 CDI diário histórico (SGS 12)")

try:
    df_cdi = get_cdi_history(since)
    if not df_cdi.empty:
        # Show annualized
        df_cdi["cdi_anualizado"] = ((1 + df_cdi["cdi_daily"] / 100) ** 252 - 1) * 100

        fig_cdi = px.area(
            df_cdi, x="metric_date", y="cdi_anualizado",
            labels={"metric_date": "", "cdi_anualizado": "CDI anualizado (% a.a.)"},
            color_discrete_sequence=["#1f4e79"],
        )
        fig_cdi.update_traces(line_width=1, opacity=0.8)
        fig_cdi.update_layout(
            height=250,
            margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig_cdi.update_xaxes(showgrid=False)
        fig_cdi.update_yaxes(gridcolor="rgba(128,128,128,0.2)")
        st.plotly_chart(fig_cdi, use_container_width=True)
        st.caption("CDI diário (série SGS 12, BCB) anualizado por 252 dias úteis.")
    else:
        st.info("Dados de CDI não disponíveis para o período.")
except Exception as e:
    st.error(f"Erro: {e}")

# ─── Tabela de referência ─────────────────────────────────────────────────────

st.markdown("---")
st.subheader("📋 Referência atual")

if macro:
    rows = []
    codes = [
        ("CDI",       "CDI diário (SGS 12)",          "% ao dia"),
        ("SELIC",     "Selic diária (SGS 11)",         "% ao dia"),
        ("IPCA",      "IPCA mensal (SGS 433)",         "% ao mês"),
        ("IGPM",      "IGP-M mensal (SGS 189)",        "% ao mês"),
        ("CDI_PROJ",  "Selic projetada (Focus)",       "% a.a."),
        ("IPCA_PROJ", "IPCA projetado (Focus)",        "% a.a."),
    ]
    for code, desc, unit in codes:
        info = macro.get(code, {})
        if info:
            rows.append({
                "Indicador": desc,
                "Valor":     f"{info['value']:.4f}" if info.get("value") else "—",
                "Unidade":   unit,
                "Data":      str(info.get("date", "—")),
                "Fonte":     "BCB Focus" if "PROJ" in code else "BCB SGS",
            })

    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Data": st.column_config.TextColumn(width="small"),
                "Fonte": st.column_config.TextColumn(width="small"),
            }
        )

st.markdown("---")
st.caption(
    "Fonte: BCB SGS (séries históricas) · BCB Relatório Focus (expectativas de mercado) | "
    "Os indicadores são expostos como referência. A análise é feita pelo time de mesa."
)
