// 차트의 데이터 (D136): 그린 차트 오른쪽 위의 [표]·[복사] 단추 — 차트를 그리는 데 쓴 데이터를 표로 보이고 복사한다.
// - 데이터는 그 차트 블록의 설정(문서 안의 값)을 파싱해 얻는다 — 라이브러리 속을 보지 않고, 누를 때만 읽는다.
//   Vega-Lite 의 values·datasets·겹친 층, Vega 의 data[].values, ECharts 의 dataset·series·축, Plotly 의 trace.
// - CSV 를 가리키는 차트(data.url)는 표를 만들지 않고 '문서 안으로 넣으면 보인다'고 알린다 — CSV 는 문서와 함께 가지 않을 수 있다
//   (다른 PC 의 Lectern 에서는 차트도 그려지지 않는다). '문서 안으로 넣기'를 누르면 그 CSV 를 읽어 data 를 values 로 바꿔 저장한다
//   (chartops.inlineUrlData — 저장은 lineedit.js 의 'chart-inline').
// - 변환·집계가 있으면 표는 변환 전 값이라고 적는다. 30행이 넘으면 처음·끝과 일정 간격의 행만 (모두 보기로 5,000행까지).
// - 단추와 표는 차트 칸(pre.lec-chart) 안에 둔다 — 캡션 찾기·줄 단위가 차트의 앞뒤 형제를 보기 때문. 인쇄·PDF 에는 나오지 않는다.
//   Lectern 슬라이드의 차트와 Graphviz(데이터가 없는 도해)에는 달지 않는다.

import { S, emit } from './store.js';
import { html, setHtml } from './html.js';
import { toast, docUrl } from './util.js';
import { t, LANG } from './i18n.js';
import { parseCsv, delimiterOf } from './tabledata.js';
import { csvRecords, csvText, chartData, thinRows, tableText } from './chartops.js';
import { copyParts, tableMarkup } from './tablecopy.js';

const SHOW_MAX = 30;   // chartops.thinRows 의 기본
const ALL_MAX = 5000;
const ASK_ROWS = 500;   // 문서 안으로 넣을 때 이보다 많으면 묻는다
const state = new WeakMap();   // 차트 칸 → {ctx, parse, open, all}
// 펼쳐 둔 표 — 문서를 다시 그리면(Claude 가 고침·자동 새로고침) 칸이 새로 생긴다. 같은 문서의 같은 원문이면 다시 펼친다
const kept = new Map();   // '탭 id|경로|원문' → {all}
let reopen = null;        // 문서 안으로 넣은 뒤 그 차트를 다시 펼치기 — {key: '탭 id|경로', a, until}
const keyOf = (node, ctx) => `${ctx?.tab?.id}|${ctx?.path}|${node.dataset.source || ''}`;

function remember(node) {
  const st = state.get(node);
  const key = keyOf(node, st.ctx);
  kept.delete(key);
  if (st.open) kept.set(key, { all: st.all });
  while (kept.size > 40) kept.delete(kept.keys().next().value);
}

// ---- 화면 ----------------------------------------------------------------------------------

const fmt = (v) => (typeof v === 'number' ? v.toLocaleString(LANG === 'en' ? 'en-US' : 'ko-KR', { maximumFractionDigits: 6 }) : v == null ? '' : String(v));

function dataOf(node) {
  const st = state.get(node);
  let spec = null;
  try {
    spec = st.parse(node.dataset.source || '');
  } catch { /* 그려졌으니 드물다 */ }
  return chartData(node.dataset.chart, spec, (n) => t('계열 {n}', { n }));
}

