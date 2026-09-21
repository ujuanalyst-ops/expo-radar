#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""맥에 이미 깔린 크롬을 헤드리스로 띄워 **자바스크립트가 그린 뒤의 HTML**을 받아온다.

playwright·selenium 같은 추가 설치 없이, 크롬의 `--dump-dom` 만 쓴다.
자바스크립트로만 명단을 그리는 전시회(홍콩전자전·컴퓨텍스 등)를 읽으려고 만들었다.

  python3 headless.py "https://..."        # 렌더링된 HTML을 표준출력으로
"""

import os
import shutil
import subprocess
import sys
import tempfile

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def available():
    return os.path.exists(CHROME)


def render(url, wait_ms=9000, timeout=90):
    """URL을 렌더링한 뒤의 DOM 문자열. 실패하면 빈 문자열.

    크롬은 프로필 폴더를 잠그기 때문에 호출마다 임시 프로필을 쓴다(동시에 여러 개 띄우려고).
    사이트가 롱폴링을 물고 있으면 --dump-dom 이 끝나지 않으므로 timeout 으로 끊는다.
    """
    if not available():
        return ""
    prof = tempfile.mkdtemp(prefix="expo-chrome-")
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
           "--disable-extensions", "--disable-background-networking", "--mute-audio",
           "--blink-settings=imagesEnabled=false", f"--user-agent={UA}",
           f"--virtual-time-budget={wait_ms}", f"--user-data-dir={prof}", "--dump-dom", url]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=timeout).stdout
        return out.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as e:  # 롱폴링 사이트 — 그때까지 찍힌 DOM이라도 쓴다
        return (e.stdout or b"").decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""
    finally:
        shutil.rmtree(prof, ignore_errors=True)


if __name__ == "__main__":
    html = render(sys.argv[1], wait_ms=int(sys.argv[2]) if len(sys.argv) > 2 else 9000)
    sys.stdout.write(html)
    print(f"\n<!-- {len(html)} bytes -->", file=sys.stderr)
