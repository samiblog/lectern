// tablefitplan.js 의 계산 점검 — 표 열 너비 (D173). rules_check.mjs 가 돌린다 — m: tablefitplan.js, 끝에서 {n, fails} 를 돌려준다.
// 임의의 표 수백 개로 성질을 본다: 폭의 합이 쓸 폭을 넘지 않는다(옆 스크롤로 정한 때 말고), 좁혀 넣는 바닥 아래로 줄이지 않는다, 숫자 열은 좁히지 않는다,
// 한 줄 폭보다 넓히지 않는다, 칸의 글 자리가 남는다(마지막 머리 칸의 [복사] 단추 여백 56px 를 잊으면 '항/목1/0'), 첫 폭(가장 긴 낱말)을 지킨다.
// 2026-11-18 에 찾은 두 버그(평균 비례의 합이 쓸 폭을 넘음 — 1000px 에서 넘친 표 2 → 10, 머리 칸 여백을 잊어 글 자리가 없음)를 잡는 점검이다.
const { PLANS, plan, planAvg, planPair, scrollPlan, floorsOf, lastFloors, choose, sum, SCROLL_EM } = m;
let n = 0;
const fails = [];
const eq = (got, want, name) => {
  n += 1;
  if (JSON.stringify(got) !== JSON.stringify(want)) fails.push(`${name}: ${JSON.stringify(got)} ≠ ${JSON.stringify(want)}`);
};
const ok = (cond, name, detail) => {
  n += 1;
  if (!cond) fails.push(`${name}${detail === undefined ? '' : ` — ${JSON.stringify(detail).slice(0, 400)}`}`);
};

// 씨앗이 있는 난수 (같은 표가 다시 나오게)
let seed = 20261119;
const rnd = () => {
  seed = (seed * 1103515245 + 12345) % 2147483648;
  return seed / 2147483648;
};
const pickInt = (a, b) => a + Math.floor(rnd() * (b - a + 1));

const EM = 15;
/** 글자 수로 쓴 표 → tablefit.js 가 재어 넘기는 m (글자 하나 = 1em, 낱말은 빈칸으로 나눔) */
function measured(rows, { room, nums = [], copyPad = true }) {
  const cols = rows[0].length;
  const pad = Array.from({ length: cols }, (_, i) => 27 + (copyPad && i === cols - 1 ? 56 : 0));   // 칸의 좌우 여백, 마지막 머리 칸은 [복사] 자리
  const widthOf = (t) => [...t].length * EM;
  const textW = rows.map((r) => r.map(widthOf));
  const nowrap = Array.from({ length: cols }, (_, i) => nums.includes(i));
  const maxCol = pad.map((p, i) => Math.max(...textW.map((r) => r[i])) + p + 1);
  const minCol = pad.map((p, i) => (nowrap[i] ? maxCol[i] : Math.max(...rows.map((r) => Math.max(...r[i].split(' ').map(widthOf)))) + p));
  const pairCol = pad.map((p, i) => Math.max(...rows.map((r) => {
    const w = r[i].split(' ');
    let best = 0;
    for (let k = 1; k < w.length; k++) best = Math.max(best, widthOf(`${w[k - 1]} ${w[k]}`));
    return best;
  })) + p + 1);
  return { pad, textW, maxCol, minCol, pairCol, nowrap, room, em: EM };
}

