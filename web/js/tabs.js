// 프로젝트 탭 (D34): 여러 프로젝트 폴더를 탭으로 열어 두고 오간다. 탭을 누르면 왼쪽 트리·최근 변경·검색과 문서 화면이 함께 바뀐다.
//
// - 열린 탭(순서·선택된 탭)은 서버가 들고 있다 (state.py). 화면은 /api/state·/api/open·/api/close 의 답으로 맞춘다 (syncTabs).
//   다른 실행(탐색기 우클릭 등)이 넘긴 폴더로 서버의 탭 목록이 바뀌면 watch.js 가 tabs_seq 로 알아채고 resyncTabs 를 부른다.
// - 탭마다 트리 데이터·변경됨·펼친 폴더·사이드바 상태(side)와 문서 칸(panes.js)이 따로다. store.js 의 S.root·S.tree 등은
//   선택된 탭의 값을 읽고 쓰는 접근자다. 문서 칸은 문서 탭(doctabs.js, D64)마다 하나 — tab.panes(20개까지 — D67), 고른 것이 tab.pane.
// - 탭은 처음 고를 때 트리를 읽고 마지막에 보던 문서(설정 restore_last)나 폴더 개요를 연다 — 탭이 많아도 시작이 느려지지 않게.
// - 고르지 않은 탭의 칸은 자리를 지킨 채 숨는다. 숨은 동안 바뀐 화면(pane.stale)은 그 탭을 고를 때 다시 그린다.

import { S, emit, on } from './store.js';
import { getJSON, postJSON, native, revealInExplorer } from './api.js';
import { createPane, removePane, selectPane, homePane } from './panes.js';
import { navigate, restorePosition } from './nav.js';
import { loadTree } from './project.js';
import { setToc } from './toc.js';
import { setStatus } from './status.js';
import { rememberPosition } from './position.js';
import { showMenu } from './ui.js';
import { folderIcon } from './icons.js';
import { confirmCloseTerminal, disposeTerminal } from './terminal.js';
import { confirmCloseEditor, disposeEditor } from './editor.js';
import { restoreDocTabs, selectDocTab } from './doctabs.js';
import { $, esc, basename, toast, copyText } from './util.js';
import { t } from './i18n.js';

let maxTabs = 10;          // 서버의 MAX_TABS (/api/state 의 max_tabs)
let tabsSeq = -1;          // 화면이 맞춘 서버 탭 목록의 순번
let noticeSeen = 0;        // 이미 보인 서버 알림 id
let configErrorShown = false;

/** 화면이 맞춘 서버 탭 목록의 순번 (watch.js 가 서버의 값과 비교한다) */
export const knownTabsSeq = () => tabsSeq;

export function folderName(p) {
  return basename(p.replace(/[\\/]+$/, '').replace(/\\/g, '/')) || p;
}

/** 폴더 경로의 상위 폴더 이름 (같은 이름의 탭을 구분할 때) */
function parentName(p) {
  const parts = p.replace(/\\/g, '/').replace(/\/+$/, '').split('/');
  return parts.length > 1 ? parts[parts.length - 2] : '';
}

const samePath = (a, b) => a.replace(/\\/g, '/').toLowerCase() === b.replace(/\\/g, '/').toLowerCase();

function makeTab(p) {
  const tab = {
    id: p.id, root: p.root, name: p.name, watch: p.watch, seq: p.seq,
    position: p.position,   // 열 때 서버가 알려 준 마지막 문서와 스크롤 위치 (처음 고를 때 쓴다)
    tree: [], files: [], fileMap: new Map(), dirs: new Set(), changed: new Set(), open: new Set(), lastSync: null,
    treeLoaded: false,      // 트리를 받았는지 (project.js)
    loaded: false,          // 첫 화면까지 그렸는지
    loading: null,          // 첫 화면을 그리는 중이면 그 Promise
    side: { panel: 'files', filter: '', treeScroll: 0, recentScroll: 0, search: null },   // 사이드바 상태 (tree.js·recent.js·search.js·parts.js)
    // 최근 변경의 코드·자료 (recent.js, D50): 받은 파일(files — 받을 때의 버튼 key), 다시 받을지(stale), 받는 중(loading)
    recent: { files: null, key: '', stale: true, loading: null, again: false, error: null },
    // 사이드바 '코드'·'자료' 목록 (others.js): 받은 문서 외 파일(data), 펼쳐서 읽은 제외 폴더의 안(lazy: 경로 → {nodes…}, 읽는 중 loadingDirs)을
    // 붙인 트리(tree), 파일·코드로 나눈 트리(trees·index·counts), 다시 읽을지(stale),
    // 목록마다 펼친 폴더(open, 폴더 보기 folderOpen), 폴더 보기에서 문서와 합친 트리(all·allIndex), 고른 행(selected), 스크롤 위치
    others: {
      data: null, tree: null, lazy: new Map(), loadingDirs: new Set(), trees: null, index: null, counts: null, error: null, stale: true, loading: null,
      open: { files: new Set(), code: new Set() }, folderOpen: null, all: null, allIndex: null,
      selected: { files: null, code: null, folder: null }, scroll: { files: 0, code: 0 },
    },
  };
  tab.pane = createPane(tab);   // 고른 문서 탭의 칸 (doctabs.js — D64)
  tab.panes = [tab.pane];        // 문서 탭들의 칸, 탭 차례
  return tab;
}

