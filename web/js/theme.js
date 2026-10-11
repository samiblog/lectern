// 문서 스타일. '자동'은 Windows 다크 모드 설정을 따라 기본/다크를 고른다.
// 고른 스타일은 설정(theme)에 저장되어 다음 실행에도 그대로 열린다.

import { S, emit } from './store.js';
import { $, esc } from './util.js';
import { saveConfig } from './api.js';

// 스타일 추가: web/themes/<id>.css 를 만들고 여기에 한 줄 추가 (선택 목록은 이 표로 만든다)
//   dark: 앱 UI·코드 색(highlight.js github / github-dark)을 어둡게
//   mermaid: Mermaid 'base' 테마의 themeVariables — 다이어그램 색을 스타일에 맞춘다
//            (바탕, 상자 채움·테두리·글자, 보조 상자, 선, 그 밖의 글자)
const mermaidColors = (dark, background, primary, border, primaryText, secondary, tertiary, line, text) => ({
  darkMode: dark, background, primaryColor: primary, primaryBorderColor: border, primaryTextColor: primaryText,
  secondaryColor: secondary, tertiaryColor: tertiary, lineColor: line, textColor: text,
});
const THEMES = {
  default: { name: '기본', dark: false, mermaid: mermaidColors(false, '#ffffff', '#e8eff7', '#2b5c8a', '#1b3a5c', '#f1f4f8', '#fbfcfd', '#5f6b78', '#1f2933') },
  report: { name: '보고서', dark: false, mermaid: mermaidColors(false, '#ffffff', '#e6edf5', '#17304f', '#17304f', '#f3f6f9', '#fafbfc', '#5d6670', '#22262b') },
  github: { name: 'GitHub', dark: false, mermaid: mermaidColors(false, '#ffffff', '#ddf4ff', '#0969da', '#1f2328', '#f6f8fa', '#ffffff', '#59636e', '#1f2328') },
  notion: { name: '노션풍', dark: false, mermaid: mermaidColors(false, '#ffffff', '#f1f1ef', '#9b9a97', '#37352f', '#f7f6f3', '#ffffff', '#787774', '#37352f') },
  paper: { name: '종이 (세피아)', dark: false, mermaid: mermaidColors(false, '#f4ecd8', '#ece0c3', '#a88b5c', '#3f2e20', '#e6d6b2', '#f0e6cd', '#8a7158', '#5b4636') },
  academic: { name: '논문', dark: false, mermaid: mermaidColors(false, '#fffff8', '#fffff8', '#111111', '#111111', '#f3f3ea', '#fffff8', '#333333', '#111111') },
  newsprint: { name: '신문', dark: false, mermaid: mermaidColors(false, '#f3f2ee', '#e9e6dc', '#2a2a2a', '#0c0c0c', '#e2dfd5', '#f3f2ee', '#444444', '#2a2a2a') },
  contrast: { name: '고대비', dark: false, mermaid: mermaidColors(false, '#ffffff', '#ffffff', '#000000', '#000000', '#dfe6f2', '#ffffff', '#000000', '#000000') },
  dark: { name: '다크', dark: true, mermaid: mermaidColors(true, '#1f242b', '#2a313a', '#6ea8e6', '#eef2f5', '#333b45', '#262c34', '#9aa5b1', '#d5dbe1') },
  nord: { name: 'Nord', dark: true, mermaid: mermaidColors(true, '#2e3440', '#3b4252', '#81a1c1', '#eceff4', '#434c5e', '#3b4252', '#88c0d0', '#d8dee9') },
  'solarized-dark': { name: 'Solarized 다크', dark: true, mermaid: mermaidColors(true, '#002b36', '#073642', '#268bd2', '#eee8d5', '#0b3d4a', '#073642', '#2aa198', '#93a1a1') },
  night: { name: '밤 종이', dark: true, mermaid: mermaidColors(true, '#1e1a15', '#2c261e', '#b08a55', '#f0dcb4', '#352d23', '#2c261e', '#c9a46c', '#d4c8b0') },
};

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

function fillPicker() {
  const group = (label, dark) => `<optgroup label="${label}">${Object.entries(THEMES)
    .filter(([, th]) => th.dark === dark)
    .map(([id, th]) => `<option value="${esc(id)}">${esc(th.name)}</option>`).join('')}</optgroup>`;
  $('#lec-theme').innerHTML = `<option value="auto">자동 (시스템)</option>${group('밝은 스타일', false)}${group('어두운 스타일', true)}`;
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
