#!/usr/bin/env python3
"""
Download e análise dos dados de Ofertas Públicas de Distribuição da CVM.

Fonte: https://dados.cvm.gov.br/dataset/oferta-distrib

Contém dois arquivos CSV dentro de um ZIP:
  1. oferta_distribuicao.csv — Histórico completo (1988–hoje)
     Ofertas registradas/dispensadas: ICVM 400, RCVM 160, ICVM 476, ICVM 555

  2. oferta_resolucao_160.csv — Rito automático (2023–hoje)
     Ofertas sob Resolução CVM 160 com dados detalhados de coordinadores,
     público-alvo, regime de distribuição, etc.

Relevância para o projeto:
  - Base oficial e obrigatória de TODAS as ofertas públicas no Brasil
  - Contém emissor, instituição líder/coordenadora, tipo de ativo, volume, datas
  - Permite análise comparativa entre instituições (BTG, XP, Itaú, etc.)
  - Dados atualizados diariamente pela CVM
"""

import os
import sys
import zipfile
import io
import requests
import pandas as pd
from pathlib import Path

# ─── Configuração ─────────────────────────────────────────────────────────────

# Resolve paths relative to project root (parent of src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CVM_BASE_URL = "https://dados.cvm.gov.br/dados/OFERTA/DISTRIB/DADOS"
ZIP_URL = f"{CVM_BASE_URL}/oferta_distribuicao.zip"

DATA_DIR = PROJECT_ROOT / "data" / "cvm"

# Ambos os CSVs estão no mesmo ZIP
FILES = {
    "oferta_distribuicao": {
        "csv_index": 0,
        "description": "Histórico completo (1988–hoje) — ICVM 400, RCVM 160, ICVM 476, ICVM 555",
    },
    "oferta_resolucao_160": {
        "csv_index": 1,
        "description": "Rito automático (2023–hoje) — Resolução CVM 160",
    },
}


# ─── Download ─────────────────────────────────────────────────────────────────

def download_zip(url: str) -> zipfile.ZipFile:
    """Baixa o ZIP da CVM e retorna o objeto ZipFile."""
    print(f"\n{'='*80}")
    print(f"📥 Baixando dados da CVM...")
    print(f"   URL: {url}")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    size_mb = len(resp.content) / 1024 / 1024
    print(f"   Tamanho: {size_mb:.1f} MB")
    return zipfile.ZipFile(io.BytesIO(resp.content))


def extract_csv(zf: zipfile.ZipFile, csv_index: int) -> pd.DataFrame:
    """Extrai um CSV do ZIP e retorna como DataFrame."""
    csv_files = [n for n in zf.namelist() if n.endswith(".csv")]
    csv_name = csv_files[csv_index]
    print(f"   Extraindo: {csv_name}")

    with zf.open(csv_name) as f:
        # O CSV da CVM usa SEMICOLÓN (;) como separador e encoding latin-1.
        # Algumas linhas têm inconsistências, então usamos engine='python'.
        df = pd.read_csv(
            f, sep=";", encoding="latin-1",
            engine="python", on_bad_lines="skip",
        )

    print(f"   → {len(df):,} linhas, {len(df.columns)} colunas")
    return df


# ─── Análise ──────────────────────────────────────────────────────────────────

