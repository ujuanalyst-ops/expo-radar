# 링크드인 광고 라이브러리 받는 법

`https://www.linkedin.com/ad-library/search?accountOwner=<회사명>` 은 **로그인 없이** 볼 수 있지만
서버(urllib/curl)로 부르면 403이다. 브라우저로 열어야 한다. 그래서 이 자료만 사람 손으로 받아
`data/linkedin_ads.json` 에 넣어 두고, `traces.py` 가 매일 그 파일을 읽어 쓴다.

## 갱신 절차 (분기에 한 번이면 충분하다)

1. 브라우저에서 경쟁사마다 아래 주소를 연다.
   `https://www.linkedin.com/ad-library/search?accountOwner=Molex`
   (`Amphenol`, `TE Connectivity`, `Hirose Electric`, `Yazaki`, `I-PEX`, `IRISO`, `JAE`, `JST`,
    `Aptiv`, `Luxshare`, `Samtec`, `HARTING`, `Rosenberger`, `Phoenix Contact`, `ODU`, `LEMO`,
    `Smiths Interconnect`, `Radiall`, `Glenair`, `Kyocera AVX`, `Würth Elektronik`, `Stäubli`,
    `BizLink`, `ITT Cannon`, `SOURIAU`, `JONHON`, `Hosiden`, `Foxconn Interconnect Technology`)

2. 페이지마다 개발자도구 콘솔에서 아래를 실행해 광고를 쌓는다.

```js
(function(q){const o=[];document.querySelectorAll('.search-result-item').forEach(el=>{
  const a=el.querySelector('a[href*="/ad-library/detail/"]');
  o.push({q:q,t:el.innerText.replace(/\s+/g,' ').trim().slice(0,400),u:a?a.href.split('?')[0]:''})});
  let s=[];try{s=JSON.parse(localStorage.getItem('__liads')||'[]')}catch(e){}
  s=s.concat(o); localStorage.setItem('__liads',JSON.stringify(s)); return {q:q,got:o.length,total:s.length}})('Molex')
```

3. 다 돌았으면 전시회가 언급된 광고만 뽑는다.

```js
(function(){var s=JSON.parse(localStorage.getItem('__liads')||'[]'),seen={},u=[];
 s.forEach(a=>{if(!seen[a.u]){seen[a.u]=1;u.push(a)}});
 var rx=/booth|exhibit|trade\s*show|expo\b|fair\b|showcase|pavilion|visit us|see us at|will be (at|in)|messe|salon|conference|summit|出展|展示会|参展|전시회|부스/i;
 return JSON.stringify(u.filter(a=>rx.test(a.t)),null,1)})()
```

4. 나온 것을 `data/linkedin_ads.json` 의 `ads` 배열에 넣는다.
   `rival` 은 `traces.py` 의 `TARGETS` 키와 맞춘다(molex·amphenol·te·hirose…).
   `localStorage.removeItem('__liads')` 로 정리.

## 한계

- 광고 라이브러리는 **최근 1년쯤**만 남긴다. 옛 광고는 여기서 안 나온다(뉴스 쪽에서 캔다).
- 목록은 한 화면에 24건씩이라, 광고가 많은 회사는 스크롤해서 더 받아야 한다.
- 광고 대부분은 채용·제품 홍보다. 2026-09-28 수집 기준 477건 중 전시회가 언급된 것은 13건이었다.
