// 지면 틀 (D145): md 문서를 틀에 담아 html 한 파일로 — 내보내기 창이 html 로 저장하고, PDF 는 이 html 을 숨은 창이 찍는다
// (같은 파일이라 html 과 PDF 가 같은 꼴). 틀은 서버(lectern/layouts.py)가 거른 것 — 앱의 틀 web/layouts, 내 틀은 설정 폴더 layouts.
//
// 틀의 자리 (스크립트 없이 — 뼈대를 DOMParser 로 읽어 채운다):
// - {{키}} 맨 앞 설정의 값 (한국어 키도 — ALIAS). {{title}} 은 맨 앞 설정 title, 없으면 문서의 # 제목, 파일 이름.
//   {{date}} 는 date(없으면 오늘), {{date:long}}·{{date:dot}}·{{date:iso}} 날짜 모양. {{a|b|'글'}} 앞의 것이 비면 다음 것.
//   {{t:한국어|English}} 문서 언어(맨 앞 설정 lang, 없으면 화면 언어)로 고른다.
// - {{body}} 본문 — 맨 앞 설정 표, 틀이 {{title}} 을 쓰면 맨 앞 # 제목, 자리로 옮긴 박스글은 뺀다. 캡션 단락에 class caption.
//   {{toc}} 차례 (## · ###). {{slot:이름}} 은 <!-- box: 이름 --> 박스글을 옮겨 오고, 없으면 맨 앞 설정의 그 키.
// - data-if="키"·"!키"·"slot:이름" — 값이 없으면(! 는 있으면) 그 요소를 뺀다. data-each="키" — 목록 값마다 그 요소를 되풀이 ({{.}}).
// - <style> 안에서는 {{css:식}} 만 — CSS 글자로 막아 넣는다 (쪽 머리의 문서 제목 등). 그 밖의 {{…}} 는 지운다.
// 글은 화면이 그린 문서를 복제한다 (mdhtml.js 와 같은 걸러 내기 — D144). 스타일은 화면 스타일이 아니라 늘 같은 바탕
// (base.css·기본 스타일·밝은 코드 색, 종이용 @media print 는 뺀다) 위에 _base.css 와 틀의 CSS.

import { S } from './store.js';
import { getJSON, getText } from './api.js';
import { basename } from './util.js';
import { esc } from './html.js';
import { LANG } from './i18n.js';
import { katexCss, styleText, packClone } from './htmlpack.js';
import { MD_PACK, foundNotes } from './mdhtml.js';
import { readYaml } from './slides.js';
import { splitFrontMatter } from './markdown.js';

/** 한국어로 적은 맨 앞 설정 키 → 틀이 쓰는 이름 (둘 다로 찾는다) */
export const ALIAS = {
  제목: 'title', 부제: 'subtitle', 부제목: 'subtitle', 작성자: 'author', 저자: 'author', 지은이: 'author', 연구진: 'author', 날짜: 'date', 일자: 'date',
  기관: 'org', 기관명: 'org', 부서: 'dept', 담당부서: 'dept', 번호: 'number', 보고서번호: 'number', 호수: 'number', 시리즈: 'series',
  고객: 'client', 발주처: 'client', 소속: 'affiliation', 주제어: 'keywords', 키워드: 'keywords', 판: 'version', 버전: 'version',
  회사: 'company', 기업: 'company', 종목코드: 'ticker', 업종: 'sector', 장: 'chapter', 책: 'book', 꼬리표: 'kicker', 짧은제목: 'short_title',
};
const CAPTION = /^(표|그림|박스|사진|도표|전시물|Table|Figure|Box|Exhibit|Chart)-\d+/i;

let cache = null;   // 틀 목록 {at, list}

/** 고를 수 있는 틀 [{id, name, group, pages, flow, fields, slots, description, user}] — 창을 열 때마다 새로 (내 틀을 더했을 수 있다) */
export async function listLayouts(fresh = false) {
  if (!fresh && cache && Date.now() - cache.at < 3000) return cache.list;
  const r = await getJSON('/api/layouts');
  cache = { at: Date.now(), list: r.layouts || [] };
  return cache.list;
}

/**
 * 칸의 문서의 맨 앞 설정 — 한국어 키와 틀의 이름 둘 다로
 * @returns {Record<string, any>}
 */
