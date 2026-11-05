// CSV 보기 (D60): 코드 화면(codeview.js)이 csv·tsv 파일을 표로 그린다 — 머리행 아래 열마다 거르기 칸, 머리행을 누르면 정렬,
// 표 위의 통계 줄(숫자 열: 개수·합계·평균·최소·최대·중앙값, 글자 열: 개수·고유값·가장 많은 값 — 거르면 남은 행으로).
//
// - 행은 tr.cv-line[data-line] (원문의 첫 줄, 따옴표 안 줄바꿈으로 여러 줄이면 data-end) — 코드 화면처럼 우클릭 메뉴의
//   '이 줄 복사'·'Claude용 위치 복사', 편집 모드의 위치 잇기, 찾기가 그대로 된다.
// - 머리행은 어림한다 (첫 줄에 숫자가 없고, 아래에 숫자가 많은 열이 있거나 첫 줄 값이 모두 다르면). 막대의 '첫 줄은 머리행'으로 바꾼다.
// - 숫자: 1,234 / -3.5% / $105 / 12억 같은 표기도 숫자로 (doc.js 의 숫자 열과 같은 규칙). 70% 이상이 숫자면 숫자 열.
// - 그리는 행은 MAX_SHOW 까지 (통계·개수는 거른 행 전부로). 거르기·정렬·머리행은 파일마다 이번 실행 동안 기억한다.
// - 엑셀 보기(D77)도 이 표로 그린다 (renderRows — 행은 엑셀의 행 번호, 열 이름 앞에 엑셀의 열 글자, 수식 칸은 마우스를 올리면 수식).
// - 분석 (D86): 막대에 자료 요약(주기·기간·숫자 열·빈칸 — 거른 행으로), 열 머리 우클릭의 계산 열, '차트로 보기'(quickchart.js), 보이는 표 복사·문서로 보내기.
//   계산 열은 화면에만 있다 — 파일에는 쓰지 않고, 다시 그려도 남지만 파일을 다시 열면 없다 (st.calcs — mem 에 두지 않는다).
//   값은 거른 행으로 시간 차례에 계산한다: 품목으로 거른 뒤 계산하면 그 품목의 시계열이 된다. 계산 열의 거르기는 계산한 뒤에 적용한다.
// - 표 영역 (D86): 제목 줄·여러 줄 머리행·표 여럿인 시트는 tabledata.js 의 findRegions 로 나눠 가장 큰 표를 보이고, 막대 위의 단추로 다른 표·시트 전체를 고른다.
//   깔끔한 시트(plain)는 단추가 없고 전과 같다. 머리행 줄 수와 고른 표는 이번 실행 동안 기억한다 (st.root). 고른 표마다 거르기·정렬이 따로다 (st.mem).

import { S } from './store.js';
import { saveConfig } from './api.js';
import { addHtml, html, setHtml } from './html.js';
import { basename, toast, copyText } from './util.js';
import { t } from './i18n.js';
import {
  numberOf, isMissing, decimalsOf, findTimeColumn, periodText, hasSameTimes, calcValues, calcText, findRegions, reshapeRegion, regionOfLines, headerIsTime,
  parseCsv, delimiterOf,
} from './tabledata.js';
import { openChart, frequencyName } from './quickchart.js';
import { snippetOf, sendSnippets } from './basket.js';

export { numberOf };

export const TABLE_EXT = new Set(['csv', 'tsv']);
const MAX_SHOW = 2000;
const MAX_SEND = 500;   // 문서로 보낼 표의 행 — 긴 표는 거른 뒤에
const MAX_DEPTH = 6;    // 머리행 줄 수
const MA_SPANS = { D: [5, 20], W: [4, 13], M: [3, 12], Q: [4, 8], H: [2, 4], Y: [3, 5] };
const memory = new Map();   // 탭 id + 경로 (+ 고른 표) → {filters, sort, header} (다시 그려도 그대로). 파일마다의 것에 고른 표 region·머리행 줄 수 depth·지정한 범위 custom

export const isTableFile = (path) => TABLE_EXT.has(path.split('.').pop().toLowerCase());

/** 첫 줄이 머리행인지 어림한다 */
function guessHeader(rows) {
  if (rows.length < 2) return false;
  const first = rows[0];
  if (headerIsTime(first)) return true;   // 항목, 2024, 2025 — 숫자로 읽혀도 머리행이다
  if (first.some((c) => numberOf(c) != null) || first.some((c) => !c.trim())) return false;
  const body = rows.slice(1, 200);
  const numericBelow = first.some((_, c) => {
    const vals = body.map((r) => r[c]).filter((v) => v != null && String(v).trim());
    return vals.length && vals.filter((v) => numberOf(v) != null).length / vals.length >= 0.7;
  });
  return numericBelow || new Set(first).size === first.length;
}

