// slideops.js 의 계산과 Lectern 슬라이드의 줄 구조 벽 점검 (slides.py 가 페이지 안에서, rules_check 가 node 로 돌린다 — m: slideops.js, lo: lineops.js, 끝에서 {n, fails} 를 돌려준다)
const { textSizes, readCellHead, cellHeadOdds, textOdds, setTextSize, setCellSize, addSlide, duplicateSlide, moveSlide, deleteSlide, setLayout } = m;
const { planNew, insertLine, joinLine, moveLines, deleteLines } = lo;
let n = 0;
const fails = [];
const L = (s) => s.split('\n');
const eq = (got, want, name) => {
  n += 1;
  const show = (x) => (Array.isArray(x) ? x.join('\n') : JSON.stringify(x));
  if (show(got) !== show(want)) fails.push(`${name}: ${show(got)} ≠ ${show(want)}`);
};

// 글자 크기 읽기
eq(textSizes('표 14, 제목 30'), { table: 14, title: 30 }, '한국어 낱말');
eq(textSizes('table 12, sub 20'), { table: 12, sub: 20 }, '영어 낱말');
eq(textSizes('표 14', '표 12'), { table: 12 }, '뒤의 것이 이김');
eq(textSizes('없는말 14, 표 abc, 표'), {}, '모르는 것은 넘어감');
eq(textSizes(undefined, 3), {}, '글이 아니면');

// 칸 머리 줄
eq(readCellHead('a'), { name: 'a', words: [], size: null, at: null }, '이름만');
eq(readCellHead('b card accent 16'), { name: 'b', words: ['card', 'accent'], size: 16, at: null }, '꾸밈과 크기');
eq(readCellHead('hub note at 10 20 300 120'), { name: 'hub', words: ['note'], size: null, at: [10, 20, 300, 120] }, '자리');
eq(readCellHead('hub at 10 20 300 120 14'), { name: 'hub', words: [], size: 14, at: [10, 20, 300, 120] }, '자리 뒤의 크기');
eq(readCellHead('a at 1 2'), { name: 'a', words: [], size: null, at: null }, '자리가 모자라면 글자 크기로 읽지 않는다');
eq(cellHeadOdds('a at 1 2 card'), ['at 1 2'], '모자란 자리를 알린다');
eq(cellHeadOdds('a 16pt 9999 0 card 16'), ['16pt', '9999', '0'], '읽지 못한 낱말');
eq(textOdds('표 14, 제목 30'), [], '맞는 글자 크기');
eq(textOdds('표표 14, 본문 크게'), ['표표 14', '본문 크게'], '읽지 못한 글자 크기');
eq(readCellHead('a <b> "x"').words, [], '낱말이 아닌 것은 버림');

// 글자 크기 고치기
const D = '---\nmarp: true\n---\n\n## 가\n\n글\n\n---\n\n<!-- layout: two -->\n\n## 나\n';
eq(setTextSize(L(D), 4, 8, '표', 14), L('---\nmarp: true\n---\n\n<!-- text: 표 14 -->\n\n## 가\n\n글\n\n---\n\n<!-- layout: two -->\n\n## 나\n'), '없으면 장 맨 앞에');
const T = '## 가\n\n<!-- text: 표 14, 제목 28 -->\n';
eq(setTextSize(L(T), 1, 3, '표', 13), L('## 가\n\n<!-- text: 제목 28, 표 13 -->\n'), '있으면 그 낱말만');
eq(setTextSize(L(T), 1, 3, 'table', 12), L('## 가\n\n<!-- text: 제목 28, table 12 -->\n'), '다른 말의 같은 낱말');
eq(setCellSize(L('::: b card\n글\n:::'), 1, 16), L('::: b card 16\n글\n:::'), '칸 크기 더하기');
eq(setCellSize(L('::: b card 16\n글\n:::'), 1, 15), L('::: b card 15\n글\n:::'), '칸 크기 고치기');
eq(setCellSize(L('::: b at 10 20 30 40 16\n:::'), 1, 15), L('::: b at 10 20 30 40 15\n:::'), '자리의 수는 그대로');
eq(setCellSize(L('::: b at 10 20 30 40\n:::'), 1, 15), L('::: b at 10 20 30 40 15\n:::'), '자리 뒤에 더하기');
eq(setCellSize(L('::: 12 card\n:::'), 1, 15), L('::: 12 card 15\n:::'), '칸 이름이 수여도');

