// lineops.js 의 불변 조건 점검 (structure.py 가 페이지 안에서 돌린다 — m: lineops.js, 끝에서 {runs, problems} 를 돌려준다).
// 임의의 문서에서 줄마다 옮기기·지우기·추가·복제·나누기·합치기·레벨을 해 본다: 글이 사라지지 않는지, 저장 범위(diffRange)를 적용하면 같은지,
// 반대로 옮기면 원문인지, 나눈 것을 합치면 원문인지, markdown-it 으로 그린 구조(항목·코드 블록·표·제목·가로줄·인용의 수)가 바뀌지 않는지.
const { diffRange, planNew, insertLine, splitLine, joinLine, duplicateLine, indentItem, outdentItem, moveLines, deleteLines } = m;
const md = window.markdownit({ html: true });
const shape = (lines) => {
  const html = md.render(lines.join('\n'));
  const n = (re) => (html.match(re) || []).length;
  return { li: n(/<li>/g), pre: n(/<pre>/g), table: n(/<table>/g), h: n(/<h[1-6]>/g), hr: n(/<hr>/g), q: n(/<blockquote>/g) };
};
const sameShape = (a, b, skip = []) => Object.keys(a).every((k) => skip.includes(k) || a[k] === b[k]);
let seed = 7;
const rnd = (n) => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed % n; };
const pick = (a) => a[rnd(a.length)];
let uid = 0;
const w = () => `w${++uid}`;

