# Arquitetura — BTG FII Analyzer

Plataforma interna para monitoramento de ofertas primárias de FIIs. Coleta dados públicos, normaliza, armazena e expõe via API e agente de IA conversacional.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Banco de dados | PostgreSQL (Supabase) + pgvector |
| Backend API | FastAPI + uvicorn |
| Frontend | React 18 + TypeScript + Tailwind CSS |
| Agente de IA | LangGraph + ChatGroq (llama-3.3-70b) |
| Pipeline de coleta | Python + APScheduler |
| Data fetching | TanStack Query |
| Charts | Recharts |
| Embeddings | sentence-transformers / OpenAI |

---

## Estrutura de diretórios

```
case-BTG-IA/
├── src/
│   ├── api/                    # FastAPI — 30 endpoints
│   │   ├── main.py             # App, CORS, registro de routers
│   │   ├── deps.py             # Dependências injetáveis (DB, período)
│   │   ├── routers/            # dashboard, offers, alerts, agent...
│   │   ├── schemas/            # Pydantic response models
│   │   └── services/
│   │       └── insight.py      # Geração de AI insight diário
│   │
│   ├── agents/
│   │   └── fii_agent.py        # Agente ReAct com 5 tools + PostgresSaver
│   │
│   ├── db/
│   │   ├── connection.py       # get_conn() — psycopg3 context manager
│   │   ├── migrate.py          # Aplica migrations em ordem
│   │   └── migrations/
│   │       ├── 001_initial_schema.sql   # 14 tabelas base + pgvector
│   │       ├── 002_schema_updates.sql   # is_ipo, distribution_rite, gestor_id...
│   │       ├── 003_enrichment_tables.sql # dividend_payment, daily_snapshot++
│   │       └── 004_ai_jobs.sql          # daily_insight, report_job, agent_conversation
│   │
│   └── pipeline/
│       ├── run.py              # Orquestrador de collectors
│       ├── scheduler.py        # APScheduler — 06:30 diário
│       ├── embedder.py         # Gera vetores para busca semântica
│       ├── reconcile_tickers.py
│       └── collectors/
│           ├── base.py         # BaseCollector — audit trail automático
│           ├── cvm.py          # Ofertas primárias (CVM Dados Abertos)
│           ├── cvm_docs.py     # Informes mensais FII (CVM)
│           ├── b3.py           # FII listings (B3 JSON endpoint)
│           ├── b3_ifix.py      # IFIX via Yahoo Finance (^IFIX)
│           ├── fundamentus.py  # DY, P/VP, vacância, preço
│           ├── status_invest.py # Histórico de dividendos por ticker
│           ├── funds_explorer.py # Volume diário, NAV, retorno mensal
│           └── bcb.py          # Selic, CDI, IPCA, IGP-M + Focus
│
├── frontend/                   # React + Tailwind
│   ├── src/
│   │   ├── app/routes/         # 5 páginas: Dashboard, Cenário Geral, Alertas, Agent IA, Config
│   │   ├── components/         # Componentes organizados por domínio
│   │   ├── lib/                # api.ts, queryKeys.ts, constants.ts, formatters.ts
│   │   └── types/index.ts      # Todos os tipos TypeScript
│   ├── vite.config.ts          # Proxy /api → localhost:8000
│   └── tailwind.config.js      # darkMode: 'class'
│
├── data/
│   └── raw/YYYY-MM-DD/         # Snapshots brutos em Parquet (imutável)
│
├── docs/
│   ├── ARQUITETURA.md          # Este arquivo
│   └── AGENTS.md               # Documentação do agente de IA
│
├── pyproject.toml              # Dependências Python (PEP 517)
└── .env                        # Secrets (não versionado)
```

---

## Fluxo de dados

```
Fontes públicas → Collectors → PostgreSQL ← FastAPI ← React
                                    ↓
                               Embedder (pgvector)
                                    ↓
                            Agente LangGraph (SSE)
```

### Pipeline de coleta (06:30 diário)

Cada collector herda de `BaseCollector`, que registra `extraction_run` antes e depois, salva raw data em Parquet e expõe métricas de auditoria.

