// doclint.js 의 점검 (D190 — rules_check.mjs 가 돈다. m: doclint.js, 끝에서 {n, fails, runs, problems} 를 돌려준다).
// 표: 규칙마다 걸리는 문서와 안 걸리는 문서, 고친 결과. 임의 시험: 고치기 뒤 그 점검은 사라지고 다른 점검이 새로 생기지 않으며 글은 그대로.
const { lintDoc } = m;
let n = 0;
const fails = [];
const L = (s) => s.split('\n');
const slug = (text) => text.trim().toLowerCase().replace(/[^\p{L}\p{M}\p{N}\p{Pc} -]/gu, '').replace(/ /g, '-');   // markdown.js 의 slugify
const lint = (s, style = false) => lintDoc(L(s), { slug, style });
const eq = (got, want, name) => {
  n += 1;
  const show = (x) => JSON.stringify(x);
  if (show(got) !== show(want)) fails.push(`${name}: ${show(got)} ≠ ${show(want)}`);
};
/** 그 code 의 줄들 */
const at = (s, code, style = false) => lint(s, style).filter((x) => x.code === code).map((x) => x.line);
/** 그 code 의 첫 곳을 고친 글 (고치기가 없으면 null) */
const fixed = (s, code, style = false) => {
  const it = lint(s, style).find((x) => x.code === code);
  const r = it?.fix?.apply(L(s));
  return r ? r.join('\n') : null;
};

// ---- A. 깨진 틀 ----
eq(at('---\ntitle: a\nstatus: b\n\n# 제목\n\n글\n', 'front-open'), [1], '닫는 --- 가 없는 머리 설정');
eq(fixed('---\ntitle: a\nstatus: b\n\n# 제목\n\n글\n', 'front-open'), '---\ntitle: a\nstatus: b\n---\n\n# 제목\n\n글\n', '— 키 줄 뒤에 닫는 ---');
eq(at('---\n\n글\n', 'front-open'), [], '맨 앞의 가로줄은 머리 설정이 아니다');
eq(at('# a\n\n```js\nx = 1\n\n## b\n\n글\n', 'fence-open'), [3], '닫지 않은 코드 블록');
eq(fixed('# a\n\n```js\nx = 1\n\n## b\n\n글\n', 'fence-open'), '# a\n\n```js\nx = 1\n```\n\n## b\n\n글\n', '— 다음 제목 앞에 닫는 줄');
eq(fixed('글\n\n- 항목\n  ~~~~\n  코드\n', 'fence-open'), '글\n\n- 항목\n  ~~~~\n  코드\n  ~~~~\n', '— 같은 글자·같은 들여쓰기로, 문서 끝');
eq(at('$$\nx\n\n글\n', 'math-open'), [1], '닫지 않은 수식 블록');
eq(at('| a | b |\n|---|\n| 1 | 2 |\n', 'table-sep'), [1], '머리행과 구분 줄의 칸 수가 다르면 표가 되지 않는다');
eq(at('| a | b |\n|---|---|\n| 1 |\n| 1 | 2 | 3 |\n| 1 | 2 |\n', 'table-cells'), [3, 4], '칸 수가 다른 행');
eq(at('| a | `x\\|y` |\n|---|---|\n| 1 | 2 |\n', 'table-cells'), [], '\\| 와 코드 안의 | 는 칸 나눔이 아니다');
eq(at('| a | b |\n|---|---|\n| Ctrl+\\` 키 | 터미널 |\n', 'table-cells'), [], '막은 백틱(\\`)은 코드의 시작이 아니다');
eq(at('글\n\n    - 들여 쓴 항목\n', 'indent-code'), [3], '4칸 넘게 들여 쓴 항목은 코드 블록');
eq(at('글\n\n    x = 1\n', 'indent-code'), [], '들여 쓴 코드는 그대로');
eq(at('설명 글\n2. 둘째\n3. 셋째\n', 'list-glued'), [2], '2. 로 시작한 번호가 문단에 붙음');
eq(fixed('설명 글\n2. 둘째\n3. 셋째\n', 'list-glued'), '설명 글\n\n2. 둘째\n3. 셋째\n', '— 윗줄과 띄운다 (번호 그대로)');
eq(fixed('- a\n  글\n  2. x\n', 'list-glued'), '- a\n  글\n  1. x\n', '— 목록 안이면 1 부터');
eq(at('글\n2024. 3. 5. 기준\n', 'list-glued'), [], '날짜는 번호가 아니다');
eq(at('- a\n- b\n* c\n* d\n', 'bullet-mixed'), [3], '글머리표가 바뀌면 목록이 둘');
eq(fixed('- a\n- b\n* c\n* d\n', 'bullet-mixed'), '- a\n- b\n- c\n- d\n', '— 앞 글머리표로');
eq(fixed('1. a\n2) b\n3) c\n', 'bullet-mixed'), '1. a\n2. b\n3. c\n', '— 번호의 구분 글자도');
eq(at('- a\n\n글\n\n* b\n', 'bullet-mixed'), [], '사이에 글이 있으면 다른 목록이다');
eq(at('- a\n  - x\n* b\n', 'bullet-mixed'), [3], '하위 항목을 지나서도');
eq(at('글\n---\n', 'setext'), [2], '글 바로 아래의 --- 는 제목');
eq(fixed('글\n---\n', 'setext'), '글\n\n---\n', '— 빈 줄을 넣어 가로줄로');
eq(at('글\n\n---\n', 'setext'), [], '띄운 --- 는 가로줄');
eq(at('> [!NOTES]\n> 글\n', 'callout-kind'), [1], '모르는 강조글 종류');
eq(fixed('> [!NOTES]\n> 글\n', 'callout-kind'), '> [!NOTE]\n> 글\n', '— 가까운 종류로');
eq(fixed('> [!warn]\n> 글\n', 'callout-kind'), '> [!WARNING]\n> 글\n', '— 앞부분만 쓴 것도');
eq(lint('> [!FOO]\n> 글\n').find((x) => x.code === 'callout-kind')?.fix, undefined, '— 가까운 것이 없으면 고치기 없음');
eq(at('> [!TIP]\n> 글\n', 'callout-kind'), [], '아는 종류는 그대로');
eq(at('글[^1]\n', 'note-missing'), [1], '내용이 없는 주');
eq(at('글\n\n[^1]: 주\n', 'note-unused'), [3], '쓰지 않는 주의 내용');
eq(lint('글[^1] `[^x]`\n\n[^1]: 주\n').length, 0, '짝이 맞는 주, 코드 안의 [^x] 는 주가 아니다');
eq(at('# 가\n\n[가로](#가)\n[없음](#없는-절)\n', 'link-anchor'), [4], '없는 절로 가는 링크');
eq(at('표 1. 값\n\n| a |\n|---|\n| 1 |\n\n[표 1](#표-1) [표 2](#표-2)\n', 'link-anchor'), [7], '없는 캡션으로 가는 링크');
eq(at('<a id="here"></a>\n\n[여기](#here)\n', 'link-anchor'), [], 'HTML 의 id 로 가는 링크');

