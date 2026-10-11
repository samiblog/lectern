// 왼쪽 사이드바: 파일 트리, 필터, 최근 변경 목록, 우클릭 메뉴

import { S, emit, on } from './store.js';
import { saveConfig, openExternal, revealInExplorer } from './api.js';
import { showMenu } from './ui.js';
import { $, $$, esc, dirname, timeAgo, copyText, toast } from './util.js';

const MAX_FILTER_RESULTS = 300;
let tab = 'files';

const showTitles = () => S.config.show_titles !== false;
const labelOf = (f) => (showTitles() ? (f.title || f.name) : f.name);

function activeDoc() {
  return S.view?.type === 'doc' ? S.view.path : null;
}

function activeDir() {
  return S.view?.type === 'overview' ? S.view.path : null;
}

function hasChangedInside(dirPath) {
  const prefix = `${dirPath}/`;
  for (const p of S.changed) if (p.startsWith(prefix)) return true;
  return false;
}

function fileRow(f, depth, extra = '') {
  const cls = ['row', 'file'];
  if (f.path === activeDoc()) cls.push('active');
  const title = showTitles() && f.title ? `${f.path}\n${f.title}` : f.path;
  return `<div class="${cls.join(' ')}" data-doc="${esc(f.path)}" style="--d:${depth}" title="${esc(title)}" tabindex="0">`
    + `<span class="caret-space"></span><span class="label">${esc(labelOf(f))}</span>${extra}`
    + `${S.changed.has(f.path) ? '<span class="dot" title="열어 보기 전에 바뀜"></span>' : ''}</div>`;
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
      + `<span class="caret${open ? ' open' : ''}" data-toggle aria-hidden="true"></span><span class="label">${esc(n.name)}</span>`
      + `${!open && hasChangedInside(n.path) ? '<span class="dot" title="안쪽 문서가 바뀜"></span>' : ''}</div>`;
    if (open) html += nodesHtml(n.children, depth + 1);
  }
  return html;
}

function renderTree() {
  const box = $('#lec-tree');
  const scroll = box.scrollTop;
  if (!S.root) {
    box.innerHTML = '';
    return;
  }
  const query = $('#lec-filter').value.trim().toLowerCase();
  if (query) {
    const terms = query.split(/\s+/);
    const hits = S.files.filter((f) => {
      const hay = `${(f.title || '').toLowerCase()} ${f.path.toLowerCase()}`;
      return terms.every((t) => hay.includes(t));
    });
    box.innerHTML = hits.length
      ? hits.slice(0, MAX_FILTER_RESULTS).map((f) => fileRow(f, 0, dirname(f.path) ? `<span class="sub">${esc(dirname(f.path))}</span>` : '')).join('')
      : '<p class="side-empty">일치하는 문서가 없습니다</p>';
  } else {
    const rootCls = ['row', 'dir', 'root'];
    if (activeDir() === '') rootCls.push('active');
    box.innerHTML = `<div class="${rootCls.join(' ')}" data-dir="" title="프로젝트 개요" tabindex="0"><span class="label">${esc(S.name)}</span></div>`
      + (S.tree.length ? nodesHtml(S.tree, 0) : '<p class="side-empty">Markdown 문서가 없습니다</p>');
  }
  box.scrollTop = scroll;
}

function renderRecent() {
  const box = $('#lec-recent');
  const files = [...S.files].sort((a, b) => b.mtime - a.mtime).slice(0, 40);
  box.innerHTML = files.length ? files.map((f) => {
    const cls = ['row', 'recent'];
    if (f.path === activeDoc()) cls.push('active');
    return `<div class="${cls.join(' ')}" data-doc="${esc(f.path)}" title="${esc(f.path)}" tabindex="0">`
      + `<span class="when">${esc(timeAgo(f.mtime))}</span><span class="label">${esc(labelOf(f))}</span>`
      + `${S.changed.has(f.path) ? '<span class="dot"></span>' : ''}`
      + `${dirname(f.path) ? `<span class="sub">${esc(dirname(f.path))}</span>` : ''}</div>`;
  }).join('') : '<p class="side-empty">문서가 없습니다</p>';
}

