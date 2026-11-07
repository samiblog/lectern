// 블록 펼치기 (D112): 수식·다이어그램·차트·머리 설정은 원문이 여러 줄이라 칸 하나로 고칠 수 없다.
// 그 블록의 원문을 코드 줄로 펼쳐 줄마다 같은 칸으로 고친다 (코드 블록의 줄 편집 그대로 — 새 편집기가 아니다). 그린 결과는 아래에 남는다.
// 파일은 그대로 두고 화면만 바꾼다. 다시 그리면 'rendered' 에서 다시 펼친다 (pane.unfold). Esc·접기 버튼·다른 문서로 가면 접는다.

import { on } from './store.js';
import { html, setHtml } from './html.js';
import { t } from './i18n.js';
import { forgetUnits } from './spotlight.js';

export const ATOMIC = 'pre.mermaid, pre.lec-chart, .diagram-error, .math-block';

let redraw = (_pane) => {};   // nav.refreshView — import 순환을 만들지 않으려고 init 에서 받는다

const spanOf = (el) => {
  const m = /^(\d+)-(\d+)$/.exec(el.dataset.lines || '');
  return m ? [+m[1], +m[2]] : null;
};

/** 머리 설정의 안쪽 줄 [a, b] — 없으면 null */
function frontSpan(src) {
  if (src[0]?.trim() !== '---') return null;
  const end = src.findIndex((s, i) => i > 0 && /^(?:---|\.\.\.)\s*$/.test(s));
  return end > 1 ? [2, end] : null;
}

/**
 * 펼친 상자를 만들어 before 자리에 놓는다. span: 안쪽 줄 [a, b], preview: 그린 결과 (아래에 남긴다)
 * @param {any} pane @param {Element} before @param {number[]} span @param {Element | null} preview
 */
function build(pane, before, span, preview) {
  const [a, b] = span;
  const wrap = document.createElement('div');
  wrap.className = 'lec-unfold';
  const bar = document.createElement('div');
  bar.className = 'lec-unfold-bar';
  setHtml(bar, html`<span>${t('원문 — 줄마다 고칩니다')}</span><button type="button">${t('접기 (Esc)')}</button>`);
  bar.querySelector('button').addEventListener('click', () => closeBlock(pane));
  const pre = document.createElement('pre');
  const code = document.createElement('code');
  code.dataset.lines = `${a}-${b}`;
  code.textContent = pane.source.lines.slice(a - 1, b).join('\n');
  pre.append(code);
  before.replaceWith(wrap);
  wrap.append(bar, pre);
  if (preview) {
    preview.removeAttribute('data-lines');   // 그린 결과는 줄 단위가 아니다 — 안쪽 코드 줄이 그 줄을 맡는다
    for (const el of preview.querySelectorAll('[data-lines]')) el.removeAttribute('data-lines');
    wrap.append(preview);
  }
  return wrap;
}

/** pane.unfold 대로 화면을 펼친다 */
function apply(pane) {
  const u = pane.unfold;
  const { view } = pane;
  if (!u) return;
  if (view.dataset.docPath !== u.path || !pane.source) {
    pane.unfold = null;
    return;
  }
  if (u.front) {
    const span = frontSpan(pane.source.lines);
    const el = view.querySelector('.front-matter');
    if (!span || !el) {
      pane.unfold = null;
      return;
    }
    build(pane, el, span, null).classList.add('lec-unfold-front');
    forgetUnits();
    return;
  }
  const el = [...view.querySelectorAll(ATOMIC)].find((x) => {
    const s = spanOf(x);
    return s && u.line >= s[0] && u.line <= s[1];
  });
  const span = el && spanOf(el);
  if (!span) {
    pane.unfold = null;
    return;
  }
  const inner = span[1] - span[0] >= 2 ? [span[0] + 1, span[1] - 1] : span;
  u.a = inner[0];
  const holder = document.createElement('div');
  el.replaceWith(holder);
  build(pane, holder, inner, el);
  forgetUnits();
}

/** 줄 line 이 든 블록을 펼친다. 펼쳤으면 고칠 첫 줄, 아니면 0 */
export function openBlock(pane, line) {
  closeQuietly(pane);
  pane.unfold = { path: pane.view.dataset.docPath, line };
  apply(pane);
  return pane.unfold?.a ?? 0;
}

/** 머리 설정을 펼친다. 고칠 첫 줄, 없으면 0 */
export function openFront(pane) {
  if (!frontSpan(pane.source?.lines ?? [])) return 0;
  closeQuietly(pane);
  pane.unfold = { path: pane.view.dataset.docPath, front: true };
  apply(pane);
  return pane.unfold ? 2 : 0;
}

function closeQuietly(pane) {
  if (!pane.unfold) return;
  pane.unfold = null;
  redraw(pane);
}

/** 접는다. 접었으면 true */
export function closeBlock(pane) {
  if (!pane?.unfold) return false;
  pane.unfold = null;
  redraw(pane);
  return true;
}

export function initLineBlock(refresh) {
  redraw = refresh;
  on('rendered', apply);
}
