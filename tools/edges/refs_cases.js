// refs.js 의 계산 점검 (rules_check.mjs 가 돌린다 — m: refs.js, 끝에서 {n, fails} 를 돌려준다).
const { captionAt, captionsIn, renumberCaptions, refTargets, refLink, tocKind, isPageBreak, PAGE_BREAK, referencesIn, citeOf, citedCount } = m;
let n = 0;
const fails = [];
const L = (s) => s.split('\n');
const eq = (got, want, name) => {
  n += 1;
  const show = (x) => (Array.isArray(x) ? x.join('\n') : JSON.stringify(x));
  if (show(got) !== show(want)) fails.push(`${name}: ${show(got)} ≠ ${show(want)}`);
};

// 캡션 읽기
eq(captionAt('표 1. 매출'), { word: '표', n: 1, title: '매출' }, '기본 캡션');
eq(captionAt('**표 2.** 비용'), { word: '표', n: 2, title: '비용' }, '굵은 캡션');
eq(captionAt('<그림 3> 추이'), { word: '그림', n: 3, title: '추이' }, '꺾쇠 캡션');
eq(captionAt('Table 4: Sales'), { word: 'Table', n: 4, title: 'Sales' }, '영어 캡션');
eq(captionAt('표 2-1. 장 번호'), null, '장 번호가 든 캡션은 아니다');
eq(captionAt('표 2.1 소수'), null, '소수점 번호는 아니다');
eq(captionAt('표 3 은 매출을 보여 준다.'), null, '표로 시작하는 문장은 캡션이 아니다');
eq(captionsIn(L('```\n표 1. 코드 속\n```\n표 1. 진짜\n')).map((c) => c.line), [4], '코드 속은 빼고');

// 번호 다시 매기기
const R = (old, next) => renumberCaptions(L(old), L(next));
eq(R('표 1. 가\n\n표 2. 나\n', '표 3. 새\n\n표 1. 가\n\n표 2. 나\n').lines, L('표 1. 새\n\n표 2. 가\n\n표 3. 나\n'), '위에 넣은 표가 1번');
eq(R('표 1. 가\n\n표 2. 나\n\n표 3. 다\n', '표 1. 가\n\n표 3. 다\n').lines, L('표 1. 가\n\n표 2. 다\n'), '지우면 뒤를 당긴다');
eq(R('표 1. 가\n\n표 2. 나\n', '표 2. 나\n\n표 1. 가\n').lines, L('표 1. 나\n\n표 2. 가\n'), '옮기면 차례대로');
eq(R('표 1. 가\n\n표 2. 나\n', '표 1. 가\n\n표 7. 나\n').lines, L('표 1. 가\n\n표 7. 나\n'), '사람이 고친 번호는 그대로');
eq(R('표 1. 가\n\n표 3. 나\n', '표 4. 새\n\n표 1. 가\n\n표 3. 나\n').lines, L('표 4. 새\n\n표 1. 가\n\n표 3. 나\n'), '차례대로가 아니던 문서는 그대로');
eq(R('표 1. 가\n그림 1. 사진\n', '그림 2. 새\n표 1. 가\n그림 1. 사진\n').lines, L('그림 1. 새\n표 1. 가\n그림 2. 사진\n'), '낱말마다 따로');
eq(R('**표 1.** 가\n', '**표 2.** 새\n**표 1.** 가\n').lines, L('**표 1.** 새\n**표 2.** 가\n'), '굵은 캡션도');
{
  const r = R('표 1. 가\n\n표 2. 나\n\n[표 2](#표-2) 참조\n', '표 3. 새\n\n표 1. 가\n\n표 2. 나\n\n[표 2](#표-2) 참조\n');
  eq(r.lines.at(-2), '[표 3](#표-3) 참조', '참조 링크도 함께');
  eq(r.changed, 3, '바뀐 번호 수');
}
eq(R('표 1. 가\n\n표 2. 나\n\n표 2 를 보라\n', '표 3. 새\n\n표 1. 가\n\n표 2. 나\n\n표 2 를 보라\n').plain, 1, '링크가 아닌 글자는 세기만');
eq(R('표 1. 가\n\n표 2. 나\n\n표 2 를 보라\n', '표 3. 새\n\n표 1. 가\n\n표 2. 나\n\n표 2 를 보라\n').lines.at(-2), '표 2 를 보라', '링크가 아닌 글자는 고치지 않는다');
eq(R('표 1. 가\n\n표 2. 나\n\n[표 2](#표-2)\n', '표 1. 가\n\n[표 2](#표-2)\n').dangling, 1, '지운 표를 가리키는 참조');
eq(R('표 1. 가\n', '표 1. 가\n\n```\n표 9. 코드\n```\n').changed, 0, '코드 속 캡션은 세지 않는다');
eq(R('글\n', '글\n\n표 1. 처음\n').changed, 0, '처음 넣은 표');

