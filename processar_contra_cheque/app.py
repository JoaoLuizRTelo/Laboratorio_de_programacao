"""
Contra Cheque — Backend Flask
==============================
Instalar dependências:
    pip install flask

Rodar:
    python app.py

A aplicação sobe em http://localhost:5000
O frontend deve estar na mesma pasta (index.html).
"""

import re
import io
import unicodedata
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file, send_from_directory

app = Flask(__name__, static_folder=".", static_url_path="")


# ============================================================
# UTILITÁRIOS DE FORMATAÇÃO
# ============================================================


def so_numeros(texto: str) -> str:
    return re.sub(r"[^0-9]", "", texto or "")


def normalizar_texto(texto: str) -> str:
    """
    Remove acentos e substitui caracteres especiais por equivalentes ASCII.
    Ex: ç → c, ã → a, é → e, Á → A, etc.
    """
    return "".join(
        c
        for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn"
    )


def remover_letras(texto: str) -> str:
    return re.sub(r"[A-Za-z]", "", texto or "")


def formatar_cpf(valor: str) -> str:
    return so_numeros(valor).zfill(11)


def formatar_matricula(valor: str) -> str:
    return so_numeros(valor).zfill(10)


def formatar_referencia(valor: str) -> str:
    """
    Formata o campo Referência das linhas P e D.

    Regra 1 — sufixo letra (ex: "30.00D", "15.00H", "10D"):
        Remove decimais, mantém inteiro + letra maiúscula.
        "30.00D" -> "30D" | "12.50H" -> "12H" | "10D" -> "10D"

    Regra 2 — numérico puro (ex: "15.00", "27.50"):
        Formata como "00,00" com vírgula decimal.
        "15.00" -> "15,00" | "27.50" -> "27,50" | "8" -> "8,00"
    """
    valor = (valor or "").strip()
    if not valor:
        return valor

    # Caso 1: termina com letra(s)
    m = re.match(r"^(\d+)(?:\.\d+)?([A-Za-z]+)$", valor)
    if m:
        return f"{m.group(1)}{m.group(2).upper()}"

    # Caso 2: numérico puro
    numero_str = re.sub(r"[A-Za-z]", "", valor).replace(",", ".")
    try:
        return f"{float(numero_str):.2f}".replace(".", ",")
    except ValueError:
        return valor


def formatar_referencia_prefeitura1(valor: str) -> str:
    """
    Prefeitura 1 — col Referência (H).
    • Se contém letra D ou H → '0.00'
    • Padrão de parcelas (ex: '6/72', '056/096') → mantém
    • Demais → limpa e formata como decimal com ponto (ex: '40.00')
    """
    valor = (valor or "").strip().replace(" ", "")
    if not valor:
        return "0.00"
    if re.search(r"[DdHh]", valor):
        return "0.00"
    if re.match(r"^\d+/\d+$", valor):
        return valor
    limpo = re.sub(r"[^0-9.,]", "", valor).replace(",", ".")
    if not limpo:
        return "0.00"
    try:
        return f"{float(limpo):.2f}"
    except ValueError:
        return "0.00"


def formatar_valor_prefeitura1(valor: str) -> str:
    """
    Prefeitura 1 — col Valor (I): somente pontos e números.
    """
    return re.sub(r"[^0-9.]", "", valor or "")


def formatar_referencia_prefeitura2(valor: str) -> str:
    """
    Prefeitura 2 — col Referência.
    • Vazio ou '.' → '0.00'
    • Remove espaços internos
    • Padrão de parcelas → mantém
    • Trata vírgula como decimal; saída com ponto (ex: '31.00')
    """
    valor = (valor or "").strip()
    if not valor or valor == ".":
        return "0.00"
    valor = valor.replace(" ", "")
    if re.match(r"^\d+/\d+$", valor):
        return valor
    m = re.match(r"^(\d+)(?:[.,]\d+)?([A-Za-z]+)$", valor)
    if m:
        return "0.00"
    val_norm = valor.replace(",", ".")
    try:
        return f"{float(val_norm):.2f}"
    except ValueError:
        return valor


