// 오른쪽 터미널 (D38): 프로젝트 탭마다 셸(기본 Windows PowerShell 5.1)을 그 프로젝트 폴더에서 띄워 보인다.
// 화면은 xterm.js (web/vendor/xterm — 처음 열 때 불러온다), 셸은 서버의 Windows 의사 콘솔 (lectern/terminal.py·conpty.py).
// 키 입력은 POST /api/term/input, 출력은 긴 폴링 GET /api/term/read (from: 받은 곳까지). 터미널 API 는 페이지에 실린
// 실행마다 새 비밀값(meta lec-term → X-Term 헤더)을 함께 보낸다.
//
// - 사용자가 버튼·Ctrl+` 로 열 때만 시작한다 (앱을 켤 때마다 닫힌 채). 셸로 명령을 보내는 길은 사용자의 키 입력뿐이다 —
//   예외는 사용자가 우클릭 메뉴에서 고른 '터미널에 붙여 넣기'(D51)이고, 이것도 Ctrl+V 와 같은 길로 Enter 없이 넣는다 (pasteToTerminal).
// - 패널을 닫아도 셸은 그대로 돈다. 탭을 닫으면 끝난다 — 셸에서 띄운 프로그램이 돌고 있으면 먼저 묻는다 (tabs.js).
//   다른 탭을 고르면 그 탭의 셸로 바뀐다 (패널이 열려 있으면 그 탭의 셸을 띄운다).
// - 자리는 오른쪽 또는 문서 아래 (D52 — 설정 terminal_position: auto 면 창이 세로로 길 때 아래). 오른쪽이면 목차 자리를 쓰므로
//   목차를 감춘다 (목차 버튼으로 함께 볼 수 있다 — toc.js). 아래면 #lec-main 이 격자가 되어 문서·목차 아래에 전체 폭으로 놓인다.
// - 색은 문서 스타일을 따른다 (아래 '색'). 설정 창에서 끄면 늘 어둡게.
// - 터미널 모음(gather.js)은 탭마다의 화면(tab.term.box)을 이 패널에서 모음 칸으로 옮겨 보이고, 닫으면 되돌린다 (returnTerminals).
//   모으는 동안(gathered) 이 패널은 화면을 옮기거나 감추지 않는다. 셸이 생기거나 끝나면 'terms' 이벤트.
// - 터미널 안에서는 앱 단축키를 쓰지 않는다 (main.js — Ctrl+` 만 예외). Ctrl+C 는 고른 글이 있으면 복사, 없으면 셸로(중단).
//   Ctrl+V 는 붙여 넣기. 우클릭은 Windows 콘솔처럼 고른 글이 있으면 복사, 없으면 붙여 넣기.

import { S, on, emit } from './store.js';
import { getJSON, postJSON, saveConfig } from './api.js';
import { updateTocVisibility } from './toc.js';
import { $, toast, copyText } from './util.js';
import { t } from './i18n.js';

const TERM_HEADER = { 'X-Term': document.querySelector('meta[name="lec-term"]')?.content || '' };
const MIN_WIDTH = 280;
const DOC_MIN = 360;   // 본문에 남길 폭
const MIN_HEIGHT = 120;      // 아래 터미널의 높이 (D52)
const DOC_MIN_HEIGHT = 160;  // 아래 터미널 위에 문서를 남길 높이
const SEND_CHUNK = 16384;
const root = document.documentElement;

// ---- 색 (문서 스타일을 따른다 — 설정 terminal_follow_style, 끄면 늘 DARK) ----------------------
// 바탕·글자·커서·선택 색은 지금 스타일의 CSS 변수(코드 블록 바탕 --md-code-bg, 글자 --md-fg, 링크 --md-link)에서,
// ANSI 16색은 이름이 같은 터미널 색표가 있는 스타일은 그것을, 나머지는 밝은/어두운 기본 색표를 쓴다.
// 셸·프로그램은 어두운 바탕을 가정하고 흰 글자 등을 쓰므로(PSReadLine 의 숫자 등), 글자와 그 칸 바탕의 대비가
// MIN_CONTRAST 보다 낮으면 xterm 이 글자 색을 진하게·옅게 고친다 (minimumContrastRatio — 밝은 바탕에서도 다 읽히게).
const MIN_CONTRAST = 4.5;
const ANSI = ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white',
  'brightBlack', 'brightRed', 'brightGreen', 'brightYellow', 'brightBlue', 'brightMagenta', 'brightCyan', 'brightWhite'];
