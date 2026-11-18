// 표 열 너비의 계산 (D173 — DOM 없음). tablefit.js 가 잰 값(m: 열마다 한 줄 폭·가장 긴 낱말 폭·이웃한 두 낱말 폭·여백·숫자 열, 쓸 폭, em)으로
// 열 폭 후보를 짓고(plan·planAvg·planPair·scrollPlan), 실제로 그려 잰 나쁨(score)으로 고른다(choose). 규칙 시험(tools/edges/tablefit_cases.js)이 node 에서 부른다.

// 열 폭의 바닥은 칸의 글 폭(안쪽 여백을 뺀 폭)으로 센다 — 마지막 머리 칸에는 [복사] 단추 자리로 여백이 56px 더 있다
export const FLOOR_EM = 2.5;                       // 첫 폭의 바닥 (글 폭 em — 한글 두세 자)
export const LAST_EM = 2;                          // 좁혀 넣는 바닥 (글 폭 em) — 열마다 이만큼도 줄 수 없으면 옆으로 스크롤
export const SCROLL_EM = 4.5;                      // 옆으로 스크롤할 때 열의 바닥 (글 폭 em)
export const TALLER = 1.1;                         // 가장 낮은 후보보다 이만큼 넘게 높은 후보는 쓰지 않는다
export const NARROW_MANY = 3;                      // 좁혀 넣은 표에 좁은 열에서 세로로 감긴 칸이 이만큼 있으면 옆 스크롤을 대어 본다 (마지막 수단)

export const sum = (xs) => xs.reduce((a, b) => a + b, 0);

/**
 * 열의 첫 폭: 가장 긴 낱말 폭 (바닥은 글 폭 2.5em — 글이 그보다 짧으면 그 폭, 위는 max(12em, 쓸 폭의 40%) — 긴 주소 하나가 표를 차지하지 않게).
 * 숫자 열은 줄바꿈하지 않으므로 위 한계 없이 숫자 폭 그대로 — 좁은 창에서 긴 숫자의 마지막 열([복사] 여백 포함)이 숫자보다 좁아져 옆 칸에 겹쳤다
 * (2026-11-19 규칙 시험 tablefit_cases 가 찾음)
 */
export function floorsOf({ minCol, maxCol, pad, room, em, nowrap }) {
  const cap = Math.max(12 * em, room * 0.4);
  return minCol.map((w, i) => (nowrap?.[i] ? Math.min(w, maxCol[i])
    : Math.min(Math.max(w, Math.min(maxCol[i], pad[i] + FLOOR_EM * em)), Math.max(cap, pad[i] + FLOOR_EM * em), maxCol[i])));
}

/** 좁혀 넣는 바닥: 글 폭 2em (글이 그보다 짧으면 그 폭, 줄바꿈하지 않는 숫자 열은 그 폭 그대로 — 숫자를 끊거나 옆 칸에 겹치지 않게). 이것도 못 주면 옆으로 스크롤 */
export const lastFloors = ({ maxCol, minCol, nowrap, pad, em }) => maxCol.map((w, i) => (nowrap[i] ? minCol[i] : Math.min(w, pad[i] + LAST_EM * em)));

/**
 * 열의 평균 글 양에 비례해 나눈다 (사용자 제안 — '셀에 든 글자 수 대비 열 너비 비율', '열 평균'): 열마다 몸통 칸 글 폭의 평균에 비례하게,
 * 바닥(가장 긴 낱말·글 폭 2.5em)과 한 줄 폭 사이에서 (합이 쓸 폭이 되는 배율을 이분법으로). power 0.5 는 제곱근 — 글이 아주 긴 열이 다 가져가지 않게. 한 행의 칸들이 비슷한 줄 수로
 * 감긴다 — 칸이 높아져도 이웃 칸과 비슷하면 이상해 보이지 않는다. 바닥들로도 넘치면 plan 과 같이 줄인다
 */
