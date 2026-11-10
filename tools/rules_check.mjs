// 규칙 시험 (브라우저 없이, 1초 안에): 줄 구조(lineops.js)·표 읽기(tabledata.js)·자동 이스케이프(html.js)의 표 점검과 임의의 문서, 자료 모음(tests/corpus).
// tests/test_rules.py 가 돌린다 — Node 가 없으면 건너뛰고, 같은 표 점검은 ui_edges 의 structure·data 가 페이지 안에서 돌린다.
//
//   node tools/rules_check.mjs

import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const load = (rel) => import(pathToFileURL(join(root, rel)).href);
const require = createRequire(import.meta.url);
globalThis.window = { markdownit: require(join(root, 'web/vendor/markdown-it/markdown-it.min.js')) };

let bad = 0;
const say = (name, problems, count) => {
  bad += problems.length;
  console.log(`${problems.length ? 'FAIL' : 'ok  '} ${name} (${count})`);
  for (const p of problems.slice(0, 8)) console.log(`     ${String(p).slice(0, 300)}`);
};
const cases = (file, m) => new Function('m', readFileSync(join(root, file), 'utf-8'))(m);

const lineops = await load('web/js/lineops.js');
const slideops = await load('web/js/slideops.js');
const table = await load('web/js/tabledata.js');
const safe = await load('web/js/html.js');
const notes = await load('web/js/notesdata.js');
{
  const r = cases('tools/edges/lineops_cases.js', lineops);
  say('줄 구조 표 점검', r.fails, r.n);
}
{
  const r = cases('tools/edges/lineops_fuzz.js', lineops);
  say('줄 구조 임의의 문서', r.problems, r.runs);
}
{
  const r = new Function('m', 'lo', readFileSync(join(root, 'tools/edges/slideops_cases.js'), 'utf-8'))(slideops, lineops);
  say('슬라이드 표 점검', r.fails, r.n);
}
{
  const r = new Function('lo', readFileSync(join(root, 'tools/edges/slideops_fuzz.js'), 'utf-8'))(lineops);
  say('슬라이드 줄 구조 임의의 편집', r.problems, r.runs);
}
{
  const r = cases('tools/edges/headstyle_cases.js', await load('web/js/headstyle.js'));
  say('md 문서 스타일 표 점검', r.fails, r.n);
}
{
  const r = cases('tools/edges/chartops_cases.js', await load('web/js/chartops.js'));
  say('차트 값 표 점검', r.fails, r.n);
}
{
  const r = cases('tools/edges/docops_cases.js', await load('web/js/docops.js'));
  say('문서 구성 요소 표 점검', r.fails, r.n);
}
{
  const r = cases('tools/edges/refs_cases.js', await load('web/js/refs.js'));
  say('참조·캡션·인용 표 점검', r.fails, r.n);
}
{
  const r = cases('tools/edges/work_cases.js', await load('web/js/workdata.js'));
  say('업무 관리 표 점검', r.fails, r.n);
}
{
  const r = cases('tools/edges/tabledata_cases.js', table);
  say('표 읽기 표 점검', r.fails, r.n);
}
{
  const r = cases('tools/edges/html_cases.js', safe);
  say('자동 이스케이프 표 점검', r.fails, r.n);
}
{
  const r = cases('tools/edges/notes_cases.js', notes);
  say('메모 글 표 점검', r.fails, r.n);
}

// 설명서·예제의 키 표기: 'Ctrl+`' 의 백틱이 코드 표시로 먹혀 'Ctrl+' 만 남지 않는지 (앱과 같은 Markdown 으로 그려 본다)
{
  const md = globalThis.window.markdownit({ html: true });
  const docs = [];
  const walk = (dir) => {
    for (const entry of readdirSync(join(root, dir), { withFileTypes: true })) {
      const rel = `${dir}/${entry.name}`;
      if (entry.isDirectory()) walk(rel);
      else if (entry.name.endsWith('.md')) docs.push(rel);
    }
  };
  walk('samples');
  walk('web/help');
  docs.push('README.md');
  const lost = [];
  for (const rel of docs) {
    const out = md.render(readFileSync(join(root, rel), 'utf-8'));
    for (const m of out.matchAll(/(Ctrl|Shift|Alt)\+(?=<\/|<code|\)|\s|\||<br|$)/gm)) lost.push(`${rel}: …${out.slice(Math.max(0, m.index - 30), m.index + 40).replace(/\n/g, ' ')}`);
  }
  say('설명서·예제의 키 표기', lost, docs.length);
}

// 자료 모음: 파일마다 같은 이름의 .expect.json 에 적은 대로 읽히는지
const corpus = join(root, 'tests/corpus');
const files = existsSync(corpus) ? readdirSync(corpus).filter((f) => /\.(csv|tsv)$/i.test(f)) : [];
const wrong = [];
for (const file of files) {
  const want = JSON.parse(readFileSync(join(corpus, file.replace(/\.\w+$/, '.expect.json')), 'utf-8'));
  const text = readFileSync(join(corpus, file), 'utf-8').replace(/\r\n?/g, '\n').replace(/^﻿/, '');
  const { rows, lines } = table.parseCsv(text, table.delimiterOf(text, file));
  const found = table.findRegions(rows, lines);
  const region = found.plain ? null : found.regions[found.best];
  const headers = region ? region.headers : rows[0];
  const body = region ? region.rows : rows.slice(1);
  const read = table.readTable(headers, body, { caption: region?.titles.join(' ') ?? '' });
  const got = {
    regions: found.regions.length, plain: found.plain, freq: read.freq, first: read.labels[0], last: read.labels.at(-1),
    points: read.labels.length, series: read.series.map((s) => s.name), units: [...new Set(read.series.map((s) => s.unit))],
  };
  for (const [key, value] of Object.entries(want)) {
    if (JSON.stringify(got[key]) !== JSON.stringify(value)) wrong.push(`${file} ${key}: ${JSON.stringify(got[key])} ≠ ${JSON.stringify(value)}`);
  }
}
say('자료 모음', wrong, files.length);
process.exit(bad ? 1 : 0);