const ansi = (...colors) => Object.fromEntries(ANSI.map((name, i) => [name, colors[i]]));
const PALETTES = {
  // Windows Terminal 의 Campbell (파랑만 밝게)
  dark: ansi('#0c0c0c', '#c50f1f', '#13a10e', '#c19c00', '#3b78ff', '#a23fb0', '#3a96dd', '#cccccc',
    '#767676', '#e74856', '#16c60c', '#f9f1a5', '#5f9bff', '#c75fd6', '#61d6d6', '#f2f2f2'),
  // 밝은 바탕용: 흰색(white·brightWhite)은 프로그램이 '또렷한 글자'로 쓰므로 어두운 회색·검정으로
  light: ansi('#24292f', '#c4262e', '#116329', '#8a5a00', '#0b62c4', '#8250df', '#1b7c83', '#57606a',
    '#6e7781', '#a40e26', '#1a7f37', '#9a6700', '#0550ae', '#6639ba', '#136061', '#1f2328'),
  solarized: ansi('#073642', '#dc322f', '#859900', '#b58900', '#268bd2', '#d33682', '#2aa198', '#eee8d5',
    '#002b36', '#cb4b16', '#586e75', '#657b83', '#839496', '#6c71c4', '#93a1a1', '#fdf6e3'),
  'gruvbox-light': ansi('#fbf1c7', '#cc241d', '#98971a', '#d79921', '#458588', '#b16286', '#689d6a', '#7c6f64',
    '#928374', '#9d0006', '#79740e', '#b57614', '#076678', '#8f3f71', '#427b58', '#3c3836'),
  nord: ansi('#3b4252', '#bf616a', '#a3be8c', '#ebcb8b', '#81a1c1', '#b48ead', '#88c0d0', '#e5e9f0',
    '#4c566a', '#bf616a', '#a3be8c', '#ebcb8b', '#81a1c1', '#b48ead', '#8fbcbb', '#eceff4'),
  dracula: ansi('#21222c', '#ff5555', '#50fa7b', '#f1fa8c', '#bd93f9', '#ff79c6', '#8be9fd', '#f8f8f2',
    '#6272a4', '#ff6e6e', '#69ff94', '#ffffa5', '#d6acff', '#ff92df', '#a4ffff', '#ffffff'),
  'one-dark': ansi('#282c34', '#e06c75', '#98c379', '#e5c07b', '#61afef', '#c678dd', '#56b6c2', '#dcdfe4',
    '#5a6374', '#e06c75', '#98c379', '#e5c07b', '#61afef', '#c678dd', '#56b6c2', '#dcdfe4'),
  github: ansi('#24292f', '#cf222e', '#116329', '#4d2d00', '#0969da', '#8250df', '#1b7c83', '#6e7781',
    '#57606a', '#a40e26', '#1a7f37', '#633c01', '#218bff', '#a475f9', '#3192aa', '#8c959f'),
  'github-dark': ansi('#484f58', '#ff7b72', '#3fb950', '#d29922', '#58a6ff', '#bc8cff', '#39c5cf', '#b1bac4',
    '#6e7681', '#ffa198', '#56d364', '#e3b341', '#79c0ff', '#d2a8ff', '#56d4dd', '#ffffff'),
};
// 스타일 id → 색표 (없으면 밝기에 따라 light / dark). 새 스타일은 따로 적지 않아도 된다
const PALETTE_OF = { 'solarized-light': 'solarized', 'solarized-dark': 'solarized' };

// 늘 어둡게: 스타일과 상관없이 (설정 terminal_follow_style 끔)
const DARK = {
  background: '#1e1f22', foreground: '#cccccc', cursor: '#e6e6e6', cursorAccent: '#1e1f22',
  selectionBackground: '#3a5f8f', selectionInactiveBackground: '#33414f', ...PALETTES.dark,
};

