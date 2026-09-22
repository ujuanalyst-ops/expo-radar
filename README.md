# 🌍 전시회·박람회 레이더

국내와 전 세계에서 열리는 **전시회·박람회(trade fair)** 를 매일 아침 공식·공개 사이트에서 모아
곧 열리는 전시회 · 세계 지도 · 산업분야 · 정부지원(한국관) 모집으로 보는 로컬 정적 웹앱.
(정부과제 레이더 · 바뀌는 제도 레이더 · 지역 행사 레이더와 같은 구조)

- 열기: `~/Desktop/_런처/20 전시회·박람회 레이더.command` → http://localhost:4199
- 자동 수집: launchd `com.uju.expo-radar` 매일 08:45 → `run_daily.sh` (로그 `logs/YYYY-MM.log`)
- 지금 수집: `./run_daily.sh` (6~8분)
- 공유용 한 파일: `share/전시회레이더_YYYY-MM-DD.html` (앞으로 6개월·볼 만한 것만 추려 1.7MB)

첫 수집 기준 **17,900여 건 · 134개국 · 출처 6곳**.

## 수집처 (모두 로그인·API키 없음)

| 키 | 출처 | 건수 | 방법 · 함정 |
|---|---|---|---|
| `akei` | 한국전시산업진흥회 전시회 일정 | ~360 | `bbs/board.php?bo_table=schedule&searchYear&searchMonth&page` 월별(**시작 월** 기준) 14개월. 지역 필드가 없어 `taxonomy.VENUES` 장소명으로 판정 |
| `coex` / `kintex` / `bexco` | 코엑스·킨텍스·벡스코 자체 일정 | ~130 | AKEI에 없는 건 보강. 코엑스 팝업스토어는 전시회가 아니라 제외 |
| `gep` | **KOTRA 글로벌전시플랫폼(GEP) 해외전시회 DB** | ~2,300 | `POST /gept/ovrss/exbi/exbiInfo/selectOvrssExbiInfoList.do` · **한글 전시회명·국가·도시·설명·국고지원 여부·UFI/AUMA 인증**까지 준다. ①개최기간 검색은 **1년 이내**만 되므로 지난 45일/앞으로 1년 두 번에 나눠 받는다 ②`rowsPerPage`가 진짜 쪽 크기(`pageUnit`은 무시됨) ③목록 응답에 **base64 썸네일**이 붙어 한 쪽이 5MB → 받자마자 `fileInfo`를 버리고 쪽 단위 병렬 수신 ④`2026-09`처럼 월까지만 적힌 건이 섞여 있다 |
| `eventseye` | **EventsEye 세계 전시회 달력** | ~15,800 | `fairs/d1_trade-shows_<월>_<연도오프셋>[_쪽].html`, 1쪽 50건·한 달 20~30쪽. **cp1252 인코딩**(utf-8로 읽으면 깨짐), 3번째 칸에 `도시 (국가)`와 전시장이 같이 온다. 날짜가 `Sept. 2026`처럼 **월까지만** 나오는 건이 많아 `date_prec`로 구분 |
| (부가) `gep_apply` | GEP 한국관·개별참가 **모집공고** | ~150 | `prtpcoAplyStpltSelect.do` — 전시회 이름으로 매칭해 '한국관 모집 D-n' 배지를 붙인다 |

검토 후 뺀 곳: **10times.com**(= biztradeshows, Cloudflare 403), **AUMA·tradefairdates**(독일 위주 + EventsEye와 중복), EXCO·김대중컨벤션·송도컨벤시아 자체 사이트(렌더 문제 — AKEI가 커버).

## 중복 합치기

