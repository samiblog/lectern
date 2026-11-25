// 담기함의 글 (clipdata.js — D197): 쓰고 읽으면 그대로, 손으로 고친 파일, 합치기, 원문에서 찾기. rules_check.mjs 가 돌린다 (m: 모듈)
const fails = [];
let n = 0;
const eq = (name, got, want) => {
  n += 1;
  const a = JSON.stringify(got);
  const b = JSON.stringify(want);
  if (a !== b) fails.push(`${name}: ${a} ≠ ${b}`);
};
const clip = (o = {}) => ({ id: 'c1', path: 'a/b.md', lines: [3, 5], kind: 'table', name: '표 1', label: '표 1. 구리', text: '| a |\n|---|\n| 1 |', notes: '', plain: false, at: '2026-11-25', title: '', memo: '', extra: {}, ...o });
const box = (items, o = {}) => ({ title: '구리 전망', note: '', items, ...o });
const round = (b) => m.parseBox(m.writeBox(b));

for (const [name, b] of Object.entries({
  '빈 담기함': box([]),
  '제목이 없는 담기함': box([clip()], { title: '' }),
  '설명 여러 줄': box([clip()], { note: '질문 하나\n\n- 가\n- 나' }),
  '조각 하나': box([clip()]),
  '제목과 메모': box([clip({ title: '재고가 줄었다', memo: '왜?\n\n둘째 문단' })]),
  '메모가 ## 로 시작': box([clip({ memo: '## 제목처럼\n글' })]),
  '메모가 ## 만': box([clip({ memo: '##' })]),
  '메모가 # 으로 시작': box([clip({ memo: '# 큰 제목' })]),
  '각주': box([clip({ text: '글[^1]', notes: '[^1]: 주\n    이어진 줄' })]),
  '고른 글': box([clip({ plain: true, text: '보이는 글', kind: 'text' })]),
  '출처 없음': box([clip({ path: '', lines: null, at: '' })]),
  '줄 하나': box([clip({ lines: [7, 7] })]),
  '빈칸·따옴표·-->': box([clip({ path: "가 나/'다' (라).md", label: 'x --> y <b> "z" 100% &amp;' })]),
  '글 안의 같은 표시': box([clip({ text: '<!-- lectern-clip id=x -->\n<!-- lectern-clip-text -->\n  <!-- /lectern-clip -->\n<!-- \\lectern-clip-notes -->\n<!-- lectern-clips: -->' })]),
  '메모 안의 같은 표시': box([clip({ memo: '<!-- /lectern-clip -->\n글' })]),
  '설명 안의 같은 표시': box([clip()], { note: '<!-- lectern-clip -->' }),
  '앞뒤 빈 줄·들여쓰기가 있는 글': box([clip({ text: '\n    들여 쓴 코드\n\n끝' })]),
  '빈 글': box([clip({ text: '' })]),
  '코드 울타리': box([clip({ text: '```md\n# 제목\n```' })]),
  '모르는 값': box([clip({ extra: { tag: '가,나', kindof: 'fact' } })]),
  '여럿': box([clip(), clip({ id: 'c2', title: '둘' }), clip({ id: 'c3', memo: '셋' })]),
  '잘린 그림 글자': box([clip({ label: '가\ud83d' })]),
})) {
  const want = JSON.parse(JSON.stringify(b));
  for (const c of want.items) if (/\ud83d$/.test(c.label)) c.label = '가\ufffd';
  eq(name, round(b), want);
  eq(`${name} (두 번)`, m.writeBox(round(b)), m.writeBox(round(round(b))));
}
eq('CRLF 파일', m.parseBox(m.writeBox(box([clip({ memo: '가\n나' })])).replace(/\n/g, '\r\n')), box([clip({ memo: '가\n나' })]));
eq('BOM', m.parseBox(`\ufeff${m.writeBox(box([clip()]))}`).title, '구리 전망');
// 손으로 쓴 파일
const hand = m.parseBox('# 손으로\n\n설명\n\n<!-- lectern-clip path=a.md line=2 -->\n## 제목\n메모\n<!-- lectern-clip-text -->\n글\n<!-- /lectern-clip -->\n\n사이에 쓴 글\n\n<!-- lectern-clip id=q -->\n끝 표시가 없음\n<!-- lectern-clip-text -->\n열린 글');
eq('손: 제목·설명', [hand.title, hand.note], ['손으로', '설명']);
eq('손: 조각 셋', hand.items.map((c) => [c.title, c.memo, c.text, c.path, c.lines]), [['제목', '메모', '글', 'a.md', [2, 2]], ['', '', '사이에 쓴 글', '', null], ['', '끝 표시가 없음', '열린 글', '', null]]);
eq('손: id 가 저절로', hand.items.map((c) => !!c.id && typeof c.id), ['string', 'string', 'string']);
eq('손: 겹친 id', new Set(m.parseBox('<!-- lectern-clip id=a -->\n<!-- /lectern-clip -->\n<!-- lectern-clip id=a -->\n<!-- /lectern-clip -->\n<!-- lectern-clip id=x1 -->').items.map((c) => c.id)).size, 3);
eq('보통 Markdown', m.parseBox('그냥 글').note, '그냥 글');
eq('빈 파일', m.parseBox(''), { title: '', note: '', items: [] });
// 밖에서 고친 경로는 믿지 않는다
for (const bad of ['../x.md', 'a/../../x.md', '/etc/x', '\\\\server\\share\\x.md', 'C:/x.md', 'a\\b.md', 'http://x/y.md', './a.md', 'a//b.md', 'a\u0000.md']) eq(`경로 ${bad}`, m.safePath(bad), '');
for (const ok of ['a.md', '가 나/다.md', 'a/.b/c.md', 'a..b/c.md']) eq(`경로 ${ok}`, m.safePath(ok), ok);

