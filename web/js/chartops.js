// 차트의 계산 (D115, DOM 없음): vega-lite 원문을 값 표로 읽고, 값을 다시 쓰고, 종류를 바꾸고, 표에서 차트를 만든다.
// 차트의 데이터를 표로 읽는 것(chartData — D136)도 여기에: 라이브러리마다 설정 속 값의 자리를 본다.
// 사람은 JSON 을 보지 않는다. 앱이 쓰는 것은 지금의 ```vega-lite 그대로라 pptx 전환이 PowerPoint 차트로 만든다.
// 값이 문서 안에 있는 단순한 차트만 다룬다 — 파일을 읽거나 겹친 차트는 null 이고, 화면은 원문으로 연다.

import { parseCsv } from './tabledata.js';

/** 값 표로 읽는다 {fields, rows}. data.values 가 객체 배열일 때만, 아니면 null */
export function readValues(text) {
  let spec;
  try {
    spec = JSON.parse(text);
  } catch {
    return null;
  }
  const values = spec?.data?.values;
  if (!Array.isArray(values) || !values.length) return null;
  if (values.some((r) => r === null || typeof r !== 'object' || Array.isArray(r))) return null;
  const fields = [...new Set(values.flatMap((r) => Object.keys(r)))];
  if (values.some((r) => fields.some((f) => r[f] !== null && typeof r[f] === 'object'))) return null;
  return { fields, rows: values.map((r) => fields.map((f) => (r[f] == null ? '' : String(r[f])))) };
}

/** 칸의 글 → 값: 수로 읽히면 수, 빈 칸은 null */
function valueOf(s) {
  const text = String(s).trim();
  if (!text) return null;
  const n = Number(text.replace(/,/g, ''));
  return Number.isFinite(n) && /^[-+]?[\d.,]+$/.test(text) ? n : text;
}

/** 글 text 에서 "values" 의 배열이 차지하는 자리 [시작, 끝) — 없으면 null. 문자열 안의 괄호는 세지 않는다 */
function valuesSpan(text) {
  const m = /"values"\s*:\s*\[/.exec(text);
  if (!m) return null;
  const start = m.index + m[0].length - 1;
  let depth = 0;
  let quoted = false;
  for (let i = start; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '\\') i += 1;
      else if (c === '"') quoted = false;
    } else if (c === '"') quoted = true;
    else if (c === '[') depth += 1;
    else if (c === ']') {
      depth -= 1;
      if (!depth) return [start, i + 1];
    }
  }
  return null;
}

/** 값을 쓴다 — 배열만 바꾸고 나머지 글은 그대로 둔다. 쓸 수 없으면 null */
export function writeValues(text, fields, rows) {
  const span = valuesSpan(text);
  if (!span) return null;
  const objects = rows.map((r) => Object.fromEntries(fields.map((f, i) => [f, valueOf(r[i] ?? '')])));
  return `${text.slice(0, span[0])}${JSON.stringify(objects)}${text.slice(span[1])}`;
}

/** 지금 종류: 'bar'·'line'·'area'·'arc'. 겹친 차트처럼 모르면 '' */
export function chartKind(text) {
  try {
    const spec = JSON.parse(text);
    const mark = typeof spec.mark === 'string' ? spec.mark : spec.mark?.type;
    return ['bar', 'line', 'area', 'arc'].includes(mark) ? mark : '';
  } catch {
    return '';
  }
}

/** 종류를 바꾼다: 막대·선·영역은 표식만, 원은 축을 각도와 색으로. 바꾼 글, 못 바꾸면 null */
export function setChartKind(text, kind) {
  if (!chartKind(text)) return null;
  const spec = JSON.parse(text);
  const enc = spec.encoding ?? {};
  const label = enc.x ?? enc.color;
  const amount = enc.y ?? enc.theta;
  if (!label?.field || !amount?.field) return null;
  const rest = Object.fromEntries(Object.entries(enc).filter(([k]) => !['x', 'y', 'theta', 'color'].includes(k)));
  if (kind === 'arc') {
    spec.encoding = { ...rest, theta: { field: amount.field, type: 'quantitative' }, color: { field: label.field, type: 'nominal' } };
  } else {
    const series = enc.x && enc.color?.field && enc.color.field !== label.field ? { color: enc.color } : {};
    spec.encoding = { ...rest, x: { field: label.field, type: label.type ?? 'nominal' }, y: { field: amount.field, type: 'quantitative' }, ...series };
  }
  spec.mark = typeof spec.mark === 'object' && spec.mark ? { ...spec.mark, type: kind } : kind;
  return JSON.stringify(spec, null, 2);
}

