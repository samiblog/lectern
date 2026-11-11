// 문서 탭 (D64·D67): 한 프로젝트 탭에서 문서를 20개까지 열어 두고 오간다. 문서 탭마다 칸(panes.js) 하나 — 화면·뒤로/앞으로 기록·스크롤·
// 편집 상자·목차·상태줄이 따로다. tab.panes 는 탭 차례, tab.pane 은 고른 문서 탭의 칸.
//
// - 문서 위의 문서 탭 줄(#lec-doctabs): 이름(트리와 같게 — 파일 이름이나 '제목' 버튼이면 제목), 저장하지 않은 편집 ●, ×(하나뿐이면 없음),
//   + (새 탭에 문서 열기 — 빠른 열기), 오른쪽 끝 ∨ (열린 문서 탭 목록 — 넘쳐 가려진 탭도 골라 간다, D67).
//   가운데 버튼으로 누르면 닫고, 우클릭은 닫기·다른 탭 닫기와 경로 메뉴.
// - 여는 곳은 모두 'open' 이벤트 (트리·목록·링크·검색·빠른 열기…): 그 문서가 다른 문서 탭에 열려 있으면 그 탭으로, newTab(Ctrl+누르기·가운데 버튼·
//   우클릭 '새 탭에서 열기'·+)이면 새 문서 탭에서, 아니면 지금 탭에서. 20개가 차 있으면 가장 오래 안 본 탭(저장하지 않은 편집이 없는 것)에서 연다.
//   사이드바 목록에서 두 번 누르면(twice) 첫 누르기가 지금 탭에서 연 것을 새 문서 탭으로 옮긴다 (openTwice, D67).
// - 키 (main.js): Alt+1~8 그 순번의 문서 탭·Alt+9 마지막 문서 탭, Ctrl+F4 문서 탭 닫기 — 프로젝트 탭의 Ctrl+1~9·Ctrl+Tab·Ctrl+W 는 그대로.
// - 다음 실행: position.js 가 열어 둔 문서 탭(md·html 문서)을 서버에 알리고(docs), 탭을 처음 열 때 되살린다 (restoreDocTabs) —
//   고른 탭만 그리고 나머지는 고를 때 그린다 (pane.deferred).

import { S, on, emit } from './store.js';
import { createPane, removePane, selectPane } from './panes.js';
import { navigate, refreshView, seedScroll } from './nav.js';
import { goToPart } from './toc.js';
import { closeEditor } from './editor.js';
import { native, postJSON } from './api.js';
import { solo, soloQuery } from './solo.js';
import { labelOf, tipOf, pathMenuItems } from './tree.js';
import { openPalette } from './palette.js';
import { showMenu } from './ui.js';
import { fileIcon, folderIcon } from './icons.js';
import { html, setHtml } from './html.js';
import { $, basename, toast, middleClickOpens, findAnchor } from './util.js';
import { t } from './i18n.js';

export const MAX_DOCS = 20;   // 서버 config.MAX_DOC_TABS 와 같게 (D67 — v0.35.0 은 5개)

// 문서 탭이 보이는 것: 그린 화면, 아직 그리지 않은 것(되살린 탭 — deferred), 여는 중인 것(coming)
const viewOf = (pane) => pane.current || pane.deferred || pane.coming;

/** 탭(tab)에서 target(문서·코드 화면)을 보고 있는 문서 탭의 칸 */
export function docPaneOf(tab, target) {
  if (!tab || (target.type !== 'doc' && target.type !== 'code')) return null;
  return tab.panes.find((p) => { const v = viewOf(p); return v?.type === target.type && v.path === target.path; }) || null;
}

