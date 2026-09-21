#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전시회 분류 — 산업분야·국내 개최지·업무 관련도.

출처(AKEI·GEP·EventsEye)마다 분야 체계가 달라서 제목·품목·설명 텍스트를
하나의 산업 코드 체계로 다시 태깅한다. 튜닝은 이 파일만 고치고
`python3 build.py --no-fetch` 로 다시 만들면 된다.
"""

import re

# ------------------------------------------------------------------ 산업분야
# 코드: (이모지, 한글 이름, 판정 정규식) — 앞에 있을수록 먼저 붙는다(대표 분야)
INDUSTRIES = [
    ("elec", "🔌", "전기·전자·반도체",
     r"전자|전기|반도체|디스플레이|커넥터|단자|배선|전선|케이블|전자부품|인쇄회로|PCB|SMT|광학|렌즈|센서|계측|가전|조명|LED"
     r"|electron|semiconduct|microelectro|display|connector|cable|wire|pcb|circuit|component|optic|laser|photonic|sensor"
     r"|measurement|metrolog|appliance|lighting|led|chip|wafer|smt|embedded|electrical"),
    ("auto", "🚗", "자동차·모빌리티·조선",
     r"자동차|자동차부품|모빌리티|전기차|이륜|타이어|차량|조선|해양|선박|철도|캠핑카|튜닝"
     r"|auto|automotive|vehicle|\bcars?\b|mobility|\bev\b|e-mobility|motorcycle|tire|tyre|marine|maritime|boat|ship|rail|train"),
    ("mach", "⚙️", "기계·로봇·자동화·금형",
     r"기계|공작기계|금형|사출|プレス|프레스|공구|용접|주조|단조|표면처리|도금|절삭|로봇|자동화|스마트공장|제조|산업설비|베어링|유압|공압"
     r"|machine|machinery|machine tool|\btools?\b|mould|mold|\bdie\b|casting|forging|weld|surface|coating|plating|robot|automation"
     r"|factory|manufactur|industrial|bearing|hydraulic|pneumatic|fastener|metal|steel|plastics|rubber|3d print|additive"),
    ("ict", "💻", "IT·통신·소프트웨어·AI",
     r"정보통신|통신|소프트웨어|인공지능|빅데이터|클라우드|보안|게임|블록체인|메타버스|드론촬영|콘텐츠|방송|음향"
     r"|\bict\b|telecom|software|artificial intelligence|\bai\b|big data|cloud|cyber|security|game|blockchain"
     r"|metaverse|digital|computer|broadcast|media tech|\b5g\b|\b6g\b|\biot\b|data cent|smart ?city"),
    ("energy", "⚡", "에너지·환경·배터리",
     r"에너지|전력|태양광|풍력|수소|원자력|배터리|이차전지|충전|환경|폐기물|재활용|물산업|수처리|탄소|기후"
     r"|energy|power|solar|photovoltaic|wind|hydrogen|nuclear|batter|charging|environment|waste|recycl|water|carbon|climate|green"),
    ("build", "🏗", "건축·건설·인테리어",
     r"건축|건설|자재|인테리어|리모델링|주택|부동산|냉난방|공조|설비|조경|가구전|도시|스마트시티|엘리베이터"
     r"|construct|building|architect|interior|hous|real estate|hvac|heating|cooling|plumb|landscape|smart ?city|urban plan|elevator|concrete|cement"),
    ("med", "🩺", "의료·바이오·헬스케어",
     r"의료|의료기기|병원|제약|바이오|헬스|건강|치과|안경|재활|요양|실버|animal health|수의|동물병원"
     r"|medical|medicine|hospital|pharma|bio|health|dental|optic care|rehab|care|laborator|diagnost|veterinar"),
    ("food", "🍽", "식품·농수산·외식",
     r"식품|먹거리|외식|급식|커피|주류|음료|와인|맥주|위스키|주정|식음료|베이커리|제과|제빵|농업|농기계|축산|수산|양식|종자|원예|화훼|스마트팜"
     r"|food|beverage|drink|coffee|wine|beer|bakery|confection|restaurant|catering|agri|farm|livestock|fish|aqua|seed|horticult|garden"),
    ("fashion", "👗", "섬유·패션·뷰티",
     r"섬유|패션|의류|어패럴|봉제|원단|가죽|신발|쥬얼리|주얼리|시계|안경테|화장품|뷰티|미용|헤어|네일"
     r"|textile|fashion|apparel|garment|fabric|leather|shoe|footwear|jewel|watch|cosmetic|beauty|hair|nail|perfum"),
    ("life", "🛋", "소비재·생활·유아·반려",
     r"생활용품|소비재|리빙|가구|주방|침구|선물|공예|문구|유아|육아|임신|출산|반려|애견|펫|완구|취미|아웃도어|캠핑|스포츠용품"
     r"|consumer|household|living|furniture|kitchen|home |gift|craft|stationer|baby|kids|toy|pet|hobby|outdoor|camping|sport"),
    ("logi", "📦", "물류·유통·포장·인쇄",
     r"물류|창고|운송|택배|유통|프랜차이즈|리테일|포장|패키징|인쇄|라벨|지류|공급망"
     r"|logistic|warehouse|transport|supply chain|distribut|retail|franchise|packag|print|label|paper|e-commerce|sourcing"),
    ("aero", "✈️", "항공·우주·방산",
     r"항공|우주|위성|방위|방산|국방|무기|드론|\buav\b"
     r"|aero|aviation|air show|space|satellite|defen[cs]e|military|drone|unmanned"),
    ("cult", "🎓", "교육·관광·문화·서비스",
     r"교육|유학|도서|출판|학교|관광|여행|호텔|숙박|마이스|웨딩박람회|컨벤션산업|웨딩|장례|예술|공예품|전시산업|채용|취업|프랜차이즈 창업"
     r"|education|school|univers|book|publish|tourism|travel|\bmice\b|wedding|funeral|\barts?\b|culture|career|\bjobs?\b|recruit|franchise"),
    ("etc", "🏷", "종합·기타", r"$^"),
]
IND_NAME = {c: (emoji, name) for c, emoji, name, _ in INDUSTRIES}
IND_RE = [(c, re.compile(p, re.I)) for c, _, _, p in INDUSTRIES]

# GEP(KOTRA) 산업분야 코드 → 우리 코드
GEP_FIELD = {
    "131": "build", "132": "cult", "133": "mach", "134": "med", "135": "life",
    "136": "fashion", "137": "auto", "138": "elec", "139": "ict", "140": "energy", "141": "etc",
}


def industries(title="", strong="", weak="", hint=None):
    """산업분야 코드 목록 — 대표 분야가 첫 번째.

    제목(3점) > 전시품목·분야 표기(2점) > 설명문(1점)으로 가중치를 둔다.
    설명문만 보고 정하면 '아시아의 슈퍼 커넥터' 같은 비유에 전자로 잘못 찍힌다.
    """
    score = {}
    for text, w in ((title, 3), (strong, 2), (weak, 1)):
        if not text:
            continue
        for c, rx in IND_RE:
            if c != "etc" and rx.search(text):
                score[c] = score.get(c, 0) + w
    for h in (hint or []):
        if h:
            score[h] = score.get(h, 0) + 2        # 출처가 직접 붙인 분야
    if not score:
        return ["etc"]
    order = {c: i for i, (c, _, _, _) in enumerate(INDUSTRIES)}
    return sorted(score, key=lambda c: (-score[c], order[c]))


# ------------------------------------------------------------------ 업무 관련도 (UJU = 커넥터·전장부품 제조)
RELEVANCE = [
    (5, r"커넥터|connector|단자|terminal block|와이어 ?하네스|wire harness|wiring|하네스|배선"),
    (4, r"전자부품|electronic component|전장|automotive electronic|자동차 ?전장|카메라 ?모듈|camera module"
        r"|electronica|CES\b|반도체 ?장비|semiconductor|smt|pcb|인쇄회로"),
    (3, r"전기ㆍ?전자|전자전|electronics show|electronics fair|배터리|batter|이차전지|\bev\b|전기차|electric vehicle"
        r"|충전|charging|모터|motor show|센서|sensor|디스플레이|display"),
    (2, r"자동차|automotive|auto parts|부품|component|모빌리티|mobility|로봇|robot|자동화|automation"
        r"|스마트공장|smart factory|금형|mold|mould|사출|injection|공작기계|machine tool"),
    (1, r"제조|manufactur|산업|industrial|소재|material|기계|machinery|소싱|sourcing|공급망|supply chain"),
]
RELEVANCE = [(s, re.compile(p, re.I)) for s, p in RELEVANCE]

IND_BONUS = {"elec": 2.0, "auto": 1.5, "mach": 1.2, "energy": 0.8, "ict": 0.6, "logi": 0.4, "aero": 0.4}


def relevance(title, extra="", inds=(), support=False, scale=0):
    """0~10 점. 커넥터·전장 키워드 > 산업분야 > 국고지원·규모 순으로 가산."""
    blob = f"{title} {extra}"
    score = 0.0
    for s, rx in RELEVANCE:
        if rx.search(blob):
            score += s
            if s >= 4:
                break
    score += max((IND_BONUS.get(c, 0) for c in inds), default=0)
    if support:
        score += 1.0
    if scale:
        score += min(scale / 1000.0, 1.0)
    return round(min(score, 10.0), 1)


# ------------------------------------------------------------------ 국내 개최지
REGIONS = {
    "seoul": "서울", "busan": "부산", "daegu": "대구", "incheon": "인천", "gwangju": "광주",
    "daejeon": "대전", "ulsan": "울산", "sejong": "세종", "gyeonggi": "경기", "gangwon": "강원",
    "chungbuk": "충북", "chungnam": "충남", "jeonbuk": "전북", "jeonnam": "전남",
    "gyeongbuk": "경북", "gyeongnam": "경남", "jeju": "제주",
}

# 전시장 → (지역, 시·군·구, 위도, 경도) — 국내 전시회는 대부분 아래 전시장에서 열린다
VENUES = [
    (r"코엑스|COEX", "seoul", "강남구", 37.51257, 127.05882, "코엑스"),
    (r"세텍|SETEC", "seoul", "강남구", 37.48719, 127.05504, "세텍(SETEC)"),
    (r"aT ?센터|at ?center|aT", "seoul", "서초구", 37.46958, 127.03819, "aT센터"),
    (r"DDP|동대문디자인플라자", "seoul", "중구", 37.56682, 127.00937, "DDP"),
    (r"킨텍스|KINTEX", "gyeonggi", "고양시", 37.66899, 126.74525, "킨텍스"),
    (r"수원메쎄|수원컨벤션", "gyeonggi", "수원시", 37.25376, 127.05170, "수원컨벤션센터"),
    (r"송도컨벤시아|송도", "incheon", "연수구", 37.38845, 126.64322, "송도컨벤시아"),
    (r"벡스코|BEXCO", "busan", "해운대구", 35.16903, 129.13606, "벡스코"),
    (r"부산항국제전시|BPEX", "busan", "동구", 35.11605, 129.04277, "부산항국제전시컨벤션센터"),
    (r"엑스코|EXCO", "daegu", "북구", 35.90224, 128.60563, "엑스코"),
    (r"대전컨벤션|DCC", "daejeon", "유성구", 36.37585, 127.38395, "대전컨벤션센터"),
    (r"김대중컨벤션|KDJ", "gwangju", "서구", 35.13996, 126.83967, "김대중컨벤션센터"),
    (r"창원컨벤션|CECO|세코", "gyeongnam", "창원시", 35.22536, 128.67919, "창원컨벤션센터"),
    (r"울산전시컨벤션|UECO|유에코", "ulsan", "울주군", 35.55355, 129.19080, "울산전시컨벤션센터"),
    (r"군산새만금컨벤션|GSCO", "jeonbuk", "군산시", 35.94168, 126.68035, "군산새만금컨벤션센터"),
    (r"오스코|OSCO", "chungbuk", "청주시", 36.64097, 127.44652, "청주 오스코"),
    (r"화백컨벤션|HICO|하이코", "gyeongbuk", "경주시", 35.83206, 129.28337, "경주 화백컨벤션센터"),
    (r"안동국제컨벤션|ADCO", "gyeongbuk", "안동시", 36.56177, 128.72750, "안동국제컨벤션센터"),
    (r"ICC ?JEJU|제주국제컨벤션|ICC제주", "jeju", "서귀포시", 33.24657, 126.41028, "제주국제컨벤션센터"),
    (r"구미코|GUMICO", "gyeongbuk", "구미시", 36.11746, 128.38095, "구미코"),
    (r"여수엑스포", "jeonnam", "여수시", 34.75437, 127.75116, "여수세계박람회장"),
    (r"천안|독립기념관", "chungnam", "천안시", 36.80703, 127.15402, ""),
    (r"광주 ?여대|광주유니버시아드", "gwangju", "광산구", 35.13996, 126.83967, ""),
]
VENUES = [(re.compile(p, re.I), r, s, la, lo, nm) for p, r, s, la, lo, nm in VENUES]

REGION_WORDS = {
    "서울": "seoul", "부산": "busan", "대구": "daegu", "인천": "incheon", "광주": "gwangju",
    "대전": "daejeon", "울산": "ulsan", "세종": "sejong", "경기": "gyeonggi", "고양": "gyeonggi",
    "강원": "gangwon", "충북": "chungbuk", "충남": "chungnam", "전북": "jeonbuk", "전남": "jeonnam",
    "경북": "gyeongbuk", "경남": "gyeongnam", "제주": "jeju",
}


def place_kr(venue, fallback=""):
    """국내 전시장 이름 → (지역코드, 시·군·구, 위도, 경도, 대표 전시장명)"""
    t = f"{venue} {fallback}"
    for rx, reg, sub, la, lo, nm in VENUES:
        if rx.search(t):
            return reg, sub, la, lo, (nm or venue)
    for w, k in REGION_WORDS.items():
        if w in t:
            return k, "", None, None, venue
    return "", "", None, None, venue


# ------------------------------------------------------------------ 제목 정리
NOISE = re.compile(r"^\s*(제?\s*\d+\s*회|20\d\d\s*년?)\s*", re.I)


def norm_title(s):
    """중복 판정용 — 연도·회차·괄호·기호를 떼고 소문자 알파벳·한글만 남긴다."""
    s = re.sub(r"[\[\(].*?[\]\)]", " ", s or "")
    s = NOISE.sub("", s)
    s = re.sub(r"20\d\d", " ", s)
    return re.sub(r"[^0-9a-z가-힣]", "", s.lower())


# ------------------------------------------------------------------ 주요 전시 도시 (한글 ↔ 영문)
# GEP는 한글 도시명, EventsEye는 영문 도시명이라 중복 판정 때 서로 맞춰 본다.
CITY_KO = {
    "뮌헨": "munich", "프랑크푸르트": "frankfurt", "베를린": "berlin", "쾰른": "cologne", "하노버": "hanover",
    "뒤셀도르프": "dusseldorf", "함부르크": "hamburg", "뉘른베르크": "nuremberg", "슈투트가르트": "stuttgart",
    "에센": "essen", "라이프치히": "leipzig", "파리": "paris", "리옹": "lyon", "칸": "cannes", "니스": "nice",
    "밀라노": "milan", "볼로냐": "bologna", "로마": "rome", "베로나": "verona", "리미니": "rimini",
    "마드리드": "madrid", "바르셀로나": "barcelona", "발렌시아": "valencia", "빌바오": "bilbao",
    "런던": "london", "버밍엄": "birmingham", "맨체스터": "manchester", "암스테르담": "amsterdam",
    "위트레흐트": "utrecht", "로테르담": "rotterdam", "브뤼셀": "brussels", "빈": "vienna", "취리히": "zurich",
    "제네바": "geneva", "바젤": "basel", "스톡홀름": "stockholm", "코펜하겐": "copenhagen", "오슬로": "oslo",
    "헬싱키": "helsinki", "바르샤바": "warsaw", "포즈난": "poznan", "프라하": "prague", "부다페스트": "budapest",
    "이스탄불": "istanbul", "앙카라": "ankara", "모스크바": "moscow", "상트페테르부르크": "st petersburg",
    "키이우": "kiev", "두바이": "dubai", "아부다비": "abu dhabi", "도하": "doha", "리야드": "riyadh",
    "제다": "jeddah", "카이로": "cairo", "텔아비브": "tel aviv", "요하네스버그": "johannesburg",
    "나이로비": "nairobi", "라고스": "lagos", "카사블랑카": "casablanca", "뉴욕": "new york",
    "라스베이거스": "las vegas", "라스베가스": "las vegas", "시카고": "chicago", "올랜도": "orlando",
    "애틀랜타": "atlanta", "로스앤젤레스": "los angeles", "샌프란시스코": "san francisco", "보스턴": "boston",
    "댈러스": "dallas", "휴스턴": "houston", "마이애미": "miami", "디트로이트": "detroit", "토론토": "toronto",
    "몬트리올": "montreal", "밴쿠버": "vancouver", "멕시코시티": "mexico city", "상파울루": "sao paulo",
    "리우데자네이루": "rio de janeiro", "부에노스아이레스": "buenos aires", "산티아고": "santiago",
    "보고타": "bogota", "리마": "lima", "도쿄": "tokyo", "오사카": "osaka", "나고야": "nagoya",
    "요코하마": "yokohama", "상하이": "shanghai", "베이징": "beijing", "광저우": "guangzhou",
    "선전": "shenzhen", "심천": "shenzhen", "홍콩": "hong kong", "타이베이": "taipei", "타이페이": "taipei",
    "싱가포르": "singapore", "방콕": "bangkok", "하노이": "hanoi", "호치민": "ho chi minh city",
    "자카르타": "jakarta", "쿠알라룸푸르": "kuala lumpur", "마닐라": "manila", "뭄바이": "mumbai",
    "뉴델리": "new delhi", "델리": "delhi", "첸나이": "chennai", "벵갈루루": "bangalore", "방갈로르": "bangalore",
    "시드니": "sydney", "멜버른": "melbourne", "브리즈번": "brisbane", "퍼스": "perth", "오클랜드": "auckland",
}
CITY_EN = {v: v for v in CITY_KO.values()}


def city_key(name):
    """도시명 → 비교용 열쇠(영문 소문자). 모르는 도시는 None."""
    n = (name or "").strip()
    if not n:
        return None
    if n in CITY_KO:
        return CITY_KO[n]
    low = re.sub(r"[^a-z ]", "", n.lower()).strip()
    return low if low in CITY_EN else None


# ------------------------------------------------------------------ 커넥터 전용 전시회 판정
# 우리 업(커넥터·케이블·하네스·단자)이 주제인 전시회. ICH처럼 출품사 명단을 공개하지 않는 곳도
# 목록에서 사라지지 않게 따로 표시하려고 쓴다.
CONN_FAIR = re.compile(
    r"커넥터|connector|连接器|コネクタ|"
    r"하네스|harness|线束|ハーネス|"
    r"(?:wire|cable|케이블|전선|와이어)\s*(?:&|and|・|,|\s)?\s*(?:cable|harness|processing|tech|expo|show|전|线)|"
    r"wire china|wire russia|wire tech|world of cable|cables europe|cable & wire|wire & cable|"
    r"electrical wire processing|interwire|cwieme|coil winding|단자|terminal block", re.I)
# 이름만 보면 걸리지만 우리 업이 아닌 것들
NOT_CONN_FAIR = re.compile(
    r"passenger terminal|airport|공항|물류 ?터미널|logistics terminal|wireless|무선|studyrama|"
    r"요하네스버그|johannesburg|"   # '하네스'가 지명에 숨어 있다(요-하네스-버그)
    r"terminales|container terminal|bus terminal", re.I)


def is_connector_fair(*texts):
    blob = " ".join(t for t in texts if t)
    return bool(CONN_FAIR.search(blob)) and not NOT_CONN_FAIR.search(blob)
