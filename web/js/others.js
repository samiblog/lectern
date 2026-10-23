// 사이드바 '파일' 탭 (D36, D37, D42). 보는 방법 두 가지 (거르기 칸 옆 '폴더' 버튼, 설정 files_view):
// - 종류별(kind, 기본): 세 묶음 — '문서'(문서 트리, tree.js), '파일'(문서도 코드도 아닌 파일), '코드'(소스·스크립트·웹·설정 —
//   icons.js 의 코드 종류). 파일과 코드는 같은 모양의 탐색기 같은 목록이다. 묶음마다 머리줄을 눌러 접고
//   (docs_visible·others_visible·code_visible), 펼친 첫 묶음이 남은 높이를 갖고 나머지는 위 분리선을 끌어 높이를 정한다
//   (others_height·code_height, 두 번 누르면 기본).
// - 폴더(folder): 묶음 머리줄·문서 트리·코드 목록·분리선을 감추고 '파일' 목록 하나에 문서·파일·코드를 폴더 구조 그대로 함께 보인다.
//   문서 행은 문서 트리처럼 누르면 뷰어에서 열고(제목·바뀜 점·지금 보는 문서 강조), 파일 행은 탐색기처럼.
//
// - 문서가 아닌 파일은 서버가 문서 트리와 따로 훑는다 (GET /api/others). 목록이 보일 때만 읽고, 파일이 생기거나 지워지면
//   (watch.js 의 'others') 다시 읽는다. 받은 트리를 화면이 파일·코드로 나눈다. 폴더 보기는 이것과 탭의 문서 트리(S.tree)를 합친다.
//   탭마다 받은 목록, 목록마다 펼친 폴더·고른 행·스크롤 위치를 남긴다 (tab.others).
// - 탐색기처럼: 누르면 고르고, 두 번 누르거나 Enter 면 연다 — 안전한 형식(PDF·오피스·그림·csv 등)은 기본 앱, 코드·글은 편집기,
//   실행·설치 파일과 압축 등은 탐색기에서 선택만 한다 (POST /api/open-external → osutil.open_path — 실행하지 않는다). 폴더는 펼치고 접는다.
//   ↑·↓·←·→·Home·End 와 글자 입력(그 글자로 시작하는 행)으로 옮겨 다니고, 우클릭·메뉴 키·Shift+F10 에 열기·편집기로 열기·
//   탐색기에서 보기·경로 복사. 보기 전용이라 이름 바꾸기·지우기·옮기기는 없다.
// - 코드(목록의 코드, 폴더 보기의 코드 파일)는 한 번 누르거나 Enter 면 본문에 읽기 전용으로 (codeview.js, D43), 두 번 누르면 편집기로.
//   보고 있는 코드는 목록에서 상위 폴더를 펴고 강조한다.
// - 사이드바 거르기(#lec-filter)는 이 목록들에도 적용된다: 거른 파일(폴더 보기는 문서도)을 평평하게 보인다.

import { S, emit, on } from './store.js';
import { getJSON, saveConfig, openExternal, revealInExplorer } from './api.js';
import { fullPath, labelOf, tipOf, pathMenuItems, hasChangedInside } from './tree.js';
import { fileIcon, folderIcon, isCode } from './icons.js';
import { showMenu } from './ui.js';
import { $, $$, esc, dirname, formatDateTime, formatSize, copyText, toast, keepFocus } from './util.js';

const MAX_FILTER_RESULTS = 300;
const MIN_HEIGHT = 64;   // 분리선을 끌어 줄일 수 있는 높이 (머리줄 + 두 줄쯤)
const OPEN_HINT = { default: '기본 앱으로', editor: '편집기로', reveal: '탐색기에서 선택만 (실행하지 않음)' };