/** 문서 탭을 고른다. 아직 그리지 않은 탭(되살린 것)이면 그리고, 숨은 동안 바뀌었으면 다시 그린다 */
export async function selectDocTab(pane) {
  const { tab } = pane;
  if (!tab?.panes.includes(pane)) return;
  pane.used = Date.now();
  tab.pane = pane;
  if (tab === S.tab && S.pane !== pane) {
    selectPane(pane);
    // 편집 중인 탭이면 편집기에 (Ctrl+S 가 저장하게), 아니면 PageUp·PageDown·방향키가 이 문서를 스크롤하게
    if (pane.editor) pane.editor.cm.focus();
    else pane.scroller.focus({ preventScroll: true });
  }
  render();
  if (pane.deferred) {
    const target = pane.deferred;
    pane.deferred = null;
    await navigate(target, { pane, restoreScroll: true });
  } else if (pane.stale) {
    await refreshView(pane);
  }
}

/**
 * 그 파일을 편집 중인 탭(pane — 고른 뒤)에서 줄(line)·앵커(hash)로 간다 — 다시 그리지 않고 편집기가 그곳으로 (D55).
 * 다시 그리면(navigate) 편집 상자를 떠나는 것이라 편집을 닫거나 버릴지 묻게 된다
 */
function goInEditor(pane, target) {
  if (target.line) emit('edit', { line: target.line });
  else if (target.hash) {
    const frame = pane.view.querySelector('iframe.lec-html');
    const el = findAnchor(frame?.contentDocument?.body || pane.view, target.hash);
    if (el) goToPart(el);
  }
  return true;
}

/** 칸을 문서 탭에서 뺀다 (그 자리의 화면도 없앤다) */
function dropPane(pane) {
  const { tab } = pane;
  tab.panes = tab.panes.filter((p) => p !== pane);
  removePane(pane);
}

/** 문서 탭이 차 있을 때 비울 탭: keep 이 아닌 것 가운데 저장하지 않은 편집이 없고 가장 오래 안 본 것 (없으면 undefined) */
const oldestSpare = (tab, keep) => tab.panes.filter((p) => p !== keep && !p.editor?.dirty).sort((a, b) => (a.used || 0) - (b.used || 0))[0];
const fullMessage = () => t('문서 탭은 {n}개까지입니다 — 모두 저장하지 않은 편집이 있어 바꿀 탭이 없습니다. 탭 하나를 닫으세요 (Ctrl+W)', { n: MAX_DOCS });

/**
 * 새 문서 탭에서 연다 — 그 문서가 이미 다른 탭에 열려 있으면 그 탭으로. 20개가 차 있으면 가장 오래 안 본 탭(저장하지 않은 편집이 없는 것)에서.
 * 그린 뒤에 고른다 (빈 칸이 잠깐 보이지 않게). 연 칸, 열지 못했으면 null
 */
export async function openInNewTab(target) {
  const tab = S.tab;
  if (!tab) return null;
  const open = docPaneOf(tab, target);
  if (open && target.behind) return open;
  if (open) {
    await selectDocTab(open);
    if (target.hash || target.line) {
      if (open.editor) goInEditor(open, target);
      else await navigate(target, { pane: open });
    }
    return open;
  }
  let pane;
  let made = false;
  if (tab.panes.length < MAX_DOCS) {
    pane = createPane(tab);
    // 지금 탭 오른쪽에. 뒤에서 잇따라 열면 연 차례대로 (브라우저처럼 — 앞서 뒤에서 연 탭의 오른쪽에)
    const after = target.behind && tab.behindOf === tab.pane && tab.panes.includes(tab.behindLast) ? tab.behindLast : tab.pane;
    tab.panes.splice(tab.panes.indexOf(after) + 1, 0, pane);
    if (target.behind) Object.assign(tab, { behindOf: tab.pane, behindLast: pane });
    made = true;
  } else {
    pane = oldestSpare(tab, tab.pane);
    if (!pane) {
      toast(fullMessage(), 'error', 5000);
      return null;
    }
    if (pane.editor) closeEditor(pane, { ask: false, sync: false });
    pane.deferred = null;
    toast(t('문서 탭은 {n}개까지라 가장 오래 안 본 탭에서 열었습니다', { n: MAX_DOCS }));
  }
  pane.used = Date.now();
  if (target.behind && made) {   // 뒤에서: 이름만 두고 고를 때 그린다 (되살린 탭처럼)
    pane.deferred = { type: target.type, path: target.path, hash: target.hash, line: target.line };
    render();
    emit('doctabs', tab);   // 다음 실행에 되살릴 문서 탭 목록 (position.js)
    return pane;
  }
  pane.coming = target;
  render();
  const from = S.pane;
  const ok = await navigate(target, { pane });
  pane.coming = null;
  if (!ok || !tab.panes.includes(pane)) {
    if (made && tab.panes.includes(pane)) dropPane(pane);
    render();
    return null;
  }
  if (S.pane === from && !target.behind) await selectDocTab(pane);   // 그리는 동안 다른 탭을 골랐으면 그 선택을 빼앗지 않는다 (새 탭은 뒤에 남는다)
  else render();
  return pane;
}