| Collector | Fonte | O que coleta |
|---|---|---|
| `CVMCollector` | dados.cvm.gov.br CSV/ZIP | Ofertas primárias, status, coordenadores |
| `CVMDocsCollector` | dados.cvm.gov.br CSV/ZIP | Informes mensais dos FIIs |
| `B3Collector` | sistemaswebb3-listados.b3.com.br JSON | Listagem de FIIs ativos |
| `IFIXCollector` | Yahoo Finance `^IFIX` | Histórico do índice IFIX |
| `FundamentusCollector` | fundamentus.com.br HTML | DY, P/VP, vacância, preço, PL |
| `StatusInvestCollector` | statusinvest.com.br JSON API | Histórico de pagamentos de dividendos |
| `FundsExplorerCollector` | fundsexplorer.com.br HTML | Volume diário, NAV por cota, retorno |
| `BCBCollector` | api.bcb.gov.br + olinda.bcb.gov.br | Selic, CDI, IPCA, IGP-M, Focus |

---

## Banco de dados

17 tabelas, 4 migrations aplicadas em sequência por `src/db/migrate.py`.

**Atribuição correta de fontes (importante para labels e tooltips):**

| Indicador | Fonte primária | Acesso |
|---|---|---|
| Selic meta | BCB/COPOM | BCB/SGS série 13521 |
| Selic efetiva | BCB | BCB/SGS série 11 |
| CDI | B3/CETIP | BCB/SGS série 12 (espelho) |
| IPCA | IBGE | BCB/SGS série 433 (espelho) |
| IGP-M | FGV | BCB/SGS série 189 (espelho) |
| IFIX | B3 | Yahoo Finance ^IFIX (a validar) |

**Campos críticos adicionados na migration 002:**
- `offer.is_ipo` — classificação explícita (IPO vs follow-on)
- `offer.offer_sequence` — 1 = IPO, 2+ = follow-on
- `offer.distribution_rite` — rito_ordinario | rito_automatico | esforcos_restritos
- `vehicle.gestor_id` / `vehicle.administrador_id` — FKs para `participant`
- `vehicle.fund_type` — tijolo | papel | fof | desenvolvimento | hibrido | outros

**Tabela `embedding`:** vetores VECTOR(768) ou VECTOR(1536) para pgvector. Índice IVFFlat criado após ≥ 100 registros via `python -m src.pipeline.embedder`.

---

## API FastAPI

Base: `/api` · Swagger UI: `GET /docs`

| Router | Prefix | Responsabilidade |
|---|---|---|
| `dashboard` | `/api/dashboard` | Insight diário, volume, ranking, pipeline health |
| `offers` | `/api/offers` | Listagem paginada, indicadores, documentos, comparação |
| `alerts` | `/api/alerts` | Alertas, mark-as-seen |
| `agent` | `/api/agent` | Conversas + streaming SSE |
| `reports` | `/api/reports` | Jobs assíncronos de PDF |
| `general_scenario` | `/api/general-scenario` | KPIs macro, players, gráficos |
| `settings` | `/api/settings` | Trigger de pipeline |

**Contratos padrão:**
- Período: `?period=1d|7d|15d|1m`
- Paginação: `?page=1&page_size=50` → `{items, page, page_size, total_count}`
- Jobs assíncronos: `POST → {job_id, status: "queued"}` → polling `GET /jobs/{id}` → download

---

## Agente de IA

**Arquivo:** `src/agents/fii_agent.py`

Padrão ReAct com 5 tools e memória persistente via PostgresSaver. O endpoint `/api/agent/messages` retorna Server-Sent Events — o frontend recebe tool calls e a resposta final em streaming.

Ver `docs/AGENTS.md` para documentação completa das tools e técnicas de prompting.

---

## Frontend

5 páginas em React Router v6. Estado de servidor via TanStack Query (staleTime 60s).

**Tema:** `darkMode: 'class'` no Tailwind. Classe `dark` aplicada no `<html>` antes do primeiro render para evitar flash.

**Tabela de ofertas:** paginação server-side (50 rows/página). Seleção de linhas com array de IDs para comparação e PDF.

**Agent IA:** `thread_id` persistido em `localStorage` + tabela `agent_conversation`. Sidebar carrega conversas anteriores do banco.

---

## Decisões arquiteturais

**pgvector em vez de ChromaDB** — coexiste no mesmo PostgreSQL. Elimina serviço separado, mantém ACID, permite JOINs entre embeddings e dados relacionais.

**Parquet para raw data** — cada execução de pipeline salva um snapshot imutável para reprocessamento e auditoria.

**SSE em vez de WebSocket** — streaming unidirecional para o agente. Mais simples, funciona com qualquer proxy HTTP.

**AI insight pré-gerado** — gerado pelo scheduler às 07:00, salvo no banco. Frontend lê texto estático. Zero chamadas LLM no carregamento da página.

**PDF assíncrono** — `BackgroundTasks` do FastAPI. Retorna `job_id` imediatamente, cliente faz polling a cada 2.5s.
