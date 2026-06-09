'use strict';

// ---- Global state -------------------------------------------------------

let allGroups    = [];        // flat array of all group objects from /api/data
let annotations  = {};        // {run_id: {qid: {page_rank_str: {sid: bool}}}}
let currentRunId = null;      // active run tab
let sessionIdx   = 0;         // index within getRunGroups(currentRunId)
let focusRow     = 0;         // focused sentence index within current session
let animating    = false;

// ---- Bootstrap ----------------------------------------------------------

async function init() {
  try {
    const [dataRes, annRes] = await Promise.all([
      fetch('/api/data'),
      fetch('/api/annotations'),
    ]);
    if (!dataRes.ok) {
      const err = await dataRes.json();
      throw new Error(err.error || 'Failed to load annotation_data.json');
    }
    const data = await dataRes.json();
    annotations = await annRes.json();
    allGroups   = data.groups;

    if (!allGroups.length) throw new Error('annotation_data.json has no groups.');

    // Determine first run
    const runs = uniqueRuns();
    currentRunId = runs[0];
    sessionIdx   = firstIncomplete(currentRunId);

    renderRunTabs();
    renderSession(null);
    renderProgress();

    show('app');
    hide('loading');
  } catch (err) {
    document.getElementById('error-msg').textContent = `Erreur : ${err.message}`;
    show('error-view');
    hide('loading');
  }
}

// ---- Data helpers -------------------------------------------------------

function uniqueRuns() {
  const seen = new Set();
  return allGroups.filter(g => seen.has(g.run_id) ? false : seen.add(g.run_id));
}

function getRunGroups(runId) {
  return allGroups.filter(g => g.run_id === runId);
}

function sessionAnn(group) {
  return ((annotations[group.run_id] || {})[group.qid] || {})[String(group.page_rank)] || {};
}

function isComplete(group) {
  const ann = sessionAnn(group);
  return group.sentences.every(s => s.sid in ann);
}

function firstIncomplete(runId) {
  const groups = getRunGroups(runId);
  const idx = groups.findIndex(g => !isComplete(g));
  return idx === -1 ? Math.max(groups.length - 1, 0) : idx;
}

function currentGroup() {
  return getRunGroups(currentRunId)[sessionIdx];
}

// ---- Rendering ----------------------------------------------------------

function renderRunTabs() {
  const container = document.getElementById('run-tabs');
  container.innerHTML = '';
  uniqueRuns().forEach(({ run_id }) => {
    const groups   = getRunGroups(run_id);
    const complete = groups.filter(isComplete).length;
    const btn = document.createElement('button');
    btn.className = 'run-tab' + (run_id === currentRunId ? ' active' : '');
    btn.dataset.run = run_id;
    btn.innerHTML   = `${run_id} <span class="tab-badge">${complete}/${groups.length}</span>`;
    btn.addEventListener('click', () => switchRun(run_id));
    container.appendChild(btn);
  });
}

function renderProgress() {
  const groups   = getRunGroups(currentRunId);
  const total    = groups.length;
  const done     = groups.filter(isComplete).length;
  const pct      = total ? Math.round(done / total * 100) : 0;
  document.getElementById('progress-label').textContent = `${done}/${total} sessions (${pct}%)`;
  document.getElementById('progress-bar').style.width   = `${pct}%`;
}

function renderSession(direction /* -1 | 1 | null */) {
  const group  = currentGroup();
  if (!group) return;

  const groups = getRunGroups(currentRunId);
  const total  = groups.length;

  // Nav label
  const done   = isComplete(group) ? '✓ ' : '';
  document.getElementById('session-label').textContent =
    `${done}Session ${sessionIdx + 1}/${total} — ${group.doc_name} p.${group.page_number}`;

  // Nav buttons
  document.getElementById('btn-prev').disabled = sessionIdx === 0;
  document.getElementById('btn-next').disabled = sessionIdx === total - 1;

  const html = buildSessionHTML(group, groups);
  const container = document.getElementById('session-content');

  if (direction !== null && !animating) {
    animating = true;
    container.style.opacity = '0';
    container.style.transform = direction > 0 ? 'translateX(40px)' : 'translateX(-40px)';

    setTimeout(() => {
      container.innerHTML = html;
      container.style.transition = 'none';
      container.style.opacity    = '0';
      container.style.transform  = direction > 0 ? 'translateX(-40px)' : 'translateX(40px)';

      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          container.style.transition = 'opacity .28s ease, transform .28s ease';
          container.style.opacity    = '1';
          container.style.transform  = 'translateX(0)';
          setTimeout(() => { animating = false; }, 300);
        });
      });
      focusRow = 0;
      highlightFocused();
    }, 220);
  } else {
    container.style.transition = '';
    container.style.opacity    = '1';
    container.style.transform  = '';
    container.innerHTML = html;
    focusRow = 0;
    highlightFocused();
  }
}

