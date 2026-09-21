#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""공유용 단일 HTML — CSS·JS·데이터를 한 파일에 담아 메일 첨부로 보내도 더블클릭으로 열린다.

전체 데이터(9MB)는 메일로 보내기 버거워서 **앞으로 6개월 + 볼 만한 것**만 담는다:
국내 전시회 전부 · 정부지원/한국관 모집 · 업무 관련도 ★★ 이상 · 참가업체 200사 이상.

  python3 build_share.py            # share/전시회레이더_YYYY-MM-DD.html
  python3 build_share.py --open     # 만들고 바로 열기
  python3 build_share.py --full     # 추리지 않고 통째로
"""

import datetime
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SHARE = os.path.join(ROOT, "share")

BANNER = ('<div class="sharebar">📄 <b>공유용 스냅샷</b> — {today} 기준 · {n}건 '
          '(앞으로 6개월, 국내 전시회 전부 + 정부지원·업무 관련·대형 전시회만 추렸습니다). '
          '일정은 바뀔 수 있으니 참가·참관 전에 <b>원문 정보</b>로 확인해 주세요.</div>')
BANNER_CSS = ".sharebar{background:#fff6e5;border-bottom:1px solid #f0dcb8;color:#7a5320;padding:9px 28px;font-size:12.5px}"


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def trim(js):
    payload = json.loads(js[js.index("=") + 1:].rstrip().rstrip(";"))
    today = payload["today"]
    horizon = (datetime.date.fromisoformat(today) + datetime.timedelta(days=185)).isoformat()
    keep = []
    for e in payload["events"]:
        if (e.get("e") or e["s"]) < today or e["s"] > horizon:
            continue
        if (e["c"] == "KR" or e.get("sup") or e.get("ap") or (e.get("rel") or 0) >= 3
                or (e.get("ex") or 0) >= 200):
            keep.append(e)
    payload["events"] = keep
    used = {e["c"] for e in keep}
    payload["countries"] = {k: v for k, v in payload["countries"].items() if k in used}
    return payload, today


def main():
    payload, today = trim(read("app-data.js"))
    full = "--full" in sys.argv
    if full:
        data_js = read("app-data.js")
        n = len(json.loads(data_js[data_js.index("=") + 1:].rstrip().rstrip(";"))["events"])
    else:
        data_js = "window.DATA=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";"
        n = len(payload["events"])

    html = re.sub(r"\?v=\d+", "", read("index.html"))
    html = html.replace('<link rel="stylesheet" href="styles.css">',
                        "<style>\n" + read("styles.css") + BANNER_CSS + "\n</style>")
    for name, body in (("app-data.js", data_js), ("app-geo.js", read("app-geo.js")), ("app.js", read("app.js"))):
        tag = f'<script src="{name}"></script>'
        if tag not in html:
            sys.exit(f"index.html 구조가 바뀌어 {name} 인라인에 실패했습니다.")
        html = html.replace(tag, "<script>\n" + body.replace("</script", "<\\/script") + "\n</script>")
    html = html.replace("<title>전시회·박람회 레이더</title>",
                        f"<title>전시회·박람회 레이더 ({today} 기준)</title>")
    html = html.replace("<body>", "<body>\n" + BANNER.format(today=today, n=f"{n:,}"), 1)

    os.makedirs(SHARE, exist_ok=True)
    out = os.path.join(SHARE, f"전시회레이더_{today}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"생성 완료: {out}  ({os.path.getsize(out) / 1024 / 1024:.1f} MB · {n:,}건)")
    if "--open" in sys.argv:
        subprocess.run(["open", out], check=False)


if __name__ == "__main__":
    main()