/** '#rgb'·'#rrggbb' 를 투명도를 준 rgba() 로 (그 밖의 형식이면 그대로) */
function withAlpha(color, alpha) {
  let hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(color)?.[1];
  if (!hex) return color;
  if (hex.length === 3) hex = [...hex].map((c) => c + c).join('');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/** 지금 터미널 색 {theme(xterm), dark}. 스타일 파일(--md-*)이 적용된 뒤에 부른다 */
function currentColors() {
  if (S.config.terminal_follow_style === false) return { theme: DARK, dark: true };
  const dark = root.dataset.ui === 'dark';
  const css = getComputedStyle(root);
  const v = (name, fallback) => css.getPropertyValue(name).trim() || fallback;
  const background = v('--md-code-bg', DARK.background);
  const foreground = v('--md-fg', DARK.foreground);
  const accent = v('--md-link', foreground);
  const palette = PALETTES[PALETTE_OF[root.dataset.theme] || root.dataset.theme] || PALETTES[dark ? 'dark' : 'light'];
  return {
    dark,
    theme: {
      background, foreground, cursor: accent, cursorAccent: background,
      selectionBackground: withAlpha(accent, dark ? 0.4 : 0.25), selectionInactiveBackground: withAlpha(accent, dark ? 0.25 : 0.14),
      ...palette,
    },
  };
}

/** 패널·모음 칸과 열린 모든 터미널에 지금 색을 입힌다 (스타일을 바꾸거나 설정을 바꿀 때) */
function applyColors() {
  const { theme, dark } = currentColors();
  root.style.setProperty('--term-bg', theme.background);   // 터미널 둘레 여백도 같은 바탕 (app.css — 패널과 모음 칸)
  root.classList.toggle('term-light', !dark);              // 스크롤바 색 (color-scheme)
  for (const tab of S.tabs) if (tab.term) tab.term.xterm.options.theme = theme;
  return theme;
}
// PC 에 있는 글꼴만 (D26): 고정폭 영문 → 한글 고정폭 → 맑은 고딕
const FONT = '"Cascadia Mono", "Cascadia Code", Consolas, D2Coding, "NanumGothicCoding", "Malgun Gothic", monospace';

let open = false;
export const terminalOpen = () => open;
/** 터미널 모음(gather.js)이 화면들을 가져가 있는지 */
export const gathered = () => root.classList.contains('gather-on');

// ---- xterm.js 불러오기 (처음 열 때 한 번) -------------------------------------------

let loading = null;
const loaded = () => typeof window.Terminal === 'function' && window.FitAddon?.FitAddon && window.Unicode11Addon?.Unicode11Addon;

function script(src) {
  return new Promise((resolve, reject) => {
    const el = document.createElement('script');
    el.src = src;
    el.onload = resolve;
    el.onerror = () => reject(new Error(t('{name} 를 불러오지 못했습니다', { name: src })));
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
    if (!loaded()) throw new Error(t('터미널 화면 라이브러리를 불러오지 못했습니다. Lectern 을 다시 실행해 보세요'));
  })();
  loading.catch(() => { loading = null; });
  return loading;
}

// ---- 셸 하나 (탭마다 tab.term) -------------------------------------------------------

const sleep = (ms) => new Promise((resolve) => { setTimeout(resolve, ms); });

/** 탭의 화면(xterm)을 만든다 (parent: 오른쪽 패널 또는 모음 칸). 셸은 start() 가 띄운다 */
function create(tab, parent = $('#lec-term-body')) {
  const box = document.createElement('div');
  box.className = 'term-box';
  box.hidden = true;
  parent.append(box);
  const xterm = new window.Terminal({
    fontFamily: FONT, fontSize: 13, lineHeight: 1.1, cursorBlink: true, scrollback: 5000,
    allowProposedApi: true,   // unicode11 (한글처럼 두 칸인 글자의 폭)
    theme: applyColors(), minimumContrastRatio: MIN_CONTRAST,
  });
  const fit = new window.FitAddon.FitAddon();
  xterm.loadAddon(fit);
  xterm.loadAddon(new window.Unicode11Addon.Unicode11Addon());
  xterm.unicode.activeVersion = '11';
  xterm.open(box);
  const term = { tab, box, xterm, fit, id: null, next: 0, alive: false, starting: null, pending: '', sending: false, shell: '' };
  xterm.onData((data) => {
    if (term.alive) send(term, data);
    else if (!term.starting && data === '\r') start(term);   // 끝난 셸: Enter 로 다시 시작
  });
  xterm.onResize(({ cols, rows }) => {
    if (term.alive) postJSON('/api/term/resize', { t: term.id, cols, rows }, TERM_HEADER).catch(() => {});
  });
  xterm.attachCustomKeyEventHandler((e) => keyFor(term, e));
  box.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    if (xterm.hasSelection()) copySelection(term);
    else pasteFromClipboard(term);
  });
  tab.term = term;
  return term;
}

