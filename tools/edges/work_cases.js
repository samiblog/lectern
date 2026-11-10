// workdata.js 의 표 점검 — rules_check.mjs 가 돌린다 (m: workdata.js 모듈)
const { readWork, dueDay, daysBetween, addDays, attention, groupOf, dueTodos, dayEvents, eventsToRemind, pastLogTime, quietToday, nextWeekday,
  eventLine, insertEvent, fillTemplate, isoDay } = m;
const fails = [];
let n = 0;
const same = (name, got, want) => {
  n += 1;
  const a = JSON.stringify(got);
  const b = JSON.stringify(want);
  if (a !== b) fails.push(`${name}: ${a} ≠ ${b}`);
};
const TODAY = '2026-11-10';
const CARD = [
  '---',
  'status: 진행',
  'priority: 상',
  'due: 2026-11-12',
  '---',
  '',
  '# 시장분석 보고서',
  '',
  '국내 시장 현황.',
  '',
  '## 할 일',
  '',
  '- [x] 자료 수집 (11/7)',
  '- [ ] 초안 3장 작성 (11/14)',
  '- [ ] 기한 없는 일',
  '- [ ] 지난 일 (11/5)',
  '',
  '## 일정',
  '',
  '- 2026-11-10 14:00-15:00 팀장 1차 보고',
  '- 2026-11-10 종일 워크숍',
  '- 2026-11-11 10:00 자문 회의',
  '',
  '## 결정',
  '',
  '- 2026-11-01 범위를 국내로',
  '',
  '```',
  '- 2026-11-10 09:00 코드 블록 안은 일정이 아님',
  '- [ ] 코드 블록 안은 할 일이 아님',
  '```',
  '',
].join('\n');

// 읽기
const card = readWork(CARD, TODAY);
same('상태', [card.status, card.statusText], ['active', '진행']);
same('우선·마감', [card.priority, card.due], ['상', '2026-11-12']);
same('제목은 첫 # 줄', card.title, '시장분석 보고서');
same('할 일 수', card.todos.length, 4);
same('할 일의 기한과 글', card.todos.map((x) => [x.text, x.done, x.due, x.line]), [
  ['자료 수집', true, '2026-11-07', 13], ['초안 3장 작성', false, '2026-11-14', 14], ['기한 없는 일', false, null, 15], ['지난 일', false, '2026-11-05', 16]]);
same('일정', card.events.map((e) => [e.date, e.time, e.end, e.allDay, e.text, e.line]), [
  ['2026-11-10', '14:00', '15:00', false, '팀장 1차 보고', 20], ['2026-11-10', null, null, true, '워크숍', 21],
  ['2026-11-11', '10:00', null, false, '자문 회의', 22], ['2026-11-01', null, null, false, '범위를 국내로', 26]]);
same('머리 설정 title 이 먼저', readWork('---\ntitle: 이름\n---\n# 제목\n', TODAY).title, '이름');
same('머리 설정이 없어도', readWork('# 그냥 제목\n- [ ] 일 (2026-11-20)\n', TODAY).todos[0].due, '2026-11-20');
same('닫히지 않은 머리 설정은 머리 설정이 아님', readWork('---\nstatus: 진행\n# 제목\n', TODAY).status, null);
same('영어 상태', ['active', 'at-risk', 'Done', 'on-hold'].map((s) => readWork(`---\nstatus: ${s}\n---\n`, TODAY).status), ['active', 'at-risk', 'done', 'on-hold']);
same('한국어 상태 모두', ['예정', '진행', '지연위험', '막힘', '보류', '완료', '중단'].map((s) => readWork(`---\nstatus: ${s}\n---\n`, TODAY).status),
  ['planned', 'active', 'at-risk', 'blocked', 'on-hold', 'done', 'dropped']);
same('모르는 상태는 글 그대로', [readWork('---\nstatus: 검토중\n---\n', TODAY).status, readWork('---\nstatus: 검토중\n---\n', TODAY).statusText], [null, '검토중']);
same('따옴표 값', readWork('---\ndue: "2026-12-01"\n---\n', TODAY).due, '2026-12-01');
same('빈 마감', readWork('---\ndue:\n---\n', TODAY).due, null);
same('틀린 날짜는 마감 아님', [readWork('---\ndue: 2026-02-30\n---\n', TODAY).due, readWork('---\ndue: 2026-02-30\n---\n', TODAY).dueText], [null, '2026-02-30']);
same('CRLF', readWork(CARD.replace(/\n/g, '\r\n'), TODAY).todos.length, 4);
same('틀린 시각은 시각 없는 일정으로 남음', readWork('- 2026-11-10 25:00 이상한 시각\n', TODAY).events.map((e) => [e.time, e.text]), [[null, '25:00 이상한 시각']]);
same('한 자리 시', readWork('- 2026-11-10 9:30 아침 회의\n', TODAY).events[0].time, '09:30');
same('빈 글', readWork('', TODAY).todos, []);
same('null', readWork(null, TODAY).title, '');

