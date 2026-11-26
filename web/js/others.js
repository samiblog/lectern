// 사이드바 '파일' 탭 (D36, D37, D42, D48, D169). 위에서부터 네 묶음:
// - '문서'(문서 트리, tree.js), '코드'(소스·스크립트·웹·설정 — icons.js 의 코드 종류), '자료'(문서도 코드도 아닌 파일 — 목록 이름은 files)는 종류로 나눈 것,
//   '폴더'(목록 이름 folder — D169)는 문서·파일·코드를 폴더 구조 그대로 한 트리에 (전에는 거르기 칸 옆 '폴더' 버튼이 세 묶음 대신 보이던 것 — D37).
//   코드·자료·폴더는 같은 모양의 탐색기 같은 목록이다. 한 번에 한 묶음만 펼치고(D143 — 설정 files_open, 프로젝트 탭마다 tab.side.filesOpen)
//   그것이 남은 높이를 모두 갖는다. 접힌 머리줄에도 개수(거르는 중이면 맞는 수)가 보인다 — '폴더'는 위 셋을 더한 수라 보이지 않는다.
//   Ctrl+Shift+E 는 펼친 묶음으로 초점, 그 안에서 다시 누르면 다음 묶음 (focusFiles — D169).
// - '폴더'의 문서 행은 문서 트리처럼 누르면 뷰어에서 열고(제목·바뀜 점·지금 보는 문서 강조 — 두 번 누르면 새 문서 탭, D67), 파일 행은 탐색기처럼.
//   펼쳐 있을 때만 그린다 (문서 트리 전체와 합치는 일이라).
//
// - 문서가 아닌 파일은 서버가 문서 트리와 따로 훑는다 (GET /api/others). 목록이 보일 때만 읽고, 파일이 생기거나 지워지면
//   (watch.js 의 'others') 다시 읽는다. 받은 트리를 화면이 파일·코드로 나눈다. '폴더'는 이것과 탭의 문서 트리(S.tree)를 합친다.
//   탭마다 받은 목록, 목록마다 펼친 폴더·고른 행·스크롤 위치를 남긴다 (tab.others).
// - 탐색기처럼: 누르면 고르고, 두 번 누르거나 Enter 면 연다 — 안전한 형식(PDF·오피스·그림·csv 등)은 기본 앱, 코드·글은 편집기,
//   실행·설치 파일과 압축 등은 탐색기에서 선택만 한다 (POST /api/open-external → osutil.open_path — 실행하지 않는다). 폴더는 펼치고 접는다.
//   ↑·↓·←·→·Home·End 와 글자 입력(그 글자로 시작하는 행)으로 옮겨 다니고, 우클릭·메뉴 키·Shift+F10 에 열기·편집기로 열기·
//   탐색기에서 보기·경로 복사. 보기 전용이라 이름 바꾸기·지우기·옮기기는 없다.
// - 코드(목록의 코드, 폴더 보기의 코드 파일)는 한 번 누르거나 Enter 면 본문에 읽기 전용으로 (codeview.js, D43), 두 번 누르면 편집기로.
//   보고 있는 코드는 목록에서 상위 폴더를 펴고 강조한다.
// - 사이드바 거르기(#lec-filter)는 이 목록들에도 적용된다: 거른 파일('폴더'는 문서도)을 평평하게 보인다.
// - 다른 사이드바 탭(최근 변경·검색의 이름·모아 보기의 파일 종류, D50)에 나온 파일 행도 여기 규칙을 따른다 (bindFileRows):
//   문서·코드는 한 번 누르면 열고, 자료는 두 번 누르거나 Enter, 우클릭은 이 목록과 같은 메뉴.
// - 제외 폴더(dist·build·node_modules 등, D49)는 '자료'와 '폴더'에 흐린 접힌 폴더로 나온다. 서버가 안을 훑지 않으므로
//   펼칠 때 한 단계씩 받아(GET /api/others/dir) 붙이고(tab.others.lazy), 접으면 버린다 — 다시 펼치면 새로 읽는다.
//   안의 파일은 종류를 나누지 않고 모두 '자료'에 두고, 개수·거르기에는 넣지 않는다.

import { S, emit, on } from './store.js';
import { getJSON, postJSON, saveConfig, openExternal, revealInExplorer } from './api.js';
import { loadMarks, fullPath, labelOf, tipOf, telling, tellHtml, docMenuItems, newFolderItem, newFileItem, renameItem, hasChangedInside, shellWord, workCardItem, switchPanel, sendRowKey, fileTip } from './tree.js';
import { fileIcon, folderIcon, isCode, isViewable } from './icons.js';
import { showMenu, menuGroups } from './ui.js';
import { html, setHtml } from './html.js';
import { $, $$, dirname, formatDateTime, formatSize, copyText, toast, keepFocus, natCompare, openHow, repeatClick, middleClickOpens, blockedReadOnly, isMd, isHtml } from './util.js';
import { t } from './i18n.js';
import { aiCli } from './aitool.js';
import { sideOrder } from './sideorder.js';

const MAX_FILTER_RESULTS = 300;
const OPEN_HINT = { default: t('기본 앱으로'), editor: t('편집기로'), reveal: t('탐색기에서 선택만 (실행하지 않음)') };

// 목록 셋: 자료(files), 코드, 폴더(folder — 문서·파일·코드를 합친 트리, D169)
const LISTS = {
  files: { el: '#lec-others-list', none: t('문서나 코드가 아닌 파일이 없습니다'), noHit: t('일치하는 자료가 없습니다'), section: 'others' },
  code: { el: '#lec-code-list', none: t('코드 파일이 없습니다'), noHit: t('일치하는 코드가 없습니다'), section: 'code' },
  folder: { el: '#lec-folder-list', none: t('문서나 파일이 없습니다'), noHit: t('일치하는 문서나 파일이 없습니다'), section: 'folder' },
};
// 묶음 넷 (위에서부터 — index.html 의 순서와 같게). 한 번에 하나만 펼친다 (D143). list: 그 묶음의 목록 (문서는 tree.js 의 #lec-tree)
const SECTIONS = [{ name: 'docs', el: '#lec-docs', list: '#lec-tree' }, { name: 'code', el: '#lec-code', list: '#lec-code-list' },
  { name: 'others', el: '#lec-others', list: '#lec-others-list' }, { name: 'work', el: '#lec-work', list: '#lec-work-list' },   // 작업 — 업무 카드·형광펜·할 일 (D204, tree.js)
  { name: 'folder', el: '#lec-folder', list: '#lec-folder-list' }];

