# 🧪 Laboratório de Programação

Repositório acadêmico desenvolvido para a disciplina de **Laboratório de Programação**, com projetos práticos que aplicam conceitos de automação, inteligência artificial e processamento de documentos.

---

## 📁 Estrutura do Repositório

```
Laboratorio_de_programacao/
│
├── RAG/                          # Sistema de Recuperação Aumentada por Geração (RAG)
│   ├── app.py                    # Backend Flask da aplicação
│   ├── rag_core.py               # Núcleo do sistema RAG (indexação e consulta)
│   ├── rag-workspace.html        # Interface web do workspace
│   ├── politicas_internas.txt    # Base de conhecimento de exemplo
│   ├── assets/                   # Recursos estáticos (CSS, JS)
│   └── requirements.txt          # Dependências Python
│
├── processar_contra_cheque/      # Processador de Contracheque
│   ├── app.py                    # Lógica principal de processamento
│   ├── index.html                # Interface web
│   └── codigos_claude/           # Experimentos e variações de código
│
├── Automação_do_fechamento_mensal_de_faturamento_de_PJ.md   # Proposta de automação
└── README.md
```

---

## 📌 Projetos

### 🤖 RAG — Recuperação Aumentada por Geração

Sistema que combina busca em documentos com geração de respostas via IA. Permite indexar arquivos de texto e realizar consultas em linguagem natural, retornando respostas baseadas no conteúdo indexado.

**Tecnologias:** Python, Flask, Flask-CORS, HTML, CSS, JavaScript

**Funcionalidades:**
- Indexação de documentos por chunks
- Consulta semântica via banco de vetores
- Interface web interativa com modo claro/escuro
- API REST com backend Flask

---

### 📄 Processador de Contracheque

Aplicação para leitura e processamento de contracheques municipais. Realiza a extração e interpretação de dados a partir de documentos, com suporte a múltiplas prefeituras.

**Tecnologias:** Python, HTML

**Funcionalidades:**
- Processamento de contracheques em diferentes formatos
- Suporte a múltiplos municípios
- Interface web para upload e visualização dos resultados

---

### 📝 Automação do Fechamento Mensal de Faturamento (PJ)

Proposta documentada para automação do processo de fechamento mensal de faturamento para Pessoas Jurídicas, incluindo objetivos, integração com IA e benefícios esperados.

---

## 🛠️ Tecnologias Utilizadas

| Linguagem      | Participação |
|----------------|-------------|
| Python         | 97.8%       |
| HTML           | 0.9%        |
| JavaScript     | 0.5%        |
| PowerShell     | 0.4%        |
| CSS            | 0.3%        |
| C              | 0.1%        |

---

## 🚀 Como Executar (Projeto RAG)

```bash
# 1. Entre na pasta do projeto
cd RAG

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Execute o servidor
python app.py
```

Acesse `http://localhost:5000` no navegador.

---

## 👨‍🎓 Autor

**João Luiz R. Telo** — [@JoaoLuizRTelo](https://github.com/JoaoLuizRTelo)  
📧 joao.telo@unemat.br  
Curso de Engenharia/Ciência — UNEMAT
