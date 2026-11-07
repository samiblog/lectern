// 참조와 캡션의 계산 (D121, DOM 없음): 캡션 번호 다시 매기기, 상호 참조 링크, 문서 안 목차 줄, 쪽 나눔 줄, 본문 인용.
// 원문 줄 배열을 받아 계산만 한다 — 저장은 lineedit.js 가 commit 으로, 그리기는 doc.js 가. 표 점검은 tools/edges/refs_cases.js.
//
// - 캡션은 '표 1. 제목' '그림 2: 제목' '**표 3.** 제목' '<표 4> 제목' 처럼 낱말·번호·구분 글자로 시작하는 줄이다. '표 2-1'·'표 2.1' 처럼
//   장 번호가 든 것은 사람이 매긴 것이라 손대지 않는다.
// - 번호는 그 낱말의 캡션이 1, 2, 3… 차례대로였던 문서에서만, 캡션이 더해지거나 빠지거나 차례가 바뀐 저장에서만 다시 맞춘다 —
//   사람이 한 캡션의 번호만 고친 것은 그대로 둔다.
// - 상호 참조는 '[표 3](#표-3)' 꼴의 링크다. 번호가 바뀌면 글자와 주소를 함께 고친다. 링크가 아닌 '표 3' 글자는 고치지 않고 센다.

import { fencesOf, fenceAt, frontEnd, notesStart } from './lineops.js';
import { headsOf, bareText } from './docops.js';

/** 캡션의 낱말 — 한국어와 영어. 낱말마다 번호를 따로 센다 */
export const CAPTION_WORDS = ['표', '그림', 'Table', 'Figure'];   // i18n-ok (원문의 캡션 낱말)

// 앞: 공백·굵게·꺾쇠, 낱말, 공백, 번호, 뒤: '.'(소수점이 아닌)·':'·닫는 꺾쇠·굵게
const CAPTION = /^(\s*(?:\*\*)?[〈<]?)(표|그림|Table|Figure)([ \t]*)(\d{1,4})(?=\.(?!\d)|:|[〉>]|\*\*)/;

/** 캡션 꼬리표의 id (doc.js 가 캡션 단락에 단다) — '표-3', 'table-3' */
export const captionId = (word, n) => `${word.toLowerCase()}-${n}`;

/** 상호 참조 링크 — '[표 3](#표-3)' */
export const refLink = (word, n) => `[${word} ${n}](#${captionId(word, n)})`;

