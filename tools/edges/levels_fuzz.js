// 레벨 바꾸기의 임의 시험 (D152) — rules_check.mjs 가 돌린다 (d: docops.js, lo: lineops.js)
// 임의로 만든 문서(제목, 글머리·번호·할 일이 섞인 세 단계 목록, 빈 줄로 띄운 항목, 이어진 줄, 문단)에서 임의의 줄을 골라 레벨을 바꾼 뒤
// 어떤 경우에도 지켜져야 할 것을 본다:
//   줄 수가 그대로다 · 줄의 글(표시를 뗀)이 그대로다 · 어느 줄도 한 번에 두 단계 이상 움직이지 않는다 (제목 수준, 목록의 깊이)
//   · 고른 줄(이어진 줄이면 그 항목) 위의 줄은 깊이가 바뀌지 않는다 · 안으로 넣고 바로 밖으로 빼면 깊이가 처음과 같다
const { shiftLevels, bareText, headLevel } = d;
const { itemOf, itemSpan } = lo;
const problems = [];
let runs = 0;
let seed = 20261116;
const rnd = (n) => {   // mulberry32 — 아래 비트만 쓰는 선형 합동법은 고르지 않았다 (0.88.0 에서 바꿈)
  seed = (seed + 0x6d2b79f5) | 0;
  let x = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
  return Math.floor((((x ^ (x >>> 14)) >>> 0) / 4294967296) * n);
};
const pick = (list) => list[rnd(list.length)];

function makeDoc() {
  const lines = [];
  const blocks = 2 + rnd(4);
  for (let b = 0; b < blocks; b++) {
    const kind = rnd(5);
    if (kind === 0) {
      lines.push(`${'#'.repeat(1 + rnd(4))} 제목 ${b}`, '');
    } else if (kind === 1) {
      lines.push(`문단 ${b} 이다.`, '');
    } else {
      const loose = rnd(4) === 0;
      const ordered = [rnd(2) === 0, rnd(2) === 0, rnd(2) === 0];
      const counts = [0, 0, 0];
      let depth = 0;
      const n = 2 + rnd(7);
      const widths = [0];
      for (let i = 0; i < n; i++) {
        if (i > 0) depth = Math.max(0, Math.min(2, Math.min(depth + 1, depth + rnd(3) - 1)));
        for (let k = depth + 1; k < 3; k++) counts[k] = 0;
        counts[depth] += 1;
        const marker = ordered[depth] ? `${counts[depth]}.` : pick(['-', '-', '*']);
        const lead = ' '.repeat(widths[depth] ?? 0);
        lines.push(`${lead}${marker} ${rnd(5) === 0 ? '[ ] ' : ''}항목 ${b}-${i}`);
        widths[depth + 1] = (widths[depth] ?? 0) + marker.length + 1;
        if (rnd(6) === 0) lines.push(`${' '.repeat(widths[depth + 1])}이어진 줄 ${b}-${i}`);
        if (loose) lines.push('');
      }
      if (lines.at(-1) !== '') lines.push('');
    }
  }
  while (lines.length && lines.at(-1) === '') lines.pop();
  return lines;
}

/** 줄마다 깊이: 제목은 -수준(따로 본다), 목록 항목과 그 이어진 줄은 들여쓰기로 센 깊이, 그 밖은 0 */
function depths(lines) {
  const out = [];
  let stack = [];
  for (const s of lines) {
    if (!s.trim()) {
      out.push(null);
      continue;
    }
    if (headLevel(s)) {
      stack = [];
      out.push({ head: headLevel(s) });
      continue;
    }
    const width = /^ */.exec(s)[0].length;
    const it = itemOf(s);
    if (it) {
      while (stack.length && stack.at(-1) >= width) stack.pop();
      out.push({ depth: stack.length });
      stack.push(width);
    } else {
      while (stack.length && stack.at(-1) >= width) stack.pop();
      out.push({ depth: stack.length, text: true });
      if (!width) stack = [];
    }
  }
  return out;
}

for (let run = 0; run < 600; run++) {
  const src = makeDoc();
  const a = 1 + rnd(src.length);
  const b = Math.min(src.length, a + rnd(5));
  const dir = rnd(2) ? 1 : -1;
  const opt = pick([{ tab: true }, { section: true }, {}]);
  const r = shiftLevels(src, a, b, dir, opt);
  runs += 1;
  if (r.error) continue;
  const out = r.lines;
  const where = `#${run} ${a}~${b} ${dir > 0 ? '안' : '밖'} ${JSON.stringify(opt)}\n${src.join('\n')}\n→\n${out.join('\n')}`;
  if (out.length !== src.length) {
    problems.push(`줄 수가 바뀜 ${where}`);
    continue;
  }
  if (src.some((s, i) => bareText(s).replace(/^\[[ xX]\]\s*/, '') !== bareText(out[i]).replace(/^\[[ xX]\]\s*/, ''))) problems.push(`글이 바뀜 ${where}`);
  const before = depths(src);
  const after = depths(out);
  const top = itemSpan(src, a)?.[0] ?? a;   // 고른 첫 줄이 항목의 이어진 줄이면 그 항목부터 움직인다
  for (let i = 0; i < src.length; i++) {
    const x = before[i];
    const y = after[i];
    if (!x || !y) continue;
    if (x.head && (!y.head || Math.abs(x.head - y.head) > 1)) problems.push(`제목이 두 단계 이상 ${i + 1}행 ${where}`);
    if (x.head && opt.tab && y.head !== x.head) problems.push(`Tab 이 제목을 바꿈 ${i + 1}행 ${where}`);
    if (x.depth != null && y.depth != null && !x.text && Math.abs(x.depth - y.depth) > 1) problems.push(`항목이 두 단계 이상 ${i + 1}행 ${where}`);
    if (i + 1 < top && x.depth != null && !x.text && y.depth !== x.depth) problems.push(`고른 줄 위의 항목이 움직임 ${i + 1}행 ${where}`);
    if (i + 1 < top && x.head && y.head !== x.head) problems.push(`고른 줄 위의 제목이 움직임 ${i + 1}행 ${where}`);
  }
  if (problems.length > 12) break;
  // 한 줄을 안으로 넣고 바로 밖으로 빼면 깊이가 처음과 같다 (번호·표시는 달라질 수 있다)
  if (a === b && dir > 0 && !opt.section && itemOf(src[a - 1])) {
    const back = shiftLevels(out, a, a, -1, opt);
    if (!back.error) {
      const again = depths(back.lines);
      if (before.some((x, i) => x && x.depth != null && !x.text && again[i]?.depth !== x.depth)) problems.push(`안으로 넣고 밖으로 빼니 깊이가 다름 ${where}\n→\n${back.lines.join('\n')}`);
    }
  }
}

return { problems, runs };
