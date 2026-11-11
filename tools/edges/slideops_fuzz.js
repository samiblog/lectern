// Lectern 슬라이드에서 줄 구조 편집을 아무렇게나 해도 칸과 장이 깨지지 않는지 (rules_check 가 돌린다 — lo: lineops.js, 끝에서 {problems, runs} 를 돌려준다)
const { planNew, insertLine, joinLine, duplicateLine, indentItem, outdentItem, moveLines, deleteLines } = lo;
const DECK = `---
marp: true
title: 시험
---

<!-- _class: lead -->

# 표지

부제

---

<!-- layout: quad -->
<!-- text: 표 12 -->

## 네 칸

::: a card
### 첫째

- 가
- 나
  - 다
:::

::: b
| 이름 | 값 |
|---|---:|
| 가 | 1 |
| 나 | 2 |
:::

::: c accent 16
한 문단

둘째 문단
:::

::: d
\`\`\`mermaid
flowchart LR
  A --> B
\`\`\`
:::

---

<!-- layout: two -->

## 둘

::: a at 10 20 300 120
1. 하나
2. 둘
:::

::: b
> [!NOTE]
> 강조글

끝 글
:::

<!-- 발표자 노트 -->

---

## 마지막

- 끝
`.split('\n');
const WALL = /^(?::::(?:[ \t]|$)|---\s*$|<!--.*-->\s*$)/;
let seed = 20261106;
const rnd = (n) => {
  seed = (seed * 1103515245 + 12345) & 0x7fffffff;
  return seed % n;
};
const split = (line) => {
  const p = /^((?:[ \t]*>[ \t]?)*[ \t]*(?:[-*+] |\d+[.)] |#{1,6} )?)(.*)$/.exec(line);
  return { head: p[1], body: p[2], tail: '' };
};
/** 칸의 머리 줄과 닫는 줄이 번갈아 나오는지 (코드 블록 밖에서) */
function broken(lines) {
  let open = false;
  let fence = false;
  for (const s of lines) {
    if (/^\s*```/.test(s)) fence = !fence;
    if (fence) continue;
    if (/^:::\s+\S/.test(s.trim())) {
      if (open) return '칸이 겹쳤다';
      open = true;
    } else if (s.trim() === ':::') {
      if (!open) return '닫는 줄만 있다';
      open = false;
    }
  }
  return open ? '칸이 닫히지 않았다' : '';
}
const count = (lines) => lines.filter((s) => s === '---').length;
const problems = [];
let runs = 0;
for (let round = 0; round < 400 && problems.length < 5; round++) {
  let lines = DECK.slice();
  for (let step = 0; step < 25; step++) {
    const size = lines.length;
    const n = 4 + rnd(Math.max(1, size - 4));
    if (/^\s*```/.test(lines[n - 1] ?? '')) continue;   // 코드 블록의 ``` 줄은 한 줄 편집이 열지 않는다
    const wall = WALL.test(lines[n - 1] ?? '');
    const dir = rnd(2) ? 1 : -1;
    const op = rnd(7);
    let r = null;
    let name = '';
    if (op === 0) {
      name = 'move';
      r = moveLines(lines, n, Math.min(size, n + rnd(3)), dir);
    } else if (op === 1) {
      name = 'delete';
      r = deleteLines(lines, n, Math.min(size, n + rnd(4)));
    } else if (op === 2 && !wall) {
      name = 'new';
      const plan = planNew(lines, n, rnd(2) === 0);
      r = plan.error ? plan : insertLine(lines, plan, '새 글');
    } else if (op === 3) {
      name = 'join';
      r = joinLine(lines, n, { split });
    } else if (op === 4 && !wall) {
      name = 'dup';
      r = duplicateLine(lines, n, { split });
    } else if (op === 5 && !wall) {
      name = 'indent';
      r = indentItem(lines, n);
    } else if (op === 6 && !wall) {
      name = 'outdent';
      r = outdentItem(lines, n);
    }
    if (!r || r.error) continue;
    runs += 1;
    const before = lines;
    lines = r.lines;
    const bad = broken(lines);
    if (bad) problems.push(`${name} ${n}행: ${bad} — ${JSON.stringify(before[n - 1])}`);
    if (name !== 'delete' && count(lines) !== count(before)) problems.push(`${name} ${n}행: 장 수가 달라졌다 — ${JSON.stringify(before[n - 1])}`);
    if (lines.slice(0, 3).join() !== DECK.slice(0, 3).join()) problems.push(`${name} ${n}행: 맨 앞 설정이 달라졌다`);
    if (bad) break;
  }
}
return { problems, runs };
