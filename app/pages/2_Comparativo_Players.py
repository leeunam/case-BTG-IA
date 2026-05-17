"""Comparativo de Players — ranking de coordenadores por ofertas e volume."""
import sys
from pathlib import Path
from datetime import date, timedelta

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.db import get_players_summary, get_players_timeline

st.set_page_config(page_title="Comparativo Players | BTG FII", layout="wide")


def _fmt_volume(v) -> str:
    if v is None or v == 0:
        return "—"
    v = float(v)
    if v >= 1e9:
        return f"R$ {v/1e9:.1f}B"
    if v >= 1e6:
        return f"R$ {v/1e6:.0f}M"
    return f"R$ {v/1e3:.0f}K"


# ─── Sidebar ──────────────────────────────────────────────────────────────────

st.sidebar.header("Filtros")

period_opts = {
    "Últimos 12 meses": 365,
    "Últimos 24 meses": 730,
    "Desde 2023":       (date.today() - date(2023, 1, 1)).days,
    "Tudo":             9999,
}
period_label = st.sidebar.selectbox("Período de análise", list(period_opts.keys()), index=1)
since = date.today() - timedelta(days=period_opts[period_label])

top_n = st.sidebar.slider("Top N coordenadores", min_value=3, max_value=20, value=10)

st.sidebar.markdown("---")
st.sidebar.caption("⚠️ Esta aplicação não gera recomendação de investimento.")

# ─── Header ───────────────────────────────────────────────────────────────────

st.title("🏆 Comparativo de Players")
st.caption("Ranking de coordenadores líderes em ofertas primárias de FII")

# ─── Carregar dados ──────────────────────────────────────────────────────────

try:
    df = get_players_summary(since)
    df_timeline = get_players_timeline(since)
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

if df.empty:
    st.info("Nenhum dado encontrado para o período selecionado.")
    st.stop()

total_offers = int(df["total_offers"].sum())
total_volume = float(df["total_volume"].sum())
df["share_pct"] = (df["total_offers"] / total_offers * 100).round(1)
df["share_vol_pct"] = (df["total_volume"] / total_volume * 100).round(1) if total_volume > 0 else 0

top_df = df.head(top_n)

_VOL_NOTE = (
    "Volume máximo autorizado por programa (CVM shelf registration). "
    "O valor captado em cada emissão é tipicamente menor. "
    "Use como referência de proporção entre players, não como valor absoluto."
)

# ─── KPIs ────────────────────────────────────────────────────────────────────

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total de ofertas", f"{total_offers:,}")
c2.metric("Vol. autorizado (CVM)", _fmt_volume(total_volume), help=_VOL_NOTE)
c3.metric("Coordenadores ativos", f"{len(df):,}")
top_coord = df.iloc[0]["coordinator"] if not df.empty else "—"
c4.metric("Mais ativo", top_coord[:30] if top_coord else "—")

st.markdown("---")

# ─── Gráficos ────────────────────────────────────────────────────────────────

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📊 Ofertas por coordenador")
    fig_bar = px.bar(
        top_df.sort_values("total_offers"),
        x="total_offers",
        y="coordinator",
        orientation="h",
        text="total_offers",
        labels={"total_offers": "Nº de Ofertas", "coordinator": ""},
        color="total_offers",
        color_continuous_scale="Blues",
    )
    fig_bar.update_traces(textposition="outside")
    fig_bar.update_layout(
        height=400,
        margin=dict(l=0, r=60, t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col_right:
    st.subheader("💰 Concentração de volume")
    fig_pie = px.pie(
        top_df,
        values="total_volume",
        names="coordinator",
        hole=0.35,
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    fig_pie.update_layout(
        height=400,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# ─── Timeline ────────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("📅 Atividade ao longo do tempo")

if not df_timeline.empty:
    top_coords = top_df["coordinator"].tolist()
    df_tl = df_timeline[df_timeline["coordinator"].isin(top_coords)].copy()

    if not df_tl.empty:
        df_tl["month_str"] = pd.to_datetime(df_tl["month"]).dt.strftime("%Y-%m")
        fig_tl = px.bar(
            df_tl,
            x="month",
            y="offers",
            color="coordinator",
            labels={"month": "", "offers": "Ofertas", "coordinator": "Coordenador"},
            barmode="stack",
        )
        fig_tl.update_layout(
            height=320,
            margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="top", y=-0.15),
        )
        st.plotly_chart(fig_tl, use_container_width=True)

# ─── Tabela resumo ────────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("📋 Ranking completo")

display = df.copy()
display["total_volume_fmt"] = display["total_volume"].apply(_fmt_volume)
display["share_pct_fmt"]    = display["share_pct"].apply(lambda x: f"{x:.1f}%")
display["share_vol_fmt"]    = display["share_vol_pct"].apply(lambda x: f"{x:.1f}%")

display.rename(columns={
    "coordinator":       "Coordenador",
    "total_offers":      "Ofertas",
    "total_volume_fmt":  "Volume Total",
    "unique_funds":      "Fundos Únicos",
    "share_pct_fmt":     "Share (qtd)",
    "share_vol_fmt":     "Share (vol)",
    "first_offer":       "Primeira Oferta",
    "last_offer":        "Última Oferta",
}, inplace=True)

cols = ["Coordenador", "Ofertas", "Volume Total", "Fundos Únicos",
        "Share (qtd)", "Share (vol)", "Primeira Oferta", "Última Oferta"]

st.dataframe(
    display[cols].reset_index(drop=True),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Ofertas":        st.column_config.NumberColumn(format="%d"),
        "Fundos Únicos":  st.column_config.NumberColumn(format="%d"),
        "Primeira Oferta": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Última Oferta":  st.column_config.DateColumn(format="DD/MM/YYYY"),
    }
)

# ─── Alerta de concentração ──────────────────────────────────────────────────

top1_share = float(df.iloc[0]["share_pct"]) if not df.empty else 0
top3_share = float(df.head(3)["share_pct"].sum()) if len(df) >= 3 else top1_share

if top1_share >= 40:
    st.warning(
        f"⚠️ **Concentração elevada**: {df.iloc[0]['coordinator']} lidera "
        f"com {top1_share:.0f}% das ofertas no período.",
        icon="⚠️"
    )
if top3_share >= 70:
    top3_names = " · ".join(df.head(3)["coordinator"].tolist())
    st.info(
        f"ℹ️ Os 3 maiores coordenadores concentram {top3_share:.0f}% das ofertas: {top3_names}"
    )
