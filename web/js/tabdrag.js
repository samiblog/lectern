// 탭 끌어 옮기기 (D163): 프로젝트 탭 막대(tabs.js)와 문서 탭 줄(doctabs.js)에서 탭을 끌어 같은 줄 안의 다른 자리로 옮긴다.
//
// - 마우스로만 — 키보드 단축키는 두지 않는다 (사용자 결정, 2026-11-18). 다른 줄·다른 창으로 끌어내기는 하지 않는다 (D64).
// - 조금(6px) 움직여야 끌기가 된다 — 그 전에 놓으면 보통 누르기 (고르기·닫기 × ·가운데 버튼은 그대로). 끈 뒤의 click 은 버린다.
// - 끄는 동안 놓일 자리에 세로 막대 (`.lec-tab-drop` — 줄이 가로로 스크롤해도 잘리지 않게 화면에 고정), 끄는 탭은 흐리게.
//   줄 끝 가까이로 끌면 줄을 스크롤한다 (탭이 많아 넘칠 때). Esc·창 밖으로 나감은 그만두기.

const START = 6;   // 끌기로 보는 움직임 (px)
const EDGE = 28;   // 줄 끝에서 이만큼 안이면 스크롤

/**
 * @param {HTMLElement} list 탭들이 든 줄
 * @param {string} sel 탭 하나의 선택자 ('.lec-tab'·'.doc-tab')
 * @param {(from: number, to: number) => void} moved 탭 차례의 from 번째를 to 번째로 (to 는 그 탭을 뺀 차례에서의 자리)
 */
export function dragTabs(list, sel, moved) {
  /** @type {{el: HTMLElement, from: number, id: number, x: number, y: number, on: boolean, to: number, raf: number, mark: HTMLElement | null} | null} */
  let drag = null;
  let swallow = false;

  const tabs = () => /** @type {HTMLElement[]} */ ([...list.querySelectorAll(sel)]);

  /** 놓일 자리 — 놓으면 그 탭이 갈 차례 (to)와 막대를 그을 x */
  function slot(x) {
    const all = tabs();
    let s = all.findIndex((el) => { const r = el.getBoundingClientRect(); return x < r.left + r.width / 2; });
    if (s < 0) s = all.length;
    const edge = s < all.length ? all[s].getBoundingClientRect().left : all[all.length - 1].getBoundingClientRect().right;
    return { to: s > drag.from ? s - 1 : s, edge };
  }

  function paint() {
    const { to, edge } = slot(drag.x);
    drag.to = to;
    const box = list.getBoundingClientRect();
    drag.mark ??= document.body.appendChild(Object.assign(document.createElement('div'), { className: 'lec-tab-drop' }));
    drag.mark.hidden = to === drag.from || edge < box.left - 1 || edge > box.right + 1;
    Object.assign(drag.mark.style, { left: `${Math.round(edge - 1)}px`, top: `${Math.round(box.top + 3)}px`, height: `${Math.round(box.height - 6)}px` });
  }

  function scroll() {
    if (!drag?.on) return;
    const box = list.getBoundingClientRect();
    const step = drag.x < box.left + EDGE ? -10 : drag.x > box.right - EDGE ? 10 : 0;
    if (step && list.scrollWidth > list.clientWidth) {
      list.scrollLeft += step;
      paint();
    }
    drag.raf = requestAnimationFrame(scroll);
  }

  function end(apply) {
    if (!drag) return;
    const d = drag;
    drag = null;
    removeEventListener('pointermove', onMove, true);
    removeEventListener('pointerup', onUp, true);
    removeEventListener('pointercancel', onCancel, true);
    removeEventListener('keydown', onKey, true);
    removeEventListener('blur', onCancel);
    if (!d.on) return;
    cancelAnimationFrame(d.raf);
    d.mark?.remove();
    d.el.classList.remove('dragging');
    document.documentElement.classList.remove('lec-tab-dragging');
    swallow = true;   // 이어 오는 click 은 고르기로 쓰지 않는다 (고른 프로젝트 탭을 또 누르면 폴더 개요가 열린다)
    setTimeout(() => { swallow = false; });
    if (apply && d.to >= 0 && d.to !== d.from) moved(d.from, d.to);
  }

  function onMove(e) {
    if (e.pointerId !== drag.id) return;
    if (!drag.on) {
      if (Math.abs(e.clientX - drag.x) < START && Math.abs(e.clientY - drag.y) < START) return;
      drag.on = true;
      drag.el.classList.add('dragging');
      document.documentElement.classList.add('lec-tab-dragging');
      drag.raf = requestAnimationFrame(scroll);
    }
    drag.x = e.clientX;
    paint();
  }

  const onUp = (e) => { if (e.pointerId === drag?.id) end(true); };
  const onCancel = () => end(false);
  function onKey(e) {
    if (e.key !== 'Escape' || !drag?.on) return;
    e.preventDefault();
    e.stopPropagation();   // 다른 창·메뉴를 닫지 않게 — 끌기만 그만둔다
    end(false);
  }

  list.addEventListener('pointerdown', (e) => {
    if (e.button !== 0 || drag || e.target.closest?.('.tab-close')) return;
    const el = e.target.closest?.(sel);
    const from = el ? tabs().indexOf(el) : -1;
    if (from < 0 || tabs().length < 2) return;
    drag = { el, from, id: e.pointerId, x: e.clientX, y: e.clientY, on: false, to: -1, raf: 0, mark: null };
    addEventListener('pointermove', onMove, true);
    addEventListener('pointerup', onUp, true);
    addEventListener('pointercancel', onCancel, true);
    addEventListener('keydown', onKey, true);
    addEventListener('blur', onCancel);
  });
  list.addEventListener('click', (e) => {
    if (!swallow) return;
    e.preventDefault();
    e.stopImmediatePropagation();
  }, true);
}
