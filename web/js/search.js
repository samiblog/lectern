// 프로젝트 전체 본문 검색: 사이드바 '검색' 탭 (Ctrl+Shift+F). 서버가 선택된 프로젝트 탭에서 찾고(GET /api/search) 여기서 보여 준다.
// 결과 줄을 누르면 그 문서를 열고, 그 줄이 든 블록(data-lines)으로 가서 깜박이고, 문서 안 찾기로 검색어를 표시한다.
// 검색어와 결과는 프로젝트 탭마다 남겨 두었다가 그 탭을 고르면 되살린다 (tab.side.search).

import { S, on } from './store.js';
import { getJSON } from './api.js';
import { navigate } from './nav.js';
import { switchPanel } from './tree.js';
import { findText, pickMatchAt } from './find.js';
import { unfoldTo } from './fold.js';
import { flashBlock } from './diffmark.js';
import { $, esc, debounce, dirname, isHtml, keepFocus } from './util.js';

let query = '';     // 결과가 화면에 있는 검색어
let shown = null;   // 화면의 결과 (/api/search 의 답) — 탭을 바꿀 때 그 탭에 남긴다

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

function render(d) {
  shown = d;
  const docs = d.results.length;
  $('#lec-search-info').textContent = docs
    ? `문서 ${docs}개, ${d.total}곳${d.truncated ? ' (많아서 일부만 보입니다)' : ''}`
    : '찾은 곳이 없습니다';
  const box = $('#lec-search-results');
  keepFocus(box, () => { box.innerHTML = d.results.map((r) => {
    const name = r.title || r.path.split('/').pop();
    const head = `<div class="sr-doc" data-doc="${esc(r.path)}" title="${esc(r.path)}"><span class="label">${highlight(name, d.query)}</span>`
      + `${dirname(r.path) ? `<span class="sub">${esc(dirname(r.path))}</span>` : ''}</div>`;
    const hits = r.hits.map((h) => `<div class="sr-hit" data-doc="${esc(r.path)}" data-line="${h.line}" tabindex="0">`
      + `<span class="ln">${h.line}</span><span class="tx">${highlight(h.text, d.query)}</span></div>`).join('');
    return head + hits + (r.more ? '<div class="sr-more">이 문서에 더 있습니다</div>' : '');
  }).join(''); });
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
  query = q;
  $('#lec-search-info').textContent = '찾는 중…';
  let d;
  try {
    d = await getJSON(`/api/search?p=${encodeURIComponent(tab.id)}&q=${encodeURIComponent(q)}`);
  } catch (e) {
    if (q === query && tab === S.tab) $('#lec-search-info').textContent = `찾지 못했습니다: ${e.message}`;
    return;
  }
  if (q === query && tab === S.tab) render(d);   // 늦게 온 결과(다른 검색어·다른 탭)는 버린다
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

/** 검색 결과로 간다 */
async function openHit(path, line) {
  const here = S.view?.type === 'doc' && S.view.path === path;
  if (!here && !(await navigate({ type: 'doc', path }))) return;
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
    render(s.data);
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
    clear(input().value.trim() ? '찾는 중…' : '');
    later();
  });
  input().addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      later.cancel();
      if (query !== input().value.trim()) await run();   // 기다리는 중이면 바로 찾고 첫 결과로
      $('#lec-search-results .sr-hit')?.click();
    } else if (e.key === 'Escape' && input().value) {
      e.stopPropagation();
      input().value = '';
      run();
    }
  });
  $('#lec-search-results').addEventListener('click', (e) => {
    const row = e.target.closest('[data-doc]');
    if (row) openHit(row.dataset.doc, Number(row.dataset.line) || 0);
  });
  $('#lec-search-results').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.matches('.sr-hit')) e.target.click();
  });
  // 문서가 바뀌면(자동 새로고침) 결과도 다시 찾는다
  const again = debounce(() => run(true), 250);
  on('tree', () => { if (input().value.trim() && !$('#lec-search').hidden) again(); });
  on('tab', (t) => {
    later.cancel();
    again.cancel();
    onTab(t);
  });
}
