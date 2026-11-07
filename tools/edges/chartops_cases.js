// chartops.js 의 계산 점검 (rules_check.mjs 가 돌린다 — m: chartops.js, 끝에서 {n, fails} 를 돌려준다).
const { readValues, writeValues, chartKind, setChartKind, chartFromTable } = m;
let n = 0;
const fails = [];
const eq = (got, want, name) => {
  n += 1;
  if (JSON.stringify(got) !== JSON.stringify(want)) fails.push(`${name}: ${JSON.stringify(got)} ≠ ${JSON.stringify(want)}`);
};

const C = `{
  "width": "container",
  "data": {"values": [{"항목": "가", "값": 3}, {"항목": "나", "값": 5}]},
  "mark": "bar",
  "encoding": {
    "x": {"field": "항목", "type": "nominal"},
    "y": {"field": "값", "type": "quantitative"}
  }
}`;

eq(readValues(C), { fields: ['항목', '값'], rows: [['가', '3'], ['나', '5']] }, '값 표로 읽기');
eq(readValues('{"data": {"url": "a.csv"}}'), null, '파일을 읽는 차트');
eq(readValues('{"data": {"values": [1, 2]}}'), null, '수의 배열');
eq(readValues('{"data": {"values": [{"a": {"b": 1}}]}}'), null, '겹친 값');
eq(readValues('고장난 글'), null, '깨진 JSON');
eq(readValues('{"data": {"values": []}}'), null, '빈 값');
eq(readValues('{"data": {"values": [{"a": 1}, {"b": 2}]}}'), { fields: ['a', 'b'], rows: [['1', ''], ['', '2']] }, '빠진 칸');

const w = writeValues(C, ['항목', '값'], [['가', '10'], ['나', '1,200'], ['다', '']]);
eq(JSON.parse(w).data.values, [{ 항목: '가', 값: 10 }, { 항목: '나', 값: 1200 }, { 항목: '다', 값: null }], '값 쓰기 — 수로');
eq(w.split('\n')[1], '  "width": "container",', '나머지 글은 그대로');
eq(w.split('\n').length, C.split('\n').length, '줄 수가 그대로');
eq(JSON.parse(writeValues(C, ['항목', '값'], [['가]"', '텍스트']])).data.values, [{ 항목: '가]"', 값: '텍스트' }], '글 속의 괄호와 따옴표');
eq(JSON.parse(writeValues('{"data": {"values": [{"a": "]["}]}, "mark": "bar"}', ['a'], [['1']])).mark, 'bar', '문자열 안의 괄호를 세지 않는다');
eq(writeValues('{"mark": "bar"}', ['a'], [['1']]), null, '값이 없는 글');

eq(chartKind(C), 'bar', '지금 종류');
eq(chartKind('{"mark": {"type": "line"}}'), 'line', '표식이 객체');
eq(chartKind('{"layer": []}'), '', '겹친 차트');
eq(JSON.parse(setChartKind(C, 'line')).mark, 'line', '선으로');
const pie = JSON.parse(setChartKind(C, 'arc'));
eq([pie.mark, pie.encoding.theta.field, pie.encoding.color.field], ['arc', '값', '항목'], '원으로');
const back = JSON.parse(setChartKind(setChartKind(C, 'arc'), 'bar'));
eq([back.mark, back.encoding.x.field, back.encoding.y.field], ['bar', '항목', '값'], '원에서 막대로');
eq(JSON.parse(setChartKind('{"mark": {"type": "bar", "color": "red"}, "encoding": {"x": {"field": "a"}, "y": {"field": "b"}}}', 'line')).mark, { type: 'line', color: 'red' }, '표식의 설정은 남는다');
eq(setChartKind('{"layer": []}', 'line'), null, '겹친 차트는 못 바꾼다');
eq(JSON.parse(setChartKind('{"mark": "bar", "encoding": {"x": {"field": "a"}, "y": {"field": "b"}, "color": {"field": "c"}}}', 'line')).encoding.color.field, 'c', '계열은 남는다');

const one = chartFromTable(['품목', '값'], [['가', '1'], ['나', '2,000']]);
const spec1 = JSON.parse(one.lines.slice(1, -1).join('\n'));
eq([one.lines[0], one.lines.at(-1)], ['```vega-lite', '```'], '차트 울타리');
eq(spec1.data.values, [{ 품목: '가', 값: 1 }, { 품목: '나', 값: 2000 }], '표의 값');
eq([spec1.encoding.x.field, spec1.encoding.y.field], ['품목', '값'], '축');
const two = chartFromTable(['품목', '올해', '작년'], [['가', '1', '2']], { series: '구분', value: '값' });
const spec2 = JSON.parse(two.lines.slice(1, -1).join('\n'));
eq(spec2.data.values, [{ 품목: '가', 구분: '올해', 값: 1 }, { 품목: '가', 구분: '작년', 값: 2 }], '여러 열은 계열로');
eq(spec2.encoding.color.field, '구분', '계열 색');
eq(chartFromTable(['품목', '비고'], [['가', '메모']]), { error: 'not-numeric' }, '수가 아닌 열');
eq(chartFromTable(['품목'], [['가']]), { error: 'not-numeric' }, '값 열이 없다');

return { n, fails };
