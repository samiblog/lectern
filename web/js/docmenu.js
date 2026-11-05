// 문서 본문 우클릭 메뉴: 우클릭한 블록(제목·단락·목록 항목·표·그림·코드·다이어그램·수식)에 테두리를 그리고 복사 메뉴를 띄운다.
// 블록 밖(여백·문서 아래 빈 곳)을 누르면 문서 메뉴(경로 복사, 편집기로 열기, 모두 접기 등)를 띄운다.
// 하이라이트한 곳(장 하이라이트·줄 하이라이트 — spotlight.js) 안이면 그 범위의 선택 상자: Claude로 보내기, 위치·원문 복사, 담기 … (litMenu, D74·D75).
// 코드 화면에서도 하이라이트한 곳 안이면 같은 상자 (담기 없이).
//
// 원문 복사와 위치 복사는 markdown.js 가 블록마다 단 data-lines(원문 줄 범위)를 쓴다.
// md 문서의 블록·절·고른 글은 '담기'·'보내기…'(basket.js, D63·D65) — 표·그림·차트는 캡션과 '자료:' 줄도 함께.
// 코드 화면(codeview.js)에서는 줄 메뉴: 이 줄·고른 글 복사, Claude용 위치(@경로 12~20행), 편집기에서 이 줄 열기, 경로 복사, 전체 복사.
// 보기 전용: 클립보드에 복사하거나 다른 앱으로 열기만 하고, 파일을 만들거나 고치지 않는다 (D24 — 넣기는 편집 모드에서 사용자가 저장).

import { S, emit } from './store.js';
import { showMenu, menuGroups } from './ui.js';
import { pathMenuItems } from './tree.js';
import { foldAll, foldLevel, hasFolds } from './fold.js';
import { spotlightItems, litAt, stopSpotlight, sendLit, copyLitRef, copyLitSource, litOneLine, editHere } from './spotlight.js';
import { partExtent, captionOf } from './toc.js';
import { snippetOf, addSnippets, sendSnippets } from './basket.js';
import { linesEditable } from './lineedit.js';
import { openExternal } from './api.js';
import { isCode } from './icons.js';
import { colName, columnMenu, chartRange, markRange } from './csvview.js';
import { openChart, domTable } from './quickchart.js';
import { html } from './html.js';
import { $, toast, copyText, rangeText, lineRef } from './util.js';
import { t } from './i18n.js';

let doc = null;   // 메뉴를 띄운 탭의 문서 {path, lines}. 문서를 그리지 못했으면 null

/** doc.js·htmldoc.js 가 칸(pane)에 문서를 그릴 때마다 원문을 넘긴다 (문서 없음 화면이면 path 가 null). */
export function setDocSource(pane, path, text = '') {
  pane.source = path == null ? null : { path, lines: text.replace(/^﻿/, '').split(/\r\n?|\n/) };
}

// 우클릭으로 고르는 블록. 가장 안쪽 것을 고른다 (목록 항목 안의 단락이면 단락, 표의 칸이면 표)
const BLOCKS = 'img, pre.mermaid, pre.lec-chart, .diagram-error, .code-block, .math-block, table, h1, h2, h3, h4, h5, h6, li, p, dt, dd, blockquote';
const HEADING = /^H[1-6]$/;

