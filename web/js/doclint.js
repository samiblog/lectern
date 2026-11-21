// md 문서 점검 (D190, DOM 없음): 원문 줄을 읽어 틀이 깨진 곳(A)·보고서의 틀에서 벗어난 곳(B)·글버릇(C — 기본 끔)을 찾는다.
// 화면은 doccheck.js (상태줄의 '점검 N곳'과 목록), 고치기의 저장은 lineedit.js 의 'lint-fix' (commit — Ctrl+Z 한 걸음).
//
// - 돌려주는 것은 [{line, group, code, args, fix?}] — 문구는 화면이 code 로 옮긴다 (이 모듈은 i18n 을 부르지 않는다 — node 의 규칙 시험이 돌린다).
// - fix: {kind, apply(lines) → 새 줄 배열 | null}. 계산이 확실한 것만 — 그 줄이 점검할 때와 같을 때만 고친다 (그사이 바뀌었으면 null).
// - Lectern 슬라이드(marp: true)는 보지 않는다 — 슬라이드 점검(slides.js·slidetools.js)이 따로 있다.
// - 문서 속 그림이 없는 것처럼 화면에서만 알 수 있는 것은 doccheck.js 가 더한다.
// 표 점검·임의 시험은 tools/edges/lint_cases.js (rules_check).

import { fencesOf, fenceAt, frontEnd, deckOf, blocksOf, tableIn, itemOf, itemSpan, quoteOf, isBlank, renumberFrom, siblingsOf } from './lineops.js';
import { captionsIn, captionAt, refTargets, captionId, CAPTION_WORDS } from './refs.js';
import { detect, applyScheme } from './headstyle.js';

/** 강조글의 종류 (doc.js 의 decorateAlerts 와 같게) */
const KINDS = ['NOTE', 'TIP', 'IMPORTANT', 'WARNING', 'CAUTION'];
/** 표·그림 아래의 출처 줄 (toc.js 의 SOURCE 와 같게) */
const SOURCE = /^[\s※*·•\-]*[(\[]?\s*(?:자료|출처|원자료|원문|주|source|sources|data source|note)\s*[)\]]?\s*[:：]/i;   // i18n-ok (원문의 낱말)
/** 그림 캡션이 붙는 코드 블록 (차트·다이어그램 — D56·D184) */
const CHART_LANGS = /^(?:vega-lite|vega|echarts|plotly|mermaid|dot|graphviz)\b/i;
const IMAGE_ONLY = /^\s*(?:\[\s*)?!\[[^\]]*\]\([^)]*\)(?:\s*\]\([^)]*\))?\s*$/;
const TABLE_WORDS = new Set(['표', 'Table']);   // i18n-ok (캡션 낱말)
const FIGURE_WORDS = new Set(['그림', 'Figure']);   // i18n-ok (캡션 낱말)

/** C 묶음의 기준 — 작성 안내(help/writing.md)의 '한 문장은 한 줄에', 표의 칸은 한두 줄과 맞춘 어림 */
export const LIMITS = { paragraph: 600, sentence: 150, cell: 60 };

const bodyOf = (s) => s.slice(quoteOf(s).length);
const depthOf = (s) => (quoteOf(s).match(/>/g) || []).length;
const leadOf = (s) => /^[ \t]*/.exec(bodyOf(s))[0];

/** 두 낱말의 편집 거리 */
function distance(a, b) {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  }
  return d[a.length][b.length];
}

/**
 * 표의 한 행의 칸 글들 — 앞뒤의 | 를 떼고 | 로 나눈다. markdown-it(GFM)과 같게: 앞에 역슬래시가 홀수 개인 \| 만 칸 나눔이 아니고,
 * `…` 안의 | 도 칸을 나눈다
 */
export function cellsOf(line) {
  const s = bodyOf(line).trim();
  const cuts = [];
  for (let i = 0; i < s.length; i++) {
    if (s[i] !== '|') continue;
    let k = 0;
    while (i - k - 1 >= 0 && s[i - k - 1] === '\\') k += 1;
    if (k % 2 === 0) cuts.push(i);
  }
  const parts = [];
  let from = 0;
  for (const c of cuts) {
    parts.push(s.slice(from, c).trim());
    from = c + 1;
  }
  parts.push(s.slice(from).trim());
  if (cuts[0] === 0) parts.shift();   // 앞의 |
  if (cuts.length && cuts.at(-1) === s.length - 1) parts.pop();   // 뒤의 |
  return parts;
}