export const colName = (i) => {   // A, B, …, Z, AA, … (머리행이 없을 때, 엑셀의 열 글자)
  let s = '';
  for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + ((n - 1) % 26)) + s;
  return s;
};

/** 거르기 칸의 글 → (칸 값) => 맞는지. 숫자 비교 >·>=·<·<=·=·!= 와 범위 a..b, !글자 는 빼기, =글자 는 같은 것, 그 밖은 포함 */
export function matcherOf(query) {
  const q = query.trim();
  if (!q) return null;
  const range = /^(-?[\d.,]+)\s*\.\.\s*(-?[\d.,]+)$/.exec(q);
  if (range) {
    const [a, b] = [numberOf(range[1]), numberOf(range[2])];
    if (a != null && b != null) return (v) => { const n = numberOf(v); return n != null && n >= Math.min(a, b) && n <= Math.max(a, b); };
  }
  const cmp = /^(>=|<=|!=|>|<|=)\s*(.+)$/.exec(q);
  if (cmp && numberOf(cmp[2]) != null) {
    const x = numberOf(cmp[2]);
    const test = { '>': (n) => n > x, '>=': (n) => n >= x, '<': (n) => n < x, '<=': (n) => n <= x, '=': (n) => n === x, '!=': (n) => n !== x }[cmp[1]];
    return (v) => { const n = numberOf(v); return n != null && test(n); };
  }
  const low = (s) => String(s ?? '').toLowerCase();
  if (q.startsWith('!') && q.length > 1) {
    const w = low(q.slice(1));
    return (v) => !low(v).includes(w);
  }
  if (q.startsWith('=') && q.length > 1) {
    const w = low(q.slice(1)).trim();
    return (v) => low(v).trim() === w;
  }
  const w = low(q);
  return (v) => low(v).includes(w);
}

// ---- 통계 ---------------------------------------------------------------------------------

function format(n, digits) {
  return n.toLocaleString(document.documentElement.lang || undefined, { maximumFractionDigits: Math.min(6, digits) });
}

/** 열 하나의 통계 (칸 값들 — 거른 행) */
export function statsOf(values, numeric) {
  const filled = values.filter((v) => String(v ?? '').trim());
  const out = { count: filled.length, empty: values.length - filled.length };
  if (numeric) {
    const nums = filled.map(numberOf).filter((n) => n != null).sort((a, b) => a - b);
    if (!nums.length) return out;
    const dec = Math.max(0, ...filled.slice(0, 500).map(decimalsOf));
    const sum = nums.reduce((a, b) => a + b, 0);
    const mid = nums.length >> 1;
    Object.assign(out, {
      numbers: nums.length, dec, sum, mean: sum / nums.length, min: nums[0], max: nums[nums.length - 1],
      median: nums.length % 2 ? nums[mid] : (nums[mid - 1] + nums[mid]) / 2,
    });
  } else {
    const freq = new Map();
    for (const v of filled) freq.set(v.trim(), (freq.get(v.trim()) || 0) + 1);
    let top = null;
    for (const [v, n] of freq) if (!top || n > top[1]) top = [v, n];
    Object.assign(out, { unique: freq.size, top });
  }
  return out;
}

function statsHtml(s, numeric) {
  const row = (label, value) => html`<div><span>${label}</span><b>${value}</b></div>`;
  /** @type {Markup[]} */
  const markup = [row(t('개수'), format(s.count, 0)), (s.empty ? row(t('빈칸'), format(s.empty, 0)) : '')];
  if (numeric && s.numbers) {
    markup.push([row(t('합계'), format(s.sum, s.dec)), row(t('평균'), format(s.mean, s.dec + 2)), row(t('최소'), format(s.min, s.dec)), row(t('최대'), format(s.max, s.dec)), row(t('중앙값'), format(s.median, s.dec + 1))]);
  } else if (!numeric && s.top) {
    markup.push(row(t('고유값'), format(s.unique, 0)));
    if (s.top[1] > 1) markup.push(row(t('최빈'), `${s.top[0].length > 18 ? `${s.top[0].slice(0, 17)}…` : s.top[0]} (${format(s.top[1], 0)})`));   // 모두 다르면 뜻이 없다
  }
  return markup;
}

