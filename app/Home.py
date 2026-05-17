"""
BTG FII Analyzer — Home
Run: streamlit run app/Home.py
"""
import sys
from pathlib import Path
from datetime import date, timedelta

import streamlit as st
import plotly.express as px

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.db import get_kpis, get_latest_macro, get_offers, get_macro_history

st.set_page_config(
    page_title="BTG FII Analyzer",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _fmt_volume(v) -> str:
    if v is None or v == 0:
        return "—"
    v = float(v)
    if v >= 1e9:
        return f"R$ {v/1e9:.1f}B"
    if v >= 1e6:
        return f"R$ {v/1e6:.0f}M"
    if v >= 1e3:
        return f"R$ {v/1e3:.0f}K"
    return f"R$ {v:.0f}"

# ─── Sidebar ─────────────────────────────────────────────────────────────────

st.sidebar.title("BTG FII Analyzer")
st.sidebar.caption("Monitoramento de ofertas primárias de FII")
st.sidebar.markdown("---")
st.sidebar.info(
    "Os dados exibidos são coletados de fontes públicas (CVM, Fundamentus, BCB). "
    "**Esta aplicação não gera recomendação de investimento.**"
)

# ─── Header ──────────────────────────────────────────────────────────────────

st.title("🏢 BTG FII Analyzer")
st.caption("Monitoramento e análise de ofertas primárias de Fundos Imobiliários")
st.markdown("---")

# ─── KPIs ────────────────────────────────────────────────────────────────────

try:
    kpis = get_kpis()
    macro = get_latest_macro()

    cdi_proj  = macro.get("CDI_PROJ",  {}).get("value", None)
    ipca_proj = macro.get("IPCA_PROJ", {}).get("value", None)
    cdi_date  = macro.get("CDI_PROJ",  {}).get("date", "")
    cdi_diario = macro.get("CDI", {}).get("value", None)

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric(
        "Total de Ofertas",
        f"{kpis['total_offers']:,}",
        help="Ofertas primárias de FII registradas na CVM (Res. 160)"
    )
    col2.metric(
        "Em Andamento",
        f"{kpis['in_progress']:,}",
        help="Ofertas com data de início registrada e sem encerramento"
    )
    col3.metric(
        "Mediana por oferta",
        _fmt_volume(kpis["median_volume"]),
        help=(
            "Mediana do Valor_Total_Registrado por programa de emissão (CVM). "
            "Esse campo representa o limite máximo autorizado do programa de prateleira "
            "(shelf registration), não o valor efetivamente captado em cada emissão. "
            f"Faixa típica (R$50M–R$500M): {kpis['typical_count']:,} ofertas, "
            f"média R${kpis['avg_typical_m']:.0f}M."
        )
    )
    col4.metric(
        "Selic Projetada (Focus)",
        f"{cdi_proj:.2f}% a.a." if cdi_proj else "—",
        help=f"Mediana do mercado em {cdi_date}. Fonte: BCB Focus"
    )
    col5.metric(
        "IPCA Projetado (Focus)",
        f"{ipca_proj:.2f}% a.a." if ipca_proj else "—",
        help=f"Mediana do mercado em {cdi_date}. Fonte: BCB Focus"
    )

except Exception as e:
    st.error(f"Erro ao carregar KPIs: {e}")

st.markdown("---")

# ─── Últimas ofertas ─────────────────────────────────────────────────────────

col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📋 Ofertas Recentes")
    try:
        since = date.today() - timedelta(days=365)
        df = get_offers(since=since)

        if df.empty:
            st.info("Nenhuma oferta encontrada no período.")
        else:
            display = df[[
                "fund_name", "coordinator", "status", "total_volume",
                "registered_at", "target_audience"
            ]].head(20).copy()

            display["total_volume"] = display["total_volume"].apply(
                lambda x: _fmt_volume(x) if x else "—"
            )
            display.columns = ["Fundo", "Coordenador", "Status", "Volume", "Registro", "Público"]
            display = display.reset_index(drop=True)

            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Status": st.column_config.TextColumn(width="small"),
                    "Volume": st.column_config.TextColumn(width="medium"),
                    "Registro": st.column_config.DateColumn(format="DD/MM/YYYY"),
                }
            )
            st.caption(f"Mostrando 20 mais recentes de {len(df)} ofertas no período.")

    except Exception as e:
        st.error(f"Erro ao carregar ofertas: {e}")

with col_right:
    st.subheader("📈 Macro: Selic vs IPCA")
    try:
        since_macro = date.today() - timedelta(days=365 * 3)
        df_macro = get_macro_history(["CDI_PROJ", "IPCA_PROJ"], since_macro)

        if not df_macro.empty:
            label_map = {"CDI_PROJ": "Selic Proj.", "IPCA_PROJ": "IPCA Proj."}
            df_macro["indicator"] = df_macro["code"].map(label_map)
            fig = px.line(
                df_macro,
                x="metric_date",
                y="value",
                color="indicator",
                labels={"metric_date": "", "value": "% a.a.", "indicator": ""},
                color_discrete_map={"Selic Proj.": "#1f77b4", "IPCA Proj.": "#ff7f0e"},
            )
            fig.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.2)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Dados macro não disponíveis.")

    except Exception as e:
        st.error(f"Erro ao carregar macro: {e}")

    st.subheader("🏗️ Distribuição por Status")
    try:
        df_all = get_offers(since=date(2023, 1, 1))
        if not df_all.empty:
            counts = df_all["status"].value_counts().reset_index()
            counts.columns = ["Status", "Qtd"]
            fig2 = px.pie(
                counts, values="Qtd", names="Status",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig2.update_layout(
                height=250,
                margin=dict(l=0, r=0, t=10, b=0),
                showlegend=True,
                legend=dict(orientation="h"),
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig2, use_container_width=True)
    except Exception as e:
        st.error(f"Erro ao carregar status: {e}")

st.markdown("---")
st.caption(
    "Dados: CVM Dados Abertos · Fundamentus · BCB SGS · BCB Focus | "
    "Atualização diária às 06:30 | "
    "Esta aplicação não gera recomendação de investimento."
)
