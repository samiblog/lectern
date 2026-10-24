// CSV 보기 (D60): 코드 화면(codeview.js)이 csv·tsv 파일을 표로 그린다 — 머리행 아래 열마다 거르기 칸, 머리행을 누르면 정렬,
// 표 위의 통계 줄(숫자 열: 개수·합계·평균·최소·최대·중앙값, 글자 열: 개수·고유값·가장 많은 값 — 거르면 남은 행으로).
//
// - 행은 tr.cv-line[data-line] (원문의 첫 줄, 따옴표 안 줄바꿈으로 여러 줄이면 data-end) — 코드 화면처럼 우클릭 메뉴의
//   '이 줄 복사'·'Claude용 위치 복사', 편집 모드의 위치 잇기, 찾기가 그대로 된다.
// - 머리행은 어림한다 (첫 줄에 숫자가 없고, 아래에 숫자가 많은 열이 있거나 첫 줄 값이 모두 다르면). 막대의 '첫 줄은 머리행'으로 바꾼다.
// - 숫자: 1,234 / -3.5% / $105 / 12억 같은 표기도 숫자로 (doc.js 의 숫자 열과 같은 규칙). 70% 이상이 숫자면 숫자 열.
// - 그리는 행은 MAX_SHOW 까지 (통계·개수는 거른 행 전부로). 거르기·정렬·머리행은 파일마다 이번 실행 동안 기억한다.

import { S } from './store.js';
import { saveConfig } from './api.js';
import { esc } from './util.js';
import { t } from './i18n.js';

export const TABLE_EXT = new Set(['csv', 'tsv']);
const MAX_SHOW = 2000;
const NUM = /^[-+−]?(?:[$₩€¥£]\s?)?[-+−]?\d[\d,]*(?:\.\d+)?\s?(?:%p?|bp|원|달러|억|만|조|배|x|[kKmMbB])?$/;
const memory = new Map();   // 탭 id + 경로 → {filters, sort, header} (다시 그려도 그대로)

export const isTableFile = (path) => TABLE_EXT.has(path.split('.').pop().toLowerCase());

/** 칸 값의 숫자 (숫자가 아니면 null) */
export function numberOf(cell) {
  const s = String(cell ?? '').trim();
  if (!s || !NUM.test(s)) return null;
  const n = Number(s.replace(/[−]/g, '-').replace(/[^\d.+-]/g, '').replace(/(?!^)[+-]/g, ''));
  return Number.isFinite(n) ? n : null;
}

/** 구분자: tsv 는 탭, 아니면 앞 20줄에서 쉼표·세미콜론·탭 가운데 줄마다 개수가 가장 고르게 많은 것 */
function delimiterOf(text, path) {
  if (path.toLowerCase().endsWith('.tsv')) return '\t';
  const sample = text.split('\n', 20).filter((l) => l.trim());
  let best = ',';
  let score = -1;
  for (const d of [',', ';', '\t']) {
    const counts = sample.map((l) => l.split(d).length - 1);
    const min = Math.min(...counts);
    if (min > 0 && min > score) {
      best = d;
      score = min;
    }
  }
  return best;
}

/** RFC 4180 — 따옴표 안의 구분자·줄바꿈·"" 를 다룬다. {rows: [[칸]], lines: [[첫 줄, 끝 줄]] (1부터)} */
export function parseCsv(text, delim) {
  const rows = [];
  const lines = [];
  let row = [];
  let cell = '';
  let quoted = false;
  let line = 1;
  let start = 1;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          cell += '"';
          i += 1;
        } else quoted = false;
      } else {
        if (ch === '\n') line += 1;
        cell += ch;
      }
    } else if (ch === '"' && !cell) {
      quoted = true;
    } else if (ch === delim) {
      row.push(cell);
      cell = '';
    } else if (ch === '\n') {
      row.push(cell);
      if (row.length > 1 || row[0] !== '') {
        rows.push(row);
        lines.push([start, line]);
      }
      row = [];
      cell = '';
      line += 1;
      start = line;
    } else {
      cell += ch;
    }
  }
  if (cell || row.length) {
    row.push(cell);
    rows.push(row);
    lines.push([start, line]);
  }
  return { rows, lines };
}

