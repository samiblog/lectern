// 사이드바 '모아 보기' 탭 (D41): 프로젝트(또는 고른 폴더와 그 하위)의 표·그림·박스글·다이어그램·코드·수식을 종류마다 모아 보인다.
// 위의 '문서 속 요소' / '파일 종류'(D50)로 무엇을 모을지 고른다 — 파일 종류는 아래 '파일 종류' 절.
//
// - 문서마다 본문과 같은 해석기로 화면 밖에서 그려(md: markdown-it + 정화, html: DOMParser — 스크립트·그림을 부르지 않는다)
//   목차와 같은 규칙(toc.js 의 readParts)으로 센다. 그래서 번호·이름이 그 문서의 목차와 같다.
//   읽은 결과는 탭마다 문서의 수정 시각과 함께 기억해 두고(tab.partsCache), 바뀐 문서만 다시 읽는다.
// - 문서별로 묶어 트리 순서(또는 최근 수정 순)로. 그림은 작은 그림 격자 — 같은 그림을 여러 문서가 쓰면 처음 것 하나에 '+N곳'.
//   그림은 목록에서 보일 때 불러온다 (본문과 같은 규칙 — 프로젝트 밖은 막고 인터넷 그림은 설정 external_images).
// - 누르면 그 문서를 열고 목차와 같은 방법으로 그 자리로 간다 (접힌 절은 펴고 잠깐 테두리).
// - 여는 곳: 이 탭, 폴더 개요의 '모아 보기' 버튼, 트리의 폴더 우클릭, '코드'·'자료' 목록의 폴더 우클릭 ('parts' 이벤트 {path, kind, mode}).
// - 모을 것·종류·범위·거르기·순서·스크롤은 프로젝트 탭마다 남긴다 (tab.side.parts).
// - 차트·할 일·링크·출처 (D62): 차트는 그림처럼 작은 그림 격자 — 보일 때 화면 밖에서 그 차트를 그려(charts.js) 넣는다.
//   할 일·링크·출처는 목차에는 없고 여기서만 (readParts 의 more). 종류 아래 작은 단추로 '안 한 것'·'깨진 것'·'각주' 등을 고른다.
//   링크는 대상(문서·코드·자료·폴더·인터넷)을 가르고, 프로젝트 안의 파일이 없으면 '깨짐' (서버에 묻는다 — /api/exists).
// - 문서 정보 (D62): 맨 앞 설정(frontmatter)의 키마다 값으로 문서를 묶는다 ('문서 정보' — status·author·date 등).

import { S, on, emit } from './store.js';
import { getText, postJSON } from './api.js';
import { rangeText } from './docmenu.js';
import { showMenu } from './ui.js';
import { navigate } from './nav.js';
import { switchPanel, labelOf, tipOf, pathMenuItems } from './tree.js';
import { loadOthers, otherFiles, bindFileRows, fileTip } from './others.js';
import { fileIcon, fileType, isCode, PICTURE_EXT } from './icons.js';
import { readParts, goToPart, partExtent, PARTS } from './toc.js';
import { snippetOf, addSnippets, insertSnippets } from './basket.js';
import { renderMarkdown } from './markdown.js';
import { sanitizeHtml, prepareParts, loadImage, imageKey, resolveRef } from './doc.js';
import { linkPaths } from './pathlink.js';
import { renderCharts } from './charts.js';
import { readYaml } from './slides.js';
import {
  $, $$, esc, docUrl, isMd, isHtml, basename, dirname, debounce, keepFocus, docRoot, natCompare, toast, copyText,
} from './util.js';
import { t } from './i18n.js';

const KINDS = Object.keys(PARTS);
const MAX_SHOWN = 800;     // 목록에 그리는 항목 수 (넘으면 거르기로 좁히라고 알린다)
const PARALLEL = 4;        // 문서를 함께 읽는 수

// mode: parts(문서 속 요소) | meta(문서 정보, D62) | files(파일 종류, D50). kind: 문서 속 요소의 종류, ftype: 파일 형식 ('묶음:형식' — 'others:pdf'),
// sub: 종류 아래 단추 (할 일·링크·출처), mkey: 문서 정보의 키
const DEFAULT = { mode: 'parts', kind: 'table', ftype: null, scope: '', filter: '', order: 'tree', scroll: 0, sub: { task: 'open', link: 'all', source: 'all' }, mkey: null };

// 종류 아래 단추: [키, 이름, 맞는지]
const SUBS = {
  task: [['open', t('안 한 것'), (it) => !it.done], ['done', t('한 것'), (it) => it.done], ['all', t('모두'), () => true]],
  link: [['all', t('모두'), () => true], ['broken', t('깨진 것'), (it) => it.broken], ['web', t('인터넷'), (it) => it.type === 'web' || it.type === 'mail'],
    ['local', t('프로젝트 안'), (it) => ['doc', 'code', 'file', 'dir'].includes(it.type)]],
  source: [['all', t('모두'), () => true], ['source', t('출처'), (it) => !it.note], ['note', t('각주'), (it) => it.note]],
};
const LINK_TYPES = { doc: t('문서'), code: t('코드'), file: t('자료'), dir: t('폴더'), web: t('인터넷'), mail: t('메일'), outside: t('프로젝트 밖') };
let state = { ...DEFAULT };
let scanning = null;       // 지금 읽는 중인 {tab, scope, done, total}
let thumbs = null;         // 그림 칸이 보일 때 그림을 불러오는 IntersectionObserver
let listed = [];           // 지금 목록에 보이는 구성 요소 [{file, item}] — '보이는 것 모두 담기' (D63)