// ---- B. 보고서의 틀 ----
eq(at('# a\n\n## b\n\n글\n\n#### c\n\n글\n', 'head-skip'), [7], '제목 수준 건너뜀');
eq(at('# a\n\n글\n\n# b\n\n글\n', 'head-title'), [5], '제목 1 이 둘');
eq(at('# a\n\n## b\n\n## c\n\n글\n', 'head-empty'), [3], '글이 없는 절');
eq(at('# a\n\n## b\n\n### c\n\n글\n', 'head-empty'), [], '하위 절만 있는 절은 빈 절이 아니다');
eq(at('# a\n\n## 개요\n\n글\n\n## 개요\n\n글\n', 'head-same'), [7], '같은 제목');
const NUMBERED = '# 문서\n\n## 1. 가\n\n글\n\n## 2. 나\n\n글\n\n## 4. 다\n\n글\n';
eq(at(NUMBERED, 'head-number'), [11], '제목 번호가 차례와 다름');
eq(fixed(NUMBERED, 'head-number'), NUMBERED.replace('## 4. 다', '## 3. 다'), '— 다시 매긴다');
eq(at('# 문서\n\n## 1. 가\n\n글\n\n## 2. 나\n\n글\n\n## 참고 자료\n\n글\n\n## 3. 다\n\n글\n', 'head-number'), [], '번호 없는 절은 세지 않는다 (번호를 붙이라고 하지 않는다)');
eq(at('# 문서\n\n## 1. 가\n\n글\n\n## 2. 나\n\n글\n\n## 1-1. 다른 꼴\n\n글\n\n## 3. 다\n\n글\n', 'head-number'), [], '다른 꼴의 번호도');
const CAPS = '표 1. a\n\n| a |\n|---|\n| 1 |\n\n표 3. b\n\n| a |\n|---|\n| 1 |\n\n[표 3](#표-3)\n';
eq(at(CAPS, 'caption-order'), [7], '캡션 번호가 건너뜀');
eq(fixed(CAPS, 'caption-order'), CAPS.replace('표 3. b', '표 2. b').replace('[표 3](#표-3)', '[표 2](#표-2)'), '— 차례대로, 참조 링크도');
const T = (k) => `| ${k} |\n|---|\n| 1 |\n`;
const NOCAP = `표 1. a\n\n${T('a')}\n표 2. b\n\n${T('b')}\n글\n\n${T('c')}`;
eq(at(NOCAP, 'caption-missing'), [15], '표 대부분에 캡션을 쓰는 문서의 캡션 없는 표');
eq(fixed(NOCAP, 'caption-missing'), `표 1. a\n\n${T('a')}\n표 2. b\n\n${T('b')}\n글\n\n표 3.\n\n${T('c')}`, '— 빈 캡션을 차례 번호로');
eq(fixed(`${T('c')}\n표 1. a\n\n${T('a')}\n표 2. b\n\n${T('b')}`, 'caption-missing'), `표 1.\n\n${T('c')}\n표 2. a\n\n${T('a')}\n표 3. b\n\n${T('b')}`, '— 앞에 넣으면 뒤 번호를 민다');
eq(at(`표 1. a\n\n${T('a')}\n${T('b')}\n${T('c')}`, 'caption-missing'), [], '캡션이 절반이 안 되면 그 문서의 양식이 아니다');
eq(at('그림 1. x\n\n![a](a.png)\n\n그림 2. y\n\n![b](b.png)\n\n글\n\n![c](c.png)\n', 'caption-missing'), [11], '캡션 없는 그림');
eq(at('![a](a.png)\n\n그림 1. x\n\n![b](b.png)\n\n그림 2. y\n\n![c](c.png)\n', 'caption-missing'), [1], '그림 아래 캡션이 다음 그림의 것이면 그 그림은 캡션이 없다');
eq(at('| a |\n|---|\n| 1 |\n\n![b](b.png)\n', 'caption-missing'), [], '캡션을 쓰지 않는 문서는 그대로');
const NOSRC = `표 1. a\n\n${T('a')}\n자료: 통계청\n\n표 2. b\n\n${T('b')}\n자료: 한은\n\n표 3. c\n\n${T('c')}\n글\n`;
eq(at(NOSRC, 'source-missing'), [19], '자료 줄을 대부분 쓰는 문서의 자료 없는 표');
eq(fixed(NOSRC, 'source-missing'), NOSRC.replace('| 1 |\n\n글', '| 1 |\n\n자료: \n\n글'), "— 빈 '자료:' 줄");
eq(at('- a\n- b\n\n- c\n', 'list-loose-mixed'), [1], '일부만 띄운 목록');
eq(at('- a\n\n- b\n\n- c\n', 'list-loose-mixed'), [], '모두 띄운 목록');
eq(at('- a\n\n- b\n\n- c\n- d\n', 'list-loose-mixed'), [], '대부분 띄운 목록은 일부러 띄운 것');
eq(at('# 업무\n\n## 할 일\n\n## 일정\n', 'head-empty'), [3, 5], '글이 없는 절');
eq(lintDoc(L('# 업무\n\n## 할 일\n\n## 일정\n'), { slug, emptyOk: true }).filter((x) => x.code === 'head-empty').length, 0, '— 업무 카드(WORK.md)는 보지 않는다');
eq(lint('---\nmarp: true\n---\n\n# a\n\n## b\n\n## b\n'), [], 'Lectern 슬라이드는 보지 않는다');

