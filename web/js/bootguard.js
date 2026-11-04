// 시작 스크립트를 받지 못했을 때 (D81): ES 모듈은 하나만 못 받아도 앱 전체가 돌지 않아 빈 화면으로 멈추고, 창 모드에는 F5 도 없다.
// 연결이 잠깐 실패한 것이면(Windows 의 ERR_ADDRESS_IN_USE 등) 다시 불러오면 된다 — 세 번까지, 그래도 안 되면 안내(#lec-boot-fail)를 보인다.
// 일반 스크립트라 맨 먼저 돈다. 대상은 index.html 의 data-boot 스크립트뿐이다 — 처음 쓸 때 불러오는 라이브러리는 그 기능이 알린다.

(() => {
  const KEY = 'lec-boot-tries';
  const MAX = 3;
  let failed = false;

  const tries = () => {
    try {
      return Number(sessionStorage.getItem(KEY)) || 0;
    } catch {
      return MAX;   // 횟수를 세지 못하면 되풀이하지 않는다
    }
  };
  const note = (n) => {
    try {
      if (n) sessionStorage.setItem(KEY, String(n));
      else sessionStorage.removeItem(KEY);
    } catch { /* 세지 못할 뿐이다 */ }
  };
  const tell = () => { document.getElementById('lec-boot-fail').hidden = false; };

  // 스크립트의 error 는 거품처럼 올라오지 않으므로 잡기 단계에서 듣는다
  addEventListener('error', (e) => {
    if (failed || !e.target?.hasAttribute?.('data-boot')) return;
    failed = true;
    const n = tries();
    if (n < MAX) {
      note(n + 1);
      setTimeout(() => location.reload(), 300);
      return;
    }
    note(0);
    if (document.readyState === 'loading') addEventListener('DOMContentLoaded', tell);
    else tell();
  }, true);
  addEventListener('load', () => { if (!failed) note(0); });
})();
