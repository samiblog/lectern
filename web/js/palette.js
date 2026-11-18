// 빠른 열기 (Ctrl+P): 이름·제목·경로 일부로 문서와 코드를 찾아 연다 (D44). 맞는 문서 먼저, 그다음 코드 — 코드는 코드 화면으로.
// 입력 전에는 최근 수정한 문서. 코드 목록은 사이드바 '코드' 목록과 같은 것 (others.js — 아직 받지 않았으면 받아 온다).
// 고르면 새 문서 탭에서 (D91), Ctrl+Enter·Ctrl+누르기·가운데 버튼은 뒤에서, Alt+Enter·Alt+누르기는 지금 탭. 문서 탭 줄의 + 로 열면 폴더 개요에서도 새 탭에.
// ':숫자' 는 지금 문서·코드의 그 줄로 (Ctrl+G). '>' 로 시작하면 명령 찾기 (Ctrl+Shift+P — D170): 이름을 쳐서 고르고 옆에 단축키.
// 명령 목록은 main.js 가 setCommands 로 준다 (commands.js — 이 모듈이 여러 모듈을 부르면 import 순환이 생긴다).

import { S, emit } from './store.js';
import { loadOthers } from './others.js';
import { fileIcon } from './icons.js';
import { html, setHtml } from './html.js';
import { $, timeAgo, middleClickOpens, openHow } from './util.js';
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
/** @type {() => {group: string, name: string, keys: string, run: () => void}[]} */
let commandsOf = () => [];   // 명령 찾기의 목록 (commands.js)
/** @type {HTMLElement | null} */
let returnTo = null;   // 열기 전 초점 — 닫을 때 고른 일이 초점을 옮기지 않았으면 그리로 (closePalette)

/** 명령 찾기의 목록을 준다 (main.js 가 commands.js 의 것을) */
export function setCommands(fn) {
  commandsOf = fn;
}

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

/** 명령 찾기: 이름·묶음·키에 든 낱말로 거르고, 이름이 그 말로 시작하는 것을 앞에 */
function commandItems(query) {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  const all = commandsOf().map((c) => ({ ...c, cmd: true, hay: `${c.name} ${c.group} ${c.keys}`.toLowerCase() }));
  if (!terms.length) return all;
  return all.filter((c) => terms.every((w) => c.hay.includes(w)))
    .map((c, i) => ({ c, s: (c.name.toLowerCase().startsWith(terms[0]) ? 2 : 0) + (c.keys.toLowerCase() === query.toLowerCase() ? 3 : 0), i }))
    .sort((a, b) => b.s - a.s || a.i - b.i)
    .map((x) => x.c);
}