export function planAvg(m, power = 1) {
  const { pad, textW, maxCol, room: A } = m;
  const floors = floorsOf(m);
  if (sum(floors) >= A) return plan(m, 1);
  const body = textW.length > 1 ? textW.slice(1) : textW;   // 머리행은 짧은 이름표라 뺀다
  const avg = maxCol.map((_, i) => (body.reduce((t, row) => t + row[i], 0) / body.length + pad[i]) ** power);
  // 열 폭 = 평균 × k 를 바닥과 한 줄 폭 사이로 — 합이 쓸 폭이 되는 k 를 이분법으로 (합은 k 에 따라 늘기만 한다.
  // 넘치는 열과 모자라는 열을 차례로 고정하며 나누면 한 번에 둘 다 생길 때 합이 쓸 폭을 넘었다 — 1000px 에서 넘친 표 2 → 10)
  const at = (k) => avg.map((a, i) => Math.min(maxCol[i], Math.max(floors[i], a * k)));
  let lo = 0;
  let hi = 1;
  while (sum(at(hi)) < A && hi < 1e6) hi *= 2;
  for (let step = 0; step < 40; step += 1) {
    const mid = (lo + hi) / 2;
    if (sum(at(mid)) <= A) lo = mid;
    else hi = mid;
  }
  return at(lo);
}

/**
 * 열마다 이웃한 두 낱말이 한 줄에 들어가는 폭을 첫 폭으로 (글이 긴 열이 남는 폭을 다 가져가 다른 열이 낱말 하나씩 감기지 않게 —
 * 표는 높아질 수 있다. 사용자: '셀 높이가 커져도 다른 열과 비슷하면 이상해 보이지 않는다'). 들어가지 않거나 바뀌는 것이 없으면 null
 */
export function planPair(m) {
  const floors = floorsOf(m);
  const two = floors.map((f, i) => (m.nowrap[i] ? f : Math.min(m.maxCol[i], Math.max(f, m.pairCol[i]))));
  if (sum(two) > m.room || two.every((w, i) => w <= floors[i] + 0.5)) return null;
  return plan(m, 1, two);
}

/** 대어 볼 열 폭들 — 표가 가장 낮아지게 차례로(줄 수 어림의 넉넉함 1·1.15 — 낱말 단위로 감기면 글자 폭 어림보다 줄이 는다), 열 평균 비례(그대로·제곱근 — 글이 아주 긴 열이 다 가져가지 않게), 두 낱말 폭부터 */
export const PLANS = [(m) => plan(m, 1), (m) => plan(m, 1.15), (m) => planAvg(m, 1), (m) => planAvg(m, 0.5), planPair];

/** 옆으로 스크롤하는 폭 — 열마다 가장 긴 낱말·글 폭 4.5em (한 줄 폭과 위 cap 까지). 쓸 폭에 들어가면 null (스크롤할 까닭이 없다) */
export function scrollPlan(m) {
  const cap = Math.max(12 * m.em, m.room * 0.4);
  const widths = m.maxCol.map((w, i) => Math.min(w, Math.max(m.minCol[i], m.pad[i] + SCROLL_EM * m.em), Math.max(cap, m.pad[i] + SCROLL_EM * m.em)));
  return sum(widths) > m.room ? widths : null;
}

