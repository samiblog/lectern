// 담은 조각 (D63): 문서의 한 부분(장·절·블록·표·그림·차트·수식 등)의 Markdown 원문을 다른 문서에 넣을 수 있게 다듬는 함수들.
// DOM 을 쓰지 않는다 — 글만 받아 글을 돌려준다 (basket.js 가 쓴다).
// - 상대경로 다시 쓰기: 그림·링크·참조 정의·html 의 src/href, Vega(-Lite) 의 data url — 원래 문서 기준을 넣을 문서 기준으로.
//   코드 블록·글 속 `코드` 는 건드리지 않는다. 프로젝트 맨 위 기준(/…)·인터넷 주소·앵커(#…)는 그대로.
// - 각주: 조각이 쓰는 [^이름] 의 정의를 원래 문서에서 함께 가져오고, 넣을 문서의 이름과 겹치면 바꾼다.
// - 제목 수준: 조각의 맨 위 제목을 넣을 자리에 맞춘다 (조각 안의 차이는 그대로, 1~6).
// - 넣을 자리: 맨 앞(맨 앞 설정·문서 제목 아래), 맨 끝(끝의 각주 정의 앞), 절 끝, 커서가 든 블록 끝 — 앞뒤에 빈 줄을 둔다.

import { t } from './i18n.js';
import { rangeText } from './docmenu.js';