/** 첫 줄이 머리행인지 어림한다 */
function guessHeader(rows) {
  if (rows.length < 2) return false;
  const first = rows[0];
  if (first.some((c) => numberOf(c) != null) || first.some((c) => !c.trim())) return false;
  const body = rows.slice(1, 200);
  const numericBelow = first.some((_, c) => {
    const vals = body.map((r) => r[c]).filter((v) => v != null && String(v).trim());
    return vals.length && vals.filter((v) => numberOf(v) != null).length / vals.length >= 0.7;
  });
  return numericBelow || new Set(first).size === first.length;
}

const colName = (i) => {   // A, B, …, Z, AA, … (머리행이 없을 때)
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

const decimalsOf = (cell) => {
  const m = /\.(\d+)/.exec(String(cell));
  return m ? m[1].length : 0;
};

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
  const row = (label, value) => `<div><span>${esc(label)}</span><b>${esc(value)}</b></div>`;
  let html = row(t('개수'), format(s.count, 0)) + (s.empty ? row(t('빈칸'), format(s.empty, 0)) : '');
  if (numeric && s.numbers) {
    html += row(t('합계'), format(s.sum, s.dec)) + row(t('평균'), format(s.mean, s.dec + 2)) + row(t('최소'), format(s.min, s.dec))
      + row(t('최대'), format(s.max, s.dec)) + row(t('중앙값'), format(s.median, s.dec + 1));
  } else if (!numeric && s.top) {
    html += row(t('고유값'), format(s.unique, 0));
    if (s.top[1] > 1) html += row(t('최빈'), `${s.top[0].length > 18 ? `${s.top[0].slice(0, 17)}…` : s.top[0]} (${format(s.top[1], 0)})`);   // 모두 다르면 뜻이 없다
  }
  return html;
}

// ---- 그리기 ---------------------------------------------------------------------------------

/** 표의 몸통·통계·개수만 다시 그린다 (거르기·정렬) */
function update(view) {
  const st = view.csv;
  const { rows, lines, header, cols, mem } = st;
  const body = header ? rows.slice(1) : rows;
  const bodyLines = header ? lines.slice(1) : lines;
  const tests = mem.filters.map((q) => (q ? matcherOf(q) : null));
  let idx = body.map((_, i) => i).filter((i) => tests.every((test, c) => !test || test(body[i][c])));
  if (mem.sort) {
    const { col, dir } = mem.sort;
    const key = cols[col].numeric ? (i) => numberOf(body[i][col]) : (i) => String(body[i][col] ?? '').trim();
    const blank = (v) => v == null || v === '';
    idx = [...idx].sort((a, b) => {
      const x = key(a);
      const y = key(b);
      if (blank(x) || blank(y)) return blank(x) - blank(y);   // 빈칸은 늘 끝에
      const c = typeof x === 'number' ? x - y : x.localeCompare(y, undefined, { numeric: true });
      return dir * c;
    });
  }
  const shown = idx.slice(0, MAX_SHOW);
  const tbody = view.querySelector('.csv-table tbody.csv-rows');
  tbody.innerHTML = shown.map((i) => {
    const [a, b] = bodyLines[i];
    const cells = cols.map((col, c) => `<td${col.numeric ? ' class="num"' : ''}>${esc(body[i][c] ?? '')}</td>`).join('');
    return `<tr class="cv-line" data-line="${a}"${b > a ? ` data-end="${b}"` : ''}><td class="csv-rn">${a}</td>${cells}</tr>`;
  }).join('')
    + (idx.length > MAX_SHOW ? `<tr class="csv-more"><td colspan="${cols.length + 1}">${esc(t('처음 {n}행만 보입니다 — 거르면 좁힐 수 있습니다', { n: MAX_SHOW.toLocaleString() }))}</td></tr>` : '')
    + (idx.length ? '' : `<tr class="csv-more"><td colspan="${cols.length + 1}">${esc(t('맞는 행이 없습니다'))}</td></tr>`);
  const statRow = view.querySelector('.csv-stats');
  statRow.hidden = !st.stats;
  if (st.stats) {
    statRow.innerHTML = `<th class="csv-rn">${esc(t('통계'))}</th>`
      + cols.map((col, c) => `<td>${statsHtml(statsOf(idx.map((i) => body[i][c]), col.numeric), col.numeric)}</td>`).join('');
  }
  const filtered = mem.filters.some(Boolean);
  view.querySelector('.csv-count').textContent = filtered
    ? t('{total}행 중 {n}행', { total: body.length.toLocaleString(), n: idx.length.toLocaleString() })
    : t('{n}행', { n: body.length.toLocaleString() });
  view.querySelector('.csv-clear').hidden = !filtered;
  for (const th of view.querySelectorAll('.csv-head th[data-col]')) {
    const on = mem.sort?.col === +th.dataset.col;
    th.dataset.sort = on ? (mem.sort.dir > 0 ? 'asc' : 'desc') : '';
    th.setAttribute('aria-sort', on ? (mem.sort.dir > 0 ? 'ascending' : 'descending') : 'none');
  }
}

