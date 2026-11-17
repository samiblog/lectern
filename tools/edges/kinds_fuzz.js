// 줄 종류 바꾸기의 임의 시험 (D155) — rules_check.mjs 가 돌린다 (d: docops.js, lo: lineops.js)
// 임의로 만든 문서(제목, 문단, 글머리·번호·할 일이 섞인 두 단계 목록, 인용, 강조글, 표, 코드 블록)에서 임의의 줄을 골라 종류를 바꾼 뒤
// 어떤 경우에도 지켜져야 할 것을 본다:
//   고른 줄 밖의 글은 그대로다(번호와 빈 줄만 바뀔 수 있다) · 고른 줄의 글은 순서대로 남는다 · 강조글의 머리 줄은 그대로이고 본문과 갈리지 않는다
//   · 코드 블록·표는 그대로다 · 번호 목록은 번호를 잇는다(모두 같은 번호로 쓴 목록 말고) · 같은 종류로 한 번 더 바꾸면 그대로다
const { setKind, bareText, kindOfLine } = d;
const { itemOf, quoteOf, isBlank, fencesOf, fenceAt, siblingsOf } = lo;
const problems = [];
let runs = 0;
let seed = 20261117;
const rnd = (n) => {   // mulberry32 — 아래 비트만 쓰는 선형 합동법은 고르지 않아 강조글·표가 든 문서가 나오지 않았다
  seed = (seed + 0x6d2b79f5) | 0;
  let x = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
  return Math.floor((((x ^ (x >>> 14)) >>> 0) / 4294967296) * n);
};
const pick = (list) => list[rnd(list.length)];

function makeDoc() {
  const lines = [];
  const blocks = 3 + rnd(4);
  for (let b = 0; b < blocks; b++) {
    const kind = rnd(8);
    if (kind === 0) lines.push(`${'#'.repeat(2 + rnd(2))} 제목 ${b}`);
    else if (kind === 1) lines.push(`문단 ${b} 이다.`);
    else if (kind === 2) lines.push(`> 인용 ${b} 첫 줄`, `> 인용 ${b} 둘째 줄`);
    else if (kind === 3) lines.push(`> [!${pick(['NOTE', 'TIP', 'WARNING'])}]`, `> 강조 ${b} 첫 줄`, ...(rnd(2) ? [`> 강조 ${b} 둘째 줄`] : []));
    else if (kind === 4) lines.push('| 가 | 나 |', '|---|---|', `| ${b} | 값 |`);
    else if (kind === 5) lines.push('```', `코드 ${b}`, '```');
    else {
      const ordered = rnd(2) === 0;
      const flat = ordered && rnd(5) === 0;
      const loose = rnd(4) === 0;
      const n = 2 + rnd(5);
      let num = ordered ? 1 + rnd(3) : 0;
      for (let i = 0; i < n; i++) {
        const mark = ordered ? `${flat ? 1 : num++}. ` : pick(['- ', '- ', '* ']);
        lines.push(`${mark}${rnd(5) === 0 ? '[ ] ' : ''}항목 ${b}-${i}`);
        if (rnd(5) === 0) lines.push(`${' '.repeat(mark.length)}- 하위 ${b}-${i}`);
        if (loose && i < n - 1) lines.push('');
      }
    }
    lines.push('');
  }
  while (lines.length && lines.at(-1) === '') lines.pop();
  return lines;
}

/** 글의 차례 — 표시(목록·인용·제목·할 일 칸)와 빈 줄을 뺀 글 */
const words = (lines) => lines.map((s) => bareText(s).replace(/^\[[ xX]\]\s*/, '')).filter(Boolean);

/** 번호 목록이 번호를 잇는지 — 같은 수준의 형제끼리 1씩 (모두 같은 번호면 그대로 둔 것) */
function numberingOk(lines) {
  const seen = new Set();
  for (let n = 1; n <= lines.length; n++) {
    const it = itemOf(lines[n - 1]);
    if (!it?.ordered || seen.has(n)) continue;
    const sib = siblingsOf(lines, n);
    sib.forEach((x) => seen.add(x));
    const nums = sib.map((x) => itemOf(lines[x - 1]).num);
    if (nums.length > 1 && !nums.every((x) => x === nums[0]) && nums.some((x, i) => i && x !== nums[i - 1] + 1)) return `${nums.join(',')} (${sib[0]}행)`;
  }
  return '';
}

const KINDS = ['h2', 'h3', 'para', 'bullet', 'number', 'task', 'quote'];
for (let run = 0; run < 800; run++) {
  const src = makeDoc();
  const a = 1 + rnd(src.length);
  const b = Math.min(src.length, a + rnd(3));
  const kind = pick(KINDS);
  const r = setKind(src, a, b, kind);
  runs += 1;
  if (r.error) continue;
  const out = r.lines;
  const where = `#${run} ${a}~${b} → ${kind}\n${src.join('\n')}\n→\n${out.join('\n')}`;
  // 글은 순서대로 그대로 (표시만 바뀐다)
  if (words(src).join('|') !== words(out).join('|')) problems.push(`글이 바뀜 ${where}`);
  // 고른 줄 밖: 번호·빈 줄·들여쓰기(하위를 당긴 것) 말고는 그대로
  const outside = (lines, x, y) => lines.filter((_, i) => i + 1 < x || i + 1 > y).map((s) => s.replace(/^\s*>?\s*/, '').replace(/^(\d+)([.)])/, '#$2').trim()).filter(Boolean);
  const before = outside(src, a, b).filter((s) => !/^\[![A-Z]+\]$/.test(s));
  const after = outside(out, r.a, r.b).filter((s) => !/^\[![A-Z]+\]$/.test(s));
  if (before.join('|') !== after.join('|')) problems.push(`고른 줄 밖이 바뀜 ${where}`);
  // 강조글: 머리 줄 수가 그대로이고, 머리 줄 바로 다음은 강조글 본문이다
  const heads = (lines) => lines.filter((s) => /^>\s?\[![A-Z]+\]\s*$/.test(s)).length;
  if (heads(src) !== heads(out)) problems.push(`강조글 머리 줄 수가 바뀜 ${where}`);
  out.forEach((s, i) => {
    if (/^>\s?\[![A-Z]+\]\s*$/.test(s) && (i + 1 >= out.length || !quoteOf(out[i + 1]) || isBlank(out[i + 1]))) problems.push(`강조글이 머리 줄과 갈림 ${i + 1}행 ${where}`);
  });
  // 코드 블록·표는 그대로
  const blocksText = (lines) => {
    const f = fencesOf(lines);
    return lines.filter((s, i) => fenceAt(f, i + 1) || /^\|/.test(s.trim())).join('\n');
  };
  if (blocksText(src) !== blocksText(out)) problems.push(`코드·표가 바뀜 ${where}`);
  // 번호 목록은 번호를 잇는다 (원래 이어져 있던 문서에서)
  if (!numberingOk(src)) {
    const bad = numberingOk(out);
    if (bad) problems.push(`번호가 끊김 ${bad} ${where}`);
  }
  // 같은 종류로 한 번 더 바꾸면 그대로 (바꾼 줄이 모두 그 종류일 때)
  const kinds = out.slice(r.a - 1, r.b).map((s) => kindOfLine(s)).filter(Boolean);
  if (kinds.length && kinds.every((k) => k === kind)) {
    const again = setKind(out, r.a, r.b, kind);
    if (!again.error && again.lines.join('\n') !== out.join('\n')) problems.push(`한 번 더 바꾸니 달라짐 ${where}\n→\n${again.lines.join('\n')}`);
  }
  if (problems.length > 10) break;
}

return { problems, runs };
