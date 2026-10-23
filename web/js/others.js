// 사이드바 '파일' 목록 (D36, D37). 보는 방법 두 가지 (거르기 칸 옆 '폴더' 버튼, 설정 files_view):
// - 종류별(kind, 기본): 위는 문서 트리(tree.js), 분리선 너머 아래는 문서(md·트리에 보이는 html)가 아닌 파일을 탐색기처럼.
// - 폴더(folder): 문서 트리·분리선·머리줄을 감추고 이 목록 하나에 문서와 파일을 폴더 구조 그대로 함께 보인다.
//   문서 행은 문서 트리처럼 누르면 뷰어에서 열고(제목·바뀜 점·지금 보는 문서 강조), 파일 행은 탐색기처럼.
//
// - 문서가 아닌 파일은 서버가 문서 트리와 따로 훑는다 (GET /api/others). 목록이 보일 때만 읽고, 파일이 생기거나 지워지면
//   (watch.js 의 'others') 다시 읽는다. 폴더 보기는 이것과 탭의 문서 트리(S.tree)를 합쳐 그린다.
//   탭마다 받은 목록·펼친 폴더(보기마다 따로)·고른 행·스크롤 위치를 남긴다 (tab.others).
// - 탐색기처럼: 누르면 고르고, 두 번 누르거나 Enter 면 연다 — 안전한 형식(PDF·오피스·그림·csv 등)은 기본 앱, 코드·글은 편집기,
//   실행·설치 파일과 압축 등은 탐색기에서 선택만 한다 (POST /api/open-external → osutil.open_path — 실행하지 않는다). 폴더는 펼치고 접는다.
//   ↑·↓·←·→·Home·End 와 글자 입력(그 글자로 시작하는 행)으로 옮겨 다니고, 우클릭·메뉴 키·Shift+F10 에 열기·편집기로 열기·
//   탐색기에서 보기·경로 복사. 보기 전용이라 이름 바꾸기·지우기·옮기기는 없다.
// - 종류별 보기에서는 분리선을 끌어 높이를 바꾸고(설정 others_height, 두 번 누르면 기본), 머리줄을 눌러 접는다(others_visible).
// - 사이드바 거르기(#lec-filter)는 이 목록에도 적용된다: 거른 파일(폴더 보기는 문서도)을 평평하게 보인다.

import { S, emit, on } from './store.js';
import { getJSON, saveConfig, openExternal, revealInExplorer } from './api.js';
import { fullPath, labelOf, tipOf, pathMenuItems, hasChangedInside } from './tree.js';
import { fileIcon, folderIcon } from './icons.js';
import { showMenu } from './ui.js';
import { $, $$, esc, dirname, formatDateTime, formatSize, copyText, toast, keepFocus } from './util.js';

const MAX_FILTER_RESULTS = 300;
const MIN_HEIGHT = 64;   // 분리선을 끌어 줄일 수 있는 높이 (머리줄 + 두 줄쯤)
const OPEN_HINT = { default: '기본 앱으로', editor: '편집기로', reveal: '탐색기에서 선택만 (실행하지 않음)' };

const list = () => $('#lec-others-list');
const state = () => S.tab?.others || null;
const folderView = () => S.config.files_view === 'folder';
const fileTip = (f) => `${f.name}\n${formatSize(f.size)} · 수정 ${formatDateTime(f.mtime)}\n${f.path}`;

/** 목록이 보이는지: 탭이 있고, 사이드바 '파일' 탭이고, 폴더 보기이거나 펼쳐 있음 */
const shown = () => !!S.tab && !$('#lec-files').hidden && (folderView() || S.config.others_visible !== false);

/** 경로 → 노드 (부모 경로를 parent 로 단다 — ← 로 부모에 갈 때) */
function indexOf(nodes, parent = null, map = new Map()) {
  for (const n of nodes) {
    map.set(n.path, { ...n, parent });
    if (n.type === 'dir') indexOf(n.children, n.path, map);
  }
  return map;
}

