// 오른쪽 목차와 '지금 읽는 위치' 표시. 선택된 탭의 문서를 따른다 (목차는 칸마다 남겨 두고 탭을 고르면 그 칸의 것을 보인다)
//
// 제목 아래에는 그 절의 구성 요소 — 표·그림·박스글·다이어그램·코드·수식 — 를 문서 순서대로 함께 보인다 (D39).
// 누르면 그 자리로 가서(접힌 절은 편다) 잠깐 테두리로 표시한다. 목차 머리의 종류 버튼으로 종류마다 보이고 감춘다
// (설정 toc_hidden_parts — 감춘 종류를 적어 두므로 새 종류는 처음부터 보인다). 번호(표 1, 표 2 …)는 감춘 것과 상관없이 문서 순서다.
// 편집 모드(D55)에서는 '지금 읽는 위치'가 편집기의 지금 보는 곳을 따르고, 목차를 누르면 편집기가 그 줄로 간다 (editor.js).

import { S, on } from './store.js';
import { saveConfig } from './api.js';
import { unfoldTo } from './fold.js';
import { chartLabel } from './charts.js';
import { $, $$, esc, screenRect } from './util.js';
import { t } from './i18n.js';

let heads = [];   // 목차의 제목들 (지금 읽는 위치 표시는 제목만)
let links = [];   // heads 와 같은 순서의 목차 링크
let parts = [];   // 목차에 보이는 구성 요소 (링크의 data-c 순번)
let active = -1;
let raf = 0;
let editJump = null;   // 편집 중이면 목차·모아 보기에서 고른 곳으로 편집기를 옮기는 함수 (editor.js, D55) — 옮겼으면 true

/** 편집 모드가 목차의 이동을 받는다 (editor.js) */
export function setEditJump(fn) {
  editJump = fn;
}

/** 터미널(terminal.js)을 열면 목차를 감춘다 — 본문 폭이 모자라므로. 그동안 목차 버튼은 목차를 함께 보일지만 바꾼다 */
const root = document.documentElement;
// 오른쪽 터미널은 목차 자리를 쓴다 (목차 버튼으로 함께 볼 수 있다 — toc-with-term). 아래에 둔 터미널(D52)은 목차를 가리지 않는다
const hiddenByTerminal = () => root.classList.contains('term-on') && !root.classList.contains('term-bottom') && !root.classList.contains('toc-with-term');

export function updateTocVisibility() {
  const has = !!$('#lec-toc').firstChild;
  const show = S.config.toc_visible !== false && has && !hiddenByTerminal();
  root.classList.toggle('toc-off', !show);
  const on = S.config.toc_visible !== false && !hiddenByTerminal();
  $('#lec-btn-toc').classList.toggle('on', on);
  $('#lec-btn-toc').setAttribute('aria-pressed', String(on));
}

export function clearToc() {
  heads = [];
  links = [];
  parts = [];
  active = -1;
  $('#lec-toc').innerHTML = '';
  updateTocVisibility();
}

/**
 * 칸(pane)의 목차를 정한다 (root: 제목을 찾을 곳, 없으면 null). 선택된 칸이면 바로 다시 그린다.
 * outline: 코드 화면의 목차 [{line, level, name, kind}] (codeview.js·outline.js) — 있으면 제목 대신 이것으로 (줄은 root 의 .cv-line)
 */
export function setToc(pane, root, outline = null) {
  pane.tocRoot = root;
  pane.tocOutline = outline;
  if (pane === S.pane) showPaneToc(pane);
}

const showPaneToc = (pane) => {
  if (!pane.tocRoot) clearToc();
  else if (pane.tocOutline) buildOutline(pane.tocRoot, pane.tocOutline);
  else buildToc(pane.tocRoot);
};

// 코드 목차의 종류 표시: 구분 주석·영역, 클래스, 형식, 함수, 메서드, 키, 선택자, 제목, 이름표
const OUTLINE_MARK = { section: '§', class: 'C', type: 'T', function: 'ƒ', method: 'ƒ', key: '·', selector: '#', heading: 'H', label: ':' };