def analyze_oferta_distribuicao(df: pd.DataFrame):
    """Análise detalhada do dataset oferta_distribuicao.csv."""
    print(f"\n{'='*80}")
    print(f"📊 DATASET 1: oferta_distribuicao.csv")
    print(f"{'='*80}")
    print(f"   Registros: {len(df):,}")
    print(f"   Colunas:   {len(df.columns)}")

    # Período
    df["Ano"] = pd.to_datetime(df["Data_Registro_Oferta"], errors="coerce").dt.year
    ano_min = df["Ano"].dropna().min()
    ano_max = df["Ano"].dropna().max()
    print(f"   Período:   {int(ano_min)} – {int(ano_max)}")

    # ── 1. Tipo de Oferta ──
    print(f"\n   {'─'*60}")
    print(f"   1. TIPO DE OFERTA")
    print(f"   {'─'*60}")
    for val, count in df["Tipo_Oferta"].value_counts().items():
        pct = count / len(df) * 100
        print(f"      {val:20s}  {count:>8,}  ({pct:.1f}%)")

    # ── 2. Tipo de Ativo ──
    print(f"\n   {'─'*60}")
    print(f"   2. TIPO DE ATIVO (top 10)")
    print(f"   {'─'*60}")
    for val, count in df["Tipo_Ativo"].value_counts().head(10).items():
        pct = count / len(df) * 100
        print(f"      {val:55s}  {count:>7,}  ({pct:.1f}%)")

    # ── 3. Rito da Oferta ──
    print(f"\n   {'─'*60}")
    print(f"   3. RITO DA OFERTA")
    print(f"   {'─'*60}")
    for val, count in df["Rito_Oferta"].value_counts().items():
        pct = count / len(df) * 100
        print(f"      {val:50s}  {count:>7,}  ({pct:.1f}%)")

    # ── 4. Instituições Líderes ──
    print(f"\n   {'─'*60}")
    print(f"   4. TOP 10 INSTITUIÇÕES LÍDERES (coordenadoras)")
    print(f"   {'─'*60}")
    for inst, count in df["Nome_Lider"].value_counts().head(10).items():
        print(f"      {inst:65s}  {count:>6,}")

    # ── 5. Volume Financeiro ──
    print(f"\n   {'─'*60}")
    print(f"   5. VOLUME FINANCEIRO (Valor_Total)")
    print(f"   {'─'*60}")
    valor = pd.to_numeric(df["Valor_Total"], errors="coerce")
    print(f"      Total geral:     R$ {valor.sum():>18,.2f}")
    print(f"      Média por oferta: R$ {valor.mean():>18,.2f}")
    print(f"      Mediana:         R$ {valor.median():>18,.2f}")

    # ── 6. Ofertas por ano (recentes) ──
    print(f"\n   {'─'*60}")
    print(f"   6. OFERTAS POR ANO (últimos 10 anos)")
    print(f"   {'─'*60}")
    recent = df["Ano"].value_counts().sort_index().tail(10)
    for ano, count in recent.items():
        bar = "█" * int(count / 30)
        print(f"      {int(ano):4d}  {count:>6,}  {bar}")

    # ── 7. Colunas mais relevantes para o projeto ──
    print(f"\n   {'─'*60}")
    print(f"   7. COLUNAS MAIS RELEVANTES PARA O PROJETO")
    print(f"   {'─'*60}")
    relevant = [
        ("Identificação", ["Numero_Processo", "Numero_Registro_Oferta"]),
        ("Tipo", ["Tipo_Oferta", "Tipo_Ativo", "Rito_Oferta", "Modalidade_Oferta"]),
        ("Emissor", ["CNPJ_Emissor", "Nome_Emissor"]),
        ("Instituição", ["CNPJ_Lider", "Nome_Lider"]),
        ("Valores", ["Quantidade_Total", "Preco_Unitario", "Valor_Total"]),
        ("Datas", ["Data_Registro_Oferta", "Data_Inicio_Oferta", "Data_Encerramento_Oferta"]),
        ("Renda Fixa*", ["Especie_Ativo", "Classe_Ativo", "Juros", "Atualizacao_Monetaria"]),
        ("Investidores", ["Qtd_Pessoa_Fisica", "Qtd_Fundos_Investimento", "Qtd_Investidor_Estrangeiro"]),
    ]
    for category, cols in relevant:
        found = [c for c in cols if c in df.columns]
        non_nulls = [df[c].notna().sum() for c in found]
        parts = []
        for c, nn in zip(found, non_nulls):
            parts.append(f"{c} ({nn:,})")
        print(f"      {category:15s}  {', '.join(parts)}")
    print(f"\n      * Juros e Atualizacao_Monetaria têm poucos dados — taxas detalhadas")
    print(f"        estão nos prospectos (PDFs), não neste CSV.")