1. `(정규화한 이름 + 국가 + 개최 월)` — 이름은 연도·회차·괄호·기호를 떼고 비교. 한글·영문 이름 둘 다 열쇠로 쓴다.
2. GEP는 **한글 이름만**, EventsEye는 **영문 이름만** 있어 1번으로 안 붙는 짝이 많다 → `같은 나라 + 같은 시작일 + 같은 종료일`인 무리가 **딱 둘**이고, 출처가 `{gep}`·`{eventseye}`로 갈리고, 아는 도시면 도시가 같고, 산업분야가 겹칠 때만 추가로 합친다. 합친 내역은 `data/merge_log.json`에 남는다(현재 127건).

## 🏁 경쟁사 출품 (`rivals.py` → `data/rivals.json`)

**전시회 쪽 출품사 명단**을 읽는다. (경쟁사 홈페이지는 대부분 봇을 막아 두어 쓸모가 없었다 — 그 방식은 버렸다.)

| 플랫폼 | 방법 | 쓰는 전시회 |
|---|---|---|
| `mys` | **MapYourShow** `<show>.mapyourshow.com/8_0/ajax/remote-proxy.cfm?action=search&searchtype=exhibitorgallery&searchsize=6000` · **갤러리 페이지를 먼저 열어 세션 쿠키를 받아야** API가 403이 아니다 | DesignCon(26·27) · CES · Automate(26·27) · IPC APEX · Interwire · AAPEX · SEMA · MD&M West(26·27) · **ISE(26·27) · InfoComm · IMTS · PACK EXPO** |
| `xlsx` | 메세 뮌헨 계열(jl.medien)이 공개하는 출품사 엑셀 | electronica (productronica·automatica는 명단 공개 시점 전) |
| `jsae` | 자동차기술회 人とくるまのテクノロジー展 출품사 목록(서버 렌더링, `data-exbname`) | JSAE 요코하마·나고야 |
| `ceatec` | `exhibition/exhibitor-list.php?…&per=all` 한 번에 전체 카드 | CEATEC |
| `kes` | `POST /fairOnline.do` (JSON) 12건씩 · `SYSTEM_IDX`는 회차마다 바뀜(2026=232) | 한국전자전 KES |
| `table` | `<tbody><tr><td>` 3칸 표 + `offset=` 페이징 | KOAA SHOW(국제 모빌리티 산업전) |
| `tems` | tems-system(일본 전시 플랫폼) 出展者一覧, `<td class="name">` | JPCA Show(WIRE Japan Show 동시개최) |
| `manual` | 출품사 명단을 웹에 안 여는 전시회 — 주최측이 **글로 공개한** 참가·참관 기업만 옮겨 적는다(ICH 동관: 명단은 위챗 미니프로그램으로만 제공, 홈페이지엔 '지난 회차에 다녀간 세계적 기업' 목록만) | ICH 동관 커넥터전 |
| `taitra` | 대만무역센터 — 전시회 홈페이지 명단은 검색 버튼을 눌러야 나오지만, **부스 배치도가 쓰는 정적 JSON**에 전체 출품사가 있다: `booth.e-taitra.com.tw/db/map/<회차코드>/Exhibitor_en-US.json` (2026CP=COMPUTEX, 2026AP=TAIPEI AMPA) | COMPUTEX · TAIPEI AMPA |
| `hktdc` | Next.js 서버 렌더링 → `__NEXT_DATA__.props.pageProps.exhibitorListData`. **`?pageNum=N`만 서버에서 먹는다**(`page=`·`size=`는 무시) | 홍콩 전자전(추계·춘계) · electronicAsia |

- **지난 회차 명단도 모은다.** 연례 전시회는 직전 회차 출품사가 다음 회차에도 거의 그대로 나온다 →
  `kind=past` 기록은 **`cycle`년 뒤 같은 전시회**(electronica는 격년이라 2년)에 붙이고 '지난 회차 명단'으로 표시한다.
  MapYourShow는 호스트 이름만 바꾸면 지난 회차가 열린다(`dcon26` ↔ `dcon27`). 반대로 메세 뮌헨 엑셀은
  지난 회차 주소가 현재 회차로 넘어가 아카이브가 없다.
