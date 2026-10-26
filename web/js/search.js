// 프로젝트 전체 검색: 사이드바 '검색' 탭 (Ctrl+Shift+F). 본문은 서버가 선택된 프로젝트 탭에서 찾고(GET /api/search) 여기서 보여 준다.
// '문서'·'코드'·'자료' 버튼으로 찾을 곳을 고른다 (설정 search_docs·search_code·search_others, D44·D50).
// 맨 위는 이름(문서는 제목도)에 검색어가 든 파일 — 고른 종류 모두, 자료는 이름으로만 찾는다 (D50 — 화면이 트리와 '코드'·'자료' 목록에서 찾는다).
// 그 아래 본문 결과: 문서 먼저, 그다음 '코드' 묶음. 이름 행은 others.js 의 bindFileRows (자료는 두 번 누르거나 Enter 로 연다).
// 결과 줄을 누르면 그 문서를 열고, 그 줄이 든 블록(data-lines)으로 가서 깜박이고, 문서 안 찾기로 검색어를 표시한다.
// 코드 결과는 코드 화면(codeview.js)의 그 줄로 간다.
// 검색어와 결과는 프로젝트 탭마다 남겨 두었다가 그 탭을 고르면 되살린다 (tab.side.search).

import { S, on, emit } from './store.js';
import { getJSON, saveConfig } from './api.js';
import { openTarget } from './doctabs.js';
import { switchPanel } from './tree.js';
import { findText, pickMatchAt } from './find.js';
import { unfoldTo } from './fold.js';
import { flashBlock } from './diffmark.js';
import { fileIcon, isCode } from './icons.js';
import { labelOf } from './tree.js';
import { loadOthers, otherFiles, bindFileRows, fileTip } from './others.js';
import { $, esc, debounce, dirname, basename, isHtml, keepFocus, middleClickOpens, openHow } from './util.js';
import { t } from './i18n.js';

const MAX_NAMES = 100;   // 이름이 맞는 파일을 보이는 수

let query = '';     // 결과가 화면에 있는 검색어
let shown = null;   // 화면의 결과 {d: /api/search 의 답, names: 이름이 맞는 파일} — 탭을 바꿀 때 그 탭에 남긴다
let nameRows = new Map();   // 화면의 이름 행: 경로 → 노드 (bindFileRows)

const input = () => $('#lec-search-input');

/** 글을 이스케이프하면서 검색어(대소문자 무시)를 <mark> 로 감싼다 */
function highlight(text, q) {
  if (!q) return esc(text);
  const low = text.toLowerCase();
  const needle = q.toLowerCase();
  let out = '';
  let from = 0;
  for (let at = low.indexOf(needle); at !== -1; at = low.indexOf(needle, from)) {
    out += `${esc(text.slice(from, at))}<mark>${esc(text.slice(at, at + needle.length))}</mark>`;
    from = at + needle.length;
  }
  return out + esc(text.slice(from));
}

function clear(info = '') {
  query = '';
  shown = null;
  $('#lec-search-info').textContent = info;
  $('#lec-search-results').innerHTML = '';
}

// 찾을 곳: 설정 search_docs·search_code·search_others (모두 기본 켜짐)
const wantDocs = () => S.config.search_docs !== false;
const wantCode = () => S.config.search_code !== false;
const wantOthers = () => S.config.search_others !== false;
const KINDS = [['#lec-search-docs', 'search_docs'], ['#lec-search-code', 'search_code'], ['#lec-search-others', 'search_others']];

function renderKinds() {
  for (const [id, key] of KINDS) {
    const on = S.config[key] !== false;
    $(id).classList.toggle('on', on);
    $(id).setAttribute('aria-pressed', String(on));
  }
}

/** 이름(문서는 제목도)에 검색어가 든 파일: 고른 종류에서, 이름이 검색어로 시작하는 것 먼저, 그다음 최근에 고친 것. {files, total} */
function nameHits(tab, q) {
  const needle = q.toLowerCase();
  const has = (s) => (s || '').toLowerCase().includes(needle);
  const out = wantDocs() ? tab.files.filter((f) => has(f.name) || has(f.title)) : [];
  if (wantCode() || wantOthers()) {
    for (const f of otherFiles(tab)) if ((isCode(f.name) ? wantCode() : wantOthers()) && has(f.name)) out.push(f);
  }
  const starts = (f) => ([f.name, f.title].some((s) => (s || '').toLowerCase().startsWith(needle)) ? 0 : 1);
  out.sort((a, b) => starts(a) - starts(b) || b.mtime - a.mtime);
  return { files: out.slice(0, MAX_NAMES), total: out.length };
}

