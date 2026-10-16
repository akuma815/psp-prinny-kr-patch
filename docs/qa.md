# QA 및 검증 기록

## QA-RESULT-FIX-ISO-20260725 — 푯말·시간·마리 통합

- 결과: PASS(정적 삽입, 77개 BOOT UI 슬롯, 폰트, 컨테이너 왕복, 기존 슬롯 밖 BOOT 코드 보존), PENDING(실제 화면).
- ISO: `work/production/Prinny_ULJS00150_KR_Latest_20260725_ResultFix.iso`
- 크기/SHA-256: `500,465,664` bytes / `754c8b2b05cf9838937e07292522e2acc8bdae36befafe65861e08d36d9add7c`.
- 푯말: record 82 texture 0, 두 PPSSPP 해시 설치본과 갤러리 정본 SHA-256 `f5dd9b65bc85483f41e61ceb2212502f8df34f824ab2973d60c95f45ca679eba`.
- 시간: `클리어 시간`, `최고 기록` 모두 `%02d:%02d:%02d`.
- 수량: `0x0EE000`, `0x0EE008`, `0x0EE010`의 `%d匹` 변형을 `%d마리` 변형으로 교체했다.
- 수동 합격 조건: 작은 푯말이 `튜토리얼`로 보이고, 시간 숫자가 콜론 사이에 겹침 없이 표시되며, 스테이지·보스 사망 수에 `마리`가 표시되고, 기존 대사 타자 출력과 문장부호 간격이 후퇴하지 않아야 한다.

## QA-STAGE-HUD-NATIVE-001 — 스테이지 HUD 3종 ISO 내장

- 기준 빌드: `work/builds/stage_hud_native_poc_20260803/direct_run`.
- 월드 표지판: 텍스처 교체 OFF 사용자 화면 PASS(기존 `QA-WORLD-SIGN-GM3-ISO-001`).
- 튜토리얼 푯말: `SYSTEM.DAT` 새 payload hash `c8321c07`가 PPSSPP 1.19.3의
  `0x08DE41E0` 32KB와 일치해 저장·적재 PASS. 실제 푯말 화면은 PENDING.
- 타이머: `ANIME.DAT/anime95.dat` record 3 texture 0의 새 hash `4a8f828a`,
  보호 영역 밖 인덱스 변경 0. 실제 타이머 RAM·화면은 PENDING.
- 임시 6파일 ISO `F0C59864...F75BB`: ISO 내부 6파일 해시 검증과 PPSSPP Headless
  8초 부팅 PASS. 임시 ISO는 삭제 완료.
- 종료 조건: 텍스처 교체 OFF에서 튜토리얼 5 CLUT 상태 중 노출 상태와 타이머 4 상태의
  한글 가독성·숫자/아이콘 비회귀를 확인하고, 가능하면 실기에서 같은 장면을 확인한다.

## QA-LATEST-INTEGRATED-ISO-20260722 — 최신 대사 통합 빌드

- 결과: PASS(글리프 수요, 고정 슬롯 삽입, 컨테이너 빌드, 전 `102` tests, PPSSPP Headless 8초 부팅·게임 루프), PENDING(실제 화면 대사 전수 확인).
- ISO: `work/production/Prinny_ULJS00150_KR_Latest_20260722.iso`
- 크기/SHA-256: `500,465,664` bytes / `8b2367575b63b256ba6b1707191f3406c63f397a8bfef421ed3489edd1134463`.
- 최신 번역: 완료 `1,523`, 제외 `49`, 고유 한글 `830`; 생성된 `Demo00.dat` SHA-256 `7780baa4b8d03b2d402da232ec4f5c75291908b4de00f80df9a18b7903b9ee60`.
- 부팅 증거: `ULJS00150` 식별, `EBOOT.BIN` 로드, `Disgaea` 모듈 시작, `SYSTEM.DAT` 열기, 계획된 8초 타임아웃까지 게임 루프 유지, 의미 있는 오류 0건.
- 회귀 확인 대상: 최신 수정 대사, 줄바꿈·대사창 넘침, 타자 출력 도중 임시 한자/깨진 글자, 쉼표·느낌표·물음표·말줄임표 간격.
- 정리 결과: 원본 ISO와 최신 ISO만 보존하고 기존 생산·시험·중간 ISO 7개를 삭제했다.

## QA-DIALOG-PUNCTUATION-001 — 문장부호 선행 간격 보정

- 결과: PASS(지문·패치 단위 테스트, 전 100 tests, PPSSPP Headless 8초)·PENDING(실제 대사 출력).
- v3 ISO: `work/production/Prinny_ULJS00150_KR_TwoLine_TypewriterFix_v3_Punctuation2px_Test_20260722.iso`, SHA-256 `98637963c8a6a249e9b67ab74920a5c5818f3602af8eb7a6cb7646983e33d844`.
- 보정 대상: `!`, `?`, `,`, `.`. 각 글리프의 앞뒤에 2px 여백을 넣고, 한글 9px·공백 6px 설정은 유지했다.
- 수동 합격 조건: `자,`, `신입!`, `검까?`에서 문장부호가 앞 음절과 붙지 않고, `....세이브`의 각 점과 뒤 글자가 분리되며, 한글·공백 자간과 타자 출력 안정성이 후퇴하지 않아야 한다.
- 보존 상태: 자동 검증 성공 뒤 v2 테스트 ISO를 삭제하고 v3만 현재 수동 검증 대상으로 보존한다.

## QA-DIALOG-TYPEWRITER-001 — 혼합 CP932 타자 효과 보정

- 결과: v1 PASS(폭 축소)·FAIL(임시 이상 문자), v2 PASS(지문·패치 단위 테스트, 전 97 tests, PPSSPP Headless 8초)·PENDING(실제 대사 출력).
- 이전 Tracking9 후보는 사용자 화면에서 간격 개선이 확인되지 않았고 쉼표 누락 및 출력 중 임시 한자·깨진 글자가 발생해 FAIL이다.
- v2 ISO: `work/production/Prinny_ULJS00150_KR_TwoLine_TypewriterFix_v2_Test_20260722.iso`, SHA-256 `99e80a71f088753ec9f255bd852e45a1f99e534ba8896be03901aef01bba5871`.
- 수동 합격 조건: `자,`의 쉼표가 보이고, 자동 타자 출력 전 과정에서 임시 한자·깨진 한글이 없으며, 버튼으로 즉시 완성하기 전후 문자열이 같고 공백·음절 간격이 이전보다 줄어야 한다.
- 보존 상태: v1과 이전 자간·2줄 시험 ISO 및 v2를 삭제했다. v2 판정과 해시는 회귀 이력으로 유지하며 현재 수동 검증 대상은 v3다.

## QA-DEMO00-TWOLINE-001 — 에트나 대사 수동 2줄 분할

- 결과: PASS(정적 슬롯·컨테이너·관련 11 tests·PPSSPP Headless 8초 부팅), PENDING(실제 대사창 화면).
- 대상: `demo00/081A`, record ID `2074`, index `317`, file offset `0x0000A378`.
- 삽입 줄: 1행 `자, 기한은 내일`, 2행 `아침까지야.`, 3행 빈 문자열.
- 각 줄은 독립적인 35바이트 고정 슬롯이며 널 종료 전 최대 페이로드는 34바이트다. 원문 글자 수 자체를 엔진 제한으로 확정하지 않는다.
- ISO: `work/production/Prinny_ULJS00150_KR_TwoLine_Test_20260719.iso`, SHA-256 `25674dcdc093ea86041c57d330e9e284e4f54d2708e2401d02199ff7ab1eb22c`.
- 수동 합격 조건: 지정 장면에서 두 줄이 순서대로 표시되고 세 번째 줄이 비며, 글자 겹침·대사창 넘침이 없어야 한다.
- 산출물 상태: 이 시험 ISO는 후속 v2 시험판 생성·자동 검증 후 2026-07-22 삭제했다. 위 판정과 해시는 회귀 이력이다.

## QA-INTEGRATED-ISO-20260719 — 최신 통합 테스트 ISO

- 결과: PASS(정적 구조, 관련 11 tests, PPSSPP Headless 8초 부팅), PENDING(사용자 실제 화면 전수 확인).
- ISO: `work/production/Prinny_ULJS00150_KR_Test_20260719_Full.iso`
- 크기/SHA-256: `500,465,664` bytes / `1b99c3f88e81e5c261cb673ea65fdd25a5676c92957ac3bb6783f57520db429c`.
- 내부 검증: `SYSTEM.DAT`, `ANIME.DAT`, `BOOT.BIN`, `EBOOT.BIN`을 ISO9660 경로에서 다시 읽어 빌드 입력 해시와 일치함을 확인했다.
- 부팅 증거: ULJS00150 식별, `EBOOT.BIN` 로드, `Disgaea` 모듈 시작, `SYSTEM.DAT` 열기, 계획된 8초 타임아웃까지 게임 루프 유지, 의미 있는 오류 0건.
- 수동 확인 우선순위: 타이틀과 난이도 UI, Demo00의 `자, 기한은 내일 아침까지야.`, 일반 대사 공백/줄넘침, 튜토리얼 승인 화면, 저장·로드.
- 범위 제외: 월드 간판·거점 메뉴·잔여 일괄 이미지 초안은 replacement texture 상태라 ISO 단독 실행 시 일부 일본어 이미지가 남을 수 있다.
- 산출물 상태: 이 통합 테스트 ISO는 후속 v2 시험판 생성·자동 검증 후 2026-07-22 삭제했다. 확정판 `Prinny_ULJS00150_KR_Demo00_Title_Final.iso`는 별도로 보존한다.

## QA-BASE-MENU-LIVE-001 — record 82 베이스 메뉴 첫 번역

- 결과: PASS(소비자 픽셀 일치, 생성, JSON 보고서, 설치 해시), PENDING(PPSSPP 실제 화면).
- PPSSPP 원본 덤프 `091591e09a963304c67a3ca6.png`와 디코드한 record 82 texture 0은 512×256 RGBA 픽셀이 완전히 일치한다.
- 나무 간판 9개와 투명 목록 슬롯 9개를 모두 한글로 교체했으며 정적 후보에서 일본어 목록 잔재가 없음을 확인했다.
- 원본 SHA-256 `f218d1c9eaabe3836e7d88978b7ad4fde3f819562b01781cf1522609f6f8672e` 보존.
- 2026-07-25 최신 작업본·갤러리·두 팔레트 설치본 SHA-256 `f5dd9b65bc85483f41e61ceb2212502f8df34f824ab2973d60c95f45ca679eba` 일치. 작은 푯말은 `튜토리얼`로 수정했고 최신 통합 ISO에도 반영했다.

## ISSUE-WORLD-SIGN-RESIDUE-001 — 튜토리얼 간판 상단 잔재

- 상태: DEFERRED.
- 실제 화면에서 `튜토리얼` 윗부분에 원문 잔재가 소량 남는다.
- 현재 간판 후보는 유지하며 다음 그래픽 번역을 우선한다. 후속 시 글자 마스크 상단만 확장하고 화살표·철제 프레임 보존을 재검증한다.

## QA-WORLD-SIGN-LIVE-004 — 양쪽 좌우반전·선택 마스크 잔재 제거

- 결과: PASS(정적 생성, JSON 보고서, 문자 코드, 설치 해시), PENDING(PPSSPP 실제 화면).
- `마왕성`·`튜토리얼`은 모두 180도 사전 회전과 좌우반전을 적용했으며, `튜토리얼`은 X축으로 5 텍스처 px 오른쪽 이동했다.
- 문자 코드 검증: `마왕성`=`B9C8 C655 C131`, `튜토리얼`=`D29C D1A0 B9AC C5BC`.
- 일본어 중성색 픽셀을 4px 확장한 선택 마스크로 복원해 외곽선 잔재를 제거하고 화살표·주변 목재 결은 보존했다.
- 원본 SHA-256 `43a1289e643f3688960516c4d67544819d9bd3ba4d97d99654a76e7d81ad89f6` 보존.
- 작업본·설치본 SHA-256 `4e61ed9d1bf62cb485e556e2a093f548cd604016e7b6ad0e2da1e25b6cfb3edc` 일치. `requires_iso_rebuild=false`.

## QA-WORLD-SIGN-LIVE-003 — 원문 완전 제거·180도 회전·축소