function pickBlock(target, view) {
  // 다이어그램 글자(foreignObject 안의 <p>)나 메타데이터 표의 칸은 따로 고르지 않고 통째로 고른다
  const el = target.closest('.front-matter, pre.mermaid, pre.lec-chart') || target.closest(BLOCKS);
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

const sourceOf = ([a, b]) => doc.lines.slice(a - 1, b).join('\n');
// Claude Code는 '@경로' 를 파일 전체로 붙인다. 줄 범위 표기(#L40-52)는 문서화되어 있지 않아 글로 적는다 (D24)
const claudeRef = (range, note = '') => `@${doc.path} ${rangeText(range)}${note}`;

// ---- 복사 --------------------------------------------------------------------

/** 메뉴 설명·알림에 쓸 짧은 표시: 한 줄이면 앞부분, 여러 줄이면 줄 수 */
function describe(text) {
  const n = text.split('\n').length;
  if (n > 1) return t('{n}줄', { n });
  return text.length <= 40 ? text : `${text.slice(0, 40)}…`;
}

async function copyPlain(text, what = describe(text)) {
  toast(await copyText(text) ? t('복사했습니다: {what}', { what }) : t('복사하지 못했습니다'));
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
  toast(ok ? t('복사했습니다: {what}', { what }) : t('복사하지 못했습니다'));
}

/** 표 → 탭으로 나눈 글(엑셀이 칸으로 나눔)과 간단한 HTML 표(워드·메일이 표로 붙임) */
function tableData(table) {
  const rows = [...table.rows].map((r) => [...r.cells].map((c) => {
    const align = c.ownerDocument.defaultView.getComputedStyle(c).textAlign;
    return { text: c.innerText.replace(/\s+/g, ' ').trim(), head: c.tagName === 'TH', align: /right|center/.test(align) ? align : '' };
  }));
  const tsv = rows.map((r) => r.map((c) => c.text).join('\t')).join('\n');
  const markup = html`<table border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse">${rows.map((r) => html`<tr>${r.map((c) => {
    const style = c.align ? html` style="text-align:${c.align}"` : '';
    return c.head ? html`<th${style}>${c.text}</th>` : html`<td${style}>${c.text}</td>`;
  })}</tr>`)}</table>`;
  return { tsv, html: markup.text };   // 클립보드에는 글로
}

function tableSize(table) {
  const rows = table.tBodies[0]?.rows.length ?? table.rows.length;
  const cols = Math.max(0, ...[...table.rows].map((r) => r.cells.length));
  return t('{rows}행 {cols}열', { rows, cols });
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
  if (!blob) throw new Error(t('PNG로 바꾸지 못했습니다'));
  return { blob, size: `${canvas.width / scale}×${canvas.height / scale}` };
}

async function copyImage(img) {
  try {
    const { blob, size } = await imagePng(img);
    await copyParts({ 'image/png': blob }, t('그림 {size}', { size }));
  } catch {
    toast(t('그림을 복사하지 못했습니다'), 'error');
  }
}

// ---- 메뉴 --------------------------------------------------------------------

function kindOf(el) {
  const tag = el.tagName;
  if (HEADING.test(tag)) return t('제목 ({tag})', { tag });
  if (tag === 'TABLE') return `${t('표')} · ${tableSize(el)}`;
  if (tag === 'IMG') return el.classList.contains('external') ? t('인터넷 그림') : t('그림');
  if (el.matches('pre.mermaid, pre.lec-chart, .diagram-error')) return t('다이어그램');
  if (el.matches('.code-block')) {
    const lang = el.querySelector('.code-lang')?.textContent;
    return lang ? t('코드 ({lang})', { lang }) : t('코드');
  }
  if (el.matches('.math-block')) return t('수식');
  if (el.matches('.front-matter')) return t('메타데이터');
  if (tag === 'LI') return t('목록 항목');
  if (tag === 'BLOCKQUOTE') return el.classList.contains('alert') ? t('박스글') : t('인용');
  return t('단락');
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
    await copyParts({ 'image/png': blob }, `${t('다이어그램')} ${w}×${h}`);
  } catch {
    toast(t('다이어그램을 복사하지 못했습니다'), 'error');
  }
}

/** 문서 맨 앞 frontmatter(--- … ---)의 원문 줄 범위 */
function frontMatterRange() {
  if (doc.lines[0]?.trim() !== '---') return null;
  const end = doc.lines.findIndex((line, i) => i > 0 && /^(---|\.\.\.)\s*$/.test(line));
  return end > 0 ? [1, end + 1] : null;
}

const texItem = (node) => ({ label: t('LaTeX 복사'), tip: describe(node.dataset.tex), action: () => copyPlain(node.dataset.tex) });
const editorItem = (line) => ({ label: t('외부 편집기로 이 줄 열기'), tip: `${doc.path}:${line}`, action: () => openExternal(doc.path, line) });