// ---- 그리기 ---------------------------------------------------------------------------------

// ---- 표 영역 (D86) -------------------------------------------------------------------------

function memoryOf(key) {
  if (!memory.has(key)) memory.set(key, { filters: [], sort: null, header: null, depth: {} });
  return memory.get(key);
}

/** 시트의 표들을 찾는다 (사용자가 지정한 범위가 있으면 맨 뒤에) */
function loadRegions(st) {
  const { rows, lines, merges } = st.grid;
  Object.assign(st, findRegions(rows, lines, merges));
  const mark = st.root.custom && regionOfLines(rows, lines, merges, ...st.root.custom);
  if (mark) st.regions.push({ ...mark, custom: true });
}

/** 고른 표를 보일 행으로 — 시트 전체면 받은 그대로. line: 이 줄이 보여야 한다 (링크·뒤로 — 고른 표에 없으면 그 줄이 든 표로, 없으면 시트 전체로) */
function pickRegion(st, line = null) {
  const { root, regions, grid } = st;
  const auto = st.plain ? 'all' : st.best;
  let pick = root.region === 'all' || regions[root.region] ? root.region ?? auto : auto;
  const has = (r) => r?.lines.some(([a, b]) => line >= a && line <= b);
  if (line != null && pick !== 'all' && !has(regions[pick])) {
    const hit = regions.findIndex(has);
    pick = hit >= 0 ? hit : 'all';
    root.region = pick;
  }
  st.pick = pick;
  let region = pick === 'all' ? null : regions[pick];
  if (region && root.depth[pick] != null) region = { ...reshapeRegion(grid.rows, grid.lines, grid.merges, region, root.depth[pick]), custom: region.custom };
  st.region = region;
  st.letter = st.baseLetter;
  st.titleOf = st.baseTitle;
  if (!region) {
    Object.assign(st, { rows: grid.rows, lines: grid.lines, mem: root });
    return;
  }
  const head = region.depth > 0;
  Object.assign(st, {
    rows: head ? [region.headers, ...region.rows] : region.rows, lines: head ? [[0, 0], ...region.lines] : region.lines,
    mem: memoryOf(`${st.key}#${pick}`),
  });
  st.mem.header = head;
  if (st.baseLetter) st.letter = (c) => st.baseLetter(c + region.c0);
  if (st.baseTitle) st.titleOf = (line, c) => st.baseTitle(line, c + region.c0);
}

/** 표의 자리 글 (엑셀 A5:F20, csv 3~20행) */
function regionRef(st, r) {
  const first = r.lines[0]?.[0] ?? 0;
  const last = r.lines.at(-1)?.[1] ?? first;
  const top = st.grid.lines ? st.grid.lines[r.top]?.[0] ?? first : first;
  if (!st.baseLetter) return t('{a}~{b}행', { a: top, b: last });
  return `${st.baseLetter(r.c0)}${top}:${st.baseLetter(r.c1)}${last}`;
}

/** 막대 위의 표 단추 — 깔끔한 시트면 감춘다 */
function drawRegions(view) {
  const st = /** @type {CsvState} */ (view.csv);
  const bar = view.querySelector('.csv-regions');
  bar.hidden = st.plain && !st.root.custom;
  view.querySelector('.csv-headrow').hidden = !!st.region;
  if (bar.hidden) return;
  const name = (r, i) => (r.custom ? t('지정한 표') : t('표 {n}', { n: i + 1 }));
  const chips = st.regions.map((r, i) => html`<button type="button" class="csv-region" data-region="${i}" aria-pressed="${st.pick === i}" title="${r.titles.join(' · ')}">${name(r, i)}<small>${regionRef(st, r)}</small></button>`);
  const all = html`<button type="button" class="csv-region" data-region="all" aria-pressed="${st.pick === 'all'}">${st.baseLetter ? t('시트 전체') : t('파일 전체')}</button>`;
  const depth = st.region ? [html`<span class="csv-depth">${t('머리행')}<button type="button" data-depth="-1" aria-label="${t('머리행 줄이기')}">−</button><b>${t('{n}줄', { n: st.region.depth })}</b>`, html`<button type="button" data-depth="1" aria-label="${t('머리행 늘리기')}">+</button></span>`] : '';
  const title = st.region?.titles.length ? html`<span class="csv-title">${st.region.titles.join(' · ')}</span>` : '';
  setHtml(bar, [chips, all, depth, title]);
  bar.title = t('시트를 표로 나눠 봅니다 — 틀리면 시트 전체나 머리행 단추로 바로잡습니다');
}

