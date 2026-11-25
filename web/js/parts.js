// 모아 보기 (D41·D196): 프로젝트(또는 고른 폴더와 그 하위)의 표·그림·강조글·다이어그램·코드·수식을 종류마다 모아, 문서 탭 하나에 실제 모습으로 펼쳐 놓는다.
// 화면 종류 'parts' (path = 범위 폴더, '' 는 프로젝트 전체) — main.js 가 nav.js 에 등록한 렌더러 showParts 가 칸에 그린다 (doctabs.js: 프로젝트에 탭 하나).
// 0.102 까지는 사이드바의 이름 목록이었다 — 이름만 보여 견주려면 문서를 하나씩 열어야 했다 (D196).
//
// - 화면: 머리(모을 것 — 문서 속 요소 / 문서 정보(D62) / 파일 종류(D50), 종류 버튼, 종류 아래 단추), 붙어 있는 줄(거르기·순서·'새 문서로'·'AI 에'), 목록.
// - 문서마다 본문과 같은 해석기로 화면 밖에서 그려(md: markdown-it + 정화, html: DOMParser — 스크립트·그림을 부르지 않는다)
//   목차와 같은 규칙(toc.js 의 readParts)으로 센다. 그래서 번호·이름이 그 문서의 목차와 같다.
//   읽은 결과는 탭마다 문서의 수정 시각과 함께 기억해 두고(tab.partsCache), 바뀐 문서만 다시 읽는다.
// - 펼치는 종류(표·그림·차트·박스글·강조글·다이어그램·코드·수식): 문서별 묶음 안에 덩어리마다 출처 줄(절·이름·원문 줄 — 누르면 그 문서의 그 자리로,
//   Alt+← 로 돌아온다)과 실제 요소(캡션·몸체·주·자료). 묶음이 화면에 가까워질 때 그 문서를 다시 화면 밖에서 그려 요소를 옮겨 온다 (fillGroup —
//   다이어그램·차트는 옮겨 온 뒤 화면에서 그린다). 그림·차트·다이어그램은 두세 칸 격자. 같은 그림을 여러 문서가 쓰면 처음 것 하나에 '+N곳'.
//   보기만 한다 — 고치려면 출처 줄로 그 문서에 가서.
// - 할 일·링크·출처 (D62): 펼쳐 볼 내용이 없어 한 줄씩. 종류 아래 작은 단추로 '안 한 것'·'깨진 것'·'각주' 등을 고른다.
//   링크는 대상(문서·코드·자료·폴더·인터넷)을 가르고, 프로젝트 안의 파일이 없으면 '깨짐' (서버에 묻는다 — /api/exists).
// - 거르기는 이름·절·문서와 함께 내용을 본다 — 표의 칸 글, 캡션, 주·자료 줄, 코드 (그림·차트·다이어그램은 캡션·절·대체 글로만). 맞은 낱말은 표시한다.
// - '새 문서로': 보이는 것을 문서 차례대로 새 md 하나에 (basket.js 의 보내기 창 — 경로는 사용자가). 'AI 에': 보이는 것의 위치 목록을 터미널에 (Enter 없이 — D51).
// - 오른쪽 목차 패널은 모은 것의 차례 — 문서와 그 아래 구성 요소 (toc.js 의 buildItems).
// - 여는 곳: 폴더 개요의 '모아 보기' 버튼, 트리·'코드'·'자료' 목록의 폴더 우클릭, 프로젝트 탭 우클릭, 명령 찾기 ('parts' 이벤트 {path, kind, mode}).
// - 모을 것·종류·순서는 프로젝트 탭에 남겨 다음에 열 때 쓴다 (tab.side.parts). 거르기·스크롤은 그 문서 탭의 것 (pane.gather).

import { html, raw, setHtml } from './html.js';
import { S, on, emit } from './store.js';
import { getText, postJSON } from './api.js';
import { showMenu, menuGroups } from './ui.js';
import { openTarget, docPaneOf } from './doctabs.js';
import { paneOf, paneShown } from './panes.js';
import { labelOf, tipOf, telling, tellHtml, pathMenuItems } from './tree.js';
import { loadOthers, otherFiles, bindFileRows, fileTip } from './others.js';
import { fileIcon, fileType, isCode, PICTURE_EXT } from './icons.js';
import { readParts, goToPart, partExtent, partNodes, setToc, PARTS } from './toc.js';
import { snippetOf, addSnippets, sendSnippets, boxMenu, clipLabel } from './basket.js';
import { renderMarkdown } from './markdown.js';
import { sanitizeHtml, prepareParts, imageKey, resolveRef, finishPart, settlePart } from './doc.js';
import { linkPaths } from './pathlink.js';
import { renderCharts } from './charts.js';
import { renderMermaid } from './mermaid.js';
import { fitTables } from './tablefit.js';
import { readYaml } from './slides.js';
import { setStatus } from './status.js';
import { clearChanges } from './diffmark.js';
import { setDocSource } from './docmenu.js';
import { aiCli } from './aitool.js';
import {
  $, $$, docUrl, isMd, isHtml, basename, dirname, debounce, keepFocus, docRoot, natCompare, toast, copyText, middleClickOpens, linkHow, repeatClick, rangeText,
} from './util.js';
import { t } from './i18n.js';

const KINDS = Object.keys(PARTS);
const MAX_SHOWN = 800;     // 목록에 그리는 항목 수 (넘으면 거르기로 좁히라고 알린다)
const PARALLEL = 4;        // 문서를 함께 읽는 수
const MAX_SEND = 100;      // 'AI 에' 로 한 번에 넘기는 위치 수
const KEPT_DOCS = 24;      // 요소를 옮겨 오려고 화면 밖에 그려 둔 문서 수 (tab.partsDocs)
const SPREAD = new Set(KINDS.filter((k) => !PARTS[k].more));   // 실제 모습으로 펼치는 종류 — 할 일·링크·출처는 한 줄씩
const GRID = new Set(['figure', 'chart', 'diagram']);          // 두세 칸 격자로 놓는 종류

// mode: parts(문서 속 요소) | meta(문서 정보, D62) | files(파일 종류, D50). kind: 문서 속 요소의 종류, ftype: 파일 형식 ('묶음:형식' — 'others:pdf'),
// sub: 종류 아래 단추 (할 일·링크·출처), mkey: 문서 정보의 키. scope(범위 폴더)는 화면의 path
const DEFAULT = { mode: 'parts', kind: 'table', ftype: null, filter: '', order: 'tree', sub: { task: 'open', link: 'all', source: 'all' }, mkey: null, autoKind: false };
const KEEP = ['mode', 'kind', 'ftype', 'order', 'sub', 'mkey'];   // 프로젝트 탭에 남겨 다음에 열 때 쓰는 것

// 종류 아래 단추: [키, 이름, 맞는지]
const SUBS = {
  task: [['open', t('안 한 것'), (it) => !it.done], ['done', t('한 것'), (it) => it.done], ['all', t('모두'), () => true]],
  link: [['all', t('모두'), () => true], ['broken', t('깨진 것'), (it) => it.broken], ['web', t('인터넷'), (it) => it.type === 'web' || it.type === 'mail'],
    ['local', t('프로젝트 안'), (it) => ['doc', 'code', 'file', 'dir'].includes(it.type)]],
  source: [['all', t('모두'), () => true], ['source', t('출처'), (it) => !it.note], ['note', t('각주'), (it) => it.note]],
};
const LINK_TYPES = { doc: t('문서'), code: t('코드'), file: t('자료'), dir: t('폴더'), web: t('인터넷'), mail: t('메일'), outside: t('프로젝트 밖') };
let wish = null;           // openParts 가 정한 것 {path, mode, kind, at} — 다음에 그 범위를 그리는 화면이 가져간다

/** 칸이 모아 보기를 보이는지 */
const isParts = (pane) => !!pane?.gather && !!pane.view?.classList.contains('parts-view');
const partsPanes = (tab) => (tab?.panes || []).filter(isParts);
const inScope = (path, scope) => !scope || path === scope || path.startsWith(`${scope}/`);
const q = (pane, sel) => /** @type {HTMLElement} */ (pane.view.querySelector(sel));
const squeeze = (s) => String(s ?? '').replace(/\s+/g, ' ').trim();
const themeNow = () => document.documentElement.dataset.theme || '';
/** 다시 그려도 키보드 초점을 지킨다 — 선택된 칸만 (#lec-view 가 그 칸의 것이다) */
const keep = (pane, draw) => (pane === S.pane ? keepFocus(pane.view, draw) : draw());

// ---- 읽기 ---------------------------------------------------------------------

/** 요소(와 그 캡션 단락)의 원문 줄 범위 [첫 줄, 끝 줄] — md 의 data-lines (markdown.js). 모르면 null (html 문서) */
function linesOf(...els) {
  const spans = els.filter(Boolean).map((el) => (el.closest?.('[data-lines]') || el.querySelector?.('[data-lines]'))?.dataset.lines)
    .filter(Boolean).map((v) => v.split('-').map(Number));
  return spans.length ? [Math.min(...spans.map((x) => x[0])), Math.max(...spans.map((x) => x[1] || x[0]))] : null;
}

const fileKindOf = (path) => (isMd(path) || isHtml(path) ? 'doc' : isCode(basename(path)) ? 'code' : 'file');

