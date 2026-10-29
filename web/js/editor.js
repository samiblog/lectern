// 편집 모드 (D54): 보고 있는 문서(md·html)·코드를 그 자리에서 고친다 — CodeMirror 5 (web/vendor/codemirror, 처음 편집할 때 불러온다).
//
// - 칸(pane) 위를 덮는 편집 상자(.lec-editor, pane.editor)다. 아래의 화면은 그대로 두므로, 저장하면 자동 새로고침이 그 아래를
//   다시 그리고 닫으면 고친 결과가 보인다. 칸마다 하나라 다른 프로젝트 탭으로 가도 그 탭에 남는다.
// - 원문은 GET /api/source (줄바꿈은 LF 로, 서버가 저장할 때 그 파일의 CRLF·BOM 을 되살린다), 저장은 POST /api/save.
//   그사이 다른 곳(Claude Code 등)이 그 파일을 고쳤으면(원문을 받을 때의 내용 hash 와 다르면) 서버가 409 로 알리고,
//   물어서 덮어쓰거나(force) 편집을 이어 간다.
// - 저장하지 않은 편집이 있으면 다른 화면으로 가기(nav.js 의 leave guard)·편집 닫기·탭 닫기 전에 묻는다.
//   창을 닫을 때는 서버가 묻는다 — 저장하지 않은 파일 목록을 POST /api/editing 으로 알려 둔다 (app.py).
// - 여는 곳: 탭 막대 오른쪽 끝의 [편집] 버튼(켜기/끄기 — 목차·터미널 버튼 왼쪽), 상태줄의 '편집', 코드 화면 머리줄의 '편집',
//   우클릭 메뉴('이 문서 편집'·'여기를 편집' — 'edit' 이벤트 {line}), Ctrl+E.
// - 위치 잇기 (D55, 계산은 editsync.js): 줄을 주지 않으면 읽던 곳에서 연다. 편집하는 동안 아래의 읽는 화면을 편집기의
//   '지금 보는 곳'(커서가 화면 안이면 커서, 아니면 화면 맨 위 조금 아래)에 맞춰 두고, 목차의 '지금 읽는 위치'도 그곳으로 한다.
//   목차·모아 보기·검색에서 이 파일의 곳을 고르면 편집기가 그 줄로 간다. 닫으면 읽는 화면이 편집하던 곳에 있다.
// - 편집 상자 안의 키는 편집기 것이다 (main.js) — Ctrl+S 저장, Esc 닫기, Ctrl+F 찾기, Ctrl+H 바꾸기, Alt+G 줄로 가기.
// - 담은 조각 보내기 (D63·D65, basket.js): insertIntoDoc 이 그 문서를 편집 모드로 열고 조각을 넣는다 — 넣은 곳은 저장할 때까지 바탕색,
//   저장은 사용자가 한다. 새 문서는 newdoc.js 가 먼저 만든다 (경로를 정하면 바로 — '# 제목' 한 줄).

import { S, on, emit } from './store.js';
import { getJSON, postJSON } from './api.js';
import { setLeaveGuard, navigate } from './nav.js';
import { docPaneOf, selectDocTab, openInNewTab } from './doctabs.js';
import { setEditJump, updateTocActive } from './toc.js';
import { unfoldTo } from './fold.js';
import { logChange, toEditor, toView, headLines, marksOf, markAt, yOfLine, lineOfY, lineOfElement } from './editsync.js';
import { $, esc, toast, formatClock, isHtml, blockedReadOnly } from './util.js';
import { t } from './i18n.js';

const LIB = '/static/vendor/codemirror';
const ADDONS = ['dialog', 'searchcursor', 'search', 'jump-to-line', 'matchbrackets', 'active-line', 'simple'];   // simple: rust 모드가 쓴다

