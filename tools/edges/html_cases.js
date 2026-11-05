// html.js 의 표 점검 — rules_check.mjs 가 돌린다 (m: html.js 모듈)
const { html, raw, esc, setHtml, addHtml, Safe } = m;
const fails = [];
let n = 0;
const same = (name, got, want) => {
  n += 1;
  if (String(got) !== want) fails.push(`${name}: ${JSON.stringify(String(got))} ≠ ${JSON.stringify(want)}`);
};

same('글은 이스케이프', html`<p>${'<b>&'}</p>`, '<p>&lt;b&gt;&amp;</p>');
same('따옴표', html`<a title="${`"x" 'y'`}">`, '<a title="&quot;x&quot; &#39;y&#39;">');
same('숫자', html`${0}·${1.5}`, '0·1.5');
same('없는 값은 빈칸', html`[${null}${undefined}]`, '[]');
same('참·거짓은 글로', html`aria-pressed="${false}" x="${true}"`, 'aria-pressed="false" x="true"');
same('빈 글', html`[${''}]`, '[]');
same('값 없는 템플릿', html`<br>`, '<br>');
same('앞뒤 값', html`${'a'}<i>${'b'}`, 'a<i>b');
same('조각은 그대로', html`<p>${html`<b>${'<'}</b>`}</p>`, '<p><b>&lt;</b></p>');
same('두 번 이스케이프하지 않음', html`${html`${html`${'&'}`}`}`, '&amp;');
same('배열은 이어서', html`<ul>${[1, 2].map((v) => html`<li>${v}</li>`)}</ul>`, '<ul><li>1</li><li>2</li></ul>');
same('배열 속 글은 이스케이프', html`${['<', html`<b>`]}`, '&lt;<b>');
same('겹친 배열', html`${[[html`<a>`], ['&']]}`, '<a>&amp;');
same('빈 배열', html`[${[]}]`, '[]');
same('raw 는 그대로', html`${raw('<svg>')}`, '<svg>');
same('raw 의 없는 값', raw(null), '');
same('esc', esc(`<&>"'`), '&lt;&amp;&gt;&quot;&#39;');
same('esc 의 없는 값', esc(undefined), '');
same('글이 된 조각은 이스케이프 — 이으면 안 되는 까닭', html`${`${html`<b>`}`}`, '&lt;b&gt;');
n += 1;
if (!(html`x` instanceof Safe)) fails.push('html 의 결과는 Safe');

const box = { innerHTML: '', added: [], insertAdjacentHTML(where, text) { this.added.push([where, text]); } };
setHtml(box, html`<b>${'<'}</b>`);
same('setHtml 조각', box.innerHTML, '<b>&lt;</b>');
setHtml(box, '<b>');
same('setHtml 글은 글자로', box.innerHTML, '&lt;b&gt;');
setHtml(box, [html`<a>`, html`<b>`]);
same('setHtml 배열', box.innerHTML, '<a><b>');
addHtml(box, 'beforeend', html`<i>`);
same('addHtml', box.added[0].join(' '), 'beforeend <i>');
addHtml(box, 'afterbegin', '<i>');
same('addHtml 글은 글자로', box.added[1].join(' '), 'afterbegin &lt;i&gt;');

return { fails, n };
