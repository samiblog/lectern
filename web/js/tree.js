// 왼쪽 사이드바: 사이드바 탭 바꾸기, 파일 트리, 필터, 우클릭 메뉴. 선택된 프로젝트 탭의 것을 보인다.
// 사이드바 탭(파일·최근 변경·검색·모아 보기)·필터·스크롤 위치는 프로젝트 탭마다 기억했다가 그 탭을 고르면 되살린다 (tab.side).
// 최근 변경 목록은 recent.js (D50).

import { S, emit, on } from './store.js';
import { saveConfig, openExternal, revealInExplorer, getJSON } from './api.js';
import { showMenu, menuGroups } from './ui.js';
import { fileIcon, folderIcon } from './icons.js';
import { html, setHtml } from './html.js';
import { $, $$, dirname, copyText, toast, keepFocus, openHow, repeatClick, middleClickOpens, clickFromKey, isMd } from './util.js';
import { t } from './i18n.js';
import { aiCli } from './aitool.js';
import { sideOrder } from './sideorder.js';

const MAX_FILTER_RESULTS = 300;

// '문서' 묶음의 하위 묶음 (D143): 한 번에 하나만 펼치고 펼친 것 아래에 트리. 종류로 거르는 것(keep)과 문서 속을 읽어 거르는 것(content —
// 형광펜·할 일, GET /api/marks)이 있다. 문서가 없는 종류와 '전체'와 같은 종류는 머리줄을 감춘다. 설정 docs_kind, 프로젝트 탭마다 tab.side.docKind
const KINDS = () => [
  { id: 'all', name: t('전체') },
  { id: 'md', name: t('문서'), keep: (f) => f.kind === 'markdown' && !f.deck },
  { id: 'deck', name: t('슬라이드'), keep: (f) => !!f.deck },
  { id: 'html', name: 'HTML', keep: (f) => f.kind === 'html' },
  { id: 'work', name: t('업무'), keep: (f) => f.name.toLowerCase() === 'work.md' },
  { id: 'marks', name: t('형광펜'), content: true },
  { id: 'tasks', name: t('할 일'), content: true },
];
export const MARK_NAMES = () => ({ '': t('노랑'), green: t('초록'), pink: t('분홍'), blue: t('하늘') });
let panel = 'files';   // 사이드바 탭: files | recent | search | parts

// 목록에는 파일 이름을 보이고 마우스를 올리면 문서 제목 (사용자 요청, v0.7.1). '제목' 버튼(설정 show_titles)을 켜면 반대로
// 폴더 보기(others.js)의 문서 행도 같은 글을 쓴다
const showTitles = () => S.config.show_titles === true;
export const labelOf = (f) => (showTitles() ? (f.title || f.name) : f.name);
/** 마우스를 올리면 보일 글: 목록에 보이지 않는 쪽을 앞에 (파일 이름을 보이면 문서 제목), 그다음 경로 */
export const tipOf = (f) => {
  if (!f.title) return f.path;
  return showTitles() ? `${f.path}\n${f.title}` : `${f.title}\n${f.path}`;
};

function activeDoc() {
  return S.view?.type === 'doc' ? S.view.path : null;
}

function activeDir() {
  return S.view?.type === 'overview' ? S.view.path : null;
}

export function hasChangedInside(dirPath) {
  const prefix = `${dirPath}/`;
  for (const p of S.changed) if (p.startsWith(prefix)) return true;
  return false;
}

/** html 문서 표시 (md 와 구분) — 폴더 개요에서. 사이드바 목록은 아이콘으로 구분한다 (icons.js) */
export const kindBadge = (f) => (f.kind === 'html' ? html`<span class="kind" title="${t('HTML 문서')}">HTML</span>` : '');

function fileRow(f, depth, extra = null) {
  const cls = ['row', 'file'];
  if (f.path === activeDoc()) cls.push('active');
  return [html`<div class="${cls.join(' ')}" data-doc="${f.path}" style="--d:${depth}" title="${tipOf(f)}" tabindex="-1">`, html`<span class="caret-space"></span>${fileIcon(f.name, f.kind, f.deck)}<span class="label">${labelOf(f)}</span>${extra}`, html`${S.changed.has(f.path) ? html`<span class="dot" title="${t('열어 보기 전에 바뀜')}"></span>` : ''}</div>`];
}