const listEl = (k) => $(LISTS[k].el);
const keyOf = (el) => el?.closest?.('[data-list]')?.dataset.list || 'files';
const state = () => S.tab?.others || null;
/** 펼친 묶음 — docs·code·others·folder (프로젝트 탭마다, 처음은 마지막에 고른 것) */
export function openSection() {
  const v = S.tab?.side?.filesOpen ?? S.config.files_open;
  return SECTIONS.some((s) => s.name === v) ? v : 'docs';
}
const filesShown = () => !!S.tab && !$('#lec-files').hidden;
const folderShown = () => openSection() === 'folder';
export { fileTip };

/** 경로 → 노드 (부모 경로를 parent 로 단다 — ← 로 부모에 갈 때). 아직 읽지 않은 제외 폴더는 children 이 null */
function indexOf(nodes, parent = null, map = new Map()) {
  for (const n of nodes) {
    map.set(n.path, { ...n, parent });
    if (n.type === 'dir' && n.children) indexOf(n.children, n.path, map);
  }
  return map;
}

/** 트리의 파일 (제외 폴더 안은 세지도 거르지도 않는다) */
function* filesIn(nodes) {
  for (const n of nodes) {
    if (n.type === 'file') yield n;
    else if (!n.excluded) yield* filesIn(n.children);
  }
}

/** keep 에 맞는 파일만 남긴 트리 (빈 폴더는 뺀다). 제외 폴더는 excluded 가 참일 때만 그대로 (안은 종류를 나누지 않는다) */
function pick(nodes, keep, excluded = false) {
  const out = [];
  for (const n of nodes) {
    if (n.type === 'file') {
      if (keep(n)) out.push(n);
      continue;
    }
    if (n.excluded) {
      if (excluded) out.push(n);
      continue;
    }
    const children = pick(n.children, keep, excluded);
    if (children.length) out.push({ ...n, children });
  }
  return out;
}

/** 서버 트리에 펼쳐서 읽어 둔 제외 폴더의 안(o.lazy)을 붙인 복사본 */
function withLazy(o, nodes) {
  return nodes.map((n) => {
    if (n.type !== 'dir') return n;
    const got = n.excluded ? o.lazy.get(n.path) : null;
    const children = got ? got.nodes : n.children;
    return children ? { ...n, children: withLazy(o, children), truncated: got?.truncated, limit: got?.limit, error: got?.error } : n;
  });
}

/** 받은 트리(o.data)와 읽어 둔 제외 폴더로 목록의 트리·색인을 만든다 */
function build(o) {
  const code = (f) => isCode(f.name);
  o.tree = withLazy(o, o.data.tree);
  o.trees = { files: pick(o.tree, (f) => !code(f), true), code: pick(o.tree, code) };
  o.index = { files: indexOf(o.trees.files), code: indexOf(o.trees.code) };
}

const byName = (a, b) => natCompare(a.name, b.name);

/** '폴더' 묶음: 문서 트리와 문서 외 파일 트리를 폴더마다 합친다. 문서 노드에는 doc: true. 폴더 먼저, 자연 정렬 */
function merge(docs = [], others = []) {
  const dirs = new Map();
  const files = [];
  for (const [nodes, doc] of /** @type {[any[], boolean][]} */ ([[docs, true], [others, false]])) {
    for (const n of nodes) {
      if (n.type === 'file') {
        files.push({ ...n, doc });
        continue;
      }
      if (n.excluded) {   // 제외 폴더 (문서 트리에는 없다)
        dirs.set(n.path, n);
        continue;
      }
      const d = dirs.get(n.path) || { type: 'dir', name: n.name, path: n.path, docs: [], others: [] };
      d[doc ? 'docs' : 'others'] = n.children;
      dirs.set(n.path, d);
    }
  }
  const merged = [...dirs.values()].map((d) => (d.excluded ? d : { type: 'dir', name: d.name, path: d.path, children: merge(d.docs, d.others) }));
  return [...merged.sort(byName), ...files.sort(byName)];
}

/** 숨김·링크 항목과 빈 폴더(평평한 목록 — /api/others/hidden)를 합친 트리에 끼운다. 그 폴더가 트리에 없으면(숨긴 것만 든 폴더) 만든다 (D203) */
function addHidden(nodes, hidden) {
  if (!hidden?.length) return nodes;
  const top = [...nodes];
  const dirs = new Map();   // 경로 → 복사한 폴더 노드
  const childrenOf = (dir) => {
    if (!dir) return top;
    let d = dirs.get(dir);
    if (!d) {
      const list = childrenOf(dirname(dir));
      const i = list.findIndex((n) => n.type === 'dir' && n.path === dir);
      d = i >= 0 ? { ...list[i], children: list[i].children ? [...list[i].children] : [] } : { type: 'dir', name: dir.slice(dir.lastIndexOf('/') + 1), path: dir, children: [] };
      if (i >= 0) list[i] = d;
      else list.push(d);
      dirs.set(dir, d);
    }
    return d.children;
  };
  for (const h of hidden) {
    const list = childrenOf(dirname(h.path));
    if (!list.some((n) => n.path === h.path)) list.push(h);
  }
  return top;
}

/** '폴더' 묶음에서 펼쳐 읽은 폴더(숨긴 폴더·제외 폴더 — o.lazyAll)의 안을 붙인다. 붙인 폴더에는 lazy */
function withAll(o, nodes) {
  return nodes.map((n) => {
    if (n.type !== 'dir') return n;
    const got = n.children ? null : o.lazyAll.get(n.path);
    const children = got ? got.nodes : n.children;
    return children ? { ...n, children: withAll(o, children), lazy: !!got || n.lazy, truncated: got?.truncated, limit: got?.limit, error: got?.error } : n;
  });
}

/** 숨긴 파일의 경로 — 코드 화면·열기가 서버에 hidden 을 함께 보낸다 (api.hiddenFile) */
function noteHidden(o) {
  o.hiddenSet = new Set();
  const add = (n) => { if (n.hidden) o.hiddenSet.add(n.path); };
  for (const n of o.hidden || []) add(n);
  for (const got of o.lazyAll.values()) for (const n of got.nodes) add(n);
}

/** '폴더' 묶음의 트리를 지금의 문서 트리와 받은 파일로 다시 합친다 (처음 볼 때는 문서 트리에서 펼쳐 둔 폴더대로).
 * 숨김·링크·빈 폴더까지 모두 (D203) — 제외 폴더·숨긴 폴더는 펼칠 때 안을 읽는다 */
function buildAll(o) {
  o.folderOpen ??= new Set(S.open);
  o.all = withAll(o, addHidden(merge(S.tree, o.data?.tree || []), o.hidden));
  o.allIndex = indexOf(o.all);
}

// ---- 그리기 -------------------------------------------------------------------

/** 목록 k 의 지금 모양: {tree, index(경로 → 노드), open(펼친 폴더), sel(고른 행을 기억하는 이름)} */
function view(o, k) {
  if (k === 'folder') return { tree: o.all || [], index: o.allIndex || new Map(), open: o.folderOpen || new Set(), sel: 'folder' };
  return { tree: o.trees?.[k] || [], index: o.index?.[k] || new Map(), open: o.open[k], sel: k };
}