/** 서버의 탭 목록(info: /api/state 와 같은 모양)에 맞춘다. 새 탭은 만들고, 서버에 없는 탭은 칸까지 없앤다. 새로 생긴 탭들을 돌려준다 */
function syncTabs(info) {
  tabsSeq = info.tabs_seq;
  maxTabs = info.max_tabs || maxTabs;
  S.samples = info.samples ?? null;
  S.writingGuide = info.writing_guide || '';
  if (info.sep) S.sep = info.sep;
  for (const n of info.notices || []) {
    if (n.id <= noticeSeen) continue;
    noticeSeen = n.id;
    toast(n.text, 'error', 8000);
  }
  const known = new Map(S.tabs.map((tb) => [tb.id, tb]));
  const added = [];
  const next = info.projects.map((p) => {
    if (known.has(p.id)) return known.get(p.id);
    const tab = makeTab(p);
    added.push(tab);
    return tab;
  });
  const dropped = S.tabs.filter((tb) => !next.includes(tb));
  S.tabs = next;
  for (const tab of dropped) {
    if (tab === S.tab) S.tab = null;   // 부르는 쪽이 곧 다른 탭(없으면 시작 화면)을 고른다
    disposeEditor(tab);   // 편집 상자 (저장하지 않은 것은 닫기 전에 물었다)
    for (const pane of tab.panes) removePane(pane);
    disposeTerminal(tab);   // 셸은 서버가 탭을 닫을 때 끝냈다
  }
  renderTabs();
  emit('tabs');   // 터미널 모음의 칸 (gather.js)
  return added;
}

/** 칸에 짧은 안내를 보인다 (폴더를 읽는 중·읽지 못함) */
function showMessage(pane, html) {
  pane.view.className = 'welcome';
  pane.view.innerHTML = `<p>${html}</p>`;
  setToc(pane, null);
  setStatus({ path: '', info: '' }, pane);
}

/** 탭을 처음 고를 때: 트리를 읽고, 마지막에 보던 문서와 위치(설정 restore_last)로 연다. 그 문서가 없어졌으면 폴더 개요 */
function loadTab(tab) {
  tab.loading ??= (async () => {
    const { pane } = tab;
    // 문서가 수천 개인 폴더는 처음 훑는 데 몇 초 걸린다 (막 만든 파일이 많으면 더). 그동안 빈 화면 대신 알린다
    const wait = setTimeout(() => { if (!pane.current) showMessage(pane, t('{name} 폴더를 읽고 있습니다…', { name: esc(tab.name) })); }, 400);
    try {
      await loadTree({ tab });
      if (S.config.expand_first_level !== false) for (const n of tab.tree) if (n.type === 'dir') tab.open.add(n.path);
      const restore = S.config.restore_last !== false;
      const restored = restore && await restorePosition(pane, tab.position);
      // 트리가 보인 뒤 사용자가 이미 다른 문서를 눌렀으면(그리는 중 포함) 개요로 덮지 않는다
      if (!restored && !pane.current && !pane.pending) await navigate({ type: 'overview', path: '' }, { pane });
      if (restore && tab.panes.length === 1) restoreDocTabs(tab, tab.position);   // 열어 두었던 다른 문서 탭 (고를 때 그린다)
      tab.loaded = true;
    } catch (e) {
      if (S.tabs.includes(tab)) showMessage(pane, t('폴더를 읽지 못했습니다 ({error}). F5 를 누르면 다시 불러옵니다.', { error: esc(e.message) }));
    } finally {
      clearTimeout(wait);
      tab.loading = null;
    }
  })();
  return tab.loading;
}