/** 코드 화면의 목차: 지금 읽는 위치도 제목처럼 표시한다 (heads = 그 줄들) */
function buildOutline(view, items) {
  const rows = items.map((it) => ({ ...it, el: view.querySelector(`.cv-line[data-line="${it.line}"]`) })).filter((r) => r.el);
  if (!rows.length) {
    clearToc();
    return;
  }
  heads = rows.map((r) => r.el);
  parts = [];
  const box = $('#lec-toc');
  box.innerHTML = `<p class="toc-head">${t('목차')}</p><ul class="toc-list code-outline">${rows.map((r, i) => (
    `<li class="lv${Math.min(r.level, 3)} ok-${r.kind}"><a href="#" data-i="${i}" title="${esc(`${r.name} — ${t('{a}행', { a: r.line })}`)}">`
    + `<span class="ok" aria-hidden="true">${OUTLINE_MARK[r.kind] || '·'}</span>${esc(r.name)}</a></li>`
  )).join('')}</ul>`;
  links = $$('a[data-i]', box);
  active = -1;
  spy();
  updateTocVisibility();
}

// ---- 구성 요소 ------------------------------------------------------------------

// 종류: 이름(번호 — '표 3'), 여럿일 때 이름(머리 버튼 — 영어 복수형), 아이콘(index.html 의 기호). 머리 버튼은 이 순서 (모아 보기 parts.js 도 이 표를 쓴다).
// more: 모아 보기에서만 (목차에는 넣지 않는다 — 할 일·링크·출처는 많고 절 아래에 늘어놓으면 목차가 붐빈다, D62)
export const PARTS = {
  table: { name: t('표'), many: t('표', { n: 2 }), icon: 'i-table' },
  figure: { name: t('그림'), many: t('그림', { n: 2 }), icon: 'i-image' },
  chart: { name: t('차트'), many: t('차트', { n: 2 }), icon: 'i-chart' },
  box: { name: t('박스글'), many: t('박스글', { n: 2 }), icon: 'i-box' },
  diagram: { name: t('다이어그램'), many: t('다이어그램', { n: 2 }), icon: 'i-diagram' },
  code: { name: t('코드'), many: t('코드', { n: 2 }), icon: 'i-code' },
  math: { name: t('수식'), many: t('수식', { n: 2 }), icon: 'i-math' },
  task: { name: t('할 일'), many: t('할 일', { n: 2 }), icon: 'i-task', more: true },
  link: { name: t('링크'), many: t('링크', { n: 2 }), icon: 'i-link', more: true },
  source: { name: t('출처'), many: t('출처', { n: 2 }), icon: 'i-source', more: true },
};
// md(doc.js 가 꾸민 것)와 html 문서의 후보. 박스글은 인용·콜아웃과 html 의 aside·callout 류
const BOXES = 'blockquote, aside, [role="note"], .callout, .admonition';
// .image-off: 불러오지 못한 그림 자리(doc.js) — 화면 밖에서 센 모아 보기와 번호가 같게 그림으로 센다
const CANDIDATES = `table, img, .image-off, figure, ${BOXES}, .code-block, pre, .math-block, .diagram-error`;
const MORE_CANDIDATES = 'li, a[href], p';   // 할 일·링크·출처 (모아 보기)
const HEADS = 'h1[id], h2[id], h3[id], h4[id]';
// 출처 단락: '자료: …', '출처: …', '※ 자료: …', 'Source: …' (표·그림 아래에 흔하다)
const SOURCE = /^[\s※*·•\-]*[(\[]?\s*(?:자료|출처|원자료|원문|source|sources|data source)\s*[)\]]?\s*[:：]/i;
const CHART_LIBS = new Set(['vega-lite', 'vega', 'echarts', 'plotly']);   // Graphviz(dot)는 다이어그램

