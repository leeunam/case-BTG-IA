"""
Atividade Institucional — metadados de ofertas com foco em concentração de players.

Nota: Ofertas com esforços restritos (ICVM 476) têm disclosure limitado por design regulatório.
Termos financeiros não disponíveis publicamente são sinalizados explicitamente.
"""
import sys
from pathlib import Path
from datetime import date, timedelta

import streamlit as st
import plotly.express as px
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.db import get_institutional_activity, get_concentration_by_coordinator

st.set_page_config(page_title="Atividade Institucional | BTG FII", layout="wide")


def _fmt_volume(v) -> str:
    if v is None or v == 0:
        return "—"
    v = float(v)
    if v >= 1e9:
        return f"R$ {v/1e9:.1f}B"
    if v >= 1e6:
        return f"R$ {v/1e6:.0f}M"
    return f"R$ {v/1e3:.0f}K"


# ─── Sidebar ─────────────────────────────────────────────────────────────────

st.sidebar.header("Filtros")

period_opts = {
    "Últimos 12 meses": 365,
    "Últimos 24 meses": 730,
    "Desde 2023":       (date.today() - date(2023, 1, 1)).days,
    "Tudo":             9999,
}
period_label = st.sidebar.selectbox(
    "Período padrão", list(period_opts.keys()), index=0,
    help="Atividade Institucional exibe 12 meses por padrão. Expanda conforme necessário."
)
since = date.today() - timedelta(days=period_opts[period_label])

audience_options = ["Todos", "profissional", "qualificado", "geral"]
selected_audience = st.sidebar.selectbox("Público-alvo", audience_options)

show_no_terms = st.sidebar.checkbox(
    "Mostrar apenas sem termos financeiros",
    value=False,
    help="Filtra ofertas onde os termos financeiros não estão disponíveis na fonte consultada"
)

st.sidebar.markdown("---")
st.sidebar.info(
    "Termos financeiros ausentes são exibidos com a mensagem padrão: "
    "**'Termos financeiros não disponíveis na fonte consultada.'**\n\n"
    "Esta aplicação não infere, estima nem sugere taxas ou condições financeiras."
)

# ─── Header ──────────────────────────────────────────────────────────────────

st.title("🏛️ Atividade Institucional")
st.caption("Metadados de ofertas primárias de FII — concentração por player e período")

st.info(
    "**Contexto regulatório**: Ofertas com esforços restritos (ICVM 476) têm disclosure reduzido "
    "por design — são direcionadas a no máximo 75 investidores profissionais. "
    "Os dados disponíveis publicamente são limitados a metadados de registro. "
    "Termos financeiros (taxa, preço, remuneração) não são obrigatoriamente divulgados.",
    icon="ℹ️"
)

# ─── Carregar dados ──────────────────────────────────────────────────────────

try:
    df = get_institutional_activity(since)
    df_conc = get_concentration_by_coordinator(since)
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

if selected_audience != "Todos":
    df = df[df["target_audience"] == selected_audience]

if show_no_terms:
    df = df[df["financial_terms_available"] == False]  # noqa: E712

# ─── KPIs ────────────────────────────────────────────────────────────────────

c1, c2, c3, c4 = st.columns(4)
c1.metric("Registros no período", f"{len(df):,}")
c2.metric(
    "Vol. autorizado (CVM)",
    _fmt_volume(df["total_volume"].sum()),
    help="Volume máximo autorizado por programa (shelf registration CVM). Não representa valor captado por emissão."
)
c3.metric(
    "Coordenadores distintos",
    f"{df['coordinator'].nunique():,}"
)
sem_termos = int((df["financial_terms_available"] == False).sum())  # noqa: E712
c4.metric(
    "Sem termos financeiros",
    f"{sem_termos:,}",
    help="Ofertas onde os termos financeiros não estão disponíveis na fonte consultada"
)

st.markdown("---")

# ─── Concentração de players ─────────────────────────────────────────────────

st.subheader("🎯 Concentração por Coordenador")