- 현재 **전시회 33회차(2025·2026·2027) · 출품사 34,712개사**를 훑고, 경쟁사 **57곳**(사용자 지정 14 + 내가 추가 28 + 명단에서 찾아 승격 15)을 추적한다.
- 명단만 있고 우리 전시회 DB에 없는 전시회(JSAE·IPC APEX)는 `build.fairs_as_events()`가 항목을 만들어 넣는다(날짜는 월까지만).
- 출품사 명단은 **통째로 저장**한다(`data/rivals.json` → `app-data.js`). 전시회를 누르면 그 명단이 열려
  **잠재 고객 리스트**로 쓸 수 있고, 그 위에 경쟁사가 랭크된다.
- **새 경쟁사 발굴**: 이름이나 소개글이 connector·interconnect·terminal·harness인데 우리 목록에 없는 회사를
  `discovered`로 뽑는다(유통상·계측기·반도체는 `NOT_RIVAL`로 제외). 현재 **99곳**. 두 곳 이상 전시회에
  겹쳐 나오면 우선순위가 높다 — 회사를 누르면 **그 회사가 나오는 전시회 전부**가 서랍으로 열린다
  (같은 회사의 지사·법인 표기는 `norm_co()`로 묶는다).
- 경쟁사는 `RIVALS`(55곳: 사용자 지정 14 + 내가 추가한 글로벌·중국·일본·국내 경쟁사)에 정규식으로 등록. 전시회 추가는 `FAIRS`에 한 줄.

**🔌 커넥터·케이블 전용 전시회**: 이름이 커넥터·케이블·하네스·단자인 전시회는 `taxonomy.is_connector_fair()`로
따로 뽑아 탭에 always 표시한다 — **출품사 명단을 공개하지 않는 전시회가 목록에서 사라지는 문제**를 막으려고 만들었다
(ICH 동관·WIRE China·CWIEME·Electrical Wire Processing Expo 등 20건). 명단이 없으면 '명단 미공개' 배지와 검색 링크를 준다.
함정: '요**하네스**버그'가 하네스로 걸린다 → `NOT_CONN_FAIR`에 지명 제외.
또 하나: **경쟁사가 한 곳도 안 걸린 전시회라도 명단은 전시회에 연결해야 한다**(안 그러면 205개사를 받아 놓고
화면엔 '명단 미공개'로 뜬다) — `build.attach_rivals()`가 records와 별개로 fairs도 매칭한다.

**과거 회차(이력)**: MapYourShow는 **직전 1회차까지만** 살아 있다(dcon25·automate25 등은 API가 HTML을 돌려줌 = 폐쇄).
살아 있는 과거 회차: COMPUTEX 2025 · TAIPEI AMPA 2025 · JPCA Show 2025 · PACK EXPO 2024·2025(TAITRA·tems-system은
정적 파일이라 오래 남는다). **2024년은 대부분 이미 닫혀 있어 못 가져온다.**

**커넥터 전용 전시회 20곳을 하나씩 확인한 결과**(2026-09-16):
| 결과 | 전시회 |
|---|---|
| ✅ 명단 확보 | **wire Russia / Metallurgy Russia 2027** (참가업체 카탈로그 205개사, 서버 렌더링) |
| △ 주최측 공개분만 | **ICH 동관** — 출품사 명단은 위챗 미니프로그램 전용, 홈페이지엔 '지난 회차 방문 기업'만(17곳) |
| ✗ 명단 페이지 없음 | wire China(중문 사이트에 展商 메뉴만) · Coiltech(JS로도 메뉴만 나옴) · Electrical Wire Processing Expo(Current Exhibitors 링크가 404) · CWIEME(사이트 526 오류) |
| ✗ 공식 사이트 자체가 없음 | Wire&Cable 베트남·인니·필리핀·말레이시아, WORLD OF CABLE/WIRE TECH EXPO(폴란드), CABLES EUROPE — EventsEye에 **개최장소 주소만** 있고 전시회 공식 사이트가 등록돼 있지 않다 |


