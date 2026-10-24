// 문서 스타일. '자동'은 Windows 다크 모드 설정을 따라 기본/다크를 고른다.
// 고른 스타일은 설정(theme)에 저장되어 다음 실행에도 그대로 열린다.
// 내 스타일 (D53): 설정 폴더의 styles\*.css (GET /api/styles) — id 'user:<파일 이름>'. 머리 주석이 정한 바탕 스타일(base)의 파일 위에
// 그 파일(/userstyle/<파일> — 서버가 인터넷 길을 지운 것)을 #lec-user-css 로 얹는다. 목록 맨 아래 '내 스타일' 묶음.
// 3초마다 목록을 다시 받아, 파일이 생기거나 고쳐지면(Claude Code 가 저장하면) 바로 반영한다.

import { S, emit } from './store.js';
import { $, esc } from './util.js';
import { saveConfig, getJSON } from './api.js';
import { t } from './i18n.js';

// 스타일 추가: web/themes/<id>.css 를 만들고 여기에 한 줄 추가 (선택 목록은 이 표로 만든다)
//   dark: 앱 UI·코드 색(highlight.js github / github-dark)을 어둡게. 어두운 스타일은 어느 묶는 방식에서나 '어두운' 묶음
//   use / mood / tone: 밝은 스타일이 들어갈 묶음 — 용도별·분위기별·밝기별 (GROUPINGS)
//   mermaid: Mermaid 'base' 테마의 themeVariables — 다이어그램 색을 스타일에 맞춘다
//            (바탕, 상자 채움·테두리·글자, 보조 상자, 선, 그 밖의 글자)
const mermaidColors = (dark, background, primary, border, primaryText, secondary, tertiary, line, text) => ({
  darkMode: dark, background, primaryColor: primary, primaryBorderColor: border, primaryTextColor: primaryText,
  secondaryColor: secondary, tertiaryColor: tertiary, lineColor: line, textColor: text,
});
const light = (name, use, mood, tone, mermaid) => ({ name, dark: false, use, mood, tone, mermaid });
const dark = (name, mermaid) => ({ name, dark: true, mermaid });
const THEMES = {
  default: light(t('기본'), 'work', 'clean', 'light', mermaidColors(false, '#ffffff', '#e8eff7', '#2b5c8a', '#1b3a5c', '#f1f4f8', '#fbfcfd', '#5f6b78', '#1f2933')),
  report: light(t('보고서'), 'work', 'clean', 'light', mermaidColors(false, '#ffffff', '#e6edf5', '#17304f', '#17304f', '#f3f6f9', '#fafbfc', '#5d6670', '#22262b')),
  office: light(t('사내 문서'), 'work', 'clean', 'light', mermaidColors(false, '#ffffff', '#dae3f3', '#2f5597', '#1f3864', '#f2f6fc', '#ffffff', '#595959', '#262626')),
  consulting: light(t('컨설팅'), 'work', 'color', 'light', mermaidColors(false, '#ffffff', '#e3f3f5', '#13a3b2', '#0b2545', '#eef2f7', '#ffffff', '#556270', '#1d2733')),
  notion: light(t('노션풍'), 'work', 'clean', 'light', mermaidColors(false, '#ffffff', '#f1f1ef', '#9b9a97', '#37352f', '#f7f6f3', '#ffffff', '#787774', '#37352f')),
  contrast: light(t('고대비'), 'work', 'clean', 'light', mermaidColors(false, '#ffffff', '#ffffff', '#000000', '#000000', '#dfe6f2', '#ffffff', '#000000', '#000000')),
  paper: light(t('종이 (세피아)'), 'read', 'warm', 'paper', mermaidColors(false, '#f4ecd8', '#ece0c3', '#a88b5c', '#3f2e20', '#e6d6b2', '#f0e6cd', '#8a7158', '#5b4636')),
  book: light(t('책'), 'read', 'warm', 'paper', mermaidColors(false, '#fdfbf6', '#f1eadc', '#a89478', '#4a3424', '#f6f0e4', '#fdfbf6', '#6b6155', '#2b2620')),
  academic: light(t('논문'), 'read', 'warm', 'paper', mermaidColors(false, '#fffff8', '#fffff8', '#111111', '#111111', '#f3f3ea', '#fffff8', '#333333', '#111111')),
  newsprint: light(t('신문'), 'read', 'warm', 'paper', mermaidColors(false, '#f3f2ee', '#e9e6dc', '#2a2a2a', '#0c0c0c', '#e2dfd5', '#f3f2ee', '#444444', '#2a2a2a')),
  magazine: light(t('잡지'), 'read', 'warm', 'paper', mermaidColors(false, '#fbfaf7', '#f6e5e2', '#b0251b', '#111111', '#efebe3', '#fbfaf7', '#5f5a54', '#262422')),
  manuscript: light(t('원고 (타자기)'), 'read', 'clean', 'light', mermaidColors(false, '#f7f7f5', '#ebebe6', '#222222', '#222222', '#f2f2ef', '#f7f7f5', '#5a5a5a', '#222222')),
  github: light('GitHub', 'dev', 'clean', 'light', mermaidColors(false, '#ffffff', '#ddf4ff', '#0969da', '#1f2328', '#f6f8fa', '#ffffff', '#59636e', '#1f2328')),
  docsite: light(t('문서 사이트'), 'dev', 'color', 'light', mermaidColors(false, '#ffffff', '#e7f0f8', '#1f6fae', '#1d4f7c', '#f3f6f9', '#ffffff', '#5c6670', '#404040')),
  'solarized-light': light(t('Solarized 라이트'), 'dev', 'color', 'light', mermaidColors(false, '#fdf6e3', '#eee8d5', '#93a1a1', '#073642', '#f5eedb', '#fdf6e3', '#657b83', '#3d5258')),
  'gruvbox-light': light(t('Gruvbox 라이트'), 'dev', 'color', 'light', mermaidColors(false, '#fbf1c7', '#ebdbb2', '#bdae93', '#3c3836', '#f2e5bc', '#fbf1c7', '#7c6f64', '#3c3836')),
  dark: dark(t('다크'), mermaidColors(true, '#1f242b', '#2a313a', '#6ea8e6', '#eef2f5', '#333b45', '#262c34', '#9aa5b1', '#d5dbe1')),
  'github-dark': dark(t('GitHub 다크'), mermaidColors(true, '#0d1117', '#161b22', '#4493f8', '#f0f6fc', '#21262d', '#161b22', '#9198a1', '#c9d1d9')),
  nord: dark('Nord', mermaidColors(true, '#2e3440', '#3b4252', '#81a1c1', '#eceff4', '#434c5e', '#3b4252', '#88c0d0', '#d8dee9')),
  'solarized-dark': dark(t('Solarized 다크'), mermaidColors(true, '#002b36', '#073642', '#268bd2', '#eee8d5', '#0b3d4a', '#073642', '#2aa198', '#93a1a1')),
  dracula: dark('Dracula', mermaidColors(true, '#282a36', '#343746', '#bd93f9', '#f8f8f2', '#44475a', '#21222c', '#8be9fd', '#f8f8f2')),
  'one-dark': dark('One Dark', mermaidColors(true, '#282c34', '#2c313c', '#61afef', '#e6e6e6', '#3e4451', '#21252b', '#9da5b4', '#abb2bf')),
  night: dark(t('밤 종이'), mermaidColors(true, '#1e1a15', '#2c261e', '#b08a55', '#f0dcb4', '#352d23', '#2c261e', '#c9a46c', '#d4c8b0')),
  ink: dark(t('먹 (완전 검정)'), mermaidColors(true, '#000000', '#161616', '#8cc4ff', '#ffffff', '#1f1f1f', '#0a0a0a', '#a3a3a3', '#d4d4d4')),
};