/** 다른 표로 — 계산 열은 그 표의 것이라 뺀다 */
function selectRegion(view, pick) {
  const st = /** @type {CsvState} */ (view.csv);
  st.root.region = pick;
  st.calcs = [];
  pickRegion(st);
  drawRegions(view);
  build(view);
}

function stepDepth(view, step) {
  const st = /** @type {CsvState} */ (view.csv);
  const r = st.region;
  if (!r) return;
  const next = Math.max(0, Math.min(MAX_DEPTH, r.depth + step, r.depth + r.rows.length - 1));
  if (next === r.depth) return;
  st.root.depth[st.pick] = next;
  st.calcs = [];
  st.mem.filters = [];
  st.mem.sort = null;
  pickRegion(st);
  drawRegions(view);
  build(view);
}

/** 하이라이트한 줄을 표로 (docmenu.js 의 선택 상자) */
export function markRange(view, range) {
  const st = /** @type {CsvState} */ (view.csv);
  st.root.custom = range;
  loadRegions(st);
  const i = st.regions.findIndex((r) => r.custom);
  if (i < 0) {
    st.root.custom = null;
    toast(t('값이 있는 행이 없습니다'));
    return;
  }
  delete st.root.depth[i];
  selectRegion(view, i);
}

// ---- 계산 열 (D86) -------------------------------------------------------------------------

const calcLabel = ({ kind, n }) => ({
  pop: t('전기 대비 %'), yoy: t('전년 동기 대비 %'), diff: t('차분'), cum: t('누적'), ma: t('이동평균 {n}', { n }), index: t('지수 (첫 값=100)'),
})[kind];

/** 행마다 계산 열의 글을 붙인 표. idx: 거른 행 (계산은 이 행들로) */
function withCalcs(st, raw, idx) {
  const { calcs, width, time } = st;
  st.calcBlocked = false;
  if (!calcs.length) return raw;
  const body = raw.map((r) => {
    const row = Array.from({ length: width + calcs.length }, () => '');
    for (let c = 0; c < width; c++) row[c] = r[c] ?? '';
    return row;
  });
  const order = time ? idx.filter((i) => time.parsed[i]).sort((a, b) => time.parsed[a].at - time.parsed[b].at) : idx;
  const parsed = time ? order.map((i) => time.parsed[i]) : null;
  st.calcBlocked = !!time && hasSameTimes(parsed, time.freq);   // 품목별로 쌓은 표 — 앞 행이 앞 시점이 아니다
  calcs.forEach((calc, k) => {
    if (st.calcBlocked) return;
    const values = order.map((i) => (isMissing(raw[i][calc.col]) ? null : numberOf(raw[i][calc.col])));
    const res = calcValues(calc.kind, values, { n: calc.n, parsed, freq: time?.freq ?? null });
    const dec = Math.max(0, ...order.slice(0, 500).map((i) => decimalsOf(raw[i][calc.col])));
    const digits = calc.kind === 'ma' ? Math.min(6, dec + 2) : calc.kind === 'diff' || calc.kind === 'cum' ? dec : 2;
    order.forEach((i, j) => { body[i][width + k] = calcText(res[j], digits); });
  });
  return body;
}

function addCalc(view, calc) {
  view.csv.calcs.push({ ...calc, filter: '' });
  build(view);
}

/** 계산 열을 뺀다. k 가 없으면 모두 */
function dropCalc(view, k = null) {
  const st = /** @type {CsvState} */ (view.csv);
  st.calcs = k == null ? [] : st.calcs.filter((_, i) => i !== k);
  if (st.mem.sort?.col >= st.width) st.mem.sort = null;
  build(view);
}

/** 지금 보이는 표 (거른 행, 정렬 차례, 계산 열까지 — 그리는 행 수 한도와 상관없이) {title, headers, rows} */
export function shownTable(view, range = null) {
  const st = /** @type {CsvState} */ (view.csv);
  const { body, idx, cols, bodyLines } = st;
  const name = basename(view.dataset.codePath || '');
  const within = (i) => !range || (bodyLines[i][0] <= range[1] && bodyLines[i][1] >= range[0]);
  const titles = st.region?.titles ?? [];
  return {
    title: [name, st.baseLetter ? view.dataset.sheet : '', titles[0]].filter(Boolean).join(' · '), caption: titles.join(' '),
    headers: cols.map((c) => c.name), rows: idx.filter(within).map((i) => cols.map((_, c) => body[i][c] ?? '')),
  };
}