export function fieldsOf(pane) {
  const fm = /** @type {Record<string, any>} */ (readYaml(splitFrontMatter((pane.source?.lines || []).join('\n')).frontMatter || '') || {});
  /** @type {Record<string, any>} */
  const out = { ...fm };
  for (const [k, v] of Object.entries(fm)) {
    const en = ALIAS[k.replace(/\s+/g, '')];
    if (en && out[en] == null) out[en] = v;
  }
  for (const [ko, en] of Object.entries(ALIAS)) if (out[en] != null && out[ko] == null) out[ko] = out[en];
  return out;
}

const textOf = (v) => (v == null ? '' : Array.isArray(v) ? v.map(String).join(', ') : String(v)).trim();
const listOf = (v) => (Array.isArray(v) ? v.map((x) => String(x).trim()) : textOf(v).split(',').map((x) => x.trim())).filter(Boolean);
/** CSS content 의 글자 하나로 (printdoc.cssString 과 같다 — 그 모듈을 부르면 순환) */
const cssString = (s) => `"${String(s).replace(/[\u0000-\u001f\u007f]+/g, ' ').replace(/[\\"]/g, '\\$&')}"`;

/** 날짜 모양: 없으면 오늘, 읽을 수 없는 글이면 그대로 */
function dateText(raw, fmt, en) {
  const given = textOf(raw);
  const m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(given);
  if (given && !m) return given;
  if (given && !fmt) return given;
  const d = m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : new Date();
  const [y, mo, da] = [d.getFullYear(), d.getMonth() + 1, d.getDate()];
  if (fmt === 'iso') return `${y}-${String(mo).padStart(2, '0')}-${String(da).padStart(2, '0')}`;
  if (fmt === 'dot') return `${y}. ${mo}. ${da}.`;
  return en ? new Intl.DateTimeFormat('en-US', { dateStyle: 'long' }).format(d) : `${y}년 ${mo}월 ${da}일`;   // i18n-ok (문서 언어의 날짜 — 화면 언어가 아니다)
}

/** 자리의 식 하나를 글로 (body·toc·slot 은 여기서 다루지 않는다) */
function evalExpr(expr, ctx) {
  const e = expr.trim();
  if (e.startsWith('t:')) {
    const [ko, en] = e.slice(2).split('|');
    return (ctx.en ? en ?? ko : ko).trim();
  }
  for (const part of e.split('|')) {
    const p = part.trim();
    if (/^'.*'$/s.test(p)) return p.slice(1, -1);
    const [key, fmt] = p.split(':');
    let v = '';
    if (key === 'date') v = dateText(ctx.fields.date, fmt, ctx.en);
    else if (key === 'title') v = ctx.title;
    else if (key === 'slot') v = textOf(ctx.fields[fmt]);
    else v = textOf(ctx.fields[p] ?? ctx.fields[key]);
    if (v) return v;
  }
  return '';
}

/** <style> 안의 {{css:식}} 을 CSS 글자로, 그 밖의 자리는 지운다 */
const fillCss = (css, ctx) => css.replace(/\{\{\s*css:([^}]*)\}\}/g, (_, e) => cssString(evalExpr(e, ctx))).replace(/\{\{[^}]*\}\}/g, '');

/** 글 안의 @media print { … } 덩어리를 뗀다 — base.css 의 종이 규칙(색을 검게)이 틀의 색을 덮지 않게 */
function dropPrintBlocks(css) {
  let out = '';
  let i = 0;
  for (;;) {
    const at = css.indexOf('@media print', i);
    if (at < 0) return out + css.slice(i);
    const open = css.indexOf('{', at);
    if (open < 0) return out + css.slice(i);
    out += css.slice(i, at);
    let depth = 0;
    let j = open;
    for (; j < css.length; j++) {
      if (css[j] === '{') depth += 1;
      else if (css[j] === '}' && --depth === 0) break;
    }
    i = j + 1;
  }
}

/** 차례: 본문의 ## · ### (id 가 있는 것) */
function tocOf(doc, body) {
  const nav = doc.createElement('nav');
  nav.className = 'lay-toc';
  const ol = doc.createElement('ol');
  for (const h of body.querySelectorAll(':scope > h2[id], :scope > h3[id]')) {
    const li = doc.createElement('li');
    li.className = `lv${h.tagName[1]}`;
    const a = doc.createElement('a');
    a.href = `#${h.id}`;
    a.textContent = h.textContent.trim();
    li.append(a);
    ol.append(li);
  }
  nav.append(ol);
  return nav;
}

