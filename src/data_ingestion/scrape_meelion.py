#!/usr/bin/env python3
"""
Scraper de renda fixa - Meelion (comparar investimentos).

Demonstra uso de Playwright para extração de dados de página com bot-protection.
Extrai os investimentos visíveis sem autenticação (plano free, página 1).

Uso:
    python src/data_ingestion/scrape_meelion.py

Evoluções futuras:
    - Login: passar perfil do Firefox do usuário via launch_persistent_context()
      ou injetar cookies via add_cookies(). Com login desbloqueiam-se as páginas
      2 em diante (data-auth-gate="pagination") e dados de rentabilidade líquida.
    - Paginação completa: iterar ?page=1..N até não encontrar mais cards.
      O site exibe 4196 investimentos distribuídos em ~N páginas (requer login).
    - Filtros: a URL aceita parâmetros como ?investment_type=CDB&financial_index=IPCA
      permitindo extrair subconjuntos específicos sem navegar por todos os cards.
    - PRO: valores líquidos (após IR) e rentabilidade comparativa ficam atrás do
      plano pago; com conta PRO o scraper consegue esses campos extras.
    - Paralelismo: para crawlear muitas páginas, usar asyncio + async playwright.
"""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://www.meelion.com/renda-fixa/comparar-investimentos/"
OUTPUT_PATH = Path("data/meelion/investimentos_page1.json")


def parse_cards(page) -> list[dict]:
    """Extrai os cards de investimento visíveis na página."""
    cards = page.query_selector_all(".investment-card.h-100")
    results = []

    for card in cards:
        # Tipo (CDB, CRI, CRA, LCA, Debênture, ...)
        badge = card.query_selector(".badge")
        tipo = badge.inner_text().strip() if badge else None

        # Cobertura FGC
        fgc_el = card.query_selector(".ci-card-fgc-pill")
        fgc_texto = fgc_el.inner_text().strip() if fgc_el else None
        com_fgc = fgc_texto is not None and "sem fgc" not in fgc_texto.lower()

        # Nome e link de detalhes
        link_el = card.query_selector(".title-text a")
        nome = link_el.inner_text().strip() if link_el else None
        href = link_el.get_attribute("href") if link_el else None
        url_detalhe = f"https://www.meelion.com{href}" if href else None

        # Campos label/value (Oferecido por, Disponível, Vencimento)
        info = {}
        for item in card.query_selector_all(".info-item"):
            label_el = item.query_selector(".label")
            value_el = item.query_selector(".value")
            if label_el and value_el:
                label = label_el.inner_text().strip().rstrip(":")
                value = value_el.inner_text().strip()
                info[label] = value

        results.append({
            "nome": nome,
            "tipo": tipo,
            "com_fgc": com_fgc,
            "emissor": info.get("Oferecido por"),
            "distribuidor": info.get("Disponível"),
            "vencimento": info.get("Vencimento"),
            "url_detalhe": url_detalhe,
        })

    return results


def main():
    print(f"Abrindo {URL} ...")

    with sync_playwright() as p:
        # headless=False para ver o navegador abrindo (útil em demo/aula)
        browser = p.firefox.launch(headless=False)
        page = browser.new_page()

        page.goto(URL, wait_until="networkidle", timeout=30_000)
        print(f"Título: {page.title()}")

        investimentos = parse_cards(page)
        browser.close()

    print(f"\n{len(investimentos)} investimentos extraídos (plano free, página 1):\n")
    for i, inv in enumerate(investimentos, 1):
        print(f"  {i:2d}. {inv['nome']}")
        print(f"      Tipo: {inv['tipo']} | FGC: {'Sim' if inv['com_fgc'] else 'Não'}")
        print(f"      Emissor: {inv['emissor']} | Distribuidor: {inv['distribuidor']}")
        print(f"      Vencimento: {inv['vencimento']}")
        print()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(investimentos, f, indent=2, ensure_ascii=False)
    print(f"JSON salvo em: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
