#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""수집 → 누적 → 중복 병합 → 분류 → `app-data.js`.

  python3 build.py                 # 전부 수집하고 다시 만든다
  python3 build.py --no-fetch      # 받아둔 데이터로 분류·화면만 다시 만든다(taxonomy 튜닝용)
  python3 build.py --only=gep      # 한 출처만 다시 수집
  python3 build.py --detail-budget=800   # 상세 보강 건수(기본 400)
"""

import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from multiprocessing.dummy import Pool as ThreadPool

import collect
import countries
import taxonomy

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
STORE = os.path.join(DATA, "expos.json")
DETAILS = os.path.join(DATA, "details.json")
APPLY = os.path.join(DATA, "apply.json")
RIVALS = os.path.join(DATA, "rivals.json")
LOCK = os.path.join(DATA, ".build.lock")
TODAY = date.today()


def load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def save(path, obj):
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, path)


def lock():
    for _ in range(120):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            time.sleep(5)
    return False


# ------------------------------------------------------------------ 수집
def fetch(only=None):
    rows, report = [], []

    def run(item):
        key, name, fn = item
        t0 = time.time()
        try:
            r = fn()
            return key, name, r, None, time.time() - t0
        except Exception as e:  # noqa: BLE001 - 한 출처가 죽어도 나머지는 살린다
            return key, name, [], f"{type(e).__name__}: {e}", time.time() - t0

    todo = [s for s in collect.SOURCES if not only or s[0] == only]
    with ThreadPool(len(todo)) as pool:
        for key, name, r, err, sec in pool.map(run, todo):
            rows.extend(r)
            report.append({"key": key, "name": name, "count": len(r), "error": err, "sec": round(sec, 1)})
            print(f"  {key:10s} {len(r):6d}건 {sec:6.1f}s {err or ''}")
    return rows, report


def merge_store(rows, only=None):
    """수집 결과를 data/expos.json 에 누적한다(first_seen 유지, 사라진 건도 남긴다)."""
    store = load(STORE, {})
    stamp = TODAY.isoformat()
    for r in rows:
        if not r.get("title") or not r.get("start"):
            continue
        key = f"{r['source']}:{r['native_id']}"
        old = store.get(key, {})
        r["first_seen"] = old.get("first_seen", stamp)
        r["last_seen"] = stamp
        store[key] = {**old, **{k: v for k, v in r.items() if v not in (None, "", [], {})}}
    # 1년 넘게 지난 전시회는 정리
    cutoff = (TODAY - timedelta(days=400)).isoformat()
    for k in [k for k, v in store.items() if (v.get("end") or v.get("start") or "9999") < cutoff]:
        del store[k]
    save(STORE, store)
    return store


# ------------------------------------------------------------------ 상세 보강
def enrich(store, budget=400):
    """상세는 느리니 예산만큼만 — 가까운 날짜·관련도 높은 것부터."""
    cache = load(DETAILS, {})
    horizon = (TODAY + timedelta(days=300)).isoformat()
    cands = []
    for key, ev in store.items():
        if ev["source"] not in collect.DETAILERS or key in cache:
            continue
        if not (TODAY.isoformat() <= (ev.get("end") or ev["start"]) <= horizon):
            continue
        rel = taxonomy.relevance(ev.get("title", "") + " " + ev.get("title_en", ""),
                                 ev.get("ind_text", ""), ev.get("ind_hint") or ())
        cands.append((-rel, ev["start"], key))
    cands.sort()
    picks = [k for _, _, k in cands[:budget]]
    if not picks:
        return cache
    print(f"  상세 보강 {len(picks)}건 (남은 후보 {max(len(cands) - len(picks), 0)}건)")

    def one(key):
        ev = store[key]
        try:
            return key, collect.DETAILERS[ev["source"]](ev)
        except Exception:  # noqa: BLE001
            return key, {}

    with ThreadPool(8) as pool:
        for key, d in pool.map(one, picks):
            cache[key] = d
    save(DETAILS, cache)
    return cache


# ------------------------------------------------------------------ 중복 병합
SRC_RANK = {"akei": 0, "gep": 1, "coex": 2, "kintex": 2, "bexco": 2, "eventseye": 3}


def merge_keys(ev):
    """같은 전시회를 가리키는 열쇠들 — (정규화 제목, 국가, 개최 월)"""
    ym = (ev.get("start") or "")[:7]
    cc = ev.get("country") or "?"
    out = []
    for t in (ev.get("title"), ev.get("title_en")):
        n = taxonomy.norm_title(t)
        if len(n) >= 4:
            out.append(f"{n}|{cc}|{ym}")
    return out


def _quick_inds(ev):
    return set(taxonomy.industries(f"{ev.get('title', '')} {ev.get('title_en', '')}",
                                   ev.get("ind_text", ""), hint=ev.get("ind_hint")))


def dedupe(items, log=None):
    groups, index = [], {}
    for ev in sorted(items, key=lambda e: (SRC_RANK.get(e["source"], 9), e.get("start") or "")):
        ks = merge_keys(ev)
        gid = next((index[k] for k in ks if k in index), None)
        if gid is None:
            gid = len(groups)
            groups.append([])
        groups[gid].append(ev)
        for k in ks:
            index.setdefault(k, gid)

    # 2차: GEP는 한글 제목뿐이라 영문 제목이 있는 EventsEye 건과 이름으로는 못 붙는다.
    # '같은 나라 · 같은 시작일 · 같은 종료일'이 딱 두 무리뿐이고 출처가 겹치지 않으며
    # 산업분야가 하나라도 같을 때만 합친다(그 이상은 남남일 수 있어 그냥 둔다).
    by_date = {}
    for gid, g in enumerate(groups):
        if not g or any(x.get("date_prec", "day") == "month" for x in g):
            continue
        s = min(x["start"] for x in g if x.get("start"))
        e = max(x.get("end") or x["start"] for x in g)
        by_date.setdefault(f"{g[0].get('country') or '?'}|{s}|{e}", []).append(gid)
    dead = set()
    for key, gids in by_date.items():
        gids = [g for g in gids if g not in dead]
        if len(gids) != 2 or key.startswith("?|") or key.startswith("KR|"):
            continue                            # 국내는 이미 한글·영문 제목이 다 있어 이름으로 붙는다
        a, b = groups[gids[0]], groups[gids[1]]
        sa, sb = {x["source"] for x in a}, {x["source"] for x in b}
        if sa != {"gep"} or sb != {"eventseye"}:
            continue                            # 한글 제목(GEP) ↔ 영문 제목(EventsEye) 짝만
        ca = next((taxonomy.city_key(x.get("city")) for x in a if taxonomy.city_key(x.get("city"))), None)
        cb = next((taxonomy.city_key(x.get("city")) for x in b if taxonomy.city_key(x.get("city"))), None)
        if ca and cb and ca != cb:
            continue                            # 아는 도시인데 서로 다르면 다른 전시회
        ia = set().union(*(_quick_inds(x) for x in a))
        ib = set().union(*(_quick_inds(x) for x in b))
        if not (ia & ib) or (ia & ib) == {"etc"}:
            continue
        if log is not None:
            log.append(f"{key}  {a[0].get('title', '')[:40]}  ==  {b[0].get('title', '')[:40]}")
        a.extend(b)
        dead.add(gids[1])
    return [g for i, g in enumerate(groups) if g and i not in dead]


def pick(group, field, default=""):
    for ev in group:
        v = ev.get(field)
        if v not in (None, "", [], 0, {}):
            return v
    return default


# ------------------------------------------------------------------ 조립
def build_events(store, details, applies):
    items = []
    for key, ev in store.items():
        e = dict(ev)
        e.update({k: v for k, v in (details.get(key) or {}).items() if v not in (None, "", [], {})})
        e["_key"] = key
        items.append(e)

    # 한국관·개별참가 모집공고를 전시회에 붙일 색인
    apply_idx = {}
    for a in applies:
        n = taxonomy.norm_title(a.get("exhibition") or a.get("notice"))
        if len(n) >= 4:
            apply_idx.setdefault(n, a)

    out, mlog = [], []
    for g in dedupe(items, mlog):
        head = g[0]
        start = min((x["start"] for x in g if x.get("start")), default=None)
        if not start:
            continue
        prec = "day" if any(x.get("date_prec", "day") == "day" for x in g) else "month"
        end = start if prec == "month" else max((x.get("end") or x["start"] for x in g), default=start)
        cc = pick(g, "country") or "?"
        ko_title = next((x["title"] for x in g if x["source"] in ("akei", "gep", "coex", "kintex", "bexco")), "")
        en_title = pick(g, "title_en")
        title = ko_title or head["title"]
        venue = pick(g, "venue")
        city = pick(g, "city")
        sectors = pick(g, "sectors", [])
        hint = []
        for x in g:
            hint += x.get("ind_hint") or []
        inds = taxonomy.industries(f"{title} {en_title}",
                                   " ".join(filter(None, [pick(g, "ind_text"), pick(g, "items"), " ".join(sectors)])),
                                   pick(g, "summary"), hint=hint)
        support = any(x.get("support") for x in g)
        ap = apply_idx.get(taxonomy.norm_title(title)) or apply_idx.get(taxonomy.norm_title(en_title))
        exhibitors = max((int(x.get("exhibitors") or 0) for x in g), default=0)
        visitors = max((int(x.get("visitors") or 0) for x in g), default=0)
        # 관련도는 설명문을 보지 않는다 — 홍보 문구의 '슈퍼 커넥터' 같은 비유에 점수가 튄다
        rel = taxonomy.relevance(f"{title} {en_title}", " ".join(
            filter(None, [pick(g, "ind_text"), pick(g, "items"), " ".join(sectors)])),
            inds, support or bool(ap), exhibitors)
        rec = {
            "id": head["_key"],
            "t": title, "te": en_title if en_title and en_title != title else "",
            "s": start, "e": end if end != start else "", "p": prec,
            "c": cc, "ci": city, "v": venue,
            "ind": inds, "rel": rel,
            "src": sorted({x["source"] for x in g}),
            "url": pick(g, "url"), "hp": pick(g, "homepage"), "org": pick(g, "org"),
            "sum": pick(g, "summary")[:420], "items": pick(g, "items")[:220],
            "cyc": pick(g, "cycle"), "sec": sectors[:6],
            "ex": exhibitors, "vi": visitors, "ar": int(pick(g, "area", 0) or 0),
            "fs": min(x.get("first_seen", TODAY.isoformat()) for x in g),
        }
        if taxonomy.is_connector_fair(title, en_title):   # 품목 설명까지 보면 오탐이 는다
            rec["cf"] = 1                      # 커넥터·케이블·하네스가 주제인 전시회
        if any(x.get("ufi") for x in g):
            rec["ufi"] = 1
        if support:
            rec["sup"] = 1
        if cc == "KR":
            # 출처마다 전시장 이름이 달라(코엑스 / COEX Exhibition Center) 대표 이름으로 통일한다
            reg2, sig2, _la, _lo, vname = taxonomy.place_kr(venue, title + " " + city)
            if vname and vname != venue:
                rec["v"] = vname
            rec["reg"] = pick(g, "region") or reg2
            rec["sig"] = pick(g, "sigungu") or sig2
        if ap:
            rec["ap"] = {"end": ap.get("apply_end"), "url": ap.get("url"),
                         "notice": ap.get("notice", "")[:120], "cls": ap.get("classify", "")}
        out.append({k: v for k, v in rec.items() if v not in (None, "", [], 0)})
    out.sort(key=lambda r: (r["s"], -r.get("rel", 0)))
    save(os.path.join(DATA, "merge_log.json"), mlog)
    print(f"  날짜로 합친 중복 {len(mlog)}건 (data/merge_log.json)")
    return out


def attach_rivals(events):
    """경쟁사 출품 기록(data/rivals.json)을 전시회에 붙인다.

    기록은 '어느 전시회 명단에서 봤다'만 알고 날짜는 회차 시점(YYYY-MM)만 있다.
      · kind=confirmed → 그 달 근처(±2개월)의 같은 이름 전시회에 붙인다.
      · kind=history(직전 회차 명단) → **1년 뒤 같은 전시회**에 붙인다(연례 전시회는 출품사가 거의 그대로다).
    이름은 연도·부제·개최지 꼬리표를 떼고 비교하고, 못 붙인 건은 화면에 따로 보여 준다.
    """
    riv = load(RIVALS, {})
    recs = riv.get("records") or []
    if not recs:
        return riv, []
    index = {}
    for e in events:
        for t in (e.get("t"), e.get("te")):
            n = taxonomy.norm_title(t)
            if len(n) >= 3:
                index.setdefault(n, []).append(e)

    def months(ym):
        y, m = int(ym[:4]), int(ym[5:7])
        return y * 12 + m

    unmatched = []
    for r in recs:
        raw = r.get("match") or r.get("fair") or ""
        names = [raw] + [p.strip() for p in re.split(r"\s+[-–|·]\s+", raw) if len(p.strip()) >= 3]
        keys = [k for k in (taxonomy.norm_title(x) for x in names) if len(k) >= 3]
        when = r.get("when") or ""
        if not keys or len(when) < 7:
            unmatched.append(r)
            continue
        hist = r.get("kind") in ("history", "past")
        target = months(when) + (12 * int(r.get("cycle") or 1) if hist else 0)
        span = 3 if hist else 2
        cands = [e for n in keys for e in index.get(n, [])]
        if not cands:
            cands = [e for n in keys for k, lst in index.items()
                     if len(k) >= 5 and (k.startswith(n) or n.startswith(k)) for e in lst]
        hit = None
        for e in sorted(cands, key=lambda e: e["s"]):
            if abs(months(e["s"][:7]) - target) <= span:
                hit = e
                break
        if not hit:
            unmatched.append(r)
            continue
        hit.setdefault("riv", []).append({
            "r": r["rival"], "b": r.get("booth", ""), "k": r.get("kind", ""),
            "fk": r.get("fair_key", ""), "u": r.get("url", ""), "m": r.get("matched", ""),
            "fair": r.get("fair", ""),
        })
    # 경쟁사가 한 곳도 안 걸린 전시회라도 **명단 자체는 연결**한다
    # (그러지 않으면 205개사를 받아 놓고 화면엔 '명단 미공개'로 뜬다)
    for f in riv.get("fairs") or []:
        if f.get("error") or not f.get("listed"):
            continue
        raw = f.get("match") or f.get("title") or ""
        names = [raw] + [p.strip() for p in re.split(r"\s+[-–|·]\s+", raw) if len(p.strip()) >= 3]
        keys = [k for k in (taxonomy.norm_title(x) for x in names) if len(k) >= 3]
        when = f.get("when") or ""
        if not keys or len(when) < 7:
            continue
        hist = f.get("kind") in ("history", "past")
        target = months(when) + (12 * int(f.get("cycle") or 1) if hist else 0)
        span = 3 if hist else 2
        for e in sorted((e for n in keys for e in index.get(n, [])), key=lambda e: e["s"]):
            if abs(months(e["s"][:7]) - target) <= span:
                e.setdefault("fks", [])
                if f["key"] not in e["fks"]:
                    e["fks"].append(f["key"])
                e.setdefault("fk", f["key"])
                break

    for e in events:
        if e.get("riv"):
            # 명단을 열 때 기본으로 보여줄 회차는 '다가오는 회차' 명단 쪽
            cur = next((x for x in e["riv"] if x.get("k") != "past"), e["riv"][0])
            e["fk"] = cur.get("fk", "")
            e["fks"] = sorted(set(e.get("fks") or []) | {x.get("fk") for x in e["riv"] if x.get("fk")})
            seen, keep = set(), []
            for x in e["riv"]:                     # 같은 회사 여러 부스는 한 줄로
                if x["r"] in seen:
                    continue
                seen.add(x["r"])
                keep.append(x)
            e["riv"] = keep
    return riv, unmatched


def fairs_as_events(events, riv):
    """출품사 명단은 있는데 우리 전시회 DB에 없는 전시회(예: JSAE 人とくるまのテクノロジー展,
    IPC APEX EXPO)는 명단 쪽 정보로 항목을 만들어 넣는다.
    직전 회차 명단이면 1년 뒤를 '다음 회차(예상)'로 잡고 날짜는 월까지만 표시한다."""
    have = set()
    for e in events:
        have.update(e.get("fks") or ([e["fk"]] if e.get("fk") else []))
    recs = riv.get("records") or []
    by_fair = {}
    for r in recs:
        by_fair.setdefault(r["fair_key"], []).append(r)
    made = []
    for f in riv.get("fairs") or []:
        key = f["key"]
        if key in have or not by_fair.get(key) or f.get("error"):
            continue
        y, m = int(f["when"][:4]), int(f["when"][5:7])
        if f.get("kind") in ("history", "past"):
            y += int(f.get("cycle") or 1)        # 지난 회차 명단 → 다음 회차를 예상 일정으로
        start = f"{y}-{m:02d}-01"
        if start < TODAY.isoformat()[:7] + "-01":
            continue
        seen, riv_list = set(), []
        for r in by_fair[key]:
            if r["rival"] in seen:
                continue
            seen.add(r["rival"])
            riv_list.append({"r": r["rival"], "b": r.get("booth", ""), "k": r.get("kind", ""),
                             "fk": key, "u": r.get("url", ""), "m": r.get("matched", ""),
                             "fair": r.get("fair", "")})
        inds = taxonomy.industries(f["title"] + " " + f.get("note", ""))
        title = f["title"]
        if f.get("kind") in ("history", "past"):
            title = re.sub(r"\b20\d\d\b", "", title).strip() + f" {y} (다음 회차 예상)"
        made.append({
            "id": "fairlist:" + key, "t": title, "te": "", "s": start, "p": "month",
            "c": f.get("country") or "?", "ci": f.get("city", ""), "v": "",
            "ind": inds, "rel": taxonomy.relevance(f["title"] + " " + f.get("note", ""), "", inds),
            "src": ["exhibitorlist"], "url": f.get("url", ""), "sum": f.get("note", ""),
            "fs": TODAY.isoformat(), "riv": riv_list, "fk": key, "fks": [key],
            "est": 1 if f.get("kind") in ("history", "past") else 0,
        })
    return made


def write_app(events, report, rivals=None, riv_unmatched=None):
    used = sorted({e["c"] for e in events if e.get("c")})
    meta = {c: {"ko": countries.ko(c, c), "en": (countries.info(c) or {}).get("en", c),
                "region": (countries.info(c) or {}).get("region", "기타"),
                "sub": (countries.info(c) or {}).get("sub", "기타")} for c in used}
    payload = {
        "built": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "today": TODAY.isoformat(),
        "industries": [[c, e, n] for c, e, n, _ in taxonomy.INDUSTRIES],
        "regions": taxonomy.REGIONS,
        "countries": meta,
        "sources": report,
        "rivals": {
            "list": (rivals or {}).get("rivals", []),
            "fairs": (rivals or {}).get("fairs", []),
            "exhibitors": (rivals or {}).get("exhibitors", {}),
            "companies": (rivals or {}).get("companies", []),
            "discovered": (rivals or {}).get("discovered", []),
            "generated": (rivals or {}).get("generated", ""),
            "unmatched": riv_unmatched or [],
        },
        "events": events,
    }
    js = "window.DATA=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
    open(os.path.join(HERE, "app-data.js"), "w", encoding="utf-8").write(js)
    return len(js)


def main():
    args = sys.argv[1:]
    only = next((a.split("=", 1)[1] for a in args if a.startswith("--only=")), None)
    budget = int(next((a.split("=", 1)[1] for a in args if a.startswith("--detail-budget=")), 400))
    no_fetch = "--no-fetch" in args

    if not lock():
        print("다른 build 가 도는 중 — 그만둔다")
        return
    try:
        t0 = time.time()
        report = load(os.path.join(DATA, "report.json"), [])
        if no_fetch:
            store = load(STORE, {})
            print(f"수집 건너뜀 — 저장된 {len(store)}건 사용")
        else:
            print(f"[{datetime.now():%H:%M:%S}] 수집 시작")
            rows, report = fetch(only)
            store = merge_store(rows, only)
            save(os.path.join(DATA, "report.json"), report)
            try:
                applies = collect.collect_gep_apply()
                save(APPLY, applies)
                print(f"  {'gep_apply':10s} {len(applies):6d}건 (한국관·개별참가 모집공고)")
            except Exception as e:  # noqa: BLE001
                print("  gep_apply 실패:", e)
        details = enrich(store, 0 if no_fetch else budget)
        events = build_events(store, details, load(APPLY, []))
        rivals, riv_unmatched = attach_rivals(events)
        extra = fairs_as_events(events, rivals)
        if extra:
            events += extra
            events.sort(key=lambda r: (r["s"], -r.get("rel", 0)))
            print(f"  명단만 있는 전시회 {len(extra)}건을 목록에 추가")
        nriv = sum(1 for e in events if e.get("riv"))
        print(f"  경쟁사 출품 확인 {nriv}개 전시회 (못 맞춘 일정 {len(riv_unmatched)}건)")
        size = write_app(events, report, rivals, riv_unmatched)
        up = sum(1 for e in events if e["s"] >= TODAY.isoformat())
        print(f"[{datetime.now():%H:%M:%S}] 전시회 {len(events)}건(앞으로 {up}건) · "
              f"app-data.js {size // 1024}KB · {time.time() - t0:.0f}s")
    finally:
        try:
            os.remove(LOCK)
        except OSError:
            pass


if __name__ == "__main__":
    main()