/** opts: {allOpen — 폴더를 모두 펼쳐 보임(S.open 은 그대로), after(f, depth) — 문서 행 아래에 붙일 줄} */
function nodesHtml(nodes, depth, opts = null) {
  const markup = [];
  for (const n of sideOrder(nodes)) {
    if (n.type === 'file') {
      markup.push(fileRow(n, depth));
      if (opts?.after) markup.push(opts.after(n, depth + 1));
      continue;
    }
    const open = !!opts?.allOpen || S.open.has(n.path);
    const cls = ['row', 'dir'];
    if (n.path === activeDir()) cls.push('active');
    markup.push([html`<div class="${cls.join(' ')}" data-dir="${n.path}" style="--d:${depth}" title="${n.path}" tabindex="-1">`, html`<span class="caret${open ? ' open' : ''}" data-toggle aria-hidden="true"></span>${folderIcon()}<span class="label">${n.name}</span>`, html`${!open && hasChangedInside(n.path) ? html`<span class="dot" title="${t('안쪽 문서가 바뀜')}"></span>` : ''}</div>`]);
    if (open) markup.push(nodesHtml(n.children, depth + 1, opts));
  }
  return markup;
}

/** keep 에 맞는 문서만 남긴 트리 (빈 폴더는 뺀다) */
function pickDocs(nodes, keep) {
  const out = [];
  for (const n of nodes) {
    if (n.type === 'file') {
      if (keep(n)) out.push(n);
    } else {
      const children = pickDocs(n.children, keep);
      if (children.length) out.push({ ...n, children });
    }
  }
  return out;
}

/** 탭의 형광펜·할 일 (GET /api/marks) — Map(경로 → {marks, tasks}). 아직 받지 않았으면 null */
const marksOf = (tab) => tab?.marks?.data ?? null;

/** 형광펜·할 일을 받는다 — 받은 것이 그대로면(stale 이 아니면) 다시 받지 않는다. 서버는 바뀐 문서만 다시 읽는다 */
export function loadMarks(tab = S.tab) {
  if (!tab) return;
  const m = (tab.marks ||= { data: null, loading: null, stale: true });
  if (m.loading || (m.data && !m.stale)) return;
  m.stale = false;
  m.loading = getJSON(`/api/marks?p=${encodeURIComponent(tab.id)}`)
    .then((r) => { m.data = new Map(r.docs.map((d) => [d.path, d])); m.error = null; })
    .catch((e) => { m.error = e.message; m.data ||= new Map(); })
    .finally(() => {
      m.loading = null;
      if (tab === S.tab) render();
    });
}

/** 하위 묶음마다의 개수 — 형광펜·할 일은 받은 뒤에만 (칠한 곳·열린 할 일의 수) */
function kindCounts(tab) {
  const got = marksOf(tab);
  const n = {};
  for (const k of KINDS()) {
    if (k.content) n[k.id] = got ? [...got.values()].reduce((sum, d) => sum + d[k.id].length, 0) : null;
    else n[k.id] = k.keep ? tab.files.filter(k.keep).length : tab.files.length;
  }
  return n;
}

/** 보일 하위 묶음 — 문서가 없거나 '전체'와 같은 종류는 뺀다. 형광펜·할 일은 Markdown 문서가 있으면 늘 */
function shownKinds(tab) {
  if (!tab?.treeLoaded) return [];
  const n = kindCounts(tab);
  const md = tab.files.some((f) => f.kind === 'markdown');
  const out = KINDS().filter((k) => k.id === 'all' || (k.content ? md : n[k.id] > 0 && n[k.id] < n.all)).map((k) => ({ ...k, n: n[k.id] }));
  return out.length > 1 ? out : [];
}

/** 펼친 하위 묶음 — 보이지 않는 것을 골라 두었으면 '전체' */
function currentKind(kinds = shownKinds(S.tab)) {
  const id = S.tab?.side?.docKind ?? S.config.docs_kind;
  return kinds.find((k) => k.id === id) ?? kinds[0] ?? KINDS()[0];
}

/** 하위 묶음의 머리줄 — 펼친 것까지는 트리 위에, 나머지는 트리 아래에 */
function renderKinds(kinds) {
  const cur = currentKind(kinds);
  const i = kinds.findIndex((k) => k.id === cur.id);
  const head = (k) => {
    const open = k.id === cur.id;
    const n = k.content && k.n == null ? '' : String(k.n);
    return html`<button type="button" class="kind-head${open ? ' open' : ''}" data-kind="${k.id}" aria-expanded="${open}"><span class="caret${open ? ' open' : ''}" aria-hidden="true"></span><span>${k.name}</span><span class="n">${n}</span></button>`;
  };
  setHtml($('#lec-doc-kinds-top'), kinds.slice(0, i + 1).map(head));
  setHtml($('#lec-doc-kinds-bottom'), kinds.slice(i + 1).map(head));
  $('#lec-docs').classList.toggle('kinds', kinds.length > 0);
}

