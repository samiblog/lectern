// 박스글(D126)의 계산 점검 (rules_check.mjs 가 돌린다 — m: docops.js, refs: refs.js, 끝에서 {n, fails} 를 돌려준다).
const { textboxesIn, textboxAt, wrapTextbox, unwrapTextbox, textboxSpan, makeTextbox, textboxTitle, isTextboxOpen, isTextboxClose, nextCaption } = m;
let n = 0;
const fails = [];
const L = (s) => s.split('\n');
const eq = (got, want, name) => {
  n += 1;
  const show = (x) => (Array.isArray(x) && x.every((v) => typeof v === 'string') ? x.join('\n') : JSON.stringify(x));
  if (show(got) !== show(want)) fails.push(`${name}: ${show(got)} ≠ ${show(want)}`);
};
const TITLE = '**박스 1. 제목**';
const cap = (s) => /^(?:박스|Box)$/.test(refs.captionAt(s)?.word ?? '');

// 여는 줄·닫는 줄 — 공백과 대소문자에 너그럽게, 다른 글이 붙으면 아니다
eq(isTextboxOpen('<!-- box -->'), true, '여는 줄');
eq(isTextboxOpen('<!--box-->'), true, '공백 없이');
eq(isTextboxOpen('  <!--  BOX  -->  '), true, '들여쓰기·대문자·끝 공백');
eq(isTextboxOpen('<!-- box --> 글'), false, '뒤에 글이 있으면 아니다');
eq(isTextboxOpen('<!-- boxes -->'), false, '다른 낱말');
eq(isTextboxOpen('<!-- /box -->'), false, '닫는 줄은 여는 줄이 아니다');
eq(isTextboxClose('<!-- /box -->'), true, '닫는 줄');
eq(isTextboxClose('<!--/Box-->'), true, '닫는 줄 공백 없이');
eq(isTextboxClose('<!-- box -->'), false, '여는 줄은 닫는 줄이 아니다');
eq(isTextboxOpen('    <!-- box -->'), false, '네 칸 들여쓰면 코드다');

// 찾기
const DOC = L('# 글\n\n본문\n\n<!-- box -->\n**박스 1. 제목**\n\n안의 글\n<!-- /box -->\n\n뒤');
eq(textboxesIn(DOC), [{ a: 5, b: 9, end: 9 }], '하나');
eq(textboxAt(DOC, 5), { a: 5, b: 9, end: 9 }, '여는 줄도 그 박스글');
eq(textboxAt(DOC, 8), { a: 5, b: 9, end: 9 }, '안의 줄');
eq(textboxAt(DOC, 9), { a: 5, b: 9, end: 9 }, '닫는 줄');
eq(textboxAt(DOC, 3), null, '앞의 본문');
eq(textboxAt(DOC, 11), null, '뒤의 본문');
eq(textboxSpan(DOC, 6), [5, 9], '지울 범위');
eq(textboxesIn(L('글\n<!-- /box -->\n글')), [], '닫는 줄만 있으면 없다');
eq(textboxesIn(L('```\n<!-- box -->\n글\n<!-- /box -->\n```')), [], '코드 블록 안은 뺀다');
eq(textboxesIn(L('---\ntitle: 글\n---\n\n<!-- box -->\n글\n<!-- /box -->')), [{ a: 5, b: 7, end: 7 }], '머리 설정 뒤');

