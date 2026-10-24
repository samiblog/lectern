// 왼쪽 사이드바: 사이드바 탭 바꾸기, 파일 트리, 필터, 우클릭 메뉴. 선택된 프로젝트 탭의 것을 보인다.
// 사이드바 탭(파일·최근 변경·검색·모아 보기)·필터·스크롤 위치는 프로젝트 탭마다 기억했다가 그 탭을 고르면 되살린다 (tab.side).
// 최근 변경 목록은 recent.js (D50).

import { S, emit, on } from './store.js';
import { saveConfig, openExternal, revealInExplorer } from './api.js';
import { showMenu } from './ui.js';
import { fileIcon, folderIcon } from './icons.js';
import { $, $$, esc, dirname, copyText, toast, keepFocus, newTabWanted, middleClickOpens } from './util.js';
import { t } from './i18n.js';

const MAX_FILTER_RESULTS = 300;
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
export const kindBadge = (f) => (f.kind === 'html' ? `<span class="kind" title="${t('HTML 문서')}">HTML</span>` : '');

function fileRow(f, depth, extra = '') {
  const cls = ['row', 'file'];
  if (f.path === activeDoc()) cls.push('active');
  return `<div class="${cls.join(' ')}" data-doc="${esc(f.path)}" style="--d:${depth}" title="${esc(tipOf(f))}" tabindex="0">`
    + `<span class="caret-space"></span>${fileIcon(f.name, f.kind)}<span class="label">${esc(labelOf(f))}</span>${extra}`
    + `${S.changed.has(f.path) ? `<span class="dot" title="${t('열어 보기 전에 바뀜')}"></span>` : ''}</div>`;
}

function nodesHtml(nodes, depth) {
  let html = '';
  for (const n of nodes) {
    if (n.type === 'file') {
      html += fileRow(n, depth);
      continue;
    }
    const open = S.open.has(n.path);
    const cls = ['row', 'dir'];
    if (n.path === activeDir()) cls.push('active');
    html += `<div class="${cls.join(' ')}" data-dir="${esc(n.path)}" style="--d:${depth}" title="${esc(n.path)}" tabindex="0">`
      + `<span class="caret${open ? ' open' : ''}" data-toggle aria-hidden="true"></span>${folderIcon()}<span class="label">${esc(n.name)}</span>`
      + `${!open && hasChangedInside(n.path) ? `<span class="dot" title="${t('안쪽 문서가 바뀜')}"></span>` : ''}</div>`;
    if (open) html += nodesHtml(n.children, depth + 1);
  }
  return html;
}

function renderTree() {
  const box = $('#lec-tree');
  const scroll = box.scrollTop;
  if (!S.tab?.treeLoaded) {   // 탭이 없거나 아직 트리를 읽는 중
    box.innerHTML = '';
    return;
  }
  const query = $('#lec-filter').value.trim().toLowerCase();
  if (query) {
    const terms = query.split(/\s+/);
    const hits = S.files.filter((f) => {
      const hay = `${(f.title || '').toLowerCase()} ${f.path.toLowerCase()}`;
      return terms.every((w) => hay.includes(w));
    });
    box.innerHTML = hits.length
      ? hits.slice(0, MAX_FILTER_RESULTS).map((f) => fileRow(f, 0, dirname(f.path) ? `<span class="sub">${esc(dirname(f.path))}</span>` : '')).join('')
      : `<p class="side-empty">${t('일치하는 문서가 없습니다')}</p>`;
  } else {
    const rootCls = ['row', 'dir', 'root'];
    if (activeDir() === '') rootCls.push('active');
    box.innerHTML = `<div class="${rootCls.join(' ')}" data-dir="" title="${t('프로젝트 개요')}" tabindex="0"><span class="label">${esc(S.name)}</span></div>`
      + (S.tree.length ? nodesHtml(S.tree, 0) : `<p class="side-empty">${t('문서(Markdown·HTML)가 없습니다')}</p>`);
  }
  box.scrollTop = scroll;
}

function renderCount() {
  const el = $('#lec-changed-count');
  el.textContent = S.changed.size;
  el.hidden = S.changed.size === 0;
}

function render() {
  keepFocus($('#lec-tree'), renderTree);
  renderCount();
  $('#lec-btn-titles').classList.toggle('on', showTitles());
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
  if (row.dataset.doc != null) {
    emit('open', { type: 'doc', path: row.dataset.doc, newTab: newTabWanted(e) });   // Ctrl+누르기·가운데 버튼: 새 문서 탭 (D64)
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
export const shellWord = (text) => `${/^[\p{L}\p{N}_.\-\\/:@]+$/u.test(text) ? text : `'${text.replace(/'/g, "''")}'`} `;

/** 트리 행과 본문 빈 곳(docmenu.js)의 우클릭 메뉴 항목: 경로 복사(옆에 터미널에 붙여 넣기, D51), 편집기로 열기, 탐색기에서 보기 */
export function pathMenuItems(path, isDoc) {
  const items = [];
  if (path) items.push({ label: t('@{path} 복사', { path }), hint: t('Claude Code 프롬프트에 붙여 넣기'), action: () => copy(`@${path}`), term: `@${path} ` });
  items.push({ label: t('전체 경로 복사'), action: () => copy(fullPath(path)), term: shellWord(fullPath(path)) });
  items.push('-');
  if (isDoc) items.push({ label: t('편집기로 열기'), action: () => openExternal(path) });
  items.push({ label: t('탐색기에서 보기'), action: () => revealInExplorer(path) });
  if (!isDoc && S.dirs.has(path)) {   // 문서가 있는 폴더 — 모아 보기 (parts.js)
    items.push('-', { label: path ? t('이 폴더의 표·그림 등 모아 보기') : t('프로젝트의 표·그림 등 모아 보기'),
      hint: t("사이드바 '모아 보기' 탭"), action: () => emit('parts', { path }) });
  }
  return items;
}

/** 폴더 우클릭의 새로 만들기 (D65): 이 폴더에 새 문서 — 경로를 정하면 바로 만들어 새 탭에서 편집 */
export const newDocItem = (dir) => ({ label: t('이 폴더에 새 문서…'), action: () => emit('new-doc', { dir }) });

/** 문서 행의 우클릭 메뉴 — 새 탭에서 열기(D64)와 경로 항목 (트리·'코드'·'자료' 목록의 문서·최근 변경·검색이 함께 쓴다) */
export function docMenuItems(path, type = 'doc') {
  const items = [{ header: path }];
  if (!(S.view?.type === type && S.view.path === path)) {
    items.push({ label: t('새 탭에서 열기'), hint: t('Ctrl+누르기·가운데 버튼'), action: () => emit('open', { type, path, newTab: true }) }, '-');
  }
  return [...items, ...pathMenuItems(path, true)];
}

function onContextMenu(e) {
  const row = e.target.closest('.row');
  if (!row) return;
  e.preventDefault();
  if (row.dataset.doc != null) showMenu(e.clientX, e.clientY, docMenuItems(row.dataset.doc));
  else showMenu(e.clientX, e.clientY, [newDocItem(row.dataset.dir), '-', ...pathMenuItems(row.dataset.dir, false)]);
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
  tree.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.classList.contains('row')) e.target.click();
  });
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
  for (const b of $$('.side-tabs button')) b.addEventListener('click', () => switchPanel(b.dataset.tab));

  on('tree', render);
  on('changed', render);
  on('tab', onTab);
  on('view', revealCurrent);
}