/** 잰 값으로 열 폭을 정한다 (slack: 줄 수 어림의 넉넉함, start: 열의 첫 폭). 열 폭 배열 */
export function plan(m, slack, start = floorsOf(m)) {
  const { pad, textW, maxCol, room: A } = m;
  const n = maxCol.length;
  const linesAt = (i, w) => textW.map((row) => Math.max(1, Math.ceil(row[i] * slack / Math.max(1, w - pad[i]) - 0.02)));
  let widths = start.slice();
  const last = lastFloors(m);
  if (sum(last) > A) return last;   // 열마다 글 폭 2em 도 줄 수 없다 — 그 폭으로 두고 옆으로 스크롤 (마지막 수단)
  let left = A - sum(widths);
  if (left < 0) {   // 가장 긴 낱말들로는 넘친다 — 글 폭 2em(글이 짧으면 그 폭, 숫자 열은 그대로)까지 고르게 줄인다 (긴 낱말은 끊긴다)
    const extra = widths.map((w, i) => w - last[i]);
    const total = extra.reduce((a, b) => a + b, 0);
    widths = widths.map((w, i) => w - (total > 0 ? extra[i] * Math.min(1, -left / total) : 0));
    left = A - widths.reduce((a, b) => a + b, 0);
  }
  const lines = widths.map((w, i) => linesAt(i, w));
  const heightOf = () => textW.reduce((h, _, r) => h + Math.max(...lines.map((l) => l[r])), 0);
  let H = heightOf();
  // 남는 폭을 표가 가장 많이 낮아지는 열에 — 후보는 행마다 한 줄 덜·반·한 줄이 되는 폭 (가까운 것부터 24개)
  for (let guard = 0; left > 0.5 && guard < 300; guard += 1) {
    let best = null;
    for (let i = 0; i < n; i++) {
      if (widths[i] >= maxCol[i] - 0.5) continue;
      const cand = new Set();
      for (const row of textW) {
        const l = Math.max(1, Math.ceil(row[i] * slack / Math.max(1, widths[i] - pad[i]) - 0.02));
        if (l > 1) for (const k of [l - 1, Math.ceil(l / 2), 1]) cand.add(Math.min(maxCol[i], row[i] * slack / k + pad[i] + 0.5));
      }
      const others = textW.map((_, r) => lines.reduce((mx, l, j) => (j === i ? mx : Math.max(mx, l[r])), 1));   // 이 열 말고 행마다 가장 많은 줄
      for (const w of [...cand].filter((x) => x > widths[i] + 0.5 && x - widths[i] <= left).sort((a, b) => a - b).slice(0, 24)) {
        const next = linesAt(i, w);
        const gain = H - next.reduce((h, l, r) => h + Math.max(l, others[r]), 0);
        if (gain > 0 && (!best || gain / (w - widths[i]) > best.rate)) best = { i, w, rate: gain / (w - widths[i]) };
      }
    }
    if (!best) break;
    left -= best.w - widths[best.i];
    widths[best.i] = best.w;
    lines[best.i] = linesAt(best.i, best.w);
    H = heightOf();
  }
  // 한 열만 넓혀서는 낮아지지 않는 남은 폭(같은 행에서 여러 열이 감김) — 아직 감긴 열에 넘치는 글 양만큼
  const want = widths.map((w, i) => Math.max(0, maxCol[i] - w));
  const wantSum = want.reduce((a, b) => a + b, 0);
  if (left > 1 && wantSum > 0) widths = widths.map((w, i) => w + want[i] * Math.min(1, left / wantSum));
  return widths;
}


export const better = (a, b) => a.bad < b.bad || (a.bad === b.bad && a.h < b.h - a.line / 2);

/**
 * 후보 가운데 고른다 — 가장 낮은 후보보다 10%(와 한 줄) 넘게 높은 것은 빼고, 나쁨이 적은 것, 같으면 반 줄 넘게 낮은 것 (앞의 것이 먼저 — 첫째는 지금 모양).
 * 열을 고르게 하려고 표가 조금 높아지는 것은 받지만(사용자: '셀 높이가 커져도 다른 열과 비슷하면 이상해 보이지 않는다'), 글이 아주 긴 열이
 * 좁아져 표가 훨씬 높아지는 것은 받지 않는다 (사용자의 처음 불만이 '셀 높이가 아주 길어진다')
 */
export function choose(cands) {
  const sane = cands.filter((c) => !c.score.narrow);   // 가장 낮은 높이는 세로로 감긴 칸이 없는 것에서 — 좁혀 넣어 낮아진 것이 기준이 되지 않게
  const low = Math.min(...(sane.length ? sane : cands).map((c) => c.score.h));
  let best = null;
  for (const c of cands) {
    if (c.score.h > low * TALLER + c.score.line) continue;
    if (!best || better(c.score, best.score)) best = c;
  }
  return best;
}
