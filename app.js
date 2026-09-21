/* 전시회·박람회 레이더 — 화면. window.DATA(app-data.js) + window.GEO(app-geo.js)만 읽는다. */
(function () {
  "use strict";
  var D = window.DATA, GEO = window.GEO;
  var EV = D.events, CN = D.countries, TODAY = D.today;
  var IND = {}, IND_ORDER = D.industries.map(function (x) { return x[0]; });
  D.industries.forEach(function (x) { IND[x[0]] = { emoji: x[1], name: x[2] }; });
  var RIVDATA = D.rivals || { list: [], blocked: {}, sources: [], unmatched: [] };
  var RIV = {};
  RIVDATA.list.forEach(function (r) { RIV[r.key] = r; });
  function rivName(k) { return (RIV[k] && RIV[k].name) || k; }

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var main = $("#main");

  // ---------------------------------------------------------------- 값 다루기
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function flag(cc) {
    if (!cc || cc.length !== 2 || cc === "?") return "🏳️";
    return String.fromCodePoint(0x1f1e6 + cc.charCodeAt(0) - 65, 0x1f1e6 + cc.charCodeAt(1) - 65);
  }
  function cname(cc) { return (CN[cc] && CN[cc].ko) || cc || "미상"; }
  function region(cc) { return (CN[cc] && CN[cc].region) || "기타"; }
  function days(a, b) { return Math.round((new Date(b) - new Date(a)) / 86400000); }
  function dday(e) { return days(TODAY, e.s); }
  function ymd(s) { return s ? s.slice(0, 4) + "." + s.slice(5, 7) + "." + s.slice(8, 10) : ""; }
  function period(e) {
    if (e.p === "month") return e.s.slice(0, 4) + "년 " + (+e.s.slice(5, 7)) + "월 중";
    return ymd(e.s) + (e.e && e.e !== e.s ? " ~ " + (e.e.slice(0, 4) === e.s.slice(0, 4)
      ? e.e.slice(5, 7) + "." + e.e.slice(8, 10) : ymd(e.e)) : "");
  }
  function stars(r) {
    var n = Math.max(0, Math.min(5, Math.round((r || 0) / 2)));
    return n ? '<span class="stars" title="업무 관련도 ' + r + '">' + "★".repeat(n) + "</span>" : "";
  }
  function num(n) { return (n || 0).toLocaleString("ko-KR"); }
  function isKR(e) { return e.c === "KR"; }
  function live(e) { return e.s <= TODAY && (e.e || e.s) >= TODAY; }

  // 출처를 처음 붙인 날은 그 출처 전체가 같은 first_seen 이라 '신규'가 아니다 → 출처별 기준선 제외
  var SRC_BASE = {};
  EV.forEach(function (e) {
    var k = e.src[0];
    if (!SRC_BASE[k] || e.fs < SRC_BASE[k]) SRC_BASE[k] = e.fs;
  });
  function reallyNew(e) { return e.fs > SRC_BASE[e.src[0]]; }

  // ---------------------------------------------------------------- 상태
  var S = {
    tab: "soon", q: "", span: "90", scope: "all", rel: 0, sup: false,
    inds: {}, conts: {}, cc: "", riv: "", limit: 120, cal: TODAY.slice(0, 7), newDays: 7,
  };
  function anyOn(o) { for (var k in o) if (o[k]) return true; return false; }
  function keysOn(o) { return Object.keys(o).filter(function (k) { return o[k]; }); }

  function matchQ(e, q) {
    if (!q) return true;
    var hay = (e.t + " " + (e.te || "") + " " + (e.ci || "") + " " + (e.v || "") + " " + cname(e.c) +
      " " + (e.sum || "") + " " + (e.items || "") + " " + (e.sec || []).join(" ") + " " + (e.org || "")).toLowerCase();
    return q.toLowerCase().split(/\s+/).every(function (w) { return hay.indexOf(w) >= 0; });
  }

  function filtered(opt) {
    opt = opt || {};
    var q = S.q.trim(), horizon = null;
    if (S.span !== "all" && S.span !== "past" && !opt.ignoreSpan) {
      var d = new Date(TODAY); d.setDate(d.getDate() + (+S.span));
      horizon = d.toISOString().slice(0, 10);
    }
    var inds = keysOn(S.inds), conts = keysOn(S.conts);
    return EV.filter(function (e) {
      var end = e.e || e.s;
      if (S.span === "past") { if (end >= TODAY) return false; }
      else if (end < TODAY) return false;
      if (horizon && e.s > horizon) return false;
      if (S.scope === "kr" && !isKR(e)) return false;
      if (S.scope === "ov" && isKR(e)) return false;
      if (S.rel && (e.rel || 0) < S.rel) return false;
      if (S.sup && !(e.sup || e.ap)) return false;
      if (inds.length && !e.ind.some(function (i) { return S.inds[i]; })) return false;
      if (conts.length && !S.conts[region(e.c)]) return false;
      if (S.cc && e.c !== S.cc) return false;
      if (S.riv && !opt.ignoreRiv && !(e.riv || []).some(function (x) { return x.r === S.riv; })) return false;
      return matchQ(e, q);
    });
  }

  // ---------------------------------------------------------------- 공통 조각
  function rowHTML(e) {
    var dd = dday(e), tags = [];
    if (isKR(e)) tags.push('<span class="tag kr">국내</span>');
    if (e.sup) tags.push('<span class="tag sup">국고지원</span>');
    if (e.ap) {
      var ae = e.ap.end;
      tags.push('<span class="tag apply">한국관 모집' +
        (ae && ae >= TODAY ? " D-" + days(TODAY, ae) : ae ? " 마감" : "") + "</span>");
    }
    if (e.ufi) tags.push('<span class="tag ufi">UFI 인증</span>');
    if (e.riv && e.riv.length) {
      tags.push('<span class="tag riv">🏁 경쟁사 ' + e.riv.length + "곳</span>");
    }
    if (reallyNew(e) && days(e.fs, TODAY) <= 7) tags.push('<span class="tag new">NEW</span>');
    var box = live(e) ? "live" : (dd <= 30 ? "soon" : "");
    var dayTop = live(e) ? "진행" : (dd === 0 ? "오늘" : (dd > 0 ? "D-" + dd : "종료"));
    var meta = [flag(e.c) + " " + cname(e.c) + (e.ci ? " · " + esc(e.ci) : ""),
      e.v ? "📍 " + esc(e.v) : "", period(e),
      e.ex ? "🏢 참가 " + num(e.ex) + "사" : "", e.vi ? "👥 " + num(e.vi) + "명" : ""]
      .filter(Boolean).map(function (x) { return "<span>" + x + "</span>"; }).join("");
    return '<button class="row" data-id="' + esc(e.id) + '">' +
      '<span class="daybox ' + box + '"><b>' + (+e.s.slice(5, 7)) + "/" + (+e.s.slice(8, 10)) +
      "</b><span>" + dayTop + "</span></span>" +
      '<span><span class="rtitle">' + esc(e.t) + (e.te ? " <em>" + esc(e.te) + "</em>" : "") +
      "</span>" + '<span class="rmeta">' + meta + "</span></span>" +
      '<span class="rright">' + tags.join("") + stars(e.rel) +
      '<span class="tag">' + esc(IND[e.ind[0]].emoji + " " + IND[e.ind[0]].name.split("·")[0]) + "</span></span></button>";
  }

  function listHTML(list, limit, nogroup) {
    if (!list.length) return '<div class="card empty">조건에 맞는 전시회가 없습니다.</div>';
    var shown = list.slice(0, limit || list.length), out = [], cur = "";
    shown.forEach(function (e) {
      var ym = e.s.slice(0, 7);
      if (!nogroup && ym !== cur) {
        cur = ym;
        var n = list.filter(function (x) { return x.s.slice(0, 7) === ym; }).length;
        out.push('<div class="monthhead">' + (+ym.slice(0, 4)) + "년 " + (+ym.slice(5, 7)) + "월 <i></i>" +
          "<span>" + n + "건</span></div>");
      }
      out.push(rowHTML(e));
    });
    var html = '<div class="rows">' + out.join("") + "</div>";
    if (list.length > shown.length) {
      html += '<button class="more" id="more">더 보기 (' + num(list.length - shown.length) + "건 남음)</button>";
    }
    return html;
  }

  function chipRow(label, items, activeMap, onToggle) {
    var html = '<div class="frow"><span class="flabel">' + label + "</span>";
    items.forEach(function (it) {
      html += '<button class="chip' + (activeMap[it.key] ? " on" : "") + '" data-chip="' + esc(it.key) + '">' +
        esc(it.label) + (it.n != null ? " <b>" + num(it.n) + "</b>" : "") + "</button>";
    });
    return html + "</div>";
  }

  function bindChips(root, sel, map, after) {
    Array.prototype.forEach.call(root.querySelectorAll(sel), function (b) {
      b.onclick = function () {
        var k = b.getAttribute("data-chip");
        map[k] = !map[k];
        S.limit = 120;
        (after || render)();
      };
    });
  }

  function seg(items, cur, attr) {
    return '<span class="seg">' + items.map(function (it) {
      return '<button data-' + attr + '="' + it[0] + '"' + (cur === it[0] ? ' class="on"' : "") + ">" + it[1] + "</button>";
    }).join("") + "</span>";
  }

  function bindSeg(root, attr, apply) {
    Array.prototype.forEach.call(root.querySelectorAll("[data-" + attr + "]"), function (b) {
      b.onclick = function () { apply(b.getAttribute("data-" + attr)); S.limit = 120; render(); };
    });
  }

  // ---------------------------------------------------------------- 필터 바
  function filterBar(pool, opts) {
    opts = opts || {};
    var indCount = {}, contCount = {};
    pool.forEach(function (e) {
      e.ind.forEach(function (i) { indCount[i] = (indCount[i] || 0) + 1; });
      var r = region(e.c); contCount[r] = (contCount[r] || 0) + 1;
    });
    var indItems = IND_ORDER.filter(function (c) { return indCount[c]; }).map(function (c) {
      return { key: c, label: IND[c].emoji + " " + IND[c].name, n: indCount[c] };
    }).sort(function (a, b) { return b.n - a.n; });
    var contItems = Object.keys(contCount).sort(function (a, b) { return contCount[b] - contCount[a]; })
      .map(function (r) { return { key: r, label: r, n: contCount[r] }; });

    return '<div class="filters card pad">' +
      '<div class="frow"><span class="flabel">기간</span>' +
      (opts.noSpan ? '<span class="note">앞으로 열리는 전시회 전부 (이 탭은 기간을 가리지 않습니다)</span>'
        : seg([["30", "30일"], ["90", "3개월"], ["180", "6개월"], ["all", "전체"], ["past", "지난 전시"]], S.span, "span")) +
      '<span class="flabel" style="margin-left:10px">개최지</span>' +
      seg([["all", "전체"], ["kr", "🇰🇷 국내"], ["ov", "🌍 해외"]], S.scope, "scope") +
      '<span class="flabel" style="margin-left:10px">관련도</span>' +
      seg([["0", "전체"], ["3", "★★ 이상"], ["5", "★★★ 이상"]], String(S.rel), "rel") +
      '<button class="chip' + (S.sup ? " on" : "") + '" id="supchip" style="margin-left:10px">💰 국고지원·한국관만</button>' +
      "</div>" +
      chipRow("산업", indItems, S.inds) +
      chipRow("대륙", contItems, S.conts) +
      (S.cc ? '<div class="frow"><span class="flabel">나라</span><button class="chip on" id="ccchip">' +
        flag(S.cc) + " " + cname(S.cc) + " ✕</button></div>" : "") +
      "</div>";
  }

  function bindFilterBar(root) {
    bindSeg(root, "span", function (v) { S.span = v; });
    bindSeg(root, "scope", function (v) { S.scope = v; });
    bindSeg(root, "rel", function (v) { S.rel = +v; });
    bindChips(root, ".filters .frow:nth-child(2) .chip", S.inds);
    bindChips(root, ".filters .frow:nth-child(3) .chip", S.conts);
    var sc = $("#supchip", root);
    if (sc) sc.onclick = function () { S.sup = !S.sup; S.limit = 120; render(); };
    var cc = $("#ccchip", root);
    if (cc) cc.onclick = function () { S.cc = ""; render(); };
  }

  // ---------------------------------------------------------------- 탭: 곧 열리는 전시회
  function viewSoon() {
    var pool = filtered();
    var sorted = pool.slice().sort(function (a, b) { return a.s < b.s ? -1 : a.s > b.s ? 1 : (b.rel || 0) - (a.rel || 0); });
    main.innerHTML = filterBar(pool) +
      '<div class="sec-title"><h2>' + (S.span === "past" ? "지난 전시회" : "곧 열리는 전시회") + "</h2>" +
      "<small>" + num(pool.length) + "건 · 국내 " + num(pool.filter(isKR).length) +
      " · 해외 " + num(pool.length - pool.filter(isKR).length) + "</small></div>" +
      listHTML(sorted, S.limit);
    bindFilterBar(main);
  }

  // ---------------------------------------------------------------- 탭: 우리 관련·지원
  function viewPick() {
    var pool = filtered({ ignoreSpan: true }).filter(function (e) { return e.s >= TODAY; });
    var apply = pool.filter(function (e) { return e.ap || e.sup; })
      .sort(function (a, b) { return a.s < b.s ? -1 : a.s > b.s ? 1 : 0; });
    var top = pool.filter(function (e) { return (e.rel || 0) >= 4; })
      .sort(function (a, b) { return (b.rel - a.rel) || (a.s < b.s ? -1 : 1); });
    var big = pool.filter(function (e) { return (e.ex || 0) >= 300 || (e.ar || 0) >= 30000; })
      .sort(function (a, b) { return (b.ex || 0) - (a.ex || 0); });

    main.innerHTML = filterBar(pool, { noSpan: true }) +
      '<div class="sec-title"><h2>💰 정부지원·한국관 모집 전시회</h2><small>' + num(apply.length) +
      "건 · KOTRA 국고지원 전시회와 한국관 참가 모집공고가 붙은 전시회</small></div>" +
      listHTML(apply, 40) +
      '<div class="sec-title" style="margin-top:26px"><h2>🎯 우리 사업과 가까운 전시회</h2><small>' +
      "커넥터·전장·전자부품·자동차·기계 키워드 기준 상위 " + num(Math.min(top.length, 60)) + "건</small></div>" +
      listHTML(top, 60, true) +
      '<div class="sec-title" style="margin-top:26px"><h2>🏟 규모가 큰 전시회</h2><small>참가업체 300사 이상 또는 30,000㎡ 이상 ' +
      num(big.length) + "건 (KOTRA 조사 기준)</small></div>" +
      listHTML(big, 30, true);
    bindFilterBar(main);
  }

  // ---------------------------------------------------------------- 탭: 세계 지도
  function viewMap() {
    var pool = filtered();
    var cnt = {};
    pool.forEach(function (e) { if (e.c && e.c !== "?") cnt[e.c] = (cnt[e.c] || 0) + 1; });
    var max = Math.max.apply(null, [1].concat(Object.keys(cnt).map(function (k) { return cnt[k]; })));
    var paths = [], dots = [];
    Object.keys(GEO.shapes).forEach(function (cc) {
      var g = GEO.shapes[cc], n = cnt[cc] || 0;
      var t = n ? 0.18 + 0.82 * Math.pow(n / max, 0.42) : 0;
      var fill = n ? "rgba(18,87,166," + t.toFixed(3) + ")" : "#dfe6ee";
      if (g.d) {
        paths.push('<path class="cn' + (S.cc === cc ? " on" : "") + '" d="' + g.d + '" fill="' + fill +
          '" data-cc="' + cc + '"></path>');
      } else if (n) {
        dots.push('<circle class="dot" cx="' + g.cx + '" cy="' + g.cy + '" r="' +
          (2.5 + 4 * Math.pow(n / max, 0.4)).toFixed(1) + '" data-cc="' + cc + '"></circle>');
      }
    });
    Object.keys(cnt).forEach(function (cc) {
      var g = GEO.shapes[cc];
      if (g && g.d && cnt[cc] / max > 0.06) {
        dots.push('<circle class="dot" cx="' + g.cx + '" cy="' + g.cy + '" r="' +
          (2 + 5 * Math.pow(cnt[cc] / max, 0.5)).toFixed(1) + '" data-cc="' + cc + '"></circle>');
      }
    });

    var ranked = Object.keys(cnt).sort(function (a, b) { return cnt[b] - cnt[a]; });
    var bars = ranked.slice(0, 22).map(function (cc) {
      return '<button class="bar' + (S.cc === cc ? " on" : "") + '" data-cc="' + cc + '">' +
        '<span class="barname">' + flag(cc) + " " + esc(cname(cc)) + "</span>" +
        '<span class="bartrack"><span class="barfill" style="width:' +
        (100 * cnt[cc] / max).toFixed(1) + '%"></span></span>' +
        '<span class="barval">' + num(cnt[cc]) + "</span></button>";
    }).join("");

    var listed = S.cc ? pool.filter(function (e) { return e.c === S.cc; })
      .sort(function (a, b) { return a.s < b.s ? -1 : 1; }) : [];

    main.innerHTML = filterBar(pool) +
      '<div class="split map">' +
      '<div><div class="card pad"><div class="sec-title"><h2>🌍 나라별 전시회</h2><small>' +
      num(pool.length) + "건 · 진한 색일수록 많음, 나라를 누르면 그 나라만</small></div>" +
      '<div class="mapwrap"><svg viewBox="0 0 ' + GEO.w + " " + GEO.h + '">' + paths.join("") + dots.join("") +
      "</svg></div>" +
      '<div class="legend"><span><i style="background:#dfe6ee"></i>없음</span>' +
      '<span><i style="background:rgba(18,87,166,.35)"></i>적음</span>' +
      '<span><i style="background:rgba(18,87,166,1)"></i>많음 (' + num(max) + "건)</span></div></div></div>" +
      '<div class="card pad"><div class="sec-title"><h2>나라 순위</h2><small>상위 22개국</small></div>' +
      '<div class="bars">' + bars + "</div></div></div>" +
      (S.cc ? '<div class="sec-title" style="margin-top:22px"><h2>' + flag(S.cc) + " " + esc(cname(S.cc)) +
        " 전시회</h2><small>" + num(listed.length) + "건</small></div>" + listHTML(listed, 60) : "");

    bindFilterBar(main);
    Array.prototype.forEach.call(main.querySelectorAll("[data-cc]"), function (el) {
      el.onclick = function () { S.cc = (S.cc === el.getAttribute("data-cc")) ? "" : el.getAttribute("data-cc"); S.limit = 120; render(); };
      if (el.tagName.toLowerCase() !== "button") {
        el.onmousemove = function (ev) { tip(ev, el.getAttribute("data-cc"), cnt); };
        el.onmouseleave = hideTip;
      }
    });
  }

  var tipEl = $("#maptip");
  function tip(ev, cc, cnt) {
    tipEl.hidden = false;
    tipEl.innerHTML = flag(cc) + " <b>" + esc(cname(cc)) + "</b> · " + num(cnt[cc] || 0) + "건";
    tipEl.style.left = Math.min(ev.clientX + 14, window.innerWidth - 200) + "px";
    tipEl.style.top = (ev.clientY + 16) + "px";
  }
  function hideTip() { tipEl.hidden = true; }

  // ---------------------------------------------------------------- 탭: 산업분야
  function viewInd() {
    var pool = filtered();
    var cnt = {};
    pool.forEach(function (e) { e.ind.forEach(function (i) { cnt[i] = (cnt[i] || 0) + 1; }); });
    var max = Math.max.apply(null, [1].concat(IND_ORDER.map(function (c) { return cnt[c] || 0; })));
    var bars = IND_ORDER.filter(function (c) { return cnt[c]; })
      .sort(function (a, b) { return cnt[b] - cnt[a]; })
      .map(function (c) {
        return '<button class="bar' + (S.inds[c] ? " on" : "") + '" data-ind="' + c + '">' +
          '<span class="barname">' + IND[c].emoji + " " + esc(IND[c].name) + "</span>" +
          '<span class="bartrack"><span class="barfill" style="width:' + (100 * cnt[c] / max).toFixed(1) +
          '%"></span></span><span class="barval">' + num(cnt[c]) + "</span></button>";
      }).join("");

    var sel = keysOn(S.inds);
    var sub = pool.filter(function (e) { return !sel.length || e.ind.some(function (i) { return S.inds[i]; }); });
    var byC = {};
    sub.forEach(function (e) { byC[e.c] = (byC[e.c] || 0) + 1; });
    var cmax = Math.max.apply(null, [1].concat(Object.keys(byC).map(function (k) { return byC[k]; })));
    var cbars = Object.keys(byC).sort(function (a, b) { return byC[b] - byC[a]; }).slice(0, 16)
      .map(function (cc) {
        return '<button class="bar" data-cc="' + cc + '"><span class="barname">' + flag(cc) + " " +
          esc(cname(cc)) + '</span><span class="bartrack"><span class="barfill" style="width:' +
          (100 * byC[cc] / cmax).toFixed(1) + '%"></span></span><span class="barval">' + num(byC[cc]) + "</span></button>";
      }).join("");

    main.innerHTML = filterBar(pool) +
      '<div class="split wide"><div class="card pad">' +
      '<div class="sec-title"><h2>🏭 산업분야별 전시회</h2><small>분야를 누르면 그 분야만 (여러 개 선택 가능)</small></div>' +
      '<div class="bars">' + bars + "</div></div>" +
      '<div class="card pad"><div class="sec-title"><h2>' +
      (sel.length ? sel.map(function (c) { return IND[c].emoji; }).join("") + " 개최국" : "개최국") +
      "</h2><small>상위 16개국</small></div>" + '<div class="bars">' + cbars + "</div></div></div>" +
      '<div class="sec-title" style="margin-top:22px"><h2>목록</h2><small>' + num(sub.length) + "건</small></div>" +
      listHTML(sub.slice().sort(function (a, b) { return a.s < b.s ? -1 : 1; }), S.limit);

    bindFilterBar(main);
    Array.prototype.forEach.call(main.querySelectorAll("[data-ind]"), function (b) {
      b.onclick = function () { var k = b.getAttribute("data-ind"); S.inds[k] = !S.inds[k]; S.limit = 120; render(); };
    });
    Array.prototype.forEach.call(main.querySelectorAll(".bars [data-cc]"), function (b) {
      b.onclick = function () { S.cc = b.getAttribute("data-cc"); S.tab = "map"; syncTabs(); render(); };
    });
  }

  // ---------------------------------------------------------------- 탭: 국내
  function viewKR() {
    var pool = filtered().filter(isKR);
    var byR = {}, byV = {};
    pool.forEach(function (e) {
      var r = D.regions[e.reg] || "기타";
      byR[r] = (byR[r] || 0) + 1;
      var v = (e.v || "기타").replace(/\s*(제?\d+전시장|Hall.*|전시홀.*|[A-D]홀.*)$/i, "").trim() || "기타";
      byV[v] = (byV[v] || 0) + 1;
    });
    function barsOf(obj, n) {
      var ks = Object.keys(obj).sort(function (a, b) { return obj[b] - obj[a]; }).slice(0, n);
      var mx = Math.max.apply(null, [1].concat(ks.map(function (k) { return obj[k]; })));
      return ks.map(function (k) {
        return '<div class="bar"><span class="barname">' + esc(k) + '</span><span class="bartrack">' +
          '<span class="barfill" style="width:' + (100 * obj[k] / mx).toFixed(1) + '%"></span></span>' +
          '<span class="barval">' + num(obj[k]) + "</span></div>";
      }).join("");
    }
    main.innerHTML = filterBar(pool) +
      '<div class="split wide"><div class="card pad"><div class="sec-title"><h2>🇰🇷 국내 전시회</h2><small>' +
      num(pool.length) + "건 · 지역별</small></div>" + '<div class="bars">' + barsOf(byR, 17) + "</div></div>" +
      '<div class="card pad"><div class="sec-title"><h2>전시장</h2><small>상위 12곳</small></div>' +
      '<div class="bars">' + barsOf(byV, 12) + "</div></div></div>" +
      '<div class="sec-title" style="margin-top:22px"><h2>목록</h2><small>' + num(pool.length) + "건</small></div>" +
      listHTML(pool.slice().sort(function (a, b) { return a.s < b.s ? -1 : 1; }), S.limit);
    bindFilterBar(main);
  }

  // ---------------------------------------------------------------- 탭: 달력
  function viewCal() {
    var pool = filtered({ ignoreSpan: true });
    var y = +S.cal.slice(0, 4), m = +S.cal.slice(5, 7);
    var first = new Date(y, m - 1, 1), start = new Date(first);
    start.setDate(1 - first.getDay());
    // 시작일에만 찍는다 — 여러 주에 걸친 전시회를 매일 찍으면 달력이 같은 이름으로 도배된다
    var byDay = {}, vague = [];
    pool.forEach(function (e) {
      if (e.s.slice(0, 7) !== S.cal) return;
      if (e.p === "month") vague.push(e);        // 날짜가 '9월 중'으로만 알려진 건 — 1일에 몰리면 달력이 망가진다
      else (byDay[e.s] = byDay[e.s] || []).push(e);
    });
    var cells = ["일", "월", "화", "수", "목", "금", "토"].map(function (d) {
      return '<div class="calhead">' + d + "</div>";
    });
    for (var i = 0; i < 42; i++) {
      var d = new Date(start); d.setDate(start.getDate() + i);
      var key = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
      var out = key.slice(0, 7) !== S.cal;
      var evs = (byDay[key] || []).slice().sort(function (a, b) { return (b.rel || 0) - (a.rel || 0); });
      cells.push('<div class="calcell' + (out ? " out" : "") + (key === TODAY ? " today" : "") + '">' +
        '<div class="calday' + (d.getDay() === 0 ? " sun" : "") + '">' + d.getDate() + "</div>" +
        evs.slice(0, 4).map(function (e) {
          return '<button class="calev ' + (isKR(e) ? "kr" : "ov") + '" data-id="' + esc(e.id) + '" title="' +
            esc(e.t) + '">' + (isKR(e) ? "" : flag(e.c) + " ") + esc(e.t) + "</button>";
        }).join("") +
        (evs.length > 4 ? '<div class="note" style="font-size:10.5px;margin-top:2px">+' + (evs.length - 4) + "건</div>" : "") +
        "</div>");
      if (i >= 34 && key.slice(0, 7) !== S.cal && new Date(d).getDate() > 7) break;
    }
    main.innerHTML = filterBar(pool, { noSpan: true }) +
      '<div class="card pad"><div class="sec-title"><h2>📅 ' + y + "년 " + m + "월</h2>" +
      '<div class="calnav"><button data-mv="-1">‹ 이전</button><button data-mv="0">이번 달</button>' +
      '<button data-mv="1">다음 ›</button></div>' +
      "<small>이 달에 개막하는 전시회 " + num(Object.keys(byDay).reduce(function (a, k) {
        return a + byDay[k].length;
      }, 0)) + "건 · 개막일에만 표시</small></div>" +
      '<div class="calgrid">' + cells.join("") + "</div>" +
      (vague.length ? '<div class="note" style="margin-top:12px">📌 날짜가 \'' + (+S.cal.slice(5, 7)) +
        "월 중'으로만 공개된 전시회 " + num(vague.length) + "건은 달력에 넣지 않았습니다 — 아래 목록에서 확인하세요.</div>" +
        '<div class="rows" style="margin-top:10px">' + vague.slice(0, 20).map(rowHTML).join("") + "</div>" : "") +
      "</div>";
    bindFilterBar(main);
    Array.prototype.forEach.call(main.querySelectorAll("[data-mv]"), function (b) {
      b.onclick = function () {
        var mv = +b.getAttribute("data-mv");
        if (!mv) { S.cal = TODAY.slice(0, 7); } else {
          var d = new Date(+S.cal.slice(0, 4), +S.cal.slice(5, 7) - 1 + mv, 1);
          S.cal = d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2);
        }
        render();
      };
    });
  }

  // ---------------------------------------------------------------- 탭: 새로 등록
  function viewNew() {
    var pool = filtered({ ignoreSpan: true }).filter(reallyNew);
    var lim = S.newDays;
    var list = pool.filter(function (e) { return days(e.fs, TODAY) <= lim; })
      .sort(function (a, b) { return a.fs < b.fs ? 1 : a.fs > b.fs ? -1 : (b.rel || 0) - (a.rel || 0); });
    var byDay = {};
    list.forEach(function (e) { (byDay[e.fs] = byDay[e.fs] || []).push(e); });
    var html = Object.keys(byDay).sort().reverse().map(function (d) {
      var n = days(d, TODAY);
      return '<div class="monthhead">' + ymd(d) + (n === 0 ? " (오늘)" : n === 1 ? " (어제)" : " (" + n + "일 전)") +
        '<i></i><span>' + byDay[d].length + "건</span></div>" +
        '<div class="rows">' + byDay[d].map(rowHTML).join("") + "</div>";
    }).join("");
    main.innerHTML = filterBar(pool) +
      '<div class="frow" style="margin-bottom:12px"><span class="flabel">기간</span>' +
      seg([["1", "오늘"], ["3", "3일"], ["7", "7일"], ["14", "2주"]], String(S.newDays), "nd") + "</div>" +
      '<div class="sec-title"><h2>🆕 새로 올라온 전시회</h2><small>' + num(list.length) +
      "건 · 수집 첫날 대량 등록분은 뺐습니다</small></div>" +
      (html || '<div class="card empty">이 기간에 새로 올라온 전시회가 없습니다.</div>');
    bindFilterBar(main);
    bindSeg(main, "nd", function (v) { S.newDays = +v; });
  }


  // ---------------------------------------------------------------- 탭: 경쟁사
  var RFAIRS = RIVDATA.fairs || [], REXH = RIVDATA.exhibitors || {},
      RCOMP = RIVDATA.companies || [], RDISC = RIVDATA.discovered || [];
  var RFAIR = {};
  RFAIRS.forEach(function (f) { RFAIR[f.key] = f; });
  var WATCH = 10;              // 경쟁사가 이만큼 나오면 '우리가 챙겨야 할 전시회'

  function rivRecsOf(fkey) {
    return (REXH[fkey] || []).filter(function (r) { return r[2]; });
  }

  function fairRow(f) {
    var ev = EV.filter(function (e) { return e.fk === f.key; })[0];
    var dens = f.exhibitors ? (100 * (f.rivals || 0) / f.exhibitors) : 0;
    var watch = (f.rivals || 0) >= WATCH;
    return '<button class="frow-card' + (watch ? " watch" : "") + '" data-fair="' + esc(f.key) + '">' +
      '<span class="fc-n">' + num(f.rivals || 0) + '<em>경쟁사</em></span>' +
      '<span class="fc-body"><span class="fc-t">' + esc(f.title) +
      (watch ? ' <span class="tag riv">관심</span>' : "") +
      (f.kind === "history" ? ' <span class="tag">직전 회차 명단</span>' : "") + "</span>" +
      '<span class="fc-m">' + flag(f.country) + " " + esc(f.city) + " · " + esc(f.when) +
      " · 출품사 " + num(f.exhibitors) + "개 · 커넥터 계열 " + num(f.conn || 0) + "개" +
      (ev ? " · 다음 개최 " + period(ev) : "") + "</span>" +
      (f.note ? '<span class="fc-m">' + esc(f.note) + "</span>" : "") + "</span>" +
      '<span class="fc-d">' + dens.toFixed(1) + "%<em>밀도</em></span></button>";
  }

  function viewRiv() {
    var counts = {};                       // 경쟁사 → 이름이 나온 전시회 목록
    Object.keys(REXH).forEach(function (fk) {
      REXH[fk].forEach(function (r) {
        if (r[2]) (counts[r[2]] = counts[r[2]] || {})[fk] = 1;
      });
    });
    var nFair = function (k) { return Object.keys(counts[k] || {}).length; };

    var ranked = RFAIRS.filter(function (f) { return !f.error; })
      .sort(function (a, b) { return (b.rivals || 0) - (a.rivals || 0); });
    var okFairs = ranked.filter(function (f) { return f.exhibitors; });

    var chips = RIVDATA.list.filter(function (r) { return nFair(r.key); })
      .sort(function (a, b) { return nFair(b.key) - nFair(a.key); })
      .map(function (r) {
        return '<button class="chip' + (S.riv === r.key ? " on" : "") + (r.user ? " core" : "") +
          '" data-riv="' + r.key + '">' + esc(r.name) + " <b>" + nFair(r.key) + "</b></button>";
      }).join("");
    var none = RIVDATA.list.filter(function (r) { return !nFair(r.key); })
      .map(function (r) { return esc(r.name); }).join(", ");

    var confirmed = EV.filter(function (e) { return e.riv && e.riv.length; })
      .filter(function (e) { return !S.riv || e.riv.some(function (x) { return x.r === S.riv; }); })
      .sort(function (a, b) { return a.s < b.s ? -1 : 1; });

    var disc = RDISC.filter(function (c) { return !S.riv; }).slice(0, 60);
    // 커넥터·케이블이 주제인 전시회 — 명단이 없어도 목록에서 사라지지 않게 따로 뽑는다
    var connFairs = EV.filter(function (e) { return e.cf && (e.e || e.s) >= TODAY; })
      .filter(function (e) { return !S.riv || (e.riv || []).some(function (x) { return x.r === S.riv; }); })
      .sort(function (a, b) { return a.s < b.s ? -1 : 1; });

    main.innerHTML =
      '<div class="card pad" style="margin-bottom:14px">' +
      '<div class="sec-title"><h2>🏁 경쟁사 출품 레이더</h2><small>' +
      "전시회 공식 출품사 명단 " + num(okFairs.length) + "개 · 출품사 " +
      num(okFairs.reduce(function (a, f) { return a + f.exhibitors; }, 0)) + "개사를 훑어 " +
      "우리 경쟁사 " + num(Object.keys(counts).length) + "곳을 찾았습니다 · " + esc(RIVDATA.generated || "") + "</small></div>" +
      '<div class="frow"><span class="flabel">경쟁사</span>' + chips +
      (S.riv ? ' <button class="chip on" data-riv="">전체 ✕</button>' : "") + "</div>" +
      (none ? '<div class="note" style="margin-top:8px">아직 명단에서 못 본 곳: ' + none + "</div>" : "") +
      "</div>" +

      '<div class="sec-title"><h2>🗓 경쟁사가 나오는 전시회 일정</h2><small>' +
      num(confirmed.length) + "건 · 직전 회차 명단으로 다음 회차를 잡은 건은 '예상'</small></div>" +
      (confirmed.length ? '<div class="rows">' + confirmed.map(function (e) {
        return rowHTML(e) + '<div class="rivline">' + e.riv.map(function (x) {
          return '<span class="rivbadge' + (RIV[x.r] && RIV[x.r].user ? " core" : "") + '">' +
            esc(rivName(x.r)) + (x.b ? " <b>" + esc(x.b) + "</b>" : "") + "</span>";
        }).join("") + (e.fk ? ' <button class="rivsearch" data-fair="' + esc(e.fk) +
          '">출품사 전체 명단 보기 →</button>' : "") + "</div>";
      }).join("") + "</div>" : '<div class="card empty">확인된 전시회가 없습니다.</div>') +

      '<div class="sec-title"><h2>📊 전시회별 경쟁사 밀집도</h2><small>' +
      "경쟁사 " + WATCH + "곳 이상이면 <b>관심</b> — 전시회를 누르면 출품사 전체 명단이 열립니다</small></div>" +
      '<div class="frows">' + ranked.map(fairRow).join("") + "</div>" +

      '<div class="sec-title" style="margin-top:26px"><h2>🔌 커넥터·케이블 전용 전시회</h2><small>' +
      "우리 업이 주제인 전시회 — 출품사 명단을 공개하지 않는 곳도 빠뜨리지 않으려고 따로 모았습니다</small></div>" +
      (connFairs.length ? '<div class="rows">' + connFairs.slice(0, 30).map(function (e) {
        var has = e.fk && REXH[e.fk];
        return rowHTML(e) + '<div class="rivline">' +
          (has ? '<button class="rivsearch" data-fair="' + esc(e.fk) + '">출품사 명단 ' +
            num(REXH[e.fk].length) + "개사 보기 →</button>" :
            '<span class="tag">출품사 명단 미공개</span>' +
            '<a class="rivsearch" target="_blank" rel="noopener" href="https://www.google.com/search?q=' +
            encodeURIComponent((e.te || e.t) + " " + e.s.slice(0, 4) + " exhibitor list 展商名单") +
            '">명단 검색 ↗</a>') +
          (e.riv ? e.riv.map(function (x) {
            return '<span class="rivbadge' + (RIV[x.r] && RIV[x.r].user ? " core" : "") + '">' +
              esc(rivName(x.r)) + (x.k === "visitor" ? " (참관)" : "") + "</span>";
          }).join("") : "") + "</div>";
      }).join("") + "</div>" : '<div class="card empty">해당 전시회가 없습니다.</div>') +

      (disc.length ? '<div class="sec-title" style="margin-top:26px"><h2>🔬 명단에서 새로 찾은 커넥터 업체</h2>' +
        "<small>이름·소개글이 커넥터/단자/하네스인데 우리 경쟁사 목록에 없던 곳 " + num(RDISC.length) +
        "곳 — 여러 전시회에 겹쳐 나오는 순</small></div>" +
        '<div class="discgrid">' + disc.map(function (c) {
          return '<button class="disccard" data-co="' + esc(c.k) + '"><b>' + esc(c.n) + "</b>" +
            '<span class="tag riv">전시회 ' + c.f.length + "곳</span>" +
            '<div class="note">' + c.f.map(function (k) {
              return esc((RFAIR[k] || {}).title || k);
            }).join(" · ") + "</div></button>";
        }).join("") + "</div>" : "");

    Array.prototype.forEach.call(main.querySelectorAll("[data-riv]"), function (b) {
      b.onclick = function () {
        var k = b.getAttribute("data-riv");
        S.riv = (S.riv === k) ? "" : k;
        render();
      };
    });
    Array.prototype.forEach.call(main.querySelectorAll("[data-fair]"), function (b) {
      b.onclick = function (ev) { ev.stopPropagation(); openFair(b.getAttribute("data-fair")); };
    });
    Array.prototype.forEach.call(main.querySelectorAll("[data-co]"), function (b) {
      b.onclick = function (ev) { ev.stopPropagation(); openCompany(b.getAttribute("data-co")); };
    });
  }

  // 회사 서랍 — 이 회사가 어느 전시회에 나오나 (새로 찾은 업체 추적용)
  var RCOMP_BY_KEY = {};
  RCOMP.forEach(function (c) { RCOMP_BY_KEY[c.k] = c; });

  function fairEvent(fk) {
    return EV.filter(function (e) { return (e.fks || []).indexOf(fk) >= 0 || e.fk === fk; })[0];
  }

  function openCompany(ck) {
    var c = RCOMP_BY_KEY[ck];
    if (!c) return;
    var sorted = c.f.slice().sort(function (a, b) {
      return ((RFAIR[a] || {}).when || "").localeCompare((RFAIR[b] || {}).when || "");
    });
    var curYear = "";
    var rows = sorted.map(function (fk) {
      var f = RFAIR[fk] || { title: fk, when: "", city: "", country: "" };
      var head = "";
      if ((f.when || "").slice(0, 4) !== curYear) {
        curYear = (f.when || "").slice(0, 4);
        head = '<div class="monthhead" style="margin:10px 0 4px">' + esc(curYear) + "년<i></i></div>";
      }
      var ev = fairEvent(fk);
      return head + '<div class="exrow' + (f.kind === "past" ? "" : " conn") + '">' +
        "<span><b>" + esc(f.title) + "</b><br><span class='note'>" + flag(f.country) + " " +
        esc(f.city) + " · " + esc(f.when) + (f.kind === "past" ? " (지난 회차)" : "") +
        (ev ? " · 다음 개최 " + period(ev) : "") + "</span></span>" +
        (c.b && c.b[fk] ? '<span class="tag">' + esc(c.b[fk]) + "</span>" : "") +
        (ev ? '<button class="rivsearch" data-ev="' + esc(ev.id) + '">전시회 보기 →</button>' : "") +
        "</div>";
    }).join("");
    drawer.innerHTML = '<div class="dhead"><button class="dclose" id="dclose">✕</button>' +
      "<h3>" + esc(c.n) + "</h3><p>" +
      (c.r ? "우리 경쟁사 목록에 있는 곳 · " + esc(rivName(c.r)) : "명단에서 새로 찾은 커넥터 계열 업체") +
      " · 출품 전시회 " + c.f.length + "곳</p></div>" +
      '<div class="dbody">' +
      '<div class="dlinks"><a class="dlink" target="_blank" rel="noopener" href="https://www.google.com/search?q=' +
      encodeURIComponent(c.n + " connector manufacturer") + '">회사 검색 ↗</a>' +
      '<a class="dlink alt" target="_blank" rel="noopener" href="https://www.linkedin.com/search/results/companies/?keywords=' +
      encodeURIComponent(c.n) + '">LinkedIn ↗</a></div>' +
      '<div class="sec-title"><h2>나오는 전시회</h2><small>명단에서 확인된 것만</small></div>' +
      '<div class="exlist">' + rows + "</div></div>";
    $("#dclose").onclick = closeDetail;
    Array.prototype.forEach.call(drawer.querySelectorAll("[data-ev]"), function (b) {
      b.onclick = function () { openDetail(b.getAttribute("data-ev")); };
    });
    drawer.classList.add("on");
    scrim.classList.add("on");
  }

  // 전시회 출품사 전체 명단 서랍 — 잠재 고객 리스트 + 경쟁사 랭킹
  var fairState = { key: "", q: "", limit: 200, only: "" };
  function openFair(key) {
    var f = RFAIR[key];
    if (!f) return;
    fairState.key = key;
    fairState.q = fairState.q || "";
    drawFair();
    drawer.classList.add("on");
    scrim.classList.add("on");
  }
  function drawFair() {
    var f = RFAIR[fairState.key], rows = REXH[fairState.key] || [];
    var q = fairState.q.trim().toLowerCase();
    var list = rows.filter(function (r) {
      if (fairState.only === "riv" && !r[2]) return false;
      if (fairState.only === "conn" && !(r[3] >= 2 || r[2])) return false;
      return !q || r[0].toLowerCase().indexOf(q) >= 0;
    });
    list.sort(function (a, b) {
      return (b[2] ? 2 : 0) + (b[3] >= 2 ? 1 : 0) - ((a[2] ? 2 : 0) + (a[3] >= 2 ? 1 : 0)) ||
        a[0].toLowerCase().localeCompare(b[0].toLowerCase());
    });
    var rivs = rows.filter(function (r) { return r[2]; })
      .sort(function (a, b) { return a[0].localeCompare(b[0]); });
    var ev = EV.filter(function (e) { return e.fk === fairState.key; })[0];

    drawer.innerHTML = '<div class="dhead"><button class="dclose" id="dclose">✕</button>' +
      "<h3>" + esc(f.title) + "</h3><p>" + flag(f.country) + " " + esc(f.city) + " · " + esc(f.when) +
      " · 출품사 " + num(f.exhibitors) + "개" + (ev ? " · 다음 개최 " + period(ev) : "") + "</p></div>" +
      '<div class="dbody">' +
      '<div class="dsum"><b>🏁 우리 경쟁사 ' +
      Object.keys(rivs.reduce(function (a, r) { a[r[2]] = 1; return a; }, {})).length + "곳" +
      (rivs.length > 0 ? " (부스 " + rivs.length + "개)" : "") + "</b>" +
      '<div class="rivline" style="margin:8px 0 0">' + rivs.map(function (r) {
        return '<span class="rivbadge' + (RIV[r[2]] && RIV[r[2]].user ? " core" : "") + '">' +
          esc(rivName(r[2])) + (r[1] ? " <b>" + esc(r[1]) + "</b>" : "") + "</span>";
      }).join("") + "</div>" +
      '<div class="note" style="margin-top:8px">' + esc(f.note || "") +
      ' · <a class="lnk" href="' + esc(f.url) + '" target="_blank" rel="noopener">공식 명단 ↗</a></div></div>' +
      '<div class="frow" style="margin:4px 0 2px">' +
      seg([["", "전체 " + rows.length], ["conn", "커넥터 계열 " + (f.conn || 0)], ["riv", "경쟁사 " + rivs.length]],
        fairState.only, "only") + "</div>" +
      '<div class="gsbox" style="box-shadow:none;border:1px solid var(--line)"><span class="gsicon">🔍</span>' +
      '<input id="fq" type="search" placeholder="출품사 이름으로 찾기" value="' + esc(fairState.q) + '"></div>' +
      '<div class="note">' + num(list.length) + "개사" +
      (list.length > fairState.limit ? " (" + fairState.limit + "개까지 표시)" : "") + "</div>" +
      '<div class="exlist">' + list.slice(0, fairState.limit).map(function (r) {
        var ck = r[4] || "";
        var many = RCOMP_BY_KEY[ck] && RCOMP_BY_KEY[ck].f.length > 1;
        return '<div class="exrow' + (r[2] ? " riv" : r[3] >= 2 ? " conn" : "") + '">' +
          '<span>' + esc(r[0]) + "</span>" +
          (many ? '<button class="rivsearch" data-co="' + esc(ck) + '">다른 전시회 ' +
            (RCOMP_BY_KEY[ck].f.length - 1) + "곳 →</button>" : "") +
          (r[2] ? '<span class="tag riv">경쟁사</span>' : r[3] >= 2 ? '<span class="tag">커넥터 계열</span>' : "") +
          (r[1] ? '<span class="tag">' + esc(r[1]) + "</span>" : "") +
          '<a class="rivsearch" target="_blank" rel="noopener" href="https://www.google.com/search?q=' +
          encodeURIComponent(r[0]) + '">검색 ↗</a></div>';
      }).join("") + "</div>" +
      (list.length > fairState.limit ? '<button class="more" id="fmore">더 보기</button>' : "") +
      "</div>";
    $("#dclose").onclick = closeDetail;
    var fq = $("#fq"), t = null;
    fq.oninput = function () {
      clearTimeout(t);
      t = setTimeout(function () { fairState.q = fq.value; fairState.limit = 200; drawFair(); fq = $("#fq"); fq.focus(); }, 200);
    };
    Array.prototype.forEach.call(drawer.querySelectorAll("[data-only]"), function (b) {
      b.onclick = function () { fairState.only = b.getAttribute("data-only"); fairState.limit = 200; drawFair(); };
    });
    Array.prototype.forEach.call(drawer.querySelectorAll("[data-co]"), function (b) {
      b.onclick = function () { openCompany(b.getAttribute("data-co")); };
    });
    var fm = $("#fmore");
    if (fm) fm.onclick = function () { fairState.limit += 400; drawFair(); };
  }

  // ---------------------------------------------------------------- 탭: 출처
  function viewSrc() {
    var cnt = {};
    EV.forEach(function (e) { e.src.forEach(function (s) { cnt[s] = (cnt[s] || 0) + 1; }); });
    var cards = D.sources.map(function (s) {
      return '<div class="srccard' + (s.error ? " bad" : "") + '"><div class="n">' + num(cnt[s.key] || s.count) +
        "</div><b>" + esc(s.name) + "</b><div class=\"note\">키 " + esc(s.key) + " · 원본 " + num(s.count) +
        "건 · " + (s.sec || 0) + "초" + (s.error ? "<br><b style=\"color:#cf3b3b\">" + esc(s.error) + "</b>" : "") +
        "</div></div>";
    }).join("");
    main.innerHTML = '<div class="sec-title"><h2>🧭 어디서 모았나</h2><small>' + esc(D.built) +
      " 기준 · 모두 로그인·API키 없는 공개 목록</small></div>" +
      '<div class="srcgrid">' + cards + "</div>" +
      '<div class="card pad" style="margin-top:16px"><b>중복 처리</b><div class="note" style="margin-top:6px">' +
      "같은 전시회가 여러 출처에 있으면 (정규화한 이름 + 나라 + 개최 월)로 합칩니다. " +
      "KOTRA GEP는 한글 이름만, EventsEye는 영문 이름만 있어 이름이 안 맞는 경우가 있어, " +
      "<b>같은 나라·같은 시작일·같은 종료일</b>이고 산업분야가 겹치는 한 쌍만 추가로 합칩니다(기록: data/merge_log.json).</div></div>" +
      '<div class="card pad" style="margin-top:12px"><b>업무 관련도 ★</b><div class="note" style="margin-top:6px">' +
      "커넥터·와이어하네스(5점) &gt; 전자부품·전장·카메라모듈(4점) &gt; 전자·배터리·EV·센서(3점) &gt; " +
      "자동차·기계·로봇(2점) &gt; 제조·소재(1점) 키워드에 산업분야·국고지원·전시규모 가산점을 더해 10점 만점으로 매기고 별 5개로 보여 줍니다. " +
      "기준을 바꾸려면 <code>taxonomy.py</code>의 RELEVANCE를 고치고 <code>python3 build.py --no-fetch</code>.</div></div>";
  }

  // ---------------------------------------------------------------- 상세 서랍
  var drawer = $("#drawer"), scrim = $("#scrim");
  function openDetail(id) {
    var e = EV.filter(function (x) { return x.id === id; })[0];
    if (!e) return;
    var facts = [];
    function f(k, v) { if (v) facts.push("<dt>" + k + "</dt><dd>" + v + "</dd>"); }
    var span = e.e ? days(e.s, e.e) : 0;
    f("기간", period(e) + (e.s >= TODAY ? " · D-" + dday(e) : live(e) ? " · 진행 중" : "") +
      (span > 14 ? ' <span class="note">(등록된 기간이 ' + span + "일 — 주최자 공지로 확인하세요)</span>" : ""));
    f("개최지", flag(e.c) + " " + esc(cname(e.c)) + (e.ci ? " " + esc(e.ci) : "") +
      (e.reg && D.regions[e.reg] ? " (" + D.regions[e.reg] + ")" : ""));
    f("전시장", esc(e.v));
    f("산업분야", e.ind.map(function (i) {
      return '<span class="tag">' + IND[i].emoji + " " + esc(IND[i].name) + "</span>";
    }).join(" "));
    f("주기", esc(e.cyc));
    f("규모", [e.ex ? "참가업체 " + num(e.ex) + "사" : "", e.vi ? "참관객 " + num(e.vi) + "명" : "",
      e.ar ? "전시면적 " + num(e.ar) + "㎡" : ""].filter(Boolean).join(" · "));
    f("주최", esc(e.org));
    f("품목", esc(e.items));
    f("분류", (e.sec || []).map(function (s) { return esc(s); }).join(" · "));
    f("관련도", stars(e.rel) + ' <span class="note">' + (e.rel || 0) + "/10</span>");
    if (e.riv && e.riv.length) {
      f("경쟁사 출품", e.riv.map(function (x) {
        return '<span class="rivbadge' + (RIV[x.r] && RIV[x.r].core ? " core" : "") + '">' + esc(rivName(x.r)) +
          (x.b ? " <b>" + esc(x.b) + "</b>" : "") + "</span>";
      }).join(" ") + '<div class="note" style="margin-top:4px">' +
        (e.riv[0].via === "directory" ? "전시회 공식 출품사 명단에서 확인" : "경쟁사 공식 행사 페이지에서 확인") +
        (e.riv[0].u ? ' · <a class="lnk" href="' + esc(e.riv[0].u) + '" target="_blank" rel="noopener">출처 ↗</a>' : "") +
        "</div>");
    }
    f("출처", e.src.join(", ") + (reallyNew(e) ? ' · <span class="tag new">' + ymd(e.fs) + " 등록</span>" : ""));

    var ap = e.ap ? '<div class="dsum" style="border-color:#f3c9c2;background:#fff7f5">' +
      "<b>💰 정부지원·한국관 모집</b><br>" + esc(e.ap.notice || "") +
      (e.ap.end ? "<br>신청 마감 <b>" + ymd(e.ap.end) + "</b>" +
        (e.ap.end >= TODAY ? " (D-" + days(TODAY, e.ap.end) + ")" : " (마감)") : "") +
      (e.ap.cls ? " · " + esc(e.ap.cls) : "") +
      (e.ap.url ? '<br><a class="dlink" style="margin-top:8px;display:inline-block" href="' + esc(e.ap.url) +
        '" target="_blank" rel="noopener">모집공고 보기 ↗</a>' : "") + "</div>" : "";

    drawer.innerHTML = '<div class="dhead"><button class="dclose" id="dclose">✕</button>' +
      "<h3>" + esc(e.t) + "</h3><p>" + (e.te ? esc(e.te) + " · " : "") + flag(e.c) + " " + esc(cname(e.c)) +
      (e.ci ? " " + esc(e.ci) : "") + "</p></div>" +
      '<div class="dbody">' +
      '<div class="dlinks">' +
      (e.url ? '<a class="dlink" href="' + esc(e.url) + '" target="_blank" rel="noopener">원문 정보 ↗</a>' : "") +
      (e.hp ? '<a class="dlink alt" href="' + esc(e.hp) + '" target="_blank" rel="noopener">공식 홈페이지 ↗</a>' : "") +
      '<a class="dlink alt" href="https://www.google.com/search?q=' +
      encodeURIComponent((e.te || e.t) + " " + (e.ci || "") + " " + e.s.slice(0, 4)) +
      '" target="_blank" rel="noopener">구글 검색 ↗</a></div>' +
      ap +
      (e.sum ? '<div class="dsum">' + esc(e.sum) + "</div>" : "") +
      '<dl class="dfacts">' + facts.join("") + "</dl>" +
      "</div>";
    drawer.classList.add("on"); scrim.classList.add("on");
    $("#dclose").onclick = closeDetail;
  }
  function closeDetail() { drawer.classList.remove("on"); scrim.classList.remove("on"); }
  scrim.onclick = closeDetail;
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") closeDetail(); });

  // ---------------------------------------------------------------- 헤더·렌더
  function header() {
    var up = EV.filter(function (e) { return (e.e || e.s) >= TODAY; });
    var d30 = up.filter(function (e) { return dday(e) <= 30; });
    var kr = up.filter(isKR);
    var sup = up.filter(function (e) { return e.sup || e.ap; });
    var hot = up.filter(function (e) { return (e.rel || 0) >= 5; });
    $("#subline").textContent = D.built + " 기준 · 전시회 " + num(EV.length) + "건 · 나라 " +
      num(Object.keys(CN).length) + "곳 · 출처 " + D.sources.length + "곳";
    $("#kpis").innerHTML =
      '<button class="kpi" data-k="all"><b>' + num(up.length) + "</b><span>앞으로 열리는</span></button>" +
      '<button class="kpi" data-k="30"><b>' + num(d30.length) + "</b><span>30일 안</span></button>" +
      '<button class="kpi" data-k="kr"><b>' + num(kr.length) + "</b><span>🇰🇷 국내</span></button>" +
      '<button class="kpi hot" data-k="sup"><b>' + num(sup.length) + "</b><span>💰 지원·한국관</span></button>" +
      '<button class="kpi hot" data-k="rel"><b>' + num(hot.length) + "</b><span>🎯 우리 관련</span></button>";
    Array.prototype.forEach.call(document.querySelectorAll(".kpi"), function (b) {
      b.onclick = function () {
        var k = b.getAttribute("data-k");
        S.inds = {}; S.conts = {}; S.cc = ""; S.sup = false; S.rel = 0; S.limit = 120;
        if (k === "all") { S.span = "all"; S.scope = "all"; }
        if (k === "30") { S.span = "30"; S.scope = "all"; }
        if (k === "kr") { S.span = "all"; S.scope = "kr"; }
        if (k === "sup") { S.span = "all"; S.sup = true; S.tab = "pick"; }
        if (k === "rel") { S.span = "all"; S.rel = 5; }
        if (k !== "sup") S.tab = "soon";
        syncTabs(); render();
      };
    });
  }

  function quickChips() {
    var chips = [
      { k: "커넥터", q: "커넥터" }, { k: "전자부품", q: "전자부품" }, { k: "electronica", q: "electronica" },
      { k: "자동차부품", q: "자동차부품" }, { k: "배터리·EV", q: "배터리" }, { k: "반도체", q: "반도체" },
      { k: "베트남", q: "베트남" }, { k: "인도", q: "인도" }, { k: "독일", q: "독일" }, { k: "미국", q: "미국" },
    ];
    $("#gchips").innerHTML = chips.map(function (c) {
      return '<button class="gchip' + (S.q === c.q ? " on" : "") + '" data-q="' + esc(c.q) + '">' + esc(c.k) + "</button>";
    }).join("");
    Array.prototype.forEach.call(document.querySelectorAll("#gchips .gchip"), function (b) {
      b.onclick = function () {
        var q = b.getAttribute("data-q");
        S.q = (S.q === q) ? "" : q;
        $("#gq").value = S.q; S.limit = 120; S.span = "all";
        render();
      };
    });
  }

  function syncTabs() {
    Array.prototype.forEach.call(document.querySelectorAll("#tabs button"), function (b) {
      b.classList.toggle("on", b.getAttribute("data-tab") === S.tab);
    });
  }

  var VIEWS = { soon: viewSoon, pick: viewPick, riv: viewRiv, map: viewMap, ind: viewInd,
                kr: viewKR, cal: viewCal, new: viewNew, src: viewSrc };

  function render() {
    quickChips();
    (VIEWS[S.tab] || viewSoon)();
    var more = $("#more");
    if (more) more.onclick = function () { S.limit += 200; render(); };
    Array.prototype.forEach.call(main.querySelectorAll("[data-id]"), function (b) {
      b.onclick = function () { openDetail(b.getAttribute("data-id")); };
    });
    window.scrollTo({ top: window.scrollY > 400 ? window.scrollY : 0 });
  }

  Array.prototype.forEach.call(document.querySelectorAll("#tabs button"), function (b) {
    b.onclick = function () { S.tab = b.getAttribute("data-tab"); S.limit = 120; syncTabs(); render(); };
  });
  var gq = $("#gq"), timer = null;
  gq.oninput = function () {
    $("#gclear").hidden = !gq.value;
    clearTimeout(timer);
    timer = setTimeout(function () { S.q = gq.value; S.limit = 120; render(); }, 180);
  };
  $("#gclear").onclick = function () { gq.value = ""; S.q = ""; $("#gclear").hidden = true; render(); };

  header();
  render();
})();
