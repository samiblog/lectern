// 문서 스타일. '자동'은 Windows 다크 모드 설정을 따라 기본/다크를 고른다.
// 고른 스타일은 설정(theme)에 저장되어 다음 실행에도 그대로 열린다.

import { S, emit } from './store.js';
import { $, esc } from './util.js';
import { saveConfig } from './api.js';

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
  default: light('기본', 'work', 'clean', 'light', mermaidColors(false, '#ffffff', '#e8eff7', '#2b5c8a', '#1b3a5c', '#f1f4f8', '#fbfcfd', '#5f6b78', '#1f2933')),
  report: light('보고서', 'work', 'clean', 'light', mermaidColors(false, '#ffffff', '#e6edf5', '#17304f', '#17304f', '#f3f6f9', '#fafbfc', '#5d6670', '#22262b')),
  office: light('사내 문서', 'work', 'clean', 'light', mermaidColors(false, '#ffffff', '#dae3f3', '#2f5597', '#1f3864', '#f2f6fc', '#ffffff', '#595959', '#262626')),
  consulting: light('컨설팅', 'work', 'color', 'light', mermaidColors(false, '#ffffff', '#e3f3f5', '#13a3b2', '#0b2545', '#eef2f7', '#ffffff', '#556270', '#1d2733')),
  notion: light('노션풍', 'work', 'clean', 'light', mermaidColors(false, '#ffffff', '#f1f1ef', '#9b9a97', '#37352f', '#f7f6f3', '#ffffff', '#787774', '#37352f')),
  contrast: light('고대비', 'work', 'clean', 'light', mermaidColors(false, '#ffffff', '#ffffff', '#000000', '#000000', '#dfe6f2', '#ffffff', '#000000', '#000000')),
  paper: light('종이 (세피아)', 'read', 'warm', 'paper', mermaidColors(false, '#f4ecd8', '#ece0c3', '#a88b5c', '#3f2e20', '#e6d6b2', '#f0e6cd', '#8a7158', '#5b4636')),
  book: light('책', 'read', 'warm', 'paper', mermaidColors(false, '#fdfbf6', '#f1eadc', '#a89478', '#4a3424', '#f6f0e4', '#fdfbf6', '#6b6155', '#2b2620')),
  academic: light('논문', 'read', 'warm', 'paper', mermaidColors(false, '#fffff8', '#fffff8', '#111111', '#111111', '#f3f3ea', '#fffff8', '#333333', '#111111')),
  newsprint: light('신문', 'read', 'warm', 'paper', mermaidColors(false, '#f3f2ee', '#e9e6dc', '#2a2a2a', '#0c0c0c', '#e2dfd5', '#f3f2ee', '#444444', '#2a2a2a')),
  magazine: light('잡지', 'read', 'warm', 'paper', mermaidColors(false, '#fbfaf7', '#f6e5e2', '#b0251b', '#111111', '#efebe3', '#fbfaf7', '#5f5a54', '#262422')),
  manuscript: light('원고 (타자기)', 'read', 'clean', 'light', mermaidColors(false, '#f7f7f5', '#ebebe6', '#222222', '#222222', '#f2f2ef', '#f7f7f5', '#5a5a5a', '#222222')),
  github: light('GitHub', 'dev', 'clean', 'light', mermaidColors(false, '#ffffff', '#ddf4ff', '#0969da', '#1f2328', '#f6f8fa', '#ffffff', '#59636e', '#1f2328')),
  docsite: light('문서 사이트', 'dev', 'color', 'light', mermaidColors(false, '#ffffff', '#e7f0f8', '#1f6fae', '#1d4f7c', '#f3f6f9', '#ffffff', '#5c6670', '#404040')),
  'solarized-light': light('Solarized 라이트', 'dev', 'color', 'light', mermaidColors(false, '#fdf6e3', '#eee8d5', '#93a1a1', '#073642', '#f5eedb', '#fdf6e3', '#657b83', '#3d5258')),
  'gruvbox-light': light('Gruvbox 라이트', 'dev', 'color', 'light', mermaidColors(false, '#fbf1c7', '#ebdbb2', '#bdae93', '#3c3836', '#f2e5bc', '#fbf1c7', '#7c6f64', '#3c3836')),
  dark: dark('다크', mermaidColors(true, '#1f242b', '#2a313a', '#6ea8e6', '#eef2f5', '#333b45', '#262c34', '#9aa5b1', '#d5dbe1')),
  'github-dark': dark('GitHub 다크', mermaidColors(true, '#0d1117', '#161b22', '#4493f8', '#f0f6fc', '#21262d', '#161b22', '#9198a1', '#c9d1d9')),
  nord: dark('Nord', mermaidColors(true, '#2e3440', '#3b4252', '#81a1c1', '#eceff4', '#434c5e', '#3b4252', '#88c0d0', '#d8dee9')),
  'solarized-dark': dark('Solarized 다크', mermaidColors(true, '#002b36', '#073642', '#268bd2', '#eee8d5', '#0b3d4a', '#073642', '#2aa198', '#93a1a1')),
  dracula: dark('Dracula', mermaidColors(true, '#282a36', '#343746', '#bd93f9', '#f8f8f2', '#44475a', '#21222c', '#8be9fd', '#f8f8f2')),
  'one-dark': dark('One Dark', mermaidColors(true, '#282c34', '#2c313c', '#61afef', '#e6e6e6', '#3e4451', '#21252b', '#9da5b4', '#abb2bf')),
  night: dark('밤 종이', mermaidColors(true, '#1e1a15', '#2c261e', '#b08a55', '#f0dcb4', '#352d23', '#2c261e', '#c9a46c', '#d4c8b0')),
  ink: dark('먹 (완전 검정)', mermaidColors(true, '#000000', '#161616', '#8cc4ff', '#ffffff', '#1f1f1f', '#0a0a0a', '#a3a3a3', '#d4d4d4')),
};

