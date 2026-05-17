"""Alertas — novidades detectadas automaticamente pelo pipeline diário."""
import sys
from pathlib import Path
from datetime import date, timedelta

import streamlit as st
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from app.db import get_alerts, mark_alerts_read, get_alert_counts

st.set_page_config(page_title="Alertas | BTG FII", layout="wide")

_TYPE_LABELS = {
    "new_offer":     "🆕 Nova oferta",
    "status_change": "🔄 Mudança de status",
    "new_player":    "👤 Novo player",
    "concentration": "⚠️ Concentração",
    "data_gap":      "⚠️ Lacuna de dados",
}
_TYPE_COLORS = {
    "new_offer":     "🟢",
    "status_change": "🟡",
    "new_player":    "🔵",
    "concentration": "🟠",
    "data_gap":      "🔴",
}

# ─── Sidebar ─────────────────────────────────────────────────────────────────

st.sidebar.header("Filtros")
period_opts = {"7 dias": 7, "30 dias": 30, "90 dias": 90, "Tudo": 3650}
period_label = st.sidebar.selectbox("Período", list(period_opts.keys()), index=1)
days_back = period_opts[period_label]

type_options = list(_TYPE_LABELS.values()) + ["Todos"]
selected_type_label = st.sidebar.selectbox("Tipo de alerta", ["Todos"] + list(_TYPE_LABELS.values()))
only_unread = st.sidebar.checkbox("Apenas não lidos", value=False)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Alertas são gerados automaticamente pelo pipeline diário "
    "quando novas ofertas são detectadas ou o status de uma oferta muda."
)

# ─── Header ──────────────────────────────────────────────────────────────────

st.title("🔔 Alertas")
st.caption("Novidades detectadas pelo pipeline de coleta diário")

# ─── KPIs ────────────────────────────────────────────────────────────────────

try:
    counts = get_alert_counts()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total de alertas", f"{counts['total']:,}")
    c2.metric("Não lidos", f"{counts['unread']:,}",
              delta=f"-{counts['unread']}" if counts['unread'] > 0 else None,
              delta_color="inverse")
    top_type = max(counts["by_type"], key=counts["by_type"].get) if counts["by_type"] else "—"
    c3.metric("Tipo mais frequente", _TYPE_LABELS.get(top_type, top_type))
except Exception as e:
    st.error(f"Erro ao carregar contagens: {e}")

st.markdown("---")

# ─── Load alerts ─────────────────────────────────────────────────────────────

try:
    df = get_alerts(days_back=days_back, only_unread=only_unread)
except Exception as e:
    st.error(f"Erro ao carregar alertas: {e}")
    st.stop()

# Filter by type if selected
if selected_type_label != "Todos":
    reverse_map = {v: k for k, v in _TYPE_LABELS.items()}
    selected_type_code = reverse_map.get(selected_type_label)
    if selected_type_code:
        df = df[df["type"] == selected_type_code]

if df.empty:
    st.info("Nenhum alerta encontrado para os filtros selecionados.")
    st.caption(
        "Os alertas são gerados quando o pipeline roda. "
        "Execute `.venv/bin/python -m src.pipeline.run` para gerar alertas."
    )
    st.stop()

# ─── Marcar como lido ────────────────────────────────────────────────────────

unread_ids = df[df["is_read"] == False]["id"].tolist()  # noqa: E712
if unread_ids:
    col_btn, col_info = st.columns([1, 4])
    with col_btn:
        if st.button(f"✅ Marcar {len(unread_ids)} como lido(s)"):
            try:
                mark_alerts_read(unread_ids)
                st.success("Alertas marcados como lidos.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")
    with col_info:
        st.caption(f"{len(unread_ids)} alertas não lidos no período.")

st.markdown("---")

# ─── Tabela de alertas ────────────────────────────────────────────────────────

st.subheader(f"📋 {len(df):,} alertas")

display = df.copy()
display["tipo"] = display["type"].apply(
    lambda t: f"{_TYPE_COLORS.get(t, '⚪')} {_TYPE_LABELS.get(t, t)}"
)
display["lido"] = display["is_read"].apply(lambda x: "✅" if x else "🔴 Novo")

# Extract detail fields
def _detail_str(detail) -> str:
    if not detail:
        return ""
    if isinstance(detail, dict):
        parts = []
        if "from" in detail and "to" in detail:
            parts.append(f"{detail['from']} → {detail['to']}")
        if "fund" in detail:
            parts.append(detail["fund"])
        if "source" in detail:
            parts.append(f"[{detail['source']}]")
        return " | ".join(parts)
    return str(detail)

display["detalhe"] = display["detail"].apply(_detail_str)

display.rename(columns={
    "tipo":       "Tipo",
    "lido":       "Status",
    "fund_name":  "Fundo",
    "ticker":     "Ticker",
    "created_at": "Data/hora",
    "detalhe":    "Detalhe",
}, inplace=True)

cols = ["Tipo", "Status", "Fundo", "Ticker", "Data/hora", "Detalhe"]
st.dataframe(
    display[cols].reset_index(drop=True),
    use_container_width=True,
    hide_index=True,
    height=500,
    column_config={
        "Tipo":      st.column_config.TextColumn(width="medium"),
        "Status":    st.column_config.TextColumn(width="small"),
        "Fundo":     st.column_config.TextColumn(width="large"),
        "Ticker":    st.column_config.TextColumn(width="small"),
        "Data/hora": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm", width="medium"),
        "Detalhe":   st.column_config.TextColumn(width="large"),
    }
)

# ─── Distribuição por tipo ────────────────────────────────────────────────────

if len(df) > 1:
    st.markdown("---")
    st.subheader("📊 Por tipo")
    type_counts = df["type"].value_counts().reset_index()
    type_counts.columns = ["type", "count"]
    type_counts["label"] = type_counts["type"].apply(lambda t: _TYPE_LABELS.get(t, t))

    import plotly.express as px
    fig = px.bar(
        type_counts, x="label", y="count",
        labels={"label": "", "count": "Alertas"},
        color="count", color_continuous_scale="Blues",
    )
    fig.update_layout(
        height=200,
        margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig, use_container_width=True)
