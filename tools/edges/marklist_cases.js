// marklist.js 의 블록 규칙 (D192 — rules_check.mjs 가 돈다. m: marklist.js, 끝에서 {n, fails} 를 돌려준다).
// 원문 → 그린 html 의 짜임: 묶음·항목·수준, 묶음이 되지 않는 것, 문서 점검이 묶음 안의 줄을 목록으로 읽지 않는지.
const { marklistPlugin, markOf } = m;
const md = window.markdownit({ html: true, breaks: true }).use(marklistPlugin);
let n = 0;
const fails = [];
const eq = (got, want, name) => {
  n += 1;
  if (JSON.stringify(got) !== JSON.stringify(want)) fails.push(`${name}: ${JSON.stringify(got)} ≠ ${JSON.stringify(want)}`);
};
/** 항목마다 [수준, 글] — 묶음이 없으면 [] */
const items = (src) => [...md.render(src).matchAll(/<p class="lec-mark lec-lv(\d)">([\s\S]*?)<\/p>/g)].map((x) => [Number(x[1]), x[2].replace(/<br>\n/g, '/')]);
const html = (src) => md.render(src).trim();

eq(items('ㅁ 가\n ㅇ 나\n  - 다\n   · 라'), [[0, 'ㅁ 가'], [1, 'ㅇ 나'], [2, '- 다'], [3, '· 라']], 'ㅁ > ㅇ > - > · 의 수준');
eq(items('□ 가\n○ 나\n- 다\n· 라'), [[0, '□ 가'], [1, '○ 나'], [2, '- 다'], [3, '· 라']], '□·○ 도 같은 차례 (앞 빈칸은 보지 않는다)');
eq(items('ㅇ 가\n- 나\nㅇ 다'), [[0, 'ㅇ 가'], [1, '- 나'], [0, 'ㅇ 다']], '쓴 차례만 센다 — ○ 와 - 만 쓰면 ○ 가 맨 위');
eq(items('ㅁ 가\n\nㅇ 나'), [[0, 'ㅁ 가'], [1, 'ㅇ 나']], '빈 줄로 떨어진 묶음도 문서 전체의 차례로');
eq(items('ㅇ 가\n① 나\n2. 다\n※ 라\n- 마'), [[0, 'ㅇ 가'], [1, '① 나'], [1, '2. 다'], [1, '※ 라'], [1, '- 마']], '차례에 없는 머리 글자는 위 항목의 한 수준 아래');
eq(items('ㅇ 가\n이어 쓴 줄\n- 나'), [[0, 'ㅇ 가/이어 쓴 줄'], [1, '- 나']], '머리 글자가 없는 줄은 위 항목에 이어 쓴 줄');
eq(items('· 하나\n· 둘'), [[0, '· 하나'], [0, '· 둘']], '· 로도 묶음을 연다');
eq(html('설명\nㅇ 가'), '<p>설명</p>\n<div class="lec-marklist">\n<p class="lec-mark lec-lv0">ㅇ 가</p>\n</div>', '문단을 끊고 묶음이 시작한다');
eq(items('ㅇ 가\n# 제목'), [[0, 'ㅇ 가']], '제목에서 끝난다');
eq(items('ㅇ 가\n```\n코드\n```'), [[0, 'ㅇ 가']], '코드 블록에서 끝난다');
// 한글 문서에서 붙여 넣은 글·Claude 가 굵게 쓴 머리 글자
eq(items('□\u3000추진 배경\n\u3000○\u3000생산성\n\u3000\u3000－\u3000제조업'), [[0, '□\u3000추진 배경'], [1, '○\u3000생산성'], [2, '－\u3000제조업']], '전각 빈칸의 들여쓰기·머리 글자 뒤의 전각 빈칸, 전각 붙임표');
eq(items('**□ 추진 배경**\n**ㅇ 생산성**'), [[0, '<strong>□ 추진 배경</strong>'], [1, '<strong>ㅇ 생산성</strong>']], '굵게 쓴 머리 글자 (**□ 제목**)');
eq(items('□ 가\n**ㅇ** 나\n__-__ 다'), [[0, '□ 가'], [1, '<strong>ㅇ</strong> 나'], [2, '<strong>-</strong> 다']], '머리 글자만 굵게 쓴 줄 (**ㅇ** 내용)');
// 묶음이 되지 않는 것
eq(items('- 가\n- 나'), [], "'-' 로 시작하면 Markdown 목록");
eq(html('- 가\n  ㅇ 나'), '<ul>\n<li>가<br>\nㅇ 나</li>\n</ul>', '목록 항목 안의 줄은 그대로 (촘촘한 목록의 줄바꿈)');
eq(items('ㅁ제목'), [], '빈칸 없이 붙은 ㅁ 는 글머리가 아니다');
eq(items('○○ 기관의 보고서'), [], "'○○' 는 글머리가 아니다");
eq(html('□ 제목\n---'), '<h2>□ 제목</h2>', '바로 아래 --- 면 제목(setext)');
eq(items('    ㅇ 들여 쓴 코드'), [], '네 칸 들여 쓰면 코드');
eq(html('> ㅇ 가\n> - 나').includes('<blockquote>\n<div class="lec-marklist">'), true, '인용 안에서도');
// 줄 범위 — 한 줄 편집·줄 단위가 항목마다 (sourceLines 가 map 으로 단다)
const toks = md.parse('ㅁ 가\n ㅇ 나\n 이어\n- 다', {});
eq(toks.filter((tk) => tk.type === 'lec_mark_open').map((tk) => tk.map), [[0, 1], [1, 3], [3, 4]], '항목의 줄 범위 (이어 쓴 줄까지)');
eq(toks.find((tk) => tk.type === 'lec_marklist_open').map, [0, 4], '묶음의 줄 범위');
// Lectern 슬라이드에서는 하지 않는다
eq(md.render('ㅁ 가\nㅇ 나', { deck: {} }).includes('lec-mark'), false, '슬라이드에서는 하지 않는다');
// markOf
eq(markOf('ㅁ 가')?.rank, 0, 'ㅁ 의 차례 0');
eq(markOf('◦ 가')?.rank, 1, '◦ 의 차례 1');
eq(markOf('– 가')?.rank, 2, '– 의 차례 2');
eq(markOf('ㆍ 가')?.rank, 3, 'ㆍ 의 차례 3');
eq(markOf('① 가')?.rank, -1, '① 은 차례 밖');
eq(markOf('가나다'), null, '머리 글자 없음');
return { n, fails };
