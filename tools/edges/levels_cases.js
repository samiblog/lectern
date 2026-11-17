// 레벨 바꾸기와 줄 종류의 표 점검 (D152) — rules_check.mjs 가 돌린다 (d: docops.js, lo: lineops.js)
// 레벨 바꾸기 시나리오 51가지에서 '크게 바뀌던' 경우: 여러 줄을 고르면 하위가 두 번 옮겨짐, 하위 항목의 종류를 바꾸면 들여쓰기를 잃음,
// 하위가 있는 항목을 제목으로 바꾸면 하위가 코드 블록이 됨, 제목의 >> 가 하위 절까지 옮김
const { shiftLevels, setKind } = d;
const { itemSpan, indentLines, renumberAt } = lo;
const fails = [];
let n = 0;
const same = (name, got, want) => {
  n += 1;
  const a = JSON.stringify(got);
  const b = JSON.stringify(want);
  if (a !== b) fails.push(`${name}: ${a} ≠ ${b}`);
};
const L = (s) => s.split('\n');
const J = (r) => (r.error ? r.error : r.lines.join('\n'));

// ---- 여러 줄을 골라 — 앞에서 함께 옮긴 하위는 건너뛴다 ----
same('L1 하위까지 골라 안으로 — 두 번 옮기지 않음', J(shiftLevels(L('- 가\n- 나\n  - 나1\n  - 나2\n- 다'), 2, 4, 1, { tab: true })),
  '- 가\n  - 나\n    - 나1\n    - 나2\n- 다');
same('L2 번호 항목과 하위를 골라 안으로', J(shiftLevels(L('1. 가\n2. 나\n   1. 나1\n   2. 나2\n   3. 나3\n3. 다'), 2, 5, 1, { tab: true })),
  '1. 가\n   1. 나\n      1. 나1\n      2. 나2\n      3. 나3\n2. 다');
same('L3 부모와 하위를 골라 밖으로 — 평평해지지 않음', J(shiftLevels(L('- 가\n  - 가1\n    - 가1a\n    - 가1b\n- 나'), 2, 4, -1)),
  '- 가\n- 가1\n  - 가1a\n  - 가1b\n- 나');
same('L4 하위 셋을 골라 밖으로', J(shiftLevels(L('- 가\n  - 가1\n  - 가2\n  - 가3\n- 나'), 2, 4, -1)), '- 가\n- 가1\n- 가2\n- 가3\n- 나');
same('L5 형제 셋을 골라 안으로', J(shiftLevels(L('1. 가\n2. 나\n3. 다\n4. 라'), 2, 4, 1)), '1. 가\n   1. 나\n   2. 다\n   3. 라');

// ---- 제목: 그 줄만 (Tab·>>·> <) / 하위 절까지 (Alt+Shift) ----
const DOC = '# 문서\n\n## 1장\n\n### 1.1\n\n#### 1.1.1\n\n## 2장';
same('L6 >> 는 그 줄만', J(shiftLevels(L(DOC), 3, 3, 1)), '# 문서\n\n### 1장\n\n### 1.1\n\n#### 1.1.1\n\n## 2장');
const sec = shiftLevels(L(DOC), 3, 3, 1, { section: true });
same('L7 Alt+Shift 는 하위 절까지, 함께 옮긴 제목 2', [J(sec), sec.subHeads], ['# 문서\n\n### 1장\n\n#### 1.1\n\n##### 1.1.1\n\n## 2장', 2]);
same('L8 문서 제목의 >> 는 그 줄만 — 문서 전체가 내려가지 않음', J(shiftLevels(L(DOC), 1, 1, 1)), '## 문서\n\n## 1장\n\n### 1.1\n\n#### 1.1.1\n\n## 2장');
same('L9 제목 둘을 함께 골라 Alt+Shift — 하위가 두 번 내려가지 않음', J(shiftLevels(L('# 문서\n\n## 1장\n\n### 1.1\n\n## 2장'), 3, 5, 1, { section: true })),
  '# 문서\n\n### 1장\n\n#### 1.1\n\n## 2장');