function rowAttrs(o, v, path, depth, extra = '') {
  const sel = path === o.selected[v.sel];
  const picked = v.sel === 'folder' && o.picked.has(path) ? ' picked' : '';   // 여럿 고른 행 (D203 — Ctrl·Shift+누르기)
  return [html`class="row${extra}${sel ? ' selected' : ''}${picked}" role="treeitem" aria-selected="${sel || !!picked}" data-path="${path}"`, html` style="--d:${depth}" tabindex="${sel ? 0 : -1}"`];
}

const subHtml = (sub) => (sub ? html`<span class="sub">${sub}</span>` : '');

function fileRow(o, v, f, depth, sub = '', tell = '') {
  if (f.doc) {   // '폴더' 묶음의 문서: 문서 트리와 같은 글·바뀜 점, 지금 보는 문서 강조. 같은 제목이면 파일 이름을 흐리게 (D179)
    const active = S.view?.type === 'doc' && S.view.path === f.path ? ' active' : '';
    return [html`<div ${rowAttrs(o, v, f.path, depth, ` file doc${active}`)} title="${tipOf(f)}"><span class="caret-space"></span>`, html`${fileIcon(f.name, f.kind, f.deck)}<span class="label">${labelOf(f)}${tellHtml(tell)}</span>${subHtml(sub)}`, html`${S.changed.has(f.path) ? html`<span class="dot" title="${t('열어 보기 전에 바뀜')}"></span>` : ''}</div>`];
  }
  const cur = S.view?.type === 'code' && S.view.path === f.path ? ' active' : '';   // 지금 보는 코드
  const marks = `${f.excluded ? ' excluded' : ''}${f.hidden ? ' hidden' : ''}${f.link ? ' link' : ''}`;   // 숨김·링크는 '폴더' 묶음에만 (D203)
  const tip = f.link ? `${f.path}\n${t('바로가기 폴더 — 따라가지 않습니다')}` : f.hidden ? `${fileTip(f)}\n${t('숨긴 파일 — 보기만')}` : fileTip(f);
  return [html`<div ${rowAttrs(o, v, f.path, depth, ` file${cur}${marks}`)} title="${tip}"><span class="caret-space"></span>${f.link ? html`<span class="link-mark" aria-hidden="true">↪</span>` : fileIcon(f.name)}`, html`<span class="label">${f.name}</span>${subHtml(sub)}</div>`];
}

/** 목록 안의 안내 줄 (제외 폴더를 읽는 중 등) — 그 깊이의 행 글자에 맞춰 들인다 */
const noteHtml = (depth, text) => html`<p class="side-note" style="--d:${depth}">${text}</p>`;

function nodesHtml(o, v, nodes, depth, inside = false) {
  const markup = [];
  const tell = telling(nodes.filter((n) => n.doc), { folders: true });   // 같은 폴더의 같은 제목 (D179)
  for (const n of sideOrder(nodes)) {
    if (n.type === 'file') {
      markup.push(fileRow(o, v, n, depth, '', n.doc ? tell(n) : ''));
      continue;
    }
    const open = v.open.has(n.path);
    const folder = v.sel === 'folder';
    const cur = folder && S.view?.type === 'overview' && S.view.path === n.path ? ' active' : '';
    const dot = folder && !open && hasChangedInside(n.path) ? html`<span class="dot" title="${t('안쪽 문서가 바뀜')}"></span>` : '';
    const tip = n.hidden ? `${n.path}/\n${t('숨긴 폴더 — 펼칠 때 안을 읽습니다. 안의 파일은 보기만 합니다.')}`
      : n.excluded && !inside ? `${n.path}/\n${t('제외 폴더 — 펼칠 때 안을 읽습니다. 문서 트리와 검색에는 나오지 않습니다.')}` : `${n.path}/`;
    markup.push([html`<div ${rowAttrs(o, v, n.path, depth, ` dir${cur}${n.excluded ? ' excluded' : ''}${n.hidden ? ' hidden' : ''}`)} aria-expanded="${open}" title="${tip}">`, html`<span class="caret${open ? ' open' : ''}" data-toggle aria-hidden="true"></span>${folderIcon()}<span class="label">${n.name}</span>${dot}</div>`]);
    if (!open) continue;
    if (!n.children) {   // 아직 읽지 않은 제외 폴더 ('폴더' 묶음은 숨긴 폴더도 — 모두 읽는다, D203)
      markup.push(noteHtml(depth + 1, t('읽는 중…')));
      const tab = S.tab;
      queueMicrotask(() => loadDir(tab, n.path, v.sel === 'folder'));
    } else if (n.error) markup.push(noteHtml(depth + 1, t('이 폴더를 읽지 못했습니다 ({error})', { error: n.error })));
    else if ((n.excluded || v.sel === 'folder') && !n.children.length) markup.push(noteHtml(depth + 1, t('빈 폴더')));
    else {
      markup.push(nodesHtml(o, v, n.children, depth + 1, inside || n.excluded));
      if (n.truncated) markup.push(noteHtml(depth + 1, t('항목이 많아 {n}개까지만 보입니다', { n: n.limit })));
    }
  }
  return markup;
}

/** 종류별 보기의 파일·코드 목록 */
function kindHtml(o, k, v, terms) {
  if (terms) {
    const hits = [...filesIn(v.tree)].filter((f) => terms.every((w) => f.path.toLowerCase().includes(w)));
    return hits.length
      ? hits.slice(0, MAX_FILTER_RESULTS).map((f) => fileRow(o, v, f, 0, dirname(f.path)))
      : html`<p class="side-empty">${LISTS[k].noHit}</p>`;
  }
  return v.tree.length ? nodesHtml(o, v, v.tree, 0) : html`<p class="side-empty">${LISTS[k].none}</p>`;
}

/** '폴더' 묶음: 문서와 파일을 합친 트리 */
function folderHtml(o, v, terms) {
  if (terms) {
    const docs = S.files.filter((f) => terms.every((w) => `${(f.title || '').toLowerCase()} ${f.path.toLowerCase()}`.includes(w)));
    const files = [...filesIn(o.tree || []), ...(o.hidden || []).filter((n) => n.type === 'file')].filter((f) => terms.every((w) => f.path.toLowerCase().includes(w)));
    const hits = [...docs.map((f) => ({ ...f, doc: true })), ...files];
    const shown = hits.slice(0, MAX_FILTER_RESULTS);
    const tell = telling(shown.filter((f) => f.doc), { folders: true });
    return shown.length
      ? shown.map((f) => fileRow(o, v, f, 0, dirname(f.path), f.doc ? tell(f) : ''))
      : html`<p class="side-empty">${t('일치하는 문서나 파일이 없습니다')}</p>`;
  }
  return o.all.length ? nodesHtml(o, v, o.all, 0) : html`<p class="side-empty">${t('문서나 파일이 없습니다')}</p>`;
}