- 결과: PASS(생성·설치 해시), PENDING(PPSSPP 실제 화면).
- 일본어 글자와 외곽선의 전체 바운드를 관리 영역으로 복원하고, `마왕성`·`튜토리얼`을 180도 회전했다. `튜토리얼`은 18px로 축소했다.
- 원본 SHA-256 `43a1289e643f3688960516c4d67544819d9bd3ba4d97d99654a76e7d81ad89f6` 보존.
- 작업본·설치본 SHA-256 `173e8d1c16cc64f8273966ab6e5d2a8270197b79c937afec44d70573d7e2c105` 일치. `requires_iso_rebuild=false`.

## QA-ROUND-0001 — 구조 정리와 초기 정적 조사

### 기준선

- 날짜: 2026-07-17
- 원본: `ULJS00150`, version `1.01`
- ISO SHA-256: `af0d2873a96c5fe6f95b3fc2fb3e8702f98bba67e32f2f78c5c3d1bdaa8b9d03`
- 환경: Windows PowerShell, Python 3.12

### 자동·정적 검사 결과

| 검사 ID | 검사 | 결과 | 근거/비고 |
| --- | --- | --- | --- |
| `QA-MOVE-001` | 기존 원본·추출 파일 이동 전후 SHA-256 | PASS | 17개 파일 누락·추가·변경 0건 |
| `QA-MANIFEST-001` | 원본/추출 기준선 기록 | PASS | `workspace/config/baseline_manifest.json` |
| `QA-NISPACK-001` | 5개 NISPACK 시그니처와 테이블 범위 | PASS | 총 513개 엔트리 모두 파일 내부 |
| `QA-NISPACK-002` | NISPACK 엔트리 데이터 겹침 | PASS | 겹침 0건 |
| `QA-LZS-001` | `start.lzs` 전체 스트림 해제 | PASS | 출력 9,030,752바이트 |
| `QA-LZS-002` | LZS 선언 출력 크기 일치 | PASS | 기대값과 실제값 일치 |
| `QA-LZS-003` | 원본 `start.dat` 재압축 | PASS | 원본 `start.lzs`와 크기·SHA-256·전체 바이트 동일 |
| `QA-LZS-004` | PoC `start.lzs` 자기 왕복 | PASS | 3,630,811바이트를 풀어 PoC `start.dat` SHA-256 `bf605162…c526e` 복원 |
| `QA-START-001` | `start.dat` 인덱스 182개 경계 | PASS | 첫 시작 `0x16D0`, 직전 끝→다음 시작, 마지막 0→EOF; 전 구간 연속 |
| `QA-START-002` | 인덱스 경계 로더 교차 확인 | PASS | VA `0x0888B2D4` 부근이 이름 `+8+i×32`, 데이터 `+4+i×32` 사용 |
| `QA-MUSICSHOP-001` | MusicShop 레코드 전수 경계 | PASS | 30개 × 92바이트, 21/65바이트 슬롯과 4바이트 footer 일치 |
| `QA-MUSICSHOP-002` | MusicShop 문자열 슬롯 검증 | PASS | 60개 슬롯 NUL 종료·0 패딩·엄격 CP932 재인코딩 동일 |
| `QA-MUSICSHOP-003` | MusicShop parse→serialize | PASS | 2,768바이트 및 SHA-256 `9610d469…cc1f5` 동일 |
| `QA-BASETALK-001` | 실제 BaseTalk 구조·왕복 | PASS | 848바이트, 16 × 52바이트, 12바이트 zero footer, SHA-256 `1275878d…1e6a` |
| `QA-BASETALK-002` | 정적 소비 보폭 | PASS | Capstone 5.0.7로 두 소비자 모두 52바이트 계산 확인 |
| `QA-BASETALK-003` | PPSSPP 로더 런타임 대조 | PASS | count 16, 본문 `0x0942DF24`, 844바이트가 디스크 헤더 뒤와 동일 |
| `QA-NSF-LINK-001` | BaseTalk 키의 demo.nsf 해석 | PASS | 고유 키 72개 전부 531개 정렬 키 맵에서 해석, 오프셋 파일 범위 내 |
| `QA-NSF-LAYOUT-001` | demo.nsf 코드 기준 주소 | PASS | 메타데이터 뒤 `0x2E10`, 선언·실제 코드 크기 `0x30D70` 일치 |
| `QA-NSF-MSG-001` | 메시지 명령 소비 형식 후보 | PASS(후보 분모) | `42 01/02/03`, Demo00 1,481건·동적 5건·미해결 54건; 도달성은 미검증 |
| `QA-NSF-REACH-001` | 블록 로컬 명령 시작점 | PARTIAL PASS | 400블록 중 282 완료; Demo00 1,377·동적 2·미해결 리터럴 52 증명, 109건 미증명 |
| `QA-NSF-RUNTIME-001` | PPSSPP NSF 메시지 핸들러 추적 기준선 | INCONCLUSIVE | 원본 ISO, PPSSPP `v1.20.4-426-gae13b9b3e1`, 90초·자동 입력 44회에서 적중 0건; 대화 장면 진입이 확인되지 않아 미사용 판정 불가 |
| `QA-MSG-OWNER-001` | 두 메시지 표 소유자와 적재 경계 | PASS | 슬롯 0은 `Demo00.dat`; 슬롯 1은 `DL%04d.EDAT`의 `DDEM`, 컨테이너 해제 시 슬롯 1 초기화 |
| `QA-MSG-OWNER-002` | 미해결 54건 분류 | PASS | 정상 `42 01 + u32` 52건은 DDEM 조건부 참조, 비정상 `42 02/03` 패턴 2건은 계속 미증명 |
| `QA-DEMO00-001` | Demo00 구조·CP932 슬롯 검증 | PASS | 1,572 × 132바이트, ID 오름차순, 화자 17바이트·본문 35바이트 ×3, zero tail/footer |
| `QA-DEMO00-002` | Demo00 parse→serialize | PASS | 207,520바이트 및 SHA-256 `5db04fe8…b01d` 동일 |
| `QA-DEMO00-003` | Demo00 정적 소비 코드 | PASS | NSF VM `0x08879060` → 표시 래퍼 `0x08867CFC` → 조회 `0x08862F90`; 132바이트 검색과 본문 포인터 확인 |
| `QA-DEMO00-004` | Demo00 표시 제어 필드 | PASS | `+0x02` 레이아웃 1~17, `+0x03` 전부 0, `+0x06` 명패 단계 0/200/201/202와 화자 길이 전수 일치 |
| `QA-DEMO00-005` | Demo00 얼굴 자산 교차검증 | PASS | `abs(+0x04)` 고유 120종이 `start.dat`의 `wf_%04d.txp` 120개와 전부 일치; 부호 의미는 보존 |
| `QA-DEMO00-006` | Demo00 전량 번역 아티팩트 | PASS | 1,572레코드·6,288슬롯 누락 없음, 보호 필드 원본 대조, 207,520바이트 원문 재조립 동일; complete 20/needs_human_review 0/untranslated 1,552 |
| `QA-DEMO00-BATCH-001` | 난이도 화면 첫 번역 배치 | PASS(번역) | `0x005A/0x005B` 보호 병합·2바이트 예상 슬롯·`임다/임까` 문체·독립 의미 검토 PASS; 생산 인코딩·최종 화면 조판은 별도 게이트 |
| `QA-DEMO00-BATCH-002` | 도입부 머플러 설명 6건 | PASS(번역) | `demo.nsf 0xA66..0xC02` 연속 문맥, 에트나/머플러/디저트/라져임다 승인, 의미 재검토·보호 병합·최대 34/34바이트 예상 슬롯 PASS; 생산 인코딩·화면 조판은 별도 게이트 |
| `QA-DEMO00-BATCH-003` | 도입부 도주 경고 7건 | PASS(번역) | 블록 `0xC37..0xF6F`의 목표 호출 `0xD40..0xF3B` 7건 전부 실행 시작점 증명; 문맥별 `임다/슴다·임까/슴까` 규칙과 7건 번역 승인, 보호 병합·최대 29/34바이트 예상 슬롯 PASS |
| `QA-DEMO00-BATCH-004` | 도입부 멜론맛 간식 4건 | PASS(번역) | 블록 `0xF70..0x11FC`의 목표 호출 `0x10C2/0x113B/0x1168/0x11C8` 4건 전부 실행 시작점 증명; 번역·표현 승인, 보호 병합·최대 32/34바이트 예상 슬롯 PASS |
| `QA-DEMO00-REVIEW-001` | 지연 최종 검토 큐 | PASS | 사용자 승인 전 큐 129건과 SSOT 번역을 정확 대조해 전부 complete 승격; 연결 용어 결정 16건 승인, 재생성 큐 0건 |
| `QA-DEMO00-APPROVE-001` | 큐 스냅샷 승인 도구 | PASS | source identity·정확 번역·상태·예상 항목 수 대조 후에만 승인; stale 큐 거부 및 `consumer_review_required` 보존 단위 테스트 PASS |
| `QA-DEMO00-BATCH-005` | 성내 프리니 감소 6건 | PASS(중간 게이트) | 목표 호출 6/6 실행 시작점 증명, 보호 병합·최대 29/34바이트 예상 슬롯 PASS; 일반 검토 5·사람 판단 1 누적, 전체 왕복·전체 회귀는 최종 라운드로 연기 |
| `QA-DEMO00-BATCH-006` | 디저트 진행 보고 6건 | PASS(중간 게이트) | 목표 호출 6/6, 보호 병합·최대 28/34바이트 PASS; `鬼畜ッス→악랄함다` 사람 판단 누적 |
| `QA-DEMO00-BATCH-007` | 프리니거 X 대화 7건 | PASS(중간 게이트) | 목표 호출 7/7, 보호 병합·최대 30/34바이트 PASS; `プリニガーX→프리니거 X` 2건 사람 판단 누적 |
| `QA-DEMO00-BATCH-008` | 게임 중 폭언 5건 | PASS(중간 게이트) | 목표 호출 5/5, 보호 병합·최대 22/34바이트 PASS; 일반 검토 5건 누적 |
| `QA-DEMO00-BATCH-009` | 전직 상담 5건 | PASS(중간 게이트) | 목표 호출 5/5, 보호 병합·최대 27/34바이트 PASS; 선택 블록 3완료·1실패이나 목표 호출은 전부 증명, `フルボッコ→두들겨 팬다` 사람 판단 누적 |
| `QA-DEMO00-BATCH-010` | 도망친 프리니 7건 | PASS(중간 게이트) | 목표 호출 7/7, 보호 병합·최대 33/34바이트 PASS; `オレ様→이 몸` 사람 판단 누적 |
| `QA-DEMO00-BATCH-011` | 주인공 지망 소녀 9건 | PASS(중간 게이트) | 목표 호출 9/9, 보호 병합·최대 32/34바이트 PASS; 일반 검토 9건 누적 |
| `QA-DEMO00-BATCH-012` | 디저트 명령과 욕설 취향 8건 | PASS(중간 게이트) | 목표 호출 8/8, 보호 병합·최대 30/34바이트 PASS; `しけこむ` 수위와 `お腹いっぱい` 관용 번역 2건 사람 판단 누적 |
| `QA-DEMO00-BATCH-013` | 에트나의 고민 7건 | PASS(중간 게이트) | 목표 호출 7/7·선택 블록 1/1 완료, 보호 병합·최대 25/34바이트 PASS; 일반 검토 7건 누적 |
| `QA-DEMO00-BATCH-014` | 개조 게임 매각 지시 7건 | PASS(중간 게이트) | 목표 호출 7/7·선택 블록 2/2 완료, 보호 병합·최대 31/34바이트 PASS; `調子に乗る→기고만장하다` 사람 판단 누적 |
| `QA-DEMO00-BATCH-015` | 놓친 활약 기회 2건 | PASS(중간 게이트) | 목표 호출 2/2·선택 블록 1/1 완료, 보호 병합·최대 27/34바이트 PASS; 일반 검토 2건 누적 |
| `QA-DEMO00-BATCH-016` | 시대 종료 농담 추궁 4건 | PASS(중간 게이트) | 목표 호출 4/4·선택 블록 1/1 완료, 보호 병합·최대 20/34바이트 PASS; 일반 검토 4건 누적 |
| `QA-DEMO00-BATCH-017` | 궁극의 디저트 공개 10건 | PASS(중간 게이트) | 정적 목표 9/9·선택 블록 1/1 완료, 보호 병합·최대 26/34바이트 PASS; 정적 후보 없는 `0x0EE0`은 소비자 검토 유지, `ういッス` 사람 판단 누적 |
| `QA-DEMO00-BATCH-018` | 대연회 회비 반전 12건 | PASS(중간 게이트) | 정적 목표 10/10·선택 블록 1/1 완료, 보호 병합·최대 27/34바이트 PASS; 정적 후보 없는 `0x0EF0/0x0EF4` 소비자 검토, `ヘル→헬` 사람 판단 누적 |
| `QA-DEMO00-BATCH-019` | 반란과 프리니거 X 9건 | PASS(중간 게이트) | 목표 호출 9/9·선택 블록 1/1 완료, 보호 병합·최대 33/34바이트 PASS; `プリニガーX` 2건을 기존 고유명 판단에 연결 |
| `QA-DEMO00-BATCH-020` | 반란 이후 수리 심부름 14건 | PASS(중간 게이트) | 목표 호출 14/14·선택 블록 1/1 완료, 보호 병합·최대 32/34바이트 PASS; 프리니거 X·꽁치 급여·폴리퍼티·늘임 응답 4건 사람 판단 누적 |
| `QA-DEMO00-BATCH-021` | 미식 오거와 태고의 고기 11건 | PASS(중간 게이트) | 목표 호출 11/11·선택 블록 2/2 완료, 보호 병합·최대 33/34바이트 PASS; 적 이름·구먼체·태고의 고기·후리카케를 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-022` | 나츠와 4초 요리 레시피 18건 | PASS(중간 게이트) | 목표 호출 18/18·선택 블록 2/2 완료, 보호 병합·최대 33/34바이트 PASS; 나츠·4초 요리 레시피를 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-023` | 카르다몬·세사미 만담과 고급 생선 11건 | PASS(중간 게이트) | 목표 호출 11/11·선택 블록 2/2 완료, 보호 병합·최대 30/34바이트 PASS; 인명·간사이풍 구어·츳코미·고급 생선(뼈만 남음)을 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-024` | 바쿠치 카지노와 속임수 주사위 17건 | PASS(중간 게이트) | 목표 호출 17/17·선택 블록 2/2 완료, 보호 병합·최대 30/34바이트 PASS; 바쿠치·속임수 주사위를 사람 판단으로 누적하고 승인 용어 머플러 유지 |
| `QA-DEMO00-BATCH-025` | 호시카게와 드래곤 잼 11건 | PASS(수정 후 중간 게이트) | 목표 호출 11/11·선택 블록 2/2 완료; 최초 `0x2840` 35/34 초과를 25a에서 의미 보존 축약해 31/34 PASS, 나머지 보호 병합·슬롯 PASS |
| `QA-DEMO00-BATCH-026` | 모브 병사 공장과 찢어진 골판지 13건 | PASS(중간 게이트) | 목표 호출 13/13·선택 블록 2/2 완료, 보호 병합·최대 32/34바이트 PASS; 모브 병사·꿀 어미·찢어진 골판지를 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-027` | 터메릭 농장과 뜨거운 피 덮밥 15건 | PASS(중간 게이트) | 목표 호출 15/15·선택 블록 2/2 완료, 보호 병합·최대 32/34바이트 PASS; 터메릭·뜨거운 피 덮밥·정체 미상 지시 대상을 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-028` | 나츠·메그 쌍둥이와 여학생의 리코더 11건 | PASS(중간 게이트) | 목표 호출 11/11·선택 블록 2/2 완료, 보호 병합·최대 28/34바이트 PASS; 메그 이름·단속적 문체·여학생의 리코더 표현 수위를 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-029` | 카르다몬·세사미와 독사과 명주 13건 | PASS(중간 게이트) | 목표 호출 13/13·선택 블록 2/2 완료, 보호 병합·최대 31/34바이트 PASS; 전각 ￥ 보존, 부부 호칭·죽음 농담·아이템명을 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-030` | 파프리카와 모두가 좋아하는 바나나 14건 | PASS(중간 게이트) | 목표 호출 14/14·선택 블록 2/2 완료, 보호 병합·최대 30/34바이트 PASS; 모건·파프리카·냥 어미·바나나 아이템명을 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-031` | 호시카게 훈련과 드래곤 돌진 14건 | PASS(중간 게이트) | 목표 호출 14/14·선택 블록 2/2 완료, 보호 병합·최대 28/34바이트 PASS; 「와」의 마음·야바카와이·사료 광고풍 아이템명을 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-032` | 모브 공장과 붕어빵 꼬리 16건 | PASS(중간 게이트) | 목표 호출 16/16·선택 블록 2/2 완료, 보호 병합·최대 29/34바이트 PASS; 모브 대장 축약 명패·남작 지시 대상·붕어빵 현지화를 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-059` | 다스 모브의 디저트 바이킹 매복 17건 | PASS(중간 게이트) | 목표 호출 17/17, 통합 선택 블록 감사 6/6 완료; 보호 병합·최대 30/34바이트 PASS, 신규 고유명·중의성·관계·관용구는 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-060` | 미식 오거의 궁극 디저트 식탐 3건 | PASS(중간 게이트) | 목표 호출 3/3, 보호 병합·최대 21/34바이트 PASS; 승인된 미식 오거 명칭과 구먼체를 재사용 |
| `QA-DEMO00-BATCH-061` | 아니스의 프리니 왕자 수색 8건 | PASS(중간 게이트) | 목표 호출 8/8, 보호 병합·최대 30/34바이트 PASS; 전각 ￥ 보존, 과격한 수색법과 왕자 정체 단서는 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-062` | 나츠·메그의 최종병기 오해 4건 | PASS(중간 게이트) | 목표 호출 4/4, 보호 병합·최대 33/34바이트 PASS; 승인 인명과 메그의 단속적 문체를 재사용 |
| `QA-DEMO00-BATCH-063` | 카르다몬·세사미의 디저트 완성 내기 3건 | PASS(중간 게이트) | 목표 호출 3/3, 보호 병합·최대 29/34바이트 PASS; 승인 인명과 간사이풍 구어를 재사용 |
| `QA-DEMO00-BATCH-064` | 모건의 동생 패배와 재도전 5건 | PASS(중간 게이트) | 목표 호출 5/5, 보호 병합·최대 29/34바이트 PASS; 형제 관계는 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-065` | 바쿠치의 사이클롭스 출격 4건 | PASS(65a 상태 교정) | 목표 호출 4/4, 보호 병합·최대 27/34바이트 PASS; 65a에서 사이클롭스 미승인 용어 상태와 플래그를 정합화 |
| `QA-DEMO00-BATCH-066` | 사이클롭스 mk2 출격 4건 | PASS(중간 게이트) | 목표 호출 4/4, 보호 병합·최대 27/34바이트 PASS; 개량형 표기는 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-067` | 파프리카의 디저트 냄새 추적 3건 | PASS(중간 게이트) | 목표 호출 3/3, 보호 병합·최대 29/34바이트 PASS; 전각 ￥와 콩·냥 혼합 어미 보존 |
| `QA-DEMO00-BATCH-068` | 호시카게의 와비사비 수행 6건 | PASS(중간 게이트) | 목표 호출 6/6, 보호 병합·최대 31/34바이트 PASS; 와비사비·痛い人 문화 표현은 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-069` | 모브 전차부대 4건 | PASS(중간 게이트) | 목표 호출 4/4, 보호 병합·최대 26/34바이트 PASS; 승인 모브 병사 명칭과 꿀 어미 재사용 |
| `QA-DEMO00-BATCH-070` | 터메릭의 남작 복수 사연 8건 | PASS(70a 슬롯 교정) | 정적 참조 10/10, 보호 병합 PASS; `0x358A` 최초 35/34를 70a에서 28/34로 교정, 이명·관계·음식 농담은 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-071` | 스위츠 남작의 도전 10건 | PASS(중간 게이트) | 정적 참조 10/10, 보호 병합·최대 32/34바이트 PASS; 전설의 G 디저트를 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-072` | 재료 탱크와 G 디저트 27건 | PASS(중간 게이트) | 정적 참조 27/27, 보호 병합·최대 31/34바이트 PASS; 에센스·고초·남의 불행은 꿀맛 표현을 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-073` | G 디저트 기계 파괴와 임무 성공 14건 | PASS(중간 게이트) | 정적 참조 14/14, 보호 병합·최대 32/34바이트 PASS; 전설의 G 디저트 표기와 추모 어조를 후속 검토 대상으로 누적 |
| `QA-DEMO00-BATCH-074` | 프리니 라하르의 정체 29건 | PASS(중간 게이트) | 정적 참조 29/29, 보호 병합·최대 32/34바이트 PASS; 전각 ￥ 보존, 라하르 표기를 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-075` | 아사기의 주인공 오해 28건 | PASS(중간 게이트) | 정적 참조 28/28·선택 블록 2/2, 보호 병합·최대 32/34바이트 PASS; 아사기·칭호·아이템과 주인공 메타 농담을 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-076` | 아사기의 인격 혼란 23건 | PASS(중간 게이트) | 정적 참조 23/23, 보호 병합·최대 29/34바이트 PASS; 사투리 인격과 주역 입문서 아이템을 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-077` | 아사기 고민 상담실 27건 | PASS(중간 게이트) | 정적 참조 27/27, 보호 병합·최대 32/34바이트 PASS; 상담·미출시 게임 메타 농담과 주역 근성구이를 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-078` | 아사기 선거 운동과 프리니 선배 27건 | PASS(중간 게이트) | 정적 참조 27/27, 보호 병합·최대 34/34바이트 PASS; 선거·숨은 캐릭터 메타 농담과 비기 황금 모나카를 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-079` | 아사기 레벨 9999 편법과 신비 수업 27건 | PASS(중간 게이트) | 정적 참조 26/26·선택 블록 통합 감사 PASS, `0x76C6` 정적 후보 없음; 보호 병합·최대 33/34바이트 PASS |
| `QA-DEMO00-BATCH-080` | 아사기 몸매 수행과 희생 각오 30건 | PASS(중간 게이트) | 정적 참조 30/30, 보호 병합·최대 32/34바이트 PASS; 체형·변신 패러디와 프리니거 X를 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-081` | 아사기 프리티 프리니 변신과 폭발 25건 | PASS(중간 게이트) | 정적 참조 24/24, `0x77AA` 정적 후보 없음; 보호 병합·최대 32/34바이트 PASS, 변신명·중의적 죽음 표현을 사람 판단으로 누적 |
| `QA-DEMO00-BATCH-082` | 프리니가 된 아사기 후일담 2건 | PASS(중간 게이트) | 정적 참조 1/1, `0x77EE` 정적 후보 없음; 보호 병합·최대 21/34바이트 PASS |
| `QA-DEMO00-BATCH-083` | 거점 이름 없는 영혼과 시설 첫 대화 19건 | PASS(83b 상태 교정) | 정적 후보 15건 중 실행 시작점 8건 증명; 후보 없음 4건과 후보 미증명 7건은 소비자 검토, 보호 병합·최대 33/34바이트 PASS |
| `QA-DEMO00-BATCH-084` | 거점 시설 해금 설명 41건 | PASS(84a 슬롯 교정) | 정적 후보 41/41 실행 시작점 증명; 최초 2건 35/34를 84a에서 최대 30/34로 교정 |
| `QA-DEMO00-BATCH-085` | 라키 교수 보상과 라키 돌 생태 23건 | PASS(85a·85b 교정) | 정적 후보 10건 중 실행 시작점 9건 증명; 후보 없음 13건과 후보 미증명 1건은 소비자 검토, 최초 35·37/34를 최대 32/34로 교정 |
| `QA-DEMO00-BATCH-086` | 사프란의 마계 훈장 수여식 28건 | PASS(중간 게이트) | 정적 후보 28건 중 실행 시작점 24건 증명; 후보 미증명 4건은 소비자 검토, 보호 병합·최대 29/34바이트 PASS |
| `QA-DEMO00-BATCH-087` | 러너·파이터·노 미스 훈장 24건 | PASS(87a 슬롯 교정) | 정적 후보 없음 24건 소비자 검토; 최초 조건문 3건 38/34를 87a에서 최대 29/34로 교정 |
| `QA-DEMO00-BATCH-088` | 아사기·도감·진행 훈장 16건 | PASS(중간 게이트) | 정적 후보 없음 16건 소비자 검토; 보호 병합·최대 34/34바이트 PASS |
| `QA-DEMO00-BATCH-089` | 수집·점수·특수 도전 훈장 20건 | PASS(89a 슬롯 교정) | 정적 후보 없음 20건 소비자 검토; 최초 0315 39/34를 89a에서 34/34로 교정 |
| `QA-DEMO00-BATCH-090` | 프리니 전멸 마계 뉴스 9건 | PASS(중간 게이트) | 정적 후보 9/9 실행 시작점 증명; 보호 병합·최대 32/34바이트 PASS |
| `QA-DEMO00-BATCH-091~093` | 시크릿 파일·마계 레코드 획득 60건 | PASS(중간 게이트) | 정적 후보 없음 60건 소비자 검토; 보호 병합·최대 23/34바이트 PASS |
| `QA-DEMO00-BATCH-094` | 지각 프리니와 마력의 구슬 13건 | PASS(중간 게이트) | 정적 후보 13/13 실행 시작점 증명; 보호 병합·최대 27/34바이트 PASS |
| `QA-DEMO00-BATCH-095` | 에트나의 궁극 디저트 명령 16건 | PASS(중간 게이트) | 정적 후보 16/16 실행 시작점 증명; 보호 병합·최대 32/34바이트 PASS |
| `QA-DEMO00-BATCH-096` | 주인공 머플러 인계 6건 | PASS(중간 게이트) | 정적 후보 6/6 실행 시작점 증명; 승인 머플러 표기 유지, 최대 25/34바이트 PASS |
| `QA-DEMO00-BATCH-097` | 궁극 디저트 임무 거점 대화 15건 | PASS(중간 게이트) | 정적 후보 15/15 실행 시작점 증명; 보호 병합·최대 32/34바이트 PASS |
| `QA-DEMO00-POP-001` | Demo00 반복 템플릿 모집단 | PASS | `国` 49건 중 유일한 `0x00E6` 후보는 기본 Character 슬롯에서 선택 불가, 나머지 48건은 NSF 참조 0건; 제외 49·미확정 0·기본 ISO 분모 CLOSED |
| `QA-DEMO00-TRACE-001` | `0x00E6` 전용 PPSSPP 런타임 추적 | INCONCLUSIVE | PPSSPP `v1.20.4-426-gae13b9b3e1`, 원본 ISO; 부팅·메뉴 자동 60초와 적 등장 장면 수동 플레이 300초 모두 메시지 핸들러 적중 0·대상 적중 0; 미사용 판정 금지, `enemy.nsf` 블록 진입 조건 역추적 필요 |
| `QA-ENEMY-KEY-001` | `0x014466E8` 키군 공급 계약 | PASS(기본 ISO) | 실제 구조 `u32 count + 390×68 + 4`; ID 정확 조회·설명자 `+0x3C` 루트 무보정 소비 확인, 대상 소유자·코드 영역 키 0건; DLC 슬롯 1은 별도 범위 |
| `QA-FONT-001` | font.fnt 맵과 font.txp 글리프 집합 | PASS | 맵 11,615개, 글리프 ID `0..2347` 전수 포괄, TXP `2348×140`바이트 일치 |
| `QA-FONT-002` | JIS/UCS 양방향 표 | PASS | little-endian u16[65536] 두 개, canonical UCS 왕복 7,766건 전부 일치, 한글 음절 배정 0건 |
| `QA-FONT-003` | BOOT 본문 폰트 소비 경로 | PASS(정적) | 초기화 `0x08898C90`, 렌더러 `0x08899698`, 20×14·4bpp 복사와 216글리프 캐시 제한 확인 |
| `QA-FONT-004` | 원본 글리프 픽셀 복원 | PASS(정적) | low-nibble-first로 `A/あ/ア/国/プリニー` 자형 정상 복원; `work/analysis/font_glyphs.png` |
| `QA-FONT-005` | Hancom MalangMalang 입력 고정 | PASS | SHA-256 `f6682e20…43b0`, family/style 일치, modern Hangul 11,172자 cmap 누락 0 |
| `QA-FONT-POC-001` | 단일 글리프 Expected Write | PASS(자산) | `プ` glyph 371의 `0xCB34..0xCBBF`만 허용, 실제 79바이트 변경, TXP 크기 동일; 11,172자 경계 감사 최대 17×14·초과 0 |
| `QA-START-POC-001` | start.dat 동일 크기 주입 | PASS(자산) | `font.txp` 구간 `0x5339E0..0x583E3F`에서 하위 글리프 diff 79바이트만 변경; 9,030,752바이트 유지, SHA-256 `bf605162…c526e` |
| `QA-SYSTEM-POC-001` | SYSTEM.DAT 고정 extent 주입 | PASS(컨테이너) | 원래 333바이트 패딩 중 40바이트 사용, 293바이트 잔존; 다른 6개 항목과 전체 크기 보존, SHA-256 `41c9fbb6…9892` |
| `QA-ISO-POC-001` | ISO9660 동일 크기 extent 주입 | PASS | LBA 218,144·`0x1AA10000`의 `SYSTEM.DAT;1`만 치환, 원본과 같은 500,465,664바이트, 변경 1,690,574바이트 전부 대상 범위, SHA-256 `02883fd3…7a68` |
| `QA-PPSSPP-BOOT-001` | PoC ISO Headless 부팅·SYSTEM.DAT 열기 | PASS | PPSSPP Headless `v1.19.3-1588-g1ce9db0250`, 12초, 반환 0·의미 있는 오류 0; ULJS00150/EBOOT/모듈/SYSTEM.DAT 열기 확인 |
| `QA-FONT-POC-002` | PPSSPP 실제 화면 가시성 | PASS | 2026-07-17 사용자 실기 확인: 난이도 선택 `プリニー`→`가リニー`, 스테이지 결과 `死亡プリニー数`→`死亡가リニー数`; 인접 글리프 정상, 화면 전환·플레이 뒤 재표시 정상 |
| `QA-CP932-AUDIT-001` | 확정 텍스트 CP932 사용량 | PARTIAL PASS | Demo00·MusicShop·PrinnyName 6,396슬롯/비어 있지 않은 4,430슬롯, 서로 다른 코드 1,171개; 렌더 가능 2,347개 중 제한 모집단 미사용 1,176개, 전 게임 안전성은 미증명 |
| `QA-CP932-ALLOC-001` | 생산용 코드·글리프 예산 1차 감사 | PARTIAL PASS | 확정 외 후보 코드 374개와 ASCII 95개 예약; 엔진 코드 11,375개/빈 매핑 9,028개/회수 글리프 후보 726개, 고정 크기 신규 글리프 후보 상한 726개; 생산 승인 아님 |
| `QA-FONT-MULTI-001` | `가각뾰힣` 4셀 Expected Write | PASS(자산) | `プ/リ/ニ/ー`의 서로 다른 4셀·560바이트만 허용, 실제 변경 305바이트; `font.txp` 크기 유지, SHA-256 `ada60172…22983` |
| `QA-SYSTEM-MULTI-001` | 다중 PoC SYSTEM.DAT 고정 extent 주입 | PASS(컨테이너) | LZS 증가 169바이트, 기존 패딩 333바이트 중 164바이트 잔존; 다른 항목·전체 크기 보존, SHA-256 `76d3131f…b0614` |
| `QA-ISO-MULTI-001` | 다중 PoC ISO 동일 extent 주입 | PASS | 500,465,664바이트와 LBA 유지, 변경 1,750,823바이트 전부 `SYSTEM.DAT` 범위; SHA-256 `22168bd8…e628` |
| `QA-PPSSPP-MULTI-001` | 다중 PoC Headless 부팅·SYSTEM.DAT 열기 | PASS | 12초, 반환 0·의미 있는 오류 0; ULJS00150/EBOOT/Disgaea/SYSTEM.DAT/계획 timeout 확인 |
| `QA-FONT-MULTI-002` | `가각뾰힣` PPSSPP 실제 화면 | PASS | 2026-07-17 사용자 확인: 난이도 UI와 Demo00 `0x07D0` 명패에서 네 글자 연속 표시, 본문 `ー`→`힣`; 기준선·간격·인접 글리프 정상, 캐시 오염·크래시 없음 |
| `QA-DEMO00-E2E-001` | Demo00 `0x07D0` 단일 레코드 writer | PASS(자산) | 화자·첫 줄 슬롯 내부 19바이트만 변경; 레이아웃 14·얼굴 0·명패 200·두 빈 줄·tail·footer와 다른 1,571레코드 바이트 동일 |
| `QA-FONT-E2E-001` | 번역 PoC 9글자 Expected Write | PASS(자산) | `프리니우와지각했다` 9셀·1,260바이트만 허용, 실제 699바이트 변경; `font.txp` 크기 유지 |
| `QA-START-E2E-001` | font.txp+Demo00.dat 결합 주입 | PASS(자산) | 두 엔트리에서만 실제 718바이트 변경, `start.dat` 9,030,752바이트 유지 |
| `QA-SYSTEM-E2E-001` | 번역 PoC SYSTEM.DAT 고정 extent | PASS(컨테이너) | LZS 증가 262바이트, 기존 패딩 333바이트 중 71바이트 잔존; 다른 NISPACK 항목 보존 |
| `QA-ISO-E2E-001` | 번역 PoC ISO 동일 extent | PASS | ISO 크기·LBA 유지, 변경 1,742,540바이트 전부 SYSTEM.DAT 범위; SHA-256 `f2f9d940…67cb6` |
| `QA-PPSSPP-E2E-001` | 번역 PoC Headless 부팅 | PASS | 12초, 반환 0·의미 있는 오류 0; ULJS00150/EBOOT/Disgaea/SYSTEM.DAT/계획 timeout 확인 |
| `QA-DIALOG-E2E-002` | `프리니 / 우와、지각했다！！` 실제 화면 | PASS | 2026-07-17 사용자 확인, PPSSPP `v1.20.4-426-gae13b9b3e1`: 명패·본문이 목표대로 표시되고 받침·기준선·자간·구두점·명패 폭 정상, 잘림·겹침·캐시 잔상·진행 정지 없음 |
| `QA-PPSSPP-001` | 조사 후 외부 상태 정리 | PASS | 프로세스 종료, `RemoteISOPort=0`, 원격 디버거 시작/로컬 값 모두 `False` 복원 |
| `QA-TOOLS-001` | Python 단위 테스트 | PASS | 그래픽 index encoder·타이틀 builder·UV 슬롯 스타일 회귀를 포함해 총 83건, 2026-07-18 전량 PASS |
| `QA-NSF-001` | NSF 평문 Shift-JIS 후보 | 불명확 | 검색 결과가 주로 깨진 반복 패턴; 소비 증거 없음 |

