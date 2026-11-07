// vi 키 (D122): 설정 'vi 키'(vi_keys, 기본 꺼짐)를 켜면 읽는 화면(md 문서·코드 화면·Lectern 슬라이드)에서 글자 키로 움직이고 고친다.
// 있는 기능을 부르는 번역표다 — 글자 키를 같은 일을 하는 기존 키(↓·Insert·Delete·Ctrl+Enter…)로 바꿔 다시 보내거나 있는 함수를 부른다.
// 새로 만든 편집은 p·P(담아 둔 줄 넣기)와 J(고른 줄 합치기)뿐이다 (lineedit.js).
//
// - 현재 줄 = Normal, 고른 줄 = Visual Line(V), 칸 = Insert. 하이라이트가 켜져 있으면 듣지 않는다 (D118 — 보기만).
// - Ctrl·Alt 가 붙은 키는 하나도 바꾸지 않는다 (Ctrl+D 장 복제·Ctrl+F 찾기·Ctrl+B 사이드바 그대로). 쪽 넘기기는 PageUp·PageDown.
// - 글자는 e.code(KeyJ…)로 읽는다 — 한/영 상태와 관계없이 듣는다. 글 칸·입력 칸·터미널·편집 상자 안은 main.js 가 거른다.
// - 파일을 바꾸는 dd·>>·<< 는 그 줄을 고르고(Insert) 실행하는 것으로 번역한다 (D108 — 두 번 눌러야 한다).
// - 두 글자 명령(dd·yy·gg·zz·[[·>>…)은 1초 안에 다음 글자를 기다리고, 그동안 상태줄에 'd…' 처럼 보인다. 앞의 숫자는 그 수만큼 (3j, 2dd).
// - 칸 안의 Esc 는 저장하고 나온다 (lineedit.js — vi 의 Insert → Normal). 전체 편집은 CodeMirror 의 vim 키맵 (editor.js).

import { S, on } from './store.js';
import { openFind, findStep } from './find.js';
import { foldAll } from './fold.js';
import { openPalette } from './palette.js';
import { followLine, sourceLines, litSpan, lightOn } from './spotlight.js';
import { putLinesHere, joinPicked } from './lineedit.js';
import { headsOf } from './docops.js';
import { $ } from './util.js';
import { t } from './i18n.js';

export const viOn = () => S.config?.vi_keys === true;

let pending = '';   // 기다리는 앞 글자 ('d', 'g', 'z', '[' …)
let count = '';     // 앞의 숫자
let timer = 0;
let register = [];  // dd·yy·d·y 로 담은 줄 (p·P 가 넣는다) — 앱 안에만, 클립보드와 따로

/** 키 → 글자. 영문 글자·기호면 그대로, 한글 입력 상태처럼 다른 글자가 오면 자판 자리(e.code)로 읽는다. 모르는 키면 null */
function charOf(e) {
  if (/^[a-zA-Z0-9/:[\]<>]$/.test(e.key)) return e.key;
  const c = e.code;
  if (/^Key[A-Z]$/.test(c)) return e.shiftKey ? c[3] : c[3].toLowerCase();
  if (/^Digit\d$/.test(c) && !e.shiftKey) return c[5];
  const shifted = { Semicolon: ':', Period: '>', Comma: '<' };
  const plain = { Slash: '/', BracketLeft: '[', BracketRight: ']' };
  return (e.shiftKey ? shifted[c] : plain[c]) ?? null;
}

function show() {
  const el = $('#lec-st-vi');
  if (!el) return;
  el.hidden = !viOn();
  el.textContent = count || pending ? `vi ${count}${pending}…` : 'vi';
  el.title = t('vi 키가 켜져 있습니다 — 설정(Ctrl+,)에서 끕니다');
}

function reset() {
  clearTimeout(timer);
  pending = '';
  count = '';
  show();
}

/** 다음 글자를 1초 기다린다 */
function arm() {
  clearTimeout(timer);
  timer = setTimeout(reset, 1000);
  show();
}