async function copySelection(term) {
  const text = term.xterm.getSelection();
  term.xterm.clearSelection();
  if (text) toast(await copyText(text) ? t('복사했습니다') : t('복사하지 못했습니다'));
  term.xterm.focus();   // copyText 가 잠시 다른 칸을 쓸 수 있다
}

async function pasteFromClipboard(term) {
  try {
    term.xterm.paste(await navigator.clipboard.readText());
  } catch {
    toast(t('붙여 넣지 못했습니다. Ctrl+V 로 붙여 넣으세요'));
  }
}

/** xterm 이 키를 셸로 보내기 전에. false 면 xterm 이 다루지 않는다 (브라우저 기본 동작이나 앱이 다룬다) */
function keyFor(term, e) {
  if (e.type !== 'keydown') return true;
  const ctrl = e.ctrlKey && !e.altKey && !e.metaKey;
  if (ctrl && (e.code === 'Backquote' || e.key === 'Tab')) return false;     // 패널 열고 닫기, 다음·이전 탭 (main.js)
  if (ctrl && e.code === 'KeyC' && (e.shiftKey || term.xterm.hasSelection())) {   // 고른 글 복사 (없으면 Ctrl+C 는 셸로 — 중단)
    e.preventDefault();
    copySelection(term);
    return false;
  }
  if (ctrl && e.code === 'KeyV') return false;   // 브라우저의 붙여 넣기 → xterm 이 받아 셸로 보낸다
  return true;
}

/** 키 입력을 순서대로 보낸다. 보내는 중에 친 것은 모았다가 이어서 */
function send(term, data) {
  term.pending += data;
  if (!term.sending) flush(term);
}

async function flush(term) {
  term.sending = true;
  while (term.pending && term.alive) {
    let n = Math.min(SEND_CHUNK, term.pending.length);
    if (n < term.pending.length && /[\ud800-\udbff]/.test(term.pending[n - 1])) n += 1;   // 대리 문자 쌍을 가르지 않게
    const chunk = term.pending.slice(0, n);
    term.pending = term.pending.slice(n);
    try {
      await postJSON('/api/term/input', { t: term.id, data: chunk }, TERM_HEADER);
    } catch {
      term.pending = '';
    }
  }
  term.sending = false;
}

/** 셸을 띄운다 (끝난 셸이면 새로). 이미 돌고 있는 셸이 서버에 있으면 그것에 붙고, 남은 출력부터 다시 보인다 */
function start(term) {
  term.starting ??= (async () => {
    try {
      fitNow(term);
      const d = await postJSON('/api/term/open', { p: term.tab.id, cols: term.xterm.cols, rows: term.xterm.rows }, TERM_HEADER);
      if (term.id && term.id !== d.id) term.xterm.write('\r\n');
      Object.assign(term, { id: d.id, next: 0, alive: true, shell: d.shell });
      showTitle();
      emit('terms');
      pump(term, d.id);
    } catch (e) {
      term.xterm.write(`\r\n\x1b[91m${e.message}\x1b[0m\r\n`);
    } finally {
      term.starting = null;
    }
  })();
  return term.starting;
}

