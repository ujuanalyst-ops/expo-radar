#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""경쟁사가 나가는 전시회 찾기 — **전시회 쪽 출품사 명단**을 읽는다.

경쟁사 홈페이지(자사 행사 페이지)는 대부분 봇을 막아 두어 쓸모가 없었다.
반대로 전시회 주최 측은 출품사 명단을 공개한다. 여기서 우리 경쟁사 이름만 골라낸다.

세 가지 플랫폼을 지원한다.
  mys   : MapYourShow (`<show>.mapyourshow.com/8_0/ajax/remote-proxy.cfm?action=search…`)
          — DesignCon·CES·Automate·IPC APEX·Interwire 등 북미 전시회 다수가 쓴다.
          갤러리 페이지를 먼저 열어 **세션 쿠키를 받아야** API가 403이 아니다.
  xlsx  : 메세 뮌헨 계열(jl.medien)이 공개하는 출품사 엑셀 (electronica 등)
          — 지난 회차 주소는 현재 회차로 넘어간다(아카이브 없음). productronica·automatica는 포털 주소가 달라 미지원.
  jsae  : 자동차기술회 '人とくるまのテクノロジー展' 출품사 목록(서버 렌더링 HTML)

**지난 회차 명단도 모은다.** 연례 전시회는 직전 회차 출품사가 다음 회차에도 거의 그대로 나온다.
그래서 기록마다 kind = 'confirmed'(다가오는 회차 명단) / 'history'(직전 회차 이력)로 구분해 둔다.

받은 명단은 **경쟁사와 이름이 맞는 줄만 남기고 나머지는 버린다**(주최 측 명단을 그대로 쌓지 않는다).

  python3 rivals.py            # 수집 → data/rivals.json
  python3 rivals.py --dump     # 전시회별 경쟁사 목록을 자세히 출력
