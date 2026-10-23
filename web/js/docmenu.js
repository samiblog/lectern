// 문서 본문 우클릭 메뉴: 우클릭한 블록(제목·단락·목록 항목·표·그림·코드·다이어그램·수식)에 테두리를 그리고 복사 메뉴를 띄운다.
// 블록 밖(여백·문서 아래 빈 곳)을 누르면 문서 메뉴(경로 복사, 편집기로 열기, 모두 접기 등)를 띄운다.
//
// 원문 복사와 Claude용 위치 복사는 markdown.js 가 블록마다 단 data-lines(원문 줄 범위)를 쓴다.
// 코드 화면(codeview.js)에서는 줄 메뉴: 이 줄·고른 글 복사, Claude용 위치(@경로 12~20행), 편집기에서 이 줄 열기, 경로 복사, 전체 복사.
// 보기 전용: 클립보드에 복사하거나 다른 앱으로 열기만 하고, 파일을 만들거나 고치지 않는다 (D24).

import { S } from './store.js';
import { showMenu } from './ui.js';
import { pathMenuItems } from './tree.js';
import { foldAll, foldLevel, hasFolds } from './fold.js';
import { spotlightItems } from './spotlight.js';
import { openExternal } from './api.js';
import { $, esc, toast, copyText } from './util.js';

let doc = null;   // 메뉴를 띄운 탭의 문서 {path, lines}. 문서를 그리지 못했으면 null

/** doc.js·htmldoc.js 가 칸(pane)에 문서를 그릴 때마다 원문을 넘긴다 (문서 없음 화면이면 path 가 null). */
export function setDocSource(pane, path, text = '') {
  pane.source = path == null ? null : { path, lines: text.replace(/^﻿/, '').split(/\r\n?|\n/) };
}

// 우클릭으로 고르는 블록. 가장 안쪽 것을 고른다 (목록 항목 안의 단락이면 단락, 표의 칸이면 표)
const BLOCKS = 'img, pre.mermaid, .mermaid-error, .code-block, .math-block, table, h1, h2, h3, h4, h5, h6, li, p, dt, dd, blockquote';
const HEADING = /^H[1-6]$/;

function pickBlock(target, view) {
  // 다이어그램 글자(foreignObject 안의 <p>)나 메타데이터 표의 칸은 따로 고르지 않고 통째로 고른다
  const el = target.closest('.front-matter, pre.mermaid') || target.closest(BLOCKS);
  return el && el !== view && view.contains(el) ? el : null;
}

// ---- 원문 줄 범위 ------------------------------------------------------------

const isBlank = (n) => !doc.lines[n - 1]?.trim();

/** [시작, 끝] (1부터, 끝 포함). 끝의 빈 줄은 뺀다. */
function lineRange(el) {
  const holder = el.hasAttribute('data-lines') ? el
    : el.querySelector(':scope > [data-lines], :scope > pre > [data-lines]') || el.closest('[data-lines]');
  const m = /^(\d+)-(\d+)$/.exec(holder?.dataset.lines || '');
  if (!m) return null;
  let end = Math.min(+m[2], doc.lines.length);
  while (end > +m[1] && isBlank(end)) end -= 1;
  return [+m[1], end];
}

/** 제목부터 다음 같은 수준 이상의 제목 앞까지. 문서 끝까지 가면 맨 뒤의 각주 정의([^1]: ...)는 뺀다. */
function sectionRange(h) {
  const head = lineRange(h);
  if (!head) return null;
  const level = +h.tagName[1];
  let end = doc.lines.length;
  let toEnd = true;
  for (let el = h.nextElementSibling; el; el = el.nextElementSibling) {
    const next = HEADING.test(el.tagName) && +el.tagName[1] <= level && lineRange(el);
    if (next) {
      end = next[0] - 1;
      toEnd = false;
      break;
    }
  }
  while (end > head[0] && (isBlank(end) || (toEnd && /^\[\^[^\]]+\]:/.test(doc.lines[end - 1])))) end -= 1;
  return [head[0], end];
}

const rangeText = ([a, b]) => (a === b ? `${a}행` : `${a}~${b}행`);
const sourceOf = ([a, b]) => doc.lines.slice(a - 1, b).join('\n');
// Claude Code는 '@경로' 를 파일 전체로 붙인다. 줄 범위 표기(#L40-52)는 문서화되어 있지 않아 글로 적는다 (D24)
const claudeRef = (range, note = '') => `@${doc.path} ${rangeText(range)}${note}`;

// ---- 복사 --------------------------------------------------------------------

/** 메뉴 설명·알림에 쓸 짧은 표시: 한 줄이면 앞부분, 여러 줄이면 줄 수 */
function describe(text) {
  const n = text.split('\n').length;
  if (n > 1) return `${n}줄`;
  return text.length <= 40 ? text : `${text.slice(0, 40)}…`;
}