/** 형광펜·할 일 줄 — 문서 행 아래 한 단 들여 */
function itemRows(kind, f, items, depth) {
  return items.map((it) => {
    const swatch = kind === 'marks' ? ` mark-${it.color || 'yellow'}` : ' task';
    return html`<div class="row item ${kind}" data-item-doc="${f.path}" data-line="${it.line}" data-color="${it.color ?? ''}" data-text="${it.text}" style="--d:${depth}" title="${t('{a}행', { a: it.line })} · ${it.text}" tabindex="-1"><span class="caret-space"></span><span class="swatch${swatch}" aria-hidden="true"></span><span class="label">${it.text || '…'}</span></div>`;
  });
}

/** 형광펜·할 일 하위 묶음의 목록: 그것이 있는 문서와 그 아래 줄들 (폴더는 모두 펼친다). 거르는 중이면 이름·제목·줄의 글로 */
function contentHtml(kind, got, terms) {
  const itemsOf = (f) => got.get(f.path)?.[kind] ?? [];
  const empty = kind === 'marks' ? t('칠한 곳이 없습니다 — 글을 고르고 M 을 누르면 형광펜') : t('열린 할 일이 없습니다');
  if (terms) {
    const rows = [];
    for (const f of S.files) {
      const items = itemsOf(f);
      if (!items.length) continue;
      const named = terms.every((w) => `${(f.title || '').toLowerCase()} ${f.path.toLowerCase()}`.includes(w));
      const hits = named ? items : items.filter((it) => terms.every((w) => it.text.toLowerCase().includes(w)));
      if (hits.length) rows.push(fileRow(f, 0, dirname(f.path) ? html`<span class="sub">${dirname(f.path)}</span>` : ''), itemRows(kind, f, hits, 1));
    }
    return rows.length ? rows : html`<p class="side-empty">${t('일치하는 문서가 없습니다')}</p>`;
  }
  const nodes = pickDocs(S.tree, (f) => itemsOf(f).length > 0);
  return nodes.length ? nodesHtml(nodes, 0, { allOpen: true, after: (f, depth) => itemRows(kind, f, itemsOf(f), depth) }) : html`<p class="side-empty">${empty}</p>`;
}

function renderTree() {
  const box = $('#lec-tree');
  const scroll = box.scrollTop;
  const kinds = shownKinds(S.tab);
  renderKinds(kinds);
  if (!S.tab?.treeLoaded) {   // 탭이 없거나 아직 트리를 읽는 중
    box.innerHTML = '';
    return;
  }
  const kind = currentKind(kinds);
  const query = $('#lec-filter').value.trim().toLowerCase();
  if (kind.content) {   // 형광펜·할 일 (D143)
    const got = marksOf(S.tab);
    if (!got || S.tab.marks?.stale) loadMarks(S.tab);
    setHtml(box, got ? contentHtml(kind.id, got, query ? query.split(/\s+/) : null) : html`<p class="side-empty">${t('문서를 읽는 중…')}</p>`);
  } else if (query) {
    const terms = query.split(/\s+/);
    const hits = S.files.filter((f) => {
      if (kind.keep && !kind.keep(f)) return false;
      const hay = `${(f.title || '').toLowerCase()} ${f.path.toLowerCase()}`;
      return terms.every((w) => hay.includes(w));
    });
    setHtml(box, hits.length
      ? hits.slice(0, MAX_FILTER_RESULTS).map((f) => fileRow(f, 0, dirname(f.path) ? html`<span class="sub">${dirname(f.path)}</span>` : ''))
      : html`<p class="side-empty">${t('일치하는 문서가 없습니다')}</p>`);
  } else {
    // 프로젝트 이름은 탭에 있다 — 프로젝트 개요는 고른 프로젝트 탭을 또 누르거나 탭의 우클릭으로 (tabs.js)
    const nodes = kind.keep ? pickDocs(S.tree, kind.keep) : S.tree;
    setHtml(box, nodes.length ? nodesHtml(nodes, 0) : html`<p class="side-empty">${t('문서(Markdown·HTML)가 없습니다')}</p>`);
  }
  box.scrollTop = scroll;
  rove();   // Tab 으로 들어올 행 (거르기·화살표 누르기처럼 render 를 거치지 않고 다시 그려도)
}

