# Agente de IA — BTG FII Analyzer

O agente é a interface conversacional da aplicação. Ele responde perguntas sobre o mercado primário de FIIs consultando diretamente o banco de dados — sem inventar dados e sem fazer recomendação de investimento.

---

## Arquitetura

**Padrão:** ReAct (Reasoning + Acting) via LangGraph `create_react_agent`

O padrão ReAct funciona em ciclos: o LLM raciocina sobre a pergunta, decide qual ferramenta chamar, executa a ferramenta, observa o resultado, e repete até ter informação suficiente para responder. Isso permite que o agente decomponha perguntas complexas em múltiplos passos sem que o prompt precise listar todos os casos.

```
Usuário → [LLM decide tool] → [Tool executa SQL/pgvector] → [LLM sintetiza] → Resposta
                    ↑__________________________|
                        (repete se necessário)
```

**LLM:** `llama-3.3-70b-versatile` via Groq API (temperatura 0, max_tokens 2048)

**Memória:** `PostgresSaver` (LangGraph checkpoint) persiste o histórico de conversa no banco. Cada conversa tem um `thread_id` único que mapeia para a tabela `agent_conversation` e para os checkpoints do LangGraph.

**Streaming:** SSE (Server-Sent Events) via FastAPI `StreamingResponse`. O frontend recebe eventos separados para tool calls e mensagem final.

---

## System prompt

O system prompt usa **role prompting** — define quem o agente é, o que pode fazer e o que nunca pode fazer. Ele é passado como `SystemMessage` para garantir que o LLM trate as restrições como instruções de sistema, não como texto do usuário.

```python
_SYSTEM_PROMPT = SystemMessage(content=(
    "Você é assistente de análise do mercado primário de FII "
    "para o time de mesa do BTG Pactual. "
    "Exponha dados, comparações e evidências — "
    "NÃO faça recomendação de investimento. "
    "NÃO infira taxas ou condições financeiras ausentes nos dados. "
    "Quando termos financeiros não estiverem disponíveis responda: "
    "'Termos financeiros não disponíveis na fonte consultada.' "
    "Responda em português. Cite sempre a fonte e data de cada dado. "
    "DY e P/VP são do mercado secundário (Fundamentus), não da oferta primária. "
    "Para IPOs, DY histórico e P/VP são indisponíveis — o fundo não tem histórico realizado."
))
```

**Guardrails implementados:**
- Nunca faz recomendação de investimento (instrução explícita no system prompt)
- Nunca infere dados ausentes (instrução + ferramenta retorna string padrão quando dado não existe)
- Sempre cita fonte e data (instrução no system prompt)
- Para IPOs, diferencia o que não existe do que não está disponível

---

## Ferramentas (Tools)

Cada tool é uma função Python decorada com `@tool`. O LLM lê o docstring para decidir quando e como chamar cada uma. Por isso os docstrings são descritivos e incluem os parâmetros com exemplos.

### `buscar_ofertas`
Busca SQL estruturada em ofertas primárias.

- **Quando usar:** perguntas sobre ofertas específicas, filtros por coordenador, segmento, status ou período
- **Fonte:** tabelas `offer`, `vehicle`, `participant`, `daily_snapshot`
- **Parâmetros:** `status`, `coordenador`, `segmento`, `ticker`, `dias`, `limite`
- **Inclui:** `is_ipo` e `distribution_rite` para contextualizar IPO vs follow-on

### `buscar_semantico`
Busca vetorial por similaridade (pgvector + cosine distance).

- **Quando usar:** perguntas contextuais em linguagem natural ("fundos com logística e vacância baixa")
- **Fonte:** tabela `embedding` (vetores gerados pelo embedder)
- **Tipos:** `offer_profile` (perfil de oferta) ou `fund_monthly` (informe mensal)
- **Requer:** embeddings populados via `python -m src.pipeline.embedder`

### `contexto_macro`
Retorna os indicadores macroeconômicos mais recentes.

- **Quando usar:** perguntas sobre Selic, CDI, IPCA, IFIX ou contexto macro do mercado
- **Fonte:** tabela `market_metric`
- **Inclui:** atribuição correta de fonte (BCB para Selic, IBGE via BCB para IPCA, B3/CETIP via BCB para CDI)

### `perfil_fundo`
Retorna perfil completo de um FII por ticker.

- **Quando usar:** perguntas sobre um fundo específico ("como está o HGLG11?")
- **Fonte:** `daily_snapshot` (indicadores) + `offer` (histórico de ofertas primárias)
- **Diferencia:** follow-on (mostra indicadores) vs IPO (indica indisponibilidade com razão)

### `ranking_players`
Ranking de coordenadores por volume e número de ofertas.

- **Quando usar:** perguntas sobre quem domina o mercado, market share, concentração
- **Fonte:** JOIN entre `offer`, `participant_role`, `participant`

---

## Técnicas de prompting aplicadas

| Técnica | Onde é usada |
|---|---|
| **Role prompting** | System prompt define persona + restrições |
| **Guardrails explícitos** | Proibições diretas no system prompt ("NÃO faça recomendação") |
| **ReAct** | LangGraph `create_react_agent` implementa o ciclo reason-act-observe |
| **RAG** | `buscar_semantico` recupera contexto do banco vetorial antes de responder |
| **Tool descriptions** | Docstrings estruturados orientam o LLM na seleção de ferramentas |
| **Temperatura 0** | Respostas determinísticas para dados financeiros |

---

## Padrão de streaming (SSE)

O endpoint `POST /api/agent/messages` retorna um stream de eventos:

```
data: {"type": "tool", "name": "buscar_ofertas", "content": "..."}

data: {"type": "message", "content": "Foram encontradas 3 ofertas..."}

data: [DONE]
```

O frontend consome via `fetch` + `ReadableStream`, exibindo tool calls em componentes colapsáveis e a mensagem final no balão do agente.

---

## Singleton e conexão

`build_agent()` é um singleton — cria o agente e a conexão com o banco uma única vez e reutiliza em todas as requisições. A conexão `PostgresSaver` usa `autocommit=True` e `prepare_threshold=0` (parâmetros internos do LangGraph).

```python
_agent = None

def build_agent():
    global _agent
    if _agent is None:
        checkpointer = _setup_checkpointer()
        _agent = create_react_agent(_model, _TOOLS,
                                     checkpointer=checkpointer,
                                     prompt=_SYSTEM_PROMPT)
    return _agent
```

---

## Como adicionar uma nova ferramenta

1. Defina a função com `@tool` e docstring descritivo em `src/agents/fii_agent.py`
2. Adicione à lista `_TOOLS`
3. O LangGraph registra automaticamente no agente na próxima chamada de `build_agent()`

```python
@tool
def minha_ferramenta(parametro: str) -> str:
    """
    Descrição do que a ferramenta faz e quando o agente deve usá-la.

    Args:
        parametro: descrição do parâmetro com exemplo
    """
    # lógica aqui
    return resultado
```

---

## Arquivo principal

`src/agents/fii_agent.py`
