# AGENTS.md — LigaAI / Agente de Análise de Ofertas Primárias

## 1. Contexto do Projeto

Este projeto desenvolve um **agente inteligente para análise de ofertas primárias do mercado financeiro brasileiro**, utilizando o ecossistema LangChain como framework principal de orquestração.

### 1.1. Domínio e Objetivo
- **Domínio:** Ofertas primárias de renda fixa, renda variável e fundos imobiliários (FOFIs/FIIs) disponibilizadas por instituições como BTG Pactual, XP Inc. e outras corretoras.
- **Problema:** A análise comparativa entre ofertas ainda depende de processos manuais e fragmentados. Diferenças de taxas exigem acompanhamento constante de indicadores macroeconômicos, eventos políticos e notícias.
- **Solução:** Um agente inteligente que coleta, consolida e analisa ofertas primárias, identificando padrões, discrepâncias e oportunidades relativas entre taxas ofertadas, correlacionando variações com fatores macroeconômicos.

### 1.2. Arquitetura Planejada
1. **Coleta:** Web scraping de APIs públicas e sites institucionais (CVM, B3, etc.)
2. **Tratamento:** Limpeza, normalização e padronização de dados entre diferentes fontes
3. **Inteligência Analítica (LangChain):**
   - Orquestração de fluxos de raciocínio
   - Integração com LLMs (Groq — modelos gratuitos via free tier)
   - Definição de tools para cálculos e consultas externas
   - Memória para contexto histórico e recuperação de emissões anteriores
4. **Base Vetorial:** ChromaDB para armazenar embeddings de emissões anteriores e permitir recuperação semântica de comparáveis
5. **Interface:** Streamlit para dashboard interativo com filtros por instituição, tipo de ativo, indexador e período

### 1.3. Stack Tecnológica
- **Orquestração:** LangChain, LangGraph
- **LLM:** ChatGroq (modelos da Meta, Mistral, etc. via Groq API)
- **Vector Store:** ChromaDB
- **Interface:** Streamlit
- **Linguagem:** Python 3.12+
- **Ambiente:** venv local

---

## 2. Regra Fundamental: Documentação Oficial LangChain via MCP

> **TODAS as implementações, correções de código e respostas a perguntas técnicas sobre LangChain/LangGraph DEVEM ser baseadas na documentação oficial da LangChain, acessada obrigatoriamente via MCP Server `docs-langchain`.**
>
> **A BUSCA NA DOCUMENTAÇÃO DEVE SER FEITA EXCLUSIVAMENTE EM INGLÊS.** A documentação oficial do LangChain é inteiramente em inglês e a busca semântica do MCP retorna resultados significativamente piores quando consultada em português. Traduzir o conceito para inglês antes de buscar é obrigatório.

### 2.1. Por que?
- O LangChain é um framework em evolução constante. Respostas baseadas apenas em conhecimento prévio podem estar desatualizadas.
- O projeto utiliza padrões modernos do LangChain (agents com `create_agent`, checkpointers, LangGraph stores, middleware, etc.).
- Garantir que o código produzido siga as APIs e melhores práticas atuais documentadas oficialmente.
- **A documentação oficial é 100% em inglês.** Termos técnicos, nomes de classes e APIs só existem nesse idioma na base de documentação indexada pelo MCP.
- **Busca semântica em português retorna resultados irrelevantes ou vazios.** O motor de busca do MCP foi otimizado para o vocabulário técnico original em inglês.

### 2.2. Quando consultar?
| Situação | Ação obrigatória |
|----------|-----------------|
| Implementar um novo recurso do LangChain (ex: memory, tools, chains) | Consultar documentação antes de escrever código |
| Responder dúvidas do usuário sobre como funciona X no LangChain | Consultar documentação antes de responder |
| Corrigir bugs ou refatorar código LangChain existente | Consultar documentação para verificar API atual |
| Adicionar dependências relacionadas ao LangChain | Consultar documentação para verificar pacotes recomendados |

---

## 3. Como Usar a Documentação Oficial (MCP `docs-langchain`)

O ambiente possui duas ferramentas MCP para acessar a documentação oficial da LangChain:

### 3.1. Busca Semântica (`docs-langchain_search_docs_by_lang_chain`)
Use para encontrar páginas relevantes sobre um conceito, feature ou API.

**Uso:**
```json
{
  "query": "how does memory work in langchain"
}
```

> ⚠️ **ATENÇÃO:** A query DEVE ser em inglês, mesmo que a pergunta original do usuário seja em português. Se o usuário perguntar "como funciona a memória no langchain?", você deve buscar por `"how does memory work in langchain"` ou `"langchain short-term memory"`.

**Quando usar:**
- Quando não sabe qual página da documentação contém a informação
- Para descobrir o nome correto de uma feature ou API
- Para encontrar guias e tutoriais sobre um tópico

