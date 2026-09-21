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

import http.cookiejar
import io
import json
import os
import re
import ssl
import sys
import time
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


def match_rivals(name):
    if not name or NOISE.search(name):
        return []
    return [k for k, rx in RIVAL_RE if rx.search(name)]


# ================================================================ HTTP (쿠키 유지)
def opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj),
                                       urllib.request.HTTPSHandler(context=CTX))


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
    {"key": "automate26", "platform": "mys", "host": "automate26.mapyourshow.com",
     "title": "Automate 2026", "match": "Automate", "when": "2026-06", "kind": "past", "cycle": 1,
     "city": "Detroit", "country": "US", "note": "지난 회차(2026-06) 출품 이력"},
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
        booth = [b for b in (fl.get("boothsdisplay_la") or []) if "random" not in str(b)]
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
    try:
        rows, total, src = FETCH[f["platform"]](f)
    except Exception as e:  # noqa: BLE001 - 한 전시회가 막혀도 나머지는 살린다
        return f, [], [], {"key": f["key"], "title": f["title"], "platform": f["platform"],
                           "exhibitors": 0, "rivals": 0, "error": f"{type(e).__name__}: {e}",
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
                         "when": f["when"], "kind": f["kind"], "cycle": f.get("cycle", 1),
                         "city": f["city"],
                         "country": f["country"], "url": src, "note": f.get("note", "")})
    nconn = sum(1 for r in ex_rows if r[3] >= 2 or r[2])
    return f, recs, ex_rows, {
        "key": f["key"], "title": f["title"], "platform": f["platform"], "match": f["match"],
        "exhibitors": total, "listed": len(ex_rows), "rivals": len({r["rival"] for r in recs}),
        "conn": nconn, "kind": f["kind"], "when": f["when"], "cycle": f.get("cycle", 1),
        "city": f["city"],
        "country": f["country"], "error": None, "sec": round(time.time() - t0, 1),
        "url": src, "note": f.get("note", "")}


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
