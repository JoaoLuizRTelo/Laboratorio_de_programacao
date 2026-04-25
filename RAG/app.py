import streamlit as st
from rag_core import RAGBasico

st.set_page_config(page_title="RAG de Políticas Internas", layout="wide")

st.title("Sistema RAG - Políticas Internas")
st.write("Faça perguntas sobre o documento da empresa e receba respostas fundamentadas com fontes.")

rag = RAGBasico()

with st.sidebar:
    st.header("Configuração")

    arquivo_txt = st.text_input("Caminho do arquivo .txt", value="politicas_internas.txt")

    estrategia = st.selectbox(
        "Estratégia de chunking",
        ["paragrafos", "sentencas", "fixo", "itens"]
    )

    k = st.slider("Quantidade de chunks recuperados", min_value=1, max_value=5, value=3)

    if st.button("Indexar documento"):
        try:
            resultado = rag.indexar_documento(arquivo_txt, estrategia=estrategia)

            if resultado["status"] == "ok":
                st.success(f"{resultado['mensagem']} Total de chunks: {resultado['total_chunks']}")
            else:
                st.info(f"{resultado['mensagem']} Total atual: {resultado['total_chunks']}")
        except Exception as e:
            st.error(f"Erro ao indexar documento: {e}")

st.subheader("Pergunta")
pergunta = st.text_input("Digite sua pergunta")

if st.button("Consultar"):
    if not pergunta.strip():
        st.warning("Digite uma pergunta antes de consultar.")
    else:
        try:
            resultado = rag.consultar(pergunta, k=k)

            st.subheader("Resposta")
            st.write(resultado["resposta"])

            st.subheader("Fontes recuperadas")
            for i, fonte in enumerate(resultado["fontes"], start=1):
                meta = fonte.get("metadados", {})
                with st.expander(f"Fonte {i}"):
                    st.write(f"**Arquivo:** {meta.get('fonte', 'N/A')}")
                    st.write(f"**Chunk:** {meta.get('chunk_index', 'N/A')}")
                    st.write(f"**Estratégia:** {meta.get('estrategia', 'N/A')}")
                    st.write(fonte["texto"])
        except Exception as e:
            st.error(f"Erro na consulta: {e}")