/** 탭이 첫 화면까지 그려졌는지 보고, 아니면 그린다 (F5 — 처음 열 때 실패한 탭) */
export const ensureLoaded = (tab) => (tab.loaded ? Promise.resolve() : loadTab(tab));

function showWelcome() {
  const pane = homePane();
  const recent = (S.config.recent || []).slice(0, 8);
  pane.view.className = 'welcome';
  pane.view.innerHTML = `<h1>${t('프로젝트 폴더를 여세요')}</h1>
    <p>${t('폴더 안의 Markdown·HTML 문서를 트리와 개요로 정리해 보여 줍니다. 폴더마다 탭으로 열려 여러 프로젝트를 오가며 볼 수 있습니다. 숨김 파일과 node_modules 같은 폴더는 제외합니다.')}</p>
    <p class="welcome-acts"><button type="button" class="primary" data-act="open">${t('폴더 열기')}</button>
      ${S.samples ? `<button type="button" class="text-btn" data-act="samples" title="${esc(t('Lectern 둘러보기와 문서 쓰는 법이 든 예제 프로젝트 — {path}', { path: S.samples }))}">${t('예제 열기')}</button>` : ''}
      <button type="button" class="text-btn" data-act="help">${t('사용설명서')}<kbd>F1</kbd></button></p>
    ${recent.length ? `<h2>${t('최근 연 폴더')}</h2><ul>${recent.map((p) => `<li><button type="button" data-path="${esc(p)}">
      <span class="t">${esc(folderName(p))}</span><span class="p">${esc(p)}</span></button></li>`).join('')}</ul>` : ''}`;
  setToc(pane, null);
  setStatus({ path: '', info: '' }, pane);
}

/** 탭이 없을 때: 시작 화면 (폴더 열기·최근 폴더) */
function showHome() {
  const prev = S.tab;   // 방금 닫은 탭이면 이미 null 이다 (syncTabs)
  S.tab = null;
  emit('tab', { tab: null, prev });   // 사이드바를 비운다
  selectPane(homePane());
  renderTabs();
  showWelcome();
}

/**
 * 탭을 고른다. 사이드바와 문서 화면이 그 탭의 것으로 바뀐다. tell: 서버에 알린다 (다음 실행·폴더 대화상자 시작 위치).
 * 처음 고르는 탭이면 트리를 읽고 첫 화면을 그리고, 숨은 동안 바뀐 화면이면 다시 그린다.
 */
export async function selectTab(tab, { tell = true } = {}) {
  if (!tab) {
    showHome();
    return;
  }
  if (tab !== S.tab) {
    const prev = S.tab;
    S.tab = tab;
    emit('tab', { tab, prev });   // 사이드바를 이 탭의 것으로 — 칸을 바꾸기 전에 ('view' 가 트리를 다시 그린다)
    selectPane(tab.pane);
    renderTabs();
    $('#lec-tablist .lec-tab.active')?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    // 편집 중이면 편집기에 (Ctrl+S 가 저장하게), 아니면 PageUp·PageDown·방향키가 이 탭의 문서를 스크롤하게
    if (tab.pane.editor) tab.pane.editor.cm.focus();
    else tab.pane.scroller.focus({ preventScroll: true });
    if (tell) postJSON('/api/activate', { p: tab.id }).catch(() => {});
  }
  if (!tab.loaded) await loadTab(tab);
  else if (tab.pane.stale || tab.pane.deferred) await selectDocTab(tab.pane);   // 숨은 동안 바뀐 화면, 되살리고 아직 그리지 않은 문서 탭
}

/** 폴더를 탭으로 연다. 이미 열린 폴더면 그 탭으로 간다 (서버가 정한다) */
export async function openFolder(path) {
  let info;
  try {
    info = await postJSON('/api/open', { path });
  } catch (e) {
    toast(t('폴더를 열 수 없습니다: {error}', { error: e.message }), 'error');
    return false;
  }
  try {
    S.config = await getJSON('/api/config');   // 최근 연 폴더 목록
  } catch { /* 최근 폴더 목록만 늦게 바뀐다 */ }
  syncTabs(info);
  await selectTab(S.tabs.find((tb) => tb.id === info.opened) || null, { tell: false });
  return true;
}

/** 예제 프로젝트를 탭으로 연다 (D57 — 설치 폴더의 samples. 이미 열려 있으면 그 탭). 처음이면 폴더 개요 대신 README('여기서 시작하세요') */
export async function openSamples() {
  if (!S.samples) {
    toast(t('예제 폴더가 없습니다. Lectern 을 다시 설치하면 생깁니다'), 'error');
    return false;
  }
  const ok = await openFolder(S.samples);
  if (ok && S.view?.type === 'overview' && !S.view.path && S.fileMap.has('README.md')) await navigate({ type: 'doc', path: 'README.md' });
  return ok;
}