const FENCE = /^ {0,3}(`{3,}|~{3,})(.*)$/;
const HEADING = /^ {0,3}(#{1,6})(?=\s|$)(.*)$/;
const NOTE_DEF = /^ {0,3}\[\^([^\]\s]+)\]:/;
const NOTE_REF = /\[\^([^\]\s]+)\]/g;
const SCHEME = /^[a-z][a-z0-9+.-]*:/i;   // https: mailto: data: 그리고 C: (Windows 절대경로)
const CHART_FENCES = new Set(['vega-lite', 'vega']);   // 데이터 파일을 읽는 차트 (charts.js — ECharts·Plotly 는 문서 안 값만)
const INDENTED = /^( {4}|\t)/;

const dirOf = (path) => (path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '');
const segs = (dir) => (dir ? dir.split('/') : []);
const blank = (line) => !line?.trim();
const decode = (s) => { try { return decodeURIComponent(s); } catch { return s; } };

/** 줄마다 코드 블록 안인지: [{code, info(언어), open, close}] — ``` 와 ~~~ (닫는 울타리는 같은 글자, 같거나 더 긴 것) */
export function fenceMap(lines) {
  const out = [];
  let open = null;
  for (const line of lines) {
    if (open) {
      const m = /^ {0,3}(`{3,}|~{3,})\s*$/.exec(line);
      const close = !!m && m[1][0] === open.ch && m[1].length >= open.len;
      out.push({ code: true, info: open.info, close });
      if (close) open = null;
      continue;
    }
    const m = FENCE.exec(line);
    if (m && !(m[1][0] === '`' && m[2].includes('`'))) {
      open = { ch: m[1][0], len: m[1].length, info: m[2].trim().split(/\s+/)[0].toLowerCase() };
      out.push({ code: true, info: open.info, open: true });
      continue;
    }
    out.push({ code: false });
  }
  return out;
}

/** 맨 앞 설정(--- … ---)의 끝 다음 줄 번호 (0부터). 없으면 0 */
export function frontMatterEnd(lines) {
  if (lines[0]?.trim() !== '---') return 0;
  const end = lines.findIndex((line, i) => i > 0 && /^(---|\.\.\.)\s*$/.test(line));
  return end > 0 ? end + 1 : 0;
}

/** 글 속 `코드` 밖의 부분에만 fn 을 적용한다 */
function outsideCode(line, fn) {
  let out = '';
  let i = 0;
  while (i < line.length) {
    const tick = line.indexOf('`', i);
    if (tick < 0) break;
    const run = /^`+/.exec(line.slice(tick))[0];
    const close = line.indexOf(run, tick + run.length);
    if (close < 0) break;
    out += fn(line.slice(i, tick)) + line.slice(tick, close + run.length);
    i = close + run.length;
  }
  return out + fn(line.slice(i));
}

/** 원래 문서 폴더(fromDir) 기준 상대경로를 넣을 문서 폴더(toDir) 기준으로. 프로젝트 밖으로 나가거나 바꿀 것이 아니면 그대로 */
export function rebaseUrl(url, fromDir, toDir) {
  if (!url || fromDir === toDir || /^[#/\\]/.test(url) || SCHEME.test(url)) return url;
  const cut = url.search(/[?#]/);
  const path = cut < 0 ? url : url.slice(0, cut);
  if (!path) return url;
  const dir = path.endsWith('/');
  const at = segs(fromDir).map((s) => ({ raw: s, key: s.toLowerCase() }));
  for (const p of path.split('/')) {
    if (p === '.' || p === '') continue;
    if (p === '..') {
      if (!at.length) return url;   // 프로젝트 밖
      at.pop();
    } else {
      at.push({ raw: p, key: decode(p).toLowerCase() });
    }
  }
  if (!at.length) return url;   // 프로젝트 맨 위
  const to = segs(toDir).map((s) => s.toLowerCase());
  const limit = Math.min(dir ? at.length : at.length - 1, to.length);   // 파일 이름은 폴더와 맞춰 보지 않는다
  let same = 0;
  while (same < limit && at[same].key === to[same]) same += 1;
  const rel = [...Array(to.length - same).fill('..'), ...at.slice(same).map((s) => s.raw)].join('/') || '.';
  return `${rel}${dir ? '/' : ''}${cut < 0 ? '' : url.slice(cut)}`;
}

const wrapped = (dest, fn) => (dest.startsWith('<') ? `<${fn(dest.slice(1, -1))}>` : fn(dest));

/** 한 줄(코드 블록 밖)의 링크·그림·참조 정의·html 속성 주소를 옮긴다 */
function rebaseLine(line, move) {
  const def = /^( {0,3}\[(?!\^)[^\]]+\]:\s*)(<[^>]*>|\S+)(.*)$/.exec(line);   // [이름]: 주소 "제목"
  if (def) return def[1] + wrapped(def[2], move) + def[3];
  return outsideCode(line, (part) => part
    .replace(/(\]\(\s*)(<[^>\n]*>|[^\s()<>]+(?:\([^\s()]*\)[^\s()<>]*)*)/g, (m, head, dest) => head + wrapped(dest, move))
    .replace(/(\s(?:src|href)\s*=\s*)(["'])(.*?)\2/gi, (m, head, q, url) => `${head}${q}${move(url)}${q}`));
}

/** 조각 글(text — 원래 문서 from 의 것)의 상대경로를 넣을 문서(to) 기준으로 */
export function rebase(text, from, to) {
  const fromDir = dirOf(from);
  const toDir = dirOf(to);
  if (fromDir === toDir) return text;
  const move = (url) => rebaseUrl(url, fromDir, toDir);
  const lines = text.split('\n');
  const map = fenceMap(lines);
  return lines.map((line, i) => {
    if (!map[i].code) return rebaseLine(line, move);
    // 코드 블록은 그대로 — 차트의 data url 만 옮긴다
    if (!CHART_FENCES.has(map[i].info) || map[i].open || map[i].close) return line;
    return line.replace(/((?:"url"|'url'|\burl)\s*:\s*)(["'])((?:\\.|(?!\2).)*)\2/g, (m, head, q, url) => `${head}${q}${move(url)}${q}`);
  }).join('\n');
}

// ---- 각주 ----------------------------------------------------------------------

/** 글이 쓰는 각주 이름들 (정의 줄 포함, 코드 밖) */
export function noteIds(text) {
  const lines = text.split('\n');
  const map = fenceMap(lines);
  const ids = new Set();
  lines.forEach((line, i) => {
    if (map[i].code) return;
    outsideCode(line, (part) => {
      for (const m of part.matchAll(NOTE_REF)) ids.add(m[1]);
      return part;
    });
  });
  return ids;
}

/** 원래 문서(lines)에서 각주 정의들(ids)을 찾아 글로 — 정의 줄과 들여 쓴 이어진 줄. skip: 이미 조각에 든 줄 범위 [a, b] (1부터) */
export function noteDefs(lines, ids, skip = null) {
  const map = fenceMap(lines);
  const out = [];
  for (let i = 0; i < lines.length; i++) {
    const m = !map[i].code && NOTE_DEF.exec(lines[i]);
    if (!m || !ids.has(m[1]) || (skip && i + 1 >= skip[0] && i + 1 <= skip[1])) continue;
    const block = [lines[i]];
    for (let j = i + 1; j < lines.length; j++) {
      if (INDENTED.test(lines[j]) || (blank(lines[j]) && INDENTED.test(lines[j + 1] || ''))) block.push(lines[j]);
      else break;
    }
    out.push(block.join('\n').replace(/\s+$/, ''));
  }
  return out.join('\n');
}

/** 각주 이름을 바꾼다 — taken(넣을 문서와 앞 조각이 쓰는 이름)과 겹치면 '이름-2' 처럼. 쓴 이름은 taken 에 더한다 */
function renameNotes(text, taken) {
  const rename = new Map();
  for (const id of noteIds(text)) {
    let next = id;
    for (let n = 2; taken.has(next); n += 1) next = `${id}-${n}`;
    taken.add(next);
    if (next !== id) rename.set(id, next);
  }
  if (!rename.size) return text;
  const lines = text.split('\n');
  const map = fenceMap(lines);
  return lines.map((line, i) => (map[i].code ? line
    : outsideCode(line, (part) => part.replace(NOTE_REF, (m, id) => (rename.has(id) ? `[^${rename.get(id)}]` : m))))).join('\n');
}

// ---- 제목 -----------------------------------------------------------------------

/** 제목들 (# 제목 — 코드 블록 밖, doc 이면 맨 앞 설정도 밖): [{i(줄, 0부터), level, text}].
 * 조각은 doc=false — 조각 맨 앞의 --- 는 구분선이다 (맨 앞 설정은 담지 않는다) */
export function headingsOf(text, doc = true) {
  const lines = text.split('\n');
  const map = fenceMap(lines);
  const out = [];
  for (let i = doc ? frontMatterEnd(lines) : 0; i < lines.length; i++) {
    const m = !map[i].code && HEADING.exec(lines[i]);
    if (m) out.push({ i, level: m[1].length, text: m[2].replace(/\s#+\s*$/, '').trim() });
  }
  return out;
}

/** 조각의 맨 위 제목이 top 수준이 되게 모든 제목을 옮긴다 (제목이 없거나 top 이 0 이면 그대로) */
export function shiftHeadings(text, top) {
  const heads = headingsOf(text, false);
  if (!heads.length || !top) return text;
  const delta = top - Math.min(...heads.map((h) => h.level));
  if (!delta) return text;
  const lines = text.split('\n');
  for (const h of heads) lines[h.i] = lines[h.i].replace(/^( {0,3})#{1,6}/, (m, sp) => sp + '#'.repeat(Math.min(6, Math.max(1, h.level + delta))));
  return lines.join('\n');
}

// ---- 넣을 자리 ------------------------------------------------------------------

/** 끝의 빈 줄을 건너 위로 — 그 블록 바로 뒤 줄 번호 */
function backOverBlank(lines, i) {
  while (i > 0 && blank(lines[i - 1])) i -= 1;
  return i;
}

/** 고른 절의 제목 — 줄 번호와 글이 같은 것, 그사이 줄이 바뀌었으면 글이 같은 것 */
const findHead = (heads, head) => heads.find((x) => x.i === head?.i && x.text === head.text) || heads.find((x) => x.text === head?.text);

/** 넣을 줄 번호 (0부터 — 그 줄 앞에). place: {at: 'start'|'end'|'section'|'cursor', head(제목 — section), line(커서 줄 — cursor)} */
export function placeLine(text, place) {
  const lines = text.split('\n');
  const heads = headingsOf(text);
  if (place.at === 'start') {
    const front = frontMatterEnd(lines);
    const first = lines.findIndex((line, i) => i >= front && !blank(line));
    if (first < 0) return backOverBlank(lines, lines.length);
    return heads[0]?.i === first && heads[0].level === 1 ? first + 1 : first;   // 문서 제목(# …) 아래
  }
  if (place.at === 'cursor') {
    const map = fenceMap(lines);
    let i = Math.max(0, Math.min(place.line, lines.length - 1));
    if (map[i].code) {   // 코드 블록 안이면 그 블록 뒤로
      while (i < lines.length - 1 && !map[i].close) i += 1;
      return i + 1;
    }
    if (blank(lines[i])) return i;
    while (i < lines.length && !blank(lines[i])) i += 1;   // 커서가 든 블록(단락·표·목록)의 끝
    return i;
  }
  let end = backOverBlank(lines, lines.length);
  if (place.at === 'section') {
    const h = findHead(heads, place.head);
    const next = h && heads.find((x) => x.i > h.i && x.level <= h.level);
    if (next) return backOverBlank(lines, next.i);
  }
  // 문서 끝: 끝에 모인 각주 정의([^1]: …)가 있으면 그 앞에
  let j = end;
  while (j > 0 && (NOTE_DEF.test(lines[j - 1]) || INDENTED.test(lines[j - 1]) || blank(lines[j - 1]))) j -= 1;
  while (j < end && blank(lines[j])) j += 1;
  if (j < end && NOTE_DEF.test(lines[j])) end = backOverBlank(lines, j);
  return end;
}

/** 조각의 맨 위 제목이 될 수준: 고른 절·커서 위의 제목 + 1 (그 절 아래), 문서 끝·맨 앞이면 2 (문서 제목 아래).
 * 제목이 없는 문서거나 맨 위 제목 앞이면 0 (그대로) */
export function levelAt(text, place, line) {
  const heads = headingsOf(text);
  if (!heads.length) return 0;
  if (place.at === 'end' || place.at === 'start') return heads.some((h) => h.level === 1) ? 2 : 0;
  const h = place.at === 'section' ? findHead(heads, place.head) : heads.filter((x) => x.i < line).pop();
  return h ? Math.min(6, h.level + 1) : 0;
}

/**
 * 넣을 글: CodeMirror 에 넣을 자리 {line, ch}, 넣을 글 text, 그 안에서 조각 글이 시작하는 곳 offset 과 길이 size.
 * at: 넣을 줄 (0부터 — 그 줄 앞에, 줄 수와 같으면 마지막 줄 끝). 앞뒤 줄이 비어 있지 않으면 빈 줄을 둔다
 */
export function placeText(lines, at, body) {
  if (at >= lines.length) {   // 마지막 줄 끝 (파일이 줄바꿈으로 끝나지 않음 — 그 줄은 비어 있지 않다)
    const last = lines.length - 1;
    return { line: last, ch: lines[last].length, text: `\n\n${body}\n`, offset: 2, size: body.length };
  }
  const head = at > 0 && !blank(lines[at - 1]) ? '\n' : '';
  const tail = blank(lines[at]) ? '\n' : '\n\n';   // 뒤 줄이 비어 있지 않으면 빈 줄을 하나 더 (맨 끝의 빈 줄은 파일 끝 줄바꿈 뒤)
  return { line: at, ch: 0, text: `${head}${body}${tail}`, offset: head.length, size: body.length };
}

// ---- 조각 모으기 ----------------------------------------------------------------

/** 담은 곳 주석 (D63 — 화면에는 보이지 않고 Claude Code 는 읽는다). 주석을 닫는 글자는 넣지 않는다 */
export const provenance = (snip) => `<!-- ${t('담은 곳: {path}', { path: `${snip.path}${snip.lines ? ` ${rangeText(snip.lines)}` : ''}` }).replace(/-{2,}>?/g, '-')} -->`;

/**
 * 조각들을 넣을 글 하나로: 조각마다 담은 곳 주석, 경로를 넣을 문서(to) 기준으로, 각주 정의를 함께(이름이 겹치면 바꿔서),
 * 맨 위 제목을 top 수준으로 (0 이면 그대로). taken: 넣을 문서가 이미 쓰는 각주 이름
 */
export function buildBody(snippets, to, { top = 0, taken = new Set() } = {}) {
  const used = new Set(taken);
  return snippets.map((sn) => {
    if (sn.plain) return `${provenance(sn)}\n${sn.text}`;   // 고른 글 — 원문이 아니라 보이는 글 그대로
    const text = rebase(sn.notes ? `${sn.text}\n\n${sn.notes}` : sn.text, sn.path, to);
    return `${provenance(sn)}\n${shiftHeadings(renameNotes(text, used), top)}`;
  }).join('\n\n');
}

/** 새 문서의 제목 — 파일 이름에서 ('구리-요약.md' → '구리 요약') */
export const titleFromName = (path) => path.split('/').pop().replace(/\.(md|markdown)$/i, '').replace(/[-_]+/g, ' ').trim() || t('새 문서');