**🏁 경쟁사 탭 순서**: ①경쟁사 칩 ②**경쟁사가 나오는 전시회 일정**(맨 위)
③전시회별 경쟁사 밀집도 랭킹(경쟁사 10곳 이상 = 관심) ④🔌 커넥터·케이블 전용 전시회 ⑤명단에서 새로 찾은 커넥터 업체.
연도별 이력은 **회사를 눌렀을 때 나오는 서랍**에서 연도별로 묶어 보여 준다(연도별 표는 쓰지 않기로 했다). 전시회를 누르면 **출품사 전체 명단 서랍**
(경쟁사/커넥터 계열/전체 필터 + 이름 검색 + 구글 검색 링크).

**자바스크립트로만 명단을 그리는 사이트**는 `headless.py`(맥에 깔린 크롬 `--dump-dom`, 추가 설치 없음)로
렌더링한 HTML을 받아 파싱하면 된다 — `python3 headless.py <url> [대기ms]`. 다만 **클릭이 필요한 사이트**
(컴퓨텍스·TAIPEI AMPA는 검색 버튼을 눌러야 명단이 나온다)는 이것으로도 안 되고 CDP 자동화가 필요하다.

**전시회를 더 붙이는 법**: MapYourShow는 호스트 이름만 알면 끝이다(`<약칭><yy>.mapyourshow.com`).
`scratchpad/probe_mys.py` 처럼 후보 호스트를 한꺼번에 찔러 보고 200이 뜨는 것만 `FAIRS`에 넣으면 된다.

못 넣은 곳과 이유:
- **SPS·PCIM·Automechanika**(메세 프랑크푸르트) — 검색이 `api.messefrankfurt.com/service/esb_api` 사설 API + API 키. 키를 꺼내 쓰는 건 접었다.
- **embedded world**(뉘른베르크메세) — Sitecore 검색 API, 공개 엔드포인트 못 찾음.
- **Nepcon Japan**(RX재팬) — 출품사 검색이 개막 2~3개월 전에 열린다(2027-02 개최 → 연말에 재시도).
- ✅ **COMPUTEX·TAIPEI AMPA도 뚫었다** — 홈페이지 명단은 클릭이 필요하지만 **부스 배치도 JSON**을 쓰면 클릭 없이 전량을 받는다.
- **wire/Tube 뒤셀도르프**(케이블 최대) — VIS API는 `x-vis-domain: https://www.wire-tradefair.com` 헤더로 `/components/config`까지 열리지만, 출품사 엔드포인트는 회차(wire 2026/Tube 2026)를 고르는 세션이 있어야 `{}`가 아닌 값이 온다. 남은 숙제.
- **ELEXCON**(봇 차단 403) · **electronica China**(출품사 명단 페이지 자체가 없음).
- ✅ **HKTDC 홍콩전자전은 뚫었다** — JS 렌더인 줄 알았으나 `__NEXT_DATA__`에 명단이 있고 `?pageNum=`이 서버에서 먹었다(브라우저 불필요).
- 국내: **KES 468곳·KOAA SHOW 154곳을 넣었지만 커넥터 업체가 사실상 없다**(KES 0곳, KOAA 5곳 중 커넥터는 벨로우즈 1곳). 국내 커넥터 경쟁사는 전시회 출품보다 OEM 직거래 중심으로 보인다.

## 🤖 로봇 전시회 출품사 (`robots.py` → `data/robots.json` · `app-robots.js` · `robots.html`)

경쟁사만 고르는 rivals.py와 달리 **로봇 전시회의 출품사 명단을 통째로** 모아 회사 단위로 합친다.
회사마다 출처 전시회·부스, 소개글(무엇을 만드나), 전시 하이라이트(무엇을 전시했나), 카테고리·산업·분야, 소개글에서 발췌한 강점 문구를 붙인다.

