#!/usr/bin/env python3
"""
Extrai ofertas de renda fixa de artigos financeiros usando r.jina.ai + LangChain + LLM.

Demonstra:
  1. Fetch de página web via r.jina.ai (converte HTML em markdown limpo)
  2. Extração estruturada com Pydantic + with_structured_output do LangChain
  3. Modelo ChatGroq (free tier)

Uso:
    python src/data_ingestion/extract_renda_fixa.py
"""

import os
import json
import requests
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from dotenv import load_dotenv

# Carrega variáveis do .env na raiz do projeto
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ─── Configuração ─────────────────────────────────────────────────────────────

URLS = [
    "https://www.moneytimes.com.br/ipca1098-confira-os-titulos-de-renda-fixa-recomendados-pela-xp-para-maio-jcav/",
]


# ─── Schema de Saída (Pydantic) ──────────────────────────────────────────────

class TituloRendaFixa(BaseModel):
    """Um título de renda fixa extraído de uma carteira recomendada."""

    ativo_emissor: str = Field(description="Nome do ativo ou emissor (ex: CDB BMG, NTN-B, CRA Marfrig)")
    vencimento: str = Field(description="Data de vencimento no formato DD/MM/AAAA")
    indexador: str = Field(description="Tipo de indexador: Prefixado, % CDI, % Selic, IPCA+, etc.")
    duration_anos: float | None = Field(default=None, description="Duration em anos, se disponível")
    ticker: str | None = Field(default=None, description="Ticker/código do ativo na bolsa, se disponível")
    taxa_bruta: str = Field(description="Taxa bruta indicativa (ex: IPCA + 8,41%, 14,35%, 91% CDI)")
    isento_ir: bool = Field(description="Se o título é isento de Imposto de Renda")
    taxa_gross_up: str | None = Field(default=None, description="Taxa equivalente gross-up (para isentos), se disponível")
    observacao: str | None = Field(default=None, description="Observação adicional sobre o título, se houver no texto")


class CarteiraRecomendada(BaseModel):
    """Carteira de renda fixa recomendada por uma instituição financeira."""

    instituicao: str = Field(description="Nome da instituição que fez a recomendação (ex: XP, BTG, Itaú)")
    data_referencia: str = Field(description="Mês/ano de referência da recomendação (ex: Maio 2026)")
    fonte_url: str = Field(description="URL da fonte original")
    resumo_estrategia: str = Field(description="Breve resumo da estratégia/macro descrita no artigo")
    titulos: list[TituloRendaFixa] = Field(description="Lista de títulos recomendados na carteira")


# ─── Fetch via r.jina.ai ─────────────────────────────────────────────────────

def fetch_page(url: str) -> str:
    """Busca o conteúdo de uma página via r.jina.ai e retorna o markdown limpo."""
    jina_url = f"https://r.jina.ai/{url}"
    resp = requests.get(jina_url, headers={"Accept": "text/plain"}, timeout=30)
    resp.raise_for_status()
    return resp.text


# ─── Extração com LangChain + LLM ────────────────────────────────────────────

def extract_from_text(content: str, source_url: str) -> CarteiraRecomendada:
    """Usa LangChain + ChatGroq para extrair títulos em formato estruturado."""

    model = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
    )

    # Aplica structured output com o schema Pydantic
    structured_model = model.with_structured_output(CarteiraRecomendada)

    prompt = f"""Você é um analista financeiro especializado em extrair informações de títulos de renda fixa de artigos e carteiras recomendadas.

Extraia TODOS os títulos de renda fixa mencionados no texto abaixo e retorne no formato estruturado solicitado.

Regras:
- Extraia cada título da tabela ou lista mencionada
- Para taxa_bruta, use exatamente o formato que aparece (ex: "IPCA + 8,41%", "14,35%", "91% CDI", "Selic + 0,0%")
- isento_ir deve ser True se o artigo mencionar isenção de IR para aquele título
- taxa_gross_up é a taxa equivalente para títulos isentos (quando mencionada)
- Preencha instituicao com o nome da casa que recomendou (ex: "XP Investimentos")
- data_referencia é o mês/ano da recomendação mencionado no artigo
- resumo_estrategia é um breve reselho (2-3 frases) da estratégia macro descrita
- Se algum campo não estiver disponível, use null

Texto do artigo:
---
{content}
---

URL da fonte: {source_url}
"""

    result = structured_model.invoke(prompt)
    return result


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not os.environ.get("GROQ_API_KEY"):
        print("❌ Defina a variável de ambiente GROQ_API_KEY")
        print("   export GROQ_API_KEY=sua_chave_aqui")
        return

    for url in URLS:
        print(f"📄 Buscando página: {url}")
        content = fetch_page(url)
        print(f"   → {len(content):,} caracteres obtidos")

        print(f"\n🤖 Extraindo títulos com LangChain + ChatGroq...")
        carteira = extract_from_text(content, url)

        # Imprime resultado formatado
        print(f"\n{'='*80}")
        print(f"📋 CARTEIRA RECOMENDADA — {carteira.instituicao}")
        print(f"   Referência: {carteira.data_referencia}")
        print(f"   Fonte: {carteira.fonte_url}")
        print(f"\n   Estratégia: {carteira.resumo_estrategia}")
        print(f"\n   {len(carteira.titulos)} títulos encontrados:")
        print(f"{'='*80}")

        for i, t in enumerate(carteira.titulos, 1):
            ir_badge = "ISENTO IR" if t.isento_ir else ""
            print(f"\n  {i:2d}. {t.ativo_emissor} {ir_badge}")
            print(f"      Vencimento: {t.vencimento}")
            print(f"      Indexador:  {t.indexador}")
            print(f"      Taxa bruta: {t.taxa_bruta}")
            if t.taxa_gross_up:
                print(f"      Gross-up:   {t.taxa_gross_up}")
            if t.duration_anos:
                print(f"      Duration:   {t.duration_anos} anos")
            if t.ticker:
                print(f"      Ticker:     {t.ticker}")

        # Salva JSON
        output = carteira.model_dump(mode="json")
        output_path = "data/cvm/carteira_xp_maio2026.json"
        os.makedirs("data/cvm", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n💾 JSON salvo em: {output_path}")
        print(f"\n📄 JSON preview:")
        print(json.dumps(output, indent=2, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()