function* filesIn(nodes) {
  for (const n of nodes) {
    if (n.type === 'file') yield n;
    else yield* filesIn(n.children);
  }
}

// 서버(scanner.natural_key)와 같은 자연 정렬: 숫자 부분은 수로, 나머지는 소문자로 ('2장' < '10장')
const natKey = (s) => s.split(/(\d+)/).map((t, i) => (i % 2 ? Number(t) : t.toLowerCase()));
function byName(a, b) {
  const x = natKey(a.name);
  const y = natKey(b.name);
  for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i] < y[i] ? -1 : 1;
  return x.length - y.length;
}

/** 폴더 보기: 문서 트리와 문서 외 파일 트리를 폴더마다 합친다. 문서 노드에는 doc: true. 폴더 먼저, 자연 정렬 */
function merge(docs = [], others = []) {
  const dirs = new Map();
  const files = [];
  for (const [nodes, doc] of [[docs, true], [others, false]]) {
    for (const n of nodes) {
      if (n.type === 'file') {
        files.push({ ...n, doc });
        continue;
      }
      const d = dirs.get(n.path) || { type: 'dir', name: n.name, path: n.path, docs: [], others: [] };
      d[doc ? 'docs' : 'others'] = n.children;
      dirs.set(n.path, d);
    }
  }
  const merged = [...dirs.values()].map((d) => ({ type: 'dir', name: d.name, path: d.path, children: merge(d.docs, d.others) }));
  return [...merged.sort(byName), ...files.sort(byName)];
}

// ---- 그리기 -------------------------------------------------------------------

/** 지금 보기의 경로 → 노드 (키보드·메뉴가 쓴다) */
const index = () => (folderView() ? state()?.allIndex : state()?.index) || new Map();
/** 지금 보기의 펼친 폴더 */
const openSet = (o) => (folderView() ? o.folderOpen : o.open);

function rowAttrs(o, path, depth, extra = '') {
  const sel = path === o.selected;
  return `class="row${extra}${sel ? ' selected' : ''}" role="treeitem" aria-selected="${sel}" data-path="${esc(path)}"`
    + ` style="--d:${depth}" tabindex="${sel ? 0 : -1}"`;
}

const subHtml = (sub) => (sub ? `<span class="sub">${esc(sub)}</span>` : '');

function fileRow(o, f, depth, sub = '') {
  if (f.doc) {   // 폴더 보기의 문서: 문서 트리와 같은 글·바뀜 점, 지금 보는 문서 강조
    const active = S.view?.type === 'doc' && S.view.path === f.path ? ' active' : '';
    return `<div ${rowAttrs(o, f.path, depth, ` file doc${active}`)} title="${esc(tipOf(f))}"><span class="caret-space"></span>`
      + `${fileIcon(f.name, f.kind)}<span class="label">${esc(labelOf(f))}</span>${subHtml(sub)}`
      + `${S.changed.has(f.path) ? '<span class="dot" title="열어 보기 전에 바뀜"></span>' : ''}</div>`;
  }
  return `<div ${rowAttrs(o, f.path, depth, ' file')} title="${esc(fileTip(f))}"><span class="caret-space"></span>${fileIcon(f.name)}`
    + `<span class="label">${esc(f.name)}</span>${subHtml(sub)}</div>`;
}

function nodesHtml(o, nodes, depth) {
  const opened = openSet(o);
  let html = '';
  for (const n of nodes) {
    if (n.type === 'file') {
      html += fileRow(o, n, depth);
      continue;
    }
    const open = opened.has(n.path);
    const view = folderView() && S.view?.type === 'overview' && S.view.path === n.path ? ' active' : '';
    const dot = folderView() && !open && hasChangedInside(n.path) ? '<span class="dot" title="안쪽 문서가 바뀜"></span>' : '';
    html += `<div ${rowAttrs(o, n.path, depth, ` dir${view}`)} aria-expanded="${open}" title="${esc(n.path)}/">`
      + `<span class="caret${open ? ' open' : ''}" data-toggle aria-hidden="true"></span>${folderIcon()}<span class="label">${esc(n.name)}</span>${dot}</div>`;
    if (open) html += nodesHtml(o, n.children, depth + 1);
  }
  return html;
}