/** Tab 으로 트리에 들어올 행 하나 (D169 — 나머지는 ↑·↓ 로): row, 없으면 지금 보는 문서·폴더, 그것도 없으면 첫 행 */
function rove(row = null) {
  const box = $('#lec-tree');
  const pick = row || box.querySelector('.row.active') || box.querySelector('.row');
  for (const r of $$('.row[tabindex="0"]', box)) if (r !== pick) r.tabIndex = -1;
  if (pick) pick.tabIndex = 0;
}

function renderCount() {
  const el = $('#lec-changed-count');
  el.textContent = S.changed.size;
  el.hidden = S.changed.size === 0;
}

function render() {
  keepFocus($('#lec-tree'), renderTree);
  const at = document.activeElement;
  rove(at?.matches?.('#lec-tree .row') ? at : null);   // 다시 그린 뒤에도 초점이 있던 행이 Tab 의 자리
  renderCount();
  $('#lec-btn-titles').classList.toggle('on', showTitles());
  $('#lec-btn-sort').classList.toggle('on', sortWay() !== 'name');
}

const sortWay = () => (['time', 'type'].includes(S.config.side_sort) ? S.config.side_sort : 'name');

/** 목록의 차례 메뉴 (D97) — 문서·코드·자료를 함께 */
function openSort(e) {
  const r = e.currentTarget.getBoundingClientRect();
  const item = (way, label) => ({
    label,
    current: sortWay() === way,
    action: async () => {
      await saveConfig({ side_sort: way });
      render();
      emit('side-sort');
    },
  });
  showMenu(r.left, r.bottom + 2, [{ header: t('폴더 먼저, 그 안의 차례') }, item('name', t('이름순')), item('time', t('시간순')), item('type', t('형식순'))]);
}

/** 업무 카드 만들기 (D124 — work.js). 그 폴더(dir — '' 이면 맨 위)의 WORK.md 가 있으면 연다. 하위 폴더에도 (D149 — 업무 나무) */
export const workCardItem = (dir = '') => ({ label: S.fileMap.has(dir ? `${dir}/WORK.md` : 'WORK.md') ? t('업무 카드 열기') : dir ? t('이 폴더에 업무 카드 만들기…') : t('업무 카드 만들기…'),
  tip: dir ? t('이 폴더에 WORK.md — 위 폴더의 업무가 모아 봅니다') : '', action: () => emit('work-card', { folder: dir }) });

/** 폴더 모두 펼치기·접기 (D125) — 문서 트리는 여기서, 코드·자료 목록은 others.js 가 'side-open' 을 듣는다. mode: all | none | first */
function setAllOpen(mode) {
  if (!S.tab?.treeLoaded) return;
  S.open.clear();
  const walk = (nodes, depth) => {
    for (const n of nodes) {
      if (n.type !== 'dir') continue;
      S.open.add(n.path);
      if (mode === 'all' && n.children) walk(n.children, depth + 1);
    }
  };
  if (mode !== 'none') walk(S.tree, 0);
  render();
  emit('side-open', mode);
}

function openExpand(e) {
  const r = e.currentTarget.getBoundingClientRect();
  showMenu(r.left, r.bottom + 2, [{ header: t('문서·코드·자료 목록의 폴더') },
    { label: t('폴더 모두 펼치기'), tip: t('제외 폴더(흐린 폴더)는 펼치지 않습니다'), action: () => setAllOpen('all') },
    { label: t('폴더 모두 접기'), action: () => setAllOpen('none') },
    { label: t('첫 단계 폴더만 펼치기'), action: () => setAllOpen('first') }]);
}

/** 지금 보는 항목의 상위 폴더를 펼치고 트리에서 보이게 한다. */
function revealCurrent() {
  if (!S.view) return;
  if (S.view.type === 'code') {   // 코드는 '코드' 목록이 보인다 (others.js). 문서 트리의 강조만 지운다
    render();
    return;
  }
  const parts = S.view.path.split('/');
  const upto = S.view.type === 'doc' ? parts.length - 1 : parts.length;
  for (let i = 1; i <= upto; i++) S.open.add(parts.slice(0, i).join('/'));
  render();
  const sel = S.view.type === 'doc' ? `[data-doc="${CSS.escape(S.view.path)}"]` : `[data-dir="${CSS.escape(S.view.path)}"]`;
  if (panel === 'files') $(`#lec-tree ${sel}`)?.scrollIntoView({ block: 'nearest' });
}