/** 표에서 차트 원문을 만든다: 첫 열이 항목, 다음 열들이 값. 줄 배열, 값이 수가 아니면 {error: 'not-numeric'} */
export function chartFromTable(headers, rows, words = { series: 'series', value: 'value' }) {
  const [label, ...names] = headers;
  if (!names.length || !rows.length) return { error: 'not-numeric' };
  const number = (s) => valueOf(s);
  if (rows.some((r) => names.some((_, i) => typeof number(r[i + 1] ?? '') !== 'number'))) return { error: 'not-numeric' };
  const many = names.length > 1;
  const values = rows.flatMap((r) => names.map((name, i) => (many
    ? { [label]: r[0], [words.series]: name, [words.value]: number(r[i + 1]) }
    : { [label]: r[0], [name]: number(r[i + 1]) })));
  const amount = many ? words.value : names[0];
  const encoding = {
    x: { field: label, type: 'nominal', title: null, axis: { labelAngle: 0 } },
    y: { field: amount, type: 'quantitative', title: null },
    ...(many ? { color: { field: words.series, type: 'nominal', title: null } } : {}),
  };
  const body = ['{', '  "width": "container",', `  "data": {"values": ${JSON.stringify(values)}},`, '  "mark": "bar",',
    `  "encoding": ${JSON.stringify(encoding)}`, '}'];
  return { lines: ['```vega-lite', ...body, '```'] };
}

// ---- 데이터를 문서 안으로 (D136) ----------------------------------------------------------
// CSV 를 가리키는 차트(data.url)는 그 CSV 가 함께 가지 않으면 다른 PC 에서 그려지지 않는다. 사용자가 고를 때 그 CSV 를 읽어
// data 를 {"values": [...]} 로 바꾼다. 같은 그림이 나오게 CSV 의 칸은 Vega 의 자동 읽기처럼 수·참거짓은 그 값으로, 날짜·글은 글로.

/** CSV 의 칸 → 값 (Vega 의 'auto' 읽기에 맞춤): 빈 칸은 null, 수, true·false, 나머지는 글 */
export function csvValue(cell) {
  const s = String(cell ?? '');
  if (!s.trim()) return null;
  if (s === 'true' || s === 'false') return s === 'true';
  if (/^\s*[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?\s*$/i.test(s)) return Number(s);
  return s;
}

/** 파일의 글 → 읽을 글: 맨 앞의 BOM(엑셀의 UTF-8 CSV)을 떼고 줄바꿈을 \n 으로 (Vega 의 CSV 읽기도 CRLF 를 줄바꿈으로 본다) */
export const csvText = (text) => String(text).replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n');

/** CSV 의 행들(첫 행이 머리) → 레코드 배열 */
export function csvRecords(rows) {
  const [head, ...body] = rows;
  if (!head) return [];
  return body.filter((r) => r.some((c) => String(c ?? '').trim())).map((r) => Object.fromEntries(head.map((h, i) => [h, csvValue(r[i])])));
}

/** 글 안의 [시작, 끝) 마다 그 자리를 품는 가장 안쪽 객체({…})의 자리 — 문자열 안의 괄호는 세지 않는다 */
function enclosingObject(text, at) {
  const stack = [];
  let quoted = false;
  let found = -1;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (i === at) found = stack.length ? stack[stack.length - 1] : -1;
    if (quoted) {
      if (c === '\\') i += 1;
      else if (c === '"') quoted = false;
    } else if (c === '"') quoted = true;
    else if (c === '{') stack.push(i);
    else if (c === '}') {
      const open = stack.pop();
      if (open === found && found >= 0) return [open, i + 1];
    }
  }
  return null;
}

