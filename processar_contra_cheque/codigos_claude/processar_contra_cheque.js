/**
 * Processador de Contra Cheque — Frontend JavaScript
 * ====================================================
 * Reproduz a lógica da macro MACRO_V2.xlsm em JavaScript puro.
 * Projetado para ser usado em uma aplicação web com qualquer framework
 * (React, Vue, Angular, Vanilla JS, etc).
 *
 * Responsabilidades:
 *   - Ler arquivo CSV/TXT via File API ou string colada
 *   - Separar linhas por tipo: F, P, D, T, M
 *   - Formatar campos (CPF, matrícula, datas, valores)
 *   - Remover letras de campos numéricos
 *   - Gerar string TXT de saída no layout do sistema de RH
 *   - Disparar download do arquivo no navegador
 *
 * Uso básico:
 *   import { processar, gerarTxt, downloadTxt } from './processar_contra_cheque.js';
 *
 *   const resultado = processar(conteudoString, { sep: ';' });
 *   if (resultado.sucesso) {
 *     downloadTxt(resultado.linhas, 'CONTRA CHEQUE.txt');
 *   }
 *
 * Uso com File API (input[type=file]):
 *   import { lerArquivo } from './processar_contra_cheque.js';
 *
 *   const conteudo = await lerArquivo(file, 'latin1');
 *   const resultado = processar(conteudo, { sep: ';' });
 */

'use strict';

// ---------------------------------------------------------------------------
// Utilitários
// ---------------------------------------------------------------------------

/**
 * Remove tudo que não for dígito (0-9).
 * @param {string} texto
 * @returns {string}
 */
export function soNumeros(texto) {
  return (texto ?? '').replace(/[^0-9]/g, '');
}

/**
 * Remove apenas letras A-Z/a-z, mantendo dígitos e pontuação.
 * @param {string} texto
 * @returns {string}
 */
export function removerLetras(texto) {
  return (texto ?? '').replace(/[A-Za-z]/g, '');
}

/**
 * Garante CPF com 11 dígitos, preenchendo zeros à esquerda.
 * @param {string} valor
 * @returns {string}
 */
export function formatarCpf(valor) {
  return soNumeros(valor).padStart(11, '0');
}

/**
 * Garante matrícula com 10 dígitos, preenchendo zeros à esquerda.
 * @param {string} valor
 * @returns {string}
 */
export function formatarMatricula(valor) {
  return soNumeros(valor).padStart(10, '0');
}

/**
 * Converte número serial do Excel para objeto Date.
 * @param {number} serial
 * @returns {Date}
 */
function serialExcelParaDate(serial) {
  // Excel conta a partir de 1900-01-00 (dia 0 = 1899-12-30)
  const origem = new Date(Date.UTC(1899, 11, 30));
  return new Date(origem.getTime() + serial * 86400000);
}

/**
 * Converte valor de data para o formato solicitado.
 *
 * Formatos suportados:
 *   "DD/MM/AAAA"  ->  "31/01/2024"
 *   "MM/AAAA"     ->  "01/2024"
 *
 * Entradas aceitas:
 *   "31/01/2024"  (DD/MM/AAAA)
 *   "2024-01-31"  (ISO)
 *   "45292"       (serial Excel)
 *   ""            (retorna vazio)
 *
 * @param {string} valor
 * @param {'DD/MM/AAAA'|'MM/AAAA'} formato
 * @returns {string}
 */
export function formatarData(valor, formato) {
  valor = (valor ?? '').trim();
  if (!valor) return '';

  let dt = null;

  // Serial numérico do Excel (5 ou 6 dígitos)
  if (/^\d{5,6}$/.test(valor)) {
    dt = serialExcelParaDate(parseInt(valor, 10));
  }

  // Formato ISO: AAAA-MM-DD
  if (!dt && /^\d{4}-\d{2}-\d{2}/.test(valor)) {
    dt = new Date(valor.slice(0, 10) + 'T00:00:00Z');
  }

  // Formato DD/MM/AAAA
  if (!dt && /^\d{1,2}\/\d{1,2}\/\d{4}/.test(valor)) {
    const [d, m, y] = valor.split('/');
    dt = new Date(Date.UTC(parseInt(y), parseInt(m) - 1, parseInt(d)));
  }

  if (!dt || isNaN(dt.getTime())) return valor;

  const d  = String(dt.getUTCDate()).padStart(2, '0');
  const m  = String(dt.getUTCMonth() + 1).padStart(2, '0');
  const y  = dt.getUTCFullYear();

  if (formato === 'DD/MM/AAAA') return `${d}/${m}/${y}`;
  if (formato === 'MM/AAAA')    return `${m}/${y}`;
  return valor;
}

// ---------------------------------------------------------------------------
// Processamento por tipo de linha
// ---------------------------------------------------------------------------

/**
 * Retorna o valor da coluna pelo índice, ou '' se não existir.
 * @param {string[]} cols
 * @param {number} i
 * @returns {string}
 */
function c(cols, i) {
  return cols[i] ?? '';
}

