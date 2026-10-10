// 빠른 열기 (Ctrl+P): 이름·제목·경로 일부로 문서를 찾아 연다

import { S, emit } from './store.js';
import { $, esc, timeAgo } from './util.js';

const MAX_ITEMS = 60;
let items = [];
let selected = 0;

const box = () => $('#lec-palette');
const input = () => $('#lec-palette-input');

function score(f, terms, query) {
  const title = (f.title || '').toLowerCase();
  const name = f.name.toLowerCase();
  let s = 0;
  if (title.startsWith(terms[0]) || name.startsWith(terms[0])) s += 4;
  if (title.includes(query) || name.includes(query)) s += 3;
  if (terms.every((t) => name.includes(t) || title.includes(t))) s += 2;
  return s;
}

function update() {
  const query = input().value.trim().toLowerCase();
  const terms = query.split(/\s+/).filter(Boolean);
  let list;
  if (!terms.length) {
    list = [...S.files].sort((a, b) => b.mtime - a.mtime);           // 입력 전: 최근 수정 순
  } else {
    list = S.files
      .filter((f) => {
        const hay = `${(f.title || '').toLowerCase()} ${f.path.toLowerCase()}`;
        return terms.every((t) => hay.includes(t));
      })
      .map((f) => ({ f, s: score(f, terms, query) }))
      .sort((a, b) => b.s - a.s || b.f.mtime - a.f.mtime)
      .map((x) => x.f);
  }
  items = list.slice(0, MAX_ITEMS);
  selected = 0;
  renderList();
}

function renderList() {
  const ul = $('#lec-palette-list');
  if (!items.length) {
    ul.innerHTML = `<li class="empty">${S.root ? '일치하는 문서가 없습니다' : '먼저 폴더를 여세요'}</li>`;
    return;
  }
  ul.innerHTML = items.map((f, i) => `<li role="option" data-i="${i}" class="${i === selected ? 'sel' : ''}" aria-selected="${i === selected}">
      <span class="t">${esc(f.title || f.name)}</span><span class="when">${esc(timeAgo(f.mtime))}</span>
      <span class="p">${esc(f.path)}</span></li>`).join('');
  ul.querySelector('.sel')?.scrollIntoView({ block: 'nearest' });
}

function choose(i) {
  const f = items[i];
  if (!f) return;
  closePalette();
  emit('open', { type: 'doc', path: f.path });
}

export function openPalette() {
  box().hidden = false;
  input().value = '';
  update();
  input().focus();
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
      choose(selected);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();   // 문서 전체 Esc 처리(찾기 닫기 등)까지 가지 않게
      closePalette();
    }
  });
  $('#lec-palette-list').addEventListener('click', (e) => {
    const li = e.target.closest('li[data-i]');
    if (li) choose(+li.dataset.i);
  });
  box().addEventListener('mousedown', (e) => {
    if (e.target === box()) closePalette();
  });
}
