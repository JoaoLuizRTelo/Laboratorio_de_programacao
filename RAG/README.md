# RAG Workspace

Projeto de Retrieval-Augmented Generation (RAG) com backend em Flask, base vetorial em ChromaDB e geração de respostas com OpenAI.

A aplicação permite:
- indexar um arquivo `.txt` em chunks;
- recuperar os trechos mais relevantes para uma pergunta;
- gerar resposta com citação de fontes (`[Fonte X]`);
- visualizar tudo por uma interface web simples e direta.

## Sumário

- [RAG Workspace](#rag-workspace)
  - [Sumário](#sumário)
  - [Visao geral](#visao-geral)
  - [Arquitetura](#arquitetura)
  - [Estrutura de pastas](#estrutura-de-pastas)
  - [Pre-requisitos](#pre-requisitos)
  - [Instalação e configuração](#instalação-e-configuração)
  - [Como executar](#como-executar)
  - [Como usar pela interface](#como-usar-pela-interface)
  - [API REST](#api-rest)
    - [1) Health check](#1-health-check)
    - [2) Indexar documento](#2-indexar-documento)
    - [3) Consultar](#3-consultar)
    - [4) Limpar base vetorial](#4-limpar-base-vetorial)
  - [Estratégias de chunking](#estratégias-de-chunking)
  - [Formato recomendado para documentos](#formato-recomendado-para-documentos)
  - [Comportamentos importantes](#comportamentos-importantes)
  - [Troubleshooting](#troubleshooting)
    - [Erro de chave da OpenAI](#erro-de-chave-da-openai)
    - ["Nenhum documento indexado"](#nenhum-documento-indexado)
    - [Arquivo não encontrado ao indexar](#arquivo-não-encontrado-ao-indexar)
    - [Dependências não encontradas](#dependências-não-encontradas)

## Visao geral

Fluxo principal do projeto:

1. Você envia um arquivo `.txt` para indexação (ou mantém o arquivo padrão).
2. O texto é quebrado em chunks por uma estratégia escolhida.
3. Os chunks são vetorizados e armazenados no ChromaDB.
4. Ao consultar, o sistema recupera os `k` chunks mais relevantes.
5. O modelo de chat gera a resposta usando apenas o contexto recuperado.

## Arquitetura

- Backend: Flask + Flask-CORS (`app.py`)
- Núcleo RAG: carregamento de documento, chunking, indexação e consulta (`rag_core.py`)
- Banco vetorial: ChromaDB persistente em disco (`chroma_db/`)
- LLM e embeddings: OpenAI (`gpt-4o-mini` e `text-embedding-3-small` por padrão)
- Frontend: HTML + CSS + JavaScript (`rag-workspace.html` e `assets/`)

## Estrutura de pastas

```text
RAG/
	app.py
	rag_core.py
	politicas_internas.txt
	rag-workspace.html
	requirements.txt
	assets/
		app.js
		style.css
	chroma_db/
		chroma.sqlite3
```

## Pre-requisitos

- Python 3.10+ (recomendado)
- Chave de API da OpenAI
- Conexão com internet para chamadas da OpenAI

## Instalação e configuração

No diretório `RAG/`:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Crie um arquivo `.env` na raiz de `RAG/`:

```env
OPENAI_API_KEY=sua_chave_aqui
CHAT_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
```

Variáveis opcionais:
- `CHAT_MODEL`: modelo de geração de resposta.
- `EMBEDDING_MODEL`: modelo para embeddings no ChromaDB.

## Como executar

```powershell
python app.py
```

Acesse no navegador:

```text
http://127.0.0.1:5000
```

## Como usar pela interface

1. Em **Documento**, informe o arquivo `.txt` (padrão: `politicas_internas.txt`).
2. Escolha a estratégia de chunking.
3. Clique em **Indexar documento**.
4. Digite uma pergunta e clique em **Enviar**.
5. Confira a resposta e as fontes recuperadas no painel de contexto.

Para reiniciar o conteúdo vetorial, use **Limpar base**.

## API REST

Base URL local: `http://127.0.0.1:5000`

### 1) Health check

- Método: `GET`
- Rota: `/api/health`

Exemplo:

```bash
curl http://127.0.0.1:5000/api/health
```

Resposta (exemplo):

```json
{
	"status": "ok",
	"mensagem": "API ativa",
	"colecao": "manual_empresa",
	"total_chunks": 46
}
```

### 2) Indexar documento

- Método: `POST`
- Rota: `/api/indexar`

Body JSON:

```json
{
	"arquivo": "politicas_internas.txt",
	"estrategia": "itens"
}
```

Exemplo:

```bash
curl -X POST http://127.0.0.1:5000/api/indexar \
	-H "Content-Type: application/json" \
	-d "{\"arquivo\":\"politicas_internas.txt\",\"estrategia\":\"itens\"}"
```

### 3) Consultar

- Método: `POST`
- Rota: `/api/consultar`

Body JSON:

```json
{
	"pergunta": "Qual o prazo para pedir férias?",
	"k": 3
}
```

Exemplo:

```bash
curl -X POST http://127.0.0.1:5000/api/consultar \
	-H "Content-Type: application/json" \
	-d "{\"pergunta\":\"Qual o prazo para pedir férias?\",\"k\":3}"
```

Resposta (exemplo resumido):

```json
{
	"status": "ok",
	"pergunta": "Qual o prazo para pedir férias?",
	"resposta": "... [Fonte 1] ...",
	"fontes": [
		{
			"texto": "2.1 O pedido de férias deve ser feito com no mínimo 30 dias...",
			"metadados": {
				"fonte": "politicas_internas.txt",
				"chunk_index": 7,
				"estrategia": "itens"
			},
			"score": 0.91
		}
	],
	"total_fontes": 3
}
```

### 4) Limpar base vetorial

- Método: `POST`
- Rota: `/api/limpar`

Exemplo:

```bash
curl -X POST http://127.0.0.1:5000/api/limpar \
	-H "Content-Type: application/json" \
	-d "{}"
```

## Estratégias de chunking

Suportadas no projeto:

- `itens`: divide por itens numerados (bom para manuais/políticas).
- `paragrafos`: divide por blocos separados por linha em branco.
- `sentencas`: agrupa sentenças (4 por chunk).
- `fixo`: tamanho fixo (800 caracteres, overlap 100).

Regra prática:
- Use `itens` para documentos com numeração (ex.: 1.1, 1.2, 2.1...).
- Use `paragrafos` para textos corridos com boa separação visual.
- Use `sentencas` quando quiser granularidade média.
- Use `fixo` para casos gerais ou textos sem estrutura clara.

## Formato recomendado para documentos

- Arquivo `.txt` em UTF-8.
- Conteúdo bem organizado (títulos, seções, numeração quando possível).
- Evite linhas excessivamente longas e ruído textual.

## Comportamentos importantes

- A coleção é persistida em `chroma_db/`.
- Se já existir conteúdo indexado, a rota `/api/indexar` retorna `ja_indexado`.
- Para reindexar do zero, chame `/api/limpar` antes de nova indexação.
- A resposta do modelo é instruída para usar apenas o contexto recuperado.

## Troubleshooting

### Erro de chave da OpenAI

Verifique se `OPENAI_API_KEY` está no `.env` e se o terminal foi reiniciado/apontado para o ambiente correto.

### "Nenhum documento indexado"

Faça uma indexação antes de consultar (`/api/indexar`).

### Arquivo não encontrado ao indexar

- Confira o nome em **Documento**.
- Use caminho relativo à pasta `RAG/` ou caminho absoluto válido.

### Dependências não encontradas

Garanta que o ambiente virtual está ativo e rode novamente:

```powershell
pip install -r requirements.txt
```

---

Se quiser evoluir o projeto, um bom próximo passo é incluir suporte a múltiplos documentos na mesma coleção e versionamento de índice.