/** 링크의 대상: {text, target(보일 주소), type(doc·code·file·dir·web·mail·outside), local(확인할 프로젝트 안 경로)} */
function linkTarget(r, base, tab) {
  const text = r.text;
  if (r.path) return { text, target: r.href, type: fileKindOf(r.path) };   // 본문 속 경로 표기 — 있는 것만 링크가 된다 (pathlink.js)
  const ref = resolveRef(r.href, base, tab);
  if (ref.kind === 'external') return { text, target: ref.url, type: /^mailto:/i.test(ref.url) ? 'mail' : 'web' };
  if (ref.kind === 'local') {
    if (ref.isDir || ref.path === '' || tab.dirs.has(ref.path)) return { text, target: `${ref.path}/`, type: 'dir' };
    let hash = ref.hash || '';
    try { hash = decodeURIComponent(hash); } catch { /* 그대로 */ }
    return { text, target: `${ref.path}${hash}`, type: fileKindOf(ref.path), local: tab.fileMap.has(ref.path) ? '' : ref.path };
  }
  return { text, target: r.href, type: 'outside' };
}

/**
 * 프로젝트 안을 가리키는 링크 가운데 트리에 없는 것이 실제로 있는지 서버에 묻는다 — 없으면 '깨짐'. 묻지 못하면 그대로 둔다.
 * 문서가 없는 폴더를 / 없이 가리킨 링크(`[src](src)`)는 폴더로 고친다 (본문에서 누르면 탐색기로 열린다)
 */
async function checkLinks(tab, items) {
  const paths = [...new Set(items.map((it) => it.local).filter(Boolean))].slice(0, 500);
  if (!paths.length) return;
  let found;
  try {
    ({ found } = await postJSON('/api/exists', { p: tab.id, paths, base: '', dirs: true }));
  } catch {
    return;
  }
  for (const it of items) {
    if (!it.local) continue;
    const hit = found[it.local];
    it.broken = !hit;
    if (hit?.endsWith('/')) Object.assign(it, { type: 'dir', target: hit });
  }
}

/**
 * 문서를 화면 밖에서 본문과 같은 규칙으로 그린다: {root(조각 — html 문서는 그 문서의 body), meta(맨 앞 설정), foreign(html 문서 — 정화하지 않은 남의 DOM)}.
 * links: 본문 속 경로 표기도 본문처럼 링크로 (링크 번호가 본문과 같게 — 서버에 묻는다)
 */
async function parseDoc(tab, path, { links = false } = {}) {
  const text = await getText(docUrl(tab, path));
  if (isHtml(path)) return { root: new DOMParser().parseFromString(text, 'text/html').body, meta: null, foreign: true };   // 스크립트는 돌지 않고 그림도 부르지 않는다
  const { html: markup, frontMatter } = renderMarkdown(text, { math: S.config.math !== false });
  const tpl = document.createElement('template');   // template 안은 그림을 부르지 않는다 (정화가 src 도 data-src 로 뗀다)
  setHtml(tpl, raw(sanitizeHtml(markup)));
  const root = tpl.content;
  prepareParts(root);
  if (links) await linkPaths(root, path, tab);
  return { root, meta: frontMatter ? readYaml(frontMatter) : null, foreign: false };
}

/** 거르기가 볼 그 요소의 글 (D196 — 표의 칸·캡션·주·자료·코드). 그림·차트·다이어그램은 몸체를 빼고 (차트의 원문은 설정 글이라 낱말이 엉뚱하게 맞는다) */
function bodyText(r) {
  return squeeze(partNodes(r.el).filter((n) => !(GRID.has(r.kind) && n.contains(r.el))).map((n) => n.textContent).join(' ')).slice(0, 20000).toLowerCase();
}

/**
 * 문서 하나를 화면 밖에서 읽어 {items: 구성 요소 [{kind, n, name, label, caption, detail, section, lines, body, …}], meta: 맨 앞 설정}.
 * 그림은 src·alt, 차트는 chart(라이브러리), 할 일은 text·done, 링크는 text·target·type·broken, 출처는 text·note
 */
async function readDoc(tab, path) {
  const { root, meta } = await parseDoc(tab, path, { links: true });
  const base = new URL(docUrl(tab, path), location.origin);
  const items = readParts(root, { more: true }).rows.filter((r) => r.kind).map((r) => {
    const item = { kind: r.kind, n: r.n, name: r.name, label: r.label || '', caption: r.caption || '', detail: r.detail || '', section: r.section,
      lines: linesOf(r.el, r.capEl), take: linesOf(...partExtent(r.el).els) };   // take: 담을 범위 — 캡션과 '자료:' 줄까지 (D63)
    if (SPREAD.has(r.kind)) item.body = bodyText(r);
    if (r.kind === 'figure') {
      const img = r.el.tagName === 'IMG' ? r.el : r.el.querySelector('img');
      item.src = img?.getAttribute('data-src') || img?.getAttribute('src') || '';
      item.alt = img?.getAttribute('alt') || '';
    } else if (r.kind === 'chart') item.chart = r.el.dataset.chart;
    else if (r.kind === 'task') Object.assign(item, { text: r.text, done: r.done });
    else if (r.kind === 'link') Object.assign(item, linkTarget(r, base, tab), { text: r.text, href: r.href, pathLink: !!r.path });
    else if (r.kind === 'source') Object.assign(item, { text: r.text, note: r.note });
    return item;
  });
  await checkLinks(tab, items.filter((it) => it.kind === 'link'));
  return { items, meta };
}

/** 범위 안의 문서를 읽는다 (바뀐 것만). 읽는 동안 그 탭의 모아 보기 화면들을 조금씩 다시 그린다. 읽는 일은 프로젝트 탭마다 하나 (tab.partsScan — {scope, done, total}) —
 * 그 탭에서 새로 읽기 시작하면 앞의 것은 멈춘다 */
async function scan(tab, scope) {
  tab.partsCache ??= new Map();
  const files = tab.files.filter((f) => inScope(f.path, scope));
  const todo = files.filter((f) => tab.partsCache.get(f.path)?.mtime !== f.mtime);
  for (const path of tab.partsCache.keys()) if (!tab.fileMap.has(path)) tab.partsCache.delete(path);   // 지워진 문서
  if (!todo.length) return;
  const job = { scope, done: 0, total: todo.length };
  tab.partsScan = job;
  const redraw = debounce(() => { if (tab.partsScan === job) for (const pane of partsPanes(tab)) draw(pane); }, 250);
  let next = 0;
  const worker = async () => {
    while (next < todo.length && tab.partsScan === job) {
      const f = todo[next++];
      let got;
      try {
        got = await readDoc(tab, f.path);
      } catch {
        got = { items: [], meta: null };   // 읽는 사이 지워진 문서 등 — 다음 변경 때 다시 읽는다
      }
      tab.partsCache.set(f.path, { mtime: f.mtime, ...got });
      job.done += 1;
      redraw();
    }
  };
  await Promise.all(Array.from({ length: PARALLEL }, worker));
  if (tab.partsScan === job) tab.partsScan = null;
}

/**
 * 요소를 옮겨 오려고 화면 밖에 그려 둔 문서 {mtime, foreign, rows} — 읽을 때(readDoc)와 같은 규칙이라 종류별 번호가 같다.
 * 문서 몇 개만 남겨 둔다 (거르기를 바꿀 때마다 다시 받지 않게)
 */
async function prepared(tab, path) {
  const docs = (tab.partsDocs ??= new Map());
  const mtime = tab.fileMap.get(path)?.mtime;
  const had = docs.get(path);
  if (had && had.mtime === mtime) return had;
  const { root, foreign } = await parseDoc(tab, path);
  const doc = { mtime, foreign, rows: readParts(root, { more: true }).rows.filter((r) => r.kind) };
  docs.delete(path);
  docs.set(path, doc);
  for (const old of [...docs.keys()].slice(0, Math.max(0, docs.size - KEPT_DOCS))) docs.delete(old);
  return doc;
}

// ---- 그리기 ---------------------------------------------------------------------

/** 화면의 뼈대 — 머리(모을 것·종류), 붙어 있는 줄(거르기·순서·넘기기), 목록 */
function skeleton() {
  return [html`<header class="parts-head">
    <div class="parts-top"><h1>${t('모아 보기')}</h1><span class="parts-scope"></span><button type="button" class="text-btn parts-all" title="${t('프로젝트 전체로')}" hidden>${t('전체')}</button></div>
    <div class="parts-mode" role="tablist" aria-label="${t('모아 볼 것')}">
      <button type="button" role="tab" data-mode="parts" title="${t('문서 속 표·그림·차트·강조글·다이어그램·코드·수식·할 일·링크·출처')}">${t('문서 속 요소')}</button>
      <button type="button" role="tab" data-mode="meta" title="${t('맨 앞 설정(frontmatter)의 키마다 값으로 문서 묶기 — status·author·date 등')}">${t('문서 정보')}</button>
      <button type="button" role="tab" data-mode="files" title="${t('문서·코드·자료 파일을 형식별로 (엑셀·PDF·그림·py·ipynb 등)')}">${t('파일 종류')}</button>
    </div>
    <div class="parts-kinds" role="tablist" aria-label="${t('모아 볼 종류')}"></div>
    <div class="parts-sub" role="group" aria-label="${t('고르기')}" hidden></div>
  </header>`, html`<div class="parts-bar">
    <input class="parts-filter" type="search" spellcheck="false" autocomplete="off" aria-label="${t('거르기')}">
    <button type="button" class="icon-btn small toggle parts-order"></button>
    <span class="tb-spacer"></span>
    <button type="button" class="parts-send" data-act="doc" title="${t('보이는 것을 문서 차례대로 새 Markdown 문서 하나에 — 경로를 정하면 만듭니다')}">${t('새 문서로')}</button>
    <button type="button" class="parts-send" data-act="ai" title="${t('보이는 것의 위치(@경로 줄)를 터미널에 넣습니다 — 이어서 할 말을 적으세요 (Enter 는 누르지 않음)')}">${t('{cli} 에', { cli: aiCli() })}</button>
    <p class="parts-info"></p>
  </div>`, html`<div class="parts-list" role="list" aria-label="${t('모아 본 구성 요소')}"></div>`];
}

