"""Ofertas Primárias de FII — tabela completa com filtros."""
import sys
from pathlib import Path
from datetime import date, timedelta

import streamlit as st
import plotly.express as px
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.db import get_offers, get_coordinator_list, get_latest_macro, get_fii_metrics

st.set_page_config(page_title="Ofertas Primárias | BTG FII", layout="wide")


def _fmt_volume(v) -> str:
    if v is None or v == 0:
        return "—"
    v = float(v)
    if v >= 1e9:
        return f"R$ {v/1e9:.1f}B"
    if v >= 1e6:
        return f"R$ {v/1e6:.0f}M"
    return f"R$ {v/1e3:.0f}K"


# ─── Sidebar filtros ─────────────────────────────────────────────────────────

st.sidebar.header("Filtros")

period_options = {
    "Últimos 12 meses": 365,
    "Últimos 24 meses": 730,
    "Últimos 36 meses": 1095,
    "Desde 2023": (date.today() - date(2023, 1, 1)).days,
    "Tudo": 9999,
}
period_label = st.sidebar.selectbox("Período", list(period_options.keys()), index=1)
days_back = period_options[period_label]
since = date.today() - timedelta(days=days_back)

status_options = ["em andamento", "encerrado", "pendente", "futuro"]
selected_status = st.sidebar.multiselect(
    "Status", status_options, default=["em andamento", "pendente", "encerrado"]
)

try:
    coord_list = get_coordinator_list()
except Exception:
    coord_list = ["Todos"]
selected_coordinator = st.sidebar.selectbox("Coordenador Líder", coord_list)

audience_options = ["Todos", "profissional", "qualificado", "geral"]
selected_audience = st.sidebar.selectbox("Público-alvo", audience_options)

st.sidebar.markdown("---")
st.sidebar.caption("⚠️ Esta aplicação não gera recomendação de investimento.")

# ─── Header ──────────────────────────────────────────────────────────────────

st.title("📋 Ofertas Primárias de FII")
st.caption("Fonte: CVM Dados Abertos (Resolução 160) | Comparativo com Selic projetada (BCB Focus)")

# ─── Carregar dados ──────────────────────────────────────────────────────────

try:
    df = get_offers(
        since=since,
        status_filter=selected_status if selected_status else None,
        coordinator_filter=selected_coordinator,
        audience_filter=selected_audience,
    )
    macro = get_latest_macro()
    selic_proj = macro.get("CDI_PROJ", {}).get("value")
    ipca_proj  = macro.get("IPCA_PROJ", {}).get("value")
    macro_date = macro.get("CDI_PROJ", {}).get("date", "")

except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

# ─── KPIs da seleção ─────────────────────────────────────────────────────────

c1, c2, c3, c4 = st.columns(4)
c1.metric("Ofertas no período", f"{len(df):,}")
c2.metric("Volume total", _fmt_volume(df["total_volume"].sum()))
c3.metric(
    "Selic projetada",
    f"{selic_proj:.2f}% a.a." if selic_proj else "—",
    help=f"BCB Focus mediana em {macro_date}"
)
c4.metric(
    "IPCA projetado",
    f"{ipca_proj:.2f}% a.a." if ipca_proj else "—",
    help=f"BCB Focus mediana em {macro_date}"
)

st.markdown("---")

if df.empty:
    st.info("Nenhuma oferta encontrada com os filtros selecionados.")
    st.stop()

# ─── Tabela principal ─────────────────────────────────────────────────────────

st.subheader(f"📄 {len(df):,} ofertas encontradas")

# Prepare display columns
display = df[[
    "cvm_registration", "fund_name", "security_type", "status",
    "coordinator", "total_volume", "registered_at",
    "started_at", "ends_at", "target_audience",
    "distribution_regime", "bookbuilding", "cvm_status"
]].copy()

display["total_volume_fmt"] = display["total_volume"].apply(_fmt_volume)
display["bookbuilding"] = display["bookbuilding"].map({True: "Sim", False: "Não", None: "—"})

display.rename(columns={
    "cvm_registration":  "Nº CVM",
    "fund_name":         "Fundo",
    "security_type":     "Tipo",
    "status":            "Status",
    "coordinator":       "Coordenador",
    "total_volume_fmt":  "Volume",
    "registered_at":     "Registro",
    "started_at":        "Início",
    "ends_at":           "Encerramento",
    "target_audience":   "Público",
    "distribution_regime": "Regime",
    "bookbuilding":      "Bookbuilding",
    "cvm_status":        "Status CVM",
}, inplace=True)

