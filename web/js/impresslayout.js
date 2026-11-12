// html 로 전환 (D129)의 장 자리: impress.js 는 장(step)을 한 캔버스 위 좌표에 놓고 카메라가 옮겨 다닌다.
// Lectern 슬라이드에는 차례만 있으니 자리는 규칙(격자·가로 한 줄)으로 정하고, 장 주석 <!-- impress: x=… y=… --> 이 적은 축만 바꾼다.
// DOM 이 없는 계산이라 규칙 시험(tools/edges/impress_cases.js)이 돈다. 문구는 부르는 쪽이 정한다.

/** 장 주석에 적는 축 — impress 의 data-x … data-scale 과 같은 이름 */
export const AXES = ['x', 'y', 'z', 'rotate', 'rotate-x', 'rotate-y', 'scale'];
const AXIS_SET = new Set(AXES);
/** 맨 앞 설정 impress: 의 배치 방식. 영어 낱말이 안쪽 이름이다 */
const MODE_WORDS = { grid: 'grid', line: 'line', 격자: 'grid', 가로: 'line' };   // i18n-ok (문서의 문법)
export const MODES = ['grid', 'line'];
/** 격자 한 줄에 놓는 장 수 — 장 구분(lead)이 표지 하나뿐인 문서가 많아 이만큼에서 접는다 */
export const PER_ROW = 4;
const NUMBER = /^-?\d{1,6}(\.\d{1,4})?$/;

/** 맨 앞 설정의 impress 값 → {mode, bad}. 비었으면 격자, 모르는 낱말이면 격자로 두고 bad 에 그 값 */
export function readMode(value) {
  if (value === undefined || value === null || value === '') return { mode: 'grid', bad: '' };
  const word = String(value).trim();
  const mode = Object.hasOwn(MODE_WORDS, word.toLowerCase()) ? MODE_WORDS[word.toLowerCase()] : '';
  return mode ? { mode, bad: '' } : { mode: 'grid', bad: word };
}

/**
 * 장 주석의 impress 값('x=0 y=2400 rotate=90 scale=3') → {spot: {축: 수}, bad: [읽지 못한 낱말]}.
 * 낱말은 빈칸·쉼표로 나눈다. 수는 소수까지, scale 은 0 보다 크고 100 까지
 */
export function readSpot(value) {
  const spot = {};
  const bad = [];
  if (value === undefined || value === null) return { spot, bad };
  for (const word of String(value).split(/[\s,]+/).filter(Boolean)) {
    const m = /^([a-z-]+)=(.*)$/i.exec(word);
    const axis = m?.[1].toLowerCase();
    const num = m && NUMBER.test(m[2]) ? Number(m[2]) : NaN;
    if (!m || !AXIS_SET.has(axis) || Number.isNaN(num) || (axis === 'scale' && (num <= 0 || num > 100))) bad.push(word);
    else spot[axis] = num;
  }
  return { spot, bad };
}

/**
 * 장마다의 자리. slides: [{lead: 장 구분(표지·간지)인가, spot: readSpot 의 spot}] (숨긴 장은 뺀 차례),
 * mode: grid | line, w·h: 장 크기(px). 돌려주는 것: [{x, y, z, rotate, 'rotate-x', 'rotate-y', scale}] — impress 의 data-* 값.
 * 격자는 장 구분에서 줄을 바꾸고 한 줄이 perRow 장을 넘으면 접는다. 적은 축은 그 값이 이긴다 (적지 않은 축은 규칙대로)
 */
export function layoutSteps(slides, { mode = 'grid', w = 1280, h = 720, perRow = PER_ROW } = {}) {
  const dx = Math.round(w * 1.15);
  const dy = Math.round(h * 1.3);
  let row = 0;
  let col = -1;
  return slides.map((s, i) => {
    if (mode === 'line') col = i;
    else if (i > 0 && ((s.lead && col >= 0) || col + 1 >= perRow)) {
      row += 1;
      col = 0;
    } else col += 1;
    const place = { x: col * dx, y: row * dy, z: 0, rotate: 0, 'rotate-x': 0, 'rotate-y': 0, scale: 1 };
    for (const axis of AXES) if (typeof s.spot?.[axis] === 'number') place[axis] = s.spot[axis];
    return place;
  });
}

/** 전체 보기 장의 자리와 배율 — 모든 장이 한 화면에 들게 (돌린 장은 돌린 상자의 크기로). 장이 없으면 null */
export function overviewOf(places, { w = 1280, h = 720 } = {}) {
  if (!places.length) return null;
  let [left, top, right, bottom] = [Infinity, Infinity, -Infinity, -Infinity];
  for (const p of places) {
    const r = (p.rotate * Math.PI) / 180;
    const [c, s] = [Math.abs(Math.cos(r)), Math.abs(Math.sin(r))];
    const hw = ((c * w + s * h) / 2) * p.scale;
    const hh = ((s * w + c * h) / 2) * p.scale;
    left = Math.min(left, p.x - hw);
    right = Math.max(right, p.x + hw);
    top = Math.min(top, p.y - hh);
    bottom = Math.max(bottom, p.y + hh);
  }
  const scale = Math.max((right - left) / w, (bottom - top) / h) * 1.08;
  const round = (n) => Math.round(n * 100) / 100;
  return { x: round((left + right) / 2), y: round((top + bottom) / 2), scale: round(Math.max(scale, 1)) };
}