### 3.2. Leitura de Páginas (`docs-langchain_query_docs_filesystem_docs_by_lang_chain`)
Use para ler o conteúdo completo de uma página específica da documentação.

**Uso:**
```bash
# Ler página completa
cat /caminho/da/pagina.mdx

# Ler primeiras N linhas
head -80 /caminho/da/pagina.mdx

# Buscar padrão específico dentro de uma página
rg -C 3 "palavra-chave" /caminho/da/pagina.mdx

# Listar estrutura de diretórios
tree / -L 2
```

**Como descobrir o caminho da página:**
1. Use a ferramenta de busca primeiro para encontrar o `page` (ex: `oss/python/concepts/memory`)
2. O caminho do arquivo será: `/oss/python/concepts/memory.mdx`
3. Use `cat` ou `head` para ler o conteúdo

**Exemplo de workflow completo:**
```
1. Buscar: {"query": "short-term memory langgraph"}
   → Retorna: page: oss/python/langchain/short-term-memory

2. Ler: cat /oss/python/langchain/short-term-memory.mdx
   → Retorna conteúdo completo da documentação oficial

3. Implementar código baseado no que foi lido
```

### 3.3. Regras de Busca (OBRIGATÓRIAS)
- **Sempre busque em inglês.** Nunca use português na query de busca do MCP.
- Use termos técnicos originais em inglês: `checkpoint`, `checkpointer`, `tool calling`, `vector store`, `embeddings`, `summarization`, `middleware`
- Combine conceitos: `langgraph agent memory`, `create_agent tools`, `chroma vectorstore`, `langchain tool runtime`
- Para APIs específicas, busque pelo nome exato da classe/função em inglês: `PostgresSaver`, `InMemoryStore`, `ChatGroq`, `SummarizationMiddleware`
- Se a pergunta do usuário for em português, traduza o conceito para inglês antes de buscar.

---

## 4. Padrões de Código e Convenções

### 4.1. Estrutura de Arquivos
```
ligaai/
├── AGENTS.md              # Este arquivo
├── opencode.json          # Configuração MCP
├── requirements.txt       # Dependências Python
├── .env                   # Variáveis de ambiente (nunca commitar)
├── src/                   # Código-fonte principal
│   ├── agents/            # Definições de agentes LangChain/LangGraph
│   ├── tools/             # Ferramentas customizadas (scraping, cálculos)
│   ├── chains/            # Chains de processamento
│   ├── memory/            # Configurações de memória
│   ├── vectorstore/       # Integração com ChromaDB
│   ├── scrapers/          # Módulos de web scraping
│   └── streamlit_app.py   # Aplicação Streamlit
├── context/               # Documentação e contexto do projeto
└── data/                  # Dados brutos e processados
```

### 4.2. Dependências Principais
```
langchain-groq      # Integração com LLMs da Groq
langchain-core      # Core do LangChain
langgraph           # Orquestração de grafos (agents com estado)
langchain-chroma    # Vector store ChromaDB
chromadb            # Cliente ChromaDB
streamlit           # Interface web
python-dotenv       # Gerenciamento de variáveis de ambiente
requests / httpx    # Requisições HTTP para scraping
beautifulsoup4      # Parsing HTML
pandas              # Manipulação de dados
tabulate            # Formatação de tabelas
```

### 4.3. Variáveis de Ambiente
Criar arquivo `.env` na raiz:
```bash
GROQ_API_KEY=sua_chave_aqui
```

---

## 5. Checklist antes de produzir código/respostas

- [ ] A pergunta/implementação envolve LangChain/LangGraph?
- [ ] Se SIM: consultar documentação oficial via MCP **ANTES** de responder/escrever código
- [ ] **A busca foi feita EM INGLÊS?** (Nunca em português — traduzir o conceito antes de buscar)
- [ ] Verificar se a API utilizada está atualizada (ex: `create_agent` vs APIs antigas)
- [ ] Garantir que exemplos de código seguem a documentação oficial
- [ ] Nunca inventar APIs ou parâmetros que não existem na documentação
- [ ] Se houver dúvida sobre uma API, buscar na documentação antes de assumir

---

## 6. Links e Referências

- **Documentação LangChain (via MCP):** Disponível através das ferramentas `docs-langchain_search_docs_by_lang_chain` e `docs-langchain_query_docs_filesystem_docs_by_lang_chain`
- **Documentação LangChain (web):** https://python.langchain.com/
- **Documentação LangGraph:** https://langchain-ai.github.io/langgraph/
- **Groq Console:** https://console.groq.com/
- **ChromaDB:** https://docs.trychroma.com/
- **Streamlit:** https://docs.streamlit.io/
