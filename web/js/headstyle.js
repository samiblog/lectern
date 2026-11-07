// md 문서 스타일 (D103)의 계산 (DOM 없음): 머리글의 번호·기호를 읽고 md 원문에서 바꾼다. 저장은 lineedit.js 가 한다.
// 문서 방식(서술식·개조식)은 본문을 쓰는 법이고 머리글 모양은 그와 따로다. 논문은 서술식이어도 번호를 쓴다.
// 앱이 바꾸는 것은 머리글뿐이다. 본문을 바꾸는 일은 판단이 들어서 Claude 에게 요청한다.
// 문서 제목(# 하나)은 번호를 달지 않는다. 코드 블록과 맨 앞 설정 안은 머리글이 아니다.
// 머리글 모양은 단계마다 틀 글자다: {1} 숫자, {I} 로마 숫자, {가} 한글, {①} 동그라미 숫자, {path} 1.1.1 — 나머지는 그대로 쓴다.

const ROMAN = ['Ⅰ', 'Ⅱ', 'Ⅲ', 'Ⅳ', 'Ⅴ', 'Ⅵ', 'Ⅶ', 'Ⅷ', 'Ⅸ', 'Ⅹ', 'Ⅺ', 'Ⅻ'];
const HANGUL = '가나다라마바사아자차카타파하';   // i18n-ok (번호 글자)
const CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳';
const ANY_ROMAN = `[${ROMAN.join('')}]`;
const SYMBOL = '□■◆◇○●◦▪•·※▶▷-';   // i18n-ok (기호)
const TOKEN = /(\{1\}|\{I\}|\{가\}|\{①\}|\{path\})/;
const escape = (s) => s.replace(/[.*+?^${}()|[\]\\/-]/g, '\\$&');
const FIND = { '{1}': '\\d+', '{I}': `${ANY_ROMAN}+`, '{가}': '[가-힣]', '{①}': '[①-⑳]', '{path}': '\\d+(?:\\.\\d+)+\\.?' };   // i18n-ok (번호 글자)
const MAKE = {
  '{1}': (c, d) => String(c[d]),
  '{I}': (c, d) => ROMAN[c[d] - 1] ?? String(c[d]),
  '{가}': (c, d) => HANGUL[c[d] - 1] ?? String(c[d]),   // i18n-ok (번호 글자)
  '{①}': (c, d) => CIRCLED[c[d] - 1] ?? String(c[d]),
  '{path}': (c, d) => c.slice(0, d + 1).join('.'),
};

/** 문서 방식마다 고를 수 있는 기본 머리글 모양 */
export const STYLES = { prose: ['plain', 'paper', 'number', 'chapter', 'rule'], outline: ['report', 'number', 'symbol', 'plain'] };

/** 기본 머리글 모양: id → 단계마다 틀 글자. plain 은 번호 없음 */
const BASE = {
  plain: [],
  paper: ['{I}.', '{1}.', '{1})', '({1})', '{①}', '{가}.'],   // i18n-ok (번호 글자)
  chapter: ['제{1}장', '제{1}절', '{1}.', '{가}.', '{1})', '{가})'],   // i18n-ok (번호 글자)
  rule: ['제{1}장', '제{1}조', '{①}', '{1}.', '{가}.', '{가})'],   // i18n-ok (번호 글자)
  report: ['{I}.', '{1}.', '{가}.', '{1})', '{가})', '({1})'],   // i18n-ok (번호 글자)
  number: ['{1}.', '{path}', '{path}', '{path}', '{path}', '{path}'],
  symbol: ['□', '○', '-', '·', '·', '·'],
};
let own = {};   // 내 스타일: id → 틀 글자들

/** 내 스타일을 알린다 (서버의 md-styles — mdstyle.js) */
export function setOwnStyles(list) {
  own = Object.fromEntries(list.map((x) => [`own:${x.name}`, x.marks]));
}

const marksOf = (id) => BASE[id] ?? own[id] ?? [];
const allIds = () => [...Object.keys(BASE), ...Object.keys(own)];
const patternOf = (mark) => (mark ? new RegExp(`^${mark.split(TOKEN).map((p) => FIND[p] ?? escape(p)).join('')}\\s`) : null);
const makeMark = (mark, counts, depth) => (mark ? mark.split(TOKEN).map((p) => MAKE[p]?.(counts, depth) ?? p).join('') : '');

