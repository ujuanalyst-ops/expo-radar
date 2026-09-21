#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전시회·박람회 레이더 로컬 서버 — 파이썬 기본 http.server + 캐시 금지 헤더.

기본 http.server는 캐시 지시 헤더를 보내지 않아 브라우저(특히 사파리)가 예전 app.js를 재사용할 수 있다.
모든 응답에 no-cache를 붙여 새로고침 한 번이면 항상 최신 파일을 받게 한다.

  python3 serve.py            # 포트 4199, 이 폴더를 서비스
  python3 serve.py 4199
"""

import functools
import http.server
import os
import socket
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()


class DualStackServer(http.server.ThreadingHTTPServer):
    """IPv6 소켓 하나로 IPv4까지 받는다 — localhost·127.0.0.1·맥이름.local 어느 주소로 와도 응답."""
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4199
    handler = functools.partial(NoCacheHandler, directory=ROOT)
    srv = DualStackServer(("::", port), handler)
    print(f"전시회·박람회 레이더 서버: http://localhost:{port}  (폴더 {ROOT})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