// 날짜
same('M/D 는 가장 가까운 해 (지난 기한이 내년으로 가지 않음)', dueDay('11/5', TODAY), '2026-11-05');
same('연말에 쓴 1월 기한은 다음 해', dueDay('1/5', '2026-12-20'), '2027-01-05');
same('연초에 쓴 12월 기한은 지난해', dueDay('12/28', '2027-01-03'), '2026-12-28');
same('없는 날', dueDay('2/30', TODAY), null);
same('날 수', [daysBetween('2026-11-10', '2026-11-12'), daysBetween('2026-11-10', '2026-11-05'), daysBetween('2026-12-31', '2027-01-01')], [2, -5, 1]);
same('날 더하기 (달 넘김)', addDays('2026-11-30', 1), '2026-12-01');
same('다가오는 요일 (오늘이 그 요일이면 다음 주)', [nextWeekday('2026-11-10', 2), nextWeekday('2026-11-10', 5), nextWeekday('2026-11-10', 1)], ['2026-11-17', '2026-11-13', '2026-11-16']);

// 주의할 것
const now = Date.UTC(2026, 10, 10) / 1000;
const sec = (iso) => new Date(`${iso}T12:00:00`).getTime() / 1000;
same('마감 D-2 는 주의', attention(card, now, TODAY), ['due-soon']);
same('마감 지남', attention(readWork('---\nstatus: 진행\ndue: 2026-11-09\n---\n', TODAY), now, TODAY), ['overdue']);
same('막힘', attention(readWork('---\nstatus: 막힘\n---\n', TODAY), now, TODAY), ['blocked']);
same('오래 안 바뀐 진행', attention(readWork('---\nstatus: 진행\n---\n', TODAY), sec('2026-10-20'), TODAY), ['stale']);
same('14일은 아직 아님', attention(readWork('---\nstatus: 진행\n---\n', TODAY), sec('2026-10-27'), TODAY), []);
same('완료는 마감이 지나도 없음', attention(readWork('---\nstatus: 완료\ndue: 2026-01-01\n---\n', TODAY), now, TODAY), []);
same('무리', [groupOf({ status: 'done' }, []), groupOf({ status: 'active' }, ['due-soon']), groupOf({ status: 'on-hold' }, []), groupOf({ status: null }, [])],
  ['closed', 'attention', 'hold', 'open']);

// 기한 있는 할 일·오늘 일정
same('기한 있는 할 일 (안 한 것, 7일 안, 빠른 차례)', dueTodos([card], TODAY).map((x) => [x.todo.text, x.left]), [['지난 일', -5], ['초안 3장 작성', 4]]);
same('끝난 과제의 할 일은 없음', dueTodos([readWork(`---\nstatus: 완료\n---\n- [ ] 일 (11/9)\n`, TODAY)], TODAY).length, 0);
same('오늘 일정 (종일 먼저)', dayEvents([card], TODAY).map((x) => x.event.text), ['워크숍', '팀장 1차 보고']);

// 알림
const at = (hm) => new Date(2026, 10, 10, Number(hm.slice(0, 2)), Number(hm.slice(3)));
same('10분 전', eventsToRemind([card], at('13:50')).map((x) => x.event.text), ['팀장 1차 보고']);
same('11분 전은 아직', eventsToRemind([card], at('13:49')).length, 0);
same('시작한 뒤는 알리지 않음', eventsToRemind([card], at('14:00')).length, 0);
same('알림 열쇠', eventsToRemind([card], at('13:55'))[0].key, '2026-11-10 14:00 팀장 1차 보고');
same('기록 알림 시각', [pastLogTime(at('17:29')), pastLogTime(at('17:30'))], [false, true]);
same('오늘 안 바뀐 진행 과제', quietToday([{ card, mtime: sec('2026-11-09') }, { card, mtime: sec('2026-11-10') },
  { card: readWork('---\nstatus: 보류\n---\n', TODAY), mtime: 0 }], TODAY).length, 1);
