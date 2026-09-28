/* 경쟁사 흔적 추적 — app-traces.js(window.TRACES)를 화면에 그린다.
   탭: 경쟁사→전시회 / 전시회→경쟁사 / 새로 찾은 전시회 / 원문·광고 / 만든 방법·한계 */
(function () {
  "use strict";
  var D = window.TRACES || { rivals: [], fields: [], pairs: [], rows: [], generated: "" };
  var RIV = {}, FLD = {};
  D.rivals.forEach(function (r) { RIV[r.key] = r; });
  D.fields.forEach(function (f) { FLD[f.key] = f.name; });

  // 다른 화면에서 traces.html?q=InnoTrans 로 넘어오면 그 검색어로 열어 준다
  var q0 = (location.search.match(/[?&]q=([^&]*)/) || [])[1];
  q0 = q0 ? decodeURIComponent(q0.replace(/\+/g, " ")) : "";
  var S = { tab: "pair", q: q0, riv: "", fld: "", year: "", freshOnly: false, kind: "", basis: "", limit: 200 };
  var main = document.getElementById("main");
  var drawer = document.getElementById("drawer");
  var scrim = document.getElementById("scrim");

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function num(n) { return (n || 0).toLocaleString("ko-KR"); }
  function rivName(k) { return RIV[k] ? RIV[k].name : k; }
  function fldName(k) { return FLD[k] || "기타"; }
  function host(u) {
    return String(u || "").replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/.*$/, "");
  }
  var KIND = { news: "뉴스", ad: "광고", official: "회사 공식", web: "웹", list: "출품사 명단" };
  // 이 줄을 무엇으로 확인했나 — 출품사 명단(확실) / 뉴스·광고 글(정황) / 둘 다
  function basisOf(p) { return p.has_list && p.has_text ? "both" : p.has_list ? "list" : "text"; }
  var BASIS = {
    both: '<span class="badge known">명단 + 글</span>',
    list: '<span class="badge known">출품사 명단</span>',
    text: '<span class="badge fresh">글에서만 (흔적)</span>'
  };

  // ---------------------------------------------------------------- 헤더
  function header() {
    var fresh = D.pairs.filter(function (p) { return !p.known; }).length;
    var both = D.pairs.filter(function (p) { return basisOf(p) === "both"; }).length;
    var fairs = {}, oldest = "9999";
    D.pairs.forEach(function (p) { fairs[p.fair] = 1; });
    D.rows.forEach(function (r) { if (r.date && r.date < oldest) oldest = r.date; });
    var withRiv = {};
    D.pairs.forEach(function (p) { withRiv[p.rival] = 1; });

    document.getElementById("subline").textContent =
      D.generated + " 기준 · 두 가지를 한 표에 합쳤습니다 — 전시회 주최 측 '출품사 명단'으로 확인한 것(확실)과, " +
      "뉴스·보도자료·회사 소식란·링크드인 광고에서 찾은 '흔적'(정황, 과거·명단 비공개 전시회까지)" +
      (oldest !== "9999" ? " (가장 오래된 근거 " + oldest.slice(0, 4) + "년)." : ".");
    document.getElementById("kpis").innerHTML =
      '<div class="kpi"><b>' + num(D.pairs.length) + "</b><span>경쟁사 × 전시회</span></div>" +
      '<div class="kpi hot"><b>' + num(fresh) + "</b><span>글에서만 찾은 것</span></div>" +
      '<div class="kpi"><b>' + num(both) + "</b><span>명단·글 둘 다</span></div>" +
      '<div class="kpi"><b>' + num(Object.keys(fairs).length) + "</b><span>전시회</span></div>" +
      '<div class="kpi"><b>' + num(Object.keys(withRiv).length) + "</b><span>경쟁사</span></div>";
  }

  // ---------------------------------------------------------------- 찾기
  function hay(p) {
    var t = p.fair + " " + rivName(p.rival) + " " + fldName(p.field) + " " + (p.year || "") + " " +
      (p.booth || "") + " " + (p.city || "");
    (p.src || []).forEach(function (s) { t += " " + s.t + " " + s.s; });
    return t.toLowerCase();
  }
  function rowHay(r) {
    return (r.title + " " + (r.ko || "") + " " + r.desc + " " + r.site + " " + rivName(r.rival) + " " +
      (r.fairs || []).map(function (f) { return f.fair; }).join(" ")).toLowerCase();
  }

  function pairs() {
    var q = S.q.trim().toLowerCase();
    return D.pairs.filter(function (p) {
      if (S.riv && p.rival !== S.riv) return false;
      if (S.fld && p.field !== S.fld) return false;
      if (S.year && String(p.year) !== S.year) return false;
      if (S.freshOnly && p.known) return false;
      if (S.basis === "off") { if (!p.off) return false; }
      else if (S.basis && basisOf(p) !== S.basis) return false;
      if (q && hay(p).indexOf(q) < 0) return false;
      return true;
    });
  }

  // ---------------------------------------------------------------- 공통 조각
  function srcHtml(src) {
    return '<div class="srcs">' + (src || []).map(function (s) {
      var site = s.s || host(s.u) || "출처";
      var label = (s.d ? s.d.slice(0, 7) + " " : "") + site;
      var tail = s.k === "news" && /뉴스|news/i.test(site) ? "" : "<em>" + (KIND[s.k] || s.k) + "</em>";
      return '<a href="' + esc(s.u) + '" target="_blank" rel="noopener" title="' + esc(s.t) + '">' +
        esc(label) + tail + "</a>";
    }).join("") + "</div>";
  }

  function toolbar(extra) {
    var years = {};
    D.pairs.forEach(function (p) { if (p.year) years[p.year] = 1; });
    var ys = Object.keys(years).sort().reverse();
    var rivOpts = D.rivals.slice().sort(function (a, b) { return a.name.localeCompare(b.name); });
    return '<div class="card ttool">' +
      '<select id="fRiv"><option value="">경쟁사 전체</option>' +
      rivOpts.map(function (r) {
        return '<option value="' + r.key + '"' + (S.riv === r.key ? " selected" : "") + ">" + esc(r.name) + "</option>";
      }).join("") + "</select>" +
      '<select id="fYear"><option value="">연도 전체</option>' +
      ys.map(function (y) {
        return '<option value="' + y + '"' + (S.year === y ? " selected" : "") + ">" + y + "년</option>";
      }).join("") + "</select>" +
      (extra || "") +
      (extra ? "" : '<select id="fBasis">' + [["", "근거 전체"], ["both", "명단 + 글 둘 다"],
        ["list", "출품사 명단으로 확인"], ["off", "회사 공식 전시 일정"],
        ["text", "글에서만 찾은 흔적"]].map(function (o) {
          return '<option value="' + o[0] + '"' + (S.basis === o[0] ? " selected" : "") + ">" + o[1] + "</option>";
        }).join("") + "</select>") +
      '<label class="ck"><input type="checkbox" id="fFresh"' + (S.freshOnly ? " checked" : "") +
      "> 출품사 명단으로는 못 잡던 것만</label>" +
      '<span class="cnt" id="cnt"></span></div>';
  }

  function fieldChips(list) {
    var cnt = {};
    list.forEach(function (p) { cnt[p.field] = (cnt[p.field] || 0) + 1; });
    var keys = Object.keys(cnt).sort(function (a, b) { return cnt[b] - cnt[a]; });
    if (!keys.length) return "";
    return '<div class="fchips"><span class="lbl">분야</span>' +
      '<button class="fchip' + (S.fld ? "" : " on") + '" data-fld="">전체<b>' + list.length + "</b></button>" +
      keys.map(function (k) {
        return '<button class="fchip' + (S.fld === k ? " on" : "") + '" data-fld="' + k + '">' +
          esc(fldName(k)) + "<b>" + cnt[k] + "</b></button>";
      }).join("") + "</div>";
  }

  function wire() {
    var r = document.getElementById("fRiv"), y = document.getElementById("fYear"),
      f = document.getElementById("fFresh"), k = document.getElementById("fKind"),
      bs = document.getElementById("fBasis");
    if (bs) bs.onchange = function () { S.basis = bs.value; S.limit = 200; render(); };
    if (r) r.onchange = function () { S.riv = r.value; S.limit = 200; render(); };
    if (y) y.onchange = function () { S.year = y.value; S.limit = 200; render(); };
    if (f) f.onchange = function () { S.freshOnly = f.checked; S.limit = 200; render(); };
    if (k) k.onchange = function () { S.kind = k.value; S.limit = 200; render(); };
    Array.prototype.forEach.call(main.querySelectorAll("[data-fld]"), function (b) {
      b.onclick = function () { S.fld = b.getAttribute("data-fld"); S.limit = 200; render(); };
    });
    Array.prototype.forEach.call(main.querySelectorAll("[data-pair]"), function (b) {
      b.onclick = function (e) {
        if (e.target.closest("a")) return;
        openPair(b.getAttribute("data-pair"));
      };
    });
    Array.prototype.forEach.call(main.querySelectorAll("[data-more]"), function (b) {
      b.onclick = function () { S.limit += 200; render(); };
    });
    Array.prototype.forEach.call(main.querySelectorAll("[data-goriv]"), function (b) {
      b.onclick = function () { S.riv = b.getAttribute("data-goriv"); S.tab = "pair"; setTab(); render(); window.scrollTo(0, 0); };
    });
  }

  // ---------------------------------------------------------------- 탭: 경쟁사 → 전시회
  function tabPair() {
    var list = pairs();
    var shown = list.slice(0, S.limit);
    main.innerHTML = toolbar() + fieldChips(list) +
      '<div class="card tblwrap"><table class="ttbl"><thead><tr>' +
      "<th>경쟁사</th><th>전시회 · 부스</th><th>연도</th><th>분야</th><th>근거</th><th>건수</th>" +
      "</tr></thead><tbody>" +
      shown.map(function (p, i) {
        var idx = D.pairs.indexOf(p);
        return '<tr class="pr" data-pair="' + idx + '">' +
          '<td class="riv">' + esc(rivName(p.rival)) +
          "<small>" + esc((RIV[p.rival] || {}).country || "") + "</small></td>" +
          '<td class="fr">' + esc(p.fair) +
          (p.booth ? '<small class="booth">부스 ' + esc(p.booth) + "</small>" : "") +
          '<div class="bs">' + BASIS[basisOf(p)] +
          (p.off ? ' <span class="badge official" title="경쟁사 홈페이지의 전시회·이벤트 목록에 올라 있음">회사 공식 발표</span>' : "") +
          (p.list_kind === "visitor" ? ' <span class="badge web">참관</span>' : "") +
          (p.how === "발굴" ? ' <span class="badge dig">기사에서 캐냄</span>' : "") + "</div></td>" +
          '<td class="yr">' + (p.year || "—") + "</td>" +
          "<td>" + esc(fldName(p.field)) + "</td>" +
          '<td class="ev">' + esc((p.src[0] || {}).t || "") + srcHtml(p.src) + "</td>" +
          '<td class="n">' + p.n + "</td></tr>";
      }).join("") + "</tbody></table>" +
      (list.length > shown.length
        ? '<div class="morebar"><button class="rbtn" data-more="1">더 보기 (' +
          num(list.length - shown.length) + "건 남음)</button></div>" : "") +
      "</div>";
    var c = document.getElementById("cnt");
    if (c) c.innerHTML = "<b>" + num(list.length) + "</b>건";
    wire();
  }

  // ---------------------------------------------------------------- 탭: 전시회 → 경쟁사
  function tabFair() {
    var list = pairs();
    var byFair = {};
    list.forEach(function (p) {
      var f = byFair[p.fair] || (byFair[p.fair] = { fair: p.fair, field: p.field, years: {}, rivals: {}, n: 0, src: [] });
      f.n += p.n;
      if (p.year) f.years[p.year] = 1;
      f.rivals[p.rival] = f.rivals[p.rival] || p.known;
      p.src.forEach(function (s) {
        if (f.src.length < 8 && f.src.every(function (x) { return x.u !== s.u; })) f.src.push(s);
      });
    });
    var cards = Object.keys(byFair).map(function (k) { return byFair[k]; });
    cards.sort(function (a, b) {
      return Object.keys(b.rivals).length - Object.keys(a.rivals).length || b.n - a.n || a.fair.localeCompare(b.fair);
    });
    main.innerHTML = toolbar() + fieldChips(list) +
      '<div class="tgrid">' + cards.slice(0, S.limit).map(function (f) {
        var ys = Object.keys(f.years).sort().reverse().join(", ");
        return '<div class="card tcard"><h3>' + esc(f.fair) + "</h3>" +
          '<div class="meta">' + esc(fldName(f.field)) + (ys ? " · " + ys : "") +
          " · 경쟁사 " + Object.keys(f.rivals).length + "곳 · 근거 " + f.n + "건</div>" +
          '<div class="rl">' + Object.keys(f.rivals).map(function (r) {
            return '<span class="' + (f.rivals[r] ? "" : "fresh") + '" data-goriv="' + r + '" title="' +
              (f.rivals[r] ? "출품사 명단으로도 확인된 경쟁사" : "흔적으로만 확인 — 명단에는 없던 경쟁사") +
              '">' + esc(rivName(r)) + "</span>";
          }).join("") + "</div>" + srcHtml(f.src) + "</div>";
      }).join("") + "</div>" +
      (cards.length > S.limit
        ? '<div class="morebar"><button class="rbtn" data-more="1">더 보기</button></div>' : "");
    var c = document.getElementById("cnt");
    if (c) c.innerHTML = "<b>" + num(cards.length) + "</b>개 전시회";
    wire();
  }

  // ---------------------------------------------------------------- 탭: 새로 찾은 전시회
  function tabNew() {
    var prev = S.freshOnly;
    S.freshOnly = true;
    var list = pairs();
    S.freshOnly = prev;
    var shown = list.slice(0, S.limit);
    main.innerHTML =
      '<p class="note" style="padding:0 2px">경쟁사 레이더(<b>출품사 명단</b>을 읽는 쪽)에서는 못 잡았는데, ' +
      "뉴스·보도자료·광고에는 남아 있던 흔적입니다. <b>주최 측이 명단을 안 여는 전시회</b>와 " +
      "<b>이미 끝나 명단이 내려간 과거 회차</b>가 여기 모입니다. 참가 확정이 아니라 '정황'이므로 " +
      "출처 링크를 열어 직접 확인하세요.</p>" +
      toolbar() + fieldChips(list) +
      '<div class="card tblwrap"><table class="ttbl"><thead><tr>' +
      "<th>경쟁사</th><th>전시회</th><th>연도</th><th>어떻게 찾았나</th><th>근거</th>" +
      "</tr></thead><tbody>" +
      shown.map(function (p) {
        var idx = D.pairs.indexOf(p);
        return '<tr class="pr" data-pair="' + idx + '">' +
          '<td class="riv">' + esc(rivName(p.rival)) + "</td>" +
          '<td class="fr">' + esc(p.fair) + "</td>" +
          '<td class="yr">' + (p.year || "—") + "</td>" +
          "<td>" + (p.how === "발굴"
            ? '<span class="badge dig">기사 문장에서 이름을 캐냄</span>'
            : '<span class="badge news">전시회 이름 사전과 일치</span>') + "</td>" +
          '<td class="ev">' + esc((p.src[0] || {}).t || "") + srcHtml(p.src) + "</td></tr>";
      }).join("") + "</tbody></table>" +
      (list.length > shown.length
        ? '<div class="morebar"><button class="rbtn" data-more="1">더 보기 (' +
          num(list.length - shown.length) + "건 남음)</button></div>" : "") +
      "</div>";
    var c = document.getElementById("cnt");
    if (c) c.innerHTML = "<b>" + num(list.length) + "</b>건";
    wire();
  }

  // ---------------------------------------------------------------- 탭: 원문·광고
  function tabRaw() {
    var q = S.q.trim().toLowerCase();
    var list = D.rows.filter(function (r) {
      if (S.riv && r.rival !== S.riv) return false;
      if (S.kind && r.kind !== S.kind) return false;
      if (S.year && String(r.date || "").slice(0, 4) !== S.year) return false;
      if (S.freshOnly && !(r.fairs || []).length) return false;
      if (q && rowHay(r).indexOf(q) < 0) return false;
      return true;
    });
    var shown = list.slice(0, S.limit);
    var kindSel = '<select id="fKind"><option value="">출처 전체</option>' +
      ["news", "official", "ad", "web"].map(function (k) {
        return '<option value="' + k + '"' + (S.kind === k ? " selected" : "") + ">" + KIND[k] + "</option>";
      }).join("") + "</select>";
    main.innerHTML = toolbar(kindSel).replace(
      "출품사 명단으로는 못 잡던 것만", "전시회 이름이 잡힌 글만") +
      '<div class="card rawlist">' + shown.map(function (r) {
        return '<div class="rawrow">' +
          '<div class="when">' + esc(r.date || "—") + "</div>" +
          '<div class="who">' + esc(rivName(r.rival)) + "</div>" +
          '<div class="body"><a class="tt" href="' + esc(r.url) + '" target="_blank" rel="noopener">' +
          esc(r.title) + "</a>" +
          (r.ko ? '<span class="ko">' + esc(r.ko) + "</span>" : "") +
          '<div class="sub"><span class="badge ' + r.kind + '">' + (KIND[r.kind] || r.kind) + "</span> " +
          esc(r.site || host(r.url)) +
          ((r.fairs || []).length
            ? " · <b>" + r.fairs.map(function (f) {
                return esc(f.fair) + (f.year ? " " + f.year : "");
              }).join(", ") + "</b>"
            : "") + "</div></div></div>";
      }).join("") + "</div>" +
      (list.length > shown.length
        ? '<div class="morebar"><button class="rbtn" data-more="1">더 보기 (' +
          num(list.length - shown.length) + "건 남음)</button></div>" : "");
    var c = document.getElementById("cnt");
    if (c) c.innerHTML = "<b>" + num(list.length) + "</b>건";
    wire();
  }

  // ---------------------------------------------------------------- 서랍
  function openPair(idx) {
    var p = D.pairs[+idx];
    if (!p) return;
    var rows = D.rows.filter(function (r) {
      // 같은 해 글만 — DesignCon 2027 줄에 2026년 기사가 섞이지 않게
      return r.rival === p.rival && (r.fairs || []).some(function (f) {
        var y = f.year || +(r.date || "").slice(0, 4) || 0;
        return f.fair === p.fair && (!p.year || !y || y === p.year);
      });
    });
    drawer.innerHTML = '<div class="dhead"><button class="dclose" id="dwX">✕</button><h3>' +
      esc(rivName(p.rival)) + "</h3><p>" + esc(p.fair) + (p.year ? " " + p.year : "") +
      " · 분야 " + esc(fldName(p.field)) + " · 근거 " + p.n + "건</p></div>" +
      '<div class="dbody"><p class="note">' +
      ({ both: "<b>출품사 명단</b>과 <b>" + (p.off ? "회사 공식 전시 일정" : "뉴스·광고 글") + "</b> 양쪽에서 확인됐습니다.",
         list: "전시회 주최 측 <b>출품사 명단</b>으로 확인했습니다.",
         text: "출품사 명단으로는 못 잡고 <b>글에서만 확인</b>된 흔적입니다. 참가 확정이 아닐 수 있습니다."
       })[basisOf(p)] +
      "</p>" +
      (p.src || []).filter(function (x) { return x.k === "list"; }).map(function (x) {
        return '<div class="rawrow" style="padding-left:0;padding-right:0"><div class="body">' +
          '<a class="tt" href="' + esc(x.u) + '" target="_blank" rel="noopener">' + esc(x.t) + "</a>" +
          '<div class="sub"><span class="badge official">출품사 명단</span> ' + esc(x.d || "") +
          " · 주최 측 공개 명단에서 이름을 확인</div></div></div>";
      }).join("") +
      rows.map(function (r) {
        return '<div class="rawrow" style="padding-left:0;padding-right:0">' +
          '<div class="body"><a class="tt" href="' + esc(r.url) + '" target="_blank" rel="noopener">' +
          esc(r.title) + "</a>" +
          (r.ko ? '<span class="ko">' + esc(r.ko) + "</span>" : "") +
          (r.desc ? '<div class="sub">' + esc(r.desc.slice(0, 220)) + "</div>" : "") +
          '<div class="sub"><span class="badge ' + r.kind + '">' + (KIND[r.kind] || r.kind) + "</span> " +
          esc(r.date || "") + " " + esc(r.site || host(r.url)) + "</div></div></div>";
      }).join("") + "</div>";
    drawer.classList.add("on");
    scrim.classList.add("on");
    document.getElementById("dwX").onclick = closeDrawer;
  }
  function closeDrawer() { drawer.classList.remove("on"); scrim.classList.remove("on"); }
  scrim.onclick = closeDrawer;
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrawer(); });

  // ---------------------------------------------------------------- 탭: 만든 방법·한계
  function tabHow() {
    var byKind = {};
    D.rows.forEach(function (r) { byKind[r.kind] = (byKind[r.kind] || 0) + 1; });
    main.innerHTML = '<div class="card how">' +
      "<h3>왜 따로 만들었나</h3><ul>" +
      "<li>경쟁사 레이더는 <b>전시회 주최 측이 공개한 출품사 명단</b>을 읽습니다. 확실하지만, " +
      "<b>명단을 안 여는 전시회</b>(서울 ADEX·KADEX·electronica China·InnoTrans 등)와 " +
      "<b>이미 끝나 명단이 내려간 과거 회차</b>는 그 방식으로는 영원히 안 잡힙니다.</li>" +
      "<li>이 화면은 반대편에서 팝니다 — 경쟁사 이름이 박힌 <b>뉴스·보도자료·회사 소식란·링크드인 광고</b>를 " +
      "모아, 그 글에 적힌 전시회 이름을 뽑아냅니다. 그래서 <b>과거 흔적</b>과 <b>명단 비공개 전시회</b>가 여기서 잡힙니다.</li>" +
      "<li><b>🏁 경쟁사 → 전시회</b> 표에는 두 가지를 <b>합쳐</b> 보여줍니다 — 경쟁사 레이더가 출품사 명단으로 확인한 기록 " +
      "(<span class=\"badge official\">출품사 명단</span>, 부스 번호 포함)과 이 화면이 글에서 찾은 흔적 " +
      "(<span class=\"badge fresh\">글에서만</span>). 양쪽에서 다 나온 것은 <span class=\"badge known\">명단 + 글</span>입니다. " +
      "같은 경쟁사·같은 해에 이름이 같으면 한 줄로 합치되, <i>electronica</i>와 <i>electronica India</i>처럼 " +
      "지역이 붙은 다른 전시회는 합치지 않습니다.</li>" +
      "</ul><h3>어디서 모았나</h3><table><tr><th>출처</th><th>건수</th><th>설명</th></tr>" +
      "<tr><td>뉴스</td><td>" + num(byKind.news || 0) + "</td><td>구글 뉴스 RSS(영·일·한·중·독) + 빙 뉴스. " +
      "<code>after:2010-01-01</code> 같은 기간 질의로 옛 기사까지 꺼냅니다. 경쟁사마다 일반형·기간형·" +
      "전시회 짝지음형·현지어형으로 나눠 물어봅니다.</td></tr>" +
      "<tr><td>회사 소식란</td><td>" + num(byKind.official || 0) + "</td><td>봇을 막지 않는 곳만 직접 읽습니다 — " +
      "이리소·야자키·I-PEX·JAE·로젠베르거·앱티브. 나머지(몰렉스·암페놀·TE·하팅 등)는 차단됩니다.</td></tr>" +
      "<tr><td>링크드인 광고</td><td>" + num(byKind.ad || 0) + "</td><td>광고 라이브러리는 로그인 없이 볼 수 있지만 " +
      "서버 접근이 403이라, 브라우저로 받아 <code>data/linkedin_ads.json</code>에 넣어 둡니다(분기 1회 수동).</td></tr>" +
      "</table><h3>전시회 이름은 어떻게 알아내나</h3><ul>" +
      "<li>직접 정리한 <b>전시회 이름 사전</b>(커넥터 업계가 나가는 곳 150여 곳)과, 우리 전시회 DB·로봇 DB에서 " +
      "가져온 이름을 합쳐 약 6,000개 규칙으로 글을 훑습니다.</li>" +
      "<li>사전에 없으면 문장에서 직접 캅니다 — <i>“…at IOTFA 2017”</i>, <i>「国際ロボット展」に出展</i>, " +
      "<i>인터배터리 2026에 참가</i> 같은 꼴을 잡아 이름을 뽑습니다(<span class=\"badge dig\">기사에서 캐냄</span> 표시). " +
      "<b>우리가 모르던 전시회를 찾아내는 게 이 방식의 목적</b>입니다.</li>" +
      "<li>이름 주변 40자에서 연도를 읽어 붙입니다. 같은 경쟁사·같은 해에 이름이 겹치면 하나로 합칩니다.</li>" +
      "</ul><h3>한계 — 이 숫자를 그대로 믿으면 안 되는 이유</h3><ul>" +
      "<li><b>참가 확정이 아닙니다.</b> “나갈 예정”이라는 기사도, 남의 부스에 제품이 걸린 기사도 같이 잡힙니다. " +
      "출품사 명단으로 확인된 것은 <span class=\"badge known\">명단 확인됨</span>으로 구분해 뒀습니다.</li>" +
      "<li><b>안 나온다고 안 나간 게 아닙니다.</b> 보도자료를 안 내는 회사(이리소·JST·LEMO·라디알·연호전자)는 " +
      "흔적이 거의 없습니다. 히로세도 일본 기사는 제품 소식 위주라 전시회는 잘 안 걸립니다.</li>" +
      "<li><b>구글 뉴스는 하루 질의 수에 한도가 있습니다.</b> 한 번에 2,000건 넘게 물으면 뒤쪽은 빈 응답이 옵니다. " +
      "그래서 받은 글을 <code>data/traces_raw.json</code>에 쌓아 두고 <b>매일 조금씩 더</b> 채웁니다 — " +
      "날이 갈수록 흔적이 늘어납니다.</li>" +
      "<li><b>링크드인 광고는 최근 1년치</b>만 남습니다. 옛 광고는 여기서 안 나옵니다.</li>" +
      "<li>한국어 줄은 구글 번역(키 없는 엔드포인트) 기계번역입니다.</li>" +
      "</ul></div>";
  }

  // ---------------------------------------------------------------- 검색창
  var tq = document.getElementById("tq"), timer = null;
  tq.oninput = function () {
    document.getElementById("tclear").hidden = !tq.value;
    clearTimeout(timer);
    timer = setTimeout(function () { S.q = tq.value; S.limit = 200; render(); }, 180);
  };
  document.getElementById("tclear").onclick = function () {
    tq.value = ""; S.q = ""; this.hidden = true; S.limit = 200; render(); tq.focus();
  };

  // ---------------------------------------------------------------- 탭 전환
  function setTab() {
    Array.prototype.forEach.call(document.querySelectorAll("#tabs button"), function (b) {
      b.classList.toggle("on", b.getAttribute("data-tab") === S.tab);
    });
  }
  Array.prototype.forEach.call(document.querySelectorAll("#tabs button"), function (b) {
    b.onclick = function () { S.tab = b.getAttribute("data-tab"); S.limit = 200; setTab(); render(); window.scrollTo(0, 0); };
  });

  function render() {
    if (S.tab === "fair") tabFair();
    else if (S.tab === "new") tabNew();
    else if (S.tab === "raw") tabRaw();
    else if (S.tab === "how") tabHow();
    else tabPair();
  }

  if (S.q) { tq.value = S.q; document.getElementById("tclear").hidden = false; }
  header();
  render();
})();