### 잔여·후속 검사 상태

| 검사 | 상태 | 실행 전제 |
| --- | --- | --- |
| ISO 동일 크기 파일 치환 | PASS | ISO9660 경로·LBA·extent와 전체 diff 검증; 일반 파일 크기 변경은 별도 게이트 |
| NISPACK 재패킹 | PASS | 미확정 필드·비대상 payload 보존, 가변 이동 대조군과 고정 extent 생산안 모두 PPSSPP 부팅 확인 |
| LZS 해제→재압축→재해제 | PASS | 원본 바이트 동일 재현, PoC 자기 왕복, PoC ISO `SYSTEM.DAT` 열기 확인 |
| start.dat 재패킹 | PASS(고정 크기 생산안) | 182개 끝 오프셋·마지막 0·미확정 필드·비대상 payload 보존; 가변 크기는 런타임 실패로 폐기 |
| PPSSPP 화면 부팅·플레이 | 자동 부팅 PASS/생산 화면 미실행 | 생산 ISO 5초 Headless PASS; 난이도·거점·전투 전후·긴 문장 화면 확인 필요 |
| 실기 부팅 | 미실행 | 테스트 장치와 설치 방식 |
| 한글 글리프 표시 PoC | PASS | 단일 `가`와 `가각뾰힣`이 UI·Demo00 명패·본문에서 실제 표시; 화면 전환 후 재표시 정상 |
| CP932 코드 공간 | PASS(Demo00 기본 ISO 범위) | 사용자 정의 코드 830개와 기존 글리프 830개 할당, 예약 후 공급 916개·여유 86개; DLC·비Demo00 추가 번역은 별도 감사 |
| 폰트 게임 임베딩 범위 | PASS(제공 자료) | 한컴 서체 사용범위 표에서 게임기 등 디바이스 내 탑재·폰트파일 임베딩 모두 사용 가능; 원본 TTF 별도 재배포는 제외 |
| 대사 1건 재삽입 PoC | PASS | `0x07D0` writer·ISO·Headless·실제 `프리니 / 우와、지각했다！！` 화면과 진행 확인 완료; 시험용 전역 프록시는 생산용 인코딩과 분리 |
| Demo00 전량 번역 아티팩트 | 번역 승인 완료 | complete 1,523/untranslated 49; 기본 ISO 번역 대상 전량 사용자 승인, 검토 큐 0건, 용어 결정 approved 122건, 현 `consumer_review_required` 157건은 별도 기술 검토 |
| `QA-DEMO00-BATCH-098-106` | 후반 거점 대사 103건 | PASS | 정적 후보·실행 시작점 103/103, 보호 병합 및 최대 33/34바이트; UTF-8 교정 배치 9개로 문자 치환 복구 |
| `QA-DEMO00-BATCH-107-112` | 최종 거점 대사 57건 | PASS | 정적 후보·실행 시작점 57/57, 보호 병합 및 최대 34/34바이트, 비의도 `???` 잔존 0건 |
| `QA-DEMO00-APPROVE-003` | 최종 검토 큐 승인 | PASS | 사용자 수정 16건 SSOT 반영·최대 31/34바이트, 큐 1,127건과 용어 67건 정확 승인, 새 큐 0건 |
| `QA-DEMO00-PRODUCTION-001` | 승인 코퍼스 전체 writer | PASS(자산) | complete 1,523/excluded 49, 한글 830/비한글 62, 최대 34바이트; Demo00 제어 메타데이터 보존, 실제 변경 75,393바이트 |
| `QA-FONT-RECLAIM-001` | Demo00 범위 고정 크기 글리프 공급 | PASS(정적) | 예약 집합 보존 후 기존 글리프 916개 재사용 가능, 830개 사용·86개 여유; `font.txp` 328,800바이트 유지 |
| `QA-RUNTIME-EXPAND-CONTROL-001` | 확장 실패 원인 대조군 | PASS(격리) | 이동 컨테이너+원본 start PASS, 확장 start+원본 폰트 FAIL; 가변 ISO/NISPACK이 아니라 확장 해제 결과가 블로커 |
| `QA-DEMO00-PRODUCTION-START-001` | 고정 크기 start.dat 전체 삽입 | PASS | 182개 인덱스·미확정 필드·비대상 payload 보존, 9,030,752바이트, SHA-256 `97c005f8…6c740` |
| `QA-DEMO00-PRODUCTION-ISO-001` | 생산 ISO 빌드·Headless 부팅 | PASS(자동) | ISO 500,465,664바이트·원래 오프셋 보존, SHA-256 `cd983265…de1c3`; PPSSPP 5초·의미 있는 오류 0 |
| `QA-DEMO00-PRODUCTION-SCREEN-001` | 생산 ISO 실제 대화 화면 | PASS(대표 표본) | 2026-07-18 사용자 확인: 난이도 화면과 거점 대화에서 화자명·본문 한글 정상, 받침·줄 간격·명패·진행 이상 없음 |
| `QA-GRAPHICS-INVENTORY-001` | 잔여 일본어 UI 모집단 | PASS(저장 자산 분류) | 949개 복원: BG TXP 155, start TXP 157, ANIME 458, start ANIME 179; 타이틀 record 78·거점 메뉴 82·난이도 장식 84·튜토리얼 anime12 record 0 대응 확정. 간판·데모 스킵은 별도 조사 |
| `QA-GRAPHICS-POC-001` | 타이틀 로고·메뉴 v1 | FAIL(실제 화면) | 정적·Headless는 PASS했으나 16색 런타임 팔레트 뱅크에서 전역 안티앨리어싱 인덱스가 다른 색으로 소비되어 글자 깨짐 확인 |
| `QA-GRAPHICS-POC-002` | 타이틀 로고·메뉴 v2 | FAIL(표현 기준) | 안전 인덱스로 깨짐은 해소했으나 Regular 문구의 1px 외곽선으로 전체가 Bold처럼 보이고 데이터 두 문구의 외곽선 인덱스가 달라 두께 불일치 |
| `QA-GRAPHICS-POC-003` | 타이틀 로고·메뉴 v3 | FAIL(실제 화면) | `프리니`를 한 블록에 그렸으나 런타임은 원본 네 UV 슬롯을 따로 소비해 블록 조각이 서로 다른 위치에 합성됨; 정적·82 tests·Headless PASS는 보존 |
| `QA-GRAPHICS-POC-004` | 타이틀 로고·메뉴 v4 | FAIL(실제 화면) | 슬롯별 화면 확대·회전 차이로 글자 크기·각도 불일치, 이진화 계단, `プ` 반탁점과 `ニ` 아래 획 잔재 확인 |
| `QA-GRAPHICS-POC-005` | 타이틀 로고·메뉴 v5 | FAIL(실제 화면) | 잔재는 제거됐으나 세 글자 각도 불일치, 작은 `니`, 제목·부제 외곽선 단계 부족 확인 |
| `QA-GRAPHICS-POC-006` | 타이틀 로고·메뉴 v6 | PASS(정적·자동 부팅)/화면 PENDING | Bold `32/28/30px`·공통 소스각 15도, 제목/부제 stroke 1 반투명 흰색 외곽선; 83 tests·Headless 5초 PASS, ISO `d92e700c…c6c6` |
| `QA-GRAPHICS-POC-007-FINAL` | 타이틀 로고·메뉴 v7 최종 | PASS | 사용자 화면 승인, 각도 `18/21/21도`, 앵커 Y `181/161/159`; start `1ada6dc0…3312`, LZS `72bf09cc…edce`, SYSTEM `e00e54da…3dd1`, ISO `36dfb20b…4a9a`; 84 tests·Headless 5초 PASS |
| Demo00 번역 완료 분모 | PASS(기본 ISO) | 번역 대상 1,523/근거 기반 제외 49/미확정 0; 선택적 DLC는 별도 모집단 |
| MusicShop 표시명 교체 PoC | 미실행 | BGM 목록 화면 소비 확인 |