/** 자리 이름의 글: 옮겨 온 박스글, 없으면 맨 앞 설정의 값 (목록이면 목록) */
function slotNode(doc, name, ctx) {
  const box = ctx.slots.get(name);
  if (box) return box;
  const v = ctx.fields[name] ?? ctx.fields[ALIAS[name]];
  if (v == null || !textOf(v)) return null;
  if (Array.isArray(v)) {
    const ul = doc.createElement('ul');
    for (const x of v) {
      const li = doc.createElement('li');
      li.textContent = String(x);
      ul.append(li);
    }
    return ul;
  }
  const p = doc.createElement('p');
  p.textContent = textOf(v);
  return p;
}

const truthy = (cond, ctx) => {
  const neg = cond.trim().startsWith('!');
  const key = cond.trim().replace(/^!/, '').trim();
  const has = key.startsWith('slot:') ? ctx.slots.has(key.slice(5)) || !!textOf(ctx.fields[key.slice(5)]) : !!evalExpr(key, ctx);
  return neg ? !has : has;
};

/** 뼈대를 채운다 — 자리 글은 글자로만 넣고(html 로 읽지 않는다), body·toc·slot 은 요소로 */
function fillMarkup(markup, ctx) {
  const doc = new DOMParser().parseFromString(`<!doctype html><body>${markup}</body>`, 'text/html');
  const root = doc.body;
  for (const el of [...root.querySelectorAll('[data-each]')]) {
    for (const item of listOf(ctx.fields[el.getAttribute('data-each')])) {
      const c = /** @type {Element} */ (el.cloneNode(true));
      c.removeAttribute('data-each');
      for (const n of textNodes(doc, c)) n.data = n.data.replace(/\{\{\s*\.\s*\}\}/g, item);
      el.before(c);
    }
    el.remove();
  }
  for (const el of [...root.querySelectorAll('[data-if]')]) {
    if (!el.isConnected) continue;
    if (truthy(el.getAttribute('data-if'), ctx)) el.removeAttribute('data-if');
    else el.remove();
  }
  for (const n of textNodes(doc, root)) {
    if (!n.data.includes('{{')) continue;
    const frag = doc.createDocumentFragment();
    let last = 0;
    for (const m of n.data.matchAll(/\{\{([^}]*)\}\}/g)) {
      frag.append(n.data.slice(last, m.index));
      const e = m[1].trim();
      if (e === 'body') frag.append(ctx.body);
      else if (e === 'toc') frag.append(tocOf(doc, ctx.body));
      else if (e.startsWith('slot:')) {
        const [name, ...rest] = e.slice(5).split('|');
        const node = slotNode(doc, name.trim(), ctx);
        frag.append(node || evalExpr(rest.join('|'), ctx));
      } else frag.append(evalExpr(e, ctx));
      last = m.index + m[0].length;
    }
    frag.append(n.data.slice(last));
    n.replaceWith(frag);
  }
  for (const el of root.querySelectorAll('*')) {
    for (const at of [...el.attributes]) if (at.value.includes('{{')) el.setAttribute(at.name, at.value.replace(/\{\{([^}]*)\}\}/g, (_, e) => evalExpr(e, ctx)));
  }
  return root;
}

function textNodes(doc, root) {
  const out = [];
  const walk = doc.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) out.push(/** @type {Text} */ (n));
  return out;
}

/** 틀의 루트 class — lay-파일 이름 (글자·숫자·- 만) */
export const layoutClass = (id) => `lay-${String(id).replace(/^user\//, '').replace(/[^\p{L}\p{N}-]+/gu, '-')}`;

/**
 * 칸이 그린 md 문서를 틀에 담아 html 한 파일의 글로: {text, title, notes, missing(틀이 쓰는데 비어 있는 맨 앞 설정 키)}
 * @param {Pane} pane
 * @param {string} path
 * @param {{ id: string, name: string, flow: boolean, fields: string[] }} info 틀 목록의 한 줄
 */
