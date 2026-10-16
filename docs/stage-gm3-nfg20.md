# STAGE.DAT GM3/NFG2 조사 및 HUD ISO 내장 PoC

조사 기준일은 2026-08-03이다. 기준 `STAGE.DAT`는 155,647,296바이트이며 SHA-256은
`09E373171069B3FF9402EEF0FD4B86E1D21A3C1EA6597265038A305C8935F717`이다.

## GM3 확정 구조

- `STAGE.DAT` NISPACK에는 GM3 157개와 DAT 159개가 있다.
- GM3 선두의 첫 u32는 모델 블록 수이자 관찰 버전으로 `1`, `2`, `3`이 존재한다.
- 둘째 u32는 텍스처 수, 셋째 u32는 전 표본에서 동일한 미확정 값이다.
- 버전에 따라 추가 u32가 `version - 1`개 있고, 뒤의 offset table은 모델 블록 시작과 텍스처 시작을 담는다.
- 텍스처 헤더는 `<IHHHBBHH>`이며 `size, width, height, palette_count, log2_width, log2_height, swizzled, flags` 순서다.
- 팔레트는 RGBA8888이다. 16색은 4bpp, 256색은 8bpp이며 4bpp의 왼쪽 픽셀은 low nibble이다.
- `swizzled=1`은 PSP 16바이트 x 8행 블록 순서를 사용한다.

전수 결과는 GM3 157개, 텍스처 1,611개다. 버전 분포는 v1 148개, v2 8개, v3 1개다.
모든 텍스처의 디코드와 동일 인덱스 재삽입이 바이트 단위 무변경으로 통과했다.
정본 보고서는 `work/analysis/gm3_nfg20_survey_20260803/stage_gm3_inventory.json`이다.

## PPSSPP quick hash 교차 검증

PPSSPP 공식 `StableQuickTexHash`와 동일한 계산을 구현해 GM3 원시 픽셀 payload를 대조했다.

- 월드 방향 표지판 content hash `65714c1a`: `st000_01~10`, `st000_21~27`의 `texture-6`과 정확히 일치, 총 17개
- 튜토리얼 표지판 content hash `b6e0db29`: GM3 일치 0개
- 데모 스킵 타이머 content hash `b5a34886`: GM3 일치 0개

따라서 월드 표지판은 GM3 저장 자산으로 확정했다. 나머지 두 CLUT4 버퍼는 완성 GM3 텍스처가 아니며,
런타임 생성 또는 별도 복사 경로를 추적해야 한다.

## NFG2 계열 현황

DAT 159개 중 157개가 `NFG2` 접두를 사용한다. 5번째 바이트는 `0x30`, `0x40`, `0x60`, `0xD0`, `0xF0` 변형이 있다.
나머지 2개는 68/84바이트의 `camerawork001_01.dat`, `camerawork001_02.dat`다.
NFG2 계열에서는 16바이트 정렬된 `NCEL`, `NGIM`, `NMSP`, `NARE`, `NRED`, `NEND` 섹션 표식이 반복된다.
현재 증거로는 텍스처 저장소가 아니라 셀·영역·연결/맵 정보 컨테이너로 분류한다. 필드 의미는 아직 미확정이다.

## 월드 표지판 PoC

`build_stage_world_sign_poc.py`는 기존 256색 팔레트를 보존하고 번역 PNG를 최근접 팔레트 인덱스로 변환한다.
content hash가 일치하는 17개 픽셀 payload만 같은 크기로 수정한다.

- 출력: `work/analysis/gm3_nfg20_survey_20260803/world_sign_poc/STAGE.DAT`
- 출력 SHA-256: `0F2D45CAC1D4E84CB9D20E59E4309A8AFEB526B1A26FB5B93E0AA4267E8FE63E`
- 변경 바이트: 127,075개, 비대상 변경 0개
- 수정본 전수 검사: GM3 157개, 텍스처 1,611개 파싱 및 no-op 왕복 PASS
- 별도 직접 실행본: `work/builds/stage_gm3_world_sign_poc_20260803/direct_run`
- 기존 R7 직접 실행본과 다른 파일: `PSP_GAME/USRDIR/STAGE.DAT` 1개뿐

PPSSPP에서는 텍스처 교체를 끈 상태로 새 게임 부팅 후 월드 방향 표지판을 확인해야 한다.
2026-08-03 사용자가 PPSSPP 텍스처 교체를 끈 상태에서 PoC 직접 실행본의 월드 방향 표지판이
한글로 정상 출력됨을 확인했다. 따라서 GM3 저장·재삽입·게임 소비 경로는 런타임 PASS다.
실기 검증은 PENDING이며, 튜토리얼 푯말과 타이머가 남아 있으므로 아직 배포 xdelta에는 포함하지 않는다.