export async function chooseAndOpen() {
  if (S.tabs.length >= maxTabs) {
    toast(t('탭은 {n}개까지 열 수 있습니다. 안 쓰는 탭을 닫고 다시 여세요', { n: maxTabs }), 'error');
    return;
  }
  const path = await native.chooseFolder();
  if (path) await openFolder(path);
}

/** 탭을 닫는다 (그 탭의 터미널도 끝난다). 선택된 탭이었으면 그 오른쪽(없으면 왼쪽) 탭을 고른다. 마지막 탭이면 시작 화면 */
export async function closeTab(tab) {
  if (!S.tabs.includes(tab)) return;
  if (!await confirmCloseTerminal(tab)) return;   // 터미널에서 프로그램이 돌고 있으면 묻는다
  // 편집 모드에서 저장하지 않은 것이 있으면 묻는다 (D54 — 묻기만. 편집 상자는 탭이 실제로 닫힌 뒤 syncTabs 가 치운다)
  if (!confirmCloseEditor(tab)) return;
  await rememberPosition(tab);   // 스크롤을 멈춘 지 얼마 안 됐어도 마지막 위치를 남긴다 (닫은 뒤에는 서버가 받지 않는다)
  const i = S.tabs.indexOf(tab);
  const next = tab === S.tab ? (S.tabs[i + 1] || S.tabs[i - 1] || null) : S.tab;
  let info;
  try {
    info = await postJSON('/api/close', { p: tab.id });
  } catch (e) {
    toast(t('탭을 닫지 못했습니다: {error}', { error: e.message }), 'error');
    return;
  }
  syncTabs(info);
  const target = S.tabs.includes(next) ? next : S.tabs[Math.min(i, S.tabs.length - 1)] || null;
  if (target !== S.tab || !target) await selectTab(target);
}

async function closeOthers(keep) {
  await selectTab(keep);
  for (const tab of S.tabs.filter((tb) => tb !== keep)) await closeTab(tab);
}

export const closeCurrentTab = () => (S.tab ? closeTab(S.tab) : undefined);

/** 다음(+1)·이전(-1) 탭 (Ctrl+Tab, Ctrl+Shift+Tab). 끝에서는 반대쪽 끝으로 */
export function cycleTab(step) {
  if (S.tabs.length < 2) return;
  const i = S.tabs.indexOf(S.tab);
  selectTab(S.tabs[(i + step + S.tabs.length) % S.tabs.length]);
}

/** Ctrl+1~8 은 그 순번의 탭, Ctrl+9 는 마지막 탭 (브라우저와 같게). 그 탭이 없으면 false */
export function selectTabAt(n) {
  const tab = n === 9 ? S.tabs[S.tabs.length - 1] : S.tabs[n - 1];
  if (tab) selectTab(tab);
  return !!tab;
}

/** 서버의 탭 목록이 바뀌었을 때 (다른 실행이 넘긴 폴더 등). 서버가 고른 탭이 다르면 그 탭으로 */
export async function resyncTabs() {
  const info = await getJSON('/api/state');
  syncTabs(info);
  const want = S.tabs.find((tb) => tb.id === info.active) || S.tab || S.tabs[0] || null;
  if (want !== S.tab || !want) await selectTab(want, { tell: false });
}

/** 시작할 때: 서버가 되살린 탭들을 만들고 선택돼 있던 탭을 연다 */
export async function loadTabs() {
  let info;
  try {
    info = await getJSON('/api/state');
  } catch (e) {
    toast(t('프로젝트를 불러오지 못했습니다: {error}', { error: e.message }), 'error');
    showHome();
    return;
  }
  syncTabs(info);
  if (info.config_error && !configErrorShown) {
    configErrorShown = true;
    toast(info.config_error, 'error', 15000);
  }
  await selectTab(S.tabs.find((tb) => tb.id === info.active) || S.tabs[0] || null, { tell: false });
}

// ---- 탭 막대 -------------------------------------------------------------------

