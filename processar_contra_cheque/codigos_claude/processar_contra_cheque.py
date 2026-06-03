"""
Processador de Contra Cheque - Backend Python
==============================================
Reproduz a lógica da macro MACRO_V2.xlsm em Python puro.

Responsabilidades:
  - Ler arquivo CSV/TXT com separador configurável
  - Separar linhas por tipo: F, P, D, T, M
  - Formatar campos (CPF, matrícula, datas, valores)
  - Remover letras de campos numéricos
  - Gerar arquivo TXT de saída no layout do sistema de RH

Uso via terminal:
    python processar_contra_cheque.py entrada.csv saida.txt
    python processar_contra_cheque.py entrada.csv saida.txt --sep ";"

Uso como módulo (para integrar com Flask/FastAPI):
    from processar_contra_cheque import processar
    resultado = processar(conteudo_str, sep=";")
    # resultado["linhas"] -> list[str]
    # resultado["stats"]  -> dict com contagens
    # resultado["erros"]  -> list[str]
"""

import re
import sys
import argparse
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def so_numeros(texto: str) -> str:
    """Remove tudo que não for dígito (0-9)."""
    return re.sub(r"[^0-9]", "", texto or "")


def remover_letras(texto: str) -> str:
    """Remove apenas letras A-Z/a-z, mantendo dígitos e pontuação."""
    return re.sub(r"[A-Za-z]", "", texto or "")


def formatar_cpf(valor: str) -> str:
    """Garante CPF com 11 dígitos, preenchendo zeros à esquerda."""
    return so_numeros(valor).zfill(11)


def formatar_matricula(valor: str) -> str:
    """Garante matrícula com 10 dígitos, preenchendo zeros à esquerda."""
    return so_numeros(valor).zfill(10)


def _serial_excel_para_data(serial: int) -> datetime:
    """Converte número serial do Excel para datetime Python."""
    # Excel conta a partir de 1900-01-00 (dia 0 = 1899-12-30)
    origem = datetime(1899, 12, 30)
    return origem + timedelta(days=serial)


def formatar_data(valor: str, formato: str) -> str:
    """
    Converte valor de data para o formato solicitado.

    Formatos suportados:
        "DD/MM/AAAA"  ->  "31/01/2024"
        "MM/AAAA"     ->  "01/2024"

    Entradas aceitas:
        "31/01/2024"  (DD/MM/AAAA)
        "2024-01-31"  (ISO)
        "45292"       (serial Excel)
        ""            (retorna vazio)
    """
    valor = (valor or "").strip()
    if not valor:
        return ""

    dt = None

    # Serial numérico do Excel
    if re.match(r"^\d{5,6}$", valor):
        try:
            dt = _serial_excel_para_data(int(valor))
        except Exception:
            return valor

    # Formato ISO: AAAA-MM-DD
    if dt is None and re.match(r"^\d{4}-\d{2}-\d{2}", valor):
        try:
            dt = datetime.strptime(valor[:10], "%Y-%m-%d")
        except ValueError:
            return valor

    # Formato DD/MM/AAAA
    if dt is None and re.match(r"^\d{1,2}/\d{1,2}/\d{4}", valor):
        try:
            dt = datetime.strptime(valor[:10], "%d/%m/%Y")
        except ValueError:
            return valor

    if dt is None:
        return valor  # devolve sem alteração se não reconheceu

    if formato == "DD/MM/AAAA":
        return dt.strftime("%d/%m/%Y")
    if formato == "MM/AAAA":
        return dt.strftime("%m/%Y")
    return valor


# ---------------------------------------------------------------------------
# Processamento por tipo de linha
# ---------------------------------------------------------------------------

