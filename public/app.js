/* ═══════════════════════════════════════════════════════════════════════
   NOTA MIL · Plataforma — sem framework, sem build
   ═══════════════════════════════════════════════════════════════════════ */

const $ = (sel, raiz = document) => raiz.querySelector(sel);
const $$ = (sel, raiz = document) => Array.from(raiz.querySelectorAll(sel));

/* ─── Utilitários ────────────────────────────────────────────────────── */

function esc(txt) {
  const d = document.createElement('div');
  d.textContent = String(txt ?? '');
  return d.innerHTML;
}

function aviso(mensagem, tipo = 'info') {
  const box = $('#avisos');
  const el = document.createElement('div');
  el.className = `aviso aviso--${tipo}`;
  el.textContent = mensagem;
  box.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 300);
  }, 4200);
}

async function api(caminho, corpo) {
  const opts = corpo
    ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) }
    : { method: 'GET' };

  const res = await fetch(`/api${caminho}`, opts);
  let dados;
  try { dados = await res.json(); }
  catch { throw new Error('Resposta do servidor não é JSON válido.'); }

  if (!res.ok) throw new Error(dados.erro || `Erro HTTP ${res.status}`);
  return dados;
}

function corDaNota(n) {
  if (n >= 700) return 'n-alta';
  if (n >= 400) return 'n-media';
  return 'n-baixa';
}


/* ═══ ABAS ═══════════════════════════════════════════════════════════ */