def analyze_oferta_resolucao_160(df: pd.DataFrame):
    """Análise detalhada do dataset oferta_resolucao_160.csv."""
    print(f"\n{'='*80}")
    print(f"📊 DATASET 2: oferta_resolucao_160.csv")
    print(f"{'='*80}")
    print(f"   Registros: {len(df):,}")
    print(f"   Colunas:   {len(df.columns)}")

    # Período
    df["Ano"] = pd.to_datetime(df["Data_Registro"], errors="coerce").dt.year
    ano_min = df["Ano"].dropna().min()
    ano_max = df["Ano"].dropna().max()
    print(f"   Período:   {int(ano_min)} – {int(ano_max)}")

    # ── 1. Valor Mobiliário ──
    print(f"\n   {'─'*60}")
    print(f"   1. VALOR MOBILIÁRIO (top 10)")
    print(f"   {'─'*60}")
    for val, count in df["Valor_Mobiliario"].value_counts().head(10).items():
        pct = count / len(df) * 100
        print(f"      {val:55s}  {count:>7,}  ({pct:.1f}%)")

    # ── 2. Tipo de Requerimento ──
    print(f"\n   {'─'*60}")
    print(f"   2. TIPO DE REQUERIMENTO")
    print(f"   {'─'*60}")
    for val, count in df["Tipo_requerimento"].value_counts().head(8).items():
        pct = count / len(df) * 100
        print(f"      {val:65s}  {count:>7,}  ({pct:.1f}%)")

    # ── 3. Público-Alvo ──
    print(f"\n   {'─'*60}")
    print(f"   3. PÚBLICO-ALVO")
    print(f"   {'─'*60}")
    for val, count in df["Publico_alvo"].value_counts().items():
        pct = count / len(df) * 100
        print(f"      {val:30s}  {count:>7,}  ({pct:.1f}%)")

    # ── 4. Regime de Distribuição ──
    print(f"\n   {'─'*60}")
    print(f"   4. REGIME DE DISTRIBUIÇÃO")
    print(f"   {'─'*60}")
    for val, count in df["Regime_distribuicao"].value_counts().items():
        pct = count / len(df) * 100
        print(f"      {val:45s}  {count:>7,}  ({pct:.1f}%)")

    # ── 5. Bookbuilding ──
    print(f"\n   {'─'*60}")
    print(f"   5. BOOKBUILDING")
    print(f"   {'─'*60}")
    for val, count in df["Bookbuilding"].value_counts().items():
        pct = count / len(df) * 100
        print(f"      {'Sim' if val == 'S' else 'Não':10s}  {count:>7,}  ({pct:.1f}%)")

    # ── 6. Status ──
    print(f"\n   {'─'*60}")
    print(f"   6. STATUS DA OFERTA")
    print(f"   {'─'*60}")
    for val, count in df["Status_Requerimento"].value_counts().items():
        pct = count / len(df) * 100
        print(f"      {val:35s}  {count:>7,}  ({pct:.1f}%)")

    # ── 7. Instituições Líderes ──
    print(f"\n   {'─'*60}")
    print(f"   7. TOP 10 INSTITUIÇÕES LÍDERES")
    print(f"   {'─'*60}")
    for inst, count in df["Nome_Lider"].value_counts().head(10).items():
        print(f"      {inst:65s}  {count:>6,}")

    # ── 8. Ofertas por ano ──
    print(f"\n   {'─'*60}")
    print(f"   8. OFERTAS POR ANO")
    print(f"   {'─'*60}")
    by_year = df["Ano"].value_counts().sort_index()
    for ano, count in by_year.items():
        bar = "█" * int(count / 50)
        print(f"      {int(ano):4d}  {count:>6,}  {bar}")

    # ── 9. Títulos sustentáveis / incentivados ──
    print(f"\n   {'─'*60}")
    print(f"   9. TÍTULOS ESPECIAIS")
    print(f"   {'─'*60}")
    for col, label in [
        ("Titulo_classificado_como_sustentavel", "Sustentável (ESG)"),
        ("Titulo_incentivado", "Incentivado"),
        ("Titulo_padronizado", "Padronizado"),
    ]:
        if col in df.columns:
            s_count = (df[col] == "S").sum()
            n_count = (df[col] == "N").sum()
            total = s_count + n_count
            if total > 0:
                print(f"      {label:25s}  Sim: {s_count:>6,} ({s_count/total*100:.1f}%)  |  Não: {n_count:>6,}")

    # ── 10. Colunas mais relevantes ──
    print(f"\n   {'─'*60}")
    print(f"   10. COLUNAS MAIS RELEVANTES PARA O PROJETO")
    print(f"   {'─'*60}")
    relevant = [
        ("Identificação", ["Numero_Requerimento", "Numero_Processo"]),
        ("Tipo", ["Valor_Mobiliario", "Tipo_Oferta", "Tipo_requerimento"]),
        ("Emissor", ["CNPJ_Emissor", "Nome_Emissor"]),
        ("Instituição", ["CNPJ_Lider", "Nome_Lider", "Grupo_Coordenador"]),
        ("Público", ["Publico_alvo", "Bookbuilding"]),
        ("Distribuição", ["Regime_distribuicao", "Mercado_negociacao"]),
        ("Valores", ["Qtde_Total_Registrada", "Valor_Total_Registrado"]),
        ("Datas", ["Data_requerimento", "Data_Registro", "Data_Encerramento"]),
        ("ESG/Incentivo", ["Titulo_classificado_como_sustentavel", "Titulo_incentivado"]),
        ("Garantias", ["Tipo_lastro", "Regime_fiduciario", "Descricao_garantias"]),
        ("Investidores", ["Num_Invest_Pessoa_Natural", "Num_Invest_Fundos_Investimento"]),
    ]
    for category, cols in relevant:
        found = [c for c in cols if c in df.columns]
        non_nulls = [df[c].notna().sum() for c in found]
        parts = []
        for c, nn in zip(found, non_nulls):
            parts.append(f"{c} ({nn:,})")
        print(f"      {category:15s}  {', '.join(parts)}")