/** 원문 줄 범위의 복사 항목: 원문 복사, 위치 복사 (Claude 에 붙이는 @경로 a~b행) */
function sourceCopies(range, label = t('원문 복사'), note = '') {
  const ref = claudeRef(range, note);
  return [
    { label, tip: `Markdown ${rangeText(range)}`, action: () => copyPlain(sourceOf(range)), term: sourceOf(range) },
    { label: t('위치 복사'), tip: ref, action: () => copyPlain(ref), term: `${ref} ` },
  ];
}

/** 원문 줄 범위의 편집 항목: 여기서 편집 (편집 모드 — D54), 외부 편집기로 이 줄 열기 */
const sourceEdits = (range) => [
  { label: t('여기서 편집'), hint: 'Ctrl+E', tip: t('{a}행', { a: range[0] }), action: () => emit('edit', { line: range[0] }) },
  editorItem(range[0]),
];

/** 새 메모로 보내기 (D92): 글과 어디서 왔는지 — notes.js 가 받는다 */
const noteItem = (body, path, range) => ({ label: t('새 메모로 보내기'), tip: t('이 프로젝트의 메모에 — 어디서 왔는지도 함께'), action: () => emit('new-note', { body, path, line: range?.[0] || 0, end: range?.[1] || 0 }) });

/** 담기·보내기 (D63·D65): 이 문서의 줄 범위(range)를 조각으로. info: {kind, name, label, text?, plain?} — basket.js 의 snippetOf */
function takeItems(range, info, labels = [t('담기'), t('문서로 보내기…')]) {
  const from = doc;
  const snip = () => snippetOf(from, range, info);
  return [{ label: labels[0], tip: t("사이드바 '담기' 탭에 — 모아서 한 번에 보내기"), action: () => addSnippets([snip()]) },
    { label: labels[1], tip: t('열린 문서 탭이나 새 문서로 바로'), action: () => sendSnippets([snip()]) },
    noteItem(info.text ?? sourceOf(range), from.path, range)];
}

/**
 * 하이라이트한 곳(spotlight.js 의 litAt — 장 하이라이트의 장, 줄 하이라이트의 줄들) 안에서 우클릭하면 나오는 선택 상자 (D74·D75).
 * 맨 위 'Claude로 보내기' 는 그 범위의 위치(@경로 a~b행)를 맨 앞 터미널(Claude Code)에 Enter 없이 넣는다 — 우클릭만으로는 보내지 않는다.
 * 그 밖에 위치·원문 복사, 담기·문서로 보내기(md 만), 그 블록(코드 화면은 그 줄)의 보통 메뉴, 하이라이트 해제. 범위는 원문 줄.
 * 보내기·복사는 키(Shift+→·Shift+←·Ctrl+C)와 같은 함수다. 하이라이트로 할 일이 늘면 이 상자에 더한다.
 * hl: litAt 의 {path, range, ref, text, code}. blockMenu: 우클릭한 블록의 보통 메뉴를 띄우는 함수 (없으면 null)
 */