// ---- C. 글버릇 (style) ----
const LONG = `${'가'.repeat(700)}\n`;
eq(at(LONG, 'long-para'), [], '기본은 글버릇을 보지 않는다');
eq(at(LONG, 'long-para', true), [1], '긴 문단');
eq(at(LONG, 'long-sentence', true), [1], '긴 문장');
eq(at(`| a |\n|---|\n| ${'가'.repeat(70)} |\n`, 'long-cell', true), [3], '긴 표의 칸');
eq(fixed('글  \n다음\n', 'hard-break', true), '글\n다음\n', '줄 끝 공백 두 칸 걷기');
eq(fixed('- a\n\t- b\n', 'tab-indent', true), '- a\n    - b\n', '탭을 칸으로');
eq(fixed('# 제목.\n\n글\n', 'head-punct', true), '# 제목\n\n글\n', '제목 끝 마침표');
eq(at('## 1.\n\n글\n', 'head-punct', true), [], '번호만 있는 제목');
eq(lint('a\n').find((x) => x.code === 'long-para'), undefined, '짧은 글');
// 그사이 문서가 바뀌었으면 고치지 않는다
{
  const it = lint('글\n---\n').find((x) => x.code === 'setext');
  eq(it.fix.apply(L('글\n----\n')), null, '그 줄이 바뀌었으면 고치지 않는다');
}