const panelShown = () => !$('#lec-parts').hidden;
const inScope = (path, scope) => !scope || path === scope || path.startsWith(`${scope}/`);

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
 * 문서 하나를 화면 밖에서 읽어 {items: 구성 요소 [{kind, n, name, label, caption, detail, section, lines, …}], meta: 맨 앞 설정}.
 * 그림은 src·alt, 차트는 chart(라이브러리)·code(원문), 할 일은 text·done, 링크는 text·target·type·broken, 출처는 text·note
 */
async function readDoc(tab, path) {
  const text = await getText(docUrl(tab, path));
  let root;
  let meta = null;
  if (isHtml(path)) {
    root = new DOMParser().parseFromString(text, 'text/html').body;   // 스크립트는 돌지 않고 그림도 부르지 않는다
  } else {
    const { html, frontMatter } = renderMarkdown(text, { math: S.config.math !== false });
    const tpl = document.createElement('template');   // template 안은 그림을 부르지 않는다 (정화가 src 도 data-src 로 뗀다)
    tpl.innerHTML = sanitizeHtml(html);
    root = tpl.content;
    prepareParts(root);
    await linkPaths(root, path, tab);   // 본문 속 경로 표기도 본문(doc.js)처럼 링크로 — 링크 번호가 본문과 같게
    meta = frontMatter ? readYaml(frontMatter) : null;
  }
  const base = new URL(docUrl(tab, path), location.origin);
  const items = readParts(root, { more: true }).rows.filter((r) => r.kind).map((r) => {
    const item = { kind: r.kind, n: r.n, name: r.name, label: r.label || '', caption: r.caption || '', detail: r.detail || '', section: r.section,
      lines: linesOf(r.el, r.capEl), take: linesOf(...partExtent(r.el).els) };   // take: 담을 범위 — 캡션과 '자료:' 줄까지 (D63)
    if (r.kind === 'figure') {
      const img = r.el.tagName === 'IMG' ? r.el : r.el.querySelector('img');
      item.src = img?.getAttribute('data-src') || img?.getAttribute('src') || '';
      item.alt = img?.getAttribute('alt') || '';
    } else if (r.kind === 'chart') {
      item.chart = r.el.dataset.chart;
      item.code = r.el.dataset.source ?? r.el.textContent;   // 화면 밖에서는 그리지 않아 원문 그대로
    } else if (r.kind === 'task') Object.assign(item, { text: r.text, done: r.done });
    else if (r.kind === 'link') Object.assign(item, linkTarget(r, base, tab), { text: r.text, href: r.href, pathLink: !!r.path });
    else if (r.kind === 'source') Object.assign(item, { text: r.text, note: r.note });
    return item;
  });
  await checkLinks(tab, items.filter((it) => it.kind === 'link'));
  return { items, meta };
}