// CodeMirror 의 언어: 모드 → 불러올 파일 (쓰는 것 먼저 — web/vendor/codemirror/mode, tools/update_vendor.py 의 CODEMIRROR_MODES)
const WEB = ['xml', 'javascript', 'css', 'htmlmixed'];
const MODE_FILES = {
  markdown: ['xml', 'markdown'], htmlmixed: WEB, xml: ['xml'], javascript: ['javascript'], css: ['css'], python: ['python'],
  yaml: ['yaml'], toml: ['toml'], properties: ['properties'], shell: ['shell'], powershell: ['powershell'], clike: ['clike'],
  go: ['go'], rust: ['rust'], ruby: ['ruby'], php: [...WEB, 'clike', 'php'], sql: ['sql'], r: ['r'], lua: ['lua'], swift: ['swift'],
  perl: ['perl'], dart: ['clike', 'dart'], groovy: ['groovy'],
};
// 확장자 → [모드 파일 묶음, CodeMirror 의 mode 값]. 없으면 글자 그대로 (색 없음)
const EXT = {
  md: ['markdown', 'markdown'], markdown: ['markdown', 'markdown'], html: ['htmlmixed', 'htmlmixed'], htm: ['htmlmixed', 'htmlmixed'],
  vue: ['htmlmixed', 'htmlmixed'], svelte: ['htmlmixed', 'htmlmixed'], xml: ['xml', 'xml'], xsl: ['xml', 'xml'],
  js: ['javascript', 'javascript'], mjs: ['javascript', 'javascript'], cjs: ['javascript', 'javascript'], jsx: ['javascript', 'javascript'],
  ts: ['javascript', 'text/typescript'], tsx: ['javascript', 'text/typescript'],
  json: ['javascript', 'application/json'], jsonc: ['javascript', 'application/json'], ipynb: ['javascript', 'application/json'],
  css: ['css', 'css'], scss: ['css', 'text/x-scss'], less: ['css', 'text/x-less'],
  py: ['python', 'python'], pyw: ['python', 'python'], yaml: ['yaml', 'yaml'], yml: ['yaml', 'yaml'], toml: ['toml', 'toml'],
  ini: ['properties', 'properties'], cfg: ['properties', 'properties'], conf: ['properties', 'properties'], env: ['properties', 'properties'],
  sh: ['shell', 'shell'], bash: ['shell', 'shell'], zsh: ['shell', 'shell'], ps1: ['powershell', 'powershell'], psm1: ['powershell', 'powershell'],
  c: ['clike', 'text/x-csrc'], h: ['clike', 'text/x-csrc'], cc: ['clike', 'text/x-c++src'], cpp: ['clike', 'text/x-c++src'],
  hpp: ['clike', 'text/x-c++src'], cs: ['clike', 'text/x-csharp'], java: ['clike', 'text/x-java'], kt: ['clike', 'text/x-kotlin'],
  go: ['go', 'go'], rs: ['rust', 'rust'], rb: ['ruby', 'ruby'], php: ['php', 'php'], sql: ['sql', 'text/x-sql'], r: ['r', 'r'],
  lua: ['lua', 'lua'], swift: ['swift', 'swift'], pl: ['perl', 'perl'], dart: ['dart', 'dart'], gradle: ['groovy', 'groovy'],
};
const INDENT4 = new Set(['py', 'pyw', 'java', 'cs', 'kt', 'go', 'rs', 'php', 'ps1', 'psm1', 'c', 'h', 'cc', 'cpp', 'hpp', 'swift', 'dart']);

const extOf = (path) => (/\.([^./]+)$/.exec(path)?.[1] || '').toLowerCase();

// ---- 라이브러리 ------------------------------------------------------------------

const loading = new Map();   // 주소 → Promise (한 번만)

function load(src, css = false) {
  if (!loading.has(src)) {
    loading.set(src, new Promise((resolve, reject) => {
      const el = document.createElement(css ? 'link' : 'script');
      if (css) {
        el.rel = 'stylesheet';
        el.href = src;
      } else {
        el.src = src;
      }
      el.onload = resolve;
      el.onerror = () => {
        loading.delete(src);
        reject(new Error(t('편집기 파일을 읽지 못했습니다 ({file}). Lectern 을 다시 설치하면 고쳐집니다', { file: src })));
      };
      document.head.append(el);
    }));
  }
  return loading.get(src);
}

