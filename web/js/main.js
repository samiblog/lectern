// 시작점: 초기화, 툴바, 단축키, 프로젝트 열기

import { S, emit, on } from './store.js';
import { getJSON, postJSON, saveConfig, native } from './api.js';
import { initTheme } from './theme.js';
import { initUi, showMenu, hideMenu, closeLightbox } from './ui.js';
import { initToc, setToc, updateTocVisibility } from './toc.js';
import { initFind, openFind, closeFind } from './find.js';
import { initFold } from './fold.js';
import { initSpotlight, spotlightOn, moveSpotlight, stopSpotlight } from './spotlight.js';
import { initTextSize } from './textsize.js';
import { initDocMenu } from './docmenu.js';
import { initChangeMarks } from './diffmark.js';
import { initSearch, openSearch } from './search.js';
import { initStatus, setStatus } from './status.js';
import { initOverview } from './overview.js';
import { initTree, focusFilter } from './tree.js';
import { initPalette, openPalette, closePalette } from './palette.js';
import { initPanes, selectPane } from './panes.js';
import { initNav, navigate, back, forward, resetHistory, refreshView, seedScroll, restorePanes } from './nav.js';
import { initSettings, openSettings, closeSettings } from './settings.js';
import { initPosition } from './position.js';
import { initResize } from './resize.js';
import { initPathLinks } from './pathlink.js';
import { initWatch, startWatch } from './watch.js';
import { loadTree } from './project.js';
import { forgetFailedImages } from './doc.js';
import { $, esc, basename, toast } from './util.js';

// ---- 프로젝트 ---------------------------------------------------------------

function folderName(p) {
  return basename(p.replace(/[\\/]+$/, '').replace(/\\/g, '/')) || p;
}

function showWelcome() {
  const recent = (S.config.recent || []).slice(0, 8);
  const view = $('#lec-view');
  view.className = 'welcome';
  view.innerHTML = `<h1>프로젝트 폴더를 여세요</h1>
    <p>폴더 안의 Markdown·HTML 문서를 트리와 개요로 정리해 보여 줍니다. 숨김 파일과 node_modules 같은 폴더는 제외합니다.</p>
    <p><button type="button" class="primary" data-act="open">폴더 열기</button></p>
    ${recent.length ? `<h2>최근 연 폴더</h2><ul>${recent.map((p) => `<li><button type="button" data-path="${esc(p)}">
      <span class="t">${esc(folderName(p))}</span><span class="p">${esc(p)}</span></button></li>`).join('')}</ul>` : ''}`;
  setToc(S.pane, null);
  setStatus({ path: '', info: '' });
}

/** 문서가 수천 개인 폴더는 처음 훑는 데 몇 초 걸린다 (막 만든 파일이 많으면 더). 그동안 빈 화면·옛 폴더 대신 알린다 */
function showLoading() {
  const view = $('#lec-view');
  view.className = 'welcome';
  view.innerHTML = `<p>${esc(S.name)} 폴더를 읽고 있습니다…</p>`;
  $('#lec-tree').innerHTML = '';
  setToc(S.pane, null);
  setStatus({ path: '', info: '' });
}

let configErrorShown = false;

async function reloadProject() {
  if (S.reloading) return;
  S.reloading = true;
  try {
    const st = await getJSON('/api/state');
    if (st.config_error && !configErrorShown) {
      configErrorShown = true;
      toast(st.config_error, 'error', 15000);
    }
    S.root = st.root;
    S.name = st.name;
    S.sep = st.sep;
    S.seq = st.seq;
    S.watch = st.watch;
    S.lastSync = null;
    S.changed.clear();
    S.open.clear();
    resetHistory();
    updateProjectHeader();
    if (!S.root) {
      S.tree = [];
      S.files = [];
      emit('tree');
      showWelcome();
      return;
    }
    const wait = setTimeout(showLoading, 400);
    try {
      await loadTree();
    } finally {
      clearTimeout(wait);
    }
    if (S.config.expand_first_level !== false) for (const n of S.tree) if (n.type === 'dir') S.open.add(n.path);
    // 마지막에 열어 둔 창들과 위치로 (설정 restore_last). 문서가 모두 없어졌으면 폴더 개요로
    const pos = st.position;
    if (S.config.restore_last !== false && pos) {
      seedScroll(pos.scroll);
      if (await restorePanes(pos)) return;
    }
    await navigate({ type: 'overview', path: '' });
  } catch (e) {
    toast(`프로젝트를 불러오지 못했습니다: ${e.message}`, 'error');
  } finally {
    S.reloading = false;
  }
}

