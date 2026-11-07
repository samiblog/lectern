// 넣기 창 (D109): 구성 요소를 고르는 작은 창. 빈 줄의 `/`, 칸의 Ctrl+Shift+/, 우클릭 '여기에 넣기…'·'이 줄 바꾸기…'.
// 줄 옆에 뜨고 찾기 칸에 초점을 둔다 — 한글은 조합 중이라 키로 옮길 수 없다 (D101). 표시를 외우지 않아도 넣게 한다.
// 고르는 일만 한다: 고른 것을 돌려주면 lineedit.js 가 넣는다. 파일을 고르는 단계(그림·첨부·링크)와 글을 묻는 단계(주·표 크기)도 이 창이 맡는다.

import { S } from './store.js';
import { getJSON } from './api.js';
import { $ } from './util.js';
import { html, setHtml } from './html.js';
import { t } from './i18n.js';

const box = () => $('#lec-put');
const find = () => $('#lec-put-find');
const list = () => $('#lec-put-list');

let waiting = null;   // {resolve, items, sel, free} — free: 찾기 칸의 글을 그대로 돌려줄 수 있다

/** 글의 종류 — 넣기와 '이 줄 바꾸기' 가 함께 쓴다 */
const TEXT_ITEMS = () => [
  { id: 'h1', group: t('글'), name: t('제목 1'), hint: 'Ctrl+Alt+1', words: '# heading title' },
  { id: 'h2', group: t('글'), name: t('제목 2'), hint: 'Ctrl+Alt+2', words: '## heading' },
  { id: 'h3', group: t('글'), name: t('제목 3'), hint: 'Ctrl+Alt+3', words: '### heading' },
  { id: 'h4', group: t('글'), name: t('제목 4'), hint: 'Ctrl+Alt+4', words: '#### heading' },
  { id: 'para', group: t('글'), name: t('문단'), hint: 'Ctrl+Alt+0', words: 'paragraph text' },
  { id: 'bullet', group: t('글'), name: t('목록'), words: '- list bullet 글머리' },   // i18n-ok (찾는 말)
  { id: 'number', group: t('글'), name: t('번호 목록'), words: '1. number ordered' },
  { id: 'task', group: t('글'), name: t('할 일'), words: 'todo task checkbox 체크' },   // i18n-ok (찾는 말)
  { id: 'quote', group: t('글'), name: t('인용'), words: '> quote' },
];

const BOX_ITEMS = () => [
  { id: 'box:NOTE', group: t('박스글'), name: t('박스글 — 참고'), words: 'note callout 상자' },   // i18n-ok (찾는 말)
  { id: 'box:TIP', group: t('박스글'), name: t('박스글 — 팁'), words: 'tip callout 상자' },   // i18n-ok (찾는 말)
  { id: 'box:IMPORTANT', group: t('박스글'), name: t('박스글 — 중요'), words: 'important callout 요약 핵심 상자' },   // i18n-ok (찾는 말)
  { id: 'box:WARNING', group: t('박스글'), name: t('박스글 — 경고'), words: 'warning callout 상자' },   // i18n-ok (찾는 말)
  { id: 'box:CAUTION', group: t('박스글'), name: t('박스글 — 주의'), words: 'caution callout 상자' },   // i18n-ok (찾는 말)
];