same('L10 제목만 골라 Tab — 까닭', shiftLevels(L('## 1장\n\n### 1.1'), 1, 3, 1, { tab: true }).error, 'heading-tab');
same('L11 제목과 목록을 함께 골라 Tab — 목록만', J(shiftLevels(L('## 1장\n\n- 가\n- 나'), 1, 4, 1, { tab: true })), '## 1장\n\n- 가\n  - 나');
same('L12 제목 6 에 닿음', shiftLevels(L('## 가\n\n###### 깊은 제목'), 1, 1, 1, { section: true }).error, 'edge');
same('L13 그 줄만이면 하위가 6 이어도 된다', J(shiftLevels(L('## 가\n\n###### 깊은 제목'), 1, 1, 1)), '### 가\n\n###### 깊은 제목');

// ---- 번호를 다시 매긴 바깥 항목 수 (알림) ----
same('L14 셋째를 안으로 — 넷째 번호 하나', shiftLevels(L('1. 가\n2. 나\n3. 다\n4. 라'), 3, 3, 1).renumbered, 1);
same('L15 첫 하위를 밖으로 — 뒤 형제 둘과 부모의 다음 항목', shiftLevels(L('1. 가\n   1. 가1\n   2. 가2\n   3. 가3\n2. 나'), 2, 2, -1).renumbered, 3);
same('L16 글머리 목록은 셀 번호가 없다', shiftLevels(L('- 가\n- 나\n- 다'), 2, 2, 1).renumbered, 0);
same('L17 하위는 함께 옮긴 것이라 세지 않음', shiftLevels(L('1. 가\n2. 나\n   1. 나1\n   2. 나2\n3. 다'), 2, 2, 1).renumbered, 1);

// ---- 줄 종류: 목록끼리는 들여쓰기를 지키고, 하위가 있는 항목을 목록 밖으로 바꾸면 하위를 당긴다 ----
same('L18 하위 항목을 번호로 — 들여쓰기 그대로', setKind(L('- 가\n  - 가1\n  - 가2\n- 나'), 2, 2, 'number').lines.join('\n'), '- 가\n  1. 가1\n  - 가2\n- 나');
same('L19 하위 번호 항목을 할 일로', setKind(L('1. 가\n   1. 가1\n2. 나'), 2, 2, 'task').lines.join('\n'), '1. 가\n   - [ ] 가1\n2. 나');
same('L20 하위 항목 둘을 목록으로', setKind(L('- 가\n  1. 가1\n  2. 가2'), 2, 3, 'bullet').lines.join('\n'), '- 가\n  - 가1\n  - 가2');
same('L21 10. 항목(하위 4칸)을 제목으로 — 하위가 코드 블록이 되지 않음', setKind(L('9. 아홉\n10. 열\n    - 열의 하위\n11. 열하나'), 2, 2, 'h2').lines.join('\n'),
  '9. 아홉\n\n## 열\n\n- 열의 하위\n10. 열하나');   // 뒤 항목은 앞 항목에 잇는다 (D155)
same('L22 하위가 있는 항목을 문단으로', setKind(L('1. 가\n2. 나\n   - 나1\n   - 나2\n3. 다'), 2, 2, 'para').lines.join('\n'), '1. 가\n\n나\n\n- 나1\n- 나2\n2. 다');   // D155
same('L23 하위가 없는 항목은 그대로', setKind(L('- 가\n- 나\n- 다'), 2, 2, 'h2').lines.join('\n'), '- 가\n\n## 나\n\n- 다');
same('L24 맨 위 목록 가운데를 번호로 (전과 같음)', setKind(L('- 가\n- 나\n- 다'), 2, 2, 'number').lines.join('\n'), '- 가\n1. 나\n- 다');

// ---- 도우미 ----
same('L25 itemSpan — 하위까지', [itemSpan(L('- 가\n  - 가1\n- 나'), 1), itemSpan(L('문단'), 1)], [[1, 2], null]);
same('L26 indentLines — 0 칸 아래로는 가지 않음', indentLines(L('  - a\n\n    - b'), 1, 3, -3), ['- a', '', ' - b']);
same('L27 renumberAt — 복제로 겹친 번호', renumberAt(L('1. 하나\n1. 하나\n2. 둘'), 2), ['1. 하나', '2. 하나', '3. 둘']);
same('L28 renumberAt — 모두 1. 로 쓴 목록은 그대로', renumberAt(L('1. a\n1. a\n1. b'), 2), ['1. a', '1. a', '1. b']);
same('L29 renumberAt — 5 부터', renumberAt(L('5. a\n5. a\n6. b'), 1), ['5. a', '6. a', '7. b']);
same('L30 renumberAt — 번호 목록이 아니면 그대로', renumberAt(L('- a\n- a'), 1), ['- a', '- a']);

return { fails, n };
