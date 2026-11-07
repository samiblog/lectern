// headstyle.js 의 계산 (rules_check 가 돌린다). m 은 모듈
const { headings, detect, preview, applyScheme, kindOf, STYLES, marksFrom, setOwnStyles, sample } = m;
let n = 0;
const fails = [];
const L = (s) => s.split('\n');
const slug = (s) => s.trim().toLowerCase().replace(/[^\p{L}\p{M}\p{N}\p{Pc} -]/gu, '').replace(/ /g, '-');
const eq = (got, want, name) => {
  n += 1;
  const show = (x) => (Array.isArray(x) ? x.join('\n') : JSON.stringify(x));
  if (show(got) !== show(want)) fails.push(`${name}: ${show(got)} ≠ ${show(want)}`);
};
const heads = (text, id) => applyScheme(L(text), id, slug).lines.filter((s) => s.startsWith('#'));

const DOC = '# 보고서\n\n요약 글\n\n## 개요\n\n글\n\n### 시장\n\n#### 가격\n\n##### 재고\n\n### 수요\n\n## 결론\n';
eq(heads(DOC, 'report'), ['# 보고서', '## Ⅰ. 개요', '### 1. 시장', '#### 가. 가격', '##### 1) 재고', '### 2. 수요', '## Ⅱ. 결론'], '보고서형');
eq(heads(DOC, 'number'), ['# 보고서', '## 1. 개요', '### 1.1 시장', '#### 1.1.1 가격', '##### 1.1.1.1 재고', '### 1.2 수요', '## 2. 결론'], '숫자형');
eq(heads(DOC, 'symbol'), ['# 보고서', '## □ 개요', '### ○ 시장', '#### - 가격', '##### · 재고', '### ○ 수요', '## □ 결론'], '기호형');
eq(heads(DOC, 'plain'), DOC.split('\n').filter((s) => s.startsWith('#')), '번호 없음은 그대로');
eq(heads(DOC, 'chapter'), ['# 보고서', '## 제1장 개요', '### 제1절 시장', '#### 1. 가격', '##### 가. 재고', '### 제2절 수요', '## 제2장 결론'], '장·절형');

// 왕복: 어느 모양에서든 돌아온다
eq(heads(DOC, 'paper'), ['# 보고서', '## Ⅰ. 개요', '### 1. 시장', '#### 1) 가격', '##### (1) 재고', '### 2. 수요', '## Ⅱ. 결론'], '논문형');
eq(heads(DOC, 'rule'), ['# 보고서', '## 제1장 개요', '### 제1조 시장', '#### ① 가격', '##### 1. 재고', '### 제2조 수요', '## 제2장 결론'], '규정형');
for (const from of ['report', 'number', 'symbol', 'chapter', 'paper', 'rule']) {
  const shaped = applyScheme(L(DOC), from, slug).lines;
  eq(detect(shaped), from, `${from} 을 알아본다`);
  eq(applyScheme(shaped, 'plain', slug).lines, L(DOC), `${from} 에서 번호 없음으로 돌아온다`);
  for (const to of ['report', 'number', 'symbol', 'chapter', 'paper', 'rule']) {
    eq(applyScheme(shaped, to, slug).lines, applyScheme(L(DOC), to, slug).lines, `${from} 에서 ${to} 로`);
  }
}
eq(detect(L(DOC)), 'plain', '번호가 없으면 번호 없음');

// 문서 방식은 본문으로 본다
const PROSE = '# 글\n\n## 개요\n\n첫 문단입니다.\n\n둘째 문단입니다.\n\n셋째 문단입니다.\n\n- 항목 하나\n';
const LIST = '# 글\n\n## 개요\n\n- 가격 상승\n- 재고 감소\n- 수요 증가\n\n요약 한 줄\n';
eq(kindOf(L(PROSE)), 'prose', '문단이 많으면 서술식');
eq(kindOf(L(LIST)), 'outline', '목록이 많으면 개조식');
eq(kindOf(applyScheme(L(PROSE), 'number', slug).lines), 'prose', '번호가 있어도 본문이 문장이면 서술식');
eq(kindOf(applyScheme(L(LIST), 'plain', slug).lines), 'outline', '번호가 없어도 본문이 목록이면 개조식');
eq(kindOf(L('# 글\n\n## □ 개요\n\n## □ 결론\n')), 'outline', '본문이 거의 없으면 머리글로');
eq(kindOf(L('# 글\n\n## 개요\n')), 'prose', '본문도 번호도 없으면 서술식');
eq(kindOf(L('# 글\n\n```\n- 코드\n- 코드\n- 코드\n- 코드\n```\n\n| 표 |\n|---|\n| 칸 |\n\n첫 문단\n\n둘째 문단\n\n셋째 문단\n')), 'prose', '코드와 표는 세지 않는다');
{
  const two = '# 글\n\n## Ⅰ. 서론\n\n### 1. 배경\n\n## Ⅱ. 본론\n';
  eq(detect(L(two), 'prose'), 'paper', '똑같이 맞으면 서술식에서는 논문형');
  eq(detect(L(two), 'outline'), 'report', '똑같이 맞으면 개조식에서는 보고서형');
}
eq(STYLES.prose.includes('chapter') && STYLES.outline.includes('report') && STYLES.prose.includes('number') && STYLES.outline.includes('number'), true, '숫자형은 양쪽에');