### 현재 종료 판정

기본 ISO Demo00 번역 대상 1,523건의 승인, 전체 고정 슬롯 writer, 한글 830자 고정 크기 폰트, `start.dat`·LZS·SYSTEM.DAT·ISO 생성, PPSSPP Headless 부팅과 대표 실제 대화 화면은 **PASS**다. 확장 `start.dat` 실패는 대조군으로 격리했고 생산안에서는 원본 해제 크기를 유지했다. 잔여 UI 타이틀 v1~v5의 실제 화면 실패 원인을 팔레트, 굵기, UV 분할, 슬롯별 변형·이진화·분리 잔재·최종 각도와 크기로 격리했다. v6는 공통 15도, 확대된 `니`, 제목·부제 반투명 외곽선으로 정적·자동 부팅까지 PASS했으며 다음 필수 게이트는 실제 화면의 각도·크기·가장자리·선택 상태 확인이다. `consumer_review_required` 157건과 DLC는 번역 승인·기본 ISO 생산 범위와 분리해 유지한다.

## 향후 실제 플레이 체크 범위

- 부팅과 타이틀 진입
- 새 게임·로드·세이브
- 튜토리얼과 일반 대사
- 메뉴, 아이템·스킬·적 이름
- 스테이지 선택과 전투 HUD
- BGM 목록, 갤러리, 리플레이
- 좁은 창과 긴 문장 줄바꿈
- 이벤트·음성 타이밍과 장면 전환
- 엔딩과 클리어 후 콘텐츠
- PPSSPP와 실기 차이
| `QA-TUTORIAL-GRAPHICS-001` | 튜토리얼 v1·60개 번역 | FAIL(실제 화면) | 제목 좌측 치우침, 검정 완성 문장과 별도 빨간 강조어·버튼 아이콘 중복 합성 확인 |
| `QA-TUTORIAL-GRAPHICS-002` | 튜토리얼 v2·61개 슬롯 | FAIL(실제 화면 간격) | 합성 중복은 해소됐지만 X/□ 버튼 뒤 여백, 강조어 따옴표, `들기/던지기` 네 따옴표 위치 불량 |
| `QA-TUTORIAL-GRAPHICS-003` | 튜토리얼 v3 간격 보정 | PASS(정적/부팅), PENDING(화면) | 버튼 뒤 문구와 강조어 따옴표 독립 이동, `들기/던지기` 4따옴표 분리. `ANIME.DAT` diff 102,892바이트는 texture 0~3 payload 내부뿐. ISO `fc056c01…bfe6`, 87 tests, Headless 5초 PASS |
| `QA-TUTORIAL-LIVE-001` | PPSSPP 튜토리얼 교체 텍스처 7개 | PASS(생성/90 tests), PENDING(실제 화면) | 단일 콘텐츠 해시만 교체해 화면 갱신이 누락되는 원인을 확인. `textures.ini`가 동일 접두사·크기의 62개 관찰 해시를 최신 PNG 7개로 매핑, INI `9d327559…3b30`, ISO 재빌드 없음 |
| `QA-TUTORIAL-LIVE-002` | 관리 영역 stale 픽셀 제거 및 글자 크기 보정 | PASS(자동 90 tests), PENDING(실기 화면) | 관리 영역은 후보 인덱스로 강제 재구성. 점프 +2px, 강조 문구 14px/던지기 13px. 중복 괄호·해골·깨진 `가능!` 회귀 테스트 포함. 후보 `39309773…3723`, ISO 재생성 없음. |
| `QA-TUTORIAL-LIVE-003` | 강조 문구 19px 통일 및 괄호 외곽 배치 | PASS(자동 90 tests), PENDING(실기 화면) | 축소 6항목을 19px로 복원하고 괄호를 증가 폭만큼 좌우 이동. `던지기` 슬롯 56px. 후보 `0179ce3f…1702`, ISO 재생성 없음. |
| `QA-TUTORIAL-LIVE-004` | 점프·연사·웅크리기 중심, 던지기 잘림, 해골 중복 | PASS(자동 90 tests), PENDING(실기 화면) | 3문구 +4px, 던지기 19px/가로 0.88/출력폭 ≤48px, 해골 relocation 제거. 후보 `0707d499…513d`, ISO 재생성 없음. |
| `QA-TUTORIAL-LIVE-005` | 던지기 선명도·실드 카운터 중심 | PASS(자동 90 tests), PENDING(실기 화면) | 던지기 가로 재표본화를 폐기하고 19px 원본 글리프·자간 -3으로 44px 폭 생성. 실드 카운터 +4px. 후보 `22c7e125…a7f0`, texture 3 `18313cf5…56d9`, ISO 재생성 없음. |
| `QA-TUTORIAL-LIVE-006` | 웅크리기 행 앞 문장·괄호 충돌 | PASS(사용자 최종 승인) | 앞 문장 우측 경계 x=286과 여는 괄호 x=275의 11px 중첩을 해소. 앞 문장 -12px, 괄호·19px 강조어 유지, 결과 간격 1px. 후보 `9b487201…d2f7`, ISO 재생성 없음. |
| `QA-WORLD-SIGN-PROBE-001` | 월드 방향 간판 공유 소비자 | PASS(사용자 화면) | 자홍색 마커가 `チュートリアル`과 `魔王城` 간판에 함께 표시되어 `09bba150f04e998665714c1a.png` 공유 소비를 확인. ISO 재생성 없음. |
| `QA-WORLD-SIGN-GM3-ISO-001` | GM3 내장 월드 방향 간판 | PASS(사용자 화면, 2026-08-03) | 별도 직접 실행본에서 PPSSPP 텍스처 교체 OFF로 한글 정상 출력을 확인. `STAGE.DAT` SHA-256 `0F2D45CAC1D4E84CB9D20E59E4309A8AFEB526B1A26FB5B93E0AA4267E8FE63E`. 실기 검증은 PENDING. |
| `QA-WORLD-SIGN-LIVE-001` | `마왕성`·`튜토리얼` 한글 간판 | FAIL(실제 화면 좌우 반전) | 정상 방향으로 합성한 후보 `aa10b385…3cf0c`가 런타임에서 좌우 반전됨. 간판 메시의 수평 반전 UV 확인. |
| `QA-WORLD-SIGN-LIVE-002` | 문자 레이어 사전 좌우 반전 | PASS(생성·설치 해시), PENDING(실제 화면) | 목재·화살표는 보존하고 한글만 사전 반전. 후보·설치 SHA-256 `b2e55afb…4e94`, ISO 재생성 없음. |
| `QA-BAKED-BULK-001` | 이미지 텍스트 전수 카탈로그 | PARTIAL PASS | 949개 복원 분모 유지. 난이도·리플레이·적명 아틀라스·장식 간판·엔딩 카드·크레딧·몽타주·에필로그를 target/pending으로 등록하고 debug/test를 분리. 개별 프레임 대응 전 완료 선언 금지. |
| `QA-BAKED-BULK-002` | 1차 일괄 PNG 생성 | PASS(정적) | 5개 초안 모두 원본 크기 유지, ISO 생성 없음. 난이도·리플레이 교체본을 PPSSPP에 설치. 실제 소비·조판은 PENDING. |
| `QA-BAKED-BULK-003` | 초벌 이미지 실시간 매핑 | PASS(설치/102 tests), PENDING(화면) | 난이도 `0918bd60…5edf` 형태 일치, 리플레이 `091cd1e0…7712` 픽셀 완전 일치. 기존 튜토리얼 별칭 보존, INI 64개/`305ecf28…8f0a`, ISO 생성 없음. 간판·엔딩·에필로그는 런타임 해시 대기. |
| `QA-BAKED-BULK-004` | 이미지 텍스트 1차 초벌 15개 | PASS(정적/2 tests), PENDING(화면) | 생성 15개, 원본 크기 유지. 적 명칭·스테이지 결과·난이도·리플레이 4개 논리 자산을 PPSSPP에 설치하고 별칭 68개를 보존했다. 접촉표와 JSON 보고서 생성, ISO 생성 없음. 크레딧·엔딩·anime91은 런타임 해시 대기, anime92/93은 프레임 대응 대기. |
| `QA-BASE-MENU-DEFER-001` | 거점 메뉴 실제 화면 | DEFERRED | 현재 즉시 진입할 수 없어 후보·설치 상태를 보존하고 전수 이미지 초안 이후 재확인. |