same('isoDay', isoDay(new Date(2026, 0, 5)), '2026-01-05');

// 일정 줄
same('시각과 끝', eventLine({ date: '2026-11-14', time: '10:00', end: '11:00', text: ' 팀  회의 ' }), '- 2026-11-14 10:00-11:00 팀 회의');
same('종일', eventLine({ date: '2026-11-14', allDay: true, text: '워크숍' }), '- 2026-11-14 종일 워크숍');
same('영어 종일', eventLine({ date: '2026-11-14', allDay: true, text: 'Workshop' }, 'all-day'), '- 2026-11-14 all-day Workshop');
same('시각 없음', eventLine({ date: '2026-11-14', text: '마감' }), '- 2026-11-14 마감');
same('한 자리 시를 맞춤', eventLine({ date: '2026-11-14', time: '9:05', text: 'x' }), '- 2026-11-14 09:05 x');
same('넣은 줄을 다시 읽음', readWork(eventLine({ date: '2026-11-14', time: '10:00', end: '11:00', text: '팀 회의' }), TODAY).events[0].end, '11:00');
same('줄바꿈은 빈칸으로', eventLine({ date: '2026-11-14', text: '가\n나' }), '- 2026-11-14 가 나');

// 일정 넣기
const L = '- 2026-11-14 10:00 팀 회의';
{
  const r = insertEvent(CARD, L);
  same('일정 절의 끝에', r.text.split('\n').slice(19, 24), ['- 2026-11-10 14:00-15:00 팀장 1차 보고', '- 2026-11-10 종일 워크숍', '- 2026-11-11 10:00 자문 회의', L, '']);
  same('넣은 줄 번호', [r.line, r.text.split('\n')[r.line - 1]], [23, L]);
  same('다른 곳은 그대로', r.text.replace(`${L}\n`, ''), CARD);
}
{
  const src = '# 공통 업무\n\n## 일정\n\n## 할 일\n';
  const r = insertEvent(src, L);
  same('빈 절', r.text, `# 공통 업무\n\n## 일정\n\n${L}\n\n## 할 일\n`);
  same('빈 절의 줄 번호', r.line, 5);
}
{
  const r = insertEvent('# 제목\n\n본문\n', L);
  same('절이 없으면 끝에 만듦', r.text, `# 제목\n\n본문\n\n## 일정\n\n${L}\n`);
  same('만든 절의 줄 번호', r.text.split('\n')[r.line - 1], L);
}
same('영어 절 이름', insertEvent('# T\n\n## Schedule\n\n- 2026-11-01 old\n', L).text, `# T\n\n## Schedule\n\n- 2026-11-01 old\n${L}\n`);
same('없으면 영어로 만듦', insertEvent('# T\n', L, 'Schedule').text, `# T\n\n## Schedule\n\n${L}\n`);
same('빈 파일', insertEvent('', L).text, `## 일정\n\n${L}\n`);
same('절 끝의 문단 뒤는 빈 줄을 두고', insertEvent('## 일정\n\n설명 문단\n', L).text, `## 일정\n\n설명 문단\n\n${L}\n`);
same('### 하위 제목은 절 안', insertEvent('## 일정\n\n### 11월\n\n- 2026-11-01 a\n\n## 기록\n', L).text, `## 일정\n\n### 11월\n\n- 2026-11-01 a\n${L}\n\n## 기록\n`);
same('코드 블록 안의 ## 일정 은 절이 아님', insertEvent('```\n## 일정\n```\n', L).text, `\`\`\`\n## 일정\n\`\`\`\n\n## 일정\n\n${L}\n`);
same('머리 설정 안은 보지 않음', insertEvent('---\nstatus: 진행\n---\n# T\n', L).text, `---\nstatus: 진행\n---\n# T\n\n## 일정\n\n${L}\n`);
same('끝 줄바꿈이 없던 파일', insertEvent('## 일정\n\n- 2026-11-01 a', L).text, `## 일정\n\n- 2026-11-01 a\n${L}`);

// 틀 채우기
same('틀', fillTemplate('---\nstatus: 예정\npriority: {{priority}}\ndue: {{due}}\n---\n\n# {{title}}\n', { title: '새 과제\n이름', due: '2026-12-01', priority: '중' }),
  '---\nstatus: 예정\npriority: 중\ndue: 2026-12-01\n---\n\n# 새 과제 이름\n');
same('빈 값', fillTemplate('due: {{due}}', {}), 'due: ');