/** 종류별 보기: 문서가 아닌 파일만 */
function kindHtml(o, terms) {
  if (terms) {
    const hits = [...filesIn(o.data.tree)].filter((f) => terms.every((t) => f.path.toLowerCase().includes(t)));
    return hits.length
      ? hits.slice(0, MAX_FILTER_RESULTS).map((f) => fileRow(o, f, 0, dirname(f.path))).join('')
      : '<p class="side-empty">일치하는 파일이 없습니다</p>';
  }
  return o.data.tree.length ? nodesHtml(o, o.data.tree, 0) : '<p class="side-empty">문서가 아닌 파일이 없습니다</p>';
}

/** 폴더 보기: 맨 위 프로젝트 행(누르면 개요) + 문서와 파일을 합친 트리 */
function folderHtml(o, terms) {
  if (terms) {
    const docs = S.files.filter((f) => terms.every((t) => `${(f.title || '').toLowerCase()} ${f.path.toLowerCase()}`.includes(t)));
    const files = [...filesIn(o.data?.tree || [])].filter((f) => terms.every((t) => f.path.toLowerCase().includes(t)));
    const hits = [...docs.map((f) => ({ ...f, doc: true })), ...files];
    return hits.length
      ? hits.slice(0, MAX_FILTER_RESULTS).map((f) => fileRow(o, f, 0, dirname(f.path))).join('')
      : '<p class="side-empty">일치하는 문서나 파일이 없습니다</p>';
  }
  const root = S.view?.type === 'overview' && !S.view.path ? ' active' : '';
  return `<div ${rowAttrs(o, '', 0, ` dir root${root}`)} title="프로젝트 개요"><span class="label">${esc(S.name)}</span></div>`
    + (o.all.length ? nodesHtml(o, o.all, 0) : '<p class="side-empty">문서나 파일이 없습니다</p>');
}

function renderHead() {
  const d = state()?.data;
  $('#lec-others-count').textContent = d ? `${d.count}${d.truncated ? '+' : ''}` : '';
}

function render() {
  renderHead();
  const o = state();
  const box = list();
  const folder = folderView();
  if (!o || (folder ? !S.tab.treeLoaded : !o.data)) {   // 탭이 없거나 아직 읽는 중
    box.innerHTML = o?.error && !folder ? `<p class="side-empty">${esc(o.error)}</p>` : '';
    return;
  }
  if (folder) {
    o.folderOpen ??= new Set(S.open);   // 처음 폴더 보기로 볼 때 문서 트리에서 펼쳐 둔 폴더대로
    o.all = merge(S.tree, o.data?.tree);
    o.allIndex = indexOf(o.all);
  }
  const query = $('#lec-filter').value.trim().toLowerCase();
  const terms = query ? query.split(/\s+/) : null;
  let html = folder ? folderHtml(o, terms) : kindHtml(o, terms);
  if (o.data?.truncated) html += `<p class="side-empty">파일이 많아 ${o.data.limit}개까지만 보입니다</p>`;
  keepFocus(box, () => { box.innerHTML = html; });
  // Tab 키로 목록에 들어올 행: 고른 행, 없으면 첫 행
  if (!box.querySelector('.row[tabindex="0"]')) box.querySelector('.row')?.setAttribute('tabindex', '0');
}

/** 폴더 보기에서 지금 보는 문서(폴더)가 보이게: 상위 폴더를 펴고 그 행까지 스크롤 (문서 트리의 revealCurrent 처럼) */
function revealCurrent() {
  const o = state();
  if (!o || !folderView() || !S.view) return;
  o.folderOpen ??= new Set(S.open);
  const parts = S.view.path ? S.view.path.split('/') : [];
  const upto = S.view.type === 'doc' ? parts.length - 1 : parts.length;
  for (let i = 1; i <= upto; i++) o.folderOpen.add(parts.slice(0, i).join('/'));
  render();
  list().querySelector('.row.active')?.scrollIntoView({ block: 'nearest' });
}

