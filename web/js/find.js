// 문서 안에서 찾기 (Ctrl+F)
//
// pywebview는 디버그 모드가 아니면 WebView2의 기본 찾기(Ctrl+F)를 끈다.
// 그래서 CSS Custom Highlight API로 직접 구현한다 (DOM을 바꾸지 않아 다시 그리기와 충돌이 없다).

import { on } from './store.js';
import { $, debounce } from './util.js';

const MAX_HITS = 2000;
let ranges = [];
let current = -1;

const bar = () => $('#lec-findbar');
const input = () => $('#lec-find-input');
const supported = () => typeof CSS !== 'undefined' && CSS.highlights && typeof Highlight !== 'undefined';

function clearMarks() {
  if (supported()) {
    CSS.highlights.delete('lec-find');
    CSS.highlights.delete('lec-find-current');
  }
  ranges = [];
  current = -1;
  $('#lec-find-count').textContent = '';
}

function search(keepIndex = false) {
  const prev = current;
  clearMarks();
  const query = input().value;
  if (!query || !supported()) return;
  const needle = query.toLowerCase();
  const view = $('#lec-view');
  const walker = document.createTreeWalker(view, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.parentElement?.closest('.code-tools, svg, .katex-mathml, script, style')
      ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  for (let node = walker.nextNode(); node && ranges.length < MAX_HITS; node = walker.nextNode()) {
    const text = node.nodeValue.toLowerCase();
    for (let i = text.indexOf(needle); i !== -1 && ranges.length < MAX_HITS; i = text.indexOf(needle, i + needle.length)) {
      const r = new Range();
      r.setStart(node, i);
      r.setEnd(node, i + needle.length);
      ranges.push(r);
    }
  }
  if (!ranges.length) {
    $('#lec-find-count').textContent = '없음';
    return;
  }
  CSS.highlights.set('lec-find', new Highlight(...ranges));
  go(keepIndex && prev >= 0 ? Math.min(prev, ranges.length - 1) : 0, !keepIndex);
}

function go(index, scroll = true) {
  if (!ranges.length) return;
  current = (index + ranges.length) % ranges.length;
  CSS.highlights.set('lec-find-current', new Highlight(ranges[current]));
  $('#lec-find-count').textContent = `${current + 1}/${ranges.length}`;
  if (!scroll) return;
  const content = $('#lec-content');
  const box = content.getBoundingClientRect();
  const rect = ranges[current].getBoundingClientRect();
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
  // 문서가 다시 그려지면(자동 새로고침 포함) 같은 검색어로 다시 표시
  on('rendered', () => { if (!bar().hidden) search(true); });
}
