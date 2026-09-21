#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""세계 지도 만들기 — world-atlas TopoJSON(110m) → 로빈슨 투영 SVG 패스(`app-geo.js`).

한 번만 돌리면 된다. 화면(app.js)은 나라별 path와 중심점(cx, cy),
그리고 lat/lon → x/y 변환 계수(proj)를 함께 받아 도시 점도 찍는다.
"""

import json
import math
import os

import countries

HERE = os.path.dirname(os.path.abspath(__file__))
W = 1000.0

# 로빈슨 투영 계수표 (위도 0°~90°, 5° 간격)
RX = [1.0000, 0.9986, 0.9954, 0.9900, 0.9822, 0.9730, 0.9600, 0.9427, 0.9216, 0.8962,
      0.8679, 0.8350, 0.7986, 0.7597, 0.7186, 0.6732, 0.6213, 0.5722, 0.5322]
RY = [0.0000, 0.0620, 0.1240, 0.1860, 0.2480, 0.3100, 0.3720, 0.4340, 0.4958, 0.5571,
      0.6176, 0.6769, 0.7346, 0.7903, 0.8435, 0.8936, 0.9394, 0.9761, 1.0000]
KX, KY = 0.8487, 1.3523
HALF_W = KX * math.pi          # 투영 좌표계에서 경도 180°까지의 폭
HALF_H = KY * 1.0
SCALE = W / (2 * HALF_W)
H = round(2 * HALF_H * SCALE, 2)


def _interp(tbl, alat):
    i = min(int(alat / 5.0), 17)
    t = (alat - i * 5.0) / 5.0
    return tbl[i] + (tbl[i + 1] - tbl[i]) * t


def project(lat, lon):
    """위경도 → 화면 좌표(픽셀)."""
    a = min(abs(lat), 90.0)
    x = KX * _interp(RX, a) * math.radians(lon)
    y = KY * _interp(RY, a) * (1 if lat >= 0 else -1)
    return (x + HALF_W) * SCALE, (HALF_H - y) * SCALE


def _decode_arcs(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    out = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((y * sy + ty, x * sx + tx))  # (lat, lon)
        out.append(pts)
    return out


def _ring(arcs, idxs):
    pts = []
    for i in idxs:
        a = arcs[~i][::-1] if i < 0 else arcs[i]
        pts.extend(a[1:] if pts else a)
    return pts


def _area_centroid(ring):
    """투영 좌표 기준 다각형 넓이와 무게중심."""
    xy = [project(la, lo) for la, lo in ring]
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(xy, xy[1:] + xy[:1]):
        c = x0 * y1 - x1 * y0
        a += c
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    if abs(a) < 1e-9:
        xs = [p[0] for p in xy]
        ys = [p[1] for p in xy]
        return 0.0, (sum(xs) / len(xs), sum(ys) / len(ys))
    return abs(a / 2), (cx / (3 * a), cy / (3 * a))


def _path(ring):
    d = []
    last = None
    for la, lo in ring:
        x, y = project(la, lo)
        p = (round(x, 1), round(y, 1))
        if p == last:
            continue
        d.append(("M" if last is None else "L") + f"{p[0]},{p[1]}")
        last = p
    return "".join(d) + "Z" if len(d) > 2 else ""


def build():
    topo = json.load(open(os.path.join(HERE, "geo", "countries-110m.json"), encoding="utf-8"))
    arcs = _decode_arcs(topo)
    num2iso = {c["num"]: c["iso2"] for c in countries.COUNTRIES.values()}

    shapes, misses = {}, []
    for g in topo["objects"]["countries"]["geometries"]:
        nid = str(g.get("id", "")).zfill(3)
        a2 = num2iso.get(nid) or countries.iso2(g["properties"].get("name", ""))
        if not a2:
            misses.append(g["properties"].get("name"))
            continue
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        d, best, cxy = [], 0.0, None
        for poly in polys:
            for k, ring_idx in enumerate(poly):
                ring = _ring(arcs, ring_idx)
                p = _path(ring)
                if p:
                    d.append(p)
                if k == 0:
                    a, c = _area_centroid(ring)
                    if a > best:
                        best, cxy = a, c
        if not d:
            continue
        shapes[a2] = {"d": "".join(d), "cx": round(cxy[0], 1), "cy": round(cxy[1], 1)}

    # 지도에 없는 도시국가는 좌표로 점만 찍는다
    for a2, (la, lo) in countries.FALLBACK_LL.items():
        if a2 not in shapes:
            x, y = project(la, lo)
            shapes[a2] = {"d": "", "cx": round(x, 1), "cy": round(y, 1)}

    meta = {a2: {"ko": c["ko"], "en": c["en"], "region": c["region"], "sub": c["sub"]}
            for a2, c in countries.COUNTRIES.items()}
    js = ("// geo_world.py 가 만든 파일 — 직접 고치지 말 것\n"
          "window.GEO=" + json.dumps({
              "w": W, "h": H, "kx": KX, "ky": KY, "scale": SCALE,
              "rx": RX, "ry": RY, "shapes": shapes, "country": meta,
          }, ensure_ascii=False, separators=(",", ":")) + ";\n")
    open(os.path.join(HERE, "app-geo.js"), "w", encoding="utf-8").write(js)
    print(f"app-geo.js 생성 · 나라 {len(shapes)}개 · {len(js) // 1024}KB · 매칭 실패 {misses}")


if __name__ == "__main__":
    build()
