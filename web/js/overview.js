// 폴더 개요 화면: 최근 변경, 하위 폴더, 문서 목록(제목·요약·수정 시각)

import { S, emit } from './store.js';
import { getJSON } from './api.js';
import { clearToc } from './toc.js';
import { setStatus } from './status.js';
import { kindBadge } from './tree.js';
import { $, esc, timeAgo, formatDateTime } from './util.js';

function crumbs(path) {
  const parts = path ? path.split('/') : [];
  const items = [`<button type="button" data-dir="">${esc(S.name)}</button>`];
  parts.slice(0, -1).forEach((name, i) => {
    items.push(`<button type="button" data-dir="${esc(parts.slice(0, i + 1).join('/'))}">${esc(name)}</button>`);
  });
  return parts.length ? `<nav class="crumbs" aria-label="상위 폴더">${items.join('<span class="sep">/</span>')}</nav>` : '';
}

function relativeDir(filePath, base) {
  const dir = filePath.includes('/') ? filePath.slice(0, filePath.lastIndexOf('/')) : '';
  if (!base) return dir;
  return dir === base ? '' : dir.slice(base.length + 1);
}

function render(d) {
  const recent = d.total > 3 ? d.recent : [];
  const parts = [];
  parts.push(`<header class="ov-head">${crumbs(d.path)}<h1>${esc(d.name)}</h1>
    <p class="ov-sub">${d.total ? `문서 ${d.total}개` : '문서 없음'}${d.dirs.length ? `, 폴더 ${d.dirs.length}개` : ''}</p></header>`);

  if (recent.length) {
    parts.push(`<section class="ov-sec"><h2>최근 변경</h2><ol class="ov-rail">${recent.map((f) => {
      const fresh = S.changed.has(f.path);
      const where = relativeDir(f.path, d.path);
      return `<li><button type="button" data-doc="${esc(f.path)}" title="${esc(f.path)}, ${formatDateTime(f.mtime)}">
        <span class="when">${esc(timeAgo(f.mtime))}</span><span class="mark${fresh ? ' fresh' : ''}" aria-hidden="true"></span>
        <span class="t">${esc(f.title || f.name)}${fresh ? '<span class="sr">(새 변경)</span>' : ''}</span>
        <span class="where">${esc(where)}</span></button></li>`;
    }).join('')}</ol></section>`);
  }

  if (d.dirs.length) {
    parts.push(`<section class="ov-sec"><h2>폴더</h2><ul class="ov-dirs">${d.dirs.map((x) => `
      <li><button type="button" data-dir="${esc(x.path)}">
        <span class="name">${esc(x.name)}</span>
        <span class="meta">문서 ${x.count}개${x.mtime ? `, ${esc(timeAgo(x.mtime))} 수정` : ''}</span>
      </button></li>`).join('')}</ul></section>`);
  }

  if (d.files.length) {
    parts.push(`<section class="ov-sec"><h2>${d.dirs.length ? '이 폴더의 문서' : '문서'}</h2><ul class="ov-files">${d.files.map((f) => {
      const fresh = S.changed.has(f.path);
      return `<li><button type="button" data-doc="${esc(f.path)}">
        <span class="t">${esc(f.title || f.name)}${kindBadge(f)}${fresh ? '<span class="fresh-dot" title="열어 보기 전에 바뀜"></span>' : ''}</span>
        <span class="when" title="${formatDateTime(f.mtime)}">${esc(timeAgo(f.mtime))}</span>
        ${f.title ? `<span class="fname">${esc(f.name)}</span>` : ''}
        ${f.summary ? `<span class="sum">${esc(f.summary)}</span>` : ''}
      </button></li>`;
    }).join('')}</ul></section>`);
  }

  if (!d.total) {
    parts.push('<p class="ov-empty">이 폴더에는 문서(Markdown·HTML)가 없습니다. 숨김 폴더와 node_modules 같은 제외 폴더는 보이지 않습니다.</p>');
  }
  return parts.join('');
}

export async function showOverview(path, { scrollTop } = {}) {
  const id = ++S.renderId;
  const view = $('#lec-view');
  let data;
  try {
    data = await getJSON(`/api/overview?path=${encodeURIComponent(path)}`);
  } catch (err) {
    if (id !== S.renderId) return false;
    view.className = 'overview';
    view.innerHTML = `<div class="ov-empty"><h1>${esc(path || S.name)}</h1><p>폴더를 읽지 못했습니다 (${esc(err.message)}). 삭제되었거나 숨김 폴더일 수 있습니다.</p></div>`;
    clearToc();
    emit('rendered');
    return true;
  }
  if (id !== S.renderId) return false;

  const top = typeof scrollTop === 'function' ? scrollTop() : scrollTop;   // 함수면 바꿔 끼우기 직전의 위치 (refreshView)
  view.className = 'overview';
  view.innerHTML = render(data);
  clearToc();
  $('#lec-content').scrollTop = top ?? 0;
  setStatus({ path: path ? `${path}/` : `${S.name} (프로젝트 루트)`, info: `문서 ${data.total}개` });
  emit('rendered');
  return true;
}

export function initOverview() {
  $('#lec-view').addEventListener('click', (e) => {
    if (!$('#lec-view').classList.contains('overview')) return;
    const btn = e.target.closest('button[data-doc], button[data-dir]');
    if (!btn) return;
    if (btn.dataset.doc != null) emit('open', { type: 'doc', path: btn.dataset.doc });
    else {
      if (btn.dataset.dir) S.open.add(btn.dataset.dir);
      emit('open', { type: 'overview', path: btn.dataset.dir });
    }
  });
}