export async function buildLayoutHtml(pane, path, info) {
  const layout = await getJSON(`/api/layouts/${info.id.split('/').map(encodeURIComponent).join('/')}`);
  const view = pane.view;
  const fields = fieldsOf(pane);
  const lang = textOf(fields.lang) || document.documentElement.lang || LANG;
  const h1 = view.querySelector(':scope > h1')?.textContent.replace(/\s+/g, ' ').trim();
  const title = textOf(fields.title) || h1 || basename(path).replace(/\.[^.]+$/, '');
  const images = new Map();
  const found = { external: 0, missing: 0, media: 0 };
  const body = await packClone(view, { ...MD_PACK, keepAnchors: true, images, found });
  body.className = 'md-body';
  if (S.config?.external_images === false) {   // 인터넷 그림을 끈 설정 — 주소를 담지 않는다
    for (const img of body.querySelectorAll('img[src^="http"]')) img.removeAttribute('src');
    found.external = 0;
  }
  if (/\{\{\s*title\b/.test(layout.markup)) {   // 틀이 제목을 따로 쓰면 본문 맨 앞의 # 제목은 뺀다
    const first = body.firstElementChild;
    if (first?.tagName === 'H1') first.remove();
  }
  for (const p of body.querySelectorAll('p[id]')) if (CAPTION.test(p.id)) p.classList.add('caption');
  const wanted = new Set([...layout.markup.matchAll(/(?:\{\{\s*|data-if="!?)slot:([^}|"]+)/g)].map((m) => m[1].trim()));
  const slots = new Map();
  for (const box of body.querySelectorAll(':scope > aside.lec-textbox[data-slot]')) {
    const name = box.getAttribute('data-slot');
    if (wanted.has(name) && !slots.has(name)) {
      // 자리에 옮긴 박스글의 제목 줄: '박스 1. …' 이나 굵은 글뿐인 제목이면 뺀다 (자리에 제목 띠가 있다). 그 밖의 한 줄 문단은 글 그대로
      const head = box.querySelector(':scope > .lec-textbox-title');
      if (head) {
        const strong = head.children.length === 1 && head.firstElementChild?.tagName === 'STRONG' && head.textContent.trim() === head.firstElementChild.textContent.trim();
        if (strong || /^\s*(박스|Box)\s*\d+\s*\./i.test(head.textContent)) head.remove();
        else head.classList.remove('lec-textbox-title');
      }
      slots.set(name, box);
      box.remove();
    }
  }
  const ctx = { fields, title, en: /^en/i.test(lang), body, slots };
  const markup = fillMarkup(layout.markup, ctx);
  const math = !!view.querySelector('.katex');
  const css = styleText([
    math ? await katexCss() : '',
    await getText('/static/vendor/highlight/github.min.css'),
    dropPrintBlocks(await getText('/static/themes/base.css')),
    await getText('/static/themes/default.css'),
    layout.base,
    fillCss(layout.css, ctx),
  ]);
  const external = found.external > 0;
  const policy = [
    "default-src 'none'",
    "style-src 'self' 'unsafe-inline'",
    `img-src data:${external ? ' https: http:' : ''}`,
    'font-src data:',
    "base-uri 'none'",
    "form-action 'none'",
  ].join('; ');
  const cls = `lec-layout ${layoutClass(info.id)} ${info.flow ? 'lay-flow' : 'lay-paged'}`;
  const text = [
    '<!doctype html>',
    `<html lang="${esc(lang)}">`,
    '<head>',
    '<meta charset="utf-8">',
    '<meta name="generator" content="Lectern">',
    `<meta http-equiv="Content-Security-Policy" content="${esc(policy)}">`,
    '<meta name="referrer" content="no-referrer">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    `<meta name="lectern-source" content="${esc(basename(path))}">`,
    `<meta name="lectern-layout" content="${esc(info.id)}">`,
    `<title>${esc(title)}</title>`,
    `<style>${css}</style>`,
    '</head>',
    '<body>',
    `<div class="${esc(cls)}">${markup.innerHTML}</div>`,
    '</body>',
    '</html>',
    '',
  ].join('\n').replace(/\r\n?/g, '\n');
  const missing = (info.fields || []).filter((k) => !['title', 'date'].includes(k) && !textOf(fields[k] ?? fields[ALIAS[k]]));
  return { text, title, notes: foundNotes(found), missing };
}

/** 틀이 쓰는 맨 앞 설정의 견본 — 내보내기 창의 '맨 앞 설정 견본 복사' */
export const fieldSample = (info, fields) => ['---', ...(info.fields || []).filter((k) => !textOf(fields[k])).map((k) => `${k}: `), '---'].join('\n');
