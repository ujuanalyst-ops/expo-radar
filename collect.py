#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전시회·박람회 수집기 — 표준 라이브러리만, 로그인·API키 없는 공개 목록만 읽는다.

각 수집기는 dict 리스트를 돌려준다. 공통 키:
  source / native_id / title / start / end (YYYY-MM-DD) / country(ISO2 또는 'KR') / city / venue / url
  선택: title_en / date_prec('day'|'month') / summary / org / homepage / cycle / ind_hint
        exhibitors / visitors / area / ufi / auma / support / image / region / sigungu / lat / lon
"""

import html as htmllib
import json
import re
import ssl
import subprocess
import time
import urllib.parse
import urllib.request
from multiprocessing.dummy import Pool as ThreadPool
from datetime import date, timedelta

import countries
import taxonomy

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
TIMEOUT = 90
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def _open(req, retries=2):
    last = None
    for i in range(retries + 1):
        try:
            return urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX).read()
        except Exception as e:  # noqa: BLE001 - 사이트 장애 시 다음 수집기로 넘어가기 위함
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def _curl(url, headers, data=None):
    """파이썬 소켓 연결을 끊는 사이트(GEP 등)용 우회로."""
    cmd = ["curl", "-sSL", "-m", str(TIMEOUT), "--retry", "2", "--retry-delay", "2", "-k"]
    for k, v in headers.items():
        if k.lower() != "connection":
            cmd += ["-H", f"{k}: {v}"]
    if data is not None:
        cmd += ["--data-binary", data.decode("utf-8") if isinstance(data, bytes) else data]
    cmd.append(url)
    return subprocess.run(cmd, capture_output=True, timeout=TIMEOUT + 30).stdout


def http(url, data=None, headers=None, form=None, as_json=False, enc="utf-8"):
    h = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
         "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
         "Connection": "close"}
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        h["X-Requested-With"] = "XMLHttpRequest"
    h.update(headers or {})
    try:
        raw = _open(urllib.request.Request(url, data=data, headers=h))
    except Exception:  # noqa: BLE001
        raw = _curl(url, h, data)
        if not raw:
            raise
    body = raw.decode(enc, "replace")
    return json.loads(body) if as_json else body


TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")


def text(s):
    if not s:
        return ""
    s = re.sub(r"<br\s*/?>", " ", str(s), flags=re.I)
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = TAG.sub(" ", s)
    s = htmllib.unescape(s).replace("\xa0", " ").replace("　", " ")
    return WS.sub(" ", s).strip()


DATE_RE = re.compile(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")


def norm_date(s):
    if not s:
        return None
    s = str(s)
    m = re.fullmatch(r"\s*(20\d{2})(\d{2})(\d{2})\s*", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = DATE_RE.search(s)
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None


def _num(s):
    m = re.search(r"[\d,]+", str(s or ""))
    return int(m.group(0).replace(",", "")) if m else 0


# ================================================================ 1) AKEI 국내전시회
AKEI = "https://www.akei.or.kr"


def _months(n):
    d = date.today()
    y, m = d.year, d.month
    for _ in range(n):
        yield y, m
        m += 1
        if m > 12:
            y, m = y + 1, 1


def collect_akei(months=14):
    """한국전시산업진흥회 전시회 일정 — searchMonth는 '시작 월' 기준, 상세 표가 목록에 인라인.
    지역 필드가 없어 장소명으로 판정하고, 해외 개최 건은 국가를 따로 잡는다."""
    out, seen = [], set()
    for y, m in _months(months):
        page = 1
        while page < 30:
            t = http(f"{AKEI}/bbs/board.php?bo_table=schedule&searchYear={y}&searchMonth={m:02d}&page={page}")
            blocks = re.findall(r'<li class="content_sc_li" id="content_sc_(\d+)">(.*?)'
                                r'(?=<li class="content_sc_li"|<nav class="pg_wrap|</form>)', t, re.S)
            for wid, blk in blocks:
                if wid in seen:
                    continue
                seen.add(wid)
                rows = {re.sub(r"\s", "", text(a)): text(b)
                        for a, b in re.findall(r"<th><span>(.*?)</span></th>\s*<td>(.*?)</td>", blk, re.S)}
                title = rows.get("전시회명(한글)") or rows.get("전시회명(영문)") or ""
                if not title:
                    continue
                ds = re.findall(r"20\d\d-\d\d-\d\d", rows.get("기간", ""))
                venue = rows.get("장소", "")
                field = re.sub(r"^\d+\.\s*", "", rows.get("전시분야", ""))
                hp = re.search(r'href="(https?://[^"]+)"', blk)
                reg, sub, la, lo, vname = taxonomy.place_kr(venue)
                cc = "KR" if reg else (countries.iso2(venue) or "KR")
                out.append({
                    "source": "akei", "native_id": wid, "title": title,
                    "title_en": rows.get("전시회명(영문)", ""),
                    "start": ds[0] if ds else None, "end": ds[-1] if ds else None,
                    "country": cc, "city": sub, "venue": vname,
                    "region": reg, "sigungu": sub, "lat": la, "lon": lo,
                    "org": rows.get("주최", ""), "summary": " · ".join(
                        x for x in (field, rows.get("세부품목", "")) if x)[:400],
                    "ind_text": f"{field} {rows.get('세부품목', '')}",
                    "url": f"{AKEI}/bbs/board.php?bo_table=schedule&wr_id={wid}",
                    "homepage": hp.group(1) if hp and "akei.or.kr" not in hp.group(1) else "",
                })
            if not blocks or not re.search(rf"page={page + 1}\D", t):
                break
            page += 1
            time.sleep(0.2)
    return out


# ================================================================ 2) 국내 전시장 자체 일정
def _venue_range(days=330):
    d = date.today()
    return d.isoformat(), (d + timedelta(days=days)).isoformat()


def collect_coex():
    s, e = _venue_range()
    out, seen = [], set()
    for page in range(1, 40):
        t = http(f"https://www.coex.co.kr/event/full-schedules/?var_page={page}"
                 f"&search_start_date={s.replace('-', '.')}&search_end_date={e.replace('-', '.')}&list_type=LIST")
        items = re.findall(r"<a href='(https://www\.coex\.co\.kr/exhibitions/[^'?]+)[^']*' "
                           r"class='BlogEventItem-link'>(.*?)</a>", t, re.S)
        fresh = 0
        for href, blk in items:
            if href in seen:
                continue
            seen.add(href)
            fresh += 1
            cont = blk.split("<div class='BlogEventItemCont'>", 1)[-1]

            def g(cls, c=cont):
                m = re.search(rf"class='BlogEventItemCont-{cls}[^']*'>(.*?)</", c, re.S)
                return text(m.group(1)) if m else ""

            cate = g("cate")
            if cate.startswith("Pop"):           # 팝업스토어는 전시회가 아니다
                continue
            ds = [norm_date(x) for x in re.findall(r"20\d\d\.\d\d\.\d\d", g("date"))]
            img = re.search(r"<img src='([^']+)'", blk)
            out.append({
                "source": "coex",
                "native_id": urllib.parse.unquote(href.rstrip("/").rsplit("/", 1)[-1])[:80],
                "title": g("tit"), "start": ds[0] if ds else None, "end": ds[-1] if ds else None,
                "country": "KR", "city": "강남구", "venue": "코엑스 " + g("hall"),
                "region": "seoul", "sigungu": "강남구", "lat": 37.51257, "lon": 127.05882,
                "ind_text": cate, "image": img.group(1) if img else "", "url": href,
            })
        if not fresh:
            break
        time.sleep(0.2)
    return out


def collect_kintex():
    s, e = _venue_range()
    out = []
    t = http(f"https://www.kintex.com/web/ko/event/list.do?pageIndex=1&pageUnit=300"
             f"&searchType=11&searchStartDt={s}&searchEndDt={e}")
    for sid, blk in re.findall(r"fnView\('\./view\.do',\s*(\d+)\)(.*?item-date\">.*?</div>)", t, re.S):
        def g(cls, b=blk):
            m = re.search(rf'item-{cls}">(.*?)</div>', b, re.S)
            return text(m.group(1)) if m else ""

        title = g("subject")
        if not title:
            continue
        ds = [norm_date(x) for x in re.findall(r"20\d\d\.\d\d\.\d\d", g("date"))]
        out.append({
            "source": "kintex", "native_id": sid, "title": title,
            "start": ds[0] if ds else None, "end": ds[-1] if ds else None,
            "country": "KR", "city": "고양시", "venue": ("킨텍스 " + g("client")).strip(),
            "region": "gyeonggi", "sigungu": "고양시", "lat": 37.66899, "lon": 126.74525,
            "url": f"https://www.kintex.com/web/ko/event/view.do?seq={sid}",
        })
    return out


def collect_bexco():
    s, e = _venue_range()
    out, seen = [], set()
    for page in range(1, 30):
        t = http(f"https://www.bexco.co.kr/kor/CMS/EventScheduleMgr/list.do?mCode=MN214&page={page}"
                 f"&schEvent=001&schStartDate={s}&schEndDate={e}")
        it = re.findall(r'event_seq=(\d+)">.*?<span class="subject">(.*?)</span>\s*'
                        r'<span class="date">(.*?)</span>\s*<span class="place">(.*?)</span>', t, re.S)
        fresh = 0
        for sid, title, date_s, place in it:
            if sid in seen:
                continue
            seen.add(sid)
            fresh += 1
            ds = [norm_date(x) for x in re.findall(r"20\d\d[.\-]\d\d[.\-]\d\d", re.sub(r"\s+", "", date_s))]
            out.append({
                "source": "bexco", "native_id": sid, "title": text(title),
                "start": ds[0] if ds else None, "end": ds[-1] if ds else None,
                "country": "KR", "city": "해운대구", "venue": ("벡스코 " + text(place)).strip(),
                "region": "busan", "sigungu": "해운대구", "lat": 35.16903, "lon": 129.13606,
                "url": f"https://www.bexco.co.kr/kor/CMS/EventScheduleMgr/view.do?mCode=MN214&event_seq={sid}",
            })
        if not fresh:
            break
        time.sleep(0.2)
    return out


# ================================================================ 3) KOTRA 글로벌전시플랫폼(GEP) 해외전시회 DB
GEP = "https://www.gep.or.kr"
GEP_LIST = GEP + "/gept/ovrss/exbi/exbiInfo/selectOvrssExbiInfoList.do"
GEP_DETAIL = GEP + "/gept/ovrss/exbi/exbiInfo/exbiDetailMain.do?ovrssExbiCd="
DROP = ("fileInfo",)   # 목록 응답에 섞여 오는 base64 썸네일 — 그대로 두면 응답이 5MB가 넘는다


def _gep_page(st, ed, page, rows=100):
    hdr = {"Referer": GEP + "/gept/ovrss/exbi/exbiInfo/allExbiList.do"}
    d = http(GEP_LIST, headers=hdr, as_json=True,
             form={"opmtPdStrDe": st, "opmtPdEndDe": ed, "pageNumber": str(page), "rowsPerPage": str(rows)})
    for it in d.get("list", []):
        for k in DROP:
            it.pop(k, None)
    return d


def _gep_day(s):
    """'2026-09' 처럼 월까지만 적힌 건이 섞여 있다 → (YYYY-MM-DD, 정밀도)"""
    s = (s or "").strip()
    if re.fullmatch(r"20\d\d-\d\d", s):
        return s + "-01", "month"
    return (s if re.fullmatch(r"20\d\d-\d\d-\d\d", s) else None), "day"


def collect_gep(back_days=45, ahead_days=360):
    """개최기간 검색은 최대 1년 — 지난 45일(진행 중)과 앞으로 1년을 두 번에 나눠 받는다."""
    today = date.today()
    windows = [((today - timedelta(days=back_days)).isoformat(), today.isoformat()),
               (today.isoformat(), (today + timedelta(days=ahead_days)).isoformat())]
    out, seen = [], set()
    for st, ed in windows:
        first = _gep_page(st, ed, 1)
        pages = int(first["param"].get("totalPage", 1) or 1)
        # 목록 응답에 base64 썸네일이 붙어 오느라 한 쪽이 5MB다 → 쪽 단위로 병렬 수신
        with ThreadPool(6) as pool:
            later = pool.map(lambda p: _gep_page(st, ed, p), range(2, pages + 1))
        for d in [first] + list(later):
            for it in d.get("list", []):
                code = it.get("ovrssExbiCd")
                if not code or code in seen:
                    continue
                seen.add(code)
                s, prec = _gep_day(it.get("opmtPdStrDe"))
                e = _gep_day(it.get("opmtPdEndDe"))[0]
                if s and e and (e < s or (date.fromisoformat(e) - date.fromisoformat(s)).days > 60):
                    e = s                      # 기간 입력이 깨진 건이 있어 시작일만 신뢰
                name = (it.get("krnOvrssExbiNm") or "").strip()
                en = re.search(r"\[([^\]]+)\]\s*$", name)
                cc = countries.iso2(it.get("opmtNatNm")) or ""
                hint = [taxonomy.GEP_FIELD[c] for c in str(it.get("exbiIndustFildCd") or "").split(",")
                        if c in taxonomy.GEP_FIELD]
                out.append({
                    "source": "gep", "native_id": code,
                    "title": htmllib.unescape(re.sub(r"\s*\[[^\]]+\]\s*$", "", name) or name),
                    "title_en": htmllib.unescape(en.group(1)).strip() if en else "",
                    "start": s, "end": e or s, "date_prec": prec,
                    "country": cc, "country_raw": it.get("opmtNatNm", ""),
                    "city": it.get("opmtCtyNm", ""), "venue": "",
                    "summary": htmllib.unescape(it.get("exbiDcCn") or "")[:600],
                    "ind_hint": hint, "ind_text": name,
                    "exhibitors": _num(it.get("prtpcoCnt")), "visitors": _num(it.get("obsrvrCnt")),
                    "ufi": it.get("ufiCrtfcYn") == "Y", "auma": it.get("aumaCrtfcYn") == "Y",
                    "support": it.get("ntntrsSprtExbiYn") == "Y",
                    "url": GEP_DETAIL + code,
                })
    return out


def detail_gep(ev):
    """GEP 상세 — 개최장소·전시규모·전시품목·주최자·홈페이지·최근 통계."""
    t = http(GEP_DETAIL + ev["native_id"])
    body = re.sub(r"<script.*?</script>", " ", t, flags=re.S)
    plain = text(body)
    d = {}

    def grab(label, nxt):
        m = re.search(rf"{label}\s*(.*?)\s*(?={nxt})", plain)
        return m.group(1).strip() if m else ""

    d["venue"] = grab("개최장소", "개최규모|산업분야|전시품목|주최자")
    scale = grab("개최규모", "산업분야|전시품목|주최자")
    m = re.search(r"([\d,]+)\s*sqm", scale)
    if m:
        d["area"] = _num(m.group(1))
    d["items"] = grab("전시품목", "주최자|주최기관")[:400]
    d["org"] = grab("주최기관", "담당자|전화|팩스|이메일|홈페이지")
    m = re.search(r"홈페이지\s*([\w./\-]+\.[a-z]{2,}[^\s]*)", plain)
    if m:
        hp = m.group(1).strip(" .")
        d["homepage"] = hp if hp.startswith("http") else "http://" + hp
    # 최근 통계: '년도 참가국수 참가업체수(전체) 참가업체수(외국) 2025 20 262 156'
    m = re.search(r"참가업체수\(외국\)\s*((?:\d{4}\s+[\d,]+\s+[\d,]+\s+[\d,]+\s*)+)", plain)
    if m:
        rows = re.findall(r"(\d{4})\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", m.group(1))
        best = max((r for r in rows if _num(r[2])), key=lambda r: r[0], default=None)
        if best:
            d["stat_year"], d["nations"] = int(best[0]), _num(best[1])
            d["exhibitors"] = _num(best[2])
    m = re.search(r"참가객수\(단위:백명\)\s*((?:\d{4}\s+[\d.,]+\s*)+)", plain)
    if m:
        rows = [(y, v) for y, v in re.findall(r"(\d{4})\s+([\d.,]+)", m.group(1)) if float(v.replace(",", "")) > 0]
        if rows:
            d["visitors"] = int(float(max(rows)[1].replace(",", "")) * 100)
    return {k: v for k, v in d.items() if v}


def collect_gep_apply(pages=45):
    """한국관·개별참가 모집공고(정부지원) — 어떤 전시회에 지금 참가 신청을 받는지."""
    out = []
    url = GEP + "/gept/ovrss/prtcp/rcritPblanc/prtpcoAplyStpltSelect.do"
    hdr = {"Referer": GEP + "/gept/ovrss/prtcp/rcritPblanc/prtpcoPblancList.do"}
    for p in range(1, pages + 1):
        try:
            d = http(url, headers=hdr, as_json=True, form={"pageNumber": str(p)})
        except Exception:  # noqa: BLE001
            break
        lst = d.get("result") or []
        if not lst:
            break
        for it in lst:
            out.append({
                "source": "gep_apply", "native_id": str(it.get("pblancid", "")),
                "notice": it.get("noticeName", ""), "exhibition": it.get("exhibitionName", ""),
                "apply_start": norm_date(it.get("ntifyPdStrDe")), "apply_end": norm_date(it.get("ntifyPdEndDe")),
                "start": norm_date(it.get("opmtPdStrDe")), "end": norm_date(it.get("opmtPdEndDe")),
                "classify": it.get("classify", ""),
                "url": (GEP + "/gept/ovrss/prtcp/rcritPblanc/prtpcoPblancDetail.do"
                        f"?pblancId={it.get('pblancid', '')}&nowMenuNo=79&upperMenuNo=79"),
            })
        if p >= int((d.get("param") or {}).get("totalPage", 1) or 1):
            break
        time.sleep(0.3)
    return out


# ================================================================ 4) EventsEye · 전 세계 전시회 달력
EYE = "https://www.eventseye.com/fairs/"
MONTH_EN = ["january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december"]
MON_ABBR = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12}
ROW = re.compile(r"<tr>\s*<td>\s*<a href=\"(f-[^\"]+?-(\d+)-\d+\.html)\">(.*?)</a>\s*</td>\s*"
                 r"<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>", re.S)


def _eye_date(cell):
    """'09/01/2026<br><i>2 days</i>' 또는 'Sept. 2026' → (시작, 종료, 정밀도)"""
    raw = text(cell)
    m = re.search(r"(\d{2})/(\d{2})/(20\d{2})", raw)
    if m:
        s = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        days = _num(re.search(r"(\d+)\s*day", raw).group(1)) if re.search(r"(\d+)\s*day", raw) else 1
        return s.isoformat(), (s + timedelta(days=max(days - 1, 0))).isoformat(), "day"
    m = re.search(r"([A-Za-z]{3,5})\.?\s*(20\d{2})", raw)
    if m and m.group(1)[:3].lower() in MON_ABBR:
        mo = MON_ABBR[m.group(1)[:4].lower().rstrip(".")] if m.group(1)[:4].lower().rstrip(".") in MON_ABBR \
            else MON_ABBR[m.group(1)[:3].lower()]
        return f"{m.group(2)}-{mo:02d}-01", f"{m.group(2)}-{mo:02d}-28", "month"
    return None, None, "month"


def collect_eventseye(months=15, max_pages=40):
    """월별 목록(1쪽 50건)을 훑는다. cp1252 인코딩이고, 3번째 칸에 '도시 (국가)'와 전시장이 같이 온다.
    한 달치가 20~30쪽이라 달 단위로 병렬 수신하고, 같은 달 안에서는 순서대로 넘긴다."""
    today = date.today()
    y0 = today.year

    def one_month(i):
        out = []
        y = y0 + (today.month - 1 + i) // 12
        mo = (today.month - 1 + i) % 12
        for page in range(max_pages):
            suffix = "" if page == 0 else f"_{page}"
            url = f"{EYE}d1_trade-shows_{MONTH_EN[mo]}_{y - y0}{suffix}.html"
            try:
                t = http(url, enc="cp1252")
            except Exception:  # noqa: BLE001
                break
            rows = ROW.findall(t)
            if not rows:
                break
            for href, fid, name_cell, cycle, place, when in rows:
                m = re.search(r"<b>(.*?)</b>", name_cell, re.S)
                title = text(m.group(1)) if m else text(name_cell)
                m = re.search(r"<i>(.*?)</i>", name_cell, re.S)
                desc = text(m.group(1)) if m else ""
                s_, e_, prec = _eye_date(when)
                links = re.findall(r'<a href="([^"]+)">(.*?)</a>', place, re.S)
                city_raw = text(links[0][1]) if links else text(place)
                venue = text(links[1][1]) if len(links) > 1 else ""
                m = re.match(r"(.*?)\s*\((.+)\)\s*$", city_raw)
                city, cname = (m.group(1), m.group(2)) if m else (city_raw, "")
                out.append({
                    "source": "eventseye", "native_id": f"{fid}|{s_}",
                    "title": title, "title_en": title,
                    "start": s_, "end": e_, "date_prec": prec,
                    "country": countries.iso2(cname) or "", "country_raw": cname,
                    "city": re.sub(r",\s*[A-Z]{2}$", "", city), "venue": venue,
                    "cycle": text(cycle), "summary": desc[:400], "ind_text": f"{title} {desc}",
                    "url": EYE + href,
                })
            if len(rows) < 50:
                break
            time.sleep(0.2)
        return out

    with ThreadPool(8) as pool:
        chunks = pool.map(one_month, range(months))
    out, seen = [], set()
    for rows in chunks:
        for r in rows:
            if r["native_id"] in seen:
                continue
            seen.add(r["native_id"])
            out.append(r)
    return out


def detail_eventseye(ev):
    """EventsEye 상세 — 분야(Related industries)·관람대상·다음 회차 일정."""
    t = http(ev["url"], enc="cp1252")
    d = {}
    blk = re.search(r'<div class="industries".*?>(.*?)</div>', t, re.S)
    if blk:
        inds = [text(x) for x in re.findall(r"<a [^>]*>(.*?)</a>", blk.group(1), re.S)]
        if inds:
            d["sectors"] = inds[:8]
    m = re.search(r'<div class="audience".*?</h2>(.*?)</div>', t, re.S)
    if m:
        d["audience"] = text(m.group(1))
    m = re.search(r'<div class="frequency".*?</h2>(.*?)</div>', t, re.S)
    if m:
        d["cycle"] = text(m.group(1))
    # 공식 홈페이지는 'Contact info for <전시회>' 블록 안의 class="ev-web" 링크.
    # 그 블록 밖(개최장소 칸)에도 같은 클래스가 쓰여서, 범위를 좁히지 않으면
    # 호텔·컨벤션센터 주소를 전시회 홈페이지로 잘못 싣는다.
    blk = re.search(r'Contact info for(.{0,1800}?)</div>\s*</div>', t, re.S)
    if blk:
        m = re.search(r'href="(https?://[^"]+)"[^>]*class="ev-web"', blk.group(1)) or \
            re.search(r'class="ev-web"[^>]*href="(https?://[^"]+)"', blk.group(1))
        if m:
            d["homepage"] = m.group(1)
    return d


# ================================================================ 등록
SOURCES = [
    ("akei", "한국전시산업진흥회 국내전시회", collect_akei),
    ("coex", "코엑스 일정", collect_coex),
    ("kintex", "킨텍스 일정", collect_kintex),
    ("bexco", "벡스코 일정", collect_bexco),
    ("gep", "KOTRA 글로벌전시플랫폼(해외전시회)", collect_gep),
    ("eventseye", "EventsEye 세계 전시회 달력", collect_eventseye),
]
DETAILERS = {"gep": detail_gep, "eventseye": detail_eventseye}


if __name__ == "__main__":
    import sys
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for key, name, fn in SOURCES:
        if only and only != key:
            continue
        t0 = time.time()
        try:
            rows = fn()
            print(f"{key:10s} {len(rows):5d}건  {time.time() - t0:5.1f}s  {name}")
            if rows:
                print("   예시:", json.dumps(rows[0], ensure_ascii=False)[:300])
        except Exception as e:  # noqa: BLE001
            print(f"{key:10s} 실패: {type(e).__name__} {e}")