// 스타일 선택 목록을 묶는 방식 (설정 theme_groups — 설정 창에서 고른다). 묶음은 이 순서로 보인다
export const GROUPINGS = {
  use: { name: t('용도별'), groups: { work: t('업무·보고'), read: t('읽기·출판'), dev: t('개발·기술'), dark: t('어두운') } },
  mood: { name: t('분위기별'), groups: { clean: t('깔끔한'), warm: t('따뜻한·종이'), color: t('색이 있는'), dark: t('어두운') } },
  tone: { name: t('밝기별'), groups: { light: t('밝은'), paper: t('종이·책'), dark: t('어두운') } },
};
const groupOf = (th, kind) => (th.dark ? 'dark' : th[kind]);
export const grouping = () => (GROUPINGS[S.config.theme_groups] ? S.config.theme_groups : 'use');

const media = window.matchMedia('(prefers-color-scheme: dark)');

// ---- 내 스타일 (D53) ----------------------------------------------------------------
const USER_POLL_MS = 3000;
let userStyles = [];                    // [{id, file, name, dark, base, mtime}]
let userPlace = { dir: '', guide: '' };   // 스타일 폴더와 만드는 법(설명서) 파일의 전체 경로

/** 내 스타일 목록을 받는다. 받았으면 true */
export async function loadUserStyles() {
  try {
    const d = await getJSON('/api/styles');
    userStyles = d.styles || [];
    userPlace = { dir: d.dir || '', guide: d.guide || '' };
    return true;
  } catch {
    return false;
  }
}

