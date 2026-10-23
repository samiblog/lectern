// 오른쪽 터미널 (D38): 프로젝트 탭마다 셸(기본 Windows PowerShell 5.1)을 그 프로젝트 폴더에서 띄워 보인다.
// 화면은 xterm.js (web/vendor/xterm — 처음 열 때 불러온다), 셸은 서버의 Windows 의사 콘솔 (lectern/terminal.py·conpty.py).
// 키 입력은 POST /api/term/input, 출력은 긴 폴링 GET /api/term/read (from: 받은 곳까지). 터미널 API 는 페이지에 실린
// 실행마다 새 비밀값(meta lec-term → X-Term 헤더)을 함께 보낸다.
//
// - 사용자가 버튼·Ctrl+` 로 열 때만 시작한다 (앱을 켤 때마다 닫힌 채). 셸로 명령을 보내는 길은 사용자의 키 입력뿐이다.
// - 패널을 닫아도 셸은 그대로 돈다. 탭을 닫으면 끝난다 — 셸에서 띄운 프로그램이 돌고 있으면 먼저 묻는다 (tabs.js).
//   다른 탭을 고르면 그 탭의 셸로 바뀐다 (패널이 열려 있으면 그 탭의 셸을 띄운다).
// - 터미널을 열면 목차를 감춘다 (본문 폭) — 목차 버튼으로 함께 볼 수 있다 (toc.js).
// - 터미널 안에서는 앱 단축키를 쓰지 않는다 (main.js — Ctrl+` 만 예외). Ctrl+C 는 고른 글이 있으면 복사, 없으면 셸로(중단).
//   Ctrl+V 는 붙여 넣기. 우클릭은 Windows 콘솔처럼 고른 글이 있으면 복사, 없으면 붙여 넣기.

import { S, on } from './store.js';
import { getJSON, postJSON, saveConfig } from './api.js';
import { updateTocVisibility } from './toc.js';
import { $, toast, copyText } from './util.js';

const TERM_HEADER = { 'X-Term': document.querySelector('meta[name="lec-term"]')?.content || '' };
const MIN_WIDTH = 280;
const DOC_MIN = 360;   // 본문에 남길 폭
const SEND_CHUNK = 16384;
const root = document.documentElement;

// 셸 글자 색(PSReadLine 기본)이 어두운 바탕을 가정하므로 스타일과 상관없이 어둡게 (Windows Terminal 의 Campbell)
const THEME = {
  background: '#1e1f22', foreground: '#cccccc', cursor: '#e6e6e6', cursorAccent: '#1e1f22', selectionBackground: '#3a5f8f',
  black: '#0c0c0c', red: '#c50f1f', green: '#13a10e', yellow: '#c19c00', blue: '#3b78ff', magenta: '#a23fb0', cyan: '#3a96dd', white: '#cccccc',
  brightBlack: '#767676', brightRed: '#e74856', brightGreen: '#16c60c', brightYellow: '#f9f1a5', brightBlue: '#5f9bff',
  brightMagenta: '#c75fd6', brightCyan: '#61d6d6', brightWhite: '#f2f2f2',
};
// PC 에 있는 글꼴만 (D26): 고정폭 영문 → 한글 고정폭 → 맑은 고딕
const FONT = '"Cascadia Mono", "Cascadia Code", Consolas, D2Coding, "NanumGothicCoding", "Malgun Gothic", monospace';

let open = false;
export const terminalOpen = () => open;

// ---- xterm.js 불러오기 (처음 열 때 한 번) -------------------------------------------

let loading = null;
const loaded = () => typeof window.Terminal === 'function' && window.FitAddon?.FitAddon && window.Unicode11Addon?.Unicode11Addon;

function script(src) {
  return new Promise((resolve, reject) => {
    const el = document.createElement('script');
    el.src = src;
    el.onload = resolve;
    el.onerror = () => reject(new Error(`${src} 를 불러오지 못했습니다`));
    document.head.append(el);
  });
}

