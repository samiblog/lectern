// 읽는 화면에서 글을 고르고 서식을 준다 (D142). 줄 단위인 현재 줄·고른 줄(spotlight.js)과 달리 낱말을 고른다 — 브라우저의 고르기(Selection)를 쓴다.
//
// - 고르는 법: 두 번 누르기(낱말 — 한 줄 편집 칸은 열지 않는다, 편집은 F2·우클릭으로만), 끌기, 현재 줄에서 → (첫 낱말)·← (마지막 낱말).
// - 고른 채: → / ← 오른쪽·왼쪽 낱말로, Shift+→ / Shift+← 낱말 단위로 넓히고 줄이기, Home / End 첫·마지막 낱말(Shift 와 함께면 거기까지),
//   ↑·↓ 는 풀고 현재 줄을 옮긴다, Esc 는 푼다 (main.js 의 clearPick). 원문 한 줄 안에서만 움직인다 — 끝에서 다음 줄로 넘어가지 않는다.
// - 서식: B·I·S·M·F 와 Ctrl+B·Ctrl+I·Ctrl+Shift+X·H·C — 고른 글에 하고 바로 저장한다 (lineedit.formatShown — 계산은 inlinefmt.js).
//   고른 글은 그대로 남아 형광펜·글자색을 거듭 누르면 다음 색이다. 고른 글이 없을 때 한 글자 키는 고른 줄(lineedit.litKey)의 것이고,
//   아무것도 고르지 않았으면 듣지 않는다 (사용자 결정 — 읽다가 누른 글자로 파일이 바뀌지 않게).
// - F2: 그 줄의 칸을 열고 같은 글을 골라 둔다 (lineedit.editShown). 우클릭: 서식의 선택 상자 (docmenu.js 가 wordMenu 를 부른다).
// 낱말은 띄어쓰기로 나눈다. 표의 행은 칸마다 따로 — 칸을 넘어 고르면 서식은 하지 않는다. md 문서에서만 (코드 화면은 글을 고치는 화면이 아니다).

import { S } from './store.js';
import { lineSlot, blockOfLine } from './lineunits.js';
import { sourceLines, pickedMany, followLine } from './spotlight.js';
import { formatShown, formatPicked, editShown, linesEditable } from './lineedit.js';
import { visibleOf, visibleOffsets } from './inlinefmt.js';
import { toast } from './util.js';
import { t } from './i18n.js';

/** 한 글자 서식 키 (자판 자리 — 한글 입력 상태에서도) */
const LETTERS = { KeyB: 'bold', KeyI: 'italic', KeyS: 'strike', KeyM: 'mark', KeyF: 'color' };
/** Ctrl+Shift 서식 키 — 한 줄 편집 칸 안과 같다 (D141) */
const CTRL_SHIFT = { KeyX: 'strike', KeyH: 'mark', KeyC: 'color' };

let last = null;   // 키로 고른 낱말 {line, seg, endSeg, va, vb, anchor, focus} — 고르기가 그대로면 넓히는 방향을 잇는다

const view = () => S.pane?.view;
const isDoc = (v) => !!v && v.classList.contains('md-body') && !!v.dataset.docPath && !v.classList.contains('code-view');
const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
const lead = (s) => s.length - s.replace(/^[\s ]+/, '').length;

/** 원문 줄 line 의 칸들 (화면의 Range) — 글을 고를 수 있는 줄만 (코드·그림·다이어그램은 null) */
function rangesOf(v, line) {
  const slot = lineSlot(v, line, sourceLines());
  return slot && slot.kind !== 'code' ? slot.ranges : null;
}

/** 표의 행인지 — 표는 칸마다 글이 따로다. 글 줄의 칸이 여럿이면 수식 같은 것이 글을 끊은 것이다 (서식은 F2 로) */
const isRow = (v, line) => lineSlot(v, line, sourceLines())?.kind === 'table';

/** 점(node, offset)이 든 원문 줄과 칸 {line, seg, ranges, table} — 없으면 null */
function lineAt(v, node, offset) {
  let el = (node.nodeType === 1 ? node : node.parentElement)?.closest?.('[data-lines]');
  while (el && v.contains(el)) {
    const m = /^(\d+)-(\d+)$/.exec(el.dataset.lines || '');
    if (m) {
      for (let n = Number(m[1]); n <= Number(m[2]); n += 1) {
        const ranges = rangesOf(v, n);
        const seg = ranges ? ranges.findIndex((r) => r.isPointInRange(node, offset)) : -1;
        if (seg >= 0) return { line: n, seg, ranges, table: isRow(v, n) };
      }
    }
    el = el.parentElement?.closest?.('[data-lines]');
  }
  return null;
}

/** range 의 처음부터 점(node, offset)까지의 글자 수 */
function offsetIn(range, node, offset) {
  const r = range.cloneRange();
  r.setEnd(node, offset);
  return r.toString().length;
}

