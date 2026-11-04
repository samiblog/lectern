// 줄 번호 (D80): md 문서 왼쪽 여백에 원문 줄 번호 — 툴바 버튼·Alt+L 로 보이고 감춘다 (설정 line_numbers).
//
// 번호는 lineunits.js 의 줄 단위 그대로다 — 현재 위치·줄 하이라이트·'@경로 a~b행'과 같은 줄이다. 단위마다 첫 화면 줄 옆에 첫 원문 줄을 적으므로
// 화면에 없는 줄(빈 줄, 머리 정보, raw HTML)의 번호는 건너뛰고, 화면에서 꺾인 글은 첫 줄에만 있다.
// 문서 DOM 은 그대로이고 칸의 스크롤 상자에 덮개(.lec-gutter)를 겹친다 — 찾기·복사·담기에 들어가지 않고, 누르기를 막지 않는다.
// 본문 왼쪽 여백은 html.line-numbers 로 넓힌다 (app.css — 화면을 그릴 때마다 칸의 class 를 다시 쓰므로 칸에 달지 않는다).
// 칸마다 그린다 — 모두 펼치기(D73)는 칸이 여럿 보인다. 코드 화면은 늘 번호가 있고, html 문서·슬라이드는 원문 줄이 없어 쓰지 않는다.

import { S, on } from './store.js';
import { saveConfig } from './api.js';
import { collectUnits, baseOf, markOf } from './lineunits.js';
import { keepPlace } from './textsize.js';
import { $ } from './util.js';
import { t } from './i18n.js';

const GAP = 28;   // 번호의 오른쪽 끝과 본문 글 사이 — 그 사이에 현재 위치 삼각형·하이라이트 막대·접기 화살표
const wanted = () => S.config.line_numbers === true;
/** 줄 번호를 쓰는 화면: md 문서 (슬라이드·없는 문서 뺌) */
const usable = (view) => !!view?.dataset.docPath && view.classList.contains('md-body') && !view.classList.contains('lec-deck') && !view.querySelector('.doc-missing');

let watcher = null;
const queued = new Set();

/** 칸의 번호를 다시 그린다 (쓰지 않는 화면이면 지운다) */
function draw(pane) {
  const { view, scroller, source } = pane;
  let box = scroller.querySelector(':scope > .lec-gutter');
  if (!wanted() || !usable(view) || source?.path !== view.dataset.docPath) {
    box?.remove();
    return;
  }
  if (!box) {
    box = document.createElement('div');
    box.className = 'lec-gutter';
    box.setAttribute('aria-hidden', 'true');
    scroller.append(box);
  }
  const textLeft = view.getBoundingClientRect().left - scroller.getBoundingClientRect().left + parseFloat(getComputedStyle(view).paddingLeft || '0');
  box.style.width = `${Math.max(0, Math.round(textLeft - GAP))}px`;
  const base = baseOf(view);
  box.replaceChildren(...collectUnits(view, source.lines).map((u) => {
    const num = document.createElement('span');
    num.textContent = u.a;
    num.style.top = `${Math.round(markOf(u, base))}px`;
    return num;
  }));
  watcher.observe(view);   // 그림을 불러옴·접기·칸 폭·글자 크기로 높이가 바뀌면 다시 잰다
}

/** 다음 그림에 다시 그린다 — 크기가 여러 번 바뀌어도 칸마다 한 번 */
function later(pane) {
  if (!queued.size) {
    requestAnimationFrame(() => {
      const panes = [...queued];
      queued.clear();
      for (const p of panes) if (S.panes.includes(p)) draw(p);
    });
  }
  queued.add(pane);
}

function updateButton() {
  const btn = $('#lec-btn-lines');
  const able = usable($('#lec-view'));
  btn.disabled = !able;
  btn.classList.toggle('on', able && wanted());
  btn.setAttribute('aria-pressed', String(able && wanted()));
  btn.title = able ? t('줄 번호 보이기/감추기 (Alt+L)') : t('줄 번호는 Markdown 문서에서 씁니다 — 코드 화면에는 늘 있습니다');
}

function apply() {
  document.documentElement.classList.toggle('line-numbers', wanted());
  for (const pane of S.panes) draw(pane);
  updateButton();
}

/** 버튼·Alt+L: 보이고 감춘다. md 문서가 아니면 false */
export function toggleLineNumbers() {
  if (!usable($('#lec-view'))) return false;
  keepPlace(() => {
    saveConfig({ line_numbers: !wanted() });   // S.config 는 바로 바뀌고 저장은 뒤에서
    apply();
  });
  return true;
}

export function initLineNumbers() {
  watcher = new ResizeObserver((entries) => {
    if (!wanted()) return;
    for (const e of entries) {
      const pane = S.panes.find((p) => p.view === e.target);
      if (pane) later(pane);
    }
  });
  $('#lec-btn-lines').addEventListener('click', toggleLineNumbers);
  on('rendered', (pane) => {
    draw(pane);
    if (pane === S.pane) updateButton();
  });
  on('pane', updateButton);
  on('view', updateButton);
  document.documentElement.classList.toggle('line-numbers', wanted());
  updateButton();
}