def formatar_referencia_prefeitura3(valor: str) -> str:
    """
    prefeitura3 do Leste — col Referência.
    • Remove sufixo de letra (D, H, etc.) mas mantém o valor decimal
    • Padrão de parcelas → mantém
    • Saída com ponto decimal (ex: '30.00', '40.00')
    """
    valor = (valor or "").strip().replace(" ", "")
    if not valor:
        return "0.00"
    if re.match(r"^\d+/\d+$", valor):
        return valor
    # Remove letra(s) no final, preserva número
    m = re.match(r"^([\d.,]+)[A-Za-z]+$", valor)
    if m:
        valor = m.group(1)
    val_norm = valor.replace(",", ".")
    try:
        return f"{float(val_norm):.2f}"
    except ValueError:
        return valor


def _serial_excel_para_data(serial: int) -> datetime:
    return datetime(1899, 12, 30) + timedelta(days=serial)


def formatar_data(valor: str, formato: str) -> str:
    valor = (valor or "").strip()
    if not valor:
        return ""

    dt = None

    if re.match(r"^\d{5,6}$", valor):
        try:
            dt = _serial_excel_para_data(int(valor))
        except Exception:
            return valor

    if dt is None and re.match(r"^\d{4}-\d{2}-\d{2}", valor):
        try:
            dt = datetime.strptime(valor[:10], "%Y-%m-%d")
        except ValueError:
            return valor

    if dt is None and re.match(r"^\d{1,2}/\d{1,2}/\d{4}", valor):
        try:
            dt = datetime.strptime(valor[:10], "%d/%m/%Y")
        except ValueError:
            return valor

    # DDMMAAAA sem separadores (ex: 02091963 → 02/09/1963)
    if dt is None and re.match(r"^\d{8}$", valor):
        try:
            dt = datetime.strptime(valor, "%d%m%Y")
        except ValueError:
            return valor

    if dt is None:
        return valor

    if formato == "DD/MM/AAAA":
        return dt.strftime("%d/%m/%Y")
    if formato == "MM/AAAA":
        return dt.strftime("%m/%Y")
    return valor


# ============================================================
# PROCESSADORES POR TIPO DE LINHA
# ============================================================


def _c(cols, i):
    return cols[i] if i < len(cols) else ""


def processar_linha_f(cols):
    """
    Linha F — Ficha do funcionário.
    [0]=F [1]=CódEmp [2]=CódSetor [3]=CPF [4]=Matrícula [5]=Nome [6]=CBO
    [7]=NomeEmpresa [8]=NomeSetor [9]=DtNasc [10]=DtAdm [11]=MêsAnoPgto
    [12]=Cargo [13]=Lotação [14]=CódLotação [15]=CódVínculo [16]=NomeVínculo
    [17]=Banco [18]=Agência [19]=ContaCorrente [20]=PIS [21]=RG
    [22]=Dependentes [23]=PlanoCarreira
    """
    return ";".join(
        [
            "F",
            _c(cols, 1),
            _c(cols, 2),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            _c(cols, 5),
            _c(cols, 6),
            _c(cols, 7),
            _c(cols, 8),
            formatar_data(_c(cols, 9), "DD/MM/AAAA"),
            formatar_data(_c(cols, 10), "DD/MM/AAAA"),
            formatar_data(_c(cols, 11), "MM/AAAA"),
            _c(cols, 12),
            _c(cols, 13),
            _c(cols, 14),
            _c(cols, 15),
            _c(cols, 16),
            _c(cols, 17),
            _c(cols, 18),
            _c(cols, 19),
            _c(cols, 20),
            _c(cols, 21),
            "0",  # Dependentes (zerar)
            "0",  # Plano Carreira (zerar)
        ]
    )


def processar_linha_p(cols):
    """
    Linha P — Proventos.
    [0]=P [1]=CódEmp [2]=CódSetor [3]=CPF [4]=Matrícula
    [5]=Código [6]=Descrição [7]=Referência [8]=Valor
    """
    return ";".join(
        [
            "P",
            _c(cols, 1),
            _c(cols, 2),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            _c(cols, 5),
            _c(cols, 6),
            formatar_referencia(_c(cols, 7)),
            remover_letras(_c(cols, 8)),
        ]
    )


def processar_linha_d(cols):
    """
    Linha D — Descontos. Mesma estrutura da Linha P.
    """
    return ";".join(
        [
            "D",
            _c(cols, 1),
            _c(cols, 2),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            _c(cols, 5),
            _c(cols, 6),
            formatar_referencia(_c(cols, 7)),
            remover_letras(_c(cols, 8)),
        ]
    )