// ---- 사용자 시나리오: 손으로 쓰다 낸 오타 (A) — 줄은 버리지 않고, 고칠 곳은 '확인할 줄'로 -----------------------------
const base = (front, body = '') => `---\n${front}\n---\n\n# 시장분석\n\n${body}`;
const probs = (text) => readWork(text, TODAY).problems.map((p) => [p.kind, p.line, ...(p.hint ? [p.hint] : [])]);
same('A1 상태 오타: 값은 글 그대로, 확인할 줄', [readWork(base('status: 진핸'), TODAY).status, readWork(base('status: 진핸'), TODAY).statusText, probs(base('status: 진핸'))],
  [null, '진핸', [['status', 2]]]);
same('A2 마감 오타 (없는 날): 마감 없음, 확인할 줄', [readWork(base('due: 2026-12-32'), TODAY).due, probs(base('due: 2026-12-32'))], [null, [['due', 2]]]);
same('A3 마감을 점·빗금·한 자리로 써도 읽음', ['due: 2026.12.15', 'due: 2026/12/5', 'due: 2026-12-5', 'due: 12/15'].map((x) => readWork(base(x), TODAY).due),
  ['2026-12-15', '2026-12-05', '2026-12-05', '2026-12-15']);
same('A3 그때 확인할 줄은 없음', probs(base('due: 2026.12.15')), []);
same('A4 키의 대문자·콜론 앞 빈칸·전각 콜론·값 끝 빈칸', ['Status: 진행', 'status : 진행', 'status： 진행', 'status: 진행  ', 'STATUS: Active'].map((x) => readWork(base(x), TODAY).status),
  ['active', 'active', 'active', 'active', 'active']);
same('A5 키 이름 오타는 맞는 키를 알려 줌', [probs(base('stauts: 진행')), probs(base('prority: 상')), probs(base('duee: 2026-12-01'))],
  [[['key', 2, 'status']], [['key', 2, 'priority']], [['key', 2, 'due']]]);
same('A5 다른 키는 오타로 보지 않음', probs(base('requester: 팀장\ntags: [보고서]\ntitle: 이름\ndate: 2026-11-01\nowner: 나')), []);
same('A5 맞는 키가 따로 있으면 오타로 보지 않음', probs(base('status: 진행\nstatu: 메모')), []);
same('A6 할 일 기한 오타 (없는 날): 할 일은 남고 기한 없음', (() => { const c = readWork('- [ ] 초안 (11/31)\n', TODAY); return [c.todos.length, c.todos[0].due, c.todos[0].text, probs('- [ ] 초안 (11/31)\n')]; })(),
  [1, null, '초안 (11/31)', [['todo-due', 1]]]);
same('A7 할 일 기한의 닫는 괄호 빠짐', [readWork('- [ ] 초안 (11/14\n', TODAY).todos[0].due, probs('- [ ] 초안 (11/14\n')], [null, [['todo-due', 1]]]);
same('A7 기한을 점으로 써도 읽음', readWork('- [ ] 초안 (2026.11.14)\n', TODAY).todos[0].due, '2026-11-14');
same('A7 (1.2) 같은 글은 기한으로 읽지 않음', [readWork('- [ ] 버전 정리 (1.2)\n', TODAY).todos[0].due, probs('- [ ] 버전 정리 (1.2)\n')], [null, []]);
same('A8 체크 칸 오타는 할 일로 세지 않고 확인할 줄',
  ['- [] 할 일', '-[ ] 할 일', '- [v] 할 일', '- [ ]할 일', '[ ] 할 일'].map((x) => [readWork(`${x}\n`, TODAY).todos.length, probs(`${x}\n`).map((p) => p[0])]),
  [[0, ['todo-box']], [0, ['todo-box']], [0, ['todo-box']], [0, ['todo-box']], [0, ['todo-box']]]);
same('A8 링크 목록은 체크 칸 오타가 아님', probs('- [링크](a.md)\n- [x] 끝난 일\n* [ ] 별표 할 일\n'), []);
same('A9 없는 시각 (25:00): 시각 없는 일정으로 남고 확인할 줄', [readWork('- 2026-11-10 25:00 회의\n', TODAY).events.length, probs('- 2026-11-10 25:00 회의\n')], [1, [['event-time', 1]]]);
same('A9 끝 시각의 콜론 빠짐 (14:00-1500): 확인할 줄', [readWork('- 2026-11-10 14:00-1500 회의\n', TODAY).events[0].time, probs('- 2026-11-10 14:00-1500 회의\n')], [null, [['event-time', 1]]]);
same('A10 일정 날짜를 점·한 자리로 써도 읽음', ['- 2026.11.12 14:00 회의', '- 2026-11-5 회의', '- 2026/11/12 종일 행사'].map((x) => readWork(`${x}\n`, TODAY).events.map((e) => [e.date, e.time, e.allDay])),
  [[['2026-11-12', '14:00', false]], [['2026-11-05', null, false]], [['2026-11-12', null, true]]]);
