#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""국가 사전 — ISO2 기준으로 한글명·영문명·대륙·별칭을 한 곳에서 관리한다.

`geo/iso3166.json`(ISO 3166 전체)과 `geo/gep_nat.json`(KOTRA GEP의 한글 국가명·ISO2)을
합쳐 만든다. 출처마다 국가 표기가 달라서(영문·한글·'UK - United Kingdom' 같은 변형)
별칭 색인 ALIAS로 한 번에 정규화한다.
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

REGION_KO = {
    "Asia": "아시아", "Europe": "유럽", "Africa": "아프리카",
    "Americas": "아메리카", "Oceania": "오세아니아", "": "기타",
}
SUB_KO = {
    "Eastern Asia": "동아시아", "South-eastern Asia": "동남아시아", "Southern Asia": "남아시아",
    "Western Asia": "서아시아·중동", "Central Asia": "중앙아시아",
    "Northern Europe": "북유럽", "Western Europe": "서유럽", "Southern Europe": "남유럽",
    "Eastern Europe": "동유럽", "Northern America": "북미", "Latin America and the Caribbean": "중남미",
    "Northern Africa": "북아프리카", "Sub-Saharan Africa": "아프리카",
    "Australia and New Zealand": "호주·뉴질랜드", "Melanesia": "오세아니아",
    "Micronesia": "오세아니아", "Polynesia": "오세아니아",
}

# 출처별 표기 흔들림을 잡는 수동 별칭 (왼쪽은 소문자·기호 제거 후 비교)
EXTRA_ALIAS = {
    "usa": "US", "unitedstates": "US", "unitedstatesofamerica": "US", "us": "US",
    "uk": "GB", "ukunitedkingdom": "GB", "unitedkingdom": "GB", "greatbritain": "GB", "england": "GB",
    "scotland": "GB", "wales": "GB", "northernireland": "GB",
    "southkorea": "KR", "korea": "KR", "republicofkorea": "KR", "koreasouth": "KR", "한국": "KR",
    "대한민국": "KR", "northkorea": "KP",
    "russia": "RU", "russianfederation": "RU",
    "uae": "AE", "unitedarabemirates": "AE", "아랍에미리트": "AE", "두바이": "AE",
    "vietnam": "VN", "vietnamese": "VN", "iran": "IR", "syria": "SY", "laos": "LA",
    "taiwan": "TW", "chinesetaipei": "TW", "hongkong": "HK", "macao": "MO", "macau": "MO",
    "czechrepublic": "CZ", "czechia": "CZ", "slovakia": "SK", "slovakrepublic": "SK",
    "bosniaherzegovina": "BA", "bosniaandherzegovina": "BA",
    "netherlands": "NL", "holland": "NL", "thenetherlands": "NL",
    "turkey": "TR", "turkiye": "TR", "튀르키예": "TR", "터키": "TR",
    "ivorycoast": "CI", "cotedivoire": "CI", "capeverde": "CV",
    "democraticrepublicofthecongo": "CD", "drcongo": "CD", "congo": "CG",
    "bolivia": "BO", "venezuela": "VE", "tanzania": "TZ", "moldova": "MD", "brunei": "BN",
    "swaziland": "SZ", "eswatini": "SZ", "myanmar": "MM", "burma": "MM",
    "palestine": "PS", "palestinianterritories": "PS", "vatican": "VA", "vaticancity": "VA",
    "southsudan": "SS", "northmacedonia": "MK", "macedonia": "MK",
    "dominicanrepublic": "DO", "puertorico": "PR", "reunion": "RE",
    "serbia": "RS", "montenegro": "ME", "kosovo": "XK",
    "saudiarabia": "SA", "사우디": "SA", "타이완": "TW", "대만": "TW", "홍콩": "HK", "마카오": "MO", "러시아": "RU", "체코": "CZ", "미국": "US", "영국": "GB", "중국": "CN", "일본": "JP",
    "독일": "DE", "프랑스": "FR", "이탈리아": "IT", "스페인": "ES", "인도": "IN",
}

# 세계 지도 topojson에 없는(작은) 나라의 대략 좌표 보정
FALLBACK_LL = {
    "SG": (1.35, 103.82), "HK": (22.32, 114.17), "MO": (22.19, 113.54), "BH": (26.07, 50.55),
    "MT": (35.9, 14.5), "MU": (-20.3, 57.55), "MV": (3.2, 73.22), "LU": (49.61, 6.13),
    "AD": (42.5, 1.52), "MC": (43.73, 7.42), "LI": (47.14, 9.55), "SM": (43.94, 12.45),
    "BB": (13.19, -59.54), "XK": (42.6, 20.9), "PS": (31.9, 35.2), "BN": (4.54, 114.72),
}


def _key(s):
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())


def _load():
    iso = json.load(open(os.path.join(HERE, "geo", "iso3166.json"), encoding="utf-8"))
    gep = json.load(open(os.path.join(HERE, "geo", "gep_nat.json"), encoding="utf-8"))["list"]
    ko_by_iso2 = {r["cd"]: r["cdNm"] for r in gep if len(r.get("cd", "")) == 2}

    countries, alias = {}, {}
    for r in iso:
        a2 = r["alpha-2"]
        en = re.sub(r"\s*\(.*?\)\s*", " ", r["name"]).strip()
        countries[a2] = {
            "iso2": a2, "iso3": r["alpha-3"], "num": r["country-code"],
            "en": en, "ko": ko_by_iso2.get(a2, en),
            "region": REGION_KO.get(r["region"], "기타"),
            "sub": SUB_KO.get(r["sub-region"], REGION_KO.get(r["region"], "기타")),
        }
        for v in (r["name"], en, r["alpha-3"], ko_by_iso2.get(a2, "")):
            if v:
                alias.setdefault(_key(v), a2)
        # "Korea (the Republic of)" 처럼 괄호 앞부분만 쓰는 표기
        alias.setdefault(_key(r["name"].split("(")[0]), a2)
    alias.update(EXTRA_ALIAS)
    return countries, alias


COUNTRIES, ALIAS = _load()


def iso2(name):
    """국가 표기(한글·영문·약칭) → ISO2. 못 찾으면 None."""
    if not name:
        return None
    s = str(name).strip()
    if len(s) == 2 and s.upper() in COUNTRIES:
        return s.upper()
    k = _key(s)
    if k in ALIAS:
        return ALIAS[k]
    # 'UK - United Kingdom' / 'Korea, Republic of' / 'Myanmar (Burma)' 처럼 구분자가 있는 표기
    for part in re.split(r"[-,/·()]", s):
        k = _key(part)
        if len(k) > 2 and k in ALIAS:
            return ALIAS[k]
    return None


def info(a2):
    return COUNTRIES.get(a2 or "", None)


def ko(a2, default=""):
    c = COUNTRIES.get(a2 or "")
    return c["ko"] if c else default


if __name__ == "__main__":
    print(len(COUNTRIES), "개국")
    for t in ("이집트", "USA", "UK - United Kingdom", "대한민국", "Viet Nam", "타이완"):
        print(t, "→", iso2(t), ko(iso2(t)))
