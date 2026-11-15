// inlinefmt.js 의 계산 점검 (rules_check.mjs 가 돌린다 — m: inlinefmt.js, d: docops.js. 끝에서 {n, fails} 를 돌려준다).
const { spansOf, applyFormat, clearFormats, wholeOf, stripFormat, wrapWhole, nextValue, paintOf, MARK_COLORS, TEXT_COLORS } = m;
const { formatLines } = d;
let n = 0;
const fails = [];
const eq = (got, want, name) => {
  n += 1;
  const show = (x) => JSON.stringify(x);
  if (show(got) !== show(want)) fails.push(`${name}: ${show(got)} ≠ ${show(want)}`);
};
/** '[' 와 ']' 로 고른 곳을 적는다 — '가 [나] 다'. 하나뿐이면('|') 커서 */
const sel = (s) => {
  if (s.includes('|')) return [s.replace('|', ''), s.indexOf('|'), s.indexOf('|')];
  const a = s.indexOf('[');
  const b = s.indexOf(']') - 1;
  return [s.replace('[', '').replace(']', ''), a, b];
};
const show = (r) => (r.a === r.b ? `${r.text.slice(0, r.a)}|${r.text.slice(r.a)}` : `${r.text.slice(0, r.a)}[${r.text.slice(r.a, r.b)}]${r.text.slice(r.b)}`);
const fmt = (s, kind, value) => show(applyFormat(...sel(s), kind, value));
const kinds = (s) => spansOf(s).map((x) => `${x.kind}${x.value ? `:${x.value}` : ''}=${s.slice(x.a, x.b)}`);

// 읽기
eq(kinds('가 **나** *다* ~~라~~ `마` 끝'), ['bold=나', 'italic=다', 'strike=라', 'code=마'], '네 가지');
eq(kinds('***둘 다***'), ['bold=*둘 다*', 'italic=둘 다'], '굵고 기울임');
eq(kinds('`**코드 안**` 밖'), ['code=**코드 안**'], '코드 안은 서식이 아니다');
eq(kinds('2 * 3 * 4 와 a ** b'), [], '띄어 쓴 별표는 서식이 아니다');
eq(kinds('<mark>가</mark> <mark class="green">나</mark> <span style="color:red">다</span>'), ['mark=가', 'mark:green=나', 'color:red=다'], '형광펜과 글자색');
eq(kinds('<span style="color:#abc">가</span> <mark class="x">나</mark>'), [], '정한 색이 아니면 읽지 않는다');
eq(kinds('**가** 나 **다**'), ['bold=가', 'bold=다'], '두 군데');
eq(spansOf('가 **나** 다')[0], { kind: 'bold', value: '', oa: 2, a: 4, b: 5, cb: 7 }, '범위');

// 감싸고 풀기
eq(fmt('가 [나] 다', 'bold'), '가 **[나]** 다', '굵게');
eq(fmt('가 **[나]** 다', 'bold'), '가 [나] 다', '다시 하면 푼다');
eq(fmt('가 [**나**] 다', 'bold'), '가 [나] 다', '표시까지 골라도 푼다');
eq(fmt('가 **나 [다] 라** 마', 'bold'), '가 나 [다] 라 마', '굵은 글의 일부를 골라도 그 굵게를 푼다');
eq(fmt('가 [ 나 ] 다', 'bold'), '가  **[나]**  다', '고른 글 앞뒤의 공백은 표시 밖에');
eq(fmt('가 [나] 다', 'italic'), '가 *[나]* 다', '기울임');
eq(fmt('가 *[나]* 다', 'italic'), '가 [나] 다', '기울임 풀기');
eq(fmt('가 **[나]** 다', 'italic'), '가 ***[나]*** 다', '굵은 글에 기울임을 더한다');
eq(fmt('가 ***[나]*** 다', 'italic'), '가 **[나]** 다', '기울임만 푼다');
eq(fmt('가 ***[나]*** 다', 'bold'), '가 *[나]* 다', '굵게만 푼다');
eq(fmt('가 [나] 다', 'strike'), '가 ~~[나]~~ 다', '취소선');
eq(fmt('가 ~~[나]~~ 다', 'strike'), '가 [나] 다', '취소선 풀기');
eq(fmt('가 [나] 다', 'code'), '가 `[나]` 다', '코드');
eq(fmt('가 `[나]` 다', 'code'), '가 [나] 다', '코드 풀기');
eq(fmt('[가] 나', 'bold'), '**[가]** 나', '줄 맨 앞');
eq(fmt('가 [나]', 'bold'), '가 **[나]**', '줄 맨 끝');

