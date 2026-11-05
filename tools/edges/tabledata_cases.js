// tabledata.js 의 표 읽기 점검 (data.py 가 페이지 안에서 돌린다 — m: tabledata.js, 끝에서 {n, fails} 를 돌려준다).
const { numberOf, isMissing, parseTime, frequencyOf, periodText, findTimeColumn, hasSameTimes, unitInfo, readTable, calcValues, calcText, findRegions, reshapeRegion, regionOfLines } = m;
let n = 0;
const fails = [];
const eq = (got, want, name) => {
  n += 1;
  const a = JSON.stringify(got);
  const b = JSON.stringify(want);
  if (a !== b) fails.push(`${name}: ${a} ≠ ${b}`);
};
const T = (s) => {
  const p = parseTime(s);
  return p && [p.kind, p.y, p.m, p.d];
};

// 시간 표기 (10-3 ③)
eq(T('2026'), ['Y', 2026, 1, 1], '연도');
eq(T('2026-03'), ['M', 2026, 3, 1], '연-월');
eq(T('2026.3'), ['M', 2026, 3, 1], '연.월');
eq(T('2026/03'), ['M', 2026, 3, 1], '연/월');
eq(T('202603'), ['M', 2026, 3, 1], '6자리');
eq(T('2026-03-15'), ['D', 2026, 3, 15], '날짜');
eq(T('2026.3.15.'), ['D', 2026, 3, 15], '날짜 끝 점');
eq(T('20260315'), ['D', 2026, 3, 15], '8자리');
eq(T('2026Q1'), ['Q', 2026, 1, 1], '2026Q1');
eq(T('2026 Q4'), ['Q', 2026, 10, 1], '2026 Q4');
eq(T('1Q26'), ['Q', 2026, 1, 1], '1Q26');
eq(T("3Q'25"), ['Q', 2025, 7, 1], "3Q'25");
eq(T('Q2 2026'), ['Q', 2026, 4, 1], 'Q2 2026');
eq(T('26Q3'), ['Q', 2026, 7, 1], '26Q3');
eq(T('2026년 1분기'), ['Q', 2026, 1, 1], '한글 분기');
eq(T('2026년 3월'), ['M', 2026, 3, 1], '한글 월');
eq(T('26년 3월'), ['M', 2026, 3, 1], '두 자리 연도');
eq(T('2026년 3월 15일'), ['D', 2026, 3, 15], '한글 날짜');
eq(T('2026년'), ['Y', 2026, 1, 1], '한글 연도');
eq(T('Mar-26'), ['M', 2026, 3, 1], 'Mar-26');
eq(T('March 2026'), ['M', 2026, 3, 1], 'March 2026');
eq(T('15-Mar-26'), ['D', 2026, 3, 15], '15-Mar-26');
eq(T('2026H1'), ['H', 2026, 1, 1], '2026H1');
eq(T('2026년 하반기'), ['H', 2026, 7, 1], '하반기');
eq(T('2026E'), ['Y', 2026, 1, 1], '전망 표시');
eq(T('2026(F)'), ['Y', 2026, 1, 1], '전망 괄호');
eq(T('2026년(전망)'), ['Y', 2026, 1, 1], '한글 전망');
eq(T("'26.3"), null, '앞 따옴표의 두 자리 연.월은 시점으로 보지 않음');
eq(T('2026-13'), null, '13월');
eq(T('2026-02-30'), null, '없는 날');
eq(T('평균'), null, '글');
eq(T('구리'), null, '품목');
eq(T('1234'), null, '범위 밖 연도');
eq(T('105.5'), null, '소수');
eq(T('Marble 12'), null, '달 이름이 아닌 글');
eq(T('Sept 2026'), ['M', 2026, 9, 1], 'Sept');

// 숫자·빈칸
eq(numberOf('1,234.5'), 1234.5, '쉼표');
eq(numberOf('-3.5%'), -3.5, '퍼센트');
eq(numberOf('$105'), 105, '달러');
eq(numberOf('-'), null, '대시');
eq(['', '-', '–', 'n.a.', 'N/A', 'NA', '#N/A', '해당 없음'].every(isMissing), true, '값 없는 칸');
eq(['0', '1.5', '구리'].some(isMissing), false, '값 있는 칸');

