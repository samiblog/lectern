// html 한 파일로 담기 — 화면이 그린 것을 복제해 바깥 파일 없이 열리는 html 로 (D129 의 슬라이드 'html 로 전환'과 D144 의 md 문서 'html 로 저장'이 함께 쓴다).
//
// - 그림: 앱과 같은 출처의 그림은 data URI 로 파일 안에, 인터넷 그림은 주소 그대로(referrer 없이), 그 밖은 뗀다. 복제한 canvas 는 비어 있어 그림(PNG)으로.
// - 걸러 내기: 스크립트·iframe·폼·앱의 단추와 표시를 떼고, 이벤트 속성·javascript: 주소·앱이 다는 data- 속성을 지운다.
//   화면이 이미 DOMPurify 를 거쳤지만 받은 사람의 브라우저에서 열리는 파일이라 한 번 더 거른다.
// - 링크: 인터넷 주소는 새 창으로, mailto 는 그대로, 같은 파일 안의 #절 링크는 keepAnchors 일 때만. 프로젝트 안 문서·파일 링크는 이 파일에서 갈 곳이 없어 글로 남긴다.
// - 스타일: 앱 화면과 같은 차례 (KaTeX, 코드 색, base, 스타일, 내 스타일). KaTeX 글꼴(woff2)은 파일 안에.
// 파일의 글을 지을 때는 html.js 의 esc 를 쓴다 — 화면에 넣는 것이 아니라 파일로 쓰는 글이다.

import { getText } from './api.js';
import { $, $$ } from './util.js';

/** 같은 출처의 주소 → data URI */
export async function dataUrl(url) {
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(String(res.status));
  const blob = await res.blob();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

/** CSP 의 해시 하나 ('sha256-…') */
export async function sha256(text) {
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)));
  return `'sha256-${btoa(String.fromCharCode(...digest))}'`;
}

/** KaTeX CSS — 글꼴(woff2)을 파일 안에. woff·ttf 대체는 지운다 (바깥에 묻지 않게) */
export async function katexCss() {
  const href = $('link[href*="katex"]')?.getAttribute('href') || '/static/vendor/katex/katex.min.css';
  const css = await getText(href);
  const base = new URL('.', new URL(href, location.href)).href;
  const fonts = new Map();
  for (const m of css.matchAll(/url\((fonts\/[\w-]+\.woff2)\)/g)) fonts.set(m[1], '');
  for (const name of fonts.keys()) fonts.set(name, await dataUrl(base + name));
  return css.replace(/url\((fonts\/[\w-]+\.woff2)\) format\("woff2"\)(?:,url\(fonts\/[\w-]+\.(?:woff|ttf)\) format\("(?:woff|truetype)"\))*/g,
    (_, name) => `url(${fonts.get(name)}) format("woff2")`);
}

/** 앱 화면의 문서 스타일 글: 수식이 있으면 KaTeX, 코드 색, base, 고른 스타일, 내 스타일 — 화면과 같은 차례 */
export async function appCss({ math = false } = {}) {
  const hrefs = [
    $('#lec-hljs-css')?.getAttribute('href'),
    $('link[href$="/themes/base.css"]')?.getAttribute('href'),
    $('#lec-theme-css')?.getAttribute('href'),
    $('#lec-user-css')?.getAttribute('href'),
  ].filter(Boolean);
  const texts = math ? [await katexCss()] : [];
  for (const href of hrefs) texts.push(await getText(href));
  return texts;
}

/** <style> 안에 넣을 글 — 글 안의 </style> 이 틀을 닫지 않게 */
export const styleText = (texts) => texts.join('\n').replace(/<\/(style)/gi, '<\\/$1');