/** 사이드바 탭을 바꾼다: files(파일) | recent(최근 변경) | search(검색) | parts(모아 보기) | basket(담기 — D63). focus: 검색이면 입력칸에 초점 */
export function switchPanel(next, { focus = true } = {}) {
  panel = next;
  for (const b of $$('.side-tabs button')) b.classList.toggle('active', b.dataset.tab === next);
  $('#lec-files').hidden = next !== 'files';   // 문서 트리 + 문서 외 파일 (others.js)
  $('#lec-recent-panel').hidden = next !== 'recent';   // 최근 변경 (recent.js)
  $('#lec-filter').closest('.side-filter').hidden = next !== 'files';
  $('#lec-search').hidden = next !== 'search';   // 전체 검색 (search.js)
  $('#lec-parts').hidden = next !== 'parts';     // 모아 보기 (parts.js)
  $('#lec-basket').hidden = next !== 'basket';   // 담기 (basket.js)
  if (next === 'search' && focus) $('#lec-search-input').focus();
  emit('panel', next);
}

/** 프로젝트 탭을 바꾸면: 앞 탭의 사이드바 상태를 그 탭에 남기고, 새 탭의 것을 되살린다 */
function onTab({ tab, prev }) {
  if (prev && S.tabs.includes(prev)) {
    Object.assign(prev.side, { panel, filter: $('#lec-filter').value, treeScroll: $('#lec-tree').scrollTop });
  }
  const side = tab?.side || { panel: 'files', filter: '', treeScroll: 0 };
  $('#lec-filter').value = side.filter;
  switchPanel(side.panel, { focus: false });
  render();
  $('#lec-tree').scrollTop = side.treeScroll;
}

function onRowClick(e) {
  const row = e.target.closest('.row');
  if (!row) return;
  if (row.dataset.itemDoc != null) {   // 형광펜·할 일 줄: 그 문서의 그 줄로 (D143)
    if (!repeatClick(e)) emit('open', { type: 'doc', path: row.dataset.itemDoc, line: Number(row.dataset.line), ...openHow(e) });
    return;
  }
  if (row.dataset.doc != null) {
    if (!repeatClick(e)) emit('open', { type: 'doc', path: row.dataset.doc, ...openHow(e) });   // D91
    return;
  }
  const dir = row.dataset.dir;
  if (e.target.closest('[data-toggle]')) {       // 화살표: 펼치기/접기만
    if (S.open.has(dir)) S.open.delete(dir);
    else S.open.add(dir);
    renderTree();
    return;
  }
  if (dir) S.open.add(dir);
  emit('open', { type: 'overview', path: dir });
}

/** 프로젝트 기준 경로 → 전체 경로 (서버 OS 의 구분자로). '' 면 프로젝트 폴더 */
export function fullPath(path) {
  return path ? `${S.root}${S.sep}${path.split('/').join(S.sep)}` : S.root;
}

async function copy(text) {
  toast(await copyText(text) ? t('복사했습니다: {what}', { what: text }) : t('복사하지 못했습니다'), '');
}

/** 터미널에 넣을 경로: 글자·숫자·경로 기호 말고 다른 것(빈칸·&·$·괄호 등)이 있으면 작은따옴표로 감싼다 — PowerShell 이 한 낱말로 읽고
 * $·` 를 풀지 않게 (안의 ' 는 '' 로). 끝에 빈칸 — 이어서 치도록 */
// PowerShell 은 ' 말고도 ‘ ’ ‚ ‛ 를 작은따옴표로 읽는다 — 이름에 그런 글자가 있어도 문자열을 끝내지 못하게 모두 겹쳐 쓴다
export const psQuote = (text) => `'${String(text).replace(/['\u2018\u2019\u201a\u201b]/g, (c) => c + c)}'`;
export const shellWord = (text) => `${/^[\p{L}\p{N}_.\-\\/:@]+$/u.test(text) ? text : psQuote(text)} `;