/** CodeMirror 와 그 언어 파일을 차례로 (언어 파일은 앞의 것을 쓴다) */
async function loadLib(group) {
  await Promise.all([load(`${LIB}/codemirror.css`, true), load(`${LIB}/addon/dialog.css`, true)]);
  await load(`${LIB}/codemirror.js`);
  // 문서 속 id 가 이름을 가릴 수 있다 (window.CodeMirror = 제목 요소) — 진짜 라이브러리인지 본다
  if (typeof window.CodeMirror !== 'function') throw new Error(t('편집기를 불러오지 못했습니다'));
  for (const name of ADDONS) await load(`${LIB}/addon/${name}.js`);
  for (const name of MODE_FILES[group] || []) await load(`${LIB}/mode/${name}.js`);
}

// ---- 위치 잇기 (D55) -------------------------------------------------------------

const LEAD = 40;   // 편집기 화면 맨 위에서 이만큼 아래가 '지금 보는 곳' (커서가 화면 밖일 때). 줄로 갈 때도 그 줄을 여기에 둔다

const marksFor = (ed) => (ed.marks ||= marksOf(ed.pane, ed.heads));   // 읽는 화면을 다시 그리면 비운다
const viewTop = (pane) => pane.view.getBoundingClientRect().top;

/** 편집기에서 지금 보는 곳: 커서가 화면 안이면 커서, 아니면 화면 맨 위 조금 아래. {at: 편집기의 자리, y: 화면 좌표} */
function editorSpot(ed) {
  const { cm } = ed;
  const box = cm.getScrollerElement().getBoundingClientRect();
  const c = cm.cursorCoords(true, 'window');
  const y = c.top >= box.top && c.bottom <= box.bottom ? c.top : box.top + LEAD;
  const n = cm.lineAtHeight(y, 'window');
  const h = cm.getLineHandle(n)?.height || 1;
  return { at: n + Math.min(Math.max((y - cm.heightAtLine(n, 'window')) / h, 0), 0.999), y };
}

/** 아래의 읽는 화면을 편집기의 지금 보는 곳에 맞춘다 — 같은 원문 자리가 같은 높이에 오게. 목차의 '지금 읽는 위치'도 그곳으로 */
function syncView(ed) {
  const { pane } = ed;
  if (pane.editor !== ed) return;
  const spot = editorSpot(ed);
  const y = yOfLine(marksFor(ed), toView(ed.log, spot.at), viewTop(pane));
  pane.tocLimit = spot.y;
  if (y != null) {
    const before = pane.scroller.scrollTop;
    pane.scroller.scrollTop = before + y - spot.y;
    pane.tocLimit = y - (pane.scroller.scrollTop - before);   // 문서 끝에 닿아 덜 움직였으면 그 자리는 그만큼 아래에 있다
  }
  if (pane === S.pane) updateTocActive();
}

/** 다음 그림 때 한 번 맞춘다 (스크롤·커서가 움직일 때마다 부른다) */
function follow(ed) {
  if (!ed.raf) ed.raf = requestAnimationFrame(() => { ed.raf = 0; syncView(ed); });
}

/** 열 때: 편집기를 읽는 화면에 맞춘다 — 읽던 곳(편집기의 지금 보는 곳과 같은 높이)의 원문 줄이 같은 높이에, 커서는 그 줄 머리에 */
function matchView(ed) {
  const { cm, pane } = ed;
  const y = cm.getScrollerElement().getBoundingClientRect().top + LEAD;
  const at = Math.min(lineOfY(marksFor(ed), y, viewTop(pane)), cm.lineCount() - 0.001);
  const n = Math.floor(at);
  cm.setCursor({ line: n, ch: 0 });
  const want = y - (at - n) * (cm.getLineHandle(n)?.height || 0);   // 그 줄의 머리가 올 곳
  cm.scrollTo(null, Math.max(0, cm.getScrollInfo().top + cm.heightAtLine(n, 'window') - want));
}

