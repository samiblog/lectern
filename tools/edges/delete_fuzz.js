// 한 줄 지우기가 남은 줄의 종류·레벨을 바꾸지 않는지 (D189 — 2026-11-22 사용자 보고: '위 아래의 스타일 또는 레벨이 변경되는 경우도 있었다').
// rules_check.mjs 가 돌린다 (m: lineops.js, window.markdownit). 끝에서 {runs, problems, kinds} 를 돌려준다.
// 줄마다 markdown-it 이 읽은 자리(목록·항목의 깊이, 인용·강조글, 문단·느슨한 목록의 문단·제목·표의 행·코드)를 적고, 화면의 한 줄(줄 단위)을
// 지운 뒤 남은 글 줄의 자리가 그대로인지 본다. 지운 항목의 하위 항목이 그 자리로 올라가는 것은 정한 대로다 (deleteLines).
const { deleteLines } = m;
const md = window.markdownit({ html: true });
const CALLOUT = /^\s*(?:>\s*)+\[!\w+\]/;
const SETEXT = /^\s*(?:=+|-+)\s*$/;

/** 줄마다의 자리 — 글 줄만 (빈 줄·표시 줄은 null). items: 그 줄을 가진 항목들의 [첫 줄, 끝 다음 줄] (0부터), list: 가장 안쪽 목록의 첫 줄 */
function placesOf(lines) {
  const toks = md.parse(lines.join('\n'), {});
  const out = lines.map(() => null);
  const stack = [];
  const set = (map, leaf) => {
    if (!map) return;
    const path = stack.filter((s) => s.name).map((s) => s.name);
    const items = stack.filter((s) => s.item).map((s) => s.item);
    const list = stack.filter((s) => s.list != null).at(-1)?.list ?? null;
    for (let i = map[0]; i < map[1] && i < lines.length; i++) out[i] = { at: [...path, leaf].join('>'), items, list };
  };
  for (const t of toks) {
    if (t.nesting === 1) {
      let name = null;
      if (t.type === 'bullet_list_open') name = `ul${t.markup}`;
      else if (t.type === 'ordered_list_open') name = `ol${t.markup}`;
      else if (t.type === 'list_item_open') name = 'li';
      else if (t.type === 'blockquote_open') name = CALLOUT.test(lines[t.map[0]] ?? '') ? 'callout' : 'bq';
      else if (t.type === 'thead_open') name = 'thead';
      else if (t.type === 'tbody_open') name = 'tbody';
      if (t.type === 'paragraph_open') set(t.map, t.hidden ? 'p' : 'p+');   // p+: 느슨한 목록의 문단 (항목 사이가 벌어진다)
      else if (t.type === 'heading_open') set(t.map, t.tag);
      else if (t.type === 'tr_open') set(t.map, 'tr');
      let item = null;
      if (t.type === 'list_item_open') {   // [첫 줄, 끝 다음 줄, 앞 형제 항목들의 첫 줄]
        const own = stack.filter((s) => s.list != null).at(-1);
        item = [t.map[0], t.map[1], own ? own.seen.slice() : []];
        if (own) own.seen.push(t.map[0]);
      }
      stack.push({ name, item, list: /^(bullet|ordered)_list_open$/.test(t.type) ? t.map[0] : null, seen: [] });
    } else if (t.nesting === -1) stack.pop();
    else if (t.type === 'fence' || t.type === 'code_block') set(t.map, 'code');
    else if (t.type === 'hr') set(t.map, 'hr');
    else if (t.type === 'html_block') set(t.map, 'html');
  }
  return out;
}

const idOf = (s) => /w\d+/.exec(s)?.[0] ?? null;

// ---- 임의의 문서 (mulberry32 — PITFALLS: 선형 합동법은 아래 비트가 고르지 않다) -----------------
let seed = globalThis.DELETE_FUZZ_SEED ?? 20261122;
const rand = () => {
  seed = (seed + 0x6D2B79F5) | 0;
  let x = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
  return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
};
const rnd = (n) => Math.floor(rand() * n);
const pick = (a) => a[rnd(a.length)];
let uid = 0;
const w = () => `글w${++uid}`;