// 번호처럼 보이는 제목을 지우지 않는다
const LOOKS = '# 문서\n\n## 2026년 전망\n\n## 3D 프린터\n\n## 1.5배 성장\n\n## 3.14 원주율\n\n## - 빼기\n\n## A. 부록\n';
eq(detect(L(LOOKS)), 'plain', '연도와 소수는 번호가 아니다');
eq(heads(LOOKS, 'report'), ['# 문서', '## Ⅰ. 2026년 전망', '## Ⅱ. 3D 프린터', '## Ⅲ. 1.5배 성장', '## Ⅳ. 3.14 원주율', '## Ⅴ. - 빼기', '## Ⅵ. A. 부록'], '번호가 아닌 글은 지우지 않는다');
eq(heads('# 문서\n\n## 2026\n\n## 2027\n', 'number'), ['# 문서', '## 1. 2026', '## 2. 2027'], '숫자만 있는 제목');
eq(heads('# 문서\n\n## 1. 개요\n\n## 둘째\n\n## 셋째\n', 'report'), ['# 문서', '## Ⅰ. 개요', '## Ⅱ. 둘째', '## Ⅲ. 셋째'], '일부만 번호가 있어도 겹치지 않는다');

// 제목 수준
eq(heads('## 첫째\n\n### 안\n\n## 둘째\n', 'number'), ['## 1. 첫째', '### 1.1 안', '## 2. 둘째'], '문서 제목이 없으면 맨 위 수준부터');
eq(heads('# 하나\n\n# 둘\n\n## 안\n', 'number'), ['# 1. 하나', '# 2. 둘', '## 2.1 안'], '# 가 여럿이면 그것도 번호');
eq(heads('# 문서\n\n#### 깊은 곳\n\n## 얕은 곳\n', 'number'), ['# 문서', '#### 1.1.1 깊은 곳', '## 2. 얕은 곳'], '수준을 건너뛰어도');
eq(heads('글\n\n# 문서\n\n## 안\n', 'number'), ['# 문서', '## 1. 안'], '앞에 글이 있어도 # 하나는 제목');
eq(heads('# 문서\n', 'number'), ['# 문서'], '제목뿐이면 그대로');
eq(applyScheme(L('글뿐\n'), 'number', slug).changed, 0, '머리글이 없으면');

// 머리글이 아닌 것
const CODE = '---\ntitle: 글\n# 설정\n---\n\n# 문서\n\n```md\n## 코드 속\n```\n\n## 진짜\n\n~~~\n## 물결 속\n~~~\n';
eq(heads(CODE, 'number').filter((s) => s.includes('.')), ['## 1. 진짜'], '코드와 맨 앞 설정은 머리글이 아니다');
eq(applyScheme(L(CODE), 'number', slug).lines.includes('## 코드 속'), true, '코드 속은 그대로');
eq(heads('# 문서\n\n## 닫는 표시 ##\n', 'number'), ['# 문서', '## 1. 닫는 표시'], '닫는 # 는 뗀다');
eq(applyScheme(L('# 문서\n\n  ## 들여 쓴 제목\n'), 'number', slug).lines[2], '  ## 1. 들여 쓴 제목', '들여쓰기는 그대로');
eq(applyScheme(L('# 문서\n\n## **굵은** 제목\n\n본문 1. 번호\n'), 'report', slug).lines, L('# 문서\n\n## Ⅰ. **굵은** 제목\n\n본문 1. 번호\n'), '본문은 건드리지 않는다');

// 큰 번호
const many = ['# 문서', ...Array.from({ length: 15 }, (_, i) => `## 절${i + 1}`)].join('\n');
eq(heads(many, 'report')[13], '## 13. 절13', '로마 숫자를 넘으면 숫자로');
const deep = ['# 문서', '## 큰 절', ...Array.from({ length: 16 }, (_, i) => `### 작은${i}`).flatMap((s) => [s, '#### 안'])].join('\n');
eq(heads(deep, 'report').at(-1), '#### 가. 안', '아래 단계는 위 단계마다 다시 센다');

