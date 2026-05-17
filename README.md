# BTG FII Analyzer

## Sobre o projeto

Agente de análise e contextualização de ofertas primárias de Fundos Imobiliários (FII). O sistema coleta automaticamente dados de múltiplas fontes (CVM, ANBIMA, B3, Funds Explorer, BTG, XP e outras), compara as ofertas em andamento entre si e contra benchmarks de mercado, e contextualiza as variações embasado em indicadores macroeconômicos e eventos recentes.

O projeto é desenvolvido como case para o Banco BTG Pactual e faz parte do escopo mais amplo de análise de ofertas primárias de renda variável, começando por FIIs.

---

## Pipeline

```
[1. Coleta]
  ├── CVM Dados Abertos       → ofertas primárias em andamento (CSV/API)
  ├── CVM SDI                 → prospectos e lâminas em PDF (scraping simples)
  ├── ANBIMA                  → benchmark IFIX e dados de emissões (Jina)
  ├── Funds Explorer          → DY histórico, P/VP, vacância, tipo FII (Playwright)
  ├── Status Invest           → dividendos históricos, P/VP (Playwright)
  ├── BCB SGS via python-bcb  → CDI, IPCA histórico e projetado (API direta)
  ├── BTG Digital / XP        → ofertas concorrentes ativas (Jina)
  └── InfoMoney / portais     → notícias para contextualização (Jina)

[2. Tratamento]
  ├── Normalização de tickers (padrão B3 com sufixo .SA)
  ├── Parsing de PDFs (prospectos/lâminas) com LLM
  └── Padronização de datas, percentuais e valores monetários

[3. Análise comparativa]
  ├── Rentabilidade: DY atual vs CDI e IPCA projetado
  ├── Tamanho: PL do fundo e volume da oferta vs mercado
  ├── Preço: P/VP vs média de FIIs similares (por segmento)
  └── Benchmark: posicionamento relativo ao IFIX/ANBIMA

[4. Contextualização]
  ├── Correlação DY com ciclo de juros (Selic/IPCA)
  └── Notícias recentes relevantes (real estate, tributação, política monetária)

[5. Output]
  ├── Dashboard Streamlit (tabelas ag-grid + gráficos Plotly)
  └── Relatório analítico gerado por LLM
```

---

## Hierarquia de análise

1. **Rentabilidade** — DY da oferta comparado ao CDI e IPCA projetado no mesmo período
2. **Tamanho** — PL do fundo e volume total da oferta vs. outros FIIs em oferta primária
3. **Preço relativo** — P/VP da oferta vs. mercado secundário e FIIs do mesmo segmento
4. **Benchmark** — posicionamento relativo ao índice IFIX e ao benchmark ANBIMA

---

## Cadeia de modelos (Groq)

| Etapa | Modelo | Motivo |
|---|---|---|
| Extração estruturada de páginas web | `llama-3.1-8b-instant` | Rápido e barato para tarefas mecânicas de extração com schema Pydantic |
| Parsing de prospectos/lâminas (PDF) | `qwen-3-32b` | Forte em documentos longos e extração de dados financeiros estruturados |
| Análise comparativa e scoring | `llama-3.3-70b-versatile` | Melhor raciocínio quantitativo |
| Contextualização macroeconômica | `openai/gpt-oss-120b` | Síntese qualitativa de alta complexidade |
| Geração do relatório final | `openai/gpt-oss-120b` | Qualidade narrativa para relatório analítico em português |

---

## Fontes de dados

