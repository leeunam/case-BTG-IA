"""

Evoluções futuras:
    - Adicionar memória persistente com checkpointers do LangGraph para o
      agente lembrar conversas anteriores entre sessões.
    - Incluir ChromaDB como vector store para busca semântica sobre histórico
      de emissões (ex: "emissões parecidas com essa CRA de 2024").
    - Integrar ferramenta de web search para correlacionar ofertas com
      eventos macroeconômicos recentes (Selic, IPCA, decisões do Copom).
    - Expor o agente via Streamlit para interface visual com filtros interativos.
    - Substituir scraping manual por pipeline agendado (cron) que atualiza os
      dados automaticamente e alimenta o agente com informações frescas.
"""

import json
import os
import unicodedata
import warnings
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_groq import ChatGroq

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from langgraph.prebuilt import create_react_agent

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# ─── Carrega dados uma vez ao iniciar (evita re-leitura a cada tool call) ─────

_df_cvm = pd.read_csv(DATA_DIR / "cvm" / "oferta_resolucao_160.csv", sep=";")
_df_cvm["Data_Registro"] = pd.to_datetime(_df_cvm["Data_Registro"], errors="coerce")
_df_cvm["Ano"] = _df_cvm["Data_Registro"].dt.year

with open(DATA_DIR / "cvm" / "carteira_xp_maio2026.json", encoding="utf-8") as f:
    _carteira_xp = json.load(f)

with open(DATA_DIR / "meelion" / "investimentos_page1.json", encoding="utf-8") as f:
    _meelion = json.load(f)


# ─── Tools ────────────────────────────────────────────────────────────────────

@tool
def resumo_mercado_cvm() -> str:
    """
    Retorna um resumo geral do mercado de ofertas primárias registradas na CVM
    (2023–2026): total de ofertas, volume financeiro, breakdown por tipo de ativo
    e pelos maiores líderes de distribuição.
    Use quando o usuário pedir uma visão geral do mercado ou quiser saber
    quais tipos de ativos e bancos dominam as emissões.
    """
    total = len(_df_cvm)
    volume = _df_cvm["Valor_Total_Registrado"].sum() / 1e9

    por_tipo = (
        _df_cvm.groupby("Valor_Mobiliario")["Valor_Total_Registrado"]
        .agg(qtd="count", volume_bi=lambda x: x.sum() / 1e9)
        .sort_values("volume_bi", ascending=False)
        .head(8)
    )

    por_lider = (
        _df_cvm.groupby("Nome_Lider")["Valor_Total_Registrado"]
        .agg(qtd="count", volume_bi=lambda x: x.sum() / 1e9)
        .sort_values("volume_bi", ascending=False)
        .head(6)
    )

    por_ano = (
        _df_cvm.groupby("Ano")["Valor_Total_Registrado"]
        .agg(qtd="count", volume_bi=lambda x: x.sum() / 1e9)
        .sort_index()
    )

    return (
        f"RESUMO MERCADO CVM (Resolução 160 — 2023 a 2026)\n"
        f"Total de ofertas registradas: {total:,}\n"
        f"Volume total: R$ {volume:.1f} bilhões\n\n"
        f"Por tipo de ativo (top 8):\n{por_tipo.to_string()}\n\n"
        f"Por líder de distribuição (top 6):\n{por_lider.to_string()}\n\n"
        f"Por ano:\n{por_ano.to_string()}"
    )


@tool
def buscar_ofertas_cvm(tipo: str = "", lider: str = "", ano: int = 0, limite: int = 10) -> str:
    """
    Busca ofertas primárias na base da CVM com filtros opcionais.

    Parâmetros:
        tipo  — tipo de ativo (ex: 'Debêntures', 'CRI', 'CRA', 'FIDC', 'FII').
                Busca parcial, case-insensitive.
        lider — nome do banco líder (ex: 'BTG', 'XP', 'Itaú', 'Bradesco').
                Busca parcial, case-insensitive.
        ano   — ano de registro (ex: 2024, 2025). 0 = todos os anos.
        limite — número máximo de resultados (padrão: 10).

    Retorna as colunas mais relevantes: data, tipo, emissor, líder, volume e status.
    """
    df = _df_cvm.copy()

    def normalize(s: str) -> str:
        return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()

    if tipo:
        df = df[df["Valor_Mobiliario"].map(normalize).str.contains(normalize(tipo), case=False, na=False)]
    if lider:
        df = df[df["Nome_Lider"].map(normalize).str.contains(normalize(lider), case=False, na=False)]
    if ano:
        df = df[df["Ano"] == ano]

    if df.empty:
        return "Nenhuma oferta encontrada com os filtros informados."

    cols = ["Data_Registro", "Valor_Mobiliario", "Nome_Emissor", "Nome_Lider",
            "Valor_Total_Registrado", "Status_Requerimento"]
    resultado = df[cols].sort_values("Data_Registro", ascending=False).head(limite)
    resultado = resultado.copy()
    resultado["Valor_Total_Registrado"] = resultado["Valor_Total_Registrado"].apply(
        lambda v: f"R$ {v/1e6:.1f}M" if pd.notna(v) else "N/D"
    )
    resultado["Data_Registro"] = resultado["Data_Registro"].dt.strftime("%d/%m/%Y")

    return (
        f"Encontradas {len(df):,} ofertas (exibindo {min(limite, len(df))}):\n\n"
        + resultado.to_string(index=False)
    )


