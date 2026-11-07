// 문서 삭제 (D104): 사이드바 '문서' 목록의 우클릭으로 고른 문서 하나를 휴지통으로 보낸다. 코드와 자료에는 이 길이 없다.
// 늘 묻는다 (#lec-delete — 초점은 그만두기에). 저장하지 않은 편집이 있는 문서는 지우지 않는다.
// 지운 뒤에는 그 문서를 보던 칸을 닫는다. 하나뿐인 칸은 그 폴더의 개요로 간다 (트리·목록은 감시가 알아서 갱신한다).

import { S, on } from './store.js';
import { postJSON } from './api.js';
import { navigate } from './nav.js';
import { closeDocTab } from './doctabs.js';
import { closeEditor } from './editor.js';
import { $, toast, basename, dirname, blockedReadOnly } from './util.js';
import { t } from './i18n.js';

let asked = null;   // {tab, path} — 묻고 있는 문서

const box = () => $('#lec-delete');
const dirtyIn = (tab, path) => tab.panes.some((p) => p.editor?.path === path && p.editor.dirty);
const dirtyNote = (path) => t('{name} 에 저장하지 않은 편집이 있습니다 — 저장하거나 편집을 닫은 뒤 지우세요', { name: basename(path) });

/** 선택된 탭의 문서(path — 프로젝트 기준)를 지울지 묻는다 */
export function askDelete(path) {
  const tab = S.tab;
  if (!tab || !path || blockedReadOnly(tab)) return;
  if (dirtyIn(tab, path)) {
    toast(dirtyNote(path), 'error', 5000);
    return;
  }
  asked = { tab, path };
  $('#lec-delete-title').textContent = t('문서 삭제 — {path}', { path });
  setMsg('');
  box().hidden = false;
  $('#lec-delete-no').focus();
}

export function closeDelete() {
  if (box().hidden) return false;
  box().hidden = true;
  asked = null;
  return true;
}

function setMsg(text) {
  const p = $('#lec-delete-msg');
  p.hidden = !text;
  p.textContent = text;
}

async function submit() {
  if (!asked) return;
  const { tab, path } = asked;
  if (dirtyIn(tab, path)) {   // 창을 연 뒤에 편집이 생겼다 (보내기 등) — 버리지 않는다
    closeDelete();
    toast(dirtyNote(path), 'error', 5000);
    return;
  }
  try {
    await postJSON('/api/delete-doc', { p: tab.id, path });
  } catch (e) {   // 휴지통이 없는 드라이브, 다른 프로그램이 씀 — 파일은 그대로다
    if (asked?.path === path) setMsg(e.message);
    return;
  }
  closeDelete();
  await gone(tab, path);
  toast(t('휴지통으로 보냈습니다: {name} — 휴지통에서 되살립니다', { name: basename(path) }));
}

/** 지운 문서를 보던 칸을 정리한다. remote: 다른 창이 지웠다 — 이 창의 저장하지 않은 편집은 닫지 않는다 */
async function gone(tab, path, remote = false) {
  for (const pane of tab.panes.slice()) {
    const same = pane.current?.type === 'doc' && pane.current.path === path;
    const later = pane.deferred?.type === 'doc' && pane.deferred.path === path;
    if (!same && !later) continue;
    if (pane.editor) {
      if (remote) continue;
      closeEditor(pane, { ask: false, sync: false });
    }
    if (!closeDocTab(pane)) await navigate({ type: 'overview', path: dirname(path) }, { pane });
  }
}

export function initDeleteDoc() {
  on('delete-doc', ({ path }) => askDelete(path));   // 트리의 우클릭 메뉴
  on('file-deleted', ({ tab, path }) => gone(tab, path, true));   // 다른 창이 지웠다 (doctabs)
  on('tab', closeDelete);   // 다른 프로젝트 탭으로 — 묻던 문서는 그 탭의 것
  $('#lec-delete-yes').addEventListener('click', submit);
  $('#lec-delete-no').addEventListener('click', closeDelete);
  box().addEventListener('mousedown', (e) => { if (e.target === box()) closeDelete(); });
  box().addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    e.preventDefault();
    e.stopPropagation();
    closeDelete();
  });
}