function tableHtml(tb, all) {
  const numeric = tb.fields.map((_, c) => tb.rows.some((r) => typeof r[c] === 'number'));
  const { items, step } = all ? thinRows(Math.min(tb.rows.length, ALL_MAX), ALL_MAX) : thinRows(tb.rows.length, SHOW_MAX);
  const head = html`<tr>${tb.fields.map((f, c) => html`<th class="${numeric[c] ? 'num' : ''}">${f}</th>`)}</tr>`;
  const body = items.map((it) => (it.skip
    ? html`<tr class="skip"><td colspan="${tb.fields.length}">${t('… {n}행 건너뜀', { n: it.skip })}</td></tr>`
    : html`<tr>${tb.rows[it.i].map((v, c) => html`<td class="${numeric[c] ? 'num' : ''}">${fmt(v)}</td>`)}</tr>`));
  const shown = items.filter((it) => !it.skip).length;
  const size = t('{rows}행 {cols}열', { rows: tb.rows.length, cols: tb.fields.length });
  const thin = shown < tb.rows.length ? (all ? t('처음 {n}행만', { n: ALL_MAX }) : t('{n}행 보임 — 약 {step}행마다', { n: shown, step })) : '';
  const toggle = tb.rows.length > SHOW_MAX ? html`<button type="button" class="text-btn" data-act="all">${all ? t('줄여 보기') : t('모두 보기')}</button>` : '';
  return html`<div class="cd-head"><b>${tb.name || t('데이터')}</b><span>${size}${thin ? ` · ${thin}` : ''}</span>${toggle}</div>
    <div class="table-wrap"><table><thead>${head}</thead><tbody>${body}</tbody></table></div>`;
}

function renderPanel(node) {
  const st = state.get(node);
  let panel = node.querySelector(':scope > .lec-chart-data');
  if (!st.open) {
    panel?.remove();
    return;
  }
  if (!panel) {
    panel = document.createElement('div');
    panel.className = 'lec-chart-data';
    node.append(panel);
  }
  const d = dataOf(node);
  const notes = [];
  if (d.transform && d.tables.length) notes.push(html`<p class="cd-note">${t('차트는 이 값을 변환·집계해 그립니다 — 표는 변환 전 값입니다')}</p>`);
  if (d.urls.length) {
    notes.push(html`<p class="cd-note">${t('이 차트의 데이터는 {url} 에 있습니다 — 문서 안으로 넣으면 다른 PC 에서도 차트와 표가 보입니다', { url: d.urls.join(', ') })}
 <button type="button" class="text-btn" data-act="inline">${t('데이터를 문서 안으로 넣기')}</button></p>`);
  }
  if (d.generated) notes.push(html`<p class="cd-note">${t('이 차트는 데이터를 만들어 그립니다 (sequence 등) — 표로 볼 값이 없습니다')}</p>`);
  if (!d.tables.length && !d.urls.length && !d.generated) notes.push(html`<p class="cd-note">${t('이 차트에서 표로 볼 데이터를 찾지 못했습니다')}</p>`);
  setHtml(panel, [...d.tables.map((tb) => tableHtml(tb, st.all)), ...notes]);
}

function toggle(node) {
  const st = state.get(node);
  st.open = !st.open;
  node.querySelector(':scope > .lec-chart-tools [data-act="table"]')?.setAttribute('aria-pressed', String(st.open));
  remember(node);
  renderPanel(node);
}

function copy(node) {
  const d = dataOf(node);
  if (!d.tables.length) {
    toast(d.urls.length ? t('데이터가 {url} 에 있어 복사할 값이 없습니다 — 문서 안으로 넣으면 복사할 수 있습니다', { url: d.urls[0] }) : t('이 차트에서 복사할 데이터를 찾지 못했습니다'));
    return;
  }
  const tsv = d.tables.map((tb) => (d.tables.length > 1 && tb.name ? `${tb.name}\n` : '') + tableText(tb)).join('\n\n');
  const markup = d.tables.map((tb) => tableMarkup([tb.fields.map((f) => ({ text: f, head: true })),
    ...tb.rows.map((r) => r.map((v) => ({ text: v == null ? '' : String(v), align: typeof v === 'number' ? 'right' : '' })))])).join('<br>');
  const rows = d.tables.reduce((n, tb) => n + tb.rows.length, 0);
  copyParts({ 'text/plain': tsv, 'text/html': markup }, t('차트 데이터 {n}행', { n: rows }));
}

