// 문서 안에서 찾기 (Ctrl+F)
//
// pywebview는 디버그 모드가 아니면 WebView2의 기본 찾기(Ctrl+F)를 끈다.
// 그래서 CSS Custom Highlight API로 직접 구현한다 (DOM을 바꾸지 않아 다시 그리기와 충돌이 없다).
// html 문서는 iframe 안을 찾는다. 하이라이트는 문서마다 따로라서 iframe 창의 CSS.highlights 에 넣는다 (표시 색은 css/frame.css).

import { S, on } from './store.js';
import { unfoldTo } from './fold.js';
import { $, debounce, docRoot, screenRect } from './util.js';

const MAX_HITS = 2000;
let ranges = [];
let current = -1;
let win = window;   // 하이라이트를 넣은 창 (html 문서면 iframe 의 창)

const bar = () => $('#lec-findbar');
const input = () => $('#lec-find-input');
const supported = (w) => !!(w.CSS?.highlights && w.Highlight);

function clearMarks() {
  if (supported(win)) {
    win.CSS.highlights.delete('lec-find');
    win.CSS.highlights.delete('lec-find-current');
  }
  ranges = [];
  current = -1;
  $('#lec-find-count').textContent = '';
}

// 같은 블록 안의 글자는 이어 붙여 찾는다 ('**굵게**, `코드`' → '굵게, 코드'). 블록 사이에는 줄바꿈을 넣어 넘어가지 않게 한다
const BLOCKS = 'p, li, td, th, dt, dd, h1, h2, h3, h4, h5, h6, pre, blockquote, figcaption, caption, summary, '
  + 'div, section, article, header, footer, main, nav, aside, table, tr, ul, ol, dl, details, body';

/** root 의 보이는 글자를 한 줄로: text 는 소문자·공백 정리(글자 수는 그대로), parts 는 [시작 위치, 텍스트 노드] */
function flatten(root) {
  const walker = root.ownerDocument.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.parentElement?.closest('.code-tools, svg, .katex-mathml, script, style')
      ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  let text = '';
  const parts = [];
  let block = null;
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const here = node.parentElement.closest(BLOCKS);
    if (block && here !== block) text += '\n';
    block = here;
    parts.push([text.length, node]);
    const low = node.nodeValue.toLowerCase();   // 소문자로 바꾸며 글자 수가 달라지는 드문 글자(İ 등)가 있으면 그 노드는 그대로
    text += (low.length === node.nodeValue.length ? low : node.nodeValue).replace(/\s/g, ' ');   // 줄바꿈도 한 글자 공백으로
  }
  return { text, parts };
}

/** 이어 붙인 글자의 위치 → [텍스트 노드, 그 안의 위치] (이분 탐색) */
function locate(parts, at) {
  let lo = 0;
  let hi = parts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (parts[mid][0] <= at) lo = mid;
    else hi = mid - 1;
  }
  return [parts[lo][1], at - parts[lo][0]];
}

function search(keepIndex = false) {
  const prev = current;
  clearMarks();
  const query = input().value;
  const root = docRoot();
  const doc = root.ownerDocument;
  win = doc.defaultView;
  if (!query.trim() || !supported(win)) return;
  const needle = query.toLowerCase().replace(/\s+/g, ' ');
  const { text, parts } = flatten(root);
  for (let i = text.indexOf(needle); i !== -1 && ranges.length < MAX_HITS; i = text.indexOf(needle, i + needle.length)) {
    const [a, aOff] = locate(parts, i);
    const [b, bOff] = locate(parts, i + needle.length - 1);
    const r = doc.createRange();
    r.setStart(a, aOff);
    r.setEnd(b, bOff + 1);
    ranges.push(r);
  }
  if (!ranges.length) {
    $('#lec-find-count').textContent = '없음';
    return;
  }
  win.CSS.highlights.set('lec-find', new win.Highlight(...ranges));
  go(keepIndex && prev >= 0 ? Math.min(prev, ranges.length - 1) : 0, !keepIndex);
}

function go(index, scroll = true) {
  if (!ranges.length) return;
  current = (index + ranges.length) % ranges.length;
  win.CSS.highlights.set('lec-find-current', new win.Highlight(ranges[current]));
  $('#lec-find-count').textContent = `${current + 1}/${ranges.length}`;
  if (!scroll) return;
  unfoldTo(ranges[current].startContainer.parentElement);   // 접힌 절 안의 결과는 펴서 보여 준다
  const content = $('#lec-content');
  const box = content.getBoundingClientRect();
  const rect = screenRect(ranges[current]);
  if (rect.top < box.top + 56 || rect.bottom > box.bottom - 24) {
    content.scrollTop += rect.top - box.top - box.height / 3;
  }
}

export function openFind() {
  bar().hidden = false;
  input().focus();
  input().select();
  if (input().value) search();
}

/** 검색어를 넣고 찾기 막대를 연다 (전체 검색 결과로 갈 때). scroll 이 거짓이면 부른 쪽이 위치를 정한다 */
export function findText(query, { scroll = false } = {}) {
  bar().hidden = false;
  input().value = query;
  search(!scroll);
}

/** el 안(없으면 그 뒤)의 첫 결과를 지금 결과로 한다. 스크롤은 하지 않는다 (전체 검색 결과의 줄로 갔을 때) */
export function pickMatchAt(el) {
  const i = ranges.findIndex((r) => el.contains(r.startContainer)
    || el.compareDocumentPosition(r.startContainer) & Node.DOCUMENT_POSITION_FOLLOWING);
  if (i >= 0) go(i, false);
}

export function closeFind() {
  if (bar().hidden) return false;
  bar().hidden = true;
  clearMarks();
  return true;
}

export function initFind() {
  const run = debounce(() => search(), 120);
  input().addEventListener('input', run);
  input().addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      go(current + (e.shiftKey ? -1 : 1));
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      closeFind();
    }
  });
  $('#lec-find-next').addEventListener('click', () => go(current + 1));
  $('#lec-find-prev').addEventListener('click', () => go(current - 1));
  $('#lec-find-close').addEventListener('click', closeFind);
  // 문서가 다시 그려지면(자동 새로고침 포함) 같은 검색어로 다시 표시. 다른 탭을 고르면 그 탭의 문서에서 (찾기 막대도 그 칸으로 옮겨 간다)
  on('rendered', (pane) => { if (pane === S.pane && !bar().hidden) search(true); });
  on('pane', () => { if (!bar().hidden) search(true); });
}
