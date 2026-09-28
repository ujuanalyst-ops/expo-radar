#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""경쟁사 흔적(트레이스) 추적 — 뉴스·보도자료·광고·검색결과에서 '어디에 나갔나'를 캐낸다.

rivals.py 는 **전시회 쪽 출품사 명단**을 읽는다. 명단을 공개하지 않는 전시회(그리고 이미 끝나
명단이 내려간 과거 회차)는 그 방식으로는 영원히 안 잡힌다. 이 파일은 반대편에서 판다 —
경쟁사 이름이 박힌 **뉴스·보도자료·회사 소식란·광고**를 모아 거기서 전시회 이름을 뽑아낸다.

  구글 뉴스 RSS   news.google.com/rss/search — 언어별(en/ja/ko/de/zh) 질의. 2010년대 기사까지 나온다.
  빙 뉴스 RSS     bing.com/news/search?format=RSS
  빙 웹검색       bing.com/search — 뉴스가 아닌 회사 행사 페이지·출품사 디렉터리가 걸린다
  덕덕고           html.duckduckgo.com — 빙이 막힐 때 대체
  회사 소식란     봇을 막지 않는 곳만 직접 읽는다 (이리소·야자키·I-PEX·JAE·JST·로젠베르거·앱티브)
  링크드인 광고   광고 라이브러리는 서버에서 403이라 브라우저로 한 번 받아 data/linkedin_ads.json 에 둔다.
                  (tools/linkedin_ads.md 참고) 이 파일이 있으면 그대로 합쳐 쓴다.

모은 글에서 **전시회 이름 사전**(아래 FAIRS + data/rivals.json + data/robots.json)을 찾아
(경쟁사 × 전시회 × 연도) 흔적으로 만든다. 전시회를 못 찾은 글도 '기타 흔적'으로 남긴다 —
사람이 읽고 새 전시회를 발견하는 게 이 화면의 목적이기 때문이다.

  python3 traces.py             # 수집 → data/traces.json → app-traces.js
  python3 traces.py --quick     # 질의 수를 줄여 빠르게(개발용)
