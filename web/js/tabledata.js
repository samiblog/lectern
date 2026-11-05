// 표 읽기 (D86, DOM 없음): 표의 글을 시간·숫자·단위로 읽는다. 빠른 차트(quickchart.js)와 데이터 보기(csvview.js)가 함께 쓴다.
//
// - 시간: 2026 · 2026-03 · 2026.3 · 202603 · 2026-03-15 · 20260315 · 2026Q1 · 1Q26 · 2026년 1분기 · 2026년 3월 · Mar-26 · 2026H1 · 2026E 등.
//   주기는 표기로 알고, 날짜 표기는 간격으로 어림한다 (월말 날짜의 표는 월별).
// - 시간 열: 80%(맨 앞 열은 60%) 이상이 시점인 열. 숫자로도 읽히는 표기(2026, 202603)는 맨 앞 열이나 머리행에 날짜·연도 같은 말이 있고 차례대로일 때만 — 가격 열을 연도로 읽지 않게.
// - 숫자 열: 빈칸·-·n.a. 를 뺀 칸의 70% 이상이 숫자인 열 (doc.js 의 숫자 열과 같은 규칙). 그런 칸은 0 이 아니라 값이 없는 곳이다.
// - 단위: 머리행의 괄호 (없으면 캡션), 비율은 %·%p·bp·증가율·YoY 등, 배수는 x·배. 단위가 같은 계열이 한 축을 쓴다.

const NUM = /^[-+−]?(?:[$₩€¥£]\s?)?[-+−]?\d[\d,]*(?:\.\d+)?\s?(?:%p?|bp|원|달러|억|만|조|배|x|[kKmMbB])?$/;
const MISSING = /^(?:[-–—.…]+|n\.?\s?a\.?|n\/a|#n\/a|nan|null|없음|해당\s?없음)$/i;
const TIME_WORD = /날짜|일자|연도|년도|연월|년월|기간|시점|분기|월별|연별|date|year|month|quarter|period|time/i;
const RATE_WORD = /%|\bbp\b|증가율|증감률|변화율|등락률|성장률|상승률|하락률|전년비|전년\s?동기|전월\s?대비|전기\s?대비|전분기\s?대비|전년\s?대비|yoy|mom|qoq|y-?o-?y/i;
const RATE_CELL = /(?:%p?|bp)$/;
const TIMES_CELL = /(?:x|배)$/;
const TIMES_WORD = /[([]\s*(?:x|배)\s*[)\]]\s*$/i;
const UNIT = /[([]\s*([^()[\]]+?)\s*[)\]]\s*$/;
const CAPTION_UNIT = /(?:단위|units?)\s*[:：]\s*([^),]+)/i;
const MONTH_NAMES = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'];

/** 칸 값의 숫자 (숫자가 아니면 null) */
export function numberOf(cell) {
  const s = String(cell ?? '').trim();
  if (!s || !NUM.test(s)) return null;
  const n = Number(s.replace(/[−]/g, '-').replace(/[^\d.+-]/g, '').replace(/(?!^)[+-]/g, ''));
  return Number.isFinite(n) ? n : null;
}

/** 값이 없는 칸 (빈칸·-·n.a. 등) */
export function isMissing(cell) {
  const s = String(cell ?? '').trim();
  return !s || MISSING.test(s);
}

// ---- 시간 ---------------------------------------------------------------------------------

const yearOf = (s) => {
  const y = Number(s) + (s.length === 2 ? (Number(s) >= 70 ? 1900 : 2000) : 0);
  return y >= 1800 && y <= 2200 ? y : null;
};

function point(kind, y, m = 1, d = 1) {
  if (y == null || m < 1 || m > 12 || d < 1 || d > 31) return null;
  const at = Date.UTC(y, m - 1, d);
  return new Date(at).getUTCMonth() === m - 1 ? { kind, y, m, d, at } : null;   // 2월 30일 같은 것은 날짜가 아니다
}