/** 목차·모아 보기에서 고른 곳(읽는 화면의 요소)으로 편집기를 옮긴다. 편집 중이 아니면 false — 읽는 화면이 간다 (toc.js) */
function jumpTo(el) {
  const ed = S.pane?.editor;
  if (!ed) return false;
  const line = lineOfElement(marksFor(ed), el, viewTop(ed.pane));
  goTo(ed, Math.floor(toEditor(ed.log, line)) + 1, { flash: true });
  ed.cm.focus();
  return true;
}

/** 닫기 전에: 읽는 화면을 편집하던 곳으로 — 접힌 절 안이면 펴고, 장 하이라이트도 그 장으로 (unfoldTo) */
function settle(ed) {
  cancelAnimationFrame(ed.raf);
  ed.raf = 0;
  const el = markAt(marksFor(ed), toView(ed.log, editorSpot(ed).at));
  if (el) unfoldTo(el);
  syncView(ed);
}

// ---- 열기·닫기 ------------------------------------------------------------------

const dirtyPaths = () => S.panes.filter((p) => p.editor?.dirty).map((p) => `${p.tab.name}: ${p.editor.path}`);
let reported = '[]';
let sending = Promise.resolve();   // 차례대로 보낸다 (늦게 간 옛 목록이 새 목록을 덮지 않게)

/** 저장하지 않은 파일 목록을 서버에 (창을 닫을 때 묻는 데 — 바뀔 때만. 못 보냈으면 다음에 다시 — initEditor 의 주기) */
function reportDirty() {
  const now = JSON.stringify(dirtyPaths());
  if (now === reported) return;
  reported = now;
  sending = sending.then(() => postJSON('/api/editing', { dirty: JSON.parse(now) })).catch(() => { reported = ''; });
}

/** 저장하지 않은 편집이 있는지 (화면을 다시 불러오기 전에 — settings.js) */
export const hasUnsavedEdits = () => dirtyPaths().length > 0;
let reloading = false;   // 사용자가 버리기로 하고 다시 불러옴 — beforeunload 에서 또 묻지 않는다

/** 화면을 다시 불러와도 되는지: 저장하지 않은 편집이 있으면 묻는다 (언어·인터넷 그림 설정) */
export function confirmReload() {
  if (!hasUnsavedEdits()) return true;
  reloading = window.confirm(t('저장하지 않은 편집이 있습니다:\n{files}\n\n화면을 다시 불러오면 이 내용은 사라집니다. 계속할까요?', { files: dirtyPaths().join('\n') }));
  return reloading;
}

function setState(ed, text) {
  ed.box.querySelector('.ed-state').textContent = text;
}

function setDirty(ed, dirty) {
  if (ed.dirty === dirty) return;
  ed.dirty = dirty;
  ed.box.classList.toggle('dirty', dirty);
  if (dirty) setState(ed, t('저장하지 않음'));
  reportDirty();
  emit('editor', ed.pane);   // 문서 탭의 ● (doctabs.js)
}

/** 편집 버튼들: 탭 막대의 [편집]은 편집 중이면 눌린 모양, 문서·코드 화면이 아니면 누를 수 없음. 상태줄의 '편집'은 편집할 수 있을 때만 */
function updateButton() {
  const editing = !!S.pane?.editor;
  const can = S.view?.type === 'doc' || S.view?.type === 'code';
  $('#lec-st-edit').hidden = !can || editing || !!S.tab?.readonly;   // 보기만 하는 프로젝트 (D71) — 탭 막대의 [편집]은 눌러서 까닭을 알린다
  const btn = $('#lec-btn-edit');
  btn.setAttribute('aria-pressed', String(editing));
  btn.disabled = !can && !editing;
}