| Fonte | O que fornece | Método | Status |
|---|---|---|---|
| CVM Dados Abertos | Ofertas primárias, histórico desde 1989 | API/CSV | ✅ Funcionando |
| CVM SDI (documentos) | Prospectos e lâminas em PDF | Scraping simples | ✅ Funcionando |
| BCB SGS via python-bcb | CDI, IPCA, Selic histórico e projetado | API direta | ✅ Funcionando |
| BCB Relatório Focus | CDI e IPCA esperados pelo mercado | Jina | ⚠️ Parcial |
| ANBIMA | Benchmark IFIX, dados de emissões | Jina + scraping | ⚠️ Parcial |
| B3 FII listagem | Tickers ativos, setor, gestora | Jina | ⚠️ Parcial |
| Funds Explorer | DY histórico, P/VP, vacância, segmento | Playwright | 🔄 Em teste |
| Status Invest | Dividendos históricos, P/VP | Playwright | 🔄 Em teste |
| BTG Digital (FIIs) | Oferta atual do BTG | Jina | 🔄 Em teste |
| XP (FIIs) | Ofertas concorrentes | Jina / Playwright | ⚠️ Parcial |
| InfoMoney (notícias FII) | Contextualização informacional | Jina | ✅ Funcionando |

---

## Stack

| Camada | Tecnologia |
|---|---|
| Orquestração / Agente | LangChain, LangGraph |
| LLM | ChatGroq (qwen-3-32b, llama-3.3-70b, llama-3.1-8b, gpt-oss-120b) |
| Coleta dinâmica | Playwright |
| Coleta via leitura web | r.jina.ai |
| Dados BCB | python-bcb |
| Vector Store | pgvector (PostgreSQL extension — Fase 2) |
| Interface | Streamlit + Plotly |
| Pipeline agendado | APScheduler |
| Banco de dados | PostgreSQL (Supabase) |
| Linguagem | Python 3.11+ |

---

## Estrutura do repositório

```
├── requirements.txt
├── src/
│   ├── db/
│   │   ├── connection.py                  # get_conn() — psycopg3 context manager
│   │   ├── migrate.py                     # Aplica migrações SQL
│   │   └── migrations/
│   │       └── 001_initial_schema.sql     # Schema completo (14 tabelas + pgvector)
│   └── pipeline/
│       ├── run.py                         # Orquestrador (manual ou scheduler)
│       ├── scheduler.py                   # APScheduler 06:30 diário
│       └── collectors/
│           ├── base.py                    # BaseCollector (audit trail automático)
│           ├── cvm.py                     # CVM Dados Abertos (FIIs + alertas)
│           ├── fundamentus.py             # Fundamentus (DY, P/VP, vacância)
│           └── bcb.py                     # BCB SGS + Focus (CDI, IPCA, Selic)
├── app/
│   ├── db.py                              # Queries compartilhadas
│   ├── Home.py                            # KPIs + últimas ofertas
│   └── pages/
│       ├── 1_Ofertas_Primárias.py         # Tabela com filtros + referência secundário
│       ├── 2_Comparativo_Players.py       # Ranking + timeline + alertas de concentração
│       ├── 3_Atividade_Institucional.py   # Metadados + treemap
│       ├── 4_Macro.py                     # CDI, IPCA, Selic + projeções Focus
│       └── 5_Alertas.py                   # Alertas do pipeline
├── data/
│   └── raw/YYYY-MM-DD/                    # Snapshots brutos em Parquet (imutável)
```

---

## Como iniciar

### 1. Configurar ambiente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install firefox
```

### 2. Variáveis de ambiente

Criar arquivo `.env`:

```env
GROQ_API_KEY=sua_chave_aqui
```

### 3. Rodar os scripts disponíveis

```bash
# Baixar e analisar dados de ofertas da CVM
python src/data_ingestion/download_cvm_ofertas.py

# Testar acessibilidade das fontes via Jina
python scraping-inicial.py

# Agente interativo com dados reais (requer GROQ_API_KEY)
python src/agents/agent.py
```

---

## Escopo futuro

Em fases posteriores, o sistema poderá ser expandido para:

- **Ações** — ofertas primárias (IPOs e follow-ons)
- **Renda fixa** — CRI, CRA, LCI, LCA, FIDC, Debêntures isentas e não isentas (com foco em comparação vs CDI pela isenção tributária)
