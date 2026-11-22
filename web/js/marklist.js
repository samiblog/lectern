// 글머리 글자 목록 (D192) — 한국식 개조 목록: 줄 맨 앞의 □·ㅁ, ○·ㅇ, -, · 같은 글머리 글자를 목록으로 읽고 하위 수준은 상위 수준보다 들여 쓴다.
//
// - 원문은 그대로다. markdown-it 블록 규칙이 그런 줄들을 한 묶음(div.lec-marklist)으로, 항목마다 문단(p.lec-mark)으로 그린다 — 글머리 글자는 글 그대로 보인다.
//   항목은 원문 줄 하나(와 이어 쓴 줄)라 한 줄 편집·줄 단위·내어쓰기(hang.js, D191)가 항목마다 된다.
// - 묶음은 □·ㅁ·■·○·ㅇ·●·◎·◦·ㆍ·•·· 로 시작하는 줄에서 시작한다 ('-' 로 시작하면 지금처럼 Markdown 목록). 묶음 안에서는 '-' 줄과 ①·1.·가.·※ 줄도 항목이고
//   (Markdown 목록이 되지 않는다), 머리 글자가 없는 줄은 위 항목에 이어 쓴 줄이다. 빈 줄·제목·코드 블록·인용·표·가로줄에서 끝난다.
// - 수준은 글머리 글자의 종류로 정한다 — 보고서의 차례 □ > ○ > - > · 가운데 그 문서가 쓴 것만 세어 0, 1, 2… (○ 와 - 만 쓰면 ○ 가 맨 위).
//   차례에 없는 머리 글자(①·1.·가.·※)는 위 항목의 한 수준 아래. 원문의 앞 빈칸은 보지 않는다 (Markdown 이 문단 줄의 앞 빈칸을 버린다).
// - Lectern 슬라이드와 Markdown 목록 항목 안에서는 하지 않는다 (슬라이드는 칸·넘침 맞춤이 따로, 목록 항목 안은 촘촘한 목록의 줄바꿈이 깨진다).

import { hangPrefix } from './hang.js';

/** 차례가 있는 글머리 글자 — 보고서의 □ > ○ > - > · */
export const RANKS = ['□■ㅁ▢▣', '○●ㅇ◎◦', '-–—－', '·ㆍ•∙‧'];
/** 묶음을 여는 글머리 글자 ('-' 는 Markdown 목록이 먼저다) */
const START = RANKS[0] + RANKS[1] + RANKS[3];
/** 묶음의 수준은 여섯까지 (그보다 깊으면 여섯째) */
const MAX_LEVEL = 5;

/**
 * 줄의 머리 글자 — 없으면 null. rank: 차례(0~3), 차례에 없는 머리 글자(①·1.·가.·※ …)면 -1
 * @param {string} text
 */
export function markOf(text) {
  const prefix = hangPrefix(text);
  if (!prefix) return null;
  const c = prefix.trim();
  return { prefix, rank: c.length === 1 ? RANKS.findIndex((r) => r.includes(c)) : -1 };
}

/**
 * 원문 줄에서 머리 글자를 볼 글 — 앞의 전각 빈칸(한글 문서에서 붙여 넣은 들여쓰기)과 머리 글자를 감싼 굵게·기울임 표시를 뗀다
 * ('**□ 제목**' 처럼 줄 전체를, '**ㅇ** 내용' 처럼 머리 글자만 감싼 것 모두 — Claude 가 흔히 쓴다)
 * @param {string} line 앞 빈칸을 뗀 원문 줄
 */
export function markText(line) {
  const s = line.replace(/^\u3000+/, '');
  const m = /^(\*\*|__|\*|_)(?=\S)/.exec(s);
  if (!m) return s;
  const rest = s.slice(m[1].length);
  const c = [...rest][0] ?? '';
  return rest.slice(c.length, c.length + m[1].length) === m[1] ? c + rest.slice(c.length + m[1].length) : rest;
}

/** 이 자리가 Markdown 목록 항목 안인지 — 열린 list_item 이 있는지 토큰을 거슬러 본다 (머리 글자가 있는 줄에서만 부른다) */
function inListItem(state) {
  let depth = 0;
  for (let i = state.tokens.length - 1; i >= 0; i--) {
    const type = state.tokens[i].type;
    if (type === 'list_item_close') depth += 1;
    else if (type === 'list_item_open') {
      if (!depth) return true;
      depth -= 1;
    }
  }
  return false;
}