// 장 다루기 — 앞 설정 3줄, 장 셋
const S3 = L('---\nmarp: true\n---\n\n# 하나\n\n---\n\n## 둘\n\n글\n\n---\n\n## 셋\n');
const spans = [[4, 6], [8, 12], [14, 16]];
eq(addSlide(S3, spans[0], '새').lines, L('---\nmarp: true\n---\n\n# 하나\n\n---\n\n## 새\n\n---\n\n## 둘\n\n글\n\n---\n\n## 셋\n'), '장 더하기');
eq(addSlide(S3, spans[0], '새').line, 12 - 3, '새 제목 줄');
eq(addSlide(S3, spans[2], '새').lines.slice(-6), ['## 셋', '', '---', '', '## 새', ''], '끝에 더하기');
eq(duplicateSlide(S3, spans[1]).lines, L('---\nmarp: true\n---\n\n# 하나\n\n---\n\n## 둘\n\n글\n\n---\n\n## 둘\n\n글\n\n---\n\n## 셋\n'), '복제');
eq(moveSlide(S3, spans, 1, -1).lines, L('---\nmarp: true\n---\n\n## 둘\n\n글\n\n---\n\n# 하나\n\n---\n\n## 셋\n'), '앞으로');
eq(moveSlide(S3, spans, 1, -1).line, 5, '앞으로 옮긴 줄');
eq(moveSlide(S3, spans, 1, 1).lines, L('---\nmarp: true\n---\n\n# 하나\n\n---\n\n## 셋\n\n---\n\n## 둘\n\n글\n'), '뒤로');
eq(moveSlide(S3, spans, 1, 1).line, 13, '뒤로 옮긴 줄');
eq(moveSlide(S3, spans, 0, -1), { error: 'edge' }, '맨 앞');
eq(moveSlide(S3, spans, 2, 1), { error: 'edge' }, '맨 뒤');
eq(deleteSlide(S3, spans, 1).lines, L('---\nmarp: true\n---\n\n# 하나\n\n---\n\n## 셋\n'), '가운데 지우기');
eq(deleteSlide(S3, spans, 0).lines, L('---\nmarp: true\n---\n\n## 둘\n\n글\n\n---\n\n## 셋\n'), '맨 앞 지우기');
eq(deleteSlide(S3, spans, 2).lines, L('---\nmarp: true\n---\n\n# 하나\n\n---\n\n## 둘\n\n글\n'), '맨 뒤 지우기');
eq(deleteSlide(S3, [[4, 16]], 0), { error: 'only' }, '하나뿐');

// 배치 넣기
const W = { body: '글', number: '0', label: '설명' };
const lay = (s, name) => setLayout(L(s), [1, L(s).length], name, W);
eq(lay('## 제목', 'two').lines, L('<!-- layout: two -->\n\n## 제목\n\n::: a card\n글\n:::\n\n::: b card\n글\n:::'), '빈 장에 뼈대');
eq(lay('## 제목', 'two').line, 6, '첫 칸의 글 줄');
eq(lay('## 제목\n\n- 가\n- 나\n\n<!-- 노트 -->', 'two').lines, L('<!-- layout: two -->\n\n## 제목\n\n::: a\n- 가\n- 나\n:::\n\n<!-- 노트 -->\n\n::: b card\n글\n:::'), '칸 없는 장의 글은 첫 칸으로');
eq(lay('<!-- layout: quad -->\n\n## 제목\n\n::: a card\n가\n:::\n\n::: b\n나\n:::\n\n::: c\n다\n:::', 'two').lines, L('<!-- layout: two -->\n\n\n## 제목\n\n::: a card\n가\n:::\n\n::: b\n나\n:::\n\n::: c\n다\n:::'), '남는 칸은 지우지 않는다');
eq(lay('<!-- grid: x y -->\n<!-- cols: 1fr 1fr -->\n\n::: x\n가\n:::\n\n::: y\n나\n:::', 'quad').lines, L('<!-- layout: quad -->\n\n\n::: a\n가\n:::\n\n::: b\n나\n:::\n\n::: c card\n글\n:::\n\n::: d card\n글\n:::'), '격자를 배치로, 칸 이름을 차례대로');
eq(lay('## 제목', 'kpi').lines.slice(4, 8), ['::: a kpi', '**0**', '설명', ':::'], 'KPI 뼈대');
eq(lay('## 제목', 'kpi').lines.at(-3), '::: e card', 'KPI 의 넓은 칸');
eq(lay('## 제목\n\n```\n::: 코드\n```', 'two').lines.includes('::: 코드'), true, '코드 블록 안의 ::: 는 칸이 아니다');

