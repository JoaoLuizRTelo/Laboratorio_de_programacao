import os
import re
from typing import List, Dict

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class Chunker:
  
    @staticmethod
    def por_itens_numerados(texto: str) -> List[str]:
        padrao = r'(?=^\d+(\.\d+)*\s+)'
        partes = re.split(padrao, texto, flags=re.MULTILINE)
        chunks = [p.strip() for p in partes if p and p.strip()]
        return chunks
      
    @staticmethod
    def por_tamanho_fixo(
        texto: str, tamanho: int = 800, overlap: int = 100
    ) -> List[str]:
        chunks = []
        inicio = 0

        while inicio < len(texto):
            fim = inicio + tamanho
            chunk = texto[inicio:fim].strip()

            if chunk:
                chunks.append(chunk)

            inicio = fim - overlap

        return chunks

    @staticmethod
    def por_sentencas(texto: str, sentencas_por_chunk: int = 4) -> List[str]:
        sentencas = re.split(r"(?<=[.!?])\s+", texto)
        chunks = []

        for i in range(0, len(sentencas), sentencas_por_chunk):
            chunk = " ".join(sentencas[i : i + sentencas_por_chunk]).strip()
            if chunk:
                chunks.append(chunk)

        return chunks

    @staticmethod
    def por_paragrafos(texto: str) -> List[str]:
        paragrafos = texto.split("\n\n")
        return [p.strip() for p in paragrafos if p.strip()]


class RAGBasico:
    def __init__(
        self, nome_colecao: str = "manual_empresa", pasta_db: str = "./chroma_db"
    ):
        self.client = OpenAI()

        self.chroma = chromadb.PersistentClient(path=pasta_db)

        self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
            model_name=EMBEDDING_MODEL, api_key=OPENAI_API_KEY
        )

        self.colecao = self.chroma.get_or_create_collection(
            name=nome_colecao, embedding_function=self.embedding_fn
        )

    def carregar_txt(self, caminho_arquivo: str) -> str:
        with open(caminho_arquivo, "r", encoding="utf-8") as arquivo:
            return arquivo.read()

    def gerar_chunks(self, texto: str, estrategia: str = "paragrafos") -> List[str]:
        if estrategia == "fixo":
          return Chunker.por_tamanho_fixo(texto)
        elif estrategia == "sentencas":
          return Chunker.por_sentencas(texto)
        elif estrategia == "itens":
          return Chunker.por_itens_numerados(texto)
        else:
          return Chunker.por_paragrafos(texto)

    def indexar_documento(
        self, caminho_arquivo: str, estrategia: str = "paragrafos"
    ) -> Dict:
        texto = self.carregar_txt(caminho_arquivo)
        chunks = self.gerar_chunks(texto, estrategia)

        if self.colecao.count() > 0:
            return {
                "status": "ja_indexado",
                "mensagem": "A coleção já possui documentos indexados.",
                "total_chunks": self.colecao.count(),
            }

        ids = [f"chunk_{i}" for i in range(len(chunks))]
        metadados = [
            {"fonte": caminho_arquivo, "chunk_index": i, "estrategia": estrategia}
            for i in range(len(chunks))
        ]

        self.colecao.add(documents=chunks, metadatas=metadados, ids=ids)

        return {
            "status": "ok",
            "mensagem": "Documento indexado com sucesso.",
            "total_chunks": len(chunks),
        }

    def recuperar_contexto(self, pergunta: str, k: int = 3) -> List[Dict]:
        resultados = self.colecao.query(query_texts=[pergunta], n_results=k)

        documentos = resultados.get("documents", [[]])[0]
        metadados = resultados.get("metadatas", [[]])[0]

        contextos = []
        for doc, meta in zip(documentos, metadados):
            contextos.append({"texto": doc, "metadados": meta})

        return contextos

    def gerar_resposta(self, pergunta: str, contextos: List[Dict]) -> str:
        contexto_formatado = "\n\n".join(
            [f"[Fonte {i+1}] {c['texto']}" for i, c in enumerate(contextos)]
        )

        prompt = f"""
Responda à pergunta usando APENAS as informações fornecidas no contexto.
Se a informação não estiver no contexto, diga claramente que não encontrou essa informação nos documentos.
Cite as fontes no formato [Fonte X].

CONTEXTO:
{contexto_formatado}

PERGUNTA:
{pergunta}

RESPOSTA:
"""

        resposta = self.client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Você responde apenas com base no contexto fornecido e cita as fontes utilizadas.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        return resposta.choices[0].message.content

    def consultar(self, pergunta: str, k: int = 3) -> Dict:
        contextos = self.recuperar_contexto(pergunta, k=k)
        print("\n===== CONTEXTOS RECUPERADOS =====")
        for i, c in enumerate(contextos, start=1):
            print(f"\n--- Fonte {i} ---")
            print(c["texto"][:500])
        resposta = self.gerar_resposta(pergunta, contextos)

        return {"pergunta": pergunta, "resposta": resposta, "fontes": contextos}