/** range 안의 n 번째 글자 자리 {node, offset} */
function pointIn(range, n) {
  const root = range.commonAncestorContainer;
  if (root.nodeType === 3) return { node: root, offset: Math.min(range.startOffset + n, range.endOffset) };
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let left = n;
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (!range.intersectsNode(node)) continue;
    const start = node === range.startContainer ? range.startOffset : 0;
    const end = node === range.endContainer ? range.endOffset : node.nodeValue.length;
    if (left <= end - start) return { node, offset: start + left };
    left -= end - start;
  }
  return { node: range.endContainer, offset: range.endOffset };
}

/**
 * 지금 읽는 화면에서 고른 글 {line, seg, endSeg, ranges, va, vb} (va·vb 는 칸 seg·endSeg 의 화면 글에서의 자리).
 * 글을 고르지 않았거나 문서 밖이면 null, 여러 줄에 걸치면 {cross: true}
 */
export function shownPick() {
  const v = view();
  if (!isDoc(v) || S.pane?.lineEdit || S.pane?.editor) return null;
  const sel = getSelection();
  if (!sel.rangeCount || sel.isCollapsed) return null;
  const r = sel.getRangeAt(0);
  if (!v.contains(r.startContainer) || !v.contains(r.endContainer)) return null;
  const a = lineAt(v, r.startContainer, r.startOffset);
  if (!a) return null;
  let b = lineAt(v, r.endContainer, r.endOffset);
  let end = [r.endContainer, r.endOffset];
  if (!b || b.line !== a.line) {   // 두 번 누르기는 칸·줄 끝을 넘어 다음 블록의 처음까지 고르기도 한다 — 그 사이가 빈칸뿐이면 줄 안으로 당긴다
    const c = clampEnd(r, a.ranges);
    if (c) {
      b = { ...a, seg: c.seg };
      end = [c.node, c.offset];
    }
  }
  if (!b) return null;
  if (a.line !== b.line) return { cross: true };
  return {
    line: a.line, seg: a.seg, endSeg: b.seg, ranges: a.ranges, table: a.table,
    va: offsetIn(a.ranges[a.seg], r.startContainer, r.startOffset), vb: offsetIn(a.ranges[b.seg], end[0], end[1]),
  };
}

/** 고른 끝이 그 줄의 마지막 칸 뒤이고 그 사이가 빈칸뿐이면 그 칸의 끝 {seg, node, offset}, 아니면 null */
function clampEnd(r, ranges) {
  const i = ranges.length - 1;
  const g = ranges[i];
  if (g.comparePoint(r.endContainer, r.endOffset) <= 0) return null;   // 끝이 그 칸 안이나 앞이다
  const tail = document.createRange();
  tail.setStart(g.endContainer, g.endOffset);
  tail.setEnd(r.endContainer, r.endOffset);
  return tail.toString().trim() ? null : { seg: i, node: g.endContainer, offset: g.endOffset };
}

/** 칸들의 낱말 [{seg, a, b}] — 화면 글에서 띄어쓰기로 나눈 것 */
function wordsOf(ranges) {
  const out = [];
  ranges.forEach((r, seg) => {
    for (const m of r.toString().matchAll(/\S+/g)) out.push({ seg, a: m.index, b: m.index + m[0].length });
  });
  return out;
}

/** 고른 글이 든 낱말의 차례 {anchor, focus} — 키로 고른 그대로면 넓히던 방향을 잇는다 */
function spanOf(p, words) {
  if (last && last.line === p.line && last.seg === p.seg && last.endSeg === p.endSeg && last.va === p.va && last.vb === p.vb) return last;
  let lo = words.findIndex((w) => w.seg > p.seg || (w.seg === p.seg && w.b > p.va));
  let hi = words.findLastIndex((w) => w.seg < p.endSeg || (w.seg === p.endSeg && w.a < p.vb));
  if (lo < 0) lo = words.length - 1;
  if (hi < lo) hi = lo;
  return { anchor: lo, focus: hi };
}

/** 낱말 anchor~focus 를 고른다 (그 줄 안) */
function selectWords(line, ranges, words, anchor, focus) {
  const lo = words[Math.min(anchor, focus)];
  const hi = words[Math.max(anchor, focus)];
  const s = pointIn(ranges[lo.seg], lo.a);
  const e = pointIn(ranges[hi.seg], hi.b);
  const sel = getSelection();
  sel.setBaseAndExtent(s.node, s.offset, e.node, e.offset);
  last = { line, seg: lo.seg, endSeg: hi.seg, va: lo.a, vb: hi.b, anchor, focus };
  const box = sel.getRangeAt(0).getBoundingClientRect();
  const sc = S.pane?.scroller;
  if (sc && box.height) {   // 화면 밖이면 보이게
    const r = sc.getBoundingClientRect();
    if (box.top < r.top + 8) sc.scrollTop -= r.top + 8 - box.top;
    else if (box.bottom > r.bottom - 8) sc.scrollTop += box.bottom - (r.bottom - 8);
  }
}