/** 지금 탭이 문서·코드를 보여 주는지 — 그때만 새 문서 탭으로 연다 (D91). 폴더 개요·빈 탭에는 지킬 문서가 없어 그 자리에서 */
const holdsDoc = (pane) => {
  const v = pane && viewOf(pane);
  return v?.type === 'doc' || v?.type === 'code';
};

/**
 * 화면을 연다 ('open' 이벤트 — 트리·목록·링크·검색·빠른 열기): 그 문서·코드가 다른 문서 탭에 열려 있으면 그 탭으로,
 * newTab 이면 새 문서 탭에서 (behind 면 뒤에서, force 면 폴더 개요에서도), 아니면 지금 탭에서 (nav.js 의 navigate). 열었으면 true
 */
export async function openTarget(target) {
  const tab = S.tab;
  if (tab && !solo && target.type === 'doc' && native.has('open_window') && (target.deck || tab.fileMap.get(target.path)?.deck)) {
    // Lectern 슬라이드는 슬라이드 창에서 (D96 — 이미 열려 있으면 서버가 그 창을 앞으로 가져온다). 이 칸에는 열리지 않았으니 false — 부르는 쪽이 이 칸에서 이어서 하지 않게
    await openWindow(tab, target.deckLine ? { ...target, line: target.deckLine } : target);
    return false;
  }
  if (tab && (target.type === 'doc' || target.type === 'code')) {
    const open = docPaneOf(tab, target);
    if (open && target.behind) return true;   // 이미 열려 있다 — 보던 문서를 그대로
    // 다른 문서 탭에 열려 있으면 그 탭으로. 지금 탭에서 편집 중인 그 파일이면 떠나지 않는다 (담기의 '문서에서 보기' 등)
    if (open && (open !== S.pane || open.editor)) {
      if (open !== S.pane) await selectDocTab(open);
      if (!target.hash && !target.line) return true;
      return open.editor ? goInEditor(open, target) : navigate(target, { pane: open });
    }
    if (target.newTab && !open && (target.behind || target.force || holdsDoc(S.pane))) return !!(await openInNewTab(target));
  }
  return navigate(target);
}

/** 문서 탭을 닫는다 (하나뿐이면 닫지 않는다). 저장하지 않은 편집이 있으면 묻는다. 닫았으면 true */
export function closeDocTab(pane = S.pane) {
  const tab = pane?.tab;
  if (!tab || tab.panes.length < 2 || !tab.panes.includes(pane)) return false;
  if (pane.editor && !closeEditor(pane, { sync: false })) return false;
  rememberClosed(pane);
  const i = tab.panes.indexOf(pane);
  emit('doctabs', tab);   // 다음 실행에 되살릴 문서 탭 목록 (position.js — 고르지 않은 탭을 닫으면 view 이벤트가 없다)
  if (tab.pane === pane) {
    const next = tab.panes[i + 1] || tab.panes[i - 1];   // 오른쪽, 없으면 왼쪽
    tab.pane = next;
    if (tab === S.tab) selectDocTab(next);
  }
  dropPane(pane);
  render();
  return true;
}