function nameRow(f, q) {
  const has = (s) => (s || '').toLowerCase().includes(q.toLowerCase());
  const label = f.kind && !has(f.name) ? f.title : (f.kind ? labelOf(f) : f.name);   // 문서는 제목이 맞으면 제목
  const tip = f.kind ? [f.title, f.path].filter(Boolean).join('\n') : fileTip(f);
  return `<div class="sr-name" data-file="${esc(f.path)}" tabindex="0" title="${esc(tip)}">${fileIcon(f.name, f.kind)}`
    + `<span class="label">${highlight(label, q)}</span>${dirname(f.path) ? `<span class="sub">${esc(dirname(f.path))}</span>` : ''}</div>`;
}

function render(d, names = null) {
  shown = { d, names };
  const docs = d.docs ?? d.results.length;
  const code = d.code ?? 0;
  const found = [docs && t('문서 {n}개', { n: docs }), code && t('코드 {n}개', { n: code })].filter(Boolean).join('·');
  const info = [];
  if (names?.total) info.push(t('이름 {n}개', { n: names.total }));
  if (d.results.length) info.push(`${found}, ${t('{n}곳', { n: d.total })}${d.truncated ? t(' (많아서 일부만 보입니다)') : ''}`);
  $('#lec-search-info').textContent = info.length ? info.join(' · ') : t('찾은 곳이 없습니다');
  const box = $('#lec-search-results');
  let html = '';
  nameRows = new Map((names?.files || []).map((f) => [f.path, f]));
  if (names?.files.length) {
    html += `<p class="sr-group names">${t('이름이 맞는 파일')}<span class="n">${names.total}</span></p>`
      + names.files.map((f) => nameRow(f, d.query || query)).join('');
    if (names.total > names.files.length) html += `<div class="sr-more">${t('처음 {n}개만 보입니다', { n: names.files.length })}</div>`;
    if (docs) html += `<p class="sr-group">${t('문서 본문')}</p>`;
  }
  let codeHead = false;
  for (const r of d.results) {
    const isCode = r.kind === 'code';
    if (isCode && !codeHead && (docs || names?.files.length)) html += `<p class="sr-group">${t('코드')}</p>`;   // 문서 결과 아래에 '코드' 묶음
    codeHead ||= isCode;
    const name = r.title || basename(r.path);
    const kind = isCode ? ' data-kind="code"' : '';
    html += `<div class="sr-doc" data-doc="${esc(r.path)}"${kind} title="${esc(r.path)}">${isCode ? fileIcon(name) : ''}`
      + `<span class="label">${highlight(name, d.query)}</span>${dirname(r.path) ? `<span class="sub">${esc(dirname(r.path))}</span>` : ''}</div>`;
    html += r.hits.map((h) => `<div class="sr-hit" data-doc="${esc(r.path)}"${kind} data-line="${h.line}" tabindex="0">`
      + `<span class="ln">${h.line}</span><span class="tx">${highlight(h.text, d.query)}</span></div>`).join('');
    if (r.more) html += `<div class="sr-more">${isCode ? t('이 파일에 더 있습니다') : t('이 문서에 더 있습니다')}</div>`;
  }
  keepFocus(box, () => { box.innerHTML = html; });
}

/** again: 같은 검색어라도 다시 찾는다 (파일이 바뀌었을 때). 아니면 이미 결과가 있는 검색어는 건너뛴다 (Enter 뒤의 늦은 입력 처리) */
async function run(again = false) {
  const q = input().value.trim();
  if (!again && q && q === query && shown) return;
  const tab = S.tab;
  if (!q || !tab) {
    clear();
    return;
  }
  if (!wantDocs() && !wantCode() && !wantOthers()) {
    clear(t('찾을 곳(문서·코드·자료)을 고르세요'));
    return;
  }
  query = q;
  $('#lec-search-info').textContent = t('찾는 중…');
  let d = { query: q, results: [], total: 0, truncated: false, docs: 0, code: 0 };
  let names;
  try {
    // 본문은 서버에서 (자료는 본문을 찾지 않는다), 이름은 트리와 '코드'·'자료' 목록에서
    const body = wantDocs() || wantCode()
      ? getJSON(`/api/search?p=${encodeURIComponent(tab.id)}&q=${encodeURIComponent(q)}&docs=${wantDocs() ? 1 : 0}&code=${wantCode() ? 1 : 0}`)
      : null;
    if (wantCode() || wantOthers()) await loadOthers(tab);
    names = nameHits(tab, q);
    if (body) d = await body;
  } catch (e) {
    if (q === query && tab === S.tab) $('#lec-search-info').textContent = t('찾지 못했습니다: {error}', { error: e.message });
    return;
  }
  if (q === query && tab === S.tab) render(d, names);   // 늦게 온 결과(다른 검색어·다른 탭)는 버린다
}