/** 트리 행과 본문 빈 곳(docmenu.js)의 우클릭 메뉴 항목: 경로 복사(옆에 터미널에 붙여 넣기, D51), 편집기로 열기, 탐색기에서 보기 */
export function pathMenuItems(path, isDoc) {
  /** @type {MenuItem[]} */
  const copies = [];
  if (path) copies.push({ label: t('@{path} 복사', { path }), tip: t('{cli} 프롬프트에 붙여 넣기', { cli: aiCli() }), action: () => copy(`@${path}`), term: `@${path} ` });
  copies.push({ label: t('전체 경로 복사'), action: () => copy(fullPath(path)), term: shellWord(fullPath(path)) });
  /** @type {MenuItem[]} */
  const opens = [];
  if (isDoc) opens.push({ label: t('외부 편집기로 열기'), action: () => openExternal(path) });
  opens.push({ label: t('탐색기에서 보기'), action: () => revealInExplorer(path) });
  /** @type {MenuItem[]} */
  const views = [];
  if (!isDoc && S.dirs.has(path)) {   // 문서가 있는 폴더 — 모아 보기 (parts.js)
    views.push({ label: path ? t('이 폴더의 표·그림 등 모아 보기') : t('프로젝트의 표·그림 등 모아 보기'),
      tip: t("사이드바 '모아 보기' 탭"), action: () => emit('parts', { path }) });
  }
  return menuGroups(copies, opens, views);
}

/** 파일 우클릭의 이름 바꾸기 (D66 — rename.js): 같은 폴더 안에서 이름만. F2 도 (트리·'코드'·'자료' 목록·최근 변경·검색) */
export const renameItem = (path) => ({ label: t('이름 바꾸기…'), hint: 'F2', action: () => emit('rename', { path }) });

/** 문서 삭제 (D104 — deletedoc.js): 이 트리의 문서만. 코드·자료 목록과 최근 변경·검색에는 넣지 않는다 */
const deleteItem = (path) => ({ label: t('문서 삭제…'), tip: t('휴지통으로 보냅니다'), action: () => emit('delete-doc', { path }) });

/** 우클릭의 새로 만들기 (D65·D105): 이 폴더에 새 문서 — 제목과 스타일을 묻고 만들어 바로 쓴다 */
export const newDocItem = (dir) => ({ label: t('새 문서 만들기…'), hint: 'Ctrl+N', action: () => emit('new-doc', { dir }) });
/** 우클릭의 새 폴더 (D114): 이 폴더 안에 — 빈 폴더는 트리에 나오지 않아 만든 뒤 그 폴더의 새 문서 창을 연다 */
export const newFolderItem = (dir) => ({ label: t('새 폴더 만들기…'), action: () => emit('new-folder', { dir }) });

/** 문서를 Lectern 슬라이드로 바꿔 달라는 요청 글 (한 줄 — D96). 원본은 그대로 두고 같은 폴더에 만든다 (상대 경로가 살아 있게) */
function slideRequest(path) {
  const ask = t('@{path} 를 Lectern 슬라이드로 만들어 주세요. 원본은 고치지 말고 같은 폴더에 새 파일로 만드세요.', { path });
  return S.slidesGuide ? `${ask} ${t('작성 방법은 {path} 를 읽으세요.', { path: S.slidesGuide })}` : ask;
}

/** 문서 행의 우클릭 메뉴 — 새 탭에서 열기(D64)·이름 바꾸기(D66)와 경로 항목 (트리·'코드'·'자료' 목록의 문서·최근 변경·검색이 함께 쓴다) */
export function docMenuItems(path, type = 'doc') {
  /** @type {MenuItem[]} */
  const opens = [];
  if (!(S.view?.type === type && S.view.path === path)) {
    opens.push({ label: t('새 문서 탭에서 열기'), hint: t('누르기'), action: () => emit('open', { type, path, newTab: true, force: true }) },
      { label: t('지금 탭에서 열기'), hint: t('Alt+누르기'), action: () => emit('open', { type, path }) });
  }
  opens.push({ label: t('새 창에서 열기'), action: () => emit('open-window', { type, path }) });
  /** @type {MenuItem[]} */
  const asks = type === 'doc' && isMd(path) && !S.tab?.fileMap.get(path)?.deck
    ? [{ label: t('Lectern 슬라이드로 바꾸기 요청'), tip: t('터미널에 (Enter 는 누르지 않음)'), action: () => emit('term-paste', slideRequest(path)) }]
    : [];
  return menuGroups([{ header: path }], opens, asks, pathMenuItems(path, true), [renameItem(path)]);
}

