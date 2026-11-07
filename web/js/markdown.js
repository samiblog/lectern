// Markdown → HTML 변환 (markdown-it + 플러그인 + 수식 + mermaid·차트 코드 블록)
//
// vendor 전역: markdownit, markdownItAnchor, markdownitFootnote, markdownitTaskLists, hljs, katex

import { S } from './store.js';
import { slideRule, cellRule } from './slides.js';
import { tocKind, isPageBreak } from './refs.js';
import { t } from './i18n.js';

const instances = new Map();

// 차트 코드 블록의 언어 이름 → 종류 (그리는 것은 charts.js, D56)
const CHART_LANGS = { 'vega-lite': 'vega-lite', vegalite: 'vega-lite', vega: 'vega', echarts: 'echarts', plotly: 'plotly', dot: 'dot', graphviz: 'dot' };

/** GitHub와 같은 규칙의 제목 앵커 (한글 유지). Claude가 쓴 '목차 링크'와 맞추기 위함. */
export function slugify(text) {
  return text.trim().toLowerCase()
    .replace(/[^\p{L}\p{M}\p{N}\p{Pc} -]/gu, '')
    .replace(/ /g, '-');
}

function highlight(code, lang) {
  const name = (lang || '').trim().toLowerCase();
  if (name && window.hljs?.getLanguage(name)) {
    try {
      return window.hljs.highlight(code, { language: name, ignoreIllegals: true }).value;
    } catch { /* 일반 텍스트로 표시 */ }
  }
  return '';
}

// ---------------------------------------------------------------------------
// 수식: $...$, $$...$$, \(...\), \[...\], ```math·latex·tex 코드 블록
//
// 원자재 리서치 문서에는 '$105/t' 같은 달러 표기가 많다. 그래서 pandoc 규칙을 따른다.
//   - 여는 $ 바로 뒤는 공백이 아니어야 함
//   - 닫는 $ 바로 앞은 공백이 아니어야 하고, 바로 뒤가 숫자면 안 됨
//   - 첫 번째 닫는 $ 후보가 규칙에 맞지 않으면 수식이 아님 (더 멀리 찾지 않음)
// 예) '$105에서 $110' → 수식 아님,  '$x_t = \beta$' → 수식
// ---------------------------------------------------------------------------

function renderTex(tex, displayMode) {
  try {
    return window.katex.renderToString(tex, { displayMode, throwOnError: false, output: 'html', strict: 'ignore' });
  } catch {
    return `<code class="math-error">${tex.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]))}</code>`;
  }
}

// ```math(GitHub)·```latex·```tex 코드 블록도 수식으로. Claude 는 식을 흔히 ```latex 블록에 쓴다.
// KaTeX 가 못 읽으면 코드 그대로 둔다 — LaTeX 문서 원문 예시는 \documentclass·\section·\item 같은 명령에서 걸린다.
const TEX_FENCES = new Set(['math', 'latex', 'tex']);

/** 코드 블록 속 식을 { tex, html } 로. 빈 줄로 나뉜 식은 따로 그린다 (TeX 도 수식 안의 빈 줄은 오류). 못 읽으면 null */
function fenceTex(content) {
  const parts = content.split(/\n\s*\n/)
    .map((s) => s.trim().replace(/^\$\$([\s\S]*)\$\$$|^\\\[([\s\S]*)\\\]$/, '$1$2').trim())   // 블록 안에 또 쓴 $$…$$, \[…\]
    .filter(Boolean);
  if (!parts.length) return null;
  try {
    const html = parts.map((t) => window.katex.renderToString(t, { displayMode: true, throwOnError: true, output: 'html', strict: 'ignore' }));
    return { tex: parts.join('\n\n'), html: html.join('') };
  } catch {
    return null;
  }
}

function mathInlineDollar(state, silent) {
  const src = state.src;
  const start = state.pos;
  if (src.charCodeAt(start) !== 0x24 /* $ */) return false;
  const display = src.charCodeAt(start + 1) === 0x24;
  const delim = display ? '$$' : '$';
  const from = start + delim.length;
  if (!display) {
    const next = src[from];
    if (!next || /\s/.test(next)) return false;
  }
  let end = from;
  for (;;) {
    end = src.indexOf(delim, end);
    if (end === -1) return false;
    if (src[end - 1] === '\\') { end += 1; continue; }
    break;
  }
  if (end === from) return false;
  if (!display) {
    if (/\s/.test(src[end - 1])) return false;
    if (/[0-9]/.test(src[end + 1] || '')) return false;
  }
  if (!silent) {
    const token = state.push(display ? 'math_display_inline' : 'math_inline', 'math', 0);
    token.content = src.slice(from, end);
    token.markup = delim;
  }
  state.pos = end + delim.length;
  return true;
}