@tool
def carteira_recomendada_xp() -> str:
    """
    Retorna a carteira de renda fixa recomendada pela XP Investimentos para Maio 2026,
    extraída de artigo financeiro via LLM. Inclui todos os títulos com taxa, indexador,
    vencimento, isenção de IR e observações.
    Use quando o usuário perguntar sobre recomendações da XP, títulos específicos
    da carteira ou quiser comparar ofertas do mercado com as recomendações.
    """
    c = _carteira_xp
    linhas = [
        f"CARTEIRA XP — {c['data_referencia']}",
        f"Instituição: {c['instituicao']}",
        f"Estratégia: {c['resumo_estrategia']}",
        f"Fonte: {c['fonte_url']}",
        f"\n{len(c['titulos'])} títulos recomendados:",
    ]
    for i, t in enumerate(c["titulos"], 1):
        ir = " [ISENTO IR]" if t["isento_ir"] else ""
        gross = f" | Gross-up: {t['taxa_gross_up']}" if t.get("taxa_gross_up") else ""
        linhas.append(
            f"\n  {i}. {t['ativo_emissor']}{ir}\n"
            f"     Indexador: {t['indexador']} | Taxa: {t['taxa_bruta']}{gross}\n"
            f"     Vencimento: {t['vencimento']}"
        )
    return "\n".join(linhas)


@tool
def investimentos_meelion() -> str:
    """
    Retorna os investimentos de renda fixa disponíveis no comparador Meelion
    (dados coletados via scraping — plano free, página 1).
    Inclui nome, tipo, cobertura FGC, emissor, distribuidor e vencimento.
    Use quando o usuário quiser ver ofertas disponíveis em plataformas de
    distribuição ou comparar com as recomendações da XP.
    """
    linhas = [f"INVESTIMENTOS MEELION ({len(_meelion)} resultados — plano free):"]
    for i, inv in enumerate(_meelion, 1):
        fgc = "Com FGC" if inv["com_fgc"] else "Sem FGC"
        linhas.append(
            f"\n  {i}. {inv['nome']}\n"
            f"     Tipo: {inv['tipo']} | {fgc}\n"
            f"     Emissor: {inv['emissor']} | Distribuidor: {inv['distribuidor']}\n"
            f"     Vencimento: {inv['vencimento']}"
        )
    return "\n".join(linhas)


# ─── Agente ───────────────────────────────────────────────────────────────────

def build_agent():
    if not os.environ.get("GROQ_API_KEY"):
        raise EnvironmentError("Defina GROQ_API_KEY no arquivo .env")

    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

    tools = [
        resumo_mercado_cvm,
        buscar_ofertas_cvm,
        carteira_recomendada_xp,
        investimentos_meelion,
    ]

    system_prompt = """Você é um analista de mercado financeiro especializado em ofertas primárias de renda fixa no Brasil.

Você tem acesso a dados reais:
- Base CVM (Resolução 160): 13.015 ofertas registradas de 2023 a 2026
- Carteira recomendada da XP Investimentos para Maio 2026
- Investimentos disponíveis no comparador Meelion (scraping ao vivo)

Ao responder:
- Sempre consulte as ferramentas disponíveis antes de responder sobre dados concretos
- Cite volumes em reais (ex: R$ 2,3 bilhões) e use linguagem técnica mas acessível
- Quando relevante, compare fontes diferentes (ex: o que a CVM registrou vs o que a XP recomenda)
- Seja objetivo: números primeiro, interpretação depois
- Se o usuário pedir algo que seus dados não cobrem, diga claramente o que está fora do escopo"""

    return create_react_agent(llm, tools, prompt=system_prompt)


# ─── Loop interativo ──────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  LigaAI — Agente de Análise de Ofertas Primárias")
    print("  Dados: CVM 2023-2026 | Carteira XP | Meelion")
    print("  Digite 'sair' para encerrar")
    print("=" * 60)

    agent = build_agent()

    while True:
        pergunta = input("\nVocê: ").strip()
        if not pergunta or pergunta.lower() in {"sair", "exit", "quit"}:
            print("Encerrando agente.")
            break

        # stream() emite um evento por passo: tool calls e resposta final visíveis
        for step in agent.stream(
            {"messages": [{"role": "user", "content": pergunta}]},
            stream_mode="updates",
        ):
            # Passo de tool call: mostra qual ferramenta foi chamada
            if "tools" in step:
                for msg in step["tools"]["messages"]:
                    print(f"\n  [tool: {msg.name}] → {msg.content[:120]}...")

            # Passo final do agente: imprime a resposta
            if "agent" in step:
                last = step["agent"]["messages"][-1]
                if last.content:
                    print(f"\nAgente: {last.content}")


if __name__ == "__main__":
    main()