const chartShown = (view, only = null, range = null) => openChart(shownTable(view, range), { only });

async function copyShown(view) {
  const { headers, rows } = shownTable(view);
  const flat = (s) => String(s).replace(/[\t\r\n]+/g, ' ');
  const text = [headers, ...rows].map((r) => r.map(flat).join('\t')).join('\n');
  toast(await copyText(text) ? t('복사했습니다: {what}', { what: `${t('표')} ${t('{rows}행 {cols}열', { rows: rows.length, cols: headers.length })}` }) : t('복사하지 못했습니다'));
}

function sendShown(view) {
  const { title, headers, rows } = shownTable(view);
  if (rows.length > MAX_SEND) {
    toast(t('문서로 보내는 표는 {n}행까지입니다 — 거른 뒤 보내세요', { n: MAX_SEND }));
    return;
  }
  const cell = (s) => String(s).replace(/\|/g, '\\|').replace(/[\r\n]+/g, ' ').trim();
  const line = (r) => `| ${r.map(cell).join(' | ')} |`;
  const rule = `| ${view.csv.cols.map((c) => (c.numeric ? '---:' : '---')).join(' | ')} |`;
  const text = [line(headers), rule, ...rows.map(line)].join('\n');
  sendSnippets([snippetOf({ path: view.dataset.codePath, lines: [] }, null, { kind: 'table', name: t('표'), label: `${title} · ${t('{rows}행 {cols}열', { rows: rows.length, cols: headers.length })}`, text, plain: true })]);
}

/** 열 머리 우클릭의 메뉴 (docmenu.js) */
export function columnMenu(view, c) {
  const st = /** @type {CsvState} */ (view.csv);
  const col = st.cols[c];
  const series = col.numeric && c !== st.time?.col;
  const items = [];
  if (col.calc != null) items.push({ header: col.name }, { label: t('이 계산 열 빼기'), action: () => dropCalc(view, col.calc) });
  else if (series) {
    const add = (kind, n) => ({ label: calcLabel({ kind, n }), action: () => addCalc(view, { kind, col: c, n }) });
    items.push({ header: t("'{name}' 열로 계산", { name: col.name }) }, add('pop'));
    if (st.time) items.push(add('yoy'));
    items.push(add('diff'), add('cum'), ...(MA_SPANS[st.time?.freq] ?? [3, 5]).map((n) => add('ma', n)), add('index'));
  } else items.push({ header: col.name });
  items.push('-');
  if (series) items.push({ label: t('이 열을 차트로'), action: () => chartShown(view, col.name) });
  items.push({ label: t('차트로 보기'), tip: t('거른 행 그대로'), action: () => chartShown(view) });
  if (st.calcs.length && col.calc == null) items.push({ label: t('계산 열 모두 빼기'), action: () => dropCalc(view) });
  return items;
}

/** 하이라이트한 행을 차트로 (docmenu.js 의 선택 상자) */
export const chartRange = (view, range) => chartShown(view, null, range);

// ---- 요약 줄 (D86) -------------------------------------------------------------------------

/** 거른 행의 요약: 주기 · 기간 · 숫자 열 · 빈칸 */
function summaryText(st, idx, raw) {
  const { time, cols, width } = st;
  const parts = [];
  const list = time ? idx.map((i) => time.parsed[i]).filter(Boolean) : [];
  if (list.length) {
    const first = list.reduce((a, b) => (b.at < a.at ? b : a));
    const last = list.reduce((a, b) => (b.at > a.at ? b : a));
    const [from, to] = [periodText(first, time.freq), periodText(last, time.freq)];
    parts.push(frequencyName(time.freq), from === to ? from : `${from} ~ ${to}`);
  }
  const numeric = cols.slice(0, width).map((c, i) => (c.numeric && i !== time?.col ? i : -1)).filter((i) => i >= 0);
  if (numeric.length) parts.push(t('숫자 열 {n}', { n: numeric.length }));
  let blanks = 0;
  for (const i of idx) for (const c of numeric) if (isMissing(raw[i][c])) blanks += 1;
  if (blanks) parts.push(t('빈칸 {n}', { n: blanks.toLocaleString() }));
  return parts.join(' · ');
}

