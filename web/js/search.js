// 프로젝트 전체 본문 검색: 사이드바 '검색' 탭 (Ctrl+Shift+F). 서버가 찾고(GET /api/search) 여기서 보여 준다.
// 결과 줄을 누르면 그 문서를 열고, 그 줄이 든 블록(data-lines)으로 가서 깜박이고, 문서 안 찾기로 검색어를 표시한다.

import { S, on } from './store.js';
import { getJSON } from './api.js';
import { navigate } from './nav.js';
import { switchTab } from './tree.js';
import { findText } from './find.js';
import { unfoldTo } from './fold.js';
import { flashBlock } from './diffmark.js';
import { $, esc, debounce, dirname } from './util.js';

let query = '';    // 결과가 화면에 있는 검색어

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

function render(d) {
  const docs = d.results.length;
  $('#lec-search-info').textContent = docs
    ? `${docs}개 문서, ${d.total}곳${d.truncated ? ' (많아서 일부만 보입니다)' : ''}`
    : '찾은 곳이 없습니다';
  $('#lec-search-results').innerHTML = d.results.map((r) => {
    const name = r.title || r.path.split('/').pop();
    const head = `<div class="sr-doc" data-doc="${esc(r.path)}" title="${esc(r.path)}"><span class="label">${highlight(name, d.query)}</span>`
      + `${dirname(r.path) ? `<span class="sub">${esc(dirname(r.path))}</span>` : ''}</div>`;
    const hits = r.hits.map((h) => `<div class="sr-hit" data-doc="${esc(r.path)}" data-line="${h.line}" tabindex="0">`
      + `<span class="ln">${h.line}</span><span class="tx">${highlight(h.text, d.query)}</span></div>`).join('');
    return head + hits + (r.more ? '<div class="sr-more">이 문서에 더 있습니다</div>' : '');
  }).join('');
}

async function run() {
  const q = input().value.trim();
  query = q;
  if (!q || !S.root) {
    $('#lec-search-info').textContent = '';
    $('#lec-search-results').innerHTML = '';
    return;
  }
  $('#lec-search-info').textContent = '찾는 중…';
  let d;
  try {
    d = await getJSON(`/api/search?q=${encodeURIComponent(q)}`);
  } catch (e) {
    if (q === query) $('#lec-search-info').textContent = `찾지 못했습니다: ${e.message}`;
    return;
  }
  if (q === query) render(d);   // 늦게 온 결과는 버린다
}

/** 지금 문서에서 line 번째 원문 줄이 든 가장 작은 블록으로 간다 */
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
  if (!best) return false;
  unfoldTo(best);
  best.scrollIntoView({ block: 'center' });
  flashBlock(best);
  return true;
}

async function openHit(path, line) {
  const here = S.view?.type === 'doc' && S.view.path === path;
  if (!here && !(await navigate({ type: 'doc', path }))) return;
  findText(query);
  if (line) goToLine(line);
}

export function openSearch() {
  switchTab('search');
  input().focus();
  input().select();
}

export function initSearch() {
  const later = debounce(run, 250);
  input().addEventListener('input', later);
  input().addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
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
  on('tree', () => { if (query && !$('#lec-search').hidden) later(); });
}