const CODES = { Insert: 'Insert', Delete: 'Delete', Enter: 'Enter', Escape: 'Escape', F2: 'F2', ArrowUp: 'ArrowUp', ArrowDown: 'ArrowDown', ArrowLeft: 'ArrowLeft', ArrowRight: 'ArrowRight', z: 'KeyZ', c: 'KeyC', '[': 'BracketLeft', ']': 'BracketRight' };

/** 같은 일을 하는 기존 키를 그 자리에 보낸다 — main.js 의 처리기를 그대로 거친다 */
function press(target, key, { ctrl = false, shift = false, alt = false } = {}) {
  const ev = new KeyboardEvent('keydown', { key, code: CODES[key] ?? key, ctrlKey: ctrl, shiftKey: shift, altKey: alt, bubbles: true, cancelable: true });
  (target instanceof Element ? target : document.body).dispatchEvent(ev);
}

const times = (n, fn) => {
  for (let i = 0; i < n; i++) fn();
};

/** 현재 줄부터 n 줄을 고른다 (Insert, Shift+↓) — 고른 줄을 담는다 */
function pickLines(target, n) {
  press(target, 'Insert');
  times(n - 1, () => press(target, 'ArrowDown', { shift: true }));
  keep();
}

/** 고른 줄의 원문을 담는다 (p·P 가 넣는다) */
function keep() {
  const span = litSpan();
  if (span) register = sourceLines().slice(span[0] - 1, span[1]);
}

const hereLine = () => S.pane?.here?.line ?? 1;

/** 원문 줄 n 으로 (끝을 넘으면 마지막 글 줄) */
function goTo(n) {
  const src = sourceLines();
  let last = src.length;
  while (last > 1 && !src[last - 1].trim()) last -= 1;
  followLine(Math.max(1, Math.min(n, last)));
}

/** 앞·뒤 제목으로 (dir 만큼) */
function goHeading(dir, n) {
  const heads = headsOf(sourceLines()).map((h) => h.n);
  let at = hereLine();
  for (let i = 0; i < n; i++) {
    const next = dir > 0 ? heads.find((x) => x > at) : heads.findLast((x) => x < at);
    if (next == null) break;
    at = next;
  }
  if (at !== hereLine()) followLine(at);
}

/** F2 로 칸을 열고 커서를 줄 처음(start)이나 끝으로 */
function edit(target, start) {
  press(target, 'F2');
  let tries = 0;
  const place = () => {
    const el = document.activeElement;
    if (el?.classList?.contains('lec-line-edit')) {
      const r = document.createRange();
      r.selectNodeContents(el);
      r.collapse(start);
      getSelection().removeAllRanges();
      getSelection().addRange(r);
    } else if (++tries < 40) setTimeout(place, 25);
  };
  setTimeout(place, 0);
}

function center() {
  S.pane?.scroller?.querySelector('.lec-here')?.scrollIntoView({ block: 'center' });
}