same('A11 없는 날의 일정: 확인할 줄', [readWork('- 2026-11-31 회의\n', TODAY).events.length, probs('- 2026-11-31 회의\n')], [0, [['event-date', 1]]]);
same('A12 내용 없는 일정: 확인할 줄', [probs('- 2026-11-12\n'), probs('- 2026-11-12 14:00\n')], [[['event-text', 1]], [['event-text', 1]]]);
same('A13 콜론 없는 시각은 내용으로', readWork('- 2026-11-12 1400 회의\n', TODAY).events[0].text, '1400 회의');
same('A14 코드 블록 안의 오타는 보지 않음', probs('```\n- [] x\n- 2026-11-31 y\n```\n'), []);

// ---- 사용자 시나리오: 일부를 지웠을 때 (B) ------------------------------------------------------------
{
  const cut = '---\nstatus: 진행\ndue: 2026-12-15\n\n# 시장분석\n\n- [ ] 초안 (11/14)\n';
  const c = readWork(cut, TODAY);
  same('B1 닫는 --- 를 지움: 상태·마감 없음, 제목·할 일은 그대로, 확인할 줄', [c.status, c.due, c.title, c.todos.length, probs(cut)], [null, null, '시장분석', 1, [['front', 1]]]);
}
same('B2 머리 설정을 통째로 지움: 값 없음, 탈 없음', (() => { const c = readWork('# 시장분석\n\n- [ ] 초안\n', TODAY); return [c.status, c.title, c.todos.length, c.problems.length]; })(), [null, '시장분석', 1, 0]);
same('B3 ## 일정 제목을 지워도 일정 줄은 읽음', readWork('# T\n\n- 2026-11-12 14:00 회의\n', TODAY).events.length, 1);
same('B4 내용을 모두 지움', (() => { const c = readWork('', TODAY); return [c.title, c.todos.length, c.events.length, c.problems.length]; })(), ['', 0, 0, 0]);
same('B5 맨 앞 --- 만 남김', probs('---\n'), [['front', 1]]);
same('B6 반쯤 지운 일정·할 일 줄은 탈 없이 지나감', [readWork('- 2026-11-\n- [ \n', TODAY).events.length, probs('- 2026-11-\n- [ \n')], [0, []]);
same('B7 BOM 이 남은 파일', readWork('﻿---\nstatus: 진행\n---\n# T\n', TODAY).status, 'active');
same('B8 ##일정 (빈칸 빠짐)·## 일정 (11월)·### 일정 도 일정 절', [
  insertEvent('##일정\n\n- 2026-11-01 a\n\n## 기록\n', L).text,
  insertEvent('## 일정 (11월)\n\n## 기록\n', L).text,
  insertEvent('## 계획\n\n### 일정\n\n- 2026-11-01 a\n\n### 할 일\n', L).text,
], [
  `##일정\n\n- 2026-11-01 a\n${L}\n\n## 기록\n`,
  `## 일정 (11월)\n\n${L}\n\n## 기록\n`,
  `## 계획\n\n### 일정\n\n- 2026-11-01 a\n${L}\n\n### 할 일\n`,
]);
same('B10 제목이 일정으로 시작해도 일정 절이 아님 (# 일정 관리 개선·## 일정표 정리)', [
  insertEvent('# 일정 절 없음\n\n- 2026-11-01 지난 일정', L).text,
  insertEvent('# T\n\n## 일정표 정리\n\n글\n', L).text,
], [
  `# 일정 절 없음\n\n- 2026-11-01 지난 일정\n\n## 일정\n\n${L}`,
  `# T\n\n## 일정표 정리\n\n글\n\n## 일정\n\n${L}\n`,
]);
same('B9 닫는 --- 를 지운 파일에도 일정 절을 찾아 넣음', insertEvent('---\nstatus: 진행\n\n## 일정\n\n## 기록\n', L).text, `---\nstatus: 진행\n\n## 일정\n\n${L}\n\n## 기록\n`);

return { fails, n };
