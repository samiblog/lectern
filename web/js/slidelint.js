// 슬라이드 점검의 앞단 (D96): 그려 놓으면 보이지 않는 실수를 찾는다 — 사람도 Claude 도 화면을 다 살피지 못하므로 점검 하나로 고치게.
// 글이 말없이 사라지는 것(닫지 않은 주석·<style>·코드 블록), 칸·구분 줄로 읽지 못한 줄, 지시어·칸 머리의 오타, 잘못된 격자,
// 그린 뒤에만 아는 것(바탕과 비슷한 글자, 옆으로 잘린 코드, 없는 그림). 결과는 [{text, line}] 또는 add(text, el).

import { $$ } from './util.js';
import { LAYOUTS, SAFE_TRACK, cellHeadOdds, readCellHead, textOdds, textSizes } from './slideops.js';
import { t } from './i18n.js';

const WORDS = new Set(['card', 'accent', 'dark', 'note', 'kpi', 'center', 'text-center', 'text-right', 'cols-2', 'cols-3']);
const TYPO_NAMES = ['layout', 'grid', 'cols', 'rows', 'text', 'eyebrow', 'links', 'class', 'paginate', 'header', 'footer', 'color', 'backgroundColor', 'backgroundImage'];
const short = (s) => {
  const x = String(s).trim();
  return x.length > 40 ? `${x.slice(0, 40)}…` : x;
};

/** 두 낱말의 거리 (글자 바꿈·넣기·빼기·이웃 맞바꿈) */
function distance(a, b) {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
    }
  }
  return d[a.length][b.length];
}

/** 노트로 읽은 주석이 지시어를 잘못 쓴 것 같으면 그 글. 아니면 빈 글 (<!-- 출처: 통계청 --> 같은 노트는 그대로) */
export function commentSlip(text) {
  const one = text.trim();
  if (one.includes('\n')) return '';
  const named = /^_?([A-Za-z][\w-]*)\s*:\s*\S/.exec(one);
  if (named) {
    const name = named[1];
    if (name.length > 24) return '';
    const near = TYPO_NAMES.find((n) => n !== name && distance(name.toLowerCase(), n.toLowerCase()) <= (n.length > 4 ? 2 : 1));
    return near ? t("'{name}' 은(는) 지시어가 아니어서 노트로 읽었습니다 — {near} 인가요?", { name, near }) : '';
  }
  const bare = /^_?(layout|text)\s+(.+)$/.exec(one);
  if (!bare) return '';
  const value = bare[2].trim();
  const meant = bare[1] === 'layout' ? Object.hasOwn(LAYOUTS, value) : Object.keys(textSizes(value)).length > 0;
  return meant ? t('{name} 뒤에 콜론이 없어 노트로 읽었습니다 — {name}: 값 으로 씁니다', { name: bare[1] }) : '';
}

/** html 블록이 닫히지 않아 뒤의 글을 삼켰으면 그 글 */
export function openBlock(content) {
  if (/^\s*<!--/.test(content) && !content.includes('-->')) return t('주석이 닫히지 않아 뒤의 글이 보이지 않습니다 — --> 를 쓰세요');
  const m = /^\s*<(script|pre|style|textarea)\b/i.exec(content);
  if (m && !new RegExp(`</${m[1]}>`, 'i').test(content)) return t('<{tag}> 이 닫히지 않아 뒤의 글이 보이지 않습니다 — </{tag}> 를 쓰세요', { tag: m[1].toLowerCase() });
  return '';
}