/** 설정 창이 쓰는 것: 스타일 폴더·설명서 경로와 스타일 수 */
export const userStyleInfo = () => ({ ...userPlace, count: userStyles.length });

const userStyle = (id) => userStyles.find((s) => s.id === id);
const themeOf = (id) => THEMES[id] || userStyle(id);

/** 파일이 생기거나 고쳐졌으면 목록·화면에 반영한다 (보는 중인 내 스타일이면 다시 입히고 다시 그린다 — 다이어그램 색) */
async function syncUserStyles() {
  if (document.hidden) return;
  const before = JSON.stringify(userStyles);
  if (!(await loadUserStyles()) || JSON.stringify(userStyles) === before) return;
  fillPicker();
  emit('user-styles');
  if ((S.config.theme || '').startsWith('user:')) {
    applyTheme();
    redrawAfterLoad();
  }
}

/** 다시 그린다 — 내 스타일이면 새 css 를 다 불러온 뒤에 (다이어그램 색을 그 CSS 변수에서 읽는다, mermaidFromCss) */
function redrawAfterLoad() {
  if (!userStyle(resolvedTheme())) {
    emit('refresh-view');
    return;
  }
  // 주소가 바뀐(아직 불러오는 중인) css 만 기다린다 — setHref 가 단 표시를 load·error 가 지운다
  const loaded = (link) => new Promise((resolve) => {
    if (!link.dataset.loading) {
      resolve();
      return;
    }
    link.addEventListener('load', resolve, { once: true });
    link.addEventListener('error', resolve, { once: true });
    setTimeout(resolve, 3000);
  });
  Promise.all([loaded($('#lec-theme-css')), loaded($('#lec-user-css'))]).then(() => emit('refresh-view'));
}

/** 스타일 파일의 주소를 바꾼다 (같으면 그대로). 바뀌면 다 불러올 때까지 data-loading (redrawAfterLoad) */
function setHref(link, href) {
  if (link.getAttribute('href') === href) return;
  if (href) {
    link.dataset.loading = '1';
    link.href = href;
  } else {
    delete link.dataset.loading;
    link.removeAttribute('href');
  }
}

export function resolvedTheme() {
  const id = S.config.theme || 'auto';
  if (id === 'auto') return media.matches ? 'dark' : 'default';
  return themeOf(id) ? id : 'default';
}

/** 내 스타일의 Mermaid 색: 그 스타일의 CSS 변수에서 (바탕·표 머리·제목·글자·코드 바탕·흐린 글자) */
function mermaidFromCss(dark) {
  const css = getComputedStyle(document.documentElement);
  const v = (name, fallback) => css.getPropertyValue(name).trim() || fallback;
  const bg = v('--md-bg', dark ? '#1f242b' : '#ffffff');
  const heading = v('--md-heading', dark ? '#eef2f5' : '#1b3a5c');
  return mermaidColors(dark, bg, v('--md-th-bg', dark ? '#2a313a' : '#e8eff7'), heading, heading,
    v('--md-code-bg', dark ? '#333b45' : '#f1f4f8'), bg, v('--md-muted', dark ? '#9aa5b1' : '#5f6b78'), v('--md-fg', dark ? '#d5dbe1' : '#1f2933'));
}