// 이 문서 안의 절 링크
const LINKS = '# 문서\n\n[개요로](#개요) [밖](다른.md#개요) [없는 곳](#없음)\n\n```\n[코드](#개요)\n```\n\n## 개요\n\n## 시장 현황\n\n[시장](#시장-현황)\n';
{
  const r = applyScheme(L(LINKS), 'number', slug);
  eq(r.lines[2], '[개요로](#1-개요) [밖](다른.md#개요) [없는 곳](#없음)', '절 링크를 함께 고친다');
  eq(r.lines[5], '[코드](#개요)', '코드 속 링크는 그대로');
  eq(r.lines.at(-2), '[시장](#2-시장-현황)', '뒤의 링크도');
  eq([r.changed, r.links], [2, 2], '센 수');
}
eq(preview(L(DOC), 'report', 3).map((x) => [x.depth, x.text]), [[1, 'Ⅰ. 개요'], [2, '1. 시장'], [3, '가. 가격']], '미리보기');
eq(headings(L(DOC)).map((h) => h.depth), [0, 1, 2, 3, 4, 2, 1], '단계');

// 이 문서를 스타일로: 머리글에서 틀 글자를 뽑는다
eq(marksFrom(applyScheme(L(DOC), 'report', slug).lines), ['{I}.', '{1}.', '{가}.', '{1})'], '보고서형을 뽑는다');
eq(marksFrom(applyScheme(L(DOC), 'chapter', slug).lines), ['제{1}장', '제{1}절', '{1}.', '{가}.'], '장·절형을 뽑는다');
eq(marksFrom(applyScheme(L(DOC), 'number', slug).lines), ['{1}.', '{path}', '{path}', '{path}'], '숫자형을 뽑는다');
eq(marksFrom(applyScheme(L(DOC), 'symbol', slug).lines), ['□', '○', '-', '·'], '기호형을 뽑는다');
eq(marksFrom(L('# 문서\n\n## ① 개요\n\n### (가) 배경\n\n#### ※ 참고\n')), ['{①}', '({가})', '※'], '여러 모양');
eq(marksFrom(L('# 문서\n\n## 제1편 총칙\n\n### 제2조 목적\n')), ['제{1}편', '제{1}조'], '편과 조');
eq(marksFrom(L(DOC)), [], '번호가 없으면 없다');
eq(marksFrom(L('# 문서\n\n## 2026년 전망\n\n## 3.14 원주율\n')).join(), '{path}', '첫 번호를 쓴 것은 그대로 본다');
eq(marksFrom(L('# 문서\n\n## 개요\n\n### 1. 배경\n')), ['', '{1}.'], '첫 단계에 번호가 없으면 비운다');

// 내 스타일
setOwnStyles([{ name: '회사 규정', kind: 'prose', marks: ['제{1}조', '{①}', '{1}.'] }]);
const OWN = '# 규정\n\n## 목적\n\n### 범위\n\n#### 대상\n\n### 정의\n\n## 시행\n';
eq(heads(OWN, 'own:회사 규정'), ['# 규정', '## 제1조 목적', '### ① 범위', '#### 1. 대상', '### ② 정의', '## 제2조 시행'], '내 스타일을 입힌다');
{
  const shaped = applyScheme(L(OWN), 'own:회사 규정', slug).lines;
  eq(detect(shaped), 'own:회사 규정', '내 스타일을 알아본다');
  eq(applyScheme(shaped, 'plain', slug).lines, L(OWN), '내 스타일에서 번호 없음으로');
  eq(applyScheme(shaped, 'report', slug).lines, applyScheme(L(OWN), 'report', slug).lines, '내 스타일에서 다른 모양으로');
}
eq(sample('own:회사 규정'), '제1조  ①  1.', '목록의 보기 글자');
eq(sample('symbol'), '□  ○  -  ·', '기본 모양의 보기 글자');
eq(sample('number'), '1.  1.1  1.1.1  1.1.1.1', '숫자형의 보기 글자');
eq(heads('# 문서\n\n## 가\n\n### 나\n', 'own:없는 스타일'), ['# 문서', '## 가', '### 나'], '없는 모양은 번호 없음');
setOwnStyles([{ name: '빈칸', kind: 'outline', marks: ['', '{1}.'] }]);
eq(heads('# 문서\n\n## 큰 절\n\n### 작은 절\n', 'own:빈칸'), ['# 문서', '## 큰 절', '### 1. 작은 절'], '비운 단계는 번호 없이');
setOwnStyles([]);
return { n, fails };