/** 줄 머리의 들여쓰기 (그 자리가 든 줄) */
const indentAt = (text, at) => /^[ \t]*/.exec(text.slice(text.lastIndexOf('\n', at - 1) + 1))[0];

/**
 * 차트 원문의 "url": "<주소>" 를 품은 data 객체를 {"values": [...], 나머지 키} 로 바꾼다. data: {주소 → 레코드 배열}.
 * format 의 type·delimiter 는 글을 읽는 방법이라 뺀다 (parse 는 둔다). 바꿀 수 없으면 null
 */
export function inlineUrlData(text, data) {
  let out = text;
  let changed = false;
  for (const [url, records] of Object.entries(data)) {
    const re = new RegExp(`"url"\\s*:\\s*${JSON.stringify(url).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`, 'g');
    const hits = [...out.matchAll(re)].map((m) => m.index).reverse();   // 뒤에서부터 — 앞의 자리가 그대로이게
    for (const at of hits) {
      const span = enclosingObject(out, at);
      if (!span) return null;
      let obj;
      try {
        obj = JSON.parse(out.slice(span[0], span[1]));
      } catch {
        return null;
      }
      delete obj.url;
      if (obj.format && typeof obj.format === 'object') {
        delete obj.format.type;
        delete obj.format.delimiter;
        if (!Object.keys(obj.format).length) delete obj.format;
      }
      const ind = indentAt(out, span[0]);
      const inner = `${ind}  `;
      const parts = [`"values": [\n${records.map((r) => `${inner}  ${JSON.stringify(r)}`).join(',\n')}\n${inner}]`,
        ...Object.entries(obj).map(([k, v]) => `${JSON.stringify(k)}: ${JSON.stringify(v)}`)];
      out = `${out.slice(0, span[0])}{\n${parts.map((p) => `${inner}${p}`).join(',\n')}\n${ind}}${out.slice(span[1])}`;
      changed = true;
    }
  }
  return changed ? out : null;
}

// ---- 차트의 데이터를 표로 (D136 — 화면은 chartdata.js, 점검은 tools/edges/chartops_cases.js) ----------------

const isObj = (v) => v && typeof v === 'object' && !Array.isArray(v);

/** 값의 배열 → {fields, rows}: 객체면 키들(처음 나온 차례), 배열이면 칸 번호, 값 하나면 'value' */
export function tableOf(values, name = '') {
  if (!Array.isArray(values) || !values.length) return null;
  if (values.every(isObj)) {
    const fields = [...new Set(values.flatMap((r) => Object.keys(r)))];
    return { name, fields, rows: values.map((r) => fields.map((f) => cellOf(r[f]))) };
  }
  if (values.every(Array.isArray)) {
    const width = Math.max(...values.map((r) => r.length));
    return { name, fields: Array.from({ length: width }, (_, i) => String(i + 1)), rows: values.map((r) => Array.from({ length: width }, (_, i) => cellOf(r[i]))) };
  }
  return { name, fields: ['value'], rows: values.map((v) => [cellOf(v)]) };
}

/** 칸의 값: 수·글·참거짓은 그대로, 없음은 null, 객체·배열은 JSON 글로 */
const cellOf = (v) => (v == null ? null : typeof v === 'object' ? JSON.stringify(v) : v);

/** 글로 적은 값(values 가 글 — format.type 이 csv·tsv·json) */
function textValues(text, format) {
  const type = format?.type || 'json';
  if (type === 'json') {
    try {
      return JSON.parse(text);
    } catch {
      return null;
    }
  }
  const delim = type === 'tsv' ? '\t' : format?.delimiter || ',';
  return csvRecords(parseCsv(csvText(text), delim).rows);
}