$$('.aba').forEach(btn => {
  btn.addEventListener('click', () => {
    const alvo = btn.dataset.aba;
    $$('.aba').forEach(b => {
      const ativa = b === btn;
      b.classList.toggle('is-ativa', ativa);
      b.setAttribute('aria-selected', String(ativa));
    });
    $$('.painel').forEach(p => {
      const ativo = p.id === `painel-${alvo}`;
      p.classList.toggle('is-ativo', ativo);
      p.hidden = !ativo;
    });
    location.hash = alvo;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
});

// abre a aba do hash se houver
(function abrirDoHash() {
  const alvo = (location.hash || '').replace('#', '');
  if (['redacao', 'banco', 'gerar'].includes(alvo)) {
    $(`.aba[data-aba="${alvo}"]`)?.click();
  }
})();


/* ═══ MÓDULO 1 · REDAÇÃO ══════════════════════════════════════════════ */

const formRedacao = $('#form-redacao');
const texto = formRedacao.elements.texto;
const contador = $('#contador');

texto.addEventListener('input', () => {
  const t = texto.value;
  const palavras = t.trim() ? t.trim().split(/\s+/).length : 0;
  contador.textContent = `${palavras} palavra${palavras === 1 ? '' : 's'} · ${t.length} caractere${t.length === 1 ? '' : 's'}`;
});

formRedacao.addEventListener('submit', async (e) => {
  e.preventDefault();
  const dados = {
    tema: formRedacao.elements.tema.value.trim(),
    texto: formRedacao.elements.texto.value.trim(),
  };
  if (dados.texto.split(/\s+/).length < 50) {
    return aviso('A redação precisa ter pelo menos 50 palavras.', 'erro');
  }

  const btn = $('#btn-corrigir');
  btn.classList.add('is-carregando');
  btn.disabled = true;

  $('#resultado-redacao').innerHTML = `
    <div class="cartao">
      <div class="pensando"><i></i><i></i><i></i>A banca de IA está lendo sua redação…</div>
    </div>`;
  $('#resultado-redacao').scrollIntoView({ behavior: 'smooth', block: 'start' });

  try {
    const r = await api('/corrigir', dados);
    renderRedacao(r);
    aviso('Correção pronta.', 'ok');
  } catch (err) {
    $('#resultado-redacao').innerHTML = '';
    aviso(err.message, 'erro');
  } finally {
    btn.classList.remove('is-carregando');
    btn.disabled = false;
  }
});

function renderRedacao(r) {
  const cls = corDaNota(r.nota_final);
  const html = `
    <div class="res-nota">
      <span class="res-nota__lbl">Nota estimada</span>
      <div class="res-nota__num ${cls}">${r.nota_final}<small>/1000</small></div>
    </div>

    ${r.competencias.map(c => `
      <div class="comp">
        <div class="comp__topo">
          <div class="comp__nome">Competência ${c.numero}<span>${esc(c.titulo)}</span></div>
          <div class="comp__nota">${c.nota}<span style="color:var(--txt-3);font-weight:500;font-size:.75em">/200</span></div>
        </div>
        <div class="comp__barra"><i style="width:${(c.nota / 200) * 100}%"></i></div>
        <p class="comp__coment">${esc(c.comentario)}</p>
      </div>`).join('')}

    ${r.resumo ? `
      <div class="bloco bloco--info">
        <h3>🧭 Diagnóstico geral</h3>
        <p style="color:var(--txt-2);margin:0;line-height:1.6">${esc(r.resumo)}</p>
      </div>` : ''}

    ${r.pontos_fortes?.length ? `
      <div class="bloco bloco--ok">
        <h3>✅ Pontos fortes</h3>
        <ul>${r.pontos_fortes.map(p => `<li>${esc(p)}</li>`).join('')}</ul>
      </div>` : ''}

    ${r.pontos_a_melhorar?.length ? `
      <div class="bloco bloco--atn">
        <h3>⚠️ Pontos a melhorar</h3>
        <ul>${r.pontos_a_melhorar.map(p => `<li>${esc(p)}</li>`).join('')}</ul>
      </div>` : ''}

    ${r.reescritas?.length ? `
      <div class="cartao">
        <h3 class="cartao__titulo">✍️ Sugestões de reescrita</h3>
        <p class="cartao__texto" style="margin-bottom:1rem">Compare o que você escreveu com a versão sugerida.</p>
        ${r.reescritas.map(x => `
          <div class="reesc">
            <div class="reesc__antes"><b>Antes</b>${esc(x.trecho_original)}</div>
            <div class="reesc__depois"><b>Depois</b>${esc(x.sugestao)}</div>
            <div class="reesc__motivo">${esc(x.motivo)}</div>
          </div>`).join('')}
      </div>` : ''}
  `;
  $('#resultado-redacao').innerHTML = html;
}


/* ═══ MÓDULO 2 · BANCO DE QUESTÕES ════════════════════════════════════ */

let areaAtiva = '';
let questoesCache = [];
let gabaritosCache = {};

async function carregarBanco() {
  $('#banco-carregando').hidden = false;
  $('#banco-carregando').textContent = 'Carregando questões…';
  $('#banco-lista').innerHTML = '';

  try {
    const params = new URLSearchParams({
      limite: '10',
      embaralhar: '1',
      ...(areaAtiva ? { area: areaAtiva } : {}),
    });
    const r = await api(`/questoes?${params}`);
    questoesCache = r.questoes;
    gabaritosCache = r.gabaritos;
    $('#banco-carregando').hidden = true;
    renderBanco(r.questoes);
  } catch (err) {
    $('#banco-carregando').textContent = `Erro ao carregar questões: ${err.message}`;
  }
}

let bancoIndice = 0;

function renderBanco(qs) {
  bancoIndice = 0;
  mostrarQuestaoBanco();
}

function mostrarQuestaoBanco() {
  const qs = questoesCache;
  if (!qs.length) {
    $('#banco-lista').innerHTML = '<div class="cartao">Nenhuma questão nessa área.</div>';
    return;
  }
  const i = bancoIndice;
  const q = qs[i];
  $('#banco-lista').innerHTML = `
    <article class="questao" data-qid="${esc(q.id)}">
      <div class="questao__meta">
        <span>Questão ${i + 1} de ${qs.length}</span>
        <span>${esc(q.area)}</span>
        ${q.topico ? `<span>${esc(q.topico)}</span>` : ''}
      </div>
      <div class="questao__enun">${esc(q.enunciado)}</div>
      <div class="alt-lista">
        ${q.alternativas.map(a => `
          <button class="alt" data-letra="${a.letra}">
            <span class="alt__letra">${a.letra}</span>
            <span>${esc(a.texto)}</span>
          </button>`).join('')}
      </div>
      <div class="veredito-container"></div>
    </article>
    <div class="nav-questao">
      <button class="botao botao--secundario" id="btn-ant" ${i === 0 ? 'disabled' : ''}>← Anterior</button>
      <span class="nav-questao__contador">${i + 1} / ${qs.length}</span>
      <button class="botao botao--secundario" id="btn-prox" ${i === qs.length - 1 ? 'disabled' : ''}>Próxima →</button>
    </div>`;

  const art = $('.questao');
  $$('.alt', art).forEach(btn => {
    btn.addEventListener('click', () => responderBanco(art, q.id, btn.dataset.letra));
  });
  $('#btn-ant')?.addEventListener('click', () => { bancoIndice--; mostrarQuestaoBanco(); window.scrollTo({top:0, behavior:'smooth'}); });
  $('#btn-prox')?.addEventListener('click', () => { bancoIndice++; mostrarQuestaoBanco(); window.scrollTo({top:0, behavior:'smooth'}); });
}

function responderBanco(article, qid, letra) {
  if (article.dataset.respondida) return;
  article.dataset.respondida = '1';

  const gab = gabaritosCache[qid];
  if (!gab) return;

  $$('.alt', article).forEach(b => {
    b.disabled = true;
    if (b.dataset.letra === gab.gabarito) b.classList.add('certa');
    else if (b.dataset.letra === letra) b.classList.add('errada');
  });

  const acertou = letra === gab.gabarito;
  const box = $('.veredito-container', article);
  box.innerHTML = `
    <div class="veredito veredito--${acertou ? 'ok' : 'erro'}">
      <span aria-hidden="true">${acertou ? '✓' : '✗'}</span>
      <span>${acertou ? 'Resposta certa.' : `Gabarito: ${gab.gabarito}. Você marcou ${letra}.`}</span>
    </div>
    ${gab.explicacao ? `
      <div class="explicacao">
        <h4>Explicação</h4>
        <p>${esc(gab.explicacao)}</p>
      </div>` : ''}
  `;
}

$$('.chip[data-area]').forEach(chip => {
  chip.addEventListener('click', () => {
    $$('.chip[data-area]').forEach(c => c.classList.remove('is-ativa'));
    chip.classList.add('is-ativa');
    areaAtiva = chip.dataset.area;
    carregarBanco();
  });
});

$('#btn-recarregar').addEventListener('click', carregarBanco);

// carrega quando a aba for aberta pela primeira vez
let bancoIniciado = false;
$('.aba[data-aba="banco"]').addEventListener('click', () => {
  if (!bancoIniciado) {
    bancoIniciado = true;
    carregarBanco();
  }
});
// se abriu direto no hash #banco, carrega já
if (location.hash === '#banco') {
  bancoIniciado = true;
  carregarBanco();
}


/* ═══ MÓDULO 3 · GERAR COM IA ═════════════════════════════════════════ */

const SUGESTOES = {
  matematica: ['Funções do 2º grau', 'Progressão geométrica', 'Análise combinatória', 'Probabilidade condicional'],
  natureza:   ['Leis de Newton', 'Estequiometria', 'Genética mendeliana', 'Óptica geométrica'],
  humanas:    ['Era Vargas', 'Urbanização brasileira', 'Filosofia de Kant', 'Guerra Fria'],
  linguagens: ['Regência verbal', 'Funções da linguagem', 'Modernismo brasileiro', 'Figuras de linguagem'],
};

const formGerar = $('#form-gerar');
const selArea = formGerar.elements.area;
const inpTopico = formGerar.elements.topico;

function pintaSugestoes() {
  const lista = SUGESTOES[selArea.value] || [];
  $('#sugestoes').innerHTML = lista.length
    ? `<span class="sugestoes__lbl">Sugestões:</span>` +
      lista.map(t => `<button type="button" class="sug">${esc(t)}</button>`).join('')
    : '';
  $$('.sug').forEach(b => b.addEventListener('click', () => {
    inpTopico.value = b.textContent;
    inpTopico.focus();
  }));
}
selArea.addEventListener('change', pintaSugestoes);
pintaSugestoes();

formGerar.addEventListener('submit', async (e) => {
  e.preventDefault();
  const dados = {
    area: selArea.value,
    topico: inpTopico.value.trim(),
    quantidade: parseInt(formGerar.elements.quantidade.value, 10),
  };

  if (dados.topico.length < 3) return aviso('Descreva o tópico com pelo menos 3 caracteres.', 'erro');

  const btn = $('#btn-gerar');
  btn.classList.add('is-carregando');
  btn.disabled = true;

  $('#resultado-gerar').innerHTML = `
    <div class="cartao">
      <div class="pensando"><i></i><i></i><i></i>Elaborando questões sobre <b style="color:var(--txt);margin-left:4px">${esc(dados.topico)}</b>…</div>
    </div>`;
  $('#resultado-gerar').scrollIntoView({ behavior: 'smooth', block: 'start' });

  try {
    const r = await api('/gerar', dados);
    renderGeradas(r);
    aviso(`${r.questoes.length} questões inéditas criadas.`, 'ok');
  } catch (err) {
    $('#resultado-gerar').innerHTML = '';
    aviso(err.message, 'erro');
  } finally {
    btn.classList.remove('is-carregando');
    btn.disabled = false;
  }
});

function renderGeradas(r) {
  const html = r.questoes.map((q, i) => `
    <article class="questao" data-qid="${esc(q.id)}">
      <div class="questao__meta">
        <span>Questão ${i + 1}</span>
        <span>${esc(r.area)}</span>
        <span>${esc(r.topico)}</span>
      </div>
      <div class="questao__enun">${esc(q.enunciado)}</div>
      <div class="alt-lista">
        ${q.alternativas.map(a => `
          <button class="alt" data-letra="${a.letra}">
            <span class="alt__letra">${a.letra}</span>
            <span>${esc(a.texto)}</span>
          </button>`).join('')}
      </div>
      <div class="veredito-container"></div>
    </article>`).join('');

  $('#resultado-gerar').innerHTML = html;

  // atalho: guardo gabarito das geradas no dataset para reutilizar responderBanco()
  r.questoes.forEach(q => {
    gabaritosCache[q.id] = { gabarito: q.gabarito, explicacao: q.explicacao };
  });

  $$('#resultado-gerar .questao').forEach(art => {
    const qid = art.dataset.qid;
    $$('.alt', art).forEach(btn => {
      btn.addEventListener('click', () => responderBanco(art, qid, btn.dataset.letra));
    });
  });
}