/** 묶음 머리줄의 개수 — 거르는 중이면 맞는 수 (접힌 묶음에서도 어디에 있는지 보이게, D143) */
function renderHead() {
  const o = state();
  const more = o?.data?.truncated ? '+' : '';
  const query = $('#lec-filter').value.trim().toLowerCase();
  const terms = query ? query.split(/\s+/) : null;
  const hit = (hay) => !terms || terms.every((w) => hay.includes(w));
  $('#lec-docs-count').textContent = S.tab?.treeLoaded ? String(terms ? S.files.filter((f) => hit(`${(f.title || '').toLowerCase()} ${f.path.toLowerCase()}`)).length : S.files.length) : '';
  for (const [k, id] of [['files', '#lec-others-count'], ['code', '#lec-code-count']]) {
    if (!o?.trees) $(id).textContent = '';
    else $(id).textContent = terms ? String([...filesIn(o.trees[k])].filter((f) => hit(f.path.toLowerCase())).length) : `${o.counts[k]}${more}`;
  }
}

function renderList(k) {
  const o = state();
  const box = listEl(k);
  const folder = k === 'folder';
  if (!o || (folder ? !S.tab.treeLoaded : !o.data)) {   // 탭이 없거나 아직 읽는 중
    setHtml(box, o?.error && !folder ? html`<p class="side-empty">${o.error}</p>` : '');
    return;
  }
  if (folder) buildAll(o);
  const v = view(o, k);
  const query = $('#lec-filter').value.trim().toLowerCase();
  const terms = query ? query.split(/\s+/) : null;
  const markup = [folder ? folderHtml(o, v, terms) : kindHtml(o, k, v, terms)];
  if (o.data?.truncated) markup.push(html`<p class="side-empty">${t('파일이 많아 {n}개까지만 보입니다', { n: o.data.limit })}</p>`);
  keepFocus(box, () => { setHtml(box, markup); });
  // Tab 키로 목록에 들어올 행: 고른 행, 없으면 첫 행
  if (!box.querySelector('.row[tabindex="0"]')) box.querySelector('.row')?.setAttribute('tabindex', '0');
}

function render() {
  renderHead();
  renderList('files');
  renderList('code');
  if (folderShown()) renderList('folder');   // 문서 트리 전체와 합치므로 펼쳐 있을 때만
}

/**
 * 지금 보는 것이 목록에서 보이게: 상위 폴더를 펴고 그 행까지 스크롤 (문서 트리의 revealCurrent 처럼).
 * '폴더' 묶음을 펼쳤으면 문서·폴더·코드, 아니면 코드 화면일 때 '코드' 목록에서
 */
function revealCurrent() {
  const o = state();
  if (!o || !S.view) return;
  const folder = folderShown();
  const code = S.view.type === 'code';
  if (!folder && !code) {
    render();   // 지금 보는 코드 강조를 지운다
    return;
  }
  const k = folder ? 'folder' : 'code';
  if (folder) o.folderOpen ??= new Set(S.open);
  const set = view(o, k).open;
  const parts = S.view.path ? S.view.path.split('/') : [];
  const upto = S.view.type === 'overview' ? parts.length : parts.length - 1;
  for (let i = 1; i <= upto; i++) set.add(parts.slice(0, i).join('/'));
  render();
  listEl(k).querySelector('.row.active')?.scrollIntoView({ block: 'nearest' });
}

// 코드 화면에서 보는 파일 — 코드와 csv·tsv·txt·log (D60), 엑셀 xlsx·xlsm (D77). 한 번 누르면 Lectern 에서, 두 번 누르면 편집기·기본 앱
// '폴더' 묶음의 숨긴 파일은 글로 된 것이면 글 그대로 본다 (D203 — 보기만): .env·.gitignore 처럼 확장자가 없는 것, md·html 도.
// 기본 앱으로 여는 형식(그림·오피스 등)과 실행·압축 파일은 두 번 누르기로
const isViewFile = (n) => n?.type === 'file' && !n.doc && !n.link && (isViewable(n.name) || (!!n.hidden && (n.open === 'editor' || isMd(n.name) || isHtml(n.name))));

// ---- 읽기 ---------------------------------------------------------------------

/** 펼쳐 둔 폴더 경로를 남길지: 목록에 있거나, 제외 폴더 안이라 아직 읽지 않았을 뿐인 것 (다시 읽으면 그대로 펼친다) */
function stillThere(index, path) {
  if (index.has(path)) return true;
  const parts = path.split('/');
  return parts.some((_, i) => index.get(parts.slice(0, i + 1).join('/'))?.excluded);
}

function load(tab, { fresh = false } = {}) {
  const o = tab.others;
  o.stale = false;
  if (fresh) o.lazy.clear();   // F5: 펼쳐 둔 제외 폴더도 새로 읽는다
  o.loading = (async () => {
    try {
      const d = await getJSON(`/api/others?p=${encodeURIComponent(tab.id)}${fresh ? '&fresh=1' : ''}`);
      o.data = d;
      build(o);
      o.counts = { files: [...filesIn(o.trees.files)].length, code: [...filesIn(o.trees.code)].length };
      o.error = null;
      for (const k of ['files', 'code']) for (const p of [...o.open[k]]) if (!stillThere(o.index[k], p)) o.open[k].delete(p);
    } catch (e) {
      if (S.tabs.includes(tab)) o.error = t('파일 목록을 읽지 못했습니다 ({error}). F5 를 누르면 다시 읽습니다.', { error: e.message });
    } finally {
      o.loading = null;
    }
    if (tab === S.tab) render();
    emit('others-read', tab);   // '문서' 묶음의 오피스 하위 묶음 (tree.js — D202)
    if (o.stale) ensure();   // 읽는 동안 또 바뀌었다
  })();
  return o.loading;
}

/** 제외 폴더 하나의 안(한 단계)을 받아 붙인다 — 그 폴더를 펼쳤을 때 (nodesHtml). all: '폴더' 묶음 — 숨긴 폴더도, 숨김·링크까지 (D203) */
async function loadDir(tab, path, all = false) {
  const o = tab.others;
  const store = all ? o.lazyAll : o.lazy;
  const key = all ? `all:${path}` : path;
  if (o.loadingDirs.has(key) || store.has(path) || (!all && !o.data)) return;
  o.loadingDirs.add(key);
  try {
    const d = await getJSON(`/api/others/dir?p=${encodeURIComponent(tab.id)}&path=${encodeURIComponent(path)}${all ? '&all=1' : ''}`);
    store.set(path, { nodes: d.nodes, truncated: d.truncated, limit: d.limit });
  } catch (e) {
    store.set(path, { nodes: [], error: e.message });   // 접었다 펼치면 다시 읽는다
  } finally {
    o.loadingDirs.delete(key);
  }
  if (all) noteHidden(o);
  else if (o.data) build(o);
  if (tab === S.tab) render();
}