/** 범위 안 문서들의 항목: [{file, items}] (순서: 트리 또는 최근 수정) */
function collected(tab, st) {
  const files = tab.files.filter((f) => inScope(f.path, st.scope) && tab.partsCache?.has(f.path));
  if (st.order === 'recent') files.sort((a, b) => b.mtime - a.mtime);
  return files.map((file) => ({ file, items: tab.partsCache.get(file.path).items }));
}

const wordsOf = (text) => text.toLowerCase().split(/\s+/).filter(Boolean);

function matcher(text) {
  const words = wordsOf(text);
  return (...fields) => {
    const hay = fields.join(' ').toLowerCase();
    return words.every((w) => hay.includes(w));
  };
}

/** 항목의 마우스 설명: 캡션(있으면)·이름·설명·절·문서 */
const itemTip = (file, item) => [item.text, item.caption, `${item.name}${item.label ? ` · ${item.label}` : ''}`, item.target,
  item.section && t('절: {name}', { name: item.section }), file.path].filter(Boolean).join('\n');

/** 행의 이름과 그 아래 설명. 캡션이 있으면 캡션이 이름(그 아래에 '표 3 · 6행 2열' — D61), 할 일·링크·출처는 그 글이 이름 (D62) */
function itemTexts(item) {
  if (item.kind === 'task') return { main: item.text || item.name, sub: '' };
  if (item.kind === 'link') return { main: item.text || item.target, sub: `${LINK_TYPES[item.type] || ''} · ${item.target}` };
  if (item.kind === 'source') return { main: item.text, sub: item.note ? item.name : t('출처') };
  if (item.caption) return { main: item.caption, sub: [item.name, item.detail].filter(Boolean).join(' · ') };
  return { main: item.name, sub: item.label };
}

/** 한 줄짜리 행 — 할 일·링크·출처 (D62) */
function itemRow(file, item) {
  const { main, sub } = itemTexts(item);
  const long = item.caption || item.text;
  const cls = `pt-item${long ? ' has-cap' : ''}${item.done ? ' pt-done' : ''}`;
  const bad = item.broken ? html`<span class="pt-bad">${t('깨짐')}</span>` : '';
  return [html`<div class="${cls}" tabindex="0" data-doc="${file.path}" data-kind="${item.kind}" data-n="${item.n}" title="${itemTip(file, item)}">`, html`<svg class="tp-icon" aria-hidden="true"><use href="#${PARTS[item.kind].icon}"/></svg>`, html`<span class="pt-text"><span class="pt-name">${main}</span>${sub || bad ? html`<span class="pt-label">${bad}${sub}</span>` : ''}`, html`${item.section ? html`<span class="pt-sec">${item.section}</span>` : ''}</span></div>`];
}

const chunkKey = (path, item) => `${path}|${item.kind}|${item.n}`;

/**
 * 펼친 덩어리 (D196): 출처 줄(절 › 이름 — 누르면 그 문서의 그 자리로, 원문 줄)과 요소가 들어올 자리. 요소는 묶음이 화면에 가까워지면 옮겨 온다 (fillGroup) —
 * 그때까지는 이름만. 전에 그렸던 높이를 자리에 잡아 둔다 (돌아왔을 때 스크롤 위치가 맞게)
 */
function chunkHtml(file, item, st, others = []) {
  const detail = item.detail || (item.caption ? '' : item.label);   // 표의 크기, 캡션이 없으면 이름표(대체 글·첫 줄)
  const tall = st.heights.get(chunkKey(file.path, item));
  const more = others.length ? html`<span class="pt-more" title="${`${t('같은 그림을 쓰는 다른 문서:')}\n${others.join('\n')}`}">${t('+{n}곳', { n: others.length })}</span>` : '';
  return [html`<article class="pv-chunk" tabindex="0" data-doc="${file.path}" data-kind="${item.kind}" data-n="${item.n}"${tall ? html` style="min-height:${tall}px"` : ''}>`, html`<div class="pv-src"><button type="button" class="pv-go" title="${`${t('문서에서 보기 — 그 자리로 갑니다 (Alt+← 로 돌아옵니다)')}\n${itemTip(file, item)}`}">`, html`${item.section ? html`<span class="pv-sec">${item.section}</span>` : ''}<span class="pv-name">${item.name}</span>${detail ? html`<span class="pv-detail">${detail}</span>` : ''}</button>${item.lines ? html`<span class="pv-lines">${rangeText(item.lines)}</span>` : ''}${more}</div>`, html`<div class="pv-body pv-wait"><p class="pv-hold">${item.caption || item.alt || item.label || item.name}</p></div></article>`];
}

/** 모을 것 버튼, 범위, 순서, 거르기 칸의 안내, 넘기는 단추 */
function drawHead(pane) {
  const { tab } = pane;
  const st = pane.gather;
  for (const b of $$('.parts-mode button', pane.view)) {
    const on = b.dataset.mode === st.mode;
    b.classList.toggle('active', on);
    b.setAttribute('aria-selected', String(on));
  }
  const filter = /** @type {HTMLInputElement} */ (q(pane, '.parts-filter'));
  filter.placeholder = st.mode === 'files' ? t('이름·경로로 거르기') : st.mode === 'meta' ? t('문서·값으로 거르기') : t('이름·내용·절·문서로 거르기');
  if (document.activeElement !== filter && filter.value.trim() !== st.filter) filter.value = st.filter;
  const scope = q(pane, '.parts-scope');
  scope.textContent = st.scope ? t('{folder} 폴더', { folder: st.scope }) : t('{name} 전체', { name: tab.name });
  scope.title = st.scope ? t('{folder} 폴더와 그 하위 폴더', { folder: st.scope }) : t('프로젝트 전체');
  q(pane, '.parts-all').hidden = !st.scope;
  const order = q(pane, '.parts-order');
  order.textContent = st.order === 'recent' ? t('최근 수정 순') : t('트리 순서');
  order.title = st.order === 'recent' ? t('누르면 트리 순서로') : (st.mode === 'files' ? t('누르면 최근 수정한 파일부터') : t('누르면 최근 수정한 문서부터'));
  for (const b of $$('.parts-send', pane.view)) b.hidden = st.mode !== 'parts';
}

/** 화면을 지금 상태로 다시 그린다 — 뼈대는 그대로 두고 단추·목록만 (거르기 칸의 초점과 이미 옮겨 온 덩어리를 지킨다) */
function draw(pane) {
  if (!isParts(pane) || !pane.tab) return;
  const st = pane.gather;
  saveHeights(pane);
  keep(pane, () => {
    drawHead(pane);
    q(pane, '.parts-sub').hidden = true;
    st.listed = [];
    st.fileRows = new Map();
    if (st.mode === 'files') drawFiles(pane);
    else if (st.mode === 'meta') drawMeta(pane);
    else drawParts(pane);
  });
  for (const b of /** @type {HTMLButtonElement[]} */ ($$('.parts-send', pane.view))) b.disabled = !st.listed.length;
  watch(pane);
  setStatus({ path: st.scope ? t('모아 보기 — {path}/', { path: st.scope }) : t('모아 보기 — {name} (프로젝트 전체)', { name: pane.tab.name }), info: q(pane, '.parts-info').textContent }, pane);
}