def processar_linha_t(cols):
    """
    Linha T — Totais.
    [0]=T [1]=CódEmp [2]=CódSetor [3]=CPF [4]=Matrícula
    [5]=TotalProventos [6]=TotalDescontos [7]=Líquido [8]=SalárioBase
    [9]=SalContribINSS [10]=BaseFGTS [11]=FGTSMes [12]=BaseIRRF
    [13]=FaixaIRRF [14-18]=MensagensIndividuais(1-5)
    """
    return ";".join(
        [
            "T",
            _c(cols, 1),
            _c(cols, 2),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            remover_letras(_c(cols, 5)),
            remover_letras(_c(cols, 6)),
            remover_letras(_c(cols, 7)),
            remover_letras(_c(cols, 8)),
            remover_letras(_c(cols, 9)),
            remover_letras(_c(cols, 10)),
            remover_letras(_c(cols, 11)),
            remover_letras(_c(cols, 12)),
            remover_letras(_c(cols, 13)),
            _c(cols, 14),
            _c(cols, 15),
            _c(cols, 16),
            _c(cols, 17),
            _c(cols, 18),
        ]
    )


def processar_linha_m(cols):
    """
    Linha M — Mensagem Geral.
    [0]=M [1]=CódEmp [2]=CódSetor [3]=CPF [4]=Matrícula [5-9]=MensagemGeral(1-5)
    """
    return ";".join(
        [
            "M",
            _c(cols, 1),
            _c(cols, 2),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            _c(cols, 5),
            _c(cols, 6),
            _c(cols, 7),
            _c(cols, 8),
            _c(cols, 9),
            "",  # campo extra trailing
        ]
    )


PROCESSADORES = {
    "F": processar_linha_f,
    "P": processar_linha_p,
    "D": processar_linha_d,
    "T": processar_linha_t,
    "M": processar_linha_m,
}

ORDEM_SAIDA = ["F", "P", "D", "T", "M"]


# ============================================================
# PROCESSADORES ESPECÍFICOS POR PREFEITURA
# ============================================================

# ---- Prefeitura 1 ----


def processar_linha_f_prefeitura1(cols):
    """Prefeitura 1 — Linha F: strip em campos de texto (nomes vêm com espaços de preenchimento)."""
    return ";".join(
        [
            "F",
            _c(cols, 1).strip(),
            _c(cols, 2).strip(),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            _c(cols, 5).strip(),  # Nome — remove espaços de preenchimento
            _c(cols, 6).strip(),
            _c(cols, 7).strip(),
            _c(cols, 8).strip(),
            formatar_data(_c(cols, 9), "DD/MM/AAAA"),
            formatar_data(_c(cols, 10), "DD/MM/AAAA"),
            formatar_data(_c(cols, 11), "MM/AAAA"),
            _c(cols, 12).strip(),
            _c(cols, 13).strip(),
            _c(cols, 14).strip(),
            _c(cols, 15).strip(),
            _c(cols, 16).strip(),
            _c(cols, 17).strip(),
            _c(cols, 18).strip(),
            _c(cols, 19).strip(),
            _c(cols, 20).strip(),
            _c(cols, 21).strip(),
            "0",  # Dependentes (zerar)
            "0",  # Plano Carreira (zerar)
        ]
    )


def processar_linha_p_prefeitura1(cols):
    """Prefeitura 1 — Linha P: referência sem letras D/H (→ 0.00); valor só dígitos+ponto."""
    return ";".join(
        [
            "P",
            _c(cols, 1),
            _c(cols, 2),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            _c(cols, 5),
            _c(cols, 6),
            formatar_referencia_prefeitura1(_c(cols, 7)),
            formatar_valor_prefeitura1(_c(cols, 8)),
        ]
    )


def processar_linha_d_prefeitura1(cols):
    """Prefeitura 1 — Linha D: mesma regra da Linha P."""
    return ";".join(
        [
            "D",
            _c(cols, 1),
            _c(cols, 2),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            _c(cols, 5),
            _c(cols, 6),
            formatar_referencia_prefeitura1(_c(cols, 7)),
            formatar_valor_prefeitura1(_c(cols, 8)),
        ]
    )


# ---- Prefeitura 2 ----


