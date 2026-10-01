#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""맥 한글 파일명을 NFC(완성형)로 바꾼다 — 메일로 보내면 'ㄷㅣㅈㅏㅇㅣㄴ'처럼 자모가 풀리는 문제.

맥(Finder·다운로드)은 한글 파일명을 NFD(자모 분리형)로 저장하는 경우가 많고,
그대로 첨부하면 윈도우·아웃룩 받는 쪽에서 글자가 풀려 보인다.
파일명을 NFC로 고쳐 두면 맥에서는 똑같이 보이고, 받는 쪽도 정상으로 보인다.

  python3 tools/nfc_names.py ~/Downloads            # 바꿀 목록만 보기
  python3 tools/nfc_names.py ~/Downloads --apply    # 실제로 이름 바꾸기
"""

import os
import sys
import unicodedata


def main(args):
    apply = "--apply" in args
    roots = [a for a in args if a != "--apply"] or ["."]
    n = 0
    for root in roots:
        # 아래에서부터 바꿔야 상위 폴더 이름이 바뀌어도 경로가 안 꼬인다
        # 권한이 막히면(맥 개인정보 보호) 조용히 넘어가지 않고 알린다
        for d, dirs, files in os.walk(os.path.expanduser(root), topdown=False,
                                      onerror=lambda e: print(f"읽기 실패: {e}", file=sys.stderr)):
            for name in files + dirs:
                nfc = unicodedata.normalize("NFC", name)
                if nfc == name:
                    continue
                n += 1
                print(os.path.join(d, nfc))
                if apply:
                    os.rename(os.path.join(d, name), os.path.join(d, nfc))
    print(f"\n{n:,}개 {'바꿈' if apply else '바꿀 대상 (--apply 로 실행)'}")


if __name__ == "__main__":
    main(sys.argv[1:])
