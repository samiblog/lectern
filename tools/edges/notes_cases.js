// notesdata.js 의 표 점검 — rules_check.mjs 가 돌린다 (m: notesdata.js 모듈)
const { parseNotes, writeNotes, shownOrder, filterNotes, isTaskList, switchList, toggleTask, setTask, addTask, bodyLines, noteText, fromText, newId } = m;
const fails = [];
let n = 0;
const same = (name, got, want) => {
  n += 1;
  const a = JSON.stringify(got);
  const b = JSON.stringify(want);
  if (a !== b) fails.push(`${name}: ${a} ≠ ${b}`);
};
const note = (over = {}) => ({ id: 'n1', title: '', body: '', color: '', pinned: false, path: '', line: 0, end: 0, extra: {}, ...over });
const round = (notes) => parseNotes(writeNotes(notes));
const rangeText = ([a, b]) => (a === b ? `${a}행` : `${a}~${b}행`);

// 읽고 쓰기
same('빈 파일', parseNotes(''), []);
same('없는 값', parseNotes(null), []);
same('머리말만', parseNotes(writeNotes([])), []);
same('제목과 본문', round([note({ title: '제목', body: '본문' })])[0].title + '|' + round([note({ title: '제목', body: '본문' })])[0].body, '제목|본문');
same('본문만', round([note({ body: '글만' })])[0].body, '글만');
same('제목만', round([note({ title: '제목' })])[0].title, '제목');
same('아무것도 없는 메모는 쓰지 않음', round([note(), note({ id: 'n2', body: '글' })]).length, 1);
same('여러 메모의 차례', round([note({ body: 'a' }), note({ id: 'n2', body: 'b' }), note({ id: 'n3', body: 'c' })]).map((x) => x.body), ['a', 'b', 'c']);
same('색·고정·출처가 남음', (() => { const x = round([note({ body: 'a', color: 'green', pinned: true, path: 'docs/가 나.md', line: 12, end: 20 })])[0]; return [x.color, x.pinned, x.path, x.line, x.end]; })(), ['green', true, 'docs/가 나.md', 12, 20]);
same('모르는 색은 없앰', parseNotes('<!-- lectern-note id=a color=red -->\n글')[0].color, '');
same('모르는 값은 남김', writeNotes(parseNotes('<!-- lectern-note id=a future=1 -->\n글')).includes('future=1'), true);
same('값의 위험한 글자', round([note({ body: 'a', path: 'a b"c-->d.md' })])[0].path, 'a b"c-->d.md');
same('본문의 위험한 글자', round([note({ body: '<b>&amp; --> "x"' })])[0].body, '<b>&amp; --> "x"');
same('여러 줄 본문', round([note({ body: '첫 줄\n\n셋째 줄' })])[0].body, '첫 줄\n\n셋째 줄');
same('본문의 ## 은 둘째 줄부터 글', round([note({ title: 'T', body: '## 안쪽\n글' })])[0].body, '## 안쪽\n글');
same('두 번 돌려도 같음', writeNotes(round([note({ title: 'T', body: 'b', color: 'blue' })])), writeNotes([note({ title: 'T', body: 'b', color: 'blue' })]));
same('CRLF 파일', parseNotes('<!-- lectern-note id=a -->\r\n## 제목\r\n\r\n글\r\n')[0].body, '글');
same('BOM', parseNotes('﻿<!-- lectern-note id=a -->\n글')[0].id, 'a');
same('설명 줄 없는 글도 메모가 됨', parseNotes('사람이 직접 쓴 글\n둘째 줄')[0].body, '사람이 직접 쓴 글\n둘째 줄');
same('설명 줄 앞의 글도 잃지 않음', parseNotes('앞 글\n<!-- lectern-note id=a -->\n뒤 글').map((x) => x.body), ['앞 글', '뒤 글']);
same('id 가 없으면 만든다', parseNotes('글')[0].id, 'x0');
same('고쳐 쓴 파일의 깨진 값', parseNotes('<!-- lectern-note id=a path=%E0%A4%A -->\n글')[0].path, '%E0%A4%A');
same('id 가 겹치지 않음', new Set([newId(1), newId(1), newId(1)]).size, 3);

// 차례와 거르기
same('고정 먼저', shownOrder([note({ id: 'a' }), note({ id: 'b', pinned: true }), note({ id: 'c' })]).map((x) => x.id), ['b', 'a', 'c']);
same('거르기 없음', filterNotes([note({ id: 'a' })], '  ').length, 1);
same('낱말 모두', filterNotes([note({ id: 'a', title: '구리 가격', body: '2024' }), note({ id: 'b', title: '구리' })], '구리 2024').map((x) => x.id), ['a']);
same('대소문자 무시', filterNotes([note({ body: 'ABC' })], 'abc').length, 1);

// 할 일
same('할 일 읽기', bodyLines('- [ ] 가\n- [x] 나\n글').map((l) => [l.task, l.done, l.text]), [[true, false, '가'], [true, true, '나'], [false, false, '글']]);
same('대문자 X', bodyLines('- [X] 나')[0].done, true);
same('할 일 목록', isTaskList('- [ ] 가\n\n- [x] 나'), true);
same('글이 섞이면 아님', isTaskList('- [ ] 가\n글'), false);
same('빈 본문은 아님', isTaskList(''), false);
same('글 → 할 일', switchList('가\n\n나'), '- [ ] 가\n- [ ] 나');
same('목록 → 할 일', switchList('- 가\n* 나'), '- [ ] 가\n- [ ] 나');
same('할 일 → 글', switchList('- [ ] 가\n- [x] 나'), '가\n나');
same('끝내면 아래로', toggleTask('- [ ] 가\n- [ ] 나\n- [ ] 다', 0), '- [ ] 나\n- [ ] 다\n- [x] 가');
same('되살리면 끝낸 것 앞으로', toggleTask('- [ ] 나\n- [x] 가', 1), '- [ ] 나\n- [ ] 가');
same('글이 섞이면 자리 그대로', toggleTask('글\n- [ ] 가\n- [ ] 나', 0), '글\n- [x] 가\n- [ ] 나');
same('없는 할 일', toggleTask('글', 3), '글');
same('글 바꾸기', setTask('- [ ] 가\n- [x] 나', 1, '다'), '- [ ] 가\n- [x] 다');
same('비우면 뺌', setTask('- [ ] 가\n- [ ] 나', 0, '  '), '- [ ] 나');
same('더하기는 끝낸 것 앞에', addTask('- [ ] 가\n- [x] 나', '다'), '- [ ] 가\n- [ ] 다\n- [x] 나');
same('빈 메모에 더하기', addTask('', '가'), '- [ ] 가');

// 복사하는 글
same('출처', fromText(note({ path: 'a.md', line: 3, end: 5 }), rangeText), '@a.md 3~5행');
same('한 줄 출처', fromText(note({ path: 'a.md', line: 3 }), rangeText), '@a.md 3행');
same('줄 없는 출처', fromText(note({ path: 'a.md' }), rangeText), '@a.md');
same('출처 없음', fromText(note(), rangeText), '');
same('복사 글', noteText(note({ title: 'T', body: 'b', path: 'a.md', line: 1 }), rangeText), '## T\n\nb\n\n@a.md 1행');
same('본문만 복사', noteText(note({ body: 'b' }), rangeText), 'b');

return { fails, n };
