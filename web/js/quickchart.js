// 빠른 차트 (D86): 표를 그 자리에서 선·막대 차트로 본다 — 앱 창 (문서 속 차트와 달리 움직이는 ECharts, 마우스를 올리면 값). 보기만 한다.
//
// - 여는 곳: 표 우클릭 '차트로 보기', 표의 행을 하이라이트한 곳의 선택 상자(그 행만), 데이터 보기(csv·엑셀)의 '차트로 보기'(거른 행 그대로)와 열 머리 우클릭.
// - 표 읽기는 tabledata.js 의 readTable — 시간·방향·단위를 어림하고, 틀리면 창의 버튼(행↔열, 계열 고르기, 종류, 단위)으로 바로잡는다.
// - 축은 둘까지다: 단위가 같은 계열이 한 축을 쓴다. 처음에는 6개까지 켜 두고, 단위가 셋이면 앞의 둘만 켠다.
// - 자동 종류: 레벨은 막대, 비율·배수는 선. 점이 많으면(LONG) 레벨도 선 — 막대가 뭉개진다.

import { chartLib } from './charts.js';
import { readTable } from './tabledata.js';
import { $, $$, esc, toast } from './util.js';
import { t } from './i18n.js';

const MAX_ON = 6;
const LONG = 36;
const ZOOM = 60;     // 이보다 점이 많으면 아래에 확대 막대
const SAMPLE = 2000;
const FREQ = () => ({ Y: t('연별'), H: t('반기별'), Q: t('분기별'), M: t('월별'), W: t('주별'), D: t('일별') });

let st = null;   // 열린 창 {table, only, swap, kind, scale, read, on: 켠 계열 차례 Set}
let chart = null;
let watcher = null;

const box = () => $('#lec-chart');
export const frequencyName = (freq) => FREQ()[freq] ?? '';

/** 켜 둘 계열: only 가 있으면 그것, 없으면 앞에서부터 MAX_ON 개 — 단위는 둘까지 */
function firstOn(series, only) {
  const on = new Set();
  const keys = new Set();
  series.forEach((s, i) => {
    if (only ? s.name !== only : on.size >= MAX_ON) return;
    if (!keys.has(s.key) && keys.size >= 2) return;
    keys.add(s.key);
    on.add(i);
  });
  return on.size || !only ? on : firstOn(series, null);
}

/** 보일 계열 (단위 버튼으로 거른 것) */
function shown() {
  const { series } = st.read;
  return [...st.on].sort((a, b) => a - b).map((i) => series[i]).filter((s) => st.scale === 'both' || (st.scale === 'rate') === (s.group === 'rate'));
}

/** 축마다의 묶음 — 레벨 먼저 */
function axisKeys(list) {
  const keys = [...new Set(list.map((s) => s.key))];
  return keys.sort((a, b) => (a === 'rate') - (b === 'rate'));
}

const typeOf = (s, points) => (st.kind !== 'auto' ? st.kind : s.group === 'level' && points <= LONG ? 'bar' : 'line');

function option() {
  const { labels } = st.read;
  const list = shown();
  const keys = axisKeys(list);
  const zoom = labels.length > ZOOM;
  const unitOfKey = (k) => list.find((s) => s.key === k)?.unit ?? '';
  return {
    animation: false,
    tooltip: { trigger: 'axis', confine: true },
    legend: { type: 'scroll', top: 0 },
    grid: { left: 12, right: 16, top: 44, bottom: zoom ? 44 : 10, containLabel: true },
    xAxis: { type: 'category', data: labels, axisLabel: { hideOverlap: true } },
    yAxis: keys.map((k, i) => ({
      type: 'value', name: unitOfKey(k), position: i ? 'right' : 'left', splitLine: { show: !i },
      scale: !list.some((s) => s.key === k && typeOf(s, labels.length) === 'bar'),   // 막대는 0 에서 시작해야 크기를 잴 수 있다
    })),
    dataZoom: zoom ? [{ type: 'inside' }, { type: 'slider', height: 20, bottom: 6 }] : [],
    series: list.map((s) => {
      const type = typeOf(s, labels.length);
      return {
        name: s.name, type, data: s.values, yAxisIndex: keys.indexOf(s.key), connectNulls: false, showSymbol: labels.length <= ZOOM,
        sampling: labels.length > SAMPLE ? 'lttb' : undefined,
        tooltip: { valueFormatter: (v) => (v == null ? '-' : `${Number(v).toLocaleString()}${s.unit ? ` ${s.unit}` : ''}`) },
      };
    }),
  };
}