// ---- 임의 시험: 결함을 넣은 문서에서 고치기마다 ----
let seed = globalThis.LINT_FUZZ_SEED ?? 190;
const rand = () => {
  seed = (seed + 0x6D2B79F5) | 0;
  let x = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
  return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
};
const rnd = (k) => Math.floor(rand() * k);
const pick = (a) => a[rnd(a.length)];
let uid = 0;
const w = () => `w${++uid}`;
const BLOCKS = [
  () => [`## ${rnd(3) ? '' : `${rnd(4) + 1}. `}${w()}`],
  () => [`### ${w()}`],
  () => [w(), ...(rnd(3) ? [] : [w()])],
  () => [`${w()}`, `${rnd(2) + 2}. ${w()}`],
  () => [`- ${w()}`, `${pick(['-', '*'])} ${w()}`, ...(rnd(2) ? ['', `- ${w()}`] : [])],
  () => [`1. ${w()}`, `2${pick(['.', ')'])} ${w()}`],
  () => [`> [!${pick(['NOTE', 'NOTES', 'WARN', 'TIP'])}]`, `> ${w()}`],
  () => [...(rnd(2) ? [`표 ${rnd(4) + 1}. ${w()}`, ''] : []), `| ${w()} | ${w()} |`, '|---|---|', `| ${w()} |${rnd(2) ? ` ${w()} |` : ''}`, ...(rnd(2) ? ['', `자료: ${w()}`] : [])],
  () => [...(rnd(2) ? [`그림 ${rnd(3) + 1}. ${w()}`, ''] : []), `![${w()}](${w()}.png)`],
  () => [`${w()}[^${rnd(3) + 1}]`],
  () => [`[^${rnd(3) + 1}]: ${w()}`],
  () => [`[${w()}](#${pick(['없는-곳', 'w1'])})`],
  () => [w(), '---'],
  () => ['```', w(), ...(rnd(5) ? ['```'] : [])],
];
const words = (lines) => (lines.join('\n').match(/w\d+/g) || []).sort().join(',');
const count = (list) => list.reduce((m, x) => m.set(x.code, (m.get(x.code) ?? 0) + 1), new Map());
// 고친 뒤 새로 생겨도 되는 점검 — 갈린 목록을 이으면 띄운 정도가 섞일 수 있다, 닫은 코드 블록 뒤의 글은 이제 점검된다
// 밑줄 제목을 가로줄로 바꾸면 그 제목이 없어져 아래 제목의 수준이 건너뛸 수 있다
const MAY_APPEAR = { 'same-marker': ['list-loose-mixed'], 'close-fence': null, 'blank-before': ['head-empty', 'list-glued', 'bullet-mixed', 'list-loose-mixed', 'head-skip'] };
const problems = [];
let runs = 0;
for (let d = 0; d < (globalThis.LINT_FUZZ_DOCS ?? 300); d++) {
  const lines = ['# 문서', ''];
  for (let k = 0, all = 3 + rnd(8); k < all; k++) lines.push(...pick(BLOCKS)(), '');
  const before = lintDoc(lines, { slug, style: true });
  for (const it of before) {
    if (!it.fix) continue;
    runs += 1;
    const next = it.fix.apply(lines.slice());
    const show = `${it.line}:${it.code}\n${lines.join('\n')}`;
    if (!next) { problems.push(`고치지 못함 ${show}`); continue; }
    if (words(next) !== words(lines)) { problems.push(`글이 바뀜 ${show}`); continue; }
    const a = count(before);
    const b = count(lintDoc(next, { slug, style: true }));
    if ((b.get(it.code) ?? 0) >= (a.get(it.code) ?? 0)) problems.push(`점검이 남음 ${show}\n→\n${next.join('\n')}`);
    const may = MAY_APPEAR[it.fix.kind];
    if (may === null) continue;
    for (const [code, k] of b) if (k > (a.get(code) ?? 0) && !(may ?? []).includes(code)) problems.push(`새 점검 ${code} ← ${show}\n→\n${next.join('\n')}`);
  }
}
return { n, fails, runs, problems: globalThis.LINT_ALL ? problems : problems.slice(0, 8) };