/**
 * 문서 탭 줄의 닫기 (D127): 탭이 여럿이면 그 탭을 닫고, 하나뿐이면 그 탭을 프로젝트 폴더의 개요로 바꾼다 — 프로젝트를 처음 열었을 때와 같은 화면.
 * 칸은 늘 하나가 남는다 (칸이 없는 프로젝트 탭은 만들지 않는다 — panes.js·nav.js 가 칸 하나를 기대한다). 이미 폴더 개요면 닫을 것이 없다 (false).
 * 독립창의 마지막 탭은 창을 닫는다
 */
export function closeTab(pane = S.pane) {
  const tab = pane?.tab;
  if (!tab || !tab.panes.includes(pane)) return false;
  if (tab.panes.length > 1) return closeDocTab(pane);
  if (solo) {
    if (!pane.editor || closeEditor(pane, { sync: false })) native.closeWindow();
    return true;
  }
  if (!holdsFile(pane)) return false;
  if (pane.editor && !closeEditor(pane, { sync: false })) return false;
  rememberClosed(pane);
  navigate({ type: 'overview', path: '' }, { pane });
  return true;
}

/** 칸이 문서·코드 같은 파일을 보이는지 — 폴더 개요·빈 칸이 아닌지 */
const holdsFile = (pane) => { const v = viewOf(pane); return !!v && v.type !== 'overview'; };

/** 닫은 문서 탭을 기억한다 (Ctrl+Shift+T — D91). 프로젝트 탭마다, 그 탭이 열려 있는 동안만 */
function rememberClosed(pane) {
  const v = viewOf(pane);
  if (v?.type !== 'doc' && v?.type !== 'code') return;
  const list = (pane.tab.closedDocs ??= []);
  list.push({ type: v.type, path: v.path });
  list.splice(0, Math.max(0, list.length - MAX_DOCS));
}

/** Ctrl+Shift+T: 마지막에 닫은 문서 탭을 다시 연다. 지워진 파일은 건너뛴다 */
export async function reopenDocTab() {
  const tab = S.tab;
  const list = tab?.closedDocs || [];
  while (list.length) {
    const target = list.pop();
    if (target.type === 'code' || tab.fileMap.has(target.path)) return !!(await openInNewTab(target));
  }
  toast(t('다시 열 문서 탭이 없습니다'));
  return false;
}

let otherWindows = [];   // 서버가 알려 준 다른 창들 [{id, project, title}] (D95)

/** 다른 창에 보일 이 창의 이름 — 보고 있는 문서 */
export function windowName() {
  const v = S.pane && viewOf(S.pane);
  const name = v?.path ? basename(v.path) : S.tab?.name || '';
  const more = (S.tab?.panes.length || 1) - 1;
  return more ? t('{name} 외 {n}개', { name, n: more }) : name;
}

/** 이 프로젝트의 다른 독립창 */
const peers = (tab) => otherWindows.filter((w) => w.id && w.project === tab.id);

/** 칸을 떠나보낸 뒤: 다른 탭이 있으면 탭만 닫고, 마지막 탭이면 독립창은 닫고 메인 창은 폴더 개요로 */
async function leavePane(pane) {
  if (pane.tab.panes.length > 1) closeDocTab(pane);
  else if (solo) native.closeWindow();
  else await navigate({ type: 'overview', path: '' }, { pane });
}

/** 문서 탭을 다른 창으로 보낸다 (D95). to: 창 id, 메인 창은 빈 값 */
export async function sendToWindow(pane, to) {
  const v = viewOf(pane);
  if (pane.editor && !closeEditor(pane, { sync: false })) return false;
  let sent = false;
  try {
    sent = (await postJSON('/api/window-send', { to, type: v.type, path: v.path, top: Math.round(pane.scroller.scrollTop) })).ok;
  } catch { /* 아래에서 알린다 */ }
  if (!sent) {
    toast(t('그 창이 닫혀 보내지 못했습니다'), 'error');
    return false;
  }
  await leavePane(pane);
  return true;
}