// 스타일 선택 목록을 묶는 방식 (설정 theme_groups — 설정 창에서 고른다). 묶음은 이 순서로 보인다
export const GROUPINGS = {
  use: { name: '용도별', groups: { work: '업무·보고', read: '읽기·출판', dev: '개발·기술', dark: '어두운' } },
  mood: { name: '분위기별', groups: { clean: '깔끔한', warm: '따뜻한·종이', color: '색이 있는', dark: '어두운' } },
  tone: { name: '밝기별', groups: { light: '밝은', paper: '종이·책', dark: '어두운' } },
};
const groupOf = (th, kind) => (th.dark ? 'dark' : th[kind]);
export const grouping = () => (GROUPINGS[S.config.theme_groups] ? S.config.theme_groups : 'use');

const media = window.matchMedia('(prefers-color-scheme: dark)');

export function resolvedTheme() {
  const t = S.config.theme || 'auto';
  if (t === 'auto') return media.matches ? 'dark' : 'default';
  return THEMES[t] ? t : 'default';
}

/** mermaid.initialize 에 넘길 테마 설정 */
export function mermaidTheme() {
  const th = THEMES[resolvedTheme()];
  return { theme: 'base', themeVariables: th.mermaid };
}

export function applyTheme() {
  const id = resolvedTheme();
  const th = THEMES[id];
  $('#lec-theme-css').href = `/static/themes/${id}.css`;
  $('#lec-hljs-css').href = `/static/vendor/highlight/${th.dark ? 'github-dark' : 'github'}.min.css`;
  document.documentElement.dataset.ui = th.dark ? 'dark' : 'light';
  document.documentElement.dataset.theme = id;
  $('#lec-theme').value = S.config.theme || 'auto';
}

/** 스타일 선택 목록을 지금 묶는 방식(설정 theme_groups)으로 채운다. 설정 창에서 방식을 바꾸면 다시 부른다 */
export function fillPicker() {
  const kind = grouping();
  const groups = Object.entries(GROUPINGS[kind].groups).map(([key, label]) => {
    const items = Object.entries(THEMES).filter(([, th]) => groupOf(th, kind) === key);
    return `<optgroup label="${esc(label)}">${items.map(([id, th]) => `<option value="${esc(id)}">${esc(th.name)}</option>`).join('')}</optgroup>`;
  });
  $('#lec-theme').innerHTML = `<option value="auto">자동 (시스템)</option>${groups.join('')}`;
  $('#lec-theme').value = S.config.theme || 'auto';
}

export function initTheme() {
  fillPicker();
  $('#lec-theme').addEventListener('change', async (e) => {
    await saveConfig({ theme: e.target.value });
    applyTheme();
    emit('refresh-view');   // mermaid 다이어그램은 테마를 바꾸면 다시 그려야 한다
  });
  media.addEventListener('change', () => {
    if ((S.config.theme || 'auto') !== 'auto') return;
    applyTheme();
    emit('refresh-view');
  });
  applyTheme();
}