/** 목록 — 깊이·번호·할 일·이어 쓴 줄·문단 띄우기(느슨한 목록) */
function list(depth = 0, pad = 0, loose = rnd(3) === 0) {
  const out = [];
  const ordered = rnd(2) === 0;
  const bullet = pick(['-', '-', '*']);
  const n = 1 + rnd(4);
  for (let i = 1; i <= n; i++) {
    if (loose && out.length) out.push('');
    const marker = ordered ? `${i}.` : bullet;
    out.push(`${' '.repeat(pad)}${marker} ${rnd(5) === 0 ? '[ ] ' : ''}${w()}`);
    const content = pad + marker.length + 1;
    if (rnd(5) === 0) out.push(`${' '.repeat(content)}${w()}`);   // 이어 쓴 줄
    if (rnd(6) === 0) out.push('', `${' '.repeat(content)}${w()}`);   // 항목 안의 둘째 문단
    if (depth < 2 && rnd(3) === 0) out.push(...list(depth + 1, content, rnd(4) === 0));
  }
  return out;
}
const BLOCKS = [
  () => [`# ${w()}`],
  () => [`## ${w()}`],
  () => [`### ${w()}`],
  () => [w()],
  () => [w(), w()],
  () => list(),
  () => list(),
  () => [`> ${w()}`, `> ${w()}`],
  () => [`> ${w()}`, '>', `> ${w()}`],
  () => ['> [!NOTE]', `> ${w()}`],
  () => ['> [!TIP]', `> ${w()}`, `> ${w()}`],
  () => ['> [!WARNING]', `> ${w()}`, '>', `> ${w()}`],
  () => [`| ${w()} | ${w()} |`, '|---|---|', `| ${w()} | ${w()} |`, `| ${w()} | ${w()} |`],
  () => ['```', w(), w(), '```'],
  () => ['---'],
  () => [`제목 ${w()}`, '==='],
  () => list().map((s) => (s ? `> ${s}` : '>')),   // 인용 안의 목록
  () => ['> [!NOTE]', ...list().map((s) => (s ? `> ${s}` : '>'))],   // 강조글 안의 목록
];
function doc() {
  const parts = [];
  const n = 2 + rnd(6);
  for (let i = 0; i < n; i++) {
    const p = pick(BLOCKS)();
    if (!i && p[0] === '---') { i -= 1; continue; }   // 맨 앞의 --- 는 머리 설정으로 읽힌다 (markdown-it 은 가로줄)
    parts.push(p);
  }
  const lines = [];
  parts.forEach((p, i) => { if (i) lines.push(''); lines.push(...p); });
  lines.push('');
  return lines;
}

/** 화면의 한 줄(줄 단위)로 지우는 범위 — 강조글의 첫 글 줄은 머리 줄과 한 단위, 밑줄 제목은 두 줄, 나머지는 그 줄 */
function unitOf(lines, n) {
  if (CALLOUT.test(lines[n - 2] ?? '')) return [n - 1, n];
  if (n < lines.length && lines[n - 1].trim() && SETEXT.test(lines[n] ?? '') && !/^\s*[-*+]\s/.test(lines[n - 1])) return [n, n + 1];
  return [n, n];
}