/** 다른 창이 보낸 것을 받는다: 문서는 새 문서 탭에서, 터미널로 보낼 글·메모는 고른 프로젝트의 것일 때만 */
async function receive({ type, path, top, term, note, p, stay, hash, line, to }) {
  if (type === 'renamed') {
    const tab = S.tabs.find((x) => x.id === p);
    if (tab) emit('file-renamed', { tab, path, to });
    return;
  }
  if (type === 'deleted') {
    const tab = S.tabs.find((x) => x.id === p);
    if (tab) emit('file-deleted', { tab, path });
    return;
  }
  if (term != null || note) {
    if (p !== S.tab?.id) toast(t('메인 창이 다른 프로젝트를 보고 있어 받지 않았습니다'), 'error');
    else if (note) emit('new-note', note);
    else emit(stay ? 'term-paste-stay' : 'term-paste', term);
    return;
  }
  const open = docPaneOf(S.tab, { type, path });   // 슬라이드 창이 이미 연 발표 (D96)
  if (open) {
    await selectDocTab(open);
    if (hash || (line && type === 'code')) await navigate({ type, path, hash, line }, { pane: open });
  } else {
    const pane = await openInNewTab({ type, path, hash, line });
    if (!pane) return;
    if (top) pane.scroller.scrollTop = top;
  }
  if (line && type === 'doc') emit('go-line', { line });   // 문서 화면은 navigate 의 line 을 듣지 않는다 (코드 화면만)
}

/** 이 창이 지금 연 Lectern 슬라이드들 (D96) — 서버가 '이 발표의 창'을 찾는 데 쓴다 */
export function windowDecks() {
  const tab = S.tab;
  return tab ? openDocs(tab).filter((path) => tab.fileMap.get(path)?.deck) : [];
}

/** 문서를 독립창에서 연다 (D95). 띄웠으면 true. fresh: 이 발표의 창이 있어도 새 창으로 (탭을 옮길 때) */
async function openWindow(tab, target, top = 0, fresh = false) {
  const deck = target.deck || !!tab.fileMap.get(target.path)?.deck;
  const done = await native.openWindow(soloQuery(tab.id, target, top, deck, fresh));
  if (!done) toast(t('새 창을 열지 못했습니다. 안 쓰는 창을 닫고 다시 하세요'), 'error');
  return done;
}

/**
 * 문서 탭을 독립창으로 옮긴다 (D95 — 브라우저의 '새 창으로 탭 이동'). 저장하지 않은 편집이 있으면 먼저 묻는다.
 * 하나뿐인 문서 탭이면 메인 창은 폴더 개요로. 독립창의 하나뿐인 탭은 옮길 까닭이 없다.
 */
export async function moveToWindow(pane = S.pane) {
  const v = pane && viewOf(pane);
  if (v?.type !== 'doc' && v?.type !== 'code') {
    toast(t('문서나 코드를 볼 때 새 창으로 옮길 수 있습니다'));
    return false;
  }
  const only = pane.tab.panes.length < 2;
  if (solo && only) {
    toast(t('이 창에 문서 탭이 하나뿐입니다'));
    return false;
  }
  if (pane.editor && !closeEditor(pane, { sync: false })) return false;
  if (!await openWindow(pane.tab, v, pane.scroller.scrollTop, true)) return false;
  await leavePane(pane);
  return true;
}

/** Ctrl+W: 지금 문서 탭을 닫는다. 하나뿐이면 폴더 개요로 (D127), 이미 폴더 개요면 알린다 (프로젝트는 Ctrl+Shift+W). 독립창이면 창을 닫는다 */
export function closeDocTabKey() {
  if (!S.tab) return false;
  if (closeTab()) return true;
  if (S.tab.panes.length < 2 && !S.pane?.editor) toast(t('열린 문서가 없습니다 — 프로젝트를 닫으려면 Ctrl+Shift+W 를 누르세요'));
  return false;
}