/** '폴더' 묶음의 숨김·링크 항목과 빈 폴더를 받는다 (D203) — 그 묶음을 펼칠 때·F5·붙여 넣은 뒤. 감시는 숨긴 것의 변화를 알리지 않는다 */
function loadHidden(tab) {
  const o = tab.others;
  if (o.hiddenLoading) return o.hiddenLoading;
  o.hiddenStale = false;
  o.hiddenLoading = getJSON(`/api/others/hidden?p=${encodeURIComponent(tab.id)}`)
    .then((d) => { o.hidden = d.nodes; })
    .catch(() => { o.hidden ||= []; })
    .finally(() => {
      o.hiddenLoading = null;
      noteHidden(o);
      if (tab === S.tab && folderShown()) renderList('folder');
      if (o.hiddenStale) ensure();
    });
  return o.hiddenLoading;
}

/** 제외 폴더를 접으면 읽어 둔 안(그 아래 폴더들 것까지)을 버린다 — 다시 펼치면 새로 읽는다. all: '폴더' 묶음의 것 */
function forgetDir(o, path, all = false) {
  const store = all ? o.lazyAll : o.lazy;
  const before = store.size;
  for (const p of [...store.keys()]) if (p === path || p.startsWith(`${path}/`)) store.delete(p);
  if (store.size !== before && !all) build(o);
}

/** 폴더 모두 펼치기·접기 (D125 — 사이드바 '펼침', 문서 트리는 tree.js). 제외 폴더는 펼치지 않는다 — 펼치면 안을 읽는다 (D49).
 * 접을 때는 읽어 둔 제외 폴더의 안도 버린다. mode: all | none | first */
function setAllOpen(mode) {
  const o = state();
  if (!o) return;
  for (const k of Object.keys(LISTS)) {
    if (k === 'folder') {
      if (!S.tab?.treeLoaded) continue;
      buildAll(o);   // 아직 펼쳐 보지 않았어도 — 펼치면 이대로
    }
    const v = view(o, k);
    if (mode !== 'all') {
      for (const p of [...v.open]) if (v.index.get(p)?.excluded) forgetDir(o, p);
      v.open.clear();
    }
    if (mode === 'none') continue;
    const walk = (nodes) => {
      for (const n of nodes) {
        if (n.type !== 'dir' || n.excluded || n.hidden || !n.children) continue;   // 숨긴 폴더도 펼치지 않는다 — 펼치면 안을 읽는다 (D203)
        v.open.add(n.path);
        if (mode === 'all' && n.children) walk(n.children);
      }
    };
    walk(v.tree);
  }
  render();
}

/** 목록이 보이는데 아직 받지 않았거나 그 뒤로 파일이 바뀌었으면 읽는다 */
/** '파일' 탭이 보이면 코드·자료 목록을 받아 둔다 — 접힌 묶음의 머리줄에도 개수가 보이게 */
function ensure() {
  const o = state();
  if (o && filesShown() && (o.stale || !o.data) && !o.loading) load(S.tab);
  if (o && filesShown() && folderShown() && (o.hiddenStale || !o.hidden) && !o.hiddenLoading) loadHidden(S.tab);   // D203
}

/** 받아 둔 문서 외 파일 노드 (제외 폴더 안은 빼고) — 검색의 이름·모아 보기의 파일 종류 (loadOthers 뒤에) */
export const otherFiles = (tab) => [...filesIn(tab?.others.data?.tree || [])];

/** 탭의 파일·코드 목록을 (보이지 않아도) 받아 둔다 — 빠른 열기(palette.js)·검색·모아 보기가 쓸 때 */
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
  o.hiddenStale = true;
  o.lazyAll.clear();   // '폴더' 묶음에서 펼쳐 읽은 폴더도 새로
  if (filesShown() && folderShown() && !o.hiddenLoading) loadHidden(S.tab);
  if (filesShown() && !o.loading) load(S.tab, { fresh: true });
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
  const o = state();
  const v = view(o, k);
  const want = open ?? !v.open.has(path);
  if (want) v.open.add(path);
  else {
    v.open.delete(path);
    const n = v.index.get(path);
    if (k === 'folder' ? n?.lazy : n?.excluded) forgetDir(o, path, k === 'folder');
  }
  renderList(k);
  select(k, path);
}

/** 두 번 누르기·Enter: 파일은 열고(문서는 뷰어에서) 폴더는 펼치거나 접는다.
 * how: 문서를 열 곳 (util.openHow, D91) */
function activate(k, path, how = {}) {
  const n = view(state(), k).index.get(path);
  if (!n) return;
  if (n.link) toast(t('바로가기 폴더는 따라가지 않습니다 — 탐색기에서 여세요'));   // D203
  else if (n.type === 'dir') toggle(k, path);
  else if (n.doc) emit('open', { type: 'doc', path, ...how });
  else openExternal(path);
}

/** Enter: 코드·csv·txt 는 읽기 화면(한 번 누르기와 같게), 그 밖은 두 번 누르기와 같게 */
function enter(k, path, how) {
  if (isViewFile(view(state(), k).index.get(path))) emit('open', { type: 'code', path, ...how });
  else activate(k, path, how);
}

async function copy(text) {
  toast(await copyText(text) ? t('복사했습니다: {what}', { what: text }) : t('복사하지 못했습니다'));
}

/** 경로 복사 항목 */
function copyItems(n) {
  /** @type {MenuItem[]} */
  const items = [{ label: t('@{path} 복사', { path: n.path }), tip: t('{cli} 프롬프트에 붙여 넣기', { cli: aiCli() }), action: () => copy(`@${n.path}`), term: `@${n.path} ` },
    { label: t('전체 경로 복사'), action: () => copy(fullPath(n.path)), term: shellWord(fullPath(n.path)) }];
  if (n.type === 'file') items.push({ label: t('파일 이름 복사'), action: () => copy(n.name), term: shellWord(n.name) });
  return items;
}