function renderCount() {
  const el = $('#lec-changed-count');
  el.textContent = S.changed.size;
  el.hidden = S.changed.size === 0;
}

function render() {
  renderTree();
  renderRecent();
  renderCount();
  $('#lec-btn-titles').classList.toggle('on', showTitles());
}

/** 지금 보는 항목의 상위 폴더를 펼치고 트리에서 보이게 한다. */
function revealCurrent() {
  if (!S.view) return;
  const parts = S.view.path.split('/');
  const upto = S.view.type === 'doc' ? parts.length - 1 : parts.length;
  for (let i = 1; i <= upto; i++) S.open.add(parts.slice(0, i).join('/'));
  render();
  const sel = S.view.type === 'doc' ? `[data-doc="${CSS.escape(S.view.path)}"]` : `[data-dir="${CSS.escape(S.view.path)}"]`;
  $(`#lec-${tab === 'files' ? 'tree' : 'recent'} ${sel}`)?.scrollIntoView({ block: 'nearest' });
}

export function switchTab(next) {
  tab = next;
  for (const b of $$('.side-tabs button')) b.classList.toggle('active', b.dataset.tab === next);
  $('#lec-tree').hidden = next !== 'files';
  $('#lec-recent').hidden = next !== 'recent';
  $('#lec-filter').closest('.side-filter').hidden = next !== 'files';
  $('#lec-search').hidden = next !== 'search';   // 전체 검색 (search.js)
  if (next === 'search') $('#lec-search-input').focus();
}

function onRowClick(e) {
  const row = e.target.closest('.row');
  if (!row) return;
  if (row.dataset.doc != null) {
    emit('open', { type: 'doc', path: row.dataset.doc });
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

function fullPath(path) {
  return path ? `${S.root}${S.sep}${path.split('/').join(S.sep)}` : S.root;
}

async function copy(text) {
  toast(await copyText(text) ? `복사했습니다: ${text}` : '복사하지 못했습니다', '');
}

/** 트리 행과 본문 빈 곳(docmenu.js)의 우클릭 메뉴 항목: 경로 복사, 편집기로 열기, 탐색기에서 보기 */
export function pathMenuItems(path, isDoc) {
  const items = [];
  if (path) items.push({ label: `@${path} 복사`, hint: 'Claude Code 프롬프트에 붙여 넣기', action: () => copy(`@${path}`) });
  items.push({ label: '전체 경로 복사', action: () => copy(fullPath(path)) });
  items.push('-');
  if (isDoc) items.push({ label: '편집기로 열기', action: () => openExternal(path) });
  items.push({ label: '탐색기에서 보기', action: () => revealInExplorer(path) });
  return items;
}

function onContextMenu(e) {
  const row = e.target.closest('.row');
  if (!row) return;
  e.preventDefault();
  const isDoc = row.dataset.doc != null;
  showMenu(e.clientX, e.clientY, pathMenuItems(isDoc ? row.dataset.doc : row.dataset.dir, isDoc));
}

export function focusFilter() {
  switchTab('files');
  $('#lec-filter').focus();
  $('#lec-filter').select();
}

export function initTree() {
  for (const id of ['#lec-tree', '#lec-recent']) {
    $(id).addEventListener('click', onRowClick);
    $(id).addEventListener('contextmenu', onContextMenu);
    $(id).addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && e.target.classList.contains('row')) e.target.click();
    });
  }
  const filter = $('#lec-filter');
  filter.addEventListener('input', renderTree);
  filter.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      $('#lec-tree .row.file')?.click();
    } else if (e.key === 'Escape' && filter.value) {
      e.stopPropagation();
      filter.value = '';
      renderTree();
    }
  });
  $('#lec-btn-titles').addEventListener('click', async () => {
    await saveConfig({ show_titles: !showTitles() });
    render();
  });
  for (const b of $$('.side-tabs button')) b.addEventListener('click', () => switchTab(b.dataset.tab));

  on('tree', render);
  on('changed', render);
  on('view', revealCurrent);
  setInterval(renderRecent, 60_000);   // '5분 전' 같은 표시 갱신
}