/** CSV 를 읽어 그 차트의 data 를 문서 안의 값으로 (저장은 lineedit.js — 'chart-inline') */
async function inline(node) {
  const st = state.get(node);
  const { ctx } = st;
  const lines = /^(\d+)-(\d+)$/.exec(node.dataset.lines || '');
  const d = dataOf(node);
  if (!lines || !d.urls.length || !ctx?.tab) return;
  const base = new URL(docUrl(ctx.tab, ctx.path), location.origin);
  const prefix = `/doc/${ctx.tab.id}/`;
  const data = {};
  for (const url of d.urls) {
    const target = new URL(url, base);
    if (target.origin !== location.origin || !target.pathname.startsWith(prefix)) {
      toast(t('데이터는 이 프로젝트 안의 파일만 읽습니다 — 문서 기준 상대경로로 적으세요: {url}', { url }), 'error');
      return;
    }
    try {
      const res = await fetch(target.pathname, { cache: 'no-store' });
      if (!res.ok) throw new Error(String(res.status));
      const text = csvText(await res.text());
      const name = decodeURIComponent(target.pathname);
      data[url] = name.toLowerCase().endsWith('.json') ? JSON.parse(text) : csvRecords(parseCsv(text, delimiterOf(text, name)).rows);
      if (!Array.isArray(data[url])) throw new Error('not rows');
    } catch {
      toast(t('데이터 파일을 읽지 못했습니다 — 경로를 확인하세요: {url}', { url }), 'error');
      return;
    }
  }
  const total = Object.values(data).reduce((n, rows) => n + (Array.isArray(rows) ? rows.length : 0), 0);
  if (total > ASK_ROWS && !window.confirm(t('{n}행을 문서 안에 넣습니다 — 문서가 길어집니다. 넣을까요?', { n: total.toLocaleString() }))) return;
  reopen = { key: `${ctx.tab.id}|${ctx.path}`, a: Number(lines[1]), until: Date.now() + 20000 };
  emit('chart-inline', { pane: S.pane, a: Number(lines[1]), b: Number(lines[2]), data });
}

/**
 * 그린 차트에 [표]·[복사] 단추를 단다 (charts.js 가 그릴 때마다 — 다시 그리면 칸의 안을 바꿔 끼우므로 표를 펼쳐 두었으면 다시 그린다).
 * parse 는 charts.js 의 parseSpec (가져오면 import 가 돈다)
 */
export function addChartTools(node, ctx, parse) {
  if (node.dataset.chart === 'dot' || node.closest('.lec-slide, .lec-deck')) return;
  let st = state.get(node);
  if (!st) {
    const was = kept.get(keyOf(node, ctx));
    const again = reopen && reopen.until > Date.now() && reopen.key === `${ctx?.tab?.id}|${ctx?.path}` && node.dataset.lines?.startsWith(`${reopen.a}-`);
    if (again) reopen = null;
    st = { open: !!was || !!again, all: !!was?.all };
    state.set(node, st);
  }
  Object.assign(st, { ctx, parse });
  if (st.open) remember(node);
  const tools = document.createElement('div');
  tools.className = 'lec-chart-tools';
  setHtml(tools, [html`<button type="button" data-act="table" aria-pressed="${String(st.open)}" title="${t('차트를 그린 데이터를 표로 보기')}">${t('표')}</button>`,
    html`<button type="button" data-act="copy" title="${t('차트 데이터 복사 — 엑셀에 붙이면 칸이 나뉩니다')}">${t('복사')}</button>`]);
  node.append(tools);
  if (st.open) renderPanel(node);
}

export function initChartData() {
  document.addEventListener('click', (e) => {
    const btn = e.target.closest?.('pre.lec-chart > .lec-chart-tools button, pre.lec-chart > .lec-chart-data button');
    if (!btn) return;
    const node = btn.closest('pre.lec-chart');
    if (!state.has(node)) return;
    e.preventDefault();
    e.stopPropagation();
    const act = btn.dataset.act;
    if (act === 'table') toggle(node);
    else if (act === 'copy') copy(node);
    else if (act === 'all') {
      const st = state.get(node);
      st.all = !st.all;
      remember(node);
      renderPanel(node);
    } else if (act === 'inline') inline(node);
  }, true);
}