"""

import html as _html
import http.cookiejar
import io
import json
import os
import re
import ssl
import sys
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import date, datetime
from multiprocessing.dummy import Pool as ThreadPool

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "rivals.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# ================================================================ 경쟁사 명단
# (키, 표시이름, 본사국, 성격, 이름 찾기 정규식, 등급)
#   등급 direct = 커넥터를 직접 만드는 경쟁사 / adj = 인접(하네스·수동부품·산업용 단자)
RIVALS = [
    # ── 사용자가 지정한 곳
    ("molex", "Molex", "US", "커넥터 종합(코크 그룹)", r"\bmolex\b", "direct"),
    ("te", "TE Connectivity (Tyco)", "CH", "커넥터 세계 1위", r"\bTE\s*Connectivity\b|\btyco\s*electronics\b", "direct"),
    ("aptiv", "Aptiv (구 Delphi)", "IE", "전장 하네스·커넥터", r"\baptiv\b|delphi (technologies|connection|automotive|connector)", "direct"),
    ("amphenol", "Amphenol", "US", "커넥터·센서 2위", r"amphenol|temposonics", "direct"),
    ("hirose", "Hirose 히로세", "JP", "소형 기판 커넥터", r"\bhirose\b|ヒロセ電機", "direct"),
    ("yazaki", "Yazaki 야자키", "JP", "전장 하네스 1위", r"\byazaki\b|矢崎", "direct"),
    ("jae", "JAE 일본항공전자", "JP", "차량·기기 커넥터", r"\bJAE\b|japan aviation electronics|日本航空電子", "direct"),
    ("jst", "JST 일본압착단자", "JP", "압착 단자·커넥터", r"\bJST\b(?!\s*(?:health|medical|pharma|bio|food))|j\.s\.t\.|japan solderless|日本圧着端子", "direct"),
    ("luxshare", "Luxshare 立讯精密", "CN", "커넥터·케이블 어셈블리", r"luxshare|立讯", "direct"),
    ("foxconn", "Foxconn FIT 鴻海", "TW", "커넥터·EMS", r"foxconn|hon\s*hai|鴻海|富士康", "direct"),
    ("ket", "KET 한국단자공업", "KR", "국내 전장 커넥터 1위", r"korea electric terminal|한국단자|케이이티|\bKET\b(?![a-z])", "direct"),
    ("iriso", "IRISO 이리소", "JP", "차량용 플로팅 커넥터", r"\biriso\b|イリソ", "direct"),
    ("rosenberger", "Rosenberger", "DE", "RF·고주파 커넥터", r"rosenberger", "direct"),
    ("harwin", "Harwin", "GB", "고신뢰 소형 커넥터", r"\bharwin\b", "direct"),
    ("ipex", "I-PEX 다이이치정공", "JP", "초소형 기판·FPC 커넥터", r"\bi-?pex\b|第一精工|dai-?ichi seiko", "direct"),
    # ── 내가 추가한 직접 경쟁사 (같은 제품군·같은 전시회에서 마주치는 곳)
    ("samtec", "Samtec", "US", "고속 전송 커넥터", r"\bsamtec\b", "direct"),
    ("harting", "HARTING", "DE", "산업용 커넥터", r"\bharting\b", "direct"),
    ("phoenix", "Phoenix Contact", "DE", "산업 커넥터·단자대", r"phoenix contact", "direct"),
    ("weidmuller", "Weidmüller", "DE", "산업 커넥터·단자대", r"weidm(ü|ue)?ller", "direct"),
    ("wago", "WAGO", "DE", "스프링 단자·커넥터", r"\bwago\b", "direct"),
    ("odu", "ODU", "DE", "고신뢰 커넥터", r"\bodu\b(?!\w)|odu-usa", "direct"),
    ("lemo", "LEMO", "CH", "푸시풀 커넥터", r"\blemo\b(?!\w)", "direct"),
    ("fischer", "Fischer Connectors", "CH", "고신뢰 커넥터", r"fischer connect", "direct"),
    ("binder", "binder", "DE", "원형 커넥터", r"\bbinder\b(?!\w)", "direct"),
    ("smiths", "Smiths Interconnect", "GB", "고신뢰·RF 커넥터", r"smiths interconnect", "direct"),
    ("radiall", "Radiall", "FR", "RF·광 커넥터", r"\bradiall\b", "direct"),
    ("souriau", "SOURIAU (Eaton)", "FR", "군용·항공 커넥터", r"souriau|sunbank", "direct"),
    ("glenair", "Glenair", "US", "군용·항공 커넥터", r"\bglenair\b", "direct"),
    ("itt", "ITT Cannon", "US", "군용·산업 커넥터", r"itt cannon|\bcannon\b(?= connector)", "direct"),
    ("staubli", "Stäubli Electrical", "CH", "전력·산업 커넥터", r"st(ä|a)ubli|multi-?contact", "direct"),
    ("erni", "ERNI (TE)", "DE", "기판 커넥터", r"\berni\b(?!\w)", "direct"),
    ("lumberg", "Lumberg", "DE", "기판·산업 커넥터", r"\blumberg\b", "direct"),
    ("wurth", "Würth Elektronik", "DE", "커넥터·수동부품", r"w(ü|ue)rth elektronik", "direct"),
    ("kyocera", "Kyocera / AVX", "JP", "커넥터·수동부품", r"kyocera (avx|connector|industrial|electronic)|\bavx corp|kyocera avx", "direct"),
    ("panasonic", "Panasonic Industry", "JP", "커넥터·전자부품", r"panasonic", "adj"),
    ("hosiden", "Hosiden 호시덴", "JP", "커넥터·기구부품", r"hosiden|ホシデン", "direct"),
    ("smk", "SMK", "JP", "커넥터·스위치", r"\bSMK\b(?!\w)", "direct"),
    ("kel", "KEL 케이이엘", "JP", "고속 케이블 커넥터", r"\bKEL\b(?!\w)", "direct"),
    ("ddk", "DDK 第一電子工業", "JP", "커넥터", r"\bDDK\b|第一電子工業", "direct"),
    ("3m", "3M Interconnect", "US", "고속 인터커넥트", r"^3M\b|\b3M (company|inter|elect)", "adj"),
    ("bizlink", "BizLink", "TW", "케이블 어셈블리·커넥터", r"bizlink", "direct"),
    ("jonhon", "JONHON 中航光电", "CN", "군수·차량 커넥터", r"jonhon|中航光电", "direct"),
    ("yonggui", "Yonggui 永贵电器", "CN", "철도·차량 커넥터", r"yonggui|永贵", "direct"),
    ("deren", "Deren 得润电子", "CN", "차량 커넥터", r"deren|得润", "direct"),
    ("everwin", "Everwin 长盈精密", "CN", "커넥터·정밀부품", r"everwin|长盈", "direct"),
    # ── 출품사 명단에서 찾아내 승격시킨 곳 (여러 전시회에 겹쳐 나오는 커넥터 제조사)
    ("aces", "ACES 宏致電子", "TW", "커넥터·케이블", r"\bACES\b(?!\w)|宏致", "direct"),
    ("lintes", "Lintes 良維科技", "TW", "커넥터", r"lintes|良維", "direct"),
    ("bellwether", "Bellwether 維翰", "TW", "커넥터", r"bellwether electronic", "direct"),
    ("wieson", "Wieson 維熹科技", "TW", "커넥터·케이블", r"wieson", "direct"),
    ("greenconn", "GREENCONN 佳必琪", "TW", "커넥터", r"greenconn", "direct"),
    ("nienyi", "Nien-Yi 年一", "TW", "커넥터", r"nien-?yi", "direct"),
    ("jpcconn", "JPC Connectivity", "TW", "커넥터·케이블", r"jpc connectivity", "direct"),
    ("yfc", "YFC-BonEagle 裕山", "TW", "커넥터·케이블", r"yfc-?boneagle|yfc\b", "direct"),
    ("ksterminals", "K.S. Terminals 健和興", "TW", "단자·커넥터", r"k\.?s\.? terminals", "direct"),
    ("yamaichi", "Yamaichi 山一電機", "JP", "소켓·커넥터", r"yamaichi|山一電機", "direct"),
    ("junkosha", "Junkosha 潤工社", "JP", "고속 케이블", r"junkosha|潤工社", "direct"),
    ("zhaolong", "Zhaolong 兆龍互連", "CN", "케이블·인터커넥트", r"zhaolong|兆龙|兆龍", "direct"),
    ("preci", "PRECI-DIP", "CH", "정밀 컨택트·소켓", r"preci-?dip", "direct"),
    ("keystone", "Keystone Electronics", "US", "단자·커넥터 액세서리", r"keystone electronics", "direct"),
    ("advint", "Advanced Interconnections", "US", "소켓·커넥터", r"advanced interconnect", "direct"),
    # ── 국내 경쟁사·인접
    ("yeonho", "연호전자", "KR", "국내 커넥터", r"연호전자|연호일렉|yeonho", "direct"),
    ("cnplus", "씨엔플러스", "KR", "국내 커넥터", r"씨엔플러스|\bCN ?Plus\b|시엔플러스", "direct"),
    ("shinhwa", "신화콘텍", "KR", "국내 커넥터", r"신화콘텍|shinhwa contec", "direct"),
    ("lsmtron", "LS Mtron", "KR", "국내 커넥터", r"\bLS Mtron\b|엘에스엠트론", "direct"),
    ("sumitomo", "Sumitomo 스미토모", "JP", "전장 하네스·배선", r"sumitomo (electric|wiring)|住友電", "adj"),
    ("furukawa", "Furukawa 후루카와", "JP", "전선·전장부품", r"furukawa|古河", "adj"),
    ("fujikura", "Fujikura 후지쿠라", "JP", "전선·커넥터", r"fujikura|藤倉", "adj"),
    ("yura", "유라코퍼레이션", "KR", "국내 하네스", r"유라코퍼레이션|\bYURA\b", "adj"),
    ("kyungshin", "경신", "KR", "국내 하네스", r"경신|kyungshin", "adj"),
    ("leoni", "LEONI", "DE", "하네스·케이블", r"\bleoni\b", "adj"),
    ("kostal", "KOSTAL", "DE", "전장·커넥터", r"\bkostal\b", "adj"),
]
USER_KEYS = {"molex", "te", "aptiv", "amphenol", "hirose", "yazaki", "jae", "jst",
             "luxshare", "foxconn", "ket", "iriso", "rosenberger", "harwin"}
RIVAL_RE = [(k, re.compile(p, re.I)) for k, _, _, _, p, _ in RIVALS]
RIVAL_META = {k: {"key": k, "name": n, "country": c, "note": note, "tier": tier,
                  "user": k in USER_KEYS} for k, n, c, note, _p, tier in RIVALS}

# 자회사·판매법인 이름에 섞여 오탐이 잘 나는 조합을 걸러낸다
NOISE = re.compile(r"university|institute|associat|magazine|media|publish|consult(ing)?\b", re.I)


ROWS_CACHE = os.path.join(HERE, "data", "fair_rows_cache.json")
_CACHE_LOCK = threading.Lock()


def cache_rows(key, rows=None, label=""):
    """전시회별 '마지막으로 성공한 명단'을 보관한다.
    주최측 사이트가 하루 막히면(403·타임아웃) 그날 수집이 0건이 되는데,
    그대로 두면 공개 화면에서 그 전시회 출품사가 통째로 사라진다. 그래서
    성공하면 저장하고, 실패하거나 평소의 절반도 안 되면 지난 명단으로 되돌린다."""
    try:
        db = json.load(open(ROWS_CACHE, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        db = {}
    if rows is None:                      # 읽기
        return db.get(key)
    with _CACHE_LOCK:                     # 전시회를 동시에 받으므로 쓰기는 한 번에 하나씩
        try:
            db = json.load(open(ROWS_CACHE, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            db = {}
        db[key] = {"when": datetime.now().strftime("%Y-%m-%d %H:%M"), "n": len(rows), "rows": rows}
        tmp = f"{ROWS_CACHE}.{os.getpid()}.tmp"
        os.makedirs(os.path.dirname(ROWS_CACHE), exist_ok=True)
        json.dump(db, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, ROWS_CACHE)
    return None


def match_rivals(name):
    if not name or NOISE.search(name):
        return []
    return [k for k, rx in RIVAL_RE if rx.search(name)]


# ================================================================ 분야 구분
# 전시회가 79개까지 늘어 한 화면에 섞으면 못 본다. 분야 하나씩 나눠 보도록 꼬리표를 붙인다.
FIELD_RULES = [
    ("robot", "🤖 로봇·자동화", ("rb_", "automate")),
    ("defense", "🛡 방산·항공", ("eurosatory", "dsei", "siae", "ausa", "xponential", "farnborough", "droneshow")),
    ("auto", "🚗 자동차", ("jsae", "ampa", "aapex", "sema", "koaa", "automechanika", "iaa", "seoulmobility")),
    ("factory", "🏭 산업·기계", ("hannover", "sps26", "autoworld", "imts", "packexpo", "elecs", "h2meet")),
    ("medical", "🏥 의료", ("mdmwest", "medica")),
    ("battery", "🔋 배터리·EV", ("tbse", "tbsm", "interbattery", "evtrend")),
    ("connector", "🔌 커넥터·케이블 전문", ("ich_", "interwire", "wire_", "wire26")),
    # 나머지는 전자·IT (전자부품·반도체·광통신·데이터센터·통신·AV)
]
FIELD_DEFAULT = ("elec", "💻 전자·IT")
FIELD_NAMES = [(k, n) for k, n, _ in FIELD_RULES] + [FIELD_DEFAULT]


def field_of(key):
    for k, _, pats in FIELD_RULES:
        if any(key.startswith(p) or p in key for p in pats):
            return k
    return FIELD_DEFAULT[0]


# ================================================================ HTTP (쿠키 유지)
def opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj),
                                       urllib.request.HTTPSHandler(context=CTX))


TAG = re.compile(r"<[^>]+>")


def clean(t):
    return re.sub(r"\s+", " ", (t or "").replace("&nbsp;", " ").replace("\xa0", " ")).strip()


def get(op, url, referer=None, timeout=60):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
        **({"Referer": referer, "X-Requested-With": "XMLHttpRequest"} if referer else {})})
    return op.open(req, timeout=timeout).read()


# ================================================================ 전시회 목록
# match: 우리 전시회 DB에서 찾을 이름 · when: 명단이 가리키는 회차의 개최 시점(YYYY-MM)
FAIRS = [
    # ── MapYourShow (북미·글로벌)
    {"key": "designcon27", "platform": "mys", "host": "dcon27.mapyourshow.com",
     "title": "DesignCon 2027", "match": "DesignCon", "when": "2027-02", "kind": "confirmed",
     "city": "Santa Clara", "country": "US", "note": "고속 신호·인터커넥트 설계 전시회"},
    {"key": "ces27", "platform": "mys", "host": "exhibitors.ces.tech",
     "title": "CES 2027", "match": "CES", "when": "2027-01", "kind": "confirmed",
     "city": "Las Vegas", "country": "US", "note": "세계 최대 소비재 전자"},
    {"key": "automate27", "platform": "mys", "host": "automate27.mapyourshow.com",
     "title": "Automate 2027", "match": "Automate", "when": "2027-06", "kind": "confirmed",
     "city": "Chicago", "country": "US", "note": "북미 최대 자동화·로봇"},
    {"key": "apex27", "platform": "mys", "host": "apexexpo27.mapyourshow.com",
     "title": "IPC APEX EXPO 2027", "match": "APEX EXPO", "when": "2027-03", "kind": "confirmed",
     "city": "Anaheim", "country": "US", "note": "전자 조립·PCB"},
    {"key": "interwire27", "platform": "mys", "host": "interwire27.mapyourshow.com",
     "title": "Interwire 2027", "match": "Interwire", "when": "2027-05", "kind": "confirmed",
     "city": "Atlanta", "country": "US", "note": "와이어·케이블"},
    {"key": "aapex26", "platform": "mys", "host": "aapex2026.mapyourshow.com",
     "title": "AAPEX 2026", "match": "AAPEX", "when": "2026-11", "kind": "confirmed",
     "city": "Las Vegas", "country": "US", "note": "북미 자동차 애프터마켓 부품"},
    {"key": "mdmwest27", "platform": "mys", "host": "mdmwest27.mapyourshow.com",
     "title": "MD&M West 2027", "match": "MD&M West", "when": "2027-02", "kind": "confirmed",
     "city": "Anaheim", "country": "US", "note": "의료기기 설계·제조(고신뢰 커넥터 업체 다수)"},
    {"key": "sema26", "platform": "mys", "host": "sema26.mapyourshow.com",
     "title": "SEMA Show 2026", "match": "SEMA Show", "when": "2026-11", "kind": "confirmed",
     "city": "Las Vegas", "country": "US", "note": "자동차 튜닝·애프터마켓 (AAPEX와 같은 주)"},
    # ── 지난 회차 명단 (연례 전시회는 직전 출품사가 다음 회차에도 거의 그대로 나온다)
    {"key": "designcon26", "platform": "mys", "host": "dcon26.mapyourshow.com",
     "title": "DesignCon 2026", "match": "DesignCon", "when": "2026-01", "kind": "past", "cycle": 1,
     "city": "Santa Clara", "country": "US", "note": "지난 회차(2026-01) 출품 이력"},
    {"key": "automate26", "platform": "robots", "robot_key": "automate26",
     "page": "https://automate26.mapyourshow.com/8_0/explore/exhibitor-gallery.cfm",
     "title": "Automate 2026", "match": "Automate", "when": "2026-06", "kind": "history", "cycle": 1,
     "city": "Detroit", "country": "US",
     "note": "지난 회차 — 주최측 사이트가 닫혀(403) 이전에 받아 둔 명단을 쓴다"},
    {"key": "mdmwest26", "platform": "mys", "host": "mdmwest26.mapyourshow.com",
     "title": "MD&M West 2026", "match": "MD&M West", "when": "2026-02", "kind": "past", "cycle": 1,
     "city": "Anaheim", "country": "US", "note": "지난 회차(2026-02) 출품 이력"},
    # ── 메세 뮌헨 계열 출품사 엑셀
    {"key": "electronica26", "platform": "xlsx",
     "url": "https://exhibitors.electronica.de/download/informationmaterial/"
            "xls_electronica_Export_2026_en/electronica_export_2026_en.xlsx",
     "page": "https://exhibitors.electronica.de/exhibitor-portal/2026/list-of-exhibitors/",
     "title": "electronica 2026", "match": "electronica", "when": "2026-11", "kind": "confirmed",
     "city": "Munich", "country": "DE", "note": "세계 최대 전자부품 전시회"},
    {"key": "koaa26", "platform": "table",
     "url": "https://koaashow.com/visitors/company-list.php?category=",
     "title": "KOAA SHOW 2026 (국제 모빌리티 산업전)", "match": "KOAA SHOW", "when": "2026-10",
     "kind": "confirmed", "city": "서울 aT센터", "country": "KR",
     "note": "한국자동차산업협동조합 주최 — 국내 자동차부품사 집결"},
    {"key": "jpca26", "platform": "tems",
     "url": "https://jpca2026.tems-system.com/eguide/jp/jpca/list",
     "title": "JPCA Show 2026 (WIRE Japan Show 동시개최)", "match": "JPCA Show", "when": "2026-06",
     "kind": "past", "cycle": 1, "city": "Tokyo", "country": "JP",
     "note": "일본 전자회로·실장 전시회 — WIRE Japan Show·마이크로일렉트로닉스쇼 동시 개최"},
    # ── MapYourShow 추가 (AV·산업)
    {"key": "ise2027", "platform": "mys", "host": "ise2027.mapyourshow.com",
     "title": "ISE 2027 (Integrated Systems Europe)", "match": "ISE", "when": "2027-02",
     "kind": "confirmed", "city": "Barcelona", "country": "ES", "note": "유럽 최대 AV·시스템통합"},
    {"key": "ise2026", "platform": "mys", "host": "ise2026.mapyourshow.com",
     "title": "ISE 2026", "match": "ISE", "when": "2026-02", "kind": "past", "cycle": 1,
     "city": "Barcelona", "country": "ES", "note": "지난 회차 출품 이력"},
    {"key": "infocomm27", "platform": "mys", "host": "infocomm27.mapyourshow.com",
     "title": "InfoComm 2027", "match": "InfoComm", "when": "2027-06", "kind": "confirmed",
     "city": "Orlando", "country": "US", "note": "북미 최대 AV"},
    {"key": "imts26", "platform": "mys", "host": "imts26.mapyourshow.com",
     "title": "IMTS 2026", "match": "IMTS", "when": "2026-09", "kind": "past", "cycle": 2,
     "city": "Chicago", "country": "US", "note": "북미 최대 공작기계·제조기술(격년)"},
    {"key": "packexpo26", "platform": "mys", "host": "packexpo26.mapyourshow.com",
     "title": "PACK EXPO International 2026", "match": "PACK EXPO", "when": "2026-11",
     "kind": "confirmed", "city": "Chicago", "country": "US", "note": "북미 최대 포장기계"},
    {"key": "wire_russia27", "platform": "table",
     "url": "https://metallurgy-russia.ru/ru/exhibition/participants",
     "title": "wire Russia / Metallurgy Russia 2027", "match": "wire Russia", "when": "2027-05",
     "kind": "confirmed", "city": "Moscow", "country": "RU", "step": 5000, "max_rows": 5000,
     "note": "와이어·케이블·금속 동시 개최 — 참가업체 카탈로그가 한 쪽에 전부 나온다(러시아어 음차 표기)"},
    # ── IT·데이터센터·광통신·반도체 (기존 수집기를 그대로 쓰는 곳)
    {"key": "ofc27", "platform": "mys", "host": "ofc27.mapyourshow.com",
     "title": "OFC 2027 (광통신)", "match": "OFC", "when": "2027-03", "kind": "confirmed", "cycle": 1,
     "city": "San Diego", "country": "US",
     "note": "세계 최대 광통신 전시회 — 데이터센터 고속 인터커넥트 접점"},
    {"key": "pcim26", "platform": "mfesb",
     "api": "https://api.messefrankfurt.com/service/esb_api/exhibitor-service/api/2.1/public/exhibitor/search",
     "api_key": "LXnMWcYQhipLAS7rImEzmZ3CkrU033FMha9cwVSngG4vbufTsAOCQQ==", "event": "PCIMEUROPE",
     "page": "https://pcim.mesago.com/nuernberg/en/exhibitor-search.html",
     "title": "PCIM Europe 2026 (전력전자)", "match": "PCIM", "when": "2026-05", "kind": "history", "cycle": 1,
     "city": "Nuremberg", "country": "DE", "note": "전력전자 — 홈페이지·주소·홀/부스까지 나온다"},
    {"key": "productronica25", "platform": "xlsx",
     "url": "https://exhibitors.productronica.com/download/informationsmaterial/"
            "xls_productronica_Export_2025_de/productronica_export_2025_de.xlsx",
     "page": "https://exhibitors.productronica.com/ausstellerportal/2025/aussteller/",
     "title": "productronica 2025 (전자 생산장비)", "match": "PRODUCTRONICA", "when": "2025-11",
     "kind": "history", "cycle": 2, "city": "Munich", "country": "DE",
     "note": "격년(다음 2027-11) — electronica와 같은 포털. 주최측 표기상 상업적 이용 불가 자료"},
    {"key": "ocp26", "platform": "ocp",
     "page": "https://ocpstagingweb2.opencompute.org/summit/global-summit/sponsorship",
     "title": "OCP Global Summit 2026 (데이터센터)", "match": "OCP", "when": "2026-10", "kind": "confirmed",
     "cycle": 1, "city": "San Jose", "country": "US",
     "note": "AI 데이터센터 하드웨어 — 본 사이트가 봇을 막아 스테이징 호스트에서 읽는다(후원 등급=부스, 번호는 미공개)"},
    {"key": "sc26", "platform": "ungerboeck",
     "api": "https://hallerickson.ungerboeck.com/prod/api/VFPServer/GetInitialData",
     "origin": "https://hallerickson.ungerboeck.com", "config": 183,
     "page": "https://sc26.supercomputing.org/exhibition/exhibitor-list/",
     "title": "SC26 슈퍼컴퓨팅 (HPC)", "match": "SUPERCOMPUTING", "when": "2026-11", "kind": "confirmed",
     "cycle": 1, "city": "St. Louis", "country": "US", "note": "HPC·AI 인프라 — 부스·국가·품목코드 포함"},
    {"key": "embwld26", "platform": "algolia", "app": "4EB6G0V1NT",
     "api_key": "f0416e3d1b38ae3aa789c8750e12bfe5", "index": "prod_website_companies_en",
     "filter": 'site:"embwld"', "name_field": "companyName",
     "page": "https://www.embedded-world.de/en/exhibitors-products/find-exhibitors",
     "title": "embedded world 2026 (임베디드)", "match": "EMBEDDED WORLD", "when": "2026-03",
     "kind": "history", "cycle": 1, "city": "Nuremberg", "country": "DE",
     "note": "임베디드·보드 — 부스·국가 포함"},
    {"key": "mwc26", "platform": "algolia", "app": "8VVB6VR33K",
     "api_key": "8cfe02127da8785081bb08f9fbf274c7", "index": "exhibitors-barcelonaMWC",
     "name_field": "name", "letter_field": "letter",
     "letters": list("#ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
     "page": "https://www.mwcbarcelona.com/exhibitors",
     "title": "MWC Barcelona 2026 (통신)", "match": "MWC", "when": "2026-03", "kind": "history",
     "cycle": 1, "city": "Barcelona", "country": "ES",
     "note": "세계 최대 통신 전시회 — 머리글자로 나눠 받는다(한 번에 1000건 제한)"},
    {"key": "semicon_kr26", "platform": "a2z",
     "api": "https://expo.semi.org/korea2026/Public/Exhibitors.aspx",
     "page": "https://www.semiconkorea.org", "title": "SEMICON Korea 2026 (반도체)",
     "match": "SEMICON KOREA", "when": "2026-02", "kind": "history", "cycle": 1,
     "city": "서울 코엑스", "country": "KR", "note": "반도체 장비·소켓 — 국내 반도체 고객 접점"},
    {"key": "semicon_tw26", "platform": "a2z",
     "api": "https://expo.semi.org/taiwan2026/Public/Exhibitors.aspx",
     "page": "https://www.semicontaiwan.org", "title": "SEMICON Taiwan 2026 (반도체)",
     "match": "SEMICON TAIWAN", "when": "2026-09", "kind": "history", "cycle": 1,
     "city": "Taipei", "country": "TW", "note": "대만 반도체 — 커넥터·소켓 업체 다수"},
    {"key": "semicon_us26", "platform": "a2z",
     "api": "https://expo.semi.org/west2026/Public/eventmap.aspx",
     "page": "https://www.semiconwest.org", "title": "SEMICON West 2026 (반도체)",
     "match": "SEMICON WEST", "when": "2026-10", "kind": "history", "cycle": 1,
     "city": "Phoenix", "country": "US", "note": "출품사 목록 페이지가 막혀 배치도 페이지에서 읽는다"},
    {"key": "cioe26", "platform": "cioe",
     "api": "https://exhibitors.cioe.cn/gwen/data/zslist.ashx?method=dg_zhanshang&random=1",
     "page": "https://exhibitors.cioe.cn/gwen/index.html",
     "title": "CIOE 2026 (선전 광전자)", "match": "CIOE", "when": "2026-09", "kind": "history", "cycle": 1,
     "city": "Shenzhen", "country": "CN", "note": "중국 최대 광전자 — 홀·부스·주요품목 포함(응답이 느리다)"},
    {"key": "wis26", "platform": "wis", "api": "https://www.worlditshow.co.kr/src/visit_list.php",
     "year": 2026, "page": "https://www.worlditshow.co.kr/visit/03.php",
     "title": "월드IT쇼 2026", "match": "월드IT쇼", "when": "2026-04", "kind": "history", "cycle": 1,
     "city": "서울 코엑스", "country": "KR", "note": "국내 ICT 종합 — 회사명·소개·홈페이지(부스는 팝업)"},
    {"key": "ectc27", "platform": "ectc", "page": "https://www.ectc.net/exhibitors/",
     "title": "ECTC 2027 (패키징·인터커넥트)", "match": "ECTC", "when": "2027-06", "kind": "confirmed",
     "cycle": 1, "city": "Denver", "country": "US", "note": "패키징·인터커넥트 학회 전시(회사명만)"},
    {"key": "apec27", "platform": "cadmium",
     "api": "https://www.conferenceharvester.com/floorplan/v2/ajaxcalls/CreateRentedBoothList.asp",
     "event_id": 27332, "client_id": 2458, "event_key": "DDUCYCSD",
     "page": "https://www.conferenceharvester.com/floorplan/v2/index.asp?EventKey=DDUCYCSD",
     "title": "APEC 2027 (전력전자)", "match": "APEC", "when": "2027-03", "kind": "confirmed", "cycle": 1,
     "city": "New Orleans", "country": "US", "note": "전력전자 — 부스 포함"},
    {"key": "sensors27", "platform": "a2z",
     "api": "https://s36.a2zinc.net/clients/questex/sensors27/Public/eventmap.aspx",
     "page": "https://www.sensorsconverge.com", "title": "Sensors Converge 2027 (센서·IoT)",
     "match": "SENSORS CONVERGE", "when": "2027-06", "kind": "confirmed", "cycle": 1,
     "city": "Santa Clara", "country": "US", "note": "다가오는 회차 — 명단이 아직 초기(92곳)"},
    {"key": "ecoc26", "platform": "wpjson",
     "api": "https://www.ecocexhibition.com/wp-json/wp/v2/exhibitor-post",
     "page": "https://www.ecocexhibition.com/exhibit/exhibitor-list/",
     "title": "ECOC 2026 (유럽 광통신)", "match": "ECOC", "when": "2026-09", "kind": "history", "cycle": 1,
     "city": "Europe", "country": "DE", "note": "유럽 광통신 — 회사명만(부스는 업체별 상세에 있음)"},
    {"key": "nepcon_jp27", "platform": "rxalgolia", "app": "XD0U5M6Y4R",
     "api_key": "d5cd7d4ec26134ff4a34d736a7f9ad47",
     "index": "evt-545455d1-d612-473c-8b76-79bdddf367d0-index",
     "edition": "eve-c9ed2b9d-84a3-4932-ab81-e3e1d1441041",
     "page": "https://www.nepconjapan.jp/tokyo/en-gb/search/2027/directory.html",
     "title": "NEPCON JAPAN 2027 (도쿄, Automotive World 동시개최)", "match": "NEPCON JAPAN",
     "when": "2027-01", "kind": "confirmed", "cycle": 1, "city": "Tokyo", "country": "JP",
     "note": "일본 최대 전자·전장 전시회군 — 전자부품재료전·CAR-ELE·EV재팬이 한 회차에 같이 열린다"},
    {"key": "nepcon_asia26", "platform": "rxalgolia", "app": "XD0U5M6Y4R",
     "api_key": "d5cd7d4ec26134ff4a34d736a7f9ad47",
     "index": "evt-4fdd2120-7ff4-4a0d-b3ac-ecf82875547b-index",
     "edition": "eve-49c91c88-8eae-425e-8db1-e41f03da4a10",
     "page": "https://www.nepconasia.com/en-gb/zszx/exhibitor-directory.html",
     "title": "NEPCON Asia 2026 (선전)", "match": "NEPCON ASIA", "when": "2026-10", "kind": "history",
     "cycle": 1, "city": "Shenzhen", "country": "CN", "note": "중국 화남 전자제조 — 동남아 EMS 접점"},
    {"key": "technofrontier26", "platform": "jma",
     "api": "https://www.jma-exhibition.com/joint/webguide_en_tf/list.php",
     "page": "https://tf.jma.or.jp/",
     "title": "TECHNO-FRONTIER 2026 (도쿄, 모터·전원)", "match": "TECHNO-FRONTIER", "when": "2026-07",
     "kind": "history", "cycle": 1, "city": "Tokyo", "country": "JP",
     "note": "모터·전원·계측 부품전 — 예전 도메인(techno-frontier.com)은 폐쇄됐다"},
    {"key": "semicon_jp25", "platform": "a2z",
     "api": "https://expo.semi.org/japan2025/Public/Exhibitors.aspx",
     "page": "https://www.semiconjapan.org", "title": "SEMICON Japan 2025 (도쿄)",
     "match": "SEMICON JAPAN", "when": "2025-12", "kind": "history", "cycle": 1,
     "city": "Tokyo", "country": "JP", "note": "2026 회차 명단은 아직 미공개 — 직전 회차"},
    {"key": "touchtaiwan26", "platform": "chanchao",
     "api": "https://www.touchtaiwan.com/en/visitorExhibitor.asp",
     "page": "https://www.touchtaiwan.com/en/",
     "title": "Touch Taiwan 2026 (디스플레이·FPC)", "match": "TOUCH TAIWAN", "when": "2026-04",
     "kind": "history", "cycle": 1, "city": "Taipei", "country": "TW",
     "note": "디스플레이·FPC — K-Display의 대만판"},
    {"key": "medica26", "platform": "messedus",
     "api": "https://finder.messe-duesseldorf.de/vis-api/vis/v1/en/directory/",
     "vis_domain": "www.compamed-tradefair.com",
     "page": "https://www.compamed-tradefair.com/vis/v1/en/directory/exhibitors",
     "title": "MEDICA + COMPAMED 2026 (뒤셀도르프 의료)", "match": "COMPAMED", "when": "2026-11",
     "kind": "confirmed", "cycle": 1, "city": "Düsseldorf", "country": "DE",
     "note": "COMPAMED은 의료기기 부품전 — 고신뢰 커넥터 업체가 가장 많이 모이는 곳 중 하나(홀·부스 포함)"},
    {"key": "wire26", "platform": "messedus",
     "api": "https://finder.messe-duesseldorf.de/vis-api/vis/v1/en/directory/",
     "vis_domain": "www.wire-tradefair.com",
     "page": "https://www.wire-tradefair.com/vis/v1/en/directory/exhibitors",
     "title": "wire 뒤셀도르프 2026 (와이어·케이블)", "match": "WIRE DUSSELDORF", "when": "2026-04",
     "kind": "confirmed", "cycle": 2, "city": "Düsseldorf", "country": "DE",
     "note": "세계 최대 와이어·케이블 전시회(격년) — 우리 업의 상류 공정"},
    {"key": "tbse26", "platform": "mys", "host": "tbse26.mapyourshow.com",
     "title": "The Battery Show Europe 2026 (슈투트가르트)", "match": "BATTERY SHOW EUROPE",
     "when": "2026-06", "kind": "history", "cycle": 1, "city": "Stuttgart", "country": "DE",
     "note": "유럽 배터리·EV — TE·Amphenol·JAE·야마이치 출품"},
    {"key": "tbsm26", "platform": "mys", "host": "tbsm26.mapyourshow.com",
     "title": "The Battery Show North America 2026 (디트로이트)", "match": "BATTERY SHOW",
     "when": "2026-10", "kind": "history", "cycle": 1, "city": "Detroit", "country": "US",
     "note": "북미 배터리·EV — 커넥터 업체가 유럽판보다 훨씬 많다"},
    {"key": "automechanika26", "platform": "mfesb",
     "api": "https://api.messefrankfurt.com/service/esb_api/exhibitor-service/api/2.1/public/exhibitor/search",
     "api_key": "LXnMWcYQhipLAS7rImEzmZ3CkrU033FMha9cwVSngG4vbufTsAOCQQ==", "event": "AUTOMECHANIKA",
     "page": "https://automechanika.messefrankfurt.com",
     "title": "Automechanika Frankfurt 2026", "match": "AUTOMECHANIKA", "when": "2026-09",
     "kind": "history", "cycle": 2, "city": "Frankfurt", "country": "DE",
     "note": "자동차 애프터마켓(격년) — 출품사 4,146곳이지만 커넥터 업체는 사실상 없다"},
    {"key": "iaa25", "platform": "xlsx",
     "url": "https://exhibitors.iaa-mobility.com/download/informationsmaterial/"
            "xls_IAA_Export_2025_en/iaa_export_2025_en.xlsx",
     "page": "https://exhibitors.iaa-mobility.com/exhibitordirectory/2025/start/",
     "title": "IAA Mobility 2025 (뮌헨)", "match": "IAA MOBILITY", "when": "2025-09", "kind": "history",
     "cycle": 2, "city": "Munich", "country": "DE",
     "note": "격년(다음 2027-09) — 완성차·모빌리티 서비스 위주로 바뀌어 부품사 비중이 낮다"},
    # ── 한국 (배터리·전력·모빌리티·수소·드론)
    {"key": "interbattery26", "platform": "coexems",
     "api": "https://site-api.ems.coex.co.kr/public/company-directories",
     "coex_host": "www.interbattery.or.kr", "campaign": 2620,
     "page": "https://www.interbattery.or.kr",
     "title": "InterBattery 2026 (서울 배터리)", "match": "INTERBATTERY", "when": "2026-03",
     "kind": "history", "cycle": 1, "city": "서울 코엑스", "country": "KR",
     "note": "국내 최대 배터리전 — 부스·홈페이지·품목 포함 (2027 회차는 아직 미공개)"},
    {"key": "evtrend26", "platform": "coexems",
     "api": "https://site-api.ems.coex.co.kr/public/company-directories",
     "coex_host": "www.evtrendkorea.co.kr", "campaign": 2639,
     "page": "https://www.evtrendkorea.co.kr",
     "title": "EV 트렌드 코리아 2026", "match": "EV TREND", "when": "2026-03", "kind": "history",
     "cycle": 1, "city": "서울 코엑스", "country": "KR", "note": "EV 충전·인프라 — 규모가 작다(68곳)"},
    {"key": "elecs26", "platform": "elecs", "year": 2026,
     "page": "https://elecskorea.org/fairContents.do?FAIRMENU_IDX=6971&hl=KOR",
     "title": "일렉스 2026 (옛 SIEF 전기전력전)", "match": "일렉스", "when": "2026-10", "kind": "history",
     "cycle": 1, "city": "서울 코엑스", "country": "KR",
     "note": "전기·전력 기자재 — 옛 sief.co.kr은 죽고 elecskorea.org로 옮겼다(부스·품목 포함)"},
    {"key": "h2meet26", "platform": "h2meet",
     "api": "https://www.h2meet.com/common/inc/company_info.php",
     "page": "https://www.h2meet.com/html/ko/booth_list.php", "lo": 1, "hi": 200,
     "title": "H2 MEET 2026 (수소산업전)", "match": "H2 MEET", "when": "2026-09", "kind": "history",
     "cycle": 1, "city": "고양 킨텍스", "country": "KR",
     "note": "수소 — 목록 화면은 비어 있지만 업체별 상세가 살아 있어 번호로 훑는다"},
    {"key": "droneshow26", "platform": "gnuboard",
     "api": "https://www.droneshowkorea.com/board/bbs/board.php?bo_table=total_company",
     "page": "https://www.droneshowkorea.com/board/bbs/board.php?bo_table=total_company",
     "title": "드론쇼코리아 2026 (부산)", "match": "드론쇼코리아", "when": "2026-02", "kind": "history",
     "cycle": 1, "city": "부산 벡스코", "country": "KR", "note": "국내 최대 드론전 — 회사명만(부스는 상세에 있음)"},
    {"key": "seoulmobility25", "platform": "kamaxlsx",
     "url": "https://mobilityshow.or.kr/download/2025/SMS_2025_Exhibitors_List.xlsx",
     "page": "https://mobilityshow.or.kr/ko/exhibitors_list",
     "title": "서울모빌리티쇼 2025", "match": "서울모빌리티쇼", "when": "2025-04", "kind": "history",
     "cycle": 2, "city": "고양 킨텍스", "country": "KR",
     "note": "격년(다음 2027-04) — 다음 회차 목록은 준비 중이라 지난 회차 엑셀을 쓴다"},
    # ── 방산·항공 (커넥터 수요처인데 그동안 우리 자료에 아예 없던 분야)
    {"key": "eurosatory26", "platform": "finderr",
     "api": "https://eurosatory.finderr.cloud/api/catalog/search_exhibitors",
     "api_key": "9532b2dbcb94ddfb48bf4f6b240b856575f6ad5a3f0a70a618608e4cbe23c15e",
     "origin": "https://eurosatory.finderr.cloud",
     "page": "https://eurosatory.finderr.cloud/standalone/catalog/company-list?lang=en",
     "title": "Eurosatory 2026 (파리 방산전)", "match": "EUROSATORY", "when": "2026-06", "kind": "history",
     "cycle": 2, "city": "Paris", "country": "FR",
     "note": "세계 최대 지상방산전(격년, 다음 2028) — 부스·홈페이지·국가·소개 포함"},
    {"key": "dsei25", "platform": "aspevents",
     "page": "https://www.dsei.co.uk/visit/exhibiting-companies",
     "title": "DSEI London 2025 (영국 방산전)", "match": "DSEI", "when": "2025-09", "kind": "history",
     "cycle": 2, "city": "London", "country": "GB",
     "note": "유럽 최대 종합 방산전(격년, 다음 2027) — 부스 포함"},
    {"key": "siae25", "platform": "hubj2c",
     "api": "https://new-liste-exposants.hubj2c.com/siae2025/main/en/getSettings",
     "page": "https://new-liste-exposants.hubj2c.com/siae2025/main/en",
     "title": "Paris Air Show 2025 (파리 에어쇼)", "match": "PARIS AIR SHOW", "when": "2025-06", "kind": "history",
     "cycle": 2, "city": "Paris", "country": "FR",
     "note": "세계 최대 항공전(격년, 다음 2027) — 커넥터 업체는 Hall 2b에 몰려 있다"},
    {"key": "ausa26", "platform": "eshow",
     "api": "https://meetings.ausa.org/annual/2026/exhibitor_exhibitor_list.cfm",
     "page": "https://meetings.ausa.org/annual/2026/exhibitor_exhibitor_list.cfm",
     "title": "AUSA Annual Meeting 2026 (미 육군협회)", "match": "AUSA", "when": "2026-10", "kind": "confirmed",
     "cycle": 1, "city": "Washington DC", "country": "US",
     "note": "미 육군 최대 조달 전시회 — 다가오는 회차 확정 명단(부스 포함)"},
    {"key": "xponential26", "platform": "eshow",
     "api": "https://xponential.org/2026/exhibitor_list.cfm",
     "page": "https://xponential.org/2026/exhibitor_list.cfm",
     "title": "AUVSI XPONENTIAL 2026 (무인기·자율시스템)", "match": "XPONENTIAL", "when": "2026-05",
     "kind": "history", "cycle": 1, "city": "Houston", "country": "US",
     "note": "무인기·드론 최대 전시회 — 소형 커넥터(I-PEX·Harwin) 접점"},
    {"key": "farnborough26", "platform": "farnborough",
     "page": "https://www.farnboroughairshow.com/the-show/exhibitor-listing/",
     "title": "Farnborough Airshow 2026 (영국 에어쇼)", "match": "FARNBOROUGH", "when": "2026-07",
     "kind": "history", "cycle": 2, "city": "Farnborough", "country": "GB",
     "note": "격년(다음 2028) — 소개글·홈페이지 포함, 인터커넥트는 얇은 편"},
    # ── 산업 자동화
    {"key": "hannover26", "platform": "hmcsv",
     "api": "https://www.hannovermesse.de/en/application/exhibitor-index/csvExport?rt=ex&sort=AZ",
     "page": "https://www.hannovermesse.de/en/exhibitors-products/",
     "title": "Hannover Messe 2026 (하노버 산업전)", "match": "HANNOVER MESSE", "when": "2026-04",
     "kind": "history", "cycle": 1, "city": "Hannover", "country": "DE",
     "note": "세계 최대 산업전 — 주최측이 CSV 내려받기를 열어 둠(회차 종료로 부스 칸은 빔)"},
    {"key": "sps26", "platform": "mfesb",
     "api": "https://api.messefrankfurt.com/service/esb_api/exhibitor-service/api/2.1/public/exhibitor/search",
     "api_key": "LXnMWcYQhipLAS7rImEzmZ3CkrU033FMha9cwVSngG4vbufTsAOCQQ==", "event": "SPS",
     "page": "https://sps.mesago.com/nuernberg/en/exhibitor-search.html",
     "title": "SPS 2026 뉘른베르크 (산업 자동화)", "match": "SPS", "when": "2026-11", "kind": "confirmed",
     "cycle": 1, "city": "Nuremberg", "country": "DE",
     "note": "유럽 최대 FA 전시회 — 다가오는 회차 확정 명단(홀·부스·국가)"},
    {"key": "autoworld26", "platform": "coexems",
     "api": "https://site-api.ems.coex.co.kr/public/company-directories",
     "coex_host": "www.automationworld.co.kr", "campaign": 2635,
     "page": "https://www.automationworld.co.kr",
     "title": "오토메이션월드 2026 (스마트공장·자동화산업전)", "match": "AUTOMATION WORLD", "when": "2026-03",
     "kind": "history", "cycle": 1, "city": "서울 코엑스", "country": "KR",
     "note": "국내 최대 FA 전시회 — 부스·홈페이지·품목 포함 (2027 회차는 아직 미공개)"},
    # ── 로봇·자동화 (robots.py가 모아 둔 명단을 그대로 검사 — 새로 긁지 않는다)
    {"key": "rb_irex25", "platform": "robots", "robot_key": "irex25",
     "page": "https://irex.nikkan.co.jp/exhibitor/",
     "title": "iREX 2025 国際ロボット展", "match": "국제로봇전", "when": "2025-12",
     "kind": "history", "cycle": 2, "city": "Tokyo", "country": "JP",
     "note": "로봇 전시회 — 세계 최대 로봇 전문 전시회 (격년, 다음 2027-11). 소개글·전시 분야 태그 포함"},
    {"key": "rb_automatica25", "platform": "robots", "robot_key": "automatica25",
     "page": "https://exhibitors.automatica-munich.com/en/exhibitors-details/exhibitors-brands",
     "title": "automatica 2025", "match": "AUTOMATICA", "when": "2025-06",
     "kind": "history", "cycle": 2, "city": "Munich", "country": "DE",
     "note": "로봇 전시회 — 유럽 최대 로봇·자동화 (격년, 다음 2027-06). 홈페이지·제품군·회사소개(독일어 多"},
    {"key": "rb_promat27", "platform": "robots", "robot_key": "promat27",
     "page": "https://pm2027.mapyourshow.com/8_0/explore/exhibitor-gallery.cfm",
     "title": "ProMat 2027", "match": "ProMat", "when": "2027-03",
     "kind": "confirmed", "cycle": 2, "city": "Chicago", "country": "US",
     "note": "로봇 전시회 — 북미 최대 물류 자동화 — 로봇·AMR·피킹 관련 업체만 추림"},
    {"key": "rb_promat25", "platform": "robots", "robot_key": "promat25",
     "page": "https://pm2025.mapyourshow.com/8_0/explore/exhibitor-gallery.cfm",
     "title": "ProMat 2025", "match": "ProMat", "when": "2025-03",
     "kind": "history", "cycle": 2, "city": "Chicago", "country": "US",
     "note": "로봇 전시회 — 직전 회차 — 로봇 관련 업체만 추림"},
    {"key": "rb_robotworld26", "platform": "robots", "robot_key": "robotworld26",
     "page": "https://www.robotworld.or.kr/visitors/list_of_exhibitors.php",
     "title": "로보월드 2026", "match": "로보월드", "when": "2026-11",
     "kind": "confirmed", "cycle": 1, "city": "고양(킨텍스)", "country": "KR",
     "note": "로봇 전시회 — 국내 최대 로봇 전문전 — 부스·전시분야·홈페이지·회사소개 포함"},
    {"key": "rb_nextai26", "platform": "robots", "robot_key": "nextai26",
     "page": "https://nextaikorea.com/visitors/companies",
     "title": "THE NEXT AI 피지컬AI·스마트팩토리산업전 2026", "match": "THE NEXT AI", "when": "2026-10",
     "kind": "confirmed", "cycle": 1, "city": "창원", "country": "KR",
     "note": "로봇 전시회 — 신설 전시회 — 소개·출품내역·홈페이지 포함, 부스 미공개"},
    {"key": "rb_robottech26", "platform": "robots", "robot_key": "robottech26",
     "page": "https://smarttechkorea.com/exhibitor-directory",
     "title": "Robot Tech Show 2026 (스마트테크코리아)", "match": "ROBOT TECH SHOW", "when": "2026-06",
     "kind": "history", "cycle": 1, "city": "서울(코엑스)", "country": "KR",
     "note": "로봇 전시회 — 직전 회차 — 회사명·부스만 (다음 2027-06)"},
    {"key": "rb_robex25", "platform": "robots", "robot_key": "robex25",
     "page": "https://fixkorea.or.kr/participation/bis_info_list.asp?site=robex&yy=2025&lang=kor",
     "title": "ROBEX 대구국제로봇산업전 2025", "match": "ROBEX", "when": "2025-10",
     "kind": "history", "cycle": 1, "city": "대구(엑스코)", "country": "KR",
     "note": "로봇 전시회 — 직전 회차 — FIX 디렉토리 등록 업체만(실제 출품사의 일부), 전시품목·홈페이지 포함"},
    {"key": "rb_wrc26", "platform": "robots", "robot_key": "wrc26",
     "page": "https://www.worldrobotconference.com/expo/",
     "title": "WRC 세계로봇대회 2026 (베이징)", "match": "베이징 로봇", "when": "2026-08",
     "kind": "history", "cycle": 1, "city": "Beijing", "country": "CN",
     "note": "로봇 전시회 — 직전 회차 — 관별 명단·부스·회사소개(중국어) 포함 (다음 2027-08)"},
    {"key": "rb_fairplus26", "platform": "robots", "robot_key": "fairplus26",
     "page": "https://fairplus.cn/exhibitor-list/",
     "title": "FAIR plus 선전 로봇산업체인전 2026", "match": "선전 로봇", "when": "2026-04",
     "kind": "history", "cycle": 1, "city": "Shenzhen", "country": "CN",
     "note": "로봇 전시회 — 직전 회차 — 회사소개(중국어) 포함, 부스 미공개 (다음 2027-04)"},
    {"key": "rb_hrte26", "platform": "robots", "robot_key": "hrte26",
     "page": "https://www.arte.net.cn/about_36/",
     "title": "HRTE 항저우 휴머노이드로봇기술전 2026", "match": "휴머노이드로봇", "when": "2026-05",
     "kind": "history", "cycle": 1, "city": "Hangzhou", "country": "CN",
     "note": "로봇 전시회 — 직전 회차 — 회사명(중·영)·부스만 (다음 2027-05)"},
    {"key": "rb_vimf_bn26", "platform": "robots", "robot_key": "vimf_bn26",
     "page": "https://vimf.vn/danh-sach-don-vi-tham-gia/",
     "title": "RAV Robotic & Automation Vietnam 2026 (VIMF 박닌)", "match": "RAV", "when": "2026-11",
     "kind": "confirmed", "cycle": 1, "city": "Bac Ninh", "country": "VN",
     "note": "로봇 전시회 — VIMF 산업전과 통합 명단 — 로봇·자동화 관련 업체만 추림, 소개·제품 포함"},
    {"key": "rb_roboticssummit23", "platform": "robots", "robot_key": "roboticssummit23",
     "page": "https://www.roboticssummit.com/exhibit-floor/",
     "title": "Robotics Summit & Expo 2023 (보스턴)", "match": "ROBOTICS SUMMIT", "when": "2023-05",
     "kind": "history", "cycle": 1, "city": "Boston", "country": "US",
     "note": "로봇 전시회 — 2027 회차 명단이 아직 안 열려 지난 회차(ExpoFP 배치도)로 대체 — 홈페이지·국"},
    {"key": "rb_robobusiness23", "platform": "robots", "robot_key": "robobusiness23",
     "page": "https://www.robobusiness.com/exhibit-floor/",
     "title": "RoboBusiness 2023 (산타클라라)", "match": "ROBOBUSINESS", "when": "2023-10",
     "kind": "history", "cycle": 1, "city": "Santa Clara", "country": "US",
     "note": "로봇 전시회 — 2026 회차 배치도 미공개 — 지난 회차 명단(회사명·부스)"},
    {"key": "rb_r4m24", "platform": "robots", "robot_key": "r4m24",
     "page": "https://robot4manufacturing.com/en/exhibitors",
     "title": "ROBOT4MANUFACTURING 2024 (라로슈쉬르용)", "match": "ROBOT4MANUFACTURING", "when": "2024-11",
     "kind": "history", "cycle": 1, "city": "La Roche-sur-Yon", "country": "FR",
     "note": "로봇 전시회 — 2026 명단 미발표 — 주최측이 올린 2024 회차 PDF 명단에서 추출(국가·홈페이지·"},
    {"key": "rb_tairos26", "platform": "robots", "robot_key": "tairos26",
     "page": "https://tairos.chanchao.com.tw/VisitorExhibitor",
     "title": "TAIROS 2026 (타이베이) — 일부", "match": "TAIROS", "when": "2026-08",
     "kind": "history", "cycle": 1, "city": "Taipei", "country": "TW",
     "note": "로봇 전시회 — 주최측 사이트가 Cloudflare 봇 차단 — 인터넷 아카이브에 남은 목록 1쪽(전체 8"},
    {"key": "rb_robotics_si27", "platform": "robots", "robot_key": "robotics_si27",
     "page": "https://icm.si/events/mte-slovenia-exhibitors/",
     "title": "Robotics Slovenia 2027 (IFAM·INTRONIKA·ROBOTICS·MTE)", "match": "ROBOTICS SLOVENIA", "when": "2027-01",
     "kind": "confirmed", "cycle": 1, "city": "Ljubljana", "country": "SI",
     "note": "로봇 전시회 — 자동화·전자·로봇 합동전 — 홈페이지·제품군·국가 포함"},
    {"key": "rb_robotics_rs26", "platform": "robots", "robot_key": "robotics_rs26",
     "page": "https://icm.si/events/robotics-serbia-novi-sad/",
     "title": "Robotics Serbia 2026 (IFAM·INTRONIKA·ROBOTICS·MTE)", "match": "ROBOTICS SERBIA", "when": "2026-10",
     "kind": "confirmed", "cycle": 1, "city": "Novi Sad", "country": "RS",
     "note": "로봇 전시회 — 자동화·전자·로봇 합동전 — 홈페이지·제품군·국가 포함"},
    {"key": "rb_roboticswarsaw26", "platform": "robots", "robot_key": "roboticswarsaw26",
     "page": "https://roboticswarsaw.com/katalog-wystawcow-2026/",
     "title": "ROBOTICS Warsaw 2026", "match": "ROBOTICS Warsaw", "when": "2026-02",
     "kind": "history", "cycle": 1, "city": "Warsaw(Nadarzyn)", "country": "PL",
     "note": "로봇 전시회 — 직전 회차 — 회사명·부스만 (다음 2027-02)"},
    {"key": "rb_warsawautomatica26", "platform": "robots", "robot_key": "warsawautomatica26",
     "page": "https://automaticaexpo.com/katalog-wystawcow-2026/",
     "title": "Warsaw Industry Automatica 2026", "match": "WARSAW INDUSTRY AUTOMATICA", "when": "2026-05",
     "kind": "history", "cycle": 1, "city": "Warsaw(Nadarzyn)", "country": "PL",
     "note": "로봇 전시회 — 직전 회차 — 회사명·부스만 (다음 2027-05)"},
    {"key": "rb_stom_robotics26", "platform": "robots", "robot_key": "stom_robotics26",
     "page": "https://www.targikielce.pl/en/industrial-spring-2026/list-of-exhibitors?aliases=714",
     "title": "STOM-ROBOTICS 2026 (Kielce Industrial Spring)", "match": "STOM-ROBOTICS", "when": "2026-03",
     "kind": "history", "cycle": 1, "city": "Kielce", "country": "PL",
     "note": "로봇 전시회 — 직전 회차 — 회사명·국가·부스 (다음 2027-04)"},
    # ── 커넥터 전용 전시회 중 출품사 명단을 웹에 안 여는 곳 — 주최측이 글로 밝힌 기업만
    {"key": "ich_dg27", "platform": "manual",
     "page": "https://www.ich-expo.com/dongguan/?about_15/",
     "title": "ICH 동관 국제 커넥터·케이블 하네스전 2027", "match": "ICH", "when": "2027-03",
     "kind": "visitor", "city": "Dongguan", "country": "CN",
     "note": "주최측이 '지난 회차에 다녀간 세계적 기업'으로 공개한 목록 (출품사 명단은 위챗 미니프로그램으로만 제공)",
     "companies": ["安波福 Aptiv", "莱尼 LEONI", "住友 Sumitomo", "矢崎 Yazaki", "得润 Deren",
                   "富士康 Foxconn", "立讯 Luxshare", "比亚迪 BYD", "华为 Huawei", "美的 Midea",
                   "格力 Gree", "金亭 Jinting", "格兰仕 Galanz", "卡莱医疗 Carlisle Medical",
                   "海尔 Haier", "TCL", "松下 Panasonic"]},
    # ── 대만(TAITRA) — 대만 커넥터·케이블 업체 본진
    {"key": "computex26", "platform": "taitra",
     "url": "https://booth.e-taitra.com.tw/db/map/2026CP/Exhibitor_en-US.json",
     "page": "https://www.computextaipei.com.tw/en/exhibitor/index.html",
     "title": "COMPUTEX TAIPEI 2026", "match": "COMPUTEX", "when": "2026-05", "kind": "past",
     "cycle": 1, "city": "Taipei", "country": "TW", "note": "아시아 최대 ICT — 지난 회차 출품 이력"},
    {"key": "ampa26", "platform": "taitra",
     "url": "https://booth.e-taitra.com.tw/db/map/2026AP/Exhibitor_en-US.json",
     "page": "https://www.taipeiampa.com.tw/en_US/exhibitor/index.html",
     "title": "TAIPEI AMPA 2026 (대만 자동차부품전)", "match": "TAIPEI AMPA", "when": "2026-04",
     "kind": "past", "cycle": 1, "city": "Taipei", "country": "TW",
     "note": "대만 자동차부품·전장 — 지난 회차 출품 이력"},
    {"key": "computex25", "platform": "taitra",
     "url": "https://booth.e-taitra.com.tw/db/map/2025CP/Exhibitor_en-US.json",
     "page": "https://www.computextaipei.com.tw/en/exhibitor/index.html",
     "title": "COMPUTEX TAIPEI 2025", "match": "COMPUTEX", "when": "2025-05", "kind": "past",
     "cycle": 2, "city": "Taipei", "country": "TW", "note": "2025 회차 출품 이력"},
    {"key": "ampa25", "platform": "taitra",
     "url": "https://booth.e-taitra.com.tw/db/map/2025AP/Exhibitor_en-US.json",
     "page": "https://www.taipeiampa.com.tw/en_US/exhibitor/index.html",
     "title": "TAIPEI AMPA 2025", "match": "TAIPEI AMPA", "when": "2025-04", "kind": "past",
     "cycle": 2, "city": "Taipei", "country": "TW", "note": "2025 회차 출품 이력"},
    {"key": "jpca25", "platform": "tems",
     "url": "https://jpca2025.tems-system.com/eguide/jp/jpca/list",
     "title": "JPCA Show 2025", "match": "JPCA Show", "when": "2025-06", "kind": "past",
     "cycle": 2, "city": "Tokyo", "country": "JP", "note": "2025 회차 출품 이력"},
    # ── 홍콩(HKTDC) — 아시아 커넥터·부품 업체의 본진
    {"key": "hkef26", "platform": "hktdc",
     "url": "https://www.hktdc.com/event/hkelectronicsfairae/en/exhibitor-list",
     "title": "홍콩 전자전 (추계) 2026", "match": "Hong Kong Electronics Fair", "when": "2026-10",
     "kind": "confirmed", "city": "Hong Kong", "country": "HK",
     "note": "아시아 최대 전자 완제품·부품 전시회"},
    {"key": "hkef_se27", "platform": "hktdc",
     "url": "https://www.hktdc.com/event/hkelectronicsfairse/en/exhibitor-list",
     "title": "홍콩 전자전 (춘계) 2027", "match": "Hong Kong Electronics Fair", "when": "2027-04",
     "kind": "confirmed", "city": "Hong Kong", "country": "HK",
     "note": "춘계 — 소비자 전자 중심"},
    {"key": "hkecf26", "platform": "hktdc",
     "url": "https://www.hktdc.com/event/electronicasia/en/exhibitor-list",
     "title": "electronicAsia 2026 (홍콩 전자부품전)", "match": "electronicAsia", "when": "2026-10",
     "kind": "confirmed", "city": "Hong Kong", "country": "HK",
     "note": "electronicAsia — 전자부품 전문"},
    {"key": "ceatec26", "platform": "ceatec",
     "url": "https://www.ceatec.com/ja/exhibition/exhibitor-list.php?q=&gojuon=&catmode=or&sort=name&per=all&page=1",
     "title": "CEATEC 2026", "match": "CEATEC", "when": "2026-10", "kind": "confirmed",
     "city": "Chiba", "country": "JP", "note": "일본 최대 전자·IT 종합 전시회"},
    {"key": "kes26", "platform": "kes", "system_idx": 232,
     "page": "https://www.kes.org/fairOnline.do?selAction=single_page&SYSTEM_IDX=232&FAIRMENU_IDX=24379&hl=KOR",
     "title": "한국전자전 KES 2026", "match": "한국전자전", "when": "2026-10", "kind": "confirmed",
     "city": "서울 코엑스", "country": "KR", "note": "국내 최대 전자 전시회 (SYSTEM_IDX는 회차마다 바뀜)"},
    {"key": "jsae_yokohama26", "platform": "jsae",
     "url": "https://aee.expo-info.jsae.or.jp/ja/yokohama/exb_list/",
     "title": "人とくるまのテクノロジー展 2026 YOKOHAMA", "match": "人とくるまのテクノロジー展 YOKOHAMA",
     "when": "2026-05", "kind": "past", "cycle": 1, "city": "Yokohama", "country": "JP",
     "note": "일본 최대 자동차 기술 전시회(요코하마) — 직전 회차 출품 이력"},
    {"key": "jsae_nagoya26", "platform": "jsae",
     "url": "https://aee.expo-info.jsae.or.jp/ja/nagoya/exb_list/",
     "title": "人とくるまのテクノロジー展 2026 NAGOYA", "match": "人とくるまのテクノロジー展 NAGOYA",
     "when": "2026-07", "kind": "past", "cycle": 1, "city": "Nagoya", "country": "JP",
     "note": "일본 자동차 기술 전시회(나고야) — 직전 회차 출품 이력"},
]


# ---------------------------------------------------------------- 플랫폼별 수집
def fetch_mys(f):
    """MapYourShow — 갤러리 페이지로 쿠키를 받은 뒤 검색 API를 부른다(안 그러면 403)."""
    op = opener()
    base = f"https://{f['host']}/8_0"
    gallery = base + "/explore/exhibitor-gallery.cfm"
    try:
        get(op, gallery, timeout=40)
    except Exception:  # noqa: BLE001
        pass
    raw = get(op, base + "/ajax/remote-proxy.cfm?action=search&searchtype=exhibitorgallery&searchsize=6000",
              referer=gallery)
    d = json.loads(raw.decode("utf-8", "replace"))["DATA"]["results"]["exhibitor"]
    rows = []
    for h in d.get("hit", []):
        fl = h.get("fields", {})
        booth = [str(b).replace("randomstring", "").strip() for b in (fl.get("boothsdisplay_la") or [])]
        booth = [b for b in booth if b]
        rows.append((fl.get("exhname_t", ""), booth[0] if booth else "",
                     (fl.get("exhdesc_t") or "")[:600]))
    return rows, int(d.get("found") or len(rows)), gallery


CELL = re.compile(r'<c r="([A-Z]+)\d+"([^>]*)>(.*?)</c>', re.S)


def fetch_xlsx(f):
    """jl.medien 출품사 엑셀 — B열 회사명, D/E열 도시·국가, F열 홀/부스."""
    op = opener()
    raw = get(op, f["url"])
    if raw[:2] != b"PK":
        return [], 0, f["page"]
    zf = zipfile.ZipFile(io.BytesIO(raw))
    shared = [re.sub(r"<[^>]+>", "", x) for x in re.findall(
        r"<si>(.*?)</si>", zf.read("xl/sharedStrings.xml").decode("utf-8", "replace"), re.S)] \
        if "xl/sharedStrings.xml" in zf.namelist() else []
    sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8", "replace")
    rows, total = [], 0
    for row in re.findall(r"<row[^>]*>(.*?)</row>", sheet, re.S):
        cells = {}
        for col, attrs, body in CELL.findall(row):
            m = re.search(r"<v>(.*?)</v>", body, re.S)
            if m:
                v = m.group(1)
                cells[col] = shared[int(v)] if 't="s"' in attrs and v.isdigit() and int(v) < len(shared) else v
            else:
                m2 = re.search(r"<t[^>]*>(.*?)</t>", body, re.S)
                cells[col] = re.sub(r"<[^>]+>", "", m2.group(1)) if m2 else ""
        name = (cells.get("B") or "").strip()
        if not name or name.lower() in ("company",):
            continue
        total += 1
        rows.append((name, (cells.get("F") or "").strip(),
                     " ".join(x for x in ((cells.get("D") or ""), (cells.get("E") or "")) if x)))
    return rows, total, f["page"]


def fetch_jsae(f):
    """人とくるまのテクノロジー展 — data-exbname="일본어|영문|카나", 부스는 exb_no_*."""
    op = opener()
    html_text = get(op, f["url"]).decode("utf-8", "replace")
    rows = []
    for blk in re.findall(r'<div class="exb_wrap[^"]*"(.*?)(?=<div class="exb_wrap|</li>)', html_text, re.S):
        m = re.search(r'data-exbname="([^"]*)"', blk)
        if not m:
            continue
        parts = [p.strip() for p in m.group(1).split("|") if p.strip()]
        name = " / ".join(parts[:2])
        booth = re.search(r'class="exb_no[^"]*"[^>]*>\s*<span>([^<]*)</span>', blk)
        cat = re.search(r'data-cat="([^"]*)"', blk)
        rows.append((name, booth.group(1).strip() if booth else "", cat.group(1) if cat else ""))
    return rows, len(rows), f["url"]


def fetch_ceatec(f):
    """CEATEC — `exhibitor-list.php?...&per=all` 한 방에 전체 카드가 서버 렌더링으로 온다."""
    op = opener()
    html_text = get(op, f["url"], timeout=90).decode("utf-8", "replace")
    rows = []
    for card in re.findall(r'<div class="exl-card__nameline">(.*?)(?=<div class="exl-card__nameline">|</main>)',
                           html_text, re.S):
        m = re.search(r'class="exl-card__name">(.*?)</h3>', card, re.S)
        if not m:
            continue
        name = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        booth = re.search(r'class="exl-card__booth">(.*?)</span>', card, re.S)
        desc = re.search(r'class="exl-card__highlight[^"]*">(.*?)</p>', card, re.S)
        rows.append((name, re.sub(r"<[^>]+>", "", booth.group(1)).strip() if booth else "",
                     re.sub(r"<[^>]+>", " ", desc.group(1))[:600] if desc else ""))
    return rows, len(rows), f["url"]


def fetch_kes(f):
    """한국전자전(KES) — 참가업체 디렉터리는 `POST /fairOnline.do`(JSON) 로 12건씩 온다.
    SYSTEM_IDX 는 회차마다 바뀐다(2026 = 232)."""
    op = opener()
    base = "https://www.kes.org/fairOnline.do"

    def page(n):
        body = json.dumps({"page": n, "SYSTEM_IDX": f["system_idx"],
                           "searchFullTextIndex": "N", "selOrder": "cfair_nm_special_first"}).encode()
        req = urllib.request.Request(base, data=body, headers={
            "User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest", "Referer": f["page"]})
        return json.loads(op.open(req, timeout=60).read().decode("utf-8", "replace"))

    first = page(1)
    total = int((first.get("pagesJson") or {}).get("totalRows") or 0)
    per = int((first.get("pagesJson") or {}).get("numOfRows") or 12) or 12
    pages = (total + per - 1) // per
    chunks = [first]
    if pages > 1:
        with ThreadPool(6) as pool:
            chunks += pool.map(page, range(2, pages + 1))
    rows = []
    for d in chunks:
        for c in d.get("prodList") or []:
            name = (c.get("company_nm_kor") or "").strip()
            en = (c.get("company_nm_eng") or "").strip()
            label = f"{name} / {en}".strip(" /")
            cats = " ".join(str(c.get(k) or "") for k in c if k.startswith(("main_cate", "sub_cate")))
            rows.append((label, str(c.get("booth_num") or c.get("cfair_booth") or "").strip()[:24],
                         (c.get("company_pr_kor") or "")[:400] + " " + cats))
    return rows, total or len(rows), f["page"]


def fetch_table(f):
    """단순 표(HTML) — 업체명·부스·품목이 <tr><td> 세 칸으로 오는 국내 전시회용(KOAA SHOW 등).
    한 쪽에 10건씩이고 `offset=` 으로 넘긴다."""
    op = opener()
    rows, seen = [], set()
    for off in range(0, f.get("max_rows", 600), f.get("step", 10)):
        url = f["url"] + ("&" if "?" in f["url"] else "?") + f"offset={off}"
        try:
            html_text = get(op, url, timeout=60).decode(f.get("enc", "utf-8"), "replace")
        except Exception:  # noqa: BLE001
            break
        bodies = re.findall(r"<tbody[^>]*>(.*?)</tbody>", html_text, re.S) or [html_text]
        got = 0
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", " ".join(bodies), re.S):
            tds = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", td)).strip()
                   for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(tds) < 2 or not tds[0] or tds[0] in seen:
                continue
            seen.add(tds[0])
            got += 1
            rows.append((tds[0][:90], tds[1][:24], (tds[2] if len(tds) > 2 else "")[:400]))
        if not got:
            break
        time.sleep(0.15)
    return rows, len(rows), f["url"]


def fetch_tems(f):
    """tems-system(일본 전시 플랫폼) 출전자 일람 — `<td class="name">` 안에 회사명, 마지막 칸이 小間번호.
    JPCA Show(WIRE Japan Show 동시 개최) 등이 이 플랫폼을 쓴다."""
    op = opener()
    html_text = get(op, f["url"], timeout=90).decode("utf-8", "replace")
    rows, seen = [], set()
    for tr in re.findall(r"<tr>(.*?)</tr>", html_text, re.S):
        m = re.search(r'<td class="name"[^>]*>(.*?)</td>', tr, re.S)
        if not m:
            continue
        name = clean(re.sub(r"<[^>]+>", " ", m.group(1)))
        if not name or name in seen:
            continue
        seen.add(name)
        tds = [clean(re.sub(r"<[^>]+>", " ", td)) for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        booth = tds[-1] if tds else ""
        rows.append((name[:90], booth[:24], " ".join(tds[:3])[:300]))
    return rows, len(rows), f["url"]


def fetch_hktdc(f):
    """HKTDC(홍콩무역발전국) 전시회 — Next.js 서버 렌더링이라 `__NEXT_DATA__` 안에 명단이 그대로 있다.
    한 쪽 10건, **`?pageNum=N`이 서버에서 먹는다**(`page=`·`size=`는 무시됨)."""
    def one_page(n):
        html_text = get(opener(), f["url"] + ("&" if "?" in f["url"] else "?") + f"pageNum={n}", timeout=60)
        m = re.search(rb'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_text, re.S)
        if not m:
            return None
        return json.loads(m.group(1).decode("utf-8", "replace"))["props"]["pageProps"]["exhibitorListData"]

    first = one_page(1)
    if not first:
        return [], 0, f["url"]
    total = int(first.get("totalSize") or 0)
    per = int(first.get("size") or 10) or 10
    pages = min((total + per - 1) // per, f.get("max_pages", 200))
    chunks = [first]
    if pages > 1:
        with ThreadPool(8) as pool:
            chunks += [c for c in pool.map(one_page, range(2, pages + 1)) if c]
    rows, seen = [], set()
    for d in chunks:
        for c in d.get("data") or []:
            name = clean(c.get("exhibitorName"))
            if not name or name in seen:
                continue
            seen.add(name)
            extra = " ".join(clean(str(x.get("productName", ""))) for x in (c.get("latestProducts") or [])[:5])
            rows.append((name[:90], clean(c.get("boothNumbers"))[:24],
                         (clean(c.get("countryDesc")) + " " + extra)[:400]))
    return rows, total or len(rows), f["url"]


def fetch_manual(f):
    """주최측이 웹에 **글로 공개한** 참가·참관 기업 명단. 출품사 명단을 안 여는 전시회용.
    (ICH 동관 커넥터전은 출품사 명단을 위챗 미니프로그램으로만 주고, 홈페이지에는
     '지난 회차에 다녀간 세계적 기업' 목록만 글로 올린다 → 그 목록을 그대로 옮겨 적는다.)"""
    return [(n, "", f.get("note", "")) for n in f["companies"]], len(f["companies"]), f["page"]


# ================================================================ 방산·항공 (커넥터 수요처인데 그동안 빈 분야였다)
def _json_post(url, body=b"", headers=None, timeout=180):
    req = urllib.request.Request(url, data=body,
                                 headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace"))


def fetch_finderr(f):
    """Eurosatory(파리 방산전) — 카탈로그 앱이 쓰는 검색 API. 한 번에 전부 준다(페이징 없음).
    X-API-KEY는 공개 JS 번들에 박힌 열람용 키라 주최측이 바꾸면 401이 난다 → 그때 번들에서 다시 뽑는다."""
    d = _json_post(f["api"], b"{}", {
        "Content-Type": "application/json", "X-API-KEY": f["api_key"],
        "Origin": f["origin"], "Referer": f["page"]})
    rows = []
    for r in d.get("ListDetailsExhibitors", []):
        name = clean(r.get("Exhi_CompanyName"))
        if not name:
            continue
        booth = ", ".join(x for x in (f"{(s_.get('Hall') or '').strip()} {(s_.get('Name') or '').strip()}".strip()
                                      for s_ in (r.get("Stands") or [])) if x)
        extra = " ".join([clean(r.get("OneLiner")), clean(r.get("ShortPresentation")),
                          clean(r.get("Exhi_Country_CodeISO2")), clean(r.get("Exhi_Website"))])
        rows.append((name[:90], booth[:24], extra[:600]))
    return rows, int(d.get("NbExhibitors") or len(rows)), f["page"]


def fetch_hubj2c(f):
    """파리 에어쇼(SIAE) — 출품사 목록 위젯이 쓰는 getSettings가 명단을 통째로 담아 온다."""
    d = _json_post(f["api"], b"", {"Referer": f["page"], "X-Requested-With": "XMLHttpRequest"})
    rows = []
    for r in d.get("list", []):
        name = clean(r.get("exposant"))
        if not name:
            continue
        extra = " ".join([clean(r.get("TexteActivite")), clean(r.get("Texte")),
                          clean(r.get("nomPays")), clean(r.get("SecteursActivite"))])
        rows.append((name[:90], clean(r.get("stands"))[:24], extra[:600]))
    return rows, len(rows), f["page"]


def fetch_aspevents(f):
    """DSEI(런던 방산전) — Clarion ASP.events. 목록이 서버에서 그려져 ?page=N으로 넘기면 된다."""
    op = opener()
    rows, page = [], 1
    while page < 40:
        t = get(op, f"{f['page']}?page={page}", timeout=90).decode("utf-8", "replace")
        got = 0
        for m in re.finditer(r'(?s)<li class="m-exhibitors-list__items__item [^"]*js-library-item"[^>]*>(.*?)</li>', t):
            b = m.group(1)
            nm = re.search(r'(?s)__header__title__link[^>]*>(.*?)</a>', b)
            st = re.search(r'(?s)__meta__stand">(.*?)</div>', b)
            name = clean(TAG.sub(" ", nm.group(1))) if nm else ""
            if not name:
                continue
            got += 1
            booth = clean(TAG.sub(" ", st.group(1))).replace("Stand:", "").strip() if st else ""
            rows.append((name[:90], booth[:24], clean(TAG.sub(" ", b))[:600]))
        if not got:
            break
        page += 1
    return rows, len(rows), f["page"]


def fetch_eshow(f):
    """AUSA·XPONENTIAL(미국 방산·무인기) — eShow 표 한 장. 부스·회사명만 공개한다."""
    t = get(opener(), f["api"], timeout=90).decode("utf-8", "replace")
    rows = []
    for tr in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", t):
        if "ExhibitorPopup(" not in tr:
            continue
        tds = [clean(TAG.sub(" ", x)) for x in re.findall(r"(?s)<td[^>]*>(.*?)</td>", tr)]
        a = re.search(r'(?s)<a href="javascript:void\(0\)"[^>]*>(.*?)</a>', tr)
        name = clean(TAG.sub(" ", a.group(1))) if a else ""
        if not name:
            continue
        rows.append((name[:90], (tds[0] if tds else "")[:24], (tds[2] if len(tds) > 2 else "")[:600]))
    return rows, len(rows), f.get("page") or f["api"]


def fetch_farnborough(f):
    """판버러 에어쇼 — 20건씩 65쪽. 카드 안에 소개글·홈페이지까지 들어 있다."""
    op = opener()
    rows, seen, page = [], set(), 1
    while page < 90:
        u = f["page"] + (f"?page={page}" if page > 1 else "")
        t = get(op, u, timeout=90).decode("utf-8", "replace")
        got = 0
        for m in re.finditer(r'(?s)<div class="modal fade exhibitor-list-modal" id="model-Exhibitor(\d+)"(.*?)'
                             r'</div>\s*</div>\s*</div>', t):
            eid, b = m.group(1), m.group(2)
            if eid in seen:
                continue
            seen.add(eid)
            nm = re.search(r"(?s)<h5[^>]*>(.*?)</h5>", b)
            st = re.search(r'(?s)class="stand-number">(.*?)</span>', b)
            de = re.search(r'(?s)<p class="card-des[^"]*">(.*?)</p>', b)
            web = re.findall(r'<a href="([^"]+)"[^>]*title="Website"', b)
            name = clean(TAG.sub(" ", nm.group(1))) if nm else ""
            if not name:
                continue
            got += 1
            rows.append((name[:90], (clean(TAG.sub(" ", st.group(1))) if st else "")[:24],
                         (clean(TAG.sub(" ", de.group(1))) if de else "" + " " + (web[0] if web else ""))[:600]))
        if not got:
            break
        page += 1
    return rows, len(rows), f["page"]


# ================================================================ 산업 자동화
def fetch_hmcsv(f):
    """하노버 산업전 — 출품사 색인이 CSV 내려받기를 그대로 열어 둔다(세미콜론·latin-1).
    열: Hit type;Exhibitor;Country;Zip;City;State;CCI;Company website;Booth;Exhibitor presentation.
    회차가 끝나면 Booth 칸은 비어서 온다."""
    raw = get(opener(), f["api"], timeout=180).decode("latin-1", "replace")
    lines = raw.splitlines()
    head = None
    rows = []
    for ln in lines:
        cells = ln.split(";")
        if head is None:
            if "Exhibitor" in cells and "Country" in cells:
                head = {c.strip(): i for i, c in enumerate(cells)}
            continue
        if len(cells) < len(head):
            continue
        g = lambda k: clean(cells[head[k]]) if k in head and head[k] < len(cells) else ""  # noqa: E731
        name = g("Exhibitor")
        if not name:
            continue
        rows.append((name[:90], g("Booth")[:24],
                     " ".join([g("Country"), g("City"), g("Company website")])[:600]))
    return rows, len(rows), f["page"]


def fetch_mfesb(f):
    """SPS 뉘른베르크 — 메세프랑크푸르트 출품사 검색 API. **GET**이어야 하고(POST는 403),
    findEventVariable은 대문자(SPS). apikey는 공개 번들에서 가져온 열람용 키."""
    q = urllib.parse.urlencode({"language": "en-GB", "q": "", "orderBy": "name", "pageNumber": 1,
                                "pageSize": 2000, "orSearchFallback": "false",
                                "findEventVariable": f["event"]})
    req = urllib.request.Request(f["api"] + "?" + q,
                                 headers={"User-Agent": UA, "Accept": "application/json", "apikey": f["api_key"]})
    d = json.loads(urllib.request.urlopen(req, timeout=180).read().decode("utf-8", "replace"))
    res = d.get("result") or {}
    rows = []
    for h in res.get("hits", []):
        e = h.get("exhibitor") or {}
        name = clean(e.get("name"))
        if not name:
            continue
        ex = e.get("exhibition") or {}
        halls = [clean(x.get("name")) for x in (ex.get("exhibitionHall") or [])]
        stands = [clean(x.get("name")) for x in (ex.get("stand") or [])]
        booth = " ".join([x for x in halls + stands if x])
        addr = (e.get("address") or {}).get("country") or {}
        rows.append((name[:90], booth[:24],
                     " ".join([clean(e.get("shortDescription")), clean(addr.get("label"))])[:600]))
    return rows, int(res.get("hitsTotal") or len(rows)), f["page"]


def fetch_coexems(f):
    """코엑스 전시회 공통 출품사 API(오토메이션월드 등) — 어느 전시회인지는 호스트 헤더로 가른다.
    coex-host를 안 보내면 0건이 온다. 회차는 archiveCampaignIdx로 고른다."""
    q = urllib.parse.urlencode({"archiveCampaignIdx": f["campaign"], "page": 1, "size": 1000, "language": "ko"})
    req = urllib.request.Request(f["api"] + "?" + q, headers={
        "User-Agent": UA, "Accept": "application/json", "coex-host": f["coex_host"]})
    d = json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace"))
    data = d.get("data") or {}
    rows = []
    for r in data.get("list", []):
        name = clean(r.get("companyNameEng")) or clean(r.get("companyName"))
        if not name:
            continue
        co = r.get("company") or {}
        rows.append((name[:90], clean(r.get("boothNumber"))[:24],
                     " ".join([clean(r.get("keywordEng")), clean(r.get("keyword")),
                               clean(co.get("website")), clean(co.get("country"))])[:600]))
    return rows, int(d.get("totalRows") or data.get("totalRows") or len(rows)), f["page"]


# ================================================================ IT·데이터센터·반도체
def fetch_ocp(f):
    """OCP 글로벌 서밋(데이터센터) — 출품사 명단이 따로 없고 후원 등급별 로고 벽이 곧 부스 명단이다.
    본 사이트는 봇을 막아 두어(Cloudflare 403) 같은 내용을 내주는 스테이징 호스트에서 읽는다.
    스테이징이라 인증서가 만료돼 있다(우리 opener는 검증을 끄고 쓴다)."""
    t = get(opener(), f["page"], timeout=90).decode("utf-8", "replace")
    tier, rows = "", []
    for m in re.finditer(r'(?s)<h[1-6][^>]*>(.*?)</h[1-6]>'
                         r'|<a[^>]+href="([^"]*)"[^>]*>\s*<img[^>]*alt="([^"]*) logo"', t):
        if m.group(1) is not None:
            x = clean(TAG.sub("", m.group(1)))
            if x:
                tier = x
            continue
        name = clean(_html.unescape(m.group(3)))
        if name:
            rows.append((name[:90], "", f"{tier} {m.group(2)}"[:600]))
    return rows, len(rows), f["page"]


def fetch_ungerboeck(f):
    """Momentus(Ungerboeck) 부스 배치도 API — SC(슈퍼컴퓨팅) 등이 쓴다.
    토큰이 필요 없고 ConfigID 하나로 명단을 통째로 준다."""
    import uuid
    hd = {"Accept": "application/json", "Content-Type": "application/json", "appcode": "VFP",
          "authorization": "Bearer", "clientappcategory": "30", "clientapptype": "2",
          "emailaddress": "", "servicerequeststart": "", "showactionid": "false",
          "ucn": "", "udf": "", "uldf": "", "utf": "", "utmf": "", "utsf": "",
          "version": "25.3.9508.32422", "workstationname": uuid.uuid4().hex,
          "wsid": uuid.uuid4().hex[:24], "x-nonce": str(uuid.uuid4()),
          "User-Agent": UA, "Origin": f["origin"]}
    req = urllib.request.Request(f["api"], data=json.dumps(["", 0, "", f["config"], "", 0]).encode(),
                                 headers=hd, method="POST")
    j = json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace"))
    if isinstance(j, list):
        j = j[0]
    if isinstance(j, str):
        j = json.loads(j)
    rows = []
    for e in (j.get("ReturnObj") or {}).get("ExhibitorList", []):
        name = clean(e.get("Name"))
        if not name:
            continue
        rows.append((name[:90], ", ".join(e.get("BoothNames") or [])[:24],
                     " ".join([clean(e.get("CatCountryDesc")), " ".join(e.get("ProductCodes") or [])])[:600]))
    return rows, len(rows), f["page"]


def fetch_algolia(f):
    """전시회 검색이 Algolia로 돌아가는 곳(NürnbergMesse·GSMA 계열).
    앱ID·키는 화면 코드에 박힌 열람용이라 주최측이 바꾸면 다시 뽑아야 한다.
    한 번에 1000건까지만 주므로 letters가 있으면 머리글자로 나눠 받는다."""
    url = f"https://{f['app']}-dsn.algolia.net/1/indexes/{f['index']}/query"
    hd = {"X-Algolia-Application-Id": f["app"], "X-Algolia-API-Key": f["api_key"],
          "Content-Type": "application/json", "User-Agent": UA}
    rows, seen, total = [], set(), 0
    for key in (f.get("letters") or [None]):
        body = {"query": "", "hitsPerPage": 1000, "attributesToHighlight": []}
        flt = [f["filter"]] if f.get("filter") else []
        if key is not None:
            flt.append(f'{f["letter_field"]}:"{key}"')
        if flt:
            body["filters"] = " AND ".join(flt)
        d = _json_post(url, json.dumps(body).encode(), hd, timeout=120)
        total += int(d.get("nbHits") or 0)
        for h in d.get("hits", []):
            name = clean(h.get(f["name_field"]))
            if not name or name in seen:
                continue
            seen.add(name)
            b = h.get("booth")
            if isinstance(b, list) and b and isinstance(b[0], dict):
                booth = ", ".join(clean(f"{x.get('boothHall','')} {x.get('boothNumber','')}") for x in b)
            else:
                st = h.get("stands") or h.get("booth") or ""
                booth = clean(", ".join(str(x) for x in st) if isinstance(st, list) else str(st))
            extra = " ".join(str(h.get(k) or "") for k in ("country", "city", "building"))
            rows.append((name[:90], booth[:24], clean(extra)[:600]))
    return rows, total or len(rows), f["page"]


def fetch_a2z(f):
    """a2zinc 출품사 표(SEMI 계열·Questex 등) — 한 쪽에 전부 나오는 정적 HTML."""
    t = get(opener(), f["api"], timeout=180).decode("utf-8", "replace")
    rows = []
    for tr in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", t):
        m = re.search(r'(?s)class="exhibitorName"[^>]*href="(eBooth\.aspx[^"]*)"[^>]*>(.*?)</a>', tr)
        if not m:
            continue
        name = clean(TAG.sub(" ", m.group(2)))
        if not name:
            continue
        booths = [clean(TAG.sub(" ", x)) for x in
                  re.findall(r'(?s)<td[^>]*class="[^"]*boothLabel[^"]*"[^>]*>(.*?)</td>', tr)]
        rows.append((name[:90], " ".join(x for x in booths if x)[:24], ""))
    return rows, len(rows), f.get("page") or f["api"]


def fetch_cioe(f):
    """CIOE(선전 광전자) — 목록이 ashx AJAX로 오고, 본문과 페이저가 구분자로 붙어 온다."""
    op = opener()
    rows, page, total = [], 1, 0
    while page < 40:
        body = urllib.parse.urlencode({"pageindex": page, "pagesize": 200, "zq": "", "zg": "",
                                       "zsqy": "", "zslx": "", "cxtj": "", "zpfw": ""}).encode()
        req = urllib.request.Request(f["api"], data=body, headers={
            "User-Agent": UA, "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Referer": f["page"]})
        t = op.open(req, timeout=180).read().decode("utf-8", "replace")
        part = t.split("!@#$%^&*")
        lst = part[0]
        if len(part) > 1 and not total:
            m = re.search(r"Total:(\d+)", part[1])
            total = int(m.group(1)) if m else 0
        got = 0
        for li in re.findall(r"(?s)<li>.*?</li>", lst):
            g = lambda p: (clean(TAG.sub(" ", re.search(p, li, re.S).group(1))) if re.search(p, li, re.S) else "")  # noqa: E731
            name = g(r'<h3 class="title">(.*?)</h3>')
            if not name:
                continue
            got += 1
            rows.append((name[:90], f"{g(r'Hall：</dt><dd>(.*?)</dd>')} {g(r'Booth No：</dt><dd>(.*?)</dd>')}".strip()[:24],
                         g(r"Main products：</dt><dd>(.*?)</dd>")[:600]))
        if not got or len(rows) >= (total or 10 ** 9):
            break
        page += 1
    return rows, total or len(rows), f["page"]


def fetch_wis(f):
    """월드IT쇼 — 목록이 16건씩 JSON으로 온다. 부스는 팝업에만 있어 여기선 안 가져온다."""
    op = opener()
    rows, page = [], 1
    while page < 80:
        u = f["api"] + "?" + urllib.parse.urlencode({"page": page, "order": "", "make": "com_name",
                                                     "search": "", "insert_year": f["year"]})
        req = urllib.request.Request(u, headers={"User-Agent": UA, "Referer": f["page"]})
        d = json.loads(op.open(req, timeout=60).read().decode("utf-8", "replace"))
        if not d:
            break
        for r in d:
            name = clean(r.get("com_name"))
            if name:
                rows.append((name[:90], "", " ".join([clean(r.get("company_content")),
                                                      clean(r.get("homepage"))])[:600]))
        page += 1
    return rows, len(rows), f["page"]


def fetch_ectc(f):
    """ECTC(패키징·인터커넥트 학회 전시) — 회사명만 <br>로 줄줄이 적힌 정적 페이지."""
    t = get(opener(), f["page"], timeout=90).decode("utf-8", "replace")
    seg = t[t.find("Exhibiting Companies"):][:60000]
    rows = []
    for para in re.findall(r'(?s)<p class="wp-block-paragraph">(.*?)</p>', seg):
        for x in re.split(r"<br\s*/?>", para):
            name = clean(_html.unescape(TAG.sub("", x)))
            if name and len(name) > 2:
                rows.append((name[:90], "", ""))
    return rows, len(rows), f["page"]


def fetch_cadmium(f):
    """Cadmium Conference Harvester 배치도(APEC 등) — 필수 인자를 다 채워야 목록이 온다."""
    body = urllib.parse.urlencode({
        "EventID": f["event_id"], "EventClientID": f["client_id"], "EventKey": f["event_key"],
        "ShowLogos": "Yes", "LogoLocation": "1", "ShowCompanyWithNegativeBalance": 1,
        "OpenBoothPopupLink": "ajaxcalls/OpenBoothPopup.asp?",
        "RentedBoothPopupLink": "ajaxcalls/ExhibitorInfoPopup.asp?",
        "BlockLogosBeforeLogoTaskCompletion": "true"}).encode()
    d = _json_post(f["api"], body, {
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": f["page"]}, timeout=90)
    rows = []
    for x in d.get("boothList") or []:
        name = clean(x.get("exhibitorName"))
        if name:
            rows.append((name[:90], clean(x.get("boothNumber"))[:24], ""))
    return rows, len(rows), f["page"]


def fetch_wpjson(f):
    """워드프레스 REST로 출품사를 내주는 곳(ECOC) — 100건씩 넘긴다."""
    op = opener()
    rows, page = [], 1
    while page < 30:
        try:
            raw = get(op, f["api"] + f"?per_page=100&page={page}&_fields=id,title,link", timeout=90)
        except Exception:  # noqa: BLE001
            break
        items = json.loads(raw.decode("utf-8", "replace"))
        if not isinstance(items, list) or not items:
            break
        for x in items:
            name = clean(_html.unescape(TAG.sub("", (x.get("title") or {}).get("rendered", ""))))
            if name:
                rows.append((name[:90], "", clean(x.get("link"))[:600]))
        if len(items) < 100:
            break
        page += 1
    return rows, len(rows), f["page"]


def fetch_rxalgolia(f):
    """RX 재팬·RX 글로벌 전시회(NEPCON Japan·Automotive World·NEPCON Asia 등).
    화면은 JS 컴포넌트지만 그 뒤의 Algolia 색인이 그대로 열려 있다. 한 회차 색인에
    같은 기간 같은 장소의 여러 전시회가 함께 들어 있어(ppsAnswers로 구분) 한 번에 받는다."""
    url = f"https://{f['app']}-dsn.algolia.net/1/indexes/{f['index']}/query"
    hd = {"X-Algolia-Application-Id": f["app"], "X-Algolia-API-Key": f["api_key"],
          "Content-Type": "application/json", "User-Agent": UA}
    rows, page, pages = [], 0, 1
    while page < pages and page < 20:
        params = urllib.parse.urlencode({
            "query": "", "hitsPerPage": 1000, "page": page,
            "filters": f"recordType:exhibitor AND eventEditionId:{f['edition']} AND locale:en-gb"})
        d = _json_post(url, json.dumps({"params": params}).encode(), hd, timeout=120)
        pages = int(d.get("nbPages") or 1)
        for h in d.get("hits", []):
            name = clean(h.get("companyName"))
            if not name:
                continue
            sub = h.get("ppsAnswers") or []
            sub = [clean(x) for x in sub if isinstance(x, str)]
            rows.append((name[:90], clean(h.get("standReference"))[:24],
                         " ".join([clean(h.get("countryName")), clean(h.get("website")),
                                   clean(h.get("exhibitorDescription")), " ".join(sub[:4])])[:600]))
        page += 1
    return rows, len(rows), f["page"]


def fetch_jma(f):
    """일본능률협회(JMA) 전시회 가이드 — 한 쪽에 40건씩 서버에서 그려 준다."""
    op = opener()
    rows, page = [], 1
    while page < 40:
        t = get(op, f"{f['api']}?page={page}&", timeout=90).decode("utf-8", "replace")
        got = 0
        for no, nm, body in re.findall(r'<h2><a href="company\.php\?no=(\d+)"[^>]*>([^<]+)</a>(.*?)</figure>',
                                       t, re.S):
            name = clean(_html.unescape(nm))
            if not name:
                continue
            got += 1
            b = re.search(r"Booth number\s*([^<]+)", body)
            rows.append((name[:90], clean(b.group(1))[:24] if b else "", clean(TAG.sub(" ", body))[:600]))
        if not got:
            break
        page += 1
    return rows, len(rows), f["page"]


def fetch_chanchao(f):
    """찬차오(대만) 전시회 — 목록 위에 '인기 출품사' 띠가 매 쪽 반복되므로
    부스 번호가 붙은 줄만 실제 명단으로 본다."""
    op = opener()
    rows, seen, page = [], set(), 1
    while page < 30:
        t = get(op, f"{f['api']}?page={page}&Area=&view=&sort=", timeout=90).decode("utf-8", "replace")
        got = 0
        for m in re.finditer(r'<h4>\s*<a href="visitorExhibitorDetail\.asp\?comNo=(\d+)[^"]*"[^>]*>(.*?)</a>'
                             r'(.*?)Booth No\s*[:：]\s*([^<]*)', t, re.S):
            cid, nm, mid, booth = m.groups()
            name = clean(TAG.sub(" ", _html.unescape(nm)))
            if not name or cid in seen:
                continue
            seen.add(cid)
            got += 1
            rows.append((name[:90], clean(booth)[:24], clean(TAG.sub(" ", mid))[:600]))
        if not got:
            break
        page += 1
    return rows, len(rows), f["page"]


def fetch_messedus(f):
    """메세 뒤셀도르프 공통 출품사 API — 어느 전시회인지는 X-Vis-Domain 헤더로 가른다.
    한 도메인이 같은 기간 함께 열리는 전시회를 다 담아 온다(MEDICA+COMPAMED처럼).
    머리글자 a~z를 다 돌아 합친다."""
    op = opener()
    rows, seen = [], set()
    for L in "abcdefghijklmnopqrstuvwxyz":
        req = urllib.request.Request(f["api"] + L, headers={
            "User-Agent": UA, "Accept": "application/json", "X-Vis-Domain": f["vis_domain"]})
        try:
            d = json.loads(op.open(req, timeout=120).read().decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            continue
        for e in d if isinstance(d, list) else []:
            eid = e.get("exh")
            if not eid or eid in seen:
                continue
            if f.get("only") and not str(eid).startswith(f["only"]):
                continue
            seen.add(eid)
            name = clean(e.get("name") or e.get("exhName"))
            if not name:
                continue
            tags = [t if isinstance(t, str) else str(t.get("name") or t.get("label") or "")
                    for t in (e.get("tags") or [])]
            rows.append((name[:90], clean(e.get("location"))[:24],
                         " ".join([clean(e.get("country")), clean(e.get("city")),
                                   " ".join(tags)])[:600]))
        time.sleep(0.1)
    return rows, len(rows), f["page"]


# ================================================================ 한국 전시회
def fetch_elecs(f):
    """일렉스(옛 SIEF 전기전력전) — 한 페이지에 2016~2026 회차가 연도별 패널로 다 들어 있다.
    '<연도> 참가업체 목록' 제목 다음 패널만 잘라 읽는다."""
    t = get(opener(), f["page"], timeout=120).decode("utf-8", "replace")
    m = re.search(rf'{f["year"]}\s*참가업체 목록(.*?)(?:참가업체 목록|</body>)', t, re.S)
    seg = m.group(1) if m else ""
    rows = []
    for tr in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", seg):
        tds = [clean(_html.unescape(TAG.sub(" ", x))) for x in re.findall(r"(?s)<td[^>]*>(.*?)</td>", tr)]
        if len(tds) < 3 or not tds[2]:
            continue
        rows.append((tds[2][:90], tds[0][:24], " ".join(tds[3:])[:600]))
    return rows, len(rows), f["page"]


def fetch_gnuboard(f):
    """그누보드 게시판을 출품사 목록으로 쓰는 전시회(드론쇼코리아 등, BEXCO 계열)."""
    op = opener()
    rows, seen, page = [], set(), 1
    while page < 60:
        t = get(op, f"{f['api']}&page={page}", timeout=90).decode("utf-8", "replace")
        got = 0
        for blk in t.split('<li class="element-item')[1:]:
            wid = re.search(r"wr_id=(\d+)", blk)
            nm = re.search(r'<p class="item_tlt">\s*(.*?)\s*</p>', blk, re.S)
            if not wid or not nm or wid.group(1) in seen:
                continue
            name = clean(_html.unescape(TAG.sub(" ", nm.group(1))))
            if not name:
                continue
            seen.add(wid.group(1))
            got += 1
            rows.append((name[:90], "", ""))
        if not got:
            break
        page += 1
    return rows, len(rows), f["page"]


def fetch_h2meet(f):
    """H2 MEET — 목록 화면은 새 회차 준비로 비어 있지만 업체별 상세는 그대로 응답한다.
    번호를 훑어 있는 것만 담는다(없는 번호는 건너뛴다)."""
    op = opener()
    rows = []

    def one(n):
        try:
            t = get(op, f"{f['api']}?no={n}", referer=f["page"], timeout=40).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return None
        nm = re.search(r'<p class="tt">(.*?)</p>', t, re.S)
        name = clean(_html.unescape(TAG.sub(" ", nm.group(1)))) if nm else ""
        if not name:
            return None
        b = re.search(r"Booth\s*No\.?\s*[:：]?\s*</[^>]+>\s*([^<]*)", t, re.S) or \
            re.search(r"부스\s*번호[^<]*</[^>]+>\s*([^<]*)", t, re.S)
        body = clean(TAG.sub(" ", t))
        return (name[:90], clean(b.group(1))[:24] if b else "", body[:600])
    with ThreadPool(6) as pool:
        for r in pool.map(one, range(f.get("lo", 1), f.get("hi", 200))):
            if r:
                rows.append(r)
    return rows, len(rows), f["page"]


def fetch_kamaxlsx(f):
    """서울모빌리티쇼(KAMA) — 다음 회차 목록은 'Coming Soon'이지만 지난 회차 엑셀이 그대로 열려 있다.
    열: No | 부스 | 국문사명 | 영문사명 | 국가 | 분야 | 품목군 …"""
    raw = get(opener(), f["url"], timeout=120)
    if raw[:2] != b"PK":
        raise RuntimeError("엑셀이 아님")
    zf = zipfile.ZipFile(io.BytesIO(raw))
    shared = [re.sub(r"<[^>]+>", "", x) for x in re.findall(
        r"<si>(.*?)</si>", zf.read("xl/sharedStrings.xml").decode("utf-8", "replace"), re.S)]
    sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8", "replace")
    rows = []
    for row in re.findall(r"<row[^>]*>(.*?)</row>", sheet, re.S):
        cells = {}
        for col, attrs, body in CELL.findall(row):
            v = re.search(r"<v>(.*?)</v>", body or "", re.S)
            if v:
                v = v.group(1)
                cells[col] = shared[int(v)] if 't="s"' in attrs and v.isdigit() and int(v) < len(shared) else v
        name = clean(_html.unescape(cells.get("D") or cells.get("C") or ""))
        booth = clean(cells.get("B"))
        # 제목·머리글 줄 걸러내기 (엑셀 위쪽에 안내 줄이 몇 개 있다)
        if not name or name.isdigit() or len(name) < 3 or name.lower().startswith("company") \
                or name.lower() in ("eng.", "kor.", "name") or "booth" in booth.lower():
            continue
        rows.append((name[:90], booth[:24],
                     " ".join(clean(_html.unescape(cells.get(c) or "")) for c in "EFGH")[:600]))
    return rows, len(rows), f["page"]


def fetch_robots(f):
    """robots.py가 모아 둔 로봇 전시회 출품사 명단(data/robots.json)을 그대로 읽는다.
    로봇·자동화는 커넥터 수요처인데 여기선 따로 긁지 않고 이미 받아 둔 것을 재사용한다
    (run_daily.sh에서 robots.py를 먼저 돌린다)."""
    path = os.path.join(HERE, "data", "robots.json")
    d = json.load(open(path, encoding="utf-8"))
    key = f["robot_key"]
    rows = []
    for c in d.get("companies", []):
        ent = [x for x in c.get("f", []) if x.get("k") == key]
        if not ent:
            continue
        extra = " ".join([c.get("what", ""), " ".join(c.get("tags", [])), c.get("desc", "")])[:600]
        for nm in [c.get("n", ""), c.get("ja", "")]:
            if nm:
                rows.append((nm, ent[0].get("b", ""), extra))
                break
    src = next((x.get("url", "") for x in d.get("fairs", []) if x.get("key") == key), f.get("page", ""))
    return rows, len(rows), src or f.get("page", "")


def fetch_taitra(f):
    """대만무역센터(TAITRA) 전시회 — 전시회 홈페이지 명단은 검색 버튼을 눌러야 나오지만,
    **부스 배치도가 쓰는 정적 JSON**에 전체 출품사가 그대로 있다.
    `booth.e-taitra.com.tw/db/map/<회차코드>/Exhibitor_en-US.json` (2026CP=COMPUTEX, 2026AP=TAIPEI AMPA)."""
    raw = get(opener(), f["url"], timeout=60)
    d = json.loads(raw.decode("utf-8", "replace")).get("exhibitors") or []
    rows = []
    for x in d:
        name = clean(x.get("name"))
        if not name:
            continue
        rows.append((name[:90], clean(x.get("booth_no"))[:24],
                     (clean(x.get("product")) + " " + clean(x.get("brand")))[:400]))
    return rows, len(rows), f.get("page") or f["url"]


FETCH = {"mys": fetch_mys, "xlsx": fetch_xlsx, "jsae": fetch_jsae, "ceatec": fetch_ceatec,
         "robots": fetch_robots, "finderr": fetch_finderr, "hubj2c": fetch_hubj2c,
         "aspevents": fetch_aspevents, "eshow": fetch_eshow, "farnborough": fetch_farnborough,
         "hmcsv": fetch_hmcsv, "mfesb": fetch_mfesb, "coexems": fetch_coexems,
         "ocp": fetch_ocp, "ungerboeck": fetch_ungerboeck, "algolia": fetch_algolia,
         "a2z": fetch_a2z, "cioe": fetch_cioe, "wis": fetch_wis, "ectc": fetch_ectc,
         "cadmium": fetch_cadmium, "wpjson": fetch_wpjson, "rxalgolia": fetch_rxalgolia,
         "jma": fetch_jma, "chanchao": fetch_chanchao, "messedus": fetch_messedus,
         "elecs": fetch_elecs, "gnuboard": fetch_gnuboard, "h2meet": fetch_h2meet,
         "kamaxlsx": fetch_kamaxlsx,
         "kes": fetch_kes, "table": fetch_table, "tems": fetch_tems, "hktdc": fetch_hktdc,
         "taitra": fetch_taitra, "manual": fetch_manual}


# ================================================================ 커넥터 관련 업체 판별 (새 경쟁사 발굴용)
# 이름이나 소개글에 아래가 있으면 '커넥터 계열' 업체로 본다 → 우리가 모르던 경쟁사를 찾아내는 씨앗
CONN_NAME = re.compile(r"connector|interconnect|커넥터|コネクタ|连接器|連接器|terminal|단자|"
                       r"cable assembl|wire harness|harness|와이어|하네스", re.I)
CONN_DESC = re.compile(r"\bconnectors?\b|interconnect|cable assembl(y|ies)|wire harness|"
                       r"terminal blocks?|contacts?\s+(and|&)\s+connect|board[- ]to[- ]board|"
                       r"backplane|high[- ]speed connect|コネクタ|连接器", re.I)


# 소개글에 'connector'가 나와도 경쟁사가 아닌 곳들 — 유통상·계측기·반도체·EDA·조립설비
NOT_RIVAL = re.compile(
    r"mouser|digi-?key|arrow electronics|avnet|\brs components\b|farnell|element14|\btti\b|heilind|"
    r"future electronics|\bwpg\b|rutronik|distribut|keysight|tektronix|rohde|anritsu|teledyne|"
    r"national instrument|fluke|yokogawa|oscillosc|marvell|realtek|infineon|texas instrument|"
    r"\bnxp\b|renesas|stmicro|broadcom|qualcomm|mediatek|cadence|ansys|synopsys|keysight|"
    r"altium|siemens|zuken|software|simulation|univers|research institute|magazine|press|"
    r"\bems\b|assembly (machine|equipment)|solder|dispenser|reflow|smt (machine|equipment)|"
    r"test (house|lab)|laborator|certificat", re.I)


def conn_score(name, extra):
    """0~3 — 이름에 커넥터·단자·하네스가 박힌 곳이 3점(가장 확실),
    소개글에만 나오면 1점(유통상·계측기 업체가 자주 걸려 약하게 준다)."""
    if NOT_RIVAL.search(name or ""):
        return 0
    s = 3 if CONN_NAME.search(name or "") else 0
    if not s and CONN_DESC.search(extra or "") and not NOT_RIVAL.search(extra or ""):
        s = 1
    return s


# ================================================================ 실행
def one(f):
    t0 = time.time()
    err, stale = None, ""
    try:
        rows, total, src = FETCH[f["platform"]](f)
    except Exception as e:  # noqa: BLE001 - 한 전시회가 막혀도 나머지는 살린다
        rows, total, src, err = [], 0, f.get("page") or f.get("url", ""), f"{type(e).__name__}: {e}"
    cached = cache_rows(f["key"])
    if cached and len(rows) < max(1, cached["n"] * 0.5):
        rows = [tuple(r) for r in cached["rows"]]
        total = max(total, cached["n"])
        stale = f"지난 수집분({cached['when']}) 사용 — 이번엔 " + (err or f"{len(rows)}건만 응답")
    elif rows:
        cache_rows(f["key"], [list(r) for r in rows])
    if not rows:
        return f, [], [], {"key": f["key"], "title": f["title"], "platform": f["platform"],
                           "field": field_of(f["key"]), "exhibitors": 0, "rivals": 0, "error": err,
                           "sec": round(time.time() - t0, 1), "when": f["when"], "kind": f["kind"],
                           "city": f["city"], "country": f["country"], "match": f["match"],
                           "url": f.get("page") or f.get("url", ""), "note": f.get("note", "")}
    recs, seen, ex_rows = [], set(), []
    for row in rows:
        name, booth = row[0], row[1]
        extra = row[2] if len(row) > 2 else ""
        if not name:
            continue
        keys = match_rivals(name)
        cs = conn_score(name, extra)
        # 화면에 실을 출품사 한 줄: [이름, 부스, 경쟁사키, 커넥터점수, 회사키(같은 회사 묶기용)]
        ex_rows.append([name[:90], booth[:24], keys[0] if keys else "", cs, norm_co(name)])
        for k in keys:
            if (k, name) in seen:
                continue
            seen.add((k, name))
            recs.append({"rival": k, "matched": name[:80], "booth": booth[:24],
                         "fair_key": f["key"], "fair": f["title"], "match": f["match"],
                         "field": field_of(f["key"]),
                         "when": f["when"], "kind": f["kind"], "cycle": f.get("cycle", 1),
                         "city": f["city"],
                         "country": f["country"], "url": src, "note": f.get("note", "")})
    nconn = sum(1 for r in ex_rows if r[3] >= 2 or r[2])
    return f, recs, ex_rows, {
        "key": f["key"], "title": f["title"], "platform": f["platform"], "match": f["match"],
        "exhibitors": total, "listed": len(ex_rows), "rivals": len({r["rival"] for r in recs}),
        "conn": nconn, "kind": f["kind"], "when": f["when"], "cycle": f.get("cycle", 1),
        "city": f["city"],
        "country": f["country"], "error": err, "stale": stale, "sec": round(time.time() - t0, 1),
        "field": field_of(f["key"]), "url": src, "note": f.get("note", "")}


def norm_co(name):
    """회사 이름 정규화 — 법인격·지역 표기를 떼고 같은 회사로 묶는다."""
    n = re.sub(r"[（(].*?[）)]", " ", name or "")
    n = re.split(r"\s*/\s*", n)[-1] if re.search(r"[ぁ-んァ-ン一-龥]", n) else n
    n = re.sub(r"\b(co|inc|ltd|llc|corp|corporation|company|gmbh|ag|kg|s\.?a|s\.?r\.?l|b\.?v|"
               r"n\.?v|plc|pte|pty|limited|holdings?|group|technologies|technology|electronics|"
               r"electric|usa|america|americas|europe|japan|korea|china|taiwan|deutschland|"
               r"合同会社|株式会社|有限会社)\b\.?", " ", n, flags=re.I)
    n = re.sub(r"[^0-9a-z가-힣ぁ-んァ-ン一-龥]", "", n.lower())
    return n


def build_companies(all_rows, fairs_by_key):
    """출품사를 회사 단위로 묶어 '어느 전시회에 나오는지'를 만든다.
    두 곳 이상 나오는 커넥터 계열 업체가 곧 '우리가 모르던 경쟁사 후보'."""
    comp = {}
    for fkey, rows in all_rows.items():
        for name, booth, rk, cs, key in rows:
            if len(key) < 3:
                continue
            c = comp.setdefault(key, {"name": name, "rival": rk or "", "conn": cs, "fairs": {}})
            if len(name) < len(c["name"]):
                c["name"] = name                  # 가장 짧은 표기를 대표 이름으로
            c["rival"] = c["rival"] or rk
            c["conn"] = max(c["conn"], cs)
            c["fairs"][fkey] = booth
    out = []
    for key, c in comp.items():
        out.append({"k": key, "n": c["name"], "r": c["rival"], "c": c["conn"],
                    "f": sorted(c["fairs"]), "b": c["fairs"]})
    out.sort(key=lambda x: (-len(x["f"]), -x["c"], x["n"].lower()))
    return out


def collect_all():
    records, report, all_rows = [], [], {}
    with ThreadPool(6) as pool:
        for f, recs, ex_rows, rep in pool.map(one, FAIRS):
            records += recs
            report.append(rep)
            if ex_rows:
                all_rows[f["key"]] = ex_rows
    companies = build_companies(all_rows, {r["key"]: r for r in report})
    # 우리가 모르던 커넥터 계열 업체 = 경쟁사 후보
    discovered = [c for c in companies
                  if not c["r"] and (c["c"] >= 3 or (c["c"] >= 1 and len(c["f"]) >= 2))]
    report.sort(key=lambda r: -(r.get("rivals") or 0))
    return {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fields": [[k, n] for k, n in FIELD_NAMES],
        "rivals": [RIVAL_META[k] for k, *_ in RIVALS],
        "fairs": report,
        "records": records,
        "exhibitors": all_rows,
        "companies": companies,
        "discovered": discovered,
    }


if __name__ == "__main__":
    data = collect_all()
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    for r in data["fairs"]:
        print(f"  {r['key']:16s} 출품사 {r['exhibitors']:5d}  경쟁사 {r.get('rivals', 0):3d}  "
              f"커넥터계열 {r.get('conn', 0):4d}  {r['sec']:5.1f}s  {r.get('error') or r['title']}")
    by = {}
    for r in data["records"]:
        by.setdefault(r["rival"], set()).add(r["fair"])
    print(f"\n경쟁사 {len(by)}곳 · 기록 {len(data['records'])}건 · "
          f"출품사 {sum(len(v) for v in data['exhibitors'].values())}개 · "
          f"새 후보 {len(data['discovered'])}곳")
    if "--dump" in sys.argv:
        for k, v in sorted(by.items(), key=lambda x: -len(x[1])):
            print(f"  {RIVAL_META[k]['name']:24s} {len(v)}곳  " + ", ".join(sorted(v))[:120])
        print("\n새로 찾은 커넥터 계열 업체 TOP 40")
        for c in data["discovered"][:40]:
            print(f"  {c['n'][:44]:46s} 전시회 {len(c['f'])}곳  {','.join(c['f'])}")
