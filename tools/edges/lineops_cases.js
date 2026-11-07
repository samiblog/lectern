// lineops.js 의 계산 점검 (structure.py 가 페이지 안에서 돌린다 — m: lineops.js, 끝에서 {n, fails} 를 돌려준다).
const { diffRange, planNew, insertLine, splitLine, joinLine, duplicateLine, indentItem, outdentItem, moveLines, deleteLines } = m;
let n = 0;
const fails = [];
const L = (s) => s.split('\n');
const eq = (got, want, name) => {
  n += 1;
  const show = (x) => (Array.isArray(x) ? x.join('\n') : JSON.stringify(x));
  if (show(got) !== show(want)) fails.push(`${name}: ${show(got)} ≠ ${show(want)}`);
};
const split = (line) => {
  const p = /^((?:[ \t]*>[ \t]?)*[ \t]*(?:[-*+] |\d+[.)] |#{1,6} )?)(.*)$/.exec(line);
  return { head: p[1], body: p[2], tail: '' };
};
const plain = (l) => ({ head: '', body: l, tail: '' });

// 줄 추가
const add = (s, at, below, text, o) => {
  const l = L(s);
  const p = planNew(l, at, below, o);
  return p.error ? p : insertLine(l, p, text).lines;
};
eq(add('- a\n- b\n', 1, true, 'x'), L('- a\n- x\n- b\n'), '글머리 아래');
eq(add('- a\n  - c\n- b\n', 1, true, 'x'), L('- a\n  - c\n- x\n- b\n'), '하위 항목 뒤에');
eq(add('- a\n- b\n', 2, false, 'x'), L('- a\n- x\n- b\n'), '글머리 위');
eq(add('1. a\n2. b\n3. c\n', 1, true, 'x'), L('1. a\n2. x\n3. b\n4. c\n'), '번호 아래');
eq(add('1. a\n2. b\n', 1, false, 'x'), L('1. x\n2. a\n3. b\n'), '번호 위');
eq(add('1. a\n1. b\n', 1, true, 'x'), L('1. a\n1. x\n1. b\n'), '모두 같은 번호');
eq(add('5. a\n6. b\n', 2, true, 'x'), L('5. a\n6. b\n7. x\n'), '5 부터 시작');
eq(add('9. a\n   more\n10. b\n', 1, true, 'x'), L('9. a\n   more\n10. x\n11. b\n'), '9 뒤에');
eq(add('8. a\n9. b\n   more\n', 1, true, 'x'), L('8. a\n9. x\n10. b\n    more\n'), '자릿수가 늘면 안쪽 줄도');
eq(add('- [x] a\n', 1, true, 'x'), L('- [x] a\n- [ ] x\n'), '할 일');
eq(add('- a\n\n- b\n', 1, true, 'x'), L('- a\n\n- x\n\n- b\n'), '빈 줄로 띄운 목록');
eq(add('para\n\nnext\n', 1, true, 'x'), L('para\n\nx\n\nnext\n'), '문단 아래');
eq(add('para\n\nnext\n', 3, false, 'x'), L('para\n\nx\n\nnext\n'), '문단 위');
eq(add('para', 1, true, 'x'), L('para\n\nx'), '끝 줄바꿈 없는 파일');
eq(add('para\n', 1, true, 'x'), L('para\n\nx\n'), '파일 끝');
eq(add('# t\ntext\n', 1, true, 'x'), L('# t\n\nx\n\ntext\n'), '붙은 제목');
eq(add('# t\n\ntext\n', 1, true, 'x'), L('# t\n\nx\n\ntext\n'), '제목 아래');
eq(add('a\nb\nc\n', 2, true, 'x'), L('a\nb\nc\n\nx\n'), '나눠 쓴 문단은 그 뒤에');
eq(add('> a\n> b\n\nz\n', 1, true, 'x'), L('> a\n> b\n>\n> x\n\nz\n'), '인용');
eq(add('> [!NOTE]\n> a\n', 2, false, 'x'), L('> [!NOTE]\n> x\n>\n> a\n'), '박스글 위');
eq(add('> - a\n> - b\n', 1, true, 'x'), L('> - a\n> - x\n> - b\n'), '인용 속 목록');
eq(add('|a|b|\n|-|-|\n|1|2|\n', 3, true, 'x'), { error: 'table' }, '표');
eq(add('```\n  a\nb\n```\n', 2, true, 'x', { parts: { head: '', body: '  a' } }), L('```\n  a\nx\nb\n```\n'), '코드 블록');
eq(add('x\ny\n', 1, true, 'z', { code: true }), L('x\nz\ny\n'), '코드 화면');

// 나누기
const sp = (s, at, off, o = {}) => {
  const r = splitLine(L(s), at, off, { split, ...o });
  return r.error ? r : r.lines;
};
eq(sp('- abc def\n  - kid\n', 1, 4), L('- abc\n- def\n  - kid\n'), '항목 나누기 — 하위 항목은 뒤 글을 따름');
eq(sp('1. abc def\n2. z\n', 1, 4), L('1. abc\n2. def\n3. z\n'), '번호 나누기');
eq(sp('abc def\n\nz\n', 1, 4), L('abc\n\ndef\n\nz\n'), '문단 나누기');
eq(sp('abc def\nnext\n\nz\n', 1, 4), L('abc\n\ndef\nnext\n\nz\n'), '나눠 쓴 문단 나누기');
eq(sp('## abc def\n\nz\n', 1, 4), L('## abc\n\ndef\n\nz\n'), '제목 나누기');
eq(sp('> abc def\n', 1, 4), L('> abc\n>\n> def\n'), '인용 나누기');

// 복제
const dup = (s, at, o = {}) => {
  const r = duplicateLine(L(s), at, { split, ...o });
  return r.error ? r : [r.lines.join('\n'), r.line, r.offset];
};
eq(dup('- a\n- b\n', 1), ['- a\n- a\n- b\n', 2, 1], '항목 복제');
eq(dup('1. a\n2. b\n', 1), ['1. a\n2. a\n3. b\n', 2, 1], '번호 복제');
eq(dup('## a\n\nz\n', 1), ['## a\n\n## a\n\nz\n', 3, 1], '제목 복제');
eq(dup('a\n\nz\n', 1), ['a\n\na\n\nz\n', 3, 1], '문단 복제');
eq(dup('|a|\n|-|\n|1|\n', 3), { error: 'table' }, '표는 복제하지 않음');

// 합치기
const jn = (s, at, o = {}) => {
  const r = joinLine(L(s), at, { split, ...o });
  return r.error ? r : [r.lines.join('\n'), r.line, r.offset];
};
eq(jn('- a\n- b\n', 2), ['- ab\n', 1, 1], '항목 합치기');
eq(jn('1. a\n2. b\n3. c\n', 2), ['1. ab\n2. c\n', 1, 1], '번호 합치기');
eq(jn('a\n\nb\n', 3), ['ab\n', 1, 1], '문단 합치기');
eq(jn('a\nb\n', 2), ['ab\n', 1, 1], '문단의 줄 합치기');
eq(jn('# a\n\nb\n', 3), { error: 'different' }, '제목과 문단');
eq(jn('- a\n\nb\n', 3), { error: 'different' }, '항목과 문단');
eq(jn('## a\n\n## b\n', 3), ['## ab\n', 1, 1], '같은 수준 제목');
eq(jn('## a\n\n### b\n', 3), { error: 'different' }, '다른 수준 제목');
eq(jn('- a\n  more\n', 2), ['- amore\n', 1, 1], '이어진 줄');
eq(jn('- a\n- b\n  - c\n', 2), ['- ab\n  - c\n', 1, 1], '하위 항목은 그대로');
eq(jn('a\n', 1), { error: 'different' }, '첫 줄');
eq(jn('```\na\nb\n```\n', 3, { split: plain }), ['```\nab\n```\n', 2, 1], '코드 줄');
eq(jn('```\na\n```\n', 2, { split: plain }), { error: 'different' }, '코드 블록의 첫 줄');
eq(jn('|a|\n|-|\n|1|\n\nz\n', 5), { error: 'different' }, '표 뒤의 문단');

// 레벨
const ind = (s, at) => {
  const r = indentItem(L(s), at);
  return r.error ? r : r.lines;
};
const out = (s, at) => {
  const r = outdentItem(L(s), at);
  return r.error ? r : r.lines;
};
eq(ind('- a\n- b\n', 2), L('- a\n  - b\n'), '안으로');
eq(ind('- a\n- b\n  - c\n', 2), L('- a\n  - b\n    - c\n'), '하위 항목도');
eq(ind('- a\n', 1), { error: 'first-item' }, '맨 앞 항목');
eq(ind('para\n', 1), { error: 'not-list' }, '문단');
eq(ind('1. a\n2. b\n3. c\n', 2), L('1. a\n   1. b\n2. c\n'), '번호 안으로');
eq(ind('- a\n  - x\n- b\n', 3), L('- a\n  - x\n  - b\n'), '앞 항목의 하위 목록에');
eq(ind('1. a\n   1. x\n2. b\n', 3), L('1. a\n   1. x\n   2. b\n'), '번호 하위 목록에');
eq(out('- a\n  - b\n', 2), L('- a\n- b\n'), '밖으로');
eq(out('- a\n', 1), { error: 'top-level' }, '맨 바깥');
eq(out('1. a\n   1. b\n2. c\n', 2), L('1. a\n2. b\n3. c\n'), '번호 밖으로');
eq(out('- a\n  - b\n    - c\n', 2), L('- a\n- b\n  - c\n'), '밖으로 — 하위 항목도');
eq(out('- a\n  - b\n  - c\n', 2), L('- a\n- b\n  - c\n'), '뒤 항목은 하위가 됨');
eq(out('1. a\n   1. b\n   2. c\n', 2), L('1. a\n2. b\n   1. c\n'), '남은 번호');

// 옮기기
const mv = (s, a, b, d, o) => {
  const r = moveLines(L(s), a, b, d, o);
  return r.error ? r : [r.lines.join('\n'), r.a, r.b];
};
eq(mv('- a\n- b\n', 2, 2, -1), ['- b\n- a\n', 1, 1], '항목 위로');
eq(mv('- a\n  - k\n- b\n', 1, 1, 1), ['- b\n- a\n  - k\n', 2, 2], '하위 항목과 아래로');
eq(mv('- a\n- b\n  - k\n', 2, 2, -1), ['- b\n  - k\n- a\n', 1, 1], '하위 항목과 위로');
eq(mv('- a\n', 1, 1, -1), { error: 'edge' }, '목록의 끝');
eq(mv('1. a\n2. b\n3. c\n', 3, 3, -1), ['1. a\n2. c\n3. b\n', 2, 2], '번호 다시 매김');
eq(mv('3. a\n4. b\n', 1, 1, 1), ['3. b\n4. a\n', 2, 2], '시작 번호 유지');
eq(mv('- a\n\n- b\n', 1, 1, 1), ['- b\n\n- a\n', 3, 3], '띄운 목록');
eq(mv('- a\n- b\n- c\n', 1, 2, 1), ['- c\n- a\n- b\n', 2, 3], '두 항목');
eq(mv('- a\n  - k\n- b\n- c\n', 2, 3, 1), { error: 'mixed' }, '수준이 다른 항목');
eq(mv('p1\n\np2\n\np3\n', 3, 3, -1), ['p2\n\np1\n\np3\n', 1, 1], '문단');
eq(mv('p1\n\np2\n', 3, 3, 1), { error: 'edge' }, '마지막 문단');
eq(mv('p1\n\nl1\nl2\nl3\n', 4, 4, -1), ['p1\n\nl2\nl1\nl3\n', 3, 3], '문단 안의 줄');
eq(mv('p1\n\nl1\nl2\n', 3, 3, -1), { error: 'edge' }, '문단 안의 맨 윗줄');
eq(mv('p1\n\nl1\nl2\n', 3, 4, -1), ['l1\nl2\n\np1\n', 1, 2], '문단 통째로');
eq(mv('---\nt: 1\n---\n\np1\n', 5, 5, -1), { error: 'edge' }, '머리 정보 위로는 못 감');
eq(mv('# a\n\ntext\n', 3, 3, -1), ['text\n\n# a\n', 1, 1], '제목 위로');
eq(mv('```\na\nb\nc\n```\n', 3, 3, -1), ['```\nb\na\nc\n```\n', 2, 2], '코드 줄');
eq(mv('```\na\nb\n```\n', 2, 2, -1), { error: 'edge' }, '코드 블록 안에서만');
eq(mv('x\n\n```\na\n\nb\n```\n', 4, 6, -1), ['```\na\n\nb\n```\n\nx\n', 2, 4], '코드 줄 전부면 블록째');
eq(mv('|a|\n|-|\n|1|\n|2|\n', 4, 4, -1), ['|a|\n|-|\n|2|\n|1|\n', 3, 3], '표의 행');
eq(mv('|a|\n|-|\n|1|\n|2|\n', 3, 3, -1), { error: 'edge' }, '표의 첫 행');
eq(mv('|a|\n|-|\n|1|\n', 1, 2, 1), { error: 'table-head' }, '머리행');
eq(mv('p\n\n|a|\n|-|\n|1|\n', 3, 5, -1), ['|a|\n|-|\n|1|\n\np\n', 1, 3], '표 통째로');
eq(mv('> [!NOTE]\n> a\n> b\n', 3, 3, -1), ['> [!NOTE]\n> b\n> a\n', 2, 2], '박스글 안');
eq(mv('> [!NOTE]\n> a\n> b\n', 2, 2, -1), { error: 'edge' }, '박스글 머리 위로는 못 감');
eq(mv('a\nb\nc\n', 2, 2, 1, { code: true }), ['a\nc\nb\n', 3, 3], '코드 화면');
eq(mv('a\nb\n', 2, 2, 1, { code: true }), { error: 'edge' }, '코드 화면의 끝');
eq(mv('Title\n===\n\np\n', 4, 4, -1), ['p\n\nTitle\n===\n', 1, 1], '밑줄 제목 위로');

// 지우기
const del = (s, a, b, o) => {
  const r = deleteLines(L(s), a, b, o);
  return r.error ? r : [r.lines.join('\n'), r.line, r.ask];
};
eq(del('a\n\nb\n\nc\n', 3, 3), ['a\n\nc\n', 3, false], '문단');
eq(del('a\n\nb\n', 3, 3), ['a\n', 2, false], '끝 문단');
eq(del('a\n\nb\n', 1, 1), ['b\n', 1, false], '첫 문단');
eq(del('# t\n\nb\n', 1, 1), ['b\n', 1, true], '제목은 물음');
eq(del('1. a\n2. b\n3. c\n', 2, 2), ['1. a\n2. c\n', 2, false], '번호 다시 매김');
eq(del('1. a\n2. b\n3. c\n', 1, 1), ['1. b\n2. c\n', 1, false], '첫 항목');
eq(del('- a\n  - k\n- b\n', 1, 1), ['- k\n- b\n', 1, false], '남는 하위 항목을 올림');
eq(del('|a|\n|-|\n|1|\n\nz\n', 1, 2), { error: 'table-head' }, '머리행만');
eq(del('|a|\n|-|\n|1|\n|2|\n\nz\n', 3, 3), ['|a|\n|-|\n|2|\n\nz\n', 3, false], '표의 행');
eq(del('x\n\n|a|\n|-|\n|1|\n\nz\n', 3, 5), ['x\n\nz\n', 3, false], '표 전체');
eq(del('```\na\nb\n```\n', 2, 2), ['```\nb\n```\n', 2, false], '코드 줄');
eq(del('x\n\n```\na\nb\n```\n\nz\n', 4, 5), ['x\n\nz\n', 3, false], '코드 줄 전부');
eq(del('x\n\n```\na\nb\n```\n', 1, 4), { error: 'fence' }, '코드 블록 일부');
eq(del('```\n\n\nb\n```\n', 2, 2), ['```\n\nb\n```\n', 2, false], '코드의 빈 줄은 줄이지 않음');
eq(del('a\nb\nc\nd\ne\nf\ng\nh\ni\nj\nk\nl\n', 1, 11), ['l\n', 1, true], '11줄은 물음');
eq(del('a\nb\nc\nd\ne\nf\ng\nh\ni\nj\nk\n', 1, 10), ['k\n', 1, false], '10줄은 묻지 않음');
eq(del('a\nb\n', 2, 2, { code: true }), ['a\n', 2, false], '코드 화면');
eq(del('a\n', 1, 2), ['', 1, false], '전부');
eq(del('> a\n>\n> b\n>\n> c\n', 3, 3), ['> a\n>\n> c\n', 3, false], '인용 안');
eq(del('```\n# x\n```\n', 2, 2), ['', 1, false], '코드의 # 줄은 제목이 아님');

// 다른 곳
eq(diffRange(L('a\nb\nc'), L('a\nx\nc')), { start: 2, before: ['b'], after: ['x'] }, '바뀐 줄');
eq(diffRange(L('a\nc'), L('a\nb\nc')), { start: 1, before: ['a'], after: ['a', 'b'] }, '넣기');
eq(diffRange(L('c'), L('b\nc')), { start: 1, before: ['c'], after: ['b', 'c'] }, '맨 앞에 넣기');
eq(diffRange(L('a\n\n\nb'), L('a\n\nb')), { start: 1, before: ['a', '', ''], after: ['a', ''] }, '빈 줄뿐이면 앞 글 줄까지');
// 문서 끝의 새 줄 (D106)
const { planEnd, shiftPlan } = m;
const atEnd = (s, text) => insertLine(L(s), planEnd(L(s)), text).lines;
eq(atEnd('', 'x'), L('x\n'), '빈 문서');
eq(atEnd('# 제목\n\n', 'x'), L('# 제목\n\nx\n\n'), '제목 뒤');
eq(atEnd('글\n', 'x'), L('글\n\nx\n'), '문단 뒤');
eq(atEnd('글', 'x'), L('글\n\nx'), '끝에 줄바꿈이 없는 문서');
eq(atEnd('- a\n- b\n', 'x'), L('- a\n- b\n- x\n'), '목록은 같은 레벨');
eq(atEnd('- a\n  - b\n', 'x'), L('- a\n  - b\n  - x\n'), '하위 목록은 같은 레벨');
eq(atEnd('1. a\n2. b\n', 'x'), L('1. a\n2. b\n3. x\n'), '번호 목록');
eq(atEnd('> [!NOTE]\n> 글\n', 'x'), L('> [!NOTE]\n> 글\n>\n> x\n'), '박스글은 박스 안');
eq(atEnd('| a |\n|---|\n| 1 |\n', 'x'), L('| a |\n|---|\n| 1 |\n\nx\n'), '표 뒤는 문단');
eq(atEnd('```\ncode\n```\n', 'x'), L('```\ncode\n```\n\nx\n'), '코드 블록 뒤는 문단');
eq(atEnd('$$\nx^2\n$$\n', 'y'), L('$$\nx^2\n$$\n\ny\n'), '수식 뒤는 문단');
eq(atEnd('글\n\n---\n', 'x'), L('글\n\n---\n\nx\n'), '구분선 뒤');
eq(atEnd('---\ntitle: a\n---\n', 'x'), L('---\ntitle: a\n---\n\nx\n'), '머리 설정만 있는 문서');
eq(atEnd('글\n\n\n\n', 'x'), L('글\n\nx\n\n\n\n'), '끝의 빈 줄은 건너뛴다');

// 빈 새 줄의 레벨 (D106)
const shifted = (s, at, dirs, text) => {
  const l = L(s);
  let p = planNew(l, at, true);
  for (const d of dirs) p = shiftPlan(l, p, d) ?? p;
  return insertLine(l, p, text).lines;
};
eq(shifted('- a\n', 1, [-1], 'x'), L('- a\n\nx\n'), '맨 바깥 항목은 문단이 된다');
eq(shifted('- a\n', 1, [1], 'x'), L('- a\n  - x\n'), '윗 항목의 하위로');
eq(shifted('- a\n', 1, [1, 1], 'x'), L('- a\n  - x\n'), '더 들어갈 수 없으면 그대로');
eq(shifted('- a\n  - b\n', 2, [-1], 'x'), L('- a\n  - b\n- x\n'), '한 레벨 밖으로');
eq(shifted('- a\n  - b\n', 2, [-1, -1], 'x'), L('- a\n  - b\n\nx\n'), '두 번이면 목록이 끝난다');
eq(shifted('1. a\n', 1, [1], 'x'), L('1. a\n   1. x\n'), '번호 항목의 하위');
eq(shifted('1. a\n   1. b\n', 2, [-1], 'x'), L('1. a\n   1. b\n2. x\n'), '번호 목록 밖으로');
eq(shifted('- a\n- b\n', 1, [-1], 'x'), L('- a\n\nx\n\n- b\n'), '목록 가운데서 끝내면 앞뒤로 빈 줄');
eq(shifted('> 글\n', 1, [-1], 'x'), L('> 글\n\nx\n'), '인용 밖으로');
eq(shifted('> - a\n', 1, [-1], 'x'), L('> - a\n>\n> x\n'), '인용 안 목록을 끝낸다');
eq(shifted('> - a\n', 1, [-1, -1], 'x'), L('> - a\n\nx\n'), '인용 밖까지');
eq(shifted('글\n', 1, [-1], 'x'), L('글\n\nx\n'), '보통 문단은 그대로');

return { n, fails };