function drawParts(pane) {
  const { tab } = pane;
  const st = pane.gather;
  const list = q(pane, '.parts-list');
  const groups = collected(tab, st);
  // 종류 버튼: 범위 안의 개수
  const counts = Object.fromEntries(KINDS.map((k) => [k, 0]));
  for (const g of groups) for (const it of g.items) counts[it.kind] += 1;
  const reading = tab.partsScan ? t('문서 읽는 중 {done}/{total}', { done: tab.partsScan.done, total: tab.partsScan.total }) : '';
  if (st.autoKind && !reading) {   // 종류를 정하지 않고 열었는데 그 범위에 없으면, 있는 첫 종류로
    if (!counts[st.kind]) st.kind = KINDS.find((k) => counts[k]) || st.kind;
    st.autoKind = false;
  }
  setHtml(q(pane, '.parts-kinds'), KINDS.map((k) => [html`<button type="button" role="tab" data-kind="${k}" aria-selected="${k === st.kind}"`, html` class="${k === st.kind ? 'active' : ''}${counts[k] ? '' : ' zero'}"><svg aria-hidden="true"><use href="#${PARTS[k].icon}"/></svg>${PARTS[k].many}`, html`<span class="n">${counts[k]}</span></button>`]));
  // 종류 아래 단추 (할 일·링크·출처 — D62): 범위 안의 그 종류를 단추마다 센다
  const subs = SUBS[st.kind];
  const sub = subs?.find(([k]) => k === st.sub[st.kind]) || subs?.[0];
  if (subs) {
    const of = (test) => groups.reduce((n, g) => n + g.items.filter((it) => it.kind === st.kind && test(it)).length, 0);
    setHtml(q(pane, '.parts-sub'), subs.map(([k, label, test]) => [html`<button type="button" data-sub="${k}" aria-pressed="${k === sub[0]}"`, html` class="${k === sub[0] ? 'active' : ''}">${label}<span class="n">${of(test)}</span></button>`]));
    q(pane, '.parts-sub').hidden = false;
  }
  const subTest = sub ? sub[2] : () => true;
  // 목록
  const spread = SPREAD.has(st.kind);
  const match = matcher(st.filter);
  const seen = new Map();   // 그림 → 처음 보인 칸의 '다른 문서' 목록 (같은 그림을 한 번만)
  let shown = 0;
  let docs = 0;
  const found = [];
  const tell = telling(groups.map((g) => g.file), { folders: true });   // 문서 머리는 '제목' 설정대로, 같은 제목이면 파일 이름을 흐리게 (D179)
  for (const { file, items } of groups) {
    const title = file.title || basename(file.path);
    let mine = items.filter((it) => it.kind === st.kind && subTest(it)
      && match(it.name, it.label, it.caption, it.text, it.target, it.section, it.alt, title, file.path, it.body));
    if (!mine.length) continue;
    const others = new Map();   // 그림 → 같은 그림을 쓰는 다른 문서들
    if (st.kind === 'figure') {
      mine = mine.filter((it) => {
        const key = it.src ? imageKey(it.src, file.path, tab) : `${file.path}#${it.n}`;
        if (seen.has(key)) {
          seen.get(key).push(file.path);
          return false;
        }
        const list2 = [];
        seen.set(key, list2);
        others.set(it, list2);
        return true;
      });
      if (!mine.length) continue;
    }
    if (shown >= MAX_SHOWN) break;   // 같은 그림의 '+N곳'은 여기까지 읽은 문서로 센다
    shown += mine.length;
    docs += 1;
    found.push({ file, mine, others });
  }
  st.listed = found.flatMap(({ file, mine }) => mine.map((item) => ({ file, item })));
  // 묶음마다 한 요소 — 이미 요소를 옮겨 온 묶음은 그대로 다시 쓴다 (같은 문서·같은 항목이면. 읽는 중에 다시 그리거나 거르기를 고쳐도 깜빡이지 않게)
  const old = new Map(/** @type {HTMLElement[]} */ ([...list.children]).filter((el) => el.classList.contains('pv-filled')).map((el) => [el.dataset.key, el]));
  const theme = themeNow();
  const els = found.map(({ file, mine, others }) => {
    const label = labelOf(file);
    const key = [file.path, tab.partsCache.get(file.path).mtime, st.kind, theme, label, tell(file), mine.map((it) => `${it.n}+${(others.get(it) || []).join(',')}`).join(' ')].join('|');
    const had = spread ? old.get(key) : null;
    if (had) return had;
    const el = document.createElement('section');
    el.className = `pv-group${spread ? ' pv-spread' : ''}`;
    el.dataset.key = key;
    el.dataset.doc = file.path;
    const head = [html`<div class="pt-doc" tabindex="0" data-doc="${file.path}" title="${file.path}">`, html`<span class="label">${label}${tellHtml(tell(file))}</span>${dirname(file.path) ? html`<span class="sub">${dirname(file.path)}</span>` : ''}</div>`];
    setHtml(el, spread ? [head, html`<div class="pv-chunks${GRID.has(st.kind) ? ' pv-grid' : ''}">${mine.map((it) => chunkHtml(file, it, st, others.get(it)))}</div>`]
      : [head, mine.map((it) => itemRow(file, it))]);
    return el;
  });
  list.replaceChildren(...els);
  const words = wordsOf(st.filter);
  for (const el of els) if (el.classList.contains('pv-filled') && el.dataset.hits !== words.join(' ')) markHits(el, words);
  // 목차 패널: 모은 것의 차례 — 문서와 그 아래 구성 요소 (D196)
  const outline = [];
  found.forEach(({ file, mine }, i) => {
    outline.push({ level: 0, name: labelOf(file), tip: file.path, el: els[i].firstElementChild });
    const rows = $$('.pv-chunk, .pt-item', els[i]);
    mine.forEach((it, k) => {
      const { main, sub: under } = itemTexts(it);
      outline.push({ level: 1, name: spread ? it.name : main, label: spread ? it.caption || it.label : under, icon: PARTS[it.kind].icon, el: rows[k] });
    });
  });
  setToc(pane, pane.view, { title: t('모아 보기'), items: outline });
  // 알림: 개수, 거른 결과, 읽는 중
  const kind = PARTS[st.kind];
  const name = kind.many.toLowerCase();   // 영어는 문장 속 복수형 (한국어는 그대로)
  const total = counts[st.kind];
  let info;
  if (!total) info = reading || t('이 범위에는 {name}{josa} 없습니다', { name, josa: josa(name, '이', '가') });   // i18n-ok (조사)
  else {
    info = st.filter || (sub && sub[0] !== 'all') ? t('거른 결과 {shown}개 (모두 {total}개)', { shown, total })
      : `${t('문서 {n}개', { n: docs })}, ${t('{kind} {n}개', { kind: (total === 1 ? kind.name : kind.many).toLowerCase(), n: total })}`;
    if (shown >= MAX_SHOWN) info += ` — ${t('처음 {n}개만, 거르기로 좁히세요', { n: MAX_SHOWN })}`;
    if (reading) info += ` · ${reading}`;
  }
  q(pane, '.parts-info').textContent = info;
}

// ---- 요소 옮겨 오기 (D196) ------------------------------------------------------

/** 거르기에 맞은 낱말을 옮겨 온 요소 안에서 표시한다 (그림·수식·단추 안은 빼고). 앞의 표시는 걷는다 */
function markHits(group, words) {
  for (const m of $$('mark.pv-hit', group)) {
    const parent = m.parentNode;
    m.replaceWith(...m.childNodes);
    parent?.normalize();
  }
  group.dataset.hits = words.join(' ');
  if (!words.length) return;
  for (const body of $$('.pv-body.md-body', group)) {
    const walk = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (n.parentElement?.closest('svg, .katex, button, .code-tools, .lec-chart-tools, .lec-chart-data, script, style') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    });
    /** @type {Text[]} */
    const texts = [];
    for (let n = walk.nextNode(); n; n = walk.nextNode()) if (n instanceof Text) texts.push(n);
    for (const node of texts) {
      const low = node.data.toLowerCase();
      if (low.length !== node.data.length) continue;   // 소문자로 바꾸면 길이가 달라지는 글자 — 자리가 어긋난다
      const spans = [];
      for (const w of words) for (let i = low.indexOf(w); i >= 0; i = low.indexOf(w, i + w.length)) spans.push([i, i + w.length]);
      if (!spans.length) continue;
      spans.sort((x, y) => x[0] - y[0]);
      /** @type {(string | Node)[]} */
      const out = [];
      let at = 0;
      for (const [a, b] of spans) {
        if (a < at) continue;
        if (a > at) out.push(node.data.slice(at, a));
        const m = document.createElement('mark');
        m.className = 'pv-hit';
        m.textContent = node.data.slice(a, b);
        out.push(m);
        at = b;
      }
      if (at < node.data.length) out.push(node.data.slice(at));
      node.replaceWith(...out);
    }
  }
}

/** 옮겨 온 덩어리의 높이를 적어 둔다 — 이 화면을 다시 그릴 때(뒤로 돌아왔을 때) 그 자리를 잡아 스크롤 위치가 맞게 */
function saveHeights(pane) {
  if (!isParts(pane)) return;
  const st = pane.gather;
  for (const chunk of /** @type {HTMLElement[]} */ ($$('.pv-done .pv-chunk', pane.view))) {
    const h = chunk.offsetHeight;
    if (h) st.heights.set(`${chunk.dataset.doc}|${chunk.dataset.kind}|${chunk.dataset.n}`, h);
  }
}

/**
 * 묶음(그 문서의 덩어리들)에 실제 요소를 옮겨 온다: 그 문서를 화면 밖에서 그려(prepared — 읽을 때와 같은 규칙) 같은 종류·번호의 요소를 찾고,
 * 캡션·몸체·주·자료를 복제해 본문처럼 다듬는다 (doc.js 의 finishPart — 그림·링크·표의 [복사]·전시물 묶음). html 문서의 것은 남의 DOM 이라 정화해서 넣는다.
 * 다이어그램·차트는 화면에 붙은 뒤에 그린다 (크기를 잰다). 그사이 문서가 바뀌어 찾지 못하면 이름만 남긴다 (곧 다시 읽고 다시 그린다)
 */