function mathInlineParen(state, silent) {
  // \( ... \)  또는  \[ ... \]  — markdown-it의 escape 규칙보다 먼저 처리해야 한다
  const src = state.src;
  const start = state.pos;
  if (src.charCodeAt(start) !== 0x5c /* \ */) return false;
  const open = src[start + 1];
  if (open !== '(' && open !== '[') return false;
  const close = open === '(' ? '\\)' : '\\]';
  const end = src.indexOf(close, start + 2);
  if (end === -1 || end === start + 2) return false;
  // 마크다운의 \[ 는 대괄호를 글자로 쓰는 표기이기도 하다 ('원문은 \[판독 불확실\]로 표시').
  // 그래서 \[…\] 는 줄을 통째로 차지할 때만 수식이고, 한글·한자가 있는데 TeX 명령이 없으면 \(…\) 도 수식이 아니다
  if (open === '[') {
    const before = src.slice(src.lastIndexOf('\n', start - 1) + 1, start);
    const lineEnd = src.indexOf('\n', end);
    if (before.trim() || src.slice(end + 2, lineEnd === -1 ? src.length : lineEnd).trim()) return false;
  }
  const content = src.slice(start + 2, end);
  if (/[\p{Script=Hangul}\p{Script=Han}]/u.test(content) && !/\\[a-zA-Z]/.test(content)) return false;
  if (!silent) {
    const token = state.push(open === '(' ? 'math_inline' : 'math_display_inline', 'math', 0);
    token.content = content;
    token.markup = open === '(' ? '\\(' : '\\[';
  }
  state.pos = end + 2;
  return true;
}

function mathBlock(state, startLine, endLine, silent) {
  const begin = state.bMarks[startLine] + state.tShift[startLine];
  const max = state.eMarks[startLine];
  if (state.sCount[startLine] - state.blkIndent >= 4) return false;
  if (state.src.slice(begin, begin + 2) !== '$$') return false;

  const firstRest = state.src.slice(begin + 2, max);
  let content = '';
  let line = startLine;
  let found = false;

  const firstTrim = firstRest.trim();
  if (firstTrim.endsWith('$$') && firstTrim.length > 2) {
    content = firstTrim.slice(0, -2);            // $$ ... $$ 한 줄
    found = true;
  } else if (firstTrim.endsWith('$$')) {
    return false;
  } else {
    if (firstTrim) content = `${firstRest}\n`;
    for (line = startLine + 1; line < endLine; line++) {
      const s = state.bMarks[line] + state.tShift[line];
      const e = state.eMarks[line];
      const text = state.src.slice(s, e);
      if (text.trim().endsWith('$$')) {
        content += text.trim().slice(0, -2);
        found = true;
        break;
      }
      content += `${text}\n`;
    }
  }
  if (!found) return false;
  if (silent) return true;

  state.line = line + 1;
  const token = state.push('math_block', 'math', 0);
  token.block = true;
  token.content = content;
  token.map = [startLine, state.line];
  token.markup = '$$';
  return true;
}

function mathPlugin(md) {
  md.inline.ruler.before('escape', 'math_paren', mathInlineParen);
  md.inline.ruler.after('escape', 'math_dollar', mathInlineDollar);
  md.block.ruler.before('fence', 'math_block', mathBlock, { alt: ['paragraph', 'reference', 'blockquote', 'list'] });
  // KaTeX 는 output:'html' 이라 원래 TeX 이 화면에 남지 않는다. 우클릭 메뉴의 'LaTeX 복사'용으로 data-tex 에 둔다
  const tex = (t) => ` data-tex="${md.utils.escapeHtml(t.trim())}"`;
  md.renderer.rules.math_inline = (tokens, i) => (
    `<span class="math-inline"${tex(tokens[i].content)}>${renderTex(tokens[i].content, false)}</span>`);
  md.renderer.rules.math_display_inline = (tokens, i) => (
    `<span class="math-display"${tex(tokens[i].content)}>${renderTex(tokens[i].content, true)}</span>`);
  md.renderer.rules.math_block = (tokens, i, options, env, self) => (
    `<div class="math-block"${tex(tokens[i].content)}${self.renderAttrs(tokens[i])}>${renderTex(tokens[i].content, true)}</div>\n`);
  const fence = md.renderer.rules.fence;
  md.renderer.rules.fence = (tokens, i, options, env, self) => {
    const t = tokens[i];
    const m = TEX_FENCES.has(t.info.trim().split(/\s+/)[0].toLowerCase()) && fenceTex(t.content);
    return m ? `<div class="math-block"${tex(m.tex)}${self.renderAttrs(t)}>${m.html}</div>\n` : fence(tokens, i, options, env, self);
  };
}

/**
 * 블록마다 원문 줄 범위를 data-lines="시작-끝"(1부터, 끝 줄 포함)으로 단다.
 * 본문 우클릭 메뉴(docmenu.js)의 원문 복사·Claude용 위치 복사가 쓴다. env.lineOffset 은 떼어 낸 frontmatter 줄 수.
 */
function sourceLines(md) {
  md.core.ruler.push('source_lines', (state) => {
    const offset = state.env.lineOffset || 0;
    for (const t of state.tokens) {
      if (t.block && t.map && t.nesting !== -1) t.attrSet('data-lines', `${t.map[0] + 1 + offset}-${t.map[1] + offset}`);
    }
  });
}