// Lectern 슬라이드의 벽: 칸·장·지시어 줄을 넘거나 깨뜨리지 않는다
const DK = '---\nmarp: true\n---\n\n<!-- layout: two -->\n\n## 제목\n\n::: a card\n첫 글\n:::\n\n::: b\n- 가\n- 나\n:::\n\n---\n\n## 끝\n';
const dk = L(DK);
const add = (at, below, text) => { const p = planNew(dk, at, below); return insertLine(dk, p, text).lines; };
eq(add(15, true, '다').slice(13, 17), ['- 가', '- 나', '- 다', ':::'], '칸 끝 항목 아래 새 항목');
eq(moveLines(dk, 10, 10, 1), { error: 'edge' }, '칸의 문단을 아래로');
eq(moveLines(dk, 10, 10, -1), { error: 'edge' }, '칸의 문단을 위로');
eq(moveLines(dk, 15, 15, 1).error, 'edge', '칸 끝 항목을 아래로');
eq(moveLines(dk, 7, 7, -1), { error: 'edge' }, '제목을 지시어 위로');
eq(joinLine(dk, 10, { split: (l) => ({ head: '', body: l, tail: '' }) }), { error: 'different' }, '칸 첫 줄을 머리 줄과 잇기');
eq(joinLine(dk, 20, { split: (l) => ({ head: '', body: l, tail: '' }) }), { error: 'different' }, '장 첫 줄을 앞 장과 잇기');
eq(deleteLines(dk, 9, 10), { error: 'wall' }, '머리 줄만 걸쳐 지우기');
eq(deleteLines(dk, 10, 11), { error: 'wall' }, '닫는 줄만 걸쳐 지우기');
eq(deleteLines(dk, 9, 11).error, undefined, '칸째 지우기');
eq(deleteLines(dk, 10, 10).error, undefined, '칸 안 한 줄 지우기');
// 제목으로 갈리는 문서 — 제목 앞은 앞 장이다
const dv = L('---\nmarp: true\nheadingDivider: 2\n---\n\n## 하나\n\n첫 글\n\n## 둘\n\n둘째 글\n');
const dvs = [[6, 9], [10, 13]];
eq(setTextSize(dv, 10, 13, '표', 14).slice(9, 13), ['## 둘', '<!-- text: 표 14 -->', '', '둘째 글'], '지시어는 제목 다음에');
eq(setTextSize(dv, 6, 9, '표', 14).slice(5, 8), ['<!-- text: 표 14 -->', '', '## 하나'], '첫 장은 맨 앞에');
eq(setLayout(dv, dvs[1], 'two', W).lines.slice(9, 15), ['## 둘', '', '<!-- layout: two -->', '', '::: a', '둘째 글'], '배치도 제목 다음에');
eq(setLayout(dv, dvs[1], 'two', W).line, 15, '배치의 첫 칸 줄');
eq(moveSlide(dv, dvs, 0, 1).lines.slice(5, 13), ['## 둘', '', '둘째 글', '', '## 하나', '', '첫 글', ''], '제목으로 갈린 장 옮기기');
const headless = L('---\nmarp: true\nheadingDivider: 2\n---\n\n머리 없는 글\n\n## 둘\n\n글\n');
eq(moveSlide(headless, [[6, 7], [8, 11]], 0, 1), { error: 'edge' }, '제목 없는 장은 옮기면 앞 장에 붙는다');
const empty = L('---\nmarp: true\n---\n\n## 하나\n\n---\n\n---\n\n## 셋\n');
eq(moveSlide(empty, [[4, 6], [8, 8], [10, 12]], 0, 1), { error: 'edge' }, '빈 장과는 맞바꾸지 않는다');

