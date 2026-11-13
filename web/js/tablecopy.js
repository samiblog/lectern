// 표와 차트 데이터의 복사 (D136): 탭으로 나눈 글(엑셀이 칸으로 나눔)과 간단한 HTML 표(워드·메일이 표로 붙임)를 함께 클립보드에.
// - md 문서의 표마다 표 상자 오른쪽 위의 [복사] 단추 (doc.js 의 decorateTables 가 단다 — 마우스를 올리면 보인다). 우클릭 '표 복사'와 같다.
// - 차트의 [복사]는 chartdata.js 가 그 차트의 데이터로 같은 형식을 만든다.

import { html } from './html.js';
import { toast, copyText } from './util.js';
import { t } from './i18n.js';

/** 칸들 [[{text, head, align}]] → 간단한 HTML 표 (글) */
export function tableMarkup(rows) {
  return html`<table border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse">${rows.map((r) => html`<tr>${r.map((c) => {
    const style = c.align ? html` style="text-align:${c.align}"` : '';
    return c.head ? html`<th${style}>${c.text}</th>` : html`<td${style}>${c.text}</td>`;
  })}</tr>`)}</table>`.text;
}

/** 문서의 표 → {tsv, html} — 보이는 그대로 */
export function tableData(table) {
  const rows = [...table.rows].map((r) => [...r.cells].map((c) => {
    const align = c.ownerDocument.defaultView.getComputedStyle(c).textAlign;
    return { text: c.innerText.replace(/\s+/g, ' ').trim(), head: c.tagName === 'TH', align: /right|center/.test(align) ? align : '' };
  }));
  return { tsv: rows.map((r) => r.map((c) => c.text).join('\t')).join('\n'), html: tableMarkup(rows) };
}

export function tableSize(table) {
  const rows = table.tBodies[0]?.rows.length ?? table.rows.length;
  const cols = Math.max(0, ...[...table.rows].map((r) => r.cells.length));
  return t('{rows}행 {cols}열', { rows, cols });
}

/** 여러 형식을 함께 클립보드에 넣고 알린다. parts: {'text/plain', 'text/html', 'image/png'} */
export async function copyParts(parts, what) {
  let ok = false;
  try {
    const data = {};
    for (const [type, value] of Object.entries(parts)) data[type] = typeof value === 'string' ? new Blob([value], { type }) : value;
    await navigator.clipboard.write([new ClipboardItem(data)]);
    ok = true;
  } catch {
    if (typeof parts['text/plain'] === 'string') ok = await copyText(parts['text/plain']);
  }
  toast(ok ? t('복사했습니다: {what}', { what }) : t('복사하지 못했습니다'));
  return ok;
}

/** 표 하나를 복사한다 (단추·우클릭) */
export function copyTable(table) {
  const data = tableData(table);
  return copyParts({ 'text/plain': data.tsv, 'text/html': data.html }, `${t('표')} ${tableSize(table)}`);
}

/** 표 상자에 [복사] 단추를 단다 (doc.js — 표를 상자로 감쌀 때). Lectern 슬라이드의 표에는 달지 않는다 */
export function addTableCopy(wrap) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'table-copy';
  btn.textContent = t('복사');
  btn.title = t('표 복사 — 엑셀에 붙이면 칸이 나뉘고, 워드·메일에는 표로');
  wrap.append(btn);   // 표 뒤에 — 상자의 첫 자식이 표라고 보는 곳이 있다 (tablefit.js). 자리는 CSS 가 오른쪽 위로
}

export function initTableCopy() {
  // 단추는 문서를 그릴 때마다 새로 생긴다 — 누르기는 한곳에서 받는다
  document.addEventListener('click', (e) => {
    const btn = e.target.closest?.('.table-copy');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    const table = btn.parentElement?.querySelector(':scope > table');
    if (table) copyTable(table);
  }, true);
}
