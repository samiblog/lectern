// 밀린 줄 찾기 (DOM 없음): 원문이 바뀌어 줄 번호가 밀렸을 때 같은 줄들의 새 자리를 찾는다.
// 여러 줄 저장(lineedit.js 의 writeLines)이 쓴다 — Claude Code 가 같은 파일을 고치는 중일 수 있다.

const NEAR = 300;   // 앞뒤로 이만큼의 줄 안에서 찾는다

/**
 * lines(원문 줄 배열)에서 start(1부터) 자리에 block(줄 배열)이 있으면 start. 없으면 앞뒤 near 줄 안에서 같은 줄들을 찾아
 * 하나뿐일 때만 그 자리 — 둘 이상이면 어느 것인지 모르니 0 (없어도 0)
 */
export function locateLines(lines, start, block, near = NEAR) {
  const here = (at) => block.every((s, i) => lines[at - 1 + i] === s);
  if (here(start)) return start;
  const hits = [];
  const last = Math.min(lines.length - block.length + 1, start + near);
  for (let at = Math.max(1, start - near); at <= last; at++) if (here(at)) hits.push(at);
  return hits.length === 1 ? hits[0] : 0;
}