// 닫지 않은 것 — 줄을 버리지 않는다
eq(textboxesIn(L('<!-- box -->\n글 하나\n\n글 둘\n\n## 다음 절\n\n본문')), [{ a: 1, b: 0, end: 4 }], '다음 제목 앞에서 끝난다');
eq(textboxesIn(L('<!-- box -->\n글 하나\n\n글 둘\n')), [{ a: 1, b: 0, end: 4 }], '문서 끝에서 끝난다 (끝의 빈 줄은 뺀다)');
eq(textboxesIn(L('<!-- box -->\n글\n\n<!-- box -->\n둘\n<!-- /box -->')), [{ a: 1, b: 0, end: 2 }, { a: 4, b: 6, end: 6 }], '또 열면 앞의 것이 끝난다');
eq(textboxesIn(L('<!-- box -->\n글\n<!-- /box -->\n\n<!-- /box -->\n\n<!-- box -->\n둘\n<!-- /box -->')), [{ a: 1, b: 3, end: 3 }, { a: 7, b: 9, end: 9 }], '남은 닫는 줄은 그냥 주석');
eq(textboxesIn(L('<!-- box -->')), [{ a: 1, b: 0, end: 1 }], '여는 줄뿐');
eq(textboxAt(L('<!-- box -->\n글\n\n## 절\n본문'), 5), null, '제목 뒤는 박스글이 아니다');

// 새로 넣기
eq(makeTextbox('박스', 2, '제목', '내용'), ['<!-- box -->', '**박스 2. 제목**', '', '내용', '<!-- /box -->'], '새 박스글의 줄');
eq(textboxTitle('Box', 1, 'Title'), '**Box 1. Title**', '영어 제목 줄');
eq(nextCaption(DOC, '박스'), 2, '다음 번호');
eq(nextCaption(L('글'), '박스'), 1, '처음이면 1');

// 묶기
eq(wrapTextbox(L('앞\n\n가\n\n나\n\n뒤'), 3, 5, TITLE).lines, L('앞\n\n<!-- box -->\n**박스 1. 제목**\n\n가\n\n나\n<!-- /box -->\n\n뒤'), '고른 줄을 묶는다 — 제목 줄을 넣는다');
eq(wrapTextbox(L('앞\n\n가\n\n나\n\n뒤'), 3, 5, TITLE).line, 4, '묶은 뒤 제목 줄로');
eq(wrapTextbox(L('앞\n가\n뒤'), 2, 2, TITLE).lines, L('앞\n\n<!-- box -->\n**박스 1. 제목**\n\n가\n<!-- /box -->\n\n뒤'), '앞뒤에 빈 줄을 둔다');
eq(wrapTextbox(L('박스 3. 이미 쓴 제목\n\n글'), 1, 3, TITLE, cap).lines, L('<!-- box -->\n박스 3. 이미 쓴 제목\n\n글\n<!-- /box -->'), '첫 줄이 캡션이면 제목 줄을 더하지 않는다');
eq(wrapTextbox(L('**Box 1. Title**\n\ntext'), 1, 3, TITLE, cap).lines, L('<!-- box -->\n**Box 1. Title**\n\ntext\n<!-- /box -->'), '영어 캡션도');
eq(wrapTextbox(L('가\n\n\n나'), 2, 3, TITLE), { error: 'kind' }, '빈 줄만 고르면 묶지 않는다');
eq(wrapTextbox(L('\n가\n\n'), 1, 4, TITLE).lines, L('\n<!-- box -->\n**박스 1. 제목**\n\n가\n<!-- /box -->\n\n'), '고른 범위의 앞뒤 빈 줄은 밖에 둔다');
eq(wrapTextbox(L('가\n\n## 절\n\n나'), 1, 5, TITLE), { error: 'textbox-heading' }, '제목에 걸치면 묶지 않는다');
eq(wrapTextbox(DOC, 3, 6, TITLE), { error: 'in-textbox' }, '박스글에 걸치면 묶지 않는다');
eq(wrapTextbox(DOC, 8, 8, TITLE), { error: 'in-textbox' }, '박스글 안에서 묶지 않는다');
eq(wrapTextbox(L('---\ntitle: 글\n---\n본문'), 2, 4, TITLE), { error: 'kind' }, '머리 설정은 묶지 않는다');
eq(wrapTextbox(L('글\n\n```py\na = 1\nb = 2\n```\n\n뒤'), 4, 4, TITLE).lines, L('글\n\n<!-- box -->\n**박스 1. 제목**\n\n```py\na = 1\nb = 2\n```\n<!-- /box -->\n\n뒤'), '코드 블록의 한 줄을 고르면 블록째');
eq(wrapTextbox(L('글\n\n```\n## 제목 아님\n```'), 3, 5, TITLE).error, undefined, '코드 안의 # 은 제목이 아니다');
eq(wrapTextbox(L('| 가 | 나 |\n|---|---|\n| 1 | 2 |'), 1, 3, TITLE).lines, L('<!-- box -->\n**박스 1. 제목**\n\n| 가 | 나 |\n|---|---|\n| 1 | 2 |\n<!-- /box -->'), '표를 묶는다');