// 목록 둘: 파일(폴더 보기에서는 문서·파일·코드를 합친 트리)과 코드
const LISTS = {
  files: { el: '#lec-others-list', none: '문서나 코드가 아닌 파일이 없습니다', noHit: '일치하는 파일이 없습니다', visible: 'others_visible' },
  code: { el: '#lec-code-list', none: '코드 파일이 없습니다', noHit: '일치하는 코드가 없습니다', visible: 'code_visible' },
};
// 묶음 셋 (위에서부터). 펼친 첫 묶음이 남은 높이를 갖는다
const SECTIONS = [
  { el: '#lec-docs', visible: 'docs_visible' },
  { el: '#lec-others', visible: 'others_visible', height: 'others_height', css: '--others-h', split: '#lec-others-split' },
  { el: '#lec-code', visible: 'code_visible', height: 'code_height', css: '--code-h', split: '#lec-code-split' },
];

const listEl = (k) => $(LISTS[k].el);
const keyOf = (el) => el?.closest?.('[data-list]')?.dataset.list || 'files';
const state = () => S.tab?.others || null;
const folderView = () => S.config.files_view === 'folder';
const isOpen = (key) => S.config[key] !== false;
const fileTip = (f) => `${f.name}\n${formatSize(f.size)} · 수정 ${formatDateTime(f.mtime)}\n${f.path}`;

/** 목록 k 가 보이는지: 탭이 있고, 사이드바 '파일' 탭이고, (폴더 보기의 파일 목록이거나) 그 묶음이 펼쳐 있음 */
function shown(k) {
  if (!S.tab || $('#lec-files').hidden) return false;
  if (folderView()) return k === 'files';
  return isOpen(LISTS[k].visible);
}

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