async function fillGroup(pane, group) {
  if (!group.isConnected || group.classList.contains('pv-filled') || !isParts(pane)) return;
  const { tab } = pane;
  const path = group.dataset.doc;
  let doc = null;
  try {
    doc = await prepared(tab, path);
  } catch { /* 읽는 사이 지워진 문서 — 이름만 */ }
  if (!group.isConnected || group.classList.contains('pv-filled')) return;
  group.classList.add('pv-filled');
  for (const chunk of /** @type {HTMLElement[]} */ ($$('.pv-chunk', group))) {
    const hold = chunk.querySelector('.pv-body');
    const row = doc?.rows.find((r) => r.kind === chunk.dataset.kind && r.n === Number(chunk.dataset.n));
    hold.classList.remove('pv-wait');
    if (!row) {   // 읽은 뒤에 문서가 바뀌었다 — 이름만 두고 알린다 (곧 다시 읽어 다시 그린다)
      hold.classList.add('pv-gone');
      hold.querySelector('.pv-hold')?.setAttribute('data-gone', t('문서가 바뀌어 다시 읽습니다'));
      continue;
    }
    const body = document.createElement('div');
    body.className = 'pv-body md-body';
    const nodes = partNodes(row.el);
    if (doc.foreign) {   // html 문서 — 정화해서 (스크립트·이벤트 속성을 걷고 그림 주소는 data-src 로), 표·코드는 본문처럼 꾸민다
      setHtml(body, raw(sanitizeHtml(nodes.map((n) => n.outerHTML).join(''))));
      prepareParts(body);
    } else body.append(...nodes.map((n) => n.cloneNode(true)));
    finishPart(body, path, tab);
    hold.replaceWith(body);
  }
  for (const body of /** @type {HTMLElement[]} */ ($$('.pv-body.md-body', group))) fitTables(body);
  markHits(group, wordsOf(pane.gather.filter));
  const box = group.querySelector('.pv-chunks');
  if (box.querySelector('pre.mermaid, pre.lec-chart')) {   // 다이어그램·차트는 따로 줄을 서서 — 라이브러리를 불러오는 동안 다른 묶음이 기다리지 않게
    const st = pane.gather;
    st.drawing = (st.drawing || Promise.resolve()).then(() => drawGraphics(pane, group, path)).catch(() => {});
    return;
  }
  settle(pane, group);
}

/** 묶음의 다이어그램·차트를 화면에서 그린다 (붙어 있어야 크기를 잰다 — 본문은 화면 밖 무대에서 그린 뒤 바꿔 끼우지만 여기는 덩어리마다 따로다) */
async function drawGraphics(pane, group, path) {
  if (!group.isConnected) return;
  const box = group.querySelector('.pv-chunks');
  try {
    await renderMermaid(box);
    await renderCharts(box, { tab: pane.tab, path, sanitize: sanitizeHtml, resolveRef });
  } catch { /* 그리지 못한 것은 각자 까닭을 보인다 */ }
  for (const body of /** @type {HTMLElement[]} */ ($$('.pv-body.md-body', group))) settlePart(body);
  settle(pane, group);
}

/** 다 옮겨 온 묶음: 잡아 둔 자리를 풀고 높이를 적는다 */
function settle(pane, group) {
  for (const chunk of /** @type {HTMLElement[]} */ ($$('.pv-chunk', group))) chunk.style.minHeight = '';
  group.classList.add('pv-done');
  requestAnimationFrame(() => saveHeights(pane));
}

/** 묶음이 화면에 가까워지면 요소를 옮겨 오고(하나씩 — 다이어그램·차트 라이브러리가 무겁다), 파일 종류의 그림 칸은 그림을 불러온다 */
function watch(pane) {
  const st = pane.gather;
  const { tab } = pane;
  st.io?.disconnect();
  st.io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      st.io.unobserve(e.target);
      const el = /** @type {HTMLElement} */ (e.target);
      if (el.classList.contains('pt-pic')) {   // 파일 종류의 그림 파일 (D50) — 그 파일 그대로
        const img = document.createElement('img');
        img.alt = '';
        img.addEventListener('error', () => { setHtml(el, html`<span class="image-off">${t('그림을 그리지 못했습니다')}</span>`); }, { once: true });
        img.src = docUrl(tab, el.dataset.fileSrc);
        el.append(img);
      } else st.queue = (st.queue || Promise.resolve()).then(() => fillGroup(pane, el)).catch(() => {});
    }
  }, { root: pane.scroller, rootMargin: '700px 0px' });
  for (const el of $$('.pv-group.pv-spread:not(.pv-filled), .pt-pic:empty', pane.view)) st.io.observe(el);
}

// ---- 문서 정보 (D62) ----------------------------------------------------------
// 맨 앞 설정(frontmatter)의 키마다 값으로 문서를 묶는다. 위 단추는 키(그 키가 있는 문서 수), 목록은 값마다 문서들 —
// 그 키가 없는 문서(맨 앞 설정은 있는)는 끝에 '값 없음'. Lectern 슬라이드의 Marp 설정과 제목·요약처럼 문서마다 다른 긴 값은 키로 보이지 않는다.

const META_SKIP = new Set(['marp', 'pptxStyle', 'templates', 'style', 'theme', 'size', 'headingDivider', 'paginate', 'header', 'footer', 'class', 'backgroundColor',
  'backgroundImage', 'backgroundPosition', 'backgroundRepeat', 'backgroundSize', 'color', 'math', 'title', 'name', 'description', 'lang']);
const DATE_LIKE = /^\d{4}(?:[-./]\d{1,2}){0,2}/;

const metaValues = (v) => (Array.isArray(v) ? v : [v]).map((x) => String(x ?? '').trim()).filter((x) => x && x.length <= 120);

function drawMeta(pane) {
  const { tab } = pane;
  const st = pane.gather;
  setToc(pane, null);
  const docs = tab.files.filter((f) => inScope(f.path, st.scope) && tab.partsCache?.get(f.path)?.meta)
    .map((f) => ({ file: f, meta: tab.partsCache.get(f.path).meta }))
    .filter((d) => Object.keys(d.meta).some((k) => !META_SKIP.has(k)));   // Lectern 슬라이드의 Marp 설정뿐인 것 등은 빼고
  if (st.order === 'recent') docs.sort((a, b) => b.file.mtime - a.file.mtime);
  const counts = new Map();
  for (const d of docs) {
    for (const [k, v] of Object.entries(d.meta)) if (!META_SKIP.has(k) && metaValues(v).length) counts.set(k, (counts.get(k) || 0) + 1);
  }
  const keys = [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a) || natCompare(a, b));
  if (!counts.has(st.mkey)) st.mkey = keys[0] || null;
  setHtml(q(pane, '.parts-kinds'), keys.map((k) => [html`<button type="button" role="tab" data-mkey="${k}" aria-selected="${k === st.mkey}"`, html` class="${k === st.mkey ? 'active' : ''}">${k}<span class="n">${counts.get(k)}</span></button>`]));
  const reading = tab.partsScan ? t('문서 읽는 중 {done}/{total}', { done: tab.partsScan.done, total: tab.partsScan.total }) : '';
  const list = q(pane, '.parts-list');
  if (!st.mkey) {
    list.replaceChildren();
    q(pane, '.parts-info').textContent = reading || t('이 범위의 문서에는 맨 앞 설정(frontmatter)이 없습니다');
    return;
  }
  const match = matcher(st.filter);
  const byValue = new Map();
  const none = [];
  for (const d of docs) {
    const title = d.file.title || basename(d.file.path);
    const values = metaValues(d.meta[st.mkey]);
    if (!values.length) {
      if (match(title, d.file.path)) none.push(d.file);
      continue;
    }
    for (const v of values) {
      if (!match(title, d.file.path, v)) continue;
      if (!byValue.has(v)) byValue.set(v, []);
      byValue.get(v).push(d.file);
    }
  }
  const values = [...byValue.keys()];
  const dates = values.length && values.every((v) => DATE_LIKE.test(v));
  const numbers = values.length && values.every((v) => /^-?\d+(\.\d+)?$/.test(v));
  values.sort(dates ? (a, b) => natCompare(b, a) : numbers ? (a, b) => a - b : (a, b) => byValue.get(b).length - byValue.get(a).length || natCompare(a, b));
  const tell = telling(docs.map((d) => d.file), { folders: true });
  const row = (f) => [html`<div class="pt-doc pt-mdoc" tabindex="0" data-doc="${f.path}" title="${f.path}">`, html`<span class="label">${labelOf(f)}${tellHtml(tell(f))}</span>${dirname(f.path) ? html`<span class="sub">${dirname(f.path)}</span>` : ''}</div>`];
  const group = (label, files, cls = '') => html`<div class="pt-val${cls}"><span class="label">${label}</span><span class="n">${files.length}</span></div>${files.map(row)}`;
  setHtml(list, [values.map((v) => group(v, byValue.get(v))), (none.length ? group(t('값 없음'), none, ' none') : '')]);
  q(pane, '.parts-info').textContent = [`${t('문서 {n}개', { n: docs.length })}, ${t('값 {n}가지', { n: values.length })}`, reading].filter(Boolean).join(' · ');
}