async function copyPlain(text, what = describe(text)) {
  toast(await copyText(text) ? `복사했습니다: ${what}` : '복사하지 못했습니다');
}

/** 여러 형식을 함께 클립보드에 넣는다. parts: {'text/plain', 'text/html', 'image/png'} */
async function copyParts(parts, what) {
  let ok = false;
  try {
    const data = {};
    for (const [type, value] of Object.entries(parts)) data[type] = typeof value === 'string' ? new Blob([value], { type }) : value;
    await navigator.clipboard.write([new ClipboardItem(data)]);
    ok = true;
  } catch {
    if (typeof parts['text/plain'] === 'string') ok = await copyText(parts['text/plain']);
  }
  toast(ok ? `복사했습니다: ${what}` : '복사하지 못했습니다');
}

/** 표 → 탭으로 나눈 글(엑셀이 칸으로 나눔)과 간단한 HTML 표(워드·메일이 표로 붙임) */
function tableData(table) {
  const rows = [...table.rows].map((r) => [...r.cells].map((c) => {
    const align = c.ownerDocument.defaultView.getComputedStyle(c).textAlign;
    return { text: c.innerText.replace(/\s+/g, ' ').trim(), head: c.tagName === 'TH', align: /right|center/.test(align) ? align : '' };
  }));
  const tsv = rows.map((r) => r.map((c) => c.text).join('\t')).join('\n');
  const html = `<table border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse">${rows.map((r) => `<tr>${r.map((c) => {
    const tag = c.head ? 'th' : 'td';
    return `<${tag}${c.align ? ` style="text-align:${c.align}"` : ''}>${esc(c.text)}</${tag}>`;
  }).join('')}</tr>`).join('')}</table>`;
  return { tsv, html };
}

function tableSize(table) {
  const rows = table.tBodies[0]?.rows.length ?? table.rows.length;
  const cols = Math.max(0, ...[...table.rows].map((r) => r.cells.length));
  return `${rows}행 ${cols}열`;
}

/** 그림을 PNG로. 같은 출처(/doc/*, data:)만 된다 — 인터넷 그림은 브라우저가 픽셀을 읽지 못하게 막는다 */
async function imagePng(img) {
  if (!img.complete || !img.naturalWidth) await img.decode();
  const svg = /^data:image\/svg/i.test(img.currentSrc) || /\.svg$/i.test(new URL(img.currentSrc).pathname);
  const scale = svg ? 2 : 1;   // SVG는 선명하게 2배로 그린다
  const canvas = document.createElement('canvas');
  canvas.width = Math.round((img.naturalWidth || img.width) * scale);
  canvas.height = Math.round((img.naturalHeight || img.height) * scale);
  canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise((resolve) => { canvas.toBlob(resolve, 'image/png'); });
  if (!blob) throw new Error('PNG로 바꾸지 못했습니다');
  return { blob, size: `${canvas.width / scale}×${canvas.height / scale}` };
}

async function copyImage(img) {
  try {
    const { blob, size } = await imagePng(img);
    await copyParts({ 'image/png': blob }, `그림 ${size}`);
  } catch {
    toast('그림을 복사하지 못했습니다', 'error');
  }
}

// ---- 메뉴 --------------------------------------------------------------------

function kindOf(el) {
  const tag = el.tagName;
  if (HEADING.test(tag)) return `제목 (${tag})`;
  if (tag === 'TABLE') return `표 · ${tableSize(el)}`;
  if (tag === 'IMG') return el.classList.contains('external') ? '인터넷 그림' : '그림';
  if (el.matches('pre.mermaid, .mermaid-error')) return '다이어그램';
  if (el.matches('.code-block')) {
    const lang = el.querySelector('.code-lang')?.textContent;
    return lang ? `코드 (${lang})` : '코드';
  }
  if (el.matches('.math-block')) return '수식';
  if (el.matches('.front-matter')) return '메타데이터';
  if (tag === 'LI') return '목록 항목';
  if (tag === 'BLOCKQUOTE') return el.classList.contains('alert') ? `박스글 (${el.querySelector('.alert-title')?.textContent || ''})` : '인용';
  return '단락';
}