// ---- 읽기 ---------------------------------------------------------------------

function load(tab, { fresh = false } = {}) {
  const o = tab.others;
  o.stale = false;
  o.loading = (async () => {
    try {
      const d = await getJSON(`/api/others?p=${encodeURIComponent(tab.id)}${fresh ? '&fresh=1' : ''}`);
      o.data = d;
      o.index = indexOf(d.tree);
      o.error = null;
      for (const p of [...o.open]) if (!o.index.has(p)) o.open.delete(p);
    } catch (e) {
      if (S.tabs.includes(tab)) o.error = `파일 목록을 읽지 못했습니다 (${e.message}). F5 로 다시 읽습니다.`;
    } finally {
      o.loading = null;
    }
    if (tab === S.tab) render();
    if (o.stale) ensure();   // 읽는 동안 또 바뀌었다
  })();
  return o.loading;
}

/** 목록이 보이는데 아직 받지 않았거나 그 뒤로 파일이 바뀌었으면 읽는다 */
function ensure() {
  const o = state();
  if (o && shown() && (o.stale || !o.data) && !o.loading) load(S.tab);
}

/** F5: 서버에서 새로 훑는다 (감시가 놓친 변경까지) */
export function refreshOthers() {
  const o = state();
  if (!o) return;
  o.stale = true;
  if (shown() && !o.loading) load(S.tab, { fresh: true });
}

// ---- 고르기·열기 ----------------------------------------------------------------

const rowOf = (path) => list().querySelector(`.row[data-path="${CSS.escape(path)}"]`);
const rows = () => $$('.row', list());

function select(path, { focus = true } = {}) {
  const o = state();
  if (!o || path == null) return;
  o.selected = path;
  for (const r of $$('.row.selected', list())) {
    r.classList.remove('selected');
    r.setAttribute('aria-selected', 'false');
    r.tabIndex = -1;
  }
  const row = rowOf(path);
  if (!row) return;
  row.classList.add('selected');
  row.setAttribute('aria-selected', 'true');
  row.tabIndex = 0;
  if (focus) row.focus({ preventScroll: true });
  row.scrollIntoView({ block: 'nearest' });
}

function toggle(path, open) {
  const set = openSet(state());
  const want = open ?? !set.has(path);
  if (want) set.add(path);
  else set.delete(path);
  render();
  select(path);
}

/** 두 번 누르기·Enter: 파일은 열고(문서는 뷰어에서) 폴더는 펼치거나 접는다. 폴더 보기의 프로젝트 행은 개요 */
function activate(path) {
  if (path === '' && folderView()) {
    emit('open', { type: 'overview', path: '' });
    return;
  }
  const n = index().get(path);
  if (!n) return;
  if (n.type === 'dir') toggle(path);
  else if (n.doc) emit('open', { type: 'doc', path });
  else openExternal(path);
}

async function copy(text) {
  toast(await copyText(text) ? `복사했습니다: ${text}` : '복사하지 못했습니다');
}

