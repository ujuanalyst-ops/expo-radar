#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""해외 전시회 참가 지원공고 알림 — 새로 올라온 '우리 관련' 지원공고를 메일로 보낸다.

공고 원본은 옆 폴더 정부과제 레이더(gov-rnd-radar)가 매일 08:00에 모아 둔 것을 그대로 읽는다
(기업마당=부처·지자체, KOTRA 사업신청, GEP 한국관 모집, 중기부 수출컨소시엄, 수출바우처).
여기서는 ① 해외 전시회 참가 지원인지 ② 우리가 신청할 만한지(업종·지역)만 가려서 ③ 처음 본 것만 알린다.

  python3 support.py            # 새 공고가 있으면 메일 발송 (run_daily.sh가 매일 호출)
  python3 support.py --dry      # 무엇이 걸리는지 화면에만 출력 (발송·기록 없음)
  python3 support.py --test     # 지금 신청 가능한 공고 전체로 시험 메일 1통 (기록은 건드리지 않음)

메일 설정은 data/mail.json (git에 올라가지 않는다). 비밀번호는 파일에 적지 않고 맥 키체인에서 읽는다:
  security add-generic-password -s expo-radar-mail -a <보내는 계정> -w
"""

import html
import json
import os
import re
import smtplib
import subprocess
import sys
from datetime import date, timedelta
from email.mime.text import MIMEText
from email.utils import formatdate

import taxonomy

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
GOV_JS = os.path.join(ROOT, "..", "gov-rnd-radar", "app-data.js")
SEEN = os.path.join(DATA, "support_seen.json")
MAILCFG = os.path.join(DATA, "mail.json")
PREVIEW = os.path.join(ROOT, "share", "지원공고_알림_최신.html")
KEYCHAIN = "expo-radar-mail"
TODAY = date.today().isoformat()
OLD = (date.today() - timedelta(days=45)).isoformat()

SOURCES = {"gep": "GEP 한국관 모집", "kotra": "KOTRA 사업신청", "bizinfo": "기업마당(부처/지자체)",
           "smeexpo": "중기부 수출컨소시엄", "exportvoucher": "수출바우처"}
HOME = {"경기"}                 # 우리 사업장 지역 — 다른 시·도 기업 한정 공고는 신청 자격이 없다
MIN_REL = 3.0                   # 전시회가 정해진 공고는 업무 관련도 이 점수 이상만 알린다

FAIR = re.compile(r"전시|박람|한국관|공동관|단체관|엑스포|expo|페어|\bfair\b|\bshow\b|\b쇼\b", re.I)
ABROAD = re.compile(
    r"해외|수출|글로벌|국제|미국|중국|일본|독일|프랑스|이탈리아|이태리|스페인|영국|네덜란드|폴란드|튀르키예|러시아"
    r"|베트남|태국|인도|인도네시아|말레이시아|싱가포르|필리핀|대만|홍콩|호주|캐나다|멕시코|브라질"
    r"|UAE|두바이|사우디|카타르|이집트|유럽|북미|중남미|동남아|중동|아세안|CIS"
    r"|" + "|".join(sorted(taxonomy.CITY_KO, key=len, reverse=True)), re.I)
# 전시회 하나를 찍지 않고 '어느 해외 전시회든 참가비를 대 주는' 사업 — 업종과 무관하게 지역만 맞으면 대상
GENERIC = re.compile(r"개별\s*참가|전시(회|박람회)?\s*참가\s*(비\s*)?지원|해외\s*전시(회|박람회)?\s*(참가)?\s*지원"
                     r"|해외마케팅\s*지원|수출바우처.*(참여|참가|지원)\s*기업\s*모집")
# 참가비 지원사업이라도 남의 업종으로 못 박은 것은 뺀다
OTHER_IND = re.compile(r"소방|방산|국방|바이오|헬스|의료|제약|식품|푸드|food|농|수산|축산|뷰티|화장품|미용|섬유|패션|콘텐츠|게임|관광"
                       r"|교육|가구|완구|유아|반려|주류|한류|할랄", re.I)
SKIP = re.compile(r"수행기관|상담회\s*참가|매칭페어|캠페인|공모전|신고기간|채용|라이브커머스|환경개선|입찰|세미나|설명회|교육|결과\s*(발표|공고)|선정\s*결과|참관단|바이어\s*모집"
                  r"|팝업|온라인\s*(상담|로드쇼)|착한가격|기업박람회|취업|일자리")


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def load_programs():
    """정부과제 레이더가 만든 화면 데이터에서 공고 목록을 읽는다 → (공고들, 그 데이터의 기준일)."""
    with open(GOV_JS, encoding="utf-8") as f:
        s = f.read()
    d, _ = json.JSONDecoder().raw_decode(s[s.index("{"):])
    return d.get("programs") or [], d.get("today") or ""


def judge(p):
    """알릴 만한 공고면 {kind, rel, flags}를, 아니면 None을 준다."""
    if p.get("source") not in SOURCES:
        return None
    if (p.get("apply_end") or "9999") < TODAY or p.get("state") == "마감" or p.get("info_only"):
        return None
    title = p.get("title") or ""
    blob = f"{title} {p.get('program') or ''}"
    if SKIP.search(title):
        return None
    regions = set(p.get("regions") or [])
    if regions and not (regions & HOME):
        return None
    generic = bool(GENERIC.search(title))
    if generic and OTHER_IND.search(title):
        return None
    # 마감일이 없는 게시판 글은 오래된 것까지 '접수중'으로 남는다 → 올라온 지 45일 넘으면 뺀다
    if not p.get("apply_end") and (p.get("posted") or p.get("first_seen") or TODAY) < OLD:
        return None
    # KOTRA·GEP·수출컨소시엄은 해외 사업만 다루므로 '해외' 신호를 따로 요구하지 않는다
    if not generic and not (FAIR.search(blob) and (p["source"] != "bizinfo" or ABROAD.search(title))):
        return None
    inds = taxonomy.industries(blob)
    rel = taxonomy.relevance(blob, "", inds, support=True)
    if not generic and rel < MIN_REL:
        return None
    flags = []
    if p.get("sme_only") or p["source"] == "smeexpo":
        flags.append("중소기업 한정일 수 있음(중견기업 자격 확인)")
    if regions:
        flags.append("/".join(sorted(regions)) + " 소재 기업 대상")
    return {"kind": "generic" if generic else "fair", "rel": rel, "flags": flags}


def pick(programs):
    out, used = [], set()
    for p in programs:
        j = judge(p)
        if not j:
            continue
        k = taxonomy.norm_title(p.get("title") or "")      # 같은 공고가 GEP와 수출컨소시엄 공지에 함께 올라온다
        if k in used:
            continue
        used.add(k)
        out.append({**p, **j})
    out.sort(key=lambda r: (r["kind"] != "fair", -r["rel"], r.get("apply_end") or "9999"))
    return out


# ------------------------------------------------------------------ 메일
def dleft(end):
    if not end:
        return ""
    n = (date.fromisoformat(end) - date.fromisoformat(TODAY)).days
    return "오늘 마감" if n == 0 else f"D-{n}"


def row_html(r):
    e = html.escape
    end = r.get("apply_end")
    meta = [SOURCES[r["source"]]]
    if r.get("exec_org"):
        meta.append(r["exec_org"])
    meta.append(f"신청 마감 {end} ({dleft(end)})" if end else "신청 마감은 공고문 확인")
    if r.get("event_start"):
        meta.append(f"전시회 개최 {r['event_start']}")
    flags = "".join(f'<div style="color:#b45309;font-size:12px">주의: {e(f)}</div>' for f in r["flags"])
    return ('<li style="margin:0 0 14px"><a href="%s" style="font-weight:600;color:#1d4ed8;text-decoration:none">%s</a>'
            '<div style="color:#555;font-size:13px">%s</div>%s</li>'
            % (e(r.get("url") or ""), e(r["title"]), e(", ".join(meta)), flags))


def mail_html(rows, head, stale):
    fairs = [r for r in rows if r["kind"] == "fair"]
    gens = [r for r in rows if r["kind"] == "generic"]
    parts = ['<div style="font-family:-apple-system,\'Apple SD Gothic Neo\',sans-serif;font-size:14px;color:#111;'
             'max-width:720px"><h2 style="font-size:18px;margin:0 0 4px">%s</h2>'
             '<div style="color:#666;font-size:12px;margin-bottom:18px">%s 기준, 전시회/박람회 레이더</div>'
             % (html.escape(head), TODAY)]
    if stale:
        parts.append('<div style="background:#fff6e5;padding:8px 12px;font-size:12px;margin-bottom:14px">'
                     '공고 원본(정부과제 레이더)이 %s 수집본입니다. 오늘 수집이 아직 안 돌았을 수 있습니다.</div>'
                     % html.escape(stale))
    for name, lst in (("전시회가 정해진 모집공고 (한국관, 단체참가)", fairs),
                      ("전시회를 고르는 참가비 지원사업 (개별참가, 바우처)", gens)):
        if lst:
            parts.append('<h3 style="font-size:14px;margin:18px 0 8px">%s %d건</h3><ul style="padding-left:18px;margin:0">'
                         % (name, len(lst)) + "".join(row_html(r) for r in lst) + "</ul>")
    parts.append('<div style="color:#888;font-size:12px;margin-top:20px">업종(전기전자, 자동차, 기계/로봇 등)과 '
                 '지역(전국 또는 경기)으로 추린 결과입니다. 신청 자격과 마감은 공고 원문에서 확인해 주세요.</div></div>')
    return "".join(parts)


def keychain_pw(user):
    r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN, "-a", user, "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def send_mail(subject, body):
    """보냈으면 True. 설정이나 비밀번호가 없으면 False(예외 없이)."""
    cfg = load_json(MAILCFG, {})
    user, to = cfg.get("user"), cfg.get("to") or []
    pw = keychain_pw(user) if user else ""
    if not (user and to and pw):
        print("  메일 미설정: data/mail.json 또는 키체인 비밀번호 없음 → 발송 건너뜀")
        return False
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"], msg["From"], msg["To"], msg["Date"] = subject, cfg.get("from") or user, ", ".join(to), formatdate(localtime=True)
    with smtplib.SMTP(cfg.get("host", "smtp.gmail.com"), int(cfg.get("port", 587)), timeout=30) as s:
        s.starttls()
        s.login(user, pw)
        s.sendmail(user, to, msg.as_string())
    print(f"  메일 발송: {', '.join(to)}")
    return True


def notify_mac(text):
    """메일이 아직 설정되지 않았을 때만 쓰는 임시 알림."""
    subprocess.run(["osascript", "-e", 'display notification "%s" with title "전시회 레이더: 지원공고"'
                    % text.replace('"', "'")], capture_output=True)


def main():
    dry, test = "--dry" in sys.argv, "--test" in sys.argv
    try:
        programs, gov_day = load_programs()
    except (OSError, ValueError) as e:
        print("지원공고: 정부과제 레이더 데이터를 못 읽음 →", e)
        return
    if not programs:
        print("지원공고: 원본이 비어 있어 건너뜀")
        return
    rows = pick(programs)
    first = not os.path.exists(SEEN)
    seen = load_json(SEEN, {})
    new = rows if (first or test) else [r for r in rows if r["id"] not in seen]
    print(f"지원공고: 신청 가능한 관련 공고 {len(rows)}건, 새로 알릴 것 {len(new)}건"
          + (" (첫 실행: 전체를 한 번 알림)" if first and not test else ""))
    for r in new:
        print(f"  [{r['source']:8s}] 관련도 {r['rel']:4.1f} 마감 {r.get('apply_end') or '미정':10s} {r['title'][:70]}")
    if dry or not new:
        return
    head = (f"지금 신청 가능한 해외 전시회 지원공고 {len(new)}건" if first or test
            else f"새 해외 전시회 지원공고 {len(new)}건")
    body = mail_html(new, head, gov_day if gov_day != TODAY else "")
    os.makedirs(os.path.dirname(PREVIEW), exist_ok=True)
    with open(PREVIEW, "w", encoding="utf-8") as f:
        f.write('<meta charset="utf-8">' + body)
    try:
        sent = send_mail(f"[전시회 레이더] {head} ({TODAY})", body)
    except Exception as e:  # noqa: BLE001 - 메일이 실패해도 수집 전체를 멈추지 않는다
        print("  메일 실패:", e)
        sent = False
    if test:
        return
    if not sent:
        notify_mac(f"새 지원공고 {len(new)}건 (메일 미발송, share 폴더의 지원공고_알림_최신.html 확인)")
        return                      # 못 보낸 건은 기록하지 않아 다음 실행 때 다시 알린다
    for r in new:
        seen[r["id"]] = TODAY
    with open(SEEN, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