async function openFolder(path) {
  try {
    await postJSON('/api/open', { path });
    S.config = await getJSON('/api/config');
    await reloadProject();
  } catch (e) {
    toast(`폴더를 열 수 없습니다: ${e.message}`, 'error');
  }
}

async function chooseAndOpen() {
  const path = await native.chooseFolder();
  if (path) await openFolder(path);
}

function updateProjectHeader() {
  const btn = $('#lec-btn-project');
  btn.textContent = S.root ? S.name : '폴더를 열어 주세요';
  btn.title = S.root || '';
  btn.disabled = !S.root;
}

function updateWindowTitle() {
  if (!S.root) {
    native.setTitle('Lectern');
    return;
  }
  let title = S.name;
  if (S.view?.type === 'doc') {
    const f = S.fileMap.get(S.view.path);
    title = `${f?.title || basename(S.view.path)} - ${S.name}`;
  }
  native.setTitle(`${title} - Lectern`);
}

/** 뒤로/앞으로는 선택된 창의 기록 */
function updateNavButtons() {
  $('#lec-btn-back').disabled = S.pane.hIndex <= 0;
  $('#lec-btn-forward').disabled = S.pane.hIndex >= S.pane.history.length - 1;
}

// ---- 레이아웃 -----------------------------------------------------------------

function applyLayout() {
  document.documentElement.classList.toggle('sidebar-off', S.config.sidebar_visible === false);
  $('#lec-btn-sidebar').classList.toggle('on', S.config.sidebar_visible !== false);
  updateTocVisibility();
}

async function toggleSidebar() {
  await saveConfig({ sidebar_visible: S.config.sidebar_visible === false });
  applyLayout();
}

async function toggleToc() {
  await saveConfig({ toc_visible: S.config.toc_visible === false });
  applyLayout();
}

async function manualRefresh() {
  if (!S.root) return;
  forgetFailedImages();   // 불러오지 못했던 외부 이미지도 다시 시도
  try {
    await loadTree({ fresh: true });
    await refreshView();
    toast('다시 불러왔습니다');
  } catch (e) {
    toast(`다시 불러오지 못했습니다: ${e.message}`, 'error');
  }
}

// ---- 연결 ---------------------------------------------------------------------

function bindToolbar() {
  $('#lec-btn-sidebar').addEventListener('click', toggleSidebar);
  $('#lec-btn-toc').addEventListener('click', toggleToc);
  $('#lec-btn-back').addEventListener('click', back);
  $('#lec-btn-forward').addEventListener('click', forward);
  $('#lec-btn-open').addEventListener('click', chooseAndOpen);
  $('#lec-btn-palette').addEventListener('click', openPalette);
  $('#lec-btn-project').addEventListener('click', () => S.root && navigate({ type: 'overview', path: '' }));
  $('#lec-btn-recent').addEventListener('click', (e) => {
    const recent = S.config.recent || [];
    const r = e.currentTarget.getBoundingClientRect();
    const items = recent.length
      ? recent.map((p) => ({ label: folderName(p), hint: p, action: () => openFolder(p) }))
      : [{ label: '최근 연 폴더가 없습니다', action: () => {} }];
    items.push('-', { label: '다른 폴더 열기...', action: chooseAndOpen });
    showMenu(r.left, r.bottom + 4, items);
  });
  $('#lec-panes').addEventListener('click', (e) => {
    if (!e.target.closest('.welcome')) return;
    const btn = e.target.closest('button');
    if (!btn) return;
    if (btn.dataset.act === 'open') chooseAndOpen();
    else if (btn.dataset.path) openFolder(btn.dataset.path);
  });
}