def print_comparison(df1: pd.DataFrame, df2: pd.DataFrame):
    """Comparação entre os dois datasets."""
    print(f"\n{'='*80}")
    print(f"📋 COMPARAÇÃO ENTRE OS DATASETS")
    print(f"{'='*80}")

    print(f"\n   {'':30s}  {'oferta_distribuicao':>22s}  {'oferta_resolucao_160':>22s}")
    print(f"   {'─'*30}  {'─'*22}  {'─'*22}")
    print(f"   {'Registros':30s}  {len(df1):>22,}  {len(df2):>22,}")
    print(f"   {'Colunas':30s}  {len(df1.columns):>22}  {len(df2.columns):>22}")

    # Colunas em comum
    common = set(df1.columns) & set(df2.columns)
    print(f"   {'Colunas em comum':30s}  {len(common):>22}")

    # Sobreposição de emissores
    emissores1 = set(df1["Nome_Emissor"].dropna().unique())
    emissores2 = set(df2["Nome_Emissor"].dropna().unique())
    overlap = emissores1 & emissores2
    print(f"   {'Emissores em comum':30s}  {len(overlap):>22}")

    # Sobreposição de líderes
    lideres1 = set(df1["Nome_Lider"].dropna().unique())
    lideres2 = set(df2["Nome_Lider"].dropna().unique())
    overlap_lideres = lideres1 & lideres2
    print(f"   {'Líderes em comum':30s}  {len(overlap_lideres):>22}")


def print_project_relevance():
    """Resumo de relevância para o projeto."""
    print(f"\n{'='*80}")
    print(f"🎯 RELEVÂNCIA PARA O PROJETO — AGENTE DE ANÁLISE DE OFERTAS")
    print(f"{'='*80}")

    print(f"""
   ✅ O QUE ESTES DADOS PERMITEM:

   1. Catálogo completo de ofertas primárias no Brasil
      → Base oficial da CVM, atualizada diariamente
      → 48.943 registros históricos + 13.040 em rito automático (2023+)

   2. Comparação entre instituições financeiras
      → Nome_Lider / Grupo_Coordenador identificam quem coordena cada oferta
      → Top players: BTG Pactual, Itaú BBA, XP, Singulare, Bradesco, Santander

   3. Análise por tipo de ativo
      → Debêntures, CRI, CRA, Cotas de FII/FIDC, Ações, Notas Comerciais
      → Permite filtrar e comparar ofertas similares

   4. Volume e timing de ofertas
      → Valor_Total, Quantidade_Total, datas de registro/encerramento
      → Identificar picos de emissão, tendências temporais

   5. Perfil do investidor
      → Distribuição por tipo: PF, fundos, estrangeiros, seguradoras
      → Público-alvo: Profissional, Qualificado, Público Geral

   6. Regime e estrutura
      → Garantia Firme vs Melhores Esforços
      → Bookbuilding vs sem bookbuilding
      → Regime fiduciário, tipo de lastro

   ⚠️ LIMITAÇÕES IDENTIFICADAS:

   1. TAXAS DETALHADAS (IPCA+%, CDI+%, % prefixada)
      → NÃO estão neste CSV — estão nos prospectos (PDFs)
      → Necessário complementar com scraping das plataformas (XP, BTG, etc.)

   2. DADOS HISTÓRICOS vs ATUAIS
      → oferta_distribuicao: rico em histórico, mas dados recentes são escassos
        (após 2023, migrou para rito automático → oferta_resolucao_160)
      → oferta_resolucao_160: dados atuais (2023-2026), mas sem histórico longo

   3. ENCODING
      → CSV usa latin-1, não UTF-8 (acentos aparecem corrompidos se lido errado)

   📌 RECOMENDAÇÃO:
      Usar estes dados como BASE OFICIAL de validação + estrutura,
      e complementar com scraping das plataformas para obter taxas em tempo real.
""")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("🏛️  CVM — Ofertas Públicas de Distribuição")
    print(f"📁 Diretório de dados: {DATA_DIR.absolute()}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Download
    zf = download_zip(ZIP_URL)

    # Extrair e salvar
    results = {}
    for key, info in FILES.items():
        print(f"\n📂 Extraindo: {key}")
        print(f"   Descrição: {info['description']}")
        df = extract_csv(zf, info["csv_index"])

        csv_path = DATA_DIR / f"{key}.csv"
        df.to_csv(csv_path, index=False, sep=";", encoding="utf-8")
        print(f"   💾 Salvo: {csv_path}")
        results[key] = df

    # Análises
    analyze_oferta_distribuicao(results["oferta_distribuicao"])
    analyze_oferta_resolucao_160(results["oferta_resolucao_160"])
    print_comparison(results["oferta_distribuicao"], results["oferta_resolucao_160"])
    print_project_relevance()

    print(f"\n{'='*80}")
    print(f"✅ Concluído! Dados salvos em: {DATA_DIR.absolute()}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