/** Ctrl+Tab·Ctrl+PageDown: 다음(+1)·이전(-1) 문서 탭. 끝에서는 반대쪽 끝으로 */
export function cycleDocTab(step) {
  const tab = S.tab;
  if (!tab || tab.panes.length < 2) return false;
  const n = tab.panes.length;
  selectDocTab(tab.panes[(tab.panes.indexOf(tab.pane) + step + n) % n]);
  return true;
}

/** 이 탭 말고 모두 닫기 (저장하지 않은 편집이 있는 탭은 묻는다 — 남기기로 하면 그 탭은 남는다) */
function closeOthers(keep) {
  selectDocTab(keep);
  for (const p of keep.tab.panes.filter((x) => x !== keep)) closeDocTab(p);
}

/** Alt+1~8: 그 순번의 문서 탭, Alt+9: 마지막 문서 탭 (프로젝트 탭의 Ctrl+1~9 처럼). 없으면 false */
export function docTabAt(n) {
  const panes = S.tab?.panes || [];
  const pane = n === 9 ? panes[panes.length - 1] : panes[n - 1];
  if (pane) selectDocTab(pane);
  return !!pane;
}

/**
 * 탭을 처음 열 때 (tabs.js — 마지막 문서를 tab.pane 에 그린 뒤): 서버가 기억한 문서 탭들(position.docs, 탭 차례)을 되살린다.
 * 그린 문서는 그 자리에, 나머지는 고를 때 그린다. 없어진 문서는 뺀다
 */
export function restoreDocTabs(tab, pos) {
  const docs = (pos?.docs || []).filter((p) => tab.fileMap.has(p)).slice(0, MAX_DOCS);
  if (docs.length < 2) return;
  const shown = tab.pane.current?.type === 'doc' ? tab.pane.current.path : null;
  const panes = docs.map((path) => {
    if (path === shown) return tab.pane;
    const pane = createPane(tab);
    pane.deferred = { type: 'doc', path };
    seedScroll(pane, pos);
    return pane;
  });
  if (!panes.includes(tab.pane)) {   // 그린 화면이 기억한 문서가 아님 (폴더 개요 등) — 맨 앞에 두고 넘치는 것은 뺀다
    panes.unshift(tab.pane);
    for (const extra of panes.splice(MAX_DOCS)) removePane(extra);
  }
  tab.panes = panes;
  tab.pane.used = Date.now();
  render();
}

/** 열어 둔 문서 탭들의 문서 (탭 차례 — md·html 문서만, 다음 실행에 되살린다. position.js) */
export const openDocs = (tab) => tab.panes.map((p) => viewOf(p)).filter((v) => v?.type === 'doc' && tab.fileMap.has(v.path)).map((v) => v.path);

// ---- 문서 탭 줄 -------------------------------------------------------------------

/** 문서 탭의 아이콘·이름·설명 (모두 펼치기의 칸 머리도 — spread.js) */
export function describe(pane) {
  const v = viewOf(pane);
  const tab = pane.tab;
  if (!v) return { icon: folderIcon(), name: t('빈 탭'), tip: '' };
  if (v.type === 'overview') return { icon: folderIcon(), name: v.path ? basename(v.path) : tab.name, tip: t('폴더 개요: {path}', { path: v.path || tab.name }) };
  const f = v.type === 'doc' ? tab.fileMap.get(v.path) : null;
  return { icon: fileIcon(basename(v.path), f?.kind, f?.deck), name: f ? labelOf(f) : basename(v.path), tip: f ? tipOf(f) : v.path };
}