function loadLib() {
  if (loaded()) return Promise.resolve();
  loading ??= (async () => {
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = '/static/vendor/xterm/xterm.css';
    document.head.append(css);
    await script('/static/vendor/xterm/xterm.js');
    await Promise.all([script('/static/vendor/xterm/addon-fit.js'), script('/static/vendor/xterm/addon-unicode11.js')]);
    // 문서 속 id 가 window.<id> 로 잡혀 이름을 가릴 수 있다 — 진짜 라이브러리인지 본다 (mermaid.js 처럼)
    if (!loaded()) throw new Error('터미널 화면 라이브러리를 불러오지 못했습니다');
  })();
  loading.catch(() => { loading = null; });
  return loading;
}

// ---- 셸 하나 (탭마다 tab.term) -------------------------------------------------------

const sleep = (ms) => new Promise((resolve) => { setTimeout(resolve, ms); });

/** 탭의 화면(xterm)을 만든다. 셸은 start() 가 띄운다 */
function create(tab) {
  const box = document.createElement('div');
  box.className = 'term-box';
  box.hidden = true;
  $('#lec-term-body').append(box);
  const xterm = new window.Terminal({
    fontFamily: FONT, fontSize: 13, lineHeight: 1.1, cursorBlink: true, scrollback: 5000,
    allowProposedApi: true,   // unicode11 (한글처럼 두 칸인 글자의 폭)
    theme: THEME,
  });
  const fit = new window.FitAddon.FitAddon();
  xterm.loadAddon(fit);
  xterm.loadAddon(new window.Unicode11Addon.Unicode11Addon());
  xterm.unicode.activeVersion = '11';
  xterm.open(box);
  const t = { tab, box, xterm, fit, id: null, next: 0, alive: false, starting: null, pending: '', sending: false, shell: '' };
  xterm.onData((data) => {
    if (t.alive) send(t, data);
    else if (!t.starting && data === '\r') start(t);   // 끝난 셸: Enter 로 다시 시작
  });
  xterm.onResize(({ cols, rows }) => {
    if (t.alive) postJSON('/api/term/resize', { t: t.id, cols, rows }, TERM_HEADER).catch(() => {});
  });
  xterm.attachCustomKeyEventHandler((e) => keyFor(t, e));
  box.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    if (xterm.hasSelection()) copySelection(t);
    else pasteFromClipboard(t);
  });
  tab.term = t;
  return t;
}

async function copySelection(t) {
  const text = t.xterm.getSelection();
  t.xterm.clearSelection();
  if (text) toast(await copyText(text) ? '복사했습니다' : '복사하지 못했습니다');
  t.xterm.focus();   // copyText 가 잠시 다른 칸을 쓸 수 있다
}

async function pasteFromClipboard(t) {
  try {
    t.xterm.paste(await navigator.clipboard.readText());
  } catch {
    toast('붙여 넣지 못했습니다. Ctrl+V 로 붙여 넣으세요');
  }
}

/** xterm 이 키를 셸로 보내기 전에. false 면 xterm 이 다루지 않는다 (브라우저 기본 동작이나 앱이 다룬다) */
function keyFor(t, e) {
  if (e.type !== 'keydown') return true;
  const ctrl = e.ctrlKey && !e.altKey && !e.metaKey;
  if (ctrl && (e.code === 'Backquote' || e.key === 'Tab')) return false;     // 패널 열고 닫기, 다음·이전 탭 (main.js)
  if (ctrl && e.code === 'KeyC' && (e.shiftKey || t.xterm.hasSelection())) {   // 고른 글 복사 (없으면 Ctrl+C 는 셸로 — 중단)
    e.preventDefault();
    copySelection(t);
    return false;
  }
  if (ctrl && e.code === 'KeyV') return false;   // 브라우저의 붙여 넣기 → xterm 이 받아 셸로 보낸다
  return true;
}

/** 키 입력을 순서대로 보낸다. 보내는 중에 친 것은 모았다가 이어서 */
function send(t, data) {
  t.pending += data;
  if (!t.sending) flush(t);
}