/**
 * Linha F — Ficha do funcionário.
 *
 * Colunas esperadas (índice 0-based, após split):
 * 0=F  1=CódEmp  2=CódSetor  3=CPF  4=Matrícula  5=Nome  6=CBO
 * 7=NomeEmpresa  8=NomeSetor  9=DtNasc  10=DtAdm  11=MêsAnoPgto
 * 12=Cargo  13=Lotação  14=CódLotação  15=CódVínculo  16=NomeVínculo
 * 17=Banco  18=Agência  19=ContaCorrente  20=PIS  21=RG
 * 22=Dependentes  23=PlanoCarreira
 *
 * @param {string[]} cols
 * @returns {string}
 */
export function processarLinhaF(cols) {
  return [
    'F',
    c(cols, 1),                                 // Código Empresa
    c(cols, 2),                                 // Código Setor
    formatarCpf(c(cols, 3)),                    // CPF 11 dígitos
    formatarMatricula(c(cols, 4)),              // Matrícula 10 dígitos
    c(cols, 5),                                 // Nome
    c(cols, 6),                                 // CBO
    c(cols, 7),                                 // Nome Empresa
    c(cols, 8),                                 // Nome Setor
    formatarData(c(cols, 9),  'DD/MM/AAAA'),   // Data Nascimento
    formatarData(c(cols, 10), 'DD/MM/AAAA'),   // Data Admissão
    formatarData(c(cols, 11), 'MM/AAAA'),      // Mês/Ano Pagamento
    c(cols, 12),                                // Cargo
    c(cols, 13),                                // Lotação
    c(cols, 14),                                // Código Lotação
    c(cols, 15),                                // Código Vínculo
    c(cols, 16),                                // Nome Vínculo
    c(cols, 17),                                // Banco
    c(cols, 18),                                // Agência
    c(cols, 19),                                // Conta Corrente
    c(cols, 20),                                // PIS
    c(cols, 21),                                // RG
    '0',                                        // Dependentes (zerar)
    '0',                                        // Plano Carreira (zerar)
  ].join(';');
}

/**
 * Linha P — Proventos.
 *
 * 0=P  1=CódEmp  2=CódSetor  3=CPF  4=Matrícula
 * 5=Código  6=Descrição  7=Referência  8=Valor
 *
 * @param {string[]} cols
 * @returns {string}
 */
export function processarLinhaP(cols) {
  return [
    'P',
    c(cols, 1),                     // Código Empresa
    c(cols, 2),                     // Código Setor
    formatarCpf(c(cols, 3)),        // CPF
    formatarMatricula(c(cols, 4)),  // Matrícula
    c(cols, 5),                     // Código
    c(cols, 6),                     // Descrição
    c(cols, 7),                     // Referência
    removerLetras(c(cols, 8)),      // Valor (sem letras)
  ].join(';');
}

/**
 * Linha D — Descontos.
 *
 * Mesma estrutura da Linha P.
 *
 * @param {string[]} cols
 * @returns {string}
 */
export function processarLinhaD(cols) {
  return [
    'D',
    c(cols, 1),
    c(cols, 2),
    formatarCpf(c(cols, 3)),
    formatarMatricula(c(cols, 4)),
    c(cols, 5),
    c(cols, 6),
    c(cols, 7),
    removerLetras(c(cols, 8)),
  ].join(';');
}

/**
 * Linha T — Totais.
 *
 * 0=T  1=CódEmp  2=CódSetor  3=CPF  4=Matrícula
 * 5=TotalProventos  6=TotalDescontos  7=Líquido  8=SalárioBase
 * 9=SalárioContribInss  10=BaseFGTS  11=FGTSMes  12=BaseIRRF
 * 13=FaixaIRRF  14-18=MensagensIndividuais(1-5)
 *
 * @param {string[]} cols
 * @returns {string}
 */
export function processarLinhaT(cols) {
  return [
    'T',
    c(cols, 1),
    c(cols, 2),
    formatarCpf(c(cols, 3)),
    formatarMatricula(c(cols, 4)),
    removerLetras(c(cols, 5)),    // Total Proventos
    removerLetras(c(cols, 6)),    // Total Descontos
    removerLetras(c(cols, 7)),    // Líquido
    removerLetras(c(cols, 8)),    // Salário Base
    removerLetras(c(cols, 9)),    // Salário Contrib. INSS
    removerLetras(c(cols, 10)),   // Base FGTS
    removerLetras(c(cols, 11)),   // FGTS do Mês
    removerLetras(c(cols, 12)),   // Base IRRF
    removerLetras(c(cols, 13)),   // Faixa IRRF
    c(cols, 14),                  // Mensagem 1
    c(cols, 15),                  // Mensagem 2
    c(cols, 16),                  // Mensagem 3
    c(cols, 17),                  // Mensagem 4
    c(cols, 18),                  // Mensagem 5
  ].join(';');
}

/**
 * Linha M — Mensagem Geral.
 *
 * 0=M  1=CódEmp  2=CódSetor  3=CPF  4=Matrícula
 * 5-9=MensagemGeral(1-5)
 *
 * @param {string[]} cols
 * @returns {string}
 */