// 참조 고르기
{
  const slug = (s) => s.trim().toLowerCase().replace(/[^\p{L}\p{M}\p{N}\p{Pc} -]/gu, '').replace(/ /g, '-');
  const t = refTargets(L('# 보고서\n\n## 수요 전망\n\n표 1. 매출\n\n## 수요 전망\n'), slug);
  eq(t.map((x) => x.text), ['[보고서](#보고서)', '[수요 전망](#수요-전망)', refLink('표', 1), '[수요 전망](#수요-전망-1)'], '참조 대상과 링크');
}

// 목차 줄과 쪽 나눔
eq(tocKind('[목차]'), 'toc', '목차 줄');
eq(tocKind('[TOC]'), 'toc', 'TOC 줄');
eq(tocKind('[표 목차]'), 'tables', '표 목차 줄');
eq(tocKind('[List of Figures]'), 'figures', '그림 목차 줄');
eq(tocKind('[목차] 보기'), null, '글이 붙으면 아니다');
eq(isPageBreak(PAGE_BREAK), true, '쪽 나눔 줄');
eq(isPageBreak('<div style="break-after: page"></div>'), true, 'break-after 도');
eq(isPageBreak('<div class="x"></div>'), false, '다른 div 는 아니다');

// 본문 인용
const BIB = '# 글\n\n본문 (김영삼, 2026) 과 (Kim & Lee, 2024).\n\n## 참고문헌\n\n- 김영삼 (2026). 철도 수요. 출판사.\n- Kim, Y., & Lee, S. (2024). Demand. *Journal*, 3(2).\n- Park, J., Choi, H., & Han, M. (2023). Supply.\n- World Bank. (2022). Report.\n- 이철수·박민수 (2025). 제목.\n\n## 부록\n\n- 문헌 아님\n';
eq(referencesIn(L(BIB)).map((r) => r.line), [7, 8, 9, 10, 11], '참고문헌 절의 문헌');
eq(citeOf('김영삼 (2026). 철도 수요. 출판사.').cite, '(김영삼, 2026)', '한국어 한 사람');
eq(citeOf('Kim, Y., & Lee, S. (2024). Demand.').cite, '(Kim & Lee, 2024)', '영어 두 사람');
eq(citeOf('Park, J., Choi, H., & Han, M. (2023). Supply.').cite, '(Park et al., 2023)', '영어 셋 이상');
eq(citeOf('World Bank. (2022). Report.').cite, '(World Bank, 2022)', '기관');
eq(citeOf('이철수·박민수 (2025). 제목.').cite, '(이철수·박민수, 2025)', '한국어 두 사람');
eq(citeOf('김영삼 외 (2021). 제목.').cite, '(김영삼 외, 2021)', '한국어 외');
eq(citeOf('Lee, S. et al. (2020). Title.').cite, '(Lee et al., 2020)', '영어 et al.');
eq(citeOf('제목만 있는 자료').cite, '(제목만 있는 자료)', '연도가 없으면 저자 자리 그대로');
eq(citedCount(L(BIB), '김영삼 (2026). 철도 수요.'), 1, '본문에 인용된 수');
eq(citedCount(L(BIB), 'Park, J., Choi, H., & Han, M. (2023). Supply.'), 0, '안 쓴 문헌');

return { n, fails };