/** 머리·거르기 칸까지 새로 (처음, '첫 줄은 머리행'을 바꿀 때) */
function build(view) {
  const st = view.csv;
  const { rows, mem } = st;
  st.header = mem.header ?? guessHeader(rows);
  const width = Math.max(0, ...rows.slice(0, 500).map((r) => r.length));
  const body = st.header ? rows.slice(1) : rows;
  st.cols = Array.from({ length: width }, (_, c) => {
    const vals = body.slice(0, 1000).map((r) => r[c]).filter((v) => v != null && String(v).trim());
    const numeric = vals.length > 0 && vals.filter((v) => numberOf(v) != null).length / vals.length >= 0.7;
    return { name: st.header ? (rows[0][c] ?? '').trim() || colName(c) : colName(c), numeric };
  });
  if (mem.filters.length !== width) mem.filters = Array(width).fill('');
  if (mem.sort && mem.sort.col >= width) mem.sort = null;
  const tip = t('글자를 포함하는 행 — !글자 는 빼기, =글자 는 같은 것. 숫자는 >100 · <=5 · 10..20');
  view.querySelector('.csv-table thead').innerHTML = `<tr class="csv-head"><th class="csv-rn">#</th>${st.cols.map((col, c) => (
    `<th data-col="${c}"${col.numeric ? ' class="num"' : ''} title="${esc(t('누르면 정렬 ({kind})', { kind: col.numeric ? t('숫자 열') : t('글자 열') }))}">${esc(col.name)}</th>`
  )).join('')}</tr><tr class="csv-filter"><th class="csv-rn"></th>${st.cols.map((col, c) => (
    `<th><input type="search" data-col="${c}" value="${esc(mem.filters[c] || '')}" placeholder="${esc(t('거르기'))}" title="${esc(tip)}" spellcheck="false"></th>`
  )).join('')}</tr>`;
  view.querySelector('.csv-headrow input').checked = st.header;
  update(view);
}

/**
 * 표를 그린다 (codeview.js 의 showCode 가 부른다 — view 의 머리줄 뒤에 붙인다). key: 탭 id + 경로 (거르기·정렬 기억)
 * {cols, rows, header} 를 돌려준다 (상태줄 글)
 */
export function renderCsv(view, path, text, key) {
  const { rows, lines } = parseCsv(text, delimiterOf(text, path));
  if (!memory.has(key)) memory.set(key, { filters: [], sort: null, header: null });
  view.csv = { rows, lines, mem: memory.get(key), stats: S.config?.csv_stats !== false, header: false, cols: [] };
  view.classList.add('csv-view');
  view.insertAdjacentHTML('beforeend', `<div class="csv-bar">
    <span class="csv-count"></span>
    <button type="button" class="text-btn csv-stats-btn" aria-pressed="${view.csv.stats}">${esc(t('통계'))}</button>
    <label class="csv-headrow"><input type="checkbox"> ${esc(t('첫 줄은 머리행'))}</label>
    <button type="button" class="text-btn csv-clear" hidden>${esc(t('거르기 지우기'))}</button>
  </div><table class="csv-table"><thead></thead><tbody class="csv-stats-body"><tr class="csv-stats"></tr></tbody><tbody class="csv-rows"></tbody></table>`);
  build(view);
  const head = view.querySelector('.cv-head');
  view.style.setProperty('--csv-top', `${head?.offsetHeight || 0}px`);
  return { rows: rows.length - (view.csv.header ? 1 : 0), cols: view.csv.cols.length, delim: delimiterOf(text, path) };
}

let timer = 0;

/** 거르기·정렬·통계·머리행 (codeview.js 의 initCodeView 가 #lec-panes 에 붙인다) */
export function initCsv(root) {
  root.addEventListener('input', (e) => {
    const input = e.target.closest('.csv-filter input[data-col]');
    const view = input?.closest('.csv-view');
    if (!view?.csv) return;
    view.csv.mem.filters[+input.dataset.col] = input.value;
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
    if (th) {
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
      for (const input of view.querySelectorAll('.csv-filter input')) input.value = '';
      update(view);
    }
  });
}