const BLOCK_ITEMS = () => [
  { id: 'table', group: t('자료'), name: t('표'), words: 'table' },
  { id: 'image', group: t('자료'), name: t('그림'), words: 'image picture 이미지 사진' },   // i18n-ok (찾는 말)
  { id: 'chart', group: t('자료'), name: t('차트'), words: 'chart graph 그래프' },   // i18n-ok (찾는 말)
  { id: 'diagram', group: t('자료'), name: t('다이어그램'), words: 'diagram mermaid 흐름도' },   // i18n-ok (찾는 말)
  { id: 'math', group: t('자료'), name: t('수식'), words: 'math equation 공식' },   // i18n-ok (찾는 말)
  { id: 'code', group: t('자료'), name: t('코드'), words: 'code' },
  { id: 'note', group: t('주·참조'), name: t('주'), hint: 'Ctrl+Alt+F', words: 'footnote 각주 미주' },   // i18n-ok (찾는 말)
  { id: 'source', group: t('주·참조'), name: t('출처 줄'), words: 'source 자료 출처' },   // i18n-ok (찾는 말)
  { id: 'tablenote', group: t('주·참조'), name: t('표 주'), words: 'table note 주석' },   // i18n-ok (찾는 말)
  { id: 'link', group: t('주·참조'), name: t('링크'), hint: 'Ctrl+K', words: 'link url' },
  { id: 'ref', group: t('주·참조'), name: t('상호 참조'), words: 'cross reference 참조 표 그림 절 링크' },   // i18n-ok (찾는 말)
  { id: 'cite', group: t('주·참조'), name: t('본문 인용'), words: 'citation cite 인용 문헌 참고문헌' },   // i18n-ok (찾는 말)
  { id: 'attach', group: t('주·참조'), name: t('첨부'), words: 'attachment 붙임 별첨 파일' },   // i18n-ok (찾는 말)
  { id: 'appendix', group: t('주·참조'), name: t('부록'), words: 'appendix' },
  { id: 'rule', group: t('쪽'), name: t('구분선'), words: '--- rule line' },
  { id: 'pagebreak', group: t('쪽'), name: t('쪽 나눔'), words: 'page break 페이지 나누기 인쇄' },   // i18n-ok (찾는 말)
  { id: 'toc', group: t('쪽'), name: t('목차'), words: 'toc contents 차례' },   // i18n-ok (찾는 말)
  { id: 'tables', group: t('쪽'), name: t('표 목차'), words: 'list of tables 표 차례' },   // i18n-ok (찾는 말)
  { id: 'figures', group: t('쪽'), name: t('그림 목차'), words: 'list of figures 그림 차례' },   // i18n-ok (찾는 말)
];

/** 슬라이드에 넣지 않는 것: 각주를 쓰지 않고, 첨부·부록·목차·쪽 나눔·참조·인용은 문서의 것이고, --- 는 장을 가른다 */
const NOT_IN_DECK = new Set(['note', 'tablenote', 'attach', 'appendix', 'rule', 'pagebreak', 'toc', 'tables', 'figures', 'ref', 'cite']);
const SPEAKER = () => ({ id: 'speaker', group: t('주·참조'), name: t('발표자 노트'), words: 'speaker note 노트 메모' });   // i18n-ok (찾는 말)

/** 넣을 수 있는 것 */
export const putItems = (deck = false) => [...TEXT_ITEMS(), ...BOX_ITEMS(), ...BLOCK_ITEMS().filter((x) => !deck || !NOT_IN_DECK.has(x.id)), ...(deck ? [SPEAKER()] : [])];
/** 줄을 바꿀 수 있는 것 */
export const changeItems = () => [...TEXT_ITEMS(), ...BOX_ITEMS()];

function draw() {
  const q = find().value.trim().toLowerCase();
  const { items } = waiting;
  const shown = (q ? items.filter((x) => `${x.name} ${x.words || ''} ${x.sub || ''}`.toLowerCase().includes(q)) : items);
  waiting.shown = shown;
  waiting.sel = Math.min(waiting.sel, Math.max(0, shown.length - 1));
  let group = null;
  setHtml(list(), shown.length ? shown.flatMap((x, i) => {
    const head = x.group && x.group !== group ? html`<li class="head">${x.group}</li>` : '';
    group = x.group ?? group;
    return [head, html`<li role="option" data-i="${i}" class="${i === waiting.sel ? 'sel' : ''}" aria-selected="${i === waiting.sel}">
      <span class="t">${x.name}</span>${x.sub ? html`<span class="p">${x.sub}</span>` : ''}${x.hint ? html`<kbd>${x.hint}</kbd>` : ''}
    </li>`];
  }) : html`<li class="none">${waiting.free ? t('Enter 를 누르면 쓴 글을 씁니다') : t('맞는 것이 없습니다')}</li>`);
  list().querySelector('li.sel')?.scrollIntoView({ block: 'nearest' });
}