/** 모아 보기만의 종류 (할 일·링크·출처) — 아니면 null */
function moreKind(el) {
  // 다이어그램·차트 안(그린 SVG 의 링크, Mermaid 상자 글의 p)은 세지 않는다 — 화면 밖에서는 그리지 않아 원문뿐이라 번호가 어긋난다
  if (el.closest('.front-matter, h1, h2, h3, h4, h5, h6, svg, pre.mermaid, pre.lec-chart, .diagram-error')) return null;
  const tag = el.tagName;
  if (tag === 'LI') {
    if (el.closest('.footnotes')) return el.parentElement?.closest('li') ? null : 'source';   // 각주
    return el.classList.contains('task-list-item') || el.querySelector(':scope > input[type="checkbox"], :scope > p > input[type="checkbox"]') ? 'task' : null;
  }
  if (tag === 'A') {
    const href = el.getAttribute('href') || '';
    if (el.closest('.footnotes, .footnote-ref') || el.classList.contains('footnote-backref')) return null;
    if (el.classList.contains('path-link')) return 'link';   // 본문 속 경로 표기 (pathlink.js)
    return href && !href.startsWith('#') ? 'link' : null;   // 문서 안 앵커는 빼고
  }
  if (tag === 'P' && !el.closest('.footnotes, li, td, th') && SOURCE.test(squeeze(el.textContent))) return 'source';
  return null;
}

/** 목차에 넣을 구성 요소면 그 종류, 아니면 null */
function partKind(el) {
  if (el.closest('.front-matter, .footnotes, h1, h2, h3, h4, h5, h6')) return null;
  const tag = el.tagName;
  if (tag === 'TABLE') return 'table';
  if (tag === 'FIGURE') return 'figure';
  if (tag === 'IMG' || el.classList.contains('image-off')) {
    if (el.closest('figure, table')) return null;   // 그림 틀·표 안의 그림은 그 틀·표로
    // 아이콘: 크기 속성으로만 본다 (불러온 크기로 보면 불러오기 전에 센 모아 보기와 번호가 어긋난다)
    const w = Number(el.getAttribute('width')) || 0;
    const h = Number(el.getAttribute('height')) || 0;
    if (w && h && w < 32 && h < 32) return null;
    return 'figure';
  }
  if (el.matches(BOXES)) return el.parentElement?.closest(BOXES) ? null : 'box';   // 박스 안의 박스는 바깥 것만
  if (el.matches('pre.lec-chart, .diagram-error[data-chart]')) return CHART_LIBS.has(el.dataset.chart) ? 'chart' : 'diagram';   // 차트 (D56·D62)
  if (el.matches('pre.mermaid, .diagram-error')) return 'diagram';
  if (el.matches('.code-block')) return 'code';
  if (tag === 'PRE') return el.closest('.code-block, .diagram-error, .math-block') ? null : 'code';   // html 문서의 코드
  if (el.matches('.math-block')) return 'math';
  return null;
}

const squeeze = (s) => String(s ?? '').replace(/\s+/g, ' ').trim();
const clip = (s, n = 44) => { const text = squeeze(s); return text.length > n ? `${text.slice(0, n - 1)}…` : text; };
// 캡션 단락의 머리: '표 1.' '<표 1>' '[그림 2]' '〈표 Ⅱ-15〉' '표 3-1' 'Table 2:' 'Fig. 3' … (번호는 숫자·로마 숫자, - 나 . 로 이음)
const CAPTION = /^[<[〈《(（【]?\s*(?:표|그림|도표|차트|사진|다이어그램|코드|예시|table|tab\.|fig(?:ure)?\.?|chart|diagram|listing|code)\s*[\dⅠ-Ⅻ]+(?:\s*[.\-–]\s*[\dⅠ-Ⅻ]+)*\s*[>\]〉》)）】]?\s*[.:)]?\s*/i;

