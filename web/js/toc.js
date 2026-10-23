// 오른쪽 목차와 '지금 읽는 위치' 표시. 선택된 탭의 문서를 따른다 (목차는 칸마다 남겨 두고 탭을 고르면 그 칸의 것을 보인다)
//
// 제목 아래에는 그 절의 구성 요소 — 표·그림·박스글·다이어그램·코드·수식 — 를 문서 순서대로 함께 보인다 (D39).
// 누르면 그 자리로 가서(접힌 절은 편다) 잠깐 테두리로 표시한다. 목차 머리의 종류 버튼으로 종류마다 보이고 감춘다
// (설정 toc_hidden_parts — 감춘 종류를 적어 두므로 새 종류는 처음부터 보인다). 번호(표 1, 표 2 …)는 감춘 것과 상관없이 문서 순서다.

import { S, on } from './store.js';
import { saveConfig } from './api.js';
import { unfoldTo } from './fold.js';
import { $, $$, esc, screenRect } from './util.js';

let heads = [];   // 목차의 제목들 (지금 읽는 위치 표시는 제목만)
let links = [];   // heads 와 같은 순서의 목차 링크
let parts = [];   // 목차에 보이는 구성 요소 (링크의 data-c 순번)
let active = -1;
let raf = 0;

/** 터미널(terminal.js)을 열면 목차를 감춘다 — 본문 폭이 모자라므로. 그동안 목차 버튼은 목차를 함께 보일지만 바꾼다 */
const root = document.documentElement;
const hiddenByTerminal = () => root.classList.contains('term-on') && !root.classList.contains('toc-with-term');

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
  box.innerHTML = `<p class="toc-head">목차</p><ul class="toc-list code-outline">${rows.map((r, i) => (
    `<li class="lv${Math.min(r.level, 3)} ok-${r.kind}"><a href="#" data-i="${i}" title="${esc(`${r.name} — ${r.line}행`)}">`
    + `<span class="ok" aria-hidden="true">${OUTLINE_MARK[r.kind] || '·'}</span>${esc(r.name)}</a></li>`
  )).join('')}</ul>`;
  links = $$('a[data-i]', box);
  active = -1;
  spy();
  updateTocVisibility();
}

// ---- 구성 요소 ------------------------------------------------------------------

// 종류: 이름(머리 버튼·번호), 아이콘(index.html 의 기호). 머리 버튼은 이 순서 (모아 보기 parts.js 도 이 표를 쓴다)
export const PARTS = {
  table: { name: '표', icon: 'i-table' },
  figure: { name: '그림', icon: 'i-image' },
  box: { name: '박스글', icon: 'i-box' },
  diagram: { name: '다이어그램', icon: 'i-diagram' },
  code: { name: '코드', icon: 'i-code' },
  math: { name: '수식', icon: 'i-math' },
};
// md(doc.js 가 꾸민 것)와 html 문서의 후보. 박스글은 인용·콜아웃과 html 의 aside·callout 류
const BOXES = 'blockquote, aside, [role="note"], .callout, .admonition';
// .image-off: 불러오지 못한 그림 자리(doc.js) — 화면 밖에서 센 모아 보기와 번호가 같게 그림으로 센다
const CANDIDATES = `table, img, .image-off, figure, ${BOXES}, .code-block, pre, .math-block, .mermaid-error`;
const HEADS = 'h1[id], h2[id], h3[id], h4[id]';

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
  if (el.matches('pre.mermaid, .mermaid-error')) return 'diagram';
  if (el.matches('.code-block')) return 'code';
  if (tag === 'PRE') return el.closest('.code-block, .mermaid-error, .math-block') ? null : 'code';   // html 문서의 코드
  if (el.matches('.math-block')) return 'math';
  return null;
}

const squeeze = (s) => String(s ?? '').replace(/\s+/g, ' ').trim();
const clip = (s, n = 44) => { const t = squeeze(s); return t.length > n ? `${t.slice(0, n - 1)}…` : t; };
const CAPTION = /^(?:표|그림|table|fig(?:ure)?\.?|tab\.)\s*[\d.-]+\s*[.:)]?\s*/i;