// 장 하이라이트 중에 앞뒤 장으로 가는 키 (입력칸·목록·열린 팝업에서는 원래대로)
const SPOT_KEYS = { ArrowUp: -1, ArrowDown: 1, PageUp: -1, PageDown: 1 };
const typing = (e) => e.target.closest?.('input, textarea, select, [contenteditable="true"]')
  || !$('#lec-menu').hidden || !$('#lec-palette').hidden || !$('#lec-settings').hidden;

function bindKeys() {
  document.addEventListener('keydown', (e) => {
    const mod = e.ctrlKey || e.metaKey;
    const key = e.key.toLowerCase();
    if (mod && !e.shiftKey && key === 'p') {
      e.preventDefault();
      openPalette();
    } else if (mod && e.shiftKey && key === 'f') {
      e.preventDefault();
      openSearch();
    } else if (mod && key === 'f') {
      e.preventDefault();
      if (S.view?.type === 'doc') openFind();
      else focusFilter();
    } else if (mod && e.key === ',') {
      e.preventDefault();
      openSettings();
    } else if (mod && key === 'o') {
      e.preventDefault();
      chooseAndOpen();
    } else if (mod && key === 'b') {
      e.preventDefault();
      toggleSidebar();
    } else if (e.altKey && e.key === 'ArrowLeft') {
      e.preventDefault();
      back();
    } else if (e.altKey && e.key === 'ArrowRight') {
      e.preventDefault();
      forward();
    } else if (mod && !e.shiftKey && !e.altKey && S.panes[Number(e.key) - 1]) {   // Ctrl+1·2·3: 그 창을 고른다
      e.preventDefault();
      selectPane(S.panes[Number(e.key) - 1]);
    } else if (e.key === 'F5') {
      e.preventDefault();
      manualRefresh();
    } else if (SPOT_KEYS[e.key] && !mod && !e.altKey && !e.shiftKey && spotlightOn() && !typing(e)) {
      e.preventDefault();
      moveSpotlight(SPOT_KEYS[e.key]);
    } else if (e.key === 'Escape') {
      if (closePalette() || closeSettings() || hideMenu() || closeLightbox() || closeFind() || stopSpotlight()) e.preventDefault();
    }
  });
  // 마우스 뒤로/앞으로 버튼
  window.addEventListener('mouseup', (e) => {
    if (e.button === 3) { e.preventDefault(); back(); }
    if (e.button === 4) { e.preventDefault(); forward(); }
  });
}

/**
 * 창 모드에서는 pywebview 가 페이지를 다 불러온 뒤 window.pywebview(토큰·js_api)를 넣고 pywebviewready 를 보낸다.
 * 토큰 없이는 /api/* 가 모두 403 이므로 늦어져도 끝까지 기다린다. 오래 걸리면 화면에 알린다.
 */
async function waitForBridge() {
  if (S.mode !== 'app' || native.has('choose_folder')) return;
  const slow = setTimeout(() => {
    const view = $('#lec-view');
    view.className = 'welcome';
    view.innerHTML = '<h1>창과 연결하는 중입니다</h1><p>이 화면이 계속되면 Lectern을 닫았다가 다시 실행해 주세요.</p>';
  }, 4000);
  await new Promise((resolve) => window.addEventListener('pywebviewready', resolve, { once: true }));
  clearTimeout(slow);
}

async function boot() {
  await waitForBridge();
  try {
    S.config = await getJSON('/api/config');
  } catch {
    S.config = {};
  }
  initTheme();
  initUi();
  initPanes();
  initToc();
  initFind();
  initFold();
  initSpotlight();
  initTextSize();
  initDocMenu();
  initChangeMarks();
  initSearch();
  initSettings();
  initPosition();
  initResize();
  initPathLinks();
  initStatus();
  initOverview();
  initTree();
  initPalette();
  initNav();
  initWatch();
  bindToolbar();
  bindKeys();
  applyLayout();

  on('view', () => { updateNavButtons(); updateWindowTitle(); });
  on('project-switched', reloadProject);

  await reloadProject();
  startWatch();
}

boot();