// 주기
const P = (list) => list.map(parseTime);
eq(frequencyOf(P(['2024', '2025', '2026'])), 'Y', '연별');
eq(frequencyOf(P(['2026Q1', '2026Q2'])), 'Q', '분기별');
eq(frequencyOf(P(['2026-01', '2026-02'])), 'M', '월별');
eq(frequencyOf(P(['2026-01-05', '2026-01-06', '2026-01-07', '2026-01-08'])), 'D', '일별');
eq(frequencyOf(P(['2026-01-02', '2026-01-05', '2026-01-06', '2026-01-07', '2026-01-08', '2026-01-09', '2026-01-12'])), 'D', '영업일');
eq(frequencyOf(P(['2026-01-02', '2026-01-09', '2026-01-16'])), 'W', '주별');
eq(frequencyOf(P(['2026-01-31', '2026-02-28', '2026-03-31'])), 'M', '월말 날짜는 월별');
eq(frequencyOf(P(['2026-03-31', '2026-06-30', '2026-09-30'])), 'Q', '분기말 날짜는 분기별');
eq(frequencyOf(P(['2024-12-31', '2025-12-31', '2026-12-31'])), 'Y', '연말 날짜는 연별');
eq(periodText(parseTime('2026-03-31'), 'M'), '2026-03', '월별 글');
eq(periodText(parseTime('2026-05-15'), 'Q'), '2026Q2', '분기 글');
eq(periodText(parseTime('2026Q3'), 'Q'), '2026Q3', '분기 글 2');

// 시간 열 — 가격을 연도로 읽지 않게
const col = (h, r) => findTimeColumn(h, r)?.col ?? -1;
eq(col(['날짜', '가격'], [['2026-01', '1'], ['2026-02', '2']]), 0, '날짜 열');
eq(col(['품목', '날짜', '값'], [['구리', '2026-01', '1'], ['구리', '2026-02', '2']]), 1, '둘째 열');
eq(col(['연도', '값'], [['2024', '1'], ['2025', '2']]), 0, '연도 열');
eq(col(['값', '연도'], [['5', '2024'], ['6', '2025']]), 1, '머리행에 연도');
eq(col(['품목', '가격'], [['구리', '2010'], ['니켈', '2050'], ['아연', '2100']]), -1, '가격이 연도처럼 보여도 시간이 아님');
eq(col(['가격'], [['2100'], ['2010'], ['2050']]), -1, '맨 앞 열이어도 차례가 아니면');
eq(col(['품목', '값'], [['구리', '1'], ['니켈', '2']]), -1, '시간 없음');
eq(col(['시점', '값'], [['2024', '1'], ['2025', '2'], ['평균', '1.5']]), 0, '시점이 아닌 행이 섞임');
eq(hasSameTimes(P(['2026-01', '2026-01']), 'M'), true, '같은 시점');
eq(hasSameTimes(P(['2026-01', '2026-02']), 'M'), false, '다른 시점');

// 단위 (10-3 ④)
const U = (h, cells = ['1', '2'], cap = '') => {
  const u = unitInfo(h, cells, cap);
  return [u.group, u.unit];
};
eq(U('가격 (USD/t)'), ['level', 'USD/t'], '머리행 단위');
eq(U('수입량(천톤)'), ['level', '천톤'], '붙은 단위');
eq(U('가격'), ['level', ''], '단위 없음');
eq(U('증가율'), ['rate', '%'], '증가율');
eq(U('전년비'), ['rate', '%'], '전년비');
eq(U('YoY'), ['rate', '%'], 'YoY');
eq(U('전월 대비'), ['rate', '%'], '전월 대비');
eq(U('변화 (%)'), ['rate', '%'], '% 단위');
eq(U('금리 차 (bp)'), ['rate', 'bp'], 'bp');
eq(U('값', ['1%', '2%', '3%']), ['rate', '%'], '칸의 %');
eq(U('배율 (x)'), ['multiple', 'x'], '배수 머리행');
eq(U('PER', ['10x', '12x']), ['multiple', 'x'], '칸의 x');
eq(U('가격', ['1', '2'], '표 1. 구리 가격 (단위: USD/t)'), ['level', 'USD/t'], '캡션의 단위');
eq(U('증가', ['1', '2'], '표 2. 증가 (%)'), ['rate', '%'], '캡션의 %');