/** 표의 몸통·통계·개수만 다시 그린다 (거르기·정렬) */
function update(view) {
  const st = /** @type {CsvState} */ (view.csv);
  const { rows, lines, header, cols, mem, calcs, width } = st;
  const raw = header ? rows.slice(1) : rows;
  const bodyLines = header ? lines.slice(1) : lines;
  const tests = mem.filters.map((q) => (q ? matcherOf(q) : null));
  let idx = raw.map((_, i) => i).filter((i) => tests.every((test, c) => !test || test(raw[i][c])));
  const body = withCalcs(st, raw, idx);
  const calcTests = calcs.map((c) => (c.filter ? matcherOf(c.filter) : null));
  if (calcTests.some(Boolean)) idx = idx.filter((i) => calcTests.every((test, k) => !test || test(body[i][width + k])));
  if (mem.sort) {
    const { col, dir } = mem.sort;
    /** @type {(i: number) => any} */
    const key = cols[col].numeric ? (i) => numberOf(body[i][col]) : (i) => String(body[i][col] ?? '').trim();
    const blank = (v) => v == null || v === '';
    idx = [...idx].sort((a, b) => {
      const x = key(a);
      const y = key(b);
      if (blank(x) || blank(y)) return Number(blank(x)) - Number(blank(y));   // 빈칸은 늘 끝에
      const c = typeof x === 'number' ? x - y : x.localeCompare(y, undefined, { numeric: true });
      return dir * c;
    });
  }
  Object.assign(st, { body, idx, bodyLines });
  const shown = idx.slice(0, MAX_SHOW);
  const tbody = view.querySelector('.csv-table tbody.csv-rows');
  setHtml(tbody, [shown.map((i) => {
    const [a, b] = bodyLines[i];
    const cells = cols.map((col, c) => {
      const formula = c < width ? st.titleOf?.(a, c) : '';   // 엑셀의 수식 (D77) — 계산 열에는 없다
      const tip = formula ? html` title="${t('수식: {formula}', { formula })}"` : '';
      const cls = [col.numeric ? 'num' : '', col.calc != null ? 'csv-calc' : ''].filter(Boolean).join(' ');
      return html`<td${cls ? html` class="${cls}"` : ''}${tip}>${body[i][c] ?? ''}</td>`;
    });
    return html`<tr class="cv-line" data-line="${a}"${b > a ? html` data-end="${b}"` : ''}><td class="csv-rn">${a}</td>${cells}</tr>`;
  }), (idx.length > MAX_SHOW ? html`<tr class="csv-more"><td colspan="${cols.length + 1}">${t('처음 {n}행만 보입니다 — 거르면 좁힐 수 있습니다', { n: MAX_SHOW.toLocaleString() })}</td></tr>` : ''), (idx.length ? '' : html`<tr class="csv-more"><td colspan="${cols.length + 1}">${t('맞는 행이 없습니다')}</td></tr>`)]);
  const statRow = view.querySelector('.csv-stats');
  statRow.hidden = !st.stats;
  if (st.stats) {
    setHtml(statRow, [html`<th class="csv-rn">${t('통계')}</th>`, cols.map((col, c) => html`<td>${statsHtml(statsOf(idx.map((i) => body[i][c]), col.numeric), col.numeric)}</td>`)]);
  }
  const filtered = mem.filters.some(Boolean) || calcs.some((c) => c.filter);
  view.querySelector('.csv-count').textContent = filtered
    ? t('{total}행 중 {n}행', { total: body.length.toLocaleString(), n: idx.length.toLocaleString() })
    : t('{n}행', { n: body.length.toLocaleString() });
  view.querySelector('.csv-summary').textContent = summaryText(st, idx, raw);
  view.querySelector('.csv-blocked').hidden = !st.calcBlocked;
  view.querySelector('.csv-clear').hidden = !filtered;
  for (const th of view.querySelectorAll('.csv-head th[data-col]')) {
    const on = mem.sort?.col === +th.dataset.col;
    th.dataset.sort = on ? (mem.sort.dir > 0 ? 'asc' : 'desc') : '';
    th.setAttribute('aria-sort', on ? (mem.sort.dir > 0 ? 'ascending' : 'descending') : 'none');
  }
}