/** 블록 규칙 — markdown-it 의 list 앞에 (문단·인용을 끊을 수 있다) */
function markRule(state, startLine, endLine, silent) {
  if (state.env.deck || state.parentType === 'list') return false;
  if (state.sCount[startLine] - state.blkIndent >= 4) return false;   // 들여 쓴 코드
  const text = (n) => state.src.slice(state.bMarks[n] + state.tShift[n], state.eMarks[n]);
  const first = markText(text(startLine));
  if (!START.includes(first[0] ?? '\0') || !markOf(first)) return false;
  const under = startLine + 1 < endLine ? text(startLine + 1) : '';
  if (/^(?:=+|-+)[ \t]*$/.test(under) && state.sCount[startLine + 1] - state.blkIndent < 4) return false;   // 바로 아래가 --- · === 면 제목(setext)이 먼저
  if (inListItem(state)) return false;
  // 끝: 빈 줄, 또는 문단을 끊는 블록(제목·코드 블록·인용·가로줄·표·html …) — Markdown 목록(list)과 이 규칙은 끊지 않는다
  const rules = state.md.block.ruler.__rules__;
  const own = new Set(rules.filter((r) => r.name === 'list' || r.name === 'lec_marklist').map((r) => r.fn));
  const stops = state.md.block.ruler.getRules('paragraph').filter((fn) => !own.has(fn));
  let end = startLine + 1;
  for (; end < endLine; end++) {
    if (state.isEmpty(end)) break;
    if (state.sCount[end] - state.blkIndent > 3 || state.sCount[end] < 0) continue;   // 깊이 들여 쓴 줄은 이어 쓴 줄
    const old = state.parentType;
    state.parentType = 'paragraph';
    const stop = stops.some((fn) => fn(state, end, endLine, true));
    state.parentType = old;
    if (stop) break;
  }
  if (silent) return true;
  const items = [];
  for (let n = startLine; n < end; n++) {
    const mark = markOf(markText(text(n)));
    if (mark || !items.length) items.push({ start: n, end: n + 1, rank: mark?.rank ?? -1 });
    else items.at(-1).end = n + 1;
  }
  const open = state.push('lec_marklist_open', 'div', 1);
  open.map = [startLine, end];
  open.attrSet('class', 'lec-marklist');
  for (const it of items) {
    const p = state.push('lec_mark_open', 'p', 1);
    p.map = [it.start, it.end];
    p.meta = { rank: it.rank };
    const inline = state.push('inline', '', 0);
    // 줄마다 앞의 빈칸·전각 빈칸을 뗀다 — 수준의 들여쓰기가 대신한다
    inline.content = state.getLines(it.start, it.end, state.blkIndent, false).split('\n').map((s) => s.replace(/^[ \t\u3000]+/, '')).join('\n').trim();
    inline.map = [it.start, it.end];
    inline.children = [];
    state.push('lec_mark_close', 'p', -1);
  }
  state.push('lec_marklist_close', 'div', -1);
  state.line = end;
  return true;
}

/** 수준: 그 문서가 쓴 차례만 세어 0, 1, 2… — 차례에 없는 머리 글자는 위 항목의 한 수준 아래 */
function markLevels(state) {
  const marks = state.tokens.filter((tk) => tk.type === 'lec_mark_open');
  if (!marks.length) return;
  const used = [...new Set(marks.map((tk) => tk.meta.rank).filter((r) => r >= 0))].sort();
  let above = 0;
  for (const tk of state.tokens) {
    if (tk.type === 'lec_marklist_open') above = 0;
    if (tk.type !== 'lec_mark_open') continue;
    const level = Math.min(MAX_LEVEL, tk.meta.rank >= 0 ? used.indexOf(tk.meta.rank) : above + 1);
    if (tk.meta.rank >= 0) above = level;
    tk.attrSet('class', `lec-mark lec-lv${level}`);
  }
}

/**
 * markdown-it 플러그인 — markdown.js 와 문서 점검(doclint.js)이 같이 쓴다 (점검이 묶음 안의 '-'·'2.' 줄을 목록으로 읽지 않게)
 * @param {any} md
 */
export function marklistPlugin(md) {
  md.block.ruler.before('list', 'lec_marklist', markRule, { alt: ['paragraph', 'blockquote'] });
  md.core.ruler.after('block', 'lec_marklist_levels', markLevels);
}
