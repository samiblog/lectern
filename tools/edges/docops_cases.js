// docops.js 의 계산 점검 (rules_check.mjs 가 돌린다 — m: docops.js, 끝에서 {n, fails} 를 돌려준다).
const { setKind, shiftHeadings, moveSection, deleteSection, sectionEnd, bareText, headLevel } = m;
let n = 0;
const fails = [];
const L = (s) => s.split('\n');
const eq = (got, want, name) => {
  n += 1;
  const show = (x) => (Array.isArray(x) ? x.join('\n') : JSON.stringify(x));
  if (show(got) !== show(want)) fails.push(`${name}: ${show(got)} ≠ ${show(want)}`);
};
const kind = (s, a, b, k) => {
  const r = setKind(L(s), a, b, k);
  return r.error ? r : r.lines;
};

// 표시 떼기
eq(bareText('## 제목 ##'), '제목', '제목');
eq(bareText('- [ ] 할 일'), '할 일', '할 일');
eq(bareText('> - 인용 항목'), '인용 항목', '인용 안 목록');
eq(bareText('  1. 번호'), '번호', '들여쓴 번호');
eq(headLevel('### 작은 절'), 3, '수준');
eq(headLevel('글'), 0, '제목이 아님');

// 줄 종류
eq(kind('글\n', 1, 1, 'h2'), L('## 글\n'), '문단을 제목으로');
eq(kind('## 글\n', 1, 1, 'h3'), L('### 글\n'), '제목 수준');
eq(kind('## 글\n', 1, 1, 'para'), L('글\n'), '제목을 문단으로');
eq(kind('글\n', 1, 1, 'bullet'), L('- 글\n'), '문단을 목록으로');
eq(kind('글\n', 1, 1, 'number'), L('1. 글\n'), '문단을 번호 목록으로');
eq(kind('글\n', 1, 1, 'task'), L('- [ ] 글\n'), '문단을 할 일로');
eq(kind('글\n', 1, 1, 'quote'), L('> 글\n'), '문단을 인용으로');
eq(kind('> 글\n', 1, 1, 'para'), L('글\n'), '인용을 문단으로');
eq(kind('- 글\n', 1, 1, 'para'), L('글\n'), '항목을 문단으로');
eq(kind('- [x] 글\n', 1, 1, 'bullet'), L('- 글\n'), '할 일을 항목으로');
eq(kind('- 글\n', 1, 1, 'number'), L('1. 글\n'), '항목을 번호로');
eq(kind('가\n\n나\n\n다\n', 1, 5, 'bullet'), L('- 가\n- 나\n- 다\n'), '문단 여러 개를 목록으로');
eq(kind('가\n나\n', 1, 2, 'number'), L('1. 가\n2. 나\n'), '이어 쓴 줄을 번호로');
eq(kind('- 가\n- 나\n', 1, 2, 'para'), L('가\n\n나\n'), '목록을 문단들로');
eq(kind('가\n\n나\n', 1, 3, 'quote'), L('> 가\n>\n> 나\n'), '문단 여러 개를 인용으로');
eq(kind('- a\n- b\n- c\n', 2, 2, 'h2'), L('- a\n\n## b\n\n- c\n'), '항목을 제목으로 하면 앞뒤에 빈 줄');
eq(kind('앞\n글\n뒤\n', 2, 2, 'h2'), L('앞\n\n## 글\n\n뒤\n'), '이어 쓴 줄을 제목으로');
eq(kind('- a\n\n글\n', 3, 3, 'bullet'), L('- a\n\n- 글\n'), '빈 줄 건너편 목록은 그대로 둔다');
eq(kind('- a\n글\n', 2, 2, 'bullet'), L('- a\n- 글\n'), '이어지는 항목');
eq(kind('1. a\n글\n', 2, 2, 'number'), L('1. a\n2. 글\n'), '이어지는 번호');
eq(kind('> - a\n', 1, 1, 'number'), L('> 1. a\n'), '인용 안의 목록');
eq(setKind(L('## Ⅰ. 첫째\n'), 1, 1, 'para', { bare: (s) => s.replace(/^Ⅰ\. /, '') }).lines, L('첫째\n'), '제목의 번호를 뗀다');
eq(kind('```\ncode\n```\n', 2, 2, 'h2'), { error: 'kind' }, '코드 블록은 바꾸지 않는다');
eq(kind('| a |\n|---|\n| 1 |\n', 3, 3, 'h2'), { error: 'table-kind' }, '표는 바꾸지 않는다');
eq(kind('\n\n', 1, 2, 'h2'), { error: 'kind' }, '빈 줄뿐');
eq(setKind(L('앞\n\n글\n'), 3, 3, 'h2').line, 3, '바뀐 줄 번호');
eq(setKind(L('앞\n글\n'), 2, 2, 'h2').line, 3, '빈 줄이 들어가면 밀린다');