if not df_conc.empty:
    top10 = df_conc.head(10).copy()

    col_a, col_b = st.columns(2)

    with col_a:
        fig_offers = px.bar(
            top10.sort_values("total_offers"),
            x="total_offers",
            y="coordinator",
            orientation="h",
            text=top10.sort_values("total_offers")["share_offers_pct"].apply(lambda x: f"{x:.0f}%"),
            labels={"total_offers": "Nº de Ofertas", "coordinator": ""},
            color="share_offers_pct",
            color_continuous_scale="Blues",
            title="Participação por nº de ofertas",
        )
        fig_offers.update_traces(textposition="outside")
        fig_offers.update_layout(
            height=380,
            margin=dict(l=0, r=60, t=30, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_offers, use_container_width=True)

    with col_b:
        vol_top = top10[top10["total_volume"] > 0].copy()
        if not vol_top.empty:
            fig_vol = px.treemap(
                vol_top,
                path=["coordinator"],
                values="total_volume",
                color="share_volume_pct",
                color_continuous_scale="Blues",
                title="Concentração de volume (treemap)",
                custom_data=["share_volume_pct"],
            )
            fig_vol.update_traces(
                texttemplate="%{label}<br>%{customdata[0]:.1f}%"
            )
            fig_vol.update_layout(
                height=380,
                margin=dict(l=0, r=0, t=30, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig_vol, use_container_width=True)
        else:
            st.info("Volume não disponível para os coordenadores no período.")

# ─── Tabela de concentração ───────────────────────────────────────────────────

st.markdown("---")
st.subheader("📊 Tabela de concentração")

if not df_conc.empty:
    conc_display = df_conc.copy()
    conc_display["total_volume_fmt"] = conc_display["total_volume"].apply(_fmt_volume)
    conc_display["share_offers_fmt"] = conc_display["share_offers_pct"].apply(lambda x: f"{x:.1f}%")
    conc_display["share_volume_fmt"] = conc_display.get("share_volume_pct", pd.Series([0]*len(conc_display))).apply(lambda x: f"{x:.1f}%")

    conc_display.rename(columns={
        "coordinator":       "Coordenador",
        "total_offers":      "Ofertas",
        "total_volume_fmt":  "Volume Total",
        "unique_funds":      "Fundos Únicos",
        "share_offers_fmt":  "Share Qtd",
        "share_volume_fmt":  "Share Vol",
        "first_offer":       "Primeira Oferta",
        "last_offer":        "Última Oferta",
    }, inplace=True)

    cols = ["Coordenador", "Ofertas", "Volume Total", "Fundos Únicos",
            "Share Qtd", "Share Vol", "Primeira Oferta", "Última Oferta"]
    st.dataframe(
        conc_display[cols].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Ofertas":         st.column_config.NumberColumn(format="%d"),
            "Fundos Únicos":   st.column_config.NumberColumn(format="%d"),
            "Primeira Oferta": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Última Oferta":   st.column_config.DateColumn(format="DD/MM/YYYY"),
        }
    )

# ─── Listagem de ofertas ──────────────────────────────────────────────────────

st.markdown("---")
st.subheader(f"📋 Ofertas no período ({len(df):,})")

if df.empty:
    st.info("Nenhuma oferta encontrada com os filtros selecionados.")
else:
    list_display = df[[
        "cvm_registration", "fund_name", "coordinator", "registered_at",
        "total_volume", "target_audience", "financial_terms_available",
        "distribution_regime", "cvm_status", "tipo_requerimento"
    ]].copy()

    list_display["total_volume_fmt"] = list_display["total_volume"].apply(_fmt_volume)

    # Termos financeiros: mostrar mensagem padrão quando indisponível
    list_display["termos"] = list_display["financial_terms_available"].apply(
        lambda x: "✅ Disponível" if x is True else "⚠️ Termos financeiros não disponíveis na fonte consultada."
    )

    list_display.rename(columns={
        "cvm_registration":    "Nº CVM",
        "fund_name":           "Fundo",
        "coordinator":         "Coordenador",
        "registered_at":       "Registro",
        "total_volume_fmt":    "Volume",
        "target_audience":     "Público",
        "termos":              "Termos Financeiros",
        "distribution_regime": "Regime",
        "cvm_status":          "Status CVM",
        "tipo_requerimento":   "Tipo Req.",
    }, inplace=True)

    cols_list = ["Nº CVM", "Fundo", "Coordenador", "Registro", "Volume",
                 "Público", "Regime", "Termos Financeiros", "Status CVM", "Tipo Req."]

    st.dataframe(
        list_display[cols_list].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
        height=450,
        column_config={
            "Nº CVM":         st.column_config.TextColumn(width="small"),
            "Fundo":          st.column_config.TextColumn(width="large"),
            "Coordenador":    st.column_config.TextColumn(width="medium"),
            "Registro":       st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Volume":         st.column_config.TextColumn(width="small"),
            "Termos Financeiros": st.column_config.TextColumn(width="large"),
        }
    )

st.markdown("---")
st.caption(
    "Fonte: CVM Dados Abertos (Resolução 160) | "
    "Dados de concentração calculados sobre ofertas com coordenador líder identificado. | "
    "Esta aplicação não gera recomendação de investimento."
)