/** 지금 문서에서 line 번째 원문 줄이 든 가장 작은 블록으로 간다. 그 블록(없으면 null) */
function goToLine(line) {
  let best = null;
  let size = Infinity;
  for (const el of $('#lec-view').querySelectorAll('[data-lines]')) {
    const [a, b] = el.dataset.lines.split('-').map(Number);
    if (a <= line && line <= b && b - a < size) {
      best = el;
      size = b - a;
    }
  }
  if (!best) return null;
  unfoldTo(best);
  best.scrollIntoView({ block: 'center' });
  flashBlock(best);
  return best;
}

/**
 * 검색 결과로 간다. code: 코드 결과 — 코드 화면의 그 줄로. how: 열 곳 (util.openHow — Ctrl+누르기는 새 문서 탭, 두 번 누르기는 첫 누르기가 연 것을
 * 새 문서 탭으로 — D64·D67. 다른 문서 탭에 열려 있으면 그 탭으로)
 */
async function openHit(path, line, code = false, how = {}) {
  if (line && S.pane?.editor?.path === path) {   // 편집 중인 파일 — 편집기가 그 줄로 (D55)
    emit('edit', { line });
    return;
  }
  if (code) {
    if (!(await openTarget({ type: 'code', path, line, ...how }))) return;
    findText(query);
    const row = line ? $(`#lec-view .cv-line[data-line="${line}"]`) : null;
    if (row) pickMatchAt(row);
    return;
  }
  const here = S.view?.type === 'doc' && S.view.path === path;
  if ((!here || how.twice) && !(await openTarget({ type: 'doc', path, ...how }))) return;
  if (isHtml(path)) {
    findText(query, { scroll: true });   // html 은 원문 줄과 화면 위치를 이을 수 없어 첫 결과로 간다
  } else {
    findText(query);
    const block = line ? goToLine(line) : null;
    if (block) pickMatchAt(block);   // 찾기 막대의 '지금 결과'도 그 줄의 것으로 (↓ 가 거기서 이어지게)
  }
}

/** 프로젝트 탭을 바꾸면: 앞 탭의 검색어·결과를 그 탭에 남기고, 새 탭의 것을 되살린다 */
function onTab({ tab, prev }) {
  if (prev && S.tabs.includes(prev)) {
    prev.side.search = { input: input().value, query, data: shown, scroll: $('#lec-search-results').scrollTop };
  }
  const s = tab?.side.search;
  input().value = s?.input || '';
  if (s?.data) {
    render(s.data.d, s.data.names);
    query = s.query;
    $('#lec-search-results').scrollTop = s.scroll;
  } else {
    clear();
    if (input().value.trim()) run();   // 찾는 중에 탭을 바꿨으면 다시 찾는다
  }
}

export function openSearch() {
  switchPanel('search');
  input().focus();
  input().select();
}

export function initSearch() {
  const later = debounce(run, 250);
  input().addEventListener('input', () => {
    // 앞 검색어의 결과를 바로 지운다 — 남아 있으면 Enter·클릭이 옛 결과를 연다
    clear(input().value.trim() ? t('찾는 중…') : '');
    later();
  });
  input().addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      later.cancel();
      if (query !== input().value.trim()) await run();   // 기다리는 중이면 바로 찾고 첫 결과로
      const hit = $('#lec-search-results .sr-hit');
      if (hit) hit.click();
      else $('#lec-search-results .sr-name')?.focus();   // 이름만 맞으면 첫 파일에 초점 (Enter 로 연다)
    } else if (e.key === 'Escape' && input().value) {
      e.stopPropagation();
      input().value = '';
      run();
    }
  });
  $('#lec-search-results').addEventListener('click', (e) => {
    const row = e.target.closest('[data-doc]');
    if (row) openHit(row.dataset.doc, Number(row.dataset.line) || 0, row.dataset.kind === 'code', openHow(e));
  });
  middleClickOpens($('#lec-search-results'), '[data-doc]');   // 가운데 버튼: 새 문서 탭 (D64)
  $('#lec-search-results').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.matches('.sr-hit')) e.target.click();
  });
  bindFileRows($('#lec-search-results'), (path) => nameRows.get(path));
  // 찾을 곳: '문서'·'코드'·'자료' 버튼 (모두 끄면 찾지 않고 고르라고 알린다)
  for (const [id, key] of KINDS) {
    $(id).addEventListener('click', async () => {
      await saveConfig({ [key]: S.config[key] === false });
      renderKinds();
      if (input().value.trim()) run(true);
    });
  }
  renderKinds();
  // 문서가 바뀌면(자동 새로고침) 결과도 다시 찾는다
  const again = debounce(() => run(true), 250);
  on('tree', () => { if (input().value.trim() && !$('#lec-search').hidden) again(); });
  on('others', () => { if (input().value.trim() && !$('#lec-search').hidden && (wantCode() || wantOthers())) again(); });   // 파일이 생기거나 지워짐
  on('titles', () => { if (shown) render(shown.d, shown.names); });
  on('tab', (tab) => {
    later.cancel();
    again.cancel();
    onTab(tab);
  });
}
