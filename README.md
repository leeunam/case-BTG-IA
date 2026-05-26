# BTG FII Analyzer

Monitoramento automatizado de ofertas primárias de Fundos Imobiliários — desenvolvido como case técnico para o Banco BTG Pactual em parceria com a Liga de Inteligência Artificial do Inteli.

---

## O projeto

Toda vez que um novo fundo imobiliário abre capital ou lança uma nova emissão, essa oferta precisa ser registrada na CVM. Acompanhar esse fluxo manualmente, cruzando dados de regulador, bolsa e banco central, é lento e sujeito a erro.

Este sistema faz isso automaticamente. Todo dia, coleta as ofertas da CVM, enriquece com dados de mercado e contextualiza com indicadores econômicos. A equipe de mesa acessa tudo em um dashboard e pode fazer perguntas diretamente a um agente de IA.

Sem recomendação de investimento. Sem dados proprietários. Tudo de fontes públicas e oficiais.

---

## O que entrega

- Tabela de ofertas em andamento com status, coordenador, volume e gestor
- Separação clara entre IPO (fundo novo, sem histórico) e follow-on (fundo existente)
- Indicadores de mercado — DY, P/VP, vacância, volume diário — apenas quando existem, com fonte explícita
- Contexto macroeconômico — Selic, CDI, IPCA, IFIX — atualizado diariamente
- Alertas automáticos para novas ofertas, mudanças de status e falhas de coleta
- Histórico completo de dividendos por fundo (via Status Invest)
- Agente de IA conversacional com acesso a todos os dados da aplicação

---

## Stack

| Camada | Tecnologia |
|---|---|
| Banco de dados | PostgreSQL (Supabase) + pgvector |
| API backend | FastAPI + uvicorn |
| Frontend | React 18 + TypeScript + Tailwind CSS |
| Agente de IA | LangGraph + ChatGroq (llama-3.3-70b) |
| Pipeline diário | Python + APScheduler |
| Coleta de dados | httpx, python-bcb, BeautifulSoup, yfinance |
| Raw data | Parquet |

---

## Estrutura

```
case-BTG-IA/
├── src/
│   ├── api/               # FastAPI — 30 endpoints em 7 routers
│   ├── agents/            # Agente ReAct com 5 tools
│   ├── db/                # Migrations (001–004) e conexão psycopg3
│   └── pipeline/          # 8 collectors + embedder + scheduler
│
├── frontend/              # React + Tailwind (5 páginas)
├── data/raw/YYYY-MM-DD/   # Snapshots brutos em Parquet
├── docs/                  # ARQUITETURA.md e AGENTS.md
├── pyproject.toml
└── .env
```

---

## Como rodar

### Pré-requisitos

- Python 3.11+
- Node.js 18+
- PostgreSQL com extensão `pgvector` (ou conta no Supabase)
- Chave de API do Groq (gratuita em [console.groq.com](https://console.groq.com))

---

### 1. Clone e configure o ambiente Python

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

### 2. Configure as variáveis de ambiente

Crie `.env` na raiz do projeto:

```env
GROQ_API_KEY=gsk_...            # Obrigatório — LLM (Groq)
DATABASE_URL=postgresql://...   # Obrigatório — PostgreSQL/Supabase
OPENAI_API_KEY=sk-...           # Opcional — embeddings de melhor qualidade
```

### 3. Crie o banco de dados

```bash
python src/db/migrate.py
```

Aplica as 4 migrations em sequência. Seguro para rodar mais de uma vez.

### 4. Rode a coleta inicial de dados

```bash
python -m src.pipeline.run
```

Baixa dados de todas as 8 fontes. O dashboard por padrão exibe o último mês — os dados históricos ficam no banco para análise e busca semântica. A primeira execução pode levar alguns minutos dependendo da velocidade da conexão.

Para rodar só uma fonte específica:

```bash
python -m src.pipeline.run bcb_sgs          # só BCB (~30s)
python -m src.pipeline.run cvm_dados_abertos # só CVM (~2 min)
```

### 5. Inicie a API (terminal 1)

```bash
uvicorn src.api.main:app --reload --port 8000
```

- API: `http://localhost:8000`
- Documentação interativa: `http://localhost:8000/docs`

### 6. Inicie o frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

- App: `http://localhost:5173`
- O Vite faz proxy automático de `/api` para `localhost:8000` — sem CORS na dev.

### 7. (Opcional) Gere o AI insight do dia

```bash
curl -X POST http://localhost:8000/api/dashboard/daily-insight/generate
```

O insight é gerado em background e salvo no banco. Recarregue o dashboard depois.

### 8. (Opcional) Gere embeddings para busca semântica

```bash
python -m src.pipeline.embedder --type=offers --limit=500
```

Necessário para a ferramenta `buscar_semantico` do agente funcionar.

### 9. Agendamento automático (opcional)

```bash
python -m src.pipeline.scheduler
```

Mantém a coleta rodando toda manhã às 06:30 (horário de Brasília). Encerra com `Ctrl+C`.

---

## Documentação técnica

- [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) — estrutura completa do projeto, decisões de design, schema do banco
- [`docs/AGENTS.md`](docs/AGENTS.md) — funcionamento do agente de IA, tools, prompting

---

## Roadmap

- [ ] Parsing de PDFs de prospectos e lâminas via LLM — para capturar termos financeiros que não estão nos CSVs (cap rate, LTV, duration)
- [ ] Análise IA do player top na tela Cenário Geral — pré-gerada no pipeline, similar ao insight diário
- [ ] Expansão para outros ativos — ações (IPOs/follow-ons), CRI, CRA, FIDC, debêntures

---

## Autor

**Leunam Sousa de Jesus** — case técnico para o Banco BTG Pactual, Liga AI — 2026.

---

## Licença

MIT License — Copyright (c) 2026 Leunam Sousa de Jesus

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