async function flush(t) {
  t.sending = true;
  while (t.pending && t.alive) {
    let n = Math.min(SEND_CHUNK, t.pending.length);
    if (n < t.pending.length && /[\ud800-\udbff]/.test(t.pending[n - 1])) n += 1;   // 대리 문자 쌍을 가르지 않게
    const chunk = t.pending.slice(0, n);
    t.pending = t.pending.slice(n);
    try {
      await postJSON('/api/term/input', { t: t.id, data: chunk }, TERM_HEADER);
    } catch {
      t.pending = '';
    }
  }
  t.sending = false;
}

/** 셸을 띄운다 (끝난 셸이면 새로). 이미 돌고 있는 셸이 서버에 있으면 그것에 붙고, 남은 출력부터 다시 보인다 */
function start(t) {
  t.starting ??= (async () => {
    try {
      fitNow(t);
      const d = await postJSON('/api/term/open', { p: t.tab.id, cols: t.xterm.cols, rows: t.xterm.rows }, TERM_HEADER);
      if (t.id && t.id !== d.id) t.xterm.write('\r\n');
      Object.assign(t, { id: d.id, next: 0, alive: true, shell: d.shell });
      showTitle();
      pump(t, d.id);
    } catch (e) {
      t.xterm.write(`\r\n\x1b[91m${e.message}\x1b[0m\r\n`);
    } finally {
      t.starting = null;
    }
  })();
  return t.starting;
}

/** 출력 받기: 긴 폴링을 이어 간다. 셸이 끝나거나 탭이 닫히면 멈춘다 */
async function pump(t, id) {
  while (t.id === id && t.alive && S.tabs.includes(t.tab)) {
    let d;
    try {
      d = await getJSON(`/api/term/read?t=${encodeURIComponent(id)}&from=${t.next}`, TERM_HEADER);
    } catch (e) {
      if (e.status === 404) {
        d = { data: '', next: t.next, alive: false, exit: null };
      } else {
        await sleep(1000);   // 서버가 잠시 답하지 않음
        continue;
      }
    }
    if (t.id !== id) return;
    if (d.data) t.xterm.write(d.data);
    t.next = d.next;
    if (!d.alive) {
      t.alive = false;
      const code = d.exit != null ? ` (종료 코드 ${d.exit})` : '';
      t.xterm.write(`\r\n\x1b[90m[셸이 끝났습니다${code}. Enter 를 누르면 다시 시작합니다]\x1b[0m\r\n`);
    }
  }
}

function fitNow(t) {
  if (!t || t.box.hidden || !t.box.clientWidth) return;
  try {
    t.fit.fit();
  } catch { /* 크기를 잴 수 없는 순간 */ }
}

/** 다시 시작: 지금 셸(과 거기서 띄운 프로그램)을 끝내고 새로 */
async function restart() {
  const t = S.tab?.term;
  if (!t) return;
  const old = t.id;
  t.id = null;   // 지금 받는 출력(끝났다는 알림 포함)은 버린다 — pump
  if (t.alive) {
    t.alive = false;
    await postJSON('/api/term/close', { t: old }, TERM_HEADER).catch(() => {});
  }
  t.xterm.reset();
  await start(t);
  t.xterm.focus();
}

// ---- 패널 ---------------------------------------------------------------------

function showTitle() {
  const t = S.tab?.term;
  const name = S.tab ? `${t?.shell || 'PowerShell'} — ${S.tab.name}` : '터미널 — 열린 프로젝트가 없습니다';
  $('#lec-term-title').textContent = name;
  $('#lec-term-title').title = S.tab ? S.tab.root : '';
}