/** markdown-it 으로 머리 설정 뒤의 본문을 읽는다 — 토큰의 map 을 원문 줄(0부터)로 맞춘다 */
function tokensOf(lines, md) {
  const start = frontEnd(lines);
  const toks = md.parse(lines.slice(start).join('\n'), {});
  for (const tk of toks) if (tk.map) tk.map = [tk.map[0] + start, tk.map[1] + start];
  return toks;
}

/** 줄 n 이 점검할 때와 같을 때만 fn 으로 고친다 — 그사이 문서가 바뀌었으면 null */
const guarded = (n, expect, fn) => (lines) => (lines[n - 1] === expect ? fn(lines) : null);
/** 줄 at(1부터) 앞에 줄들을 넣은 새 배열 */
const insertAt = (lines, at, add) => [...lines.slice(0, at - 1), ...add, ...lines.slice(at - 1)];
/** 줄 n 의 인용 표시에 맞춘 빈 줄 */
const blankLike = (s) => quoteOf(s).replace(/[ \t]+$/, '');

/**
 * 캡션 번호를 문서 차례대로 1, 2, 3… — 그 낱말의 상호 참조 링크([표 3](#표-3))도 함께. 같은 번호가 둘이면 참조를 알 수 없어 null
 */
function orderCaptions(lines, word) {
  const caps = captionsIn(lines).filter((c) => c.word === word);
  const olds = caps.map((c) => c.n).filter((n) => n > 0);
  if (new Set(olds).size !== olds.length) return null;
  const map = new Map();
  const next = lines.slice();
  caps.forEach((c, i) => {
    if (c.n > 0) map.set(c.n, i + 1);
    next[c.line - 1] = next[c.line - 1].replace(new RegExp(`(${word}[ \\t]*)${c.n}(?!\\d)`), `$1${i + 1}`);
  });
  const fences = fencesOf(next);
  const ref = new RegExp(`\\[${word} (\\d{1,4})\\]\\(#${word.toLowerCase()}-(\\d{1,4})\\)`, 'g');
  return next.map((s, i) => (fenceAt(fences, i + 1) || !s.includes('](#') ? s : s.replace(ref, (all, a) => {
    const to = map.get(Number(a));
    return to ? `[${word} ${to}](#${captionId(word, to)})` : all;
  })));
}

/**
 * 제목 번호를 이 문서의 모양(headstyle.detect)대로 다시 매긴 새 배열 — 이미 번호가 있는 제목의 번호만 바꾸고, 번호가 없는 제목(일부러 뺀 절)·
 * 다른 꼴의 번호('1-1.')에는 번호를 붙이지 않는다. 바꾼 제목으로 가는 절 링크도. 바꿀 것이 없으면 null
 */
function numbersOnly(lines, slug) {
  const scheme = detect(lines);
  if (scheme === 'plain') return null;
  const first = applyScheme(lines, scheme, slug);
  if (!first.changed) return null;
  const head = (s) => /^\s*#{1,6}\s/.test(s);
  const text = (x) => x.replace(/^\s*#{1,6}\s+/, '').replace(/\s+#+\s*$/, '').trim();
  const rest = (s) => text(s).replace(/^\S+\s+/, '');
  // 번호가 없던 제목(번호를 붙이려 한 것)은 셈에서 뺀다 — 제목이 아닌 줄로 가려 두고 다시 매긴다
  const masked = lines.map((s, i) => (head(s) && first.lines[i] !== s && rest(first.lines[i]) === text(s) ? `​${s}` : s));
  const r = applyScheme(masked, scheme, slug);
  const next = lines.slice();
  const moved = new Map();
  r.lines.forEach((s, i) => {
    if (s === masked[i] || masked[i] !== lines[i] || !head(lines[i]) || rest(s) !== rest(lines[i])) return;   // 번호 글자만 바뀐 제목
    next[i] = s;
    moved.set(slug(text(lines[i])), slug(text(s)));
  });
  if (!moved.size) return null;
  const fences = fencesOf(next);
  return next.map((s, i) => (fenceAt(fences, i + 1) || /^\s*#{1,6}\s/.test(s) || !s.includes('](#') ? s
    : s.replace(/\]\(#([^)\s]+)\)/g, (all, id) => {
      let key = id;
      try {
        key = decodeURIComponent(id);
      } catch { /* 그대로 */ }
      const to = moved.get(key);
      return to ? `](#${to})` : all;
    })));
}