// 코드 속의 지시어·칸 표시는 코드다
const fc = L('---\nmarp: true\n---\n\n## 코드\n\n```md\n<!-- text: 표 9 -->\n<!-- layout: quad -->\n::: z\n:::\n```\n');
eq(setTextSize(fc, 4, 12, '표', 14).slice(3, 6), ['', '<!-- text: 표 14 -->', ''], '코드 속 지시어를 고치지 않는다');
eq(setTextSize(fc, 4, 12, '표', 14).includes('<!-- text: 표 9 -->'), true, '코드 속 지시어가 남는다');
eq(setLayout(fc, [4, 12], 'two', W).lines.includes('<!-- layout: quad -->'), true, '코드 속 배치를 지우지 않는다');
eq(setLayout(fc, [4, 12], 'two', W).lines.includes('::: z'), true, '코드 속 칸 이름을 바꾸지 않는다');

// 한 장만의 지시어 _text, _layout
const sp = L('---\nmarp: true\n---\n\n<!-- _text: 표 12 -->\n<!-- _layout: quad -->\n\n## 글\n');
eq(setTextSize(sp, 4, 8, '제목', 28)[4], '<!-- _text: 표 12, 제목 28 -->', '_text 를 고친다');
eq(setLayout(sp, [4, 8], 'two', W).lines.some((s) => s.includes('_layout')), false, '_layout 을 갈아 끼운다');

// 칸·장의 경계
const wl = L('---\nmarp: true\n---\n\n::: a\n- 항목\n:::\n\n::: b\n글\n:::\n\n---\n\n## 다음\n\n<!-- 노트 -->\n');
eq(deleteLines(wl, 7, 9), { error: 'wall' }, '앞 칸의 끝과 다음 칸의 머리를 함께 지우지 않는다');
eq(deleteLines(wl, 11, 15), { error: 'wall' }, '구분 줄을 지우지 않는다');
eq(deleteLines(wl, 5, 11).error, undefined, '두 칸을 통째로 지운다');
eq(deleteLines(wl, 17, 17).ask, true, '주석은 묻고 지운다');
eq(lo.indentItem(wl, 10).error, 'not-list', '앞 칸의 목록은 이 줄의 주인이 아니다');
const st = L('---\nmarp: true\n---\n\n밑줄 제목\n---\n\n글\n');
eq(deleteLines(st, 6, 6).error, undefined, '밑줄 제목의 --- 는 구분 줄이 아니다');
const yes = L('---\nmarp: yes\n---\n\n::: a\n글\n:::\n');
eq(deleteLines(yes, 5, 6), { error: 'wall' }, 'marp: yes 도 Lectern 슬라이드');
const quoted = L('---\nmarp: "true"\n---\n\n::: a\n글\n:::\n');
eq(deleteLines(quoted, 5, 6).error, undefined, '따옴표를 쓰면 글이라 Lectern 슬라이드가 아니다');

