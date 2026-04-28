const els = {
  documentName: document.getElementById('document-name'),
  chunking: document.getElementById('chunking'),
  topK: document.getElementById('top-k'),
  question: document.getElementById('question'),
  indexButton: document.getElementById('index-button'),
  clearButton: document.getElementById('clear-button'),
  reindexButton: document.getElementById('reindex-button'),
  sendButton: document.getElementById('send-button'),
  statusBadge: document.getElementById('ingest-status'),
  chunksCount: document.getElementById('stat-chunks'),
  documentStat: document.getElementById('stat-document'),
  modelStat: document.getElementById('stat-model'),
  embeddingStat: document.getElementById('stat-embedding'),
  chatScroll: document.getElementById('chat-scroll'),
  contextList: document.getElementById('context-list'),
  contextTopK: document.getElementById('context-top-k'),
  sessionMeta: document.getElementById('session-meta')
};

function escapeHtml(value = '') {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function setStatus(text, tone = 'default') {
  els.statusBadge.textContent = text;
  els.statusBadge.classList.remove('success', 'warning', 'error');
  if (tone !== 'default') els.statusBadge.classList.add(tone);
}

function ajustarAlturaPergunta() {
  if (!els.question) return;

  const alturaMaximaVar = getComputedStyle(document.documentElement)
    .getPropertyValue('--composer-max-height')
    .trim();
  const alturaMaxima = Number.parseInt(alturaMaximaVar, 10) || 120;

  els.question.style.height = 'auto';
  const alturaConteudo = els.question.scrollHeight;
  const alturaIdeal = Math.min(alturaConteudo, alturaMaxima);
  els.question.style.height = `${alturaIdeal}px`;
  els.question.style.overflowY = alturaConteudo > alturaMaxima ? 'auto' : 'hidden';
}

function appendUserMessage(text) {
  const article = document.createElement('article');
  article.className = 'message user-message';
  article.innerHTML = `
    <p class="message-label">Você</p>
    <div class="bubble user-bubble"><p>${escapeHtml(text)}</p></div>
  `;
  els.chatScroll.appendChild(article);
  els.chatScroll.scrollTop = els.chatScroll.scrollHeight;
}

function appendAssistantMessage(text, estrategia) {
  const article = document.createElement('article');
  article.className = 'message assistant-message';
  article.innerHTML = `
    <div class="assistant-head">
      <div class="assistant-chip">R</div>
      <div>
        <p class="message-label">RAG Engine</p>
        <p class="message-meta">Consulta concluída · Estratégia: ${escapeHtml(estrategia)}</p>
      </div>
    </div>
    <div class="bubble assistant-bubble"><p>${escapeHtml(text)}</p></div>
  `;
  els.chatScroll.appendChild(article);
  els.chatScroll.scrollTop = els.chatScroll.scrollHeight;
}

function renderContexts(fontes = []) {
  els.contextList.innerHTML = '';
  if (!fontes.length) {
    els.contextList.innerHTML = '<p class="empty-copy">Nenhuma fonte recuperada ainda.</p>';
    return;
  }

  fontes.forEach((fonte, index) => {
    const meta = fonte.metadados || {};
    const score = fonte.score ? `${Math.round(fonte.score * 100)}% match` : 'score indisponível';
    const card = document.createElement('section');
    card.className = index === 0 ? 'context-card' : 'context-card muted';
    card.innerHTML = `
      <div class="context-card-head">
        <span class="citation-tag">Fonte ${index + 1}</span>
        <span class="confidence">${escapeHtml(score)}</span>
      </div>
      <h3>${escapeHtml(meta.fonte || 'Documento')}</h3>
      <p class="context-section">Chunk ${escapeHtml(String(meta.chunk_index ?? 'N/A'))} · ${escapeHtml(meta.estrategia || 'N/A')}</p>
      <p class="context-snippet">${escapeHtml(fonte.texto || '')}</p>
    `;
    els.contextList.appendChild(card);
  });
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.mensagem || 'Erro inesperado na API.');
  return data;
}