const word = () => '가'.repeat(pickInt(1, 6));
const cellText = (kind) => {
  if (kind === 'num') return String(pickInt(1, 9999999)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  if (kind === 'short') return word();
  return Array.from({ length: pickInt(kind === 'long' ? 8 : 1, kind === 'long' ? 60 : 6) }, word).join(' ');
};

function randomTable() {
  const cols = pickInt(2, 14);
  const kinds = Array.from({ length: cols }, () => ['short', 'mid', 'mid', 'long', 'num'][pickInt(0, 4)]);
  const rows = Array.from({ length: pickInt(2, 16) }, (_, r) => kinds.map((k) => (r === 0 ? `항목 ${pickInt(1, 99)}` : cellText(k))));
  const nums = kinds.map((k, i) => (k === 'num' ? i : -1)).filter((i) => i >= 0);
  return measured(rows, { room: pickInt(300, 1300), nums, copyPad: rnd() < 0.7 });
}

// ---- 성질: 임의의 표 400개 × 후보 다섯 ----------------------------------------------------------
const TABLES = 400;
const seen = { fit: 0, squeezed: 0, forced: 0 };
for (let t = 0; t < TABLES; t++) {
  const mm = randomTable();
  if (sum(mm.maxCol) <= mm.room) continue;   // 한 줄로 다 들어가는 표는 tablefit 이 맞추지 않는다
  const floors = floorsOf(mm);
  const last = lastFloors(mm);
  const forced = sum(last) > mm.room;   // 열마다 좁혀 넣는 바닥도 못 준다 — 옆으로 스크롤로 정한 때
  seen[forced ? 'forced' : sum(floors) > mm.room ? 'squeezed' : 'fit'] += 1;
  PLANS.forEach((planner, k) => {
    const w = planner(mm);
    if (w === null) return;   // 두 낱말 후보: 들어가지 않거나 바뀌는 것이 없다
    const name = `표 ${t} 후보 ${k}`;
    ok(w.length === mm.maxCol.length && w.every((x) => Number.isFinite(x) && x > 0), `${name}: 열마다 양의 폭`, w);
    if (!forced) ok(sum(w) <= mm.room + 1, `${name}: 폭의 합이 쓸 폭을 넘지 않는다`, { sum: sum(w), room: mm.room });
    ok(w.every((x, i) => x >= last[i] - 0.5), `${name}: 좁혀 넣는 바닥 아래로 줄이지 않는다`, { w, last });
    ok(w.every((x, i) => !mm.nowrap[i] || x >= mm.minCol[i] - 0.5), `${name}: 숫자 열은 좁히지 않는다 (옆 칸에 겹치지 않게)`, { w, minCol: mm.minCol, nowrap: mm.nowrap });
    ok(w.every((x, i) => x <= mm.maxCol[i] + 0.5), `${name}: 한 줄 폭보다 넓히지 않는다`, { w, maxCol: mm.maxCol });
    ok(w.every((x, i) => x - mm.pad[i] >= Math.min(mm.maxCol[i] - mm.pad[i] - 1, 2 * EM) - 0.5), `${name}: 칸의 글 자리가 남는다 (여백을 빼고 2em 또는 글 폭)`, { w, pad: mm.pad });
    if (!forced && sum(floors) <= mm.room && k !== 4) ok(w.every((x, i) => x >= floors[i] - 0.5), `${name}: 바닥들이 들어가면 첫 폭(가장 긴 낱말)을 지킨다`, { w, floors });
  });
  const s = scrollPlan(mm);
  const want = mm.maxCol.map((w, i) => Math.min(w, mm.pad[i] + SCROLL_EM * EM));
  if (s === null) ok(sum(mm.maxCol.map((w, i) => Math.min(w, Math.max(mm.minCol[i], mm.pad[i] + SCROLL_EM * EM)))) <= mm.room + 0.5, `표 ${t}: 옆 스크롤 폭이 없으면 쓸 폭에 들어간다`);
  else ok(sum(s) > mm.room && s.every((x, i) => x >= Math.min(want[i], mm.maxCol[i]) - 0.5), `표 ${t}: 옆 스크롤 폭은 쓸 폭보다 넓고 열마다 글 폭 4.5em`, s);
}
ok(seen.fit > 50 && seen.squeezed > 20 && seen.forced > 5, '임의의 표가 세 경우(들어감·좁혀 넣음·옆 스크롤)를 고루 지난다', seen);

// ---- 2026-11-18 의 두 버그를 그대로 ---------------------------------------------------------------
{
  // 평균 비례: 한 열은 한 줄 폭에, 다른 열은 바닥에 한 번에 걸리는 표 — 예전 나누기는 합이 쓸 폭을 넘었다
  const mm = measured([['가', '나', '다'], ['가'.repeat(40), '가', '가 가 가 가 가 가 가 가 가 가 가 가 가 가 가 가 가 가 가 가'], ['가'.repeat(38), '가', '가']], { room: 520, copyPad: false });
  for (const power of [1, 0.5]) {
    const w = planAvg(mm, power);
    ok(sum(w) <= mm.room + 1, `평균 비례(${power}) — 합이 쓸 폭을 넘지 않는다 (1000px 에서 넘친 표 2 → 10)`, { sum: sum(w), room: mm.room });
  }
  // 마지막 머리 칸의 [복사] 여백 — 열 열 개를 좁혀 넣어도 마지막 열의 글 자리가 남는다
  const ten = measured([Array.from({ length: 10 }, (_, i) => `항목${i + 1}`), ...Array.from({ length: 3 }, () => Array(10).fill('가나 다라'))], { room: 656 });
  const w = plan(ten, 1);
  ok(w[9] - ten.pad[9] >= 2 * EM - 0.5, "마지막 머리 칸의 [복사] 여백 56px 를 빼고도 글 자리 2em ('항/목1/0' 이 되지 않게)", { last: w[9], pad: ten.pad[9] });
}

// ---- 두 낱말 후보 -----------------------------------------------------------------------------------
{
  const mm = measured([['요약', '설명'], ['수요 전망의 바탕이 되는 각국 전력망 투자 계획', '가 '.repeat(120).trim()]], { room: 640, copyPad: false });
  const w = planPair(mm);
  ok(w === null || w[0] >= mm.pairCol[0] - 0.5, '두 낱말 후보 — 짧은 열에 이웃한 두 낱말이 한 줄에 든다', { w, pair: mm.pairCol });
  const one = measured([['가', '나'], ['가가가가가가가가', '가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가가']], { room: 400, copyPad: false });
  eq(planPair(one), null, '두 낱말 후보 — 낱말이 하나뿐인 칸이면 바뀌는 것이 없다');
}

// ---- 고르기 (choose) — 실제로 그려 잰 나쁨 --------------------------------------------------------
{
  const c = (bad, h, narrow = 0, tag = '') => ({ score: { bad, h, narrow, line: 20, cells: 30 }, tag });
  eq(choose([c(5, 1000, 0, '지금'), c(3, 1050, 0, '고른 열')]).tag, '고른 열', '나쁨이 적으면 조금 높아도 (10% 안)');
  eq(choose([c(5, 1000, 0, '지금'), c(0, 1300, 0, '두 낱말')]).tag, '지금', '10% 넘게 높아지는 후보는 나쁨이 적어도 쓰지 않는다');
  eq(choose([c(2, 1000, 0, '지금'), c(2, 995, 0, '거의 같음')]).tag, '지금', '나쁨이 같고 반 줄도 안 낮으면 지금 모양 그대로');
  eq(choose([c(2, 1000, 0, '지금'), c(2, 980, 0, '반 줄 넘게 낮음')]).tag, '반 줄 넘게 낮음', '나쁨이 같으면 반 줄 넘게 낮은 것');
  eq(choose([c(9, 600, 5, '좁혀 넣음'), c(4, 1000, 0, '지금'), c(2, 1080, 0, '고른 열')]).tag, '고른 열',
    '가장 낮은 높이는 세로로 감긴 칸이 없는 후보에서 — 좁혀 넣어 낮아진 것이 기준이 되지 않게');
}

return { n, fails };
