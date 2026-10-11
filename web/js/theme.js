// 문서 스타일. '자동'은 Windows 다크 모드 설정을 따라 기본/다크를 고른다.
// 고른 스타일은 설정(theme)에 저장되어 다음 실행에도 그대로 열린다.

import { S, emit } from './store.js';
import { $, esc } from './util.js';
import { saveConfig } from './api.js';

// 스타일 추가: web/themes/<id>.css 를 만들고 여기에 한 줄 추가 (선택 목록은 이 표로 만든다)
//   dark: 앱 UI·코드 색(highlight.js github / github-dark)을 어둡게
//   mermaid: Mermaid 기본 테마 이름, 또는 'base' + mermaidVars 로 스타일 색에 맞춤
const THEMES = {
  default: { name: '기본', dark: false, mermaid: 'default' },
  report: { name: '보고서', dark: false, mermaid: 'neutral' },
  github: { name: 'GitHub', dark: false, mermaid: 'default' },
  notion: { name: '노션풍', dark: false, mermaid: 'neutral' },
  paper: {
    name: '종이 (세피아)', dark: false, mermaid: 'base',
    mermaidVars: {
      background: '#f4ecd8', primaryColor: '#ece0c3', primaryBorderColor: '#a88b5c', primaryTextColor: '#3f2e20',
      secondaryColor: '#e6d6b2', tertiaryColor: '#f0e6cd', lineColor: '#8a7158', textColor: '#5b4636',
    },
  },
  academic: { name: '논문', dark: false, mermaid: 'neutral' },
  newsprint: { name: '신문', dark: false, mermaid: 'neutral' },
  contrast: { name: '고대비', dark: false, mermaid: 'default' },
  dark: { name: '다크', dark: true, mermaid: 'dark' },
  nord: {
    name: 'Nord', dark: true, mermaid: 'base',
    mermaidVars: {
      darkMode: true, background: '#2e3440', primaryColor: '#3b4252', primaryBorderColor: '#81a1c1', primaryTextColor: '#eceff4',
      secondaryColor: '#434c5e', tertiaryColor: '#3b4252', lineColor: '#88c0d0', textColor: '#d8dee9',
    },
  },
  'solarized-dark': {
    name: 'Solarized 다크', dark: true, mermaid: 'base',
    mermaidVars: {
      darkMode: true, background: '#002b36', primaryColor: '#073642', primaryBorderColor: '#268bd2', primaryTextColor: '#eee8d5',
      secondaryColor: '#0b3d4a', tertiaryColor: '#073642', lineColor: '#2aa198', textColor: '#93a1a1',
    },
  },
  night: {
    name: '밤 종이', dark: true, mermaid: 'base',
    mermaidVars: {
      darkMode: true, background: '#1e1a15', primaryColor: '#2c261e', primaryBorderColor: '#b08a55', primaryTextColor: '#f0dcb4',
      secondaryColor: '#352d23', tertiaryColor: '#2c261e', lineColor: '#c9a46c', textColor: '#d4c8b0',
    },
  },
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
  return { theme: th.mermaid, themeVariables: th.mermaidVars || {} };
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