/** 창을 at(화면의 요소·좌표) 옆에 놓는다 */
function place(at) {
  const el = box();
  const r = at?.getBoundingClientRect?.() ?? { left: at?.x ?? 200, bottom: at?.y ?? 200, top: at?.y ?? 200 };
  el.hidden = false;
  const { width, height } = el.getBoundingClientRect();
  const left = Math.max(8, Math.min(r.left, innerWidth - width - 8));
  const below = r.bottom + 4;
  el.style.left = `${left}px`;
  el.style.top = `${below + height > innerHeight - 8 ? Math.max(8, r.top - height - 4) : below}px`;
}

/**
 * 고르는 창을 띄운다. 고른 것(또는 free 면 쓴 글 {text}), 그만두면 null.
 * items: [{id, name, group?, sub?, hint?, words?}], title, at: 옆에 놓을 곳, value: 찾기 칸의 처음 글, free: 쓴 글도 받는다
 */
export function pick({ items, title, at = null, value = '', free = false, placeholder = '' }) {
  return new Promise((resolve) => {
    waiting?.resolve(null);
    waiting = { resolve, items, sel: 0, free, shown: items };
    $('#lec-put-title').textContent = title;
    find().value = value;
    find().placeholder = placeholder || t('이름으로 거르기');
    draw();
    place(at);
    find().focus();
    find().select();
  });
}

export function closePut() {
  if (box().hidden) return false;
  box().hidden = true;
  const w = waiting;
  waiting = null;
  w?.resolve(null);
  return true;
}

function choose() {
  if (!waiting) return;
  const item = waiting.shown[waiting.sel];
  const text = find().value.trim();
  const w = waiting;
  if (!item && !(w.free && text)) return;
  box().hidden = true;
  waiting = null;
  w.resolve(item ?? { text });
}

/** 글을 묻는다 (주의 내용, 표 크기). 쓴 글, 그만두면 null */
export async function askText({ title, at = null, value = '', placeholder = '' }) {
  const r = await pick({ items: [], title, at, value, free: true, placeholder });
  return r ? r.text : null;
}

/** 프로젝트의 파일 목록 — 문서와 자료 {path, name, doc}. want: 파일을 거르는 함수 */
/** @param {(f: any) => boolean} [want] */
export async function projectFiles(want = () => true) {
  const tab = S.tab;
  const { tree } = await getJSON(`/api/others?p=${encodeURIComponent(tab.id)}`);
  const out = [];
  const walk = (nodes) => {
    for (const n of nodes) {
      if (n.children) walk(n.children);
      else if (!n.excluded) out.push({ path: n.path, name: n.name });
    }
  };
  walk(tree);
  for (const f of tab.fileMap.values()) out.push({ path: f.path, name: f.name, title: f.title, doc: true });
  return out.filter(want);
}

export function initPut() {
  find().addEventListener('input', () => {
    if (!waiting) return;
    waiting.sel = 0;
    draw();
  });
  find().addEventListener('keydown', (e) => {
    if (e.isComposing || e.keyCode === 229 || !waiting) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const n = waiting.shown.length;
      if (n) {
        waiting.sel = (waiting.sel + (e.key === 'ArrowDown' ? 1 : -1) + n) % n;
        draw();
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      choose();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      closePut();
    }
    e.stopPropagation();
  });
  list().addEventListener('mousedown', (e) => e.preventDefault());   // 초점은 찾기 칸에
  list().addEventListener('click', (e) => {
    const li = e.target.closest('li[data-i]');
    if (!li || !waiting) return;
    waiting.sel = Number(li.dataset.i);
    choose();
  });
  document.addEventListener('mousedown', (e) => {
    if (!box().hidden && !box().contains(e.target)) closePut();
  }, true);
}