function nested(depth = 0, parentContent = 0) {
  const out = [];
  const ordered = rnd(2) === 0;
  const n = 1 + rnd(4);
  const pad = ' '.repeat(parentContent);
  for (let i = 1; i <= n; i++) {
    const marker = ordered ? `${i}.` : '-';
    out.push(`${pad}${marker} ${rnd(4) === 0 ? '[ ] ' : ''}${w()}`);
    const content = parentContent + marker.length + 1;
    if (rnd(4) === 0) out.push(`${' '.repeat(content)}${w()}`);
    if (depth < 2 && rnd(3) === 0) out.push(...nested(depth + 1, content));
  }
  return out;
}
const BLOCKS = [
  () => [`# ${w()}`],
  () => [`## ${w()}`],
  () => [w()],
  () => [w(), w(), w()],
  () => nested(),
  () => [`> ${w()}`, `> ${w()}`],
  () => ['> [!NOTE]', `> ${w()}`, `> ${w()}`],
  () => [`| ${w()} | ${w()} |`, '|---|---|', `| ${w()} | ${w()} |`, `| ${w()} | ${w()} |`],
  () => ['```python', w(), '', `# ${w()}`, '```'],
  () => ['~~~', w(), '~~~'],
  () => ['$$', w(), '', w(), '$$'],
  () => ['---'],
  () => [`Title ${w()}`, '==='],
];
function doc() {
  const parts = [];
  if (rnd(5) === 0) parts.push(['---', `t: ${w()}`, '---']);
  const n = 1 + rnd(7);
  for (let i = 0; i < n; i++) parts.push(pick(BLOCKS)());
  const lines = [];
  parts.forEach((p, i) => { if (i) lines.push(''); lines.push(...p); });
  if (rnd(4)) lines.push('');
  return lines;
}
const words = (lines) => lines.join('\n').match(/w\d+/g) || [];
const sameWords = (a, b) => JSON.stringify([...words(a)].sort()) === JSON.stringify([...words(b)].sort());
const applied = (old, d) => { const x = old.slice(); x.splice(d.start - 1, d.before.length, ...d.after); return x; };
const split = (line) => { const p = /^((?:[ \t]*>[ \t]?)*[ \t]*(?:[-*+] (?:\[[ xX]\] )?|\d+[.)] (?:\[[ xX]\] )?|#{1,6} )?)(.*)$/.exec(line); return { head: p[1], body: p[2], tail: '' }; };

let runs = 0;
const problems = new Map();
const bad = (kind, lines, info) => { if (!problems.has(kind)) problems.set(kind, { n: 0, lines: lines.join('\n'), info }); problems.get(kind).n += 1; };
const diffOk = (old, next, kind) => {
  const d = diffRange(old, next);
  if (old.length && !d.before.length) bad(`${kind}: 빈 before`, old, next.join('\n'));
  if (applied(old, d).join('\n') !== next.join('\n')) bad(`${kind}: diff 적용이 다름`, old, next.join('\n'));
};

const N = 500;
for (let i = 0; i < N; i++) {
  const lines = doc();
  if (lines[0] === '---' && lines[1] === '') continue;   // 맨 앞의 가로줄: 뒤의 --- 까지 머리 정보로 읽힌다 — 고칠 수 있는 줄이 없다
  const textLines = lines.map((s, k) => (s.trim() ? k + 1 : 0)).filter(Boolean);
  if (!textLines.length) continue;
  for (let j = 0; j < 12; j++) {
    runs += 1;
    const a = pick(textLines);
    const b = Math.min(lines.length, a + (rnd(3) === 0 ? rnd(5) : 0));
    const dir = rnd(2) ? 1 : -1;
    const code = rnd(10) === 0;
    try {
      const mv = moveLines(lines, a, b, dir, { code });
      if (!mv.error) {
        if (mv.lines.length !== lines.length) bad('옮기기: 줄 수가 바뀜', lines, [a, b, dir, mv.lines.join('\n')]);
        if (!sameWords(lines, mv.lines)) bad('옮기기: 글이 사라짐', lines, [a, b, dir, mv.lines.join('\n')]);
        if (mv.a < 1 || mv.b > mv.lines.length || mv.a > mv.b) bad('옮기기: 범위가 잘못됨', lines, [a, b, dir, mv.a, mv.b]);
        const shown = lines.slice(a - 1, b).join('\n').match(/w\d+/g) || [];
        const after = mv.lines.slice(mv.a - 1, mv.b).join('\n').match(/w\d+/g) || [];
        if (shown.join() !== after.join()) bad('옮기기: 돌려준 범위가 옮긴 줄이 아님', lines, [a, b, dir, mv.a, mv.b, mv.lines.join('\n')]);
        diffOk(lines, mv.lines, '옮기기');
        if (!code && !sameShape(shape(lines), shape(mv.lines))) bad('옮기기: 구조가 바뀜', lines, [a, b, dir, shape(lines), shape(mv.lines), mv.lines.join('\n')]);
        const back = moveLines(mv.lines, mv.a, mv.b, -dir, { code });
        if (code && mv.lines.at(-1) === '') { /* 코드 화면: 빈 줄이 끝으로 가면 끝 줄바꿈으로 읽는다 */ }
        else if (back.error) bad(`옮기기: 되돌아오지 못함 (${back.error})`, lines, [a, b, dir, mv.a, mv.b, mv.lines.join('\n')]);
        else if (back.lines.join('\n') !== lines.join('\n')) bad('옮기기: 반대로 옮겨도 원문이 아님', lines, [a, b, dir, mv.lines.join('\n'), back.lines.join('\n')]);
      }
      const del = deleteLines(lines, a, b, { code });
      if (!del.error) {
        const gone = lines.slice(del.a - 1, del.b);
        const keep = [...lines.slice(0, del.a - 1), ...lines.slice(del.b)];
        if (!sameWords(keep, del.lines)) bad('지우기: 범위 밖의 글이 사라지거나 늘어남', lines, [a, b, del.a, del.b, del.lines.join('\n')]);
        if (del.line < 1 || (del.lines.length && del.line > del.lines.length)) bad('지우기: 현재 줄이 잘못됨', lines, [a, b, del.line, del.lines.length]);
        diffOk(lines, del.lines, '지우기');
        if (!code) {
          const x = shape(lines);
          const y = shape(del.lines);
          if (y.pre > x.pre) bad('지우기: 코드 블록이 생김', lines, [a, b, del.a, del.b, del.lines.join('\n')]);
          if (y.table > x.table) bad('지우기: 표가 생김', lines, [a, b, del.lines.join('\n')]);
        }
        for (let k = 1; k < del.lines.length; k++) {
          if (!code && !del.lines[k].trim() && !del.lines[k - 1].trim() && k < del.lines.length - 0) {
            const had = lines.some((s, q) => q && !s.trim() && !lines[q - 1].trim());
            if (!had) { bad('지우기: 빈 줄이 겹침', lines, [a, b, del.lines.join('\n')]); break; }
          }
        }
        void gone;
      }
      for (const below of [true, false]) {
        const plan = planNew(lines, a, below, { code, parts: split(lines[a - 1]) });
        if (!plan.error) {
          const r = insertLine(lines, plan, 'NEW');
          if (!r.lines[r.line - 1].endsWith('NEW')) bad('줄 추가: 돌려준 줄이 새 줄이 아님', lines, [a, below, r.line, r.lines.join('\n')]);
          if (!sameWords(lines, r.lines)) bad('줄 추가: 글이 바뀜', lines, [a, below, r.lines.join('\n')]);
          diffOk(lines, r.lines, '줄 추가');
          if (!code) {
            const x = shape(lines);
            const y = shape(r.lines);
            if (plan.kind === 'item' ? y.li !== x.li + 1 || !sameShape(x, y, ['li']) : !sameShape(x, y)) bad(`줄 추가: 구조가 바뀜 (${plan.kind})`, lines, [a, below, x, y, r.lines.join('\n')]);
          }
        }
      }
      const dup = duplicateLine(lines, a, { split, code });
      if (!dup.error) {
        if (dup.lines.length < lines.length + 1) bad('복제: 줄이 늘지 않음', lines, [a]);
        diffOk(lines, dup.lines, '복제');
      }
      const body = split(lines[a - 1]).body;
      if (body.length > 2 && !/^\s*(?:---|===|\||```|~~~|\$\$|> \[!)/.test(lines[a - 1]) && !(a <= 3 && lines[0] === '---')) {   // 한 줄 편집으로 고칠 수 없는 줄은 빼고
        const off = 1 + rnd(body.length - 1);
        const sp = splitLine(lines, a, off, { split, code });
        if (!sp.error) {
          if (!sp.lines.join('').includes(body.slice(off).trimStart())) bad('나누기: 뒤 글이 사라짐', lines, [a, off, sp.lines.join('\n')]);
          diffOk(lines, sp.lines, '나누기');
          const j2 = joinLine(sp.lines, sp.line, { split, code });
          if (/^#{1,6} /.test(lines[a - 1])) { /* 제목을 나누면 문단이 되어 합치지 않는다 (사용자 결정) */ }
          else if (j2.error) bad(`나누기: 합치지 못함 (${j2.error})`, lines, [a, off, sp.lines.join('\n')]);
          else if (j2.lines.join('\n').replace(/\s+/g, '') !== lines.join('\n').replace(/\s+/g, '')) bad('나누기: 합쳐도 원문이 아님', lines, [a, off, sp.lines.join('\n'), j2.lines.join('\n')]);
        }
      }
      const jn = joinLine(lines, a, { split, code });
      if (!jn.error) {
        if (!sameWords(lines, jn.lines)) bad('합치기: 글이 사라짐', lines, [a, jn.lines.join('\n')]);
        diffOk(lines, jn.lines, '합치기');
      }
      const ind = indentItem(lines, a);
      if (!ind.error) {
        if (ind.lines.length !== lines.length || !sameWords(lines, ind.lines)) bad('안으로: 글이 바뀜', lines, [a, ind.lines.join('\n')]);
        diffOk(lines, ind.lines, '안으로');
        if (!sameShape(shape(lines), shape(ind.lines))) bad('안으로: 구조가 바뀜', lines, [a, shape(lines), shape(ind.lines), ind.lines.join('\n')]);
      }
      const out = outdentItem(lines, a);
      if (!out.error) {
        if (out.lines.length !== lines.length || !sameWords(lines, out.lines)) bad('밖으로: 글이 바뀜', lines, [a, out.lines.join('\n')]);
        diffOk(lines, out.lines, '밖으로');
        if (!sameShape(shape(lines), shape(out.lines))) bad('밖으로: 구조가 바뀜', lines, [a, shape(lines), shape(out.lines), out.lines.join('\n')]);
      }
    } catch (e) {
      bad(`예외: ${e.message}`, lines, [a, b, dir, e.stack.split('\n')[1]]);
    }
  }
}
return { runs, problems: [...problems].map(([kind, p]) => `${kind} (${p.n}번): ${JSON.stringify(p.lines)} ${JSON.stringify(p.info)}`) };