/** 범위 안의 문서를 읽는다 (바뀐 것만). 읽는 동안 조금씩 다시 그린다. 다른 탭·범위로 새로 읽기 시작하면 멈춘다 */
async function scan(tab, scope) {
  tab.partsCache ??= new Map();
  const files = tab.files.filter((f) => inScope(f.path, scope));
  const todo = files.filter((f) => tab.partsCache.get(f.path)?.mtime !== f.mtime);
  for (const path of tab.partsCache.keys()) if (!tab.fileMap.has(path)) tab.partsCache.delete(path);   // 지워진 문서
  if (!todo.length) return;
  const job = { tab, scope, done: 0, total: todo.length };
  scanning = job;
  const redraw = debounce(() => { if (scanning === job) render(); }, 250);
  let next = 0;
  const worker = async () => {
    while (next < todo.length && scanning === job) {
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
  if (scanning === job) scanning = null;
}

// ---- 그리기 ---------------------------------------------------------------------

/** 범위 안 문서들의 항목: [{file, items}] (순서: 트리 또는 최근 수정) */
function collected(tab) {
  const files = tab.files.filter((f) => inScope(f.path, state.scope) && tab.partsCache?.has(f.path));
  if (state.order === 'recent') files.sort((a, b) => b.mtime - a.mtime);
  return files.map((file) => ({ file, items: tab.partsCache.get(file.path).items }));
}

function matcher(text) {
  const words = text.toLowerCase().split(/\s+/).filter(Boolean);
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

function itemRow(file, item, extra = '') {
  const { main, sub } = itemTexts(item);
  const long = item.caption || item.text;
  const cls = `pt-item${long ? ' has-cap' : ''}${item.done ? ' pt-done' : ''}`;
  const bad = item.broken ? `<span class="pt-bad">${esc(t('깨짐'))}</span>` : '';
  return `<div class="${cls}" tabindex="0" data-doc="${esc(file.path)}" data-kind="${item.kind}" data-n="${item.n}" title="${esc(itemTip(file, item))}">`
    + `<svg class="tp-icon" aria-hidden="true"><use href="#${PARTS[item.kind].icon}"/></svg>`
    + `<span class="pt-text"><span class="pt-name">${esc(main)}</span>${sub || bad ? `<span class="pt-label">${bad}${esc(sub)}</span>` : ''}`
    + `${item.section ? `<span class="pt-sec">${esc(item.section)}</span>` : ''}</span>${extra}</div>`;
}

/** 차트의 작은 그림 칸 — 그림은 보일 때 그린다 (drawChartThumb) */
function chartThumb(file, item) {
  return `<div class="pt-thumb pt-chart" tabindex="0" data-doc="${esc(file.path)}" data-kind="chart" data-n="${item.n}" title="${esc(itemTip(file, item))}">`
    + `<div class="pt-pic" data-chart="${esc(item.chart || '')}"></div>`
    + `<span class="pt-cap">${esc(item.caption || item.label || item.name)}</span></div>`;
}

function thumb(file, item, others) {
  const more = others.length ? `<span class="pt-more" title="${esc(`${t('같은 그림을 쓰는 다른 문서:')}\n${others.join('\n')}`)}">${t('+{n}곳', { n: others.length })}</span>` : '';
  return `<div class="pt-thumb" tabindex="0" data-doc="${esc(file.path)}" data-kind="figure" data-n="${item.n}" title="${esc(itemTip(file, item))}">`
    + `<div class="pt-pic" data-src="${esc(item.src)}" data-alt="${esc(item.alt)}"></div>`
    + `<span class="pt-cap">${esc(item.caption || item.label || item.name)}</span>${more}</div>`;
}

/** 모을 것 버튼과 거르기 칸의 안내 */
function renderMode() {
  for (const b of $$('#lec-parts-mode button')) {
    const on = b.dataset.mode === state.mode;
    b.classList.toggle('active', on);
    b.setAttribute('aria-selected', String(on));
  }
  $('#lec-parts-filter').placeholder = state.mode === 'files' ? t('이름·경로로 거르기') : state.mode === 'meta' ? t('문서·값으로 거르기') : t('이름·절·문서로 거르기');
}

/** 범위와 순서 (두 모드가 같이 쓴다) */
function renderBar(tab) {
  $('#lec-parts-scope').textContent = state.scope ? t('{folder} 폴더', { folder: state.scope }) : t('{name} 전체', { name: tab.name });
  $('#lec-parts-scope').title = state.scope ? t('{folder} 폴더와 그 하위 폴더', { folder: state.scope }) : t('프로젝트 전체');
  $('#lec-parts-all').hidden = !state.scope;
  const order = $('#lec-parts-order');
  order.textContent = state.order === 'recent' ? t('최근 수정 순') : t('트리 순서');
  order.title = state.order === 'recent' ? t('누르면 트리 순서로') : (state.mode === 'files' ? t('누르면 최근 수정한 파일부터') : t('누르면 최근 수정한 문서부터'));
}

function render() {
  const tab = S.tab;
  const list = $('#lec-parts-list');
  renderMode();
  if (!tab) {
    $('#lec-parts-kinds').innerHTML = '';
    $('#lec-parts-info').textContent = t('열린 프로젝트가 없습니다');
    list.innerHTML = '';
    return;
  }
  renderBar(tab);
  $('#lec-parts-sub').hidden = true;
  listed = [];
  if (state.mode === 'files') {
    renderFiles(tab);
    return;
  }
  if (state.mode === 'meta') {
    renderMeta(tab);
    return;
  }
  const groups = collected(tab);
  // 종류 버튼: 범위 안의 개수
  const counts = Object.fromEntries(KINDS.map((k) => [k, 0]));
  for (const g of groups) for (const it of g.items) counts[it.kind] += 1;
  const reading = scanning?.tab === tab ? t('문서 읽는 중 {done}/{total}', { done: scanning.done, total: scanning.total }) : '';
  if (state.autoKind && !reading) {   // 종류를 정하지 않고 열었는데 그 범위에 없으면, 있는 첫 종류로
    if (!counts[state.kind]) state.kind = KINDS.find((k) => counts[k]) || state.kind;
    state.autoKind = false;
  }
  $('#lec-parts-kinds').innerHTML = KINDS.map((k) => `<button type="button" role="tab" data-kind="${k}" aria-selected="${k === state.kind}"`
    + ` class="${k === state.kind ? 'active' : ''}${counts[k] ? '' : ' zero'}"><svg aria-hidden="true"><use href="#${PARTS[k].icon}"/></svg>${esc(PARTS[k].many)}`
    + `<span class="n">${counts[k]}</span></button>`).join('');
  // 종류 아래 단추 (할 일·링크·출처 — D62): 범위 안의 그 종류를 단추마다 센다
  const subs = SUBS[state.kind];
  const sub = subs?.find(([k]) => k === state.sub[state.kind]) || subs?.[0];
  if (subs) {
    const of = (test) => groups.reduce((n, g) => n + g.items.filter((it) => it.kind === state.kind && test(it)).length, 0);
    $('#lec-parts-sub').innerHTML = subs.map(([k, label, test]) => `<button type="button" data-sub="${k}" aria-pressed="${k === sub[0]}"`
      + ` class="${k === sub[0] ? 'active' : ''}">${esc(label)}<span class="n">${of(test)}</span></button>`).join('');
    $('#lec-parts-sub').hidden = false;
  }
  const subTest = sub ? sub[2] : () => true;
  // 목록
  const match = matcher(state.filter);
  const seen = new Map();   // 그림 → 처음 보인 칸의 '다른 문서' 목록 (같은 그림을 한 번만)
  let shown = 0;
  let docs = 0;
  const html = [];
  for (const { file, items } of groups) {
    const title = file.title || basename(file.path);
    let mine = items.filter((it) => it.kind === state.kind && subTest(it)
      && match(it.name, it.label, it.caption, it.text, it.target, it.section, title, file.path));
    if (!mine.length) continue;
    let body;
    if (state.kind === 'figure') {
      const cells = [];
      mine = mine.filter((it) => {
        const key = it.src ? imageKey(it.src, file.path, tab) : `${file.path}#${it.n}`;
        if (seen.has(key)) {
          seen.get(key).push(file.path);
          return false;
        }
        const others = [];
        seen.set(key, others);
        cells.push([it, others]);
        return true;
      });
      if (!mine.length) continue;
      body = { cells };
    } else if (state.kind === 'chart') {
      body = { charts: mine };
    }
    if (shown >= MAX_SHOWN) break;   // 같은 그림의 '+N곳'은 여기까지 읽은 문서로 센다
    shown += mine.length;
    docs += 1;
    const head = `<div class="pt-doc" tabindex="0" data-doc="${esc(file.path)}" title="${esc(file.path)}">`
      + `<span class="label">${esc(title)}</span>${dirname(file.path) ? `<span class="sub">${esc(dirname(file.path))}</span>` : ''}</div>`;
    html.push({ head, file, mine, body });
  }
  listed = html.flatMap(({ file, mine }) => mine.map((item) => ({ file, item })));
  keepFocus(list, () => {
    list.innerHTML = html.map(({ head, file, mine, body }) => {
      if (body?.charts) return `${head}<div class="pt-grid pt-charts">${body.charts.map((it) => chartThumb(file, it)).join('')}</div>`;
      if (body) return `${head}<div class="pt-grid">${body.cells.map(([it, others]) => thumb(file, it, others)).join('')}</div>`;
      return head + mine.map((it) => itemRow(file, it)).join('');
    }).join('');
  });
  watchThumbs(tab);
  // 알림: 개수, 거른 결과, 읽는 중
  const kind = PARTS[state.kind];
  const name = kind.many.toLowerCase();   // 영어는 문장 속 복수형 (한국어는 그대로)
  const total = counts[state.kind];
  let info;
  if (!total) info = reading || t('이 범위에는 {name}{josa} 없습니다', { name, josa: josa(name, '이', '가') });   // i18n-ok (조사)
  else {
    info = state.filter || (sub && sub[0] !== 'all') ? t('거른 결과 {shown}개 (모두 {total}개)', { shown, total })
      : `${t('문서 {n}개', { n: docs })}, ${t('{kind} {n}개', { kind: (total === 1 ? kind.name : kind.many).toLowerCase(), n: total })}`;
    if (shown >= MAX_SHOWN) info += ` — ${t('처음 {n}개만, 거르기로 좁히세요', { n: MAX_SHOWN })}`;
    if (reading) info += ` · ${reading}`;
  }
  $('#lec-parts-info').textContent = info;
}

// ---- 문서 정보 (D62) ----------------------------------------------------------
// 맨 앞 설정(frontmatter)의 키마다 값으로 문서를 묶는다. 위 단추는 키(그 키가 있는 문서 수), 목록은 값마다 문서들 —
// 그 키가 없는 문서(맨 앞 설정은 있는)는 끝에 '값 없음'. 발표 문서의 Marp 설정과 제목·요약처럼 문서마다 다른 긴 값은 키로 보이지 않는다.

const META_SKIP = new Set(['marp', 'style', 'theme', 'size', 'headingDivider', 'paginate', 'header', 'footer', 'class', 'backgroundColor',
  'backgroundImage', 'backgroundPosition', 'backgroundRepeat', 'backgroundSize', 'color', 'math', 'title', 'name', 'description', 'lang']);
const DATE_LIKE = /^\d{4}(?:[-./]\d{1,2}){0,2}/;

const metaValues = (v) => (Array.isArray(v) ? v : [v]).map((x) => String(x ?? '').trim()).filter((x) => x && x.length <= 120);

function renderMeta(tab) {
  const docs = tab.files.filter((f) => inScope(f.path, state.scope) && tab.partsCache?.get(f.path)?.meta)
    .map((f) => ({ file: f, meta: tab.partsCache.get(f.path).meta }))
    .filter((d) => Object.keys(d.meta).some((k) => !META_SKIP.has(k)));   // 발표 문서의 Marp 설정뿐인 것 등은 빼고
  if (state.order === 'recent') docs.sort((a, b) => b.file.mtime - a.file.mtime);
  const counts = new Map();
  for (const d of docs) {
    for (const [k, v] of Object.entries(d.meta)) if (!META_SKIP.has(k) && metaValues(v).length) counts.set(k, (counts.get(k) || 0) + 1);
  }
  const keys = [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a) || natCompare(a, b));
  if (!counts.has(state.mkey)) state.mkey = keys[0] || null;
  $('#lec-parts-kinds').innerHTML = keys.map((k) => `<button type="button" role="tab" data-mkey="${esc(k)}" aria-selected="${k === state.mkey}"`
    + ` class="${k === state.mkey ? 'active' : ''}">${esc(k)}<span class="n">${counts.get(k)}</span></button>`).join('');
  const reading = scanning?.tab === tab ? t('문서 읽는 중 {done}/{total}', { done: scanning.done, total: scanning.total }) : '';
  const list = $('#lec-parts-list');
  if (!state.mkey) {
    list.innerHTML = '';
    $('#lec-parts-info').textContent = reading || t('이 범위의 문서에는 맨 앞 설정(frontmatter)이 없습니다');
    return;
  }
  const match = matcher(state.filter);
  const byValue = new Map();
  const none = [];
  for (const d of docs) {
    const title = d.file.title || basename(d.file.path);
    const values = metaValues(d.meta[state.mkey]);
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
  const row = (f) => `<div class="pt-doc pt-mdoc" tabindex="0" data-doc="${esc(f.path)}" title="${esc(f.path)}">`
    + `<span class="label">${esc(f.title || basename(f.path))}</span>${dirname(f.path) ? `<span class="sub">${esc(dirname(f.path))}</span>` : ''}</div>`;
  const group = (label, files, cls = '') => `<div class="pt-val${cls}"><span class="label">${esc(label)}</span><span class="n">${files.length}</span></div>${files.map(row).join('')}`;
  keepFocus(list, () => {
    list.innerHTML = values.map((v) => group(v, byValue.get(v))).join('') + (none.length ? group(t('값 없음'), none, ' none') : '');
  });
  $('#lec-parts-info').textContent = [`${t('문서 {n}개', { n: docs.length })}, ${t('값 {n}가지', { n: values.length })}`, reading].filter(Boolean).join(' · ');
}

// ---- 파일 종류 (D50) ----------------------------------------------------------
// 범위 안의 파일을 묶음(문서·코드·자료)마다 형식별로 센다 (icons.js 의 fileType — 엑셀·파워포인트·워드·한글은 한 이름, 나머지는 확장자).
// 문서는 탭의 트리, 코드·자료는 '코드'·'자료' 목록과 같은 것 (others.js — 제외 폴더 안은 세지 않는다). 그림 파일은 작은 그림 격자.
// 행은 others.js 의 bindFileRows — 문서·코드는 한 번 누르면 열고, 자료는 두 번 누르거나 Enter.

const GROUPS = [['docs', t('문서')], ['code', t('코드')], ['others', t('자료')]];
let fileRows = new Map();   // 화면의 파일 행: 경로 → 노드

/** 범위 안의 파일: [{f, group, type, key}] */
function fileEntries(tab) {
  const all = [...tab.files.map((f) => [f, 'docs']), ...otherFiles(tab).map((f) => [f, isCode(f.name) ? 'code' : 'others'])];
  return all.filter(([f]) => inScope(f.path, state.scope)).map(([f, group]) => {
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

function renderFiles(tab) {
  const list = $('#lec-parts-list');
  const o = tab.others;
  const entries = fileEntries(tab);
  const chips = new Map();   // 'docs:md' → {group, type, n, icon}
  for (const e of entries) {
    if (!chips.has(e.key)) chips.set(e.key, { group: e.group, type: e.type, n: 0, icon: fileIcon(e.f.name, e.f.kind) });
    chips.get(e.key).n += 1;
  }
  const reading = !o.data && !o.error ? t('파일 목록을 읽는 중…') : '';
  if (!chips.has(state.ftype) && !reading) {   // 고른 형식이 이 범위에 없으면: 자료 → 코드 → 문서 순으로, 그 안에서 가장 많은 것
    const order = ['others', 'code', 'docs'];
    const [best] = [...chips.entries()].sort(([, a], [, b]) => order.indexOf(a.group) - order.indexOf(b.group) || b.n - a.n);
    if (best) state.ftype = best[0];
  }
  $('#lec-parts-kinds').innerHTML = GROUPS.map(([group, name]) => {
    const mine = [...chips.entries()].filter(([, c]) => c.group === group)
      .sort(([, a], [, b]) => b.n - a.n || natCompare(a.type.label, b.type.label));
    if (!mine.length) return '';
    return `<div class="ft-group"><span class="ft-label">${esc(name)}</span>${mine.map(([key, c]) => `<button type="button" role="tab" data-ftype="${esc(key)}"`
      + ` aria-selected="${key === state.ftype}" class="${key === state.ftype ? 'active' : ''}">${c.icon}${esc(c.type.label)}<span class="n">${c.n}</span></button>`).join('')}</div>`;
  }).join('');
  // 목록: 고른 형식의 파일 (거르기는 이름·경로, 문서는 제목도)
  const match = matcher(state.filter);
  let files = entries.filter((e) => e.key === state.ftype && match(e.f.name, e.f.path, e.f.title || '')).map((e) => e.f);
  files.sort(state.order === 'recent' ? (a, b) => b.mtime - a.mtime : (a, b) => treeOrder(a.path, b.path));
  const matched = files.length;
  files = files.slice(0, MAX_SHOWN);
  fileRows = new Map(files.map((f) => [f.path, f]));
  const current = S.view?.type === 'doc' || S.view?.type === 'code' ? S.view.path : null;
  const [group, typeKey] = (state.ftype || '').split(':');
  const html = group === 'others' && PICTURE_EXT.has(typeKey)
    ? `<div class="pt-grid">${files.map((f) => `<div class="ft-thumb" tabindex="0" data-file="${esc(f.path)}" title="${esc(fileTip(f))}">`
      + `<div class="pt-pic" data-file-src="${esc(f.path)}"></div><span class="pt-cap">${esc(f.name)}</span></div>`).join('')}</div>`
    : files.map((f) => `<div class="row ft-row${f.path === current ? ' active' : ''}" tabindex="0" data-file="${esc(f.path)}"`
      + ` title="${esc(f.kind ? tipOf(f) : fileTip(f))}">${fileIcon(f.name, f.kind)}<span class="label">${esc(f.kind ? labelOf(f) : f.name)}</span>`
      + `${dirname(f.path) ? `<span class="sub">${esc(dirname(f.path))}</span>` : ''}</div>`).join('');
  keepFocus(list, () => { list.innerHTML = html; });
  watchThumbs(tab);
  const total = chips.get(state.ftype)?.n || 0;
  let info;
  if (reading) info = reading;
  else if (o.error && !o.data) info = o.error;
  else if (!chips.size) info = t('이 범위에는 파일이 없습니다');
  else {
    info = state.filter ? t('거른 결과 {shown}개 (모두 {total}개)', { shown: matched, total }) : t('파일 {n}개', { n: total });
    if (matched > MAX_SHOWN) info += ` — ${t('처음 {n}개만, 거르기로 좁히세요', { n: MAX_SHOWN })}`;
  }
  $('#lec-parts-info').textContent = info;
}

/** 받침이 있으면 a, 없으면 b (표가 / 그림이) */
function josa(word, a, b) {
  const code = word.charCodeAt(word.length - 1) - 0xac00;
  return code >= 0 && code < 11172 && code % 28 ? a : b;
}

/** 그림 칸이 목록에서 보일 때 그림을 불러온다 */
function watchThumbs(tab) {
  thumbs?.disconnect();
  thumbs = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      thumbs.unobserve(e.target);
      const pic = e.target;
      if (pic.dataset.fileSrc) {   // 파일 종류의 그림 파일 (D50) — 그 파일 그대로
        if (tab !== S.tab) continue;
        const img = document.createElement('img');
        img.alt = '';
        img.addEventListener('error', () => { pic.innerHTML = `<span class="image-off">${esc(t('그림을 그리지 못했습니다'))}</span>`; }, { once: true });
        img.src = docUrl(tab, pic.dataset.fileSrc);
        pic.append(img);
        continue;
      }
      if (pic.dataset.chart !== undefined) {   // 차트 (D62) — 그려서
        drawChartThumb(pic, tab);
        continue;
      }
      const docPath = pic.closest('.pt-thumb')?.dataset.doc;
      if (!pic.dataset.src || !docPath || tab !== S.tab) continue;
      const img = document.createElement('img');
      img.alt = pic.dataset.alt || '';
      img.setAttribute('data-src', pic.dataset.src);
      img.loading = 'lazy';
      pic.append(img);
      loadImage(img, docPath, tab);   // 본문과 같은 규칙. 불러오지 못하면 글로 바뀐다
    }
  }, { root: $('#lec-parts-list'), rootMargin: '200px 0px' });
  for (const pic of $$('#lec-parts-list .pt-pic:empty')) thumbs.observe(pic);
}

let chartQueue = Promise.resolve();   // 차트는 하나씩 그린다 (라이브러리가 무겁다)

/**
 * 차트의 작은 그림 (D62): 화면 밖 무대(560px)에서 본문과 같은 규칙으로 그려(charts.js — 문서 기준 상대경로의 CSV 도) SVG 를 칸에 넣는다.
 * 그린 것은 항목에 남겨 두고 스타일이 같으면 다시 쓴다 (스타일을 바꾸면 그 색으로 다시 그린다)
 */
function drawChartThumb(pic, tab) {
  const found = itemOf(pic.closest('.pt-thumb'));
  if (!found) return;
  const { path, item } = found;
  const theme = document.documentElement.dataset.theme || '';
  if (item.svg && item.svgTheme === theme) {
    pic.innerHTML = item.svg;
    return;
  }
  chartQueue = chartQueue.then(async () => {
    if (!pic.isConnected || tab !== S.tab) return;
    const stage = document.createElement('div');
    stage.className = 'lec-stage';
    stage.style.width = '560px';
    stage.innerHTML = `<pre class="lec-chart" data-chart="${esc(item.chart)}">${esc(item.code || '')}</pre>`;
    document.body.append(stage);
    try {
      await renderCharts(stage, { tab, path, sanitize: sanitizeHtml, resolveRef });
    } catch { /* 아래에서 알린다 */ } finally {
      stage.remove();
    }
    const svg = stage.querySelector('pre.lec-chart > svg');
    if (svg) Object.assign(item, { svg: svg.outerHTML, svgTheme: theme });
    if (pic.isConnected) pic.innerHTML = svg ? item.svg : `<span class="image-off">${esc(t('차트를 그리지 못했습니다'))}</span>`;
  });
}

/** 범위의 문서를 (바뀐 것만) 읽고 그린다 */
async function refresh() {
  const tab = S.tab;
  if (!tab || !panelShown()) {
    render();
    return;
  }
  if (state.mode === 'files') {
    const others = loadOthers(tab);   // 받아 둔 목록이 그대로면 바로 끝난다
    render();
    await others;
    if (tab === S.tab && panelShown()) render();
    return;
  }
  const job = scan(tab, state.scope);   // 읽을 것이 있으면 여기서 바로 '읽는 중'이 된다 (첫 await 전까지는 이어서 돈다)
  render();
  await job;
  if (tab === S.tab && panelShown()) render();
}

// ---- 열기 ---------------------------------------------------------------------

/** 항목으로 간다: 그 문서를 열고, 목차와 같은 규칙으로 센 같은 종류·번호의 것으로 */
/** 목록의 행(.pt-item·.pt-thumb)이 가리키는 문서와 구성 요소 */
function itemOf(el) {
  const path = el.dataset.doc;
  const item = S.tab?.partsCache?.get(path)?.items.find((it) => it.kind === el.dataset.kind && it.n === Number(el.dataset.n));
  return item ? { path, item } : null;
}

async function copy(text, what) {
  toast(await copyText(text) ? t('복사했습니다: {what}', { what }) : t('복사하지 못했습니다'));
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

/** 지금 목록에 보이는 것 모두 담기: 문서마다 원문을 한 번 읽어 차례대로. html 문서의 것(원문 줄이 없음)은 빼고 알린다 */
async function takeAll(entries) {
  const tab = S.tab;
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
  if (tab !== S.tab) return;
  addSnippets(snips, skipped ? t('{n}개는 원문이 없어(html 문서) 담지 않았습니다', { n: skipped }) : '');
}

/** 구성 요소의 우클릭 메뉴 (D61): 문서에서 보기, Claude용 위치·원문 복사(옆에 터미널 버튼 — D51), 담기·문서에 넣기(D63), 문서 경로 */
async function partMenu(el, x, y) {
  const found = itemOf(el);
  if (!found) return;
  const { path, item } = found;
  const tab = S.tab;
  const range = item.lines;
  const note = item.caption || (item.kind === 'task' || item.kind === 'source' ? (item.text.length > 40 ? `${item.text.slice(0, 39)}…` : item.text) : '');
  const ref = `@${path}${range ? ` ${rangeText(range)}` : ''}${note ? ` ('${note}')` : ''}`;
  const items = [{ header: `${item.name} · ${path}` },
    { label: t('문서에서 보기'), hint: t('누르기·Enter'), action: () => openItem(el) },
    { label: t('Claude용 위치 복사'), hint: ref, action: () => copy(ref, ref), term: `${ref} ` }];
  if (item.kind === 'link') items.push({ label: t('링크 주소 복사'), hint: item.target, action: () => copy(item.target, item.target), term: item.target });
  let lines = null;   // 그 문서의 원문 줄들 (md)
  if (!isHtml(path)) {
    try {
      lines = (await getText(docUrl(tab, path))).replace(/^﻿/, '').split(/\r\n?|\n/);
    } catch { /* 읽는 사이 지워진 문서 — 원문 항목 없이 */ }
    if (tab !== S.tab) return;
  }
  const source = range && lines ? lines.slice(range[0] - 1, range[1]).join('\n') : '';
  if (source) items.push({ label: t('원문 복사'), hint: `Markdown ${rangeText(range)}`, action: () => copy(source, `${path} ${rangeText(range)}`), term: source });
  // 담기·문서에 넣기 (D63) — 그 하나, 또는 지금 목록에 보이는 것 모두
  const snip = itemSnippet(path, lines, item);
  if (snip) {
    items.push('-', { label: t('담기'), hint: t("사이드바 '담기' 탭에 — 모아서 한 번에 넣기"), action: () => addSnippets([snip]) },
      { label: t('문서에 넣기…'), hint: t('다른 문서나 새 문서에 바로'), action: () => insertSnippets([snip]) });
  }
  if (listed.length > 1) {
    items.push({ label: t('보이는 것 모두 담기 ({n}개)', { n: listed.length }), hint: t('지금 목록의 것을 문서 차례대로 — 거르기·단추로 좁힌 그대로'), action: () => takeAll(listed) });
  }
  items.push('-', ...pathMenuItems(path, true));
  el.classList.add('lec-picked');
  showMenu(x, y, items, () => el.classList.remove('lec-picked'));
}

async function openItem(el) {
  const path = el.dataset.doc;
  const here = S.view?.type === 'doc' && S.view.path === path;
  if (!here && !(await navigate({ type: 'doc', path }))) return;
  if (!el.dataset.kind) return;   // 문서 머리줄
  const row = readParts(docRoot(), { more: true }).rows.find((r) => r.kind === el.dataset.kind && r.n === Number(el.dataset.n));
  if (row) goToPart(row.el);
}

/** 모아 보기를 연다 (폴더 개요의 버튼·트리 우클릭·'코드'·'자료' 목록의 폴더 우클릭). path: 범위 폴더 ('' = 프로젝트 전체),
 * kind: 문서 속 요소의 종류 (없으면 그대로), mode: 'files' 면 파일 종류 (아니면 문서 속 요소) */
export function openParts({ path = '', kind = null, mode = 'parts' } = {}) {
  state.mode = mode === 'files' ? 'files' : 'parts';
  state.scope = path;
  if (kind && PARTS[kind]) state.kind = kind;
  state.autoKind = !kind;
  state.filter = '';
  $('#lec-parts-filter').value = '';
  $('#lec-parts-list').scrollTop = 0;
  emit('show-sidebar');
  if (panelShown()) refresh();
  else switchPanel('parts');   // 'panel' 이벤트가 refresh 한다
}

/** 프로젝트 탭을 바꾸면: 앞 탭의 상태를 남기고 새 탭의 것을 되살린다 */
function onTab({ tab, prev }) {
  if (prev && S.tabs.includes(prev)) prev.side.parts = { ...state, scroll: $('#lec-parts-list').scrollTop };
  state = { ...DEFAULT, ...(tab?.side.parts || {}) };
  $('#lec-parts-filter').value = state.filter;
  if (panelShown()) {
    refresh().then(() => { $('#lec-parts-list').scrollTop = state.scroll; });
  }
}

export function initParts() {
  $('#lec-parts-mode').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-mode]');
    if (!b || b.dataset.mode === state.mode) return;
    state.mode = b.dataset.mode;
    $('#lec-parts-list').scrollTop = 0;
    refresh();
  });
  $('#lec-parts-kinds').addEventListener('click', (e) => {
    const f = e.target.closest('button[data-ftype]');
    if (f && f.dataset.ftype !== state.ftype) {   // 파일 형식
      state.ftype = f.dataset.ftype;
      $('#lec-parts-list').scrollTop = 0;
      render();
      return;
    }
    const m = e.target.closest('button[data-mkey]');   // 문서 정보의 키 (D62)
    if (m) {
      if (m.dataset.mkey !== state.mkey) {
        state.mkey = m.dataset.mkey;
        $('#lec-parts-list').scrollTop = 0;
        render();
      }
      return;
    }
    const b = e.target.closest('button[data-kind]');
    if (!b || b.dataset.kind === state.kind) return;
    state.kind = b.dataset.kind;
    state.autoKind = false;
    $('#lec-parts-list').scrollTop = 0;
    render();
  });
  $('#lec-parts-all').addEventListener('click', () => openParts({ path: '' }));
  $('#lec-parts-order').addEventListener('click', () => {
    state.order = state.order === 'recent' ? 'tree' : 'recent';
    render();
  });
  const filter = $('#lec-parts-filter');
  const later = debounce(render, 150);
  filter.addEventListener('input', () => {
    state.filter = filter.value.trim();
    later();
  });
  filter.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      state.filter = filter.value.trim();
      render();   // 거르기가 아직 반영되기 전이어도 지금 글자로 거른 첫 항목을 연다
      if (state.mode === 'files') $('#lec-parts-list [data-file]')?.focus();   // 파일은 초점만 (Enter 로 연다 — 자료는 다른 앱이 뜬다)
      else $('#lec-parts-list .pt-item, #lec-parts-list .pt-thumb')?.click();
    }
    else if (e.key === 'Escape' && filter.value) {
      e.stopPropagation();
      filter.value = '';
      filter.dispatchEvent(new Event('input'));
    }
  });
  const list = $('#lec-parts-list');
  bindFileRows(list, (path) => fileRows.get(path));   // 파일 종류의 행 (D50)
  list.addEventListener('click', (e) => {
    const el = e.target.closest('.pt-item, .pt-thumb, .pt-doc');
    if (el) openItem(el);
  });
  list.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.matches('.pt-item, .pt-thumb, .pt-doc')) openItem(e.target);
  });
  list.addEventListener('contextmenu', (e) => {   // 구성 요소의 우클릭 — 파일 행은 각자 (bindFileRows)
    const el = e.target.closest('.pt-item, .pt-thumb, .pt-doc');
    if (!el) return;
    e.preventDefault();
    if (el.matches('.pt-doc')) showMenu(e.clientX, e.clientY, [{ header: el.dataset.doc }, ...pathMenuItems(el.dataset.doc, true)]);   // 문서 머리줄·문서 정보의 문서
    else partMenu(el, e.clientX, e.clientY);
  });
  $('#lec-parts-sub').addEventListener('click', (e) => {   // 종류 아래 단추 (D62)
    const b = e.target.closest('button[data-sub]');
    if (!b) return;
    state.sub = { ...state.sub, [state.kind]: b.dataset.sub };
    $('#lec-parts-list').scrollTop = 0;
    render();
  });
  on('panel', (name) => { if (name === 'parts') refresh(); });
  on('parts', openParts);
  on('tab', onTab);
  on('tree', () => { if (panelShown()) refresh(); });   // 문서가 바뀌면 (트리를 새로 받으면) 바뀐 문서만 다시 읽는다
  on('others', (tab) => { if (tab === S.tab && panelShown() && state.mode === 'files') refresh(); });   // 파일이 생기거나 지워짐
  on('titles', () => { if (panelShown() && state.mode === 'files') render(); });
}