// 어느 모양이든 번호가 틀림없는 것. 1.1 처럼 소수로도 읽히는 것과 - 는 그 모양의 문서에서만 뗀다
const SURE = new RegExp(`^(?:제\\d+[장절편조항]|${ANY_ROMAN}+\\.|\\d+\\.|[가-힣]\\.|\\d+\\)|[가-힣]\\)|\\(\\d+\\)|[①-⑳]|[□■◆◇○●◦▪•·※▶▷])\\s+`);   // i18n-ok (번호 글자)
const HEAD = /^( {0,3})(#{1,6})([ \t]+)(.*?)(?:[ \t]+#+)?[ \t]*$/;

function fenced(lines) {
  let open = '';
  return lines.map((s) => {
    const f = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(s);
    if (open) {
      if (f && f[1][0] === open[0] && f[1].length >= open.length && !f[2].trim()) open = '';
      return true;
    }
    if (f && !(f[1][0] === '`' && f[2].includes('`'))) open = f[1];
    return !!open;
  });
}

const frontEnd = (lines) => (lines[0]?.trim() === '---' ? lines.findIndex((s, n) => n > 0 && s.trim() === '---') + 1 : 0);

/** 머리글들 [{line(0부터), mark('##'), level, text, depth(번호 단계, 문서 제목은 0)}] */
export function headings(lines) {
  const code = fenced(lines);
  const start = frontEnd(lines);
  const out = [];
  lines.forEach((s, i) => {
    const m = i >= start && !code[i] ? HEAD.exec(s) : null;
    if (m && m[4]) out.push({ line: i, pad: m[1], mark: m[2], gap: m[3], level: m[2].length, text: m[4], depth: 0 });
  });
  const titled = out.filter((h) => h.level === 1).length === 1 && out[0]?.level === 1;
  const body = titled ? out.slice(1) : out;
  const top = Math.min(...body.map((h) => h.level));
  for (const h of body) h.depth = Math.min(6, h.level - top + 1);
  return out;
}

// 번호를 달지 않는 절 (맨 바깥 수준만): 앞뒤에 붙는 것들. 논문·보고서에서 번호 없이 쓴다 (D107)
const NO_NUMBER = /^(?:참고\s*문헌|부록|붙임|별첨|첨부|요약|초록|목차|감사의\s*글|references|bibliography|appendix|abstract|summary|acknowledge?ments)(?:\s|$)/i;   // i18n-ok (절 이름)
const counted = (h) => !(h.depth === 1 && NO_NUMBER.test(h.text));

/** 지금 문서의 머리글 모양 id. 번호가 달린 머리글이 열에 여섯이 넘으면 그 모양이다. 똑같이 맞으면 문서 방식 kind 의 모양을 먼저 본다 */
export function detect(lines, kind = '') {
  const body = headings(lines).filter((h) => h.depth && counted(h));
  let best = 'plain';
  let most = 0;
  for (const id of [...(STYLES[kind] ?? []), ...allIds()]) {
    const marks = marksOf(id);
    if (!marks.length) continue;
    const hits = body.filter((h) => patternOf(marks[h.depth - 1])?.test(`${h.text} `)).length;
    if (hits > most && hits >= body.length * 0.6) {
      best = id;
      most = hits;
    }
  }
  return best;
}

/**
 * 지금 문서 방식: 'prose' | 'outline'. 본문으로 본다 — 목록 줄이 문단 줄보다 많으면 개조식이다.
 * 본문이 거의 없으면 머리글로 본다. 코드·표·머리글·주석은 세지 않는다.
 */
export function kindOf(lines) {
  const code = fenced(lines);
  const heads = new Set(headings(lines).map((h) => h.line));
  const start = frontEnd(lines);
  let items = 0;
  let plain = 0;
  lines.forEach((s, i) => {
    const x = s.trim();
    if (i < start || code[i] || heads.has(i) || !x || /^(?:\||<!--|---|```|~~~)/.test(x)) return;
    if (/^(?:[-*+]|\d+[.)]|[□■○●·])\s/.test(x)) items += 1;
    else plain += 1;
  });
  if (items + plain >= 3) return items > plain ? 'outline' : 'prose';
  return ['report', 'symbol'].includes(detect(lines)) ? 'outline' : 'prose';
}

/** 번호를 뗀 글. current: 지금 문서의 모양 */
function bare(text, current) {
  const own1 = marksOf(current).map(patternOf).find((re) => re?.test(`${text} `));
  const m = own1?.exec(`${text} `);
  const off = m ? text.slice(m[0].length).trimStart() : text;
  return off.replace(SURE, '') || text;
}

/** 모양 id 를 입힌 머리글들 — 문서 제목은 그대로 */
function dressed(lines, id) {
  const current = detect(lines);
  const marks = marksOf(id);
  const counts = [0, 0, 0, 0, 0, 0];
  return headings(lines).filter((h) => h.depth).map((h) => {
    const text = bare(h.text, current);
    if (!counted({ ...h, text })) return { ...h, old: h.text, text };   // 참고문헌·부록 같은 절은 번호를 달지 않고 세지도 않는다
    counts[h.depth - 1] += 1;
    counts.fill(0, h.depth);
    for (let d = 0; d < h.depth - 1; d++) counts[d] ||= 1;
    const mark = makeMark(marks[h.depth - 1], counts, h.depth - 1);
    return { ...h, old: h.text, text: mark ? `${mark} ${text}` : text };
  });
}

/** 지금 문서의 번호 모양 id — 번호가 없으면 빈 글자 (D107) */
export function numberScheme(lines) {
  const id = detect(lines);
  return id === 'plain' ? '' : id;
}

/** 머리글 글 text 에서 번호 부분의 길이 (뒤의 빈칸까지) — 한 줄 편집의 칸이 번호를 잠근다 (D107) */
export function markLength(text, id) {
  return text.length - bare(text, id).length;
}

/** 번호를 뗀 머리글 글 — 제목을 문단으로 바꿀 때 (docops.setKind) */
export const bareHeading = (text, id) => bare(text, id);

/** 제목 차례가 같은지 (수준과 번호를 뗀 글) — 다르면 번호를 다시 맞춘다 */
export function sameHeads(a, b) {
  const key = (lines) => { const id = detect(lines); return JSON.stringify(headings(lines).map((h) => [h.level, bare(h.text, id)])); };
  return key(a) === key(b);
}

/** 미리보기: 머리글 앞의 몇 개 [{depth, text}] */
export function preview(lines, id, count = 12) {
  return dressed(lines, id).slice(0, count).map(({ depth, text }) => ({ depth, text }));
}

/** 목록에 보여 줄 번호 글자 ('Ⅰ.  1.  가.') */
export function sample(id, count = 4) {
  const marks = marksOf(id).filter(Boolean).slice(0, count);
  return [...new Set(marks.map((m, i) => makeMark(m, [1, 1, 1, 1, 1, 1], i)))].join('  ');
}

/** 머리글을 모양 id 로 바꾼다. 이 문서 안의 절 링크(#제목)도 함께. {lines, changed(머리글 수), links(고친 링크 수)} */
export function applyScheme(lines, id, slug) {
  const next = lines.slice();
  const moved = new Map();
  let changed = 0;
  for (const h of dressed(lines, id)) {
    if (h.text === h.old) continue;
    next[h.line] = `${h.pad}${h.mark}${h.gap}${h.text}`;
    changed += 1;
    if (!moved.has(slug(h.old))) moved.set(slug(h.old), slug(h.text));
  }
  let links = 0;
  const skip = new Set(headings(lines).map((h) => h.line));
  const code = fenced(lines);
  next.forEach((s, i) => {
    if (skip.has(i) || code[i] || !s.includes('](#')) return;
    next[i] = s.replace(/\]\(#([^)\s]+)\)/g, (all, target) => {
      const to = moved.get(decodeURIComponent(target));
      if (!to) return all;
      links += 1;
      return `](#${to})`;
    });
  });
  return { lines: next, changed, links };
}

/** 머리글 앞 글자를 틀 글자로. 번호가 아니면 빈 글자 */
function markOf(text) {
  const word = /^\S+(?=\s)/.exec(text)?.[0] ?? '';
  /** @type {[RegExp, (m: RegExpExecArray) => string][]} */
  const forms = [
    [/^제\d+([장절편조항])$/, (m) => `제{1}${m[1]}`],   // i18n-ok (번호 글자)
    [/^\d+(?:\.\d+)+\.?$/, () => '{path}'],
    [/^\d+([.)])$/, (m) => `{1}${m[1]}`],
    [/^\(\d+\)$/, () => '({1})'],
    [new RegExp(`^${ANY_ROMAN}+([.)])$`), (m) => `{I}${m[1]}`],
    [/^[가-힣]([.)])$/, (m) => `{가}${m[1]}`],   // i18n-ok (번호 글자)
    [/^\([가-힣]\)$/, () => '({가})'],   // i18n-ok (번호 글자)
    [/^[①-⑳]$/, () => '{①}'],
    [new RegExp(`^[${escape(SYMBOL)}]$`), (m) => m[0]],
  ];
  for (const [re, make] of forms) {
    const m = re.exec(word);
    if (m) return make(m);
  }
  return '';
}

/** 이 문서의 머리글 모양을 틀 글자들로 뽑는다. 번호가 달린 머리글이 없으면 빈 배열 */
export function marksFrom(lines) {
  const marks = ['', '', '', '', '', ''];
  for (const h of headings(lines)) {
    if (h.depth && !marks[h.depth - 1]) marks[h.depth - 1] = markOf(h.text);
  }
  while (marks.length && !marks.at(-1)) marks.pop();
  return marks;
}
