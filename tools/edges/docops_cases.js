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

// 넣기
const put = (s, at, block) => m.insertBlock(L(s), at, block).lines;
eq(put('글\n', 1, ['---']), L('글\n\n---\n'), '글 뒤에 빈 줄을 두고');
eq(put('가\n나\n', 1, ['---']), L('가\n\n---\n\n나\n'), '글 사이에 앞뒤 빈 줄');
eq(put('가\n\n나\n', 2, ['---']), L('가\n\n---\n\n나\n'), '빈 줄이 있으면 더하지 않는다');
eq(m.insertBlock(L('글\n'), 1, ['---']).line, 3, '블록의 첫 줄');
eq(m.blockEnd(L('가\n나\n\n다\n'), 1), 2, '블록의 끝');
eq(m.nextCaption(L('표 1. a\n\n**표 3. b**\n\n〈표 2〉 c\n'), '표'), 4, '표 번호');
eq(m.nextCaption(L('글\n'), '그림'), 1, '첫 번호');

// 표
const T = '| a | b |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |\n';
const tb = (f, ...a) => {
  const r = f(L(T), ...a);
  return r.error ? r : r.lines;
};
eq(m.makeTable(2, 1), ['|  |  |', '| --- | --- |', '|  |  |'], '빈 표');
eq(tb(m.addRow, 3, true), L('| a | b |\n| --- | --- |\n| 1 | 2 |\n|  |  |\n| 3 | 4 |\n'), '아래에 행');
eq(tb(m.addRow, 3, false), L('| a | b |\n| --- | --- |\n|  |  |\n| 1 | 2 |\n| 3 | 4 |\n'), '위에 행');
eq(tb(m.addRow, 1, true), L('| a | b |\n| --- | --- |\n|  |  |\n| 1 | 2 |\n| 3 | 4 |\n'), '머리행 아래는 첫 본문 행');
eq(tb(m.addRow, 1, false), L('| a | b |\n| --- | --- |\n|  |  |\n| 1 | 2 |\n| 3 | 4 |\n'), '머리행 위에는 넣지 않는다');
eq(tb(m.addRow, 4, true), L('| a | b |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |\n|  |  |\n'), '끝 행 아래');
eq(m.addRow(L(T), 4, true).line, 5, '새 행의 줄');
eq(m.addRow(L('글\n'), 1, true), { error: 'not-table' }, '표가 아니다');
eq(tb(m.addColumn, 3, 0, true), L('| a |  | b |\n| --- | --- | --- |\n| 1 |  | 2 |\n| 3 |  | 4 |\n'), '오른쪽에 열');
eq(tb(m.addColumn, 3, 0, false), L('|  | a | b |\n| --- | --- | --- |\n|  | 1 | 2 |\n|  | 3 | 4 |\n'), '왼쪽에 열');
eq(tb(m.removeColumn, 3, 0), L('| b |\n| --- |\n| 2 |\n| 4 |\n'), '열 지우기');
eq(m.removeColumn(L('| a |\n| --- |\n| 1 |\n'), 3, 0), { error: 'last-column' }, '하나뿐인 열');
eq(tb(m.moveColumn, 3, 0, 1), L('| b | a |\n| --- | --- |\n| 2 | 1 |\n| 4 | 3 |\n'), '열 옮기기');
eq(tb(m.moveColumn, 3, 1, 1), { error: 'edge' }, '끝 열');
eq(tb(m.alignColumn, 3, 1, 'right'), L('| a | b |\n| --- | ---: |\n| 1 | 2 |\n| 3 | 4 |\n'), '오른쪽 정렬');
eq(m.tableSpan(L(`글\n\n${T}`), 5), [3, 6], '표의 범위');
eq(m.addRow(L('| a \\| x | b |\n| --- | --- |\n| 1 | 2 |\n'), 3, true).lines[3], '|  |  |', '칸 글의 | 는 칸이 아니다');
eq(m.addColumn(L('> | a |\n> | --- |\n> | 1 |\n'), 3, 0, true).lines, L('> | a |  |\n> | --- | --- |\n> | 1 |  |\n'), '박스 안의 표');
eq(m.rowsFromTsv('a\tb\n1\t2\n'), [['a', 'b'], ['1', '2']], '엑셀 범위');
eq(m.rowsFromTsv('a\tb\n1\n'), null, '칸 수가 다르면 표가 아니다');
eq(m.rowsFromTsv('그냥 글\n둘째 줄\n'), null, '탭이 없으면 표가 아니다');
eq(m.tableFromRows([['a', 'b|c'], ['1', '2']]), ['| a | b\\|c |', '| --- | --- |', '| 1 | 2 |'], '값으로 표를');

