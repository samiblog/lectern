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

// ---- 차트의 데이터를 표로 (D136) ----
const { chartData, thinRows, tableText, csvValue, csvRecords, csvText, inlineUrlData } = m;
const tables = (kind, spec) => chartData(kind, spec).tables.map((x) => [x.fields, x.rows]);

eq(tables('vega-lite', JSON.parse(C)), [[['항목', '값'], [['가', 3], ['나', 5]]]], 'VL 값 — 수는 수로');
eq(tables('vega-lite', { datasets: { d: [{ a: 1 }] }, data: { name: 'd' }, mark: 'bar' }), [[['a'], [[1]]]], 'VL 이름 붙인 데이터');
eq(tables('vega-lite', { data: { values: [{ a: 1 }] }, layer: [{ mark: 'bar' }, { mark: 'text' }] }), [[['a'], [[1]]]], 'VL 겹친 층이 같은 데이터');
eq(tables('vega-lite', { layer: [{ data: { values: [{ a: 1 }] } }, { data: { values: [{ b: 2 }] } }] }).length, 2, 'VL 층마다 다른 데이터');
eq(tables('vega-lite', { hconcat: [{ data: { values: [{ a: 1 }] } }] }).length, 1, 'VL 나란히 놓은 차트');
eq(chartData('vega-lite', { data: { values: [{ a: 1 }] }, transform: [{ filter: 'datum.a > 0' }] }).transform, true, 'VL 변환이 있다');
eq(chartData('vega-lite', { data: { values: [{ a: 1 }] }, encoding: { y: { aggregate: 'sum', field: 'a' } } }).transform, true, 'VL 집계가 있다');
eq(chartData('vega-lite', { data: { values: [{ a: 1 }] }, encoding: { x: { bin: true, field: 'a' } } }).transform, true, 'VL 구간이 있다');
eq(chartData('vega-lite', JSON.parse(C)).transform, false, 'VL 변환 없음');
const url = chartData('vega-lite', { data: { url: 'data/a.csv' }, mark: 'bar' });
eq([url.tables.length, url.urls], [0, ['data/a.csv']], 'VL 파일을 읽는 차트는 표 없이 주소만');
eq(tables('vega-lite', { data: { values: 'a,b\n1,x\n2,y', format: { type: 'csv' } } }), [[['a', 'b'], [[1, 'x'], [2, 'y']]]], 'VL 글로 적은 CSV');
eq(chartData('vega-lite', { data: { sequence: { start: 0, stop: 10 } } }).generated, true, 'VL 만든 데이터');
eq(tables('vega-lite', { data: { values: [{ a: null, b: { c: 1 } }] } }), [[['a', 'b'], [[null, '{"c":1}']]]], 'VL 빈 값과 겹친 값');
eq(tables('vega-lite', { data: { values: [1, 2] } }), [[['value'], [[1], [2]]]], 'VL 수의 배열');
eq(tables('vega', { data: [{ name: 't', values: [{ x: 1 }] }, { name: 's', source: 't', transform: [{ type: 'filter', expr: 'true' }] }] }), [[['x'], [[1]]]], 'Vega 값과 그 위의 변환');
eq(chartData('vega', { data: [{ name: 't', url: 'b.csv' }] }).urls, ['b.csv'], 'Vega 파일');
eq(tables('echarts', { dataset: { source: [['품목', '1월'], ['가', 3], ['나', 4]] } }), [[['품목', '1월'], [['가', 3], ['나', 4]]]], 'EC dataset 머리행');
eq(tables('echarts', { dataset: { dimensions: ['a', { name: 'b' }], source: [[1, 2]] } }), [[['a', 'b'], [[1, 2]]]], 'EC dataset dimensions');
eq(tables('echarts', { dataset: { source: [{ a: 1 }] } }), [[['a'], [[1]]]], 'EC dataset 객체');
eq(tables('echarts', { xAxis: { type: 'category', data: ['월', '화'] }, series: [{ name: '방문', data: [3, 5] }, { data: [1, { value: 2 }] }] }),
  [[['', '방문', 'series 2'], [['월', 3, 1], ['화', 5, 2]]]], 'EC 축과 계열 — 이름 없는 계열');
eq(tables('echarts', { yAxis: [{ type: 'category', data: ['가'] }], xAxis: { type: 'value' }, series: { type: 'bar', data: [7] } }), [[['', 'series 1'], [['가', 7]]]], 'EC 가로 막대');
eq(tables('echarts', { series: [{ type: 'pie', data: [{ name: '가', value: 1 }, { name: '나', value: 2 }] }] }), [[['name', 'value'], [['가', 1], ['나', 2]]]], 'EC 원');
eq(tables('echarts', { xAxis: {}, yAxis: {}, series: [{ name: 's', type: 'scatter', data: [[1, 2], [3, 4]] }] }), [[['series', 'x', 'y'], [['s', 1, 2], ['s', 3, 4]]]], 'EC 점');
eq(tables('echarts', { series: [] }), [], 'EC 계열 없음');
eq(tables('plotly', { data: [{ x: ['a', 'b'], y: [1, 2], name: '올해' }, { x: ['a', 'b'], y: [3, 4] }] }), [[['x', '올해', 'series 2'], [['a', 1, 3], ['b', 2, 4]]]], 'PL 같은 x');
eq(tables('plotly', [{ x: [1], y: [2], name: 'p' }, { x: [5, 6], y: [7, 8], name: 'q' }]), [[['series', 'x', 'y'], [['p', 1, 2], ['q', 5, 7], ['q', 6, 8]]]], 'PL 다른 x 는 긴 표');
eq(tables('plotly', { data: [{ y: [4, 5] }] }), [[['x', 'series 1'], [[1, 4], [2, 5]]]], 'PL x 가 없으면 차례 번호');
eq(tables('plotly', { data: [{ type: 'pie', labels: ['가'], values: [9] }] }), [[['label', 'value'], [['가', 9]]]], 'PL 원');
eq(tables('plotly', { data: [{ type: 'box', y: [1, 2], name: '가' }, { type: 'box', y: [3], name: '나' }] }), [[['series', 'y'], [['가', 1], ['가', 2], ['나', 3]]]], 'PL 상자 그림 — 차례 번호 없이');
eq(tables('plotly', { data: [{ type: 'histogram', x: [5, 6] }] }), [[['series', 'x'], [['series 1', 5], ['series 1', 6]]]], 'PL 히스토그램 — x 만');
eq(tables('plotly', { data: [{ type: 'box', y: [1, 2] }, { type: 'box', y: [3, 4] }] }), [[['series', 'y'], [['series 1', 1], ['series 1', 2], ['series 2', 3], ['series 2', 4]]]], 'PL 길이가 같은 상자 그림도 긴 표');
eq(chartData('plotly', null).tables, [], '설정 없음');
eq(chartData('dot', { a: 1 }).tables, [], 'Graphviz 는 없음');