function menuItems(n) {
  if (n.doc) return [{ header: n.path }, ...pathMenuItems(n.path, true)];   // 문서 트리와 같은 메뉴
  const items = [];
  if (n.type === 'dir') {
    items.push({ header: `${n.path}/` },
      { label: openSet(state()).has(n.path) ? '접기' : '펼치기', hint: '두 번 누르기·Enter', action: () => toggle(n.path) });
    if (folderView() && S.dirs.has(n.path)) items.push({ label: '폴더 개요 보기', action: () => emit('open', { type: 'overview', path: n.path }) });
    items.push({ label: '탐색기에서 열기', action: () => openExternal(n.path) });
  } else {
    items.push({ header: `${n.name} · ${formatSize(n.size)} · ${formatDateTime(n.mtime)}` },
      { label: '열기', hint: `${OPEN_HINT[n.open] || ''} — 두 번 누르기·Enter`, action: () => openExternal(n.path) });
    // 기본 앱으로 여는 형식(csv·txt 등)은 편집기로도. 읽을 수 없는 형식(실행 파일·압축 등)은 편집기로 열지 않는다
    if (n.open === 'default') items.push({ label: '편집기로 열기', action: () => openExternal(n.path, undefined, 'editor') });
    items.push({ label: '탐색기에서 보기', action: () => revealInExplorer(n.path) });
  }
  items.push('-', { label: `@${n.path} 복사`, hint: 'Claude Code 프롬프트에 붙여 넣기', action: () => copy(`@${n.path}`) },
    { label: '전체 경로 복사', action: () => copy(fullPath(n.path)) });
  if (n.type === 'file') items.push({ label: '파일 이름 복사', action: () => copy(n.name) });
  return items;
}

function openMenu(path, x, y) {
  const n = path === '' && folderView() ? { type: 'dir', path: '', root: true } : index().get(path);
  if (!n) return;
  select(path);
  showMenu(x, y, n.root ? [{ header: S.root }, ...pathMenuItems('', false)] : menuItems(n));
}

// 글자를 치면 그 글자로 시작하는 다음 행으로 (탐색기처럼). 잠깐 사이에 이어 치면 이어진 글자로
let typed = '';
let typedAt = 0;

function onKey(e) {
  const o = state();
  const all = rows();
  if (!o || !all.length) return;
  const cur = e.target.closest?.('.row') || rowOf(o.selected ?? '') || all[0];
  const i = all.indexOf(cur);
  const path = cur.dataset.path;
  const n = index().get(path);
  const opened = openSet(o);
  const go = (row) => row && select(row.dataset.path);
  if (e.key === 'ArrowDown') go(all[Math.min(all.length - 1, i + 1)]);
  else if (e.key === 'ArrowUp') go(all[Math.max(0, i - 1)]);
  else if (e.key === 'Home') go(all[0]);
  else if (e.key === 'End') go(all[all.length - 1]);
  else if (e.key === 'ArrowRight' && n?.type === 'dir') {
    if (!opened.has(path)) toggle(path, true);
    else go(all[i + 1]);   // 펼쳐 있으면 첫 항목으로
  } else if (e.key === 'ArrowLeft') {
    if (n?.type === 'dir' && opened.has(path)) toggle(path, false);
    else if (n?.parent && rowOf(n.parent)) select(n.parent);   // 거른 목록에서는 부모가 보이지 않아 그대로
  } else if (e.key === 'Enter') activate(path);
  else if (e.key === 'ContextMenu' || (e.key === 'F10' && e.shiftKey)) {
    const r = cur.getBoundingClientRect();
    openMenu(path, r.left + 24, r.bottom);
  } else if (e.key.length === 1 && e.key !== ' ' && !e.ctrlKey && !e.metaKey && !e.altKey) {
    const now = Date.now();
    typed = now - typedAt > 800 ? e.key.toLowerCase() : typed + e.key.toLowerCase();
    typedAt = now;
    const from = typed.length === 1 ? i + 1 : i;   // 같은 글자를 거듭 치면 다음 것으로
    const order = [...all.slice(from), ...all.slice(0, from)];
    go(order.find((r) => r.querySelector('.label').textContent.toLowerCase().startsWith(typed)));
  } else return;
  e.preventDefault();
  e.stopPropagation();   // 장 하이라이트의 ↑·↓ 등 앱 단축키로 가지 않게
}

// ---- 보기·분리선·접기 -----------------------------------------------------------