export function processarLinhaM(cols) {
  return [
    'M',
    c(cols, 1),
    c(cols, 2),
    formatarCpf(c(cols, 3)),
    formatarMatricula(c(cols, 4)),
    c(cols, 5),
    c(cols, 6),
    c(cols, 7),
    c(cols, 8),
    c(cols, 9),
    '',   // campo extra (trailing ; como na macro original)
  ].join(';');
}

// ---------------------------------------------------------------------------
// Mapa de processadores e ordem de saída
// ---------------------------------------------------------------------------

const PROCESSADORES = {
  F: processarLinhaF,
  P: processarLinhaP,
  D: processarLinhaD,
  T: processarLinhaT,
  M: processarLinhaM,
};

const ORDEM_SAIDA = ['F', 'P', 'D', 'T', 'M'];

// ---------------------------------------------------------------------------
// Função principal de processamento
// ---------------------------------------------------------------------------

/**
 * Processa o conteúdo bruto do arquivo base e retorna o resultado.
 *
 * @param {string} conteudo   String completa do arquivo de entrada
 * @param {object} [opcoes]
 * @param {string} [opcoes.sep=';']   Separador de colunas
 *
 * @returns {{
 *   linhas:  string[],
 *   stats:   { F: number, P: number, D: number, T: number, M: number, ignoradas: number },
 *   erros:   string[],
 *   sucesso: boolean
 * }}
 */
export function processar(conteudo, { sep = ';' } = {}) {
  /** @type {Record<string, string[]>} */
  const buckets = { F: [], P: [], D: [], T: [], M: [] };
  const stats   = { F: 0, P: 0, D: 0, T: 0, M: 0, ignoradas: 0 };
  const erros   = [];

  const linhasEntrada = conteudo
    .split(/\r?\n/)
    .filter(l => l.trim());

  linhasEntrada.forEach((linha, idx) => {
    const cols = linha.split(sep);
    const tipo = (cols[1] ?? '').trim().toUpperCase();

    if (!PROCESSADORES[tipo]) {
      stats.ignoradas++;
      return;
    }

    try {
      const linhaFormatada = PROCESSADORES[tipo](cols);
      buckets[tipo].push(linhaFormatada);
      stats[tipo]++;
    } catch (err) {
      erros.push(`Linha ${idx + 1} (tipo ${tipo}): ${err.message}`);
    }
  });

  // Monta saída na ordem correta: F → P → D → T → M
  const saida = ORDEM_SAIDA.flatMap(tipo => buckets[tipo]);

  return {
    linhas:  saida,
    stats,
    erros,
    sucesso: stats.F > 0,
  };
}

// ---------------------------------------------------------------------------
// Geração e download do TXT
// ---------------------------------------------------------------------------

/**
 * Junta as linhas com CRLF (padrão Windows, como a macro original).
 * @param {string[]} linhas
 * @returns {string}
 */
export function gerarTxt(linhas) {
  return linhas.join('\r\n');
}

/**
 * Dispara o download do TXT no navegador.
 *
 * @param {string[]} linhas
 * @param {string}   [nomeArquivo='CONTRA CHEQUE.txt']
 * @param {string}   [encoding='utf-8-sig']   'utf-8-sig' inclui BOM (compatível com Excel/Notepad)
 */
export function downloadTxt(linhas, nomeArquivo = 'CONTRA CHEQUE.txt') {
  const conteudo = '\uFEFF' + gerarTxt(linhas); // BOM UTF-8
  const blob = new Blob([conteudo], { type: 'text/plain;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = nomeArquivo;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Leitura de arquivo via File API
// ---------------------------------------------------------------------------

/**
 * Lê um File do input[type=file] e retorna o conteúdo como string.
 *
 * @param {File}   file
 * @param {string} [encoding='latin1']   Encoding do arquivo (latin1 é o mais comum em sistemas BR)
 * @returns {Promise<string>}
 */
export function lerArquivo(file, encoding = 'latin1') {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = e => resolve(e.target.result);
    reader.onerror = () => reject(new Error('Falha ao ler o arquivo.'));
    reader.readAsText(file, encoding);
  });
}

// ---------------------------------------------------------------------------
// Exemplo de uso (Vanilla JS — descomente para testar)
// ---------------------------------------------------------------------------
//
// document.getElementById('btn-processar').addEventListener('click', async () => {
//   const fileInput = document.getElementById('arquivo');
//   const file = fileInput.files[0];
//   if (!file) { alert('Selecione um arquivo.'); return; }
//
//   const conteudo  = await lerArquivo(file, 'latin1');
//   const resultado = processar(conteudo, { sep: ';' });
//
//   if (!resultado.sucesso) {
//     alert('Nenhuma linha tipo F encontrada. Verifique o separador.');
//     return;
//   }
//
//   console.log('Stats:', resultado.stats);
//   console.log('Erros:', resultado.erros);
//
//   downloadTxt(resultado.linhas, 'CONTRA CHEQUE.txt');
// });