// 캡션 머리의 낱말이 말하는 종류 — 표 캡션은 표만, 그림 캡션은 그림·다이어그램만 가져간다
const CAPTION_WORD = [[/^[<[〈《(（【]?\s*(?:표|table|tab\.)/i, 'table'], [/^[<[〈《(（【]?\s*(?:코드|예시|listing|code)/i, 'code'],
  [/^[<[〈《(（【]?\s*(?:그림|도표|차트|사진|다이어그램|fig|chart|diagram)/i, 'figure']];
const wordKind = (text) => (CAPTION.test(text) ? CAPTION_WORD.find(([re]) => re.test(text))?.[1] : null) || null;
const fits = (word, kind) => !word || word === (kind === 'diagram' || kind === 'chart' ? 'figure' : kind);

/** node 가 구성 요소를 담은 것이면 그 종류 (캡션 단락이 앞뒤 어느 요소의 것인지 가를 때) */
function holderKind(node) {
  if (!node) return null;
  if (node.tagName === 'P' && node.querySelector('img, .image-off') && squeeze(node.textContent) === '') return 'figure';
  if (node.tagName === 'FIGURE') return 'figure';
  if (node.matches?.('.table-wrap') || node.tagName === 'TABLE') return 'table';
  if (node.matches?.('pre.mermaid, pre.lec-chart, .diagram-error')) return 'diagram';
  if (node.matches?.('.code-block')) return 'code';
  return null;
}


/**
 * el(표 상자·그림 단락·다이어그램·코드 상자) 바로 앞(before)이나 뒤(after)의 캡션 단락: {text(쓴 그대로), short(머리 번호를 뗀 것), el} 또는 null.
 * 'any' 면 '표 1. …'처럼 번호로 시작하거나 통째로 굵게·기울여 쓴 짧은 단락('**〈표 Ⅱ-15〉 철재의 HS코드**'), 'numbered' 면 번호로 시작하는 것만.
 * 머리 낱말이 다른 종류를 말하면('그림 1.' 을 표가) 가져가지 않는다. 두 요소 사이의 캡션은 관례대로 — 그림 뒤면 그 그림의 것(그림은 아래 캡션),
 * 표·다이어그램·코드 앞이면 그것의 것(위 캡션)
 */
function captionPara(el, kind, { before = null, after = null, afterFirst = false } = {}) {
  const pick = (p, mode, side) => {
    if (!mode || !p || p.tagName !== 'P') return null;
    const text = squeeze(p.textContent);
    if (!text || text.length > 90) return null;
    const only = p.children.length === 1 && /^(STRONG|B|EM|I)$/.test(p.firstElementChild.tagName) && squeeze(p.firstElementChild.textContent) === text;
    if (!CAPTION.test(text) && !(mode === 'any' && only)) return null;
    if (!fits(wordKind(text), kind)) return null;
    const word = wordKind(text);
    if (side === 'before' && holderKind(p.previousElementSibling) === 'figure' && fits(word, 'figure')) return null;   // 앞 그림의 아래 캡션
    if (side === 'after') {
      const next = holderKind(p.nextElementSibling);
      if (next && next !== 'figure' && fits(word, next)) return null;   // 뒤 표·다이어그램·코드의 위 캡션
    }
    return { text, short: text.replace(CAPTION, '') || text, el: p };
  };
  const a = () => pick(el.previousElementSibling, before, 'before');
  const b = () => pick(el.nextElementSibling, after, 'after');
  return afterFirst ? b() || a() : a() || b();
}

const captionTag = (node) => {   // <caption>·<figcaption>
  const text = squeeze(node?.textContent);
  return text ? { text, short: text.replace(CAPTION, '') || text, el: node } : null;
};

/** 혼자 든 단락 (그림의 캡션은 그 단락의 앞뒤에서 찾는다) */
const loneHolder = (el) => (el.parentElement?.tagName === 'P' && squeeze(el.parentElement.textContent) === '' ? el.parentElement : null);

/** 구성 요소의 캡션 (모아 보기는 이것을 이름으로 — D61). 표는 위, 그림은 아래가 먼저. 박스글·수식은 없다 */
export function captionOf(kind, el) {
  if (kind === 'table') return captionTag(el.caption) || captionPara(el.closest('.table-wrap') || el, kind, { before: 'any', after: 'numbered' });
  if (kind === 'figure') {
    if (el.tagName === 'FIGURE') return captionTag(el.querySelector('figcaption'));
    const holder = loneHolder(el);
    return holder ? captionPara(holder, kind, { before: 'numbered', after: 'any', afterFirst: true }) : null;
  }
  if (kind === 'diagram' || kind === 'chart') return captionPara(el, kind, { before: 'any', after: 'numbered' });
  if (kind === 'code') return captionPara(el.closest('.code-block') || el, kind, { before: 'numbered', after: 'numbered' });
  return null;
}

/**
 * 구성 요소를 옮길 때 함께 갈 것 (담기 — D63): {kind, caption(글), label(목차의 이름표 — 'Vega-Lite · 제목'),
 * els: [캡션 단락, 요소, 바로 뒤의 출처 단락('자료: …')] 가운데 있는 것}. 구성 요소가 아니면 {kind: null, caption: '', label: '', els: [el]}
 */
export function partExtent(el) {
  const kind = partKind(el);
  if (!kind || PARTS[kind].more) return { kind: null, caption: '', label: '', els: [el] };
  const { label = '' } = describe(kind, el, 0);
  const cap = captionOf(kind, el);
  const box = (kind === 'table' && el.closest('.table-wrap')) || (kind === 'figure' && loneHolder(el)) || (kind === 'code' && el.closest('.code-block')) || el;
  const last = cap && box.compareDocumentPosition(cap.el) & Node.DOCUMENT_POSITION_FOLLOWING ? cap.el : box;   // 아래 캡션이면 그 뒤
  const next = last.nextElementSibling;
  const source = next?.tagName === 'P' && SOURCE.test(squeeze(next.textContent)) ? next : null;
  return { kind, caption: cap?.text || '', label, els: [cap?.el, el, source].filter(Boolean) };
}

function tableLabel(table, cap) {
  const rows = table.tBodies[0]?.rows.length ?? table.rows.length;
  const cols = Math.max(0, ...[...table.rows].map((r) => r.cells.length));
  const size = t('{rows}행 {cols}열', { rows, cols });
  const name = cap?.short || [...(table.tHead?.rows[0] || table.rows[0])?.cells || []].slice(0, 3).map((c) => squeeze(c.textContent)).filter(Boolean).join('·');
  return { label: [clip(name, 32), size].filter(Boolean).join(' · '), detail: size };
}

function figureLabel(el, cap) {
  if (el.tagName === 'FIGURE') return clip(cap?.short || el.querySelector('img')?.alt);
  if (el.classList.contains('image-off')) return clip(cap?.short || el.textContent);
  const src = el.getAttribute('src') || el.dataset.src || '';
  let file = src.split(/[?#]/)[0].split(/[/\\]/).pop() || '';
  try { file = decodeURIComponent(file); } catch { /* 그대로 */ }
  return clip(cap?.short || el.alt || el.title || file);
}

function boxLabel(el) {
  const title = squeeze(el.querySelector(':scope > .alert-title')?.textContent);
  const text = [...el.children].filter((c) => !c.classList.contains('alert-title')).map((c) => c.textContent).join(' ') || el.textContent;
  return { name: title || (el.tagName === 'BLOCKQUOTE' ? t('인용') : t('박스글')), label: clip(text, 40) };
}

const DIAGRAMS = {
  flowchart: t('흐름도'), graph: t('흐름도'), sequenceDiagram: t('시퀀스'), classDiagram: t('클래스'), stateDiagram: t('상태'), 'stateDiagram-v2': t('상태'),
  erDiagram: 'ER', gantt: t('간트'), pie: t('원그래프'), mindmap: t('마인드맵'), timeline: t('타임라인'), journey: t('여정'), gitGraph: 'Git',
  quadrantChart: t('사분면'), 'xychart-beta': t('차트'), 'sankey-beta': t('흐름량'), 'block-beta': t('블록'), requirementDiagram: t('요구사항'),
};

function diagramLabel(el, cap) {
  const src = el.dataset.source ?? el.querySelector('pre')?.textContent ?? el.textContent;   // mermaid.js·charts.js 가 원문을 data-source 에 둔다
  if (el.dataset.chart) {   // 차트 (D56): 'Vega-Lite · 제목'
    const lib = chartLabel(el.dataset.chart, '');
    return { label: clip(cap ? `${lib} · ${cap.short}` : chartLabel(el.dataset.chart, src), 40), detail: lib };
  }
  const body = src.replace(/^\s*---[\s\S]*?---\s*/, '').replace(/^(\s*%%.*\n)+/, '');
  const word = /^\s*([\w-]+)/.exec(body)?.[1] || '';
  const title = cap?.short || /^\s*title:?\s+"?(.+?)"?\s*$/m.exec(src)?.[1] || /\["?([^\]"]+)"?\]|\(\(?"?([^)"]+)"?\)|\{"?([^}"]+)"?\}/.exec(body)?.slice(1).find(Boolean);
  return { label: [DIAGRAMS[word] || word, clip(title, 30)].filter(Boolean).join(' · '), detail: DIAGRAMS[word] || word };
}

/** 할 일: 그 항목의 글(안의 목록은 빼고)과 했는지 */
function taskInfo(li) {
  const box = li.querySelector(':scope > input[type="checkbox"], :scope > p > input[type="checkbox"]');
  const copy = li.cloneNode(true);
  for (const sub of copy.querySelectorAll('ul, ol')) sub.remove();
  return { text: squeeze(copy.textContent), done: !!box && (box.checked || box.hasAttribute('checked')) };
}

function codeLabel(el, cap) {
  const lang = squeeze(el.querySelector('.code-lang')?.textContent);
  const code = (el.matches('pre') ? el : el.querySelector('pre'))?.textContent || '';
  return { label: [lang, clip(cap?.short || code.split('\n').find((l) => l.trim()), 36)].filter(Boolean).join(' · '), detail: lang };
}

/**
 * 구성 요소 하나의 목차 글: {name(번호 붙인 이름), label, caption(캡션을 쓴 그대로 — 없으면 ''), detail(캡션과 함께 보일 크기·종류), capEl}.
 * 목차는 name·label 을, 모아 보기는 캡션이 있으면 caption 을 이름으로 쓴다 (D61)
 */
function describe(kind, el, n) {
  if (kind === 'box') return boxLabel(el);
  const name = `${PARTS[kind].name} ${n}`;
  // 모아 보기만의 종류: text 가 이름, label 이 그 아래 설명 (parts.js)
  if (kind === 'task') {
    const { text, done } = taskInfo(el);
    return { name, text, done, label: done ? t('한 것') : t('안 한 것') };
  }
  if (kind === 'link') {
    const text = squeeze(el.textContent) || el.getAttribute('href') || '';
    return { name, text, href: el.classList.contains('path-link') ? el.dataset.lecHref : el.getAttribute('href') || '', path: el.dataset.path || '' };
  }
  if (kind === 'source') {
    const note = el.tagName === 'LI';
    return { name: note ? `${t('각주')} ${squeeze(el.id).replace(/\D+/g, '') || n}` : name, text: squeeze(el.textContent).replace(/\s*↩︎?\s*$/, ''), note };
  }
  const cap = captionOf(kind, el);
  const more = { caption: cap?.text || '', capEl: cap?.el || null };
  if (kind === 'table') return { name, ...tableLabel(el, cap), ...more };
  if (kind === 'figure') return { name, label: figureLabel(el, cap), detail: '', ...more };
  if (kind === 'diagram' || kind === 'chart') return { name, ...diagramLabel(el, cap), ...more };
  if (kind === 'code') return { name, ...codeLabel(el, cap), ...more };
  return { name, label: clip(el.dataset.tex || el.textContent, 36) };   // 수식: TeX 원문 (markdown.js 의 data-tex)
}

const hiddenParts = () => new Set(Array.isArray(S.config.toc_hidden_parts) ? S.config.toc_hidden_parts : []);

// ---- 목차 그리기 ------------------------------------------------------------------

const INDENT = [10, 22, 34, 44];   // 제목 수준별 왼쪽 여백 (app.css 의 .lv1~3 과 같게)

/**
 * 문서(root — 칸의 본문, html 문서의 body, 화면 밖에서 그린 조각)의 제목과 구성 요소를 문서 순서로 읽는다.
 * {listed: 목차에 넣을 제목들, rows: [{head} | {kind, el, n(종류별 번호), name, label, section(바로 앞 제목)}], counts: 종류별 개수}.
 * 모아 보기(parts.js)도 이것으로 세고 이것으로 찾아가므로 목차와 번호·이름이 같다. more: 모아 보기만의 종류(할 일·링크·출처)도 센다 — 찾아갈 때도 같게.
 */
export function readParts(root, { more = false } = {}) {
  const all = $$(HEADS, root).filter((h) => !h.closest('.front-matter, .footnotes'));
  const h1s = all.filter((h) => h.tagName === 'H1');
  const title = h1s.length === 1 ? h1s[0] : null;   // 문서 제목(H1 하나)은 목차에서 뺀다
  const listed = new Set(title ? all.filter((h) => h !== title) : all);
  const counts = {};
  const rows = [];
  let section = '';
  for (const el of $$(`h1, h2, h3, h4, ${CANDIDATES}${more ? `, ${MORE_CANDIDATES}` : ''}`, root)) {
    if (/^H[1-4]$/.test(el.tagName)) {   // id 가 없는 제목(html 문서를 화면 밖에서 읽을 때)도 절 이름으로는 쓴다
      if (el !== title && !el.closest('.front-matter, .footnotes')) section = squeeze(el.textContent);
      if (listed.has(el)) rows.push({ head: el });
      continue;
    }
    const kind = partKind(el) || (more ? moreKind(el) : null);
    if (!kind) continue;
    counts[kind] = (counts[kind] || 0) + 1;
    rows.push({ kind, el, n: counts[kind], section, ...describe(kind, el, counts[kind]) });
  }
  return { listed, rows, counts };
}

function buildToc(view) {
  const { listed, rows, counts } = readParts(view);
  const top = Math.min(4, ...[...listed].map((h) => +h.tagName[1]));
  const hidden = hiddenParts();
  const box = $('#lec-toc');
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  if (listed.size < 2 && !total) {   // 목차로 보일 것이 없다
    clearToc();
    return;
  }
  heads = [];
  parts = [];
  let lv = -1;   // 바로 앞 제목의 수준 (첫 제목 앞이면 -1)
  const items = rows.map((r) => {
    if (r.head) {
      lv = +r.head.tagName[1] - top;
      heads.push(r.head);
      return `<li class="lv${lv}"><a href="#${esc(r.head.id)}" data-i="${heads.length - 1}">${esc(r.head.textContent.trim())}</a></li>`;
    }
    if (hidden.has(r.kind)) return '';
    parts.push(r.el);
    const pad = lv < 0 ? INDENT[0] : INDENT[Math.min(lv, 3)] + 14;
    const tip = [r.name, r.label].filter(Boolean).join(' · ');
    return `<li class="part part-${r.kind}"><a href="#" data-c="${parts.length - 1}" style="padding-left:${pad}px" title="${esc(tip)}">`
      + `<svg class="tp-icon" aria-hidden="true"><use href="#${PARTS[r.kind].icon}"/></svg>`
      + `<span class="tp-name">${esc(r.name)}</span>${r.label ? `<span class="tp-label">${esc(r.label)}</span>` : ''}</a></li>`;
  }).join('');
  const kinds = Object.keys(PARTS).filter((k) => counts[k]);
  const buttons = kinds.map((k) => {
    const on = !hidden.has(k);
    return `<button type="button" data-part="${k}" aria-pressed="${on}" title="${esc(on ? t('목차에서 {kind} 감추기', { kind: PARTS[k].many }) : t('목차에 {kind} 보이기', { kind: PARTS[k].many }))}">`
      + `<svg aria-hidden="true"><use href="#${PARTS[k].icon}"/></svg>${esc(counts[k] === 1 ? PARTS[k].name : PARTS[k].many)} ${counts[k]}</button>`;
  }).join('');
  box.innerHTML = `<p class="toc-head">${t('목차')}</p>${buttons ? `<div class="toc-parts" role="group" aria-label="${t('목차에 보일 구성 요소')}">${buttons}</div>` : ''}`
    + `<ul class="toc-list">${items}</ul>`;
  links = $$('a[data-i]', box);
  active = -1;
  spy();
  updateTocVisibility();
}

/** '지금 읽는 위치'를 다시 정한다 — 편집 모드가 편집기의 지금 보는 곳을 바꿀 때 (editor.js) */
export const updateTocActive = () => spy();

function spy() {
  raf = 0;
  if (!heads.length) return;
  const content = $('#lec-content');
  // 편집 중이면 편집기의 지금 보는 곳(커서 등 — 그 자리의 화면 좌표 pane.tocLimit, editor.js)이 든 절. 아니면 화면 위쪽의 절
  const editing = S.pane?.editor && S.pane.tocLimit != null;
  const limit = editing ? S.pane.tocLimit + 2 : content.getBoundingClientRect().top + 96;
  let idx = 0;
  const shown = (h) => !h.classList.contains('lec-fold-hidden');   // 접힌 절 안의 제목은 위치가 0이다
  for (let i = 0; i < heads.length; i++) {
    if (!shown(heads[i])) continue;
    if (screenRect(heads[i]).top <= limit) idx = i;   // html 문서(iframe) 안의 제목도 화면 좌표로
    else break;
  }
  // 문서 끝까지 내려오면 마지막 절들은 위로 올라갈 수 없으므로, 화면에 보이는 마지막 제목을 현재 위치로 본다
  if (!editing && content.scrollTop + content.clientHeight >= content.scrollHeight - 4) {
    const bottom = content.getBoundingClientRect().bottom;
    for (let i = heads.length - 1; i > idx; i--) {
      if (shown(heads[i]) && screenRect(heads[i]).top < bottom) { idx = i; break; }
    }
  }
  if (idx === active) return;
  links[active]?.classList.remove('active');
  links[idx]?.classList.add('active');
  active = idx;
  links[idx]?.scrollIntoView({ block: 'nearest' });
}

/** 구성 요소로 간다: 접힌 절을 펴고, 크면 위를 맞추고 작으면 가운데로, 잠깐 테두리로 표시 (base.css·frame.css 의 lec-target).
 * 편집 중이면 편집기가 그 줄로 간다 (모아 보기도 이것으로 간다) */
export function goToPart(el) {
  const target = el.closest('.table-wrap') || el;
  if (editJump?.(target)) return;
  unfoldTo(target);
  const tall = screenRect(target).height > $('#lec-content').clientHeight * 0.7;
  target.scrollIntoView({ block: tall ? 'start' : 'center' });
  target.classList.remove('lec-target');
  void target.offsetWidth;   // 같은 것을 다시 눌러도 처음부터 깜박이게
  target.classList.add('lec-target');
  clearTimeout(target.lecTargetTimer);
  target.lecTargetTimer = setTimeout(() => target.classList.remove('lec-target'), 1800);
}

async function togglePart(kind) {
  const hidden = hiddenParts();
  if (hidden.has(kind)) hidden.delete(kind);
  else hidden.add(kind);
  const list = Object.keys(PARTS).filter((k) => hidden.has(k));
  const scroll = $('#lec-toc').scrollTop;
  const p = saveConfig({ toc_hidden_parts: list });   // S.config 는 바로 바뀐다
  if (S.pane?.tocRoot) buildToc(S.pane.tocRoot);
  $('#lec-toc').scrollTop = scroll;
  $(`#lec-toc .toc-parts button[data-part="${kind}"]`)?.focus();
  await p;
}

export function initToc() {
  // 스크롤은 거품처럼 올라오지 않으므로 잡기 단계에서 듣는다. 선택된 칸(#lec-content)의 스크롤만
  document.addEventListener('scroll', (e) => {
    if (e.target === S.pane?.scroller && !raf) raf = requestAnimationFrame(spy);
  }, { capture: true, passive: true });
  on('pane', showPaneToc);
  $('#lec-toc').addEventListener('click', (e) => {
    const btn = e.target.closest('.toc-parts button[data-part]');
    if (btn) {
      togglePart(btn.dataset.part);
      return;
    }
    const part = e.target.closest('a[data-c]');
    if (part) {
      e.preventDefault();
      const el = parts[+part.dataset.c];
      if (el?.isConnected) goToPart(el);
      return;
    }
    const a = e.target.closest('a[data-i]');
    if (!a) return;
    e.preventDefault();
    const h = heads[+a.dataset.i];
    if (!h || editJump?.(h)) return;   // 편집 중이면 편집기가 그 제목(줄)으로
    if (h.classList.contains('cv-line')) {   // 코드 화면: 그 줄을 위에 두고 잠깐 표시
      h.scrollIntoView({ block: 'start' });
      h.classList.remove('lec-target');
      void h.offsetWidth;
      h.classList.add('lec-target');
      setTimeout(() => h.classList.remove('lec-target'), 1800);
      return;
    }
    unfoldTo(h);
    (h.closest('.lec-slide-wrap') || h).scrollIntoView({ block: 'start' });   // 발표 문서(D59)면 그 슬라이드째
  });
}
