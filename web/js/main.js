// 시작점: 초기화, 툴바, 단축키

import { S, on } from './store.js';
import { getJSON, saveConfig, native } from './api.js';
import { initTheme, loadUserStyles } from './theme.js';
import { initUi, hideMenu, closeLightbox } from './ui.js';
import { initToc, updateTocVisibility } from './toc.js';
import { initFind, openFind, closeFind } from './find.js';
import { initFold } from './fold.js';
import { initSpotlight, spotlightOn, moveSpotlight, stopSpotlight } from './spotlight.js';
import { initTextSize } from './textsize.js';
import { initDocMenu } from './docmenu.js';
import { initChangeMarks } from './diffmark.js';
import { initSearch, openSearch } from './search.js';
import { initParts } from './parts.js';
import { initStatus } from './status.js';
import { initOverview } from './overview.js';
import { initTree, focusFilter } from './tree.js';
import { initRecent, refreshRecent } from './recent.js';
import { initOthers, refreshOthers } from './others.js';
import { initPalette, openPalette, closePalette } from './palette.js';
import { initPanes } from './panes.js';
import { initNav, back, forward, refreshView } from './nav.js';
import {
  initTabs, loadTabs, chooseAndOpen, closeCurrentTab, cycleTab, selectTabAt, ensureLoaded,
} from './tabs.js';
import { initSettings, openSettings, closeSettings } from './settings.js';
import {
  initHelp, toggleManual, closeManual, manualOpen, toggleShortcuts, closeShortcuts,
} from './help.js';
import { initPosition } from './position.js';
import { initResize } from './resize.js';
import { initPathLinks } from './pathlink.js';
import { initWatch, startWatch } from './watch.js';
import { initTerminal, toggleTerminal, terminalOpen, terminalBelow } from './terminal.js';
import { initEditor, toggleEditor, inEditor } from './editor.js';
import { initBasket, closeInsert, askNewDoc } from './basket.js';
import { initRename, closeRename } from './rename.js';
import { initDocTabs, docTabAt, closeDocTab } from './doctabs.js';
import { initCodeView } from './codeview.js';
import { initSlides } from './slides.js';
import { initPresent, presenting, presentKey, startPresent } from './present.js';
import { initGather, gatherOn, toggleGather, leaveGather, leaveToFocused, focusNextTile } from './gather.js';
import { loadTree } from './project.js';
import { forgetFailedImages } from './doc.js';
import { $, basename, toast } from './util.js';
import { t, translatePage } from './i18n.js';

function updateWindowTitle() {
  if (!S.root) {
    native.setTitle('Lectern');
    return;
  }
  let title = S.name;
  if (S.view?.type === 'doc') {   // 파일 이름 [문서 제목] — 제목이 없거나 파일 이름과 같으면 파일 이름만
    const f = S.fileMap.get(S.view.path);
    const name = basename(S.view.path);
    title = `${f?.title && f.title !== name ? `${name} [${f.title}]` : name} - ${S.name}`;
  } else if (S.view?.type === 'code') {
    title = `${basename(S.view.path)} - ${S.name}`;
  }
  native.setTitle(`${title} - Lectern`);
}

/** 뒤로/앞으로는 선택된 탭의 기록 */
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
  if (gatherOn()) {   // 터미널 모음이 문서 화면을 가리고 있으면 닫고 목차를 보인다
    leaveGather();
    if (S.config.toc_visible !== false && !terminalOpen()) return;
  }
  if (terminalOpen() && !terminalBelow()) {   // 오른쪽 터미널을 연 동안은 목차를 함께 볼지만 바꾼다 (설정은 그대로 — toc.js)
    document.documentElement.classList.toggle('toc-with-term');
    applyLayout();
    return;
  }
  await saveConfig({ toc_visible: S.config.toc_visible === false });
  applyLayout();
}

/** F5: 선택된 탭의 트리를 새로 훑고 화면을 다시 그린다 (처음 열 때 읽지 못한 탭이면 다시 연다) */
async function manualRefresh() {
  const tab = S.tab;
  if (!tab) return;
  forgetFailedImages();   // 불러오지 못했던 외부 이미지도 다시 시도
  try {
    if (!tab.loaded) {
      await ensureLoaded(tab);
      return;
    }
    await loadTree({ fresh: true, tab });
    refreshOthers();
    refreshRecent();
    for (const pane of tab.panes) if (pane !== tab.pane && pane.current) pane.stale = true;   // 숨은 문서 탭은 고를 때 (D64)
    await refreshView(tab.pane);
    toast(t('다시 불러왔습니다'));
  } catch (e) {
    toast(t('다시 불러오지 못했습니다: {error}', { error: e.message }), 'error');
  }
}

// ---- 연결 ---------------------------------------------------------------------