"""

import hashlib
import html as _html
import json
import os
import re
import ssl
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from multiprocessing.dummy import Pool as ThreadPool

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "traces.json")
APPOUT = os.path.join(HERE, "app-traces.js")
KO_CACHE = os.path.join(HERE, "data", "ko_cache.json")
LI_ADS = os.path.join(HERE, "data", "linkedin_ads.json")
RAW_CACHE = os.path.join(HERE, "data", "traces_raw.json")   # 지난 수집분 — 검색엔진이 막혀도 유지된다

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
QUICK = "--quick" in sys.argv
OFFLINE = "--offline" in sys.argv   # 새로 안 캐고 data/traces_raw.json 만 다시 정리한다


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def get(url, timeout=25, headers=None):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as f:
        return f.read().decode("utf-8", "replace")


def clean(t):
    t = re.sub(r"<[^>]+>", " ", t or "")
    t = _html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


# ================================================================ 추적 대상 경쟁사
# (키, 표시이름, [검색어 별칭], 본사국)
#   별칭에는 현지 표기를 넣는다 — 일본 기사는 'ヒロ세電機', 한국 기사는 '히로세'로만 쓴다.
#   sig = 이 이름이 글에 실제로 있는지 확인하는 정규식(동명이인 걸러내기).
TARGETS = [
    ("molex", "Molex 몰렉스", "US", ["Molex", "モレックス", "몰렉스", "莫仕"],
     r"\bmolex\b|モレックス|몰렉스|莫仕"),
    ("amphenol", "Amphenol 암페놀", "US", ["Amphenol", "アンフェノール", "암페놀", "安费诺"],
     r"amphenol|アンフェノール|암페놀|安费诺"),
    ("te", "TE Connectivity (타이코)", "CH",
     ['"TE Connectivity"', "タイコエレクトロニクス", "TE커넥티비티", "泰科电子", '"Tyco Electronics"'],
     r"TE\s*Connectivity|tyco\s*electronics|タイコエレクトロニクス|TE\s*커넥티비티|泰科电子"),
    ("hirose", "Hirose 히로세", "JP", ["Hirose Electric", "ヒロセ電機", "히로세전기", "广濑"],
     r"hirose\s*(electric|electronic|connector|corporation|corp)|ヒロセ電機|히로세|广濑"),
    ("yazaki", "Yazaki 야자키", "JP", ["Yazaki", "矢崎総業", "야자키"],
     r"\byazaki\b|矢崎|야자키"),
    ("iriso", "IRISO 이리소", "JP", ["IRISO Electronics", "イリソ電子工業", "이리소"],
     r"iriso|イリソ|이리소"),
    ("ipex", "I-PEX 아이펙스", "JP", ['"I-PEX"', "アイペックス", "第一精工", "아이펙스"],
     r"\bi-?pex\b|アイペックス|第一精工|아이펙스"),
    ("jae", "JAE 일본항공전자", "JP", ['"Japan Aviation Electronics"', "日本航空電子", '"JAE Connector"'],
     r"japan aviation electronics|日本航空電子|\bJAE\b(?=.{0,40}(connector|コネクタ|커넥터|electronics))"),
    ("jst", "JST 일본압착단자", "JP", ['"JST Mfg"', "日本圧着端子", '"J.S.T. Connector"'],
     r"j\.?s\.?t\.?\s*(mfg|connector|corporation)|日本圧着端子|JST\s*(커넥터|コネクタ)"),
    ("aptiv", "Aptiv 앱티브", "IE", ["Aptiv", "アプティブ", "앱티브"],
     r"\baptiv\b|アプティブ|앱티브"),
    ("luxshare", "Luxshare 럭스쉐어", "CN", ["Luxshare", "立讯精密", "럭스쉐어"],
     r"luxshare|立讯|럭스쉐어|럭스셰어"),
    ("foxconn", "Foxconn FIT 폭스콘", "TW", ['"Foxconn Interconnect"', '"FIT Hon Teng"', "鴻騰精密"],
     r"foxconn\s*interconnect|fit\s*hon\s*teng|鴻騰|鸿腾"),
    ("samtec", "Samtec 샘텍", "US", ["Samtec", "サムテック", "샘텍"],
     r"\bsamtec\b|サムテック|샘텍"),
    ("harting", "HARTING 하팅", "DE", ["HARTING", "ハーティング", "하팅"],
     r"\bharting\b|ハーティング|하팅"),
    ("rosenberger", "Rosenberger 로젠베르거", "DE", ["Rosenberger", "ローゼンベルガー", "로젠베르거"],
     r"rosenberger|ローゼンベルガー|로젠베르거"),
    ("phoenix", "Phoenix Contact 피닉스컨택트", "DE", ['"Phoenix Contact"', "フエニックス・コンタクト", "피닉스컨택트"],
     r"phoenix\s*contact|フエニックス|피닉스\s*컨택"),
    ("odu", "ODU 오디유", "DE", ['"ODU Connector"', '"ODU GmbH"', '"ODU-USA"'],
     r"\bODU\b(?!\w)"),
    ("lemo", "LEMO 레모", "CH", ['"LEMO connector"', '"LEMO SA"'], r"\bLEMO\b(?!\w)"),
    ("smiths", "Smiths Interconnect", "GB", ['"Smiths Interconnect"'], r"smiths\s*interconnect"),
    ("radiall", "Radiall 라디알", "FR", ["Radiall"], r"\bradiall\b"),
    ("glenair", "Glenair 글레네어", "US", ["Glenair"], r"\bglenair\b"),
    ("souriau", "SOURIAU (Eaton)", "FR", ["SOURIAU", '"Souriau-Sunbank"'], r"souriau|sunbank"),
    ("itt", "ITT Cannon", "US", ['"ITT Cannon"'], r"itt\s*cannon"),
    ("jonhon", "JONHON 중항광전", "CN", ["JONHON", "中航光电"], r"jonhon|中航光电"),
    ("ket", "KET 한국단자공업", "KR", ["한국단자공업", '"Korea Electric Terminal"'],
     r"한국단자|korea electric terminal"),
    ("yeonho", "연호전자", "KR", ["연호전자", "Yeonho Electronics"], r"연호전자|yeonho"),
    ("woojin", "우진커넥터·기타 국내", "KR", ["커넥터 업체 전시회 참가", "커넥터 기업 출품"],
     r"커넥터"),
    ("hosiden", "Hosiden 호시덴", "JP", ["Hosiden", "ホシデン"], r"hosiden|ホシデン"),
    ("kyocera", "Kyocera AVX", "JP", ['"Kyocera AVX"', "京セラAVX"], r"kyocera\s*avx|京セラavx"),
    ("wurth", "Würth Elektronik", "DE", ['"Wurth Elektronik"', '"Würth Elektronik"'], r"w(ü|u)rth\s*elektronik"),
    ("staubli", "Stäubli Electrical", "CH", ['"Staubli Electrical"', '"Stäubli Electrical"'],
     r"st(ä|a)ubli"),
    ("bizlink", "BizLink 빅링크", "TW", ["BizLink Holding", "貿聯"], r"bizlink|貿聯|贸联"),
]
TARGET_IX = {t[0]: t for t in TARGETS}

# ================================================================ 전시회 이름 사전(직접 정리)
# 커넥터·전장·로봇·방산 업계가 실제로 나가는 곳. (표시이름, 찾기 정규식, 분야)
# data/rivals.json · data/robots.json 에서 읽어온 이름은 아래에 자동으로 더해진다.
FAIRS = [
    # 전자·부품
    ("electronica", r"\belectronica\b(?!\s*(china|india|south))", "elec"),
    ("electronica China", r"electronica\s*china|慕尼黑上海电子展", "elec"),
    ("electronica India", r"electronica\s*india", "elec"),
    ("productronica", r"\bproductronica\b", "elec"),
    ("embedded world", r"embedded\s*world", "elec"),
    ("CES", r"\bCES\s*20\d\d\b|\bCES\b(?=.{0,30}(라스베이거스|las vegas|가전))", "elec"),
    ("COMPUTEX", r"computex|台北國際電腦展", "elec"),
    ("CEATEC", r"\bceatec\b", "elec"),
    ("한국전자전 KES", r"한국전자전|\bKES\s*20\d\d", "elec"),
    ("NEPCON Japan", r"nepcon\s*japan|ネプコン\s*ジャパン", "elec"),
    ("NEPCON Asia", r"nepcon\s*(asia|china|south china)", "elec"),
    ("JPCA Show", r"\bJPCA\s*(show|展)", "elec"),
    ("IPC APEX EXPO", r"ipc\s*apex", "elec"),
    ("DesignCon", r"designcon", "elec"),
    ("electronicAsia", r"electronic\s*asia|香港電子", "elec"),
    ("홍콩 전자전 HKEF", r"hong\s*kong\s*electronics\s*fair|香港電子產品展", "elec"),
    ("CIOE 중국광박람회", r"\bCIOE\b|中国国际光电", "elec"),
    ("SEMICON", r"\bsemicon\s*(west|japan|korea|taiwan|china|europe|southeast)", "elec"),
    ("ECTC", r"\bECTC\b|electronic components and technology", "elec"),
    ("APEC 전력전자", r"\bAPEC\b(?=.{0,40}(power|전력|electronics))", "elec"),
    ("PCIM Europe", r"\bPCIM\b", "elec"),
    ("Sensors Converge", r"sensors\s*(converge|expo)", "elec"),
    ("SPS 뉘른베르크", r"\bSPS\b(?=.{0,40}(nürnberg|nuremberg|smart production|automation|드라이브))|sps\s*ipc\s*drives", "fa"),
    ("InfoComm", r"infocomm", "elec"),
    ("ISE", r"integrated\s*systems\s*europe|\bISE\s*20\d\d", "elec"),
    ("MWC", r"mobile\s*world\s*congress|\bMWC\s*(바르셀로나|barcelona|20\d\d)", "elec"),
    ("OFC", r"\bOFC\b(?=.{0,40}(optical|fiber|conference|광))|optical\s*fiber\s*communication", "elec"),
    ("ECOC", r"\bECOC\b|european\s*conference\s*on\s*optical", "elec"),
    ("OCP Global Summit", r"\bOCP\b.{0,20}(global\s*summit|regional\s*summit)|open\s*compute\s*(project\s*)?summit", "elec"),
    ("SC 슈퍼컴퓨팅", r"\bSC\s*2\d\b(?=.{0,30}(supercomput|HPC))|supercomputing\s*conference", "elec"),
    ("Touch Taiwan", r"touch\s*taiwan", "elec"),
    ("K-Display 한국디스플레이산업전", r"k-?display|한국디스플레이산업전", "elec"),
    # 자동차·모빌리티
    ("人とくるまのテクノロジー展 (JSAE)", r"人とくるまのテクノロジー|automotive\s*engineering\s*exposition", "auto"),
    ("Automotive World Tokyo", r"automotive\s*world|オートモーティブ\s*ワールド", "auto"),
    ("AAPEX", r"\bAAPEX\b", "auto"),
    ("SEMA Show", r"\bSEMA\s*show\b", "auto"),
    ("Automechanika", r"automechanika", "auto"),
    ("TAIPEI AMPA", r"taipei\s*ampa|\bAMPA\b(?=.{0,20}(台北|taipei))", "auto"),
    ("IAA Mobility", r"\bIAA\b\s*(mobility|transportation|모빌리티)", "auto"),
    ("Seoul Mobility Show", r"서울모빌리티쇼|seoul\s*mobility\s*show", "auto"),
    ("KOAA SHOW", r"\bKOAA\b", "auto"),
    ("EVS 전기차심포지엄", r"\bEVS\d\d\b|electric\s*vehicle\s*symposium", "auto"),
    ("InterBattery", r"인터배터리|interbattery", "batt"),
    ("The Battery Show", r"the\s*battery\s*show|battery\s*show\s*(north america|europe)", "batt"),
    ("Auto Shanghai / Auto China", r"auto\s*(shanghai|china)|上海车展|北京车展", "auto"),
    ("SAE WCX", r"\bWCX\b|sae\s*world\s*congress", "auto"),
    ("Tire Technology / 車両", r"tire\s*technology\s*expo", "auto"),
    # 산업·자동화·로봇
    ("Hannover Messe", r"hannover\s*messe|하노버\s*(산업|메세)|ハノーバーメッセ", "fa"),
    ("automatica", r"\bautomatica\b", "robot"),
    ("Automate", r"\bautomate\s*20\d\d\b|automate\s*show", "robot"),
    ("iREX 국제로봇전", r"\biREX\b|国際ロボット展", "robot"),
    ("로보월드 RobotWorld", r"로보월드|robot\s*world\s*20\d\d", "robot"),
    ("IMTS", r"\bIMTS\b", "fa"),
    ("EMO Hannover", r"\bEMO\s*(hannover|hanover|milano)", "fa"),
    ("CIIF 중국국제공업박람회", r"\bCIIF\b|中国国际工业博览会", "fa"),
    ("ProMat", r"\bpromat\b", "robot"),
    ("MODEX", r"\bMODEX\b\s*20\d\d", "robot"),
    ("LogiMAT", r"logimat", "robot"),
    ("오토메이션월드", r"오토메이션\s*월드|automation\s*world\s*20\d\d", "fa"),
    ("TECHNO-FRONTIER", r"techno-?frontier|テクノフロンティア", "fa"),
    ("스마트공장·자동화산업전", r"스마트공장\s*자동화산업전|smart\s*factory\s*\+?\s*automation\s*world", "fa"),
    ("PACK EXPO", r"pack\s*expo", "fa"),
    ("Interwire / wire", r"\binterwire\b|\bwire\s*(düsseldorf|dusseldorf|china|india|southeast)", "fa"),
    ("드론쇼코리아", r"드론쇼\s*코리아|drone\s*show\s*korea", "robot"),
    ("WRC 세계로봇대회", r"world\s*robot\s*conference|世界机器人大会", "robot"),
    ("Robotics Summit", r"robotics\s*summit", "robot"),
    ("RoboBusiness", r"robobusiness", "robot"),
    ("TAIROS", r"\btairos\b", "robot"),
    # 방산·항공
    ("Eurosatory", r"eurosatory", "def"),
    ("DSEI", r"\bDSEI\b", "def"),
    ("AUSA", r"\bAUSA\b\s*(annual|20\d\d)", "def"),
    ("XPONENTIAL", r"xponential", "def"),
    ("Paris Air Show", r"paris\s*air\s*show|salon\s*du\s*bourget", "def"),
    ("Farnborough", r"farnborough", "def"),
    ("Seoul ADEX", r"서울\s*ADEX|\bADEX\b\s*20\d\d|seoul\s*international\s*aerospace", "def"),
    ("DX Korea / KADEX", r"\bKADEX\b|\bDX\s*KOREA\b", "def"),
    ("Space Tech Expo", r"space\s*tech\s*expo", "def"),
    ("AUVSI", r"\bAUVSI\b", "def"),
    ("Singapore Airshow", r"singapore\s*airshow", "def"),
    ("Dubai Airshow", r"dubai\s*airshow", "def"),
    ("MSPO", r"\bMSPO\b", "def"),
    ("Sea Air Space", r"sea\s*air\s*space", "def"),
    # 의료·기타
    ("MD&M West", r"md&?m\s*west|medical\s*design\s*&?\s*manufactur", "med"),
    ("MEDICA / COMPAMED", r"\bmedica\b\s*(20\d\d|düsseldorf|뒤셀도르프)|compamed", "med"),
    ("KIMES", r"\bKIMES\b", "med"),
    ("InnoTrans", r"innotrans", "rail"),
    ("Railway / 철도산업전", r"railway\s*interiors|철도산업전|rail\s*live", "rail"),
    ("Intersolar / RE+", r"intersolar|\bRE\+\b", "enr"),
    ("H2 MEET", r"h2\s*meet|수소모빌리티", "enr"),
    ("ICH 커넥터·하네스전", r"\bICH\b(?=.{0,40}(connector|커넥터|harness))|国际连接器", "conn"),
    ("커넥터·케이블 하네스 전문전", r"connector\s*(&|and)\s*cable\s*(harness|assembly)\s*(expo|show)", "conn"),
    # ── 고주파·광·반도체
    ("IMS / MTT-S 국제마이크로파심포지엄",
     r"\bIMS\b(?=\s*20\d\d)|20\d\d\s*\bIMS\b|international\s*microwave\s*symposium|\bMTT-?S\b", "elec"),
    ("EuMW 유럽마이크로파주간", r"european\s*microwave\s*week|\bEuMW\b", "elec"),
    ("Photonics West", r"photonics\s*west", "elec"),
    ("LASER World of PHOTONICS", r"laser\s*world\s*of\s*photonics", "elec"),
    ("SPIE", r"\bSPIE\b\s*(defense|photonics|optics|advanced)", "elec"),
    ("DAC 설계자동화학회", r"design\s*automation\s*conference|\bDAC\s*20\d\d", "elec"),
    ("GTC 엔비디아", r"\bGTC\b\s*(20\d\d|엔비디아|nvidia)", "elec"),
    ("ISC High Performance", r"\bISC\s*high\s*performance|isc\s*20\d\d\b", "elec"),
    ("CIIE 중국국제수입박람회", r"\bCIIE\b|中国国际进口博览会", "elec"),
    ("Canton Fair 광교회", r"canton\s*fair|广交会|廣交會", "elec"),
    ("IFA 베를린", r"\bIFA\s*(berlin|20\d\d)", "elec"),
    ("Embedded Tech / ET & IoT", r"\bET\s*&\s*IoT|embedded\s*technology\s*(west|展)", "elec"),
    ("Interop Tokyo", r"interop\s*tokyo", "elec"),
    ("Data Center World / DCD", r"data\s*cent(er|re)\s*world|\bDCD\b\s*(connect|>)", "elec"),
    ("AWE 어드밴스드", r"\bAWE\b\s*(usa|europe|20\d\d)", "elec"),
    ("KES 전자파", r"국제전기전자|전기·?전자산업전", "elec"),
    ("FPD China / 디스플레이", r"\bFPD\s*china|display\s*week|\bSID\b\s*display", "elec"),
    ("SEMICON Korea", r"semicon\s*korea|세미콘\s*코리아", "elec"),
    ("반도체대전 SEDEX", r"\bSEDEX\b|반도체대전", "elec"),
    # ── 자동차 심화
    ("CAR-ELE / 오토모티브월드 재팬", r"car-?ele|カーエレクトロニクス技術展|オートモーティブ\s*ワールド", "auto"),
    ("Bharat Mobility / Auto Expo", r"bharat\s*mobility|auto\s*expo\s*components", "auto"),
    ("Automotive Testing Expo", r"automotive\s*testing\s*expo", "auto"),
    ("Vehicle Electrification Expo", r"vehicle\s*electrification|electric\s*&\s*hybrid\s*vehicle", "auto"),
    ("CES Asia / 상하이", r"ces\s*asia", "auto"),
    ("JAPAN MOBILITY SHOW", r"japan\s*mobility\s*show|ジャパンモビリティショー|東京モーターショー", "auto"),
    ("Munich / IAA Transportation", r"iaa\s*transportation", "auto"),
    ("EVS / EV Trend Korea", r"ev\s*trend\s*korea|전기차\s*트렌드", "auto"),
    ("xEV / 배터리 재팬", r"battery\s*japan|バッテリー\s*ジャパン|スマートエネルギー", "batt"),
    ("CIBF 중국국제배터리전", r"\bCIBF\b|中国国际电池", "batt"),
    # ── 산업·기계 심화
    ("Motek", r"\bmotek\b", "fa"),
    ("all about automation", r"all\s*about\s*automation", "fa"),
    ("MECSPE", r"\bmecspe\b", "fa"),
    ("SPS Italia", r"sps\s*italia", "fa"),
    ("Global Industrie", r"global\s*industrie", "fa"),
    ("Advanced Engineering UK", r"advanced\s*engineering\s*(uk|show)", "fa"),
    ("Southern Manufacturing", r"southern\s*manufacturing", "fa"),
    ("METALEX", r"\bmetalex\b", "fa"),
    ("Manufacturing World Japan", r"manufacturing\s*world|ものづくりワールド", "fa"),
    ("MTA / ITAP 싱가포르", r"\bITAP\b|industrial\s*transformation\s*asia", "fa"),
    ("Vietnam Manufacturing Expo", r"vietnam\s*manufacturing\s*expo|\bVMEX\b|\bVIMF\b", "fa"),
    ("IMTEX / ELECRAMA 인도", r"\bIMTEX\b|\belecrama\b|automation\s*expo\s*india", "fa"),
    ("Fakuma / K show", r"\bfakuma\b|\bK\s*20\d\d\b(?=.{0,30}(düsseldorf|plastic))", "fa"),
    ("JIMTOF", r"\bJIMTOF\b|日本国際工作機械", "fa"),
    ("한국기계전 / 서울국제생산제조", r"한국기계전|생산제조기술전|\bSIMTOS\b", "fa"),
    ("MWCS 중국국제기계", r"\bMWCS\b|中国数控机床", "fa"),
    # ── 방산 심화
    ("IDEX 아부다비", r"\bIDEX\b\s*(abu|20\d\d)", "def"),
    ("Defexpo / DefExpo India", r"def\s*expo\s*india|defexpo", "def"),
    ("Modern Day Marine / Sea Air", r"modern\s*day\s*marine", "def"),
    ("Space Symposium", r"space\s*symposium", "def"),
    ("AIAA SciTech", r"aiaa\s*(scitech|aviation)", "def"),
    ("ILA Berlin", r"\bILA\s*berlin", "def"),
    ("Aero India", r"aero\s*india", "def"),
    ("Indo Defence / DSA", r"indo\s*defence|\bDSA\s*20\d\d", "def"),
    ("Enforce Tac / Milipol", r"enforce\s*tac|milipol", "def"),
    ("AUSA Global / Warfighter", r"ausa\s*global", "def"),
    # ── 기타
    ("NAB Show", r"\bNAB\s*show", "elec"),
    ("IBC 암스테르담", r"\bIBC\s*20\d\d\b|\bIBC\b(?=.{0,30}amsterdam)", "elec"),
    ("Vision 슈투트가르트", r"\bVISION\s*(stuttgart|20\d\d)", "robot"),
    ("Interphex / Pharma", r"interphex", "med"),
    ("Arab Health", r"arab\s*health", "med"),
    ("Enlit / E-world", r"\benlit\b|e-?world\s*energy", "enr"),
    ("Intersolar / SNEC", r"\bSNEC\b|intersolar", "enr"),
    ("WindEnergy 함부르크", r"windenergy\s*hamburg|husum\s*wind", "enr"),
    ("Hannover 에너지 / Hydrogen+Fuel Cells", r"hydrogen\s*\+\s*fuel\s*cells", "enr"),
    ("전기산업대전 / 국제전기", r"전기산업대전|국제전기전자산업전|\bSIEF\b", "enr"),
    ("스마트테크코리아", r"스마트테크\s*코리아|smart\s*tech\s*korea", "robot"),
    ("국제물류산업대전 KOREA MAT", r"국제물류산업대전|korea\s*mat\b", "robot"),
]

FIELD_NAME = {"elec": "💻 전자·IT", "auto": "🚗 자동차·모빌리티", "fa": "🏭 산업·자동화",
              "robot": "🤖 로봇", "def": "🛡 방산·항공우주", "med": "🏥 의료", "batt": "🔋 배터리",
              "rail": "🚆 철도", "enr": "⚡ 에너지", "conn": "🔌 커넥터 전문", "etc": "기타"}
# rivals.json 이 쓰는 분야 키를 여기 키로 맞춘다 (같은 분야가 두 줄로 갈라지지 않게)
FIELD_ALIAS = {"defense": "def", "factory": "fa", "medical": "med", "battery": "batt",
               "connector": "conn"}

# 전시회 기사임을 알려주는 말 — 전시회 이름을 못 찾아도 이게 있으면 '기타 흔적'으로 남긴다
SHOW_HINT = re.compile(
    r"\bbooth\b|\bstand\s*[A-Z]?\d|trade\s*show|tradeshow|exhibit|exhibition|showcase[sd]?|"
    r"will\s*(show|display|present|demo|unveil|introduce)|on\s*display\s*at|visit\s*us|"
    r"\bexpo\b|\bfair\b|pavilion|unveil|demonstrat|present(s|ed|ing)?\s+(at|its|new)|"
    r"\bshows?\s+(its|new|off|the)|brings?\s+its\b|\bat\s+the\s+20\d\d\b|\bat\s+20\d\d\b|"
    r"出展|展示会|展示|出品|ブース|見本市|披露|公開|参考出品|お披露目|"
    r"参展|展会|展位|展台|亮相|参加展|"
    r"전시회|부스|출품|참가|전시관|박람회|선보|공개|전시한|참여|"
    r"messe|\bstand\b|ausstellung|fachmesse|pr(ä|ae)sentiert|zeigt\s|vorgestellt|"
    r"salon\b|feria|pr(é|e)sente|exposici(ó|o)n", re.I)

# 광고·채용 같은 잡음 (전시회와 무관)
NOISE = re.compile(r"price target|analyst|earnings|quarterly|dividend|stock\b|shares?\s*(rose|fell)|"
                   r"buy rating|hold rating|채용|주가|목표주가|증권", re.I)


# ================================================================ 사전 만들기
PROBE = {}
# DB 이름 중 너무 흔해 아무 기사에나 걸리는 것 (전시회 이름으로 쓰기엔 변별력이 없다)
GENERIC = re.compile(r"^(international|world|global|asia|china|korea|japan|europe|american)?\s*"
                     r"(automotive|industry|industrial|manufacturing|machinery|technology|electronics|"
                     r"energy|building|food|medical|trade|business|consumer|home|textile|"
                     r"mobility|logistics|packaging|plastics|construction)\s*"
                     r"(expo|fair|show|exhibition|week|summit|forum|conference|convention|festival)$", re.I)


def build_fair_dict():
    """직접 정리한 FAIRS + 우리 데이터에서 읽은 전시회 이름을 하나로."""
    out = []
    seen = set()
    for name, pat, fld in FAIRS:
        out.append((name, re.compile(pat, re.I), fld, "직접"))
        seen.add(name.lower())

    def add(name, fld):
        n = (name or "").strip()
        if len(n) < 5 or n.lower() in seen:
            return
        # 연도·회차를 뗀다
        n = re.sub(r"\b(19|20)\d\d\b|제\s*\d+\s*회|第\s*\d+\s*回", "", n).strip(" -–—·,")
        if len(n) < 5 or n.lower() in seen:
            return
        seen.add(n.lower())
        out.append((n, re.compile(r"\b" + re.escape(n) + r"\b", re.I), fld, "DB"))
        PROBE[len(out) - 1] = n.lower()[:12]   # 싼 문자열 검사용 앞머리

    try:
        riv = json.load(open(os.path.join(HERE, "data", "rivals.json"), encoding="utf-8"))
        for r in riv.get("records", []):
            fk = r.get("field") or "etc"
            add(r.get("match") or "", FIELD_ALIAS.get(fk, fk))
    except Exception:  # noqa: BLE001
        pass
    try:
        rb = json.load(open(os.path.join(HERE, "data", "robots.json"), encoding="utf-8"))
        for e in rb.get("expos", []):
            add(e.get("te") or "", "robot")
    except Exception:  # noqa: BLE001
        pass
    # 전시회 DB(19,000건)의 영문 이름도 — 전시회 같은 말이 들어간 두 단어 이상짜리만 고른다
    sfx = re.compile(r"expo|fair|show|exhibition|summit|congress|forum|week|messe|salon|symposium|"
                     r"conference|convention|festival", re.I)
    try:
        store = json.load(open(os.path.join(HERE, "data", "expos.json"), encoding="utf-8"))
        for e in (store.values() if isinstance(store, dict) else store):
            n = (e.get("title_en") or "").strip()
            if not n or not sfx.search(n) or len(n) > 55 or n.count(" ") < 1:
                continue
            if GENERIC.search(n):
                continue
            add(n, "etc")
    except Exception:  # noqa: BLE001
        pass
    return out


FAIRDICT = build_fair_dict()


# 전시회가 아닌데 이름만 전시회처럼 생긴 것 (행사장 이름·자선행사·채용박람회)
NOT_FAIR = re.compile(
    r"convention cent(er|re)|congress cent(er|re)|exhibition cent(er|re)|mccormick place|"
    r"health\s*&?\s*fitness|marathon|job\s*fair|career\s*fair|hiring\s*event|채용\s*박람회|"
    r"food\s*(fair|festival)|book\s*fair|art\s*fair|county\s*fair|state\s*fair", re.I)


def find_fairs(text):
    """글에서 전시회 이름과 (있으면) 연도를 뽑는다."""
    hits = []
    low = text.lower()
    for i, (name, rx, fld, src) in enumerate(FAIRDICT):
        p = PROBE.get(i)
        if p is not None and p not in low:
            continue                       # DB 이름은 앞머리 문자열이 없으면 정규식도 안 돌린다
        m = rx.search(text)
        if not m:
            continue
        # 이름 주변 40자에서 연도를 찾는다
        near = text[max(0, m.start() - 15):m.end() + 40]
        y = re.search(r"(?<!\d)(20[0-3]\d)(?!\d)", near)
        if NOT_FAIR.search(name):
            continue
        hits.append({"fair": name, "field": fld, "year": int(y.group(1)) if y else 0, "src": src})
        if len(hits) >= 4:
            break
    return hits


# ---------------------------------------------------------------- 사전에 없는 전시회 캐내기
# "… at DesignCon 2026", "「国際ロボット展」に出展", "인터배터리 2026에 참가" 같은 꼴에서
# 전시회 이름을 직접 뽑는다. 우리 사전에 없는 전시회를 **새로 발견**하는 게 목적이다.
GUESS = [
    re.compile(r"\b(?:at|during|for)\s+(?:the\s+)?"
               r"((?:[A-Z][\w&.'+-]*|20\d\d)(?:[ -](?:[A-Z][\w&.'+-]*|of|and|&|for|the|20\d\d)){0,5})"
               r"(?=[,.;:!?)\s]|$)"),
    re.compile(r"「([^」]{3,40}?(?:展|EXPO|Expo|フェア|ショー|見本市))」"),
    re.compile(r"([\w\u4e00-\u9fff\u3040-\u30ff]{2,20}(?:展|博覧会|見本市))\s*(?:20\d\d)?\s*(?:に|で|へ)?\s*出展"),
    re.compile(r"([가-힣A-Za-z0-9·\- ]{3,30}?(?:전시회|박람회|산업전|엑스포|EXPO|쇼))\s*(?:20\d\d)?\s*(?:에|에서|)\s*(?:참가|참여|출품|전시)"),
    re.compile(r"([0-9A-Za-z][\w&.'+-]*(?:[ -][A-Za-z][\w&.'+-]*){0,4}\s+20\d\d)\s*"
               r"(?:에서|에|展|で|に)?\s*(?:booth|展示|出展|참가|부스)", re.I),
]
# 전시회 이름일 리가 없는 말 (위 정규식이 흔히 물어 오는 것들)
GUESS_STOP = re.compile(
    r"^(the|a|an|its|our|their|this|new|ces|q[1-4]|inc|corp|ltd|gmbh|co|llc|kk|plc|sa|ag|nv|bv)$|"
    r"^(january|february|march|april|may|june|july|august|september|october|november|december)\b|"
    r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|"
    r"^(reuters|bloomberg|yahoo|google|linkedin|facebook|x|twitter|youtube)\b|"
    r"^(molex|amphenol|te connectivity|hirose|yazaki|iriso|i-pex|jae|jst|aptiv|luxshare|foxconn|"
    r"samtec|harting|rosenberger|phoenix contact|odu|lemo|radiall|glenair|souriau|itt|jonhon|"
    r"kyocera|hosiden|bizlink)\b|"
    r"^(ai|iot|ev|usb|pcb|rf|5g|6g|hdmi|ethernet|automotive|industrial|data center|north america|"
    r"europe|asia|china|japan|korea|india|germany|france|uk|us|usa)$", re.I)
GUESS_GOOD = re.compile(
    r"expo|fair|show|exhibition|summit|congress|forum|conference|week|messe|salon|symposium|"
    r"world|days?\b|festival|convention|展|博覧会|見本市|フェア|ショー|전시회|박람회|산업전|엑스포|쇼\b",
    re.I)


def guess_fairs(text):
    """사전에 없는 전시회 이름을 글에서 직접 캐낸다. 확신이 낮으므로 src='발굴'로 표시한다."""
    out, seen = [], set()
    for rx in GUESS:
        for m in rx.finditer(text):
            n = re.sub(r"\s+", " ", m.group(1)).strip(" -–—·,.'\"")
            y = re.search(r"(?<!\d)(20[0-3]\d)(?!\d)", n)
            year = int(y.group(1)) if y else 0
            n2 = re.sub(r"(?<!\d)20[0-3]\d(?!\d)", "", n).strip(" -–—·,")
            # "Medical Technology Ireland This September…" 처럼 다음 문장이 딸려오면 자른다
            n2 = re.split(r"\s+(?=(?:This|That|We|Our|Join|Visit|Come|Meet|The|It|He|She|They)\b)",
                          n2)[0].strip(" -–—·,")
            if len(n2) < 4 or len(n2) > 55 or n2.lower() in seen:
                continue
            if GUESS_STOP.search(n2) or NOT_FAIR.search(n2):
                continue
            # 전시회 같은 말이 들어 있거나, 연도가 붙어 있고 대문자로 시작하는 고유명사여야 한다
            if not (GUESS_GOOD.search(n2)
                    or (year and re.match(r"^[A-Z0-9]", n2) and len(n2) >= 3
                        and not n2.islower() and n2 not in ("The", "This", "New"))):
                continue
            seen.add(n2.lower())
            out.append({"fair": n2, "field": "etc", "year": year, "src": "발굴"})
            if len(out) >= 3:
                return out
    return out


# ================================================================ 수집기
_seen_lock = threading.Lock()


def rss_items(xml):
    out = []
    for m in re.finditer(r"<item>(.*?)</item>", xml, re.S):
        b = m.group(1)

        def pick(tag):
            mm = re.search(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), b, re.S)
            return clean(mm.group(1)) if mm else ""
        link = re.search(r"<link[^>]*>(.*?)</link>", b, re.S)
        out.append({"title": pick("title"), "desc": pick("description"),
                    "url": clean(link.group(1)) if link else "",
                    "date": pick("pubDate"), "site": pick("source")})
    return out


GN = {"en": ("en-US", "US", "US:en"), "ja": ("ja", "JP", "JP:ja"), "ko": ("ko", "KR", "KR:ko"),
      "de": ("de", "DE", "DE:de"), "zh": ("zh-CN", "CN", "CN:zh-Hans"),
      "fr": ("fr", "FR", "FR:fr"), "tw": ("zh-TW", "TW", "TW:zh-Hant")}


BLOCKED = {"n": 0, "stop": False}   # 연속으로 빈 응답이 오면 검색엔진이 한도를 건 것이다


def gnews(q, lang="en"):
    hl, gl, ceid = GN.get(lang, GN["en"])
    u = ("https://news.google.com/rss/search?q=%s&hl=%s&gl=%s&ceid=%s"
         % (urllib.parse.quote(q), hl, gl, ceid))
    items = None
    for attempt in range(3):          # 구글 뉴스는 한도를 넘기면 429/빈 응답을 준다 — 쉬었다 다시
        try:
            items = rss_items(get(u, 20))
            break
        except Exception as e:  # noqa: BLE001
            if "429" in str(e) or "503" in str(e):
                if BLOCKED["stop"]:
                    return []
                time.sleep(4 * (attempt + 1))
            else:
                return []
    if items is None:
        return []
    for it in items:
        it["kind"] = "news"
        it["q"] = q
    return items


def bingnews(q):
    u = "https://www.bing.com/news/search?q=%s&format=RSS" % urllib.parse.quote(q)
    try:
        items = rss_items(get(u, 20))
    except Exception:  # noqa: BLE001
        return []
    for it in items:
        it["kind"] = "news"
        it["site"] = it.get("site") or "Bing 뉴스"
        it["q"] = q
    return items


def bingweb(q):
    """빙 웹검색 — 뉴스가 아닌 회사 행사 페이지·출품사 디렉터리가 걸린다."""
    u = "https://www.bing.com/search?q=%s&count=20" % urllib.parse.quote(q)
    try:
        h = get(u, 20)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for m in re.finditer(r'<li class="b_algo".*?</li>', h, re.S):
        blk = m.group(0)
        a = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
        if not a:
            continue
        p = re.search(r'<p[^>]*>(.*?)</p>', blk, re.S)
        out.append({"title": clean(a.group(2)), "url": a.group(1), "desc": clean(p.group(1)) if p else "",
                    "date": "", "site": urllib.parse.urlparse(a.group(1)).netloc, "kind": "web", "q": q})
    return out


def ddg(q):
    u = "https://html.duckduckgo.com/html/?q=%s" % urllib.parse.quote(q)
    try:
        h = get(u, 20)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for m in re.finditer(r'<a rel="nofollow" class="result__a" href="([^"]+)">(.*?)</a>', h, re.S):
        url = _html.unescape(m.group(1))
        if "uddg=" in url:
            url = urllib.parse.unquote(re.search(r"uddg=([^&]+)", url).group(1))
        out.append({"title": clean(m.group(2)), "url": url, "desc": "", "date": "",
                    "site": urllib.parse.urlparse(url).netloc, "kind": "web", "q": q})
    return out


# ================================================================ 회사 소식란 (봇을 막지 않는 곳만)
def newsroom(key, url, item_re, base=""):
    try:
        h = get(url, 25)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for m in re.finditer(item_re, h, re.S | re.I):
        d = m.groupdict()
        href = d.get("url") or ""
        if href and not href.startswith("http"):
            href = urllib.parse.urljoin(base or url, href)
        out.append({"title": clean(d.get("title") or ""), "url": href or url,
                    "desc": clean(d.get("desc") or ""), "date": clean(d.get("date") or ""),
                    "site": urllib.parse.urlparse(url).netloc, "kind": "official", "q": "회사 소식란"})
    return [o for o in out if len(o["title"]) > 4]


NEWSROOMS = [
    ("iriso", "https://www.iriso.co.jp/news/",
     r'<a[^>]+href="(?P<url>[^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*(?P<date>20\d\d[./-]\d\d?[./-]\d\d?)?\s*(?:<[^>]+>\s*)*(?P<title>[^<]{8,120})'),
    ("yazaki", "https://www.yazaki-group.com/news/",
     r'<time[^>]*>(?P<date>[^<]+)</time>.{0,200}?<a[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>[^<]{8,160})'),
    ("ipex", "https://www.i-pex.com/news",
     r'href="(?P<url>[^"]*news[^"]*)"[^>]*>\s*(?:<[^>]*>\s*)*(?P<date>20\d\d[./-]\d\d?[./-]\d\d?)?\s*(?:<[^>]*>\s*)*(?P<title>[^<]{8,160})'),
    ("jae", "https://www.jae.com/en/topics/",
     r'<a[^>]+href="(?P<url>[^"]+)"[^>]*>\s*(?:<[^>]*>\s*)*(?P<date>20\d\d[./-]\d\d?[./-]\d\d?)?\s*(?:<[^>]*>\s*)*(?P<title>[^<]{8,160})'),
    ("rosenberger", "https://www.rosenberger.com/news-events/",
     r'<a[^>]+href="(?P<url>[^"]+)"[^>]*>\s*(?:<[^>]*>\s*)*(?P<title>[^<]{10,160})'),
    ("aptiv", "https://www.aptiv.com/en/newsroom",
     r'<a[^>]+href="(?P<url>[^"]+)"[^>]*>\s*(?:<[^>]*>\s*)*(?P<title>[^<]{10,160})'),
]


def run_newsrooms():
    out = []

    def work(row):
        key, url, rx = row
        got = newsroom(key, url, rx)
        for g in got:
            g["rival"] = key
        return key, url, got
    with ThreadPool(6) as pool:
        for key, url, got in pool.map(work, NEWSROOMS):
            log("  소식란 %-12s %4d건  %s" % (key, len(got), url))
            out += got
    return out


# ================================================================ 링크드인 광고 (브라우저로 받아 둔 파일)
def linkedin_ads():
    try:
        d = json.load(open(LI_ADS, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    out = []
    for a in d.get("ads", []):
        out.append({"title": a.get("title") or a.get("text", "")[:120], "desc": a.get("text", ""),
                    "url": a.get("url") or ("https://www.linkedin.com/ad-library/search?accountOwner="
                                            + urllib.parse.quote(a.get("advertiser", ""))),
                    "date": a.get("date", ""), "site": "LinkedIn 광고 라이브러리", "kind": "ad",
                    "rival": a.get("rival", ""), "q": a.get("advertiser", "")})
    return out


# ================================================================ 질의 만들기
# 구글 뉴스 RSS 가 주력이다. 빙 웹검색은 회사 홈페이지·스팸만 올라와 쓰지 않는다(2026-09 확인).
#  1) 일반형   "몰렉스" (booth OR exhibit OR …)        — 최근 기사
#  2) 기간형   … after:2016-01-01 before:2020-01-01    — 구글 뉴스는 옛 기사도 이렇게 꺼낼 수 있다
#  3) 짝지음형 "몰렉스" "electronica"                   — 전시회를 하나씩 직접 물어본다
#  4) 현지어형 "矢崎総業" 出展 / "몰렉스" 전시회 참가       — 일본·한국·중국·독일 기사는 이 말만 쓴다
EN_SHOW = '(booth OR exhibit OR exhibition OR showcase OR "trade show" OR expo OR pavilion)'
SPANS = ["after:2010-01-01 before:2015-01-01", "after:2015-01-01 before:2019-01-01",
         "after:2019-01-01 before:2023-01-01", "after:2023-01-01 before:2026-01-01"]

# 짝지음형으로 물어볼 전시회 — 커넥터 업계가 실제로 나가는 곳
PAIR_EN = ["electronica", "productronica", "embedded world", "Hannover Messe", "CES", "DesignCon",
           "automatica", "Automate", "SPS", "Eurosatory", "DSEI", "MD&M West", "MWC", "COMPUTEX",
           "NEPCON", "Automotive World", "OFC", "ECOC", "SEMICON", "IMTS", "AAPEX", "SEMA",
           "InnoTrans", "Paris Air Show", "Farnborough", "AUSA", "XPONENTIAL", "IPC APEX",
           "CEATEC", "IFA", "IMS", "PCIM", "Battery Show", "MEDICA", "ProMat", "LogiMAT",
           "Automechanika", "CIOE", "Touch Taiwan", "AMPA", "JPCA", "ISE", "InfoComm", "OCP"]
PAIR_JA = ["国際ロボット展", "人とくるまのテクノロジー展", "CEATEC", "ネプコン", "オートモーティブワールド",
           "テクノフロンティア", "JPCA", "スマートエネルギー", "国際物流総合展", "モーターショー"]
PAIR_KO = ["한국전자전", "인터배터리", "서울모빌리티쇼", "오토메이션월드", "로보월드", "스마트공장",
           "드론쇼", "국제물류산업대전", "반도체대전", "ADEX"]
PAIR_ZH = ["慕尼黑上海电子展", "工博会", "广交会", "进博会", "汽车零部件", "国际机器人展"]
PAIR_DE = ["Hannover Messe", "electronica", "SPS", "embedded world", "productronica", "Automechanika"]


def queries_for(key, name, country, aliases):
    """경쟁사 하나에 대한 검색어 → [(엔진, 질의, 언어)]"""
    qs = []
    a0 = aliases[0] if aliases[0].startswith('"') else '"%s"' % aliases[0]
    # 1) 일반형
    qs.append(("gn", "%s %s" % (a0, EN_SHOW), "en"))
    qs.append(("gn", '%s ("will exhibit" OR "to showcase" OR "will showcase" OR "on display at" '
                     'OR "booth number" OR "at booth")' % a0, "en"))
    qs.append(("gn", "%s (exhibitor OR keynote OR demo OR unveil) (expo OR show OR fair)" % a0, "en"))
    # 2) 기간형 — 옛 흔적
    for sp in SPANS:
        qs.append(("gn", "%s %s %s" % (a0, EN_SHOW, sp), "en"))
    # 3) 짝지음형
    for fair in PAIR_EN:
        qs.append(("gn", '%s "%s"' % (a0, fair), "en"))
    # 4) 현지어형
    jp = [a for a in aliases[1:] if re.search(r"[ぁ-んァ-ヶ]", a)]
    cn = [a for a in aliases[1:] if re.search(r"[一-龯]", a) and a not in jp]
    kr = [a for a in aliases[1:] if re.search(r"[가-힣]", a)]
    if country in ("JP",) or jp:
        base = '"%s"' % (jp[0] if jp else aliases[0])
        qs.append(("gn", "%s (出展 OR 展示会 OR ブース OR 見本市)" % base, "ja"))
        qs.append(("gn", "%s 出展 after:2012-01-01 before:2020-01-01" % base, "ja"))
        for fair in PAIR_JA:
            qs.append(("gn", '%s "%s"' % (base, fair), "ja"))
    if country in ("CN", "TW") or cn:
        base = '"%s"' % (cn[0] if cn else aliases[0])
        qs.append(("gn", "%s (参展 OR 展会 OR 展位 OR 亮相)" % base, "zh"))
        for fair in PAIR_ZH:
            qs.append(("gn", '%s "%s"' % (base, fair), "zh"))
        if country == "TW":
            qs.append(("gn", "%s (參展 OR 展覽 OR 攤位)" % base, "tw"))
    if kr or country == "KR":
        base = '"%s"' % (kr[0] if kr else aliases[0])
        qs.append(("gn", "%s (전시회 OR 부스 OR 출품 OR 참가 OR 박람회)" % base, "ko"))
        for fair in PAIR_KO:
            qs.append(("gn", '%s "%s"' % (base, fair), "ko"))
    else:
        # 한국 기사에 영문명으로 나오는 경우도 훑는다
        qs.append(("gn", "%s (전시회 OR 부스 OR 출품)" % a0, "ko"))
    if country in ("DE", "CH", "AT"):
        qs.append(("gn", "%s (Messe OR Fachmesse OR Stand OR Ausstellung)" % a0, "de"))
        for fair in PAIR_DE:
            qs.append(("gn", '%s "%s"' % (a0, fair), "de"))
    qs.append(("bn", "%s booth exhibition" % a0, "en"))
    if QUICK:
        qs = [q for q in qs if "after:" not in q[1]][:12]
    return qs


# ================================================================ 본체
def collect():
    jobs = []
    for key, name, country, aliases, sig in TARGETS:
        for eng, q, lang in queries_for(key, name, country, aliases):
            jobs.append((key, eng, q, lang))
    # 구글 뉴스는 한 번에 2,000건 넘게 물으면 뒤쪽이 빈 응답으로 온다. 그래서 하루 한도를 두고
    # **날짜에 따라 다른 조각**을 돌린다 — 받은 글은 data/traces_raw.json 에 쌓이므로
    # 며칠이면 전체를 한 바퀴 돌고, 그 뒤로는 계속 새것만 더해진다.
    cap = 120 if QUICK else 1200
    total = len(jobs)
    if total > cap:
        start = (date.today().toordinal() * cap) % total
        jobs = (jobs + jobs)[start:start + cap]
    log("검색 %d건 (전체 %d건 중 오늘 몫 · 경쟁사 %d곳)" % (len(jobs), total, len(TARGETS)))

    got = []
    lock = threading.Lock()
    done = [0]

    def work(job):
        key, eng, q, lang = job
        if BLOCKED["stop"]:
            return 0
        if eng == "gn":
            items = gnews(q, lang)
            # 40건 연속으로 아무것도 안 오면 한도에 걸린 것 — 남은 질의는 접고 내일 이어서 한다
            with lock:
                BLOCKED["n"] = 0 if items else BLOCKED["n"] + 1
                if BLOCKED["n"] >= 40 and not BLOCKED["stop"]:
                    BLOCKED["stop"] = True
                    log("  검색엔진이 한도를 걸었습니다 — 남은 질의는 접습니다(내일 이어서 받습니다)")
        elif eng == "bn":
            items = bingnews(q)
        elif eng == "bw":
            items = bingweb(q) or ddg(q)
            time.sleep(0.4)
        else:
            items = []
        for it in items:
            it["rival"] = key
            it["engine"] = eng
        with lock:
            got.extend(items)
            done[0] += 1
            if done[0] % 50 == 0:
                log("  … %d/%d 질의, 원문 %d건" % (done[0], len(jobs), len(got)))
        return len(items)

    with ThreadPool(6) as pool:
        pool.map(work, jobs)
    log("검색 결과 %d건" % len(got))

    log("회사 소식란 읽는 중")
    got += run_newsrooms()
    li = linkedin_ads()
    if li:
        log("링크드인 광고 %d건 (data/linkedin_ads.json)" % len(li))
        got += li
    return got


MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def parse_date(s):
    if not s:
        return ""
    m = re.search(r"(\d{1,2})\s+([A-Z][a-z]{2})\s+(20\d\d)", s)
    if m:
        return "%s-%02d-%02d" % (m.group(3), MONTHS.get(m.group(2), 1), int(m.group(1)))
    m = re.search(r"(20\d\d)[./-](\d{1,2})[./-](\d{1,2})", s)
    if m:
        return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(20\d\d)年(\d{1,2})月(\d{1,2})日", s)
    if m:
        return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))
    m = re.search(r"\b(20\d\d)\b", s)
    return m.group(1) if m else ""


def refine(raw):
    """경쟁사 이름이 진짜 들어 있는 글만 남기고, 전시회를 찾아 붙인다."""
    sigs = {t[0]: re.compile(t[4], re.I) for t in TARGETS}
    seen_url = {}
    rows = []
    for it in raw:
        key = it.get("rival")
        if key not in sigs:
            continue
        text = " ".join([it.get("title", ""), it.get("desc", "")])
        if not text.strip():
            continue
        if it.get("kind") not in ("official", "ad") and not sigs[key].search(text):
            continue                       # 이름이 안 보이면 버린다 (검색엔진 오탐)
        if NOISE.search(text) and not SHOW_HINT.search(text):
            continue
        fairs = find_fairs(text)
        if not fairs:
            fairs = guess_fairs(text)
        hint = bool(SHOW_HINT.search(text))
        if not fairs and not hint and it.get("kind") != "ad":
            continue                       # 전시회 얘기가 아예 아닌 글
        url = (it.get("url") or "").split("&ved=")[0]
        d = parse_date(it.get("date") or "")
        ukey = (key, url)
        if ukey in seen_url:
            continue
        seen_url[ukey] = 1
        rows.append({
            "rival": key, "title": it.get("title", "")[:300], "desc": it.get("desc", "")[:400],
            "url": url, "date": d, "site": it.get("site", "")[:60], "kind": it.get("kind", "news"),
            "engine": it.get("engine", ""), "fairs": fairs, "hint": hint, "q": it.get("q", "")[:120],
        })
    return rows


def _norm(t):
    return re.sub(r"[^0-9a-z가-힣ぁ-んァ-ヶ一-龯]+", "", (t or "").lower())


def known_pairs():
    """rivals.py 가 이미 출품사 명단으로 확인해 둔 (경쟁사, 전시회) 짝."""
    out = set()
    try:
        riv = json.load(open(os.path.join(HERE, "data", "rivals.json"), encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return out
    for r in riv.get("records", []):
        out.add((r.get("rival"), _norm(r.get("match") or "")))
    return out


def pair_rows(rows):
    """(경쟁사 × 전시회 × 연도) 로 묶는다 — 화면의 핵심 표."""
    known = known_pairs()
    pairs = {}
    for r in rows:
        for f in r["fairs"]:
            y = f["year"] or (int(r["date"][:4]) if r["date"][:4].isdigit() else 0)
            k = (r["rival"], f["fair"], y)
            nf = _norm(f["fair"])
            seen_before = any(kr == r["rival"] and kf and (kf in nf or nf in kf) for kr, kf in known)
            p = pairs.setdefault(k, {"rival": r["rival"], "fair": f["fair"], "year": y,
                                     "field": f["field"], "how": f.get("src", ""),
                                     "known": seen_before, "n": 0, "src": []})
            p["n"] += 1
            if len(p["src"]) < 6 and r["url"] not in [x["u"] for x in p["src"]]:
                p["src"].append({"t": r["title"][:160], "u": r["url"], "d": r["date"],
                                 "s": r["site"], "k": r["kind"]})
    # 같은 경쟁사·같은 해에서 "IRCE"와 "IRCE Expo"처럼 겹치는 이름은 하나로 합친다.
    # 직접 정리한 사전 이름(how='직접')을 우선 남기고, 없으면 긴 쪽(정보가 많은 쪽)을 남긴다.
    merged = {}
    for p in sorted(pairs.values(), key=lambda x: (x["how"] != "직접", -len(x["fair"]))):
        g = (p["rival"], p["year"])
        nf = _norm(p["fair"])
        host = None
        for q in merged.get(g, []):
            nq = _norm(q["fair"])
            if len(nf) >= 4 and len(nq) >= 4 and (nf in nq or nq in nf):
                host = q
                break
        if host:
            host["n"] += p["n"]
            host["known"] = host["known"] or p["known"]
            for s2 in p["src"]:
                if len(host["src"]) < 8 and s2["u"] not in [x["u"] for x in host["src"]]:
                    host["src"].append(s2)
        else:
            merged.setdefault(g, []).append(p)
    out = [p for g in merged.values() for p in g]
    out.sort(key=lambda p: (-p["year"], -p["n"], p["rival"]))
    return out


# ---------------------------------------------------------------- 한국어 번역
TR_URL = "https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=auto&tl=ko"
_tr_lock = threading.Lock()


def _tr_one(text):
    data = urllib.parse.urlencode({"q": text}).encode()
    req = urllib.request.Request(TR_URL, data=data, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=40, context=CTX).read().decode("utf-8", "replace"))
            return clean(d[0][0] if isinstance(d[0], list) else d[0])
        except Exception as e:  # noqa: BLE001
            time.sleep(20 * (attempt + 1) if "429" in str(e) else 2)
    return ""


def translate(rows, budget=1500):
    try:
        cache = json.load(open(KO_CACHE, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        cache = {}
    ko_re = re.compile(r"[가-힣]")
    todo = {}
    for r in rows:
        t = r["title"]
        if t and not ko_re.search(t):
            h = hashlib.sha1(t.encode("utf-8")).hexdigest()
            if h not in cache:
                todo[h] = t
    items = list(todo.items())[:budget]
    if items:
        log("한국어 번역 %d문장 (캐시 %d)" % (len(items), len(cache)))

        def work(pair):
            h, t = pair
            r = _tr_one(t)
            if r:
                with _tr_lock:
                    cache[h] = r
            time.sleep(0.25)
        with ThreadPool(4) as pool:
            pool.map(work, items)
        json.dump(cache, open(KO_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    n = 0
    for r in rows:
        t = r["title"]
        if not t or ko_re.search(t):
            r["ko"] = ""
        else:
            r["ko"] = cache.get(hashlib.sha1(t.encode("utf-8")).hexdigest(), "")
            n += 1 if r["ko"] else 0
    return n


def main():
    t0 = time.time()
    raw = [] if OFFLINE else collect()
    # 지난 수집분과 합친다 — 검색엔진이 하루 막혀도 쌓인 흔적은 남는다
    try:
        old = json.load(open(RAW_CACHE, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        old = []
    merged, seen = [], set()
    for it in raw + old:
        k = (it.get("rival"), (it.get("url") or "").split("&ved=")[0])
        if k in seen:
            continue
        seen.add(k)
        merged.append(it)
    if OFFLINE:
        li = linkedin_ads()
        have = {(x.get("rival"), x.get("url")) for x in merged}
        merged += [x for x in li if (x.get("rival"), x.get("url")) not in have]
    log("원문 %d건 (이번 %d + 지난 %d)" % (len(merged), len(raw), len(old)))
    if not OFFLINE:
        json.dump(merged[:60000], open(RAW_CACHE, "w", encoding="utf-8"), ensure_ascii=False)

    rows = refine(merged)
    log("경쟁사 이름이 확인된 글 %d건" % len(rows))
    translate(rows)
    pairs = pair_rows(rows)
    log("경쟁사 × 전시회 흔적 %d건" % len(pairs))

    by_r = {}
    for p in pairs:
        by_r.setdefault(p["rival"], set()).add(p["fair"])
    for key, name, country, aliases, sig in TARGETS:
        log("  %-12s 전시회 %3d곳 · 글 %4d건" % (
            key, len(by_r.get(key, ())), sum(1 for r in rows if r["rival"] == key)))

    data = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "rivals": [{"key": k, "name": n, "country": c, "alias": a} for k, n, c, a, s in TARGETS],
        "fields": [{"key": k, "name": v} for k, v in FIELD_NAME.items()],
        "pairs": pairs,
        "rows": sorted(rows, key=lambda r: (r["date"] or "0000"), reverse=True),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    with open(APPOUT, "w", encoding="utf-8") as f:
        f.write("window.TRACES=")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    log("완료 %.0fs · app-traces.js %dKB" % (time.time() - t0, os.path.getsize(APPOUT) // 1024))


if __name__ == "__main__":
    main()