function render() {
  const tab = S.tab;
  const strip = $('#lec-doctabs');
  strip.hidden = !tab;
  $('#lec-panes').classList.toggle('has-doctabs', !!tab);
  if (!tab) return;
  const n = tab.panes.length;
  setHtml($('#lec-doctab-list'), tab.panes.map((p, i) => {
    const active = p === tab.pane;
    const { icon, name, tip } = describe(p);
    const dirty = p.editor?.dirty ? html`<span class="dirty" title="${t('저장하지 않은 편집이 있습니다')}">●</span>` : '';
    const close = n > 1 || (!solo && holdsFile(p)) ? html`<button type="button" class="tab-close" title="${t('문서 탭 닫기 (Ctrl+W)')}" aria-label="${t('{name} 문서 탭 닫기', { name })}"><svg><use href="#i-close"/></svg></button>` : '';
    const key = keyOf(i, n);
    return [html`<div class="doc-tab${active ? ' active' : ''}" role="tab" aria-selected="${active}" tabindex="0" data-i="${i}" data-path="${viewOf(p)?.path || ''}" title="${key ? `${tip}\n${key}` : tip}">`, html`${icon}<span class="name">${name}</span>${dirty}${close}</div>`];
  }));
  const full = n >= MAX_DOCS;
  $('#lec-doctab-new').title = full ? t('새 탭에 문서 열기 — {n}개가 차 있어 가장 오래 안 본 탭에서 엽니다', { n: MAX_DOCS })
    : t('새 탭에 문서 열기 (문서를 Ctrl+클릭·두 번 누르기·가운데 버튼으로 눌러도)');
  const all = $('#lec-doctab-all');
  all.title = t('열린 문서 탭 {n}개 — 골라서 가기', { n });
  all.querySelector('.n').textContent = n > 1 ? n : '';
  $('#lec-doctab-list .doc-tab.active')?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  emit('doctab-list', tab);   // 모두 펼치기(spread.js, D73)가 칸을 다시 놓는다 — 탭이 생기거나 닫히거나 이름·고른 탭이 바뀜
}

/** i 번째(0부터) 문서 탭의 단축키 — Alt+1~8, 마지막 탭은 Alt+9 (n: 탭 수) */
const keyOf = (i, n) => (i < 8 ? `Alt+${i + 1}` : i === n - 1 ? 'Alt+9' : '');

/**
 * 문서 탭 줄 오른쪽 끝 ∨ 의 목록 (D67): 열린 문서 탭을 탭 차례로 — 아이콘·이름·경로, 고른 탭은 강조. 고르면 그 탭으로.
 * 탭이 많아 줄에서 가려진 것도 여기서 고른다
 */
function listMenu(btn) {
  const tab = S.tab;
  if (!tab) return;
  const n = tab.panes.length;
  /** @type {MenuItem[]} */
  const items = [{ header: t('열린 문서 탭 {n}개 (최대 {max}개)', { n, max: MAX_DOCS }) }];
  tab.panes.forEach((p, i) => {
    const v = viewOf(p);
    const { icon, name } = describe(p);
    const where = v?.type === 'overview' ? t('폴더 개요: {path}', { path: v.path || tab.name }) : v?.path || '';
    const key = keyOf(i, n);
    items.push({
      icon, label: p.editor?.dirty ? `${name} ●` : name, hint: key ? `${where} · ${key}` : where, current: p === tab.pane, action: () => selectDocTab(p),
    });
  });
  if (n > 1) items.push('-', { label: t('다른 문서 탭 모두 닫기'), action: () => closeOthers(tab.pane) });
  const r = btn.getBoundingClientRect();
  showMenu(r.right, r.bottom + 2, items);
  // 단추의 오른쪽 끝에 맞춘다 — 목차·터미널이 열려 있으면 단추가 창 오른쪽 끝이 아니다
  const menu = $('#lec-menu');
  menu.style.left = `${Math.max(8, r.right - menu.offsetWidth)}px`;
  menu.querySelector('button[aria-current="true"]')?.focus();
}