/** 머리·거르기 칸까지 새로 (처음, '첫 줄은 머리행'을 바꿀 때) */
function build(view) {
  const st = /** @type {CsvState} */ (view.csv);
  const { rows, mem } = st;
  const letter = st.letter || colName;
  st.header = mem.header ?? guessHeader(rows);
  const width = Math.max(0, ...rows.slice(0, 500).map((r) => r.length));
  const body = st.header ? rows.slice(1) : rows;
  const base = Array.from({ length: width }, (_, c) => {
    const vals = body.slice(0, 1000).map((r) => r[c]).filter((v) => !isMissing(v));
    const numeric = vals.length > 0 && vals.filter((v) => numberOf(v) != null).length / vals.length >= 0.7;
    return { name: st.header ? (rows[0][c] ?? '').trim() || letter(c) : letter(c), numeric, letter: st.letter && st.header ? letter(c) : '' };
  });
  st.calcs = st.calcs.filter((c) => c.col < width && base[c.col].numeric);   // 머리행을 바꾸면 열이 달라질 수 있다
  st.width = width;
  st.time = findTimeColumn(base.map((c) => c.name), body);
  if (st.time) base[st.time.col].numeric = false;   // 연도·날짜는 합계·평균을 낼 값이 아니다
  st.cols = [...base, ...st.calcs.map((calc, k) => ({ name: `${base[calc.col].name} ${calcLabel(calc)}`, numeric: true, letter: '', calc: k }))];
  if (mem.filters.length !== width) mem.filters = Array(width).fill('');
  if (mem.sort && mem.sort.col >= st.cols.length) mem.sort = null;
  const tip = t('글자를 포함하는 행 — !글자 는 빼기, =글자 는 같은 것. 숫자는 >100 · <=5 · 10..20');
  setHtml(view.querySelector('.csv-table thead'), html`<tr class="csv-head"><th class="csv-rn">#</th>${st.cols.map((col, c) => (
    html`<th data-col="${c}" class="${[col.numeric ? 'num' : '', col.calc != null ? 'csv-calc' : ''].filter(Boolean).join(' ')}" title="${col.calc != null ? t('계산 열 — 화면에만 있습니다. 파일에는 쓰지 않습니다') : t('누르면 정렬 ({kind}) — 우클릭은 계산·차트', { kind: col.numeric ? t('숫자 열') : t('글자 열') })}">${col.letter ? html`<small class="csv-letter">${col.letter}</small>` : ''}${col.name}${col.calc != null ? html`<button type="button" class="csv-calc-x" data-calc="${col.calc}" title="${t('이 계산 열 빼기')}" aria-label="${t('이 계산 열 빼기')}">×</button>` : ''}</th>`
  ))}</tr><tr class="csv-filter"><th class="csv-rn"></th>${st.cols.map((col, c) => (
    html`<th><input type="search" data-col="${c}" value="${(col.calc != null ? st.calcs[col.calc].filter : mem.filters[c]) || ''}" placeholder="${t('거르기')}" title="${tip}" spellcheck="false"></th>`
  ))}</tr>`);
  view.querySelector('.csv-headrow input').checked = st.header;
  update(view);
}

/**
 * 표를 그린다 (codeview.js 의 showCode 가 부른다 — view 의 머리줄 뒤에 붙인다). key: 탭 id + 경로 (거르기·정렬 기억)
 * {cols, rows, header} 를 돌려준다 (상태줄 글)
 */
export function renderCsv(view, path, text, key, keep = null, line = null) {
  const { rows, lines } = parseCsv(text, delimiterOf(text, path));
  return { ...renderRows(view, rows, lines, key, { keep, line }), delim: delimiterOf(text, path) };
}

/**
 * 행 배열을 표로 (엑셀 보기 — D77, csv 도 이것으로). rows: [[칸 글…]], lines: 행마다 [첫 줄, 끝 줄] (엑셀은 행 번호).
 * opts.letter: 열 차례 → 열 이름 (엑셀의 A·B…, 머리행이 있으면 그 앞에 작게), opts.titleOf: (행 번호, 열 차례) → 마우스를 올리면 보일 수식,
 * opts.note: 막대에 보일 알림 (앞부분만 보일 때), opts.keep: 앞 화면의 view.csv (같은 표면 계산 열을 잇는다). {rows, cols}
 */