function renderTabs() {
  const count = new Map();
  for (const tb of S.tabs) count.set(tb.name.toLowerCase(), (count.get(tb.name.toLowerCase()) || 0) + 1);
  $('#lec-tablist').innerHTML = S.tabs.map((tb, i) => {
    const active = tb === S.tab;
    const parent = count.get(tb.name.toLowerCase()) > 1 ? parentName(tb.root) : '';   // 같은 이름의 폴더는 상위 폴더 이름으로 구분
    const key = i < 8 ? `Ctrl+${i + 1}` : i === S.tabs.length - 1 ? 'Ctrl+9' : '';
    return `<div class="lec-tab${active ? ' active' : ''}" role="tab" aria-selected="${active}" tabindex="0" data-id="${esc(tb.id)}"
      title="${esc(tb.root)}${key ? `\n${key}` : ''}">${folderIcon()}<span class="name">${esc(tb.name)}</span>${parent ? `<span class="sub">${esc(parent)}</span>` : ''}`
      + `${!active && tb.changed.size ? `<span class="dot" title="${t('열어 보기 전에 바뀐 문서가 있습니다')}"></span>` : ''}`
      + `<button type="button" class="tab-close" title="${t('탭 닫기 (Ctrl+W)')}" aria-label="${esc(t('{name} 탭 닫기', { name: tb.name }))}"><svg><use href="#i-close"/></svg></button></div>`;
  }).join('');
}

const tabOf = (el) => S.tabs.find((tb) => tb.id === el?.closest('.lec-tab')?.dataset.id) || null;

async function copy(text) {
  toast(await copyText(text) ? t('복사했습니다: {what}', { what: text }) : t('복사하지 못했습니다'));
}

function tabMenu(tab) {
  const items = [{ header: tab.root }, { label: t('탭 닫기'), hint: tab === S.tab ? 'Ctrl+W' : '', action: () => closeTab(tab) }];
  if (S.tabs.length > 1) items.push({ label: t('다른 탭 모두 닫기'), action: () => closeOthers(tab) });
  items.push('-', { label: t('전체 경로 복사'), action: () => copy(tab.root) },
    { label: t('탐색기에서 보기'), action: () => revealInExplorer('', tab) });
  return items;
}

function recentMenu(e) {
  const recent = S.config.recent || [];
  const r = e.currentTarget.getBoundingClientRect();
  const items = recent.length
    ? recent.map((p) => ({
      label: folderName(p), hint: S.tabs.some((tb) => samePath(tb.root, p)) ? t('{path} (열린 탭)', { path: p }) : p, action: () => openFolder(p),
    }))
    : [{ label: t('최근 연 폴더가 없습니다'), action: () => {} }];
  items.push('-', { label: t('다른 폴더 열기…'), hint: 'Ctrl+O', action: chooseAndOpen });
  if (S.samples) items.push({ label: t('예제 열기'), hint: t('Lectern 둘러보기·문서 쓰는 법'), action: openSamples });
  showMenu(r.left, r.bottom + 4, items);
}

export function initTabs() {
  const list = $('#lec-tablist');
  list.addEventListener('click', (e) => {
    const tab = tabOf(e.target);
    if (!tab) return;
    if (e.target.closest('.tab-close')) closeTab(tab);
    else selectTab(tab);
  });
  list.addEventListener('mousedown', (e) => { if (e.button === 1) e.preventDefault(); });   // 가운데 버튼의 자동 스크롤 대신
  list.addEventListener('auxclick', (e) => {   // 가운데 버튼으로 누르면 닫기 (브라우저 탭처럼)
    const tab = e.button === 1 && tabOf(e.target);
    if (tab) closeTab(tab);
  });
  list.addEventListener('keydown', (e) => {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('.lec-tab')) {
      e.preventDefault();
      selectTab(tabOf(e.target));
    }
  });
  list.addEventListener('contextmenu', (e) => {
    const tab = tabOf(e.target);
    if (!tab) return;
    e.preventDefault();
    showMenu(e.clientX, e.clientY, tabMenu(tab));
  });
  // 탭이 많아 넘치면 휠로 가로 스크롤
  list.addEventListener('wheel', (e) => {
    if (!e.deltaY || list.scrollWidth <= list.clientWidth) return;
    list.scrollLeft += e.deltaY;
    e.preventDefault();
  }, { passive: false });
  $('#lec-btn-open').addEventListener('click', chooseAndOpen);
  $('#lec-btn-recent').addEventListener('click', recentMenu);
  // 시작 화면의 '폴더 열기'와 최근 폴더
  $('#lec-panes').addEventListener('click', (e) => {
    if (!e.target.closest('.welcome')) return;
    const btn = e.target.closest('button');
    if (btn?.dataset.act === 'open') chooseAndOpen();
    else if (btn?.dataset.act === 'samples') openSamples();
    else if (btn?.dataset.path) openFolder(btn.dataset.path);
  });
  on('changed', renderTabs);   // 숨은 탭의 '바뀜' 점
}
