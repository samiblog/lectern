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
import { copyFolds } from './fold.js';
import { closeEditor } from './editor.js';
import { labelOf, tipOf, pathMenuItems } from './tree.js';
import { openPalette } from './palette.js';
import { showMenu } from './ui.js';
import { fileIcon, folderIcon } from './icons.js';
import { $, esc, basename, toast, middleClickOpens, findAnchor } from './util.js';
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
const fullMessage = () => t('문서 탭은 {n}개까지입니다 — 모두 저장하지 않은 편집이 있어 바꿀 탭이 없습니다. 탭 하나를 닫으세요 (Ctrl+F4)', { n: MAX_DOCS });

/**
 * 새 문서 탭에서 연다 — 그 문서가 이미 다른 탭에 열려 있으면 그 탭으로. 20개가 차 있으면 가장 오래 안 본 탭(저장하지 않은 편집이 없는 것)에서.
 * 그린 뒤에 고른다 (빈 칸이 잠깐 보이지 않게). 연 칸, 열지 못했으면 null
 */
export async function openInNewTab(target) {
  const tab = S.tab;
  if (!tab) return null;
  const open = docPaneOf(tab, target);
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
    tab.panes.splice(tab.panes.indexOf(tab.pane) + 1, 0, pane);   // 지금 탭 오른쪽에
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
  if (S.pane === from) await selectDocTab(pane);   // 그리는 동안 다른 탭을 골랐으면 그 선택을 빼앗지 않는다 (새 탭은 뒤에 남는다)
  else render();
  return pane;
}

// 지금 탭에서 마지막으로 연 것 {target, pane, from: 앞 화면·뒤로 기록, at, done: 그리기} — 두 번 누르기가 새 문서 탭으로 옮긴다 (openTwice)
let lastOpen = null;
const TWICE_MS = 1500;   // 첫 누르기에서 이만큼 안에 온 두 번째 누르기만 (Windows 의 두 번 누르기 간격은 기본 0.5초)

/**
 * 화면을 연다 ('open' 이벤트 — 트리·목록·링크·검색·빠른 열기): 그 문서·코드가 다른 문서 탭에 열려 있으면 그 탭으로,
 * newTab 이면 새 문서 탭에서, twice(두 번 누르기 — D67)면 openTwice, 아니면 지금 탭에서 (nav.js 의 navigate). 열었으면 true
 */
export async function openTarget(target) {
  const tab = S.tab;
  if (target.twice && tab && (target.type === 'doc' || target.type === 'code')) return openTwice(target);
  lastOpen = null;
  if (tab && (target.type === 'doc' || target.type === 'code')) {
    const open = docPaneOf(tab, target);
    // 다른 문서 탭에 열려 있으면 그 탭으로. 지금 탭에서 편집 중인 그 파일이면 떠나지 않는다 (담기의 '문서에서 보기' 등)
    if (open && (open !== S.pane || open.editor)) {
      if (open !== S.pane) await selectDocTab(open);
      if (!target.hash && !target.line) return true;
      return open.editor ? goInEditor(open, target) : navigate(target, { pane: open });
    }
    if (target.newTab && !open) return !!(await openInNewTab(target));
  }
  const pane = S.pane;
  const done = navigate(target);
  if (pane?.tab && pane.current) lastOpen = { target, pane, from: { view: pane.current, history: pane.history.slice(), hIndex: pane.hIndex }, at: Date.now(), done };
  return done;
}

/**
 * 두 번 누르기 (D67 — 사이드바 목록): 첫 누르기는 지금 탭에서 열었다 — 그 탭을 새 문서 탭으로 하고 제자리에는 앞 화면을 되살려
 * 새 탭에서 연 것과 같게 한다 (splitOff — 그린 문서를 다시 그리지 않는다). 첫 누르기가 그 문서의 탭으로 갔거나 이미 보던 문서면 그대로,
 * 지금 탭에서 열지 못했으면(편집을 떠나지 않기로 함 등) 새 탭에서 연다
 */
async function openTwice(target) {
  const tab = S.tab;
  const last = lastOpen;
  lastOpen = null;
  const same = (v) => v?.type === target.type && v.path === target.path;
  if (last && last.pane.tab === tab && same(last.target) && Date.now() - last.at < TWICE_MS) {
    await last.done;   // 첫 누르기의 그리기가 끝나기를
    const { pane, from } = last;
    if (tab.panes.includes(pane) && same(pane.current) && !same(from.view)) return splitOff(pane, from);
  }
  const open = docPaneOf(tab, target);
  if (open) {
    if (open !== S.pane) await selectDocTab(open);
    return true;
  }
  return !!(await openInNewTab(target));
}

/**
 * 칸(pane — 두 번 누르기의 첫 누르기가 연 화면)을 새 문서 탭으로 하고, 그 왼쪽(제자리)에 앞 화면(from — 그 화면·뒤로 기록·스크롤)의
 * 문서 탭을 새로 놓는다. 새 탭은 뒤로 기록이 없다 (새 탭에서 연 것처럼). 20개가 차 있으면 가장 오래 안 본 탭을 닫는다
 */