// 표 → 계열
const R = (h, r, o) => {
  const x = readTable(h, r, o);
  return { l: x.labels, s: x.series.map((s) => [s.name, s.values]), t: x.turned, k: x.skipped, f: x.freq };
};
eq(R(['연도', '값'], [['2024', '1'], ['2025', '2']]), { l: ['2024', '2025'], s: [['값', [1, 2]]], t: false, k: 0, f: 'Y' }, '기본');
eq(R(['연도', '값'], [['2025', '2'], ['2024', '1']]).l, ['2024', '2025'], '최근 것이 위인 표는 뒤집음');
eq(R(['분기', '값'], [['2Q26', '2'], ['1Q26', '1'], ['4Q25', '0']]).l, ['4Q25', '1Q26', '2Q26'], '분기 차례');
eq(R(['항목', '2024', '2025', '2026'], [['구리', '1', '2', '3'], ['니켈', '4', '5', '6']]),
  { l: ['2024', '2025', '2026'], s: [['구리', [1, 2, 3]], ['니켈', [4, 5, 6]]], t: true, k: 0, f: 'Y' }, '머리행이 시점이면 저절로 바꿈');
eq(R(['항목', '2024', '2025'], [['구리', '1', '2'], ['니켈', '3', '4']], { swap: true }).l, ['구리', '니켈'], '행↔열로 되돌림');
eq(R(['품목', '값'], [['구리', '1'], ['니켈', '2']], { swap: true }).s.map((s) => s[0]), ['구리', '니켈'], '행↔열 — 품목이 계열로');
eq(R(['연도', '값'], [['2024', '1'], ['평균', '1.5'], ['2025', '2']]).k, 1, '시점이 아닌 행은 뺌');
eq(R(['연도', '값'], [['2024', '1'], ['2025', '-'], ['2026', 'n.a.'], ['2027', '4']]).s[0][1], [1, null, null, 4], '빈칸·- 는 끊긴 곳');
eq(R(['품목', '값'], [['구리', '1'], ['니켈', '2']]).l, ['구리', '니켈'], '시간이 없으면 글 열이 이름표');
eq(R(['a', 'b'], [['1', '2'], ['3', '4']]).l, ['1', '2'], '글 열도 없으면 행 번호');
eq(R(['품목', '메모'], [['구리', '좋음']]).s, [], '숫자 열 없음');
eq(readTable([], []).series, [], '빈 표');
eq(readTable(['날짜', '품목', '값'], [['2026-01', '구리', '1'], ['2026-01', '니켈', '2']]).same, true, '품목별로 쌓은 표');