/** 표·그림 바로 앞(뒤)의 짧은 단락이 '표 1. …'처럼 시작하거나 통째로 굵게·기울여 쓴 글이면 그것을 이름으로 본다 */
function captionNear(el, next = false) {
  const p = next ? el.nextElementSibling : el.previousElementSibling;
  if (!p || p.tagName !== 'P') return '';
  const text = squeeze(p.textContent);
  if (!text || text.length > 90) return '';
  const only = p.children.length === 1 && /^(STRONG|B|EM|I)$/.test(p.firstElementChild.tagName) && squeeze(p.firstElementChild.textContent) === text;
  return CAPTION.test(text) || only ? text.replace(CAPTION, '') : '';
}

function tableLabel(table) {
  const rows = table.tBodies[0]?.rows.length ?? table.rows.length;
  const cols = Math.max(0, ...[...table.rows].map((r) => r.cells.length));
  const name = squeeze(table.caption?.textContent) || captionNear(table.closest('.table-wrap') || table)
    || [...(table.tHead?.rows[0] || table.rows[0])?.cells || []].slice(0, 3).map((c) => squeeze(c.textContent)).filter(Boolean).join('·');
  return [clip(name, 32), `${rows}행 ${cols}열`].filter(Boolean).join(' · ');
}

function figureLabel(el) {
  if (el.tagName === 'FIGURE') return clip(el.querySelector('figcaption')?.textContent || el.querySelector('img')?.alt);
  if (el.classList.contains('image-off')) return clip(el.textContent);
  const holder = el.parentElement?.tagName === 'P' && squeeze(el.parentElement.textContent) === '' ? el.parentElement : null;
  const src = el.getAttribute('src') || el.dataset.src || '';
  let file = src.split(/[?#]/)[0].split(/[/\\]/).pop() || '';
  try { file = decodeURIComponent(file); } catch { /* 그대로 */ }
  return clip(el.alt || el.title || (holder && captionNear(holder, true)) || file);
}

function boxLabel(el) {
  const title = squeeze(el.querySelector(':scope > .alert-title')?.textContent);
  const text = [...el.children].filter((c) => !c.classList.contains('alert-title')).map((c) => c.textContent).join(' ') || el.textContent;
  return { name: title || (el.tagName === 'BLOCKQUOTE' ? '인용' : '박스글'), label: clip(text, 40) };
}

const DIAGRAMS = {
  flowchart: '흐름도', graph: '흐름도', sequenceDiagram: '시퀀스', classDiagram: '클래스', stateDiagram: '상태', 'stateDiagram-v2': '상태',
  erDiagram: 'ER', gantt: '간트', pie: '원그래프', mindmap: '마인드맵', timeline: '타임라인', journey: '여정', gitGraph: 'Git',
  quadrantChart: '사분면', 'xychart-beta': '차트', 'sankey-beta': '흐름량', 'block-beta': '블록', requirementDiagram: '요구사항',
};

function diagramLabel(el) {
  const src = el.dataset.source ?? el.querySelector('pre')?.textContent ?? el.textContent;   // mermaid.js 가 원문을 data-source 에 둔다
  const body = src.replace(/^\s*---[\s\S]*?---\s*/, '').replace(/^(\s*%%.*\n)+/, '');
  const word = /^\s*([\w-]+)/.exec(body)?.[1] || '';
  const title = /^\s*title:?\s+(.+)$/m.exec(src)?.[1] || /\["?([^\]"]+)"?\]|\(\(?"?([^)"]+)"?\)|\{"?([^}"]+)"?\}/.exec(body)?.slice(1).find(Boolean);
  return [DIAGRAMS[word] || word, clip(title, 30)].filter(Boolean).join(' · ');
}

function codeLabel(el) {
  const lang = squeeze(el.querySelector('.code-lang')?.textContent);
  const code = (el.matches('pre') ? el : el.querySelector('pre'))?.textContent || '';
  return [lang, clip(code.split('\n').find((l) => l.trim()), 36)].filter(Boolean).join(' · ');
}

/** 구성 요소 하나의 목차 글: {name(번호 붙인 이름), label} */
function describe(kind, el, n) {
  if (kind === 'box') return boxLabel(el);
  const name = `${PARTS[kind].name} ${n}`;
  if (kind === 'table') return { name, label: tableLabel(el) };
  if (kind === 'figure') return { name, label: figureLabel(el) };
  if (kind === 'diagram') return { name, label: diagramLabel(el) };
  if (kind === 'code') return { name, label: codeLabel(el) };
  return { name, label: clip(el.dataset.tex || el.textContent, 36) };   // 수식: TeX 원문 (markdown.js 의 data-tex)
}