function litMenu(hl, selected, blockMenu, own = []) {
  const { range, ref, text } = hl;
  const chart = hl.chapter ? null : litChart(range);
  const name = t('하이라이트한 곳');
  /** @type {MenuItem[]} */
  const uniques = own.filter((it) => !(chart && it !== '-' && 'label' in it && it.label === t('차트로 보기')));
  if (chart) uniques.push(chart);
  if (chart && hl.code) uniques.push({ label: t('이 범위를 표로'), tip: t('맨 위 행을 머리행으로 어림합니다'), action: () => markRange($('#lec-view'), range) });
  /** @type {MenuItem[]} */
  const copies = [];
  if (selected) copies.push({ label: t('고른 글 복사'), tip: describe(selected), action: () => copyPlain(selected) });
  copies.push({ label: t('원문 복사'), hint: 'Ctrl+C', tip: `${hl.code ? '' : 'Markdown '}${rangeText(range)}`, action: copyLitSource },
    { label: t('위치 복사'), hint: 'Shift+←', tip: ref, action: copyLitRef });
  const takes = hl.code ? [noteItem(text, hl.path, range)] : takeItems(range, { kind: hl.chapter ? 'section' : 'block', name, label: describe(text.replace(/\s+/g, ' ').trim()) });
  /** @type {MenuItem[]} */
  const edits = !hl.chapter && linesEditable() && litOneLine() ? [{ label: t('여기서 편집'), hint: 'F2', action: () => editHere() }] : [];
  /** @type {MenuItem[]} */
  const views = [];
  if (blockMenu) views.push({ label: hl.code ? t('이 줄의 메뉴…') : t('이 블록의 메뉴…'), tip: t('하이라이트 밖에서 우클릭할 때의 메뉴'), action: blockMenu });   // ui.js 가 메뉴를 닫은 뒤에 연다
  views.push({ label: t('하이라이트 해제'), hint: 'Esc', action: () => stopSpotlight() });
  /** @type {MenuItem[]} */
  const danger = !hl.chapter && linesEditable() ? [{ label: t('줄 지우기'), hint: 'Delete', tip: rangeText(range), action: () => emit('line-delete', {}) }] : [];
  return menuGroups([{ header: `${name} · ${rangeText(range)}` }], uniques,
    [{ label: t('Claude로 보내기'), hint: 'Shift+→', tip: t('터미널에 (Enter 는 누르지 않음)'), action: sendLit }], copies, takes, edits, views, danger);
}

/** 표를 차트로 — 캡션은 제목과 단위를 어림하는 데 쓴다 (D86). range: 이 원문 줄의 행만 */
function chartTable(table, range = null) {
  const caption = captionOf('table', table)?.text || '';
  openChart({ ...domTable(table, range), title: caption || t('표'), caption });
}

/** 하이라이트한 곳이 표 하나의 행이면 '차트로 보기' 항목 (그 행만). 데이터 보기는 그 행들을, md 문서는 그 표의 행들을 */
function litChart(range) {
  const view = $('#lec-view');
  if (view.csv && view.classList.contains('csv-view')) return { label: t('차트로 보기'), tip: t('하이라이트한 행'), action: () => chartRange(view, range) };
  if (view.classList.contains('code-view')) return null;
  const hit = [...view.querySelectorAll('table')].filter((table) => domTable(table, range).rows.length);
  if (hit.length !== 1) return null;
  return { label: t('차트로 보기'), tip: t('하이라이트한 행'), action: () => chartTable(hit[0], range) };
}

/** 블록을 담을 범위와 이름: 표·그림·차트 등은 캡션과 바로 뒤의 '자료:' 줄까지 (toc.js 의 partExtent) */
function blockTake(picked) {
  // 박스글·인용 안의 단락·목록이면 박스 통째로 ('> [!WARNING]' 머리줄까지 — 안의 단락만 담으면 박스의 종류를 잃는다)
  let el = picked;
  for (let box = picked.closest('blockquote'); box; box = box.parentElement?.closest('blockquote')) el = box;
  const ext = partExtent(el);
  const spans = ext.els.map(lineRange).filter(Boolean);
  if (!spans.length) return null;
  const range = [Math.min(...spans.map((s) => s[0])), Math.max(...spans.map((s) => s[1]))];
  // 이름: 캡션, 없으면 목차의 이름표(차트 'Vega-Lite · 제목', 표 '머리행 · 3행 2열' 등), 그 밖의 블록은 그 글
  const label = ext.caption || ext.label || describe(el.innerText.replace(/\s+/g, ' ').trim());
  return { range, info: { kind: ext.kind || 'block', name: ext.kind === 'chart' ? t('차트') : kindOf(el), label } };
}