// 커서만 있을 때 — 이어 쓰기
eq(fmt('가 | 다', 'bold'), '가 **|** 다', '빈 표시 사이에 커서');
eq(fmt('가 **나|** 다', 'bold'), '가 나| 다', '굵은 글 안의 커서는 푼다');
eq(fmt('가 **|나** 다', 'bold'), '가 |나 다', '안의 글 맨 앞의 커서도');
eq(fmt('가 **나** |다', 'bold'), '가 **나** **|**다', '굵은 글 밖이면 새로');

// 형광펜 — 색이 차례로
eq(fmt('가 [나] 다', 'mark'), '가 <mark>[나]</mark> 다', '노랑부터');
eq(fmt('가 <mark>[나]</mark> 다', 'mark'), '가 <mark class="green">[나]</mark> 다', '노랑 → 초록');
eq(fmt('가 <mark class="green">[나]</mark> 다', 'mark'), '가 <mark class="pink">[나]</mark> 다', '초록 → 분홍');
eq(fmt('가 <mark class="pink">[나]</mark> 다', 'mark'), '가 <mark class="blue">[나]</mark> 다', '분홍 → 하늘');
eq(fmt('가 <mark class="blue">[나]</mark> 다', 'mark'), '가 [나] 다', '마지막 색 다음은 푼다');
eq(fmt('가 [<mark>나</mark>] 다', 'mark'), '가 <mark class="green">[나]</mark> 다', '표시까지 골라도 다음 색');
eq(fmt('가 <mark>나|</mark> 다', 'mark'), '가 <mark class="green">나|</mark> 다', '커서만 있어도 다음 색');
eq(fmt('가 [나] 다', 'mark', 'pink'), '가 <mark class="pink">[나]</mark> 다', '메뉴: 그 색으로');
eq(fmt('가 <mark>[나]</mark> 다', 'mark', 'pink'), '가 <mark class="pink">[나]</mark> 다', '메뉴: 다른 색으로 바꾼다');
eq(fmt('가 <mark class="pink">[나]</mark> 다', 'mark', 'pink'), '가 [나] 다', '메뉴: 같은 색이면 푼다');
eq(fmt('가 <mark class="pink">[나]</mark> 다', 'mark', ''), '가 <mark>[나]</mark> 다', '메뉴: 노랑으로');

// 글자색
eq(fmt('가 [나] 다', 'color'), '가 <span style="color:red">[나]</span> 다', '빨강부터');
eq(fmt('가 <span style="color:red">[나]</span> 다', 'color'), '가 <span style="color:blue">[나]</span> 다', '빨강 → 파랑');
eq(fmt('가 <span style="color:blue">[나]</span> 다', 'color'), '가 <span style="color:green">[나]</span> 다', '파랑 → 초록');
eq(fmt('가 <span style="color:green">[나]</span> 다', 'color'), '가 <span style="color:goldenrod">[나]</span> 다', '초록 → 노랑');
eq(fmt('가 <span style="color:goldenrod">[나]</span> 다', 'color'), '가 [나] 다', '노랑 다음은 푼다');
eq(fmt('가 <span style="color:red">[나]</span> 다', 'bold'), '가 <span style="color:red">**[나]**</span> 다', '색 안에 굵게');
eq(fmt('가 **[나]** 다', 'color'), '가 **<span style="color:red">[나]</span>** 다', '굵게 안에 색');
eq(MARK_COLORS.length === 4 && TEXT_COLORS.length === 4, true, '색은 네 가지씩');