function splitOff(pane, from) {
  const { tab } = pane;
  if (tab.panes.length >= MAX_DOCS) {
    const spare = oldestSpare(tab, pane);
    if (!spare) {
      toast(fullMessage(), 'error', 5000);
      return true;   // 지금 탭에서 연 채로 둔다
    }
    if (spare.editor) closeEditor(spare, { ask: false, sync: false });
    dropPane(spare);
    toast(t('문서 탭은 {n}개까지라 가장 오래 안 본 탭을 닫았습니다', { n: MAX_DOCS }));
  }
  const prev = createPane(tab);
  Object.assign(prev, { history: from.history, hIndex: from.hIndex, scrollPos: new Map(pane.scrollPos), used: Date.now() - 1, coming: from.view });
  copyFolds(pane, prev);
  tab.panes.splice(tab.panes.indexOf(pane), 0, prev);
  Object.assign(pane, { history: [pane.current], hIndex: 0, wanted: null, used: Date.now() });
  render();
  emit('doctabs', tab);   // 다음 실행에 되살릴 문서 탭 목록 (position.js)
  // 앞 화면은 숨은 채 바로 그려 둔다 (돌아가면 곧바로 보이게). 그리지 못했으면 고를 때 다시
  navigate(from.view, { pane: prev, restoreScroll: true }).then((ok) => {
    prev.coming = null;
    if (!ok && !prev.current && tab.panes.includes(prev)) prev.deferred = from.view;
    render();
  });
  return true;
}

/** 문서 탭을 닫는다 (하나뿐이면 닫지 않는다). 저장하지 않은 편집이 있으면 묻는다. 닫았으면 true */
export function closeDocTab(pane = S.pane) {
  const tab = pane?.tab;
  if (!tab || tab.panes.length < 2 || !tab.panes.includes(pane)) return false;
  if (pane.editor && !closeEditor(pane, { sync: false })) return false;
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

/** 문서 탭의 아이콘·이름·설명 */
function describe(pane) {
  const v = viewOf(pane);
  const tab = pane.tab;
  if (!v) return { icon: folderIcon(), name: t('빈 탭'), tip: '' };
  if (v.type === 'overview') return { icon: folderIcon(), name: v.path ? basename(v.path) : tab.name, tip: t('폴더 개요: {path}', { path: v.path || tab.name }) };
  const f = v.type === 'doc' ? tab.fileMap.get(v.path) : null;
  return { icon: fileIcon(basename(v.path), f?.kind), name: f ? labelOf(f) : basename(v.path), tip: f ? tipOf(f) : v.path };
}

function render() {
  const tab = S.tab;
  const strip = $('#lec-doctabs');
  strip.hidden = !tab;
  $('#lec-panes').classList.toggle('has-doctabs', !!tab);
  if (!tab) return;
  const n = tab.panes.length;
  $('#lec-doctab-list').innerHTML = tab.panes.map((p, i) => {
    const active = p === tab.pane;
    const { icon, name, tip } = describe(p);
    const dirty = p.editor?.dirty ? `<span class="dirty" title="${esc(t('저장하지 않은 편집이 있습니다'))}">●</span>` : '';
    const close = n > 1 ? `<button type="button" class="tab-close" title="${esc(t('문서 탭 닫기 (Ctrl+F4)'))}" aria-label="${esc(t('{name} 문서 탭 닫기', { name }))}"><svg><use href="#i-close"/></svg></button>` : '';
    const key = keyOf(i, n);
    return `<div class="doc-tab${active ? ' active' : ''}" role="tab" aria-selected="${active}" tabindex="0" data-i="${i}" data-path="${esc(viewOf(p)?.path || '')}" title="${esc(key ? `${tip}\n${key}` : tip)}">`
      + `${icon}<span class="name">${esc(name)}</span>${dirty}${close}</div>`;
  }).join('');
  const full = n >= MAX_DOCS;
  $('#lec-doctab-new').title = full ? t('새 탭에 문서 열기 — {n}개가 차 있어 가장 오래 안 본 탭에서 엽니다', { n: MAX_DOCS })
    : t('새 탭에 문서 열기 (문서를 Ctrl+클릭·두 번 누르기·가운데 버튼으로 눌러도)');
  const all = $('#lec-doctab-all');
  all.title = t('열린 문서 탭 {n}개 — 골라서 가기', { n });
  all.querySelector('.n').textContent = n > 1 ? n : '';
  $('#lec-doctab-list .doc-tab.active')?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
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

function tabMenu(pane) {
  const v = viewOf(pane);
  const items = [{ header: v?.path || pane.tab.name }];
  if (pane.tab.panes.length > 1) {
    items.push({ label: t('문서 탭 닫기'), hint: pane === S.pane ? 'Ctrl+F4' : t('가운데 버튼'), action: () => closeDocTab(pane) },
      { label: t('다른 문서 탭 모두 닫기'), action: () => closeOthers(pane) });
  }
  if (v?.path && (v.type === 'doc' || v.type === 'code')) items.push('-', ...pathMenuItems(v.path, true));
  return items;
}

export function initDocTabs() {
  const list = $('#lec-doctab-list');
  list.addEventListener('click', (e) => {
    const pane = paneAt(e.target);
    if (!pane) return;
    if (e.target.closest('.tab-close')) closeDocTab(pane);
    else selectDocTab(pane);
  });
  list.addEventListener('mousedown', (e) => { if (e.button === 1) e.preventDefault(); });   // 가운데 버튼의 자동 스크롤 대신
  list.addEventListener('auxclick', (e) => {   // 가운데 버튼으로 누르면 닫기 (프로젝트 탭처럼)
    const pane = e.button === 1 && paneAt(e.target);
    if (pane) closeDocTab(pane);
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
