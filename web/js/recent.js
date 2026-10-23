// 사이드바 '최근 변경' 탭 (D50): 최근에 고친 문서·코드·자료를 섞어 최근 것부터. 위의 '문서'·'코드'·'자료' 버튼으로 보일 것을 고른다
// (설정 recent_docs·recent_code·recent_others). 문서는 탭의 트리(S.files — 고치면 자동 새로고침이 트리를 새로 받는다)에서,
// 코드·자료는 서버가 고른 최근 파일(GET /api/others/recent — 감시가 내용 수정을 touch 로 남긴다)에서. 코드·자료는 이 탭이 보일 때만 받는다.
// 행은 others.js 의 bindFileRows — 문서·코드는 한 번 누르면 열고, 자료는 두 번 누르거나 Enter. 스크롤 위치는 프로젝트 탭마다 (tab.side).

import { S, on } from './store.js';
import { getJSON, saveConfig } from './api.js';
import { labelOf, tipOf } from './tree.js';
import { bindFileRows, fileTip } from './others.js';
import { fileIcon } from './icons.js';
import { $, esc, dirname, timeAgo, keepFocus } from './util.js';
import { t } from './i18n.js';

const MAX_ROWS = 50;
const KINDS = [['#lec-recent-docs', 'recent_docs'], ['#lec-recent-code', 'recent_code'], ['#lec-recent-others', 'recent_others']];

const want = (key) => S.config[key] !== false;
const box = () => $('#lec-recent');
const shown = () => !$('#lec-recent-panel').hidden;
/** 코드·자료 중 무엇을 받는지 — 바뀌면 다시 받는다 */
const filesKey = () => `${want('recent_code') ? 'c' : ''}${want('recent_others') ? 'o' : ''}`;
let rows = new Map();   // 화면에 있는 행: 경로 → 노드 (bindFileRows)

function renderKinds() {
  for (const [id, key] of KINDS) {
    $(id).classList.toggle('on', want(key));
    $(id).setAttribute('aria-pressed', String(want(key)));
  }
}

/** 지금 보는 문서·코드 */
const current = () => (S.view?.type === 'doc' || S.view?.type === 'code' ? S.view.path : null);

function render() {
  const tab = S.tab;
  const list = [];
  if (tab && want('recent_docs')) list.push(...S.files);
  const r = tab?.recent;
  if (r?.files && r.key === filesKey()) list.push(...r.files);
  list.sort((a, b) => b.mtime - a.mtime);
  const top = list.slice(0, MAX_ROWS);
  rows = new Map(top.map((f) => [f.path, f]));
  let html;
  if (!KINDS.some(([, key]) => want(key))) html = `<p class="side-empty">${t('보일 것(문서·코드·자료)을 고르세요')}</p>`;
  else if (!top.length) html = r?.loading ? '' : `<p class="side-empty">${t('고친 파일이 없습니다')}</p>`;
  else {
    html = top.map((f) => {
      const doc = !!f.kind;
      const cls = `row recent${f.path === current() ? ' active' : ''}`;
      return `<div class="${cls}" data-file="${esc(f.path)}" title="${esc(doc ? tipOf(f) : fileTip(f))}" tabindex="0">`
        + `<span class="when">${esc(timeAgo(f.mtime))}</span><span class="label">${fileIcon(f.name, f.kind)}${esc(doc ? labelOf(f) : f.name)}</span>`
        + `${doc && S.changed.has(f.path) ? '<span class="dot"></span>' : ''}`
        + `${dirname(f.path) ? `<span class="sub">${esc(dirname(f.path))}</span>` : ''}</div>`;
    }).join('');
  }
  if (r?.error && filesKey()) html += `<p class="side-empty">${esc(t('코드·자료를 읽지 못했습니다 ({error}). F5 를 누르면 다시 읽습니다.', { error: r.error }))}</p>`;
  keepFocus(box(), () => { box().innerHTML = html; });
}

/** 탭의 코드·자료 최근 파일을 받는다 (tab.recent) */
async function load(tab) {
  const r = tab.recent;
  const key = filesKey();
  if (r.loading) {   // 받는 동안 또 바뀌었다 — 끝나고 한 번 더
    r.again = true;
    return;
  }
  r.stale = false;
  if (!key) {
    Object.assign(r, { files: [], key, error: null });
    return;
  }
  r.loading = getJSON(`/api/others/recent?p=${encodeURIComponent(tab.id)}&code=${key.includes('c') ? 1 : 0}&others=${key.includes('o') ? 1 : 0}`);
  try {
    const d = await r.loading;
    Object.assign(r, { files: d.files, key, error: null });
  } catch (e) {
    r.error = e.message;
  } finally {
    r.loading = null;
  }
  if (tab === S.tab) render();
  if (r.again) {
    r.again = false;
    ensure();
  }
}

/** 탭이 보이는데 코드·자료를 아직 받지 않았거나, 그 뒤로 바뀌었거나, 버튼이 바뀌었으면 받는다 */
function ensure() {
  const tab = S.tab;
  if (!tab || !shown()) return;
  const r = tab.recent;
  if (r.stale || r.key !== filesKey()) load(tab);
}

/** F5: 코드·자료도 새로 받는다 */
export function refreshRecent() {
  if (!S.tab) return;
  S.tab.recent.stale = true;
  ensure();
}

/** 프로젝트 탭을 바꾸면: 앞 탭의 스크롤 위치를 남기고 새 탭의 것을 되살린다 */
function onTab({ tab, prev }) {
  if (prev && S.tabs.includes(prev)) prev.side.recentScroll = box().scrollTop;
  render();
  box().scrollTop = tab?.side.recentScroll || 0;
  ensure();
}

export function initRecent() {
  bindFileRows(box(), (path) => rows.get(path));
  for (const [id, key] of KINDS) {
    $(id).addEventListener('click', async () => {
      await saveConfig({ [key]: !want(key) });
      renderKinds();
      render();
      ensure();
    });
  }
  renderKinds();
  on('tree', render);      // 문서가 바뀜 (트리를 새로 받음)
  on('changed', render);   // 바뀜 점
  on('view', () => {
    render();
    if (shown()) box().querySelector('.row.active')?.scrollIntoView({ block: 'nearest' });
  });
  on('tab', onTab);
  on('titles', render);
  on('panel', (name) => { if (name === 'recent') ensure(); });
  // 코드·자료가 생기거나 지워지거나 고쳐짐 (watch.js 가 tab.recent.stale 을 단다)
  on('touched', (tab) => { if (tab === S.tab) ensure(); });
  setInterval(render, 60_000);   // '5분 전' 같은 표시 갱신
}
