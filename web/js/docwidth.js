// 문서 폭 (툴바의 ↔ 버튼, D68): md 문서 본문의 단 폭을 넓히고 줄인다. 스타일이 정한 폭(--md-width × 글자 크기)이 100% 이고,
// '가득'은 칸 폭 전체. 글자 크기는 그대로다 (줄이 길어지거나 짧아진다). 값은 설정 doc_width 에 저장되어 다음 실행에도 쓰인다.
// md 문서와 스타일 없는 html 은 CSS 변수 --md-wide (base.css — htmldoc.js 가 iframe 에도). 코드 화면·발표 문서·스타일 있는 html 은 그대로.

import { S, emit } from './store.js';
import { saveConfig } from './api.js';
import { keepPlace } from './textsize.js';
import { $ } from './util.js';
import { t } from './i18n.js';

const FULL = 10;   // '가득' — 칸보다 넓은 값이라 칸 폭 전체가 된다
const STEPS = [0.8, 0.9, 1, 1.15, 1.3, 1.5, 1.75, 2, FULL];

/** 지금 폭 배율 (설정이 없거나 이상하면 1) */
export function docWidth() {
  const w = Number(S.config.doc_width);
  return Number.isFinite(w) && w >= STEPS[0] && w <= FULL ? w : 1;
}

function render() {
  const w = docWidth();
  document.documentElement.style.setProperty('--md-wide', String(w));
  $('#lec-width-reset').textContent = w >= FULL ? t('폭 가득') : t('폭 {n}%', { n: Math.round(w * 100) });
  $('#lec-width-narrower').disabled = w <= STEPS[0];
  $('#lec-width-wider').disabled = w >= FULL;
}

function setWidth(w) {
  keepPlace(() => {
    saveConfig({ doc_width: w });   // S.config 는 바로 바뀌고 저장은 뒤에서
    render();
  });
  emit('doc-width', w);
}

/** 한 단계 넓게(+1)·좁게(-1). 설정 파일에 단계 사이 값을 적었어도 가까운 단계로 */
function step(dir) {
  const w = docWidth();
  const next = dir > 0 ? STEPS.find((x) => x > w + 1e-6) : [...STEPS].reverse().find((x) => x < w - 1e-6);
  if (next) setWidth(next);
}

export function initDocWidth() {
  $('#lec-width-narrower').addEventListener('click', () => step(-1));
  $('#lec-width-wider').addEventListener('click', () => step(1));
  $('#lec-width-reset').addEventListener('click', () => { if (docWidth() !== 1) setWidth(1); });
  render();
}