const LIMIT = globalThis.DELETE_FUZZ_LIMIT ?? 3;   // 종류마다 보일 보기 수
// 지운 줄이 든 목록의 간격 — 지운 문단이 그 목록을 느슨하게 하던 까닭이었으면(문단이 하나만 남은 항목 등) Markdown 에서 피할 수 없다. 세기만 한다
const SAME_LIST = '지운 줄이 든 목록의 간격이 바뀜 (피할 수 없는 것)';
const MERGED = '두 목록이 하나로 합쳐져 간격이 바뀜 — 한쪽이 띄운 목록 (피할 수 없는 것)';
const problems = [];
const kinds = {};
let runs = 0;
const note = (kind, lines, range, before, after, id) => {
  kinds[kind] = (kinds[kind] || 0) + 1;
  const near = lines.map((s, i) => `${i + 1 >= range[0] && i + 1 <= range[1] ? 'x' : ' '}${i + 1}|${s}`).slice(Math.max(0, range[0] - (globalThis.DELETE_FUZZ_NEAR ?? 8)), range[1] + (globalThis.DELETE_FUZZ_NEAR ?? 8));
  if (kinds[kind] <= LIMIT && ((kind !== SAME_LIST && kind !== MERGED) || globalThis.DELETE_FUZZ_ALL)) problems.push(`${kind}: ${range.join('~')}행을 지우니 ${id} 가 ${before} → ${after}\n${near.join('\n')}`);
};
const ITEM = /^\s*(?:>\s*)*\s*(?:[-*+]|\d{1,9}[.)])(?:\s|$)/;
const lis = (at) => at.split('>').filter((s) => s === 'li').length;
const leaf = (at) => at.split('>').at(-1).replace(/\+$/, '');
for (let d = 0; d < (globalThis.DELETE_FUZZ_DOCS ?? 400); d++) {
  const lines = doc();
  const before = placesOf(lines);
  const words = lines.map((s, i) => (idOf(s) && before[i] != null ? i + 1 : 0)).filter(Boolean);
  // 한 줄 단위마다, 그리고 가끔 뒤의 한두 단위까지 (여러 줄 고르기)
  const ranges = words.flatMap((n, k) => {
    const one = unitOf(lines, n);
    const to = words[k + 1 + rnd(2)];
    return rnd(3) === 0 && to && globalThis.DELETE_FUZZ_MULTI !== false ? [one, [one[0], unitOf(lines, to)[1]]] : [one];
  });
  for (const [a, b] of ranges) {
    const del = deleteLines(lines, a, b);
    if (del.error) continue;
    runs += 1;
    const after = placesOf(del.lines);
    const where = new Map(del.lines.map((s, i) => [idOf(s), i]).filter(([id]) => id));
    const gone = new Set();
    for (let i = del.a; i <= del.b; i++) gone.add(i - 1);
    // 지운 항목: 그 항목의 글이 남으면 첫 줄이 표시를 넘겨받아 같은 레벨, 하위 항목만 남으면 앞 형제가 있으면 그 아래로 같은 레벨,
    // 목록의 첫 항목이었으면 한 레벨 위로 (deleteLines)
    const keepsItem = ([s0, e0, prevs]) => {
      if (prevs.some((p) => p < a - 1)) return true;   // 지우지 않는 앞 형제가 있다 — 그 아래로
      for (let i = b; i < e0; i++) {   // 범위 뒤의 첫 글 줄이 이 항목 자신의 글(가장 안쪽 항목이 이 항목)이면 표시를 넘겨받는다
        if (!lines[i].replace(/^[\s>]*/, '')) continue;
        return before[i]?.items.at(-1)?.[0] === s0 && !ITEM.test(lines[i]) && !/^\s*(?:>\s*)*\s*(?:```|~~~|#|\|)/.test(lines[i]);
      }
      return false;
    };
    const deletedLists = new Set();   // 지운 줄들이 든 목록 (강조글의 머리 줄은 남는다)
    for (let i = del.a; i <= del.b; i++) if (before[i - 1]?.list != null) deletedLists.add(before[i - 1].list);
    // 두 목록이 하나로 합쳐진 것 — 지운 항목의 하위 항목이 앞 형제의 하위 목록과 같은 종류일 때, 두 목록 사이의 글을 지웠을 때.
    // 합친 목록의 간격은 한쪽이 띄운 목록이면 띄운 목록이다 (피할 수 없다 — 둘 다 붙은 목록이면 deleteLines 가 붙인다)
    const sources = new Map();
    lines.forEach((s, i) => {
      const j = where.get(idOf(s));
      if (j == null || gone.has(i) || after[j]?.list == null) return;
      if (!sources.has(after[j].list)) sources.set(after[j].list, new Set());
      sources.get(after[j].list).add(before[i]?.list ?? 'none');
    });
    const merged = new Set([...sources].filter(([, from]) => from.size > 1).map(([list]) => list));
    lines.forEach((s, i) => {
      const id = idOf(s);
      if (!id || gone.has(i) || before[i] == null) return;
      const j = where.get(id);
      if (j == null) { note('글이 사라짐', lines, [a, b], before[i].at, '없음', id); return; }
      const x = before[i];
      const y = after[j];
      if (y == null) { note('글 줄이 아니게 됨', lines, [a, b], x.at, '?', id); return; }
      const owners = x.items.filter(([s0]) => s0 >= a - 1 && s0 <= b - 1);   // 그 줄을 가진, 지운 항목들
      if (owners.length) {
        const up = owners.filter((r) => !keepsItem(r)).length;
        if (lis(y.at) !== lis(x.at) - up || leaf(y.at) !== leaf(x.at)) note('지운 항목 안의 줄이 엉뚱한 레벨로', lines, [a, b], x.at, y.at, id);
        return;
      }
      if (x.at === y.at) return;
      if (x.at.replace(/p\+$/, 'p') === y.at.replace(/p\+$/, 'p')) {
        note(x.list != null && deletedLists.has(x.list) ? SAME_LIST : merged.has(y.list) ? MERGED : '다른 목록의 간격(느슨함)이 바뀜', lines, [a, b], x.at, y.at, id);
      }
      else note(lis(x.at) !== lis(y.at) ? '항목의 레벨이 바뀜' : '줄의 종류가 바뀜', lines, [a, b], x.at, y.at, id);
    });
  }
}
return { runs, problems, kinds };
