// 이름 바꾸기 (D66): 사이드바(트리·'코드'·'자료' 목록·최근 변경·검색)의 파일 하나를 같은 폴더 안에서 다른 이름으로 — 우클릭 '이름 바꾸기…'·F2.
// 이름을 묻는 작은 창(#lec-rename — 처음 값은 지금 이름, 확장자 앞까지 골라 둠) → POST /api/rename (옮기기·덮어쓰기는 하지 않는다).
// 바뀐 뒤에는 그 파일을 보던 칸(문서 탭)·뒤로 기록·스크롤 위치·담은 조각의 경로를 새 이름으로 옮긴다 (트리·목록은 감시가 다시 그린다).
// 다른 문서 속 링크는 고치지 않는다. 저장하지 않은 편집이 있는 파일은 바꾸지 않는다 (먼저 저장하거나 닫기).

import { S, on } from './store.js';
import { postJSON } from './api.js';
import { navigate, renamePath } from './nav.js';
import { closeEditor, openEditor } from './editor.js';
import { isViewable } from './icons.js';
import { $, toast, basename, dirname, isMd, isHtml } from './util.js';
import { t } from './i18n.js';

let asked = null;   // {tab, path} — 이름을 묻고 있는 파일

const box = () => $('#lec-rename');
const input = () => $('#lec-rename-input');
const extOf = (name) => (name.lastIndexOf('.') > 0 ? name.slice(name.lastIndexOf('.')).toLowerCase() : '');
const dirtyIn = (tab, path) => tab.panes.some((p) => p.editor?.path === path && p.editor.dirty);

function setMsg(text, bad = false) {
  const p = $('#lec-rename-msg');
  p.hidden = !text;
  p.textContent = text;
  p.classList.toggle('bad', bad);
}

/** 선택된 탭의 파일(path — 프로젝트 기준)의 새 이름을 묻는다 */
export function askRename(path) {
  const tab = S.tab;
  if (!tab || !path) return;
  if (dirtyIn(tab, path)) {
    toast(t('{name} 에 저장하지 않은 편집이 있습니다 — 저장하거나 편집을 닫은 뒤 이름을 바꾸세요', { name: basename(path) }), 'error', 5000);
    return;
  }
  asked = { tab, path };
  const name = basename(path);
  $('#lec-rename-title').textContent = t('이름 바꾸기 — {path}', { path });
  input().value = name;
  setMsg(isMd(path) || isHtml(path) ? t('다른 문서 속 이 문서의 링크는 그대로입니다') : '');
  box().hidden = false;
  input().focus();
  const dot = name.lastIndexOf('.');
  input().setSelectionRange(0, dot > 0 ? dot : name.length);   // 확장자 앞까지 — 바로 고쳐 쓰게 (탐색기처럼)
}

export function closeRename() {
  if (box().hidden) return false;
  box().hidden = true;
  asked = null;
  return true;
}

async function submit() {
  if (!asked) return;
  const { tab, path } = asked;
  if (dirtyIn(tab, path)) {   // 창을 연 뒤에 편집이 생겼다 (보내기 등) — 버리지 않는다
    closeRename();
    toast(t('{name} 에 저장하지 않은 편집이 있습니다 — 저장하거나 편집을 닫은 뒤 이름을 바꾸세요', { name: basename(path) }), 'error', 5000);
    return;
  }
  const old = basename(path);
  const name = input().value.trim();
  if (!name || name === old) {
    closeRename();
    return;
  }
  if (extOf(name) !== extOf(old) && !window.confirm(t('확장자를 {from} 에서 {to} 로 바꿀까요? 여는 프로그램과 보이는 목록이 달라질 수 있습니다',
    { from: extOf(old) || t('(없음)'), to: extOf(name) || t('(없음)') }))) {
    input().focus();
    return;
  }
  let r;
  try {
    r = await postJSON('/api/rename', { p: tab.id, path, name });
  } catch (e) {   // 같은 이름·쓸 수 없는 이름·다른 프로그램이 씀 — 고쳐서 다시 Enter
    if (asked?.path === path) setMsg(e.message, true);
    return;
  }
  closeRename();
  await moved(tab, path, r.path);
  toast(t('이름을 바꿨습니다: {name}', { name: basename(r.path) }));
}

/** 바뀐 이름을 화면에 옮긴다 — 그 파일을 보던 칸은 새 이름으로 다시 연다 (편집 중이었으면 편집도) */
async function moved(tab, from, to) {
  for (const sn of tab.basket || []) if (sn.path === from) sn.path = to;   // 담은 조각 (D63)
  // 확장자가 같으면 보던 종류 그대로 (앱 소스 폴더의 html 은 코드 화면 — 원칙 4), 바뀌면 새 확장자로. 읽을 수 없는 종류면 그 폴더 개요
  const sameExt = extOf(basename(from)) === extOf(basename(to));
  const kind = isMd(to) || isHtml(to) ? 'doc' : isViewable(basename(to)) ? 'code' : null;
  const targetOf = (type) => {
    const next = sameExt ? type : kind;
    return next ? { type: next, path: to } : { type: 'overview', path: dirname(to) };
  };
  for (const pane of renamePath(tab, from, targetOf)) {
    const next = targetOf(pane.current.type);
    const editing = !!pane.editor && next.type !== 'overview';
    if (pane.editor) closeEditor(pane, { ask: false, sync: false });   // 저장하지 않은 편집은 없다 (askRename·submit)
    if (await navigate(next, { pane, push: false, scrollTop: pane.scroller.scrollTop }) && editing) await openEditor(pane);
  }
}

export function initRename() {
  input().addEventListener('input', () => setMsg(''));
  input().addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      submit();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      closeRename();
    }
  });
  box().addEventListener('mousedown', (e) => { if (e.target === box()) closeRename(); });
  on('rename', ({ path }) => askRename(path));   // 사이드바의 우클릭 메뉴·F2 (tree·others)
  on('tab', closeRename);   // 다른 프로젝트 탭으로 — 묻던 파일은 그 탭의 것
}