/** 블록에서만 하는 일: 표 복사·그림 복사·코드 복사·링크 등 (하이라이트 메뉴에서도 바로 보인다) */
function uniqueItems(el, target) {
  /** @type {MenuItem[]} */
  const items = [];
  const tag = el.tagName;
  // 블록 안에서 누른 작은 것: 문장 속 수식, 링크
  const math = target.closest('[data-tex]');
  if (math && math !== el && el.contains(math)) items.push(texItem(math));
  const link = target.closest('a[data-lec-href]');
  if (link) {
    if (link.dataset.lecOpen != null || link.matches('.path-link')) {   // 앱 안에서 여는 링크 (D91 — Ctrl+누르기와 같다)
      items.push({ label: t('새 문서 탭에서 열기'), hint: t('Ctrl+누르기'), action: () => link.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, ctrlKey: true })) });
    }
    items.push({ label: t('링크 주소 복사'), tip: link.dataset.lecHref, action: () => copyPlain(link.dataset.lecHref), term: `${link.dataset.lecHref} ` });
  }
  if (tag === 'IMG') {
    if (el.classList.contains('external')) items.push({ label: t('그림 주소 복사'), tip: el.src, action: () => copyPlain(el.src) });
    else items.push({ label: t('그림 복사'), tip: t('PNG — 워드·PPT·메일에 붙여 넣기'), action: () => copyImage(el) });
  } else if (tag === 'TABLE') {
    items.push({
      label: t('표 복사'), tip: t('엑셀에 붙이면 칸이 나뉘고, 워드·메일에는 표로'),
      action: () => { const data = tableData(el); copyParts({ 'text/plain': data.tsv, 'text/html': data.html }, `${t('표')} ${tableSize(el)}`); },
    }, { label: t('차트로 보기'), tip: t('시간·단위를 어림해 선·막대로'), action: () => chartTable(el) });
  } else if (el.matches('.code-block')) {
    const code = el.querySelector('pre').textContent.replace(/\n$/, '');
    items.push({ label: t('코드 복사'), action: () => copyPlain(code), term: code });
  } else if (el.matches('pre.mermaid, pre.lec-chart')) {
    if (el.querySelector('svg')) items.push({ label: t('그림 복사'), tip: t('PNG — 워드·PPT·메일에 붙여 넣기'), action: () => copyDiagram(el) });
  } else if (el.matches('.math-block')) {
    items.push(texItem(el));
  }
  return items;
}

/** 블록의 보통 메뉴. 묶음의 차례는 ui.js 의 menuGroups */
function blockItems(el, target, views = []) {
  const tag = el.tagName;
  /** @type {MenuItem[]} */
  const copies = [];
  /** @type {MenuItem[]} */
  let takes = [];
  /** @type {MenuItem[]} */
  let edits = [];
  /** @type {MenuItem[]} */
  const folds = [];
  const plain = !el.matches('img, table, .code-block, pre.mermaid, pre.lec-chart, .math-block, .diagram-error');
  if (plain) copies.push({ label: HEADING.test(tag) ? t('제목 글자 복사') : t('텍스트 복사'), action: () => copyPlain(el.innerText.trim()), term: el.innerText.trim() });
  if (HEADING.test(tag)) {
    const section = sectionRange(el);
    if (el.id) {
      const anchor = `${doc.path}#${el.id}`;
      copies.push({ label: t('절 링크 복사'), tip: anchor, action: () => copyPlain(anchor) });
    }
    if (section) {
      const name = el.textContent.trim();
      copies.push(...sourceCopies(section, t('이 절 원문 복사'), ` (${t("'{name}' 절", { name })})`));
      edits = sourceEdits(section);
      takes = takeItems(section, { kind: 'section', name: t("'{name}' 절", { name: describe(name) }), label: name }, [t('이 절 담기'), t('이 절을 문서로 보내기…')]);
    }
    if (el.classList.contains('lec-fold') || el.parentElement === $('#lec-view')) {
      const level = +tag[1];
      folds.push({ label: t('같은 수준({tag}) 모두 접기', { tag }), action: () => foldLevel(level, true) },
        { label: t('같은 수준({tag}) 모두 펴기', { tag }), action: () => foldLevel(level, false) });
    }
  } else {
    const range = el.matches('.front-matter') ? frontMatterRange() : lineRange(el);
    if (range) {
      copies.push(...sourceCopies(range));
      edits = sourceEdits(range);
    }
    const take = range && !el.matches('.front-matter') && blockTake(el);   // 맨 앞 설정은 담지 않는다
    if (take) takes = takeItems(take.range, take.info);
  }
  return menuGroups([{ header: kindOf(el) }], uniqueItems(el, target), copies, takes, edits, [...folds, ...views]);
}

