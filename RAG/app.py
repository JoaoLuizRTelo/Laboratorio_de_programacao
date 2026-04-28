from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from rag_core import RAGBasico

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_FILE = BASE_DIR / "rag-workspace.html"
ASSETS_DIR = BASE_DIR / "assets"
DEFAULT_DOC = BASE_DIR / "politicas_internas.txt"

app = Flask(__name__, static_folder="assets")
CORS(app)

rag = RAGBasico(
    nome_colecao="manual_empresa",
    pasta_db=str(BASE_DIR / "chroma_db")
)


def _json_error(message: str, status_code: int = 400):
    return jsonify({"status": "erro", "mensagem": message}), status_code


@app.get("/")
def home():
    return send_from_directory(BASE_DIR, FRONTEND_FILE.name)


@app.get("/assets/<path:filename>")
def assets(filename: str):
    return send_from_directory(ASSETS_DIR, filename)


@app.get("/api/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "mensagem": "API ativa",
            "colecao": rag.nome_colecao,
            "total_chunks": rag.total_chunks(),
        }
    )


@app.post("/api/indexar")
def indexar():
    data = request.get_json(silent=True) or {}
    arquivo = data.get("arquivo") or DEFAULT_DOC.name
    estrategia = data.get("estrategia", "itens")

    caminho_arquivo = Path(arquivo)
    if not caminho_arquivo.is_absolute():
        caminho_arquivo = BASE_DIR / arquivo

    if not caminho_arquivo.exists():
        return _json_error(f"Arquivo não encontrado: {caminho_arquivo.name}", 404)

    try:
        resultado = rag.indexar_documento(str(caminho_arquivo), estrategia=estrategia)
        return jsonify(resultado)
    except Exception as e:
        return _json_error(f"Erro ao indexar documento: {e}", 500)


@app.post("/api/consultar")
def consultar():
    data = request.get_json(silent=True) or {}
    pergunta = (data.get("pergunta") or "").strip()
    k = int(data.get("k", 3))

    if not pergunta:
        return _json_error("Envie uma pergunta para consulta.", 400)

    if rag.total_chunks() == 0:
        return _json_error("Nenhum documento indexado. Indexe um documento primeiro.", 400)

    try:
        resultado = rag.consultar(pergunta, k=k)
        return jsonify({"status": "ok", **resultado})
    except Exception as e:
        return _json_error(f"Erro na consulta: {e}", 500)


@app.post("/api/limpar")
def limpar():
    try:
        resultado = rag.limpar_base()
        return jsonify(resultado)
    except Exception as e:
        return _json_error(f"Erro ao limpar base: {e}", 500)


if __name__ == "__main__":
    app.run(debug=True)