def processar_linha_f_prefeitura2(cols):
    """Prefeitura 2 — Linha F: preserva o número real de dependentes (col 22)."""
    return ";".join(
        [
            "F",
            _c(cols, 1),
            _c(cols, 2),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            _c(cols, 5),
            _c(cols, 6),
            _c(cols, 7),
            _c(cols, 8),
            formatar_data(_c(cols, 9), "DD/MM/AAAA"),
            formatar_data(_c(cols, 10), "DD/MM/AAAA"),
            formatar_data(_c(cols, 11), "MM/AAAA"),
            _c(cols, 12),
            _c(cols, 13),
            _c(cols, 14),
            _c(cols, 15),
            _c(cols, 16),
            _c(cols, 17),
            _c(cols, 18),
            _c(cols, 19),
            _c(cols, 20),
            _c(cols, 21),
            _c(cols, 22),  # dependentes: valor real do arquivo
            "0",
        ]
    )


def processar_linha_p_prefeitura2(cols):
    """Prefeitura 2 — Linha P: referência sem espaços/virgula, ponto decimal."""
    return ";".join(
        [
            "P",
            _c(cols, 1),
            _c(cols, 2),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            _c(cols, 5),
            _c(cols, 6),
            formatar_referencia_prefeitura2(_c(cols, 7)),
            remover_letras(_c(cols, 8)),
        ]
    )


def processar_linha_d_prefeitura2(cols):
    """Prefeitura 2 — Linha D: mesma regra da Linha P."""
    return ";".join(
        [
            "D",
            _c(cols, 1),
            _c(cols, 2),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            _c(cols, 5),
            _c(cols, 6),
            formatar_referencia_prefeitura2(_c(cols, 7)),
            remover_letras(_c(cols, 8)),
        ]
    )


def processar_linha_t_prefeitura2(cols):
    """Prefeitura 2 — Linha T: zera col F (TotalProventos) e col K (BaseFGTS)."""
    return ";".join(
        [
            "T",
            _c(cols, 1),
            _c(cols, 2),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            "0",  # col F — TotalProventos → zerado
            remover_letras(_c(cols, 6)),
            remover_letras(_c(cols, 7)),
            remover_letras(_c(cols, 8)),
            remover_letras(_c(cols, 9)),
            "0",  # col K — BaseFGTS → zerado
            remover_letras(_c(cols, 11)),
            remover_letras(_c(cols, 12)),
            remover_letras(_c(cols, 13)),
            _c(cols, 14),
            _c(cols, 15),
            _c(cols, 16),
            _c(cols, 17),
            _c(cols, 18),
        ]
    )


# ---- prefeitura3 do Leste ----


def processar_linha_f_prefeitura3(cols):
    """prefeitura3 — Linha F: preserva dependentes; remove espaços do NomeVínculo (col 16)."""
    return ";".join(
        [
            "F",
            _c(cols, 1),
            _c(cols, 2),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            _c(cols, 5),
            _c(cols, 6),
            _c(cols, 7),
            _c(cols, 8),
            formatar_data(_c(cols, 9), "DD/MM/AAAA"),  # suporta DDMMAAAA
            formatar_data(_c(cols, 10), "DD/MM/AAAA"),
            formatar_data(_c(cols, 11), "MM/AAAA"),
            _c(cols, 12),
            _c(cols, 13),
            _c(cols, 14),
            _c(cols, 15),
            _c(cols, 16).strip(),  # NomeVínculo sem espaços extras
            _c(cols, 17),
            _c(cols, 18),
            _c(cols, 19),
            _c(cols, 20),
            _c(cols, 21),
            _c(cols, 22),  # dependentes: valor real do arquivo
            "0",
        ]
    )


def processar_linha_p_prefeitura3(cols):
    """prefeitura3 — Linha P: remove letra do sufixo da referência, mantém decimal."""
    return ";".join(
        [
            "P",
            _c(cols, 1),
            _c(cols, 2),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            _c(cols, 5),
            _c(cols, 6),
            formatar_referencia_prefeitura3(_c(cols, 7)),
            remover_letras(_c(cols, 8)),
        ]
    )


def processar_linha_d_prefeitura3(cols):
    """prefeitura3 — Linha D: mesma regra da Linha P."""
    return ";".join(
        [
            "D",
            _c(cols, 1),
            _c(cols, 2),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            _c(cols, 5),
            _c(cols, 6),
            formatar_referencia_prefeitura3(_c(cols, 7)),
            remover_letras(_c(cols, 8)),
        ]
    )