def processar_linha_f(cols: list[str]) -> str:
    """
    Linha F — Ficha do funcionário.

    Colunas esperadas (índice 0-based, após split):
    0=F  1=CódEmp  2=CódSetor  3=CPF  4=Matrícula  5=Nome  6=CBO
    7=NomeEmpresa  8=NomeSetor  9=DtNasc  10=DtAdm  11=MêsAnoPgto
    12=Cargo  13=Lotação  14=CódLotação  15=CódVínculo  16=NomeVínculo
    17=Banco  18=Agência  19=ContaCorrente  20=PIS  21=RG
    22=Dependentes  23=PlanoCarreira
    """
    def c(i): return cols[i] if i < len(cols) else ""

    campos = [
        "F",
        c(1),                                   # Código Empresa
        c(2),                                   # Código Setor
        formatar_cpf(c(3)),                     # CPF 11 dígitos
        formatar_matricula(c(4)),               # Matrícula 10 dígitos
        c(5),                                   # Nome
        c(6),                                   # CBO
        c(7),                                   # Nome Empresa
        c(8),                                   # Nome Setor
        formatar_data(c(9),  "DD/MM/AAAA"),     # Data Nascimento
        formatar_data(c(10), "DD/MM/AAAA"),     # Data Admissão
        formatar_data(c(11), "MM/AAAA"),        # Mês/Ano Pagamento
        c(12),                                  # Cargo
        c(13),                                  # Lotação
        c(14),                                  # Código Lotação
        c(15),                                  # Código Vínculo
        c(16),                                  # Nome Vínculo
        c(17),                                  # Banco
        c(18),                                  # Agência
        c(19),                                  # Conta Corrente
        c(20),                                  # PIS
        c(21),                                  # RG
        "0",                                    # Dependentes (zerar)
        "0",                                    # Plano Carreira (zerar)
    ]
    return ";".join(campos)


def processar_linha_p(cols: list[str]) -> str:
    """
    Linha P — Proventos.

    0=P  1=CódEmp  2=CódSetor  3=CPF  4=Matrícula
    5=Código  6=Descrição  7=Referência  8=Valor
    """
    def c(i): return cols[i] if i < len(cols) else ""

    campos = [
        "P",
        c(1),                       # Código Empresa
        c(2),                       # Código Setor
        formatar_cpf(c(3)),         # CPF
        formatar_matricula(c(4)),   # Matrícula
        c(5),                       # Código
        c(6),                       # Descrição
        c(7),                       # Referência
        remover_letras(c(8)),       # Valor (sem letras)
    ]
    return ";".join(campos)


def processar_linha_d(cols: list[str]) -> str:
    """
    Linha D — Descontos.

    Mesma estrutura da Linha P.
    """
    def c(i): return cols[i] if i < len(cols) else ""

    campos = [
        "D",
        c(1),
        c(2),
        formatar_cpf(c(3)),
        formatar_matricula(c(4)),
        c(5),
        c(6),
        c(7),
        remover_letras(c(8)),
    ]
    return ";".join(campos)


def processar_linha_t(cols: list[str]) -> str:
    """
    Linha T — Totais.

    0=T  1=CódEmp  2=CódSetor  3=CPF  4=Matrícula
    5=TotalProventos  6=TotalDescontos  7=Líquido  8=SalárioBase
    9=SalárioContribInss  10=BaseFGTS  11=FGTSMes  12=BaseIRRF
    13=FaixaIRRF  14-18=MensagensIndividuais(1-5)
    """
    def c(i): return cols[i] if i < len(cols) else ""

    campos = [
        "T",
        c(1),
        c(2),
        formatar_cpf(c(3)),
        formatar_matricula(c(4)),
        remover_letras(c(5)),   # Total Proventos
        remover_letras(c(6)),   # Total Descontos
        remover_letras(c(7)),   # Líquido
        remover_letras(c(8)),   # Salário Base
        remover_letras(c(9)),   # Salário Contrib. INSS
        remover_letras(c(10)),  # Base FGTS
        remover_letras(c(11)),  # FGTS do Mês
        remover_letras(c(12)),  # Base IRRF
        remover_letras(c(13)),  # Faixa IRRF
        c(14),                  # Mensagem 1
        c(15),                  # Mensagem 2
        c(16),                  # Mensagem 3
        c(17),                  # Mensagem 4
        c(18),                  # Mensagem 5
    ]
    return ";".join(campos)


def processar_linha_m(cols: list[str]) -> str:
    """
    Linha M — Mensagem Geral.

    0=M  1=CódEmp  2=CódSetor  3=CPF  4=Matrícula
    5-9=MensagemGeral(1-5)
    """
    def c(i): return cols[i] if i < len(cols) else ""

    campos = [
        "M",
        c(1),
        c(2),
        formatar_cpf(c(3)),
        formatar_matricula(c(4)),
        c(5), c(6), c(7), c(8), c(9),
        "",   # campo extra (trailing ; como na macro original)
    ]
    return ";".join(campos)


# ---------------------------------------------------------------------------
# Função principal de processamento
# ---------------------------------------------------------------------------

PROCESSADORES = {
    "F": processar_linha_f,
    "P": processar_linha_p,
    "D": processar_linha_d,
    "T": processar_linha_t,
    "M": processar_linha_m,
}