/** keep 에 맞는 파일만 남긴 트리 (빈 폴더는 뺀다) */
function pick(nodes, keep) {
  const out = [];
  for (const n of nodes) {
    if (n.type === 'file') {
      if (keep(n)) out.push(n);
      continue;
    }
    const children = pick(n.children, keep);
    if (children.length) out.push({ ...n, children });
  }
  return out;
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

/** 목록 k 의 지금 모양: {tree, index(경로 → 노드), open(펼친 폴더), sel(고른 행을 기억하는 이름)} */
function view(o, k) {
  if (k === 'files' && folderView()) return { tree: o.all || [], index: o.allIndex || new Map(), open: o.folderOpen || new Set(), sel: 'folder' };
  return { tree: o.trees?.[k] || [], index: o.index?.[k] || new Map(), open: o.open[k], sel: k };
}

function rowAttrs(o, v, path, depth, extra = '') {
  const sel = path === o.selected[v.sel];
  return `class="row${extra}${sel ? ' selected' : ''}" role="treeitem" aria-selected="${sel}" data-path="${esc(path)}"`
    + ` style="--d:${depth}" tabindex="${sel ? 0 : -1}"`;
}

const subHtml = (sub) => (sub ? `<span class="sub">${esc(sub)}</span>` : '');

function fileRow(o, v, f, depth, sub = '') {
  if (f.doc) {   // 폴더 보기의 문서: 문서 트리와 같은 글·바뀜 점, 지금 보는 문서 강조
    const active = S.view?.type === 'doc' && S.view.path === f.path ? ' active' : '';
    return `<div ${rowAttrs(o, v, f.path, depth, ` file doc${active}`)} title="${esc(tipOf(f))}"><span class="caret-space"></span>`
      + `${fileIcon(f.name, f.kind)}<span class="label">${esc(labelOf(f))}</span>${subHtml(sub)}`
      + `${S.changed.has(f.path) ? '<span class="dot" title="열어 보기 전에 바뀜"></span>' : ''}</div>`;
  }
  const cur = S.view?.type === 'code' && S.view.path === f.path ? ' active' : '';   // 지금 보는 코드
  return `<div ${rowAttrs(o, v, f.path, depth, ` file${cur}`)} title="${esc(fileTip(f))}"><span class="caret-space"></span>${fileIcon(f.name)}`
    + `<span class="label">${esc(f.name)}</span>${subHtml(sub)}</div>`;
}

function nodesHtml(o, v, nodes, depth) {
  let html = '';
  for (const n of nodes) {
    if (n.type === 'file') {
      html += fileRow(o, v, n, depth);
      continue;
    }
    const open = v.open.has(n.path);
    const folder = v.sel === 'folder';
    const cur = folder && S.view?.type === 'overview' && S.view.path === n.path ? ' active' : '';
    const dot = folder && !open && hasChangedInside(n.path) ? '<span class="dot" title="안쪽 문서가 바뀜"></span>' : '';
    html += `<div ${rowAttrs(o, v, n.path, depth, ` dir${cur}`)} aria-expanded="${open}" title="${esc(n.path)}/">`
      + `<span class="caret${open ? ' open' : ''}" data-toggle aria-hidden="true"></span>${folderIcon()}<span class="label">${esc(n.name)}</span>${dot}</div>`;
    if (open) html += nodesHtml(o, v, n.children, depth + 1);
  }
  return html;
}

/** 종류별 보기의 파일·코드 목록 */
function kindHtml(o, k, v, terms) {
  if (terms) {
    const hits = [...filesIn(v.tree)].filter((f) => terms.every((t) => f.path.toLowerCase().includes(t)));
    return hits.length
      ? hits.slice(0, MAX_FILTER_RESULTS).map((f) => fileRow(o, v, f, 0, dirname(f.path))).join('')
      : `<p class="side-empty">${LISTS[k].noHit}</p>`;
  }
  return v.tree.length ? nodesHtml(o, v, v.tree, 0) : `<p class="side-empty">${LISTS[k].none}</p>`;
}

/** 폴더 보기: 맨 위 프로젝트 행(누르면 개요) + 문서와 파일을 합친 트리 */
function folderHtml(o, v, terms) {
  if (terms) {
    const docs = S.files.filter((f) => terms.every((t) => `${(f.title || '').toLowerCase()} ${f.path.toLowerCase()}`.includes(t)));
    const files = [...filesIn(o.data?.tree || [])].filter((f) => terms.every((t) => f.path.toLowerCase().includes(t)));
    const hits = [...docs.map((f) => ({ ...f, doc: true })), ...files];
    return hits.length
      ? hits.slice(0, MAX_FILTER_RESULTS).map((f) => fileRow(o, v, f, 0, dirname(f.path))).join('')
      : '<p class="side-empty">일치하는 문서나 파일이 없습니다</p>';
  }
  const root = S.view?.type === 'overview' && !S.view.path ? ' active' : '';
  return `<div ${rowAttrs(o, v, '', 0, ` dir root${root}`)} title="프로젝트 개요"><span class="label">${esc(S.name)}</span></div>`
    + (o.all.length ? nodesHtml(o, v, o.all, 0) : '<p class="side-empty">문서나 파일이 없습니다</p>');
}

/** 묶음 머리줄의 개수 */
function renderHead() {
  const o = state();
  const more = o?.data?.truncated ? '+' : '';
  $('#lec-docs-count').textContent = S.tab?.treeLoaded ? String(S.files.length) : '';
  $('#lec-others-count').textContent = o?.trees ? `${o.counts.files}${more}` : '';
  $('#lec-code-count').textContent = o?.trees ? `${o.counts.code}${more}` : '';
}

function renderList(k) {
  const o = state();
  const box = listEl(k);
  const folder = k === 'files' && folderView();
  if (!o || (folder ? !S.tab.treeLoaded : !o.data)) {   // 탭이 없거나 아직 읽는 중
    box.innerHTML = o?.error && !folder ? `<p class="side-empty">${esc(o.error)}</p>` : '';
    return;
  }
  if (folder) {
    o.folderOpen ??= new Set(S.open);   // 처음 폴더 보기로 볼 때 문서 트리에서 펼쳐 둔 폴더대로
    o.all = merge(S.tree, o.data?.tree);
    o.allIndex = indexOf(o.all);
  }
  const v = view(o, k);
  const query = $('#lec-filter').value.trim().toLowerCase();
  const terms = query ? query.split(/\s+/) : null;
  let html = folder ? folderHtml(o, v, terms) : kindHtml(o, k, v, terms);
  if (o.data?.truncated) html += `<p class="side-empty">파일이 많아 ${o.data.limit}개까지만 보입니다</p>`;
  keepFocus(box, () => { box.innerHTML = html; });
  // Tab 키로 목록에 들어올 행: 고른 행, 없으면 첫 행
  if (!box.querySelector('.row[tabindex="0"]')) box.querySelector('.row')?.setAttribute('tabindex', '0');
}

function render() {
  renderHead();
  renderList('files');
  if (!folderView()) renderList('code');
}

/**
 * 지금 보는 것이 목록에서 보이게: 상위 폴더를 펴고 그 행까지 스크롤 (문서 트리의 revealCurrent 처럼).
 * 폴더 보기는 문서·폴더·코드, 종류별 보기는 코드 화면일 때 '코드' 목록에서
 */
function revealCurrent() {
  const o = state();
  if (!o || !S.view) return;
  const code = S.view.type === 'code';
  if (!folderView() && !code) {
    render();   // 지금 보는 코드 강조를 지운다
    return;
  }
  const k = folderView() ? 'files' : 'code';
  if (folderView()) o.folderOpen ??= new Set(S.open);
  const set = view(o, k).open;
  const parts = S.view.path ? S.view.path.split('/') : [];
  const upto = S.view.type === 'overview' ? parts.length : parts.length - 1;
  for (let i = 1; i <= upto; i++) set.add(parts.slice(0, i).join('/'));
  render();
  listEl(k).querySelector('.row.active')?.scrollIntoView({ block: 'nearest' });
}

const isCodeFile = (n) => n?.type === 'file' && !n.doc && isCode(n.name);

// ---- 읽기 ---------------------------------------------------------------------

function load(tab, { fresh = false } = {}) {
  const o = tab.others;
  o.stale = false;
  o.loading = (async () => {
    try {
      const d = await getJSON(`/api/others?p=${encodeURIComponent(tab.id)}${fresh ? '&fresh=1' : ''}`);
      o.data = d;
      const code = (f) => isCode(f.name);
      o.trees = { files: pick(d.tree, (f) => !code(f)), code: pick(d.tree, code) };
      o.index = { files: indexOf(o.trees.files), code: indexOf(o.trees.code) };
      o.counts = { files: [...filesIn(o.trees.files)].length, code: [...filesIn(o.trees.code)].length };
      o.error = null;
      for (const k of Object.keys(LISTS)) for (const p of [...o.open[k]]) if (!o.index[k].has(p)) o.open[k].delete(p);
    } catch (e) {
      if (S.tabs.includes(tab)) o.error = `파일 목록을 읽지 못했습니다 (${e.message}). F5 를 누르면 다시 읽습니다.`;
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
  if (o && (shown('files') || shown('code')) && (o.stale || !o.data) && !o.loading) load(S.tab);
}

/** 탭의 파일·코드 목록을 (보이지 않아도) 받아 둔다 — 빠른 열기(palette.js)가 코드를 찾을 때 */
export function loadOthers(tab) {
  const o = tab?.others;
  if (!o) return Promise.resolve(null);
  if (o.data && !o.stale) return Promise.resolve(o);
  return (o.loading || load(tab)).then(() => o);
}

/** F5: 서버에서 새로 훑는다 (감시가 놓친 변경까지) */
export function refreshOthers() {
  const o = state();
  if (!o) return;
  o.stale = true;
  if ((shown('files') || shown('code')) && !o.loading) load(S.tab, { fresh: true });
}

// ---- 고르기·열기 ----------------------------------------------------------------

const rowOf = (k, path) => listEl(k).querySelector(`.row[data-path="${CSS.escape(path)}"]`);

function select(k, path, { focus = true } = {}) {
  const o = state();
  if (!o || path == null) return;
  o.selected[view(o, k).sel] = path;
  for (const r of $$('.row.selected', listEl(k))) {
    r.classList.remove('selected');
    r.setAttribute('aria-selected', 'false');
    r.tabIndex = -1;
  }
  const row = rowOf(k, path);
  if (!row) return;
  row.classList.add('selected');
  row.setAttribute('aria-selected', 'true');
  row.tabIndex = 0;
  if (focus) row.focus({ preventScroll: true });
  row.scrollIntoView({ block: 'nearest' });
}

function toggle(k, path, open) {
  const set = view(state(), k).open;
  const want = open ?? !set.has(path);
  if (want) set.add(path);
  else set.delete(path);
  renderList(k);
  select(k, path);
}

/** 두 번 누르기·Enter: 파일은 열고(문서는 뷰어에서) 폴더는 펼치거나 접는다. 폴더 보기의 프로젝트 행은 개요 */
function activate(k, path) {
  if (path === '' && k === 'files' && folderView()) {
    emit('open', { type: 'overview', path: '' });
    return;
  }
  const n = view(state(), k).index.get(path);
  if (!n) return;
  if (n.type === 'dir') toggle(k, path);
  else if (n.doc) emit('open', { type: 'doc', path });
  else openExternal(path);
}

/** Enter: 코드는 읽기 화면(한 번 누르기와 같게), 그 밖은 두 번 누르기와 같게 */
function enter(k, path) {
  if (isCodeFile(view(state(), k).index.get(path))) emit('open', { type: 'code', path });
  else activate(k, path);
}

async function copy(text) {
  toast(await copyText(text) ? `복사했습니다: ${text}` : '복사하지 못했습니다');
}

function menuItems(k, n) {
  if (n.doc) return [{ header: n.path }, ...pathMenuItems(n.path, true)];   // 문서 트리와 같은 메뉴
  const items = [];
  if (n.type === 'dir') {
    items.push({ header: `${n.path}/` },
      { label: view(state(), k).open.has(n.path) ? '접기' : '펼치기', hint: '두 번 누르기·Enter', action: () => toggle(k, n.path) });
    if (folderView() && S.dirs.has(n.path)) items.push({ label: '폴더 개요 보기', action: () => emit('open', { type: 'overview', path: n.path }) });
    items.push({ label: '탐색기에서 열기', action: () => openExternal(n.path) });
  } else {
    items.push({ header: `${n.name} · ${formatSize(n.size)} · ${formatDateTime(n.mtime)}` });
    if (isCodeFile(n)) {
      items.push({ label: '읽기 화면에서 보기', hint: '누르기·Enter', action: () => emit('open', { type: 'code', path: n.path }) },
        { label: '편집기로 열기', hint: '두 번 누르기', action: () => openExternal(n.path) });
    } else {
      items.push({ label: '열기', hint: `${OPEN_HINT[n.open] || ''} — 두 번 누르기·Enter`, action: () => openExternal(n.path) });
    }
    // 기본 앱으로 여는 형식(csv·txt 등)은 편집기로도. 읽을 수 없는 형식(실행 파일·압축 등)은 편집기로 열지 않는다
    if (n.open === 'default') items.push({ label: '편집기로 열기', action: () => openExternal(n.path, undefined, 'editor') });
    items.push({ label: '탐색기에서 보기', action: () => revealInExplorer(n.path) });
  }
  items.push('-', { label: `@${n.path} 복사`, hint: 'Claude Code 프롬프트에 붙여 넣기', action: () => copy(`@${n.path}`) },
    { label: '전체 경로 복사', action: () => copy(fullPath(n.path)) });
  if (n.type === 'file') items.push({ label: '파일 이름 복사', action: () => copy(n.name) });
  return items;
}

function openMenu(k, path, x, y) {
  const root = path === '' && k === 'files' && folderView();
  const n = root ? { type: 'dir', path: '', root: true } : view(state(), k).index.get(path);
  if (!n) return;
  select(k, path);
  showMenu(x, y, n.root ? [{ header: S.root }, ...pathMenuItems('', false)] : menuItems(k, n));
}

// 글자를 치면 그 글자로 시작하는 다음 행으로 (탐색기처럼). 잠깐 사이에 이어 치면 이어진 글자로
let typed = '';
let typedAt = 0;

function onKey(e) {
  const k = keyOf(e.currentTarget);
  const o = state();
  const all = $$('.row', listEl(k));
  if (!o || !all.length) return;
  const v = view(o, k);
  const cur = e.target.closest?.('.row') || rowOf(k, o.selected[v.sel] ?? '') || all[0];
  const i = all.indexOf(cur);
  const path = cur.dataset.path;
  const n = v.index.get(path);
  const go = (row) => row && select(k, row.dataset.path);
  if (e.key === 'ArrowDown') go(all[Math.min(all.length - 1, i + 1)]);
  else if (e.key === 'ArrowUp') go(all[Math.max(0, i - 1)]);
  else if (e.key === 'Home') go(all[0]);
  else if (e.key === 'End') go(all[all.length - 1]);
  else if (e.key === 'ArrowRight' && n?.type === 'dir') {
    if (!v.open.has(path)) toggle(k, path, true);
    else go(all[i + 1]);   // 펼쳐 있으면 첫 항목으로
  } else if (e.key === 'ArrowLeft') {
    if (n?.type === 'dir' && v.open.has(path)) toggle(k, path, false);
    else if (n?.parent && rowOf(k, n.parent)) select(k, n.parent);   // 거른 목록에서는 부모가 보이지 않아 그대로
  } else if (e.key === 'Enter') enter(k, path);
  else if (e.key === 'ContextMenu' || (e.key === 'F10' && e.shiftKey)) {
    const r = cur.getBoundingClientRect();
    openMenu(k, path, r.left + 24, r.bottom);
  } else if (e.key.length === 1 && e.key !== ' ' && !e.ctrlKey && !e.metaKey && !e.altKey) {
    const now = Date.now();
    typed = now - typedAt > 800 ? e.key.toLowerCase() : typed + e.key.toLowerCase();
    typedAt = now;
    // 같은 글자를 거듭 치면(탐색기처럼) 그 글자로 시작하는 다음 행, 다른 글자를 이어 치면 이어진 글자로 시작하는 행
    const same = [...typed].every((c) => c === typed[0]);
    const want = same ? typed[0] : typed;
    const from = same ? i + 1 : i;
    const order = [...all.slice(from), ...all.slice(0, from)];
    go(order.find((r) => r.querySelector('.label').textContent.toLowerCase().startsWith(want)));
  } else return;
  e.preventDefault();
  e.stopPropagation();   // 장 하이라이트의 ↑·↓ 등 앱 단축키로 가지 않게
}

// ---- 묶음·분리선·보기 -----------------------------------------------------------

function applyLayout() {
  const folder = folderView();
  $('#lec-files').classList.toggle('folder-view', folder);
  $('#lec-btn-view').classList.toggle('on', folder);
  listEl('files').setAttribute('aria-label', folder ? '문서와 파일 (폴더 구조)' : '파일');
  const grow = SECTIONS.find((s) => isOpen(s.visible));   // 펼친 첫 묶음이 남은 높이를 갖는다
  for (const s of SECTIONS) {
    const sec = $(s.el);
    const open = isOpen(s.visible);
    sec.classList.toggle('closed', !open);
    sec.classList.toggle('grow', s === grow);
    const head = sec.querySelector('.side-head');
    head.setAttribute('aria-expanded', String(open));
    head.querySelector('.caret').classList.toggle('open', open);
    if (!s.split) continue;
    $(s.split).hidden = !open || s === grow;   // 분리선은 높이를 정하는 묶음 위에만
    const h = Number(S.config[s.height]);
    if (h) sec.style.setProperty(s.css, `${Math.round(h)}px`);
    else sec.style.removeProperty(s.css);   // app.css 의 기본 높이
  }
}

/** 분리선을 끌어 그 아래 묶음의 높이를 바꾼다. 키운 만큼 남은 높이를 갖는 묶음이 줄어든다 */
function bindSplit(s) {
  const split = $(s.split);
  const root = document.documentElement;
  split.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    split.setPointerCapture(e.pointerId);
    const sec = $(s.el);
    const start = sec.getBoundingClientRect().height;
    const room = ($('#lec-files .side-sec.grow')?.getBoundingClientRect().height || MIN_HEIGHT) - MIN_HEIGHT;
    // 잡은 곳에서 움직인 만큼 (분리선을 잡는 순간 높이가 튀지 않게)
    const heightAt = (ev) => Math.round(Math.min(start + room, Math.max(MIN_HEIGHT, start + e.clientY - ev.clientY)));
    const move = (ev) => sec.style.setProperty(s.css, `${heightAt(ev)}px`);
    const up = (ev) => {
      split.removeEventListener('pointermove', move);
      split.removeEventListener('pointerup', up);
      root.classList.remove('resizing-rows');
      if (ev.clientY !== e.clientY) saveConfig({ [s.height]: heightAt(ev) });   // 누르기만 했으면(두 번 누르기 등) 저장하지 않는다
    };
    root.classList.add('resizing-rows');
    split.addEventListener('pointermove', move);
    split.addEventListener('pointerup', up);
  });
  split.addEventListener('dblclick', () => {
    saveConfig({ [s.height]: null });
    applyLayout();
  });
}

function bindLayout() {
  for (const s of SECTIONS) {
    $(s.el).querySelector('.side-head').addEventListener('click', async () => {
      await saveConfig({ [s.visible]: !isOpen(s.visible) });
      applyLayout();
      render();
      ensure();
    });
    if (s.split) bindSplit(s);
  }
  // 종류별 ↔ 폴더 구조
  $('#lec-btn-view').addEventListener('click', async () => {
    await saveConfig({ files_view: folderView() ? 'kind' : 'folder' });
    applyLayout();
    if (folderView()) revealCurrent();
    else render();
    ensure();
  });
}

function bindList(k) {
  const box = listEl(k);
  box.addEventListener('click', (e) => {
    const row = e.target.closest('.row');
    if (!row) return;
    const { path } = row.dataset;
    if (e.target.closest('[data-toggle]')) {
      toggle(k, path);
      return;
    }
    select(k, path);
    // 폴더 보기의 문서와 프로젝트 행은 문서 트리처럼 한 번 누르면 연다. 코드는 한 번 누르면 읽기 화면 (두 번 누르면 편집기)
    const n = view(state(), k).index.get(path);
    if (k === 'files' && folderView() && (path === '' || n?.doc)) activate(k, path);
    else if (isCodeFile(n)) emit('open', { type: 'code', path });
  });
  box.addEventListener('dblclick', (e) => {
    const row = e.target.closest('.row');
    if (!row || e.target.closest('[data-toggle]')) return;
    const { path } = row.dataset;
    if (k === 'files' && folderView() && (path === '' || view(state(), k).index.get(path)?.doc)) return;   // 한 번 누를 때 이미 열었다
    activate(k, path);
  });
  box.addEventListener('contextmenu', (e) => {
    const row = e.target.closest('.row');
    if (!row) return;
    e.preventDefault();
    openMenu(k, row.dataset.path, e.clientX, e.clientY);
  });
  box.addEventListener('keydown', onKey);
  box.addEventListener('scroll', () => { const o = state(); if (o) o.scroll[k] = box.scrollTop; }, { passive: true });
}

export function initOthers() {
  for (const k of Object.keys(LISTS)) bindList(k);
  bindLayout();
  applyLayout();
  $('#lec-filter').addEventListener('input', render);
  on('tab', () => {
    render();
    for (const k of Object.keys(LISTS)) listEl(k).scrollTop = state()?.scroll[k] || 0;
    ensure();
  });
  on('panel', ensure);   // 사이드바 '파일' 탭으로 돌아오면
  on('others', (tab) => { if (tab === S.tab) ensure(); });
  // 문서 개수, 그리고 폴더 보기는 문서 트리도 그린다: 트리·바뀜 점·지금 보는 문서가 바뀌면 다시
  on('tree', () => { if (folderView()) render(); else renderHead(); });
  on('changed', () => { if (folderView()) render(); });
  on('view', revealCurrent);
}
