// 블록 펼치기 (D112·D115): 수식·다이어그램·차트·머리 설정은 원문이 여러 줄이라 칸 하나로 고칠 수 없다.
// 화면 옆 패널에 원문을 코드 줄로 펼쳐 줄마다 같은 칸으로 고친다 (코드 블록의 줄 편집 그대로 — 새 편집기가 아니다).
// 블록은 그 자리에 그대로 있어 고친 결과가 보인다. 슬라이드의 칸은 작아서 칸 안에 펼치면 잘린다.
// 값이 문서 안에 있는 vega-lite 차트는 값 표로 연다 (chartops.js) — 사람은 JSON 을 보지 않는다. '원문 보기' 로 줄을 볼 수 있다.
// 파일은 그대로 두고 화면만 바꾼다. 다시 그리면 'rendered' 에서 다시 펼친다 (pane.unfold). Esc·접기 버튼·다른 문서로 가면 접는다.

import { on, emit } from './store.js';
import { html, setHtml } from './html.js';
import { t } from './i18n.js';
import { forgetUnits } from './spotlight.js';
import { readValues, chartKind } from './chartops.js';

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

/** 패널의 머리줄 */
function barOf(pane, title, extra = []) {
  const bar = document.createElement('div');
  bar.className = 'lec-unfold-bar';
  setHtml(bar, html`<span>${title}</span>`);
  bar.append(...extra);
  const fold = document.createElement('button');
  fold.type = 'button';
  fold.textContent = t('접기 (Esc)');
  fold.addEventListener('click', () => closeBlock(pane));
  bar.append(fold);
  return bar;
}

function buttonOf(label, action, on_ = false) {
  const b = document.createElement('button');
  b.type = 'button';
  b.textContent = label;
  b.classList.toggle('on', on_);
  b.addEventListener('click', action);
  return b;
}

/** 원문 줄 패널 */
function codePanel(pane, [a, b], extra) {
  const wrap = document.createElement('div');
  wrap.className = 'lec-unfold';
  const pre = document.createElement('pre');
  const code = document.createElement('code');
  code.dataset.lines = `${a}-${b}`;
  code.textContent = pane.source.lines.slice(a - 1, b).join('\n');
  pre.append(code);
  code.addEventListener('dblclick', (e) => {   // 누른 줄을 연다 — 패널은 본문 자리와 겹치므로 줄을 여기서 찾는다
    e.stopPropagation();
    const r = code.getBoundingClientRect();
    const rows = Math.max(1, b - a + 1);
    emit('line-open', { line: a + Math.min(rows - 1, Math.max(0, Math.floor((e.clientY - r.top) / (r.height / rows)))) });
  });
  wrap.append(barOf(pane, t('원문 — 줄마다 고칩니다'), extra), pre);
  return wrap;
}

/** 값 표 패널 */
function valuesPanel(pane, data, kind) {
  const u = pane.unfold;
  const wrap = document.createElement('div');
  wrap.className = 'lec-unfold lec-unfold-values';
  const table = document.createElement('table');
  table.className = 'lec-values';
  setHtml(table, [html`<thead><tr>${data.fields.map((f) => html`<th>${f}</th>`)}</tr></thead>`,
    html`<tbody>${data.rows.map((row, r) => html`<tr>${row.map((v, c) => html`<td><input data-r="${r}" data-c="${c}" value="${v}" spellcheck="false" autocomplete="off"></td>`)}</tr>`)}</tbody>`]);
  /** @returns {HTMLInputElement | null} */
  const cell = (r, c) => table.querySelector(`input[data-r="${r}"][data-c="${c}"]`);
  const rowsNow = () => data.rows.map((row, r) => row.map((_, c) => cell(r, c)?.value ?? ''));
  const save = (rows = rowsNow()) => emit('chart-values', { pane, fields: data.fields, rows });
  const go = (r, c) => {
    u.focus = { r, c };
    const el = cell(r, c);
    el?.focus();
    el?.select();
  };
  table.addEventListener('change', () => save());
  table.addEventListener('focusin', (e) => {
    const el = /** @type {HTMLInputElement} */ (e.target);
    if (el.dataset.r != null) u.focus = { r: +el.dataset.r, c: +el.dataset.c };
  });
  table.addEventListener('keydown', (e) => {
    const el = /** @type {HTMLInputElement} */ (e.target);
    if (e.isComposing || e.keyCode === 229 || el.dataset.r == null) return;
    const r = +el.dataset.r;
    const c = +el.dataset.c;
    const mod = e.ctrlKey || e.metaKey;
    e.stopPropagation();
    if (e.key === 'Enter' && mod) {
      e.preventDefault();
      const rows = rowsNow();
      rows.splice(r + 1, 0, data.fields.map(() => ''));
      u.focus = { r: r + 1, c: 0 };
      save(rows);
    } else if (mod && e.shiftKey && e.code === 'KeyK') {
      e.preventDefault();
      const rows = rowsNow();
      if (rows.length < 2) return;
      rows.splice(r, 1);
      u.focus = { r: Math.max(0, r - 1), c };
      save(rows);
    } else if (e.key === 'Enter' || e.key === 'ArrowDown') {
      e.preventDefault();
      go(Math.min(data.rows.length - 1, r + 1), c);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      go(Math.max(0, r - 1), c);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      el.blur();
      closeBlock(pane);
    }
  });
  const kinds = [['bar', t('막대')], ['line', t('선')], ['area', t('영역')], ['arc', t('원')]];
  const foot = document.createElement('div');
  foot.className = 'lec-unfold-foot';
  foot.append(buttonOf(t('행 더하기'), () => {
    u.focus = { r: data.rows.length, c: 0 };
    save([...rowsNow(), data.fields.map(() => '')]);
  }), ...(kind ? kinds.map(([id, name]) => buttonOf(name, () => emit('chart-kind', { pane, kind: id }), id === kind)) : []));
  const raw = buttonOf(t('원문 보기'), () => {
    u.raw = true;
    apply(pane);
  });
  const scroll = document.createElement('div');
  scroll.className = 'lec-values-box';
  scroll.append(table);
  wrap.append(barOf(pane, t('차트 값 — 칸마다 고칩니다'), [raw]), scroll, foot);
  wrap.dataset.key = JSON.stringify([data, kind]);
  u.refocus = () => {
    const f = u.focus ?? { r: 0, c: 0 };
    go(Math.min(f.r, data.rows.length - 1), f.c);
  };
  return wrap;
}