/** 코드·자료 파일의 우클릭 메뉴 — 이 목록과 다른 탭의 파일 행(bindFileRows)이 함께 쓴다 */
export function fileMenuItems(n) {
  /** @type {MenuItem[]} */
  const views = [];
  /** @type {MenuItem[]} */
  const opens = [];
  if (isViewFile(n)) {
    views.push({ label: t('새 문서 탭에서 열기'), hint: t('누르기'), action: () => emit('open', { type: 'code', path: n.path, newTab: true, force: true }) },
      { label: t('지금 탭에서 열기'), hint: t('Alt+누르기'), action: () => emit('open', { type: 'code', path: n.path }) });
    opens.push(isCode(n.name) ? { label: t('외부 편집기로 열기'), hint: t('두 번 누르기'), action: () => openExternal(n.path) }
      : { label: t('열기'), hint: t('두 번 누르기'), tip: OPEN_HINT[n.open] || '', action: () => openExternal(n.path) });
  } else {
    opens.push({ label: t('열기'), hint: t('두 번 누르기'), tip: OPEN_HINT[n.open] || '', action: () => openExternal(n.path) });
  }
  // 기본 앱으로 여는 형식(csv·txt 등)은 편집기로도. 읽을 수 없는 형식(실행 파일·압축 등)은 편집기로 열지 않는다
  if (n.open === 'default') opens.push({ label: t('외부 편집기로 열기'), action: () => openExternal(n.path, undefined, 'editor') });
  opens.push({ label: t('탐색기에서 보기'), action: () => revealInExplorer(n.path) });
  // 이름 바꾸기 (D66 — 제외 폴더 안은 하지 않는다)
  return menuGroups([{ header: `${n.name} · ${formatSize(n.size)} · ${formatDateTime(n.mtime)}` }], views, copyItems(n), opens, n.excluded ? [] : [renameItem(n.path)]);
}

/** '폴더' 묶음의 복사·붙여 넣기 (D203) — 다른 묶음에는 없다 */
function clipItems(k, n) {
  if (k !== 'folder') return [];
  const n2 = state()?.picked.size > 1 && state().picked.has(n.path) ? state().picked.size : 1;
  /** @type {MenuItem[]} */
  const items = [{ label: n2 > 1 ? t('{n}개 복사', { n: n2 }) : t('복사'), hint: 'Ctrl+C', tip: t('탐색기에서도 붙여 넣을 수 있습니다'), action: () => copyFiles(n.path) }];
  if (S.tab && !S.tab.readonly) items.push({ label: t('붙여 넣기'), hint: 'Ctrl+V', tip: n.type === 'dir' ? t('이 폴더 안에 — 탐색기에서 복사한 것도') : t('이 파일의 폴더에 — 탐색기에서 복사한 것도'), action: () => pasteFiles(n.type === 'dir' ? n.path : dirname(n.path)) });
  return items;
}

/** '폴더' 묶음의 새로 만들기 (D203 — 문서·코드·자료·폴더 모두) */
const newAnyItem = (dir) => ({ label: t('새로 만들기…'), tip: t('문서·코드·자료 파일'), action: () => emit('new-doc', { dir, section: 'folder' }) });

function menuItems(k, n) {
  if (n.doc) return k === 'folder' ? menuGroups(docMenuItems(n.path), clipItems(k, n)) : docMenuItems(n.path);   // 문서 트리와 같은 메뉴
  if (n.link) return menuGroups([{ header: `${n.path} · ${t('바로가기 폴더 — 따라가지 않습니다')}` }], copyItems(n), [{ label: t('탐색기에서 보기'), action: () => revealInExplorer(dirname(n.path)) }]);
  if (n.type !== 'dir') return k === 'folder' ? menuGroups(fileMenuItems(n), clipItems(k, n)) : fileMenuItems(n);
  const top = n.excluded && !view(state(), k).index.get(n.parent)?.excluded;   // 제외 폴더 자체 (그 안의 폴더가 아니라)
  /** @type {MenuItem[]} */
  const items = [{ label: view(state(), k).open.has(n.path) ? t('접기') : t('펼치기'), hint: 'Enter', action: () => toggle(k, n.path) }];
  if (k === 'folder' && S.dirs.has(n.path)) items.push({ label: t('폴더 개요 보기'), action: () => emit('open', { type: 'overview', path: n.path }) });
  // 새로 만들기 (D65·D177) — 그 묶음의 것만, 폴더는 '폴더' 묶음에서만 (D203). 제외 폴더·숨긴 폴더 안은 트리에 보이지 않아 만들지 않는다
  if (!n.excluded && !n.hidden) items.push(...(k === 'code' ? [newFileItem(n.path, 'code')] : k === 'files' ? [newFileItem(n.path, 'data')]
    : [newAnyItem(n.path), newFolderItem(n.path), ...(S.tab && !S.tab.readonly ? [workCardItem(n.path)] : [])]));   // 업무 카드 (D152 — 문서가 없는 폴더는 문서 트리에 없다)   // 새로 만들기 (D65 — 제외 폴더 안은 트리에 보이지 않아 만들지 않는다)
  /** @type {MenuItem[]} */
  const opens = [{ label: t('탐색기에서 열기'), action: () => openExternal(n.path) }];
  if (!n.excluded) {   // 제외 폴더 안은 세지 않는다 (D49)
    opens.push({ label: t('이 폴더의 파일을 종류별로 모아 보기'), tip: t('모아 보기 탭의 파일 종류'), action: () => emit('parts', { path: n.path, mode: 'files' }) });
  }
  return menuGroups([{ header: top ? `${n.path}/ · ${t('제외 폴더')}` : n.hidden ? `${n.path}/ · ${t('숨긴 폴더')}` : `${n.path}/` }], items, clipItems(k, n), copyItems(n), opens);
}

/** 복사할 것 — 여럿 고른 행이 있고 그 안이면 그것들, 아니면 그 행 하나 (D203) */
function pickedOr(path) {
  const o = state();
  return o.picked.size > 1 && o.picked.has(path) ? [...o.picked] : [path];
}

/** '폴더' 묶음에서 고른 파일·폴더를 Windows 클립보드에 — 탐색기에서 붙여 넣는다 (D203) */
async function copyFiles(path) {
  const tab = S.tab;
  if (!tab || path == null) return;
  const paths = pickedOr(path).filter(Boolean);
  if (!paths.length) return;
  try {
    const r = await postJSON('/api/files/copy', { p: tab.id, paths });
    toast(t('{n}개를 복사했습니다 — 탐색기나 폴더 묶음에서 Ctrl+V 로 붙여 넣습니다', { n: r.count }));
  } catch (e) {
    toast(e.message, 'error');
  }
}

