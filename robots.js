/* 로봇 전시회 출품사 레이더 — app-robots.js(window.ROBOTS)를 화면에 그린다.
   탭: 출품 업체(필터·정렬·CSV) / 명단 확보 전시회 / 전세계 로봇 전시회(DB) / 만든 방법·한계 */
(function () {
  "use strict";
  var D = window.ROBOTS || { fairs: [], expos: [], companies: [], cats: [], inds: [], fields: [], countries: {} };
  var CAT = {}, IND = {}, FLD = {}, FAIR = {};
  D.cats.forEach(function (x) { CAT[x[0]] = x[1]; });
  D.inds.forEach(function (x) { IND[x[0]] = x[1]; });
  D.fields.forEach(function (x) { FLD[x[0]] = x[1]; });
  D.fairs.forEach(function (f) { FAIR[f.key] = f; });

  var S = { tab: "co", q: "", fair: "", fld: "", cat: "", ind: "", cc: "", sort: "fairs", descOnly: false, multi: false, limit: 150,
            bf: "", bfq: "", bfFld: "", bfSort: "booth", bfLimit: 200 };
  var main = document.getElementById("main");
  var drawer = document.getElementById("drawer");
  var scrim = document.getElementById("scrim");

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function num(n) { return (n || 0).toLocaleString("ko-KR"); }
  function ccName(c) { return D.countries[c] || c; }
  function fairShort(k) { var f = FAIR[k]; return f ? f.title.replace(" 国際ロボット展", "") : k; }
  function fairKeys(c) { var s = {}; c.f.forEach(function (x) { s[x.k] = 1; }); return Object.keys(s); }

  // ---------------------------------------------------------------- 헤더
  function header() {
    var multi = D.companies.filter(function (c) { return fairKeys(c).length > 1; }).length;
    var withDesc = D.companies.filter(function (c) { return c.desc; }).length;
    var core = D.expos.filter(function (e) { return e.core; }).length;
    document.getElementById("subline").textContent =
      D.generated + " 기준 · 로봇 전시회 " + D.fairs.length + "회차의 출품사 명단을 회사 단위로 합쳤습니다. " +
      "한국어 소개글은 기계번역, 분류는 소개글 키워드 규칙이라 참고용입니다.";
    document.getElementById("kpis").innerHTML =
      '<div class="kpi"><b>' + num(D.companies.length) + '</b><span>출품 업체</span></div>' +
      '<div class="kpi hot"><b>' + num(multi) + '</b><span>2개 이상 전시회 출품</span></div>' +
      '<div class="kpi"><b>' + num(withDesc) + '</b><span>소개글 확보</span></div>' +
      '<div class="kpi"><b>' + D.fairs.length + '</b><span>명단 확보 회차</span></div>' +
      '<div class="kpi"><b>' + core + '</b><span>전세계 로봇 전시회</span></div>';
  }

  // ---------------------------------------------------------------- 필터
  function filtered() {
    var q = S.q.trim().toLowerCase();
    var rows = D.companies.filter(function (c) {
      if (S.fair && !c.f.some(function (x) { return x.k === S.fair; })) return false;
      if (S.fld && c.fld !== S.fld) return false;
      if (S.cat && c.cat.indexOf(S.cat) < 0) return false;
      if (S.ind && c.ind.indexOf(S.ind) < 0) return false;
      if (S.cc && c.c.indexOf(S.cc) < 0) return false;
      if (S.descOnly && !c.desc) return false;
      if (S.multi && fairKeys(c).length < 2) return false;
      if (q) {
        var hay = (c.n + " " + c.ja + " " + c.desc + " " + c.show + " " + (c.ko || "") + " " + (c.show_ko || "") + " " + (c.str_ko || []).join(" ") + " " + c.tags.join(" ") + " " +
          c.cat.map(function (k) { return CAT[k]; }).join(" ") + " " + c.ind.map(function (k) { return IND[k]; }).join(" ")).toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    });
    if (S.sort === "name") rows.sort(function (a, b) { return a.n.localeCompare(b.n); });
    else if (S.sort === "cc") rows.sort(function (a, b) { return (a.c[0] || "zz").localeCompare(b.c[0] || "zz") || a.n.localeCompare(b.n); });
    else if (S.sort === "fld") rows.sort(function (a, b) { return (a.fld || "zz").localeCompare(b.fld || "zz") || fairKeys(b).length - fairKeys(a).length; });
    else rows.sort(function (a, b) { return fairKeys(b).length - fairKeys(a).length || (b.desc ? 1 : 0) - (a.desc ? 1 : 0) || a.n.localeCompare(b.n); });
    return rows;
  }

  function opt(list, cur, all) {
    return '<option value="">' + all + "</option>" + list.map(function (x) {
      return '<option value="' + esc(x[0]) + '"' + (cur === x[0] ? " selected" : "") + ">" + esc(x[1]) + "</option>";
    }).join("");
  }

  // ---------------------------------------------------------------- 탭: 출품 업체
  function tabCompanies() {
    var rows = filtered();
    var ccs = {};
    D.companies.forEach(function (c) { c.c.forEach(function (x) { ccs[x] = (ccs[x] || 0) + 1; }); });
    var ccList = Object.keys(ccs).sort(function (a, b) { return ccs[b] - ccs[a]; }).map(function (k) { return [k, ccName(k) + " (" + ccs[k] + ")"]; });
    var fairList = D.fairs.map(function (f) { return [f.key, f.title + " · " + num(f.kept) + "사"]; });
    var catCount = {};
    D.companies.forEach(function (c) { c.cat.forEach(function (k) { catCount[k] = (catCount[k] || 0) + 1; }); });

    var html =
      '<div class="card">' +
      '<div class="rtool">' +
      '<input id="q" type="search" placeholder="회사·제품·키워드로 찾기 (예: gripper, 감속기, AMR, welding, 安川)" value="' + esc(S.q) + '">' +
      '<select id="fair">' + opt(fairList, S.fair, "모든 전시회") + "</select>" +
      '<select id="ind">' + opt(D.inds, S.ind, "모든 산업") + "</select>" +
      '<select id="cc">' + opt(ccList, S.cc, "모든 국가") + "</select>" +
      '<select id="sort">' +
      '<option value="fairs"' + (S.sort === "fairs" ? " selected" : "") + ">정렬: 출품 전시회 많은 순</option>" +
      '<option value="name"' + (S.sort === "name" ? " selected" : "") + ">정렬: 회사명</option>" +
      '<option value="cc"' + (S.sort === "cc" ? " selected" : "") + ">정렬: 국가</option>" +
      '<option value="fld"' + (S.sort === "fld" ? " selected" : "") + ">정렬: 분야</option>" +
      "</select>" +
      '<label class="ck"><input type="checkbox" id="descOnly"' + (S.descOnly ? " checked" : "") + "> 소개글 있는 곳만</label>" +
      '<label class="ck"><input type="checkbox" id="multi"' + (S.multi ? " checked" : "") + "> 2개 이상 전시회</label>" +
      '<span class="cnt"><b>' + num(rows.length) + "</b>개 업체</span>" +
      '<button class="rbtn" id="csv">⬇ CSV 내려받기</button>' +
      "</div>" +
      '<div class="rchips"><span class="lbl">분야</span>' +
      '<button class="chip' + (S.fld ? "" : " on") + '" data-fld="">전체</button>' +
      D.fields.map(function (x) {
        var n = D.companies.filter(function (c) { return c.fld === x[0]; }).length;
        return '<button class="chip' + (S.fld === x[0] ? " on" : "") + '" data-fld="' + x[0] + '">' + esc(x[1]) + " <b>" + num(n) + "</b></button>";
      }).join("") + "</div>" +
      '<div class="rchips"><span class="lbl">카테고리</span>' +
      '<button class="chip' + (S.cat ? "" : " on") + '" data-cat="">전체</button>' +
      D.cats.map(function (x) {
        return '<button class="chip' + (S.cat === x[0] ? " on" : "") + '" data-cat="' + x[0] + '">' + esc(x[1]) + " <b>" + num(catCount[x[0]] || 0) + "</b></button>";
      }).join("") + "</div>" +
      '<div class="tblwrap"><table class="rtbl"><thead><tr>' +
      "<th>회사</th><th>국가</th><th>분야</th><th>카테고리 · 산업</th><th>무엇을 만드는가</th><th>강점(소개글 발췌)</th><th>출처 전시회 · 부스</th>" +
      "</tr></thead><tbody>" +
      rows.slice(0, S.limit).map(rowHtml).join("") +
      "</tbody></table></div>" +
      (rows.length > S.limit ? '<div class="morebar"><button class="rbtn" id="more">더 보기 (' + num(rows.length - S.limit) + "개 남음)</button></div>" : "") +
      (rows.length ? "" : '<div class="empty">조건에 맞는 업체가 없습니다.</div>') +
      "</div>";
    main.innerHTML = html;

    function on(id, ev, fn) { var el = document.getElementById(id); if (el) el.addEventListener(ev, fn); }
    on("q", "input", function (e) { S.q = e.target.value; S.limit = 150; rerenderTable(); });
    on("fair", "change", function (e) { S.fair = e.target.value; S.limit = 150; render(); });
    on("ind", "change", function (e) { S.ind = e.target.value; S.limit = 150; render(); });
    on("cc", "change", function (e) { S.cc = e.target.value; S.limit = 150; render(); });
    on("sort", "change", function (e) { S.sort = e.target.value; render(); });
    on("descOnly", "change", function (e) { S.descOnly = e.target.checked; S.limit = 150; render(); });
    on("multi", "change", function (e) { S.multi = e.target.checked; S.limit = 150; render(); });
    on("more", "click", function () { S.limit += 300; render(); window.scrollTo(0, document.body.scrollHeight - 900); });
    on("csv", "click", function () { downloadCsv(filtered()); });
    Array.prototype.forEach.call(main.querySelectorAll("[data-fld]"), function (b) {
      b.addEventListener("click", function () { S.fld = b.getAttribute("data-fld"); S.limit = 150; render(); });
    });
    Array.prototype.forEach.call(main.querySelectorAll("[data-cat]"), function (b) {
      b.addEventListener("click", function () { S.cat = b.getAttribute("data-cat"); S.limit = 150; render(); });
    });
    bindRows();
  }

  // 검색어 입력 중에는 입력칸 포커스를 잃지 않게 표만 다시 그린다
  function rerenderTable() {
    var rows = filtered();
    var tb = main.querySelector(".rtbl tbody");
    if (!tb) return render();
    tb.innerHTML = rows.slice(0, S.limit).map(rowHtml).join("");
    var cnt = main.querySelector(".cnt");
    if (cnt) cnt.innerHTML = "<b>" + num(rows.length) + "</b>개 업체";
    var mb = main.querySelector(".morebar");
    if (mb) mb.style.display = rows.length > S.limit ? "" : "none";
    bindRows();
  }

  function bindRows() {
    Array.prototype.forEach.call(main.querySelectorAll("tr.co"), function (tr) {
      tr.addEventListener("click", function (e) {
        if (e.target.tagName === "A") return;
        openCompany(tr.getAttribute("data-k"));
      });
    });
  }

  function rowHtml(c) {
    var fairs = c.f.map(function (x) {
      var f = FAIR[x.k] || {};
      return '<a class="flink' + (f.kind === "history" ? " hist" : "") + '" href="' + esc(x.u || f.url) + '" target="_blank" rel="noopener" title="' + esc(f.title) + ' 출품사 페이지">' +
        esc(fairShort(x.k)) + (x.b ? "<em>" + esc(x.b) + "</em>" : "") + "</a>";
    }).join("");
    return '<tr class="co" data-k="' + esc(c.k) + '">' +
      '<td class="nm">' + esc(c.n) + (c.ja ? "<small>" + esc(c.ja) + "</small>" : "") + "</td>" +
      "<td>" + (c.c.length ? c.c.map(function (x) { return '<span class="tag cc">' + esc(ccName(x)) + "</span>"; }).join("") : '<span class="tag cc">—</span>') + "</td>" +
      "<td>" + (c.fld ? '<span class="tag ' + c.fld + '">' + esc(FLD[c.fld]) + "</span>" : '<span class="tag">미분류</span>') + "</td>" +
      '<td class="cats">' + c.cat.map(function (k) { return '<span class="tag">' + esc(CAT[k]) + "</span>"; }).join("") +
      c.ind.map(function (k) { return '<span class="tag ind">' + esc(IND[k]) + "</span>"; }).join("") + "</td>" +
      '<td class="what">' + (c.what ? (c.ko ? esc(c.ko) + "<small>" + esc(c.what) + "</small>" : esc(c.what)) : '<span style="color:var(--dim)">소개글 없음 — 전시회가 회사명만 공개</span>') + "</td>" +
      '<td class="str">' + (c.str.length ? ((c.str_ko || [])[0] ? esc(c.str_ko[0]) + "<small>" + esc(c.str[0]) + "</small>" : esc(c.str[0])) : "") + "</td>" +
      '<td class="fairs">' + fairs + "</td>" +
      "</tr>";
  }

  // ---------------------------------------------------------------- 업체 상세
  function openCompany(k) {
    var c = D.companies.filter(function (x) { return x.k === k; })[0];
    if (!c) return;
    var fairs = c.f.map(function (x) {
      var f = FAIR[x.k] || {};
      return "<li><b>" + esc(f.title || x.k) + "</b> · " + esc(f.city || "") + " · " + esc(f.when || "") +
        (x.b ? " · 부스 " + esc(x.b) : "") + ' — <a href="' + esc(x.u || f.url) + '" target="_blank" rel="noopener" style="color:var(--brand)">출처 열기 ↗</a></li>';
    }).join("");
    drawer.innerHTML =
      '<div class="dhead"><button class="dclose" id="dclose">✕</button><h3>' + esc(c.n) + "</h3><p>" +
      (c.ja ? esc(c.ja) + " · " : "") + (c.c.length ? c.c.map(ccName).join("·") : "국가 미상") + (c.city ? " · " + esc(c.city) : "") + "</p></div>" +
      '<div class="dbody">' +
      "<div>" + (c.fld ? '<span class="tag ' + c.fld + '">' + esc(FLD[c.fld]) + "</span>" : "") +
      c.cat.map(function (k) { return '<span class="tag">' + esc(CAT[k]) + "</span>"; }).join("") +
      c.ind.map(function (k) { return '<span class="tag ind">' + esc(IND[k]) + "</span>"; }).join("") + "</div>" +
      (c.web ? '<div><a class="dlink" href="' + esc(c.web) + '" target="_blank" rel="noopener">회사 홈페이지 ↗</a></div>' : "") +
      (c.ko ? "<div><h4>무엇을 만드는 회사인가 (한국어 요약 · 기계번역)</h4><p class=\"desc\">" + esc(c.ko) + "</p></div>" : "") +
      "<div><h4>전시회 소개글 원문</h4>" + (c.desc ? '<p class="desc">' + esc(c.desc) + "</p>" : "<p>소개글 없음 — 이 전시회는 회사명·부스만 공개합니다.</p>") + "</div>" +
      (c.show ? "<div><h4>무엇을 전시했는가 (전시 하이라이트)</h4><p class=\"desc\">" + (c.show_ko ? esc(c.show_ko) + "\n\n" : "") + esc(c.show) + "</p></div>" : "") +
      (c.str.length ? "<div><h4>강점 (소개글에서 발췌)</h4><ul class=\"strl\">" + c.str.map(function (s, i) { var k = (c.str_ko || [])[i]; return "<li>" + (k ? esc(k) + " <small style=\"color:var(--dim)\">" + esc(s) + "</small>" : esc(s)) + "</li>"; }).join("") + "</ul></div>" : "") +
      (c.tags.length ? "<div><h4>전시회가 붙인 분야 태그</h4><div>" + c.tags.map(function (t) { return '<span class="tag">' + esc(t) + "</span>"; }).join("") + "</div></div>" : "") +
      "<div><h4>출처 전시회</h4><ul style=\"margin:0;padding-left:18px;font-size:13px\">" + fairs + "</ul></div>" +
      "</div>";
    drawer.classList.add("on"); scrim.classList.add("on");
    document.getElementById("dclose").addEventListener("click", closeDrawer);
  }
  function closeDrawer() { drawer.classList.remove("on"); scrim.classList.remove("on"); }
  scrim.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeDrawer(); });

  // ---------------------------------------------------------------- CSV
  function downloadCsv(rows, label) {
    var head = ["회사", "회사(현지어)", "국가", "분야", "카테고리", "산업", "무엇을 만드는가(한국어)", "강점(한국어)", "전시 하이라이트(한국어)", "소개글 원문", "전시 하이라이트 원문", "강점 원문", "전시회 태그", "출처 전시회", "부스", "출처 링크", "홈페이지"];
    var lines = [head].concat(rows.map(function (c) {
      return [c.n, c.ja, c.c.map(ccName).join("·"), FLD[c.fld] || "", c.cat.map(function (k) { return CAT[k]; }).join("·"),
        c.ind.map(function (k) { return IND[k]; }).join("·"), c.ko || "", (c.str_ko || []).filter(Boolean).join(" / "), c.show_ko || "",
        c.desc, c.show, c.str.join(" / "), c.tags.join("·"),
        c.f.map(function (x) { return fairShort(x.k); }).join("·"), c.f.map(function (x) { return x.b; }).join("·"),
        c.f.map(function (x) { return x.u; }).join(" "), c.web];
    }));
    var csv = "﻿" + lines.map(function (r) {
      return r.map(function (v) { return '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"'; }).join(",");
    }).join("\r\n");
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    a.download = "로봇전시회_출품업체_" + (label ? label.replace(/[\/\\:*?"<>|]/g, "") + "_" : "") + (D.generated || "").slice(0, 10) + ".csv";
    document.body.appendChild(a); a.click(); a.remove();
  }

  // ---------------------------------------------------------------- 탭: 전시회별 업체 목록
  function boothKey(b) {
    // 'B4.320' 'W2-36' 'C-38218' 같은 부스 번호를 홀 → 숫자 순으로 정렬되게
    var m = String(b || "").match(/^([A-Za-z]*)[\s.-]*(\d+)?[\s.-]*(\d+)?/);
    return [m ? m[1].toUpperCase() : "~", m && m[2] ? +m[2] : 1e9, m && m[3] ? +m[3] : 1e9];
  }
  function fairRows(key) {
    var q = S.bfq.trim().toLowerCase();
    var rows = [];
    D.companies.forEach(function (c) {
      var ent = c.f.filter(function (x) { return x.k === key; });
      if (!ent.length) return;
      if (S.bfFld && c.fld !== S.bfFld) return;
      if (q) {
        var hay = (c.n + " " + c.ja + " " + (c.ko || "") + " " + c.desc + " " + c.cat.map(function (k) { return CAT[k]; }).join(" ")).toLowerCase();
        if (hay.indexOf(q) < 0) return;
      }
      // '調整中'(조정 중)처럼 숫자 없는 부스 표기는 미정으로 본다
      rows.push({ c: c, b: ent.map(function (x) { return x.b; }).filter(function (b) { return /\d/.test(b); }).join(", "), u: ent[0].u });
    });
    if (S.bfSort === "name") rows.sort(function (a, b) { return a.c.n.localeCompare(b.c.n); });
    else if (S.bfSort === "fld") rows.sort(function (a, b) { return (a.c.fld || "zz").localeCompare(b.c.fld || "zz") || a.c.n.localeCompare(b.c.n); });
    else if (S.bfSort === "fairs") rows.sort(function (a, b) { return fairKeys(b.c).length - fairKeys(a.c).length || a.c.n.localeCompare(b.c.n); });
    else rows.sort(function (a, b) {
      var ka = boothKey(a.b), kb = boothKey(b.b);
      return (a.b ? 0 : 1) - (b.b ? 0 : 1) || ka[0].localeCompare(kb[0]) || ka[1] - kb[1] || ka[2] - kb[2] || a.c.n.localeCompare(b.c.n);
    });
    return rows;
  }

  function tabByFair() {
    if (!S.bf || !FAIR[S.bf]) S.bf = (D.fairs[0] || {}).key || "";
    var f = FAIR[S.bf] || {};
    var rows = fairRows(S.bf);
    var withBooth = rows.filter(function (r) { return r.b; }).length;
    main.innerHTML =
      '<p class="note">전시회를 고르면 <b>그 전시회에 나오는 업체</b>만 부스 순으로 보여줍니다. 회사를 누르면 상세, 오른쪽 열은 같은 회사가 나온 다른 전시회입니다.</p>' +
      '<div class="rchips" style="padding:0 0 12px">' + D.fairs.map(function (x) {
        return '<button class="chip' + (S.bf === x.key ? " on" : "") + '" data-bf="' + esc(x.key) + '">' + esc(x.title) + " <b>" + num(x.kept) + "</b></button>";
      }).join("") + "</div>" +
      '<div class="card">' +
      '<div class="fcard" style="border-bottom:1px solid var(--line)"><h3>' + esc(f.title) + ' <span class="kind ' + (f.kind || "") + '">' + (f.kind === "confirmed" ? "확정 명단" : "직전 회차") + "</span></h3>" +
      '<div class="meta">' + esc(f.city) + " · " + esc(ccName(f.country)) + " · " + esc(f.when) + " · " + esc(f.note || "") + " · " +
      '<a class="flink" href="' + esc(f.url) + '" target="_blank" rel="noopener">출품사 명단 원문 ↗</a></div></div>' +
      '<div class="rtool">' +
      '<input id="bfq" type="search" placeholder="이 전시회 안에서 회사·제품 찾기" value="' + esc(S.bfq) + '">' +
      '<select id="bfSort">' +
      '<option value="booth"' + (S.bfSort === "booth" ? " selected" : "") + ">정렬: 부스 번호</option>" +
      '<option value="name"' + (S.bfSort === "name" ? " selected" : "") + ">정렬: 회사명</option>" +
      '<option value="fld"' + (S.bfSort === "fld" ? " selected" : "") + ">정렬: 분야</option>" +
      '<option value="fairs"' + (S.bfSort === "fairs" ? " selected" : "") + ">정렬: 다른 전시회 출품 많은 순</option>" +
      "</select>" +
      '<span class="cnt"><b>' + num(rows.length) + "</b>개 업체 · 부스 확인 " + num(withBooth) + "</span>" +
      '<button class="rbtn" id="bfcsv">⬇ 이 전시회 CSV</button>' +
      "</div>" +
      '<div class="rchips"><span class="lbl">분야</span>' +
      '<button class="chip' + (S.bfFld ? "" : " on") + '" data-bffld="">전체</button>' +
      D.fields.map(function (x) {
        var n = 0; D.companies.forEach(function (c) { if (c.fld === x[0] && c.f.some(function (e) { return e.k === S.bf; })) n++; });
        return '<button class="chip' + (S.bfFld === x[0] ? " on" : "") + '" data-bffld="' + x[0] + '">' + esc(x[1]) + " <b>" + num(n) + "</b></button>";
      }).join("") + "</div>" +
      '<div class="tblwrap"><table class="rtbl"><thead><tr>' +
      "<th>부스</th><th>회사</th><th>국가</th><th>분야</th><th>카테고리 · 산업</th><th>무엇을 만드는가</th><th>다른 출품 전시회</th>" +
      "</tr></thead><tbody>" +
      rows.slice(0, S.bfLimit).map(function (r) {
        var c = r.c;
        var others = c.f.filter(function (x) { return x.k !== S.bf; });
        var seen = {};
        return '<tr class="co" data-k="' + esc(c.k) + '">' +
          '<td style="white-space:nowrap;font-weight:700">' + (r.b ? '<a class="flink" href="' + esc(r.u || f.url) + '" target="_blank" rel="noopener">' + esc(r.b) + "</a>" : '<span style="color:var(--dim)">—</span>') + "</td>" +
          '<td class="nm">' + esc(c.n) + (c.ja ? "<small>" + esc(c.ja) + "</small>" : "") + "</td>" +
          "<td>" + (c.c.length ? c.c.map(function (x) { return '<span class="tag cc">' + esc(ccName(x)) + "</span>"; }).join("") : '<span class="tag cc">—</span>') + "</td>" +
          "<td>" + (c.fld ? '<span class="tag ' + c.fld + '">' + esc(FLD[c.fld]) + "</span>" : '<span class="tag">미분류</span>') + "</td>" +
          '<td class="cats">' + c.cat.map(function (k) { return '<span class="tag">' + esc(CAT[k]) + "</span>"; }).join("") +
          c.ind.map(function (k) { return '<span class="tag ind">' + esc(IND[k]) + "</span>"; }).join("") + "</td>" +
          '<td class="what">' + (c.what ? (c.ko ? esc(c.ko) + "<small>" + esc(c.what) + "</small>" : esc(c.what)) : '<span style="color:var(--dim)">소개글 없음</span>') + "</td>" +
          '<td class="fairs">' + others.filter(function (x) { if (seen[x.k]) return false; seen[x.k] = 1; return true; }).map(function (x) {
            return '<button class="flink' + ((FAIR[x.k] || {}).kind === "history" ? " hist" : "") + '" data-bf="' + esc(x.k) + '">' + esc(fairShort(x.k)) + "</button>";
          }).join("") + "</td></tr>";
      }).join("") +
      "</tbody></table></div>" +
      (rows.length > S.bfLimit ? '<div class="morebar"><button class="rbtn" id="bfmore">더 보기 (' + num(rows.length - S.bfLimit) + "개 남음)</button></div>" : "") +
      (rows.length ? "" : '<div class="empty">조건에 맞는 업체가 없습니다.</div>') +
      "</div>";
    function on(id, ev, fn) { var el = document.getElementById(id); if (el) el.addEventListener(ev, fn); }
    on("bfq", "input", function (e) { S.bfq = e.target.value; S.bfLimit = 200; var pos = e.target.selectionStart; render(); var el = document.getElementById("bfq"); if (el) { el.focus(); el.setSelectionRange(pos, pos); } });
    on("bfSort", "change", function (e) { S.bfSort = e.target.value; render(); });
    on("bfmore", "click", function () { S.bfLimit += 300; render(); });
    on("bfcsv", "click", function () { downloadCsv(rows.map(function (r) { return r.c; }), fairShort(S.bf)); });
    Array.prototype.forEach.call(main.querySelectorAll("[data-bf]"), function (b) {
      b.addEventListener("click", function (e) { e.stopPropagation(); S.bf = b.getAttribute("data-bf"); S.bfLimit = 200; render(); window.scrollTo(0, 0); });
    });
    Array.prototype.forEach.call(main.querySelectorAll("[data-bffld]"), function (b) {
      b.addEventListener("click", function () { S.bfFld = b.getAttribute("data-bffld"); S.bfLimit = 200; render(); });
    });
    Array.prototype.forEach.call(main.querySelectorAll("tr.co"), function (tr) {
      tr.addEventListener("click", function (e) { if (e.target.tagName === "A" || e.target.tagName === "BUTTON") return; openCompany(tr.getAttribute("data-k")); });
    });
  }

  // ---------------------------------------------------------------- 탭: 명단 확보 전시회
  function tabFairs() {
    main.innerHTML =
      '<p class="note">출품사 명단을 <b>웹에서 실제로 읽어 온</b> 전시회입니다. <b>확정 명단</b>은 다가오는 회차, <b>직전 회차</b>는 지난 회차의 출품 이력입니다(연례·격년 전시회는 출품사가 거의 그대로 이어집니다). 종합 전시회(ProMat)는 로봇 관련 업체만 추렸습니다.</p>' +
      '<div class="fgrid">' + D.fairs.map(function (f) {
        return '<div class="card fcard"><h3>' + esc(f.title) + "</h3>" +
          '<div class="meta">' + esc(f.city) + " · " + esc(ccName(f.country)) + " · " + esc(f.when) + " · " +
          '<span class="kind ' + (f.error ? "no" : f.kind) + '">' + (f.error ? "수집 실패" : f.kind === "confirmed" ? "확정 명단" : "직전 회차") + "</span></div>" +
          '<div class="nums"><div><b>' + num(f.kept) + "</b><span>실은 업체</span></div>" +
          (f.scope === "filter" ? "<div><b>" + num(f.listed) + "</b><span>전체 출품사</span></div>" : "") +
          "<div><b>" + num(f.with_desc) + "</b><span>소개글 있음</span></div></div>" +
          '<p class="note" style="margin:0 0 8px">' + esc(f.note || "") + "</p>" +
          (f.error ? '<p class="err">' + esc(f.error) + "</p>" : "") +
          '<a class="flink" href="' + esc(f.url) + '" target="_blank" rel="noopener">출품사 명단 원문 ↗</a> ' +
          '<button class="rbtn" data-goto="' + esc(f.key) + '">이 전시회 업체 보기</button>' +
          "</div>";
      }).join("") + "</div>";
    Array.prototype.forEach.call(main.querySelectorAll("[data-goto]"), function (b) {
      b.addEventListener("click", function () { S.bf = b.getAttribute("data-goto"); S.tab = "byfair"; setTab(); render(); window.scrollTo(0, 0); });
    });
  }

  // ---------------------------------------------------------------- 탭: 전세계 로봇 전시회(DB)
  var TIER = { core: ["로봇 전문", "kind confirmed"], adj: ["자동화·제조 (로봇 주요 품목)", "kind history"], mention: ["설명에 로봇 언급", "kind"] };
  function tierTag(e) { var t = TIER[e.tier || (e.core ? "core" : "mention")]; return '<span class="' + t[1] + '">' + t[0] + "</span>"; }

  function expoTable(list) {
    return '<div class="tblwrap"><table class="rtbl etbl"><thead><tr><th>일정</th><th>전시회</th><th>구분</th><th>국가 · 도시 · 장소</th><th>출품사 명단</th><th>원문</th></tr></thead><tbody>' +
      list.map(function (e) {
        return "<tr><td>" + esc(e.s) + (e.e && e.e !== e.s ? " ~ " + esc(e.e.slice(5)) : "") + "</td>" +
          '<td class="' + (e.core ? "core" : "") + '">' + esc(e.t) + (e.te && e.te !== e.t ? '<br><small style="color:var(--dim)">' + esc(e.te) + "</small>" : "") +
          (e.sum ? '<br><small style="color:var(--muted)">' + esc(e.sum.slice(0, 140)) + (e.sum.length > 140 ? "…" : "") + "</small>" : "") + "</td>" +
          "<td>" + tierTag(e) + "</td>" +
          "<td>" + esc(ccName(e.c)) + (e.city ? " · " + esc(e.city) : "") + (e.venue ? " · " + esc(e.venue) : "") + "</td>" +
          "<td>" + (e.lists.length ? e.lists.map(function (k) { return '<button class="flink" data-goto="' + k + '">' + esc(fairShort(k)) + " ↗</button>"; }).join("") : '<span class="kind no">미확보</span>') + "</td>" +
          '<td>' + (e.url ? '<a class="flink" href="' + esc(e.url) + '" target="_blank" rel="noopener">열기 ↗</a>' : "") + "</td></tr>";
      }).join("") + "</tbody></table></div>";
  }

  function tabExpos() {
    var core = D.expos.filter(function (e) { return (e.tier || "core") === "core"; });
    var adj = D.expos.filter(function (e) { return e.tier === "adj"; });
    var rest = D.expos.filter(function (e) { return e.tier === "mention" || (!e.tier && !e.core); });
    function tbl(list) {
      return '<div class="tblwrap"><table class="rtbl etbl"><thead><tr><th>일정</th><th>전시회</th><th>국가 · 도시</th><th>출품사 명단</th><th>원문</th></tr></thead><tbody>' +
        list.map(function (e) {
          return "<tr><td>" + esc(e.s) + (e.e && e.e !== e.s ? " ~ " + esc(e.e.slice(5)) : "") + "</td>" +
            '<td class="' + (e.core ? "core" : "") + '">' + esc(e.t) + (e.te && e.te !== e.t ? '<br><small style="color:var(--dim)">' + esc(e.te) + "</small>" : "") + "</td>" +
            "<td>" + esc(ccName(e.c)) + (e.city ? " · " + esc(e.city) : "") + "</td>" +
            "<td>" + (e.lists.length ? e.lists.map(function (k) { return '<button class="flink" data-goto="' + k + '">' + esc(fairShort(k)) + " ↗</button>"; }).join("") : '<span class="kind no">미확보</span>') + "</td>" +
            '<td>' + (e.url ? '<a class="flink" href="' + esc(e.url) + '" target="_blank" rel="noopener">열기 ↗</a>' : "") + "</td></tr>";
        }).join("") + "</tbody></table></div>";
    }
    main.innerHTML =
      '<p class="note">전시회 DB(국내 AKEI·코엑스·킨텍스·벡스코, KOTRA GEP, EventsEye 세계 달력 — 총 ' + "19,000여" + '건, 앞으로 15개월)에서 세 단계로 골랐습니다. ' +
      '<b>로봇 전문</b>은 제목에 로봇이 든 전시회, <b>자동화·제조</b>는 자동화·스마트팩토리·머신비전·드론·물류자동화·공작기계처럼 로봇이 주요 전시 품목인 전시회, <b>설명에 로봇 언급</b>은 소개글에서만 로봇이 나오는 곳입니다. ' +
      '같은 전시회의 여러 회차·출처는 하나로 합쳤습니다. <b>출품사 명단</b>이 "미확보"인 곳은 주최 측이 명단을 웹에 공개하지 않거나 아직 회차가 열리지 않은 곳입니다.</p>' +
      '<div class="sec-title"><h2>🤖 로봇 전문 전시회</h2><small>' + core.length + "개 · 날짜순</small></div>" +
      '<div class="card">' + expoTable(core) + "</div>" +
      '<div class="sec-title" style="margin-top:22px"><h2>🏭 자동화·제조 전시회 (로봇이 주요 품목)</h2><small>' + adj.length + "개</small></div>" +
      '<div class="card">' + expoTable(adj) + "</div>" +
      '<div class="sec-title" style="margin-top:22px"><h2>📎 설명에 로봇이 언급된 전시회</h2><small>' + rest.length + "개</small></div>" +
      '<div class="card">' + expoTable(rest) + "</div>";
    Array.prototype.forEach.call(main.querySelectorAll("[data-goto]"), function (b) {
      b.addEventListener("click", function () { S.fair = b.getAttribute("data-goto"); S.tab = "co"; S.limit = 150; setTab(); render(); });
    });
  }

  // ---------------------------------------------------------------- 탭: 한국 전시회 · 홍보 전략
  function tabKorea() {
    var kr = D.expos.filter(function (e) { return e.c === "KR"; });
    var core = kr.filter(function (e) { return e.tier === "core"; });
    var adj = kr.filter(function (e) { return e.tier === "adj"; });
    var rest = kr.filter(function (e) { return e.tier === "mention"; });
    // 데이터에서 뽑는 근거: 여러 전시회에 겹쳐 나오는 로봇 본체 업체(=부품 고객 후보), 국내 업체
    var body = D.companies.filter(function (c) { return c.fld === "body" && fairKeys(c).length >= 3; }).slice(0, 40);
    var krco = D.companies.filter(function (c) { return c.c.indexOf("KR") >= 0 || /korea|한국|코리아/i.test(c.n + c.ja); });
    var parts = D.companies.filter(function (c) { return c.fld === "parts" && fairKeys(c).length >= 3; }).slice(0, 25);
    function coList(list) {
      return list.map(function (c) {
        return '<button class="flink" data-co="' + esc(c.k) + '">' + esc(c.n) + "<em>" + fairKeys(c).length + "회</em></button>";
      }).join("");
    }
    main.innerHTML =
      '<div class="sec-title"><h2>🇰🇷 한국에서 열리는 로봇 관련 전시회</h2><small>로봇 전문 ' + core.length + " · 자동화·제조 " + adj.length + " · 로봇 언급 " + rest.length + "</small></div>" +
      '<div class="card">' + expoTable(core.concat(adj, rest)) + "</div>" +
      '<div class="sec-title" style="margin-top:26px"><h2>📣 로봇 부품 고객에게 한국에서 홍보하는 방법</h2><small>위 명단 데이터 + 국내 전시회 일정으로 정리한 제안</small></div>' +
      '<div class="card how">' +
      "<h3>1. 고객이 누구인가 — 명단 데이터가 말해 주는 것</h3><ul>" +
      "<li><b>로봇 본체 제조사</b>가 커넥터·케이블·하네스의 1차 고객입니다. 우리가 읽은 6회차 명단에서 <b>3개 이상 전시회에 겹쳐 나온 로봇 본체 업체</b>가 " + body.length + "곳입니다 — 전시회를 꾸준히 도는 곳은 신제품 주기가 빠르고 부품 소싱을 열어 두는 곳입니다.<br>" + coList(body) + "</li>" +
      "<li><b>국내 업체</b>로 해외 로봇 전시회(automatica·Automate·iREX)에 나간 곳이 " + krco.length + "곳입니다. 두산로보틱스·HD현대로보틱스·한화로보틱스·뉴로메카 계열(automatica 2025 한국관)·로보티즈·에이딘로보틱스·하이젠RNM(모터·감속기)·SPG(감속기) 등 — 해외 전시회에서 만나기보다 <b>국내에서 먼저 접촉</b>하는 편이 훨씬 싸고 빠릅니다.<br>" + coList(krco) + "</li>" +
      "<li><b>부품 경쟁·협업 상대</b>(3개 이상 전시회, 부품·요소기술): " + coList(parts) + " — 이들이 어느 부스에 어떤 형태로 나오는지가 우리 부스 기획의 기준점입니다.</li>" +
      "</ul><h3>2. 어느 국내 전시회에 나갈 것인가</h3><ul>" +
      "<li><b>로보월드 (11월, 킨텍스)</b> — 국내 최대 로봇 전문전. 로봇 본체·부품·SI가 한자리에 모이고 두산·HD현대·레인보우·뉴로메카·로보티즈 등 국내 본체사가 매년 나옵니다. <b>부품·요소기술관</b>에 부스를 내는 것이 1순위. 한국로봇산업협회(KAR)가 주최라 회원사 할인·공동관이 있습니다.</li>" +
      "<li><b>ROBEX 대구 (10월, 엑스코)</b> — 로봇 SI·제조 현장 위주(대구·경북 자동차 부품 벨트). 본체보다 <b>SI·적용 업체</b>와 만나기 좋고, 한국로봇산업진흥원(KIRIA)이 대구에 있어 지원사업 담당자를 직접 만날 수 있습니다.</li>" +
      "<li><b>AIMEX / Automation World (3월, 코엑스)</b> — 스마트공장·자동화 종합전. 로봇 본체사보다 <b>제어·센서·케이블·커넥터 부품사</b>의 비중이 큰 곳이라 우리와 같은 업종이 가장 많이 모입니다(경쟁사 동향 파악 + 협동로봇 주변기기 수요).</li>" +
      "<li><b>THE NEXT AI 피지컬AI & 스마트팩토리산업전 (10월, 창원)</b>, <b>제조자동화기술전 (4월, 창원)</b> — 경남 기계·방산 벨트. 휴머노이드·피지컬 AI를 앞세운 신설전이라 초기 출품 비용이 낮습니다.</li>" +
      "<li><b>Robot Tech Show (6월, 코엑스)</b>, <b>스마트공장구축 및 생산자동화전 (11월, 수원)</b> — 중소 SI·수요기업 위주. 부스보다 <b>참관 영업</b>(명함·샘플)이 효율적입니다.</li>" +
      "<li>인접 전시회 — 한국전자전 KES(10월)·반도체대전(10월)·국제물류산업대전 KOREA MAT(4월)은 로봇 전시회는 아니지만 <b>AMR·물류로봇·반도체 장비 로봇</b>의 수요처가 모입니다. 이미 출품 중이면 로봇용 하네스 데모를 한 코너 두는 것으로 충분합니다.</li>" +
      "</ul><h3>3. 어떻게 홍보할 것인가 — 커넥터·하네스 회사의 로봇 전시 방식</h3><ul>" +
      "<li><b>완제품이 아니라 '적용 사례'를 보여줍니다.</b> 로봇 관절(J1~J6) 내부 배선·엔코더 케이블·툴 체인저 커넥터·AMR 배터리 커넥터처럼 <b>로봇 한 대를 해부한 배선 데모</b>가 커넥터 카탈로그보다 훨씬 잘 통합니다. 굴곡 수명(1천만 회)·EMC·IP 등급을 숫자로 붙이세요.</li>" +
      "<li><b>본체사 부스를 먼저 돕니다.</b> 국내 전시회는 규모가 작아 하루면 본체사 부스를 다 돌 수 있습니다. 위 '3개 이상 전시회' 명단 중 국내 법인이 있는 곳(FANUC 코리아·야스카와·KUKA·UR·Techman·Dobot 등)은 부스 담당자가 곧 구매 창구입니다.</li>" +
      "<li><b>협동로봇·휴머노이드 신규 진입 업체</b>(에이딘·코라스·주강로보텍·리보틱스 같은 automatica 한국관 참가사)는 아직 부품 공급망이 굳지 않았습니다. 소량·맞춤 하네스 제안이 먹히는 곳입니다.</li>" +
      "<li><b>정부 지원을 씁니다.</b> KOTRA GEP 공고 기준으로 automatica(뮌헨)·Hannover Messe·WRC(베이징)는 매년 <b>한국관 단체참가</b> 모집이 있었습니다(메인 레이더의 '우리 관련·지원' 탭). 국내 전시회는 KAR·KIRIA·지자체(대구·창원) 공동관과 중소기업 참가비 지원(중진공·지방 테크노파크)을 노립니다.</li>" +
      "<li><b>전시 전후가 더 중요합니다.</b> 이 화면의 CSV로 대상 업체 목록을 뽑아 전시 4주 전 미팅 요청 → 부스에서 샘플 전달 → 전시 후 2주 내 견적. 국내 전시회는 관람객 수가 적어 <b>사전 약속 없는 부스는 성과가 낮습니다</b>.</li>" +
      "</ul><p class=\"note\" style=\"margin-top:12px\">이 제안은 위 출품사 명단(6회차)과 전시회 DB 일정을 근거로 한 판단이며, 국내 전시회 출품사 명단은 아직 자동 수집하지 못했습니다(로보월드 2026 사이트 미개설·ROBEX 비공개). 확정 부스·비용은 각 주최 측 공고로 확인하세요.</p>" +
      "</div>";
    Array.prototype.forEach.call(main.querySelectorAll("[data-goto]"), function (b) {
      b.addEventListener("click", function () { S.fair = b.getAttribute("data-goto"); S.tab = "co"; S.limit = 150; setTab(); render(); });
    });
    Array.prototype.forEach.call(main.querySelectorAll("[data-co]"), function (b) {
      b.addEventListener("click", function () { openCompany(b.getAttribute("data-co")); });
    });
  }

  // ---------------------------------------------------------------- 탭: 만든 방법·한계
  function tabHow() {
    main.innerHTML = '<div class="card how">' +
      "<h3>어떻게 모았나</h3><ul>" +
      "<li>전시회 DB에서 로봇 전시회를 고른 뒤, 주최 측이 <b>웹에 공개한 출품사 명단</b>을 읽었습니다. 각 업체 줄의 전시회 링크가 곧 출처입니다.</li>" +
      "<li>Automate·ProMat(미국)은 MapYourShow 출품사 검색, iREX(도쿄)는 출품사 그리드 API, automatica(뮌헨)는 출품사 포털의 엑셀 내려받기를 씁니다.</li>" +
      "<li>같은 회사가 전시회마다 다른 법인명(FANUC America / FANUC Deutschland)으로 나오면 법인격·지역 표기를 떼고 <b>한 회사로 합쳤습니다</b>. 국가 칸은 그래서 여러 개가 붙을 수 있고, 출품 법인 기준이라 본사와 다를 수 있습니다.</li>" +
      "</ul><h3>분류는 어떻게 했나</h3><ul>" +
      "<li><b>카테고리·산업·분야</b>는 회사 소개글·전시 하이라이트·전시회 태그에서 키워드(영·일·한·중)를 찾아 붙인 규칙 분류입니다. 소개글이 없으면 분류가 비어 있고, 소개글이 두루뭉술하면 '로봇(세부 미분류)'로 남습니다.</li>" +
      "<li><b>강점</b>은 소개글 문장 중 '세계 최대·선도·최초·특허·수상·N년' 같은 표지가 있는 문장을 그대로 발췌한 것입니다. 회사의 자기소개이므로 검증된 사실이 아닙니다.</li>" +
      "</ul><h3>한계 · 못 읽은 전시회</h3><ul>" +
      "<li>Automate 2027·automatica 2025는 회사명과 부스만 공개해 소개글이 없습니다(Automate는 회차가 다가오면 채워집니다).</li>" +
      "<li>로보월드(서울)는 2026 사이트가 아직 열리지 않았고, ROBEX(대구)는 출품사 관리 시스템 안에만, WRC(베이징)·CIROS(상하이)·TAIROS(타이베이)는 봇 차단 또는 JS 전용이라 자동 수집이 안 됩니다. Hannover Messe·SPS는 로봇 전용 필터가 없어 뺐습니다.</li>" +
      "<li>매일 08:45 수집이 돌면서 명단이 갱신됩니다. 회차가 바뀌면 robots.py의 FAIRS 목록에 새 회차를 추가해야 합니다.</li>" +
      "</ul></div>";
  }

  // ---------------------------------------------------------------- 탭 전환
  function setTab() {
    Array.prototype.forEach.call(document.querySelectorAll("#tabs button"), function (b) {
      b.classList.toggle("on", b.getAttribute("data-tab") === S.tab);
    });
  }
  Array.prototype.forEach.call(document.querySelectorAll("#tabs button"), function (b) {
    b.addEventListener("click", function () { S.tab = b.getAttribute("data-tab"); setTab(); render(); window.scrollTo(0, 0); });
  });

  function render() {
    if (S.tab === "fair") tabFairs();
    else if (S.tab === "byfair") tabByFair();
    else if (S.tab === "expo") tabExpos();
    else if (S.tab === "kr") tabKorea();
    else if (S.tab === "how") tabHow();
    else tabCompanies();
  }

  header();
  render();
})();
