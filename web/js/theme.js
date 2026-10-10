// 문서 스타일 (기본 / 보고서 / 다크, '자동'은 Windows 다크 모드 설정을 따름)

import { S, emit } from './store.js';
import { $ } from './util.js';
import { saveConfig } from './api.js';

// 테마 추가: web/themes/<id>.css 를 만들고 여기에 한 줄 추가, index.html 의 <select>에 option 추가
const THEMES = {
  default: { dark: false, mermaid: 'default' },
  report: { dark: false, mermaid: 'neutral' },
  dark: { dark: true, mermaid: 'dark' },
};

const media = window.matchMedia('(prefers-color-scheme: dark)');

export function resolvedTheme() {
  const t = S.config.theme || 'auto';
  if (t === 'auto') return media.matches ? 'dark' : 'default';
  return THEMES[t] ? t : 'default';
}

export const mermaidTheme = () => THEMES[resolvedTheme()].mermaid;

export function applyTheme() {
  const id = resolvedTheme();
  const th = THEMES[id];
  $('#lec-theme-css').href = `/static/themes/${id}.css`;
  $('#lec-hljs-css').href = `/static/vendor/highlight/${th.dark ? 'github-dark' : 'github'}.min.css`;
  document.documentElement.dataset.ui = th.dark ? 'dark' : 'light';
  document.documentElement.dataset.theme = id;
  $('#lec-theme').value = S.config.theme || 'auto';
}

export function initTheme() {
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
