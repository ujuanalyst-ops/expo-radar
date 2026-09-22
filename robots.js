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

  var S = { tab: "co", q: "", fair: "", fld: "", cat: "", ind: "", cc: "", sort: "fairs", descOnly: false, multi: false, limit: 150 };
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
      "분류는 소개글 키워드 규칙이라 참고용입니다.";
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
        var hay = (c.n + " " + c.ja + " " + c.desc + " " + c.show + " " + c.tags.join(" ") + " " +
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
      "<td>" + c.cat.map(function (k) { return '<span class="tag">' + esc(CAT[k]) + "</span>"; }).join("") +
      c.ind.map(function (k) { return '<span class="tag ind">' + esc(IND[k]) + "</span>"; }).join("") + "</td>" +
      '<td class="what">' + (c.what ? esc(c.what) : '<span style="color:var(--dim)">소개글 없음 — 전시회가 회사명만 공개</span>') + "</td>" +
      '<td class="str">' + esc(c.str[0] || "") + "</td>" +
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
      "<div><h4>무엇을 만드는 회사인가 (전시회 소개글)</h4>" + (c.desc ? '<p class="desc">' + esc(c.desc) + "</p>" : "<p>소개글 없음 — 이 전시회는 회사명·부스만 공개합니다.</p>") + "</div>" +
      (c.show ? "<div><h4>무엇을 전시했는가 (전시 하이라이트)</h4><p class=\"desc\">" + esc(c.show) + "</p></div>" : "") +
      (c.str.length ? "<div><h4>강점 (소개글에서 발췌)</h4><ul class=\"strl\">" + c.str.map(function (s) { return "<li>" + esc(s) + "</li>"; }).join("") + "</ul></div>" : "") +
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
  function downloadCsv(rows) {
    var head = ["회사", "회사(현지어)", "국가", "분야", "카테고리", "산업", "무엇을 만드는가", "전시 하이라이트", "강점", "전시회 태그", "출처 전시회", "부스", "출처 링크", "홈페이지"];
    var lines = [head].concat(rows.map(function (c) {
      return [c.n, c.ja, c.c.map(ccName).join("·"), FLD[c.fld] || "", c.cat.map(function (k) { return CAT[k]; }).join("·"),
        c.ind.map(function (k) { return IND[k]; }).join("·"), c.desc, c.show, c.str.join(" / "), c.tags.join("·"),
        c.f.map(function (x) { return fairShort(x.k); }).join("·"), c.f.map(function (x) { return x.b; }).join("·"),
        c.f.map(function (x) { return x.u; }).join(" "), c.web];
    }));
    var csv = "﻿" + lines.map(function (r) {
      return r.map(function (v) { return '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"'; }).join(",");
    }).join("\r\n");
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    a.download = "로봇전시회_출품업체_" + (D.generated || "").slice(0, 10) + ".csv";
    document.body.appendChild(a); a.click(); a.remove();
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
      b.addEventListener("click", function () { S.fair = b.getAttribute("data-goto"); S.tab = "co"; S.limit = 150; setTab(); render(); });
    });
  }

  // ---------------------------------------------------------------- 탭: 전세계 로봇 전시회(DB)
  function tabExpos() {
    var core = D.expos.filter(function (e) { return e.core; });
    var rest = D.expos.filter(function (e) { return !e.core; });
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
      '<p class="note">전시회 DB(국내 AKEI·KOTRA GEP·EventsEye 등)에서 <b>제목에 로봇이 들어간 전시회 ' + core.length + '개</b>와, 설명에 로봇이 언급된 전시회 ' + rest.length + '개를 골랐습니다. ' +
      '<b>출품사 명단</b> 칸이 "미확보"인 곳은 주최 측이 명단을 웹에 공개하지 않거나(로보월드·ROBEX·WRC·CIROS 등) 아직 회차가 열리지 않은 곳입니다.</p>' +
      '<div class="sec-title"><h2>🤖 로봇 전문 전시회</h2><small>' + core.length + "개 · 날짜순</small></div>" +
      '<div class="card">' + tbl(core) + "</div>" +
      '<div class="sec-title" style="margin-top:22px"><h2>📎 설명에 로봇이 언급된 전시회</h2><small>' + rest.length + "개 · 공작기계·자동화·물류 등</small></div>" +
      '<div class="card">' + tbl(rest) + "</div>";
    Array.prototype.forEach.call(main.querySelectorAll("[data-goto]"), function (b) {
      b.addEventListener("click", function () { S.fair = b.getAttribute("data-goto"); S.tab = "co"; S.limit = 150; setTab(); render(); });
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
    else if (S.tab === "expo") tabExpos();
    else if (S.tab === "how") tabHow();
    else tabCompanies();
  }

  header();
  render();
})();
