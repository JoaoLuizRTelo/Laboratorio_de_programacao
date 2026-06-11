# Documentação Técnica — RAG Workspace

> Projeto de **Retrieval-Augmented Generation (RAG)** com backend Flask, base vetorial ChromaDB e geração de respostas via OpenAI.

---

## Sumário

1. [Visão Geral](#1-visão-geral)
2. [Arquitetura](#2-arquitetura)
3. [Estrutura de Arquivos](#3-estrutura-de-arquivos)
4. [Dependências e Configuração](#4-dependências-e-configuração)
5. [Módulo `rag_core.py`](#5-módulo-rag_corepy)
   - [Classe `Chunker`](#51-classe-chunker)
   - [Classe `RAGBasico`](#52-classe-ragbasico)
6. [Módulo `app.py` — API REST](#6-módulo-apppy--api-rest)
7. [Frontend (`rag-workspace.html`)](#7-frontend-rag-workspacehtmll)
8. [Documento de Exemplo (`politicas_internas.txt`)](#8-documento-de-exemplo-politicas_internastxt)
9. [Fluxo Completo de Dados](#9-fluxo-completo-de-dados)
10. [Estratégias de Chunking — Comparativo](#10-estratégias-de-chunking--comparativo)
11. [Decisões de Design](#11-decisões-de-design)
12. [Limitações e Pontos de Atenção](#12-limitações-e-pontos-de-atenção)
13. [Guia de Extensão](#13-guia-de-extensão)
14. [Referência Rápida da API](#14-referência-rápida-da-api)

---

## 1. Visão Geral

RAG Workspace é uma aplicação educacional que demonstra o padrão **RAG (Retrieval-Augmented Generation)** na prática. O objetivo é mostrar como conectar uma base de conhecimento local (arquivo `.txt`) a um modelo de linguagem grande (LLM), de modo que as respostas sejam fundamentadas exclusivamente nos documentos fornecidos — e não no conhecimento genérico do modelo.

**Problema que resolve:**
- LLMs "inventam" respostas quando não têm informação suficiente (alucinação).
- Com RAG, o modelo só usa o que está no documento, citando as fontes.

**Tecnologias principais:**

| Camada          | Tecnologia                          |
|-----------------|-------------------------------------|
| Backend         | Python 3.10+, Flask, Flask-CORS     |
| Núcleo RAG      | `rag_core.py` (sem framework externo) |
| Base vetorial   | ChromaDB (persistência local)       |
| Embeddings      | OpenAI `text-embedding-3-small`     |
| Geração de texto | OpenAI `gpt-4o-mini`               |
| Frontend        | HTML + CSS + JavaScript (vanilla)   |

---

## 2. Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                     Navegador                           │
│              rag-workspace.html + assets/               │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP (JSON)
                        ▼
┌─────────────────────────────────────────────────────────┐
│                   Flask (app.py)                        │
│  GET /              POST /api/indexar                   │
│  GET /api/health    POST /api/consultar                 │
│                     POST /api/limpar                    │
└───────────────────────┬─────────────────────────────────┘
                        │ Python
                        ▼
┌─────────────────────────────────────────────────────────┐
│                  RAGBasico (rag_core.py)                │
│                                                         │
│  carregar_txt → gerar_chunks → indexar no ChromaDB      │
│  recuperar_contexto → gerar_resposta (OpenAI)           │
└────────────┬──────────────────────────┬─────────────────┘
             │                          │
             ▼                          ▼
  ┌──────────────────┐      ┌───────────────────────┐
  │  ChromaDB local  │      │  OpenAI API            │
  │  (chroma_db/)    │      │  Embeddings + Chat     │
  └──────────────────┘      └───────────────────────┘
```

O núcleo RAG é independente do Flask — pode ser importado e usado diretamente em scripts Python ou notebooks.

---

## 3. Estrutura de Arquivos

```
RAG/
├── app.py                  # Servidor Flask e rotas da API
├── rag_core.py             # Lógica RAG: chunking, indexação, consulta
├── rag-workspace.html      # Interface web (single-page)
├── requirements.txt        # Dependências Python
├── politicas_internas.txt  # Documento de exemplo para testes
├── .env                    # (criar manualmente) variáveis de ambiente
├── assets/
│   ├── app.js              # Lógica JavaScript do frontend
│   └── style.css           # Estilos da interface
└── chroma_db/              # (gerado em runtime) base vetorial persistida
    └── chroma.sqlite3
```

> **`chroma_db/` não deve ser commitada.** Adicione ao `.gitignore`:
> ```
> RAG/chroma_db/
> RAG/.env
> ```

---

## 4. Dependências e Configuração

### 4.1 Instalação

```bash
cd RAG
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 4.2 `requirements.txt`

| Pacote          | Finalidade                                         |
|-----------------|----------------------------------------------------|
| `openai`        | Chamadas à API OpenAI (embeddings e chat)          |
| `chromadb`      | Base vetorial local com persistência em SQLite     |
| `python-dotenv` | Carrega variáveis do arquivo `.env`                |
| `flask`         | Servidor HTTP e definição de rotas                 |
| `flask-cors`    | Habilita CORS para chamadas do frontend            |
| `streamlit`     | Incluído como alternativa de interface (não usado) |

### 4.3 Variáveis de ambiente (`.env`)

```env
OPENAI_API_KEY=sk-...          # Obrigatório
CHAT_MODEL=gpt-4o-mini         # Opcional (padrão: gpt-4o-mini)
EMBEDDING_MODEL=text-embedding-3-small  # Opcional (padrão: text-embedding-3-small)
```

As variáveis são carregadas no início de `rag_core.py` com `load_dotenv()`. Se não definidas, os modelos padrão são usados.

---

## 5. Módulo `rag_core.py`

Este é o coração do projeto. Contém duas classes: `Chunker` e `RAGBasico`.

### 5.1 Classe `Chunker`

Responsável por dividir o texto bruto em pedaços menores (chunks) antes da indexação. Todos os métodos são estáticos.

#### `por_itens_numerados(texto: str) → List[str]`

Divide o texto usando como separador qualquer linha que comece com um item numerado (ex.: `1.`, `1.1`, `2.3.4`).

- **Regex:** `r"(?=^\d+(\.\d+)*\s+)"` com `re.MULTILINE`
- **Melhor para:** manuais, políticas, documentos com numeração hierárquica.
- **Exemplo de split:**
  ```
  "1. EXPEDIENTE\n1.1 Horário..." → ["1. EXPEDIENTE\n1.1 Horário..."]
  ```

#### `por_tamanho_fixo(texto: str, tamanho: int = 800, overlap: int = 100) → List[str]`

Divide em blocos de `tamanho` caracteres com sobreposição de `overlap` entre chunks consecutivos.

- **Propósito do overlap:** preservar contexto nas bordas, evitando perda de informação entre chunks.
- **Melhor para:** textos sem estrutura clara ou muito longos.

#### `por_sentencas(texto: str, sentencas_por_chunk: int = 4) → List[str]`

Divide por sentenças (`.`, `!`, `?` seguidos de espaço) e agrupa `N` sentenças por chunk.

- **Regex:** `r"(?<=[.!?])\s+"`
- **Melhor para:** textos narrativos ou artigos.

#### `por_paragrafos(texto: str) → List[str]`

Divide por blocos separados por linha em branco (`\n\n`).

- **Melhor para:** textos com parágrafos bem delimitados.

---

### 5.2 Classe `RAGBasico`

Orquestra o pipeline completo: carregamento, chunking, indexação vetorial e geração de resposta.

#### Construtor `__init__(nome_colecao, pasta_db)`

```python
rag = RAGBasico(nome_colecao="manual_empresa", pasta_db="./chroma_db")
```

| Parâmetro       | Padrão              | Descrição                               |
|-----------------|---------------------|-----------------------------------------|
| `nome_colecao`  | `"manual_empresa"`  | Nome da coleção no ChromaDB             |
| `pasta_db`      | `"./chroma_db"`     | Diretório de persistência do ChromaDB   |

**O que é inicializado:**
- Cliente OpenAI (usa `OPENAI_API_KEY` do ambiente)
- `chromadb.PersistentClient` (cria a pasta se não existir)
- Função de embedding via `OpenAIEmbeddingFunction`
- Coleção ChromaDB (cria ou recupera existente)

#### `total_chunks() → int`

Retorna o número de documentos (chunks) na coleção atual.

#### `carregar_txt(caminho_arquivo: str) → str`

Lê o arquivo `.txt` em UTF-8 e retorna o conteúdo como string.

#### `gerar_chunks(texto: str, estrategia: str) → List[str]`

Despacha para o método correto da classe `Chunker` com base no valor de `estrategia`:

| `estrategia`  | Método chamado              |
|---------------|-----------------------------|
| `"itens"`     | `Chunker.por_itens_numerados` |
| `"fixo"`      | `Chunker.por_tamanho_fixo`  |
| `"sentencas"` | `Chunker.por_sentencas`     |
| qualquer outro | `Chunker.por_paragrafos`  |

#### `indexar_documento(caminho_arquivo: str, estrategia: str) → Dict`

Pipeline de indexação:

1. Carrega o texto com `carregar_txt`.
2. Divide em chunks com `gerar_chunks`.
3. **Verifica se já há dados:** se `colecao.count() > 0`, retorna `status: "ja_indexado"` sem reindexar.
4. Gera IDs únicos (`chunk_0`, `chunk_1`, ...) e metadados por chunk.
5. Envia todos os chunks para o ChromaDB via `colecao.add()` — os embeddings são gerados automaticamente pela função de embedding configurada.

**Retorno de sucesso:**
```json
{
  "status": "ok",
  "mensagem": "Documento indexado com sucesso.",
  "total_chunks": 46,
  "arquivo": "politicas_internas.txt",
  "estrategia": "itens"
}
```

#### `limpar_base() → Dict`

Deleta a coleção do ChromaDB e recria vazia. Permite reindexar com um documento diferente ou estratégia diferente.

#### `recuperar_contexto(pergunta: str, k: int = 3) → List[Dict]`

Realiza a busca semântica:

1. Envia `pergunta` ao ChromaDB via `colecao.query(query_texts=[pergunta], n_results=k)`.
2. O ChromaDB gera o embedding da pergunta e calcula similaridade com todos os chunks.
3. Retorna os `k` chunks mais próximos com seus metadados e distâncias.
4. Converte distância em score de relevância: `score = 1 / (1 + distancia)` — valores mais próximos de `1.0` indicam maior relevância.

**Estrutura de cada item retornado:**
```python
{
    "texto": "2.1 O pedido de férias deve ser feito...",
    "metadados": {
        "fonte": "politicas_internas.txt",
        "chunk_index": 7,
        "estrategia": "itens"
    },
    "score": 0.9123
}
```

#### `gerar_resposta(pergunta: str, contextos: List[Dict]) → str`

Monta o prompt e chama o modelo de chat:

- **System prompt:** instrui o modelo a responder apenas com base no contexto e citar fontes.
- **User prompt:** inclui os chunks numerados como `[Fonte 1]`, `[Fonte 2]`, etc., seguidos da pergunta.
- Chama `client.chat.completions.create` com o modelo definido em `CHAT_MODEL`.

**Estrutura do prompt:**
```
Responda à pergunta usando APENAS as informações fornecidas no contexto.
Se a informação não estiver no contexto, diga claramente que não encontrou.
Cite as fontes no formato [Fonte X].

CONTEXTO:
[Fonte 1] <texto do chunk 1>
[Fonte 2] <texto do chunk 2>
...

PERGUNTA:
<pergunta do usuário>

RESPOSTA:
```

#### `consultar(pergunta: str, k: int = 3) → Dict`

Método principal de consulta — combina `recuperar_contexto` e `gerar_resposta`:

```python
resultado = rag.consultar("Qual o prazo para solicitar férias?", k=3)
```

**Retorno:**
```json
{
  "pergunta": "Qual o prazo para solicitar férias?",
  "resposta": "O pedido de férias deve ser feito com no mínimo 30 dias de antecedência [Fonte 1].",
  "fontes": [ { "texto": "...", "metadados": {...}, "score": 0.91 } ],
  "total_fontes": 3
}
```

---

## 6. Módulo `app.py` — API REST

Servidor Flask que expõe o `RAGBasico` via HTTP.

### Inicialização

```python
rag = RAGBasico(
    nome_colecao="manual_empresa",
    pasta_db=str(BASE_DIR / "chroma_db")
)
```

A instância `rag` é criada uma única vez no carregamento do módulo e compartilhada entre todas as requisições (padrão singleton por processo).

### Rotas

#### `GET /` — Serve o frontend

Retorna o arquivo `rag-workspace.html` da pasta `BASE_DIR`.

#### `GET /assets/<filename>` — Arquivos estáticos

Serve arquivos de `assets/` (JS e CSS).

#### `GET /api/health`

Verifica se o servidor está ativo e retorna estatísticas básicas.

**Resposta:**
```json
{
  "status": "ok",
  "mensagem": "API ativa",
  "colecao": "manual_empresa",
  "total_chunks": 46
}
```

#### `POST /api/indexar`

**Body (opcional):**
```json
{
  "arquivo": "politicas_internas.txt",
  "estrategia": "itens"
}
```

- Se `arquivo` não for enviado, usa `politicas_internas.txt` como padrão.
- Se `estrategia` não for enviada, usa `"itens"` como padrão.
- O caminho do arquivo é resolvido relativo a `BASE_DIR` se não for absoluto.

**Erros possíveis:**
| Código | Situação                        |
|--------|---------------------------------|
| 404    | Arquivo não encontrado          |
| 500    | Erro interno ao indexar         |

#### `POST /api/consultar`

**Body:**
```json
{
  "pergunta": "Qual a política de home office?",
  "k": 3
}
```

- `k` define quantos chunks são recuperados (padrão: `3`).
- Retorna erro `400` se `pergunta` estiver vazia ou se não houver chunks indexados.

#### `POST /api/limpar`

Sem body necessário. Limpa toda a coleção vetorial.

### Tratamento de erros

A função auxiliar `_json_error(message, status_code)` padroniza todas as respostas de erro:
```json
{ "status": "erro", "mensagem": "<descrição>" }
```

---

## 7. Frontend (`rag-workspace.html`)

Interface single-page que consome a API REST via `fetch`. Funcionalidades:

- Campo para especificar o arquivo a indexar e seleção de estratégia de chunking.
- Botão **Indexar documento** → `POST /api/indexar`.
- Campo de pergunta + botão **Enviar** → `POST /api/consultar`.
- Exibe a resposta gerada e painel lateral com os chunks recuperados (fontes).
- Botão **Limpar base** → `POST /api/limpar`.
- Indicador de status da API via `GET /api/health`.

Os assets JS e CSS ficam em `assets/app.js` e `assets/style.css`.

---

## 8. Documento de Exemplo (`politicas_internas.txt`)

Manual interno fictício da "Empresa Exemplo S.A." com 10 seções numeradas:

| Seção | Tema                     |
|-------|--------------------------|
| 1     | Expediente               |
| 2     | Férias                   |
| 3     | Atestado Médico          |
| 4     | Home Office              |
| 5     | Reembolso de Despesas    |
| 6     | Acesso a Sistemas        |
| 7     | Conduta e Segurança      |
| 8     | Licenças e Ausências     |
| 9     | Suporte Interno          |
| 10    | Disposições Finais       |

O documento usa numeração hierárquica (`1.1`, `1.2`, `2.1`...) e foi projetado para demonstrar a estratégia `itens` do chunker.

**Perguntas de teste sugeridas:**
- `"Qual o prazo para pedir férias?"`
- `"Como solicitar reembolso de despesas?"`
- `"Posso trabalhar remotamente?"`
- `"O que fazer em caso de atestado médico?"`

---

## 9. Fluxo Completo de Dados

### Fluxo de Indexação

```
1. Usuário clica em "Indexar documento"
        │
        ▼
2. Frontend → POST /api/indexar {arquivo, estrategia}
        │
        ▼
3. app.py valida o arquivo e chama rag.indexar_documento()
        │
        ▼
4. rag_core lê o .txt → divide em chunks (Chunker)
        │
        ▼
5. ChromaDB gera embeddings via OpenAI (text-embedding-3-small)
   para cada chunk e armazena vetores + textos + metadados
        │
        ▼
6. Retorno: { status: "ok", total_chunks: N }
```

### Fluxo de Consulta

```
1. Usuário digita pergunta e clica "Enviar"
        │
        ▼
2. Frontend → POST /api/consultar {pergunta, k}
        │
        ▼
3. app.py chama rag.consultar(pergunta, k)
        │
        ▼
4. rag_core envia a pergunta ao ChromaDB para busca semântica
   → ChromaDB vetoriza a pergunta e retorna os k chunks mais similares
        │
        ▼
5. rag_core monta prompt com os chunks como contexto
   → Chama OpenAI Chat (gpt-4o-mini)
        │
        ▼
6. Retorno: { resposta, fontes, total_fontes }
        │
        ▼
7. Frontend exibe resposta e painel de fontes
```

---

## 10. Estratégias de Chunking — Comparativo

| Estratégia   | Lógica de corte               | Tamanho médio | Ideal para                          | Risco                              |
|--------------|-------------------------------|---------------|-------------------------------------|------------------------------------|
| `itens`      | Início de item numerado       | Variável       | Manuais, políticas com numeração    | Perde contexto se item for muito longo |
| `paragrafos` | Linha em branco (`\n\n`)      | Variável       | Textos corridos bem formatados      | Parágrafos muito longos ou muito curtos |
| `sentencas`  | `.`, `!`, `?` + espaço (4 por chunk) | Médio   | Artigos, textos narrativos          | Perde contexto de parágrafo        |
| `fixo`       | N caracteres + overlap 100    | ~800 chars     | Qualquer texto, fallback seguro     | Pode cortar no meio de uma frase   |

**Regra geral:** use a estratégia que mais respeita a estrutura semântica natural do documento.

---

## 11. Decisões de Design

### Por que ChromaDB?
- Zero configuração de servidor — persiste em SQLite local.
- Integração nativa com funções de embedding da OpenAI.
- Suficiente para documentos de médio porte em ambiente educacional.

### Por que não usar LangChain ou LlamaIndex?
- O projeto é educacional — implementar o pipeline manualmente torna o funcionamento do RAG transparente.
- Menos abstrações = mais fácil de entender e modificar.

### Por que a coleção não reindexar automaticamente?
- A verificação `if colecao.count() > 0` evita custos desnecessários com a API da OpenAI (cada indexação gera embeddings pagos).
- O usuário deve limpar explicitamente via `/api/limpar` antes de reindexar.

### Por que o score usa `1 / (1 + distância)`?
- O ChromaDB retorna distância L2 (quanto maior, mais diferente).
- A transformação converte para um score intuitivo entre 0 e 1 (quanto maior, mais relevante).

---

## 12. Limitações e Pontos de Atenção

| Limitação | Descrição |
|-----------|-----------|
| **Somente `.txt`** | O carregador aceita apenas arquivos de texto puro. PDFs e Word não são suportados nativamente. |
| **Um documento por vez** | A lógica de "já indexado" impede múltiplos documentos na mesma coleção sem limpar antes. |
| **Sem autenticação** | A API não possui controle de acesso — não expor em produção sem camada de segurança. |
| **Custo OpenAI** | Cada indexação e consulta gera chamadas pagas à API da OpenAI. |
| **Sem histórico de conversa** | Cada consulta é independente — o modelo não tem memória de perguntas anteriores. |
| **ChromaDB em disco** | Não é adequado para ambientes com múltiplas instâncias ou alta concorrência. |

---

## 13. Guia de Extensão

### Suporte a múltiplos documentos

Modifique `indexar_documento` para não verificar `colecao.count() > 0` e adicione prefixo ao ID:

```python
ids = [f"{Path(caminho_arquivo).stem}_chunk_{i}" for i in range(len(chunks))]
```

### Suporte a PDF

Adicione `pypdf` ao `requirements.txt` e crie um método `carregar_pdf`:

```python
def carregar_pdf(self, caminho: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(caminho)
    return "\n\n".join(page.extract_text() for page in reader.pages)
```

### Histórico de conversa

Passe o histórico como contexto adicional no prompt de `gerar_resposta`:

```python
messages = [{"role": "system", "content": "..."}]
for turno in historico:
    messages.append({"role": "user", "content": turno["pergunta"]})
    messages.append({"role": "assistant", "content": turno["resposta"]})
messages.append({"role": "user", "content": prompt})
```

### Usar outro modelo de embedding (ex.: local com Sentence Transformers)

Substitua `embedding_fn` no construtor de `RAGBasico`:

```python
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
self.embedding_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
```

---

## 14. Referência Rápida da API

Base URL: `http://127.0.0.1:5000`

| Método | Rota             | Body JSON                                      | Descrição               |
|--------|------------------|------------------------------------------------|-------------------------|
| GET    | `/`              | —                                              | Serve o frontend        |
| GET    | `/api/health`    | —                                              | Status e total de chunks |
| POST   | `/api/indexar`   | `{ "arquivo": "...", "estrategia": "itens" }`  | Indexa documento        |
| POST   | `/api/consultar` | `{ "pergunta": "...", "k": 3 }`                | Consulta com RAG        |
| POST   | `/api/limpar`    | `{}`                                           | Limpa base vetorial     |

**Exemplos curl:**

```bash
# Health
curl http://127.0.0.1:5000/api/health

# Indexar
curl -X POST http://127.0.0.1:5000/api/indexar \
  -H "Content-Type: application/json" \
  -d '{"arquivo": "politicas_internas.txt", "estrategia": "itens"}'

# Consultar
curl -X POST http://127.0.0.1:5000/api/consultar \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Como solicitar reembolso?", "k": 3}'

# Limpar
curl -X POST http://127.0.0.1:5000/api/limpar \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

*Documentação gerada para o repositório [`JoaoLuizRTelo/Laboratorio_de_programacao`](https://github.com/JoaoLuizRTelo/Laboratorio_de_programacao) — pasta `RAG/`.*