/** Mermaid 다이어그램(SVG)을 PNG로. 화면 바탕색을 깔아 다크 스타일의 밝은 글자도 붙여 넣은 곳에서 보이게 한다 */
async function copyDiagram(pre) {
  try {
    const svg = pre.querySelector('svg');
    const box = svg.viewBox?.baseVal;
    const w = Math.round(box?.width || svg.getBoundingClientRect().width);
    const h = Math.round(box?.height || svg.getBoundingClientRect().height);
    const clone = svg.cloneNode(true);   // Mermaid 는 width="100%" 라서 크기를 정해 준다
    clone.setAttribute('width', w);
    clone.setAttribute('height', h);
    clone.style.maxWidth = 'none';
    const img = new Image();
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(new XMLSerializer().serializeToString(clone))}`;
    await img.decode();
    const canvas = document.createElement('canvas');
    canvas.width = w * 2;
    canvas.height = h * 2;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = getComputedStyle($('#lec-content')).backgroundColor;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((resolve) => { canvas.toBlob(resolve, 'image/png'); });
    if (!blob) throw new Error('PNG');
    await copyParts({ 'image/png': blob }, `다이어그램 ${w}×${h}`);
  } catch {
    toast('다이어그램을 복사하지 못했습니다', 'error');
  }
}

/** 문서 맨 앞 frontmatter(--- … ---)의 원문 줄 범위 */
function frontMatterRange() {
  if (doc.lines[0]?.trim() !== '---') return null;
  const end = doc.lines.findIndex((line, i) => i > 0 && /^(---|\.\.\.)\s*$/.test(line));
  return end > 0 ? [1, end + 1] : null;
}

const texItem = (node) => ({ label: 'LaTeX 복사', hint: describe(node.dataset.tex), action: () => copyPlain(node.dataset.tex) });
const editorItem = (line) => ({ label: '편집기에서 이 줄 열기', hint: `${doc.path}:${line}`, action: () => openExternal(doc.path, line) });

/** 원문 줄 범위가 있는 블록의 공통 항목: 원문 복사, Claude용 위치 복사, 편집기에서 이 줄 열기 */
function sourceItems(range, label = '원문 복사', note = '') {
  const ref = claudeRef(range, note);
  return [
    { label, hint: `Markdown ${rangeText(range)}`, action: () => copyPlain(sourceOf(range)) },
    { label: 'Claude용 위치 복사', hint: ref, action: () => copyPlain(ref) },
    editorItem(range[0]),
  ];
}

function blockItems(el, target) {
  const items = [{ header: kindOf(el) }];
  const tag = el.tagName;
  // 블록 안에서 누른 작은 것: 문장 속 수식, 링크
  const math = target.closest('[data-tex]');
  if (math && math !== el && el.contains(math)) items.push(texItem(math));
  const link = target.closest('a[data-lec-href]');
  if (link) items.push({ label: '링크 주소 복사', hint: link.dataset.lecHref, action: () => copyPlain(link.dataset.lecHref) });
  if (tag === 'IMG') {
    if (el.classList.contains('external')) items.push({ label: '그림 주소 복사', hint: el.src, action: () => copyPlain(el.src) });
    else items.push({ label: '그림 복사', hint: 'PNG — 워드·PPT·메일에 붙여 넣기', action: () => copyImage(el) });
  } else if (tag === 'TABLE') {
    items.push({
      label: '표 복사', hint: '엑셀에 붙이면 칸이 나뉘고, 워드·메일에는 표로',
      action: () => { const t = tableData(el); copyParts({ 'text/plain': t.tsv, 'text/html': t.html }, `표 ${tableSize(el)}`); },
    });
  } else if (el.matches('.code-block')) {
    items.push({ label: '코드 복사', action: () => copyPlain(el.querySelector('pre').textContent.replace(/\n$/, '')) });
  } else if (el.matches('pre.mermaid')) {
    if (el.querySelector('svg')) items.push({ label: '그림 복사', hint: 'PNG — 워드·PPT·메일에 붙여 넣기', action: () => copyDiagram(el) });
  } else if (el.matches('.math-block')) {
    items.push(texItem(el));
  } else if (!el.matches('.mermaid-error')) {
    items.push({ label: HEADING.test(tag) ? '제목 글자 복사' : '텍스트 복사', action: () => copyPlain(el.innerText.trim()) });
  }

  if (HEADING.test(tag)) {
    const section = sectionRange(el);
    if (el.id) {
      const anchor = `${doc.path}#${el.id}`;
      items.push({ label: '절 링크 복사', hint: anchor, action: () => copyPlain(anchor) });
    }
    if (section) items.push(...sourceItems(section, '이 절 원문 복사', ` ('${el.textContent.trim()}' 절)`));
    if (el.classList.contains('lec-fold') || el.parentElement === $('#lec-view')) {
      const level = +tag[1];
      items.push('-', { label: `같은 수준(${tag}) 모두 접기`, action: () => foldLevel(level, true) },
        { label: `같은 수준(${tag}) 모두 펴기`, action: () => foldLevel(level, false) });
    }
  } else {
    const range = el.matches('.front-matter') ? frontMatterRange() : lineRange(el);
    if (range) items.push(...sourceItems(range));
  }
  return items;
}

