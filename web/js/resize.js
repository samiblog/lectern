// 사이드바·목차 폭 조절: 경계를 끌어 폭을 바꾸고, 두 번 누르면 기본 폭. 값은 설정 sidebar_width·toc_width 에 저장 (D47).
// 끄는 동안 html 문서(iframe)가 포인터를 가져가지 않게 html 에 resizing 클래스를 단다 (app.css). 오른쪽 터미널의 폭은 terminal.js.

import { S } from './store.js';
import { saveConfig } from './api.js';
import { $ } from './util.js';

const DOC_MIN = 360;   // 목차를 넓혀도 문서 칸은 이만큼 남긴다
const root = document.documentElement;

// 사이드바는 왼쪽 끝에서, 목차는 오른쪽 끝에서 경계까지가 폭이다
const PANELS = {
  side: {
    handle: '#lec-resizer', key: 'sidebar_width', cssVar: '--side-w', min: 200, max: 480,
    widthAt: (ev) => ev.clientX - $('#lec-sidebar').getBoundingClientRect().left,
    room: () => Infinity,
  },
  toc: {
    handle: '#lec-toc-resizer', key: 'toc_width', cssVar: '--toc-w', min: 160, max: 560,
    widthAt: (ev) => $('#lec-toc').getBoundingClientRect().right - ev.clientX,
    room: () => $('#lec-panes').getBoundingClientRect().width + $('#lec-toc').getBoundingClientRect().width - DOC_MIN,
  },
};

const clamp = (p, w, max = p.max) => Math.round(Math.min(max, Math.max(p.min, w)));

function applyWidth(p) {
  const w = Number(S.config[p.key]);
  if (w) root.style.setProperty(p.cssVar, `${clamp(p, w)}px`);
  else root.style.removeProperty(p.cssVar);   // app.css 의 기본 폭
}

function bind(name, p) {
  const handle = $(p.handle);
  handle.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    handle.setPointerCapture(e.pointerId);
    const max = Math.max(p.min, Math.min(p.max, p.room()));
    const widthAt = (ev) => clamp(p, p.widthAt(ev), max);
    const move = (ev) => root.style.setProperty(p.cssVar, `${widthAt(ev)}px`);
    const up = (ev) => {
      handle.removeEventListener('pointermove', move);
      handle.removeEventListener('pointerup', up);
      root.classList.remove('resizing', `resizing-${name}`);
      saveConfig({ [p.key]: widthAt(ev) });
    };
    root.classList.add('resizing', `resizing-${name}`);
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', up);
  });
  handle.addEventListener('dblclick', () => {
    saveConfig({ [p.key]: null });
    applyWidth(p);
  });
  applyWidth(p);
}

export function initResize() {
  for (const [name, p] of Object.entries(PANELS)) bind(name, p);
}