## 이미지 초벌 PPSSPP 검수 절차 (2026-07-22)

1. PPSSPP의 텍스처 교체를 켠 상태에서 프로그램을 완전히 종료 후 다시 실행한다.
2. 우선 적 명칭, 스테이지 결과, 난이도, 리플레이 화면을 확인한다.
3. 엔딩·크레딧·anime91 장면에서는 텍스처 덤프를 켜고 해당 화면까지 진행한다.
4. 새 덤프의 파일명과 생성 PNG를 대응시킨 뒤 `textures.ini`에 별칭을 추가한다.
5. 화면별 문구, 잘림, 잔재, 정렬을 검토하고 승인 전에는 ISO를 만들지 않는다.

자동 검사 `python -m unittest workspace.tests.test_build_baked_graphics_bulk_preview`는 2건 모두 PASS했다. 생성 보고서의 `iso_built=false`를 확인했다.

| `QA-BAKED-FULL-001` | 전체 이미지 고정 문구 전수 초벌 | PASS(정적), PENDING(미도달 화면) | 모집단 949, target 66, non-target 883, unknown 0. target 66/66 교체본, 누락 0, 고유 PNG 39. 원본 크기 유지, ISO 생성 없음. 즉시 검수 자산 11, staged 55. 최신 정확 대조에서 덤프 8개·논리 자산 6종 연결. |
| `QA-BAKED-FULL-002` | 전체 이미지 생성기 회귀 검사 | PASS | 관련 Python 스크립트 `py_compile` PASS, `test_build_baked_graphics_bulk_preview` 2건 PASS. 검수 시트와 manifest 재생성 완료. |
| `QA-BAKED-FULL-003` | PPSSPP 신규 덤프 재대조 | PASS(명령/신규 매핑) | 2026-07-24 갱신 명령 정상 종료. 난이도 장식 texture 1의 새 덤프 `0918bd60671c5823a41a5f08.png` 연결. target 66/66·고유 PNG 39·누락 0, 정확 일치 덤프 8개·논리 자산 6종, ISO 생성 없음. |

