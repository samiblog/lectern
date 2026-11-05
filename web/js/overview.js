// 폴더 개요 화면: 최근 변경, 하위 폴더, 문서 목록(제목·요약·수정 시각)

import { S, emit } from './store.js';
import { getJSON } from './api.js';
import { setToc, PARTS } from './toc.js';
import { setStatus } from './status.js';
import { clearChanges } from './diffmark.js';
import { paneOf } from './panes.js';
import { kindBadge } from './tree.js';
import { html, setHtml } from './html.js';
import { $, timeAgo, formatDateTime, newTabWanted } from './util.js';
import { t } from './i18n.js';

function crumbs(path, tab) {
  const parts = path ? path.split('/') : [];
  const items = [html`<button type="button" data-dir="">${tab.name}</button>`];
  parts.slice(0, -1).forEach((name, i) => {
    items.push(html`<button type="button" data-dir="${parts.slice(0, i + 1).join('/')}">${name}</button>`);
  });
  return parts.length ? html`<nav class="crumbs" aria-label="${t('상위 폴더')}">${items.flatMap((item, i) => (i ? [html`<span class="sep">/</span>`, item] : [item]))}</nav>` : '';
}

function relativeDir(filePath, base) {
  const dir = filePath.includes('/') ? filePath.slice(0, filePath.lastIndexOf('/')) : '';
  if (!base) return dir;
  return dir === base ? '' : dir.slice(base.length + 1);
}

function render(d, tab) {
  const recent = d.total > 3 ? d.recent : [];
  const parts = [];
  parts.push(html`<header class="ov-head">${crumbs(d.path, tab)}<h1>${d.name}</h1>
    <p class="ov-sub">${d.total ? t('문서 {n}개', { n: d.total }) : t('문서 없음')}${d.dirs.length ? `, ${t('폴더 {n}개', { n: d.dirs.length })}` : ''}</p>
    ${d.total ? html`<p class="ov-parts"><span>${t('모아 보기')}</span>${Object.entries(PARTS).map(([k, p]) => html`<button type="button" data-parts="${k}"
      title="${t('{scope}의 {kind} 모아 보기 — 사이드바', { scope: d.path ? t('{folder} 폴더(하위 포함)', { folder: d.path }) : t('프로젝트 전체'), kind: p.many })}">${p.many}</button>`)}</p>` : ''}</header>`);

  if (recent.length) {
    parts.push(html`<section class="ov-sec"><h2>${t('최근 변경')}</h2><ol class="ov-rail">${recent.map((f) => {
      const fresh = tab.changed.has(f.path);
      const where = relativeDir(f.path, d.path);
      return html`<li><button type="button" data-doc="${f.path}" title="${f.path}, ${formatDateTime(f.mtime)}">
        <span class="when">${timeAgo(f.mtime)}</span><span class="mark${fresh ? ' fresh' : ''}" aria-hidden="true"></span>
        <span class="t">${f.title || f.name}${fresh ? html`<span class="sr">${t('(새 변경)')}</span>` : ''}</span>
        <span class="where">${where}</span></button></li>`;
    })}</ol></section>`);
  }

  if (d.dirs.length) {
    parts.push(html`<section class="ov-sec"><h2>${t('폴더')}</h2><ul class="ov-dirs">${d.dirs.map((x) => html`
      <li><button type="button" data-dir="${x.path}">
        <span class="name">${x.name}</span>
        <span class="meta">${t('문서 {n}개', { n: x.count })}${x.mtime ? `, ${t('{when} 수정', { when: timeAgo(x.mtime) })}` : ''}</span>
      </button></li>`)}</ul></section>`);
  }

  if (d.files.length) {
    parts.push(html`<section class="ov-sec"><h2>${d.dirs.length ? t('이 폴더의 문서') : t('문서')}</h2><ul class="ov-files">${d.files.map((f) => {
      const fresh = tab.changed.has(f.path);
      return html`<li><button type="button" data-doc="${f.path}">
        <span class="t">${f.title || f.name}${kindBadge(f)}${fresh ? html`<span class="fresh-dot" title="${t('열어 보기 전에 바뀜')}"></span>` : ''}</span>
        <span class="when" title="${formatDateTime(f.mtime)}">${timeAgo(f.mtime)}</span>
        ${f.title ? html`<span class="fname">${f.name}</span>` : ''}
        ${f.summary ? html`<span class="sum">${f.summary}</span>` : ''}
      </button></li>`;
    })}</ul></section>`);
  }

  if (!d.total) {
    parts.push(html`<p class="ov-empty">${t('이 폴더에는 문서(Markdown·HTML)가 없습니다. 숨김 폴더와 node_modules 같은 제외 폴더는 보이지 않습니다.')}</p>`);
  }
  return parts;
}

/** 폴더 개요를 칸(pane)에 그린다. 프로젝트는 칸의 탭(pane.tab). 그 칸에서 더 나중에 시작한 렌더링이 있으면 결과를 버린다(false)
 * @param {Pane} pane
 * @param {string} path
 * @param {ShowOptions} [options]
 */
export async function showOverview(pane, path, { scrollTop } = {}) {
  const id = ++pane.renderId;
  const { view, tab } = pane;
  let data;
  try {
    data = await getJSON(`/api/overview?p=${encodeURIComponent(tab.id)}&path=${encodeURIComponent(path)}`);
  } catch (err) {
    if (id !== pane.renderId) return false;
    view.className = 'overview';
    setHtml(view, html`<div class="ov-empty"><h1>${path || tab.name}</h1><p>${t('폴더를 읽지 못했습니다 ({error}). 삭제되었거나 숨김 폴더일 수 있습니다.', { error: err.message })}</p></div>`);
    setToc(pane, null);
    clearChanges(pane);
    emit('rendered', pane);
    return true;
  }
  if (id !== pane.renderId) return false;

  const top = typeof scrollTop === 'function' ? scrollTop() : scrollTop;   // 함수면 바꿔 끼우기 직전의 위치 (refreshView)
  view.className = 'overview';
  setHtml(view, render(data, tab));
  setToc(pane, null);
  clearChanges(pane);
  pane.scroller.scrollTop = top ?? 0;
  setStatus({ path: path ? `${path}/` : t('{name} (프로젝트 루트)', { name: tab.name }), info: t('문서 {n}개', { n: data.total }) }, pane);
  emit('rendered', pane);
  return true;
}

export function initOverview() {
  $('#lec-panes').addEventListener('click', (e) => {
    const pane = paneOf(e.target);
    if (!pane?.view.classList.contains('overview')) return;
    const part = e.target.closest('button[data-parts]');   // 이 폴더의 표·그림 등 모아 보기 (parts.js)
    if (part) {
      emit('parts', { path: pane.current?.path || '', kind: part.dataset.parts });
      return;
    }
    const btn = e.target.closest('button[data-doc], button[data-dir]');
    if (!btn) return;
    if (btn.dataset.doc != null) emit('open', { type: 'doc', path: btn.dataset.doc, newTab: newTabWanted(e) });   // Ctrl+누르기·가운데 버튼: 새 문서 탭 (D64)
    else {
      if (btn.dataset.dir) S.open.add(btn.dataset.dir);
      emit('open', { type: 'overview', path: btn.dataset.dir });
    }
  });
}