/** 코드 블록의 끝 줄이 닫는 줄이 아니면 true — 문서 끝까지(칸이면 칸 끝까지) 코드가 된다 */
export function openFence(lines, tok) {
  const [from, to] = tok.map;
  if (to - from < 2) return true;
  const m = /^\s*(`{3,}|~{3,})\s*$/.exec(lines[to - 1] ?? '');
  return !(m && m[1][0] === tok.markup[0] && m[1].length >= tok.markup.length);
}

/** 칸·구분 줄로 읽히지 않은 줄들 [{text, n(0부터)}]. skip: 코드·html 의 줄, 칸의 머리·닫는 줄 */
export function strayLines(lines, from, to, skip) {
  const out = [];
  for (let n = from; n < to; n++) {
    if (skip.has(n)) continue;
    const s = (lines[n] ?? '').trim();
    if (/^:::(\s|$)/.test(s)) out.push({ text: t('짝이 맞지 않는 ::: 가 있습니다'), n });
    else if (/^(?::{2,}|：{2,})/.test(s)) out.push({ text: t('칸 표시로 읽지 못했습니다 — 줄 맨 앞에 콜론 셋과 빈칸으로 씁니다 (::: 이름)'), n });
    else if (/^[－—–―ㅡ]{3,}$/.test(s)) out.push({ text: t('구분 줄로 읽지 못했습니다 — 하이픈 셋으로 씁니다 (---)'), n });
  }
  return out;
}

/** 칸 머리 줄의 문제들 (css: 이 문서의 CSS — 거기 쓴 낱말은 사용자의 낱말이다) */
export function cellSlips(head, css) {
  const { name, words } = readCellHead(head);
  const odd = cellHeadOdds(head).slice(0, 3).map((word) => t("칸 {name} 의 '{word}' 을(를) 읽지 못했습니다 — 글자 크기는 16, 자리는 at x y 너비 높이 로 씁니다", { name: short(name), word: short(word) }));
  const unknown = words.filter((w) => !WORDS.has(w) && !css.includes(`.${w}`)).slice(0, 3)
    .map((word) => t("칸 {name} 의 낱말 '{word}' 을(를) 모릅니다 — card, accent, dark, note, kpi, center 를 씁니다", { name: short(name), word: short(word) }));
  return [...odd, ...unknown];
}

/** 글자 크기 지시어에서 읽지 못한 부분들 */
export const textSlips = (value) => textOdds(value).slice(0, 3).map((part) => t("글자 크기 '{part}' 을(를) 읽지 못했습니다 — 표 14 처럼 씁니다", { part: short(part) }));

/** 격자·열·행 지시어의 문제들 — 잘못 쓰면 칸이 말없이 차례대로 놓인다 */
export function gridSlips(eff) {
  const out = [];
  const layout = String(eff.layout || '').trim();
  const source = typeof eff.grid === 'string' ? eff.grid : (Object.hasOwn(LAYOUTS, layout) ? LAYOUTS[layout][0] : '');
  if (!source) return out;
  const rows = source.split('/').map((row) => row.trim().split(/\s+/));
  const width = rows[0].length;
  if (rows.some((row) => row.length !== width)) out.push(t('격자의 줄마다 칸 수가 같아야 합니다'));
  else {
    for (const name of new Set(rows.flat())) {
      if (name === '.') continue;
      const at = rows.flatMap((row, y) => row.flatMap((cell, x) => (cell === name ? [[x, y]] : [])));
      const xs = at.map((p) => p[0]);
      const ys = at.map((p) => p[1]);
      if ((Math.max(...xs) - Math.min(...xs) + 1) * (Math.max(...ys) - Math.min(...ys) + 1) !== at.length) out.push(t('격자의 칸 {name} 이(가) 네모가 아닙니다', { name: short(name) }));
    }
  }
  for (const [key, css, count] of [['cols', 'grid-template-columns', width], ['rows', 'grid-template-rows', rows.length]]) {
    const value = eff[key];
    if (typeof value !== 'string') continue;
    if (!SAFE_TRACK.test(value) || !CSS.supports(css, value)) out.push(t("{key} 값 '{value}' 을(를) 읽지 못했습니다 — 1fr 2fr 처럼 씁니다", { key, value: short(value) }));
    else if (!value.includes('(') && value.trim().split(/\s+/).length !== count) out.push(t('{key} 는 격자에 맞게 {n}개를 씁니다', { key, n: count }));
  }
  return out;
}

// ---- 그린 뒤에만 아는 것 --------------------------------------------------------------------------

/** 계산된 색 → [r, g, b, a] (0~255, a 는 0~1). 모르는 꼴이면 null */
function rgba(value) {
  const srgb = /^color\(srgb ([^)]+)\)$/.exec(value);
  const plain = /^rgba?\(([^)]+)\)$/.exec(value);
  const n = (srgb || plain)?.[1].split(/[\s,/]+/).filter(Boolean).map(Number);
  if (!n || n.length < 3 || n.some(Number.isNaN)) return null;
  return srgb ? [n[0] * 255, n[1] * 255, n[2] * 255, n[3] ?? 1] : [n[0], n[1], n[2], n[3] ?? 1];
}

const over = (top, under) => top.slice(0, 3).map((c, i) => c * top[3] + under[i] * (1 - top[3]));

/** 글 뒤의 색. 그림이 깔렸거나 알 수 없으면 null */
function backdrop(el, section) {
  const layers = [];
  for (let n = el; n; n = n.parentElement) {
    const st = getComputedStyle(n);
    if (st.backgroundImage !== 'none') return null;
    const c = rgba(st.backgroundColor);
    if (!c) return null;
    if (c[3] > 0) layers.push(c);
    if (c[3] >= 1) break;
    if (n === section) {
      if (section.querySelector(':scope > .lec-slide-bg')) return null;
      break;
    }
  }
  if (!layers.length || layers.at(-1)[3] < 1) return null;
  return layers.reverse().reduce((under, top) => [...over(top, under), 1], [0, 0, 0, 1]);
}

const light = ([r, g, b]) => {
  const ch = (v) => {
    const x = v / 255;
    return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
};

const TEXTS = ':is(h1, h2, h3, h4, h5, h6, p, li, td, th, strong, em, a, code, blockquote):not(svg *, .katex *, header *, footer *, .lec-tag, .lec-eyebrow *)';

/** 글자가 바탕과 비슷해 읽을 수 없는 곳 — 화면을 보지 않고도 알 수 있게. 한 장에 하나만 */
export function checkContrast(section, add) {
  for (const el of $$(TEXTS, section)) {
    if (![...el.childNodes].some((n) => n.nodeType === Node.TEXT_NODE && n.nodeValue.trim())) continue;
    const text = rgba(getComputedStyle(el).color);
    const back = text && backdrop(el, section);
    if (!back) continue;
    const a = light(text[3] < 1 ? over(text, back) : text);
    const b = light(back);
    if ((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) >= 2) continue;
    add(t("글자가 바탕과 비슷해 보이지 않습니다: '{text}'", { text: short(el.textContent) }), el.closest('[data-lines]') || undefined);
    return;
  }
}

/** 옆으로 잘린 코드·표 — 슬라이드는 밀어 볼 수 없다 */
export function checkClipped(section, add) {
  for (const el of $$('pre:not(.mermaid, .lec-chart, .diagram-error pre), .table-wrap', section)) {
    const wide = el.scrollWidth - el.clientWidth;
    if (wide <= 1) continue;
    add(el.matches('pre') ? t('코드가 옆으로 {n}px 잘렸습니다 — 줄을 나누세요', { n: wide }) : t('표가 옆으로 {n}px 잘렸습니다 — 열을 줄이세요', { n: wide }), el.closest('[data-lines]') || undefined);
  }
}

/** 그리지 못한 차트·다이어그램 — 원문이 대신 나와 있어도 Claude 는 화면을 보지 못한다 */
export function checkDiagrams(section, add) {
  for (const el of $$('.diagram-error', section)) add(t('그림을 그리지 못했습니다: {why}', { why: short(el.querySelector('p')?.textContent ?? '') }), el.closest('[data-lines]') || undefined);
}

/** 풀리지 않은 ** — 문장부호 뒤에 글자를 바로 붙이면(**8.0%**로) 굵게가 되지 않고 별표가 보인다. 한 장에 하나만 */
export function checkMarks(section, add) {
  const walker = document.createTreeWalker(section, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (!n.nodeValue.includes('**') || n.parentElement.closest('code, pre, svg, .katex, .lec-tag, .lec-slide-tags, style')) continue;
    add(t("굵게로 읽지 못한 별표가 있습니다: '{text}' — 닫는 ** 뒤에 빈칸을 두세요", { text: short(n.nodeValue) }), n.parentElement.closest('[data-lines]') || undefined);
    return;
  }
}

/** 불러오지 못한 그림 */
export function checkImages(section, add) {
  for (const img of $$('img', section)) {
    const src = img.getAttribute('src');
    if (!src || !img.complete || img.naturalWidth) continue;
    let name = src;
    try {
      name = decodeURIComponent(src);
    } catch { /* 주소 그대로 */ }
    add(t('그림을 찾을 수 없습니다: {src}', { src: short(name.replace(/^.*\/doc\//, '')) }), img.closest('[data-lines]') || undefined);
  }
}