2026-07-24 기준 정적 이미지 초벌 범위는 완료됐다. 실제 화면 게이트는 미도달 엔딩·크레딧·체험판 화면의 덤프 해시 연결과 조판 검토만 PENDING이다. 동적 조합 문구는 별도 런타임 텍스트 게이트에서 관리한다.
# 2026-07-24 오프라인 이미지 검수 갤러리

| 게이트 | 결과 | 근거 |
|---|---|---|
| `QA-IMAGE-GALLERY-001` | PASS | 번역 대상 66개에 대해 원본 66개와 번역본 66개 생성 |
| `QA-IMAGE-GALLERY-002` | PASS | 66개 전체 원본/번역 이미지 크기 일치 |
| `QA-IMAGE-GALLERY-003` | PASS | 외부 URL·네트워크 의존성 없음, `file://` 직접 실행 구조 |
| `QA-IMAGE-GALLERY-004` | PASS | 검색·상태/분류 필터·원본/번역 비교·오버레이·확대·메모·JSON 내보내기 구현 |
| `QA-IMAGE-GALLERY-005` | PASS | 갤러리 생성 과정에서 ISO를 생성하거나 수정하지 않음 |

실행 파일은 `work/live/image_first_pass_review/gallery/index.html`, 재생성기는 `workspace/scripts/build_image_review_gallery.py`이다. 현재 manifest는 전체 949, target 66, 고유 번역본 39, 즉시 적용/별칭 11, 덤프 대기 55, 누락 0이다. 이 환경에는 Node.js가 없어 `node --check`는 수행하지 못했으며, Python 생성기 문법·데이터 개수·파일 존재·PNG 크기·외부 URL 부재 검사를 수행했다.

## 2026-07-24 이미지 검수 JSON 반영

| 게이트 | 결과 | 근거 |
|---|---|---|
| `QA-IMAGE-REVIEW-IMPORT-001` | PASS | 검수 JSON 66건을 읽어 승인 31, 수정 필요 34, 보류 1로 집계 |
| `QA-IMAGE-REVIEW-IMPORT-002` | PASS | 갤러리 생성 시 66건의 상태와 메모를 초기값으로 포함하고 브라우저 로컬 판정을 우선하도록 구현 |
| `QA-IMAGE-REVIEW-FIX-001` | PASS(정적 생성), PENDING(사용자 재검수) | 수정 필요 34건의 생성 규칙을 갱신하고 전체 66쌍을 재생성. 원본/번역 크기 일치, 누락 0 |
| `QA-IMAGE-REVIEW-FIX-002` | PASS | 관련 Python 생성기 `py_compile` 통과, ISO 생성 없음 |

재검수 대상은 `bg9802`, `bg9803`, `system1`, `anime20 r14`, `anime91 r00 t01`,
`anime92/93 t10~t23`, `start anime00 r73/r87`이다. `system1`은 영어를 유지한다는
검수 결정을 반영해 원본과 동일하게 생성한다. 나머지는 원본 배경과 아틀라스 구조를
유지하면서 지정된 문자 영역만 다시 합성했다.

## 2026-07-25 이미지 검수 확정 JSON 재반영

| 게이트 | 결과 | 근거 |
|---|---|---|
| `QA-IMAGE-REVIEW-IMPORT-003` | PASS | 최신 검수 JSON 66건을 승인 33, 수정 필요 33, 미검수 0으로 집계 |
| `QA-IMAGE-REVIEW-FIX-003` | PASS(정적 생성), PENDING(사용자 2차 검수) | `bg9802`, `bg9803`, `anime20 r14`, `anime92/93 t10~t23`, `start anime00 r73/r87`의 검수 메모를 생성 규칙에 반영 |
| `QA-IMAGE-REVIEW-ASSET-001` | PASS | 원본 명패·회사 로고·나무 간판 프레임을 보존하고 아틀라스 슬롯 좌표를 유지하도록 수정 |
| `QA-IMAGE-REVIEW-REGRESSION-001` | PASS | Python `py_compile`, 관련 단위 테스트 2건, 전체 66쌍 크기 검사와 누락 0 확인 |
| `QA-IMAGE-REVIEW-NOISO-001` | PASS | PPSSPP 교체 텍스처와 오프라인 갤러리만 갱신했으며 ISO는 생성하지 않음 |

2차 검수는 기존 승인 33건을 다시 확인할 필요 없이, JSON에서 `needs_fix`였던
33건만 대상으로 한다. 갤러리는 기존 JSON의 상태와 메모를 미리 불러오므로 수정된
번역 이미지를 확인한 뒤 해당 항목의 판정만 갱신해 새 JSON으로 내보낸다.

## 2026-07-25 이미지 2차 검수 JSON 반영

| 게이트 | 결과 | 근거 |
|---|---|---|
| `QA-IMAGE-REVIEW-IMPORT-004` | PASS | `prinny-image-review-2026-07-25.json` 66건을 승인 34, 수정 필요 32, 미검수 0으로 집계 |
| `QA-IMAGE-REVIEW-FIX-004` | PASS(정적 생성), PENDING(사용자 재검수) | 수정 대상 `bg9802` 1건, `anime91` 1건, `anime20` 1건, 몽타주 28건, 적 명칭 아틀라스 1건을 재생성 |
| `QA-IMAGE-BACKGROUND-PRESERVE-001` | PASS | 인위적 단색 패널을 제거하고 같은 행의 원본 무문자 픽셀로 배경·종이·목재 질감을 복원 |
| `QA-IMAGE-MONTAGE-CLEAN-001` | PASS(대표 프레임 정적 확인) | 프레임별 이름표 원본을 보존하고 원문 대사 전체 높이를 복원해 `anime92 t10/t16/t23`의 일본어 잔재 제거 확인 |
| `QA-IMAGE-REVIEW-REGRESSION-002` | PASS | 관련 생성기 문법 검사, 단위 테스트 2건, 전체 66쌍 크기 일치와 누락 0 확인 |
| `QA-IMAGE-REVIEW-NOISO-002` | PASS | PPSSPP 교체 텍스처와 오프라인 갤러리만 갱신하고 ISO는 생성하지 않음 |

재검수는 기존 승인 34건을 제외하고 최신 JSON에서 `needs_fix`였던 32건만
대상으로 한다. 갤러리는 최신 JSON 66건을 초기 상태로 불러온다.
# QA-STAGE-TUTORIAL-SIGN-HASH-001 — 구·신 해시 통합 (2026-07-25)

- 결과: PASS(정적 파일·설정·해시), PENDING(사용자 실제 화면 재확인).
- 재현 원인: 최신 ISO 덤프 `091591e09a9633045a907f4a.png`는 한글이지만, `ReplaceTextures=False` 상태에서 이전 세이브스테이트가 일본어 아틀라스 `091591e09a963304c67a3ca6`를 복원했다.
- 조치: `ReplaceTextures=True`, `SaveNewTextures=True`로 설정하고 `c67a3ca6`, `53b50c70`, `5a907f4a` 세 콘텐츠 해시를 한글 정본으로 매핑했다.
- 교체 PNG 3개의 SHA-256은 모두 `f5dd9b65bc85483f41e61ceb2212502f8df34f824ab2973d60c95f45ca679eba`이다.
- `textures.ini`는 기존 별칭을 보존한 총 71개 항목이며 SHA-256은 `819f55865220d980e1ae657649b565dd47bf540f802fecb3b4c1881862fbb0b7`이다.
- 재확인 절차: PPSSPP 완전 종료 → 재실행 → 같은 세이브스테이트 로드 → 푯말이 `튜토리얼`로 표시되는지 확인한다.
# QA-SCENE-TEXTURE-CAPTURE-001 — 현재 장면 프레임 기반 해시 특정 (2026-07-26)

| 항목 | 결과 | 근거 |
|---|---|---|
| 도구 경로 및 문법 | PASS | `Tools/PPSSPPSceneTextureCapture/PPSSPPSceneTextureCapture.ps1 -SelfTest` 실행 성공 |
| PPSSPP 설치 탐지 | PASS | `H:/ppsspp/PPSSPPWindows64.exe` 확인 |
| 프레임 덤프 저장소 탐지 | PASS | `H:/ppsspp/memstick/PSP/SYSTEM/DUMP` 확인 |
| 장면 기록 가져오기 | PENDING | 사용자가 목표 화면에서 `Create frame dump`를 실행한 뒤 검증 |
| 데모 스킵 실제 해시 | PENDING | `.ppdmp`의 목표 draw call `Texture Cache State > Hashfiles` 확인 필요 |
| 튜토리얼 푯말 실제 해시 | PENDING | `.ppdmp`의 목표 draw call `Texture Cache State > Hashfiles` 확인 필요 |

검증 기준은 시각적으로 비슷한 PNG나 컨테이너 레코드 번호가 아니라, 실제 화면 draw call이 보고하는 `Hashfiles` 값이다. 이 값과 replacement PNG의 파일명이 일치할 때만 런타임 매핑 PASS로 판정한다.

# QA-STAGE-TUTORIAL-SIGN-HASH-002 — 실제 공용 아틀라스 교체 (2026-07-26)

기존 `QA-STAGE-TUTORIAL-SIGN-HASH-001`의 record 82 추정은 실제 draw call 확인 결과로 대체한다.