cols_show = ["Nº CVM", "Fundo", "Tipo", "Status", "Coordenador",
             "Volume", "Registro", "Início", "Encerramento",
             "Público", "Regime", "Bookbuilding"]

st.dataframe(
    display[cols_show].reset_index(drop=True),
    use_container_width=True,
    hide_index=True,
    height=500,
    column_config={
        "Nº CVM":        st.column_config.TextColumn(width="small"),
        "Fundo":         st.column_config.TextColumn(width="large"),
        "Tipo":          st.column_config.TextColumn(width="medium"),
        "Status":        st.column_config.TextColumn(width="small"),
        "Coordenador":   st.column_config.TextColumn(width="medium"),
        "Volume":        st.column_config.TextColumn(width="small"),
        "Registro":      st.column_config.DateColumn(format="DD/MM/YYYY", width="small"),
        "Início":        st.column_config.DateColumn(format="DD/MM/YYYY", width="small"),
        "Encerramento":  st.column_config.DateColumn(format="DD/MM/YYYY", width="small"),
        "Público":       st.column_config.TextColumn(width="small"),
        "Regime":        st.column_config.TextColumn(width="medium"),
        "Bookbuilding":  st.column_config.TextColumn(width="small"),
    }
)

# ─── Gráficos ────────────────────────────────────────────────────────────────

st.markdown("---")
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("📅 Ofertas por mês")
    df_month = df.dropna(subset=["registered_at"]).copy()
    df_month["mes"] = pd.to_datetime(df_month["registered_at"]).dt.to_period("M").dt.to_timestamp()
    monthly = df_month.groupby("mes").size().reset_index(name="qtd")
    fig = px.bar(
        monthly, x="mes", y="qtd",
        labels={"mes": "", "qtd": "Ofertas"},
        color_discrete_sequence=["#1f4e79"],
    )
    fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.subheader("💰 Volume por mês (R$)")
    vol_month = df_month.copy()
    vol_month["volume_bi"] = vol_month["total_volume"].fillna(0) / 1e9
    vol_agg = vol_month.groupby("mes")["volume_bi"].sum().reset_index()
    fig2 = px.bar(
        vol_agg, x="mes", y="volume_bi",
        labels={"mes": "", "volume_bi": "Volume (R$ B)"},
        color_discrete_sequence=["#2e75b6"],
    )
    fig2.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0),
                       plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig2, use_container_width=True)

# ─── Dados de mercado secundário ─────────────────────────────────────────────

st.markdown("---")
with st.expander("📊 Referência: mercado secundário (Fundamentus)", expanded=False):
    st.caption(
        "Dados de DY, P/VP e vacância do mercado **secundário** (Fundamentus). "
        "Não são métricas das ofertas primárias acima — servem como referência de mercado."
    )
    try:
        df_mkt = get_fii_metrics()
        if not df_mkt.empty:
            df_mkt_show = df_mkt[[
                "ticker", "segment", "dy_12m", "pvp", "price", "vacancy_rate"
            ]].copy()
            df_mkt_show.rename(columns={
                "ticker": "Ticker", "segment": "Segmento",
                "dy_12m": "DY 12m (%)", "pvp": "P/VP",
                "price": "Cotação (R$)", "vacancy_rate": "Vacância (%)"
            }, inplace=True)

            if selic_proj:
                df_mkt_show["DY - Selic (pp)"] = (
                    df_mkt_show["DY 12m (%)"] - float(selic_proj)
                ).round(2)

            st.dataframe(
                df_mkt_show.reset_index(drop=True),
                use_container_width=True,
                hide_index=True,
                height=350,
                column_config={
                    "DY 12m (%)":    st.column_config.NumberColumn(format="%.2f%%"),
                    "P/VP":          st.column_config.NumberColumn(format="%.2f"),
                    "Cotação (R$)":  st.column_config.NumberColumn(format="R$ %.2f"),
                    "Vacância (%)":  st.column_config.NumberColumn(format="%.2f%%"),
                    "DY - Selic (pp)": st.column_config.NumberColumn(format="%.2f"),
                }
            )
            st.caption(
                f"⚠️ DY e P/VP expostos como referência. "
                f"A análise de oportunidade é feita pela mesa com base nesses dados. "
                f"Selic proj. usada como referência: {selic_proj:.2f}% a.a."
                if selic_proj else ""
            )
    except Exception as e:
        st.error(f"Erro ao carregar dados de mercado: {e}")