function draw() {
  const { read } = st;
  const has = (rate) => read.series.some((s) => (s.group === 'rate') === rate);
  const both = has(true) && has(false);
  $('#lec-chart-scale').hidden = !both;
  if (!both) st.scale = 'both';
  for (const b of $$('#lec-chart-kind button')) b.setAttribute('aria-pressed', String(b.dataset.kind === st.kind));
  for (const b of $$('#lec-chart-scale button')) b.setAttribute('aria-pressed', String(b.dataset.scale === st.scale));
  $('#lec-chart-series').innerHTML = read.series.map((s, i) => `<label title="${esc(s.name)}"><input type="checkbox" data-i="${i}"${st.on.has(i) ? ' checked' : ''}>`
    + `<span>${esc(s.name)}</span>${s.unit ? `<small>${esc(s.unit)}</small>` : ''}</label>`).join('');
  const notes = [];
  if (read.freq) notes.push(frequencyName(read.freq));
  notes.push(t('{n}개 시점', { n: read.labels.length.toLocaleString() }));
  if (read.skipped) notes.push(t('시점이 아닌 행 {n}개는 뺐습니다', { n: read.skipped }));
  if (read.same) notes.push(t('같은 시점이 여러 행입니다 — 표를 거른 뒤 보면 좋습니다'));
  $('#lec-chart-note').textContent = read.series.length ? notes.join(' · ') : t('차트로 볼 숫자가 없습니다 — 행↔열을 다시 누르면 돌아갑니다');
  chart?.setOption(option(), true);
}

function read() {
  st.read = readTable(st.table.headers, st.table.rows, { swap: st.swap, caption: st.table.caption });
  st.on = firstOn(st.read.series, st.only);
}

/**
 * 표를 차트로 연다. table: {title, headers(머리행), rows(행 — 글의 배열), caption?}. only: 이 이름의 계열만 켠다.
 * 숫자가 없으면 알리고 열지 않는다
 */
export async function openChart(table, { only = null } = {}) {
  closeChart();
  const next = { table, only, swap: false, kind: 'auto', scale: 'both' };
  st = next;
  read();
  if (!st.read.series.length) {
    const swapped = readTable(table.headers, table.rows, { swap: true, caption: table.caption });
    if (!swapped.series.length) {
      st = null;
      toast(t('차트로 볼 숫자가 없습니다'));
      return;
    }
    st.swap = true;
    read();
  }
  $('#lec-chart-title').textContent = table.title || t('차트');
  box().hidden = false;
  draw();
  let lib;
  try {
    lib = await chartLib();
  } catch (e) {
    closeChart();
    toast(e.message, 'error');
    return;
  }
  if (st !== next) return;   // 받는 사이에 닫았다
  const plot = $('#lec-chart-plot');
  chart = lib.echarts.init(plot, lib.theme, { renderer: 'canvas' });
  chart.setOption(option(), true);
  watcher = new ResizeObserver(() => chart?.resize());
  watcher.observe(plot);
  $('#lec-chart-close').focus();
}

/** 창을 닫는다. 열려 있지 않았으면 false */
export function closeChart() {
  if (box().hidden) return false;
  box().hidden = true;
  watcher?.disconnect();
  watcher = null;
  chart?.dispose();
  chart = null;
  st = null;
  return true;
}

function onSeries(e) {
  const box = e.target.closest('input[data-i]');
  if (!box || !st) return;
  const i = Number(box.dataset.i);
  if (box.checked) {
    const keys = new Set([...st.on].map((k) => st.read.series[k].key));
    if (!keys.has(st.read.series[i].key) && keys.size >= 2) {
      box.checked = false;
      toast(t('축은 둘까지입니다 — 다른 단위의 계열을 먼저 끄세요'));
      return;
    }
    st.on.add(i);
  } else st.on.delete(i);
  chart?.setOption(option(), true);
}

/** 표의 행들 (table 요소) → 차트의 표. range: 이 원문 줄 범위의 행만 [a, b] */
export function domTable(table, range = null) {
  const cells = (tr) => [...tr.cells].map((c) => c.innerText.replace(/\s+/g, ' ').trim());
  const [head, ...rest] = [...table.rows];
  const within = (tr) => {
    const m = /^(\d+)-(\d+)$/.exec(tr.dataset.lines || '');
    return !range || (m && +m[1] <= range[1] && +m[2] >= range[0]);
  };
  return { headers: head ? cells(head) : [], rows: rest.filter(within).map(cells) };
}

export function initQuickChart() {
  const el = box();
  el.addEventListener('mousedown', (e) => { if (e.target === el) closeChart(); });
  $('#lec-chart-close').addEventListener('click', closeChart);
  $('#lec-chart-series').addEventListener('change', onSeries);
  $('#lec-chart-kind').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-kind]');
    if (!b || !st) return;
    st.kind = b.dataset.kind;
    draw();
  });
  $('#lec-chart-scale').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-scale]');
    if (!b || !st) return;
    st.scale = b.dataset.scale;
    draw();
  });
  $('#lec-chart-swap').addEventListener('click', () => {
    if (!st) return;
    st.swap = !st.swap;
    read();
    draw();
  });
}