function buildSessionHTML(group, groups) {
  const ann      = sessionAnn(group);
  const decided  = group.sentences.filter(s => s.sid in ann).length;
  const allDone  = decided === group.sentences.length;
  const hasNext  = sessionIdx < groups.length - 1;

  const sentRows = group.sentences.map((s, i) => buildSentenceRow(s, i, ann)).join('');

  const completeBar = allDone ? buildCompleteBar(hasNext) : '';

  return `
    <div class="top-row">
      <div class="card">
        <div class="card-header">
          <span>Question</span>
          <span class="doc-pill">📄 ${esc(group.doc_name)} — p.${group.page_number}</span>
        </div>
        <div class="card-body">
          <p class="question-text">${esc(group.question)}</p>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span>Texte de la page</span>
          <span style="font-size:.75rem;font-weight:400">↕ scroll</span>
        </div>
        <div class="card-body">
          <pre class="page-text-box">${esc(group.page_text)}</pre>
        </div>
      </div>
    </div>

    <div class="card" id="sentences-card">
      <div class="card-header">
        <span>Phrases à annoter</span>
        <span class="sentence-progress" id="sent-progress">${decided}/${group.sentences.length} annotées</span>
      </div>
      <ul class="sentence-list" id="sentence-list">
        ${sentRows}
      </ul>
      ${completeBar}
    </div>`;
}

function buildSentenceRow(sent, idx, ann) {
  const decided = sent.sid in ann;
  const isYes   = ann[sent.sid] === true;
  const isNo    = ann[sent.sid] === false;

  let cls = 's-row';
  if (isYes) cls += ' decided-yes';
  if (isNo)  cls += ' decided-no';

  return `
    <li class="${cls}" data-sid="${esc(sent.sid)}" data-idx="${idx}">
      <span class="s-idx">s${idx}</span>
      <span class="s-text">${esc(sent.text)}</span>
      <span class="s-actions">
        <button class="btn-ann btn-yes${isYes ? ' selected' : ''}"
                data-sid="${esc(sent.sid)}" data-label="true"
                title="Attribué à cette page [O]">✓ Attribué</button>
        <button class="btn-ann btn-no${isNo ? ' selected' : ''}"
                data-sid="${esc(sent.sid)}" data-label="false"
                title="Non attribué [N]">✗ Non attribué</button>
      </span>
    </li>`;
}

function buildCompleteBar(hasNext) {
  const action = hasNext
    ? `<button class="btn-next-session" data-action="next-session">Session suivante →</button>`
    : `<span class="all-done-badge">✓ Toutes les sessions terminées !</span>`;

  return `
    <div class="complete-bar" id="complete-bar">
      ${action}
      <span class="shortcuts-hint">
        Naviguer : <kbd>↑↓</kbd> &nbsp; Attribué : <kbd>O</kbd>/<kbd>A</kbd> &nbsp;
        Non attribué : <kbd>N</kbd> &nbsp; Suivant : <kbd>→</kbd> ou <kbd>Enter</kbd>
      </span>
    </div>`;
}

// ---- Annotation ---------------------------------------------------------

async function handleAnnotate(sid, label) {
  const group = currentGroup();
  if (!group) return;

  // Update local state
  const rid = group.run_id;
  const pr  = String(group.page_rank);
  annotations[rid]  ??= {};
  annotations[rid][group.qid] ??= {};
  annotations[rid][group.qid][pr] ??= {};
  annotations[rid][group.qid][pr][sid] = label;

  // Update row appearance
  const row = document.querySelector(`[data-sid="${CSS.escape(sid)}"].s-row`);
  if (row) {
    row.classList.remove('decided-yes', 'decided-no', 'flash-yes', 'flash-no', 'focused');
    void row.offsetWidth; // reflow to restart animation
    row.classList.add(label ? 'decided-yes' : 'decided-no', label ? 'flash-yes' : 'flash-no');

    row.querySelectorAll('.btn-yes').forEach(b => b.classList.toggle('selected', label === true));
    row.querySelectorAll('.btn-no').forEach(b =>  b.classList.toggle('selected', label === false));
  }

  // Update sentence progress counter
  const ann      = sessionAnn(group);
  const decided  = group.sentences.filter(s => s.sid in ann).length;
  const el       = document.getElementById('sent-progress');
  if (el) el.textContent = `${decided}/${group.sentences.length} annotées`;

  // Reveal complete bar when all done
  if (decided === group.sentences.length) {
    const card = document.getElementById('sentences-card');
    if (card && !document.getElementById('complete-bar')) {
      const groups  = getRunGroups(currentRunId);
      const hasNext = sessionIdx < groups.length - 1;
      card.insertAdjacentHTML('beforeend', buildCompleteBar(hasNext));
    }
    renderProgress();
    renderRunTabs();
  }

  // Advance focus to next sentence
  const newFocus = group.sentences.findIndex((s, i) => i > focusRow && !(s.sid in ann));
  if (newFocus !== -1) {
    focusRow = newFocus;
    highlightFocused();
    scrollFocused();
  }

  // Persist (fire-and-forget)
  fetch('/api/annotate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      run_id: group.run_id, qid: group.qid,
      page_rank: group.page_rank, sid, label,
    }),
  }).catch(err => console.error('Save failed:', err));
}

