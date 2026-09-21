#!/bin/bash
# 매일 1회 국내·전세계 전시회 수집 → 화면 데이터 생성
# launchd(com.uju.expo-radar)가 매일 08:45에 호출한다. 수동 실행도 가능.

cd "$(dirname "$0")" || exit 1

LOG="logs/$(date +%Y-%m).log"
mkdir -p logs
{
  echo "──────── $(date '+%F %T') 수집 시작"
  /usr/bin/python3 -u rivals.py       # 경쟁사 출품 정보(전시회 출품사 명단·경쟁사 행사 페이지)
  /usr/bin/python3 -u build.py        # -u: 진행 상황이 로그에 바로바로 찍히게
  /usr/bin/python3 build_share.py     # 공유용 단일 HTML(share/)도 매일 갱신
  echo "──────── $(date '+%F %T') 완료"
} >> "$LOG" 2>&1

tail -n 14 "$LOG"