/** Windows 클립보드의 파일·폴더를 dir 에 복사 (D203 — 겹치면 '- 복사본', 덮어쓰지 않는다. 잘라내기도 복사만) */
async function pasteFiles(dir) {
  const tab = S.tab;
  if (!tab || blockedReadOnly(tab)) return;
  const o = tab.others;
  try {
    const r = await postJSON('/api/files/paste', { p: tab.id, dir });
    let msg = t('{n}개를 붙여 넣었습니다', { n: r.copied });
    if (r.cut) msg += ` — ${t('옮기기는 하지 않아 복사만 했습니다 (원본은 그대로)')}`;
    if (r.skipped?.length) msg += ` — ${t('건너뛴 것: {names}', { names: r.skipped.join(', ') })}`;
    toast(msg, '', 6000);
  } catch (e) {
    toast(e.message, 'error');
    return;
  }
  if (dir) o.folderOpen?.add(dir);   // 붙인 곳이 보이게
  forgetDir(o, dir, true);
  o.stale = true;
  o.hiddenStale = true;
  if (tab === S.tab) ensure();
}

/** '폴더' 묶음에서 Ctrl·Shift+누르기 — 여럿 고르기 (D203, 탐색기처럼). 그냥 누르면 하나로 돌아간다 */
function pickRow(path, e) {
  const o = state();
  if (e.shiftKey) {
    const rows = $$('.row', listEl('folder')).map((r) => r.dataset.path);
    const a = rows.indexOf(o.picked.anchor ?? o.selected.folder ?? path);
    const b = rows.indexOf(path);
    o.picked = new Set(rows.slice(Math.min(a, b), Math.max(a, b) + 1).filter((p) => p !== undefined));
    o.picked.anchor = rows[a] ?? path;
  } else {
    const anchor = o.picked.anchor;
    if (!o.picked.size && o.selected.folder != null) o.picked.add(o.selected.folder);
    if (o.picked.has(path)) o.picked.delete(path);
    else o.picked.add(path);
    o.picked.anchor = anchor ?? path;
  }
  o.selected.folder = path;
  renderList('folder');
  rowOf('folder', path)?.focus({ preventScroll: true });
}


/**
 * 다른 사이드바 탭의 파일 행 (D50 — 최근 변경, 검색의 이름, 모아 보기의 파일 종류): data-file 이 있는 행을 이 목록처럼 다룬다.
 * 문서는 한 번 누르면 뷰어(두 번 누르면 새 문서 탭 — D67), 코드는 한 번 누르면 읽기 화면·두 번 누르면 편집기, csv·tsv·txt·log 는 한 번 누르면 읽기 화면·두 번 누르면 기본 앱,
 * 그 밖의 자료는 두 번 누르거나 Enter 로 연다 (실행하지 않음).
 * fileOf(path): 그 행의 파일 노드 (문서는 트리의 노드 — kind 가 있다)
 */
export function bindFileRows(box, fileOf) {
  const nodeOf = (e) => {
    const row = e.target.closest('[data-file]');
    return row && box.contains(row) ? fileOf(row.dataset.file) : null;
  };
  box.addEventListener('click', (e) => {
    const n = nodeOf(e);
    if (repeatClick(e)) return;
    if (n?.kind) emit('open', { type: 'doc', path: n.path, ...openHow(e) });   // D91
    else if (isViewFile(n)) emit('open', { type: 'code', path: n.path, ...openHow(e) });
  });
  middleClickOpens(box, '[data-file]');
  box.addEventListener('dblclick', (e) => {
    const n = nodeOf(e);
    if (n && !n.kind) openExternal(n.path);
  });
  box.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' && e.key !== 'F2') return;
    const n = nodeOf(e);
    if (!n) return;
    e.preventDefault();
    if (e.key === 'F2') {   // 이름 바꾸기 (D66)
      if (!n.excluded) emit('rename', { path: n.path });
    } else if (n.kind) emit('open', { type: 'doc', path: n.path, ...openHow(e) });
    else if (isViewFile(n)) emit('open', { type: 'code', path: n.path, ...openHow(e) });
    else openExternal(n.path);
  });
  box.addEventListener('contextmenu', (e) => {
    const n = nodeOf(e);
    if (!n) return;
    e.preventDefault();
    showMenu(e.clientX, e.clientY, n.kind ? docMenuItems(n.path) : fileMenuItems(n));
  });
}

