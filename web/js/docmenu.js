// 문서 본문 우클릭 메뉴: 우클릭한 블록(제목·단락·목록 항목·표·그림·코드·다이어그램·수식)에 테두리를 그리고 복사 메뉴를 띄운다.
// 블록 밖(여백·문서 아래 빈 곳)을 누르면 문서 메뉴(경로 복사, 편집기로 열기, 모두 접기 등)를 띄운다.
//
// 원문 복사와 Claude용 위치 복사는 markdown.js 가 블록마다 단 data-lines(원문 줄 범위)를 쓴다.
// 보기 전용: 클립보드에 복사하거나 다른 앱으로 열기만 하고, 파일을 만들거나 고치지 않는다 (D24).

import { S } from './store.js';
import { showMenu } from './ui.js';
import { pathMenuItems } from './tree.js';
import { foldAll, hasFolds } from './fold.js';
import { $, esc, toast, copyText } from './util.js';

let doc = null;   // 지금 보이는 문서 {path, lines}. 문서를 그리지 못했으면 null

/** doc.js 가 문서를 그릴 때마다 원문을 넘긴다 (문서 없음 화면이면 path 가 null). */
export function setDocSource(path, text = '') {
  doc = path == null ? null : { path, lines: text.replace(/^﻿/, '').split(/\r\n?|\n/) };
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
    const align = getComputedStyle(c).textAlign;
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
  if (tag === 'BLOCKQUOTE') return el.classList.contains('alert') ? '콜아웃' : '인용';
  return '단락';
}

function blockItems(el) {
  const items = [{ header: kindOf(el) }];
  const tag = el.tagName;
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
  } else if (!el.matches('pre.mermaid, .mermaid-error, .math-block')) {   // 그림·수식의 글자는 쓸모가 없어 원문 복사만 둔다
    items.push({ label: HEADING.test(tag) ? '제목 글자 복사' : '텍스트 복사', action: () => copyPlain(el.innerText.trim()) });
  }

  if (HEADING.test(tag)) {
    const section = sectionRange(el);
    if (section) items.push({ label: '이 절 원문 복사', hint: `Markdown ${rangeText(section)}`, action: () => copyPlain(sourceOf(section)) });
    if (el.id) {
      const link = `${doc.path}#${el.id}`;
      items.push({ label: '절 링크 복사', hint: link, action: () => copyPlain(link) });
    }
    if (section) {
      const ref = claudeRef(section, ` ('${el.textContent.trim()}' 절)`);
      items.push({ label: 'Claude용 위치 복사', hint: ref, action: () => copyPlain(ref) });
    }
  } else {
    const range = lineRange(el);
    if (range) {
      items.push({ label: '원문 복사', hint: `Markdown ${rangeText(range)}`, action: () => copyPlain(sourceOf(range)) });
      const ref = claudeRef(range);
      items.push({ label: 'Claude용 위치 복사', hint: ref, action: () => copyPlain(ref) });
    }
  }
  return items;
}

function docItems() {
  const items = [{ header: doc.path }, ...pathMenuItems(doc.path, true)];
  if (hasFolds()) {
    items.push('-', { label: '모두 접기', action: () => foldAll(true) }, { label: '모두 펴기', action: () => foldAll(false) });
  }
  return items;
}

function onContextMenu(e) {
  if (!doc || S.view?.type !== 'doc' || S.view.path !== doc.path) return;   // 문서 화면에서만
  if (e.target.closest('#lec-findbar')) return;
  e.preventDefault();
  const view = $('#lec-view');
  const el = pickBlock(e.target, view);
  const items = el ? blockItems(el) : docItems();
  const sel = getSelection();
  const selected = !sel.isCollapsed && view.contains(sel.anchorNode) ? sel.toString().trim() : '';
  if (selected) items.unshift({ label: '선택한 글 복사', hint: describe(selected), action: () => copyPlain(selected) }, '-');
  // 표는 가로 스크롤 상자가 테두리를 잘라 내므로 상자에 표시한다
  const mark = el?.tagName === 'TABLE' ? el.closest('.table-wrap') || el : el;
  mark?.classList.add('lec-picked');
  showMenu(e.clientX, e.clientY, items, () => mark?.classList.remove('lec-picked'));
}

export function initDocMenu() {
  $('#lec-content').addEventListener('contextmenu', onContextMenu);
}