/** 출력 받기: 긴 폴링을 이어 간다. 셸이 끝나거나 탭이 닫히면 멈춘다 */
async function pump(term, id) {
  while (term.id === id && term.alive && S.tabs.includes(term.tab)) {
    let d;
    try {
      d = await getJSON(`/api/term/read?t=${encodeURIComponent(id)}&from=${term.next}`, TERM_HEADER);
    } catch (e) {
      if (e.status === 404) {
        d = { data: '', next: term.next, alive: false, exit: null };
      } else {
        await sleep(1000);   // 서버가 잠시 답하지 않음
        continue;
      }
    }
    if (term.id !== id) return;
    if (d.data) term.xterm.write(d.data);
    term.next = d.next;
    if (!d.alive) {
      term.alive = false;
      const code = d.exit != null ? ` (${t('종료 코드 {code}', { code: d.exit })})` : '';
      term.xterm.write(`\r\n\x1b[90m[${t('셸이 끝났습니다{code}. Enter 를 누르면 다시 시작합니다', { code })}]\x1b[0m\r\n`);
      emit('terms');
    }
  }
}

function fitNow(term) {
  if (!term || term.box.hidden || !term.box.clientWidth) return;
  try {
    term.fit.fit();
  } catch { /* 크기를 잴 수 없는 순간 */ }
}

/** 다시 시작: 탭의 셸(과 거기서 띄운 프로그램)을 끝내고 새로 */
export async function restartTerminal(tab = S.tab) {
  const term = tab?.term;
  if (!term) return;
  const old = term.id;
  term.id = null;   // 지금 받는 출력(끝났다는 알림 포함)은 버린다 — pump
  if (term.alive) {
    term.alive = false;
    await postJSON('/api/term/close', { t: old }, TERM_HEADER).catch(() => {});
  }
  term.xterm.reset();
  await start(term);
  term.xterm.focus();
}

// ---- 패널 ---------------------------------------------------------------------

function showTitle() {
  const term = S.tab?.term;
  const name = S.tab ? `${term?.shell || 'PowerShell'} — ${S.tab.name}` : t('터미널 — 열린 프로젝트가 없습니다');
  $('#lec-term-title').textContent = name;
  $('#lec-term-title').title = S.tab ? S.tab.root : '';
}

/** 선택된 탭의 셸을 보인다 (없으면 만든다 — 패널이 열려 있을 때만). 터미널 모음이 화면을 가져가 있으면 제목만 */
async function showCurrent({ focus = false } = {}) {
  showTitle();
  if (gathered()) return;
  for (const tab of S.tabs) if (tab.term) tab.term.box.hidden = tab !== S.tab;
  if (!open || !S.tab) return;
  try {
    await loadLib();
  } catch (e) {
    toast(e.message, 'error');
    return;
  }
  const tab = S.tab;
  const term = tab.term || create(tab);
  term.box.hidden = false;
  fitNow(term);
  if (!term.alive && !term.id) await start(term);
  if (focus && tab === S.tab) term.xterm.focus();
}

/** 패널을 열고 닫는다 (버튼·Ctrl+`). 닫아도 셸은 그대로 돈다 */
export function toggleTerminal(want = !open) {
  open = want;
  root.classList.toggle('term-on', open);
  if (!open) root.classList.remove('toc-with-term');
  $('#lec-term').hidden = !open;
  $('#lec-term-resizer').hidden = !open;
  $('#lec-btn-term').classList.toggle('on', open);
  $('#lec-btn-term').setAttribute('aria-pressed', String(open));
  updateTocVisibility();
  if (open) showCurrent({ focus: true });
  else if (document.activeElement?.closest?.('#lec-term')) $('#lec-content')?.focus({ preventScroll: true });
}

/** 탭을 닫기 전에: 그 탭의 셸에서 프로그램이 돌고 있으면 묻는다. 닫아도 되면 true */
export async function confirmCloseTerminal(tab) {
  const term = tab.term;
  if (!term?.alive) return true;
  try {
    const info = await getJSON(`/api/term/info?t=${encodeURIComponent(term.id)}`, TERM_HEADER);
    if (!info.busy) return true;
  } catch {
    return true;
  }
  return window.confirm(t("'{name}' 탭의 터미널에서 프로그램이 실행 중입니다. 탭을 닫으면 함께 끝납니다. 닫을까요?", { name: tab.name }));
}

/** 닫힌 탭의 화면을 치운다 (셸은 서버가 탭을 닫을 때 끝낸다) */
export function disposeTerminal(tab) {
  const term = tab.term;
  if (!term) return;
  term.alive = false;
  term.id = null;
  term.xterm.dispose();
  term.box.remove();
  tab.term = null;
  emit('terms');
}