async function carregarStatus() {
  try {
    const data = await fetchJSON('/api/health');
    els.chunksCount.textContent = data.total_chunks ?? 0;
    els.documentStat.textContent = (data.total_chunks ?? 0) > 0 ? '1 ativo' : '0 ativo';
    els.modelStat.textContent = 'gpt-4o-mini';
    els.embeddingStat.textContent = 'text-embedding-3-small';
    setStatus(data.total_chunks > 0 ? 'Indexado' : 'Pronto', data.total_chunks > 0 ? 'success' : 'default');
  } catch (error) {
    setStatus('Erro', 'error');
  }
}

async function indexarDocumento() {
  setStatus('Indexando...', 'warning');
  try {
    const data = await fetchJSON('/api/indexar', {
      method: 'POST',
      body: JSON.stringify({
        arquivo: els.documentName.value.trim(),
        estrategia: els.chunking.value
      })
    });

    els.chunksCount.textContent = data.total_chunks ?? 0;
    els.documentStat.textContent = data.arquivo || els.documentName.value.trim();
    els.sessionMeta.textContent = `Base pronta · Estratégia ativa: ${els.chunking.value}`;
    setStatus(data.status === 'ja_indexado' ? 'Já indexado' : 'Indexado', 'success');
  } catch (error) {
    setStatus('Falha', 'error');
    alert(error.message);
  }
}

async function limparBase() {
  setStatus('Limpando...', 'warning');
  try {
    await fetchJSON('/api/limpar', { method: 'POST', body: JSON.stringify({}) });
    els.chunksCount.textContent = '0';
    els.documentStat.textContent = '0 ativo';
    els.contextList.innerHTML = '<p class="empty-copy">Base limpa. Indexe um documento para consultar.</p>';
    setStatus('Base limpa', 'success');
  } catch (error) {
    setStatus('Falha', 'error');
    alert(error.message);
  }
}

async function consultar() {
  const pergunta = els.question.value.trim();
  if (!pergunta) {
    alert('Digite uma pergunta antes de consultar.');
    return;
  }

  appendUserMessage(pergunta);
  els.question.value = '';
  ajustarAlturaPergunta();
  els.sendButton.disabled = true;
  setStatus('Consultando...', 'warning');

  const loadingEl = document.createElement('article');
  loadingEl.className = 'message assistant-message message--loading';
  loadingEl.id = 'loading-indicator';
  loadingEl.innerHTML = `
    <div class="assistant-head">
      <div class="assistant-chip">R</div>
      <div>
        <p class="message-label">RAG Engine</p>
        <p class="message-meta">Gerando resposta...</p>
      </div>
    </div>
    <div class="bubble assistant-bubble loading-bubble">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>
  `;
  els.chatScroll.appendChild(loadingEl);
  els.chatScroll.scrollTop = els.chatScroll.scrollHeight;

  try {
    const data = await fetchJSON('/api/consultar', {
      method: 'POST',
      body: JSON.stringify({
        pergunta,
        k: Number(els.topK.value || 3)
      })
    });

    document.getElementById('loading-indicator')?.remove();
    appendAssistantMessage(data.resposta, els.chunking.value);
    renderContexts(data.fontes || []);
    els.contextTopK.textContent = `Top ${data.total_fontes || 0}`;
    setStatus('Resposta gerada', 'success');
  } catch (error) {
    document.getElementById('loading-indicator')?.remove();
    appendAssistantMessage(error.message, els.chunking.value);
    setStatus('Falha', 'error');
  } finally {
    els.sendButton.disabled = false;
  }
}

els.indexButton?.addEventListener('click', indexarDocumento);
els.clearButton?.addEventListener('click', limparBase);
els.reindexButton?.addEventListener('click', indexarDocumento);
els.sendButton?.addEventListener('click', consultar);
els.question?.addEventListener('input', ajustarAlturaPergunta);
els.question?.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    consultar();
  }
});

ajustarAlturaPergunta();

carregarStatus();

// Painel de contexto retrátil
(function () {
  const appShell = document.querySelector('.app-shell');
  const panel = document.getElementById('context-panel');
  const toggle = document.getElementById('context-toggle');
  if (!appShell || !panel || !toggle) return;

  toggle.addEventListener('click', () => {
    const collapsed = panel.classList.toggle('context-panel--collapsed');
    appShell.classList.toggle('app-shell--context-collapsed', collapsed);
    toggle.setAttribute('aria-expanded', String(!collapsed));
    toggle.setAttribute('aria-label', collapsed ? 'Expandir painel de contexto' : 'Recolher painel de contexto');
  });
})();