// ---- 파일 종류 (D50) ----------------------------------------------------------
// 범위 안의 파일을 묶음(문서·코드·자료)마다 형식별로 센다 (icons.js 의 fileType — 엑셀·파워포인트·워드·한글은 한 이름, 나머지는 확장자).
// 문서는 탭의 트리, 코드·자료는 '코드'·'자료' 목록과 같은 것 (others.js — 제외 폴더 안은 세지 않는다). 그림 파일은 작은 그림 격자.
// 행은 others.js 의 bindFileRows — 문서·코드는 한 번 누르면 열고, 자료는 두 번 누르거나 Enter.

const GROUPS = [['docs', t('문서')], ['code', t('코드')], ['others', t('자료')]];

/** 범위 안의 파일: [{f, group, type, key}] */
function fileEntries(tab, st) {
  const all = [...tab.files.map((f) => [f, 'docs']), ...otherFiles(tab).map((f) => [f, isCode(f.name) ? 'code' : 'others'])];
  return all.filter(([f]) => inScope(f.path, st.scope)).map(([f, group]) => {
    const type = fileType(f.name);
    return { f, group, type, key: `${group}:${type.key}` };
  });
}

/** 트리 순서: 폴더마다 하위 폴더 먼저, 그다음 파일 (자연 정렬) */
function treeOrder(a, b) {
  const x = a.split('/');
  const y = b.split('/');
  for (let i = 0; i < Math.min(x.length, y.length); i++) {
    if (x[i] === y[i]) continue;
    const dirX = i < x.length - 1;
    if (dirX !== i < y.length - 1) return dirX ? -1 : 1;
    return natCompare(x[i], y[i]);
  }
  return x.length - y.length;
}

function drawFiles(pane) {
  const { tab } = pane;
  const st = pane.gather;
  setToc(pane, null);
  const list = q(pane, '.parts-list');
  const o = tab.others;
  const entries = fileEntries(tab, st);
  const chips = new Map();   // 'docs:md' → {group, type, n, icon}
  for (const e of entries) {
    if (!chips.has(e.key)) chips.set(e.key, { group: e.group, type: e.type, n: 0, icon: fileIcon(e.f.name, e.f.kind, e.f.deck) });
    chips.get(e.key).n += 1;
  }
  const reading = !o.data && !o.error ? t('파일 목록을 읽는 중…') : '';
  if (!chips.has(st.ftype) && !reading) {   // 고른 형식이 이 범위에 없으면: 자료 → 코드 → 문서 순으로, 그 안에서 가장 많은 것
    const order = ['others', 'code', 'docs'];
    const [best] = [...chips.entries()].sort(([, a], [, b]) => order.indexOf(a.group) - order.indexOf(b.group) || b.n - a.n);
    if (best) st.ftype = best[0];
  }
  setHtml(q(pane, '.parts-kinds'), GROUPS.map(([group, name]) => {
    const mine = [...chips.entries()].filter(([, c]) => c.group === group)
      .sort(([, a], [, b]) => b.n - a.n || natCompare(a.type.label, b.type.label));
    if (!mine.length) return '';
    return html`<div class="ft-group"><span class="ft-label">${name}</span>${mine.map(([key, c]) => [html`<button type="button" role="tab" data-ftype="${key}"`, html` aria-selected="${key === st.ftype}" class="${key === st.ftype ? 'active' : ''}">${c.icon}${c.type.label}<span class="n">${c.n}</span></button>`])}</div>`;
  }));
  // 목록: 고른 형식의 파일 (거르기는 이름·경로, 문서는 제목도)
  const match = matcher(st.filter);
  let files = entries.filter((e) => e.key === st.ftype && match(e.f.name, e.f.path, e.f.title || '')).map((e) => e.f);
  files.sort(st.order === 'recent' ? (a, b) => b.mtime - a.mtime : (a, b) => treeOrder(a.path, b.path));
  const matched = files.length;
  files = files.slice(0, MAX_SHOWN);
  st.fileRows = new Map(files.map((f) => [f.path, f]));
  const tellFiles = telling(files.filter((f) => f.kind), { folders: true });   // 같은 제목의 문서 (D179)
  const [group, typeKey] = (st.ftype || '').split(':');
  const markup = group === 'others' && PICTURE_EXT.has(typeKey)
    ? html`<div class="pt-grid">${files.map((f) => [html`<div class="ft-thumb" tabindex="0" data-file="${f.path}" title="${fileTip(f)}">`, html`<div class="pt-pic" data-file-src="${f.path}"></div><span class="pt-cap">${f.name}</span></div>`])}</div>`
    : files.map((f) => [html`<div class="row ft-row" tabindex="0" data-file="${f.path}"`, html` title="${f.kind ? tipOf(f) : fileTip(f)}">${fileIcon(f.name, f.kind, f.deck)}<span class="label">${f.kind ? labelOf(f) : f.name}${f.kind ? tellHtml(tellFiles(f)) : ''}</span>`, html`${dirname(f.path) ? html`<span class="sub">${dirname(f.path)}</span>` : ''}</div>`]);
  setHtml(list, markup);
  const total = chips.get(st.ftype)?.n || 0;
  let info;
  if (reading) info = reading;
  else if (o.error && !o.data) info = o.error;
  else if (!chips.size) info = t('이 범위에는 파일이 없습니다');
  else {
    info = st.filter ? t('거른 결과 {shown}개 (모두 {total}개)', { shown: matched, total }) : t('파일 {n}개', { n: total });
    if (matched > MAX_SHOWN) info += ` — ${t('처음 {n}개만, 거르기로 좁히세요', { n: MAX_SHOWN })}`;
  }
  q(pane, '.parts-info').textContent = info;
}

/** 받침이 있으면 a, 없으면 b (표가 / 그림이) */
function josa(word, a, b) {
  const code = word.charCodeAt(word.length - 1) - 0xac00;
  return code >= 0 && code < 11172 && code % 28 ? a : b;
}

// ---- 화면 (nav.js 의 렌더러) -----------------------------------------------------

/** 범위의 문서를 (바뀐 것만) 읽고 그린다 — 읽는 동안에도 받아 둔 것으로 먼저 보인다 */
async function load(pane) {
  const { tab } = pane;
  const st = pane.gather;
  if (st.mode === 'files') {
    const others = loadOthers(tab);   // 받아 둔 목록이 그대로면 바로 끝난다
    draw(pane);
    await others;
    draw(pane);
    return;
  }
  const job = scan(tab, st.scope);   // 읽을 것이 있으면 여기서 바로 '읽는 중'이 된다 (첫 await 전까지는 이어서 돈다)
  draw(pane);
  await job;
  for (const p of partsPanes(tab)) draw(p);
}

/**
 * 모아 보기를 칸(pane)에 그린다 (화면 종류 'parts' — path 는 범위 폴더). 이미 모아 보기를 보이는 칸이면 뼈대를 두고 목록만 다시 그린다
 * (자동 새로고침·범위 바꾸기 — 거르기 칸의 글과 초점, 옮겨 온 요소를 지킨다). 문서는 그린 뒤에 읽는다 (읽는 동안 '읽는 중')
 * @param {Pane} pane
 * @param {string} path
 * @param {ShowOptions} [options]
 */
export async function showParts(pane, path, { scrollTop } = {}) {
  pane.renderId += 1;   // 이 칸에서 그리던 다른 화면은 버려진다
  const { view, tab } = pane;
  const st = (pane.gather ??= { ...DEFAULT, ...(tab.side.parts || {}), scope: null, heights: new Map(), fileRows: new Map(), listed: [], io: null, queue: null, drawing: null, later: null });
  const asked = wish && wish.path === path && Date.now() - wish.at < 5000 ? wish : null;   // 폴더 개요의 버튼·우클릭이 정한 종류
  if (asked) {
    wish = null;
    Object.assign(st, { mode: asked.mode, filter: '', autoKind: !asked.kind }, asked.kind ? { kind: asked.kind } : {});
    remember(pane);
  }
  const kept = view.classList.contains('parts-view') && !!view.querySelector(':scope > .parts-list');
  const moved = !kept || st.scope !== path || !!asked;
  st.scope = path;
  const top = typeof scrollTop === 'function' ? scrollTop() : scrollTop;   // 함수면 바꿔 끼우기 직전의 위치 (refreshView)
  if (!kept) {
    view.className = 'parts-view';
    delete view.dataset.docPath;   // 앞에 보던 md 문서의 경로 — 남아 있으면 그 문서의 기능(스타일·내보내기의 판정)이 이 화면에서 켜진다
    setHtml(view, skeleton());
    setDocSource(pane, null);
    clearChanges(pane);
  }
  load(pane);   // 받아 둔 것으로 바로 그리고(첫 await 전), 바뀐 문서를 읽으며 다시 그린다 — 기다리지 않는다
  if (moved) pane.scroller.scrollTop = kept ? 0 : top ?? 0;
  emit('rendered', pane);
  return true;
}

/** 모을 것·종류·순서를 프로젝트 탭에 남긴다 — 다음에 여는 모아 보기가 여기서 시작한다 */
function remember(pane) {
  pane.tab.side.parts = Object.fromEntries(KEEP.map((k) => [k, pane.gather[k]]));
}

// ---- 열기 ---------------------------------------------------------------------