/**
 * 문서를 점검한다 → [{line(1부터), group('A'|'B'|'C'), code, args, fix?: {kind, apply}}] — 줄 차례로.
 * slug: 제목 글 → 앵커 id (markdown.js 의 slugify), style: C 묶음(글버릇)도, md: markdown-it (없으면 window.markdownit),
 * emptyOk: 글이 없는 절을 보지 않는다 (업무 카드 WORK.md — 기본 틀의 절은 비어 있다, D124)
 * @param {string[]} lines
 * @param {{slug?: (text: string) => string, style?: boolean, md?: any, emptyOk?: boolean}} [opt]
 * @returns {LintIssue[]}
 */
export function lintDoc(lines, { slug = (s) => s.toLowerCase().replace(/\s+/g, '-'), style = false, md = null, emptyOk = false } = {}) {
  if (!lines.length || deckOf(lines)) return [];
  const parser = md ?? window.markdownit({ html: true });
  /** @type {LintIssue[]} */
  const out = [];
  const add = (line, group, code, args = {}, fix = null) => out.push({ line, group, code, args, ...(fix ? { fix } : {}) });
  const fences = fencesOf(lines);
  const front = frontEnd(lines);
  const toks = tokensOf(lines, parser);
  const inCode = (n) => !!fenceAt(fences, n);
  const blocks = blocksOf(lines);

  // ---- A. 깨진 틀 -------------------------------------------------------------------------------
  // 머리 설정의 닫는 --- 가 없다 — 머리 설정 전체가 본문이 된다
  if (lines[0]?.trim() === '---' && !front && /^[\w.-]+\s*:/.test(lines[1] ?? '')) {
    let end = 2;
    while (end < lines.length && lines[end].trim() && (/^[\w.-]+\s*:/.test(lines[end]) || /^\s/.test(lines[end]))) end += 1;
    add(1, 'A', 'front-open', {}, { kind: 'close-front', apply: guarded(1, lines[0], (l) => insertAt(l, end + 1, ['---'])) });
  }
  for (const f of fences) {   // 닫지 않은 코드·수식 블록 — 뒤의 글이 모두 코드가 된다
    if (f.closed) continue;
    const open = lines[f.a - 1];
    const math = /^\s*\$\$/.test(bodyOf(open));
    const fence = math ? '$$' : /^[ \t]*(`{3,}|~{3,})/.exec(bodyOf(open))?.[1] ?? '```';
    const close = `${quoteOf(open)}${leadOf(open)}${fence}`;
    add(f.a, 'A', math ? 'math-open' : 'fence-open', {}, {
      kind: 'close-fence',
      apply: guarded(f.a, open, (l) => {   // 다음 제목 앞(그 앞의 빈 줄 앞)에, 없으면 문서 끝의 글 뒤에
        let at = l.findIndex((s, i) => i >= f.a && /^#{1,6}\s/.test(s));
        if (at < 0) at = l.length;
        while (at > f.a && isBlank(l[at - 1])) at -= 1;
        return insertAt(l, at + 1, [close]);
      }),
    });
  }
  for (const blk of blocks) {   // 표의 칸 수
    const tb = tableIn(lines, blk);
    if (!tb) continue;
    const width = cellsOf(lines[tb.head - 1]).length;
    if (cellsOf(lines[tb.sep - 1]).length !== width) {
      add(tb.head, 'A', 'table-sep', { n: cellsOf(lines[tb.sep - 1]).length, m: width });
      continue;
    }
    for (let n = tb.first; n <= tb.last; n++) {
      const k = cellsOf(lines[n - 1]).length;
      if (k !== width && lines[n - 1].includes('|')) add(n, 'A', 'table-cells', { n: k, m: width });
    }
  }
  let listDepth = 0;
  for (const tk of toks) {
    if (tk.type === 'list_item_open') listDepth += 1;
    else if (tk.type === 'list_item_close') listDepth -= 1;
    if (tk.type === 'code_block' && tk.map) {   // 4칸 넘게 들여 쓴 글·목록이 코드 블록으로
      const first = tk.content.split('\n').find((s) => s.trim()) ?? '';
      if (/^\s*(?:[-*+]|\d{1,9}[.)])\s/.test(first) || /[가-힣]/.test(first)) add(tk.map[0] + 1, 'A', 'indent-code');
    }
    if (tk.type === 'paragraph_open' && tk.map) {   // 1 이 아닌 번호가 문단 안에 — 목록이 되지 않고 윗줄의 글이 된다
      for (let i = tk.map[0] + 1; i < tk.map[1]; i++) {
        const it = itemOf(lines[i]);
        if (!it?.ordered || it.num === 1 || it.num > 99 || /^\d/.test(it.text) || !it.text.trim() || inCode(i + 1)) continue;   // '2024. 3. 5.' 같은 날짜는 아니다
        const n = i + 1;
        const expect = lines[i];
        const nested = listDepth > 0;
        add(n, 'A', 'list-glued', { n: it.num }, nested
          ? { kind: 'renumber', apply: guarded(n, expect, (l) => renumberFrom(l, n, 1).lines) }
          : { kind: 'blank-before', apply: guarded(n, expect, (l) => insertAt(l, n, [blankLike(l[n - 1])])) });
        break;
      }
    }
    if (tk.type === 'heading_open' && tk.markup === '-' && tk.map) {   // 글 바로 아래의 --- — 가로줄이 아니라 제목 2
      const n = tk.map[1];
      if (!inCode(n) && /^\s*(?:>\s*)*\s*-{3,}\s*$/.test(lines[n - 1] ?? '')) {
        const expect = lines[n - 1];
        add(n, 'A', 'setext', {}, { kind: 'blank-before', apply: guarded(n, expect, (l) => insertAt(l, n, [blankLike(l[n - 1])])) });
      }
    }
  }
  // 한 목록에 다른 글머리표·번호 구분 글자 — 목록이 둘로 갈린다
  for (let n = 1; n <= lines.length; n++) {
    const it = itemOf(lines[n - 1]);
    if (!it || inCode(n)) continue;
    let m = 0;
    for (let k = n - 1; k >= 1; k--) {
      const s = lines[k - 1];
      if (isBlank(s)) continue;
      if (depthOf(s) !== depthOf(lines[n - 1])) break;
      const x = itemOf(s);
      if (x && x.width <= it.width) {
        if (x.width === it.width) m = k;
        break;
      }
      if (!x && widthOf(s) <= it.width) break;   // 사이에 목록 밖의 글
    }
    if (!m) continue;
    const prev = itemOf(lines[m - 1]);
    const [, end] = itemSpan(lines, m) ?? [m, m];
    if (lines.slice(end, n - 1).some((s) => !isBlank(s))) continue;
    const mixed = prev.ordered === it.ordered && (it.ordered ? prev.delim !== it.delim : prev.marker !== it.marker);
    if (!mixed) continue;
    const from = it.ordered ? it.delim : it.marker;
    const to = prev.ordered ? prev.delim : prev.marker;
    const expect = lines[n - 1];
    add(n, 'A', 'bullet-mixed', { a: it.ordered ? `1${to}` : to, b: it.ordered ? `1${from}` : from }, {
      kind: 'same-marker',
      apply: guarded(n, expect, (l) => {
        const next = l.slice();
        for (let s = n; s;) {
          const x = itemOf(next[s - 1]);
          next[s - 1] = `${x.quote}${x.lead}${x.ordered ? `${x.num}${to}` : to}${next[s - 1].slice(x.quote.length + x.lead.length + x.marker.length)}`;
          const [, e] = itemSpan(next, s) ?? [s, s];
          let q = e + 1;
          while (q <= next.length && isBlank(next[q - 1])) q += 1;
          const y = itemOf(next[q - 1] ?? '');
          s = y && y.width === it.width && depthOf(next[q - 1]) === depthOf(next[n - 1]) && (y.ordered ? y.delim === from : y.marker === from) && y.ordered === it.ordered ? q : 0;
        }
        return next;
      }),
    });
  }
  // 강조글 종류 — 모르는 종류는 일반 인용으로 보인다
  lines.forEach((s, i) => {
    const m = /^\s*\[!([A-Za-z]+)\]/.exec(bodyOf(s));
    if (!m || !depthOf(s) || inCode(i + 1) || (i && depthOf(lines[i - 1]) >= depthOf(s))) return;
    const word = m[1].toUpperCase();
    if (KINDS.includes(word)) return;
    const near = KINDS.find((k) => k.startsWith(word) || word.startsWith(k)) ?? KINDS.find((k) => distance(k, word) <= 2);
    const expect = s;
    add(i + 1, 'A', 'callout-kind', { kind: m[1], to: near ?? '' }, near
      ? { kind: 'callout', apply: guarded(i + 1, expect, (l) => l.map((x, j) => (j === i ? x.replace(`[!${m[1]}]`, `[!${near}]`) : x))) }
      : null);
  });
  // 각주 — 내용(정의)이 없는 표시는 글자로 남고, 쓰지 않는 내용은 보이지 않는다
  const defs = new Map();
  const refs = new Map();
  lines.forEach((s, i) => {
    if (inCode(i + 1) || i < front) return;
    const d = /^\s*(?:>\s*)*\[\^([^\]\s]+)\]:/.exec(s);
    if (d && !defs.has(d[1])) defs.set(d[1], i + 1);
    for (const r of s.replace(/`[^`]*`/g, '').matchAll(/\[\^([^\]\s]+)\](?!:)/g)) if (!refs.has(r[1])) refs.set(r[1], i + 1);
  });
  for (const [id, n] of refs) if (!defs.has(id)) add(n, 'A', 'note-missing', { id });
  for (const [id, n] of defs) if (!refs.has(id)) add(n, 'A', 'note-unused', { id });
  // 문서 안의 절·캡션 링크 — 가리키는 곳이 없다
  const ids = new Set(refTargets(lines, slug).map((x) => /\(#([^)]+)\)$/.exec(x.text)?.[1]).filter(Boolean));
  for (const c of captionsIn(lines)) ids.add(captionId(c.word, c.n));
  for (const s of lines) for (const m of s.matchAll(/\bid=["']([^"']+)["']/g)) ids.add(m[1]);   // 문서에 직접 쓴 HTML 의 id
  const plain = (id) => {
    try {
      return decodeURIComponent(id);
    } catch {
      return id;
    }
  };
  lines.forEach((s, i) => {
    if (inCode(i + 1) || i < front || !s.includes('](#')) return;
    for (const m of s.replace(/`[^`]*`/g, '').matchAll(/\]\(#([^)\s]+)\)/g)) {
      const id = plain(m[1]);
      if (!ids.has(id) && !ids.has(m[1]) && !/^fn(?:ref)?\d/.test(id)) add(i + 1, 'A', 'link-anchor', { id });
    }
  });

  // ---- B. 보고서의 틀 ---------------------------------------------------------------------------
  const heads = [];
  toks.forEach((tk, k) => {
    if (tk.type === 'heading_open' && tk.map && tk.level === 0) heads.push({ line: tk.map[0] + 1, level: Number(tk.tag[1]), text: toks[k + 1]?.content?.trim() ?? '', k });
  });
  let prevLevel = 0;
  for (const h of heads) {   // 제목 수준 건너뜀
    if (prevLevel && h.level > prevLevel + 1) add(h.line, 'B', 'head-skip', { a: '#'.repeat(prevLevel), b: '#'.repeat(h.level) });
    prevLevel = h.level;
  }
  heads.filter((h) => h.level === 1).slice(1).forEach((h) => add(h.line, 'B', 'head-title'));
  const tops = toks.filter((tk) => tk.level === 0 && tk.nesting >= 0 && tk.block && tk.map && !/_close$/.test(tk.type));
  heads.forEach((h) => {   // 글이 없는 절 — 다음 블록이 같거나 높은 제목, 또는 문서 끝
    const i = tops.findIndex((tk) => tk.map[0] + 1 === h.line && tk.type === 'heading_open');
    const nextTk = tops[i + 1];
    const nextLevel = nextTk?.type === 'heading_open' ? Number(nextTk.tag[1]) : 0;
    if (!emptyOk && (!nextTk || (nextLevel && nextLevel <= h.level))) add(h.line, 'B', 'head-empty');
  });
  const seen = new Map();
  for (const h of heads) {   // 같은 제목 — 절 링크가 앞 절로 간다
    const key = h.text.replace(/\s+/g, ' ');
    if (!key) continue;
    if (seen.has(key)) add(h.line, 'B', 'head-same', { line: seen.get(key) });
    else seen.set(key, h.line);
  }
  const renumbered = numbersOnly(lines, slug);   // 제목 번호 — 번호가 있는 제목의 번호가 이 문서의 차례와 어긋남
  if (renumbered) {
    const n = renumbered.findIndex((s, i) => s !== lines[i]) + 1;
    add(n, 'B', 'head-number', {}, { kind: 'heading-numbers', apply: guarded(n, lines[n - 1], (l) => numbersOnly(l, slug)) });
  }
  const caps = captionsIn(lines);
  for (const word of CAPTION_WORDS) {   // 캡션 번호의 차례
    const list = caps.filter((c) => c.word === word);
    const bad = list.findIndex((c, i) => c.n !== i + 1);
    if (bad < 0) continue;
    const c = list[bad];
    const fixed = orderCaptions(lines, word);
    add(c.line, 'B', 'caption-order', { word, a: bad ? list[bad - 1].n : 0, b: c.n }, fixed
      ? { kind: 'caption-numbers', apply: guarded(c.line, lines[c.line - 1], (l) => orderCaptions(l, word)) }
      : null);
  }
  // 캡션·'자료:' 줄이 없는 표·그림 — 이 문서가 다른 표·그림에는 쓰는 것만 (쓰지 않는 문서는 그대로)
  const exhibits = [];
  for (const blk of blocks) {
    const tb = tableIn(lines, blk);
    if (tb) exhibits.push({ kind: 'table', a: tb.head, b: blk.b });
  }
  lines.forEach((s, i) => {
    if (!inCode(i + 1) && i >= front && IMAGE_ONLY.test(s) && !depthOf(s) && !leadOf(s)) exhibits.push({ kind: 'figure', a: i + 1, b: i + 1 });
  });
  for (const f of fences) {
    const info = /^[ \t]*(?:`{3,}|~{3,})\s*(\S*)/.exec(bodyOf(lines[f.a - 1]))?.[1] ?? '';
    if (f.closed && CHART_LANGS.test(info) && !depthOf(lines[f.a - 1]) && !leadOf(lines[f.a - 1])) exhibits.push({ kind: 'figure', a: f.a, b: f.b });
  }
  exhibits.sort((x, y) => x.a - y.a);
  const near = (from, dir) => {   // 위(-1)·아래(1)의 첫 글 줄
    let n = from + dir;
    while (n >= 1 && n <= lines.length && isBlank(lines[n - 1])) n += dir;
    return n >= 1 && n <= lines.length ? n : 0;
  };
  const starts = new Set(exhibits.map((e) => e.a));
  for (const x of exhibits) {
    const words = x.kind === 'table' ? TABLE_WORDS : FIGURE_WORDS;
    const above = near(x.a, -1);
    const below = near(x.b, 1);
    const capped = (n) => !!n && words.has(captionAt(lines[n - 1])?.word);
    // 표의 캡션은 위 (D184). 그림은 아래 캡션도 — 그 캡션 바로 아래가 다른 표·그림이면 그것의 캡션이다
    x.caption = capped(above) ? above : x.kind === 'figure' && capped(below) && !starts.has(near(below, 1)) ? below : 0;
    const after = x.caption && x.caption > x.b ? near(x.caption, 1) : below;
    x.source = after && SOURCE.test(lines[after - 1]) ? after : 0;
  }
  const most = (list, has) => list.filter(has).length * 2 > list.length;   // 절반 넘게 — 그 문서의 양식으로 본다 (문법을 보여 주는 안내 문서의 표까지 걸지 않게)
  for (const kind of ['table', 'figure']) {
    const words = kind === 'table' ? TABLE_WORDS : FIGURE_WORDS;
    const used = caps.find((c) => words.has(c.word));
    const list = exhibits.filter((x) => x.kind === kind);
    if (used && most(list, (e) => e.caption)) {
      for (const x of list.filter((e) => !e.caption)) {
        const word = used.word;
        const expect = lines[x.a - 1];
        add(x.a, 'B', 'caption-missing', { kind }, {
          kind: 'caption',
          apply: guarded(x.a, expect, (l) => {
            const add2 = [`${word} 0.`, ''];
            if (x.a > 1 && !isBlank(l[x.a - 2])) add2.unshift('');
            const next = insertAt(l, x.a, add2);
            return orderCaptions(next, word) ?? next;
          }),
        });
      }
    }
    const sourced = exhibits.find((e) => e.source);
    if (sourced && most(exhibits, (e) => e.source)) {
      const prefix = /^[\s※*·•\-]*[(\[]?\s*[^:：]*[:：]\s?/.exec(lines[sourced.source - 1])[0].replace(/^\s+/, '');
      for (const x of list.filter((e) => !e.source)) {
        const end = x.caption > x.b ? x.caption : x.b;
        const expect = lines[x.a - 1];
        add(x.a, 'B', 'source-missing', { kind }, {
          kind: 'source',
          apply: guarded(x.a, expect, (l) => insertAt(l, end + 1, ['', prefix.endsWith(' ') ? prefix : `${prefix} `, ...(end < l.length && !isBlank(l[end]) ? [''] : [])])),
        });
      }
    }
  }
  // 한 목록 안에서 일부만 빈 줄로 띄움 — 목록 전체가 띄운 목록이 된다
  const listed = new Set();
  for (let n = 1; n <= lines.length; n++) {
    if (!itemOf(lines[n - 1]) || inCode(n) || listed.has(n)) continue;
    const sib = siblingsOf(lines, n);
    sib.forEach((s) => listed.add(s));
    if (sib.length < 3) continue;
    const gaps = sib.slice(1).map((s, i) => {
      const [, e] = itemSpan(lines, sib[i]) ?? [sib[i], sib[i]];
      return lines.slice(e, s - 1).some(isBlank);
    });
    const loose = gaps.filter(Boolean).length;
    if (loose && loose * 2 <= gaps.length) add(sib[0], 'B', 'list-loose-mixed');   // 띄운 사이가 대부분이면 일부러 띄운 목록이다 — 몇 곳만 띄웠을 때
  }

  // ---- C. 글버릇 (기본 끔) ---------------------------------------------------------------------
  if (style) {
    let inList = 0;
    toks.forEach((tk, k) => {
      if (tk.type === 'list_item_open') inList += 1;
      else if (tk.type === 'list_item_close') inList -= 1;
      if (tk.type !== 'paragraph_open' || !tk.map) return;
      const text = (toks[k + 1]?.content ?? '').replace(/\s+/g, ' ');
      if (!inList && text.length > LIMITS.paragraph) add(tk.map[0] + 1, 'C', 'long-para', { n: text.length });
      const longest = Math.max(0, ...text.split(/(?<=[.!?。])\s+/).map((x) => x.length));
      if (longest > LIMITS.sentence) add(tk.map[0] + 1, 'C', 'long-sentence', { n: longest });
    });
    for (const blk of blocks) {
      const tb = tableIn(lines, blk);
      if (!tb) continue;
      for (let n = tb.first; n <= tb.last; n++) {
        const long = Math.max(0, ...cellsOf(lines[n - 1]).map((c) => c.length));
        if (long > LIMITS.cell) add(n, 'C', 'long-cell', { n: long });
      }
    }
    lines.forEach((s, i) => {
      const n = i + 1;
      if (inCode(n) || i < front) return;
      if (/\S {2,}$/.test(s) && !isBlank(lines[i + 1] ?? '')) add(n, 'C', 'hard-break', {}, { kind: 'trim', apply: guarded(n, s, (l) => l.map((x, j) => (j === i ? x.replace(/ +$/, '') : x))) });
      if (/^\t/.test(bodyOf(s)) && s.trim()) {
        add(n, 'C', 'tab-indent', {}, {
          kind: 'spaces',
          apply: guarded(n, s, (l) => l.map((x, j) => {
            if (j !== i) return x;
            const q = quoteOf(x);
            const lead = /^[ \t]*/.exec(x.slice(q.length))[0];
            let w = 0;
            for (const c of lead) w += c === '\t' ? 4 - (w % 4) : 1;
            return q + ' '.repeat(w) + x.slice(q.length + lead.length);
          })),
        });
      }
    });
    for (const h of heads) {
      const m = /[.:：]$/.exec(h.text);
      if (!m || /^[\d.]+$/.test(h.text) || /\.\.$/.test(h.text)) continue;
      const expect = lines[h.line - 1];
      add(h.line, 'C', 'head-punct', { c: m[0] }, { kind: 'trim', apply: guarded(h.line, expect, (l) => l.map((x, j) => (j === h.line - 1 ? x.replace(/[.:：](\s*#*\s*)$/, '$1').replace(/\s+$/, '') : x))) });
    }
  }
  return out.sort((x, y) => x.line - y.line);
}

const widthOf = (s) => {
  let w = 0;
  for (const c of leadOf(s)) w += c === '\t' ? 4 - (w % 4) : 1;
  return w;
};