/**
 * 글을 선택된 탭의 터미널에 붙여 넣는다 — 우클릭 메뉴의 '터미널에 붙여 넣기' (D51, 'term-paste' 이벤트).
 * 사용자의 Ctrl+V 와 같은 길이다 (xterm 의 paste → onData → POST /api/term/input). 끝의 줄바꿈은 떼어 Enter 를 누르지 않는다.
 * 터미널이 닫혀 있으면 열고 셸을 띄운다. 여러 줄이면, 받는 프로그램이 붙여넣기 모드(bracketed paste — Claude Code 등)를
 * 켜 두지 않았을 때 한 번 묻는다 — 셸 프롬프트에서는 줄마다 명령으로 실행될 수 있다 (Windows Terminal 처럼).
 */
export async function pasteToTerminal(text) {
  const tab = S.tab;
  text = String(text ?? '').replace(/[\r\n]+$/, '');
  if (!tab || !text) return;
  if (!gathered()) {
    if (!open) toggleTerminal(true);
    await showCurrent();
  }
  const term = tab.term;
  if (!term || tab !== S.tab) return;   // 화면 라이브러리를 읽지 못함 (showCurrent 가 알렸다), 또는 그사이 다른 탭
  if (term.starting) await term.starting;
  if (!term.alive) {
    toast(t('터미널 셸이 끝나 있습니다. 터미널에서 Enter 를 누르면 다시 시작합니다'), 'error');
    return;
  }
  const lines = text.split(/\r\n|\r|\n/).length;
  if (lines > 1 && !term.xterm.modes.bracketedPasteMode
    && !window.confirm(t('{n}줄을 터미널에 붙여 넣습니다. 셸 프롬프트에서는 줄마다 명령으로 실행될 수 있습니다. 붙여 넣을까요?', { n: lines }))) {
    return;
  }
  term.xterm.paste(text);
  term.xterm.focus();
}

// ---- 터미널 모음(gather.js)이 쓰는 것 ----------------------------------------------------

export const fitTerminal = fitNow;

/** 셸이 돌고 있는 탭 수 (탭 막대의 '터미널 모음' 버튼) */
export const liveTerminals = () => S.tabs.filter((tab) => tab.term?.alive).length;

/** 탭의 터미널을 parent(모음 칸)에 보이고, 셸이 없으면 띄운다 */
export async function ensureTerminal(tab, parent) {
  await loadLib();
  const term = tab.term || create(tab, parent);
  if (term.box.parentElement !== parent) parent.append(term.box);
  term.box.hidden = false;
  fitNow(term);
  if (!term.alive && !term.id) await start(term);
  return term;
}

/** 셸에서 띄운 프로그램이 도는지. 모르면 null */
export async function terminalBusy(term) {
  if (!term?.alive) return false;
  try {
    return (await getJSON(`/api/term/info?t=${encodeURIComponent(term.id)}`, TERM_HEADER)).busy;
  } catch {
    return null;
  }
}

/** 모음 칸에 옮겨 둔 화면들을 오른쪽 패널로 되돌린다 (터미널 모음을 닫을 때) */
export function returnTerminals() {
  const body = $('#lec-term-body');
  for (const tab of S.tabs) if (tab.term && tab.term.box.parentElement !== body) body.append(tab.term.box);
  showCurrent();
}

// ---- 자리: 오른쪽 / 아래 (D52) ----------------------------------------------------------
// 설정 terminal_position: auto(창이 세로로 길면 — 높이 ≥ 폭 — 아래, 아니면 오른쪽) | side | bottom. 머리줄 버튼은 side·bottom 을 바꾼다

const portrait = window.matchMedia('(orientation: portrait)');
const placeSetting = () => (['side', 'bottom'].includes(S.config.terminal_position) ? S.config.terminal_position : 'auto');

/** 터미널을 문서 아래에 두는지 */
export const terminalBelow = () => placeSetting() === 'bottom' || (placeSetting() === 'auto' && portrait.matches);