/** 고른 글이 든 블록들의 원문 줄 범위 (고른 글 담기의 담은 곳) */
function selectionRange(sel) {
  const spans = [sel.anchorNode, sel.focusNode].map((n) => (n?.nodeType === 1 ? n : n?.parentElement)?.closest('[data-lines]'))
    .filter(Boolean).map(lineRange).filter(Boolean);
  return spans.length ? [Math.min(...spans.map((s) => s[0])), Math.max(...spans.map((s) => s[1]))] : null;
}

/** 인쇄 대화상자. html 문서는 그 문서 자체(자기 스타일)를 인쇄한다 — iframe 에 allow-modals 가 있어야 한다 */
function printDoc() {
  const frame = $('#lec-view > iframe.lec-html:not(.lec-loading)');
  (frame ? frame.contentWindow : window).print();
}

function docItems(views = []) {
  /** @type {MenuItem[]} */
  const folds = hasFolds() ? [{ label: t('모두 접기'), action: () => foldAll(true) }, { label: t('모두 펴기'), action: () => foldAll(false) }] : [];
  return menuGroups([{ header: doc.path }], pathMenuItems(doc.path, true), [{ label: t('이 문서 편집'), hint: 'Ctrl+E', action: () => emit('edit') }], [...folds, ...views],
    [{ label: t('인쇄 / PDF로 저장…'), tip: t("프린터에서 'Microsoft Print to PDF'를 고르면 PDF로 저장"), action: printDoc }]);
}

/** 코드 화면의 줄 번호 (요소·글 위치가 든 줄) */
const lineOf = (node) => Number((node?.nodeType === 1 ? node : node?.parentElement)?.closest?.('.cv-line')?.dataset.line) || 0;

/** 코드 화면의 우클릭 메뉴 — 하이라이트한 곳 안이면 그 범위의 선택 상자 (D75), '이 줄의 메뉴…' 로 아래의 줄 메뉴 */
function codeMenu(e, view, x, y) {
  const path = view.dataset.codePath;
  if (!path || e.target.closest?.('#lec-findbar')) return;
  e.preventDefault();
  const head = view.csv && e.target.closest?.('.csv-head th[data-col]');
  if (head) {   // 열 머리: 계산 열·차트 (D86)
    showMenu(x, y, columnMenu(view, Number(head.dataset.col)));
    return;
  }
  const sel = getSelection();
  const selected = !sel.isCollapsed && view.contains(sel.anchorNode) ? sel.toString() : '';
  const hl = litAt(e.clientY);
  if (hl) {
    showMenu(x, y, litMenu(hl, selected.trim(), () => codeLineMenu(e, view, x, y)));
    return;
  }
  codeLineMenu(e, view, x, y);
}