function vegaData(d, named, out, name = '') {
  if (!isObj(d)) return;
  if (Array.isArray(d.values)) out.tables.push(tableOf(d.values, d.name || name));
  else if (typeof d.values === 'string') out.tables.push(tableOf(textValues(d.values, d.format), d.name || name));
  else if (typeof d.url === 'string') out.urls.push(d.url);
  else if (typeof d.name === 'string' && Array.isArray(named[d.name])) out.tables.push(tableOf(named[d.name], d.name));
  else if (d.sequence || d.sphere || d.graticule) out.generated = true;
  if (Array.isArray(d.transform) && d.transform.length) out.transform = true;
}

function vegaLiteSpec(spec, out) {
  const named = isObj(spec.datasets) ? spec.datasets : {};
  const visit = (node, depth) => {
    if (!isObj(node) || depth > 8) return;
    if (Array.isArray(node.transform) && node.transform.length) out.transform = true;
    if (isObj(node.encoding) && /"(aggregate|bin|timeUnit)"/.test(JSON.stringify(node.encoding))) out.transform = true;
    if (node.data) vegaData(node.data, named, out);
    for (const k of ['layer', 'concat', 'hconcat', 'vconcat']) if (Array.isArray(node[k])) node[k].forEach((n) => visit(n, depth + 1));
    if (isObj(node.spec)) visit(node.spec, depth + 1);
  };
  visit(spec, 0);
}

function echartsOption(o, out) {
  const sets = [].concat(o.dataset || []).filter(isObj);
  for (const d of sets) {
    const src = d.source;
    if (!Array.isArray(src) || !src.length) continue;
    if (src.every(Array.isArray) && !d.dimensions && src[0].every((c) => typeof c === 'string')) {
      const [head, ...body] = src;
      out.tables.push({ name: '', fields: head.map(String), rows: body.map((r) => head.map((_, i) => cellOf(r[i]))) });
    } else if (src.every(Array.isArray) && Array.isArray(d.dimensions)) {
      const fields = d.dimensions.map((x) => (isObj(x) ? x.name : String(x)));
      out.tables.push({ name: '', fields, rows: src.map((r) => fields.map((_, i) => cellOf(r[i]))) });
    } else out.tables.push(tableOf(src));
  }
  if (sets.length) return;
  const series = [].concat(o.series || []).filter(isObj);
  const value = (item) => (isObj(item) ? item.value : item);
  const axis = (a) => [].concat(a || []).find((x) => isObj(x) && Array.isArray(x.data));
  const cat = axis(o.xAxis) || axis(o.yAxis);
  const pies = series.filter((s) => s.type === 'pie' || s.type === 'funnel' || (Array.isArray(s.data) && s.data.length && s.data.every((x) => isObj(x) && 'name' in x)));
  for (const s of pies) out.tables.push({ name: s.name || '', fields: ['name', 'value'], rows: s.data.map((x) => [cellOf(x.name), cellOf(value(x))]) });
  const rest = series.filter((s) => !pies.includes(s) && Array.isArray(s.data));
  if (!rest.length) return;
  if (cat && rest.every((s) => s.data.every((x) => !Array.isArray(value(x))))) {
    const names = rest.map((s, i) => s.name || out.seriesName(i + 1));
    out.tables.push({ name: '', fields: [cat.name || '', ...names], rows: cat.data.map((c, i) => [cellOf(value(c)), ...rest.map((s) => cellOf(value(s.data[i])))]) });
    return;
  }
  const rows = rest.flatMap((s, i) => s.data.map((x) => {
    const v = value(x);
    return [s.name || out.seriesName(i + 1), ...(Array.isArray(v) ? v.slice(0, 2).map(cellOf) : [null, cellOf(v)])];
  }));
  out.tables.push({ name: '', fields: ['series', 'x', 'y'], rows });
}

