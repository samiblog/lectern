// 사이드바 폭 조절 (ROADMAP 2-5): 오른쪽 경계를 끌어 200~480px, 두 번 누르면 기본 폭. 값은 설정 sidebar_width 에 저장.
// 끄는 동안 html 문서(iframe)가 포인터를 가져가지 않게 html 에 resizing 클래스를 단다 (app.css).

import { S } from './store.js';
import { saveConfig } from './api.js';
import { $ } from './util.js';

const MIN = 200;
const MAX = 480;
const clamp = (w) => Math.round(Math.min(MAX, Math.max(MIN, w)));
const root = document.documentElement;

export function applySidebarWidth() {
  const w = Number(S.config.sidebar_width);
  if (w) root.style.setProperty('--side-w', `${clamp(w)}px`);
  else root.style.removeProperty('--side-w');   // app.css 의 기본 폭
}

export function initResize() {
  const handle = $('#lec-resizer');
  handle.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    handle.setPointerCapture(e.pointerId);
    const left = $('#lec-sidebar').getBoundingClientRect().left;
    const widthAt = (ev) => clamp(ev.clientX - left);
    const move = (ev) => root.style.setProperty('--side-w', `${widthAt(ev)}px`);
    const up = (ev) => {
      handle.removeEventListener('pointermove', move);
      handle.removeEventListener('pointerup', up);
      root.classList.remove('resizing');
      saveConfig({ sidebar_width: widthAt(ev) });
    };
    root.classList.add('resizing');
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', up);
  });
  handle.addEventListener('dblclick', () => {
    saveConfig({ sidebar_width: null });
    applySidebarWidth();
  });
  applySidebarWidth();
}