/**
 * 화면의 한 부분을 파일에 담을 복제로.
 * @param {HTMLElement} node 화면의 요소 (바꾸지 않는다)
 * @param {{ drop: string, dropAttrs: Set<string>, marks: string[], keepAnchors?: boolean, images: Map<string, string>,
 *   found: { external: number, missing: number, media: number }, dropClass?: (name: string) => boolean, dropVars?: string[] }} opt
 *   drop 은 뗄 요소의 선택자, dropAttrs 는 지울 속성, marks 는 지울 class, dropClass 는 그 밖에 지울 class 의 판정, dropVars 는 style 에서 지울 CSS 변수.
 *   images 는 같은 그림을 한 번만 읽게 나눠 쓰는 표, found 는 알릴 것(인터넷 그림·못 읽은 그림·동영상)을 센다
 */
export async function packClone(node, opt) {
  const { drop, dropAttrs, marks, keepAnchors = false, images, found, dropClass = () => false, dropVars = [] } = opt;
  const clone = /** @type {HTMLElement} */ (node.cloneNode(true));
  const canvases = $$('canvas', node);
  $$('canvas', clone).forEach((c, i) => {   // 복제한 canvas 는 비어 있다 — 그림으로
    const img = document.createElement('img');
    try {
      img.src = canvases[i].toDataURL('image/png');
      img.style.cssText = c.style.cssText;
      img.width = canvases[i].width;
      img.height = canvases[i].height;
    } catch { /* 바깥 그림이 그려진 canvas */ }
    c.replaceWith(img);
  });
  for (const el of $$(drop, clone)) {
    if (el.matches('video, audio')) found.media += 1;
    el.remove();
  }
  for (const el of [clone, ...$$('*', clone)]) {
    el.classList.remove(...marks, ...[...el.classList].filter(dropClass));
    if (!el.classList.length) el.removeAttribute('class');
    if (dropVars.length && el.hasAttribute('style')) {
      for (const v of dropVars) el.style.removeProperty(v);
      if (!el.getAttribute('style')?.trim()) el.removeAttribute('style');
    }
    for (const at of [...el.attributes]) {
      const name = at.name.toLowerCase();
      const js = /^(href|xlink:href|src|action|formaction)$/.test(name) && /^\s*javascript:/i.test(at.value);
      if (name.startsWith('on') || js || dropAttrs.has(name)) el.removeAttribute(at.name);
    }
  }
  for (const a of $$('a', clone)) {
    const href = a.getAttribute('href') || '';
    a.removeAttribute('xlink:href');
    if (/^https?:\/\//i.test(href)) {
      a.setAttribute('target', '_blank');
      a.setAttribute('rel', 'noopener noreferrer');
    } else if (keepAnchors && /^#./.test(href)) {
      // 같은 파일 안의 절·각주·상호 참조 — 그대로
    } else if (!/^mailto:/i.test(href)) {   // 프로젝트 안 문서·절 링크는 이 파일에서 갈 곳이 없다 — 글로 (제목의 경로도 떼고)
      a.removeAttribute('href');
      a.removeAttribute('title');
    }
  }
  for (const input of $$('input', clone)) input.setAttribute('disabled', '');
  for (const el of $$('.chart-ok, pre.mermaid, img.zoomable', clone)) el.removeAttribute('title');   // '누르면 크게 봅니다' — 이 파일에서는 커지지 않는다
  for (const img of $$('img', clone)) {
    img.removeAttribute('srcset');
    img.removeAttribute('loading');
    const src = img.getAttribute('src') || '';
    if (!src || src.startsWith('data:')) continue;
    const url = new URL(src, location.href);
    if (url.origin === location.origin) {
      try {
        if (!images.has(url.href)) images.set(url.href, await dataUrl(url.href));
        img.setAttribute('src', images.get(url.href));
      } catch {
        img.removeAttribute('src');
        found.missing += 1;
      }
    } else if (/^https?:$/.test(url.protocol)) {
      img.setAttribute('referrerpolicy', 'no-referrer');
      found.external += 1;
    } else img.removeAttribute('src');
  }
  return clone;
}