function applyLayout() {
  const open = S.config.others_visible !== false;
  const folder = folderView();
  $('#lec-files').classList.toggle('others-off', !open);
  $('#lec-files').classList.toggle('folder-view', folder);
  $('#lec-btn-view').classList.toggle('on', folder);
  $('#lec-others-list').setAttribute('aria-label', folder ? '문서와 파일 (폴더 구조)' : '파일');
  $('#lec-others-head').setAttribute('aria-expanded', String(open));
  $('#lec-others-head .caret').classList.toggle('open', open);
  const h = Number(S.config.others_height);
  if (h) $('#lec-others').style.setProperty('--others-h', `${Math.round(h)}px`);
  else $('#lec-others').style.removeProperty('--others-h');   // app.css 의 기본 높이
}

function bindSplit() {
  const split = $('#lec-others-split');
  const root = document.documentElement;
  split.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    split.setPointerCapture(e.pointerId);
    const max = $('#lec-files').getBoundingClientRect().height - MIN_HEIGHT;
    const start = $('#lec-others').getBoundingClientRect().height;
    // 잡은 곳에서 움직인 만큼 (분리선을 잡는 순간 높이가 튀지 않게)
    const heightAt = (ev) => Math.round(Math.min(max, Math.max(MIN_HEIGHT, start + e.clientY - ev.clientY)));
    const move = (ev) => $('#lec-others').style.setProperty('--others-h', `${heightAt(ev)}px`);
    const up = (ev) => {
      split.removeEventListener('pointermove', move);
      split.removeEventListener('pointerup', up);
      root.classList.remove('resizing-rows');
      if (ev.clientY !== e.clientY) saveConfig({ others_height: heightAt(ev) });   // 누르기만 했으면(두 번 누르기 등) 저장하지 않는다
    };
    root.classList.add('resizing-rows');
    split.addEventListener('pointermove', move);
    split.addEventListener('pointerup', up);
  });
  split.addEventListener('dblclick', () => {
    saveConfig({ others_height: null });
    applyLayout();
  });
  $('#lec-others-head').addEventListener('click', async () => {
    await saveConfig({ others_visible: S.config.others_visible === false });
    applyLayout();
    ensure();
  });
  // 종류별 ↔ 폴더 구조
  $('#lec-btn-view').addEventListener('click', async () => {
    await saveConfig({ files_view: folderView() ? 'kind' : 'folder' });
    applyLayout();
    if (folderView()) revealCurrent();
    else render();
    ensure();
  });
}

export function initOthers() {
  const box = list();
  box.addEventListener('click', (e) => {
    const row = e.target.closest('.row');
    if (!row) return;
    const { path } = row.dataset;
    if (e.target.closest('[data-toggle]')) {
      toggle(path);
      return;
    }
    select(path);
    // 폴더 보기의 문서와 프로젝트 행은 문서 트리처럼 한 번 누르면 연다
    if (folderView() && (path === '' || index().get(path)?.doc)) activate(path);
  });
  box.addEventListener('dblclick', (e) => {
    const row = e.target.closest('.row');
    if (!row || e.target.closest('[data-toggle]')) return;
    const { path } = row.dataset;
    if (folderView() && (path === '' || index().get(path)?.doc)) return;   // 한 번 누를 때 이미 열었다
    activate(path);
  });
  box.addEventListener('contextmenu', (e) => {
    const row = e.target.closest('.row');
    if (!row) return;
    e.preventDefault();
    openMenu(row.dataset.path, e.clientX, e.clientY);
  });
  box.addEventListener('keydown', onKey);
  box.addEventListener('scroll', () => { const o = state(); if (o) o.scroll = box.scrollTop; }, { passive: true });
  bindSplit();
  applyLayout();
  $('#lec-filter').addEventListener('input', render);
  on('tab', () => {
    render();
    box.scrollTop = state()?.scroll || 0;
    ensure();
  });
  on('panel', ensure);   // 사이드바 '파일' 탭으로 돌아오면
  on('others', (tab) => { if (tab === S.tab) ensure(); });
  // 폴더 보기는 문서 트리도 그린다: 트리·바뀜 점·지금 보는 문서가 바뀌면 다시
  on('tree', () => { if (folderView()) render(); });
  on('changed', () => { if (folderView()) render(); });
  on('view', revealCurrent);
}