/** 목록의 행(.pv-chunk·.pt-item)이 가리키는 문서와 구성 요소 */
function itemOf(tab, el) {
  const path = el.dataset.doc;
  const item = tab?.partsCache?.get(path)?.items.find((it) => it.kind === el.dataset.kind && it.n === Number(el.dataset.n));
  return item ? { path, item } : null;
}

async function copy(text, what) {
  toast(await copyText(text) ? t('복사했습니다: {what}', { what }) : t('복사하지 못했습니다'));
}

/** Claude용 위치: '@경로 12~19행 ('캡션')' — 할 일·출처는 그 글(40자까지) */
function refOf(path, item) {
  const note = item.caption || (item.kind === 'task' || item.kind === 'source' ? (item.text.length > 40 ? `${item.text.slice(0, 39)}…` : item.text) : '');
  return `@${path}${item.lines ? ` ${rangeText(item.lines)}` : ''}${note ? ` ('${note}')` : ''}`;
}

/**
 * 구성 요소를 담을 조각으로 (D63 — basket.js 의 snippetOf). lines: 그 문서의 원문 줄들 (html 문서는 null).
 * 링크는 그 링크 하나(경로 표기는 글 그대로), 각주는 그 글을 단락으로, 그 밖은 원문 줄 범위(캡션·'자료:' 줄까지). 담을 수 없으면 null
 */
function itemSnippet(path, lines, item) {
  const doc = { path, lines: lines || [] };
  const info = { kind: item.kind, name: item.name, label: item.caption || item.text || item.label || '' };
  if (item.kind === 'link') {
    if (item.pathLink) return snippetOf(doc, item.take, { ...info, text: item.text, plain: true });
    return snippetOf(doc, item.take, { ...info, text: `[${(item.text || item.href).replace(/[[\]]/g, '\\$&')}](${item.href})` });
  }
  if (item.kind === 'source' && item.note) return snippetOf(doc, item.take, { ...info, text: item.text, plain: true });
  return lines && item.take ? snippetOf(doc, item.take, info) : null;
}

/** 항목들을 조각으로: 문서마다 원문을 한 번 읽어 차례대로 {snips, skipped(원문이 없는 html 문서의 것)} */
async function snippetsOf(tab, entries) {
  const texts = new Map();
  const snips = [];
  let skipped = 0;
  for (const { file, item } of entries) {
    if (!texts.has(file.path)) {
      let lines = null;
      if (!isHtml(file.path)) {
        try {
          lines = (await getText(docUrl(tab, file.path))).replace(/^﻿/, '').split(/\r\n?|\n/);
        } catch { /* 읽는 사이 지워진 문서 */ }
      }
      texts.set(file.path, lines);
    }
    const snip = itemSnippet(file.path, texts.get(file.path), item);
    if (snip) snips.push(snip);
    else skipped += 1;
  }
  return { snips, skipped };
}

const skippedNote = (n) => (n ? t('{n}개는 원문이 없어(html 문서) 담지 않았습니다', { n }) : '');

/** 지금 목록에 보이는 것 모두 담기 — html 문서의 것(원문 줄이 없음)은 빼고 알린다 */
async function takeAll(tab, entries, to = null) {
  const { snips, skipped } = await snippetsOf(tab, entries);
  if (tab === S.tab) addSnippets(snips, skippedNote(skipped), to);
}

/** '새 문서로' (D196): 보이는 것을 문서 차례대로 새 md 하나에 — 경로는 보내기 창에서 사용자가 정한다 (basket.js, D65) */
async function sendToDoc(pane) {
  const { tab } = pane;
  const { snips, skipped } = await snippetsOf(tab, pane.gather.listed);
  if (tab !== S.tab) return;
  if (!snips.length) {
    toast(t('새 문서로 보낼 것이 없습니다 — html 문서의 것은 원문이 없어 보내지 못합니다'));
    return;
  }
  if (skipped) toast(skippedNote(skipped));
  sendSnippets(snips, { fresh: true });
}

/** 'AI 에' (D196): 보이는 것의 위치 목록을 터미널에 — 한 줄로, Enter 는 누르지 않는다 (무엇을 시킬지는 사용자가 이어서 적는다) */
function sendToAi(pane) {
  const list = pane.gather.listed;
  if (!list.length) return;
  if (list.length > MAX_SEND) {
    toast(t('{n}개는 한 번에 넘기기에 많습니다 — 거르기로 {max}개까지 좁히세요', { n: list.length, max: MAX_SEND }));
    return;
  }
  emit('term-paste', `${list.map(({ file, item }) => refOf(file.path, item)).join(', ')} `);
}

/** 구성 요소의 우클릭 메뉴 (D61): 문서에서 보기, Claude용 위치·원문 복사(옆에 터미널 버튼 — D51), 담기·보내기(D63·D65), 문서 경로 */
async function partMenu(pane, el, x, y) {
  const tab = pane.tab;
  const found = itemOf(tab, el);
  if (!found) return;
  const { path, item } = found;
  const range = item.lines;
  const ref = refOf(path, item);
  /** @type {MenuItem[]} */
  const copies = [{ label: t('위치 복사'), tip: ref, action: () => copy(ref, ref), term: `${ref} ` }];
  if (item.kind === 'link') copies.push({ label: t('링크 주소 복사'), tip: item.target, action: () => copy(item.target, item.target), term: item.target });
  let lines = null;   // 그 문서의 원문 줄들 (md)
  if (!isHtml(path)) {
    try {
      lines = (await getText(docUrl(tab, path))).replace(/^﻿/, '').split(/\r\n?|\n/);
    } catch { /* 읽는 사이 지워진 문서 — 원문 항목 없이 */ }
    if (tab !== S.tab) return;
  }
  const source = range && lines ? lines.slice(range[0] - 1, range[1]).join('\n') : '';
  if (source) copies.unshift({ label: t('원문 복사'), tip: `Markdown ${rangeText(range)}`, action: () => copy(source, `${path} ${rangeText(range)}`), term: source });
  // 담기·보내기 (D63·D65) — 그 하나, 또는 지금 목록에 보이는 것 모두
  const snip = itemSnippet(path, lines, item);
  const listed = pane.gather.listed;
  /** @type {MenuItem[]} */
  const takes = [];
  if (snip) {
    takes.push({ label: clipLabel(t('담기')), hint: el.matches('.pv-chunk, .pt-item') ? 'Alt+C' : '', tip: t('지금 담기함에 — 사이드바 \'담기\' 탭에서 모아 보고 보냅니다'), action: () => addSnippets([snip]) },
      { label: t('다른 담기함에 담기…'), hint: el.matches('.pv-chunk, .pt-item') ? 'Alt+Shift+C' : '', tip: t('담기함을 고르거나 새로 만들어 담습니다'), action: () => boxMenu(x, y, (to) => addSnippets([snip], '', to)) },
      { label: t('문서로 보내기…'), tip: t('열린 문서 탭이나 새 문서로 바로'), action: () => sendSnippets([snip]) },
      { label: t('새 메모로 보내기'), tip: t('이 프로젝트의 메모에 — 어디서 왔는지도 함께'), action: () => emit('new-note', { body: snip.text, path, line: range?.[0] || 0, end: range?.[1] || 0 }) });
  }
  if (listed.length > 1) {
    takes.push({ label: t('보이는 것 모두 담기 ({n}개)', { n: listed.length }), tip: t('지금 목록의 것을 문서 차례대로 — 거르기·단추로 좁힌 그대로'), action: () => takeAll(tab, listed) });
  }
  const items = menuGroups([{ header: `${item.name} · ${path}` }], [{ label: t('문서에서 보기'), hint: 'Enter', action: () => openItem(el) }], copies, takes, pathMenuItems(path, true));
  el.classList.add('lec-picked');
  showMenu(x, y, items, () => el.classList.remove('lec-picked'));
}

/**
 * 덩어리·행·문서 머리줄로 간다: 그 문서를 열고, 목차와 같은 규칙으로 센 같은 종류·번호의 것으로. how: 열 곳 (util.linkHow — 누르기는 이 탭에서
 * (Alt+← 로 모아 보기에 돌아온다), Ctrl+누르기·가운데 버튼은 뒤에서 새 문서 탭. 뒤에서 열면 그 탭을 열어 두기만 한다)
 */
async function openItem(el, how = {}) {
  const path = el.dataset.doc;
  if (how.behind) {
    await openTarget({ type: 'doc', path, ...how });
    return;
  }
  const there = !!docPaneOf(S.tab, { type: 'doc', path });   // 다른 문서 탭에 열려 있다 — 그 탭으로 간다 (doctabs.js)
  if (!(await openTarget({ type: 'doc', path, ...how }))) return;
  if (!el.dataset.kind) return;   // 문서 머리줄
  const row = readParts(docRoot(), { more: true }).rows.find((r) => r.kind === el.dataset.kind && r.n === Number(el.dataset.n));
  if (!row) return;
  if (there) emit('jump');   // 그 탭에서 읽던 곳을 뒤로 기록에 (nav.js, D78 — 이 탭에서 연 것은 모아 보기가 이미 기록에 있다)
  goToPart(row.el);
}

