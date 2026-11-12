// impresslayout.js 의 계산 점검 (rules_check.mjs 가 돌린다 — m: impresslayout.js, 끝에서 {n, fails} 를 돌려준다).
const { readMode, readSpot, layoutSteps, overviewOf } = m;
let n = 0;
const fails = [];
const eq = (got, want, name) => {
  n += 1;
  if (JSON.stringify(got) !== JSON.stringify(want)) fails.push(`${name}: ${JSON.stringify(got)} ≠ ${JSON.stringify(want)}`);
};
const xy = (places) => places.map((p) => [p.x, p.y]);

// 배치 방식
eq(readMode(undefined), { mode: 'grid', bad: '' }, '적지 않으면 격자');
eq(readMode('line'), { mode: 'line', bad: '' }, 'line');
eq(readMode('  Grid '), { mode: 'grid', bad: '' }, '대소문자·빈칸');
eq(readMode('가로'), { mode: 'line', bad: '' }, '한국어 낱말');
eq(readMode('spiral'), { mode: 'grid', bad: 'spiral' }, '모르는 낱말은 격자로 두고 알린다');
eq(readMode(3), { mode: 'grid', bad: '3' }, '수');

// 장의 자리
eq(readSpot('x=0 y=2400 rotate=90 scale=3'), { spot: { x: 0, y: 2400, rotate: 90, scale: 3 }, bad: [] }, '네 축');
eq(readSpot('x=-1.5, rotate-x=45,rotate-y=-30 z=-200'), { spot: { x: -1.5, 'rotate-x': 45, 'rotate-y': -30, z: -200 }, bad: [] }, '쉼표·음수·소수');
eq(readSpot('X=10'), { spot: { x: 10 }, bad: [] }, '대문자 축');
eq(readSpot('x=1 y=abc w=3 scale=0 scale=101 rotate'), { spot: { x: 1 }, bad: ['y=abc', 'w=3', 'scale=0', 'scale=101', 'rotate'] }, '읽지 못한 낱말');
eq(readSpot('x=1e3 y=0x10 z=1;'), { spot: {}, bad: ['x=1e3', 'y=0x10', 'z=1;'] }, '수가 아닌 글자');
eq(readSpot(''), { spot: {}, bad: [] }, '빈 값');
eq(readSpot('grid'), { spot: {}, bad: ['grid'] }, '장에 적은 배치 방식');
eq(readSpot('x="1"'), { spot: {}, bad: ['x="1"'] }, '따옴표');

// 격자: 장 구분에서 줄을 바꾸고 4장에서 접는다
const plain = (k) => Array.from({ length: k }, (_, i) => ({ lead: i === 0, spot: {} }));
eq(xy(layoutSteps(plain(6))), [[0, 0], [1472, 0], [2944, 0], [4416, 0], [0, 936], [1472, 936]], '표지 하나 + 다섯 장 — 4장에서 접는다');
eq(xy(layoutSteps([{ lead: true }, { lead: false }, { lead: true }, { lead: false }, { lead: false }, { lead: true }])),
  [[0, 0], [1472, 0], [0, 936], [1472, 936], [2944, 936], [0, 1872]], '장 구분마다 새 줄');
eq(xy(layoutSteps([{ lead: true }, { lead: true }, { lead: false }])), [[0, 0], [0, 936], [1472, 936]], '표지 바로 뒤의 간지');
eq(xy(layoutSteps([{ lead: false }, { lead: false }])), [[0, 0], [1472, 0]], '장 구분이 없는 문서');
eq(xy(layoutSteps(plain(5), { mode: 'line' })), [[0, 0], [1472, 0], [2944, 0], [4416, 0], [5888, 0]], '가로 한 줄은 접지 않는다');
eq(xy(layoutSteps(plain(3), { w: 960, h: 720 })), [[0, 0], [1104, 0], [2208, 0]], '4:3 장');
eq(layoutSteps([]), [], '장이 없다');

// 적은 축만 이긴다
const placed = layoutSteps([{ lead: true, spot: {} }, { lead: false, spot: { y: 2400, rotate: 90, scale: 3 } }, { lead: false, spot: {} }]);
eq(placed[1], { x: 1472, y: 2400, z: 0, rotate: 90, 'rotate-x': 0, 'rotate-y': 0, scale: 3 }, '적은 축 + 규칙의 x');
eq(xy([placed[2]]), [[2944, 0]], '뒤 장은 규칙대로');

// 전체 보기
eq(overviewOf([]), null, '장이 없으면 전체 보기도 없다');
eq(overviewOf(layoutSteps(plain(1))), { x: 0, y: 0, scale: 1.08 }, '한 장');
const ov = overviewOf(layoutSteps(plain(6)));
eq([ov.x, ov.y], [2208, 468], '가운데');
eq(ov.scale, Math.round(((4416 + 1280) / 1280) * 1.08 * 100) / 100, '가장 넓은 쪽에 맞춘 배율');
const turned = overviewOf([{ x: 0, y: 0, rotate: 90, scale: 1 }]);
eq(turned.scale, Math.round((1280 / 720) * 1.08 * 100) / 100, '돌린 장은 세로로 길다');
eq(overviewOf([{ x: 0, y: 0, rotate: 0, scale: 3 }]).scale, 3.24, '키운 장');

return { n, fails };