PPSSPP Headless 1.19.3 직접 실행 검사는 ULJS00150, EBOOT, Disgaea 모듈, `SYSTEM.DAT`,
수정된 `STAGE.DAT` 열기와 8초 메인 루프를 확인해 PASS했다. 보고서는
`work/analysis/gm3_nfg20_survey_20260803/world_sign_poc/headless_boot.json`이다.
이는 로더 안정성 증거이며 표지판의 실제 화면 가시성이나 실기 호환성을 증명하지는 않는다.
실제 화면 가시성은 위 사용자 확인으로 별도 PASS 처리한다.

## 튜토리얼 푯말·타이머 ANIME 소유자 확정

PPSSPP 1.19.3에서 슬롯 7을 기준으로 `0x08DE41E0`의 32KB를 덤프했다. 이 버퍼의
`StableQuickTexHash`는 기존 튜토리얼 content hash `b6e0db29`와 정확히 일치했다.
같은 시점의 타이머 주소 `0x09596A50`는 전부 0이어서 타이머 생성 전 상태임을 확인했다.

GM3만이 아니라 `ANIME.DAT`, `BG.DAT`, `SCRIPT.DAT`, `STAGE.DAT`, `SYSTEM.DAT`와
해제 `start.dat`의 TXP/ANIME 텍스처 695개를 같은 해시로 전수 대조했다.

- 튜토리얼 `b6e0db29`: `SYSTEM.DAT/start.lzs/anime00.dat`, record 17 texture 0
- 타이머 `b5a34886`: `ANIME.DAT/anime95.dat`, record 3 texture 0

둘 다 256×256, 4bpp, PSP swizzle 텍스처다. 따라서 두 자산은 런타임 생성 이미지가
아니라 ANIME 원시 픽셀이 고정 RAM 주소로 복사되는 경로다. 원본 소유자 보고서는
`work/analysis/gm3_nfg20_survey_20260803/runtime_trace/indexed_hash_matches.json`이다.

## 3종 스테이지 HUD 네이티브 PoC

`build_stage_hud_iso_poc.py`가 월드 표지판 `STAGE.DAT` PoC와 위 두 ANIME 텍스처를
R7 직접 실행본에 결합한다. 튜토리얼 5개 CLUT 상태와 타이머 4개 CLUT 상태는 하나의
공유 인덱스 배치로 역양자화한다. 팔레트와 descriptor는 보존하며 승인된 문자 영역
안의 픽셀 인덱스만 바꾼다.

- 출력: `work/builds/stage_hud_native_poc_20260803/direct_run`
- 변경 파일: `ANIME.DAT`, `SYSTEM.DAT`, `STAGE.DAT` 3개
- 튜토리얼: 영역 안 457 인덱스 변경, 영역 밖 0, 새 content hash `c8321c07`
- 타이머: 영역 안 6,659 인덱스 변경, 영역 밖 0, 새 content hash `4a8f828a`
- 패치 후 695개 전수 해시 감사에서 원본 두 해시는 0건이고 새 해시는 각 소유자 1건이다.
- `start.lzs`는 3,582,463바이트로 재압축돼 3,630,771바이트 슬롯에 수용됐고
  해제 왕복이 바이트 동일하다.

PPSSPP 1.19.3, 텍스처 교체 OFF에서 새 `SYSTEM.DAT`의 튜토리얼 32KB가 실제
`0x08DE41E0`에 적재됐으며 런타임 hash도 `c8321c07`로 일치했다. 이로써 튜토리얼은
저장→적재 경계까지 PASS다. 기존 세이브 상태의 장면 복원은 1.19.3에서 `sceKernel`
실패, 개발판에서 개발 메뉴 진입으로 재현성이 없어서 시각 PASS에는 쓰지 않았다.
타이머 장면의 실제 RAM·화면 확인과 두 항목의 실기 확인은 PENDING이다.

`build_final_iso.py`는 이제 `STAGE.DAT`까지 포함해 6개 파일을 같은 고정 extent 방식으로
삽입한다. 임시 6파일 ISO SHA-256 `F0C59864...F75BB`는 PPSSPP Headless 8초 부팅에서
`SYSTEM.DAT`와 `STAGE.DAT` 열기 및 게임 루프 진입을 PASS했다. 사용자 요청에 따라
임시 ISO는 검증 직후 삭제했고 프로젝트의 `original` 밖 ISO는 다시 0개다.