// 절
const DOC = '# 글\n\n## 첫째\n\n첫 내용\n\n### 세부\n\n세부 내용\n\n## 둘째\n\n둘 내용\n\n## 셋째\n\n셋 내용\n';
eq(sectionEnd(L(DOC), 3), 9, '절의 끝은 하위 절까지');
eq(sectionEnd(L(DOC), 7), 9, '하위 절의 끝');
eq(sectionEnd(L(DOC), 15), 17, '마지막 절의 끝');
eq(sectionEnd(L('## a\n\n```\n## 코드 속\n```\n\n## b\n'), 1), 5, '코드 속 제목은 절이 아니다');

// 수준
const shift = (s, at, d) => {
  const r = shiftHeadings(L(s), at, d);
  return r.error ? r : r.lines;
};
eq(shift('## a\n\n### b\n\n## c\n', 1, 1), L('### a\n\n#### b\n\n## c\n'), '하위 절까지 함께 안으로');
eq(shift('### a\n\n#### b\n', 1, -1), L('## a\n\n### b\n'), '하위 절까지 함께 밖으로');
eq(shift('# a\n', 1, -1), { error: 'edge' }, '1 수준 밖으로는 못 간다');
eq(shift('## a\n\n###### b\n', 1, 1), { error: 'edge' }, '하위가 6 이면 못 들어간다');
eq(shift('글\n', 1, 1), { error: 'not-heading' }, '제목이 아니다');
eq(shift('## a\n\n```\n## 코드\n```\n', 1, 1), L('### a\n\n```\n## 코드\n```\n'), '코드 속은 그대로');

// 절 옮기기
const move = (s, at, d) => {
  const r = moveSection(L(s), at, d);
  return r.error ? r : r.lines;
};
eq(move(DOC, 11, -1), L('# 글\n\n## 둘째\n\n둘 내용\n\n## 첫째\n\n첫 내용\n\n### 세부\n\n세부 내용\n\n## 셋째\n\n셋 내용\n'), '앞 절과 바꾼다 — 본문과 하위 절까지');
eq(move(DOC, 3, 1), L('# 글\n\n## 둘째\n\n둘 내용\n\n## 첫째\n\n첫 내용\n\n### 세부\n\n세부 내용\n\n## 셋째\n\n셋 내용\n'), '뒤 절과 바꾼다');
eq(move(DOC, 15, -1), L('# 글\n\n## 첫째\n\n첫 내용\n\n### 세부\n\n세부 내용\n\n## 셋째\n\n셋 내용\n\n## 둘째\n\n둘 내용\n'), '끝 절을 올려도 끝의 줄바꿈이 남는다');
eq(move(DOC, 11, 1), L('# 글\n\n## 첫째\n\n첫 내용\n\n### 세부\n\n세부 내용\n\n## 셋째\n\n셋 내용\n\n## 둘째\n\n둘 내용\n'), '끝 절과 바꾼다');
eq(move(DOC, 3, -1), { error: 'edge' }, '첫 절은 더 올리지 못한다');
eq(move(DOC, 15, 1), { error: 'edge' }, '끝 절은 더 내리지 못한다');
eq(move(DOC, 7, 1), { error: 'edge' }, '다음 절이 위 수준이면 못 넘는다');
eq(move(DOC, 5, 1), { error: 'not-heading' }, '본문');
eq(moveSection(L(DOC), 11, -1).line, 3, '옮긴 제목의 줄');
eq(moveSection(L(DOC), 3, 1).line, 7, '내린 제목의 줄');
eq(move('---\nmarp: true\n---\n\n## a\n\n## b\n', 7, -1), { error: 'edge' }, 'Lectern 슬라이드는 장으로 옮긴다');

// 절 지우기
const del = (s, at) => {
  const r = deleteSection(L(s), at);
  return r.error ? r : r.lines;
};
eq(del(DOC, 3), L('# 글\n\n## 둘째\n\n둘 내용\n\n## 셋째\n\n셋 내용\n'), '절을 지운다 — 하위 절까지');
eq(del(DOC, 15), L('# 글\n\n## 첫째\n\n첫 내용\n\n### 세부\n\n세부 내용\n\n## 둘째\n\n둘 내용\n'), '끝 절');
eq(del(DOC, 5), { error: 'not-heading' }, '본문');

return { n, fails };