def processar_linha_t_prefeitura3(cols):
    """prefeitura3 — Linha T: zera col J (SalContribINSS)."""
    return ";".join(
        [
            "T",
            _c(cols, 1),
            _c(cols, 2),
            formatar_cpf(_c(cols, 3)),
            formatar_matricula(_c(cols, 4)),
            remover_letras(_c(cols, 5)),
            remover_letras(_c(cols, 6)),
            remover_letras(_c(cols, 7)),
            remover_letras(_c(cols, 8)),
            "0",  # col J — SalContribINSS → zerado
            remover_letras(_c(cols, 10)),
            remover_letras(_c(cols, 11)),
            remover_letras(_c(cols, 12)),
            remover_letras(_c(cols, 13)),
            _c(cols, 14),
            _c(cols, 15),
            _c(cols, 16),
            _c(cols, 17),
            _c(cols, 18),
        ]
    )


# ============================================================
# DICTS DE PROCESSADORES E PRÉ-PROCESSAMENTO POR PREFEITURA
# ============================================================


def _pre_processar_prefeitura3(conteudo: str) -> str:
    """prefeitura3: substitui código de secretaria incorreto 070374 → 070474."""
    return conteudo.replace(";070374;", ";070474;")


PROCESSADORES_prefeitura1 = {
    "F": processar_linha_f_prefeitura1,
    "P": processar_linha_p_prefeitura1,
    "D": processar_linha_d_prefeitura1,
    "T": processar_linha_t,
    "M": processar_linha_m,
}

PROCESSADORES_prefeitura2 = {
    "F": processar_linha_f_prefeitura2,
    "P": processar_linha_p_prefeitura2,
    "D": processar_linha_d_prefeitura2,
    "T": processar_linha_t_prefeitura2,
    "M": processar_linha_m,
}

PROCESSADORES_prefeitura3 = {
    "F": processar_linha_f_prefeitura3,
    "P": processar_linha_p_prefeitura3,
    "D": processar_linha_d_prefeitura3,
    "T": processar_linha_t_prefeitura3,
    "M": processar_linha_m,
}

_PRE_PROCESSADORES_MAP = {
    "prefeitura3": _pre_processar_prefeitura3,
}

_PROCESSADORES_MAP = {
    "prefeitura1": PROCESSADORES_prefeitura1,
    "prefeitura2": PROCESSADORES_prefeitura2,
    "prefeitura3": PROCESSADORES_prefeitura3,
}


# ============================================================
# FUNÇÃO CORE DE PROCESSAMENTO
# ============================================================


def processar(conteudo: str, sep: str = ";", prefeitura: str = None) -> dict:
    """
    Processa o conteúdo bruto e retorna:
        linhas  : list[str]  — linhas do TXT de saída
        stats   : dict       — contagens por tipo + ignoradas
        erros   : list[str]  — linhas com problema (não interrompem)
        sucesso : bool

    O parâmetro `prefeitura` seleciona regras específicas:
        None / 'geral'    → processamento padrão
        'prefeitura1'    → regras de Prefeitura 1
        'prefeitura2'         → regras de Prefeitura 2
        'prefeitura3'       → regras de prefeitura3 do Leste
    """
    # Normaliza acentos e ç → equivalentes ASCII (ex: ç→c, é→e, ã→a)
    conteudo = normalizar_texto(conteudo)

    # Pré-processamento específico por prefeitura
    if prefeitura and prefeitura in _PRE_PROCESSADORES_MAP:
        conteudo = _PRE_PROCESSADORES_MAP[prefeitura](conteudo)

    # Seleciona o conjunto de processadores
    procs = _PROCESSADORES_MAP.get(prefeitura, PROCESSADORES)
    buckets = {t: [] for t in ORDEM_SAIDA}
    stats = {t: 0 for t in ORDEM_SAIDA}
    stats["ignoradas"] = 0
    erros = []

    for num, linha in enumerate(conteudo.splitlines(), start=1):
        if not linha.strip():
            continue

        cols = linha.split(sep)
        tipo = cols[0].strip().upper() if len(cols) > 0 else ""

        if tipo not in procs:
            stats["ignoradas"] += 1
            continue

        try:
            buckets[tipo].append(procs[tipo](cols))
            stats[tipo] += 1
        except Exception as exc:
            erros.append(f"Linha {num} (tipo {tipo}): {exc}")

    saida = []
    for tipo in ORDEM_SAIDA:
        saida.extend(buckets[tipo])

    return {
        "linhas": saida,
        "stats": stats,
        "erros": erros,
        "sucesso": stats["F"] > 0,
    }