/** 형광펜·할 일 줄의 우클릭 (D143): 그 자리로, 메모 달기, 형광펜이면 이것만·이 문서의 것 모두 지우기 */
function itemMenu(row) {
  const path = row.dataset.itemDoc;
  const line = Number(row.dataset.line);
  const text = row.dataset.text;
  const mark = row.classList.contains('marks');
  const ro = !!S.tab?.readonly;
  /** @type {MenuItem[]} */
  const items = [{ header: `${path} · ${t('{a}행', { a: line })}` }, { label: t('그 자리로 가기'), action: () => emit('open', { type: 'doc', path, line }) }];
  if (!ro) items.push({ label: t('메모 달기'), tip: t('메모 패널에 — 이 글이 제목이고, 메모에서 이 자리로 돌아옵니다 (줄이 밀려도 이 글로 찾습니다)'), action: () => emit('new-note', { title: text, path, line, end: line, find: text }) });
  if (mark && !ro) {
    items.push('-', { label: t('이 형광펜 지우기'), tip: t('글은 그대로 두고 칠한 것만'), action: () => emit('clear-marks', { path, line, text, color: row.dataset.color }) },
      { label: t('이 문서의 형광펜 모두 지우기…'), action: () => emit('clear-marks', { path }) });
  }
  return items;
}

/**
 * 형광펜 하위 묶음의 문서 행: 이 문서의 형광펜 모두·색마다 지우기
 * @returns {MenuItem[]}
 */
function clearItems(path) {
  const marks = marksOf(S.tab)?.get(path)?.marks ?? [];
  if (!marks.length || S.tab?.readonly) return [];
  const colors = [...new Set(marks.map((m) => m.color || ''))];
  const names = MARK_NAMES();
  return ['-', { label: t('이 문서의 형광펜 모두 지우기…'), tip: t('{n}곳 — 글은 그대로', { n: marks.length }), action: () => emit('clear-marks', { path }) },
    ...(colors.length > 1 ? colors.map((c) => ({ label: t('이 문서의 {color} 형광펜만 지우기…', { color: names[c] }), action: () => emit('clear-marks', { path, color: c }) })) : [])];
}

function onContextMenu(e) {
  const row = e.target.closest('.row');
  e.preventDefault();
  if (row?.dataset.itemDoc != null) {
    showMenu(e.clientX, e.clientY, itemMenu(row));
    return;
  }
  if (!row) {   // 목록의 빈 곳
    if (S.tab && !S.tab.readonly) showMenu(e.clientX, e.clientY, [newDocItem(''), newFolderItem(''), workCardItem()]);
    return;
  }
  if (row.dataset.doc != null) {
    const path = row.dataset.doc;
    const items = [...docMenuItems(path), ...(currentKind().id === 'marks' ? clearItems(path) : [])];
    showMenu(e.clientX, e.clientY, S.tab?.readonly ? items : [...items, '-', newDocItem(dirname(path)), deleteItem(path)]);
  }
  else showMenu(e.clientX, e.clientY, [newDocItem(row.dataset.dir), newFolderItem(row.dataset.dir), ...(S.tab && !S.tab.readonly ? [workCardItem(row.dataset.dir)] : []), '-', ...pathMenuItems(row.dataset.dir, false)]);
}

// 글자를 치면 그 글자로 시작하는 다음 행으로 (탐색기처럼 — others.js 와 같게). 잠깐 사이에 이어 치면 이어진 글자로
let typed = '';
let typedAt = 0;

/** 행의 위 행: 문서·폴더는 상위 폴더, 형광펜·할 일 줄은 그 문서 */
function parentRow(box, row) {
  if (row.dataset.itemDoc != null) return box.querySelector(`.row[data-doc="${CSS.escape(row.dataset.itemDoc)}"]`);
  const up = dirname(row.dataset.doc ?? row.dataset.dir ?? '');
  return up ? box.querySelector(`.row[data-dir="${CSS.escape(up)}"]`) : null;
}

/**
 * 문서 트리의 키 (D169 — '코드'·'자료'·'폴더' 목록과 같게): ↑·↓·Home·End 로 옮기고, → 는 폴더 펼치기(펼쳐 있으면 첫 항목), ← 는 접기·위 폴더,
 * 글자는 그 글자로 시작하는 행. Enter 는 누르기와 같고(문서 열기·폴더 개요), F2 는 이름 바꾸기
 */