/** 현재 줄(Normal)의 명령: 글자 → (target, n, counted) */
const NORMAL = {
  j: (e, n) => times(n, () => press(e, 'ArrowDown')),
  k: (e, n) => times(n, () => press(e, 'ArrowUp')),
  gg: (e, n, counted) => goTo(counted ? n : 1),
  G: (e, n, counted) => goTo(counted ? n : Infinity),
  '[[': (e, n) => goHeading(-1, n),
  ']]': (e, n) => goHeading(1, n),
  zz: () => center(),
  zc: (e) => press(e, '[', { ctrl: true, shift: true }),
  zo: (e) => press(e, ']', { ctrl: true, shift: true }),
  za: (e) => {
    const before = S.pane?.view?.querySelectorAll('.lec-folded').length ?? 0;
    press(e, '[', { ctrl: true, shift: true });
    if ((S.pane?.view?.querySelectorAll('.lec-folded').length ?? 0) === before) press(e, ']', { ctrl: true, shift: true });
  },
  zM: () => foldAll(true),
  zR: () => foldAll(false),
  '/': () => openFind(),
  n: (e, n) => times(n, () => findStep(1)),
  N: (e, n) => times(n, () => findStep(-1)),
  ':': () => openPalette({ query: ':' }),
  i: (e) => edit(e, true),
  I: (e) => edit(e, true),
  a: (e) => edit(e, false),
  A: (e) => edit(e, false),
  o: (e) => press(e, 'Enter', { ctrl: true }),
  O: (e) => press(e, 'Enter', { ctrl: true, shift: true }),
  V: (e) => press(e, 'Insert'),
  v: (e) => press(e, 'Insert'),
  dd: (e, n) => {
    pickLines(e, n);
    if (litSpan()) press(e, 'Delete');
  },
  yy: (e, n) => {
    pickLines(e, n);
    if (!litSpan()) return;
    press(e, 'c', { ctrl: true });
    press(e, 'Escape');
  },
  '>>': (e, n) => {
    pickLines(e, n);
    if (!litSpan()) return;
    press(e, 'ArrowRight', { alt: true, shift: true });
    press(e, 'Escape');
  },
  '<<': (e, n) => {
    pickLines(e, n);
    if (!litSpan()) return;
    press(e, 'ArrowLeft', { alt: true, shift: true });
    press(e, 'Escape');
  },
  u: (e, n) => times(n, () => press(e, 'z', { ctrl: true })),
  p: () => putLinesHere(register, false),
  P: () => putLinesHere(register, true),
};

/** 고른 줄(Visual Line)의 명령 */
const VISUAL = {
  j: (e, n) => times(n, () => press(e, 'ArrowDown', { shift: true })),
  k: (e, n) => times(n, () => press(e, 'ArrowUp', { shift: true })),
  d: (e) => {
    keep();
    press(e, 'Delete');
  },
  x: (e) => {
    keep();
    press(e, 'Delete');
  },
  y: (e) => {
    keep();
    press(e, 'c', { ctrl: true });
    press(e, 'Escape');
  },
  '>': (e, n) => times(n, () => press(e, 'ArrowRight', { alt: true, shift: true })),
  '<': (e, n) => times(n, () => press(e, 'ArrowLeft', { alt: true, shift: true })),
  J: () => joinPicked(),
  V: (e) => press(e, 'Escape'),
  v: (e) => press(e, 'Escape'),
  u: (e, n) => times(n, () => press(e, 'z', { ctrl: true })),
};

const PREFIXES = new Set(['d', 'y', 'g', 'z', '[', ']', '>', '<']);

/**
 * main.js 의 keydown 이 부른다 (vi 키를 켰고, Ctrl·Alt 없이, 글 칸·입력 칸 밖의 문서에서). 다뤘으면 true — 부른 쪽이 기본 동작을 막는다
 */
export function viKey(e) {
  if (!viOn() || e.isComposing) return false;
  const ch = charOf(e);
  if (!ch) {
    if (pending || count) reset();
    return false;
  }
  if (lightOn()) return false;
  const picked = !!litSpan();
  if (!pending && /\d/.test(ch) && (count || ch !== '0')) {   // 앞의 숫자 (0 으로 시작하지 않는다)
    count += ch;
    arm();
    return true;
  }
  const seq = pending + ch;
  const counted = !!count;
  const n = Math.max(1, Math.min(500, parseInt(count || '1', 10)));
  const table = picked ? VISUAL : NORMAL;
  const cmd = Object.hasOwn(table, seq) ? table[seq] : null;
  if (!cmd) {
    if (!picked && !pending && PREFIXES.has(ch)) {
      pending = ch;
      arm();
      return true;
    }
    const swallowed = !!(pending || count);   // 기다리던 명령이 틀렸으면 그 글자는 버린다
    reset();
    return swallowed;
  }
  reset();
  cmd(e.target, n, counted);
  return true;
}

export function initViKeys() {
  show();
  on('vi-keys', reset);   // 설정 창에서 켜고 끌 때 (settings.js)
}