| 전시회 | 방법 | 비고 |
|---|---|---|
| Automate 2026·2027 (미국) | MapYourShow 검색 API | 2026은 소개글 포함, 2027은 회사명만(회차 임박 시 채워짐) |
| iREX 2025 국際ロボット展 (도쿄) | `/api/parts/get_exhibitor_grid` (60건씩) | 소개글·전시 하이라이트·전시회 분야 태그 |
| automatica 2025 (뮌헨) | 출품사 포털의 엑셀 내려받기(`mode=xls`) | 회사·홀·도시·국가만 |
| ProMat 2025·2027 (미국, 물류) | MapYourShow | 종합 전시회라 로봇·AMR·피킹 관련 업체만(`ROBOT_RE`) |
| 로보월드 2026 (킨텍스) | `visitors/list_of_exhibitors.php?offset=` + 팝업 | 부스·전시분야·홈페이지·회사소개·제품소개 |
| THE NEXT AI 2026 (창원) | `visitors/companies?page=` + 상세 | 홈페이지·소개·출품내역 |
| Robot Tech Show 2026 (코엑스) | 엑스포럼 `floorplan.exporum.com/api/exhibitors` | 존 이름으로 로봇테크쇼만 |
| ROBEX 2025 (대구) | FIX `bis_info_list.asp?site=robex&yy=` | 디렉토리 등록 업체만 |
| WRC 2026 (베이징) | `/expo/` 관별 목록 + `/expo/company/N.html` | 부스·회사소개(중) |
| FAIR plus 2026 (선전) | 워드프레스 REST `wp/v2/exhibitor` + 상세 | 회사소개(중) |
| HRTE 2026 (항저우) | 정적 표 `arte.net.cn/about_36/` | 회사명(중·영)·부스 |
| RAV 2026 (베트남 박닌, VIMF) | 워드프레스 REST `wp/v2/posts?categories=222` | 통합 명단이라 로봇 관련만 |
| Robotics Slovenia 2027 · Serbia 2026 | Momentus(Ungerboeck) `VFPServer/GetInitialData` + 상세 | 홈페이지·제품군·국가 |
| ROBOTICS Warsaw · Warsaw Automatica 2026 | Ptak 워드프레스 정적 카탈로그 | 회사명·부스 |
| STOM-ROBOTICS 2026 (Kielce) | `api/modules/exhibitors-list/search/…` | 회사명·국가·부스 |
| automatica 2025 (뮌헨) | 상세 페이지 `exhibitorDetail/ID/…` (캐시 `data/aut_cache.json`) | 홈페이지·제품군·소개(독) |

**현 회차 명단을 안 여는 전시회는 지난 회차로 채운다**

| 전시회 | 대체 자료 |
|---|---|
| Robotics Summit 2027 · RoboBusiness 2026 | 2023 회차 ExpoFP 배치도(`<show>.expofp.com/data/data.js`) — 행사 후에도 남아 있다 |
| ROBOT4MANUFACTURING 2026 | 주최측이 올린 2024 회차 PDF 명단 — `_pdf_lines()`가 FlateDecode 스트림을 풀고 폰트별 ToUnicode CMap으로 글자를 되돌린다(폰트를 섞으면 R이 w로 깨진다) |
| TAIROS 2026 | Cloudflare 봇 차단 — 인터넷 아카이브 스냅샷의 목록 1쪽(827곳 중 20곳)만 |

명단을 못 읽는 로봇 전시회와 그 이유는 `NO_LIST`에 적혀 화면 '미확보' 옆에 표시된다.