/** 선택된 탭의 셸을 보인다 (없으면 만든다 — 패널이 열려 있을 때만) */
async function showCurrent({ focus = false } = {}) {
  for (const tab of S.tabs) if (tab.term) tab.term.box.hidden = tab !== S.tab;
  showTitle();
  if (!open || !S.tab) return;
  try {
    await loadLib();
  } catch (e) {
    toast(e.message, 'error');
    return;
  }
  const tab = S.tab;
  const t = tab.term || create(tab);
  t.box.hidden = false;
  fitNow(t);
  if (!t.alive && !t.id) await start(t);
  if (focus && tab === S.tab) t.xterm.focus();
}

/** 패널을 열고 닫는다 (버튼·Ctrl+`). 닫아도 셸은 그대로 돈다 */
export function toggleTerminal(want = !open) {
  open = want;
  root.classList.toggle('term-on', open);
  if (!open) root.classList.remove('toc-with-term');
  $('#lec-term').hidden = !open;
  $('#lec-term-resizer').hidden = !open;
  $('#lec-btn-term').classList.toggle('on', open);
  updateTocVisibility();
  if (open) showCurrent({ focus: true });
  else if (document.activeElement?.closest?.('#lec-term')) $('#lec-content')?.focus({ preventScroll: true });
}

/** 탭을 닫기 전에: 그 탭의 셸에서 프로그램이 돌고 있으면 묻는다. 닫아도 되면 true */
export async function confirmCloseTerminal(tab) {
  const t = tab.term;
  if (!t?.alive) return true;
  try {
    const info = await getJSON(`/api/term/info?t=${encodeURIComponent(t.id)}`, TERM_HEADER);
    if (!info.busy) return true;
  } catch {
    return true;
  }
  return window.confirm(`'${tab.name}' 탭의 터미널에서 프로그램이 실행 중입니다. 탭을 닫으면 함께 끝납니다. 닫을까요?`);
}

/** 닫힌 탭의 화면을 치운다 (셸은 서버가 탭을 닫을 때 끝낸다) */
export function disposeTerminal(tab) {
  const t = tab.term;
  if (!t) return;
  t.alive = false;
  t.id = null;
  t.xterm.dispose();
  t.box.remove();
  tab.term = null;
}

function applyWidth() {
  const px = Number(S.config.terminal_width);
  if (px) root.style.setProperty('--term-w', `${Math.round(px)}px`);
  else root.style.removeProperty('--term-w');   // app.css 의 기본 폭
}

function bindResizer() {
  const handle = $('#lec-term-resizer');
  handle.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    handle.setPointerCapture(e.pointerId);
    const main = $('#lec-main').getBoundingClientRect();
    const widthAt = (ev) => Math.round(Math.max(MIN_WIDTH, Math.min(main.width - DOC_MIN, main.right - ev.clientX)));
    const move = (ev) => root.style.setProperty('--term-w', `${widthAt(ev)}px`);
    const up = (ev) => {
      handle.removeEventListener('pointermove', move);
      handle.removeEventListener('pointerup', up);
      root.classList.remove('resizing', 'resizing-term');
      if (ev.clientX !== e.clientX) saveConfig({ terminal_width: widthAt(ev) });
    };
    root.classList.add('resizing', 'resizing-term');
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', up);
  });
  handle.addEventListener('dblclick', () => {
    saveConfig({ terminal_width: null });
    applyWidth();
  });
}

export function initTerminal() {
  $('#lec-btn-term').addEventListener('click', () => toggleTerminal());
  $('#lec-term-close').addEventListener('click', () => toggleTerminal(false));
  $('#lec-term-restart').addEventListener('click', restart);
  bindResizer();
  applyWidth();
  // 패널 크기가 바뀌면 글자 칸 수를 다시 맞춘다 (셸에도 알린다 — onResize)
  let raf = 0;
  new ResizeObserver(() => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => fitNow(S.tab?.term));
  }).observe($('#lec-term-body'));
  // 다른 탭을 고르면 그 탭의 셸로. 터미널에서 Ctrl+Tab 으로 왔으면 새 셸에 입력이 가게
  on('tab', () => showCurrent({ focus: !!document.activeElement?.closest?.('#lec-term') }));
}