/** 편집 모드를 연다. line: 처음 커서를 둘 원문 줄 (1부터 — 읽는 화면의 줄. 0 이면 읽던 곳). 이미 편집 중이면 그 줄로 간다 */
export async function openEditor(pane = S.pane, { line = 0 } = {}) {
  const view = pane?.current;
  if (!pane?.tab || (view?.type !== 'doc' && view?.type !== 'code')) {
    toast(t('문서나 코드를 열면 편집할 수 있습니다'));
    return;
  }
  if (blockedReadOnly(pane.tab)) return;   // Lectern 프로그램 폴더 안 (D71)
  if (pane.editor) {
    if (line) goTo(pane.editor, Math.floor(toEditor(pane.editor.log, line - 1)) + 1, { flash: true });   // 그사이 늘거나 준 줄만큼 옮겨서
    pane.editor.cm.focus();
    return;
  }
  if (pane.opening) return;   // 여는 중 (두 번 누름)
  if (pane.pending) {   // 다른 화면을 그리는 중 — 지금 보이는 것은 곧 떠날 화면이다
    toast(t('화면을 그리는 중입니다. 다 그린 뒤 다시 누르세요'));
    return;
  }
  pane.opening = true;
  const { tab } = pane;
  const { path } = view;
  try {
    const [group, mode] = EXT[extOf(path)] || [null, null];
    const [src] = await Promise.all([
      getJSON(`/api/source?p=${encodeURIComponent(tab.id)}&path=${encodeURIComponent(path)}`),
      loadLib(group),
    ]);
    if (pane.current !== view || pane.pending || !S.tabs.includes(tab)) return;   // 그사이 다른 화면으로 갔다 (또는 가는 중)
    build(pane, path, src, mode, line);
  } catch (e) {
    toast(t('편집 모드를 열지 못했습니다: {error}', { error: e.message }), 'error');
  } finally {
    pane.opening = false;
  }
}

function build(pane, path, src, mode, line) {
  const box = document.createElement('div');
  box.className = 'lec-editor';
  box.setAttribute('role', 'region');
  box.setAttribute('aria-label', t('편집 — {path}', { path }));
  box.innerHTML = `<div class="ed-head"><svg class="ed-icon" aria-hidden="true"><use href="#i-edit"/></svg>`
    + `<span class="ed-title" title="${esc(path)}">${esc(path)}</span><span class="ed-state"></span>`
    + `<button type="button" class="text-btn ed-find" title="${esc(t('찾기 (Ctrl+F) · 바꾸기 (Ctrl+H) · 줄로 가기 (Alt+G)'))}">${t('찾기·바꾸기')}</button>`
    + `<button type="button" class="primary ed-save" title="${esc(t('저장 (Ctrl+S)'))}">${t('저장')}</button>`
    + `<button type="button" class="icon-btn small ed-close" title="${esc(t('편집 닫기 (Esc) — 저장하지 않은 것이 있으면 묻습니다'))}"><svg><use href="#i-close"/></svg></button></div>`
    + '<div class="ed-body"></div>';
  pane.el.append(box);
  const ext = extOf(path);
  const indent = INDENT4.has(ext) ? 4 : 2;
  const prose = pane.current.type === 'doc';
  const ed = {
    pane, tab: pane.tab, path, box, base: { hash: src.hash }, dirty: false, saving: false, saved: false,
    inserted: [],   // 보낸 조각의 표시 (저장하면 지운다 — D63)
    // 위치 잇기 (D55): 읽는 화면을 그린 원문 뒤로 늘거나 준 줄(log — 앞에서 버린 것이 dropped 개), 저장한 때의 기록 끝(savedMark),
    // html 문서의 제목 줄(heads), 읽는 화면의 자리(marks — 다시 그리면 비움)
    log: [], dropped: 0, savedMark: null, savedHeads: null, marks: null, raf: 0,
    heads: prose && isHtml(path) ? headLines(src.text) : null,
  };
  ed.cm = window.CodeMirror(box.querySelector('.ed-body'), {
    value: src.text, mode: mode || 'text/plain', lineNumbers: true, lineWrapping: prose, styleActiveLine: true, matchBrackets: !prose,
    // autofocus 는 쓰지 않는다 — CodeMirror 가 처리기를 달기 전에 입력 칸에 초점을 주고 20ms 뒤에야 받은 것으로 치며 칸을 비워,
    // 열자마자 친 글자를 잃는다. 아래 build 끝의 cm.focus() 가 처리기를 단 뒤에 준다
    indentUnit: indent, tabSize: 4, indentWithTabs: false, spellcheck: false,
    extraKeys: {
      'Ctrl-S': () => save(ed),
      Esc: () => closeEditor(pane),
      'Ctrl-H': 'replace',
      // Tab 은 칸 들이기 (탭 글자 대신 빈칸). 고른 줄이 있으면 그 줄들을 한 단계 들인다
      Tab: (cm) => (cm.somethingSelected() ? cm.indentSelection('add') : cm.replaceSelection(' '.repeat(cm.getOption('indentUnit')))),
      'Shift-Tab': (cm) => cm.indentSelection('subtract'),
    },
  });
  ed.clean = ed.cm.changeGeneration(true);
  ed.cm.on('changes', () => setDirty(ed, !ed.cm.isClean(ed.clean)));
  ed.cm.on('change', (cm, change) => logChange(ed.log, change));
  ed.cm.on('scroll', () => follow(ed));
  ed.cm.on('cursorActivity', () => follow(ed));
  box.querySelector('.ed-save').addEventListener('click', () => save(ed));
  box.querySelector('.ed-close').addEventListener('click', () => closeEditor(pane));
  box.querySelector('.ed-find').addEventListener('click', () => ed.cm.execCommand('findPersistent'));
  pane.editor = ed;
  // 크기·글자가 바뀌면 CodeMirror 가 잰 글자 폭·줄 높이를 다시 잰다 (사이드바·터미널·글자 크기·스타일 — 안 그러면 커서 자리가 어긋난다)
  ed.resize = new ResizeObserver(() => {
    ed.cm.refresh();
    follow(ed);
  });
  ed.resize.observe(box.querySelector('.ed-body'));
  if (src.bom || src.newline === '\r\n') setState(ed, [src.newline === '\r\n' && 'CRLF', src.bom && 'BOM'].filter(Boolean).join(' · '));
  ed.cm.refresh();
  if (line) goTo(ed, line);
  else matchView(ed);
  ed.cm.focus();
  updateButton();
  emit('editor', pane);
}