const quarter = (y, q) => point('Q', yearOf(y), Number(q) * 3 - 2);
const half = (y, h) => point('H', yearOf(y), h === '2' || h === '하' ? 7 : 1);   // i18n-ok
const month = (y, m) => point('M', yearOf(y), Number(m));
const day = (y, m, d) => point('D', yearOf(y), Number(m), Number(d));
/** 달 이름의 번호 (없으면 0) — 세 글자 이상이 달 이름의 앞부분이어야 한다 (Sept 도) */
const named = (word) => {
  const w = word.toLowerCase().replace(/^sept$/, 'sep');
  return MONTH_NAMES.findIndex((name) => name === w || (w.length === 3 && name.startsWith(w))) + 1;
};

// [글, (묶음들) => 시점] — 위에서부터 처음 맞는 것
const FORMS = [
  [/^(\d{4})$/, (y) => point('Y', yearOf(y))],
  [/^(\d{4})[-./](\d{1,2})$/, month],
  [/^(\d{4})[-./](\d{1,2})[-./](\d{1,2})\.?$/, day],
  [/^(\d{4})(\d{2})$/, month],
  [/^(\d{4})(\d{2})(\d{2})$/, day],
  [/^(\d{4})[-./\s]?q([1-4])$/i, quarter],
  [/^(\d{2})q([1-4])$/i, quarter],
  [/^q([1-4])[-./\s']?(\d{4}|\d{2})$/i, (q, y) => quarter(y, q)],
  [/^([1-4])q[-./\s']?(\d{4}|\d{2})$/i, (q, y) => quarter(y, q)],
  [/^(\d{4}|\d{2})[-./\s]([1-4])q$/i, quarter],
  [/^(\d{4}|\d{2})년\s*([1-4])\s*분기$/, quarter],
  [/^(\d{4})[-./\s]?h([12])$/i, half],
  [/^([12])h[-./\s']?(\d{4}|\d{2})$/i, (h, y) => half(y, h)],
  [/^(\d{4}|\d{2})년\s*(상|하)반기$/, half],   // i18n-ok
  [/^(\d{4}|\d{2})년\s*(\d{1,2})월\s*(\d{1,2})일$/, day],
  [/^(\d{4}|\d{2})년\s*(\d{1,2})월$/, month],
  [/^(\d{4}|\d{2})년$/, (y) => point('Y', yearOf(y))],
  [/^([a-z]{3,9})\.?[-./\s']?(\d{4}|\d{2})$/i, (w, y) => month(y, named(w))],
  [/^(\d{4})[-./\s]([a-z]{3,9})$/i, (y, w) => month(y, named(w))],
  [/^(\d{1,2})[-./\s]([a-z]{3,9})[-./\s](\d{4}|\d{2})$/i, (d, w, y) => day(y, named(w), d)],
];

/** 칸의 글 → 시점 {kind: Y|H|Q|M|D, y, m, d, at(그 시작의 ms)}. 시점이 아니면 null. 전망·잠정 표시(2026E, 2026(F))는 뗀다 */
export function parseTime(cell) {
  const s = String(cell ?? '').trim().replace(/^['’‘]/, '').replace(/(\d|년|기|월)\s*\(?(?:[EFPefp]|전망|예상|추정|잠정)\)?$/, '$1');
  if (!s || s.length > 24) return null;
  for (const [re, make] of FORMS) {
    const m = re.exec(s);
    if (m) return make(...m.slice(1));
  }
  return null;
}

const GAPS = [[1.5, 'D'], [4.5, 'D'], [10, 'W'], [40, 'M'], [110, 'Q'], [220, 'H'], [400, 'Y']];

/** 시점들의 주기 Y|H|Q|M|W|D (없으면 null). 날짜 표기는 가운데 간격으로 어림한다 */
export function frequencyOf(parsed) {
  const list = parsed.filter(Boolean);
  if (!list.length) return null;
  const count = {};
  for (const p of list) count[p.kind] = (count[p.kind] || 0) + 1;
  const kind = Object.keys(count).reduce((a, b) => (count[b] > count[a] ? b : a));
  if (kind !== 'D' || list.length < 3) return kind;
  const days = [...new Set(list.map((p) => p.at / 864e5))].sort((a, b) => a - b);
  const gaps = days.slice(1).map((d, i) => d - days[i]).sort((a, b) => a - b);
  const gap = gaps[gaps.length >> 1];
  return GAPS.find(([limit]) => gap <= limit)?.[1] ?? 'D';
}

/** 시점의 차례 번호 (주기마다 1씩 — 날짜는 일수) */
function periodOf(p, freq) {
  switch (freq) {
    case 'Y': return p.y;
    case 'H': return p.y * 2 + (p.m > 6 ? 1 : 0);
    case 'Q': return p.y * 4 + Math.floor((p.m - 1) / 3);
    case 'M': return p.y * 12 + p.m - 1;
    default: return p.at / 864e5;
  }
}

const pad = (n) => String(n).padStart(2, '0');

/** 시점의 글 (요약 줄 — 주기에 맞춘 한 가지 표기) */
export function periodText(p, freq) {
  switch (freq) {
    case 'Y': return String(p.y);
    case 'H': return `${p.y}H${p.m > 6 ? 2 : 1}`;
    case 'Q': return `${p.y}Q${Math.floor((p.m - 1) / 3) + 1}`;
    case 'M': return `${p.y}-${pad(p.m)}`;
    default: return `${p.y}-${pad(p.m)}-${pad(p.d)}`;
  }
}

/** 같은 시점이 둘 이상인지 (품목별로 쌓은 표 등) */
export function hasSameTimes(parsed, freq) {
  const seen = new Set();
  for (const p of parsed) {
    const k = periodOf(p, freq);
    if (seen.has(k)) return true;
    seen.add(k);
  }
  return false;
}

const inOrder = (list) => {
  const at = list.map((p) => p.at);
  return at.every((v, i) => !i || v >= at[i - 1]) || at.every((v, i) => !i || v <= at[i - 1]);
};

/** 시간 열 {col, parsed(행마다 시점 또는 null), freq}. 없으면 null */
export function findTimeColumn(headers, rows) {
  const width = Math.min(Math.max(headers.length, ...rows.slice(0, 50).map((r) => r.length), 0), 6);
  for (let c = 0; c < width; c++) {
    const filled = rows.map((r) => r[c]).filter((v) => !isMissing(v));
    if (!filled.length) continue;
    const parsed = rows.map((r) => parseTime(r[c]));
    const hits = parsed.filter(Boolean);
    if (hits.length / filled.length < (c === 0 ? 0.6 : 0.8)) continue;   // 맨 앞 열에는 '평균'·'전망' 같은 행이 섞이곤 한다
    const plain = filled.filter((v) => parseTime(v) && numberOf(v) != null).length / filled.length >= 0.5;   // 2026·202603 처럼 숫자로도 읽히는 표기
    if (plain && !((c === 0 || TIME_WORD.test(headers[c] ?? '')) && inOrder(hits) && hits.length > 1)) continue;
    return { col: c, parsed, freq: frequencyOf(hits) };
  }
  return null;
}

// ---- 단위 ---------------------------------------------------------------------------------

/** 열의 단위 {group: level|rate|multiple, unit, key(같은 축을 쓰는 묶음)} */
export function unitInfo(header, cells, caption = '') {
  const filled = cells.map((v) => String(v ?? '').trim()).filter((v) => v && !isMissing(v));
  const mostly = (re) => filled.length > 0 && filled.filter((v) => re.test(v)).length / filled.length >= 0.7;
  const own = UNIT.exec(header ?? '')?.[1] ?? '';
  const noted = CAPTION_UNIT.exec(caption)?.[1]?.trim() || UNIT.exec(caption)?.[1] || '';
  const unit = own || noted;
  if (mostly(TIMES_CELL) || TIMES_WORD.test(header ?? '')) return { group: 'multiple', unit: unit || 'x', key: 'multiple' };
  if (mostly(RATE_CELL) || RATE_WORD.test(header ?? '') || /^(?:%p?|bp)$/i.test(unit)) {
    return { group: 'rate', unit: /%|bp/i.test(unit) ? unit : '%', key: 'rate' };
  }
  return { group: 'level', unit, key: `level:${unit}` };
}

// ---- 표 → 계열 ---------------------------------------------------------------------------

function isNumericColumn(rows, c) {
  const cells = rows.map((r) => r[c]).filter((v) => !isMissing(v));
  return cells.length > 0 && cells.filter((v) => numberOf(v) != null).length / cells.length >= 0.7;
}

const headerIsTime = (headers) => {
  const rest = headers.slice(1).filter((h) => String(h ?? '').trim());
  return rest.length >= 2 && rest.filter((h) => parseTime(h)).length / rest.length >= 0.7;
};

function transposed(headers, rows) {
  const width = Math.max(headers.length, ...rows.map((r) => r.length));
  const H = [headers[0] ?? '', ...rows.map((r) => r[0] ?? '')];
  const R = Array.from({ length: Math.max(0, width - 1) }, (_, i) => [headers[i + 1] ?? '', ...rows.map((r) => r[i + 1] ?? '')]);
  return [H, R];
}

/**
 * 표(머리행 headers, 행 rows — 글의 배열)를 차트의 계열로 읽는다. swap: 행과 열을 (자동으로 정한 것과) 바꾼다. caption: 머리행에 단위가 없을 때 볼 글.
 * 머리행이 시점이면 저절로 행과 열을 바꾼다. 시간 축이면 오래된 것부터 놓고, 시점이 아닌 행은 뺀다.
 * {labels, series: [{name, values(숫자 또는 null), group, unit, key}], freq, turned, skipped(뺀 행 수), same(같은 시점이 여럿), xName}
 */
export function readTable(headers, rows, { swap = false, caption = '' } = {}) {
  const turned = headerIsTime(headers) !== !!swap;
  const [H, R] = turned ? transposed(headers, rows) : [headers, rows];
  const time = findTimeColumn(H, R);
  const width = Math.max(H.length, ...R.map((r) => r.length), 0);
  const cols = Array.from({ length: width }, (_, c) => c);
  const x = time ? time.col : cols.find((c) => !isNumericColumn(R, c)) ?? -1;
  let order = R.map((_, i) => i);
  let skipped = 0;
  if (time) {
    order = order.filter((i) => time.parsed[i]);
    skipped = R.length - order.length;
    order.sort((a, b) => time.parsed[a].at - time.parsed[b].at);
  }
  const labels = order.map((i) => (x < 0 ? String(i + 1) : String(R[i][x] ?? '').trim()));
  const series = cols.filter((c) => c !== x && isNumericColumn(R, c)).map((c) => {
    const cells = order.map((i) => R[i][c]);
    return { name: String(H[c] ?? '').trim() || `${c + 1}`, values: cells.map((v) => (isMissing(v) ? null : numberOf(v))), ...unitInfo(H[c], cells, caption) };
  });
  return {
    labels, series, freq: time?.freq ?? null, turned, skipped, xName: x < 0 ? '' : String(H[x] ?? '').trim(),
    same: !!time && hasSameTimes(order.map((i) => time.parsed[i]), time.freq),
  };
}

// ---- 표 영역 ------------------------------------------------------------------------------
//
// 엑셀에서 온 표는 csv 처럼 깔끔하지 않다: 위에 제목·단위 줄, 여러 줄 머리행, 한 시트에 표 여럿, 아래에 자료·주 줄.
// 빈 행·빈 열로 시트를 덩어리로 나누고, 덩어리마다 제목·머리행·몸통·주를 가른다. 틀리면 화면의 버튼으로 바로잡는다.

const NOTE = /^\s*(?:자료|출처|주\s*[:：)\d]|source|note|[*※]|\(\d+\)|\d+\))/i;
const MAX_HEAD = 4;
const hasText = (v) => !!String(v ?? '').trim();
const inside = (row, c0, c1) => Array.from({ length: c1 - c0 + 1 }, (_, i) => row[c0 + i] ?? '');
const filledIn = (row, c0, c1) => inside(row, c0, c1).filter(hasText);

/** 몸통 행인지: 시점으로 시작하는 숫자 행이거나, 첫 칸 뒤의 칸 반 이상이 연도가 아닌 숫자 */
function isBody(row, c0, c1) {
  const rest = inside(row, c0 + 1, c1).filter((v) => !isMissing(v));
  if (!rest.length) return false;
  const nums = rest.filter((v) => numberOf(v) != null);
  if (nums.length && parseTime(row[c0])) return true;
  return nums.filter((v) => !parseTime(v)).length >= Math.max(1, rest.length / 2);
}

/** 덩어리를 빈 열로 나눈다. 뒤 조각에 이름표 열이 없으면(둘째 열부터 숫자뿐) 표 안의 간격이다 — 앞 조각에 붙인다 */
function splitColumns(rows, a, b) {
  const width = Math.max(...rows.slice(a, b + 1).map((r) => r.length));
  const used = Array.from({ length: width }, (_, c) => rows.slice(a, b + 1).some((r) => hasText(r[c])));
  const runs = [];
  used.forEach((on, c) => {
    if (!on) return;
    if (runs.length && runs.at(-1).c1 === c - 1) runs.at(-1).c1 = c;
    else runs.push({ c0: c, c1: c });
  });
  const labelled = ({ c0, c1 }) => {
    if (c1 === c0) return false;
    const cells = rows.slice(a, b + 1).map((r) => r[c0]).filter((v) => !isMissing(v));
    return cells.filter((v) => numberOf(v) == null || parseTime(v)).length / Math.max(1, cells.length) >= 0.5;
  };
  const out = [];
  for (const run of runs) {
    if (out.length && !labelled(run)) out.at(-1).c1 = run.c1;
    else out.push({ ...run });
  }
  return out;
}

/** 빈 행으로 나눈 덩어리들 [{a, b}] (행 차례) — 엑셀은 값이 없는 행이 빠져 있으므로 줄 번호가 뛰어도 나눈다 */
function bandsOf(rows, lines) {
  const bands = [];
  let cur = null;
  rows.forEach((r, i) => {
    if (!r.some(hasText)) {
      cur = null;
      return;
    }
    if (!cur || (lines && lines[i][0] - lines[i - 1][1] > 1)) {
      cur = { a: i, b: i };
      bands.push(cur);
    } else cur.b = i;
  });
  return bands;
}

/** 머리행들의 칸을 합친 열 이름 — 병합 칸과 윗줄의 빈칸은 왼쪽 값으로 채운다 ('수입 · 구리') */
function headerNames(rows, lines, merges, list, c0, c1) {
  const grid = list.map((i, k) => {
    const row = inside(rows[i], c0, c1).map((v) => String(v ?? '').trim());
    const line = lines ? lines[i][0] : i + 1;
    for (const [r1, m0, r2, m1] of merges) {
      if (line < r1 || line > r2) continue;
      const top = lines ? rows[lines.findIndex((x) => x[0] === r1)] : rows[r1 - 1];
      const value = String(top?.[m0] ?? '').trim();
      for (let c = Math.max(m0, c0); c <= Math.min(m1, c1); c++) row[c - c0] = value;
    }
    if (k < list.length - 1) {   // 맨 아래 줄이 아니면 병합을 잃은 표(csv)처럼 비어 있어도 왼쪽 값이 이어진다
      for (let c = 1; c < row.length; c++) if (!row[c] && row[c - 1] && inside(rows[list[k + 1]], c0, c1)[c]) row[c] = row[c - 1];
    }
    return row;
  });
  return Array.from({ length: c1 - c0 + 1 }, (_, c) => grid.map((row) => row[c]).filter((v, i, all) => v && v !== all[i - 1]).join(' · '));
}

/** 덩어리 하나의 제목·머리행·몸통·주. depth: 머리행 줄 수 (없으면 어림) */
function shapeRegion(rows, lines, merges, piece, depth = null) {
  const { c0, c1 } = piece;
  const titles = [...piece.titles];
  const notes = [...piece.notes];
  let list = [];
  for (let i = piece.a; i <= piece.b; i++) if (filledIn(rows[i], c0, c1).length) list.push(i);
  const lone = (i) => {
    const cells = filledIn(rows[i], c0, c1);
    return cells.length === 1 ? String(cells[0]).trim() : '';
  };
  while (list.length > 1 && lone(list[0]) && numberOf(lone(list[0])) == null) {
    titles.push(lone(list[0]));
    list = list.slice(1);
  }
  while (list.length > 1 && NOTE.test(lone(list.at(-1)))) {
    notes.unshift(lone(list.at(-1)));
    list = list.slice(0, -1);
  }
  const auto = list.findIndex((i) => isBody(rows[i], c0, c1));
  const head = depth ?? (auto < 0 || auto > MAX_HEAD ? Math.min(1, list.length) : auto);
  const body = list.slice(head);
  const down = merges.filter(([r1, , r2]) => r2 > r1);   // 몸통의 세로 병합 (품목 이름 등)
  const lineOf = (i) => (lines ? lines[i][0] : i + 1);
  const cellsOf = (i) => {
    const row = inside(rows[i], c0, c1);
    for (const [r1, m0, r2] of down) {
      if (lineOf(i) <= r1 || lineOf(i) > r2 || m0 < c0 || m0 > c1) continue;
      const top = list.find((x) => lineOf(x) === r1);
      if (top != null) row[m0 - c0] = rows[top][m0] ?? '';
    }
    return row;
  };
  return {
    piece, c0, c1, titles, notes, depth: head, auto: auto < 0 ? 1 : auto, top: list[0], bottom: list.at(-1),
    headers: headerNames(rows, lines, merges, list.slice(0, head), c0, c1),
    rows: body.map(cellsOf), lines: body.map((i) => (lines ? lines[i] : [i + 1, i + 1])),
    size: body.length * (c1 - c0 + 1),
  };
}

/**
 * 시트(rows, lines — 행마다 [첫 줄, 끝 줄], merges — [[첫 행, 첫 열, 끝 행, 끝 열]])의 표들.
 * {regions: [{c0, c1, titles, notes, depth, headers, rows, lines, size}], best(가장 큰 표), plain(표 하나뿐이고 머리행 한 줄인 깔끔한 시트)}
 */
export function findRegions(rows, lines = null, merges = []) {
  const items = [];   // 차례대로: {text: [글], a} 또는 조각 {a, b, c0, c1, titles, notes}
  for (const { a, b } of bandsOf(rows, lines)) {
    const text = rows.slice(a, b + 1).every((r) => r.filter(hasText).length <= 1);
    if (text) items.push({ text: rows.slice(a, b + 1).map((r) => String(r.find(hasText)).trim()) });
    else for (const run of splitColumns(rows, a, b)) items.push({ a, b, ...run, titles: [], notes: [] });
  }
  const pieces = [];
  let pending = [];
  for (const it of items) {
    if (it.text) {
      const last = pieces.at(-1);
      if (last && NOTE.test(it.text[0])) last.notes.push(...it.text);
      else pending.push(...it.text);
      continue;
    }
    const last = pieces.at(-1);
    if (last && !pending.length && it.c0 >= last.c0 && it.c1 <= last.c1 && isBody(rows[it.a], it.c0, it.c1)) {
      last.b = it.b;   // 몸통 사이의 빈 줄, 표 아래 한 칸 띄운 합계 행 — 같은 표
      continue;
    }
    pieces.push({ ...it, titles: pending });
    if (!last || last.a !== it.a) pending = [];
  }
  const regions = pieces.map((p) => shapeRegion(rows, lines, merges, p)).filter((r) => r.rows.length);
  const best = regions.reduce((k, r, i) => (r.size > regions[k].size ? i : k), 0);
  const width = Math.max(0, ...rows.map((r) => r.length));
  const only = regions.length === 1 ? regions[0] : null;
  const plain = !regions.length || (!!only && !only.titles.length && !only.notes.length && only.depth <= 1 && only.c0 === 0 && only.c1 >= width - 1
    && only.top === rows.findIndex((r) => r.some(hasText)));
  return { regions, best, plain };
}

/** 머리행 줄 수를 바꾼 표 */
export const reshapeRegion = (rows, lines, merges, region, depth) => shapeRegion(rows, lines, merges, region.piece, depth);

/** 원문 줄 a~b 를 표로 (사용자가 하이라이트한 범위). 값이 있는 행이 없으면 null */
export function regionOfLines(rows, lines, merges, a, b) {
  const hit = rows.map((_, i) => i).filter((i) => (lines ? lines[i][0] <= b && lines[i][1] >= a : i + 1 >= a && i + 1 <= b) && rows[i].some(hasText));
  if (!hit.length) return null;
  const cols = hit.flatMap((i) => rows[i].map((v, c) => (hasText(v) ? c : -1))).filter((c) => c >= 0);
  const region = shapeRegion(rows, lines, merges, { a: hit[0], b: hit.at(-1), c0: Math.min(...cols), c1: Math.max(...cols), titles: [], notes: [] });
  return region.rows.length ? region : null;
}

// ---- 계산 열 ------------------------------------------------------------------------------

const LAG = { Y: 1, H: 2, Q: 4, M: 12 };
const NEAR = [0, -1, 1, -2, 2, -3, 3];
const change = (now, before) => (now == null || before == null || !before ? null : ((now - before) / Math.abs(before)) * 100);

/** 앞 시점의 차례: 월·분기처럼 번호가 있으면 바로 앞 번호의 행 (빠진 달이면 없다), 그 밖은 앞 행 */
function previousOf(parsed, freq) {
  if (!parsed || !LAG[freq]) return (i) => (i > 0 ? i - 1 : -1);
  const at = new Map(parsed.map((p, i) => [periodOf(p, freq), i]));
  return (i) => at.get(periodOf(parsed[i], freq) - 1) ?? -1;
}

/** 1년 전 시점의 차례 — 월은 12, 분기는 4 뺀 번호, 날짜는 같은 날에서 앞뒤 3일 안 */
function lastYearOf(parsed, freq) {
  if (LAG[freq]) {
    const at = new Map(parsed.map((p, i) => [periodOf(p, freq), i]));
    return (i) => at.get(periodOf(parsed[i], freq) - LAG[freq]) ?? -1;
  }
  const at = new Map(parsed.map((p, i) => [p.at / 864e5, i]));
  return (i) => {
    const p = parsed[i];
    const target = Date.UTC(p.y - 1, p.m - 1, p.d) / 864e5;
    for (const d of NEAR) if (at.has(target + d)) return at.get(target + d);
    return -1;
  };
}

/**
 * 계산 열의 값. values: 시간 차례(시간 열이 없으면 표의 차례)의 숫자 또는 null. parsed·freq: 같은 차례의 시점과 주기 (없으면 null). n: 이동평균의 칸 수.
 * kind: pop(전기 대비 %) · yoy(전년 동기 대비 %) · diff(차분) · cum(누적) · ma(이동평균) · index(첫 값=100)
 */
export function calcValues(kind, values, { n = 3, parsed = null, freq = null } = {}) {
  if (kind === 'cum') {
    let sum = 0;
    return values.map((v) => {
      if (v == null) return null;
      sum += v;
      return sum;
    });
  }
  if (kind === 'ma') {
    return values.map((_, i) => {
      if (i + 1 < n) return null;
      const part = values.slice(i + 1 - n, i + 1);
      return part.some((v) => v == null) ? null : part.reduce((a, b) => a + b, 0) / n;
    });
  }
  if (kind === 'index') {
    const base = values.find((v) => v != null && v !== 0);
    return values.map((v) => (v == null || base == null ? null : (v / base) * 100));
  }
  if (kind === 'yoy' && !parsed) return values.map(() => null);
  const from = kind === 'yoy' ? lastYearOf(parsed, freq) : previousOf(parsed, freq);
  return values.map((v, i) => {
    const before = values[from(i)] ?? null;
    if (kind === 'diff') return v == null || before == null ? null : v - before;
    return change(v, before);
  });
}

/** 칸 글의 소수 자릿수 */
export const decimalsOf = (cell) => /\.(\d+)/.exec(String(cell))?.[1].length ?? 0;

/** 계산 값의 글. digits: 소수 자릿수 */
export function calcText(value, digits) {
  if (value == null || !Number.isFinite(value)) return '';
  const n = Number(value.toFixed(digits));
  return String(n === 0 ? 0 : n);
}