function bindToolbar() {
  $('#lec-btn-sidebar').addEventListener('click', toggleSidebar);
  $('#lec-btn-toc').addEventListener('click', toggleToc);
  $('#lec-btn-back').addEventListener('click', back);
  $('#lec-btn-forward').addEventListener('click', forward);
  $('#lec-btn-palette').addEventListener('click', openPalette);
  // 탭 막대의 터미널 버튼: 터미널 모음을 보는 중이면 모음을 닫고 이 프로젝트의 오른쪽 터미널을 연다
  $('#lec-btn-term').addEventListener('click', () => (gatherOn() ? leaveGather({ tab: S.tab, panel: true }) : toggleTerminal()));
  // 툴바의 터미널 모음 버튼은 initGather 가 잇는다
}

// 장 하이라이트 중에 앞뒤 장으로 가는 키 (입력칸·목록·열린 팝업에서는 원래대로)
const SPOT_KEYS = { ArrowUp: -1, ArrowDown: 1, PageUp: -1, PageDown: 1 };
const typing = (e) => e.target.closest?.('input, textarea, select, [contenteditable="true"]')
  || !$('#lec-menu').hidden || !$('#lec-palette').hidden || !$('#lec-settings').hidden || !$('#lec-keys').hidden || manualOpen();
const inTerminal = (e) => !!e.target.closest?.('#lec-term');

function bindKeys() {
  document.addEventListener('keydown', (e) => {
    if (presenting()) {   // 발표 중(present.js, D59): 키는 모두 발표의 것 — 넘기기·노트·전체 화면·Esc
      presentKey(e);
      return;
    }
    const mod = e.ctrlKey || e.metaKey;
    const key = e.key.toLowerCase();
    if (mod && !e.altKey && e.code === 'Backquote') {   // 터미널 열고 닫기 (터미널 안에서도), Shift 와 함께면 터미널 모음
      e.preventDefault();
      closeManual();   // 사용설명서가 덮고 있으면 걷고
      if (e.shiftKey) toggleGather();
      else if (gatherOn()) leaveToFocused();   // 모음에서는 고른 칸의 프로젝트로 가서 오른쪽 터미널
      else toggleTerminal();
      return;
    }
    const helpKey = e.key === 'F1' || (mod && (e.key === '/' || e.code === 'Slash'));   // 사용설명서·단축키 표 (help.js)
    // 터미널 모음(gather.js)이 문서 화면을 가리는 동안: 칸 사이 옮기기(Ctrl+Tab)와 탭·폴더·설정·도움말 몇 가지만. 칸 안의 키는 셸 것.
    // 사용설명서가 모음 위를 덮고 있으면 보통 때처럼
    if (gatherOn() && !manualOpen()) {
      if (mod && e.key === 'Tab') {
        e.preventDefault();
        focusNextTile(e.shiftKey ? -1 : 1);
        return;
      }
      if (e.target.closest?.('#lec-gather')) return;
      const toTab = mod && !e.shiftKey && !e.altKey && /^[1-9]$/.test(e.key);
      if (!toTab && !helpKey && !(mod && (key === 'o' || e.key === ',')) && e.key !== 'Escape') return;
      if (toTab) leaveGather();   // 그 탭으로 (아래 selectTabAt)
    }
    // 터미널 안의 키는 셸 것이다 (Ctrl+C·Ctrl+W·Esc 등). 다음·이전 탭(Ctrl+Tab)만 앱이 받는다 — terminal.js 의 keyFor
    if (inTerminal(e) && !(mod && e.key === 'Tab')) return;
    // 편집 상자 안의 키는 편집기 것이다 (Ctrl+F 찾기·Ctrl+S 저장·Esc 닫기 등 — editor.js). 탭 옮기기·편집 닫기(Ctrl+E)·문서 열기·도움말,
    // 문서 탭(Alt+1~5·Ctrl+F4 — D64)만 앱이
    const docTabKey = (e.altKey && !mod && !e.shiftKey && /^[1-5]$/.test(e.key)) || (mod && !e.altKey && !e.shiftKey && e.key === 'F4');
    if (inEditor(e.target) && !(mod && (e.key === 'Tab' || key === 'e' || key === 'p' || key === 'n' || e.key === ',' || /^[1-9]$/.test(e.key))) && !helpKey && !docTabKey) return;
    if (mod && !e.shiftKey && !e.altKey && key === 'e') {   // 편집 모드 열고 닫기 (D54)
      e.preventDefault();
      toggleEditor();
      return;
    }
    if (mod && !e.shiftKey && !e.altKey && key === 'n') {   // 새로 만들기 (D65)
      e.preventDefault();
      askNewDoc();
    } else if (mod && !e.shiftKey && key === 'p') {
      e.preventDefault();
      openPalette();
    } else if (mod && e.shiftKey && key === 'f') {
      e.preventDefault();
      openSearch();
    } else if (mod && key === 'f') {
      e.preventDefault();
      if (manualOpen() || S.view?.type === 'doc' || S.view?.type === 'code') openFind();   // 사용설명서를 연 동안은 설명서 안을
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
    } else if (mod && !e.shiftKey && key === 'w') {   // 탭 닫기 (브라우저 탭처럼)
      e.preventDefault();
      closeCurrentTab();
    } else if (mod && (e.key === 'Tab' || e.key === 'PageDown' || e.key === 'PageUp')) {   // 다음·이전 탭
      e.preventDefault();
      cycleTab(e.key === 'PageUp' || (e.key === 'Tab' && e.shiftKey) ? -1 : 1);
    } else if (mod && !e.shiftKey && !e.altKey && /^[1-9]$/.test(e.key)) {   // Ctrl+1~8: 그 탭, Ctrl+9: 마지막 탭
      if (selectTabAt(Number(e.key))) e.preventDefault();
    } else if (e.altKey && !mod && !e.shiftKey && /^[1-5]$/.test(e.key)) {   // Alt+1~5: 그 순번의 문서 탭 (D64)
      if (docTabAt(Number(e.key))) e.preventDefault();
    } else if (mod && e.key === 'F4') {   // 문서 탭 닫기 (D64 — 프로젝트 탭은 Ctrl+W)
      e.preventDefault();
      closeDocTab();
    } else if (e.altKey && e.key === 'ArrowLeft') {
      e.preventDefault();
      back();
    } else if (e.altKey && e.key === 'ArrowRight') {
      e.preventDefault();
      forward();
    } else if (e.key === 'F5' && e.shiftKey && !mod) {   // 발표 — 지금 보는 슬라이드부터 (발표 문서를 슬라이드로 볼 때, D59)
      e.preventDefault();
      startPresent();
    } else if (e.key === 'F5') {
      e.preventDefault();
      manualRefresh();
    } else if (e.key === 'F1') {
      e.preventDefault();
      toggleManual();
    } else if (helpKey) {   // Ctrl+/
      e.preventDefault();
      toggleShortcuts();
    } else if (SPOT_KEYS[e.key] && !mod && !e.altKey && !e.shiftKey && spotlightOn() && !typing(e)) {
      e.preventDefault();
      moveSpotlight(SPOT_KEYS[e.key]);
    } else if (e.key === 'Escape') {
      if (closePalette() || closeInsert() || closeRename() || closeSettings() || closeShortcuts() || hideMenu() || closeLightbox() || closeFind() || closeManual()
        || stopSpotlight()) e.preventDefault();
    }
  });
  // 마우스 뒤로/앞으로 버튼
  window.addEventListener('mouseup', (e) => {
    if (inTerminal(e) || gatherOn() || presenting()) return;
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
    view.innerHTML = `<h1>${t('창과 연결하는 중입니다')}</h1><p>${t('이 화면이 계속되면 Lectern을 닫았다가 다시 실행해 주세요.')}</p>`;
  }, 4000);
  await new Promise((resolve) => window.addEventListener('pywebviewready', resolve, { once: true }));
  clearTimeout(slow);
}