/** 서식을 한 뒤 같은 글을 다시 고른다 — 다시 그린 화면에서 */
function reselect({ line, seg, body, a, b }) {
  const v = view();
  const range = v && rangesOf(v, line)?.[seg];
  if (!range) return;
  const shown = range.toString();
  const d = lead(visibleOf(body).text) - lead(shown);
  const [x, y] = visibleOffsets(body, a, b);
  const s = pointIn(range, Math.max(0, x - d));
  const e = pointIn(range, Math.max(0, y - d));
  getSelection().setBaseAndExtent(s.node, s.offset, e.node, e.offset);
  last = null;
}

/** 고른 글 p 에 서식 kind (value: 형광펜·글자색의 색 — 없으면 다음 색) */
async function applyTo(p, kind, value) {
  if (!p.table && p.ranges.length > 1) {   // 수식·그림 같은 것이 글을 끊은 줄 — 화면 글과 원문을 맞출 수 없다
    toast(t('이 줄에는 바로 서식을 줄 수 없습니다 — F2 로 열어 칸 안에서 하세요'));
    return;
  }
  if (p.seg !== p.endSeg) {
    toast(t('표의 칸을 넘어 골랐습니다 — 한 칸 안에서 고르세요'));
    return;
  }
  const r = await formatShown({ line: p.line, seg: p.seg, shown: p.ranges[p.seg].toString(), va: p.va, vb: p.vb, kind, value });
  if (r) reselect(r);
}

/** 키의 서식 — 없으면 null */
function formatOf(e) {
  if (!e.ctrlKey && !e.shiftKey) return e.repeat ? null : LETTERS[e.code] ?? null;
  if (e.ctrlKey && !e.shiftKey && (e.code === 'KeyB' || e.code === 'KeyI')) return e.code === 'KeyB' ? 'bold' : 'italic';
  if (e.ctrlKey && e.shiftKey) return CTRL_SHIFT[e.code] ?? null;
  return null;
}

const CROSS = () => t('글은 한 줄 안에서만 골라 서식을 줍니다 — 여러 줄은 Shift+↑·↓ 로 줄을 고르세요');

/**
 * 읽는 화면의 키 (main.js 의 keydown 이 vi 키·고른 줄의 키보다 먼저 부른다). 다뤘으면 true — 부른 쪽이 기본 동작을 막는다
 */
export function wordKey(e) {
  if (e.altKey || e.metaKey || e.isComposing) return false;
  const kind = formatOf(e);
  if (kind) {
    const p = shownPick();
    if (p?.cross) {
      toast(CROSS());
      return true;
    }
    if (p) {
      if (linesEditable()) applyTo(p, kind);
      return true;
    }
    return e.ctrlKey ? formatPicked(kind) : false;   // 한 글자 키는 고른 줄의 것 (lineedit.litKey)
  }
  if (e.ctrlKey) return false;
  const k = e.key;
  const v = view();
  if (!isDoc(v)) return false;
  if (k === 'F8') return stepMark(e.shiftKey ? -1 : 1);   // 다음·이전 형광펜 (D143)
  if (k === 'F2') {
    const p = shownPick();
    if (!p || p.cross || p.seg !== p.endSeg) return false;
    editShown({ line: p.line, seg: p.seg, shown: p.ranges[p.seg].toString(), va: p.va, vb: p.vb });
    return true;
  }
  if ((k === 'ArrowUp' || k === 'ArrowDown') && !e.shiftKey) {   // 풀고 줄을 옮긴다 — 옮기는 것은 spotlight.js
    if (shownPick()) getSelection().removeAllRanges();
    return false;
  }
  if (k !== 'ArrowLeft' && k !== 'ArrowRight' && k !== 'Home' && k !== 'End') return false;
  const p = shownPick();
  if (p?.cross) return false;
  if (!p) {   // 현재 줄에서 → 첫 낱말, ← 마지막 낱말 (Shift+→·← 는 터미널로 보내기·위치 복사 그대로)
    if (e.shiftKey || (k !== 'ArrowLeft' && k !== 'ArrowRight') || pickedMany()) return false;
    const here = S.pane?.here;
    const line = here?.path === v.dataset.docPath ? here.line : null;
    const ranges = line ? rangesOf(v, line) : null;
    const words = ranges ? wordsOf(ranges) : [];
    if (!words.length) return false;
    const i = k === 'ArrowRight' ? 0 : words.length - 1;
    selectWords(line, ranges, words, i, i);
    return true;
  }
  const words = wordsOf(p.ranges);
  if (!words.length) return false;
  let { anchor, focus } = spanOf(p, words);
  const end = words.length - 1;
  if (k === 'Home' || k === 'End') {
    focus = k === 'Home' ? 0 : end;
    if (!e.shiftKey) anchor = focus;
  } else {
    const dir = k === 'ArrowRight' ? 1 : -1;
    if (e.shiftKey) focus = clamp(focus + dir, 0, end);
    else {
      focus = clamp((dir > 0 ? Math.max(anchor, focus) : Math.min(anchor, focus)) + dir, 0, end);
      anchor = focus;
    }
  }
  selectWords(p.line, p.ranges, words, anchor, focus);
  return true;
}