function update() {
  const command = /^\s*>(.*)$/.exec(input().value);
  if (command) {   // 명령 찾기 (Ctrl+Shift+P — D170)
    items = commandItems(command[1].trim());
    selected = 0;
    renderList(t('일치하는 명령이 없습니다'));
    return;
  }
  const go = /^:(\d*)$/.exec(input().value.trim());
  if (go) {   // 줄로 가기 (Ctrl+G)
    items = go[1] ? [{ goto: Number(go[1]), name: '', path: '' }] : [];
    selected = 0;
    renderList(t('줄 번호를 입력합니다'));
    return;
  }
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

function renderList(none = '') {
  const ul = $('#lec-palette-list');
  if (!items.length) {
    setHtml(ul, html`<li class="empty">${none || (S.root ? t('일치하는 문서나 코드가 없습니다') : t('먼저 폴더를 여세요'))}</li>`);
    return;
  }
  if (items[0].cmd) {   // 명령: 이름, 오른쪽에 단축키, 아래에 묶음
    setHtml(ul, items.map((c, i) => html`<li role="option" data-i="${i}" class="cmd${i === selected ? ' sel' : ''}" aria-selected="${i === selected}">
      <span class="t">${c.name}</span><span class="when">${c.keys}</span><span class="p">${c.group}</span></li>`));
    ul.querySelector('.sel')?.scrollIntoView({ block: 'nearest' });
    return;
  }
  if (items[0].goto) {
    setHtml(ul, html`<li role="option" data-i="0" class="sel" aria-selected="true"><span class="t">${t('{n}행으로 가기', { n: items[0].goto })}</span></li>`);
    return;
  }
  setHtml(ul, items.map((f, i) => html`<li role="option" data-i="${i}" class="${i === selected ? 'sel' : ''}${f.code ? ' code' : ''}${f.newDoc ? ' new-doc' : ''}" aria-selected="${i === selected}">
      <span class="t">${f.newDoc ? html`<svg class="ficon doc" aria-hidden="true"><use href="#i-plus"/></svg>` : fileIcon(f.name, f.code ? undefined : f.kind)}${f.title || f.name}</span><span class="when">${f.newDoc ? '' : timeAgo(f.mtime)}</span>
      <span class="p">${f.path}</span></li>`));
  ul.querySelector('.sel')?.scrollIntoView({ block: 'nearest' });
}

function choose(i, e) {
  const f = items[i];
  if (!f) return;
  if (!f.cmd) returnTo = null;   // 문서를 열면(다른 칸·탭일 수 있다) 앞 초점으로 돌리지 않는다 — 본문이 받는다
  closePalette();
  if (f.cmd) f.run();
  else if (f.goto) emit('go-line', { line: f.goto });
  else if (f.newDoc) emit('new-doc', {});   // 새로 만들기 (D65)
  else emit('open', { type: f.code ? 'code' : 'doc', path: f.path, ...openHow(e), force: asNewTab });
}

/** newTab: 폴더 개요에서도 새 문서 탭에서 (문서 탭 줄의 +·Ctrl+T — D64). query: 처음 글 (Ctrl+G 의 ':', Ctrl+Shift+P 의 '>') */
export function openPalette({ newTab = false, query = '' } = {}) {
  asNewTab = newTab;
  const at = /** @type {HTMLElement | null} */ (document.activeElement);
  if (!box().contains(at)) returnTo = at && at !== document.body ? at : null;
  box().hidden = false;
  input().placeholder = newTab ? t('새 탭에 열 문서·코드 — 이름, 제목, 경로') : t('문서·코드 이름, 제목, 경로 — > 로 시작하면 명령, : 는 줄 번호');
  input().value = query;
  update();
  input().focus();
  // 코드 목록을 아직 받지 않았으면 받아 온 뒤 다시 거른다 (사이드바 '코드'를 열어 보지 않았어도 찾게)
  const tab = S.tab;
  if (tab && !tab.others.trees) loadOthers(tab).then(() => { if (tab === S.tab && !box().hidden) update(); });
}

export function closePalette() {
  if (box().hidden) return false;
  box().hidden = true;
  // 감춘 칸에 초점이 남으면 다음 키를 그 칸이 받는다 — 명령 찾기에서 고른 바로 뒤의 Esc 가 PDF·인쇄 창을 닫지 못했고, Enter 를 거듭 누르면 같은 명령을
  // 또 했다 (실제 창 시험에서 찾음). 초점을 빼면 본문(body)이 받아 앱 키가 듣는다 — 고른 일이 초점을 옮기면 그리로
  if (box().contains(document.activeElement)) /** @type {HTMLElement} */ (document.activeElement).blur();
  // 열기 전에 초점이 있던 곳(편집기·문서·목록)으로 돌려준다 — 고른 일이 초점을 옮기지 않았거나 그만뒀을 때만 (Esc, '열린 문서 모두 닫기'를 묻고
  // 그만둠 등 — 전에는 본문에 남아 이어 친 키가 편집기에 가지 않았다, 0.93·0.94 함께 쓰는 시나리오에서 찾음). 다음 차례에 — 고른 일이 먼저 한다
  const back = returnTo;
  returnTo = null;
  setTimeout(() => {
    if (back?.isConnected && document.activeElement === document.body && back.checkVisibility() && box().hidden) back.focus({ preventScroll: true });
  }, 0);
  return true;
}

export function initPalette() {
  input().addEventListener('input', update);
  input().addEventListener('keydown', (e) => {
    if (box().hidden) return;   // 닫은 뒤의 키는 앱의 것
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!items.length) return;
      selected = (selected + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      renderList();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      choose(selected, e);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();   // 문서 전체 Esc 처리(찾기 닫기 등)까지 가지 않게
      closePalette();
    }
  });
  $('#lec-palette-list').addEventListener('click', (e) => {
    const li = e.target.closest('li[data-i]');
    if (li) choose(+li.dataset.i, e);
  });
  middleClickOpens($('#lec-palette-list'), 'li[data-i]');
  box().addEventListener('mousedown', (e) => {
    if (e.target === box()) closePalette();
  });
}