export function renderRows(view, rows, lines, key, { letter = null, titleOf = null, note = '', keep = null, merges = [], line = null } = {}) {
  const st = {
    grid: { rows, lines, merges }, key, root: memoryOf(key), stats: S.config?.csv_stats !== false, header: false, cols: [], baseLetter: letter, baseTitle: titleOf, calcs: [],
  };
  view.csv = st;
  loadRegions(st);
  pickRegion(st, line);
  if (keep?.key === key && keep.pick === st.pick) st.calcs = keep.calcs;   // 자동 새로고침으로 다시 그려도 남고, 파일을 다시 열면 없다
  view.classList.add('csv-view');
  addHtml(view, 'beforeend', html`<div class="csv-regions" hidden></div><div class="csv-bar">
    <span class="csv-count"></span><span class="csv-summary"></span>${note ? html`<span class="csv-note">${note}</span>` : ''}
    <span class="csv-note csv-blocked" hidden>${t('같은 시점이 여러 행이라 계산하지 못했습니다 — 품목 등으로 먼저 거르세요')}</span>
    <button type="button" class="text-btn csv-chart">${t('차트로 보기')}</button>
    <button type="button" class="text-btn csv-stats-btn" aria-pressed="${view.csv.stats}">${t('통계')}</button>
    <label class="csv-headrow"><input type="checkbox"> ${t('첫 줄은 머리행')}</label>
    <button type="button" class="text-btn csv-clear" hidden>${t('거르기 지우기')}</button>
    <button type="button" class="text-btn csv-copy-shown" title="${t('거른 행과 계산 열까지 — 엑셀에 붙이면 칸이 나뉩니다')}">${t('보이는 표 복사')}</button>
    <button type="button" class="text-btn csv-send" title="${t('Markdown 표로 다른 문서에 넣습니다')}">${t('문서로 보내기…')}</button>
  </div><table class="csv-table"><thead></thead><tbody class="csv-stats-body"><tr class="csv-stats"></tr></tbody><tbody class="csv-rows"></tbody></table>`);
  drawRegions(view);
  build(view);
  const head = view.querySelector('.cv-head');
  view.style.setProperty('--csv-top', `${head?.offsetHeight || 0}px`);
  return { rows: st.rows.length - (st.header ? 1 : 0), cols: st.cols.length };
}

let timer = 0;

/** 거르기·정렬·통계·머리행 (codeview.js 의 initCodeView 가 #lec-panes 에 붙인다) */
export function initCsv(root) {
  root.addEventListener('input', (e) => {
    const input = e.target.closest('.csv-filter input[data-col]');
    const view = input?.closest('.csv-view');
    if (!view?.csv) return;
    const c = +input.dataset.col;
    const calc = view.csv.cols[c]?.calc;
    if (calc != null) view.csv.calcs[calc].filter = input.value;
    else view.csv.mem.filters[c] = input.value;
    clearTimeout(timer);
    timer = setTimeout(() => update(view), 120);
  });
  root.addEventListener('change', (e) => {
    const box = e.target.closest('.csv-headrow input');
    const view = box?.closest('.csv-view');
    if (!view?.csv) return;
    view.csv.mem.header = box.checked;
    view.csv.mem.filters = [];
    view.csv.mem.sort = null;
    build(view);
  });
  root.addEventListener('click', (e) => {
    const view = e.target.closest('.csv-view');
    if (!view?.csv) return;
    const th = e.target.closest('.csv-head th[data-col]');
    const x = e.target.closest('.csv-calc-x');
    const chip = e.target.closest('.csv-region');
    const step = e.target.closest('.csv-depth button');
    if (chip) selectRegion(view, chip.dataset.region === 'all' ? 'all' : +chip.dataset.region);
    else if (step) stepDepth(view, +step.dataset.depth);
    else if (x) dropCalc(view, +x.dataset.calc);
    else if (th) {
      const col = +th.dataset.col;
      const cur = view.csv.mem.sort;
      view.csv.mem.sort = cur?.col !== col ? { col, dir: 1 } : cur.dir > 0 ? { col, dir: -1 } : null;   // 오름 → 내림 → 원래 순서
      update(view);
    } else if (e.target.closest('.csv-stats-btn')) {
      view.csv.stats = !view.csv.stats;
      e.target.closest('.csv-stats-btn').setAttribute('aria-pressed', String(view.csv.stats));
      saveConfig({ csv_stats: view.csv.stats });
      update(view);
    } else if (e.target.closest('.csv-clear')) {
      view.csv.mem.filters = view.csv.mem.filters.map(() => '');
      for (const calc of view.csv.calcs) calc.filter = '';
      for (const input of view.querySelectorAll('.csv-filter input')) input.value = '';
      update(view);
    } else if (e.target.closest('.csv-chart')) chartShown(view);
    else if (e.target.closest('.csv-copy-shown')) copyShown(view);
    else if (e.target.closest('.csv-send')) sendShown(view);
  });
}