function plotlySpec(spec, out) {
  const traces = (Array.isArray(spec) ? spec : spec.data || []).filter(isObj);
  const rest = [];
  for (const [i, tr] of traces.entries()) {
    const name = tr.name || out.seriesName(i + 1);
    // x 가 없으면 Plotly 는 차례 번호로 그린다 — 선·막대·점에서만 뜻이 있다 (상자 그림·히스토그램의 차례는 뜻이 없다)
    const ordered = !tr.type || /^(scatter|scattergl|bar)$/.test(tr.type);
    if (Array.isArray(tr.labels) && Array.isArray(tr.values)) out.tables.push({ name, fields: ['label', 'value'], rows: tr.labels.map((l, j) => [cellOf(l), cellOf(tr.values[j])]) });
    else if (Array.isArray(tr.y) || Array.isArray(tr.x)) rest.push({ name, x: tr.x, y: tr.y, ordered });
  }
  if (!rest.length) return;
  const xOf = (r) => (Array.isArray(r.x) ? r.x : r.ordered && Array.isArray(r.y) ? r.y.map((_, j) => j + 1) : null);
  const xs = xOf(rest[0]);
  if (xs && rest.every((r) => Array.isArray(r.y) && JSON.stringify(xOf(r)) === JSON.stringify(xs))) {
    out.tables.push({ name: '', fields: ['x', ...rest.map((r) => r.name)], rows: xs.map((x, j) => [cellOf(x), ...rest.map((r) => cellOf(r.y[j]))]) });
    return;
  }
  const withX = rest.some(xOf);
  const withY = rest.some((r) => Array.isArray(r.y));
  out.tables.push({ name: '', fields: ['series', ...(withX ? ['x'] : []), ...(withY ? ['y'] : [])],
    rows: rest.flatMap((r) => {
      const x = xOf(r);
      return Array.from({ length: Math.max(r.x?.length || 0, r.y?.length || 0) }, (_, j) => [r.name,
        ...(withX ? [cellOf(x?.[j])] : []), ...(withY ? [cellOf(r.y?.[j])] : [])]);
    }) });
}

/**
 * 설정 → {tables: [{name, fields, rows}], urls, transform, generated}. kind 는 vega-lite·vega·echarts·plotly.
 * 같은 데이터를 여러 층이 쓰면 한 번만. seriesName(n): 이름 없는 계열의 이름
 */
export function chartData(kind, spec, seriesName = (n) => `series ${n}`) {
  const out = { tables: [], urls: [], transform: false, generated: false, seriesName };
  if (!spec || typeof spec !== 'object') return out;
  if (kind === 'vega-lite') vegaLiteSpec(spec, out);
  else if (kind === 'vega') {
    for (const d of [].concat(spec.data || [])) vegaData(d, {}, out, d?.name || '');
  } else if (kind === 'echarts') echartsOption(spec, out);
  else if (kind === 'plotly') plotlySpec(spec, out);
  const seen = new Set();
  out.tables = out.tables.filter((tb) => {
    if (!tb || !tb.rows.length) return false;
    const key = JSON.stringify([tb.fields, tb.rows]);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  out.urls = [...new Set(out.urls)];
  delete out.seriesName;
  return out;
}

/**
 * n 행 가운데 보일 행: max 를 넘으면 처음·끝을 넣고 그 사이를 고르게 — [{i}] 와 건너뛴 자리 [{skip: 행 수}].
 * {items, step} — step 은 대략 몇 행마다인지 (줄이지 않았으면 1)
 */
export function thinRows(n, max = 30) {
  if (n <= max) return { items: Array.from({ length: n }, (_, i) => ({ i })), step: 1 };
  const picks = [...new Set(Array.from({ length: max }, (_, k) => Math.round((k * (n - 1)) / (max - 1))))];
  const items = [];
  picks.forEach((i, k) => {
    if (k && i - picks[k - 1] > 1) items.push({ skip: i - picks[k - 1] - 1 });
    items.push({ i });
  });
  return { items, step: Math.round((n - 1) / (max - 1)) };
}

/** 표 → 복사할 탭으로 나눈 글 (수는 그대로 — 쉼표 없이) */
export function tableText(tb) {
  const plain = (v) => (v == null ? '' : String(v));
  const rows = [tb.fields, ...tb.rows.map((r) => r.map(plain))];
  return rows.map((r) => r.map((c) => String(c).replace(/[\t\n]/g, ' ')).join('\t')).join('\n');
}
