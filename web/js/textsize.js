// 글자 크기 (툴바의 − 100% + 버튼): 문서 본문의 글자 크기와 단 폭을 함께 키우고 줄인다 (줄 길이가 그대로이게).
// 앱 UI 와 그림은 그대로다. 값은 설정 font_scale 에 저장되어 다음 실행에도 쓰인다.
// md 문서와 스타일 없는 html 은 CSS 변수 --md-scale (base.css), 스타일 있는 html 은 iframe 문서의 zoom (htmldoc.js).

import { S, emit } from './store.js';
import { saveConfig } from './api.js';
import { $ } from './util.js';

const STEPS = [0.8, 0.9, 1, 1.1, 1.2, 1.35, 1.5, 1.7, 2];

/** 지금 글자 배율 (설정이 없거나 이상하면 1) */
export function textScale() {
  const s = Number(S.config.font_scale);
  return Number.isFinite(s) && s >= STEPS[0] && s <= STEPS[STEPS.length - 1] ? s : 1;
}

function render() {
  const s = textScale();
  document.documentElement.style.setProperty('--md-scale', String(s));
  $('#lec-text-reset').textContent = `${Math.round(s * 100)}%`;
  $('#lec-text-smaller').disabled = s <= STEPS[0];
  $('#lec-text-bigger').disabled = s >= STEPS[STEPS.length - 1];
}

/** 읽던 곳이 화면에서 움직이지 않게: 칸마다(숨은 탭 포함) 바꾸기 전 화면 위쪽 블록의 위치를 기억했다가 맞춘다 (md 문서) */
function keepPlace(change) {
  const spots = S.panes.map((pane) => {
    const top = pane.scroller.getBoundingClientRect().top;
    const anchor = [...pane.view.children].find((el) => el.getBoundingClientRect().bottom > top);
    return [pane.scroller, anchor, anchor?.getBoundingClientRect().top];
  });
  change();
  for (const [scroller, anchor, before] of spots) {
    if (anchor && anchor.isConnected) scroller.scrollTop += anchor.getBoundingClientRect().top - before;
  }
}

function setScale(s) {
  keepPlace(() => {
    saveConfig({ font_scale: s });   // S.config 는 바로 바뀌고 저장은 뒤에서
    render();
  });
  emit('text-size', s);
}

/** 한 단계 크게(+1)·작게(-1). 설정 파일에 단계 사이 값(1.25 등)을 적었어도 가까운 단계로 */
function step(dir) {
  const s = textScale();
  const next = dir > 0 ? STEPS.find((x) => x > s + 1e-6) : [...STEPS].reverse().find((x) => x < s - 1e-6);
  if (next) setScale(next);
}

export function initTextSize() {
  $('#lec-text-smaller').addEventListener('click', () => step(-1));
  $('#lec-text-bigger').addEventListener('click', () => step(1));
  $('#lec-text-reset').addEventListener('click', () => { if (textScale() !== 1) setScale(1); });
  render();
}