// 모두 풀기
eq(show(clearFormats(...sel('가 **<mark>[나]</mark>** 다'))), '가 [나] 다', '겹친 서식을 모두');
eq(show(clearFormats(...sel('[**가** 와 *나* 와 ~~다~~]'))), '[가 와 나 와 다]', '고른 곳에 걸친 것 모두');
eq(show(clearFormats(...sel('**가** [나] **다**'))), '**가** [나] **다**', '걸치지 않은 것은 그대로');
eq(show(clearFormats(...sel('가 **나|** 다'))), '가 나| 다', '커서를 감싼 것');

// 줄 통째
eq(wholeOf('  **가 나**  ', 'bold') != null, true, '통째로 굵다');
eq(wholeOf('**가** 나 **다**', 'bold'), null, '두 군데는 통째가 아니다');
eq(stripFormat('**가** 나 **다**', 'bold'), '가 나 다', '걷기');
eq(wrapWhole('가 *나* 다', 'italic'), '*가 나 다*', '일부만 기울던 줄은 걷고 통째로');
eq(wrapWhole('  가 나  ', 'mark', 'green'), '  <mark class="green">가 나</mark>  ', '앞뒤 공백은 밖에');
eq(wrapWhole('   ', 'bold'), '   ', '빈 글은 그대로');
eq(nextValue('가 나', 'mark'), '', '형광펜이 없으면 노랑');
eq(nextValue('<mark>가 나</mark>', 'mark'), 'green', '다음 색');
eq(nextValue('<mark class="blue">가 나</mark>', 'mark'), undefined, '마지막 다음은 풀기');
eq(nextValue('가 나', 'color'), 'red', '글자색이 없으면 빨강');

// 줄 전체 (docops.formatLines) — 표시(목록·제목·인용)는 그대로
const L = (s) => s.split('\n');
const lines = (s, a, b, kind) => {
  const r = formatLines(L(s), a, b, kind);
  return r.error ? r : r.lines.join('\n');
};
eq(lines('- 항목 하나\n', 1, 1, 'italic'), '- *항목 하나*\n', '목록 표시는 그대로');
eq(lines('- *항목 하나*\n', 1, 1, 'italic'), '- 항목 하나\n', '다시 하면 푼다');
eq(lines('## 제목 ##\n', 1, 1, 'strike'), '## ~~제목~~ ##\n', '제목의 # 은 그대로');
eq(lines('> - [ ] 할 일\n', 1, 1, 'mark'), '> - [ ] <mark>할 일</mark>\n', '인용 안의 할 일');
eq(lines('가\n\n나\n', 1, 3, 'mark'), '<mark>가</mark>\n\n<mark>나</mark>\n', '여러 줄 — 빈 줄은 건너뛴다');
eq(lines('<mark>가</mark>\n\n나\n', 1, 3, 'mark'), '<mark class="green">가</mark>\n\n<mark class="green">나</mark>\n', '여러 줄의 색은 첫 줄을 따라 함께');
eq(lines('<mark class="blue">가</mark>\n<mark>나</mark>\n', 1, 2, 'mark'), '가\n나\n', '첫 줄이 마지막 색이면 모두 푼다');
eq(lines('가\n', 1, 1, 'color'), '<span style="color:red">가</span>\n', '글자색');
eq(lines('*가*\n나\n', 1, 2, 'italic'), '*가*\n*나*\n', '일부만 기울었으면 모두 기울인다');
eq(lines('*가*\n*나*\n', 1, 2, 'italic'), '가\n나\n', '모두 기울었으면 푼다');
eq(lines('```\n코드\n```\n', 2, 2, 'italic'), { error: 'kind' }, '코드 블록은 바꾸지 않는다');
eq(lines('| 가 |\n|---|\n| 1 |\n', 3, 3, 'mark'), { error: 'table-kind' }, '표는 바꾸지 않는다');
eq(lines('\n\n', 1, 2, 'italic'), { error: 'kind' }, '글이 없으면 그대로');

// 칠할 범위
eq(paintOf('가 **나** <mark class="green">다</mark> <span style="color:red">라</span>'),
  { marks: [[2, 4], [5, 7], [8, 28], [29, 36], [37, 61], [62, 69]], bold: [[4, 5]], 'mark-green': [[28, 29]], 'color-red': [[61, 62]] }, '칠할 범위');

return { n, fails };