const hiddenParts = () => new Set(Array.isArray(S.config.toc_hidden_parts) ? S.config.toc_hidden_parts : []);

// ---- 목차 그리기 ------------------------------------------------------------------

const INDENT = [10, 22, 34, 44];   // 제목 수준별 왼쪽 여백 (app.css 의 .lv1~3 과 같게)

/**
 * 문서(root — 칸의 본문, html 문서의 body, 화면 밖에서 그린 조각)의 제목과 구성 요소를 문서 순서로 읽는다.
 * {listed: 목차에 넣을 제목들, rows: [{head} | {kind, el, n(종류별 번호), name, label, section(바로 앞 제목)}], counts: 종류별 개수}.
 * 모아 보기(parts.js)도 이것으로 세고 이것으로 찾아가므로 목차와 번호·이름이 같다.
 */
export function readParts(root) {
  const all = $$(HEADS, root).filter((h) => !h.closest('.front-matter, .footnotes'));
  const h1s = all.filter((h) => h.tagName === 'H1');
  const title = h1s.length === 1 ? h1s[0] : null;   // 문서 제목(H1 하나)은 목차에서 뺀다
  const listed = new Set(title ? all.filter((h) => h !== title) : all);
  const counts = {};
  const rows = [];
  let section = '';
  for (const el of $$(`h1, h2, h3, h4, ${CANDIDATES}`, root)) {
    if (/^H[1-4]$/.test(el.tagName)) {   // id 가 없는 제목(html 문서를 화면 밖에서 읽을 때)도 절 이름으로는 쓴다
      if (el !== title && !el.closest('.front-matter, .footnotes')) section = squeeze(el.textContent);
      if (listed.has(el)) rows.push({ head: el });
      continue;
    }
    const kind = partKind(el);
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
    return `<button type="button" data-part="${k}" aria-pressed="${on}" title="${on ? `목차에서 ${esc(PARTS[k].name)} 감추기` : `목차에 ${esc(PARTS[k].name)} 보이기`}">`
      + `<svg aria-hidden="true"><use href="#${PARTS[k].icon}"/></svg>${esc(PARTS[k].name)} ${counts[k]}</button>`;
  }).join('');
  box.innerHTML = `<p class="toc-head">목차</p>${buttons ? `<div class="toc-parts" role="group" aria-label="목차에 보일 구성 요소">${buttons}</div>` : ''}`
    + `<ul class="toc-list">${items}</ul>`;
  links = $$('a[data-i]', box);
  active = -1;
  spy();
  updateTocVisibility();
}

function spy() {
  raf = 0;
  if (!heads.length) return;
  const content = $('#lec-content');
  const limit = content.getBoundingClientRect().top + 96;
  let idx = 0;
  const shown = (h) => !h.classList.contains('lec-fold-hidden');   // 접힌 절 안의 제목은 위치가 0이다
  for (let i = 0; i < heads.length; i++) {
    if (!shown(heads[i])) continue;
    if (screenRect(heads[i]).top <= limit) idx = i;   // html 문서(iframe) 안의 제목도 화면 좌표로
    else break;
  }
  // 문서 끝까지 내려오면 마지막 절들은 위로 올라갈 수 없으므로, 화면에 보이는 마지막 제목을 현재 위치로 본다
  if (content.scrollTop + content.clientHeight >= content.scrollHeight - 4) {
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

/** 구성 요소로 간다: 접힌 절을 펴고, 크면 위를 맞추고 작으면 가운데로, 잠깐 테두리로 표시 (base.css·frame.css 의 lec-target) */
export function goToPart(el) {
  const target = el.closest('.table-wrap') || el;
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
    if (!h) return;
    if (h.classList.contains('cv-line')) {   // 코드 화면: 그 줄을 위에 두고 잠깐 표시
      h.scrollIntoView({ block: 'start' });
      h.classList.remove('lec-target');
      void h.offsetWidth;
      h.classList.add('lec-target');
      setTimeout(() => h.classList.remove('lec-target'), 1800);
      return;
    }
    unfoldTo(h);
    h.scrollIntoView({ block: 'start' });
  });
}