function codeLineMenu(e, view, x, y) {
  const path = view.dataset.codePath;
  const row = e.target.closest?.('.cv-line');
  const line = Number(row?.dataset.line) || 0;
  const end = Number(row?.dataset.end) || line;   // csv 의 한 행이 여러 줄이면 (따옴표 안 줄바꿈 — csvview.js)
  // csv 표의 행은 칸을 이은 글이 아니라 원문 줄로
  const rowText = row?.tagName === 'TR' ? (view.codeText || '').split('\n').slice(line - 1, end).join('\n') : row?.textContent;
  const sel = getSelection();
  const selected = !sel.isCollapsed && view.contains(sel.anchorNode) ? sel.toString() : '';
  let range = line ? [line, end] : null;
  if (selected) {
    const a = lineOf(sel.anchorNode);
    const b = lineOf(sel.focusNode);
    if (a && b) range = [Math.min(a, b), Math.max(a, b)];
  }
  const sheet = view.dataset.sheet || '';   // 엑셀 보기 (D77) — 행은 엑셀의 행 번호, 보기만
  /** @type {MenuItem[]} */
  const items = [];
  if (selected) items.push({ label: t('고른 글 복사'), tip: describe(selected.trim()), action: () => copyPlain(selected), term: selected });
  const cell = sheet && !selected ? e.target.closest?.('td:not(.csv-rn):not(.csv-calc)') : null;
  if (cell && row) {   // 엑셀의 칸: 그 칸의 글 (이름은 B3 처럼 — 고른 표면 그 표의 왼쪽 끝부터, D86)
    const name = `${colName(Number(view.dataset.firstCol || 0) + (view.csv?.region?.c0 ?? 0) + cell.cellIndex - 1)}${line}`;
    items.push({ label: t('이 칸 복사'), tip: `${name} · ${describe(cell.textContent)}`, action: () => copyPlain(cell.textContent) });
  }
  if (row && !selected) items.push({ label: sheet ? t('이 행 복사') : t('이 줄 복사'), tip: describe(rowText), action: () => copyPlain(rowText), term: sheet ? undefined : rowText.trim() });
  /** @type {MenuItem[]} */
  const edits = [];
  if (range) {
    const ref = lineRef(path, range, sheet);
    items.push({ label: t('위치 복사'), tip: ref, action: () => copyPlain(ref), term: `${ref} ` });
    if (!sheet) {
      edits.push({ label: t('여기서 편집'), hint: 'Ctrl+E', tip: t('{a}행', { a: range[0] }), action: () => emit('edit', { line: range[0] }) },
        { label: t('외부 편집기로 이 줄 열기'), tip: t('{a}행', { a: range[0] }), action: () => openExternal(path, range[0]) });
    }
  }
  items.push({ label: isCode(path) ? t('코드 전체 복사') : t('전체 복사'), action: () => copyPlain(view.codeText || '', t('{name} 전체', { name: path })) });
  const header = { header: range ? `${path} ${sheet ? `${t("'{name}' 시트", { name: sheet })} ` : ''}${rangeText(range)}` : path };
  row?.classList.add('lec-picked');
  showMenu(x, y, menuGroups([header], items, pathMenuItems(path, true), edits, spotlightItems(e.target)), () => row?.classList.remove('lec-picked'));
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
  const sel = view.ownerDocument.getSelection();
  const selected = !sel.isCollapsed && view.contains(sel.anchorNode) ? sel.toString().trim() : '';
  // 하이라이트한 곳 안이면 그 범위의 선택 상자 (D74). '이 블록의 메뉴…' 로 아래의 보통 메뉴
  const hl = view === $('#lec-view') ? litAt(e.clientY) : null;
  const lit = hl && litMenu(hl, selected, () => blockMenu(e, view, el, selected, x, y), el ? uniqueItems(el, e.target) : []);
  if (lit) {
    showMenu(x, y, lit);
    return;
  }
  blockMenu(e, view, el, selected, x, y);
}

/** 우클릭한 블록(없으면 문서)의 보통 메뉴 — 고른 글이 있으면 맨 위에 그 글 */
function blockMenu(e, view, el, selected, x, y) {
  const spot = spotlightItems(e.target);   // 장 하이라이트 / 하이라이트 해제 (md 문서)
  const items = el ? blockItems(el, e.target, spot) : docItems(spot);
  const sel = view.ownerDocument.getSelection();
  if (selected) {
    const range = selectionRange(sel);
    const take = range ? takeItems(range, { kind: 'text', name: t('고른 글'), label: describe(selected.replace(/\s+/g, ' ')), text: selected, plain: true }, [t('고른 글 담기'), t('고른 글을 문서로 보내기…')]) : [];
    items.splice(1, 0, { label: t('고른 글 복사'), tip: describe(selected), action: () => copyPlain(selected), term: selected }, ...take, '-');
  }
  // 표는 가로 스크롤 상자가 테두리를 잘라 내므로 상자에 표시한다
  const mark = el?.tagName === 'TABLE' ? el.closest('.table-wrap') || el : el;
  mark?.classList.add('lec-picked');
  showMenu(x, y, items, () => mark?.classList.remove('lec-picked'));
}

function onContextMenu(e) {
  // 편집 모드 (D54) — 아래의 숨은 화면이 아니라 편집기 것. 문서 탭 줄(D64)·모두 펼치기의 칸 머리(D73)는 #lec-panes 안에 있지만 자기 메뉴가 있다
  if (e.target.closest?.('.lec-editor, #lec-doctabs, .sp-head')) return;
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