/**
 * F8·Shift+F8 (D143): 다음·이전 형광펜으로 가서 그 칠한 글을 고른다 — 이어서 M 으로 색을 바꾸거나 우클릭으로 메모를 단다.
 * 기준은 고른 글(없으면 현재 줄의 처음). 끝에서는 돌지 않고 알린다
 */
function stepMark(dir) {
  const v = view();
  const marks = [...v.querySelectorAll('mark')].filter((m) => m.getClientRects().length && !m.closest('.lec-line-edit, .lec-unfold'));
  if (!marks.length) {
    toast(t('이 문서에는 형광펜이 없습니다'));
    return true;
  }
  const sel = getSelection();
  const at = document.createRange();
  if (sel.rangeCount && !sel.isCollapsed && v.contains(sel.anchorNode)) {
    const r = sel.getRangeAt(0);
    if (dir > 0) at.setStart(r.endContainer, r.endOffset);
    else at.setStart(r.startContainer, r.startOffset);
  } else {
    const here = S.pane?.here;
    const el = here?.path === v.dataset.docPath ? blockOfLine(v, here.line) : null;
    if (el) at.setStartBefore(el);
    else at.setStart(v, 0);
  }
  at.collapse(true);
  const next = dir > 0 ? marks.find((m) => at.comparePoint(m, 0) >= 0) : marks.findLast((m) => at.comparePoint(m, m.childNodes.length) <= 0);
  if (!next) {
    toast(dir > 0 ? t('마지막 형광펜입니다 — Shift+F8 은 앞의 것') : t('첫 형광펜입니다 — F8 은 다음 것'));
    return true;
  }
  next.scrollIntoView({ block: 'center' });
  const line = Number(/^\d+/.exec(next.closest('[data-lines]')?.dataset.lines || '')?.[0]);
  if (line) followLine(line);
  sel.selectAllChildren(next);
  last = null;
  return true;
}

/** Esc: 읽는 화면에서 고른 글을 푼다. 다뤘으면 true */
export function clearPick() {
  if (!shownPick()) return false;
  getSelection().removeAllRanges();
  last = null;
  return true;
}

/**
 * 우클릭 (docmenu.js): 읽는 화면에서 한 줄 안의 글을 골랐으면 서식의 선택 상자 항목들, 아니면 null.
 * 우클릭한 때의 고른 글을 기억해 둔다 — 항목을 누를 때는 고르기가 바뀌었을 수 있다
 * @returns {MenuItem[] | null}
 */
export function wordMenu() {
  const p = shownPick();
  if (!p || p.cross || !linesEditable()) return null;
  const run = (kind, value) => () => applyTo(p, kind, value);
  const marks = [['', t('노랑')], ['green', t('초록')], ['pink', t('분홍')], ['blue', t('하늘')]];
  const colors = [['red', t('빨강')], ['blue', t('파랑')], ['green', t('초록')], ['goldenrod', t('노랑')]];
  const again = t('같은 색을 다시 고르면 풉니다. 키는 거듭 누르면 다음 색');
  return [
    { label: t('굵게'), hint: 'B', action: run('bold') },
    { label: t('기울임'), hint: 'I', action: run('italic') },
    { label: t('취소선'), hint: 'S', action: run('strike') },
    '-',
    ...marks.map(([v, name], i) => ({ label: t('형광펜 — {color}', { color: name }), hint: i ? '' : 'M', tip: again, action: run('mark', v) })),
    '-',
    ...colors.map(([v, name], i) => ({ label: t('글자색 — {color}', { color: name }), hint: i ? '' : 'F', tip: again, action: run('color', v) })),
    '-',
    { label: t('서식 풀기'), tip: t('고른 곳의 굵게·색·형광펜 같은 서식을 모두'), action: run('clear') },
    ...(p.seg === p.endSeg ? [{ label: t('여기서 편집'), hint: 'F2', tip: t('그 줄을 열고 고른 글을 골라 둡니다'), action: () => editShown({ line: p.line, seg: p.seg, shown: p.ranges[p.seg].toString(), va: p.va, vb: p.vb }) }] : []),
  ];
}
