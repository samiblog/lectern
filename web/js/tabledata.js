// 표 읽기 (D86, DOM 없음): 표의 글을 시간·숫자·단위로 읽는다. 빠른 차트(quickchart.js)와 데이터 보기(csvview.js)가 함께 쓴다.
//
// - 시간: 2026 · 2026-03 · 2026.3 · 202603 · 2026M03 · 2026-03-15 · 2026. 3. 15. · 20260315 · 2026Q1 · 1Q26 · 2026년 1분기 · 2026년 1/4분기 · 2026년 3월 · Mar-26 ·
//   3/31/2026 · 2026H1 · FY2026 · 2026E 등 (ECOS·KOSIS·World Bank·FRED·EViews·엑셀·pandas 의 표기). 날짜의 시각은 뗀다. 3/4/2026 은 열에 13 이 넘는 앞자리가 있으면 일/월로 읽는다.
//   주기는 표기로 알고, 날짜 표기는 간격으로 어림한다 (월말 날짜의 표는 월별).
// - 시간 열: 80%(맨 앞 열은 60%) 이상이 시점인 열. 숫자로도 읽히는 표기(2026, 202603)는 머리행에 날짜·연도 같은 말이 있거나 맨 앞 열이 차례대로일 때만 — 가격 열을 연도로 읽지 않게.
// - 숫자 열: 빈칸·-·n.a. 를 뺀 칸의 70% 이상이 숫자인 열 (doc.js 의 숫자 열과 같은 규칙). 그런 칸은 0 이 아니라 값이 없는 곳이다.
// - 단위: 머리행의 괄호 (없으면 캡션), 비율은 %·%p·bp·증가율·YoY 등, 배수는 x·배. 단위가 같은 계열이 한 축을 쓴다.

// 숫자: 천 단위 쉼표는 세 자리씩 (1,2 는 숫자가 아니다), 끝의 p·r·* 는 잠정·수정 표시, 괄호·△ 는 음수 (엑셀의 음수 표시와 한국 통계의 관행 — ▲ 는 뜻이 갈려 읽지 않는다)
const NUM = /^([-+−]?)(?:[$₩€¥£]\s?)?([-+−]?)((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d*)?|\.\d+)((?:[eE][-+]?\d+)?)\s?(?:%p?|bp|원|달러|억|만|조|배|x|[kKmMbB])?\s?(?:\*+|\(?[pPrR]\)?)?$/;
const NEGATIVE = /^(?:\((.+)\)|[△▼]\s?(.+))$/;
const MISSING = /^(?:[-–—.…]+|[x*]+|n\.?\s?a\.?|n\/a|nan|null|#(?:n\/a|div\/0!|ref!|value!|num!|name\?|null!)|없음|해당\s?없음|미공표|비공개|자료\s?없음)$/i;
const TIME_WORD = /날짜|일자|연도|년도|연월|년월|기간|시점|분기|월별|연별|date|year|month|quarter|period|time/i;
const RATE_WORD = /%|\bbp\b|증가율|증감률|변화율|등락률|성장률|상승률|하락률|전년비|전년\s?동기|전월\s?대비|전기\s?대비|전분기\s?대비|전년\s?대비|yoy|mom|qoq|y-?o-?y/i;
const RATE_CELL = /(?:%p?|bp)\)?$/;
const TIMES_CELL = /(?:x|배)\)?$/;
const TIMES_WORD = /[([]\s*(?:x|배)\s*[)\]]\s*$/i;
const UNIT = /[([]\s*([^()[\]]+?)\s*[)\]]\s*(?=·|$)/g;   // 머리행 끝의 괄호 (여러 줄을 합친 이름이면 줄의 끝도)
const TOTAL = /^(?:합계|총계|소계|계|total|subtotal|sum|평균|average|mean)$/i;
const MAX_SERIES = 500;
const MAX_REGIONS = 40;   // 이보다 많이 쪼개지면 표가 아니라 빈 줄로 띄운 글이다
const NOT_UNIT = /\d|기준|잠정|전망|예상|대비|현재|말$/;   // 캡션 끝의 괄호가 단위가 아닌 것 (2024년 기준, 잠정)
const CAPTION_UNIT = /(?:단위|units?)\s*[:：]\s*([^),]+)/i;
const MONTH_NAMES = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'];