ORDEM_SAIDA = ["F", "P", "D", "T", "M"]


def processar(conteudo: str, sep: str = ";") -> dict:
    """
    Processa o conteúdo bruto do arquivo base e retorna o resultado.

    Parâmetros:
        conteudo  : string completa do arquivo de entrada
        sep       : separador de colunas (padrão ";")

    Retorna dict com:
        linhas    : list[str]  — linhas do TXT de saída (sem quebra de linha)
        stats     : dict       — {"F": n, "P": n, "D": n, "T": n, "M": n, "ignoradas": n}
        erros     : list[str]  — descrições de linhas com problema (não interrompem)
        sucesso   : bool
    """
    buckets: dict[str, list[str]] = {t: [] for t in ORDEM_SAIDA}
    stats = {t: 0 for t in ORDEM_SAIDA}
    stats["ignoradas"] = 0
    erros: list[str] = []

    linhas_entrada = [l for l in conteudo.splitlines() if l.strip()]

    for num, linha in enumerate(linhas_entrada, start=1):
        cols = linha.split(sep)

        # O tipo está na coluna 1 (índice 1)
        tipo = (cols[1].strip().upper() if len(cols) > 1 else "").upper()

        if tipo not in PROCESSADORES:
            # Ignora cabeçalhos e linhas desconhecidas silenciosamente
            stats["ignoradas"] += 1
            continue

        try:
            linha_formatada = PROCESSADORES[tipo](cols)
            buckets[tipo].append(linha_formatada)
            stats[tipo] += 1
        except Exception as exc:
            erros.append(f"Linha {num} (tipo {tipo}): {exc}")

    # Monta saída na ordem correta: F → P → D → T → M
    saida: list[str] = []
    for tipo in ORDEM_SAIDA:
        saida.extend(buckets[tipo])

    return {
        "linhas": saida,
        "stats": stats,
        "erros": erros,
        "sucesso": stats["F"] > 0,
    }


def gerar_txt(linhas: list[str]) -> str:
    """Junta as linhas com CRLF (padrão Windows, como a macro original)."""
    return "\r\n".join(linhas)


# ---------------------------------------------------------------------------
# Interface de linha de comando
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Processador de Contra Cheque — converte arquivo base em TXT formatado."
    )
    parser.add_argument("entrada", help="Arquivo CSV/TXT de entrada")
    parser.add_argument("saida",   help="Arquivo TXT de saída")
    parser.add_argument("--sep",   default=";", help="Separador de colunas (padrão: ;)")
    parser.add_argument("--encoding-entrada", default="latin-1",
                        help="Encoding do arquivo de entrada (padrão: latin-1)")
    parser.add_argument("--encoding-saida", default="utf-8-sig",
                        help="Encoding do arquivo de saída (padrão: utf-8-sig — UTF-8 com BOM)")
    args = parser.parse_args()

    # Leitura
    try:
        with open(args.entrada, encoding=args.encoding_entrada, errors="replace") as f:
            conteudo = f.read()
    except FileNotFoundError:
        print(f"[ERRO] Arquivo não encontrado: {args.entrada}", file=sys.stderr)
        sys.exit(1)

    # Processamento
    resultado = processar(conteudo, sep=args.sep)

    if not resultado["sucesso"]:
        print("[ERRO] Nenhuma linha do tipo F encontrada. Verifique o separador e o formato.", file=sys.stderr)
        sys.exit(1)

    # Gravação
    txt_saida = gerar_txt(resultado["linhas"])
    with open(args.saida, "w", encoding=args.encoding_saida, newline="") as f:
        f.write(txt_saida)

    # Resumo
    s = resultado["stats"]
    print(f"✓ Processamento concluído!")
    print(f"  Funcionários (F) : {s['F']}")
    print(f"  Proventos    (P) : {s['P']}")
    print(f"  Descontos    (D) : {s['D']}")
    print(f"  Totais       (T) : {s['T']}")
    print(f"  Mensagens    (M) : {s['M']}")
    print(f"  Linhas geradas   : {len(resultado['linhas'])}")
    print(f"  Linhas ignoradas : {s['ignoradas']}")
    print(f"  Arquivo salvo em : {args.saida}")

    if resultado["erros"]:
        print(f"\n⚠ {len(resultado['erros'])} linha(s) com problema:")
        for e in resultado["erros"]:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