// 합치기
const ids = (b) => b.items.map((c) => c.id).join('');
const of = (s, o = {}) => ({ title: 't', note: '', items: [...s].map((id) => clip({ id, ...(o[id] || {}) })) });
const marks = (o = {}) => ({ touched: new Set(o.touched || ''), removed: new Set(o.removed || ''), head: !!o.head, order: !!o.order });
eq('합치기: 내가 더한 것은 앞 조각 뒤에', ids(m.mergeBox(of('abN'), of('abX'), marks({ touched: 'N' }))), 'abNX');
eq('합치기: 맨 앞에 더한 것', ids(m.mergeBox(of('Nab'), of('ab'), marks({ touched: 'N' }))), 'Nab');
eq('합치기: 내가 뺀 것', ids(m.mergeBox(of('ac'), of('abcX'), marks({ removed: 'b' }))), 'acX');
eq('합치기: 밖에서 뺀 것은 그대로', ids(m.mergeBox(of('abc'), of('ac'), marks())), 'ac');
eq('합치기: 밖에서 뺐어도 내가 고친 것은 남는다', ids(m.mergeBox(of('abc'), of('ac'), marks({ touched: 'b' }))), 'abc');
eq('합치기: 고친 것은 내 것', m.mergeBox(of('a', { a: { memo: '내' } }), of('a', { a: { memo: '밖' } }), marks({ touched: 'a' })).items[0].memo, '내');
eq('합치기: 안 고친 것은 파일의 것', m.mergeBox(of('a', { a: { memo: '내' } }), of('a', { a: { memo: '밖' } }), marks()).items[0].memo, '밖');
eq('합치기: 차례', ids(m.mergeBox(of('cab'), of('abcX'), marks({ order: true }))), 'cXab');
eq('합치기: 차례(모르는 것이 맨 앞)', ids(m.mergeBox(of('ba'), of('Xab'), marks({ order: true }))), 'Xba');
eq('합치기: 제목은 고쳤을 때만', [m.mergeBox({ ...of(''), title: '내' }, { ...of(''), title: '밖' }, marks()).title, m.mergeBox({ ...of(''), title: '내' }, { ...of(''), title: '밖' }, marks({ head: true })).title], ['밖', '내']);

// 원문에서 찾기
const src = ['# 문서', '', '| a |', '|---|', '| 1 |', '', '끝'];
eq('찾기: 그대로', m.findPiece(src, clip()), { state: 'same', lines: [3, 5] });
eq('찾기: 옮겨짐', m.findPiece(['앞', '', ...src], clip()), { state: 'moved', lines: [5, 7] });
eq('찾기: 바뀜', m.findPiece(src.map((s) => s.replace('1', '2')), clip()), { state: 'changed' });
eq('찾기: 들여쓰기를 걷은 것', m.findPiece(['  - 가', '    - 나'], clip({ text: '- 가\n  - 나', lines: [1, 2] })).state, 'same');
eq('찾기: 문서가 짧아짐', m.findPiece(['한 줄'], clip()).state, 'changed');
eq('찾기: 같은 글이 둘이면 가까운 곳', m.findPiece(['x', '글', 'x', 'x', 'x', '글'], clip({ text: '글', lines: [5, 5] })).lines, [6, 6]);

// 임의의 글 — 쓰고 읽으면 그대로
const problems = [];
let seed = 7;
const rnd = (k) => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed % k; };
const BITS = ['글', ' ', '\n', '\n\n', '## ', '# ', '<!-- ', ' -->', 'lectern-clip', '-text', '/', '\\', '<!-- lectern-clip-text -->', '<!-- /lectern-clip -->', '<!-- lectern-clip id=c9 -->', '| a |', '```', '\t', '%', '=', '😀', '[^1]'];
const text = (k) => Array.from({ length: rnd(k) }, () => BITS[rnd(BITS.length)]).join('');
const runs = 4000;
for (let i = 0; i < runs; i += 1) {
  const one = (id) => clip({ id, text: text(14), notes: rnd(3) ? '' : text(6).replace(/^\n+/, ''), title: text(4).replace(/\s+/g, ' ').trim(), memo: text(10).trim(), label: text(6) });
  const b = box(Array.from({ length: rnd(4) }, (_, k) => one(`c${k}`)), { note: text(8).trim(), title: text(4).replace(/\s+/g, ' ').trim() });
  const got = round(b);
  if (JSON.stringify(got) !== JSON.stringify(b)) problems.push(`${JSON.stringify(b)} → ${JSON.stringify(got)}`);
}
return { fails, n, problems, runs };