- **분류**는 소개글·태그의 키워드 규칙(영·일·한·중, `CATS`·`INDS`)이다. 카테고리가 6개를 넘으면 두 번 이상 나온 것만 남긴다. 소개글이 없으면 분류가 빈다.
- **강점**은 '세계 최대·선도·최초·특허·수상·N년' 같은 표지(`STRONG_RE`)가 있는 문장을 그대로 발췌한다 — 회사 자기소개이지 검증된 사실이 아니다.
- **국가**는 명단에 있으면 그것, 없으면 법인명(`NAME_COUNTRY`)으로 짐작한다. 같은 회사의 여러 법인이 합쳐져 국가가 여러 개 붙을 수 있다.
- **전세계 로봇 전시회 목록**은 `data/expos.json`에서 제목(core)·설명에 로봇이 들어간 것을 고른다. 명단을 웹에 안 여는 곳(로보월드·ROBEX·WRC·CIROS·TAIROS)은 '미확보'로만 표시.
- 회차가 바뀌면 `FAIRS`에 새 회차(호스트)를 한 줄 추가한다. 화면은 `robots.html`(CSV 내려받기 포함).

## 업무 관련도 ★

커넥터·와이어하네스(5) > 전자부품·전장·카메라모듈·electronica(4) > 전자·배터리·EV·센서·디스플레이(3) >
자동차·기계·로봇·금형(2) > 제조·소재·소싱(1) 키워드 + 산업분야 가산점 + 국고지원 + 전시규모 → 10점 만점, 별 5개로 표시.
기준은 `taxonomy.py`의 `RELEVANCE`·`IND_BONUS`만 고치고 `python3 build.py --no-fetch`.

## 구조

`collect.py`(수집) + `rivals.py`(경쟁사 출품) → `taxonomy.py`(산업분야·관련도·국내 전시장) + `countries.py`(국가 사전) →
`build.py`(누적 `data/expos.json`, 상세 캐시 `data/details.json`, 중복 합치기 → `app-data.js`) →
`index.html / app.js / styles.css`. 세계 지도는 `geo_world.py`가 한 번 만든 `app-geo.js`(로빈슨 투영 SVG 패스).

- 분류만 다시: `python3 build.py --no-fetch`
- 한 출처만: `python3 build.py --only=gep`
- 상세(전시장·규모·품목·주최자·홈페이지·참관객 통계)는 하루 400건씩 가까운 날짜·관련도 순으로 보강 → `--detail-budget=800`
- 동시 실행은 `data/.build.lock`으로 줄 세움
- 지도를 다시 그릴 일이 있으면 `python3 geo_world.py`

## 탭

곧 열리는 전시회 · 🎯 우리 관련·지원 · 🏁 경쟁사 · 🌍 세계 지도 · 🏭 산업분야 · 🇰🇷 국내 · 📅 달력 · 🆕 새로 등록 · 🧭 출처

- **🎯 우리 관련·지원**: ①정부지원·한국관 모집(신청 마감 D-day) ②커넥터·전장 관련도 상위 ③참가업체 300사·3만㎡ 이상 대형 전시회
- **📅 달력**: 개막일에만 표시한다(여러 주짜리 전시회를 매일 찍으면 달력이 같은 이름으로 도배됨). 날짜가 '○월 중'으로만 공개된 건은 달력 아래 목록으로 따로
- **🆕 새로 등록**: 출처를 처음 붙인 날은 그 출처 전체가 같은 `first_seen`이라 신규가 아니다 → 출처별 최소 `first_seen`을 기준선으로 빼고 센다(그래서 **첫날은 0건**, 이튿날부터 쌓인다)

## 알아둘 것

- GEP에 `2026.09.01 ~ 09.30`처럼 **한 달짜리로 등록된 건**이 있다. 실제 회기가 아닐 수 있어 상세 서랍에 "등록된 기간이 N일 — 주최자 공지로 확인하세요"를 띄운다.
- EventsEye는 프랑스 운영이라 프랑스·유럽 비중이 높다(나라 순위 1위 프랑스). 아시아·중동은 GEP 쪽이 촘촘하다.
- 참가업체수·참관객수·전시면적은 **KOTRA가 조사한 직전 회차 실적**이라 비어 있는 건이 많다(상세 보강이 닿은 건만).