// 풀기 — 글은 그대로
eq(unwrapTextbox(DOC, 8).lines, L('# 글\n\n본문\n\n**박스 1. 제목**\n\n안의 글\n\n뒤'), '여는 줄과 닫는 줄만 뺀다');
eq(unwrapTextbox(DOC, 3), { error: 'not-textbox' }, '박스글 밖에서는 풀지 않는다');
eq(unwrapTextbox(L('앞\n\n<!-- box -->\n\n글\n\n<!-- /box -->\n\n뒤'), 5).lines, L('앞\n\n글\n\n뒤'), '빈 줄이 겹치면 하나만');
eq(unwrapTextbox(L('<!-- box -->\n글\n\n## 절'), 2).lines, L('글\n\n## 절'), '닫지 않은 것도 푼다');
eq(unwrapTextbox(L('<!-- box -->\n글\n<!-- /box -->'), 1).lines, L('글'), '문서가 박스글뿐');
{
  const wrapped = wrapTextbox(L('앞\n\n박스 1. 제목\n\n글\n\n뒤'), 3, 5, TITLE, cap).lines;
  eq(unwrapTextbox(wrapped, 4).lines, L('앞\n\n박스 1. 제목\n\n글\n\n뒤'), '묶었다 풀면 처음 그대로');
}

// 캡션 번호 (refs.js) — 박스글을 더하거나 옮기면 번호와 참조 링크를 함께 고친다
eq(refs.captionAt('**박스 2. 구리 재고**'), { word: '박스', n: 2, title: '구리 재고' }, '박스 캡션');
eq(refs.captionAt('Box 1. Title'), { word: 'Box', n: 1, title: 'Title' }, '영어 캡션');
eq(refs.captionAt('박스권에서 움직였다'), null, '낱말만으로는 캡션이 아니다');
eq(refs.refLink('박스', 3), '[박스 3](#박스-3)', '참조 링크');
{
  const old = L('[박스 1](#박스-1) 을 보라.\n\n<!-- box -->\n**박스 1. 가**\n<!-- /box -->');
  const next = L('<!-- box -->\n**박스 2. 새것**\n<!-- /box -->\n\n[박스 1](#박스-1) 을 보라.\n\n<!-- box -->\n**박스 1. 가**\n<!-- /box -->');
  const r = refs.renumberCaptions(old, next);
  eq(r.lines, L('<!-- box -->\n**박스 1. 새것**\n<!-- /box -->\n\n[박스 2](#박스-2) 을 보라.\n\n<!-- box -->\n**박스 2. 가**\n<!-- /box -->'), '앞에 박스글을 더하면 번호와 링크가 밀린다');
  eq(r.changed, 2, '바뀐 캡션 수');
}
{
  const old = L('표 1. 가\n\n박스 1. 나');
  const next = L('표 1. 새\n\n표 1. 가\n\n박스 1. 나');
  eq(refs.renumberCaptions(old, next).lines, L('표 1. 새\n\n표 2. 가\n\n박스 1. 나'), '표 번호가 바뀌어도 박스 번호는 따로 센다');
}

return { n, fails };