/** 칸 값의 숫자 (숫자가 아니면 null) */
export function numberOf(cell) {
  const s = String(cell ?? '').trim();
  if (!s) return null;
  const neg = NEGATIVE.exec(s);
  const m = NUM.exec(neg ? neg[1] ?? neg[2] : s);
  if (!m) return null;
  const n = Number(m[3].replace(/,/g, '') + m[4]);
  if (!Number.isFinite(n)) return null;
  const minus = [m[1], m[2]].filter((c) => c === '-' || c === '−').length % 2 === 1;
  return (minus !== !!neg ? -n : n) + 0;
}

/** 값이 없는 칸 (빈칸·-·n.a. 등) */
export function isMissing(cell) {
  const s = String(cell ?? '').trim();
  return !s || MISSING.test(s);
}

// ---- csv ----------------------------------------------------------------------------------

/** 구분자: tsv 는 탭, 아니면 앞 20줄에서 쉼표·세미콜론·탭 가운데 줄마다 개수가 가장 고르게 많은 것 */
export function delimiterOf(text, path) {
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
/** @type {[RegExp, Function][]} */
const FORMS = [
  [/^(\d{4})(?:\.0+)?$/, (y) => point('Y', yearOf(y))],
  [/^(\d{4}|\d{2})(?:년\s*|[-.\s])\s*([1-4])\/4(?:\s*분기)?$/, quarter],   // 2026년 1/4분기, 2026.1/4
  [/^(\d{4}|\d{2})\/([1-4])\/4\s*분기$/, quarter],
  [/^(\d{4})[-./:](\d{1,2})\.?$/, month],
  [/^(\d{4})[-./](\d{1,2})[-./](\d{1,2})\.?$/, day],
  [/^(\d{2})\.(\d{1,2})\.(\d{1,2})\.?$/, day],   // 26.3.15
  [/^(\d{4})(\d{2})$/, month],
  [/^(\d{4})(\d{2})(\d{2})$/, day],
  [/^(\d{4})-?m(\d{1,2})$/i, month],   // World Bank·IMF·EViews
  [/^(\d{4}|\d{2})(?:년\s*|[-./:\s])?q([1-4])$/i, quarter],
  [/^q([1-4])[-./\s']?(\d{4}|\d{2})$/i, (q, y) => quarter(y, q)],
  [/^([1-4])q[-./\s']?(\d{4}|\d{2})$/i, (q, y) => quarter(y, q)],
  [/^(\d{4}|\d{2})(?:년\s*|[-./\s])([1-4])q$/i, quarter],
  [/^(\d{4}|\d{2})(?:년\s*|[-./\s]\s*)([1-4])\s*분기$/, quarter],
  [/^(\d{4}|\d{2})년([1-4])분기$/, quarter],
  [/^(\d{4})[-./\s]?h([12])$/i, half],
  [/^(\d{4})[-./\s]([12])h$/i, half],
  [/^([12])h[-./\s']?(\d{4}|\d{2})$/i, (h, y) => half(y, h)],
  [/^(\d{4}|\d{2})(?:년)?\s*(상|하)반기$/, half],   // i18n-ok
  [/^(\d{4}|\d{2})년\s*(\d{1,2})월\s*(\d{1,2})일$/, day],
  [/^(\d{4}|\d{2})년\s*(\d{1,2})월$/, month],
  [/^(\d{4})[-.\s]\s*(\d{1,2})월$/, month],
  [/^(\d{4}|\d{2})년$/, (y) => point('Y', yearOf(y))],
  [/^([a-z]{3,9})\.?[-./\s']?(\d{4}|\d{2})$/i, (w, y) => month(y, named(w))],
  [/^(\d{4})[-./\s]([a-z]{3,9})$/i, (y, w) => month(y, named(w))],
  [/^(\d{1,2})[-./\s]([a-z]{3,9})[-./\s](\d{4}|\d{2})$/i, (d, w, y) => day(y, named(w), d)],
  [/^([a-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})$/i, (w, d, y) => day(y, named(w), d)],
  [/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/, (d, m, y) => day(y, m, d)],   // 31.03.2026
];
const CLOCK = /^(\d{4}-\d{1,2}-\d{1,2})[T\s]\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?\s?(?:Z|[+-]\d{2}:?\d{2})?$/;
const SLASH = /^(\d{1,2})\/(\d{1,2})\/(\d{4}|\d{2})$/;
const SHORT_MONTH = /^(\d{2})[-./](\d{1,2})$/;

/**
 * 칸의 글 → 시점 {kind: Y|H|Q|M|D, y, m, d, at(그 시작의 ms)}. 시점이 아니면 null.
 * 앞의 ' 와 FY, 끝의 전망·잠정 표시(2026E, 2026(F), 2026*), 날짜 뒤의 시각은 뗀다. dayFirst: 3/4/2026 을 일/월로 (findTimeColumn 이 열을 보고 정한다)
 */
export function parseTime(cell, { dayFirst = false } = {}) {
  const raw = String(cell ?? '').trim().replace(/\s*·\s*/g, ' ');   // 여러 줄 머리행을 합친 이름 (2024 · 1Q)
  if (!raw || raw.length > 32) return null;
  const tick = /^['’‘]/.test(raw);
  const fiscal = /^FY/i.test(raw);
  let s = raw.replace(/^['’‘]\s*/, '').replace(/^FY['\s]?/i, '').replace(/[*†¹²³]+$/, '').replace(/\.\s+/g, '.').replace(CLOCK, '$1').replace(/년도$/, '년').replace(/월\s?말$/, '월');   // i18n-ok
  const flagged = /\d\s*\(?[EFPefp]\)?$/.test(s);
  s = s.replace(/(\d|년|기|월)\s*\(?(?:[EFPefp]|전망|예상|추정|잠정)\)?$/, '$1');
  if (/^\d{2}$/.test(s)) return tick || fiscal || flagged ? point('Y', yearOf(s)) : null;   // '26·FY26·26E — 두 자리만이면 연도가 아니다
  const short = tick && SHORT_MONTH.exec(s);   // '26.3
  if (short) return month(short[1], short[2]);
  const slash = SLASH.exec(s);
  if (slash) {
    const [, a, b, y] = slash;
    return dayFirst || Number(a) > 12 ? day(y, b, a) : day(y, a, b);
  }
  for (const [re, make] of FORMS) {
    const m = re.exec(s);
    if (m) return make(...m.slice(1));
  }
  return null;
}

/** @type {[number, string][]} */
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
    const dayFirst = filled.some((v) => Number(SLASH.exec(String(v).trim())?.[1]) > 12);   // 31/03/2026 이 있으면 01/04/2026 도 일/월이다
    const parsed = rows.map((r) => parseTime(r[c], { dayFirst }));
    const hits = parsed.filter(Boolean);
    if (hits.length / filled.length < (c === 0 ? 0.6 : 0.8)) continue;   // 맨 앞 열에는 '평균'·'전망' 같은 행이 섞이곤 한다
    const plain = filled.filter((v) => parseTime(v) && numberOf(v) != null).length / filled.length >= 0.5;   // 2026·202603 처럼 숫자로도 읽히는 표기
    if (plain && !(hits.length > 1 && (TIME_WORD.test(headers[c] ?? '') || (c === 0 && inOrder(hits))))) continue;   // 머리행에 연도라고 쓰면 품목별로 쌓여 차례가 아니어도 시간이다
    return { col: c, parsed, freq: frequencyOf(hits) };
  }
  return null;
}

// ---- 단위 ---------------------------------------------------------------------------------

/** 열의 단위 {group: level|rate|multiple, unit, key(같은 축을 쓰는 묶음)} */
export function unitInfo(header, cells, caption = '') {
  const filled = cells.map((v) => String(v ?? '').trim()).filter((v) => v && !isMissing(v));
  const mostly = (re) => filled.length > 0 && filled.filter((v) => re.test(v)).length / filled.length >= 0.7;
  const lastUnit = (s) => [...String(s ?? '').matchAll(UNIT)].at(-1)?.[1] ?? '';
  const own = lastUnit(header);
  const trailing = lastUnit(caption);
  const noted = CAPTION_UNIT.exec(caption)?.[1]?.trim() || (NOT_UNIT.test(trailing) ? '' : trailing);
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

const rowWidth = (rows) => rows.reduce((w, r) => Math.max(w, r.length), 0);

/** 머리행에서 시점이 시작하는 열 (앞에는 글 열이 있을 수 있다 — ECOS 의 통계표·항목·단위). 없으면 -1 */
function firstTimeHeader(headers) {
  const i = headers.findIndex((h, c) => c > 0 && parseTime(h));
  if (i < 0) return -1;
  const rest = headers.slice(i).filter((h) => String(h ?? '').trim());
  return rest.length >= 2 && rest.filter((h) => parseTime(h)).length / rest.length >= 0.7 ? i : -1;
}

export const headerIsTime = (headers) => firstTimeHeader(headers) > 0;

/** 행과 열을 바꾼다. 시점 앞의 글 열은 계열 이름이 된다 — 행마다 다른 열만 (통계표 이름처럼 모두 같은 열은 뺀다), 단위 열은 괄호로 */
function transposed(headers, rows) {
  const width = Math.max(headers.length, rowWidth(rows));
  const from = Math.max(1, firstTimeHeader(headers));
  const labels = Array.from({ length: from }, (_, c) => c);
  const unitCol = labels.find((c) => /단위|^units?$/i.test(String(headers[c] ?? '').trim()));
  const varying = labels.filter((c) => c !== unitCol && new Set(rows.map((r) => r[c])).size > 1);
  const nameOf = (r) => {
    const name = (varying.length ? varying : [0]).map((c) => String(r[c] ?? '').trim()).filter(Boolean).join(' · ');
    const unit = unitCol == null ? '' : String(r[unitCol] ?? '').trim();
    return unit ? `${name} (${unit})` : name;
  };
  const H = [headers[0] ?? '', ...rows.map(nameOf)];
  const R = Array.from({ length: Math.max(0, width - from) }, (_, i) => [headers[i + from] ?? '', ...rows.map((r) => r[i + from] ?? '')]);
  return [H, R];
}

/**
 * 표(머리행 headers, 행 rows — 글의 배열)를 차트의 계열로 읽는다. swap: 행과 열을 (자동으로 정한 것과) 바꾼다. caption: 머리행에 단위가 없을 때 볼 글.
 * 머리행이 시점이면 저절로 행과 열을 바꾼다. 시간 축이면 오래된 것부터 놓고, 시점이 아닌 행은 뺀다.
 * 합계·평균 행은 뺀다 (막대의 눈금을 뭉갠다). 계열은 MAX_SERIES 까지.
 * {labels, series: [{name, values(숫자 또는 null), group, unit, key}], freq, turned, skipped(시점이 아니라 뺀 행 수), totals(뺀 합계 행 수), more(못 실은 계열 수), same(같은 시점이 여럿), xName}
 */
export function readTable(headers, rows, { swap = false, caption = '' } = {}) {
  const turned = headerIsTime(headers) !== !!swap;
  const [H, R] = turned ? transposed(headers, rows) : [headers, rows];
  const time = findTimeColumn(H, R);
  const width = Math.max(H.length, rowWidth(R));
  const cols = Array.from({ length: width }, (_, c) => c);
  const x = time ? time.col : cols.find((c) => !isNumericColumn(R, c)) ?? -1;
  let order = R.map((_, i) => i);
  let skipped = 0;
  if (time) {
    order = order.filter((i) => time.parsed[i]);
    skipped = R.length - order.length;
    order.sort((a, b) => time.parsed[a].at - time.parsed[b].at);
  }
  let totals = 0;
  if (!time && x >= 0) {
    const kept = order.filter((i) => !TOTAL.test(String(R[i][x] ?? '').trim()));
    if (kept.length) {
      totals = order.length - kept.length;
      order = kept;
    }
  }
  const labels = order.map((i) => (x < 0 ? String(i + 1) : String(R[i][x] ?? '').trim()));
  const wanted = cols.filter((c) => c !== x && isNumericColumn(R, c));
  const series = wanted.slice(0, MAX_SERIES).map((c) => {
    const cells = order.map((i) => R[i][c]);
    return { name: String(H[c] ?? '').trim() || `${c + 1}`, values: cells.map((v) => (isMissing(v) ? null : numberOf(v))), ...unitInfo(H[c], cells, caption) };
  });
  return {
    labels, series, freq: time?.freq ?? null, turned, skipped, totals, more: Math.max(0, wanted.length - MAX_SERIES), xName: x < 0 ? '' : String(H[x] ?? '').trim(),
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

/** 제목 줄인지: 칸 하나, 또는 글 하나와 오른쪽의 단위 (보고서 표의 '주요 지표 … (단위: 조원)') */
function isTitleRow(row) {
  const cells = row.filter(hasText);
  if (cells.length < 2) return true;
  return cells.length === 2 && cells.every((v) => numberOf(v) == null) && /단위|^\s*[([].*[)\]]\s*$/.test(String(cells[1]));
}

/** 덩어리를 빈 열로 나눈다. 뒤 조각에 이름표 열이 없으면(둘째 열부터 숫자뿐) 표 안의 간격이다 — 앞 조각에 붙인다 */
function splitColumns(rows, a, b) {
  const width = rowWidth(rows.slice(a, b + 1));
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
  const titleOf = (i) => (isTitleRow(inside(rows[i], c0, c1)) ? filledIn(rows[i], c0, c1).map((v) => String(v).trim()).join(' ') : '');
  while (list.length > 1 && titleOf(list[0]) && numberOf(titleOf(list[0])) == null) {
    titles.push(titleOf(list[0]));
    list = list.slice(1);
  }
  while (list.length > 1 && NOTE.test(lone(list.at(-1)))) {
    notes.unshift(lone(list.at(-1)));
    list = list.slice(0, -1);
  }
  const auto = list.findIndex((i) => isBody(rows[i], c0, c1));
  let found = auto < 0 || auto > MAX_HEAD ? Math.min(1, list.length) : auto;
  while (found > 1 && lone(list[found - 1]) && hasText(rows[list[found - 1]][c0])) found -= 1;   // 몸통 바로 위의 '[실물]' 같은 묶음 줄은 머리행이 아니다
  const head = depth ?? found;
  const body = list.slice(head);
  const lineOf = (i) => (lines ? lines[i][0] : i + 1);
  const byLine = new Map(list.map((i) => [lineOf(i), i]));
  const below = new Map();   // 몸통의 세로 병합 (품목 이름 등): 줄 → [[칸, 맨 위 줄]]
  for (const [r1, m0, r2] of merges) {
    if (r2 <= r1 || m0 < c0 || m0 > c1) continue;
    for (let r = r1 + 1; r <= r2; r++) {
      if (!below.has(r)) below.set(r, []);
      below.get(r).push([m0, r1]);
    }
  }
  const cellsOf = (i) => {
    const row = inside(rows[i], c0, c1);
    for (const [col, top] of below.get(lineOf(i)) ?? []) {
      if (byLine.has(top)) row[col - c0] = rows[byLine.get(top)][col] ?? '';
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
    const text = rows.slice(a, b + 1).every(isTitleRow);
    if (text) items.push({ text: rows.slice(a, b + 1).map((r) => r.filter(hasText).map((v) => String(v).trim()).join(' ')) });
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
  if (pieces.length > MAX_REGIONS) return { regions: [], best: 0, plain: true };
  const regions = pieces.map((p) => shapeRegion(rows, lines, merges, p)).filter((r) => r.rows.length);
  const best = regions.reduce((k, r, i) => (r.size > regions[k].size ? i : k), 0);
  const width = rowWidth(rows);
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
  let c0 = Infinity;
  let c1 = -1;
  for (const i of hit) {
    rows[i].forEach((v, c) => {
      if (!hasText(v)) return;
      c0 = Math.min(c0, c);
      c1 = Math.max(c1, c);
    });
  }
  const region = shapeRegion(rows, lines, merges, { a: hit[0], b: hit.at(-1), c0, c1, titles: [], notes: [] });
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
