// 빠른 열기 (Ctrl+P): 이름·제목·경로 일부로 문서와 코드를 찾아 연다 (D44). 맞는 문서 먼저, 그다음 코드 — 코드는 코드 화면으로.
// 입력 전에는 최근 수정한 문서. 코드 목록은 사이드바 '코드' 목록과 같은 것 (others.js — 아직 받지 않았으면 받아 온다).
// Ctrl+Enter·Ctrl+누르기·가운데 버튼은 새 문서 탭에서 (D64). 문서 탭 줄의 + 로 열면 Enter 도 새 문서 탭에서, 맨 위에 '새 문서 만들기…'(D65).

import { S, emit } from './store.js';
import { loadOthers } from './others.js';
import { askNewDoc } from './basket.js';
import { fileIcon } from './icons.js';
import { $, esc, timeAgo, middleClickOpens } from './util.js';
import { t } from './i18n.js';

const MAX_ITEMS = 60;
const MIN_CODE = 20;   // 맞는 코드가 있으면 문서가 많아도 이만큼은 보인다

function* codeFiles(nodes = []) {
  for (const n of nodes) {
    if (n.type === 'file') yield n;
    else yield* codeFiles(n.children);
  }
}
let items = [];
let selected = 0;
let asNewTab = false;   // 문서 탭 줄의 + 로 열었다 — 고르면 새 문서 탭에서 (D64)

const box = () => $('#lec-palette');
const input = () => $('#lec-palette-input');

function score(f, terms, query) {
  const title = (f.title || '').toLowerCase();
  const name = f.name.toLowerCase();
  let s = 0;
  if (title.startsWith(terms[0]) || name.startsWith(terms[0])) s += 4;
  if (title.includes(query) || name.includes(query)) s += 3;
  if (terms.every((w) => name.includes(w) || title.includes(w))) s += 2;
  return s;
}

function update() {
  const query = input().value.trim().toLowerCase();
  const terms = query.split(/\s+/).filter(Boolean);
  if (!terms.length) {
    items = [...S.files].sort((a, b) => b.mtime - a.mtime).slice(0, MAX_ITEMS);   // 입력 전: 최근 수정한 문서
    if (asNewTab && S.tab) items.unshift({ newDoc: true, name: '', path: t('경로를 정하면 바로 만들어 새 탭에서 엽니다 (Ctrl+N)'), title: t('새 문서 만들기…') });
  } else {
    const match = (list) => list
      .filter((f) => {
        const hay = `${(f.title || '').toLowerCase()} ${f.path.toLowerCase()}`;
        return terms.every((w) => hay.includes(w));
      })
      .map((f) => ({ f, s: score(f, terms, query) }))
      .sort((a, b) => b.s - a.s || b.f.mtime - a.f.mtime)
      .map((x) => x.f);
    const docs = match(S.files);
    const code = match([...codeFiles(S.tab?.others.trees?.code)]).map((f) => ({ ...f, code: true }));
    const room = MAX_ITEMS - Math.min(code.length, MIN_CODE);
    const shownDocs = docs.slice(0, room);
    items = [...shownDocs, ...code.slice(0, MAX_ITEMS - shownDocs.length)];
  }
  selected = 0;
  renderList();
}

function renderList() {
  const ul = $('#lec-palette-list');
  if (!items.length) {
    ul.innerHTML = `<li class="empty">${S.root ? t('일치하는 문서나 코드가 없습니다') : t('먼저 폴더를 여세요')}</li>`;
    return;
  }
  ul.innerHTML = items.map((f, i) => `<li role="option" data-i="${i}" class="${i === selected ? 'sel' : ''}${f.code ? ' code' : ''}${f.newDoc ? ' new-doc' : ''}" aria-selected="${i === selected}">
      <span class="t">${f.newDoc ? '<svg class="ficon doc" aria-hidden="true"><use href="#i-plus"/></svg>' : fileIcon(f.name, f.code ? undefined : f.kind)}${esc(f.title || f.name)}</span><span class="when">${f.newDoc ? '' : esc(timeAgo(f.mtime))}</span>
      <span class="p">${esc(f.path)}</span></li>`).join('');
  ul.querySelector('.sel')?.scrollIntoView({ block: 'nearest' });
}

function choose(i, newTab = false) {
  const f = items[i];
  if (!f) return;
  const tab = newTab || asNewTab;
  closePalette();
  if (f.newDoc) askNewDoc();   // 새로 만들기 (D65)
  else emit('open', { type: f.code ? 'code' : 'doc', path: f.path, newTab: tab });
}

/** newTab: 고르면 새 문서 탭에서 (문서 탭 줄의 + — D64) */
export function openPalette({ newTab = false } = {}) {
  asNewTab = newTab;
  box().hidden = false;
  input().placeholder = newTab ? t('새 탭에 열 문서·코드 — 이름, 제목, 경로') : t('문서·코드 이름, 제목, 경로');
  input().value = '';
  update();
  input().focus();
  // 코드 목록을 아직 받지 않았으면 받아 온 뒤 다시 거른다 (사이드바 '코드'를 열어 보지 않았어도 찾게)
  const tab = S.tab;
  if (tab && !tab.others.trees) loadOthers(tab).then(() => { if (tab === S.tab && !box().hidden) update(); });
}

export function closePalette() {
  if (box().hidden) return false;
  box().hidden = true;
  return true;
}

export function initPalette() {
  input().addEventListener('input', update);
  input().addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!items.length) return;
      selected = (selected + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      renderList();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      choose(selected, e.ctrlKey || e.metaKey);   // Ctrl+Enter: 새 문서 탭에서
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();   // 문서 전체 Esc 처리(찾기 닫기 등)까지 가지 않게
      closePalette();
    }
  });
  $('#lec-palette-list').addEventListener('click', (e) => {
    const li = e.target.closest('li[data-i]');
    if (li) choose(+li.dataset.i, e.ctrlKey || e.metaKey);
  });
  middleClickOpens($('#lec-palette-list'), 'li[data-i]');
  box().addEventListener('mousedown', (e) => {
    if (e.target === box()) closePalette();
  });
}