| 항목 | 결과 | 근거 |
|---|---|---|
| 실제 런타임 식별자 | PASS | GE/Graphics Debugger `Hashfiles: 08de41e05976a553b6e0db29.png`, 콘텐츠 해시 `b6e0db29`, CLUT 해시 `5976ad5b` |
| 텍스처 형식 | PASS | `256x256`, `CLUT4`, 1 mip |
| 수정 영역 제한 | PASS | 좌표 `[211,179,256,210)` 안 601픽셀 변경, 영역 밖 0픽셀 변경 |
| CLUT 변형 대응 | PASS | 동일 콘텐츠 해시의 5개 런타임 파일을 각각 원본 기반으로 생성 |
| PPSSPP 설치 | PASS | `H:/ppsspp/memstick/PSP/TEXTURES/ULJS00150`에 5개 정확 파일명 설치 |
| 별칭 목록 | PASS | `textures.ini` 총 76개 별칭, SHA-256 `cac569d83fe885aa42501e0dad52695107e64b8308140b0f0c32b9caf98f9dfd` |
| 실제 화면 표시 | PENDING | PPSSPP 텍스처 재로드 후 `튜토` / `리얼` 표시 확인 필요 |
| ISO 생성 | PASS | 생성하지 않음 |

생성 보고서는 `work/live/stage_tutorial_sign/report.json`이며, 실제 화면에서 같은 draw call의 replacement 상태가 `NOT_FOUND`가 아닌 활성 상태로 바뀌는지도 함께 확인한다.
## 2026-07-26 데모 스킵·기한 타이머 QA

| 항목 | 결과 |
|---|---|
| 데모 스킵 3개 CLUT 상태의 픽셀별 복사 | 통과 |
| 타이머 4개 CLUT 상태 생성 | 통과 |
| 타이머 숫자·하단 장식 보호 영역 변경 | 0픽셀 |
| PPSSPP exact Hashfile 7개 설치 | 통과 |
| `textures.ini` 별칭 등록 | 통과 |
| ISO 재빌드 | 미실행 |
| 실제 화면 색상·가독성 | 검증 대기 |

현재 `textures.ini` SHA-256은 `79143db45bcabd0c09db0497786b2087a883f7a1f0bab7800d352d6b825931f3`이며 전체 별칭 수는 83개다.

## 2026-07-26 GE 누락 텍스트 아틀라스 QA

| 항목 | 결과 |
|---|---|
| 생성 도구 문법 검사 | PASS |
| exact Hashfile 생성 | PASS — 15개 |
| PPSSPP 설치 파일 존재 | PASS — 누락 0개 |
| 생성본/설치본 SHA-256 | PASS — 불일치 0개 |
| 텍스트 영역 밖 변경 | PASS — 15개 모두 0픽셀 |
| `textures.ini` 별칭 등록 | PASS — 누락 0개, 총 98개 |
| 공용 숫자·HUD 아틀라스 보호 | PASS — `0939d9b0b3dddb901557c943.png` 미변경 |
| ISO 생성 | PASS — 생성하지 않음 |
| PPSSPP 실제 화면 표시 | PENDING |
| 스테이지 설명 원문 위치·구조 확인 | PASS — `SYSTEM.DAT > start.lzs > StageInfo00.dat`, 20개 고정 레코드 |
| 스테이지 설명 전용 추출기 | PASS — 220개 슬롯(원문 188, 빈칸 32), 재추출 해시 동일 |
| 스테이지 설명 전용 재삽입기 | PASS — `integrate_stage_info_iso.py` |
| 스테이지 설명 번역·길이 검사 | PASS — 번역 188개, 빈 슬롯 32개 보존 |
| 스테이지 설명 실기 확인 | PENDING — 최종 통합 ISO에서 텍스처 교체 OFF 검수 |

`textures.ini` SHA-256은 `58a5f759d74454ad51deb6908a27d359778d8f5cd8ce3fe0e008248a215a0f86`이다. 실제 검수에서는 PPSSPP를 완전히 다시 시작하거나 텍스처를 다시 불러온 뒤, GE 디버거의 replacement 상태가 `ACTIVE`인지 확인한다.

## 2026-07-26 설정·타이틀 런타임 텍스트 QA

| 항목 | 결과 |
|---|---|
| exact Hashfile 3종 생성 | PASS |
| 원본 크기 256×256 및 CLUT4 소비자 유지 | PASS |
| 지정 영역 밖 변경 | PASS — 3종 모두 0픽셀 |
| 생성본/PPSSPP 설치본 SHA-256 | PASS — 불일치 0개 |
| `textures.ini` 별칭 | PASS — 누락 0개, 총 101개 |
| 생성 도구 문법 검사 | PASS |
| ISO 생성 | PASS — 생성하지 않음 |
| PPSSPP 실제 화면 표시 | PENDING |

현재 `textures.ini` SHA-256은 `ec1bfd221cc1888bbe3c7e2d7f1c19b6742c81ad3a87731974725348ad144d4d`다. PPSSPP에서 텍스처를 다시 불러오거나 완전히 재시작한 뒤 세 화면의 replacement 상태가 `ACTIVE`인지 확인한다.

## 2026-07-26 스테이지 설명 소스 경로 QA

| 항목 | 결과 |
|---|---|
| 동일 런타임 버퍼 재사용 확인 | PASS — 같은 키·CLUT에서 콘텐츠 해시만 문장별 변경 |
| CP932 원문 검색 | PASS — `魔風草原`, `死神の処刑塔`, `溶岩星`, `モーブ大要塞` 확인 |
| 원본 내부 파일 확정 | PASS — `StageInfo00.dat` |
| 레코드 구조 확인 | PASS — 20개, 크기 `0x170`, 문자열 슬롯 11×33바이트 |
| 기존 exact PNG 방식 판정 | 미리보기 전용 — 생산 방식으로 사용하지 않음 |
| 전용 CSV/JSON 추출 | PASS — `stage_info.csv` 220행, `stage_info_manifest.json` 생성 |
| 번역 재삽입 및 고정 길이 검증 | PASS — 188개 재삽입, 슬롯 초과 0개 |

## 2026-07-26 스테이지 설명 번역표·임시 PNG 정리 QA

| 항목 | 결과 |
|---|---|
| 원본 검증 | PASS — 7,376바이트, 20레코드, SHA-256 `96473f7b75e3da3676c43f8332518a7722e8cbc968c98436a0e9aeae608720e0` |
| 번역표 행 보존 | PASS — 총 220행, 원문 188행, 빈 슬롯 32행 |
| 고정 슬롯 한도 기록 | PASS — 각 슬롯 최대 32바이트 |
| 재추출 결정성 | PASS — CSV·manifest 재생성 전후 SHA-256 동일 |
| 임시 스테이지 설명 PNG 정리 | PASS — 프로젝트 생성물 6개·PPSSPP 설치본 6개 제거 |
| `textures.ini` 연결 정리 | PASS — 6개 제거, 잔존 연결 0개 |
| PPSSPP 원본 덤프 보존 | PASS — `new` 폴더 6개 모두 유지 |
| ISO 생성 | PASS — 생성하지 않음 |
| SYSTEM.DAT 재패킹 | PASS — 최종 ISO 내부 `StageInfo00.dat` 해시 일치 |
| PPSSPP 실제 화면 표시 | PENDING — 텍스처 교체 OFF 검수 |

번역표는 `workspace/text/translation/stage_info.csv`, 보호 메타데이터는 `workspace/text/source/stage_info_manifest.json`이다. 현재 `textures.ini` SHA-256은 `de1bda4d35e68d3488e80a95dba8eab67796d15834e81985d010bb24b1c2d062`다.

## 2026-07-26 `□話しかける` 누락 보완 QA

| 항목 | 결과 |
|---|---|
| 원본 분류 | PASS — `StageInfo00.dat`가 아닌 BOOT/EBOOT 공용 UI |
| 원본 위치 | PASS — `BOOT.BIN` `0x0ED96C`, `□話しかける` |
| 번역 정본 추가 | PASS — `workspace/text/boot_ui_translation.json`, `□말 걸기` |
| BOOT UI 전체 감사 | PASS — 78개 슬롯, 오류 0 |
| 고정 슬롯 길이 | PASS — 16바이트 슬롯, 번역 9바이트, 잔여 6바이트 |
| 기존 `stage_info.csv` 보존 | PASS — 수정하지 않음 |
| 통합 ISO 반영 | PASS — BOOT/EBOOT 동시 적용 |
| PPSSPP 실제 화면 표시 | PENDING |

## 2026-07-26 전체 번역 통합 ISO QA

| 항목 | 결과 |
|---|---|
| BOOT/EBOOT 공용 UI | PASS — 78개 슬롯 |
| `□말 걸기` 통합 | PASS |
| 스테이지 설명 재삽입 | PASS — 번역 188개, 빈 슬롯 32개 보존 |
| 통합 글자표 | PASS — 852자, 슬롯 초과 없음 |
| 번역 PNG 네이티브 삽입 | PASS — 총 66개 |
| 이미지 컨테이너 분포 | PASS — `BG.DAT` 3, `ANIME.DAT` 56, `start.dat` 1, `start.dat/anime00.dat` 6 |
| 최종 ISO 내부 `StageInfo00.dat` | PASS — SHA-256 `f547673fede361425551c5e721a47a1536d8c826348d98a6ba45a4afa8121d13` |
| 최종 ISO 내부 `font.fnt` | PASS — SHA-256 `1de8a11e2d4f169eccfd3a9ffb6052ea6033b9dea0d480a014a18c2cd6f84663` |
| 최종 ISO 내부 `font.txp` | PASS — SHA-256 `ede4ea1ae63c67deaf0779f67817e3082bc7edae1aa06510cc25dba67b98703f` |
| 이미지 삽입 후 BOOT/EBOOT 보존 | PASS — 중간 통합본과 바이트 일치 |
| 최종 ISO 크기 | PASS — 500,465,664바이트 |
| 최종 ISO SHA-256 | PASS — `e8366e824b005ce6f8611cba144e3543b43e570b541c55f8c9e664a3941818e1` |
| 이전 테스트·중간 ISO 정리 | PASS — 원본과 최신 통합본만 보존 |
| PPSSPP 텍스처 교체 OFF 실기 검수 | PENDING |

실기 검수는 PPSSPP의 `Replace textures`를 끄고 `work/production/Prinny_ULJS00150_KR_Integrated_20260726.iso`를 새로 부팅해 진행한다. 이전 세이브스테이트는 구형 텍스처와 메모리를 복원할 수 있으므로 최초 확인은 세이브스테이트를 불러오지 않는다.

우선 확인할 화면은 타이틀·난이도 선택, `□말 걸기`, 일반 대사와 화자명, 튜토리얼, 데모 스킵, 월드 푯말, 스테이지 설명, 스테이지 결과의 시간·`마리`, 거점·설정 UI 및 엔딩 이미지다. 자동 검증은 컨테이너 삽입과 파일 보존까지만 보장하며 화면별 번역 누락 여부는 이 실기 게이트에서 확정한다.

## 2026-07-26 직접 실행 폴더 복구 QA

| 항목 | 결과 |
|---|---|
| clean 추출본 식별 | PASS — 원본 ISO의 BOOT/EBOOT/SYSTEM/ANIME/BG와 SHA-256 일치 |
| 원본·clean 보존 | PASS — `extracted`는 읽기 전용 입력으로 사용 |
| ISO 생성 | PASS — 생성 0건 |
| 주 빌드 | PASS — `workspace/scripts/build_direct_run.py` |
| 전체 테스트 | PASS — 104 tests |
| 변경 파일 경계 | PASS — BOOT, EBOOT, SYSTEM, ANIME, BG 5개만 변경 |
| BOOT/EBOOT | PASS — SHA-256 `07e2180dfc9acf3524ab22fd51f5f7de25452ffd935ce09a06faf23589dd8f13` |
| `StageInfo00.dat` | PASS — SHA-256 `f547673fede361425551c5e721a47a1536d8c826348d98a6ba45a4afa8121d13` |
| 스테이지 CSV/manifest | PASS — 220행 전부 일치, 188 번역 + 32 빈 슬롯 |
| 스테이지 키/좌표 중복 | PASS — entry ID, record+slot, source offset 모두 0건 |
| probe 정적 검증 | PASS — 첫 5/마지막 5 레코드에 고유 표식 20개 |
| 번역 PNG 네이티브 삽입 | PASS — 66개 전부 소비, ANIME/BG 해시 기존 통합 결과와 일치 |
| 최신 Demo00 반영 | PASS — SHA-256 `9a31bd10bcca27386f9e96bd2063e532a7a742d58042bf81d864700531a09563` |
| PPSSPP 직접 실행 | PENDING — 사용자 실기 검수 필요 |