/** 모아 보기를 연다 (폴더 개요의 버튼·트리 우클릭·'코드'·'자료' 목록의 폴더 우클릭·명령 찾기). path: 범위 폴더 ('' = 프로젝트 전체),
 * kind: 문서 속 요소의 종류 (없으면 마지막에 고른 것), mode: 'files' 면 파일 종류 (아니면 문서 속 요소). 문서 탭 하나에 — 열려 있으면 그 탭에서 (doctabs.js) */
export function openParts({ path = '', kind = null, mode = 'parts' } = {}) {
  if (!S.tab) return;
  wish = { path, mode: mode === 'files' ? 'files' : 'parts', kind: kind && PARTS[kind] ? kind : null, at: Date.now() };
  emit('open', { type: 'parts', path });
}

// ---- 누르기·키 (칸의 id 가 옮겨 다니므로 #lec-panes 에서 받는다) ---------------------------

/** 이벤트가 난 모아 보기 칸 — 아니면 null */
function paneAt(e) {
  const pane = paneOf(e.target);
  return isParts(pane) && pane.view.contains(e.target) ? pane : null;
}

function onClick(e) {
  const pane = paneAt(e);
  if (!pane) return;
  const st = pane.gather;
  const at = /** @type {HTMLElement} */ (e.target);
  if (at.closest('.pv-body')) {   // 문서에서 온 글 — 문서가 심은 단추·행을 앱의 것으로 읽지 않는다. 코드의 [복사]만 여기서 (링크·그림·표의 [복사]는 각자)
    const btn = at.closest('.code-copy');
    const code = btn?.closest('.code-block')?.querySelector('pre > code');
    if (code) copy(code.textContent, t('코드'));
    return;
  }
  const top = () => { pane.scroller.scrollTop = 0; };
  const mode = at.closest('.parts-mode button[data-mode]');
  if (mode) {
    if (mode.dataset.mode === st.mode) return;
    st.mode = mode.dataset.mode;
    remember(pane);
    top();
    load(pane);
    return;
  }
  const chip = at.closest('.parts-kinds button');
  if (chip) {
    const { ftype, mkey, kind } = chip.dataset;
    if (ftype && ftype !== st.ftype) st.ftype = ftype;   // 파일 형식
    else if (mkey && mkey !== st.mkey) st.mkey = mkey;   // 문서 정보의 키 (D62)
    else if (kind && kind !== st.kind) Object.assign(st, { kind, autoKind: false });
    else return;
    remember(pane);
    top();
    draw(pane);
    return;
  }
  const sub = at.closest('.parts-sub button[data-sub]');   // 종류 아래 단추 (D62)
  if (sub) {
    st.sub = { ...st.sub, [st.kind]: sub.dataset.sub };
    remember(pane);
    top();
    draw(pane);
    return;
  }
  if (at.closest('.parts-all')) {
    emit('open', { type: 'parts', path: '' });
    return;
  }
  if (at.closest('.parts-order')) {
    st.order = st.order === 'recent' ? 'tree' : 'recent';
    remember(pane);
    draw(pane);
    return;
  }
  const send = at.closest('.parts-send');
  if (send) {
    if (send.dataset.act === 'ai') sendToAi(pane);
    else sendToDoc(pane);
    return;
  }
  const el = at.closest('.pv-go') ? at.closest('.pv-chunk') : at.closest('.pt-item, .pt-doc');
  if (el && !repeatClick(e)) openItem(/** @type {HTMLElement} */ (el), linkHow(e));
}

/** 옮겨 온 요소 안의 #절 링크는 이 화면에 그 절이 없다 — 그 문서의 그 절로 연다 (doc.js 의 bindLink 보다 먼저) */
function onAnchor(e) {
  const pane = paneAt(e);
  const a = pane && /** @type {HTMLElement} */ (e.target).closest?.('.pv-body a[href^="#"]');
  const chunk = a?.closest('.pv-chunk');
  if (!chunk) return;
  e.preventDefault();
  e.stopPropagation();
  emit('open', { type: 'doc', path: /** @type {HTMLElement} */ (chunk).dataset.doc, hash: a.getAttribute('href'), ...linkHow(e) });
}

function onInput(e) {
  const pane = paneAt(e);
  const filter = /** @type {HTMLInputElement} */ (e.target);
  if (!pane || !filter.matches?.('.parts-filter')) return;
  const st = pane.gather;
  st.filter = filter.value.trim();
  st.later ??= debounce(() => draw(pane), 150);
  st.later();
}

function onKey(e) {
  const pane = paneAt(e);
  if (!pane) return;
  const at = /** @type {HTMLElement} */ (e.target);
  if (at.matches('.parts-filter')) {
    const filter = /** @type {HTMLInputElement} */ (at);
    if (e.key === 'Enter') {
      e.preventDefault();
      pane.gather.filter = filter.value.trim();
      draw(pane);   // 거르기가 아직 반영되기 전이어도 지금 글자로 거른 첫 항목에 초점을 둔다 (Enter 를 한 번 더 누르면 그 문서로)
      (q(pane, '.parts-list .pv-chunk, .parts-list .pt-item') || q(pane, '.parts-list .pt-doc, .parts-list [data-file]'))?.focus();   // 문서 머리줄이 아니라 첫 덩어리·행
    } else if (e.key === 'Escape' && filter.value) {
      e.stopPropagation();
      filter.value = '';
      filter.dispatchEvent(new Event('input', { bubbles: true }));
    }
    return;
  }
  if (e.key === 'Enter' && !e.shiftKey && at.matches('.pv-chunk, .pt-item, .pt-doc') && !at.closest('.pv-body')) {
    e.preventDefault();
    openItem(at, linkHow(e));
  }
}

function onMenu(e) {
  const pane = paneAt(e);
  const at = /** @type {HTMLElement} */ (e.target);
  if (!pane || at.closest('input')) return;   // 거르기 칸은 기본 메뉴
  const body = at.closest('.pv-body');   // 문서에서 온 글 안이면 그 덩어리 (문서가 심은 행을 읽지 않는다)
  const el = /** @type {HTMLElement} */ (body ? body.closest('.pv-chunk') : at.closest('.pv-chunk, .pt-item, .pt-doc'));
  if (!el) return;   // 파일 행은 각자 (bindFileRows)
  e.preventDefault();
  if (el.matches('.pt-doc')) showMenu(e.clientX, e.clientY, [{ header: el.dataset.doc }, ...pathMenuItems(el.dataset.doc, true)]);   // 문서 머리줄·문서 정보의 문서
  else partMenu(pane, el, e.clientX, e.clientY);
}

/** Alt+C (D197): 초점이 있는 덩어리·행을 지금 담기함에. 이 화면이 아니면 false */
export function clipChunk(choose = false) {
  const pane = S.pane;
  if (!isParts(pane)) return false;
  const el = /** @type {HTMLElement | null} */ (document.activeElement?.closest?.('.pv-chunk, .pt-item') || null);
  const found = el && pane.view.contains(el) ? itemOf(pane.tab, el) : null;
  const entry = found && pane.gather.listed.find((x) => x.file.path === found.path && x.item === found.item);
  if (entry && choose) {
    const r = el.getBoundingClientRect();
    boxMenu(r.left + 24, Math.max(r.top, pane.scroller.getBoundingClientRect().top) + 36, (to) => takeAll(pane.tab, [entry], to));
  } else if (entry) takeAll(pane.tab, [entry]);
  else toast(t('담을 것을 누르거나 Tab 으로 고른 뒤 Alt+C 를 누르세요'));
  return true;
}

/** Ctrl+F: 모아 보기에서는 거르기 칸으로 (main.js) — 이 화면이 아니면 false */
export function focusPartsFilter() {
  if (!isParts(S.pane)) return false;
  const filter = /** @type {HTMLInputElement} */ (q(S.pane, '.parts-filter'));
  filter.focus();
  filter.select();
  return true;
}

export function initParts() {
  const panes = $('#lec-panes');
  panes.addEventListener('click', onAnchor, true);
  panes.addEventListener('click', onClick);
  panes.addEventListener('input', onInput);
  panes.addEventListener('keydown', onKey);
  panes.addEventListener('contextmenu', onMenu);
  bindFileRows(panes, (path) => (isParts(S.pane) ? S.pane.gather.fileRows.get(path) ?? null : null));   // 파일 종류의 행 (D50)
  middleClickOpens(panes, '.parts-view .pv-go, .parts-view .pt-item, .parts-view .pt-doc');   // 가운데 버튼: 뒤에서 새 문서 탭 (D64)
  const later = debounce(() => saveHeights(S.pane), 300);
  document.addEventListener('scroll', (e) => { if (e.target === S.pane?.scroller && isParts(S.pane)) later(); }, { capture: true, passive: true });
  on('parts', openParts);
  on('rendered', (pane) => { if (pane.gather && !pane.view.classList.contains('parts-view')) pane.gather.io?.disconnect(); });   // 이 칸이 다른 화면으로
  on('others', (tab) => { for (const pane of partsPanes(tab)) if (pane.gather.mode === 'files' && paneShown(pane)) load(pane); });   // 파일이 생기거나 지워짐
  on('titles', () => { for (const pane of partsPanes(S.tab)) draw(pane); });   // 문서 머리·행의 글이 '제목' 설정을 따른다 (D179)
}