# ============================================================
# ROTAS DA API
# ============================================================


@app.route("/")
def index():
    """Serve o frontend."""
    return send_from_directory(".", "index.html")


@app.route("/api/processar", methods=["POST"])
def api_processar():
    """
    Recebe o arquivo ou texto, processa e retorna JSON com stats + prévia.

    Aceita multipart/form-data com:
        arquivo  : File   — arquivo CSV/TXT
        sep      : string — separador (padrão ";")
        encoding : string — encoding do arquivo (padrão "latin-1")

    OU application/json com:
        { "conteudo": "...", "sep": ";" }

    Retorna JSON:
        { sucesso, stats, erros, total_linhas, preview (primeiras 50 linhas) }
    """
    sep = ";"
    conteudo = ""
    prefeitura = None

    if request.content_type and "multipart" in request.content_type:
        sep = request.form.get("sep", ";")
        encoding = request.form.get("encoding", "latin-1")
        prefeitura = request.form.get("prefeitura") or None
        arquivo = request.files.get("arquivo")
        if not arquivo:
            return jsonify({"sucesso": False, "erro": "Nenhum arquivo enviado."}), 400
        try:
            conteudo = arquivo.read().decode(encoding, errors="replace")
        except Exception as e:
            return jsonify({"sucesso": False, "erro": f"Erro ao ler arquivo: {e}"}), 400

    elif request.is_json:
        dados = request.get_json(force=True)
        conteudo = dados.get("conteudo", "")
        sep = dados.get("sep", ";")
        prefeitura = dados.get("prefeitura") or None

    else:
        return jsonify({"sucesso": False, "erro": "Content-Type não suportado."}), 415

    if not conteudo.strip():
        return jsonify({"sucesso": False, "erro": "Conteúdo vazio."}), 400

    resultado = processar(conteudo, sep=sep, prefeitura=prefeitura)

    return jsonify(
        {
            "sucesso": resultado["sucesso"],
            "stats": resultado["stats"],
            "erros": resultado["erros"],
            "total_linhas": len(resultado["linhas"]),
            "preview": resultado["linhas"][:50],
        }
    )


@app.route("/api/download", methods=["POST"])
def api_download():
    """
    Recebe o arquivo ou texto, processa e retorna o TXT pronto para download.

    Mesmos parâmetros de /api/processar.
    """
    sep = ";"
    conteudo = ""
    nome_saida = "CONTRA_CHEQUE.txt"
    prefeitura = None

    if request.content_type and "multipart" in request.content_type:
        sep = request.form.get("sep", ";")
        encoding = request.form.get("encoding", "latin-1")
        nome_saida = request.form.get("nome_saida", nome_saida)
        prefeitura = request.form.get("prefeitura") or None
        arquivo = request.files.get("arquivo")
        if not arquivo:
            return jsonify({"sucesso": False, "erro": "Nenhum arquivo enviado."}), 400
        try:
            conteudo = arquivo.read().decode(encoding, errors="replace")
        except Exception as e:
            return jsonify({"sucesso": False, "erro": f"Erro ao ler arquivo: {e}"}), 400

    elif request.is_json:
        dados = request.get_json(force=True)
        conteudo = dados.get("conteudo", "")
        sep = dados.get("sep", ";")
        nome_saida = dados.get("nome_saida", nome_saida)
        prefeitura = dados.get("prefeitura") or None

    else:
        return jsonify({"sucesso": False, "erro": "Content-Type não suportado."}), 415

    if not conteudo.strip():
        return jsonify({"sucesso": False, "erro": "Conteúdo vazio."}), 400

    resultado = processar(conteudo, sep=sep, prefeitura=prefeitura)

    if not resultado["sucesso"]:
        return (
            jsonify(
                {
                    "sucesso": False,
                    "erro": "Nenhuma linha tipo F encontrada. Verifique o separador e o formato.",
                }
            ),
            422,
        )

    # Gera TXT com CRLF e BOM UTF-8
    txt = "\r\n".join(resultado["linhas"])
    conteudo_bytes = ("\ufeff" + txt).encode("utf-8")

    return send_file(
        io.BytesIO(conteudo_bytes),
        mimetype="text/plain; charset=utf-8",
        as_attachment=True,
        download_name=nome_saida,
    )


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


# ============================================================
# INICIALIZAÇÃO
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("  Contra Cheque — Servidor iniciado")
    print("  Acesse: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
