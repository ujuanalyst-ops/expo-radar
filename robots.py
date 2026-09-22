#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""로봇 전시회 출품사 레이더 — 전세계 로봇 전시회의 **출품사 명단을 통째로** 모아 회사별로 정리한다.

rivals.py가 '우리 경쟁사만' 골라내는 것과 달리, 여기서는 명단을 버리지 않고 회사마다
  - 어느 전시회(출처)에 나왔는지 · 부스
  - 무엇을 만드는 회사인지(소개글) · 무엇을 전시했는지(전시 하이라이트)
  - 품목 카테고리 · 대상 산업 · 분야(본체/부품/SW/응용) · 소개글에서 뽑은 강점 문구
를 붙여 한 줄로 만든다. 분류는 소개글·태그의 키워드 규칙(영·일·한·중)으로 하므로
"소개글이 짧은 회사는 분류가 비어 있을 수 있다"는 점을 화면에 밝힌다.

출처(플랫폼):
  mys   MapYourShow — Automate(북미 최대 로봇·자동화), ProMat(물류 자동화·AMR)
  irex  国際ロボット展 iREX(도쿄) — 출품사 그리드 API, 소개글·전시 분야 태그 포함
  aut   automatica(뮌헨) — 출품사 포털의 엑셀 내려받기(회사·홀·도시·국가)

전세계 로봇 전시회 목록 자체는 data/expos.json(전시회 DB)에서 제목으로 골라 함께 싣는다.
명단을 웹에 열지 않는 전시회(로보월드·ROBEX·WRC·CIROS 등)는 '명단 미확보'로 표시만 한다.

  python3 robots.py            # 수집 → data/robots.json + app-robots.js
  python3 robots.py --dump     # 전시회별 요약만 출력