function onTreeKey(e) {
  const box = /** @type {HTMLElement} */ (e.currentTarget);
  const cur = /** @type {HTMLElement} */ (e.target).closest?.('.row');
  if (!cur) return;
  if (e.key === 'Enter') {
    clickFromKey(e);
    return;
  }
  if (e.key === 'F2') {   // 이름 바꾸기 (D66)
    if (cur.dataset.doc != null) {
      e.preventDefault();
      emit('rename', { path: cur.dataset.doc });
    }
    return;
  }
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const rows = $$('.row', box);
  const i = rows.indexOf(cur);
  const go = (row) => {
    if (!row) return;
    rove(row);
    row.focus({ preventScroll: true });
    row.scrollIntoView({ block: 'nearest' });
  };
  const dir = cur.dataset.dir;
  const shut = dir != null && !cur.querySelector('.caret')?.classList.contains('open');
  const folds = dir != null && !currentKind().content;   // 형광펜·할 일 묶음은 폴더가 늘 펼쳐 있다 — 옮기기만
  const setOpen = (open) => {
    if (open) S.open.add(dir);
    else S.open.delete(dir);
    render();   // 초점은 그 폴더 행에 남는다 (keepFocus)
  };
  if (e.key === 'ArrowDown') go(rows[Math.min(rows.length - 1, i + 1)]);
  else if (e.key === 'ArrowUp') go(rows[Math.max(0, i - 1)]);
  else if (e.key === 'Home') go(rows[0]);
  else if (e.key === 'End') go(rows[rows.length - 1]);
  else if (e.key === 'ArrowRight' && dir != null) {
    if (folds && shut) setOpen(true);
    else go(rows[i + 1]);
  } else if (e.key === 'ArrowLeft') {
    if (folds && !shut) setOpen(false);
    else go(parentRow(box, cur));   // 거른 목록에서는 위 폴더가 보이지 않아 그대로
  } else if (e.key.length === 1 && e.key !== ' ' && !e.isComposing) {
    const now = Date.now();
    typed = now - typedAt > 800 ? e.key.toLowerCase() : typed + e.key.toLowerCase();
    typedAt = now;
    const same = [...typed].every((c) => c === typed[0]);   // 같은 글자를 거듭 치면 그 글자로 시작하는 다음 행
    const want = same ? typed[0] : typed;
    const from = same ? i + 1 : i;
    const order = [...rows.slice(from), ...rows.slice(0, from)];
    go(order.find((r) => (r.querySelector('.label')?.textContent || '').toLowerCase().startsWith(want)));
  } else return;
  e.preventDefault();
  e.stopPropagation();   // 현재 줄의 ↑·↓ 등 앱 단축키로 가지 않게
}

export function focusFilter() {
  switchPanel('files');
  $('#lec-filter').focus();
  $('#lec-filter').select();
}

export function initTree() {
  const tree = $('#lec-tree');
  tree.addEventListener('click', onRowClick);
  middleClickOpens(tree, '.row[data-doc]');   // 가운데 버튼: 새 문서 탭 (D64)
  tree.addEventListener('contextmenu', onContextMenu);
  tree.addEventListener('keydown', onTreeKey);
  tree.addEventListener('focusin', (e) => { if (e.target.matches?.('.row')) rove(e.target); });   // 누른 행이 Tab 의 자리
  const filter = $('#lec-filter');
  filter.addEventListener('input', renderTree);
  filter.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      $('#lec-tree .row.file')?.click();
    } else if (e.key === 'Escape' && filter.value) {
      e.stopPropagation();
      filter.value = '';
      filter.dispatchEvent(new Event('input'));   // 트리와 문서 외 파일(others.js)을 함께 다시 그린다
    }
  });
  $('#lec-btn-titles').addEventListener('click', async () => {
    await saveConfig({ show_titles: !showTitles() });
    render();
    emit('titles');   // 최근 변경·검색·폴더 보기의 문서 행도
  });
  $('#lec-btn-sort').addEventListener('click', openSort);
  on('config-follow', (keys) => {   // 다른 창에서 바꾼 제목 보이기·차례 (D159)
    if (!keys.has('show_titles') && !keys.has('side_sort')) return;
    render();
    if (keys.has('show_titles')) emit('titles');
    if (keys.has('side_sort')) emit('side-sort');
  });
  $('#lec-btn-expand').addEventListener('click', openExpand);
  for (const box of $$('#lec-docs .doc-kinds')) {   // 하위 묶음의 머리줄 (D143)
    box.addEventListener('click', (e) => {
      const id = e.target.closest('.kind-head')?.dataset.kind;
      if (!id || !S.tab || currentKind().id === id) return;
      S.tab.side.docKind = id;
      saveConfig({ docs_kind: id });
      $('#lec-tree').scrollTop = 0;
      render();
    });
  }
  for (const b of $$('.side-tabs button')) b.addEventListener('click', () => switchPanel(b.dataset.tab));

  on('tree', () => {   // 문서가 바뀌었으면 형광펜·할 일도 다시 (보고 있을 때만 받는다)
    if (S.tab?.marks) S.tab.marks.stale = true;
    render();
  });
  on('changed', render);
  on('tab', onTab);
  on('view', revealCurrent);
}