/** pane.unfold 대로 패널을 놓는다 */
function apply(pane) {
  const u = pane.unfold;
  const { view } = pane;
  if (!u) return;
  if (view.dataset.docPath !== u.path || !pane.source) {
    pane.unfold = null;
    return;
  }
  const src = pane.source.lines;
  let span = null;
  if (u.front) span = frontSpan(src);
  else {
    const el = [...view.querySelectorAll(ATOMIC)].find((x) => {
      const s = spanOf(x);
      return s && u.line >= s[0] && u.line <= s[1];
    }) ?? null;
    const whole = el && spanOf(el);
    if (whole) {
      span = whole[1] - whole[0] >= 2 ? [whole[0] + 1, whole[1] - 1] : whole;
      el.removeAttribute('data-lines');   // 그린 결과는 줄 단위가 아니다 — 패널의 코드 줄이 그 줄을 맡는다
      for (const x of el.querySelectorAll('[data-lines]')) x.removeAttribute('data-lines');
      el.classList.add('lec-unfolded');
    } else if (u.a && view.querySelector('.lec-unfolded')) span = [u.a, u.b];   // 다시 그리지 않고 값 표와 원문을 오갈 때
  }
  view.querySelector(':scope > .lec-unfold')?.remove();
  if (!span) {
    pane.unfold = null;
    forgetUnits();
    return;
  }
  [u.a, u.b] = span;
  const text = src.slice(span[0] - 1, span[1]).join('\n');
  const vega = !u.front && /^\s*(?:`{3,}|~{3,})\s*vega-lite\b/.test(src[span[0] - 2] ?? '');
  const data = vega && !u.raw ? readValues(text) : null;
  u.values = !!data;
  if (data) {
    const kind = chartKind(text);
    const panel = u.panel?.dataset.key === JSON.stringify([data, kind]) ? u.panel : valuesPanel(pane, data, kind);   // 같은 값이면 그 칸을 그대로 — 치던 글이 사라지지 않게
    u.panel = panel;
    view.append(panel);
    u.refocus();
  } else {
    u.panel = null;
    const extra = vega && readValues(text) ? [buttonOf(t('값 표로 보기'), () => {
      u.raw = false;
      apply(pane);
    })] : [];
    const panel = codePanel(pane, span, extra);
    if (u.front) panel.classList.add('lec-unfold-front');
    view.append(panel);
  }
  forgetUnits();
}

/** 줄 line 이 든 블록을 펼친다. 펼쳤으면 고칠 첫 줄, 아니면 0 */
export function openBlock(pane, line) {
  pane.unfold = { path: pane.view.dataset.docPath, line };
  redraw(pane);   // 앞서 펼친 패널이 지운 data-lines 를 되살리고 'rendered' 에서 펼친다
  return line;
}

/** 머리 설정을 펼친다. 고칠 첫 줄, 없으면 0 */
export function openFront(pane) {
  if (!frontSpan(pane.source?.lines ?? [])) return 0;
  pane.unfold = { path: pane.view.dataset.docPath, front: true };
  apply(pane);
  return pane.unfold ? 2 : 0;
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