async function boot() {
  translatePage();   // index.html 의 화면 글자를 설정 언어로 (D46)
  initPanes();   // 시작 화면 칸 — 연결을 기다리는 안내도 여기에
  await waitForBridge();
  try {
    S.config = await getJSON('/api/config');
  } catch {
    S.config = {};
  }
  await loadUserStyles();   // 내 스타일 (D53) — 고른 스타일이 내 것이면 목록이 있어야 입힐 수 있다
  initTheme();
  initUi();
  initToc();
  initFind();
  initFold();
  initSpotlight();
  initTextSize();
  initDocMenu();
  initChangeMarks();
  initSearch();
  initParts();   // initTree 앞에 — 탭을 바꿀 때 앞 탭의 모아 보기 상태를 먼저 남긴다
  initRecent();  // 같은 까닭 (트리가 사이드바 탭을 바꾸면 숨은 목록의 스크롤 위치를 읽지 못한다)
  initSettings();
  initHelp();
  initPosition();
  initResize();
  initPathLinks();
  initStatus();
  initOverview();
  initCodeView();
  initTree();
  initOthers();   // initTree 다음에 — 탭을 바꿀 때 트리가 그 탭의 거르기 글자를 먼저 되살린다
  initPalette();
  initNav();
  initTabs();
  initWatch();
  initTerminal();
  initEditor();
  initDocTabs();
  initBasket();
  initRename();
  initSlides();
  initPresent();
  initGather();
  bindToolbar();
  bindKeys();
  applyLayout();

  on('view', () => { updateNavButtons(); updateWindowTitle(); });
  on('show-sidebar', () => { if (S.config.sidebar_visible === false) toggleSidebar(); });

  await loadTabs();
  startWatch();
}

boot();