/** 그 줄(1부터)로 — 화면 맨 위 가까이에 두고 커서를 줄 머리에. flash: 잠깐 그 줄을 표시 (목차·검색에서 옴) */
function goTo(ed, line, { flash = false } = {}) {
  const { cm } = ed;
  const at = Math.max(0, Math.min(cm.lineCount() - 1, line - 1));
  cm.setCursor({ line: at, ch: 0 });
  cm.scrollTo(null, Math.max(0, cm.heightAtLine(at, 'local') - LEAD));
  if (!flash) return;
  const handle = cm.addLineClass(at, 'background', 'ed-target');
  setTimeout(() => cm.removeLineClass(handle, 'background', 'ed-target'), 1800);
}

/** 편집을 닫는다. 저장하지 않은 것이 있으면 묻는다 (ask). 닫았으면(또는 편집 중이 아니면) true.
 * sync: 읽는 화면을 편집하던 곳으로 (탭을 닫을 때는 하지 않는다) */
export function closeEditor(pane = S.pane, { ask = true, sync = true } = {}) {
  const ed = pane?.editor;
  if (!ed) return true;
  if (ask && ed.dirty && !window.confirm(t('{path} 에 저장하지 않은 편집이 있습니다. 버리고 닫을까요?', { path: ed.path }))) {
    ed.cm.focus();
    return false;
  }
  if (sync) settle(ed);
  ed.resize.disconnect();
  ed.box.remove();
  pane.editor = null;
  pane.tocLimit = null;
  reportDirty();
  updateButton();
  emit('editor', pane);
  if (pane === S.pane) {
    updateTocActive();
    pane.scroller.focus({ preventScroll: true });
  }
  return true;
}