/** 인쇄 대화상자. html 문서는 그 문서 자체(자기 스타일)를 인쇄한다 — iframe 에 allow-modals 가 있어야 한다 */
function printDoc() {
  const frame = $('#lec-view > iframe.lec-html:not(.lec-loading)');
  (frame ? frame.contentWindow : window).print();
}

function docItems() {
  const items = [{ header: doc.path }, ...pathMenuItems(doc.path, true)];
  if (hasFolds()) {
    items.push('-', { label: '모두 접기', action: () => foldAll(true) }, { label: '모두 펴기', action: () => foldAll(false) });
  }
  items.push('-', { label: '인쇄 / PDF로 저장…', hint: "프린터에서 'Microsoft Print to PDF'를 고르면 PDF로 저장", action: printDoc });
  return items;
}

/** 코드 화면의 줄 번호 (요소·글 위치가 든 줄) */
const lineOf = (node) => Number((node?.nodeType === 1 ? node : node?.parentElement)?.closest?.('.cv-line')?.dataset.line) || 0;

/** 코드 화면의 우클릭 메뉴 */
function codeMenu(e, view, x, y) {
  const path = view.dataset.codePath;
  if (!path || e.target.closest?.('#lec-findbar')) return;
  e.preventDefault();
  const row = e.target.closest?.('.cv-line');
  const line = Number(row?.dataset.line) || 0;
  const sel = getSelection();
  const selected = !sel.isCollapsed && view.contains(sel.anchorNode) ? sel.toString() : '';
  let range = line ? [line, line] : null;
  if (selected) {
    const a = lineOf(sel.anchorNode);
    const b = lineOf(sel.focusNode);
    if (a && b) range = [Math.min(a, b), Math.max(a, b)];
  }
  const items = [{ header: range ? `${path} ${rangeText(range)}` : path }];
  if (selected) items.push({ label: '선택한 글 복사', hint: describe(selected.trim()), action: () => copyPlain(selected) });
  if (row && !selected) items.push({ label: '이 줄 복사', hint: describe(row.textContent), action: () => copyPlain(row.textContent) });
  if (range) {
    items.push({ label: 'Claude용 위치 복사', hint: `@${path} ${rangeText(range)}`, action: () => copyPlain(`@${path} ${rangeText(range)}`) },
      { label: '편집기에서 이 줄 열기', hint: `${range[0]}행`, action: () => openExternal(path, range[0]) });
  }
  items.push('-', ...pathMenuItems(path, true), '-',
    { label: '코드 전체 복사', action: () => copyPlain(view.codeText || '', `${path} 전체`) });
  row?.classList.add('lec-picked');
  showMenu(x, y, items, () => row?.classList.remove('lec-picked'));
}

/** view: 블록을 고를 범위 (#lec-view, html 문서면 iframe 의 body). x·y: 메뉴를 띄울 화면 좌표 */
function openMenu(e, view, x, y) {
  if (view.classList?.contains('code-view')) {
    codeMenu(e, view, x, y);
    return;
  }
  doc = S.pane?.source ?? null;   // 보이는 칸은 선택된 탭의 칸뿐이다 (panes.js)
  if (!doc || S.view?.type !== 'doc' || S.view.path !== doc.path) return;   // 문서 화면에서만
  if (e.target.closest?.('#lec-findbar')) return;
  e.preventDefault();
  const el = pickBlock(e.target, view);
  const items = el ? blockItems(el, e.target) : docItems();
  const spot = spotlightItems(e.target);   // 장 하이라이트 / 하이라이트 해제 (md 문서)
  if (spot.length) items.push('-', ...spot);
  const sel = view.ownerDocument.getSelection();
  const selected = !sel.isCollapsed && view.contains(sel.anchorNode) ? sel.toString().trim() : '';
  if (selected) items.unshift({ label: '선택한 글 복사', hint: describe(selected), action: () => copyPlain(selected) }, '-');
  // 표는 가로 스크롤 상자가 테두리를 잘라 내므로 상자에 표시한다
  const mark = el?.tagName === 'TABLE' ? el.closest('.table-wrap') || el : el;
  mark?.classList.add('lec-picked');
  showMenu(x, y, items, () => mark?.classList.remove('lec-picked'));
}

function onContextMenu(e) {
  openMenu(e, $('#lec-view'), e.clientX, e.clientY);
}

/** html 문서(iframe) 안의 우클릭 (htmldoc.js 가 붙인다). iframe 안의 좌표를 화면 좌표로 바꾼다 */
export function frameContextMenu(e, frame) {
  const r = frame.getBoundingClientRect();
  openMenu(e, frame.contentDocument.body, r.left + e.clientX, r.top + e.clientY);
}

export function initDocMenu() {
  $('#lec-panes').addEventListener('contextmenu', onContextMenu);
}