// ---- Navigation ---------------------------------------------------------

function goToSession(newIdx, direction) {
  if (animating) return;
  const groups = getRunGroups(currentRunId);
  if (newIdx < 0 || newIdx >= groups.length) return;
  sessionIdx = newIdx;
  renderSession(direction);
  renderProgress();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function switchRun(runId) {
  if (runId === currentRunId) return;
  currentRunId = runId;
  sessionIdx   = firstIncomplete(runId);
  renderRunTabs();
  renderSession(null);
  renderProgress();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ---- Focus helpers ------------------------------------------------------

function highlightFocused() {
  document.querySelectorAll('.s-row').forEach(r => r.classList.remove('focused'));
  const row = document.querySelector(`.s-row[data-idx="${focusRow}"]`);
  if (row) row.classList.add('focused');
}

function scrollFocused() {
  const row = document.querySelector(`.s-row[data-idx="${focusRow}"]`);
  if (row) row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

// ---- Event delegation ---------------------------------------------------

document.addEventListener('click', e => {
  // Annotation buttons
  const btn = e.target.closest('.btn-ann');
  if (btn) {
    const sid   = btn.dataset.sid;
    const label = btn.dataset.label === 'true';
    if (sid) handleAnnotate(sid, label);
    return;
  }

  // Next-session button
  if (e.target.closest('[data-action="next-session"]')) {
    goToSession(sessionIdx + 1, 1);
    return;
  }

  // Row click → focus
  const row = e.target.closest('.s-row');
  if (row) {
    const idx = parseInt(row.dataset.idx, 10);
    if (!isNaN(idx)) { focusRow = idx; highlightFocused(); }
  }
});

document.getElementById('btn-prev').addEventListener('click', () => goToSession(sessionIdx - 1, -1));
document.getElementById('btn-next').addEventListener('click', () => goToSession(sessionIdx + 1,  1));

// ---- Keyboard -----------------------------------------------------------

document.addEventListener('keydown', e => {
  if (document.activeElement.tagName === 'INPUT' ||
      document.activeElement.tagName === 'TEXTAREA') return;

  const group = currentGroup();
  if (!group) return;
  const n = group.sentences.length;

  switch (e.key) {
    case 'ArrowDown':
    case 'j':
      e.preventDefault();
      focusRow = Math.min(focusRow + 1, n - 1);
      highlightFocused(); scrollFocused();
      break;

    case 'ArrowUp':
    case 'k':
      e.preventDefault();
      focusRow = Math.max(focusRow - 1, 0);
      highlightFocused(); scrollFocused();
      break;

    case 'o': case 'O':
    case 'a': case 'A': {
      const s = group.sentences[focusRow];
      if (s) handleAnnotate(s.sid, true);
      break;
    }

    case 'n': case 'N': {
      const s = group.sentences[focusRow];
      if (s) handleAnnotate(s.sid, false);
      break;
    }

    case 'ArrowRight':
    case 'Enter':
      if (isComplete(group)) goToSession(sessionIdx + 1, 1);
      break;

    case 'ArrowLeft':
      goToSession(sessionIdx - 1, -1);
      break;
  }
});

// ---- Utilities ----------------------------------------------------------

function esc(str) {
  return String(str ?? '')
    .replace(/&/g,  '&amp;')
    .replace(/</g,  '&lt;')
    .replace(/>/g,  '&gt;')
    .replace(/"/g,  '&quot;')
    .replace(/'/g,  '&#39;');
}

function show(id) { document.getElementById(id).classList.remove('hidden'); }
function hide(id) { document.getElementById(id).classList.add('hidden'); }

// ---- Start --------------------------------------------------------------
init();