/** 열린 편집기들의 글자 폭·줄 높이를 다시 잰다 (글자 크기·스타일이 바뀜) */
function refreshEditors() {
  for (const p of S.panes) {
    if (!p.editor) continue;
    p.editor.cm.refresh();
    follow(p.editor);
  }
}

export const toggleEditor = () => (S.pane?.editor ? closeEditor(S.pane) : openEditor(S.pane));

// ---- 담은 조각 보내기 (D63·D65) ---------------------------------------------------

/**
 * 이 탭의 md 문서(path)를 편집 모드로 열고 조각을 넣는다 — 저장은 사용자가 한다. 이미 그 문서를 편집 중이면 그 편집기에.
 * 그 문서가 문서 탭에 열려 있으면 그 탭에서, 아니면(방금 만든 새 문서) 새 문서 탭에서 연다 (D64 — 보던 문서는 그 탭에 그대로).
 * compute(원문, ed) → {line, ch, text, offset, size}: 넣을 자리와 글, 그 안의 조각 글 자리 (snippet.js 의 placeText). 넣었으면 true
 */
export async function insertIntoDoc(path, compute) {
  let pane = S.pane;
  if (!pane?.tab) return false;
  if (pane.editor?.path !== path) {
    const target = { type: 'doc', path };
    const open = docPaneOf(pane.tab, target);
    if (open) await selectDocTab(open);
    pane = open || (await openInNewTab(target)) || pane;   // 새 문서 탭을 열 수 없으면(5개 모두 저장하지 않은 편집) 지금 탭에서
    if (pane.editor?.path !== path) {
      const here = !pane.editor && pane.current?.type === 'doc' && pane.current.path === path;
      if (!here && !(await navigate(target, { pane }))) return false;   // 다른 문서를 편집 중이면 leave guard 가 묻는다
      await openEditor(pane, { line: 1 });
    }
  }
  const ed = pane.editor;
  if (!ed || ed.path !== path) return false;   // 열지 못했다 (알림은 openEditor 가)
  const put = compute(ed.cm.getValue(), ed);
  if (!put) return false;
  const { cm } = ed;
  const start = cm.indexFromPos({ line: put.line, ch: put.ch });
  cm.replaceRange(put.text, { line: put.line, ch: put.ch });
  const from = cm.posFromIndex(start + put.offset);
  const to = cm.posFromIndex(start + put.offset + put.size);
  ed.inserted.push(cm.markText(from, to, { className: 'ed-inserted' }));
  goTo(ed, from.line + 1, { flash: true });
  cm.setCursor(to, null, { scroll: false });   // 다음 조각은 그 뒤에 (커서 자리에 넣기)
  cm.focus();
  return true;
}

/** 선택된 칸의 편집 중인 md 문서 (커서 자리에 넣을 수 있는 것) — {path, line(커서 줄, 0부터)} 또는 null */
export function editingDoc() {
  const ed = S.pane?.editor;
  if (!ed || S.pane.current?.type !== 'doc' || isHtml(ed.path)) return null;
  return { path: ed.path, line: ed.cm.getCursor().line };
}

// ---- 저장 ----------------------------------------------------------------------

async function save(ed, force = false) {
  if (ed.saving) return;
  ed.saving = true;
  setState(ed, t('저장하는 중…'));
  const gen = ed.cm.changeGeneration();
  const text = ed.cm.getValue();
  const mark = ed.dropped + ed.log.length;   // 이 글까지의 줄 기록 — 읽는 화면이 이것을 다시 그리면 그 앞은 버린다
  let conflict = false;
  try {
    const r = await postJSON('/api/save', { p: ed.tab.id, path: ed.path, text, hash: ed.base.hash, force });
    ed.base = r;
    ed.clean = gen;
    ed.saved = true;
    ed.savedMark = mark;
    ed.savedHeads = ed.heads && headLines(text);
    for (const m of ed.inserted.splice(0)) m.clear();   // 넣은 조각의 표시
    const dirty = !ed.cm.isClean(gen);   // 저장하는 동안 더 친 것
    setDirty(ed, dirty);
    setState(ed, dirty ? t('저장하지 않음') : t('저장했습니다 {time}', { time: formatClock(new Date()) }));
  } catch (e) {
    conflict = e.status === 409 && !force;
    if (!conflict) {
      setState(ed, t('저장하지 않음'));
      toast(t('저장하지 못했습니다: {error}', { error: e.message }), 'error');
    }
  } finally {
    ed.saving = false;
  }
  if (!conflict) return;
  setState(ed, t('저장하지 않음'));
  if (window.confirm(t('편집하는 동안 다른 곳(Claude Code 등)에서 {path} 이(가) 바뀌었습니다.\n내 편집으로 덮어쓸까요? 취소하면 저장하지 않고 편집을 이어 갑니다.', { path: ed.path }))) {
    await save(ed, true);
  }
  ed.cm.focus();
}

