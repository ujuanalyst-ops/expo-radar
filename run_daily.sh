#!/bin/bash
# 매일 1회 국내·전세계 전시회 수집 → 화면 데이터 생성
# launchd(com.uju.expo-radar)가 매일 08:45에 호출한다. 수동 실행도 가능.

cd "$(dirname "$0")" || exit 1

# 수집 결과를 GitHub에 커밋·push. 인증은 맥 키체인(osxkeychain)에 저장된 토큰을 쓴다.
# 바뀐 게 없으면 건너뛰고, push가 실패해도 수집 로그는 그대로 남긴다.
publish_github() {
  if git diff --quiet && git diff --cached --quiet; then
    echo "GitHub: 변경 없음"; return 0
  fi
  git add -A
  git -c user.name="expo-radar bot" -c user.email="ujuanalyst@gmail.com" \
    commit -q -m "데이터 갱신 $(date +%F)" || return 1
  GIT_TERMINAL_PROMPT=0 git push -q origin main && echo "GitHub: push 완료 $(date +%F)" \
    || echo "GitHub: push 실패 — 토큰 만료 여부 확인"
}

LOG="logs/$(date +%Y-%m).log"
mkdir -p logs
{
  echo "──────── $(date '+%F %T') 수집 시작"
  /usr/bin/python3 -u rivals.py       # 경쟁사 출품 정보(전시회 출품사 명단·경쟁사 행사 페이지)
  /usr/bin/python3 -u robots.py       # 로봇 전시회 출품사 전체 명단 → app-robots.js (robots.html)
  /usr/bin/python3 -u build.py        # -u: 진행 상황이 로그에 바로바로 찍히게
  /usr/bin/python3 build_share.py     # 공유용 단일 HTML(share/)도 매일 갱신
  publish_github                      # 새 app-data.js를 GitHub(공개 페이지)에 올린다
  echo "──────── $(date '+%F %T') 완료"
} >> "$LOG" 2>&1

tail -n 14 "$LOG"