function openMenu(k, path, x, y) {
  const n = view(state(), k).index.get(path);
  if (!n) return;
  select(k, path);
  showMenu(x, y, menuItems(k, n));
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
  if (k === 'folder' && (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && (e.code === 'KeyC' || e.code === 'KeyV')) {   // D203
    e.preventDefault();
    e.stopPropagation();
    if (e.code === 'KeyC') copyFiles(path);
    else pasteFiles(n?.type === 'dir' ? path : dirname(path ?? ''));
    return;
  }
  if (sendRowKey(e, path)) return;   // Shift+→ 등: 그 행의 위치를 터미널로 (tree.js — D195. 펼치기·접기는 Shift 없는 → · ←)
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
  } else if (e.key === 'Enter') enter(k, path, openHow(e));
  else if (e.key === 'F2') {   // 이름 바꾸기 (D66) — 파일만, 제외 폴더 안은 하지 않는다
    if (n && n.type !== 'dir' && !n.excluded && path) emit('rename', { path });
  } else if (e.key === 'ContextMenu' || (e.key === 'F10' && e.shiftKey)) {
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
  const cur = openSection();   // 한 번에 하나 — 그것이 남은 높이를 모두 갖는다 (D143)
  for (const s of SECTIONS) {
    const sec = $(s.el);
    const open = s.name === cur;
    sec.classList.toggle('closed', !open);
    sec.classList.toggle('grow', open);
    const head = sec.querySelector('.side-head');
    head.setAttribute('aria-expanded', String(open));
    head.querySelector('.caret').classList.toggle('open', open);
  }
}

/** 묶음 하나를 펼치고 나머지는 접는다 (D143) — 머리줄 누르기·Ctrl+Shift+E */
function openSectionNamed(name) {
  if (openSection() === name) return;
  if (S.tab) S.tab.side.filesOpen = name;
  saveConfig({ files_open: name });
  applyLayout();
  if (state() && S.view) revealCurrent();   // 그리면서 지금 보는 것까지 펼친다 ('폴더'·코드 화면의 '코드')
  else render();
  ensure();
  emit('files-open', name);
}

function bindLayout() {
  for (const s of SECTIONS) {   // 머리줄을 누르면 그 묶음을 펼치고 나머지는 접는다 — 펼친 것을 누르면 그대로 (D143)
    $(s.el).querySelector('.side-head').addEventListener('click', () => openSectionNamed(s.name));
  }
  // 묶음의 만들기 (D177 — '문서'의 것은 newdialog.js): 그 묶음에서 만드는 것만, 위치는 목록에서 고른 폴더(파일이면 그 폴더)
  for (const [name, k] of [['code', 'code'], ['others', 'files'], ['folder', 'folder']]) {
    $(`#lec-${name}-new`).addEventListener('click', () => emit('new-doc', { dir: chosenDir(k), section: name }));
  }
}

/** 목록에서 고른 행의 폴더 — 폴더면 그것, 파일이면 그 폴더. 고른 것이 없거나 제외 폴더 안이면 프로젝트 맨 위 */
function chosenDir(k) {
  const o = state();
  const v = o && view(o, k);
  const n = v?.index.get(o.selected[v.sel] ?? '');
  if (!n || n.excluded) return '';
  return n.type === 'dir' ? n.path : dirname(n.path);
}

/** 묶음 안에서 초점을 줄 곳: 고른 행·지금 보는 것·Tab 이 들어갈 행·첫 행, 행이 없으면 머리줄 */
function sectionTarget(s) {
  const list = $(s.list);
  return list?.querySelector('.row.selected, .row.active') || list?.querySelector('.row[tabindex="0"]') || list?.querySelector('.row')
    || $(s.el).querySelector('.side-head');
}

/**
 * Ctrl+Shift+E (D169): 사이드바 '파일' 탭의 펼친 묶음으로 초점. 초점이 이미 그 묶음의 목록 안에 있으면 다음 묶음을 펼치고 그리로
 * (머리줄을 마우스로 누른 뒤처럼 머리줄에 있으면 그 목록으로 — 시나리오 시험에서 찾음)
 * (문서 → 코드 → 자료 → 폴더 → 문서). 다른 사이드바 탭이면 '파일' 탭으로 (감춘 사이드바는 main.js 가 먼저 보인다)
 */
export async function focusFiles() {
  if (!S.tab) return;
  const wasShown = filesShown();
  if (!wasShown) switchPanel('files', { focus: false });
  let i = SECTIONS.findIndex((s) => s.name === openSection());
  const here = $(SECTIONS[i].el);
  const empty = !$(SECTIONS[i].list)?.querySelector('.row');
  // 목록 안일 때만 — 머리줄을 누른 뒤면 그 목록으로 들어간다. 목록에 행이 없으면(빈 '작업' 등) 머리줄에서도 다음 묶음으로 (D204 — 거기 머물지 않게)
  if (wasShown && ($(SECTIONS[i].list).contains(document.activeElement) || (empty && here.contains(document.activeElement)))) {
    i = (i + 1) % SECTIONS.length;
    openSectionNamed(SECTIONS[i].name);
  }
  const s = SECTIONS[i];
  if (s.name !== 'docs' && !state()?.data) {   // 코드·자료·폴더의 목록을 아직 받는 중 — 받은 뒤에 행으로
    $(s.el).querySelector('.side-head').focus();
    await loadOthers(S.tab);
    if (openSection() !== s.name || !$(s.el).contains(document.activeElement)) return;   // 그사이 다른 곳으로 갔다
  }
  if (s.name === 'work' && S.tab) {   // '작업' — 형광펜·할 일을 읽은 뒤에 행으로 (D204)
    $(s.el).querySelector('.side-head').focus();
    await loadMarks(S.tab);
    await new Promise((r) => requestAnimationFrame(r));
    if (openSection() !== s.name || !$(s.el).contains(document.activeElement)) return;
  }
  const el = sectionTarget(s);
  el?.focus({ preventScroll: true });
  el?.scrollIntoView({ block: 'nearest' });
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
    if (k === 'folder' && (e.ctrlKey || e.metaKey || e.shiftKey) && !e.altKey) {   // 여럿 고르기 (D203) — 새 탭에 열기는 가운데 버튼으로
      pickRow(path, e);
      return;
    }
    if (k === 'folder' && state()?.picked.size) {
      state().picked = new Set();
      renderList('folder');
    }
    select(k, path);
    // '폴더' 묶음의 문서는 문서 트리처럼 한 번 누르면 연다. 코드는 한 번 누르면 읽기 화면 (두 번 누르면 편집기)
    const n = view(state(), k).index.get(path);
    if (repeatClick(e)) return;
    if (k === 'folder' && n?.doc) activate(k, path, openHow(e));   // D91
    else if (isViewFile(n)) emit('open', { type: 'code', path, ...openHow(e) });
  });
  middleClickOpens(box, '.row');
  box.addEventListener('dblclick', (e) => {
    const row = e.target.closest('.row');
    if (!row || e.target.closest('[data-toggle]')) return;
    const { path } = row.dataset;
    if (k === 'folder' && view(state(), k).index.get(path)?.doc) return;   // 한 번 누를 때 이미 열었다
    activate(k, path);
  });
  box.addEventListener('contextmenu', (e) => {
    const row = e.target.closest('.row');
    if (!row) {
      if (k === 'folder' && S.tab && !S.tab.readonly) {   // 목록의 빈 곳 — 프로젝트 맨 위에 (D203)
        e.preventDefault();
        showMenu(e.clientX, e.clientY, menuGroups([{ label: t('붙여 넣기'), hint: 'Ctrl+V', tip: t('프로젝트 맨 위에 — 탐색기에서 복사한 것도'), action: () => pasteFiles('') }], [newAnyItem(''), newFolderItem('')]));
      }
      return;
    }
    e.preventDefault();
    openMenu(k, row.dataset.path, e.clientX, e.clientY);
  });
  box.addEventListener('keydown', onKey);
  box.addEventListener('scroll', () => { const o = state(); if (o) o.scroll[k] = box.scrollTop; }, { passive: true });
}

export function initOthers() {
  for (const k of Object.keys(LISTS)) bindList(k);
  bindFileRows($('#lec-tree'), (path) => state()?.index?.files.get(path) ?? null);   // '문서' 묶음의 오피스 하위 묶음 (D202 — tree.js 가 그린다)
  bindLayout();
  applyLayout();
  $('#lec-filter').addEventListener('input', render);
  on('tab', () => {
    applyLayout();   // 펼친 묶음은 프로젝트 탭마다 (D143)
    render();
    for (const k of Object.keys(LISTS)) listEl(k).scrollTop = state()?.scroll[k] || 0;
    ensure();
  });
  on('panel', ensure);   // 사이드바 '파일' 탭으로 돌아오면
  on('others', (tab) => {   // 파일이 생기고 지워짐 — '폴더' 묶음의 숨김·빈 폴더도 다시 (D203 — 감시는 빈 폴더·숨긴 것을 놓친다)
    if (tab?.others) tab.others.hiddenStale = true;
    if (tab === S.tab) ensure();
  });
  // 문서 개수, 그리고 '폴더' 묶음은 문서 트리도 그린다: 트리·바뀜 점·지금 보는 문서가 바뀌면 다시
  on('tree', () => { if (folderShown()) render(); else renderHead(); });
  on('changed', () => { if (folderShown()) render(); });
  on('titles', () => { if (folderShown()) render(); });
  on('side-sort', render);   // 목록의 차례 (D97)
  on('side-open', setAllOpen);   // 폴더 모두 펼치기·접기 (D125 — tree.js 의 '펼침')
  on('view', revealCurrent);
}