// 템플릿 (D101)
const { templateLines, addTemplate, applyTemplate, setFrontKey } = m;
eq(templateLines('\n# {{제목}}\n\n글\n\n', '보고'), ['# 보고', '', '글'], '템플릿 줄: 제목을 넣고 앞뒤 빈 줄을 뗀다');
eq(templateLines('# {{title}}\n', 'Report'), ['# Report'], '템플릿 줄: 영어 표시');
const TWO = L('<!-- layout: two -->\n\n## 결론\n\n::: a card\n왼쪽\n:::\n\n::: b card\n오른쪽\n:::');
const ONE = L('## 제목\n\n- 내용');
const base = L('---\nmarp: true\n---\n\n## 첫 장\n\n글\n');
{
  const r = addTemplate(base, [5, 8], TWO);
  eq(r.lines.join('\n'), '---\nmarp: true\n---\n\n## 첫 장\n\n글\n\n---\n\n<!-- layout: two -->\n\n## 결론\n\n::: a card\n왼쪽\n:::\n\n::: b card\n오른쪽\n:::\n', '새 장을 템플릿으로');
  eq(r.lines[r.line - 1], '## 결론', '새 장의 고칠 첫 줄은 제목');
}
const applied = (text, tpl, samples) => {
  const lines = L(`---\nmarp: true\n---\n\n${text}`);
  const r = applyTemplate(lines, [5, lines.length], tpl, new Set(samples));
  return { text: r.lines.slice(4).join('\n'), first: r.lines[r.line - 1] };
};
eq(applied('## 내 제목\n\n내 글', TWO).text, '<!-- layout: two -->\n\n## 내 제목\n\n::: a card\n내 글\n:::\n\n::: b card\n오른쪽\n:::', '칸 없는 장의 글은 첫 칸에');
eq(applied('## 내 제목\n\n내 글', TWO).first, '## 내 제목', '고칠 첫 줄');
eq(applied('<!-- layout: three -->\n\n## 내 제목\n\n::: a card\n하나\n:::\n\n::: b card\n둘\n:::\n\n::: c card\n셋\n:::', TWO).text,
  '<!-- layout: two -->\n\n## 내 제목\n\n::: a card\n하나\n:::\n\n::: b card\n둘\n\n셋\n:::', '못 담는 글은 맨 아래 칸에');
eq(applied('<!-- layout: two -->\n\n## 내 제목\n\n::: a card\n하나\n:::\n\n::: b card\n둘\n:::', ONE).text, '## 내 제목\n\n하나\n\n둘', '칸 없는 템플릿이면 본문에');
eq(applied('## 결론\n\n::: a card\n왼쪽\n:::', ONE, ['## 결론', '왼쪽']).text, '## 제목\n\n- 내용', '안내 글은 옮기지 않는다');
eq(applied('## 내 제목\n\n::: a\n```js\n::: b\n```\n:::', ONE).text, '## 내 제목\n\n```js\n::: b\n```', '코드 속 ::: 는 글');
eq(applied('## 내 제목\n\n글\n\n<!-- 발표자 노트 -->', ONE).text, '## 내 제목\n\n글\n\n<!-- 발표자 노트 -->', '노트는 남는다');
eq(applied('<!-- hidden: true -->\n\n## 내 제목\n\n글', ONE).text, '<!-- hidden: true -->\n\n## 내 제목\n\n글', '숨긴 장은 그대로');
eq(applied('<!-- _class: lead -->\n\n# 표지 글', ONE).text, '## 표지 글\n\n- 내용', '표지의 지시어는 빠지고 제목 수준은 템플릿을 따른다');
eq(setFrontKey(L('---\nmarp: true\n---\n\n# 글'), 'pptxStyle', '회사').join('\n'), '---\nmarp: true\npptxStyle: 회사\n---\n\n# 글', '맨 앞 설정에 넣는다');
eq(setFrontKey(L('---\nmarp: true\npptxStyle: 옛것\n---'), 'pptxStyle', '새것').join('\n'), '---\nmarp: true\npptxStyle: 새것\n---', '있으면 바꾼다');
eq(setFrontKey(L('# 글'), 'pptxStyle', '회사').join('\n'), '# 글', '맨 앞 설정이 없으면 그대로');

// 새 문서 이름의 확장자를 두 번 쓰지 않는다 (cleanPath 는 화면에서 시험)
// Lectern 슬라이드가 아니면 ::: 는 보통 글이다
const pl = L('# 글\n\n::: a\n첫 글\n:::\n');
eq(moveLines(pl, 4, 4, 1).lines, L('# 글\n\n::: a\n:::\n첫 글\n'), '보통 문서의 ::: 는 글');
return { n, fails };