/**
 * 문서 안의 목차 줄 (D121): 맨 바깥의 '[목차]'·'[표 목차]'·'[그림 목차]' 한 줄 단락을 빈 <nav class="lec-doctoc"> 로 바꾼다 — 채우는 것은 doc.js.
 * Lectern 슬라이드에서는 하지 않는다
 */
function docMarks(state) {
  if (state.env.deck) return;
  const offset = state.env.lineOffset || 0;
  const toks = state.tokens;
  for (let i = 0; i + 2 < toks.length; i++) {
    const open = toks[i];
    if (open.type !== 'paragraph_open' || open.level !== 0 || !open.map || toks[i + 1].type !== 'inline' || toks[i + 2].type !== 'paragraph_close') continue;
    const kind = tocKind(toks[i + 1].content);
    if (!kind) continue;
    const tok = new state.Token('html_block', '', 0);
    tok.block = true;
    tok.map = open.map;
    tok.content = `<nav class="lec-doctoc" data-toc="${kind}" data-lines="${open.map[0] + 1 + offset}-${open.map[1] + offset}"></nav>\n`;
    toks.splice(i, 3, tok);
  }
}

// ---------------------------------------------------------------------------

function create(math, breaks) {
  const md = window.markdownit({ html: true, linkify: true, typographer: false, breaks, highlight });
  // 기본값은 file: 링크를 글자로 남긴다. 프로젝트 안의 file:///C:/... 는 doc.js 가 상대경로로 바꾸고 밖은 막으므로 허용한다 (2-2)
  const validate = md.validateLink;
  md.validateLink = (url) => /^\s*file:/i.test(url) || validate(url);
  md.use(window.markdownitFootnote)
    .use(window.markdownitTaskLists, { enabled: false })
    .use(window.markdownItAnchor, { slugify, tabIndex: false });
  if (math) md.use(mathPlugin);
  md.use(sourceLines);
  md.core.ruler.push('lec_doc_marks', docMarks);   // 문서 안 목차 줄 (D121) — source_lines 뒤에 (줄 범위는 스스로 단다)
  // 쪽 나눔 줄 (D121): 화면에는 점선과 '쪽 나눔', 인쇄에서는 쪽이 바뀐다 (base.css). 다른 뷰어에서는 빈 div 라 보이지 않는다
  const htmlBlock = md.renderer.rules.html_block;
  md.renderer.rules.html_block = (tokens, i, options, env, self) => (!env.deck && isPageBreak(tokens[i].content)
    ? `<div class="lec-pagebreak" role="separator"${self.renderAttrs(tokens[i])}><span>${md.utils.escapeHtml(t('쪽 나눔'))}</span></div>\n`
    : htmlBlock(tokens, i, options, env, self));
  md.block.ruler.before('fence', 'lec_cell', cellRule, { alt: ['paragraph', 'reference', 'blockquote', 'list'] });   // 슬라이드의 칸 ::: 이름
  md.core.ruler.push('lec_slides', slideRule);   // Lectern 슬라이드면 줄(---)마다 슬라이드로 (slides.js, D59 — env.deck 이 있을 때만)

  // ```mermaid 와 차트(```vega-lite·```vega·```echarts·```dot — charts.js, D56)는 코드 하이라이트 대신 다이어그램 자리표시로
  const fence = md.renderer.rules.fence;
  md.renderer.rules.fence = (tokens, idx, options, env, self) => {
    const lang = tokens[idx].info.trim().split(/\s+/)[0].toLowerCase();
    const body = md.utils.escapeHtml(tokens[idx].content);
    if (lang === 'mermaid') return `<pre class="mermaid"${self.renderAttrs(tokens[idx])}>${body}</pre>\n`;
    if (CHART_LANGS[lang]) return `<pre class="lec-chart" data-chart="${CHART_LANGS[lang]}"${self.renderAttrs(tokens[idx])}>${body}</pre>\n`;
    return fence(tokens, idx, options, env, self);
  };
  return md;
}

/** 맨 앞의 YAML frontmatter(--- ... ---)를 떼어 낸다. lineOffset 은 떼어 낸 줄 수. */
export function splitFrontMatter(text) {
  const m = /^﻿?---[ \t]*\r?\n([\s\S]*?)\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|$)/.exec(text);
  if (!m) return { frontMatter: null, body: text, lineOffset: 0 };
  return { frontMatter: m[1], body: text.slice(m[0].length), lineOffset: (m[0].match(/\n/g) || []).length };
}

/** deck: Lectern 슬라이드의 설정 (slides.js 의 readDeck) — 있으면 슬라이드로 감싸 그린다 */
export function renderMarkdown(text, { math = true, deck = null, cells = false } = {}) {
  const { frontMatter, body, lineOffset } = splitFrontMatter(text);
  const breaks = S.config?.md_breaks !== false;   // 문단 안의 줄바꿈 (D93 — Word 의 Shift+Enter 처럼 보인다)
  const key = `${math ? 'math' : 'plain'}-${breaks}`;
  if (!instances.has(key)) instances.set(key, create(math, breaks));
  return { html: instances.get(key).render(body, { lineOffset, deck, cells }), frontMatter };
}