// 계산 열 (11-2 ③)
const C = (kind, v, o) => calcValues(kind, v, o).map((x) => (x == null ? null : Math.round(x * 100) / 100));
const months = P(['2025-01', '2025-02', '2025-03', '2026-01', '2026-02']);
eq(C('pop', [100, 110, 99]), [null, 10, -10], '전기 대비');
eq(C('pop', [100, null, 110]), [null, null, null], '앞 값이 없으면 없음');
eq(C('pop', [0, 5]), [null, null], '앞 값이 0 이면 없음');
eq(C('pop', [-100, -50]), [null, 50], '음수에서 오른 것은 플러스');
eq(C('pop', [100, 110, 120, 200, 220], { parsed: months, freq: 'M' }), [null, 10, 9.09, null, 10], '빠진 달 뒤는 앞 시점이 없음');
eq(C('yoy', [100, 110, 120, 200, 220], { parsed: months, freq: 'M' }), [null, null, null, 100, 100], '전년 동기 — 월은 12 뺌');
const qs = P(['2025Q1', '2025Q2', '2026Q1']);
eq(C('yoy', [100, 110, 150], { parsed: qs, freq: 'Q' }), [null, null, 50], '분기는 4 뺌');
const ds = P(['2025-03-14', '2025-03-17', '2026-03-16']);
eq(C('yoy', [100, 110, 150], { parsed: ds, freq: 'D' }), [null, null, 36.36], '날짜는 가장 가까운 날 (앞뒤 3일 안)');
eq(C('yoy', [100, 150], { parsed: P(['2025-03-01', '2026-03-16']), freq: 'D' }), [null, null], '3일 넘게 떨어지면 없음');
eq(C('yoy', [1, 2]), [null, null], '시간이 없으면 전년 동기 없음');
eq(C('diff', [100, 110, 99]), [null, 10, -11], '차분');
eq(C('cum', [1, 2, null, 3]), [1, 3, null, 6], '누적');
eq(C('ma', [1, 2, 3, 4], { n: 3 }), [null, null, 2, 3], '이동평균');
eq(C('ma', [1, null, 3, 4, 5], { n: 2 }), [null, null, null, 3.5, 4.5], '이동평균 — 빈칸이 든 곳은 없음');
eq(C('index', [null, 50, 100, 75]), [null, 100, 200, 150], '지수 — 첫 값=100');
eq(calcText(1.005, 2), '1', '소수 2자리 반올림');
eq(calcText(12.3456, 2), '12.35', '글');
eq(calcText(null, 2), '', '값 없음');
eq(calcText(-0.001, 2), '0', '음의 0');
// 표 영역 (엑셀에서 온 표)
const G = (text) => text.split('\n').map((l) => l.split('|'));
const F = (text, merges = []) => {
  const rows = G(text);
  return findRegions(rows, rows.map((_, i) => [i + 1, i + 1]), merges);
};
const one = (x) => x.regions[0];
eq(F('연도|값\n2024|1\n2025|2').plain, true, '깔끔한 표');
eq(F('a|b\nc|d').plain, true, '글뿐인 표도 그대로');
eq(F('메모\n둘째 줄').regions, [], '칸 하나뿐인 시트');
{
  const x = F('구리 수입량\n(단위: 천톤)\n\n연도|값\n2024|1\n2025|2');
  eq([x.plain, one(x).titles, one(x).headers, one(x).rows.length], [false, ['구리 수입량', '(단위: 천톤)'], ['연도', '값'], 2], '위의 제목·단위 줄');
}
{
  const x = F('구리 수입량||\n연도|값|\n2024|1|\n2025|2|');
  eq([one(x).titles, one(x).headers.slice(0, 2)], [['구리 수입량'], ['연도', '값']], '빈 줄 없이 붙은 제목');
}
{
  const x = F('구분|수입||수출|\n|구리|니켈|구리|니켈\n2024|1|2|3|4\n2025|5|6|7|8');
  eq([one(x).depth, one(x).headers, one(x).rows.length], [2, ['구분', '수입 · 구리', '수입 · 니켈', '수출 · 구리', '수출 · 니켈'], 2], '두 줄 머리행');
}
{
  const x = F('구분|수입||\n|구리|니켈|아연\n2024|1|2|3', [[1, 1, 1, 3]]);
  eq(one(x).headers, ['구분', '수입 · 구리', '수입 · 니켈', '수입 · 아연'], '병합 칸은 병합 범위까지');
}
{
  const x = F('연도|값\n2024|1\n2025|2\n\n자료: 한국은행\n주: 잠정치');
  eq([one(x).notes, one(x).rows.length, x.plain], [['자료: 한국은행', '주: 잠정치'], 2, false], '아래 자료·주 줄');
}
{
  const x = F('연도|값\n2024|1\n2025|2\n자료: 한국은행||');
  eq([one(x).notes, one(x).rows.length], [['자료: 한국은행'], 2], '붙은 자료 줄');
}
{
  const x = F('연도|값\n2024|1\n\n품목|수량|금액\n구리|1|2\n니켈|3|4\n아연|5|6');
  eq([x.regions.length, x.best, x.regions[1].headers], [2, 1, ['품목', '수량', '금액']], '위아래로 둔 두 표 — 큰 표를 고름');
}
{
  const x = F('표 가\n연도|값\n2024|1\n\n표 나\n연도|값\n2025|2');
  eq(x.regions.map((r) => r.titles), [['표 가'], ['표 나']], '표마다 제목');
}
{
  const x = F('연도|값||품목|수량\n2024|1||구리|5\n2025|2||니켈|6');
  eq([x.regions.length, x.regions[1].c0, x.regions[1].headers], [2, 3, ['품목', '수량']], '옆으로 둔 두 표');
}
eq(F('연도|가격||증가율\n2024|1||5%\n2025|2||6%').regions.length, 1, '표 안의 간격 열은 나누지 않음');
eq(F('연도|값\n2024|1\n\n2025|2\n2026|3').regions.map((r) => r.rows.length), [3], '몸통 사이의 빈 줄은 같은 표');
eq(F('품목|가격|증감|날짜\n구리|8|5%|2023-03\n니켈|16|2%|2023-04\n\n합계|25||').regions.map((r) => r.rows.length), [3], '한 칸 띄운 합계 행은 같은 표');
eq(F('품목|가격|증감|날짜\n구리|8|5%|2023-03\n니켈|16|2%|2023-04\n\n합계|25||').plain, true, '합계 행이 있어도 깔끔한 표');
eq(U('price', ['1', '2'], 'Copper (unit: USD/t)'), ['level', 'USD/t'], '영어 캡션의 단위');
eq(one(F('항목|2024|2025\n구리|1|2\n니켈|3|4')).depth, 1, '머리행의 연도를 몸통으로 보지 않음');
eq(one(F('2024|1\n2025|2')).depth, 0, '머리행 없는 표');
{
  const rows = G('품목|연도|값\n구리|2024|1\n|2025|2\n니켈|2024|3');
  const x = findRegions(rows, rows.map((_, i) => [i + 1, i + 1]), [[2, 0, 3, 0]]);
  eq(one(x).rows.map((r) => r[0]), ['구리', '구리', '니켈'], '세로 병합은 몸통에 채움');
}
{
  const rows = G('제목\n연도|값\n2024|1\n2025|2');
  const lines = rows.map((_, i) => [i + 1, i + 1]);
  const x = findRegions(rows, lines);
  const y = reshapeRegion(rows, lines, [], one(x), 2);
  eq([y.depth, y.headers, y.rows.length], [2, ['연도 · 2024', '값 · 1'], 1], '머리행 줄 수를 바꿈');
  eq(regionOfLines(rows, lines, [], 2, 3).rows, [['2024', '1']], '지정한 범위');
  eq(regionOfLines(rows, lines, [], 9, 9), null, '값이 없는 범위');
}
eq(one(findRegions(G('연도|값\n2024|1\n2025|2'), [[5, 5], [6, 6], [7, 7]])).lines, [[6, 6], [7, 7]], '줄 번호를 그대로');
eq(findRegions(G('연도|값\n2024|1\n2026|2\n2027|3'), [[1, 1], [2, 2], [9, 9], [10, 10]]).regions.length, 1, '엑셀의 빈 행(줄 번호가 뜀)도 몸통 사이면 같은 표');
// 임의의 시트: 오류가 없고, 표의 칸은 시트에 있던 글이고, 표끼리 행을 나눠 갖지 않는다
{
  let seed = 11;
  const rnd = (k) => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed % k; };
  const words = ['', '', '', '구리', '자료: 협회', '단위: 톤', '2024', '2025-03', '1Q26', '12.5', '-', 'n.a.', '1,234', '5%', '합계', '평균', '(천톤)'];
  let bad = '';
  for (let run = 0; run < 400 && !bad; run++) {
    const h = rnd(14);
    const w = 1 + rnd(7);
    const rows = Array.from({ length: h }, () => Array.from({ length: rnd(5) ? w : 1 + rnd(w) }, () => words[rnd(words.length)]));
    const lines = rows.map((_, i) => [i * (1 + rnd(2)) + 1, 0]);
    lines.forEach((l, i) => { l[0] = i ? lines[i - 1][0] + 1 + rnd(2) : 1; l[1] = l[0]; });
    try {
      const x = findRegions(rows, lines, []);
      const all = new Set(rows.flat());
      const seen = new Set();
      for (const r of x.regions) {
        if (r.rows.some((row) => row.some((v) => !all.has(v) && v !== ''))) bad = `글이 달라짐: ${JSON.stringify(rows)}`;
        for (const l of r.lines) {
          const key = `${l[0]}:${r.c0}`;
          if (seen.has(key)) bad = `행이 겹침: ${JSON.stringify(rows)}`;
          seen.add(key);
        }
        const read = readTable(r.headers, r.rows, { caption: r.titles.join(' ') });
        readTable(r.headers, r.rows, { swap: true });
        if (read.series.some((v) => v.values.length !== read.labels.length)) bad = `계열 길이: ${JSON.stringify(rows)}`;
        reshapeRegion(rows, lines, [], r, rnd(4));
      }
      if (x.regions.length && !x.regions[x.best]) bad = `best: ${JSON.stringify(rows)}`;
    } catch (e) {
      bad = `${e.message}: ${JSON.stringify(rows)}`;
    }
  }
  eq(bad, '', '임의의 시트 400개');
}
return { n, fails };