/** mermaid.initialize 에 넘길 테마 설정 */
export function mermaidTheme() {
  const id = resolvedTheme();
  const th = THEMES[id];
  return { theme: 'base', themeVariables: th ? th.mermaid : mermaidFromCss(userStyle(id).dark) };
}

export function applyTheme() {
  const id = resolvedTheme();
  const th = themeOf(id);
  const user = userStyle(id);
  setHref($('#lec-theme-css'), `/static/themes/${user ? user.base : id}.css`);
  setHref($('#lec-user-css'), user ? `/userstyle/${encodeURIComponent(user.file)}?v=${user.mtime}` : '');
  $('#lec-hljs-css').href = `/static/vendor/highlight/${th.dark ? 'github-dark' : 'github'}.min.css`;
  document.documentElement.dataset.ui = th.dark ? 'dark' : 'light';
  document.documentElement.dataset.theme = id;
  $('#lec-theme').value = themeOf(S.config.theme) ? S.config.theme : 'auto';
  updateSteps();
}

/** 스타일 선택 목록을 지금 묶는 방식(설정 theme_groups)으로 채운다 (맨 아래 '내 스타일'). 설정 창에서 방식을 바꾸면 다시 부른다 */
export function fillPicker() {
  const kind = grouping();
  const groups = Object.entries(GROUPINGS[kind].groups).map(([key, label]) => {
    const items = Object.entries(THEMES).filter(([, th]) => groupOf(th, kind) === key);
    return `<optgroup label="${esc(label)}">${items.map(([id, th]) => `<option value="${esc(id)}">${esc(th.name)}</option>`).join('')}</optgroup>`;
  });
  const mine = userStyles.length
    ? `<optgroup label="${esc(t('내 스타일'))}">${userStyles.map((s) => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join('')}</optgroup>`
    : '';
  $('#lec-theme').innerHTML = `<option value="auto">${t('자동 (시스템)')}</option>${groups.join('')}${mine}`;
  $('#lec-theme').value = themeOf(S.config.theme) ? S.config.theme : 'auto';
  updateSteps();
}

/** 위·아래 버튼: 목록의 맨 처음·맨 끝이면 누를 수 없다 */
function updateSteps() {
  const sel = $('#lec-theme');
  $('#lec-theme-prev').disabled = sel.selectedIndex <= 0;
  $('#lec-theme-next').disabled = sel.selectedIndex >= sel.options.length - 1;
}

function choose(value) {
  saveConfig({ theme: value });   // S.config 는 바로 바뀌고 저장은 뒤에서 — 위·아래를 빠르게 눌러도 화면이 바로 따라온다
  applyTheme();
  redrawAfterLoad();   // mermaid 다이어그램은 테마를 바꾸면 다시 그려야 한다
}

/** 목록에서 바로 위(-1)·아래(+1) 스타일로. 지금 묶는 방식의 목록 순서를 따른다 ('자동'이 맨 위) */
function step(dir) {
  const sel = $('#lec-theme');
  const next = sel.options[sel.selectedIndex + dir];
  if (next) choose(next.value);
}

export function initTheme() {
  for (const link of [$('#lec-theme-css'), $('#lec-user-css')]) {
    const done = () => { delete link.dataset.loading; };
    link.addEventListener('load', done);
    link.addEventListener('error', done);
  }
  fillPicker();
  $('#lec-theme').addEventListener('change', (e) => choose(e.target.value));
  $('#lec-theme-prev').addEventListener('click', () => step(-1));
  $('#lec-theme-next').addEventListener('click', () => step(1));
  media.addEventListener('change', () => {
    if ((S.config.theme || 'auto') !== 'auto') return;
    applyTheme();
    emit('refresh-view');
  });
  applyTheme();
  setInterval(syncUserStyles, USER_POLL_MS);
}