function applyPlace() {
  const below = terminalBelow();
  root.classList.toggle('term-bottom', below);
  const handle = $('#lec-term-resizer');
  handle.setAttribute('aria-orientation', below ? 'horizontal' : 'vertical');
  handle.title = below ? t('끌어서 터미널 높이 조절 (두 번 누르면 기본 높이)') : t('끌어서 터미널 폭 조절 (두 번 누르면 기본 폭)');
  const btn = $('#lec-term-place');
  btn.title = below ? t('터미널을 오른쪽으로') : t('터미널을 아래로');
  btn.querySelector('use').setAttribute('href', below ? '#i-term-side' : '#i-term-bottom');
  updateTocVisibility();
}

function applyWidth() {
  const px = Number(S.config.terminal_width);
  if (px) root.style.setProperty('--term-w', `${Math.round(px)}px`);
  else root.style.removeProperty('--term-w');   // app.css 의 기본 폭
  const h = Number(S.config.terminal_height);
  if (h) root.style.setProperty('--term-h', `${Math.round(h)}px`);
  else root.style.removeProperty('--term-h');   // 기본 높이
}

/** 경계를 끌어 폭(아래에 두면 높이)을 바꾼다. 두 번 누르면 기본 */
function bindResizer() {
  const handle = $('#lec-term-resizer');
  handle.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    handle.setPointerCapture(e.pointerId);
    const main = $('#lec-main').getBoundingClientRect();
    const below = terminalBelow();
    const sizeAt = below
      ? (ev) => Math.round(Math.max(MIN_HEIGHT, Math.min(main.height - DOC_MIN_HEIGHT, main.bottom - ev.clientY)))
      : (ev) => Math.round(Math.max(MIN_WIDTH, Math.min(main.width - DOC_MIN, main.right - ev.clientX)));
    const move = (ev) => root.style.setProperty(below ? '--term-h' : '--term-w', `${sizeAt(ev)}px`);
    const busy = [below ? 'resizing-rows' : 'resizing', 'resizing-term'];
    const up = (ev) => {
      handle.removeEventListener('pointermove', move);
      handle.removeEventListener('pointerup', up);
      root.classList.remove(...busy);
      if (below ? ev.clientY !== e.clientY : ev.clientX !== e.clientX) saveConfig({ [below ? 'terminal_height' : 'terminal_width']: sizeAt(ev) });
    };
    root.classList.add(...busy);
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', up);
  });
  handle.addEventListener('dblclick', async () => {
    await saveConfig({ [terminalBelow() ? 'terminal_height' : 'terminal_width']: null });
    applyWidth();
  });
}

export function initTerminal() {
  $('#lec-term-close').addEventListener('click', () => toggleTerminal(false));
  $('#lec-term-restart').addEventListener('click', () => restartTerminal());
  // 머리줄 버튼: 오른쪽 ↔ 아래 (설정이 자동이었으면 이제 그 자리로 고정 — 설정 창에서 자동으로 되돌린다)
  $('#lec-term-place').addEventListener('click', async () => {
    await saveConfig({ terminal_position: terminalBelow() ? 'side' : 'bottom' });
    applyPlace();
  });
  portrait.addEventListener('change', applyPlace);   // 창 모양이 바뀜 (자동일 때만 자리가 바뀐다)
  on('term-place', applyPlace);                      // 설정 창
  bindResizer();
  applyWidth();
  applyPlace();
  // 패널 크기가 바뀌면 글자 칸 수를 다시 맞춘다 (셸에도 알린다 — onResize)
  let raf = 0;
  new ResizeObserver(() => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => { if (!gathered()) fitNow(S.tab?.term); });
  }).observe($('#lec-term-body'));
  // 다른 탭을 고르면 그 탭의 셸로. 터미널에서 Ctrl+Tab 으로 왔으면 새 셸에 입력이 가게
  on('tab', () => showCurrent({ focus: !!document.activeElement?.closest?.('#lec-term') }));
  // 색: 스타일 파일을 바꿔 끼우면(theme.js) 다 불러온 뒤에 CSS 변수를 읽는다. 설정 창에서 '스타일에 맞춤'을 바꿔도
  $('#lec-theme-css').addEventListener('load', applyColors);
  on('term-colors', applyColors);
  on('term-paste', pasteToTerminal);   // 우클릭 메뉴의 '터미널에 붙여 넣기' (ui.js)
  applyColors();
}