const REF = /\[(표|그림|Table|Figure) (\d{1,4})\]\(#(표|그림|table|figure)-(\d{1,4})\)/g;

/** 줄 하나가 캡션이면 {word, n, title}. 아니면 null */
export function captionAt(line) {
  const m = CAPTION.exec(line);
  if (!m) return null;
  const title = line.slice(m[0].length).replace(/^(?:\.|:|[〉>])?(?:\*\*)?[.:]?\s*/, '').trim();
  return { word: m[2], n: Number(m[4]), title };
}

/** 문서의 캡션 [{line, word, n, title}] — 코드 울타리·머리 설정 안은 빼고 */
export function captionsIn(lines) {
  const fences = fencesOf(lines);
  const start = frontEnd(lines);
  const out = [];
  lines.forEach((s, i) => {
    const line = i + 1;
    if (line <= start || fenceAt(fences, line)) return;
    const c = captionAt(s);
    if (c) out.push({ line, ...c });
  });
  return out;
}

const inOrder = (nums) => nums.every((n, i) => n === i + 1);
const ascending = (nums) => nums.every((n, i) => !i || n > nums[i - 1]);

/**
 * 캡션 번호를 다시 맞춘다 (old: 저장 전, next: 저장할 줄). {lines, changed: 바뀐 번호 수, plain: 고치지 않은 '표 3' 글자 수, dangling: 없는 번호를 가리키는 참조 수}.
 * 낱말마다: old 의 번호가 1, 2, 3… 이었고, next 에서 캡션 수가 달라졌거나 차례가 흐트러졌을 때만
 */
export function renumberCaptions(old, next) {
  const before = captionsIn(old);
  const after = captionsIn(next);
  const maps = new Map();   // 낱말 → Map(옛 번호 → 새 번호)
  for (const word of CAPTION_WORDS) {
    const was = before.filter((c) => c.word === word).map((c) => c.n);
    const now = after.filter((c) => c.word === word);
    if (!now.length || !inOrder(was)) continue;
    const nums = now.map((c) => c.n);
    if (nums.length === was.length && ascending(nums)) continue;   // 더하거나 빼거나 옮긴 것이 아니다 — 사람이 고친 번호는 그대로
    const map = new Map();
    now.forEach((c, i) => {
      if (!map.has(c.n)) map.set(c.n, i + 1);
    });
    maps.set(word, { map, caps: now });
  }
  const out = next.slice();
  let changed = 0;
  for (const { caps } of maps.values()) {
    caps.forEach((c, i) => {
      if (c.n === i + 1) return;
      out[c.line - 1] = out[c.line - 1].replace(CAPTION, (all, head, word, gap) => `${head}${word}${gap}${i + 1}`);
      changed += 1;
    });
  }
  if (!maps.size) return { lines: next, changed: 0, plain: 0, dangling: 0 };
  const fences = fencesOf(out);
  const capLines = new Set([...maps.values()].flatMap(({ caps }) => caps.map((c) => c.line)));
  let plain = 0;
  let dangling = 0;
  out.forEach((s, i) => {
    if (fenceAt(fences, i + 1) || capLines.has(i + 1)) return;
    const fixed = s.replace(REF, (all, word, n, idWord, idN) => {
      const m = maps.get(word);
      if (!m || idWord !== word.toLowerCase() || idN !== n) return all;
      const to = m.map.get(Number(n));
      if (to == null) {
        dangling += 1;
        return all;
      }
      return to === Number(n) ? all : refLink(word, to);
    });
    if (fixed !== s) out[i] = fixed;
    // 링크가 아닌 '표 3' 글자: 번호가 바뀐 것만 센다 (다른 문서의 표일 수 있어 고치지 않는다)
    const bare = fixed.replace(REF, '');
    for (const [word, m] of maps) {
      for (const hit of bare.matchAll(new RegExp(`(?:^|[^\\p{L}])${word}\\s?(\\d{1,4})(?!\\d)`, 'gu'))) {
        const to = m.map.get(Number(hit[1]));
        if (to != null && to !== Number(hit[1])) plain += 1;
      }
    }
  });
  return { lines: out, changed, plain, dangling };
}

/**
 * 상호 참조로 고를 것 [{kind: 'caption'|'section', word?, n?, line, name, text(넣을 링크)}] — 캡션과 제목.
 * slug: 제목 글 → 앵커 id (markdown.js 의 slugify). 같은 이름의 제목은 markdown-it-anchor 처럼 -1, -2 를 붙인다
 */
export function refTargets(lines, slug) {
  const out = [];
  for (const c of captionsIn(lines)) {
    out.push({ kind: 'caption', word: c.word, n: c.n, line: c.line, name: `${c.word} ${c.n}${c.title ? `. ${c.title}` : ''}`, text: refLink(c.word, c.n) });
  }
  const seen = new Map();
  for (const h of headsOf(lines)) {
    const text = plainOf(bareText(lines[h.n - 1]));
    if (!text) continue;
    const base = slug(text);
    const k = seen.get(base) ?? 0;
    seen.set(base, k + 1);
    const id = k ? `${base}-${k}` : base;
    out.push({ kind: 'section', line: h.n, level: h.level, name: text, text: `[${text}](#${id})` });
  }
  return out.sort((a, b) => a.line - b.line);
}

// ---- 문서 안의 목차·쪽 나눔 ---------------------------------------------------------------

/** @type {[RegExp, string][]} */
const TOC_LINES = [
  [/^\[(?:목차|toc)\]$/i, 'toc'],
  [/^\[(?:표 목차|list of tables)\]$/i, 'tables'],
  [/^\[(?:그림 목차|list of figures)\]$/i, 'figures'],
];

/** 목차 줄이면 'toc'·'tables'·'figures'. 아니면 null — '[목차]' 한 줄이 그 자리에 목차로 그려진다 */
export function tocKind(line) {
  const s = line.trim();
  return TOC_LINES.find(([re]) => re.test(s))?.[1] ?? null;
}

/** 목차 줄의 글 — 화면 언어에 맞춰 넣는다 */
export const tocLine = (kind, en = false) => ({
  toc: en ? '[TOC]' : '[목차]', tables: en ? '[List of Tables]' : '[표 목차]', figures: en ? '[List of Figures]' : '[그림 목차]',   // i18n-ok (원문 표시)
}[kind]);

/** 쪽 나눔 줄 — 다른 뷰어에서는 보이지 않고, PDF 로 내보내는 도구 대부분이 쪽을 바꾼다 */
export const PAGE_BREAK = '<div style="page-break-after: always;"></div>';
const PAGE_BREAK_RE = /^<div\s+style\s*=\s*["']\s*(?:page-break-after\s*:\s*always|break-after\s*:\s*page)\s*;?\s*["']\s*>\s*<\/div>\s*$/i;

export const isPageBreak = (line) => PAGE_BREAK_RE.test(line.trim());

// ---- 본문 인용 ---------------------------------------------------------------------

const REFS_HEAD = /^(?:\d+[.)]?\s*|[IVX]+\.\s*)?(?:참고\s*문헌|참고\s*자료|인용\s*문헌|references|bibliography|works cited)\s*$/i;

/** 참고문헌 절의 문헌 [{line, text}] — 그 절의 목록 항목과 글 줄. 절이 없으면 [] */
export function referencesIn(lines) {
  const heads = headsOf(lines);
  const at = heads.find((h) => REFS_HEAD.test(bareText(lines[h.n - 1])));
  if (!at) return [];
  const next = heads.find((h) => h.n > at.n && h.level <= at.level);
  const notes = notesStart(lines);
  const end = next ? next.n - 1 : notes > at.n ? notes - 1 : lines.length;
  const fences = fencesOf(lines);
  const out = [];
  for (let n = at.n + 1; n <= end; n++) {
    const s = lines[n - 1];
    if (!s.trim() || fenceAt(fences, n) || /^#{1,6}\s/.test(s) || /^\s{2,}\S/.test(s) && out.length && !/^\s*(?:[-*+]|\d+[.)])\s/.test(s)) continue;
    const text = s.replace(/^\s*(?:[-*+]|\d+[.)]|\[\d+\])\s+/, '').trim();
    if (text) out.push({ line: n, text });
  }
  return out;
}

const plainOf = (s) => s.replace(/\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/[*_`]/g, '').trim();

/**
 * 문헌 한 줄 → 본문 인용 {cite: '(김영삼, 2026)', author, year}. 'Kim, Y., & Lee, S. (2024). …' → '(Kim & Lee, 2024)',
 * 저자가 셋 이상이면 '외'·'et al.'. 연도가 없으면 cite 는 '(첫 낱말)' 이고 year 는 ''
 */
export function citeOf(entry) {
  const s = plainOf(entry);
  const year = /\((\d{4}[a-z]?|n\.d\.)\)/.exec(s)?.[1] ?? /(?:^|[^\d])(\d{4}[a-z]?)(?!\d)/.exec(s)?.[1] ?? '';
  const cut = year ? s.indexOf(year) : -1;
  let who = (cut > 0 ? s.slice(0, cut) : s.split(/[.(]/)[0]).replace(/[\s(,.]+$/, '').trim();
  const etal = /(?:\bet al\.?|\s외)$/.test(who);   // i18n-ok (인용 표기)
  who = who.replace(/,?\s*(?:\bet al\.?|외)$/, '').replace(/[\s,.]+$/, '').trim();   // i18n-ok (인용 표기)
  const korean = /[가-힣]/.test(who);
  // 한국어는 '·' ',' '와' 로, 영어는 '&' 'and' 와 'Kim, Y., Lee, S.' 의 이름 사이 쉼표로 저자를 나눈다
  const parts = who.split(korean ? /\s*[·,]\s*|\s+(?:와|과|및)\s+/ : /\s*(?:&|\band\b)\s*|,\s+(?=[A-Z][^,]*,\s*[A-Z]\.)/).map((x) => x.replace(/,\s*$/, '').trim()).filter(Boolean);   // i18n-ok (인용 표기)
  // 영어 'Kim, Y.' 는 쉼표 앞의 성, 쉼표가 없으면(기관 이름) 그대로
  const surname = (x) => (!korean && x.includes(',') ? x.split(',')[0].trim() : x);
  const many = etal || parts.length > 2;
  const names = parts.map(surname).filter(Boolean);
  if (!names.length) names.push(who.split(/\s+/)[0] || s.split(/\s+/)[0] || '?');
  who = many ? `${names[0]}${korean ? ' 외' : ' et al.'}` : names.length === 2 ? `${names[0]}${korean ? '·' : ' & '}${names[1]}` : names[0];   // i18n-ok (인용 표기)
  return { cite: year ? `(${who}, ${year})` : `(${who})`, author: names[0], year };
}

/** 문헌이 본문(참고문헌 절 밖)에 몇 번 인용됐는지 — 저자와 연도가 한 괄호 안에 든 곳 */
export function citedCount(lines, entry) {
  const { author, year } = citeOf(entry);
  if (!author || !year) return 0;
  const skip = new Set(referencesIn(lines).map((r) => r.line));
  const literal = (x) => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(`\\([^()]*${literal(author)}[^()]*${literal(year)}[^()]*\\)`, 'g');
  let n = 0;
  lines.forEach((s, i) => {
    if (!skip.has(i + 1)) n += s.match(re)?.length ?? 0;
  });
  return n;
}
