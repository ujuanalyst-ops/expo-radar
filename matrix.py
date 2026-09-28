#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""경쟁사 전시회 참가 매트릭스 — 추정이 아니라 **주최측 공식 출품사 명단으로 확인한 것**만 ●로 적는다.

rivals.py가 매일 받아 두는 출품사 명단(data/rivals.json)에서
  ● 확인  = 그 전시회 공식 명단에 그 경쟁사가 있다 (확인된 법인명·부스까지 남긴다)
  ✕ 없음  = 명단을 받아서 확인했는데 없다
  ○ 추정  = 우리가 명단을 못 받은 전시회 — 사람이 넣어 둔 예상치를 그대로 둔다
를 구분해 엑셀로 만든다. '없음'과 '미확인'을 섞지 않는 것이 이 표의 핵심이다.

  python3 matrix.py                      # share/UJU_전시회_경쟁사_매트릭스_검증_YYYY-MM-DD.xlsx
  python3 matrix.py --base 기존.xlsx      # 기존 매트릭스의 평가 열(적합도·규모·우선순위)을 물려받는다
"""

import datetime
import json
import os
import re
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
RIVALS_JSON = os.path.join(HERE, "data", "rivals.json")
OUT_DIR = os.path.join(HERE, "share")
TODAY = datetime.date.today().isoformat()

# 매트릭스에서 열로 세우는 경쟁사 (고객사가 추적하는 10곳) — rivals.py의 키
TRACKED = [("te", "TE"), ("amphenol", "Amphenol"), ("molex", "Molex"), ("hirose", "Hirose"),
           ("jae", "JAE"), ("ipex", "I-PEX"), ("jst", "JST"), ("luxshare", "Luxshare"),
           ("ket", "KET"), ("samtec", "Samtec")]

# 기존 매트릭스의 전시회 이름 ↔ 우리 수집 키 (이름이 달라 자동으로 안 붙는 것만 손으로 잇는다)
BASE_LINK = {
    "KES 한국전자전": "kes26", "로보월드": "robotworld26", "electronica": "electronica26",
    "DesignCon": "designcon27", "automatica": "automatica25", "CES": "ces27",
    "Computex": "computex26", "IPC APEX Expo": "apex27", "CEATEC": "ceatec26",
    "iREX": "irex25", "Automate": "automate27", "NEPCON Japan / Automotive World": "jpca26",
    "스마트공장·자동화산업전": "", "Hannover Messe": "", "SPS": "",
}

ARIAL = "Arial"
HDR_FILL = PatternFill("solid", fgColor="1F3864")
SUB_FILL = PatternFill("solid", fgColor="D9E2F3")
OK_FILL = PatternFill("solid", fgColor="C6EFCE")     # ● 확인
NO_FILL = PatternFill("solid", fgColor="F2F2F2")     # ✕ 없음
GUESS_FILL = PatternFill("solid", fgColor="FFF2CC")  # ○ 추정
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


BASE_JSON = os.path.join(HERE, "matrix_base.json")


def load_base(path=None):
    """고객이 준 매트릭스(Top 50)의 평가 열과 추정 표기.
    첨부 파일은 사라지므로 matrix_base.json에 옮겨 두고 그것을 읽는다.
    --base로 새 엑셀을 주면 그 파일을 읽어 matrix_base.json을 갱신한다."""
    if path and os.path.exists(path):
        wb = load_workbook(path, data_only=True)
        ws = wb[wb.sheetnames[0]]
        head, rows = None, []
        for row in ws.iter_rows(values_only=True):
            vals = ["" if v is None else str(v).strip() for v in row]
            if not head:
                if "전시회" in vals:
                    head = {v: i for i, v in enumerate(vals) if v}
                continue
            g = lambda k: vals[head[k]] if k in head and head[k] < len(vals) else ""  # noqa: E731
            if not g("전시회"):
                continue
            rows.append({"no": len(rows) + 1, "name": g("전시회"), "지역": g("지역"), "분야": g("분야"),
                         "일정": g("일정/장소"), "적합도": g("우주 적합도(1-5)"), "규모": g("전시 규모(1-5)"),
                         "접점": g("고객 접점(1-5)"), "우선순위": g("우선순위"),
                         "추정": {k: g(n) for k, n in TRACKED if g(n)}})
        if rows:
            json.dump({"출처": os.path.basename(path), "받은날": TODAY,
                       "경쟁사열": [k for k, _ in TRACKED], "rows": rows},
                      open(BASE_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    try:
        return {r["name"]: r for r in json.load(open(BASE_JSON, encoding="utf-8"))["rows"]}
    except Exception:  # noqa: BLE001
        return {}


def base_for(f, base):
    """우리가 수집한 전시회에 대응하는 기존 매트릭스 행 찾기(수집 키 우선, 그다음 이름)."""
    key, title = f.get("key", ""), f.get("title", "")
    for name, row in base.items():
        link = BASE_LINK.get(name)
        if link and (link == key or link == key.replace("rb_", "") or link in title):
            return name, row
    t = re.sub(r"[^a-z0-9가-힣]", "", title.lower())
    for name, row in base.items():
        n = re.sub(r"[^a-z0-9가-힣]", "", name.lower())
        if len(n) > 3 and (n in t or t.startswith(n)):
            return name, row
    return None, None


def build(base_path=None):
    d = json.load(open(RIVALS_JSON, encoding="utf-8"))
    base = load_base(base_path)
    linked = set()
    fields = d.get("fields") or [["elec", "전자·IT"]]
    fname = dict(fields)

    found = {}
    for r in d["records"]:
        found.setdefault(r["fair_key"], {}).setdefault(r["rival"], []).append(r)

    wb = Workbook()
    wb.remove(wb.active)

    # ── 분야마다 시트 하나 (전시회가 79개라 한 장에 다 넣으면 못 본다)
    order = sorted(d["fairs"], key=lambda f: -len(found.get(f["key"], {})))
    counts = {}
    for fk, fn in fields:
        rows = [f for f in order if (f.get("field") or "elec") == fk]
        if not rows:
            continue
        counts[fk] = len(rows)
        ws = wb.create_sheet(_sheet_name(fn))
        _sheet(ws, fn, rows, found, base, linked)

    # ── 맨 앞에 한눈 요약
    ws0 = wb.create_sheet("요약", 0)
    ws0.append(["우주일렉트로닉스 — 커넥터 경쟁사 전시회 참가 (공식 출품사 명단 검증본)"])
    ws0.append([f"생성 {TODAY} · 분야별로 시트가 나뉘어 있습니다"])
    ws0.append([])
    ws0.append(["분야", "수집 전시회", "추적 10곳이 나온 전시회"] + [n for _, n in TRACKED])
    for fk, fn in fields:
        if fk not in counts:
            continue
        rows = [f for f in order if (f.get("field") or "elec") == fk]
        per = []
        for rk, _ in TRACKED:
            per.append(sum(1 for f in rows if rk in found.get(f["key"], {})))
        ws0.append([fn, counts[fk], sum(1 for f in rows if found.get(f["key"]))] + per)
    _style(ws0, 3 + len(TRACKED), head_row=4)
    ws0.column_dimensions["A"].width = 22
    ws0.column_dimensions["B"].width = 12
    ws0.column_dimensions["C"].width = 20

    # ── 확인 상세 (전체)
    ws2 = wb.create_sheet("확인 상세")
    ws2.append(["분야", "전시회", "국가", "시기", "경쟁사", "명단에 적힌 법인명", "부스", "구분", "출처"])
    nm = {}
    for rv in d.get("rivals", []):
        if isinstance(rv, dict):
            nm[rv.get("key")] = rv.get("name", "")
    for r in sorted(d["records"], key=lambda x: (x.get("field", ""), x["fair"], x["rival"])):
        ws2.append([fname.get(r.get("field", ""), ""), r["fair"], r.get("country", ""), r.get("when", ""),
                    nm.get(r["rival"], r["rival"]), r["matched"], r.get("booth", ""),
                    "추적 10곳" if r["rival"] in dict(TRACKED) else "그 외", r.get("url", "")])
    _style(ws2, 9, head_row=1)

    # ── 아직 명단을 못 받은 전시회
    ws3 = wb.create_sheet("미검증(추정 유지)")
    ws3.append(["전시회", "지역", "분야", "일정/장소", "적합도", "규모", "고객접점", "우선순위"] +
               [n for _, n in TRACKED] + ["비고"])
    for name, row in base.items():
        if name in linked:
            continue
        ws3.append([name, row["지역"], row["분야"], row["일정"], row["적합도"], row["규모"], row["접점"],
                    row["우선순위"]] + [row["추정"].get(k, "") for k, _ in TRACKED] +
                   ["출품사 명단을 아직 못 받은 전시회 — 표기는 사람이 넣은 추정치"])
    _style(ws3, 9 + len(TRACKED), head_row=1)

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"UJU_전시회_경쟁사_매트릭스_검증_{TODAY}.xlsx")
    wb.save(out)
    return out, len(order), len(d["records"])


def _sheet_name(fn):
    """시트 이름에 못 쓰는 글자를 걷어낸다(이모지는 남겨도 된다)."""
    return re.sub(r"[\\/*?:\[\]]", "", fn)[:31]


def _sheet(ws, fname, fairs, found, base, linked):
    ws.append([f"{fname} — 커넥터 경쟁사 참가 현황"])
    ws.append(["● 공식 명단에서 확인   ✕ 명단을 받아 확인했으나 없음   ○ 명단을 못 받아 추정 유지"])
    ws.append([])
    ws.append(["#", "전시회", "일정·장소", "확인 출품사"] + [n for _, n in TRACKED] +
              ["추적 10곳", "그 외 경쟁사", "적합도", "규모", "고객접점", "우선순위", "명단 출처"])
    metas = []
    for i, f in enumerate(fairs, 1):
        got = f.get("exhibitors") or 0
        checked = bool(got) and not f.get("error")
        name, brow = base_for(f, base)
        if name:
            linked.add(name)
        hits = found.get(f["key"], {})
        line = [i, f["title"], f.get("when", "") + (f" · {f.get('city','')}" if f.get("city") else ""),
                got if checked else "미확보"]
        for rk, _ in TRACKED:
            line.append("●" if rk in hits else ("✕" if checked else (brow or {}).get("추정", {}).get(rk, "")))
        line += ["", len([k for k in hits if k not in dict(TRACKED)]),
                 (brow or {}).get("적합도", ""), (brow or {}).get("규모", ""), (brow or {}).get("접점", ""),
                 (brow or {}).get("우선순위", ""), f.get("url", "")]
        ws.append(line)
        metas.append((ws.max_row, hits))
    c0, c1 = get_column_letter(5), get_column_letter(4 + len(TRACKED))
    for r, hits in metas:
        ws.cell(row=r, column=5 + len(TRACKED)).value = f'=COUNTIF({c0}{r}:{c1}{r},"●")'
        for i, (rk, _) in enumerate(TRACKED):
            if rk in hits:
                rec = hits[rk][0]
                ws.cell(row=r, column=5 + i).comment = Comment(
                    f"{rec['matched']}\n부스 {rec.get('booth') or '-'}\n출처 {rec.get('url','')}", "expo-radar")
    _style(ws, 10 + len(TRACKED), head_row=4)
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 42
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["D"].width = 11


def _style(ws, ncol, head_row=1, rows_meta=None):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=head_row, column=c)
        cell.font = Font(name=ARIAL, bold=True, color="FFFFFF", size=10)
        cell.fill = HDR_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for row in ws.iter_rows(min_row=head_row + 1):
        for cell in row:
            cell.font = Font(name=ARIAL, size=10)
            cell.border = BORDER
            if cell.value in ("●", "✕", "○"):
                cell.alignment = Alignment(horizontal="center")
                cell.fill = {"●": OK_FILL, "✕": NO_FILL, "○": GUESS_FILL}[cell.value]
    if head_row > 1:
        ws["A1"].font = Font(name=ARIAL, bold=True, size=13)
        ws["A2"].font = Font(name=ARIAL, size=9, color="7F7F7F")
    for c in range(1, ncol + 1):
        if get_column_letter(c) not in ws.column_dimensions:
            ws.column_dimensions[get_column_letter(c)].width = 10
    ws.freeze_panes = ws.cell(row=head_row + 1, column=3)


if __name__ == "__main__":
    bp = None
    if "--base" in sys.argv:
        bp = sys.argv[sys.argv.index("--base") + 1]
    out, nf, nr = build(bp)
    print(f"저장 {out}\n전시회 {nf}개 · 확인 기록 {nr}건")