"""

import html as _html
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
import zlib
from collections import Counter
from datetime import datetime
from multiprocessing.dummy import Pool as ThreadPool

import countries
from rivals import UA, clean, get, norm_co, opener

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "robots.json")
APP = os.path.join(HERE, "app-robots.js")
EXPOS = os.path.join(HERE, "data", "expos.json")
KO_CACHE = os.path.join(HERE, "data", "ko_cache.json")
AUT_CACHE = os.path.join(HERE, "data", "aut_cache.json")

# ================================================================ 전시회 목록
# scope: robot = 로봇 전시회라 출품사 전부 싣는다 / filter = 종합 전시회라 로봇 관련 업체만 남긴다
FAIRS = [
    {"key": "automate27", "platform": "mys", "host": "automate27.mapyourshow.com",
     "title": "Automate 2027", "when": "2027-05", "kind": "confirmed", "scope": "robot",
     "city": "Chicago", "country": "US", "note": "북미 최대 로봇·자동화 (A3 주최). 소개글은 회차 임박 시 채워진다"},
    {"key": "automate26", "platform": "mys", "host": "automate26.mapyourshow.com",
     "title": "Automate 2026", "when": "2026-06", "kind": "history", "scope": "robot",
     "city": "Detroit", "country": "US", "note": "직전 회차 — 출품사 소개글 포함"},
    {"key": "irex25", "platform": "irex", "url": "https://irex.nikkan.co.jp/exhibitor/",
     "title": "iREX 2025 国際ロボット展", "when": "2025-12", "kind": "history", "scope": "robot",
     "city": "Tokyo", "country": "JP", "note": "세계 최대 로봇 전문 전시회 (격년, 다음 2027-11). 소개글·전시 분야 태그 포함"},
    {"key": "automatica25", "platform": "aut", "url": "https://exhibitors.automatica-munich.com/en/exhibitors-details/exhibitors-brands",
     "title": "automatica 2025", "when": "2025-06", "kind": "history", "scope": "robot",
     "city": "Munich", "country": "DE", "note": "유럽 최대 로봇·자동화 (격년, 다음 2027-06). 홈페이지·제품군·회사소개(독일어 多) 포함"},
    {"key": "promat27", "platform": "mys", "host": "pm2027.mapyourshow.com",
     "title": "ProMat 2027", "when": "2027-03", "kind": "confirmed", "scope": "filter",
     "city": "Chicago", "country": "US", "note": "북미 최대 물류 자동화 — 로봇·AMR·피킹 관련 업체만 추림"},
    {"key": "promat25", "platform": "mys", "host": "pm2025.mapyourshow.com",
     "title": "ProMat 2025", "when": "2025-03", "kind": "history", "scope": "filter",
     "city": "Chicago", "country": "US", "note": "직전 회차 — 로봇 관련 업체만 추림"},
    # ── 한국
    {"key": "robotworld26", "platform": "robotworld", "url": "https://www.robotworld.or.kr/visitors/list_of_exhibitors.php",
     "title": "로보월드 2026", "when": "2026-11", "kind": "confirmed", "scope": "robot",
     "city": "고양(킨텍스)", "country": "KR", "note": "국내 최대 로봇 전문전 — 부스·전시분야·홈페이지·회사소개 포함"},
    {"key": "nextai26", "platform": "nextai", "url": "https://nextaikorea.com/visitors/companies",
     "title": "THE NEXT AI 피지컬AI·스마트팩토리산업전 2026", "when": "2026-10", "kind": "confirmed", "scope": "robot",
     "city": "창원", "country": "KR", "note": "신설 전시회 — 소개·출품내역·홈페이지 포함, 부스 미공개"},
    {"key": "robottech26", "platform": "exporum", "url": "https://smarttechkorea.com/exhibitor-directory",
     "api": "https://floorplan.exporum.com/api/exhibitors?exhibitionId=2", "zone": "ROBOT TECH SHOW",
     "title": "Robot Tech Show 2026 (스마트테크코리아)", "when": "2026-06", "kind": "history", "scope": "robot",
     "city": "서울(코엑스)", "country": "KR", "note": "직전 회차 — 회사명·부스만 (다음 2027-06)"},
    {"key": "robex25", "platform": "fixkorea", "url": "https://fixkorea.or.kr/participation/bis_info_list.asp?site=robex&yy=2025&lang=kor",
     "title": "ROBEX 대구국제로봇산업전 2025", "when": "2025-10", "kind": "history", "scope": "robot",
     "city": "대구(엑스코)", "country": "KR", "note": "직전 회차 — FIX 디렉토리 등록 업체만(실제 출품사의 일부), 전시품목·홈페이지 포함"},
    # ── 중국·동남아
    {"key": "wrc26", "platform": "wrc", "url": "https://www.worldrobotconference.com/expo/",
     "title": "WRC 세계로봇대회 2026 (베이징)", "when": "2026-08", "kind": "history", "scope": "robot",
     "city": "Beijing", "country": "CN", "note": "직전 회차 — 관별 명단·부스·회사소개(중국어) 포함 (다음 2027-08)"},
    {"key": "fairplus26", "platform": "fairplus", "url": "https://fairplus.cn/exhibitor-list/",
     "api": "https://fairplus.cn/wp-json/wp/v2/exhibitor?per_page=100&exhibitor_year=67",
     "title": "FAIR plus 선전 로봇산업체인전 2026", "when": "2026-04", "kind": "history", "scope": "robot",
     "city": "Shenzhen", "country": "CN", "note": "직전 회차 — 회사소개(중국어) 포함, 부스 미공개 (다음 2027-04)"},
    {"key": "hrte26", "platform": "hrte", "url": "https://www.arte.net.cn/about_36/",
     "title": "HRTE 항저우 휴머노이드로봇기술전 2026", "when": "2026-05", "kind": "history", "scope": "robot",
     "city": "Hangzhou", "country": "CN", "note": "직전 회차 — 회사명(중·영)·부스만 (다음 2027-05)"},
    {"key": "vimf_bn26", "platform": "vimf", "url": "https://vimf.vn/danh-sach-don-vi-tham-gia/",
     "api": "https://vimf.vn/wp-json/wp/v2/posts?categories=222&per_page=100&_fields=id,title,link,content",
     "title": "RAV Robotic & Automation Vietnam 2026 (VIMF 박닌)", "when": "2026-11", "kind": "confirmed", "scope": "filter",
     "city": "Bac Ninh", "country": "VN", "note": "VIMF 산업전과 통합 명단 — 로봇·자동화 관련 업체만 추림, 소개·제품 포함"},
    # ── 지난 회차·아카이브로 채운 곳 (현 회차 명단을 주최측이 안 여는 전시회)
    {"key": "roboticssummit23", "platform": "expofp",
     "api": "https://roboticsdtboston2023.expofp.com/data/data.js",
     "url": "https://www.roboticssummit.com/exhibit-floor/",
     "title": "Robotics Summit & Expo 2023 (보스턴)", "when": "2023-05", "kind": "history", "scope": "robot",
     "city": "Boston", "country": "US", "note": "2027 회차 명단이 아직 안 열려 지난 회차(ExpoFP 배치도)로 대체 — 홈페이지·국가·소개 포함"},
    {"key": "robobusiness23", "platform": "expofp",
     "api": "https://robobusinessdt2023.expofp.com/data/data.js",
     "url": "https://www.robobusiness.com/exhibit-floor/",
     "title": "RoboBusiness 2023 (산타클라라)", "when": "2023-10", "kind": "history", "scope": "robot",
     "city": "Santa Clara", "country": "US", "note": "2026 회차 배치도 미공개 — 지난 회차 명단(회사명·부스)"},
    {"key": "r4m24", "platform": "pdflist",
     "api": "https://robot4manufacturing.com/images/2024/Liste_provisoire_des_exposants_R4M_2024.pdf",
     "url": "https://robot4manufacturing.com/en/exhibitors",
     "title": "ROBOT4MANUFACTURING 2024 (라로슈쉬르용)", "when": "2024-11", "kind": "history", "scope": "robot",
     "city": "La Roche-sur-Yon", "country": "FR", "note": "2026 명단 미발표 — 주최측이 올린 2024 회차 PDF 명단에서 추출(국가·홈페이지·소개)"},
    {"key": "tairos26", "platform": "wayback_tairos",
     "api": "https://web.archive.org/web/20260609062150/https://tairos.chanchao.com.tw/VisitorExhibitor",
     "url": "https://tairos.chanchao.com.tw/VisitorExhibitor",
     "title": "TAIROS 2026 (타이베이) — 일부", "when": "2026-08", "kind": "history", "scope": "robot",
     "city": "Taipei", "country": "TW", "note": "주최측 사이트가 Cloudflare 봇 차단 — 인터넷 아카이브에 남은 목록 1쪽(전체 827곳 중 20곳)만"},
    # ── 유럽
    {"key": "robotics_si27", "platform": "ungerboeck",
     "aat": "4a45536f7153673739724d2f726556383664504743536d4a376d4f766f7a307165663779673555526273513d",
     "url": "https://icm.si/events/mte-slovenia-exhibitors/",
     "title": "Robotics Slovenia 2027 (IFAM·INTRONIKA·ROBOTICS·MTE)", "when": "2027-01", "kind": "confirmed", "scope": "robot",
     "city": "Ljubljana", "country": "SI", "note": "자동화·전자·로봇 합동전 — 홈페이지·제품군·국가 포함"},
    {"key": "robotics_rs26", "platform": "ungerboeck",
     "aat": "364b554e3741596b2b362b426c724a386d57486350594d51777a2f4d79333071356e58724d316b716377413d",
     "url": "https://icm.si/events/robotics-serbia-novi-sad/",
     "title": "Robotics Serbia 2026 (IFAM·INTRONIKA·ROBOTICS·MTE)", "when": "2026-10", "kind": "confirmed", "scope": "robot",
     "city": "Novi Sad", "country": "RS", "note": "자동화·전자·로봇 합동전 — 홈페이지·제품군·국가 포함"},
    {"key": "roboticswarsaw26", "platform": "ptak", "url": "https://roboticswarsaw.com/katalog-wystawcow-2026/",
     "title": "ROBOTICS Warsaw 2026", "when": "2026-02", "kind": "history", "scope": "robot",
     "city": "Warsaw(Nadarzyn)", "country": "PL", "note": "직전 회차 — 회사명·부스만 (다음 2027-02)"},
    {"key": "warsawautomatica26", "platform": "ptak", "url": "https://automaticaexpo.com/katalog-wystawcow-2026/",
     "title": "Warsaw Industry Automatica 2026", "when": "2026-05", "kind": "history", "scope": "robot",
     "city": "Warsaw(Nadarzyn)", "country": "PL", "note": "직전 회차 — 회사명·부스만 (다음 2027-05)"},
    {"key": "stom_robotics26", "platform": "kielce",
     "api": "https://www.targikielce.pl/api/modules/exhibitors-list/search/53050/78336/en", "alias": "714",
     "url": "https://www.targikielce.pl/en/industrial-spring-2026/list-of-exhibitors?aliases=714",
     "title": "STOM-ROBOTICS 2026 (Kielce Industrial Spring)", "when": "2026-03", "kind": "history", "scope": "robot",
     "city": "Kielce", "country": "PL", "note": "직전 회차 — 회사명·국가·부스 (다음 2027-04)"},
]

# 명단을 웹에 공개하지 않는 로봇 전시회 — 화면에 '미확보' 대신 이유를 보여준다 (사이트를 직접 확인한 결과)
NO_LIST = [
    ("mobile robotics summit", "주최측(Logistics Summit GmbH)이 출품사 명단을 공개하지 않음 — 출품 안내 페이지만 있음"),
    ("russia robotics week", "포럼 성격 행사 — PDF 안내서만 있고 출품사 명단 없음"),
    ("robotech expo", "주최측 사이트(robotechexpo.com)에 출품사 명단 페이지가 없음 — 후원사 로고만"),
    ("ciros", "주최측 사이트(ciros.com.cn)가 폐쇄 상태(모든 페이지 404) — 온라인 명단 없음"),
    ("aiconfexpo", "주최측 사이트(sysbh.cn)의 참展명록 페이지가 빈 틀 — 명단 미발표"),
    ("체화지능", "주최측 사이트(sysbh.cn)의 참展명록 페이지가 빈 틀 — 명단 미발표"),
    ("industrial japan", "RX Japan 신설 사이트 — 출품사 검색이 아직 없음(열려도 JS 전용 컴포넌트)"),
    ("산업장비 및 로봇 개발", "RX Japan 신설 사이트 — 출품사 검색이 아직 없음(열려도 JS 전용 컴포넌트)"),
    ("robot x @metalex", "RX Tradex 출품사 검색이 암호화 토큰 뒤에 있어 자동 수집 불가"),
    ("하노이 스마트 제조", "RX Tradex 베트남 사이트가 아직 없음(2027 신설)"),
    ("inti robotics", "INTI 통합 명단(346사)은 있으나 로봇 전시 소속 업체가 0 — 명단 미분류"),
]

# ================================================================ 분류 규칙 (영·일·한·중)
# (키, 표시이름, 정규식) — 회사 소개글·이름·전시회 태그에서 찾는다. 여러 개 붙을 수 있다.
CATS = [
    ("arm", "산업용 로봇(다관절·스카라·델타)",
     r"industrial robots?|articulated|6[- ]axis|six[- ]axis|\bscara\b|delta robots?|robot(ic)? arms?|"
     r"産業用ロボット|多関節|スカラ|垂直多関節|パラレルリンク|工业机器人|机械臂|산업용 ?로봇|다관절|스카라"),
    ("cobot", "협동로봇",
     r"\bcobots?\b|collaborative robots?|協働ロボット|协作机器人|협동 ?로봇"),
    ("amr", "이동로봇(AMR·AGV)",
     r"\bAMRs?\b|\bAGVs?\b|mobile robots?|autonomous mobile|自律走行|搬送ロボット|無人搬送|移动机器人|"
     r"자율주행 ?로봇|이동 ?로봇|무인운반"),
    ("humanoid", "휴머노이드·서비스로봇",
     r"humanoid|quadruped|legged|service robots?|delivery robots?|cleaning robots?|social robots?|"
     r"サービスロボット|人型|ヒューマノイド|配膳|人形机器人|服务机器人|휴머노이드|서비스 ?로봇|배송 ?로봇"),
    ("logi", "물류·창고 자동화",
     r"palletiz|depalletiz|warehouse|picking|sortation|sorter|\bAS/?RS\b|conveyor|goods[- ]to[- ]person|"
     r"fulfil+ment|intralogistic|material handling|物流|ピッキング|パレタイズ|倉庫|仕分け|搬送|"
     r"物流|仓储|分拣|물류|피킹|팔레타이징|창고"),
    ("vision", "머신비전·센서",
     r"machine vision|vision systems?|3d vision|\bcameras?\b|\blidar\b|force[- /]torque|\bsensors?\b|"
     r"センサ|ビジョン|カメラ|视觉|传感|비전|센서|카메라"),
    ("eoat", "그리퍼·엔드이펙터",
     r"grippers?|end[- ]effectors?|end[- ]of[- ]arm|\bEOAT\b|tool changers?|vacuum|suction|"
     r"ロボットハンド|グリッパ|ハンド|チャック|夹爪|抓手|末端执行器|그리퍼|엔드이펙터|툴체인저"),
    ("drive", "감속기·모터·액추에이터",
     r"reducers?|gearbox|gear|harmonic|cycloid|\bservo|\bmotors?\b|actuators?|encoders?|bearings?|"
     r"linear guide|ball screw|減速機|モータ|アクチュエータ|エンコーダ|ベアリング|直動|减速|电机|伺服|"
     r"감속기|모터|액추에이터|서보|엔코더"),
    ("ctrl", "제어·소프트웨어·AI",
     r"controllers?|\bPLC\b|software|simulation|offline programming|digital twin|\bAI\b|"
     r"machine learning|deep learning|\bROS\b|motion control|制御|ソフトウェア|シミュレーション|"
     r"人工知能|生成AI|控制|软件|人工智能|제어|소프트웨어|인공지능|시뮬레이션"),
    ("si", "시스템통합(SI)·자동화 솔루션",
     r"integrators?|integration|\bSIer\b|turn-?key|robot cells?|automation solutions?|system integ|"
     r"システムインテグレ|自動化システム|ロボットシステム|集成|自动化解决|시스템 ?통합|자동화 ?솔루션|로봇 ?시스템"),
    ("app", "용접·도장·가공 응용",
     r"welding|painting|deburring|polishing|grinding|machine tending|dispensing|assembly|"
     r"溶接|塗装|バリ取り|研磨|組立|焊接|喷涂|打磨|용접|도장|디버링|연마|조립"),
    ("periph", "안전·케이블·주변장치",
     r"safety|fenc(e|ing)|light curtains?|cables?|dress ?packs?|connectors?|slip rings?|cable carriers?|"
     r"安全|ケーブル|コネクタ|电缆|连接器|안전|케이블|커넥터"),
    ("med", "의료·재활·수술",
     r"surgical|medical|rehabilitation|exoskeleton|healthcare|nursing|手術|医療|リハビリ|介護|"
     r"医疗|康复|의료|수술|재활|간호"),
    ("special", "농업·건설·검사·드론",
     r"agricultur|farming|construction|inspection|underwater|drones?|\bUAV\b|disaster|"
     r"農業|建設|ドローン|点検|災害|农业|建筑|无人机|농업|건설|드론|검사"),
    ("robot", "로봇(세부 미분류)", r"(?!x)x"),   # 규칙엔 안 걸리지만 '로봇'을 말하는 회사 — classify()가 붙인다
    ("edu", "교육·연구·기관",
     r"universit|institute|research|education|association|laborator|大学|研究|協会|学会|"
     r"大学|研究院|대학|연구원|협회|교육"),
]
CATS_RE = [(k, n, re.compile(p, re.I)) for k, n, p in CATS]
CAT_NAME = {k: n for k, n, _ in CATS}

INDS = [
    ("auto", "자동차·EV", r"automotive|vehicle|\bEVs?\b|battery|自動車|汽车|电池|자동차|배터리"),
    ("elec", "전자·반도체", r"electronics?|semiconductor|\bPCB\b|wafer|display|電子|半導体|电子|半导体|전자|반도체"),
    ("logi", "물류·유통·이커머스", r"logistics|warehouse|e-?commerce|retail|distribution|物流|小売|物流|零售|물류|유통"),
    ("food", "식품·제약·포장", r"\bfood\b|beverage|pharma|packaging|cosmetic|食品|製薬|包装|食品|药|식품|제약|포장"),
    ("med", "의료·헬스케어", r"medical|hospital|healthcare|surgical|医療|病院|医疗|의료|병원"),
    ("aero", "항공·방산", r"aerospace|aircraft|defen[cs]e|航空|防衛|航空|航天|항공|방산"),
    ("metal", "금속·기계가공", r"metal|machining|\bCNC\b|foundry|forging|sheet metal|金属|加工|鋳造|金属|机械加工|금속|기계가공"),
    ("plastic", "플라스틱·성형", r"plastics?|injection mo(u)?ld|樹脂|成形|塑料|注塑|플라스틱|사출"),
    ("agri", "농업·식품생산", r"agricultur|farm|greenhouse|農業|农业|농업"),
    ("constr", "건설·인프라", r"construction|infrastructure|建設|インフラ|建筑|基建|건설|인프라"),
]
INDS_RE = [(k, n, re.compile(p, re.I)) for k, n, p in INDS]
IND_NAME = {k: n for k, n, _ in INDS}

# 분야(큰 묶음) — 카테고리에서 한 단계 올린 것. 앞에 있는 것이 우선.
FIELDS = [
    ("body", "🤖 로봇 본체", ("arm", "cobot", "amr", "humanoid", "robot")),
    ("parts", "⚙️ 부품·요소기술", ("drive", "vision", "eoat", "periph")),
    ("sw", "🧠 SW·제어·AI", ("ctrl",)),
    ("apply", "🏭 응용·SI·물류", ("si", "app", "logi", "med", "special")),
    ("etc", "📎 기타·기관", ("edu",)),
]
FIELD_NAME = {k: n for k, n, _ in FIELDS}

# 종합 전시회(ProMat)에서 로봇 관련 업체만 남길 때 쓰는 기준
ROBOT_RE = re.compile(
    r"robot|\bcobot|\bAMRs?\b|\bAGVs?\b|autonomous|humanoid|gripper|end[- ]effector|palletiz|"
    r"ロボット|机器人|로봇", re.I)

# 소개글에서 '강점' 문장을 뽑는 표지
STRONG_RE = re.compile(
    r"world'?s|global(ly)?|leading|largest|biggest|first|No\.? ?1|#1|pioneer|patent|award|"
    r"over \d+ years|\d+\+? years|\d+ countries|\bISO ?\d|founded in \d{4}|since \d{4}|"
    r"only (company|provider|supplier)|market leader|best[- ]in[- ]class|highest|fastest|"
    r"世界|リーディング|初|特許|受賞|年以上|創業|唯一|最大|最速|全球|领先|第一|专利|首|"
    r"세계|최초|1위|특허|수상|최대|유일", re.I)

SENT_SPLIT = re.compile(r"(?<=[.!?。！？])\s+|\r?\n+|・(?=\S)")

COUNTRY_RE = re.compile(r"株式会社|有限会社|合同会社|合資会社")
# 명단에 국가가 없을 때 법인명으로 짐작한다 — '출품 법인 기준'이라 본사와 다를 수 있다
NAME_COUNTRY = [
    ("US", r"\b(USA|U\.S\.A?\.?|America|Americas|North America)\b|\bInc\.?$|\bLLC\b|\bCorp(oration)?\.?$"),
    ("JP", r"\bJapan\b|\bNippon\b|株式会社|\bK\.K\.?\b"),
    ("DE", r"\bDeutschland\b|\bGmbH\b|\bAG$|\bGermany\b"),
    ("KR", r"\bKorea\b|한국|주식회사"),
    ("CN", r"\bChina\b|\bShenzhen\b|\bShanghai\b|\bSuzhou\b|\bBeijing\b|\bHangzhou\b|\bNingbo\b|有限公司"),
    ("TW", r"\bTaiwan\b"),
    ("IT", r"\bItalia\b|\bItaly\b|\bS\.?r\.?l\.?\b|\bS\.?p\.?A\.?\b"),
    ("CH", r"\bSwitzerland\b|\bSchweiz\b|\bSuisse\b"),
    ("FR", r"\bFrance\b|\bS\.?A\.?S\.?\b"),
    ("GB", r"\bUK\b|\bU\.K\.\b|\bBritain\b|\bLtd\.?$|\bLimited$"),
    ("NL", r"\bB\.?V\.?\b|\bNetherlands\b"),
    ("DK", r"\bA/S\b|\bDenmark\b"),
    ("SE", r"\bAB$|\bSweden\b"),
    ("CA", r"\bCanada\b"),
    ("IN", r"\bIndia\b|\bPvt\b"),
]
NAME_COUNTRY = [(c, re.compile(p)) for c, p in NAME_COUNTRY]


def guess_country(name):
    for c, rx in NAME_COUNTRY:
        if rx.search(name or ""):
            return c
    return ""
TAG = re.compile(r"<[^>]+>")


# ================================================================ 수집기
def fetch_mys(f):
    """MapYourShow — 갤러리로 쿠키를 받은 뒤 검색 API. rivals.fetch_mys보다 소개글을 길게 남긴다.
    상세 페이지(홈페이지)는 AWS WAF 봇 차단이라 못 읽지만, **제품 카테고리**는 카테고리별 검색을
    거꾸로 돌려(카테고리 → 출품사 목록) 업체마다 붙일 수 있다."""
    op = opener()
    base = f"https://{f['host']}/8_0"
    gallery = base + "/explore/exhibitor-gallery.cfm"
    try:
        get(op, gallery, timeout=40)
    except Exception:  # noqa: BLE001
        pass
    api = base + "/ajax/remote-proxy.cfm?action=search&searchtype=exhibitorgallery&searchsize=6000"
    raw = get(op, api, referer=gallery, timeout=120)
    d = json.loads(raw.decode("utf-8", "replace"))["DATA"]["results"]["exhibitor"]
    rows, by_id = [], {}
    for h in d.get("hit", []):
        fl = h.get("fields", {})
        booth = [b for b in (fl.get("boothsdisplay_la") or []) if "random" not in str(b)]
        eid = str(fl.get("exhid_l") or "")
        r = {"name": clean(fl.get("exhname_t")), "booth": booth[0] if booth else "",
             "desc": clean(TAG.sub(" ", fl.get("exhdesc_t") or ""))[:1500], "show": "", "tags": [], "country": "",
             "src": f"{base}/exhibitor/exhibitor-details.cfm?exhid={eid}" if eid else gallery}
        rows.append(r)
        by_id[eid] = r
    # 카테고리 사전 → 카테고리별 검색 → 업체에 태그로
    try:
        cats = json.loads(get(op, base + "/ajax/remote-proxy.cfm?action=getsearchoptions&function=getsearchcategories&exhibitorgallery=true",
                              referer=gallery, timeout=60).decode("utf-8", "replace")).get("DATA") or []
    except Exception:  # noqa: BLE001
        cats = []

    def one_cat(c):
        try:
            cd = json.loads(get(op, api + "&categories=" + urllib.parse.quote(str(c["fieldvalue"])),
                                referer=gallery, timeout=90).decode("utf-8", "replace"))["DATA"]["results"]["exhibitor"]
        except Exception:  # noqa: BLE001
            return
        for h in cd.get("hit", []):
            r = by_id.get(str(h.get("fields", {}).get("exhid_l") or ""))
            if r is not None and len(r["tags"]) < 12:
                r["tags"].append(clean(c.get("fielddisplay")))
    with ThreadPool(4) as pool:
        pool.map(one_cat, [c for c in cats if c.get("fieldvalue")])
    return rows, int(d.get("found") or len(rows)), gallery


def fetch_irex(f):
    """iREX — 목록 화면이 스크롤할 때 부르는 그리드 API를 offset 60씩 끝까지 부른다."""
    op = opener()
    api = "https://irex.nikkan.co.jp/api/parts/get_exhibitor_grid"
    get(op, f["url"], timeout=60)                      # 세션 쿠키 — 없으면 API가 403
    rows, seen, offset = [], set(), 0
    while True:
        body = urllib.parse.urlencode({"count": offset, "query": json.dumps({"search_category": []})}).encode()
        req = urllib.request.Request(api, data=body, headers={
            "User-Agent": UA, "X-Requested-With": "XMLHttpRequest", "Referer": f["url"],
            "Accept": "application/json, text/javascript, */*; q=0.01", "Origin": "https://irex.nikkan.co.jp"})
        d = json.loads(op.open(req, timeout=60).read().decode("utf-8", "replace"))
        batch = d.get("result") or []
        if not batch:
            break
        new = 0
        for x in batch:
            cid = x.get("t_company_id")
            if cid in seen:
                continue
            seen.add(cid)
            new += 1
            hall = x.get("hall") or {}
            labels = x.get("categoryLabels") or {}
            tags = []
            for lab in (labels.values() if isinstance(labels, dict) else []):
                tags.append(lab.get("category_name_en") or lab.get("category_name") or "")
                tags += [s for s in (lab.get("sub_category_name_en") or [])]
            name_ja, name_en = clean(x.get("company_name")), clean(x.get("company_en"))
            rows.append({"name": name_en or name_ja, "name_ja": name_ja, "booth": clean(x.get("booth_number")),
                         "desc": clean(hall.get("exhibit_detail"))[:1500],
                         "show": clean(hall.get("exhibit_highlights"))[:800],
                         "tags": [t for t in tags if t], "web": clean(x.get("company_homepage")),
                         "country": "JP" if COUNTRY_RE.search(name_ja) else "",
                         "src": f"https://irex.nikkan.co.jp/exhibitor/?item={cid}"})
        if not new:
            break
        offset += len(batch)
        time.sleep(0.3)
    return rows, len(rows), f["url"]


CELL = re.compile(r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', re.S)


TR = re.compile(r"<tr>(.*?)</tr>", re.S)
TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


def _txt(x):
    return clean(_html.unescape(TAG.sub(" ", x or "")))


AUT_HOST = "https://exhibitors.automatica-munich.com"


def _aut_xlsx(op, page):
    """목록 페이지의 엑셀 내려받기 링크(mode=xls) — 회사·홀/부스·도시·국가."""
    m = re.search(r'href="(/index\.php\?[^"]*mode%5D=xls[^"]*)"', page)
    if not m:
        return {}
    raw = get(op, AUT_HOST + m.group(1).replace("&amp;", "&"), timeout=120)
    if raw[:2] != b"PK":
        return {}
    zf = zipfile.ZipFile(io.BytesIO(raw))
    shared = [re.sub(r"<[^>]+>", "", x) for x in re.findall(
        r"<si>(.*?)</si>", zf.read("xl/sharedStrings.xml").decode("utf-8", "replace"), re.S)]
    sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8", "replace")
    out, first = {}, True
    for row in re.findall(r"<row[^>]*>(.*?)</row>", sheet, re.S):
        cells = {}
        for col, attrs, body in CELL.findall(row):
            v = re.search(r"<v>(.*?)</v>", body or "", re.S)
            if v:
                v = v.group(1)
                cells[col] = shared[int(v)] if 't="s"' in attrs and v.isdigit() else v
        name = _html.unescape(clean(cells.get("A")))
        if not name:
            continue
        if first:                              # 'Exhibitor list automatica 2025'
            first = False
            continue
        if name.lower() == "exhibitor":
            continue
        out[norm_co(name)] = {"booth": clean(cells.get("B")), "city": clean(cells.get("D")),
                              "country": countries.iso2(clean(cells.get("E"))) or ""}
    return out


def fetch_aut(f):
    """automatica 출품사 포털(TYPO3 nfmedb) — 목록을 20건씩 넘기며 업체 ID를 모으고,
    업체 상세 페이지에서 홈페이지·제품군·회사소개(독일어가 많음)·부스를 읽는다. 엑셀로 도시·국가를 보탠다."""
    op = opener()
    page = get(op, f["url"], timeout=60).decode("utf-8", "replace")
    extra = _aut_xlsx(op, page)
    fair_id = re.search(r"fair_id=(\d+)", page)
    fair_id = fair_id.group(1) if fair_id else "1966"
    ids, offset = {}, 0
    frag = page
    while frag:
        for i, ch in re.findall(r"exhibitorDetail/ID/(\d+)/\?cHash=([0-9a-f]+)", frag):
            ids.setdefault(i, ch)
        m = re.search(r"data-ilnoff='(\d+)'", frag)
        if not m or int(m.group(1)) <= offset or offset > 5000:
            break
        offset = int(m.group(1))
        q = ("/index.php?L=1&fair_id=" + fair_id + "&CMW=PassThrue&request[pluginName]=Exhibitors&request[controller]=Exhibitors"
             "&request[action]=defaultList&request[arguments][params][initializeWithEmptyQuery]=1"
             "&request[arguments][params][statsrch][aussteller_buchstfilter]=all&request[arguments][params][statsrch][aussteller_offset]=0"
             "&request[arguments][params][statsrch][aussteller_orderby]=ASC&request[arguments][params][statsrch][aussteller_sortby]=_title"
             f"&request[arguments][params][xoffset]={offset}&request[arguments][params][append]=1")
        try:
            frag = get(op, AUT_HOST + q.replace("[", "%5B").replace("]", "%5D"), referer=f["url"], timeout=60).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            break

    try:
        cache = json.load(open(AUT_CACHE, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        cache = {}

    def detail(item):
        i, ch = item
        u = f"{AUT_HOST}/en/exhibitors-details/exhibitors-brands/exhibitors-brands-details/exhibitorDetail/ID/{i}/?cHash={ch}"
        if i in cache:
            return dict(cache[i])
        try:
            d = get(op, u, timeout=60).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return None
        name = re.search(r"<h1[^>]*>(.*?)</h1>", d, re.S)
        name = _txt(name.group(1)) if name else ""
        if not name:
            return None
        web = re.search(r'Website:</div>\s*<div>\s*<a[^>]+href="([^"]+)"', d, re.S)
        desc = re.search(r'class="col-sm-12 firmenpraesentation-text">(.*?)</div>', d, re.S)
        booth = re.search(r'class="exhibitordetails-standdetails".*?<h3 class="mt-0">.*?</i>\s*([A-Z]\d\.\d+)</h3>', d, re.S)
        groups = []
        for li in re.findall(r'<li class="productitems">(.*?)</li>', d, re.S):
            path = [_txt(x) for x in re.findall(r'<span class="zusatzinfo small">\s*<a[^>]*>(.*?)</a>', li, re.S)]
            leaf = re.search(r'<div class="nomen_item">\s*<a[^>]*>(.*?)</a>', li, re.S)
            g = " > ".join(path + ([_txt(leaf.group(1))] if leaf else []))
            if g and g not in groups:
                groups.append(g)
        x = extra.get(norm_co(name), {})
        time.sleep(0.05)
        row = {"name": name, "booth": (booth.group(1) if booth else x.get("booth", ""))[:24],
               "desc": _txt(desc.group(1))[:1500] if desc else "", "show": "", "tags": groups[:12],
               "web": web.group(1) if web else "", "city": x.get("city", ""), "country": x.get("country", ""),
               "src": u}
        cache[i] = row
        return dict(row)
    with ThreadPool(6) as pool:
        rows = [r for r in pool.map(detail, list(ids.items())) if r]
    json.dump(cache, open(AUT_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return rows, len(rows), f["url"]


def fetch_robotworld(f):
    """로보월드 — 참가업체 목록(10건씩 offset)과 업체별 팝업(회사소개·제품소개)을 읽는다."""
    op = opener()
    rows, offset, total = [], 0, None
    while True:
        t = get(op, f"{f['url']}?offset={offset}", timeout=60).decode("utf-8", "replace")
        m = re.search(r"총\s*([\d,]+)\s*개", t)
        total = int(m.group(1).replace(",", "")) if m else total
        body = re.search(r"<tbody>(.*?)</tbody>", t, re.S)
        got = 0
        for tr in TR.findall(body.group(1) if body else ""):
            td = [_txt(x) for x in TD.findall(tr)]
            idx = re.search(r"idx=(\d+)", tr)
            if len(td) < 7 or not td[2] or td[2] == "(주) 업체명":
                continue
            got += 1
            rows.append({"name": td[3] or td[2], "name_ja": td[2] if td[3] else "", "booth": td[0],
                         "desc": "", "show": "", "tags": [x for x in (td[4], td[5]) if x], "web": td[6],
                         "country": "KR" if re.search(r"주식회사|\(주\)|㈜|[가-힣]", td[2]) else "",
                         "src": f"https://www.robotworld.or.kr/visitors/pop_list_of_exhibitors.php?idx={idx.group(1)}" if idx else f["url"],
                         "_idx": idx.group(1) if idx else ""})
        offset += 10
        if not got or (total and offset >= total) or offset > 2000:
            break

    def detail(r):
        if not r["_idx"]:
            return
        try:
            d = get(op, r["src"], timeout=40).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return
        d = re.sub(r"<script.*?</script>|<style.*?</style>", " ", d, flags=re.S)
        kv = {}
        for th, td in re.findall(r"<th>(.*?)</th>\s*<td[^>]*>(.*?)</td>", d, re.S):
            kv[_txt(th)] = _txt(td)
        r["desc"] = (kv.get("회사소개(국문)") or kv.get("회사소개(영문)") or "")[:1500]
        r["show"] = " / ".join(v for k, v in kv.items() if k.startswith("제품소개") and v)[:800]
        r["web"] = r["web"] or kv.get("홈페이지", "")
        if not r["country"] and re.search(r"Korea|대한민국|경기|서울|인천|부산|대구|광주|대전|울산|경남|경북|충청|전라|강원", kv.get("국문주소", "") + kv.get("영문주소", "")):
            r["country"] = "KR"
        time.sleep(0.15)
    with ThreadPool(6) as pool:
        pool.map(detail, rows)
    for r in rows:
        r.pop("_idx", None)
    return rows, total or len(rows), f["url"]


def fetch_nextai(f):
    """THE NEXT AI(창원) — 업체 카드 12건씩 페이지, 상세에서 홈페이지·소개·출품내역."""
    op = opener()
    rows, page = [], 1
    while page < 60:
        t = get(op, f"{f['url']}?q=&page={page}", timeout=60).decode("utf-8", "replace")
        cards = re.findall(r'<a class="nx-company-card".*?</a>', t, re.S)
        if not cards:
            break
        for c in cards:
            ko = re.search(r'nx-company-name">([^<]*)', c)
            en = re.search(r'nx-company-name-en">([^<]*)', c)
            href = re.search(r'href="([^"]+)"', c)
            url = href.group(1) if href else ""
            if url.startswith("/"):
                url = "https://nextaikorea.com" + url
            name_ko = _txt(ko.group(1) if ko else "")
            name_en = _txt(en.group(1) if en else "")
            rows.append({"name": name_en or name_ko, "name_ja": name_ko if name_en else "", "booth": "",
                         "desc": "", "show": "", "tags": [], "web": "",
                         "country": "KR" if re.search(r"[가-힣]", name_ko) else "", "src": url or f["url"]})
        if f'page={page + 1}"' not in t:
            break
        page += 1

    def detail(r):
        if not r["src"].startswith("https://nextaikorea.com/visitors/companies/view"):
            return
        try:
            d = get(op, r["src"], timeout=40).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return
        site = re.search(r'class="nx-icon-btn"[^>]*href="(https?://[^"]+)"', d, re.S)
        secs = dict(re.findall(r"<h3>([^<]+)</h3>\s*<div class=\"nx-box\">\s*<div>(.*?)</div>", d, re.S))
        r["web"] = site.group(1) if site else ""
        r["desc"] = _txt(secs.get("소개/주요사업", ""))[:1500]
        r["show"] = _txt(secs.get("전시/출품 내역", ""))[:800]
        time.sleep(0.15)
    with ThreadPool(6) as pool:
        pool.map(detail, rows)
    return rows, len(rows), f["url"]


def fetch_exporum(f):
    """엑스포럼 부스 배치도 API(스마트테크코리아 계열) — 존(zone) 이름으로 로봇테크쇼 출품사만 고른다."""
    raw = get(opener(), f["api"], timeout=60)
    d = json.loads(raw.decode("utf-8", "replace"))
    rows = []
    for x in d:
        cats = [c.get("nameEn", "") for c in x.get("categories", [])]
        if f.get("zone") and not any(c.strip().upper() == f["zone"] for c in cats):
            continue
        ko, en = clean(x.get("nameKo")), clean(x.get("nameEn"))
        rows.append({"name": en or ko, "name_ja": ko if en else "", "booth": clean(x.get("boothNo")),
                     "desc": "", "show": "", "tags": [c.get("nameKo") or c.get("nameEn") for c in x.get("categories", [])],
                     "country": "KR" if re.search(r"[가-힣]", ko) else "", "src": f["url"]})
    return rows, len(rows), f["url"]


def fetch_fixkorea(f):
    """FIX(대구 기계·로봇 통합전) 참가업체 소개 — dl.list_box 단위, 회사명(국문<br>영문)·전시품목·홈페이지."""
    op = opener()
    rows, page = [], 1
    while page < 40:
        t = get(op, f"{f['url']}&gotoPage={page}", timeout=60).decode("utf-8", "replace")
        boxes = re.findall(r'<dl class="list_box".*?</dl>', t, re.S)
        if not boxes:
            break
        for box in boxes:
            tit = re.search(r'<dd class="tit">(.*?)</dd>', box, re.S)
            tit = re.sub(r"<!--.*?-->", "", tit.group(1) if tit else "", flags=re.S)
            names = [_txt(n) for n in re.split(r"<br\s*/?>", tit)]
            items = re.search(r'<dd class="cont_t[^"]*">(.*?)</dd>', box, re.S)
            site = re.search(r'<dd class="cont_site">.*?href="([^"]+)"', box, re.S)
            num = re.search(r"num=(\d+)", box)
            name_ko, name_en = names[0], (names[1] if len(names) > 1 else "")
            if not name_ko:
                continue
            rows.append({"name": name_en or name_ko, "name_ja": name_ko if name_en else "", "booth": "",
                         "desc": "", "show": _txt(items.group(1) if items else "")[:800], "tags": [],
                         "web": site.group(1) if site else "", "country": "KR",
                         "src": f"{f['url']}&num={num.group(1)}&mode=cont" if num else f["url"]})
        m = re.search(r"총\s*(\d+)\s*\(\s*\d+\s*/\s*(\d+)\s*\)", TAG.sub(" ", t))
        if m and page >= int(m.group(2)):
            break
        page += 1
    return rows, len(rows), f["url"]


def fetch_ungerboeck(f):
    """Momentus(Ungerboeck) 부스 배치도 앱 — 페이지에서 토큰을 얻어 VFPServer API를 부른다.
    GetInitialData로 전체 명단, GetExhibitorDetails로 홈페이지·제품군."""
    import uuid
    op = opener()
    h = get(op, "https://icm.ungerboeck.com/prod/app85.cshtml?aat=" + f["aat"], timeout=60).decode("utf-8", "replace")

    def g(k):
        m = re.search(k + r':\s*"([^"]*)"', h)
        return m.group(1) if m else ""
    tok, sid, ver = g("USIFPToken"), g("USISessionId"), g("USIVersion")
    cfg = int(re.search(r'"VFPConfigID","Value":(\d+)', h).group(1))

    def call(method, args):
        hd = {"User-Agent": UA, "Version": ver, "ShowActionID": "false", "ClientAppType": "2",
              "Authorization": "Bearer " + tok, "X-Nonce": str(uuid.uuid4()), "ClientAppCategory": "30",
              "WorkStationName": str(uuid.uuid4()), "WSID": sid, "AppCode": "VFP",
              "Accept": "application/json", "Content-Type": "application/json"}
        r = op.open(urllib.request.Request("https://icm.ungerboeck.com/PROD/api/VFPServer/" + method,
                                           data=json.dumps(args).encode(), headers=hd, method="POST"), timeout=60)
        return json.loads(json.loads(r.read().decode("utf-8", "replace"))[0])["ReturnObj"]
    init = call("GetInitialData", [None, None, None, cfg, "en", 0])
    pmap = init.get("ProductDescMap") or {}
    rows = []
    for e in init.get("ExhibitorList", []):
        prods = [pmap.get(str(c), pmap.get(c, "")) for c in (e.get("ProductCodes") or [])]
        rows.append({"name": clean(e.get("Name")), "booth": ", ".join(e.get("BoothNames") or [])[:24],
                     "desc": clean(e.get("Note"))[:1500], "show": "", "tags": [p for p in prods if p][:12],
                     "country": countries.iso2(e.get("CatCountryDesc") or "") or "", "web": "",
                     "src": f["url"], "_id": e.get("Id")})

    def detail(r):
        try:
            d = call("GetExhibitorDetails", [init["OrgCode"], init["EventID"], init["ConfigCode"], r["_id"], "*"])
        except Exception:  # noqa: BLE001
            return
        r["web"] = clean(d.get("WebsiteURL"))
        if r["web"] and not r["web"].startswith("http"):
            r["web"] = "http://" + r["web"]
        r["tags"] = r["tags"] or [p.get("Desc", "") for p in d.get("Products") or [] if p.get("Desc")][:12]
        r["country"] = r["country"] or countries.iso2(d.get("CatCountry") or "") or ""
        time.sleep(0.1)
    with ThreadPool(4) as pool:
        pool.map(detail, rows)
    for r in rows:
        r.pop("_id", None)
    return rows, len(rows), f["url"]


def fetch_ptak(f):
    """Ptak Warsaw Expo 워드프레스 출품사 카탈로그 — 이름·부스만 있는 정적 HTML."""
    t = get(opener(), f["url"], timeout=60).decode("utf-8", "replace")
    rows = []
    for blk in re.findall(r'(?s)class="exhibitors__container-list">(.*?)(?=class="exhibitors__container-list">|$)', t):
        n = re.search(r'list-text-name">(.*?)</h2>\s*<p>(.*?)</p>', blk, re.S)
        if not n:
            continue
        name = _txt(n.group(1))
        if name:
            rows.append({"name": name, "booth": _txt(n.group(2))[:24], "desc": "", "show": "", "tags": [],
                         "country": "", "src": f["url"]})
    return rows, len(rows), f["url"]


def fetch_kielce(f):
    """Targi Kielce 출품사 검색 API — HTML 조각(view)과 페이저를 JSON으로 준다."""
    op = opener()
    rows, page = [], 1
    while page < 60:
        u = f["api"] + "?" + urllib.parse.urlencode({"page": page, "filters[aliases][]": f["alias"]})
        req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "application/json",
                                                  "X-Requested-With": "XMLHttpRequest"})
        d = json.loads(op.open(req, timeout=60).read().decode("utf-8", "replace"))
        for tr in re.findall(r"(?s)<tr>(.*?)</tr>", d.get("view", "")):
            m = re.search(r'(?s)<div class="main-title[^"]*">(.*?)</div>', tr)
            if not m:
                continue
            href = re.search(r'href="([^"]+list-of-exhibitors/[^"]+)"', m.group(1))
            c = [_txt(x) for x in re.findall(r"(?s)<td>(.*?)</td>", tr)]
            rows.append({"name": _txt(m.group(1)), "booth": (c[3] if len(c) > 3 else "")[:24], "desc": "", "show": "",
                         "tags": [], "country": countries.iso2(c[2]) if len(c) > 2 else "",
                         "src": (href.group(1) if href else f["url"])})
        pager = (d.get("settings") or {}).get("pager") or {}
        if page >= int(pager.get("total") or 1):
            break
        page += 1
    return rows, len(rows), f["url"]


def fetch_wrc(f):
    """세계로봇대회(베이징) — 관(A~D)별 목록 한 페이지 + 업체 상세(부스·회사소개·전시품)."""
    op = opener()
    base = "https://www.worldrobotconference.com"
    t = get(op, f["url"], timeout=60).decode("utf-8", "replace")
    rows = []
    for hall, block in re.findall(r'expo-stadium-title">([^<]+)</h2>(.*?)</ul>', t, re.S):
        for cid, name in re.findall(r'href="/expo/company/(\d+)\.html"><img[^>]*alt="([^"]*)"', block):
            rows.append({"name": _html.unescape(name).strip(), "booth": "", "desc": "", "show": "", "tags": [clean(hall)],
                         "country": "CN" if re.search(r"[一-龥]", name) else "", "src": f"{base}/expo/company/{cid}.html"})

    def detail(r):
        try:
            d = get(op, r["src"], timeout=40).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return
        b = re.search(r'class="zwh">展位号\s*([^<]*)<', d)
        i = re.search(r'class="qyxc-intor[^"]*">(.*?)</div>', d, re.S)
        r["booth"] = clean(b.group(1))[:24] if b else ""
        r["desc"] = _txt(i.group(1))[:1500] if i else ""
        prods = re.findall(r'展品介绍.*?<h3[^>]*>(.*?)</h3>', d, re.S)
        r["show"] = " / ".join(_txt(x) for x in prods[:8] if _txt(x))[:600]
        time.sleep(0.1)
    with ThreadPool(6) as pool:
        pool.map(detail, rows)
    return rows, len(rows), f["url"]


def fetch_fairplus(f):
    """FAIR plus(선전) — 워드프레스 REST로 명단, 상세 페이지에서 公司简介."""
    op = opener()
    rows, page = [], 1
    while page < 20:
        try:
            raw = get(op, f["api"] + f"&page={page}", timeout=60)
        except Exception:  # noqa: BLE001
            break
        items = json.loads(raw.decode("utf-8", "replace"))
        if not isinstance(items, list) or not items:
            break
        for it in items:
            name = _html.unescape(TAG.sub("", it.get("title", {}).get("rendered", ""))).strip()
            if name:
                rows.append({"name": name, "booth": "", "desc": "", "show": "", "tags": [],
                             "country": "CN" if re.search(r"[一-龥]", name) else "", "src": it.get("link", f["url"])})
        if len(items) < 100:
            break
        page += 1

    def detail(r):
        try:
            d = get(op, r["src"], timeout=40).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return
        m = re.search(r"公司简介\s*</[^>]+>\s*(?:<[^>]+>\s*)*(.*?)</(?:p|div)>", d, re.S)
        r["desc"] = _txt(m.group(1))[:1500] if m else ""
        time.sleep(0.1)
    with ThreadPool(6) as pool:
        pool.map(detail, rows)
    return rows, len(rows), f["url"]


def fetch_hrte(f):
    """HRTE(항저우) — 정적 표: '中文 | 이름 | 부스' 줄과 '英文 | 영문명' 줄이 짝."""
    h = get(opener(), f["url"], timeout=60).decode("utf-8", "replace")
    rows, cur = [], None
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S):
        c = [_txt(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(c) < 2:
            continue
        if c[0] == "中文":
            cur = {"name": c[1], "name_ja": "", "booth": (c[2] if len(c) > 2 else "")[:24], "desc": "", "show": "",
                   "tags": [], "country": "CN", "src": f["url"]}
            rows.append(cur)
        elif c[0] == "英文" and cur and c[1]:
            cur["name_ja"], cur["name"] = cur["name"], c[1]
    return rows, len(rows), f["url"]


def fetch_vimf(f):
    """VIMF(베트남 산업전) — 워드프레스 글 하나가 출품사 하나. 제목 'COMPANY – Số gian hàng: 983'."""
    op = opener()
    rows, page = [], 1
    while page < 20:
        try:
            raw = get(op, f["api"] + f"&page={page}", timeout=60)
        except Exception:  # noqa: BLE001
            break
        items = json.loads(raw.decode("utf-8", "replace"))
        if not isinstance(items, list) or not items:
            break
        for it in items:
            t = _html.unescape(TAG.sub("", it.get("title", {}).get("rendered", ""))).strip()
            m = re.match(r"(.*?)\s*[–-]\s*Số gian hàng:\s*(.*)", t)
            body = _txt(it.get("content", {}).get("rendered", ""))
            rows.append({"name": (m.group(1) if m else t).strip(), "booth": (m.group(2) if m else "")[:24],
                         "desc": body[:1500], "show": "", "tags": [], "country": "", "src": it.get("link", f["url"])})
        if len(items) < 100:
            break
        page += 1
    return rows, len(rows), f["url"]


def fetch_expofp(f):
    """ExpoFP 부스 배치도 — `data/data.js`에 `var __data = {...}` 통째로 들어 있다.
    지난 회차 배치도는 행사가 끝나도 그대로 남아 있어, 현 회차 명단이 없을 때 대신 쓴다."""
    raw = get(opener(), f["api"], timeout=90).decode("utf-8-sig", "replace")
    d = json.loads(raw[raw.index("=") + 1:].strip().rstrip(";"))
    booth = {}
    for b in d.get("booths") or []:
        for eid in b.get("exhibitors") or []:
            booth.setdefault(eid, b.get("name", ""))
    cats = {c["id"]: c.get("name", "") for c in (d.get("categories") or []) if c.get("id")}
    rows = []
    for e in d.get("exhibitors") or []:
        name = clean(e.get("name"))
        if not name:
            continue
        rows.append({"name": name, "booth": str(booth.get(e.get("id"), ""))[:24],
                     "desc": _txt(e.get("description"))[:1500], "show": "",
                     "tags": [cats.get(c, "") for c in (e.get("categories") or []) if cats.get(c)][:12],
                     "web": clean(e.get("website")), "city": clean(e.get("city")),
                     "country": countries.iso2(e.get("country") or "") or "", "src": f["url"]})
    return rows, len(rows), f["url"]


def _pdf_lines(raw):
    """순수 파이썬 PDF 텍스트 추출 — FlateDecode 스트림을 풀고, 폰트마다 딸린
    ToUnicode CMap으로 글리프 번호를 글자로 되돌린다(폰트를 섞으면 글자가 깨진다)."""
    objs = {int(m.group(1)): m.group(3) for m in re.finditer(rb"(\d+)\s+(\d+)\s+obj(.*?)endobj", raw, re.S)}

    def stream_of(body):
        m = re.search(rb"stream\r?\n", body)
        if not m:
            return None
        data = body[m.end():body.rfind(b"endstream")]
        if b"/FlateDecode" in body[:m.start()]:
            try:
                return zlib.decompress(data)
            except Exception:  # noqa: BLE001
                return None
        return data

    def parse_cmap(data):
        cm = {}
        for blk in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
            for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
                cm[int(src, 16)] = bytes.fromhex(dst.decode()).decode("utf-16-be", "replace")
        for blk in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
            for lo, hi, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
                lo, hi, base = int(lo, 16), int(hi, 16), int(dst, 16)
                for i in range(lo, hi + 1):
                    cm[i] = chr(base + i - lo)
        return cm
    fonts = {}
    for body in objs.values():
        fd = re.search(rb"/Font\s*<<(.*?)>>", body, re.S)
        if not fd:
            continue
        for name, ref in re.findall(rb"/(\w+)\s+(\d+)\s+0\s+R", fd.group(1)):
            tu = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", objs.get(int(ref), b""))
            if tu:
                st = stream_of(objs.get(int(tu.group(1)), b"") or b"")
                if st:
                    fonts[name.decode()] = parse_cmap(st)
    lines = []
    for body in objs.values():
        st = stream_of(body)
        if not st or (b"Tj" not in st and b"TJ" not in st):
            continue
        cur, cm = "", {}
        for m in re.finditer(rb"/(\w+)\s+[\d.]+\s+Tf|\[(.*?)\]\s*TJ|<([0-9A-Fa-f]+)>\s*Tj|"
                             rb"(?:-?[\d.]+\s+-?[\d.]+\s+(?:Td|TD))|T\*|ET", st, re.S):
            if m.group(1):
                cm = fonts.get(m.group(1).decode(), cm)
                continue
            hexes = None
            if m.group(2) is not None:
                hexes = [x.decode() for x in re.findall(rb"<([0-9A-Fa-f]+)>", m.group(2))]
            elif m.group(3) is not None:
                hexes = [m.group(3).decode()]
            if hexes is not None:
                for h in hexes:
                    cur += "".join(cm.get(int(h[i:i + 4], 16), "") for i in range(0, len(h), 4))
            elif cur.strip():
                lines.append(cur.strip())
                cur = ""
        if cur.strip():
            lines.append(cur.strip())
    return lines


# PDF 명단(R4M)의 줄 구조: 회사명(대문자) → 소개 여러 줄 → 국가 → 구분 → 홈페이지 → 담당 직함
PDF_COUNTRY = {"France": "FR", "Belgique": "BE", "Allemagne": "DE", "Espagne": "ES", "Italie": "IT",
               "Suisse": "CH", "Portugal": "PT", "Pays-Bas": "NL", "Luxembourg": "LU", "Autriche": "AT",
               "Royaume-Uni": "GB", "Danemark": "DK", "Suède": "SE", "Tunisie": "TN", "Canada": "CA",
               "Chine": "CN", "Japon": "JP", "Etats-Unis": "US", "États-Unis": "US", "USA": "US",
               "Pologne": "PL", "Turquie": "TR", "Maroc": "MA", "Irlande": "IE", "Slovaquie": "SK",
               "Slovénie": "SI", "Roumanie": "RO", "Tchéquie": "CZ", "Finlande": "FI", "Norvège": "NO"}
PDF_ROLE = ("Fournisseur", "Donneur d'ordres", "Donneur d’ordres", "Exposant")


def fetch_pdflist(f):
    raw = get(opener(), f["api"], timeout=120)
    if raw[:4] != b"%PDF":
        raise RuntimeError("PDF가 아님")
    rows, cur = [], None
    for line in _pdf_lines(raw):
        if line.isupper() and 2 < len(line) < 70 and not line.lower().startswith("http") \
                and line not in PDF_COUNTRY and not re.match(r"^[\d\W]+$", line):
            if cur:
                rows.append(cur)
            cur = {"name": line, "booth": "", "desc": "", "show": "", "tags": [], "web": "",
                   "country": "", "src": f["url"], "_d": []}
        elif cur is not None:
            if line in PDF_COUNTRY:
                cur["country"] = PDF_COUNTRY[line]
            elif line.lower().startswith(("www.", "http")):
                cur["web"] = line if line.startswith("http") else "https://" + line
            elif line in PDF_ROLE:
                cur["tags"] = [line]
            elif len(line) > 12:
                cur["_d"].append(line)
    if cur:
        rows.append(cur)
    for r in rows:
        r["desc"] = clean(" ".join(r.pop("_d")))[:1500]
    return rows, len(rows), f["url"]


def fetch_wayback_tairos(f):
    """TAIROS — 주최측이 봇을 막아 인터넷 아카이브에 남은 목록 스냅샷에서 읽는다(1쪽 분량)."""
    t = get(opener(), f["api"], timeout=90).decode("utf-8", "replace")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    blocks = re.split(r'<div[^>]*class="[^"]*ExhListHover[^"]*"[^>]*>', t)[1:]
    rows = []
    for b in blocks:
        reg = re.search(r"regNo=(\d+)", b)
        cells = [_txt(x) for x in re.findall(r">([^<>]{2,400})<", b)]
        cells = [c for c in cells if c and c not in ("0",)]
        name = next((c for c in cells if len(c) > 3 and not c.startswith(("展館", "國家", "攤位"))), "")
        booth = ""
        for i, c in enumerate(cells):
            if c.startswith("攤位號碼") and i + 1 < len(cells):
                booth = cells[i + 1]
        desc = max(cells, key=len) if cells else ""
        if not name:
            continue
        rows.append({"name": name, "booth": booth[:24], "desc": desc[:1500] if len(desc) > 40 else "",
                     "show": "", "tags": [], "country": "TW",
                     "src": f"https://tairos.chanchao.com.tw/VisitorExhibitor/Detail?regNo={reg.group(1)}" if reg else f["url"]})
    return rows, len(rows), f["url"]


FETCH = {"mys": fetch_mys, "irex": fetch_irex, "aut": fetch_aut, "robotworld": fetch_robotworld,
         "expofp": fetch_expofp, "pdflist": fetch_pdflist, "wayback_tairos": fetch_wayback_tairos,
         "wrc": fetch_wrc, "fairplus": fetch_fairplus, "hrte": fetch_hrte, "vimf": fetch_vimf,
         "ungerboeck": fetch_ungerboeck, "ptak": fetch_ptak, "kielce": fetch_kielce,
         "nextai": fetch_nextai, "exporum": fetch_exporum, "fixkorea": fetch_fixkorea}


def one(f):
    t0 = time.time()
    rep = {k: f.get(k, "") for k in ("key", "title", "platform", "when", "kind", "scope", "city", "country", "note")}
    rep["url"] = f.get("url") or f"https://{f.get('host', '')}/8_0/explore/exhibitor-gallery.cfm"
    try:
        rows, total, src = FETCH[f["platform"]](f)
    except Exception as e:  # noqa: BLE001 - 한 전시회가 막혀도 나머지는 살린다
        rep.update({"exhibitors": 0, "listed": 0, "kept": 0, "error": f"{type(e).__name__}: {e}",
                    "sec": round(time.time() - t0, 1)})
        return f, [], rep
    rows = [r for r in rows if r.get("name")]
    if f["scope"] == "filter":
        kept = [r for r in rows if ROBOT_RE.search(" ".join([r["name"], r.get("desc", ""), " ".join(r.get("tags", []))]))]
    else:
        kept = rows
    rep.update({"url": src, "exhibitors": total, "listed": len(rows), "kept": len(kept),
                "with_desc": sum(1 for r in kept if r.get("desc")), "error": None,
                "sec": round(time.time() - t0, 1)})
    return f, kept, rep


# ================================================================ 분류
def classify(text):
    """카테고리는 맞은 횟수로 매긴다 — 긴 소개글은 온갖 단어가 걸리므로
    6개를 넘으면 두 번 이상 나온 것만 남긴다(한 번 스친 단어는 버린다)."""
    hits = [(k, len(rx.findall(text))) for k, _, rx in CATS_RE]
    hits = [(k, n) for k, n in hits if n]
    if len(hits) > 6:
        strong = [(k, n) for k, n in hits if n >= 2]
        hits = strong if len(strong) >= 3 else sorted(hits, key=lambda x: -x[1])[:6]
    order = {k: i for i, (k, _, _) in enumerate(CATS_RE)}
    cats = [k for k, _ in sorted(hits, key=lambda x: order[x[0]])]
    if not any(c in ("arm", "cobot", "amr", "humanoid") for c in cats) and ROBOT_RE.search(text):
        cats.insert(0, "robot")
    inds = [k for k, _, rx in INDS_RE if rx.search(text)]
    return cats, inds


def field_of(cats):
    for k, _, members in FIELDS:
        if any(c in members for c in cats):
            return k
    return "etc" if cats else ""


def strengths(desc):
    out = []
    for s in SENT_SPLIT.split(desc or ""):
        s = s.strip(" ・-•")
        if 15 <= len(s) <= 220 and STRONG_RE.search(s):
            out.append(s)
        if len(out) >= 2:
            break
    return out


def summary(desc):
    parts = [p.strip() for p in SENT_SPLIT.split(desc or "") if p.strip()]
    s = " ".join(parts[:2])
    return s[:240] + ("…" if len(s) > 240 else "")


def build_companies(per_fair):
    comp = {}
    for f, rows in per_fair:
        for r in rows:
            key = norm_co(r["name"]) or norm_co(r.get("name_ja", "")) or r["name"].lower()
            if len(key) < 2:
                continue
            c = comp.setdefault(key, {"names": Counter(), "ja": "", "desc": "", "show": [], "tags": set(),
                                      "country": [], "city": "", "web": "", "fairs": []})
            c["names"][r["name"]] += 1
            c["ja"] = c["ja"] or r.get("name_ja", "")
            if len(r.get("desc", "")) > len(c["desc"]):
                c["desc"] = r["desc"]
            if r.get("show") and r["show"] not in c["show"]:
                c["show"].append(r["show"])
            c["tags"].update(r.get("tags", []))
            cc = r.get("country") or guess_country(r["name"])
            if cc and cc not in c["country"]:
                c["country"].append(cc)
            c["city"] = c["city"] or r.get("city", "")
            c["web"] = c["web"] or r.get("web", "")
            ent = {"k": f["key"], "b": r.get("booth", ""), "u": r.get("src", "")}
            if not any(x["k"] == ent["k"] and x["b"] == ent["b"] for x in c["fairs"]):
                c["fairs"].append(ent)
    out = []
    for key, c in comp.items():
        name = min(c["names"], key=lambda n: (-c["names"][n], len(n)))
        text = " ".join([name, c["ja"], c["desc"], " ".join(c["show"]), " ".join(c["tags"])])
        cats, inds = classify(text)
        out.append({
            "k": key, "n": name, "ja": c["ja"] if c["ja"] != name else "", "c": c["country"], "city": c["city"],
            "web": c["web"], "cat": cats, "ind": inds, "fld": field_of(cats),
            "what": summary(c["desc"]), "show": " / ".join(c["show"])[:600], "tags": sorted(c["tags"])[:12],
            "str": strengths(c["desc"]), "desc": c["desc"][:1500],
            "f": sorted(c["fairs"], key=lambda x: x["k"]),
        })
    out.sort(key=lambda x: (-len({f["k"] for f in x["f"]}), x["n"].lower()))
    return out


# ================================================================ 한국어 번역 (소개글·강점·전시 하이라이트)
# 크롬 사전 확장이 쓰는 구글 번역 엔드포인트(키 없음)를 쓴다. 문장마다 data/ko_cache.json에 저장해
# 다음 날부터는 새로 생긴 문장만 번역한다. 막히면(429 등) 그 문장은 원문 그대로 둔다.
import hashlib
import ssl
import threading

TR_URL = "https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=auto&tl=ko"
TR_CTX = ssl.create_default_context()
_tr_lock = threading.Lock()


def _tr_one(text):
    data = urllib.parse.urlencode({"q": text}).encode()
    req = urllib.request.Request(TR_URL, data=data, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=40, context=TR_CTX).read().decode("utf-8", "replace"))
            out = d[0][0] if isinstance(d[0], list) else d[0]
            return clean(out)
        except Exception as e:  # noqa: BLE001
            if "429" in str(e):
                time.sleep(20 * (attempt + 1))
            else:
                time.sleep(2)
    return ""


def translate_ko(companies, budget=4000):
    """what·str·show를 한국어로. 한국어가 이미인 문장은 건너뛴다. budget = 한 번에 새로 번역할 최대 문장 수."""
    try:
        cache = json.load(open(KO_CACHE, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        cache = {}
    ko_re = re.compile(r"[가-힣]")
    todo = {}
    for c in companies:
        for t in [c["what"], c["show"]] + c["str"]:
            if t and not ko_re.search(t):
                h = hashlib.sha1(t.encode("utf-8")).hexdigest()
                if h not in cache:
                    todo[h] = t
    items = list(todo.items())[:budget]
    if items:
        print(f"[{datetime.now():%H:%M:%S}] 한국어 번역 {len(items)}문장 (캐시 {len(cache)})", flush=True)

        def work(pair):
            h, t = pair
            r = _tr_one(t)
            if r:
                with _tr_lock:
                    cache[h] = r
            time.sleep(0.3)
        with ThreadPool(4) as pool:
            pool.map(work, items)
        os.makedirs(os.path.dirname(KO_CACHE), exist_ok=True)
        json.dump(cache, open(KO_CACHE, "w", encoding="utf-8"), ensure_ascii=False)

    def ko(t):
        if not t or ko_re.search(t):
            return ""
        return cache.get(hashlib.sha1(t.encode("utf-8")).hexdigest(), "")
    for c in companies:
        c["ko"] = ko(c["what"])
        c["show_ko"] = ko(c["show"])
        c["str_ko"] = [ko(t) for t in c["str"]]
    return sum(1 for c in companies if c["ko"])


# ================================================================ 전시회 DB에서 로봇 전시회 뽑기
# 세 단계로 나눈다 — 제목에 로봇이 박힌 '로봇 전문'(core), 제목이 자동화·스마트팩토리·머신비전·드론·
# 물류자동화·제조기술인 '로봇이 주요 품목인 전시회'(adj), 설명에만 로봇이 언급된 곳(mention).
EXPO_CORE = re.compile(r"robot|로봇|humanoid|ロボット|机器人|automatica|\bautomate\b|피지컬\s?AI|physical ai|embodied", re.I)
EXPO_ADJ = re.compile(
    r"automation|自動化|자동화|オートメーション|smart\s?factory|스마트\s?팩토리|스마트\s?공장|smart manufactur|"
    r"factory automation|\bFA\b|machine vision|머신비전|motion control|drones?|드론|\bUAV\b|intralogistic|"
    r"logistics automation|물류자동화|manufacturing technolog|industrial technolog|manufacturing (expo|show|fair)|"
    r"제조자동화|생산자동화|자동화산업|hannover messe|\bSPS\b|\bCIIF\b|machine tools?|공작기계|metalworking|"
    r"metal week|기계\s?(산업전|대전|전시회|전)\b|기계\s?&\s?제조|manufacturing|제조산업전|제조기술|\bmach-?tech\b|"
    r"mechatronic|메카트로닉스|機械要素|techno-?frontier|\bAI\b.*(제조|manufactur)|스마트제조|smart production", re.I)
EXPO_RE = EXPO_CORE


def robot_expos():
    try:
        store = json.load(open(EXPOS, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    items = store.values() if isinstance(store, dict) else store
    seen, out = set(), []
    for e in items:
        title = e.get("title", "") + " " + e.get("title_en", "")
        if EXPO_CORE.search(title):
            tier = "core"
        elif EXPO_ADJ.search(title):
            tier = "adj"
        elif EXPO_CORE.search(e.get("summary", "") or ""):
            tier = "mention"
        else:
            continue
        t = (e.get("title_en") or e.get("title") or "").lower()
        t = re.sub(r"[^a-z0-9가-힣一-龥ぁ-んァ-ン]", "", t)
        dedupe = (t, (e.get("start") or "")[:4])
        if dedupe in seen:
            continue
        seen.add(dedupe)
        out.append({"t": e.get("title", ""), "te": e.get("title_en", ""), "s": e.get("start", ""), "core": tier == "core",
                    "tier": tier, "e": e.get("end", ""), "c": e.get("country", ""), "city": e.get("city", ""),
                    "venue": e.get("venue", ""), "org": e.get("org", ""), "sum": (e.get("summary") or "")[:300],
                    "url": e.get("homepage") or e.get("url", ""), "src": e.get("source", "")})
    rank = {"core": 0, "adj": 1, "mention": 2}
    out.sort(key=lambda x: (rank[x["tier"]], x["s"]))
    return out


# 명단을 확보한 전시회 ↔ DB의 전시회 이름 연결
LIST_MATCH = {"automate": ["automate27", "automate26"], "irex": ["irex25"],
              "로보월드": ["robotworld26"], "robot world": ["robotworld26"], "robotworld": ["robotworld26"],
              "next ai": ["nextai26"], "피지컬ai": ["nextai26"], "robot tech show": ["robottech26"],
              "robex": ["robex25"], "robotics slovenia": ["robotics_si27"], "robotics serbia": ["robotics_rs26"],
              "robotics warsaw": ["roboticswarsaw26"], "warsaw automatica": ["warsawautomatica26"],
              "warsaw industry automatica": ["warsawautomatica26"], "stom-robotics": ["stom_robotics26"],
              "wrc": ["wrc26"], "베이징 로봇": ["wrc26"], "fair plus": ["fairplus26"], "선전 로봇": ["fairplus26"],
              "hrte": ["hrte26"], "휴머노이드로봇기술": ["hrte26"], "rav - robotic": ["vimf_bn26"],
              "robotics summit": ["roboticssummit23"], "robobusiness": ["robobusiness23"],
              "robot4manufacturing": ["r4m24"], "tairos": ["tairos26"],
              "国際ロボット展": ["irex25"], "international robot exhibition": ["irex25"],
              "automatica": ["automatica25"], "promat": ["promat27", "promat25"]}


def link_lists(expos):
    for e in expos:
        blob = (e["t"] + " " + e["te"]).lower()
        e["lists"] = sorted({k for word, keys in LIST_MATCH.items() if word in blob for k in keys})
        e["why"] = next((why for word, why in NO_LIST if word in blob), "") if not e["lists"] else ""
    return expos


# ================================================================ 실행
def collect_all():
    per_fair, report = [], []
    with ThreadPool(4) as pool:
        for f, rows, rep in pool.map(one, FAIRS):
            per_fair.append((f, rows))
            report.append(rep)
    companies = build_companies(per_fair)
    n_ko = translate_ko(companies)
    print(f"[{datetime.now():%H:%M:%S}] 한국어 소개글 {n_ko}개 업체", flush=True)
    order = {f["key"]: i for i, f in enumerate(FAIRS)}
    report.sort(key=lambda r: order.get(r["key"], 99))
    expos = link_lists(robot_expos())
    used = sorted({x for c in companies for x in c["c"]} | {e["c"] for e in expos if e["c"]})
    return {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fairs": report,
        "expos": expos,
        "cats": [[k, n] for k, n, _ in CATS],
        "inds": [[k, n] for k, n, _ in INDS],
        "fields": [[k, n] for k, n, _ in FIELDS],
        "countries": {c: countries.ko(c, c) for c in used},
        "companies": companies,
    }


def main():
    data = collect_all()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    js = "window.ROBOTS=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    open(APP, "w", encoding="utf-8").write(js)
    print(f"[{datetime.now():%H:%M:%S}] 로봇 전시회 {len(data['expos'])}개 · 명단 {len(data['fairs'])}회차 · "
          f"업체 {len(data['companies'])}개 · app-robots.js {len(js) // 1024}KB")
    for r in data["fairs"]:
        print(f"  {r['key']:14} {r['kind']:9} {r.get('kept', 0):5}/{r.get('listed', 0):<5} "
              f"소개글 {r.get('with_desc', 0):4}  {r['sec']:5}s  {r.get('error') or ''}")
    if "--dump" in sys.argv:
        for c in data["companies"][:40]:
            print(f"- {c['n']} [{c['c']}] {','.join(c['cat'])} | {c['what'][:80]}")


if __name__ == "__main__":
    main()