const few = thinRows(10);
eq([few.items.length, few.step, few.items.some((x) => x.skip)], [10, 1, false], '30행까지는 그대로');
const many = thinRows(100);
const shown = many.items.filter((x) => x.skip == null);
eq([shown.length, shown[0].i, shown.at(-1).i, many.step], [30, 0, 99, 3], '100행 → 처음·끝을 넣고 30행');
eq(shown.length + many.items.reduce((s, x) => s + (x.skip || 0), 0), 100, '보인 행과 건너뛴 행을 더하면 전체');
eq(many.items.every((x, k, a) => k === 0 || x.skip != null || a[k - 1].skip != null || a[k - 1].i === x.i - 1), true, '건너뛴 자리가 표시된다');
eq(thinRows(31).items.filter((x) => x.skip == null).length, 30, '31행 → 30행');
eq(thinRows(0).items, [], '빈 표');

eq(tableText({ fields: ['a', 'b'], rows: [[1.5, null], ['x\ty', 'z\nw']] }), 'a\tb\n1.5\t\nx y\tz w', '복사 글 — 탭·줄바꿈은 빈칸으로');

eq([csvValue(''), csvValue(' 3 '), csvValue('-1.5e2'), csvValue('true'), csvValue('1,000'), csvValue('2024-01-01'), csvValue('NaN'), csvValue('.5')],
  [null, 3, -150, true, '1,000', '2024-01-01', 'NaN', 0.5], 'CSV 칸 읽기');
eq(csvRecords([['a', 'b'], ['1', 'x'], ['', ''], ['2']]), [{ a: 1, b: 'x' }, { a: 2, b: null }], 'CSV 레코드 — 빈 행은 빼고 빠진 칸은 null');
eq(csvRecords([]), [], 'CSV 없음');
eq(csvText('\uFEFFa,b\r\n1,2\r3\n'), 'a,b\n1,2\n3\n', 'CSV 글 — BOM 과 CRLF');

const U = '```vega-lite\n{\n  "data": {"url": "data/a b+(1).csv", "format": {"type": "csv", "parse": {"d": "date"}}},\n  "mark": "line"\n}\n```';
const rec = { 'data/a b+(1).csv': [{ d: '2024-01', v: 1 }, { d: '2024-02', v: 2 }] };
const inl = inlineUrlData(U, rec);
const inSpec = JSON.parse(inl.split('\n').slice(1, -1).join('\n'));
eq(inSpec.data, { values: rec['data/a b+(1).csv'], format: { parse: { d: 'date' } } }, '파일 → 문서 안의 값 (읽는 방법은 빼고 parse 는 둔다)');
eq([inl.split('\n')[0], inl.split('\n').at(-1), inl.split('\n').at(-3)], ['```vega-lite', '```', '  "mark": "line"'], '나머지 줄은 그대로');
eq(inl.split('\n').filter((l) => l.trim().startsWith('{"d":')).length, 2, '한 행이 한 줄');
const L = '{"layer": [{"data": {"url": "a.csv"}, "mark": "bar"}, {"data": {"url": "a.csv"}, "mark": "rule"}, {"data": {"url": "b.csv"}}]}';
const inL = JSON.parse(inlineUrlData(L, { 'a.csv': [{ x: 1 }], 'b.csv': [{ y: 2 }] }));
eq(inL.layer.map((l) => l.data), [{ values: [{ x: 1 }] }, { values: [{ x: 1 }] }, { values: [{ y: 2 }] }], '층마다');
eq(inlineUrlData('{"data": {"values": []}}', { 'a.csv': [] }), null, '주소가 없으면 null');
eq(JSON.parse(inlineUrlData('{"data": [{"name": "t", "url": "a.csv", "format": {"type": "csv", "parse": "auto"}}]}', { 'a.csv': [{ x: 1 }] })).data,
  [{ values: [{ x: 1 }], name: 't', format: { parse: 'auto' } }], 'Vega 의 data 배열');
eq(JSON.parse(inlineUrlData('{"title": "a.csv { }", "data": {"url": "a.csv"}}', { 'a.csv': [{ x: '"}' }] })), { title: 'a.csv { }', data: { values: [{ x: '"}' }] } }, '글 속 괄호와 따옴표');
eq(inlineUrlData('{"data": {"url": "a.csv"', { 'a.csv': [] }), null, '깨진 글');

return { n, fails };