// 박스글
const B = '앞\n\n> [!NOTE]\n> 가\n>\n> 나\n\n뒤\n';
eq(m.boxAt(L(B), 4), { a: 3, b: 6, kind: 'NOTE' }, '박스글 범위');
eq(m.boxAt(L('> 그냥 인용\n'), 1), null, '보통 인용');
eq(m.boxAt(L(B), 1), null, '박스 밖');
eq(m.setBox(L(B), 4, 'WARNING').lines, L('앞\n\n> [!WARNING]\n> 가\n>\n> 나\n\n뒤\n'), '종류 바꾸기');
eq(m.unwrapBox(L(B), 4).lines, L('앞\n\n가\n\n나\n\n뒤\n'), '풀기');
eq(m.wrapBox(L('앞\n\n글\n\n뒤\n'), 3, 3, 'TIP').lines, L('앞\n\n> [!TIP]\n> 글\n\n뒤\n'), '문단을 박스글로');
eq(m.wrapBox(L('가\n\n나\n'), 1, 3, 'NOTE').lines, L('> [!NOTE]\n> 가\n>\n> 나\n'), '여러 문단을 박스글로');
eq(m.wrapBox(L('- 항목\n'), 1, 1, 'NOTE').lines, L('> [!NOTE]\n> 항목\n'), '항목의 표시를 뗀다');

// 주
eq(m.nextNote(L('글[^1]\n\n[^1]: 내용\n')), '2', '다음 주 이름');
eq(m.nextNote(L('글\n')), '1', '첫 주');
eq(m.nextNote(L('글[^2]\n\n[^2]: 내용\n')), '1', '빈 번호부터');
eq(m.addNote(L('글입니다.\n'), 1, 2, '내용').lines, L('글입[^1]니다.\n\n[^1]: 내용\n'), '주를 단다');
eq(m.addNote(L('글[^1]\n\n[^1]: 앞\n'), 1, 1, '뒤').lines, L('글[^2][^1]\n\n[^1]: 앞\n[^2]: 뒤\n'), '주 뒤에 잇는다');
eq(m.addNote(L('글\n\n\n'), 1, 1, '내용').lines, L('글[^1]\n\n[^1]: 내용\n\n\n'), '끝의 빈 줄 앞에');
eq(m.noteAt('글[^3]뒤', 2), '3', '주 표시 위');
eq(m.noteAt('글[^3]뒤', 5), '3', '주 표시 끝');
eq(m.noteAt('글[^3]뒤', 6), '', '주 밖');
eq(m.noteText(L('[^3]: 내용\n'), '3'), { n: 1, text: '내용' }, '주 내용');
eq(m.setNote(L('[^3]: 내용\n'), '3', '새 글'), L('[^3]: 새 글\n'), '주 고치기');
eq(m.droppedNotes(L('글[^1]\n\n[^1]: 내용\n'), L('글\n\n[^1]: 내용\n')), ['1'], '표시를 지운 주');
eq(m.droppedNotes(L('글[^1] 또[^1]\n\n[^1]: 내용\n'), L('글 또[^1]\n\n[^1]: 내용\n')), [], '다른 곳에 남은 주');
eq(m.removeNotes(L('글\n\n[^1]: 내용\n'), ['1']), L('글\n'), '내용 줄을 지운다');

// 첨부·부록
eq(m.addAttachment(L('글\n'), '[a](a.xlsx)', '붙임').lines, L('글\n\n## 붙임\n\n1. [a](a.xlsx)\n'), '붙임 절을 만든다');
eq(m.addAttachment(L('글\n\n## 붙임\n\n1. [a](a.xlsx)\n'), '[b](b.pdf)', '붙임').lines, L('글\n\n## 붙임\n\n1. [a](a.xlsx)\n2. [b](b.pdf)\n'), '번호를 잇는다');
eq(m.addAttachment(L('## 붙임\n\n1. a\n\n## 뒤\n'), 'b', '붙임').lines, L('## 붙임\n\n1. a\n2. b\n\n## 뒤\n'), '절 끝에');
eq(m.addAttachment(L('## 붙임\n'), 'a', '붙임').lines, L('## 붙임\n\n1. a\n'), '빈 절');
eq(m.nextAppendix(L('글\n')), 'A', '첫 부록');
eq(m.nextAppendix(L('## 부록 A. 자료\n\n## 부록 B. 표\n')), 'C', '다음 부록');

// 붙여 넣기
eq(m.pasteAfter(L('가\n나\n'), 1, ['x', '', 'y']).lines, L('가\nx\n\ny\n나\n'), '줄 뒤에 넣는다');
eq(m.pasteAfter(L('- 가\n'), 1, ['x', '', '- y'], '- ').lines, L('- 가\n- x\n- y\n'), '목록은 항목으로');

return { n, fails };