const paneAt = (el) => S.tab?.panes[Number(el?.closest('.doc-tab')?.dataset.i)] || null;

/** 문서 탭의 우클릭 메뉴 (모두 펼치기의 칸 머리도 — spread.js) */
export function tabMenu(pane) {
  const v = viewOf(pane);
  /** @type {MenuItem[]} */
  const items = [{ header: v?.path || pane.tab.name }];
  if (pane.tab.panes.length > 1) {
    items.push({ label: t('문서 탭 닫기'), hint: pane === S.pane ? 'Ctrl+W' : t('가운데 버튼'), action: () => closeDocTab(pane) },
      { label: t('다른 문서 탭 모두 닫기'), action: () => closeOthers(pane) });
  } else if (!solo && holdsFile(pane)) {
    items.push({ label: t('문서 탭 닫기'), hint: 'Ctrl+W', tip: t('폴더 개요로 돌아갑니다'), action: () => closeTab(pane) });
  }
  if (v?.path && (v.type === 'doc' || v.type === 'code')) {
    if (solo) items.push({ label: t('메인 창으로 보내기'), action: () => sendToWindow(pane, '') });
    for (const w of peers(pane.tab)) items.push({ label: t('{name} 창으로 보내기', { name: w.title }), action: () => sendToWindow(pane, w.id) });
    if (!solo || pane.tab.panes.length > 1) items.push({ label: t('새 창으로 옮기기'), hint: pane === S.pane ? 'Ctrl+Shift+N' : '', action: () => moveToWindow(pane) });
    items.push('-', ...pathMenuItems(v.path, true));
  }
  return items;
}

export function initDocTabs() {
  on('open-window', (target) => { if (S.tab) openWindow(S.tab, target); });
  on('window-news', async (d) => {
    otherWindows = d.windows || [];
    for (const item of d.inbox || []) await receive(item);
  });
  if (solo) addEventListener('pagehide', () => native.tellGone(solo.id));
  const list = $('#lec-doctab-list');
  list.addEventListener('click', (e) => {
    const pane = paneAt(e.target);
    if (!pane) return;
    if (e.target.closest('.tab-close')) closeTab(pane);
    else selectDocTab(pane);
  });
  list.addEventListener('mousedown', (e) => { if (e.button === 1) e.preventDefault(); });   // 가운데 버튼의 자동 스크롤 대신
  list.addEventListener('auxclick', (e) => {   // 가운데 버튼으로 누르면 닫기 (프로젝트 탭처럼)
    const pane = e.button === 1 && paneAt(e.target);
    if (pane) closeTab(pane);
  });
  list.addEventListener('keydown', (e) => {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('.doc-tab')) {
      e.preventDefault();
      selectDocTab(paneAt(e.target));
    }
  });
  list.addEventListener('contextmenu', (e) => {
    const pane = paneAt(e.target);
    if (!pane) return;
    e.preventDefault();
    showMenu(e.clientX, e.clientY, tabMenu(pane));
  });
  list.addEventListener('wheel', (e) => {   // 넘치면 휠로 가로 스크롤
    if (!e.deltaY || list.scrollWidth <= list.clientWidth) return;
    list.scrollLeft += e.deltaY;
    e.preventDefault();
  }, { passive: false });
  $('#lec-doctab-new').addEventListener('click', () => openPalette({ newTab: true }));
  $('#lec-doctab-all').addEventListener('click', (e) => listMenu(e.currentTarget));
  // 본문의 링크·경로 표기·폴더 개요의 문서를 가운데 버튼으로 누르면 새 문서 탭에서 (Ctrl+누르기처럼 — doc.js·pathlink.js·overview.js)
  middleClickOpens($('#lec-panes'), 'a[href], area[href], a.path-link, .overview button[data-doc]');
  on('open', (target) => { openTarget(target); });
  for (const ev of ['tab', 'pane', 'view', 'titles', 'tree', 'editor']) on(ev, render);
  render();
}
