// 차트의 계산 (D115, DOM 없음): vega-lite 원문을 값 표로 읽고, 값을 다시 쓰고, 종류를 바꾸고, 표에서 차트를 만든다.
// 사람은 JSON 을 보지 않는다. 앱이 쓰는 것은 지금의 ```vega-lite 그대로라 pptx 전환이 PowerPoint 차트로 만든다.
// 값이 문서 안에 있는 단순한 차트만 다룬다 — 파일을 읽거나 겹친 차트는 null 이고, 화면은 원문으로 연다.

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