// ---- 시작 ----------------------------------------------------------------------

/** 탭을 닫기 전에: 그 탭(문서 탭 모두)에서 저장하지 않은 편집이 있으면 묻기만 한다 (치우지 않는다 — 다른 물음에서 취소할 수 있다). 닫아도 되면 true */
export function confirmCloseEditor(tab) {
  const dirty = tab.panes.filter((p) => p.editor?.dirty).map((p) => p.editor.path);
  return !dirty.length || window.confirm(t('{path} 에 저장하지 않은 편집이 있습니다. 버리고 닫을까요?', { path: dirty.join(', ') }));
}

/** 닫힌 탭의 편집 상자들을 치운다 (tabs.js — 칸과 함께) */
export function disposeEditor(tab) {
  for (const p of tab.panes) if (p.editor) closeEditor(p, { ask: false, sync: false });
}

/** 읽는 화면을 다시 그렸으면 (저장 뒤 자동 새로고침 등): 저장한 글을 그렸으므로 그때까지의 줄 기록을 버리고 다시 맞춘다 */
function onRendered(pane) {
  const ed = pane.editor;
  if (!ed || pane.current?.path !== ed.path) return;
  if (ed.savedMark != null) {
    ed.log.splice(0, ed.savedMark - ed.dropped);
    ed.dropped = ed.savedMark;
    if (ed.savedHeads) ed.heads = ed.savedHeads;
    ed.savedMark = null;
    ed.savedHeads = null;
  }
  ed.marks = null;
  follow(ed);
}

export function initEditor() {
  setLeaveGuard((pane) => closeEditor(pane));   // 다른 화면으로 가기 전에 (nav.js)
  setEditJump(jumpTo);   // 편집 중에 목차·모아 보기에서 고르면 편집기가 그곳으로 (toc.js)
  on('rendered', onRendered);
  $('#lec-st-edit').addEventListener('click', () => openEditor(S.pane));
  $('#lec-btn-edit').addEventListener('click', () => toggleEditor());   // 탭 막대의 [편집] — 켜기/끄기
  // 코드 화면 머리줄의 '편집' (codeview.js 가 그린다)
  $('#lec-panes').addEventListener('click', (e) => { if (e.target.closest('.cv-edit')) openEditor(S.pane); });
  on('edit', ({ line = 0 } = {}) => openEditor(S.pane, { line }));   // 우클릭 메뉴
  on('view', updateButton);
  on('pane', updateButton);
  on('text-size', refreshEditors);
  $('#lec-theme-css').addEventListener('load', refreshEditors);   // 스타일 (글꼴이 바뀔 수 있다)
  $('#lec-user-css').addEventListener('load', refreshEditors);
  setInterval(reportDirty, 5000);   // 못 보낸 목록을 다시
  // 다시 불러오기·창 닫기 전에 (창 모드에서 창을 닫을 때는 서버가 묻는다). 설정에서 이미 버리기로 했으면 묻지 않는다
  window.addEventListener('beforeunload', (e) => { if (!reloading && hasUnsavedEdits()) e.preventDefault(); });
  updateButton();
}

/** 편집 상자 안인지 (main.js 의 단축키 — 안의 키는 편집기 것) */
export const inEditor = (target) => !!target?.closest?.('.lec-editor');