기존 통합 ISO의 `Demo00.dat`은 `7780baa4…`였고 현재 사용자 정본에서
재생성한 `Demo00.dat`은 `9a31bd10…`이다. 14개 레코드의 화자 또는 대사
슬롯이 달라져 `SYSTEM.DAT` 전체 해시가 기존 ISO와 다른 것은 의도된 결과다.
그래픽 컨테이너와 StageInfo/폰트는 기존 정적 통합 결과와 일치한다.

스테이지 반복 표시 원인은 아직 실기에서 확정하지 않았다. probe에서도 서로
다른 `Sxx`가 같은 값으로 보이면 런타임 레코드 선택/캐시 경로를 조사하고,
고유 표식이 정상이라면 기존 오염 트리 또는 replacement texture 별칭을 원인
후보로 좁힌다.

## 2026-07-26 데모 스킵 합성 문구 색상 통일 QA

| 항목 | 결과 |
|---|---|
| exact Hashfile | PASS — `f54138b2`, `f96c6b82`, `a8d5fd96` 3종 유지 |
| 통일 영역 | PASS — `[8,24,84,56)` |
| 기준 색상·알파 | PASS — 세 파일 모두 `f54138b2` 영역과 바이트 일치 |
| 변경 픽셀 | PASS — `a8d5fd96` 970, `f54138b2` 0, `f96c6b82` 970 |
| 보호 영역 | PASS — 문구 영역 밖 변경 0픽셀 |
| 타이머 자산 | PASS — 작업 전 백업본으로 복구, `--demo-only`에서 미처리 |
| 단위 테스트 | PASS — 관련 2 tests, 전체 106 tests |
| 설치 경로 | PASS — `H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150` |
| ISO 생성 | PASS — 생성하지 않음 |
| PPSSPP 실기 표시 | PENDING — replacement texture를 켜고 재시작 필요 |

생성 보고서는 `work/live/demo_skip_timer_preview/report.json`, 작업 전 설치본은
`backups/demo_skip_uniform_before_20260726`에 보관한다.

## 2026-07-26 사용자 실행 경로·스테이지 누락 복구 QA

| 항목 | 결과 |
|---|---|
| 잘못 실행된 대상 | CONFIRMED — 최근 실행 1번이 `direct_run_stage_probe` |
| `S02` 원인 | CONFIRMED — probe가 제목·첫 줄에 넣은 진단 표식 |
| 새 실행 대상 | PASS — `work/builds/direct_run_latest`, `stage_mode=full`, probe 0개 |
| LuckyDoll 원본 구조 | PASS — 8,176바이트, 120레코드, 68바이트 stride |
| LuckyDoll 번역 | PASS — 120/120, 고유 원문·번역 각 40개 |
| LuckyDoll 슬롯 한도 | PASS — 최대 56/65바이트, 최소 잔여 9바이트 |
| LuckyDoll 출력 SHA-256 | PASS — `04b27853df8243ecaecde5636221a78d5dc17e7f33c4cdaf3a64795fc5fd5dcc` |
| 교체 팩 누락 파일 복구 | PASS — 8개 |
| exact 자기 별칭 추가 | PASS — 11개 |
| 교체 팩 target 무결성 | PASS — 설치 PNG 51개, 별칭 106개, 누락 0개 |
| 오래된 스테이지 설명 PNG 별칭 | PASS — 6개 모두 없음 |
| PPSSPP 설정 | PASS — `ReplaceTextures=True` |
| PPSSPP 실행 경로 | PASS — `direct_run_latest` 명령줄 실행 확인 |
| 전체 자동 테스트 | PASS — 108 tests |
| 실제 화면 재검수 | PENDING — 재실행된 PPSSPP에서 사용자 확인 |

이번 수정은 ISO를 만들지 않았다. `PictureBook.dat` 91개 도감 레코드 전체
번역은 별도 모집단이며 이번 스크린샷의 튜토리얼 exact texture 복구와 혼동하지
않는다.

## 2026-07-26 셀 조판·UI 슬롯·렌더러 범위 수정 QA

| 항목 | 결과 |
|---|---|
| 데모 스킵 셀 구조 | PASS — 행마다 13×14 셀 6개 |
| 데모 스킵 조판 | PASS — `리플레이저장` 6셀, `데모스킵` 4셀+빈 2셀 |
| CLUT 상태 일치 | PASS — 세 exact texture의 셀 영역 RGBA 동일 |
| 셀 영역 밖 변경 | PASS — 0픽셀 |
| 전체 BOOT UI 후보 덤프 | PASS — `boot_ui_candidates_full.json` 3,702개 조사 후보 |
| 실기 확인 슬롯 승격 | PASS — 27개 추가, 정본 총 105개 |
| BOOT UI 고정 길이·NUL·포맷 | PASS — 105/105 |
| 스테이지 목록 소유자 | CONFIRMED — BOOT `0x0ED34C`부터 |
| 튜토리얼 메뉴 소유자 | CONFIRMED — BOOT `0x0EE83C`부터 |
| 지역 하단 포맷 소유자 | CONFIRMED — BOOT `0x0F0C98`부터 |
| 글자폭 ASM 범위 | PASS — F0-F9 9px, 원본 일본어 13px |
| 코드 동굴 | PASS — punctuation 164 + advance 32 = 196/196바이트 |
| 직접 실행 빌드 | PASS — `stage_mode=full`, BOOT UI 105슬롯 |
| 전체 자동 테스트 | PASS — 108 tests |
| ISO 생성 | PASS — 생성하지 않음 |
| 반복 상하 이동 실기 | PENDING — 새 실행본에서 확인 필요 |

이전 QA의 “오른쪽 목록과 조건문은 LuckyDoll.dat가 소유” 판정은 기각한다.
LuckyDoll 번역은 유지하되 이번 화면의 목록·포맷은 BOOT 고정 슬롯으로 검증한다.

## 2026-07-26 데모 스킵 현재 실행 해시 도달성 QA

| 항목 | 결과 |
|---|---|
| 현재 네이티브 content hash | CONFIRMED — `6ceb80dc` |
| 기존 교체 팩 도달성 | FAIL — `f4cbdbb1` exact 3종만 등록돼 현재 해시 미선택 |
| `6ceb80dc` CLUT 3종 생성·설치 | PASS |
| 동일 CLUT의 구/신 해시 출력 픽셀 | PASS — SHA-256 동일 |
| 셀 영역 밖 변경 | PASS — 0픽셀 |
| `textures.ini` | PASS — 109 aliases, 누락 0 |
| 전체 자동 테스트 | PASS — 108 tests |
| 새 실행 화면 판독 | PENDING — PPSSPP 완전 재시작 후 사용자 확인 |

정적 파일과 교체 팩 연결은 복구했지만 실제 화면 확인 전에는 그래픽 런타임
게이트를 완료로 승격하지 않는다.

## 2026-08-02 DLC 초기 추출·설치 기준선 QA

| 항목 | 결과 |
|---|---|
| 지원 입력 식별 | PASS — EDAT 3개와 `PARAM.PBP` 크기·SHA-256 고정 |
| DIDT0 청크 파싱 | PASS — 세 파일 모두 `NEND`까지 15개 청크, 남는 바이트 0 |
| 무변경 컨테이너 왕복 | PASS — 3/3 바이트 동일 |
| DDEM 구조 왕복 | PASS — 67레코드, 182개 비어 있지 않은 텍스트 슬롯 |
| 기존 기본 NSF의 DLC 참조 | PASS — 52/52가 DL0000·DL0001에 존재 |
| DLC 로컬 DDEM | PASS(구조) — DL0002 15레코드, `C35C` 실행 도달성은 미확정 |
| DSTI 구조 왕복 | PASS — 3×11=33슬롯, 비어 있지 않은 슬롯 31개 |
| 번역 CSV 보호 경계 | PASS — `ko/status/notes`만 재추출 때 승계 |
| 신규 DLC 단위 테스트 | PASS — 6 tests |
| 전체 자동 테스트 | PARTIAL — 116개 실행, 신규 포함 114 PASS; 삭제된 구 빌드 경로를 참조하는 기존 2건 ERROR |
| PPSSPP 1.19.3 설치 동일성 | PASS — 네 파일이 지원 입력과 일치 |
| PPSSPP DLC 적재·화면 | PENDING — 세 DLC 직접 진입과 화면 캡처 필요 |
| PSP 실기 | PENDING |

전체 테스트의 두 ERROR는 `work/builds/integrated_20260726`와
`work/builds/latest_20260722`가 삭제된 뒤에도 남은 기존 테스트 참조다. 이번 DLC
코드 경로와 무관하며, 전체 PASS로 표시하지 않는다. 설치 검증 보고서는
`work/analysis/dlc_install_baseline.json`, 구조·분모 기록은 `docs/dlc-survey.md`가
소유한다.

### DLC 기준선 첫 실행 경로 수정

첫 실행에서는 `Start-Process -ArgumentList @($gameRoot)`가 공백이 포함된 직접 실행
경로를 따옴표 없이 전달해 PPSSPP 프로그램만 열리고 게임은 적재되지 않았다. 실제
명령줄에서 경로가 `G:\Downloads\Korean ...` 형태로 분리된 것을 확인했다.

`launch_prinny_korean.ps1`과 현재 실행 명령을 전체 경로 명시 인용 방식으로 수정했다.
재실행 PID 20496의 창 제목이
`PPSSPP v1.19.3 - ULJS00150 : プリニー ～オレが主人公でイイんスか？～`로 바뀌어
게임 식별·적재까지 확인했다. DLC 화면 도달과 텍스트 판독은 계속 PENDING이다.

## QA-RESULT-TIME-SPACING-20260803 — 결과 화면 트로피/시간 순서 복원

- 사용자 확인으로 네이티브 월드 푯말·튜토리얼·타이머 HUD는 텍스처 교체 OFF에서 PASS로 승격했다.
- 결과 화면의 트로피는 고정 좌표이고 시간은 `BOOT.BIN` 포맷 문자열의 선행 폭에 따라 출력된다.
- `0x0EE2F8`은 `클리어 + 전각 7칸 + 반각 2칸`, `0x0EE320`은 `최고 + 전각 8칸 + 반각 1칸`으로 변경했다. 두 행의 숫자 시작 폭은 원문과 각각 0px, 약 2px 차이다.
- 빌드: `work/builds/stage_hud_native_result_spacing_20260803/direct_run`.
- 정적 검증: BOOT UI 590슬롯 감사 PASS, 기존 네이티브 HUD 빌드 대비 `BOOT.BIN`·`EBOOT.BIN`만 변경, 각 파일의 허용된 두 슬롯에서만 61바이트 변경 PASS.
- 자동 테스트: 117개 중 115 PASS. 나머지 2건은 삭제된 과거 fixture 경로를 참조해 ERROR이며 이번 변경과 무관하다.
- R1 임시 ISO `1185EB02...506058`은 시간의 첫 두 자리와 트로피가 겹쳐 FAIL이며 ISO를 삭제했다.
- R2는 첫 토큰을 `%8.2d`로 바꿔 트로피 뒤에 런타임 선행 공백 6칸을 생성한다. 저장 바이트·표시 처리 예산은 원문과 동일하다.
- R2 임시 ISO SHA-256: `AE53BC4B960B263A362756E801C21DA7224CE3DD735D2DA5882C04A0248622AC`; PPSSPP Headless 8초 부팅 PASS.
- 2026-08-03 사용자 확인: 스테이지 클리어 결과의 두 행이 `라벨 → 트로피 → 시간` 순서로 보이고 서로 겹치지 않는다. R2 실제 화면 PASS.
- R2를 정식 ISO로 재현했고 SHA-256은 임시 ISO와 동일한 `AE53BC4B960B263A362756E801C21DA7224CE3DD735D2DA5882C04A0248622AC`이다.
- 배포 xdelta 역적용본도 같은 해시로 일치했으며 PPSSPP Headless 1.19.3에서 `EBOOT.BIN`, `SYSTEM.DAT`, `STAGE.DAT` 적재와 8초 게임 루프를 PASS했다.

## QA-APPLY-MAIN-HASH-20260804 — CMD 적용 후 오검증 수정

- 재현: 최종 배포의 `apply_main.cmd`에 지원 원본 ISO를 전달하면 출력 ISO 생성 뒤 검증 오류가 발생했다.
- 출력 SHA-256은 정상 최종값 `AE53BC4B960B263A362756E801C21DA7224CE3DD735D2DA5882C04A0248622AC`이었고, 스크립트의 기대값만 이전 R7 해시였다.
- 기대값 수정 후 실제 CMD 실행은 `PASS`, 종료 코드 0, 출력 크기·해시 일치로 통과했다.
- 갱신된 배포 ZIP 내부 `apply_main.ps1`에서 최종 해시가 확인됐고 금지 확장자 엔트리는 0개다.
