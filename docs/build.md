# 조사·빌드 절차

## 최신 번역 통합 빌드 (2026-07-22)

최신 `demo00_translation.json`을 기준으로 고정 슬롯 수요를 재감사한 뒤 Demo00, 공용 폰트, BOOT UI, 타이틀, 튜토리얼 `ANIME.DAT`을 순서대로 원본 ISO에 통합한다. 마지막으로 혼합 CP932 타자 효과와 문장부호 간격 패치를 적용한다.

- 번역 SHA-256: `bd6063fa6bb69b76fe2dfaf968a8c0d559e7d5c051c57ea510cf0cf07c93447b`
- Demo00 전용 글리프 감사: `work/analysis/demo00_latest_base_reclaim_20260722.json`, PASS, 수요 `830`, 잉여 `86`
- BOOT UI 합산 글리프 감사: `work/analysis/demo00_latest_reclaim_20260722.json`, PASS, 수요 `841`, 잉여 `73`
- 삽입 Demo00 SHA-256: `7780baa4b8d03b2d402da232ec4f5c75291908b4de00f80df9a18b7903b9ee60`
- 결과 ISO: `work/production/Prinny_ULJS00150_KR_Latest_20260722.iso`
- 결과 SHA-256: `8b2367575b63b256ba6b1707191f3406c63f397a8bfef421ed3489edd1134463`

최종 자동 검증 명령은 다음과 같다.

```powershell
$env:PYTHONPATH = (Resolve-Path '.\workspace\scripts').Path
python -m unittest discover -s .\workspace\tests -p 'test_*.py'
python .\workspace\scripts\ppsspp_boot_probe.py `
  H:\ppsspp\PPSSPPHeadless.exe `
  .\work\production\Prinny_ULJS00150_KR_Latest_20260722.iso `
  .\work\reports\latest_20260722_ppsspp.json --duration 8
```

검증 성공 후에는 원본과 새 최신 ISO를 제외한 모든 `*.iso`를 삭제한다. 이번 빌드에서는 기존 생산본 2개와 중간 ISO 5개를 제거했다.

## 일반 대사 문장부호 2px 선행 간격 시험 빌드 (2026-07-22)

타자 효과 v2 ISO의 `BOOT.BIN`과 `EBOOT.BIN`에 문장부호 전용 분기 훅을 추가한다. v2가 사용한 코드 동굴 316바이트의 SHA-256과 남은 0 패딩을 먼저 검증하며, `!`, `?`, `,`, ASCII 마침표가 내부에서 변환된 CP932 `0x8144`만 그리기 전에 2px 전진시키고 해당 글리프 전진 폭에도 2px를 더한다. 한글 기본 전진 폭 9px와 공백 6px는 바꾸지 않는다.

```powershell
python .\workspace\scripts\build_dialog_punctuation_spacing_patch.py `
  .\work\production\Prinny_ULJS00150_KR_TwoLine_TypewriterFix_v2_Test_20260722.iso `
  .\work\production\Prinny_ULJS00150_KR_TwoLine_TypewriterFix_v3_Punctuation2px_Test_20260722.iso `
  .\work\reports\dialog_punctuation_spacing_v3_test_20260722.json `
  --leading-gap 2

python .\workspace\scripts\ppsspp_boot_probe.py `
  H:\ppsspp\PPSSPPHeadless.exe `
  .\work\production\Prinny_ULJS00150_KR_TwoLine_TypewriterFix_v3_Punctuation2px_Test_20260722.iso `
  .\work\reports\dialog_punctuation_spacing_v3_ppsspp_20260722.json --duration 8
```

- 기준 v2 ISO SHA-256: `99e80a71f088753ec9f255bd852e45a1f99e534ba8896be03901aef01bba5871`
- 결과 v3 ISO SHA-256: `98637963c8a6a249e9b67ab74920a5c5818f3602af8eb7a6cb7646983e33d844`
- 추가 코드 동굴: `0x088D0F08`부터 164바이트, 남은 32바이트
- 자동 검증: 100 tests PASS, PPSSPP Headless 8초 게임 루프 PASS
- 실제 화면 게이트: 쉼표·느낌표·물음표 앞뒤 2px 간격, 말줄임표와 뒤 글자의 분리, 기존 한글 자간·공백 회귀 부재 PENDING
- 보존 상태: 자동 검증 성공 뒤 직전 v2 테스트 ISO를 삭제하고 v3만 보존했다.

## 일반 대사 타자 효과·자간 보정 시험 빌드 (2026-07-22)

두 줄 출력 기준 ISO의 `BOOT.BIN`과 `EBOOT.BIN`에 혼합 CP932 타자 효과 훅을 설치한다. 스크립트는 모든 원본 명령과 0 패딩 코드 동굴을 지문 검사하고, CP932 논리 글자 수와 완전한 문자 prefix를 계산하는 두 함수를 삽입한다. 공백 6px·일반 2바이트 글리프 9px 시험값도 함께 적용한다.

```powershell
python .\workspace\scripts\build_dialog_typewriter_patch.py `
  .\work\production\Prinny_ULJS00150_KR_TwoLine_Test_20260719.iso `
  .\work\production\Prinny_ULJS00150_KR_TwoLine_TypewriterFix_v2_Test_20260722.iso `
  .\work\reports\dialog_typewriter_fix_v2_test_20260722.json `
  --space-advance 6 --double-byte-advance 9

python .\workspace\scripts\ppsspp_boot_probe.py `
  H:\ppsspp\PPSSPPHeadless.exe `
  .\work\production\Prinny_ULJS00150_KR_TwoLine_TypewriterFix_v2_Test_20260722.iso `
  .\work\reports\dialog_typewriter_fix_v2_ppsspp_20260722.json --duration 8
```

- 기준 ISO SHA-256: `25674dcdc093ea86041c57d330e9e284e4f54d2708e2401d02199ff7ab1eb22c`
- 결과 ISO SHA-256: `99e80a71f088753ec9f255bd852e45a1f99e534ba8896be03901aef01bba5871`
- 변경 범위: 양쪽 ELF의 타자 훅 5개, 간격 명령 2개, ASCII 판별 명령 5개, 코드 동굴 `0x088D0DCC`부터 316바이트
- 자동 검증: 97 tests PASS, PPSSPP Headless 8초 게임 루프 PASS
- 실제 화면 게이트: v1 폭 축소 PASS·임시 이상 문자 FAIL. v2 쉼표 표시, 출력 중 이상 문자 없음, 완성 전후 동일 문자열 PENDING
- 제한: 9px 기본 2바이트 경로는 일본어에도 영향을 주는 시험값이다. 타자 효과 훅은 CP932 전체에 안전하게 적용되지만 폭 값은 승인 후 한글 전용 분기로 제한한다.

### 테스트 ISO 정리 절차

새 테스트 ISO를 만들 때는 결과 파일의 크기·SHA-256을 확인하고 단위 테스트 및 PPSSPP Headless 기본 부팅을 통과한 뒤 `work/production`, `work/builds`, `work/diagnostics`의 이전 테스트 ISO를 삭제한다. 새 빌드나 검증이 실패하면 직전 정상 시험판은 유지한다. 확정·최종 ISO는 이 자동 정리 대상에서 제외한다.

2026-07-22에 이전 시험 ISO 총 23개를 삭제했다. 현재 `work` 보존 목록은 다음 두 파일뿐이다.

- `Prinny_ULJS00150_KR_Demo00_Title_Final.iso`
- `Prinny_ULJS00150_KR_TwoLine_TypewriterFix_v3_Punctuation2px_Test_20260722.iso`

이 문서 아래의 예전 테스트 ISO 경로와 해시는 빌드 이력이며 해당 ISO 파일은 삭제되었다. 삭제된 중간 기준물이 필요한 재빌드에서는 원본 ISO와 기록된 생산 파이프라인으로 임시 기준물을 다시 만든 뒤, 새 시험판 검증 후 함께 정리한다.

## Demo00 수동 2줄 테스트 빌드 (2026-07-19)

`workspace/text/demo00_translation.json`의 `demo00/081A`는 세 개의 독립적인 34바이트 페이로드 줄 슬롯을 갖는다. 이번 시험에서는 `자, 기한은 내일`, `아침까지야.`, 빈 문자열 순으로 삽입했다. Demo00와 통합 폰트를 다시 만든 뒤 `start.dat` → `start.lzs` → `SYSTEM.DAT`을 재구성하고, 승인된 `ANIME.DAT`, 패치된 `BOOT.BIN`, 0 패딩한 평문 `EBOOT.BIN`을 원본 ISO 고정 extent에 삽입했다.

- 결과물: `work/production/Prinny_ULJS00150_KR_TwoLine_Test_20260719.iso`
- ISO SHA-256: `25674dcdc093ea86041c57d330e9e284e4f54d2708e2401d02199ff7ab1eb22c`
- 내부 해시: `SYSTEM.DAT=cd3610397d89174112bdc0241cd310e63cd116d7f4b9cbb629f7d0a9fef25f27`, `ANIME.DAT=9b487201baef12e15661f2c956109e1e1ea88fdd392cacc7be8490af276dd2f7`, `BOOT.BIN=f4459b4980b2018343b6323e6cf0ab76f96b96892b6eeebe9526498aaa6519c1`, `EBOOT.BIN=2c515cda59931eb072b4621d435914a37413957c1df2f21741fa41275f2eb128`
- 자동 검증: 관련 11 tests PASS, PPSSPP Headless 8초 게임 루프 PASS

이 빌드는 줄 분리 확인 전용이었다. 두 파일 모두 후속 v2 테스트 ISO 생성 및 검증 후 2026-07-22 삭제했으며, 빌드 해시와 검증 결과만 이력으로 보존한다.

## 결과 화면·작은 푯말 통합 빌드 (2026-07-25)

`build_base_menu_live_preview.py`로 record 82 texture 0의 작은 `튜토리얼` 푯말을 만들고, `build_boot_ui_runtime_patch.py`로 결과 화면 시간·사망 수 문자열과 필요한 폰트를 생성한다. 마지막으로 `integrate_boot_ui_assets_iso.py`가 최신 이미지 ISO의 기존 코드와 이미지는 보존한 채 77개 BOOT UI 고정 슬롯, `font.fnt`, `font.txp`만 병합한다.

최종 ISO는 `work/production/Prinny_ULJS00150_KR_Latest_20260725_ResultFix.iso`, 크기 `500,465,664` bytes, SHA-256 `754c8b2b05cf9838937e07292522e2acc8bdae36befafe65861e08d36d9add7c`다. 통합 보고서는 `work/builds/latest_20260725_result_fix/integration_report.json`이다. EBOOT의 기존 348바이트 패딩과 UI 슬롯 밖 ASM 패치를 유지하며 컨테이너 왕복 검증을 통과했다.

결과 화면 문자열은 `workspace/text/boot_ui_translation.json`에서 관리한다. 시간 형식은 `%02d:%02d:%02d`, 개별 사망 수 슬롯은 `%d마리` 계열이다.

2026-07-26에 기존 추출 범위보다 앞선 `0x0ED96C`의 공용 행동 문구 `□話しかける`를 발견해 `□말 걸기`로 추가했다. 번역 정본은 현재 78개 슬롯이며 정적 고정 길이 감사에 통과했다. 이 변경은 다음 통합 ISO 빌드 때 BOOT와 EBOOT에 함께 반영한다.

## 최신 통합 테스트 ISO 빌드 (2026-07-19)

최신 Demo00 번역, 통합 폰트, 타이틀, 튜토리얼, BOOT UI를 원본 `ULJS00150 1.01` ISO에 순서대로 결합했다. 결과물은 `work/production/Prinny_ULJS00150_KR_Test_20260719_Full.iso`, 크기 `500,465,664` bytes, SHA-256 `1b99c3f88e81e5c261cb673ea65fdd25a5676c92957ac3bb6783f57520db429c`다.

통합 순서는 다음과 같다.

1. `demo00_translation.json`과 BOOT UI 74개 문자열의 합집합 841자를 감사하고 한컴 말랑말랑 Regular 비트맵 폰트를 생성한다.
2. 최신 Demo00와 폰트를 `start.dat`에 고정 크기로 삽입하고 타이틀 그래픽을 적용한다.
3. `start.lzs`를 재압축해 원본 크기 `SYSTEM.DAT`에 삽입한다.
4. 승인된 튜토리얼 후보 `ANIME.DAT` SHA-256 `9b487201baef12e15661f2c956109e1e1ea88fdd392cacc7be8490af276dd2f7`를 고정 extent에 삽입한다.
5. 패치된 평문 ELF를 `BOOT.BIN`에 넣고, PPSSPP가 실제로 읽는 `EBOOT.BIN` 슬롯에는 같은 ELF를 원본 슬롯 크기까지 0 패딩해 삽입한다.

최종 ISO 내부 해시는 `SYSTEM.DAT=74c4ee0ae5000edae7e8fc226997f79fd936be61d2e9fbb0836df39a7c7a6462`, `ANIME.DAT=9b487201baef12e15661f2c956109e1e1ea88fdd392cacc7be8490af276dd2f7`, `BOOT.BIN=f4459b4980b2018343b6323e6cf0ab76f96b96892b6eeebe9526498aaa6519c1`, `EBOOT.BIN=2c515cda59931eb072b4621d435914a37413957c1df2f21741fa41275f2eb128`다. 관련 11개 단위 테스트와 `H:\ppsspp\PPSSPPHeadless.exe` 8초 부팅을 통과했다.

월드 간판, 거점 메뉴와 나머지 이미지 일괄 초안은 아직 PPSSPP replacement texture 검증 단계이므로 이 테스트 ISO에 모두 포함되지는 않는다.

## 베이스 메뉴 record 82 라이브 빌드 (2026-07-19)

`workspace/scripts/build_base_menu_live_preview.py`는 PPSSPP 원본 덤프 `new\091591e09a963304c67a3ca6.png`에서 나무 간판과 투명 목록 슬롯을 한글로 재구성한다. 최신 작은 푯말 문구는 `튜토리얼`이다. 출력은 `work/live/base_menu/091591e09a963304c67a3ca6.png`이며 `--install-dir H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150`을 사용하면 `091591e09a963304c67a3ca6.png`와 팔레트 별칭 `091591e09a96330453b50c70.png`에 함께 설치한다. 최신 SHA-256은 `f5dd9b65bc85483f41e61ceb2212502f8df34f824ab2973d60c95f45ca679eba`다.

## 월드 간판 좌우반전·선택 잔재 제거 라이브 빌드 (2026-07-19)

`workspace/scripts/build_world_sign_live_preview.py`는 원본 일본어의 중성색 본체·외곽선을 검출해 4 텍스처 px 확장한 영역만 목재색으로 복원한다. `마왕성` 22px과 `튜토리얼` 18px은 180도 사전 회전 뒤 좌우반전하며, 중심 좌표는 각각 `(65,25)`, `(164,25)`다. 출력은 `work/live/world_sign/09bba150f04e998665714c1a.png`, 설치 위치는 `H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150\09bba150f04e998665714c1a.png`다. 두 파일 SHA-256은 `4e61ed9d1bf62cb485e556e2a093f548cd604016e7b6ad0e2da1e25b6cfb3edc`로 일치하며 ISO는 생성하지 않는다. PPSSPP를 완전히 종료 후 재실행해 방향, 잔재, `튜토리얼`의 오른쪽 이동을 확인한다.

## 월드 간판 180도 교정 라이브 빌드 (2026-07-19)

`workspace/scripts/build_world_sign_live_preview.py`는 원문 전체 바운드를 목재색으로 복원하고 `마왕성` 22px·`튜토리얼` 18px을 180도 회전해 합성한다. 출력은 `work/live/world_sign/09bba150f04e998665714c1a.png`, 설치 위치는 `H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150\09bba150f04e998665714c1a.png`다. 두 파일 SHA-256은 `173e8d1c16cc64f8273966ab6e5d2a8270197b79c937afec44d70573d7e2c105`로 일치하며 ISO는 생성하지 않는다. PPSSPP를 완전히 종료 후 재실행해 양쪽 간판의 방향, 잔재, 판 내부 여백을 확인한다.

## 1. 현재 상태

현재 통합 테스트 ISO 빌드 경로는 위 절차로 확정했다. 최종 배포 패치 확정 전까지 원본과 `extracted`는 수정하지 않고 모든 결과를 `work`에 생성한다.

```text
SYSTEM.DAT
→ start.lzs 추출
→ start.dat 해제
→ 끝 오프셋형 인덱스 검증
→ 대표 폰트·텍스트 후보의 조사용 추출
→ BaseTalk.dat / MusicShop.dat 무수정 왕복 검증
→ Hancom 글리프 생성 → start.dat → LZS → PoC SYSTEM.DAT
```

결과는 모두 `work`에 생성하며 `original`과 `extracted`는 수정하지 않는다.

## 2. 요구 환경

- Windows PowerShell
- Python 3.10 이상(현재 Python 3.12에서 검증)
- 기본 정적 조사: 외부 Python 패키지 없음
- 선택 런타임 조사: Capstone `5.0.7`, websocket-client `1.9.0`, PPSSPP GUI `1.20.4`, 동봉 Headless `v1.19.3-1588-g1ce9db0250`

모든 명령은 이 게임 프로젝트 루트에서 실행한다.

## 3. NISPACK 검증

```powershell
python .\workspace\scripts\inspect_nispack.py `
  .\extracted\PSP_GAME\USRDIR\SYSTEM.DAT
```

다른 아카이브도 같은 방식으로 검사한다.

```powershell
Get-ChildItem .\extracted\PSP_GAME\USRDIR\*.DAT |
  Where-Object Name -ne 'SOUND.DAT' |
  ForEach-Object {
    python .\workspace\scripts\inspect_nispack.py $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "NISPACK validation failed" }
  }
```

## 4. start.lzs 추출·해제

```powershell
python .\workspace\scripts\inspect_nispack.py `
  .\extracted\PSP_GAME\USRDIR\SYSTEM.DAT `
  --extract start.lzs `
  --output-dir .\work\system

python .\workspace\scripts\decompress_nis_lzs.py `
  .\work\system\start.lzs `
  .\work\system\start.dat
```

정상 기준:

- `start.lzs`: 3,630,771바이트
- `start.dat`: 9,030,752바이트
- 출력 메시지: `extension='dat'`

## 5. start.dat 조사

인덱스 열거:

```powershell
python .\workspace\scripts\inspect_start_dat.py `
  .\work\system\start.dat
```

대표 후보 추출:

```powershell
$names = 'font.fnt', 'font.txp', 'BaseTalk.dat', 'MusicShop.dat', 'PrinnyName.dat'
foreach ($name in $names) {
  python .\workspace\scripts\inspect_start_dat.py `
    .\work\system\start.dat `
    --extract $name `
    --output-dir .\work\system\start_assets
}
```

추출기는 헤더의 첫 데이터 시작점과 각 항목의 끝 오프셋을 사용한다. 경계는 로더 코드와 단위 테스트로 확인했지만 정렬 패딩의 소유권과 세 미확정 필드는 아직 재패킹 전제로 확정하지 않았다.

`BaseTalk.dat` 구조 요약과 무수정 왕복 검증:

```powershell
python .\workspace\scripts\base_talk.py `
  .\work\system\start_assets\BaseTalk.dat

python .\workspace\scripts\base_talk.py `
  .\work\system\start_assets\BaseTalk.dat `
  --roundtrip
```

보호된 원시 슬롯, 안정 ID, 디코딩 결과를 사람이 검토할 JSON으로 출력할 때는 `--json`을 쓴다. 이 출력은 조사 자료이며 번역 입력이나 writer 입력이 아니다.

```powershell
python .\workspace\scripts\base_talk.py `
  .\work\system\start_assets\BaseTalk.dat `
  --json
```

실제 CP932 BGM명 표는 `MusicShop.dat`다.

```powershell
python .\workspace\scripts\music_shop.py `
  .\work\system\start_assets\MusicShop.dat `
  --roundtrip
```

## 6. PPSSPP 런타임 조사

사용자가 지정한 PPSSPP 위치는 `H:\ppsspp`다. 기존 설정을 영구 변경하지 않는다. 조사 시 원격 디버거를 임시 활성화하고 종료 후 원래 값으로 복원한다. 포트는 실행마다 달라질 수 있으므로 PPSSPP 프로세스의 실제 리스닝 포트를 확인한다. 2026-07-17 실행에서는 `26835`였으며, 현재 빌드는 `localhost` WebSocket 핸드셰이크가 닫히므로 PC의 LAN IPv4 주소를 사용했다.

재현용 의존성은 무시되는 `work/pydeps`에 설치한다.

```powershell
python -m pip install --target .\work\pydeps -r .\workspace\config\requirements-analysis.txt
$env:PYTHONPATH = (Resolve-Path .\work\pydeps)
python .\workspace\scripts\ppsspp_basetalk_probe.py `
  --uri ws://<PC-LAN-IP>:15100/debugger `
  --output .\work\probes\basetalk_loader.json
```

스크립트는 VA `0x0888B32C`에 중단점을 걸고 게임을 재시작한 뒤 count 전역 `0x08A54BDC`, 본문 포인터 전역 `0x08A54BE0`, 본문 844바이트를 수집한다. 종료 시 중단점을 제거하고 CPU를 재개한다. PPSSPP 프로세스 실행과 설정 변경은 자동화하지 않는다.

NSF 메시지 명령의 실제 실행 오프셋은 다음 추적기로 수집한다. PPSSPP가 원본 ISO를 실행 중이고 원격 디버거가 활성화된 상태에서 사용한다.

```powershell
$env:PYTHONPATH = ".\work\pydeps;.\workspace\scripts"
python .\workspace\scripts\ppsspp_nsf_trace.py `
  .\work\script\demo.nsf `
  .\work\system\start_assets\Demo00.dat `
  --uri ws://<PC-LAN-IP>:15100/debugger `
  --output .\work\probes\nsf_runtime_trace.json `
  --duration 300 `
  --max-events 500
```

추적기는 `42 01/02/03` 핸들러 `0x08879060`, `0x08879100`, `0x08879238`에 중단점을 건다. 적중 시 `a1`의 VM 저장 PC와 `a3`의 런타임 코드 기준 주소로 논리 명령 오프셋·채널·메시지 ID를 복원하고, 종료 시 중단점을 제거해 CPU를 재개한다. `--auto-advance`는 타이틀 메뉴용 보조 입력일 뿐 스토리 장면 진입을 보장하지 않는다. 대화 장면까지 직접 진행한 뒤 추적하는 것을 기준 절차로 삼는다.

Demo00 ID `0x00E6`과 `enemy.nsf` 논리 오프셋 `0x1851C`의 결합 여부는 전용 필터로 확인한다. 원본 게임을 대상 적 장면까지 진행한 뒤 `--reset` 없이 실행하는 것이 본 판정 절차다.

```powershell
$env:PYTHONPATH = ".\work\pydeps;.\workspace\scripts"
python .\workspace\scripts\ppsspp_demo00_target_trace.py `
  --uri ws://<PC-LAN-IP>:<실제-리스닝-포트>/debugger `
  --output .\work\analysis\ppsspp_demo00_00e6_trace.json `
  --target-id 0x00E6 `
  --expected-offset 0x1851C `
  --duration 300 `
  --stop-on-exact-hit
```

`POSITIVE_EXACT`만 해당 정적 후보의 실행 증거다. `POSITIVE_ID_OTHER_OFFSET`은 같은 ID의 다른 호출이며 별도 문맥으로 남긴다. `INCONCLUSIVE_NO_HIT`은 제한 시간에 관찰하지 못했다는 뜻이고 미사용 판정으로 승격하지 않는다. 부팅·메뉴 자동 진행 기준선은 60초 동안 핸들러 적중 0건이었으며 결과는 `work/analysis/ppsspp_demo00_00e6_trace.json`에 있다.

적 등장 장면의 재설정 없는 수동 플레이 300초 결과는 `work/analysis/ppsspp_demo00_00e6_trace_manual.json`이다. 두 런타임 미적중 뒤에는 아래 정적 감사를 수행한다.

```powershell
python .\workspace\scripts\inspect_start_dat.py `
  .\work\system\start.dat `
  --extract Character00.dat `
  --output-dir .\work\analysis\enemy_key_assets

python .\workspace\scripts\audit_enemy_orphan_key.py `
  .\work\script\enemy.nsf `
  .\work\analysis\enemy_key_assets\Character00.dat `
  .\work\system\start.dat `
  .\extracted\PSP_GAME\SYSDIR\BOOT.BIN `
  .\work\analysis\enemy_orphan_key.json
```

감사는 `Character00.dat`의 `u32 count=390 + 390×68바이트 레코드 + 4바이트 꼬리`, 레코드 `+0x00` ID·`+0x04` 이름·`+0x3C` NSF 루트 키를 엄격 검증한다. ELF 주소 변환과 BOOT의 기본 슬롯 0·DLC 슬롯 1 적재, 정확 ID 조회, 루트 키 무보정 소비까지 고정 명령어로 확인한다. 성공 상태는 `BASE_ISO_UNREACHABLE_DLC_SEPARATE`다.

단위 테스트:

```powershell
python -m unittest discover .\workspace\tests -v
```

BaseTalk 키와 `demo.nsf` 연결 및 `Demo00.dat` 메시지 표는 다음 명령으로 재현한다.

```powershell
python .\workspace\scripts\nsf_links.py `
  .\work\system\start_assets\BaseTalk.dat `
  .\work\script\demo.nsf

python .\workspace\scripts\demo00.py `
  .\work\system\start_assets\Demo00.dat --roundtrip

python .\workspace\scripts\demo00_artifact.py export `
  .\work\system\start_assets\Demo00.dat `
  .\workspace\text\demo00_translation.json `
  --seed-poc .\workspace\text\demo00_poc_07d0.json

python .\workspace\scripts\demo00_artifact.py verify `
  .\work\system\start_assets\Demo00.dat `
  .\workspace\text\demo00_translation.json `
  .\work\analysis\demo00_translation_report.json `
  --roundtrip-output .\work\roundtrip\Demo00.dat

# export는 최초 생성 또는 승인된 재추출 전용이다. 기존 파일은 --force 없이 덮어쓰지 않는다.
# 첫 배치는 이미 병합됐으며 같은 배치의 재병합은 기준선 충돌로 거부된다.
python .\workspace\scripts\demo00_batches.py create `
  .\workspace\text\demo00_translation.json `
  .\workspace\text\batches\demo00_batch_001_difficulty.json `
  demo00_batch_001_difficulty demo00/005A demo00/005B `
  --scene "난이도 선택 화면의 두 설명 패널"

python .\workspace\scripts\demo00_batches.py merge `
  .\workspace\text\demo00_translation.json `
  .\workspace\text\batches\demo00_batch_001_difficulty.json `
  .\work\analysis\demo00_batch_001_report.json

# 두 번째 장면 배치는 demo.nsf의 연속 실행 구간을 기준으로 생성한다.
python .\workspace\scripts\demo00_batches.py create `
  .\workspace\text\demo00_translation.json `
  .\workspace\text\batches\demo00_batch_002_intro_scarf.json `
  demo00_batch_002_intro_scarf `
  demo00/0BB8 demo00/0BBA demo00/0BBC demo00/0BBE demo00/0BC0 demo00/0BC2 `
  --scene "도입부: 에트나가 프리니 부대에 머플러와 궁극의 디저트 임무를 설명하는 연속 대화" `
  --evidence "demo.nsf logical offsets 0x00000A66..0x00000C02의 연속 42 01 호출"

python .\workspace\scripts\demo00_batches.py merge `
  .\workspace\text\demo00_translation.json `
  .\workspace\text\batches\demo00_batch_002_intro_scarf.json `
  .\work\analysis\demo00_batch_002_report.json

# 세 번째 장면은 같은 블록 안에서 실행 시작점이 전부 증명된 도주 경고 대화다.
python .\workspace\scripts\demo00_batches.py create `
  .\workspace\text\demo00_translation.json `
  .\workspace\text\batches\demo00_batch_003_escape_warning.json `
  demo00_batch_003_escape_warning `
  demo00/0BEA demo00/0BEC demo00/0BEE demo00/0BF0 demo00/0BF2 demo00/0BF4 demo00/0BF6 `
  --scene "도입부 후반: 프리니의 포기·도주 시도와 에트나의 디저트 회수 명령" `
  --evidence "demo.nsf block 0x00000C37..0x00000F6F 내 logical offsets 0x00000D40..0x00000F3B의 연속 42 01 호출" `
  --evidence "BOOT dispatcher block-local stepping: target 7 offsets all proven, block completed 1/1"

python .\workspace\scripts\demo00_batches.py merge `
  .\workspace\text\demo00_translation.json `
  .\workspace\text\batches\demo00_batch_003_escape_warning.json `
  .\work\analysis\demo00_batch_003_report.json

# 네 번째 장면은 다음 블록에서 실행 시작점 4건이 전부 증명된 멜론맛 간식 대화다.
python .\workspace\scripts\demo00_batches.py create `
  .\workspace\text\demo00_translation.json `
  .\workspace\text\batches\demo00_batch_004_melon_snack.json `
  demo00_batch_004_melon_snack `
  demo00/0C1C demo00/0C1E demo00/0C20 demo00/0C22 `
  --scene "도입부 멜론맛 간식: 에트나의 추억과 프리니의 디저트 확보 보고 오해" `
  --evidence "demo.nsf block 0x00000F70..0x000011FC 내 logical offsets 0x000010C2/0x0000113B/0x00001168/0x000011C8의 연속 42 01 호출" `
  --evidence "BOOT dispatcher block-local stepping: target 4 offsets all proven, block completed 1/1"

python .\workspace\scripts\demo00_batches.py merge `
  .\workspace\text\demo00_translation.json `
  .\workspace\text\batches\demo00_batch_004_melon_snack.json `
  .\work\analysis\demo00_batch_004_report.json

# 다섯 번째 장면부터는 초벌을 needs_review/needs_human_review로 누적한다.
python .\workspace\scripts\demo00_batches.py create `
  .\workspace\text\demo00_translation.json `
  .\workspace\text\batches\demo00_batch_005_missing_prinnies.json `
  demo00_batch_005_missing_prinnies `
  demo00/0C4E demo00/0C50 demo00/0C52 demo00/0C54 demo00/0C56 demo00/0C58 `
  --scene "도입부 성내 프리니 감소: 다른 부대의 지고의 마파두부 수색" `
  --evidence "demo.nsf logical offsets 0x12F8/0x1325/0x1381/0x13AE/0x13F1/0x1434" `
  --evidence "BOOT dispatcher stepping: target 6/6 proven, selected blocks 2/2 completed"

python .\workspace\scripts\demo00_batches.py merge `
  .\workspace\text\demo00_translation.json `
  .\workspace\text\batches\demo00_batch_005_missing_prinnies.json `
  .\work\analysis\demo00_batch_005_report.json

# 전체 초벌 진행 중에는 두 검토 상태를 장면 문맥과 함께 파생 큐로 모은다.
python .\workspace\scripts\demo00_review_queue.py `
  .\workspace\text\demo00_translation.json `
  .\workspace\text\batches `
  .\work\analysis\demo00_review_queue.json

python .\workspace\scripts\audit_demo00_population.py `
  .\work\system\start_assets\Demo00.dat `
  .\extracted\PSP_GAME\SYSDIR\BOOT.BIN `
  .\work\script `
  .\work\analysis\demo00_population.json `
  --orphan-evidence .\work\analysis\enemy_orphan_key.json

python .\workspace\scripts\demo00_controls.py `
  .\work\system\start_assets\Demo00.dat `
  .\work\system\start.dat `
  --output .\work\analysis\demo00_controls.json

python .\workspace\scripts\inspect_start_dat.py `
  .\work\system\start.dat --extract jis2ucs.bin `
  --output-dir .\work\system\start_assets

python .\workspace\scripts\inspect_start_dat.py `
  .\work\system\start.dat --extract ucs2jis.bin `
  --output-dir .\work\system\start_assets

python .\workspace\scripts\font_assets.py `
  .\extracted\PSP_GAME\SYSDIR\BOOT.BIN `
  .\work\system\start_assets\font.fnt `
  .\work\system\start_assets\font.txp `
  .\work\system\start_assets\jis2ucs.bin `
  .\work\system\start_assets\ucs2jis.bin `
  --output .\work\analysis\font_assets.json

python .\workspace\scripts\render_font_glyphs.py `
  .\work\system\start_assets\font.fnt `
  .\work\system\start_assets\font.txp `
  .\work\analysis\font_glyphs.png

python .\workspace\scripts\build_font_poc.py `
  .\workspace\config\font_profile.json `
  ..\..\Font\HancomMalangMalang-Regular.ttf `
  .\work\system\start_assets\font.fnt `
  .\work\system\start_assets\font.txp `
  .\work\poc\font_visibility

python .\workspace\scripts\build_start_poc.py `
  .\workspace\config\font_profile.json `
  .\work\system\start.dat `
  .\work\poc\font_visibility\font.txp `
  .\work\poc\font_visibility

python .\workspace\scripts\compress_nis_lzs.py `
  .\work\poc\font_visibility\start.dat `
  .\work\poc\font_visibility\start.lzs `
  --report .\work\poc\font_visibility\lzs_report.json

python .\workspace\scripts\build_system_poc.py `
  .\workspace\config\font_profile.json `
  .\extracted\PSP_GAME\USRDIR\SYSTEM.DAT `
  .\work\poc\font_visibility\start.lzs `
  .\work\poc\font_visibility

python .\workspace\scripts\build_iso_poc.py `
  .\workspace\config\font_profile.json `
  ".\original\Prinny - Ore ga Shujinkou de Iinsuka (Japan, Korea).iso" `
  .\work\poc\font_visibility\SYSTEM.DAT `
  ".\build\poc\Prinny - Ore ga Shujinkou de Iinsuka (Korean Font PoC).iso"

python .\workspace\scripts\ppsspp_boot_probe.py `
  H:\ppsspp\PPSSPPHeadless.exe `
  ".\build\poc\Prinny - Ore ga Shujinkou de Iinsuka (Korean Font PoC).iso" `
  .\work\probes\poc_iso_boot.json `
  --duration 12

python .\workspace\scripts\audit_cp932_usage.py `
  .\work\system\start_assets `
  --output .\work\analysis\cp932_usage.json

python .\workspace\scripts\audit_cp932_allocation.py `
  .\workspace\config\cp932_allocation_profile.json `
  .\work\system\start.dat `
  .\extracted\PSP_GAME\SYSDIR\BOOT.BIN `
  .\work\system\start_assets `
  --output .\work\analysis\cp932_allocation.json

python .\workspace\scripts\build_font_multi_poc.py `
  .\workspace\config\font_multi_profile.json `
  ..\..\Font\HancomMalangMalang-Regular.ttf `
  .\work\system\start_assets\font.fnt `
  .\work\system\start_assets\font.txp `
  .\work\poc\font_multi_visibility

python .\workspace\scripts\build_start_poc.py `
  .\workspace\config\font_multi_profile.json `
  .\work\system\start.dat `
  .\work\poc\font_multi_visibility\font.txp `
  .\work\poc\font_multi_visibility

python .\workspace\scripts\compress_nis_lzs.py `
  .\work\poc\font_multi_visibility\start.dat `
  .\work\poc\font_multi_visibility\start.lzs `
  --report .\work\poc\font_multi_visibility\lzs_report.json

python .\workspace\scripts\build_system_poc.py `
  .\workspace\config\font_multi_profile.json `
  .\extracted\PSP_GAME\USRDIR\SYSTEM.DAT `
  .\work\poc\font_multi_visibility\start.lzs `
  .\work\poc\font_multi_visibility

python .\workspace\scripts\build_iso_poc.py `
  .\workspace\config\font_multi_profile.json `
  ".\original\Prinny - Ore ga Shujinkou de Iinsuka (Japan, Korea).iso" `
  .\work\poc\font_multi_visibility\SYSTEM.DAT `
  ".\build\poc\Prinny - Ore ga Shujinkou de Iinsuka (Korean Multi Font PoC).iso"

python .\workspace\scripts\ppsspp_boot_probe.py `
  H:\ppsspp\PPSSPPHeadless.exe `
  ".\build\poc\Prinny - Ore ga Shujinkou de Iinsuka (Korean Multi Font PoC).iso" `
  .\work\probes\multi_poc_iso_boot.json `
  --duration 12

python .\workspace\scripts\nsf_messages.py `
  .\work\script\demo.nsf `
  .\work\system\start_assets\Demo00.dat

python .\workspace\scripts\nsf_reachability.py `
  .\extracted\PSP_GAME\SYSDIR\BOOT.BIN `
  .\work\script\demo.nsf `
  .\work\system\start_assets\Demo00.dat
```

현재 성공 기준은 BaseTalk 고유 키 72개 전수 해석, NSF 키 531개·블록 939개·코드 영역 `0x2E10 + 0x30D70` 검증, Demo00 207,520바이트 완전 동일 왕복이다. 기본 ISO 번역 대상 1,523건은 모두 보호 병합과 사용자 승인을 마쳐 `complete`이며 검토 큐는 0건이다. `untranslated=49`는 도달 불가능한 `国` 레이아웃 템플릿이고 용어·문체 결정 122건은 모두 승인됐다. 승인 코퍼스의 고유 한글은 830자다. 최종 검토의 사용자 수정 16건은 최대 `31/34`바이트를 통과했다. 다음 빌드 단계는 이 승인 SSOT를 기준으로 전체 원문 왕복, 글리프 수요·생산 코드 매핑, 전량 writer와 PPSSPP 회귀를 수행한다.

폰트 검사 성공 기준은 `font.fnt` 11,615개 맵 값이 `font.txp` 글리프 ID `0..2347`을 정확히 포괄하고, TXP 픽셀 영역이 `2348×140`바이트이며, 두 변환표의 canonical UCS 왕복 7,766건이 일치하는 것이다. `font_glyphs.png`는 정적 디코드 확인 자료이며 PPSSPP 가시성 통과 증거가 아니다.

폰트 PoC 빌드는 TTF SHA-256, modern Hangul 11,172자 cmap 수록, 13px·가로 1.4배 설정의 20×14 셀 경계를 확인하고, `font.txp`의 `0xCB34..0xCBBF` 밖 변경이 있으면 실패해야 한다. 현재 전 범위 최대 경계는 17×14이고 초과는 0개다. 출력 `font.fnt`는 원본과 동일하고 `font.txp`는 원본과 같은 328,800바이트여야 한다. 이 명령은 아직 `start.dat`, `SYSTEM.DAT`, ISO를 수정하지 않는다.

`build_start_poc.py`는 고정된 원본 `start.dat` SHA-256과 `font.txp` 엔트리 `0x5339E0..0x583E3F`를 확인한 뒤 동일 크기 PoC 자산을 주입한다. 출력은 `work/poc/font_visibility/start.dat`, 보고서는 `start_report.json`이며 전체 9,030,752바이트를 유지한다. 실제 변경 79바이트가 모두 `font.txp` 하위 글리프 diff와 일치하지 않으면 실패한다.

`compress_nis_lzs.py`는 출력의 자기 왕복을 강제한다. 원본 `work/system/start.dat`에 `--reference work/system/start.lzs`를 주면 바이트 동일 여부도 `original_report.json`에 기록할 수 있으며 현재 결과는 동일하다. PoC 출력은 3,630,811바이트, SHA-256 `85431dca1d66ecca728fdc41522fc6b7b397201ccd27b657dcb2cb9dcb36fd2a`다.

`build_system_poc.py`는 원본 `SYSTEM.DAT`, 원본/PoC `start.lzs`, 복원될 PoC `start.dat` 해시를 모두 고정한다. 333바이트의 원래 0 패딩 중 40바이트를 사용하고 293바이트를 남기므로 다른 엔트리 오프셋과 파일 전체 크기는 변하지 않는다. 결과는 `work/poc/font_visibility/SYSTEM.DAT`, 보고서는 `system_report.json`이며 SHA-256은 `41c9fbb6049e74fb28d1f8e429146a053bfd2e5ffa86f8b17a3b52c000cf9892`다. 이 단계는 원본 extracted 트리를 수정하지 않는다.

`build_iso_poc.py`는 ISO9660 디렉터리를 직접 순회해 `/PSP_GAME/USRDIR/SYSTEM.DAT;1`의 LBA 218,144, 파일 오프셋 `0x1AA10000`, 크기 4,127,307바이트를 확인한다. 대체 파일이 같은 크기일 때만 원본 ISO를 별도 출력으로 복사해 해당 extent를 치환한다. 출력 ISO는 원본과 같은 500,465,664바이트, SHA-256 `02883fd3c6fdfaac53be78a94975e8bfc3ee16ce689215146e5627b5b80b7a68`이며 변경 1,690,574바이트가 모두 `0x1AA10000..0x1ADFFA4A` 안에 있다. 보고서는 출력 ISO 옆 `.iso.report.json`이다.

`ppsspp_boot_probe.py`는 `H:\ppsspp\PPSSPPHeadless.exe`를 소프트웨어 렌더러로 12초 실행하고 전체 로그를 메모리에 쌓지 않은 채 버전·게임 ID·EBOOT·모듈·`SYSTEM.DAT` 열기·계획된 timeout 증거만 보존한다. 현재 `v1.19.3-1588-g1ce9db0250` Headless에서 반환 코드 0, 의미 있는 오류 0건으로 통과했다. `lang/.ini` 검색 1건은 Headless의 알려진 환경 경고로 분리한다. 이 자동 게이트 자체는 화면 가시성을 증명하지 않지만, 별도 사용자 실기 검사에서 난이도 선택과 스테이지 결과 화면의 `プ`가 `가`로 표시되어 단일 글리프 가시성도 통과했다.

`audit_cp932_usage.py`는 경계가 확정된 Demo00·MusicShop·PrinnyName만 감사한다. 결과는 총 6,396슬롯, 비어 있지 않은 4,430슬롯, 서로 다른 CP932 코드 1,171개다. 렌더 가능한 비공백 코드 2,347개 중 1,176개가 이 모집단에서 미사용이지만, 다른 UI·실행 파일·DLC까지 포함한 안전 슬롯 증거는 아니다.

`audit_cp932_allocation.py`는 고정 해시의 `start.dat`, `BOOT.BIN`, `font.fnt`를 입력으로 사용한다. 확정 3자산은 엄격 파서 증거를 유지하고, 12개 데이터 표와 실행 파일은 강한 전각 일본어 비율을 만족하는 CP932 문자열을 휴리스틱 예약 후보로만 집계한다. `BOOT.BIN`은 NUL 경계를 요구하고 일본어 UTF-8 리터럴을 CP932로 오인한 후보를 제외한다. 확정 1,171코드 외 374코드가 추가 예약됐고 ASCII 95코드는 런타임 생성 UI 보호 정책으로 전부 예약했다. 엔진 코드 후보 11,375개 중 빈 매핑은 9,028개이며, 기존 글리프 중 보수적 회수 후보는 726개다. 따라서 파일 크기를 늘리지 않는 새 한글 글리프 수의 현재 후보 상한은 `min(9,028, 726)=726`이지만 보고서 상태는 `PARTIAL`이고 생산 매핑을 승인하지 않는다.

`font_multi_profile.json`과 `build_font_multi_poc.py`는 `プリニー`를 화면 표식으로 사용해 `プ/リ/ニ/ー` 네 셀을 `가/각/뾰/힣`로 바꾼다. 선언한 560바이트 안에서 실제 305바이트만 달라지고 `font.txp` 크기는 유지된다. 다중 PoC `start.lzs`는 3,630,940바이트이며 원본보다 169바이트 커서 기존 패딩 333바이트 안에 들어간다. 출력 `SYSTEM.DAT` SHA-256은 `76d3131f0c635b92903f94d50f05eed550ff9706e013fef11c7af8be9d8b0614`다. 다중 PoC ISO SHA-256은 `22168bd80c6c7584426dd75a66ebcee05a5642f2bf2ebf83e17e32a64966e628`이며 Headless 부팅도 통과했다. 사용자 실기에서 난이도 UI와 Demo00 `0x07D0`의 명패·본문 표시까지 통과했다.

2026-07-17 자동 진행 런타임 기준선은 90초·44회 입력에서 메시지 핸들러 적중 0건이다. 이는 해당 실행 구간에 대한 관찰값이며 미적중 오프셋의 미사용 증거가 아니다. 결과는 `work/probes/nsf_runtime_trace.json`에 보존한다.

두 메시지 표의 소유자와 기본 ISO/DLC 경계는 다음 명령으로 재현한다.

```powershell
python .\workspace\scripts\message_table_owners.py `
  .\extracted\PSP_GAME\SYSDIR\BOOT.BIN `
  .\work\script\demo.nsf `
  .\work\system\start_assets\Demo00.dat `
  --output .\work\analysis\message_table_owners.json
```

성공 기준은 슬롯 0=`Demo00.dat`, 슬롯 1=`DDEM`, 슬롯 1 컨테이너=`ms0:/PSP/GAME/%s/DL%04d.EDAT`, DDEM 후보 52건, 기타 비정상 패턴 2건이다. DLC EDAT는 원본 ISO와 별도 입력이므로 기본 ISO 빌드가 이를 생성하거나 수정하지 않는다.

### Demo00 `0x07D0` 단일 번역 E2E 빌드

프로젝트 루트에서 다음 순서로 실행한다. 번역 원본은 `workspace/text/demo00_poc_07d0.json`, 고정 해시·글리프·엔트리 경계는 `workspace/config/dialog_e2e_profile.json`이 소유한다.

```powershell
python .\workspace\scripts\build_font_multi_poc.py `
  .\workspace\config\dialog_e2e_profile.json `
  ..\..\Font\HancomMalangMalang-Regular.ttf `
  .\work\system\start_assets\font.fnt `
  .\work\system\start_assets\font.txp `
  .\work\poc\dialog_e2e_07d0

python .\workspace\scripts\build_demo00_poc.py `
  .\workspace\config\dialog_e2e_profile.json `
  .\workspace\text\demo00_poc_07d0.json `
  .\work\system\start_assets\Demo00.dat `
  .\work\poc\dialog_e2e_07d0

python .\workspace\scripts\build_start_dialog_poc.py `
  .\workspace\config\dialog_e2e_profile.json `
  .\work\system\start.dat `
  .\work\poc\dialog_e2e_07d0\font.txp `
  .\work\poc\dialog_e2e_07d0\Demo00.dat `
  .\work\poc\dialog_e2e_07d0

python .\workspace\scripts\compress_nis_lzs.py `
  .\work\poc\dialog_e2e_07d0\start.dat `
  .\work\poc\dialog_e2e_07d0\start.lzs `
  --report .\work\poc\dialog_e2e_07d0\lzs_report.json

python .\workspace\scripts\build_system_poc.py `
  .\workspace\config\dialog_e2e_profile.json `
  .\extracted\PSP_GAME\USRDIR\SYSTEM.DAT `
  .\work\poc\dialog_e2e_07d0\start.lzs `
  .\work\poc\dialog_e2e_07d0

python .\workspace\scripts\build_iso_poc.py `
  .\workspace\config\dialog_e2e_profile.json `
  ".\original\Prinny - Ore ga Shujinkou de Iinsuka (Japan, Korea).iso" `
  .\work\poc\dialog_e2e_07d0\SYSTEM.DAT `
  ".\build\poc\Prinny - Ore ga Shujinkou de Iinsuka (Korean Dialog E2E PoC).iso"

python .\workspace\scripts\ppsspp_boot_probe.py `
  H:\ppsspp\PPSSPPHeadless.exe `
  ".\build\poc\Prinny - Ore ga Shujinkou de Iinsuka (Korean Dialog E2E PoC).iso" `
  .\work\probes\dialog_e2e_iso_boot.json `
  --duration 12
```

현재 결과는 `프리니` / `우와、지각했다！！`를 각각 고정 슬롯 안에 넣었고, 레코드 메타데이터와 나머지 1,571개 레코드를 보존했다. `Demo00.dat` 실제 변경은 19바이트, 결합 `start.dat` 실제 변경은 718바이트다. LZS는 원본보다 262바이트 증가해 333바이트 패딩 중 71바이트를 남겼고, 동일 크기 `SYSTEM.DAT`와 ISO를 생성했다. ISO SHA-256은 `f2f9d94037f40cd78590b8ed13898e5b92ddc6e923815a1a9eaf2e4d60167cb6`이며 12초 Headless 부팅은 의미 있는 오류 0건으로 통과했다. 2026-07-17 사용자 화면 확인에서도 명패·본문 표시와 대화 진행이 정상으로 판정됐다.

## 7. 향후 단일 빌드가 가져야 할 경계

최종적으로는 아래 순서를 하나의 진입점에서 수행해야 한다.

```text
baseline_manifest.json 검증
→ 원본 ISO 또는 깨끗한 extracted 복제
→ NISPACK/LZS/start.dat 무변경 왕복 검사
→ 승인된 텍스트·폰트 입력 검증
→ Expected Write 계획 계산
→ 자산 재구성·컨테이너 재패킹
→ ISO 생성
→ 전체 diff·해시·부팅 검사
→ xdelta와 배포 문서 생성
```

다음 게이트가 통과하기 전에는 이 경로를 ‘빌드 완료’로 표시하지 않는다.

- NISPACK 미확정 필드 보존은 PoC 고정 extent에서 통과; 일반 가변 크기 재패킹과 게임 소비 호환성
- LZS 압축 결과의 해제 동일성·원본 바이트 동일성, 단일·다중 PoC 화면, 단일 번역 레코드 재삽입·ISO·Headless·실제 대화 화면은 통과; 생산용 코드 매핑과 전량 조판
- start.dat 미확정 필드·정렬·마지막 0 끝점 보존
- 텍스트 원문 코드·제어 토큰·참조의 가역성
- 폰트 코드 매핑과 글리프 커버리지
- 동일 크기 ISO extent 치환과 PPSSPP Headless 부팅은 통과; 일반 재배치·실기 부팅

## 8. 패치 배포 계획

최종 ISO는 `build`에만 생성하고 배포하지 않는다. `dist`에는 지원 원본 해시를 검사하는 xdelta 패치, 패치 SHA-256, 적용·제거 설명서만 둔다. xdelta 도구는 루트 `Tools/xdelta3-3.2.0-windows-x86_64`를 후보로 사용하되 버전과 라이선스 확인을 빌드 전제로 기록한다.

## 9. 생산용 Demo00 고정 크기 빌드

아래 경로는 승인된 1,523건과 한글 830자를 소비한다. 먼저 회수 감사 보고서 해시와 원본 TTF·자산 해시를 검증한다.

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH='workspace/scripts'

python .\workspace\scripts\audit_demo00_reclaim.py `
  .\workspace\config\cp932_allocation_profile.json `
  .\workspace\config\demo00_production_profile.json `
  .\workspace\text\demo00_translation.json `
  .\work\system\start.dat `
  .\extracted\PSP_GAME\SYSDIR\BOOT.BIN `
  .\work\system\start_assets `
  --output .\work\analysis\demo00_fixed_font_reclaim.json

python .\workspace\scripts\build_demo00_production.py `
  .\workspace\config\demo00_production_profile.json `
  .\workspace\text\demo00_translation.json `
  .\work\analysis\demo00_fixed_font_reclaim.json `
  "..\..\Font\HancomMalangMalang-Regular.ttf" `
  .\work\system\start_assets\font.fnt `
  .\work\system\start_assets\font.txp `
  .\work\system\start_assets\Demo00.dat `
  .\work\production\demo00

python .\workspace\scripts\build_start_production.py `
  .\workspace\config\demo00_production_profile.json `
  .\work\system\start.dat .\work\production\demo00 .\work\production\start_fixed

python .\workspace\scripts\compress_nis_lzs.py `
  .\work\production\start_fixed\start.dat `
  .\work\production\start_fixed\start.lzs `
  --report .\work\production\start_fixed\lzs_report.json

python .\workspace\scripts\build_system_production.py `
  .\workspace\config\demo00_production_profile.json `
  .\extracted\PSP_GAME\USRDIR\SYSTEM.DAT `
  .\work\production\start_fixed\start.lzs `
  .\work\production\start_fixed\start.dat `
  .\work\production\system_fixed

python .\workspace\scripts\build_iso_production.py `
  .\workspace\config\demo00_production_profile.json `
  ".\original\Prinny - Ore ga Shujinkou de Iinsuka (Japan, Korea).iso" `
  .\work\production\system_fixed\SYSTEM.DAT `
  .\work\production\Prinny_ULJS00150_KR_Demo00_fixed.iso

python .\workspace\scripts\ppsspp_boot_probe.py `
  H:\ppsspp\PPSSPPHeadless.exe `
  .\work\production\Prinny_ULJS00150_KR_Demo00_fixed.iso `
  .\work\probes\demo00_production_fixed_iso_boot.json --duration 5

python -m unittest discover -s .\workspace\tests
```

기대값은 `start.dat` 9,030,752바이트, ISO 500,465,664바이트, ISO SHA-256 `cd983265…de1c3`, 자동 테스트 73건 PASS다. Headless PASS는 실제 대화 조판을 대신하지 않는다.

## 10. 타이틀 그래픽 PoC v6 빌드

생산 Demo00 `start.dat`를 기준으로 record 78 texture 0만 고정 크기로 바꾼다. `프/리/니/빈 슬롯`에 공통 15도, 확대된 `니`, 제목·부제 반투명 외곽선과 확장 clear mask를 적용한다.

```powershell
python .\workspace\scripts\build_title_graphics_poc.py `
  .\workspace\config\title_graphics_poc.json `
  .\work\production\start_fixed\start.dat `
  "..\..\Font\HancomMalangMalang-Regular.ttf" `
  .\work\poc\title_graphics_v6 `
  --bold-font "..\..\Font\HancomMalangMalang-Bold.ttf"

python .\workspace\scripts\compress_nis_lzs.py `
  .\work\poc\title_graphics_v6\start.dat `
  .\work\poc\title_graphics_v6\start.lzs `
  --report .\work\poc\title_graphics_v6\start_lzs_report.json

python .\workspace\scripts\build_system_production.py `
  .\workspace\config\demo00_production_profile.json `
  .\extracted\PSP_GAME\USRDIR\SYSTEM.DAT `
  .\work\poc\title_graphics_v6\start.lzs `
  .\work\poc\title_graphics_v6\start.dat `
  .\work\poc\title_graphics_v6\system

python .\workspace\scripts\build_iso_production.py `
  .\workspace\config\demo00_production_profile.json `
  ".\original\Prinny - Ore ga Shujinkou de Iinsuka (Japan, Korea).iso" `
  .\work\poc\title_graphics_v6\system\SYSTEM.DAT `
  .\work\production\Prinny_ULJS00150_KR_Demo00_TitlePoc_v6.iso `
  --replacement-sha256 6d51632d6247f3d95a4a52d578f90cc10ff3aca43cedeb5f9c411df430840b9a

python .\workspace\scripts\ppsspp_boot_probe.py `
  H:\ppsspp\PPSSPPHeadless.exe `
  .\work\production\Prinny_ULJS00150_KR_Demo00_TitlePoc_v6.iso `
  .\work\poc\title_graphics_v6\ppsspp_boot_report.json --duration 5
```

기대값은 다음과 같다.

- `start.dat`: 9,030,752바이트, SHA-256 `009d006a…816c`
- `start.lzs`: 3,598,215바이트, SHA-256 `d6185eb9…47ff`
- `SYSTEM.DAT`: 4,127,307바이트, SHA-256 `6d51632d…0b9a`
- ISO: 500,465,664바이트, SHA-256 `d92e700c…c6c6`
- 정적 미리보기: `work/poc/title_graphics_v6/title_texture_kr.png`
- 자동 검증: 83 tests와 PPSSPP Headless 5초 PASS

v1~v4는 팔레트·굵기·분할 UV·슬롯 변형·이진화·원문 잔재 결함으로 폐기했다. v5는 잔재 제거에 성공했지만 최종 각도와 `니` 크기, 제목·부제 가장자리 기준으로 폐기했다. v6의 실제 화면과 선택 상태 승인은 별도다.

## 11. 타이틀 PPSSPP 실시간 보정

크기·각도·잘림을 조정할 때는 LZS·SYSTEM.DAT·ISO를 반복 생성하지 않는다. PPSSPP의 `ReplaceTextures=True`를 사용해 현재 v6 텍스처 해시 `c99d0dc5`의 여덟 팔레트 상태를 교체한다. 아래 캘리브레이션 명령은 세 글자 슬롯에 동일한 24×24 상자와 십자선을 넣으므로 실제 화면의 슬롯별 확대율·회전·클리핑을 직접 측정할 수 있다.

```powershell
python .\workspace\scripts\build_title_live_preview.py `
  .\workspace\config\title_graphics_poc.json `
  H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150\new `
  H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150 `
  "..\..\Font\HancomMalangMalang-Regular.ttf" `
  "..\..\Font\HancomMalangMalang-Bold.ttf" `
  --texture-suffix c99d0dc5 --calibration
```

`--calibration`을 빼면 현재 config의 글꼴·크기·각도·`offset_x/offset_y`를 RGBA 교체 텍스처에 즉시 렌더링한다. 같은 파일명의 교체 텍스처는 그래픽 재시작만으로 갱신되지 않을 수 있으므로 PPSSPP를 완전히 재시작한다. ISO 재빌드는 필요 없다. 화면 보정이 확정된 마지막 config만 고정 인덱스 텍스처로 생성해 생산 ISO를 한 번 빌드한다. 교체를 해제하려면 `H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150` 루트의 `*c99d0dc5.png` 여덟 개를 제거하고 `new` 덤프는 보존한다.

### v7 글자별 화면 역보정

동일한 24×24 보정 도형과 실제 타이틀 캡처로 각 글자 슬롯의 화면 위치 차이를 계측한다. 현재 기준 후보는 Bold 48px, 28×28 정규화 상자를 공통으로 사용하며 `프/리/니`의 원본 회전각은 `18°/21°/21°`다. 세 글자의 외접 중심이 아니라 `프`의 `ㅍ` 최상단과 `리/니`의 오른쪽 모음 `ㅣ` 최상단을 연결 성분에서 직접 찾아 텍스처 Y 좌표 `181/161/159`에 고정한다. 사용자 확인으로 현재 `프/리` 상태를 유지하고 `니`만 추가로 1 텍스처 px 위로 이동했다. 검수는 사용자가 PPSSPP를 실행해 캡처하고 작업자는 교체 텍스처만 갱신하는 방식으로 진행한다.

## 12. 타이틀 v7 최종 생산 빌드

2026-07-19 사용자 승인값을 `work/production/title_graphics_v7_final`에 고정하고 생산 ISO를 생성했다.

- `start.dat`: 9,030,752바이트, SHA-256 `1ada6dc07428b03746841c7ae138aadd5f59c0a153ea01c1d62e61ef8ee3312a`
- `start.lzs`: 3,598,104바이트, SHA-256 `72bf09cc3073adb7ea16d3dac28d98159e0b9685d06a1f0d16826f98c0b9edce`
- `SYSTEM.DAT`: 4,127,307바이트, SHA-256 `e00e54da0b8f70cf3a2a099d6645b357f98e278e7d73cfa23058aea94a3c3dd1`
- ISO: `work/production/Prinny_ULJS00150_KR_Demo00_Title_Final.iso`, 500,465,664바이트, SHA-256 `36dfb20bc87a07b506704bc99fa9e7c53a152318ec6d5629fff22f5a59ae4a9a`
- 검증: 고정 크기·extent·비대상 자산 보존 PASS, 84 tests PASS, PPSSPP Headless 5초 PASS

이 산출물을 이후 이미지 번역 작업의 새 생산 기준선으로 사용한다.
## 13. 튜토리얼 그래픽 v1 빌드

```powershell
python .\workspace\scripts\build_tutorial_graphics_poc.py `
  .\workspace\config\tutorial_graphics_poc.json `
  .\extracted\PSP_GAME\USRDIR\ANIME.DAT `
  ..\..\Font\HancomMalangMalang-Regular.ttf `
  .\work\poc\tutorial_graphics_v1

python .\workspace\scripts\build_iso_poc.py `
  .\workspace\config\tutorial_iso_profile.json `
  .\work\production\Prinny_ULJS00150_KR_Demo00_Title_Final.iso `
  .\work\poc\tutorial_graphics_v1\ANIME.DAT `
  .\work\production\Prinny_ULJS00150_KR_Demo00_Title_Tutorial_v1.iso

python .\workspace\scripts\ppsspp_boot_probe.py `
  H:\ppsspp\PPSSPPHeadless.exe `
  .\work\production\Prinny_ULJS00150_KR_Demo00_Title_Tutorial_v1.iso `
  .\work\poc\tutorial_graphics_v1\ppsspp_boot_report.json --duration 5
```

산출 `ANIME.DAT`은 원본과 같은 27,827,616바이트이며 SHA-256은 `641b1e7b222cfa82813c7c9e4fad8e4d2c302e764811d2580f4bc5c70ded351a`다. ISO는 기존 타이틀 최종본의 `/PSP_GAME/USRDIR/ANIME.DAT;1` extent(`0x1AE00000`, 27,827,616바이트)만 교체하며, 결과 SHA-256은 `c93078275ca2797f581852003a4237cf273ef5b580714c4e14ccf94d30a0d3ff`다.

v1 실제 화면에서 제목 좌측 치우침과 검정 본문·빨간 강조어·버튼 아이콘 중복을 확인했으므로 이 빌드는 폐기한다.

## 14. 튜토리얼 그래픽 v2 빌드

```powershell
python .\workspace\scripts\build_tutorial_graphics_poc.py `
  .\workspace\config\tutorial_graphics_poc.json `
  .\extracted\PSP_GAME\USRDIR\ANIME.DAT `
  ..\..\Font\HancomMalangMalang-Regular.ttf `
  .\work\poc\tutorial_graphics_v2

python .\workspace\scripts\build_iso_poc.py `
  .\workspace\config\tutorial_iso_profile.json `
  .\work\production\Prinny_ULJS00150_KR_Demo00_Title_Final.iso `
  .\work\poc\tutorial_graphics_v2\ANIME.DAT `
  .\work\production\Prinny_ULJS00150_KR_Demo00_Title_Tutorial_v2.iso

python .\workspace\scripts\ppsspp_boot_probe.py `
  H:\ppsspp\PPSSPPHeadless.exe `
  .\work\production\Prinny_ULJS00150_KR_Demo00_Title_Tutorial_v2.iso `
  .\work\poc\tutorial_graphics_v2\ppsspp_boot_report.json --duration 5
```

v2는 제목을 실제 UV 폭에서 가운데 정렬하고, 검정 본문을 빨간 강조어·버튼 아이콘 구간 앞뒤로 분할 렌더링한다. `닫기`를 포함한 관리 슬롯은 61개다. 산출 `ANIME.DAT` SHA-256은 `75318599f8403dd286cbf5b29a52faa2a6390968f5f8c0d3ac8e661bd04e189c`, 변경 바이트는 102,458개다. ISO SHA-256은 `069fb38c1f7a19ae9522246fc10321e475f8963f5cb09337705564ae8c965bf6`이며 86 tests와 PPSSPP Headless 5초 부팅을 통과했다.

v2 실제 화면에서 버튼 뒤 여백, 강조어 따옴표와 `들기/던지기` 배치가 어긋나므로 최종 후보로 사용하지 않는다.

## 15. 튜토리얼 그래픽 v3 빌드

v2와 같은 명령에서 출력 디렉터리와 ISO 이름만 다음처럼 바꾼다.

```powershell
python .\workspace\scripts\build_tutorial_graphics_poc.py `
  .\workspace\config\tutorial_graphics_poc.json `
  .\extracted\PSP_GAME\USRDIR\ANIME.DAT `
  ..\..\Font\HancomMalangMalang-Regular.ttf `
  .\work\poc\tutorial_graphics_v3

python .\workspace\scripts\build_iso_poc.py `
  .\workspace\config\tutorial_iso_profile.json `
  .\work\production\Prinny_ULJS00150_KR_Demo00_Title_Final.iso `
  .\work\poc\tutorial_graphics_v3\ANIME.DAT `
  .\work\production\Prinny_ULJS00150_KR_Demo00_Title_Tutorial_v3.iso
```

v3 `ANIME.DAT` SHA-256은 `74b7fa6be0cd1d6fa662f58bfcd911efff846a1cd22ae0e1d13cbc349a58339a`, 변경 바이트는 102,892개다. ISO SHA-256은 `fc056c011f5376ca97c1c4a2c2adf0084798688bade30486b00406b24f22bfe6`이며 간격 좌표 회귀를 포함한 87 tests와 PPSSPP Headless 5초 부팅을 통과했다.

## 16. 튜토리얼 PPSSPP 실시간 프리뷰

이후 간격 조정은 v3 ISO를 기준으로 replacement texture를 사용한다. `H:\ppsspp\memstick\PSP\SYSTEM\ppsspp.ini`의 `ReplaceTextures=True`, `SaveNewTextures=True`가 확인돼 있다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  .\workspace\scripts\refresh_tutorial_live_preview.ps1
```

스크립트는 `workspace/config/tutorial_graphics_poc.json`의 현재 좌표로 임시 `ANIME.DAT`만 만들고, v3 기준 인덱스와 달라진 픽셀을 다음 7개 덤프에 반영한다.

- texture 0: `0956db10*7d447ccc.png` 팔레트 변형 4개
- texture 1: `0958db109d4e7fbfb3a9c201.png`
- texture 2: `095adb109d4e7fbfdab9bc3f.png`
- texture 3: `095cdb1092a862e2cb89d932.png`

출력 위치는 `H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150`이다. 스크립트는 PNG 7개와 함께 `textures.ini`를 생성한다. 각 기준 덤프 파일명의 앞 16자리 주소·팔레트 접두사와 이미지 크기가 같은 `new` 덤프를 모두 찾아 `[hashes]`에서 기준 PNG로 연결하므로 콘텐츠 해시가 달라도 최신 후보를 소비한다. 현재 별칭은 62개, INI SHA-256은 `9d327559…3b30`이다. 실행 후 PPSSPP를 완전히 종료했다가 v3 ISO로 다시 시작한다. 생성 보고서는 `work/live/tutorial_graphics/tutorial_live_preview_report.json`이며 후보 `ANIME.DAT` SHA-256은 `e00493af…fe77`, `requires_iso_rebuild=false`다. 최종 화면 승인 뒤에만 새 `ANIME.DAT`과 ISO를 생성한다.
### 관리 영역 재구성 빌드

`refresh_tutorial_live_preview.ps1`은 설정의 `clear_bounds` 및 relocation 영역을 최신 후보 인덱스로 강제 출력한다. 이 동작은 오래된 덤프의 괄호·해골·문자 잔재를 제거하며, 관리 영역 밖의 픽셀은 보존한다. 현재 후보 SHA-256은 `393097735e8212ccf7da63dcbdf91029de44105d2326015ad1bcb1431d203723`, 변경 바이트는 103,114다. `textures.ini`는 62개 관찰 해시를 연결하며 SHA-256은 `9d3275596d44194b13d1bf7e85578e56f9d422efaf810ac2dfc34f40e62d3b30`이다. PPSSPP를 완전히 종료한 뒤 다시 실행해야 한다.
### 강조 문구 19px 후보

현재 라이브 빌드는 축소됐던 6개 강조 문구를 19px로 렌더링하고 괄호 좌표를 별도로 확장한다. 후보 SHA-256은 `0179ce3fd467238167a7f0724bd66b8f11bb6a6893b79b682665a86dc36e1702`, 변경 바이트는 103,022다. texture 1/2/3 교체 PNG는 각각 `4c881056ffd341586598abbfce5691658cb28b0a90b811764d195ef2e54a1479`, `ed1bd62ef3566a7ebcb729c1068ffa40025e040915689c37a9b51b657e4315a7`, `9a8947aaba011fd3c845a9e53ec9175716c0e919171b0396c69a348f65ddc58a`다. 확인 시 PPSSPP를 완전히 종료한 후 다시 실행한다.
### 중심·던지기·해골 후보

이 후보는 `offset_x=4` 중심 보정 3건, `던지기` 19px/가로 0.88배, 해골 relocation 제거를 포함했다. 가로 축소는 실제 화면에서 번짐이 확인되어 폐기했다. 최신 후보는 `던지기`를 19px 원본 글리프와 `tracking=-3`으로 44px 폭에 만들고 `실드 카운터`를 +4px 이동한다. 후보 SHA-256은 `22c7e125836a6cc0c57bd1286d6e6f25d130428e618ea25ebd417e687842a7f0`, 변경 바이트는 102,801다. texture 1/2/3 PNG는 `4c881056ffd341586598abbfce5691658cb28b0a90b811764d195ef2e54a1479`, `b977a11da3c699a69972d70640d0dafd3cbac5145fbe19500a40169a0690fbb8`, `18313cf568a20008f5382996d71848cf27a3888d1ab1e9ac9f085d5dfcac56d9`다.

웅크리기 행 충돌 후보는 `방향키 아래로`만 12px 왼쪽 이동한다. 최신 후보 SHA-256은 `9b487201baef12e15661f2c956109e1e1ea88fdd392cacc7be8490af276dd2f7`, 변경 바이트는 102,778이며 texture 1은 `d97da3594d4d081d1fb747737a57c7944b357f9e21b02d27f4969ee8f2c8d4cd`다. PPSSPP 교체 텍스처만 갱신하며 ISO는 만들지 않는다.

## 17. 월드 방향 간판 소비자 확인

덤프 접촉표는 주소·팔레트 접두사 16자리 기준 중복 제거와 페이지 분할을 지원한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  .\workspace\scripts\build_ppsspp_dump_contact_sheet.ps1 `
  -InputDirectory 'H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150\new' `
  -OutputPath '.\work\analysis\graphics\ppsspp_unique_prefix_page_4.png' `
  -UniquePrefix -Offset 288 -Maximum 96 -Columns 6 -ThumbnailSize 160
```

식별된 `09bba150f04e998665714c1a.png`의 오른쪽 표지에 소비자 마커를 만든다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  .\workspace\scripts\build_ppsspp_sign_probe.ps1 `
  -SourcePath 'H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150\new\09bba150f04e998665714c1a.png' `
  -OutputPath 'H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150\09bba150f04e998665714c1a.png'
```

마커는 오른쪽 표지 `[104,2,106,65]`에만 그려지며 출력 SHA-256은 `6e7f835bf814ce88526c60e69ac727cee18da919bb2413e4eb37e9fddd69d8b6`이다. PPSSPP를 완전히 종료했다가 다시 실행해 월드 간판에 자홍색 X가 표시되는지 확인한다. 이 단계에서는 ISO를 만들지 않는다.

사용자 화면에서 양쪽 간판의 마커가 확인되면 다음 명령으로 마커를 제거한 한글 교체본을 만든다.

```powershell
python .\workspace\scripts\build_world_sign_live_preview.py `
  --source 'H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150\new\09bba150f04e998665714c1a.png' `
  --font '..\..\Font\HancomMalangMalang-Bold.ttf' `
  --output '.\work\live\world_sign\09bba150f04e998665714c1a.png' `
  --install 'H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150\09bba150f04e998665714c1a.png' `
  --report '.\work\live\world_sign\world_sign_live_preview_report.json'
```

출력과 설치본은 256×128, SHA-256 `aa10b3854c14f54271712d25a8eafdf82c6cbdeaff56102da305d1484283cf0c`로 일치한다. `마왕성`·`튜토리얼`을 동시에 교체하며 `requires_iso_rebuild=false`다. PPSSPP를 완전히 종료한 뒤 다시 실행해 양쪽 표지의 정렬과 가독성을 확인한다.

첫 후보는 실제 화면에서 문구가 좌우 반전되어 폐기했다. 생성기는 이제 `LABELS[*].mirror_x=true`로 문자 바운드만 사전 좌우 반전한다. 목재·화살표는 반전하지 않는다. 최신 출력·설치 SHA-256은 `b2e55afbd5e1c6ca2d1e10860cdabe48454b737f37e37faf87cc942dd7f54e94`이며 `requires_iso_rebuild=false`다. 정적 PNG에서는 문구가 거꾸로 보여야 하고, PPSSPP를 완전히 종료한 뒤 실제 간판에서 정상 방향인지 확인한다.

## 18. 이미지 텍스트 일괄 초안

```powershell
python .\workspace\scripts\build_baked_graphics_bulk_preview.py `
  --project-root . `
  --ppsspp-textures 'H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150'
```

`work/live/baked_graphics_bulk/generated`에 난이도, 리플레이, 장식 간판, 엔딩 카드, 에필로그 초안을 만들고 `build_report.json`에 SHA-256을 기록한다. 덤프 이름이 확정된 난이도 `0918bd60611a54e7d55a5edf.png`와 리플레이 `091cd1e0f54138b2af437712.png`를 PPSSPP에 설치한다. 나머지 3개 초안은 런타임 덤프 이름을 얻을 때까지 `pending_live_mapping`에 기록한다.

생성기는 기존 `textures.ini`의 별칭을 읽어 보존한 뒤 새 별칭만 병합한다. 따라서 튜토리얼 교체 텍스처가 삭제되지 않는다. 결과 보고서의 `iso_built=false`를 확인하고 PPSSPP를 완전히 종료했다가 다시 실행한다. 현재 설치 SHA-256은 난이도 `9ebbf882b9c2ebeff0ee3a4b6a85093e0bb2ab91d9cff445db2870ea01983c54`, 리플레이 `b534f42047ed91c96aa823b7a37e518ab9f59c72b53f4e04bbf90d9fbad2d4f8`, `textures.ini` `305ecf280d588139a79a8907721959dc269adc6bcf9b88d929b4b86fc2608f0a`다.

## 19. 전체 이미지 초벌 PPSSPP 갱신

프로젝트 루트에서 다음 한 명령으로 949개 카탈로그 갱신, 66개 target 초벌 생성, 현재 PPSSPP 덤프 자동 대응, 전체 검수 시트 생성을 수행한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  .\workspace\scripts\refresh_all_baked_graphics_preview.ps1 `
  -PpssppRoot 'H:\ppsspp'
```

출력은 다음과 같다.

- 카탈로그: `work/analysis/graphics/baked_text_full_catalog.json`
- 전체 생성 보고서: `work/live/baked_graphics_full/build_report.json`
- 덤프 연결 보고서: `work/live/baked_graphics_full/bind_report.json`
- 검수 manifest: `work/live/image_first_pass_review/review_manifest.json`
- 전체 접촉표: `work/live/image_first_pass_review/all_first_pass_contact_sheet.png`

PPSSPP에서 아직 열지 않은 화면은 번역 PNG만 준비되고 임의 해시에는 설치되지 않는다. 텍스처 덤프를 켠 채 새 화면을 연 다음 같은 명령을 다시 실행하면 RGBA가 정확히 일치하는 소비자만 자동 연결된다. 이 절차는 ISO를 만들지 않는다.
# 오프라인 이미지 검수 갤러리 생성

ISO를 만들지 않고 현재 이미지 초벌 번역 66개를 갤러리로 갱신한다.

```powershell
python .\workspace\scripts\build_image_review_gallery.py `
  --project-root .
```

결과는 `work/live/image_first_pass_review/gallery/index.html`이다. 전체 이미지 갱신 스크립트 `workspace/scripts/refresh_all_baked_graphics_preview.ps1`도 마지막 단계에서 이 생성기를 자동 실행한다. 상세 사용법은 `docs/image-review-gallery.md`를 참조한다.
# record 82 구·신 해시 라이브 설치 (2026-07-25)

`workspace/scripts/build_base_menu_live_preview.py`의 `--install-dir` 실행은 기존 `textures.ini` 별칭을 보존하면서 다음 세 해시를 한글 정본으로 병합한다.

```text
091591e09a963304c67a3ca6
091591e09a96330453b50c70
091591e09a9633045a907f4a
```

세 번째 해시는 최신 결과 수정 ISO에서 관찰한 콘텐츠 해시다. 첫 번째 해시는 이전 세이브스테이트가 일본어 아틀라스를 복원할 때 사용한다. 설치 후 `H:\ppsspp\memstick\PSP\SYSTEM\ppsspp.ini`에서 `ReplaceTextures=True`, `SaveNewTextures=True`를 확인하고 PPSSPP를 완전히 종료했다가 다시 실행한다. 이 검수 단계에서는 ISO를 다시 만들 필요가 없다.

## 20. 전체 번역 통합 ISO (2026-07-26)

텍스처 교체를 끈 최종 누락 검수를 위해 다음 번역 자산을 네이티브 컨테이너에 통합했다.

- BOOT/EBOOT 공용 UI: `workspace/text/boot_ui_translation.json` 78개 슬롯
- 스테이지 정보: `workspace/text/translation/stage_info.csv` 188개 번역 슬롯
- 통합 한글 글자표: 기존 841자에 스테이지 전용 11자를 추가한 852자
- 번역 이미지: `work/live/image_first_pass_review/gallery/assets/translated`의 PNG 66개
  - `BG.DAT` 3개
  - `ANIME.DAT` 56개
  - `start.dat` 직접 자산 1개
  - `start.dat/anime00.dat` 6개

스테이지 정보 재삽입은 `workspace/scripts/integrate_stage_info_iso.py`가 담당한다. 33바이트 고정 슬롯의 최대 32바이트 페이로드, 널 종료, 레코드 ID 및 꼬리 바이트 보존을 검사한 뒤 `start.lzs`와 `SYSTEM.DAT`를 재조립한다. 이어 `workspace/scripts/build_translated_images_iso.py`로 확정 PNG를 원래 컨테이너에 삽입했다.

최종 산출물:

```text
work/production/Prinny_ULJS00150_KR_Integrated_20260726.iso
크기: 500,465,664바이트
SHA-256: e8366e824b005ce6f8611cba144e3543b43e570b541c55f8c9e664a3941818e1
```

원본 ISO는 `original`에 그대로 보존했다. 새 통합본 검증 후 이전 테스트 ISO와 중간 ISO는 삭제했으며, 현재 프로젝트에는 원본과 위 통합본만 남긴다.

## 21. clean extracted 기반 PPSSPP 직접 실행 빌드 (2026-07-26)

기존 통합 ISO를 입력으로 재사용하지 않고 `extracted`를 복사해 직접 실행 폴더를 만드는 단일 빌더를 추가했다.

```powershell
$env:PYTHONPATH = (Resolve-Path '.\workspace\scripts').Path
python .\workspace\scripts\build_direct_run.py
```

기본 출력은 `work/builds/direct_run_latest`, 보고서는
`work/reports/direct_run_latest.json`이다. ISO는 만들지 않는다. 빌더는 다음을
clean 트리에서 한 번에 합성한다.

- 혼합 CP932 타자 효과 및 문장부호 2px 간격 패치
- BOOT/EBOOT UI 78개 슬롯과 평문 EBOOT 실행 후보
- 최신 `Demo00.dat`, 852자 통합 폰트, `StageInfo00.dat`
- 번역 PNG 66개(`BG.DAT` 3, `ANIME.DAT` 56, `start.dat` 1,
  `start.dat/anime00.dat` 6)

원본 대비 변경 파일은 다음 5개뿐이다.

```text
PSP_GAME/SYSDIR/BOOT.BIN
PSP_GAME/SYSDIR/EBOOT.BIN
PSP_GAME/USRDIR/SYSTEM.DAT
PSP_GAME/USRDIR/ANIME.DAT
PSP_GAME/USRDIR/BG.DAT
```

스테이지 런타임 매핑을 분리 검증할 별도 폴더도 생성했다.

```powershell
python .\workspace\scripts\build_direct_run.py `
  --stage-mode probe `
  --output .\work\builds\direct_run_stage_probe `
  --report .\work\reports\direct_run_stage_probe.json
```

probe는 레코드 1~5와 16~20의 제목/첫 줄에 각각 `S01 TITLE`,
`S01 LINE`부터 `S20 TITLE`, `S20 LINE`까지 20개의 고유 표식을 넣는다.
나머지 자산은 `direct_run_latest`와 같다. PPSSPP 실기 검수는 replacement
texture를 끄고 이전 세이브스테이트 없이 시작한다.

## 22. 데모 스킵 합성 문구 색상 통일 (2026-07-26)

데모 스킵 exact texture 3종만 갱신하고 타이머 자산은 건드리지 않는다.

```powershell
python .\workspace\scripts\build_demo_skip_timer_live_preview.py `
  --source-dir 'H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150\new' `
  --output-dir '.\work\live\demo_skip_timer_preview\textures' `
  --install-dir 'H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150' `
  --backup-dir '.\backups\demo_skip_uniform_before_20260726' `
  --demo-only `
  --report '.\work\live\demo_skip_timer_preview\report.json'
```

`--demo-only`는 문구 영역 `[8,24,84,56)`을 `f54138b2` CLUT의 흰색
픽셀·알파로 통일한다. 영역 밖은 각 원본 상태를 그대로 보존한다. 최초 실행
전 설치본과 `textures.ini`는 지정한 백업 폴더에 한 번만 저장된다.

확인은 PPSSPP에서 `Replace textures`를 켠 뒤 완전히 재시작하고 데모 화면을
새로 진입해 수행한다. 이 절차는 ISO를 생성하지 않는다.

## 23. 현재 사용자용 한글 실행 구성 복구 (2026-07-26)

`direct_run_stage_probe`는 진단용이므로 실행하지 않는다. 번역 플레이는 다음
전용 실행기로 시작한다.

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\workspace\scripts\launch_prinny_korean.ps1
```

실행기는 PPSSPP가 완전히 종료된 상태에서만 동작한다. 다음을 한 번에 수행한다.

- `ReplaceTextures = True`
- 최근 실행 `FileName0 = work/builds/direct_run_latest`
- `direct_run_latest` 직접 실행
- 변경 전 `ppsspp.ini`를
  `backups/ppsspp_before_korean_launch_20260726`에 보관

교체 팩 파일과 별칭은 다음 명령으로 동기화한다.

```powershell
python .\workspace\scripts\sync_ppsspp_texture_pack.py
```

`textures.ini`에 등록됐지만 빠진 생성 PNG는 프로젝트 생성물에서 복구하고,
설치된 exact PNG에 자기 파일명 별칭이 없으면 추가한다. 현재 동기화 결과는
설치 PNG 51개, 별칭 106개, 누락 target 0개다.

직접 실행 빌드는 이제 `LuckyDoll.dat`도 포함한다.

```powershell
python .\workspace\scripts\export_lucky_doll.py
$env:PYTHONPATH = (Resolve-Path '.\workspace\scripts').Path
python .\workspace\scripts\build_direct_run.py --replace
```

`lucky_doll.csv` 120레코드를 65바이트 한도 안에서 인코딩하며
`StageInfo00.dat`과 함께 `SYSTEM.DAT > start.lzs`에 삽입한다.

## 24. UI 슬롯 105개·셀 방식 데모 스킵 실행본 (2026-07-26)

데모 스킵은 글자 셀 생성에 폰트가 필요하므로 `--demo-only`에서도 `--font`를
반드시 지정한다.

```powershell
python .\workspace\scripts\build_demo_skip_timer_live_preview.py `
  --source-dir 'H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150\new' `
  --font '..\..\Font\HancomMalangMalang-Regular.ttf' `
  --output-dir '.\work\live\demo_skip_timer_preview\textures' `
  --install-dir 'H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150' `
  --backup-dir '.\backups\demo_skip_cell_before_20260726' `
  --demo-only `
  --report '.\work\live\demo_skip_timer_preview\report.json'
```

BOOT UI 번역표를 확장한 뒤 폰트·실행 파일과 직접 실행 폴더를 다시 만든다.

```powershell
python .\workspace\scripts\audit_boot_ui_translation.py `
  --project-root . `
  --report .\work\analysis\boot_ui_translation_report.json

python .\workspace\scripts\build_boot_ui_runtime_patch.py `
  .\workspace\config\demo00_production_profile.json `
  .\workspace\text\boot_ui_translation.json `
  .\work\analysis\demo00_boot_ui_fixed_font_reclaim.json `
  '..\..\Font\HancomMalangMalang-Regular.ttf' `
  .\work\production\demo00\font.fnt `
  .\work\production\demo00\font.txp `
  .\work\production\demo00\hangul_mapping.json `
  .\extracted\PSP_GAME\SYSDIR\BOOT.BIN `
  .\work\builds\direct_run_boot_ui_20260726

python .\workspace\scripts\build_direct_run.py `
  --boot-ui-dir .\work\builds\direct_run_boot_ui_20260726 `
  --replace
```

최신 직접 실행본은 BOOT UI 105슬롯, StageInfo 188슬롯, LuckyDoll 120레코드를
포함한다. BOOT SHA-256은
`00bc31be9bf47ab322729c84847d4c5af90abcd3f4dfcbd8731d52817bffa2e9`,
SYSTEM.DAT은
`425d76973d69630dd16ed4bc3d91da8220317570888d05ee33ab0ede8aea544d`다.

## 25. 네이티브 record 87 해시용 데모 스킵 교체본 (2026-07-26)

`direct_run_latest`의 `start.dat/anime00.dat record 87 texture 0`은 PPSSPP에서
기존 `f4cbdbb1`이 아니라 `6ceb80dc` content hash로 관측된다. 위 24절 명령은
이제 두 해시의 CLUT 3종, 총 6개를 모두 요구하고 생성·설치한다.

```text
091cd1e0a8d5fd966ceb80dc.png
091cd1e0f54138b26ceb80dc.png
091cd1e0f96c6b826ceb80dc.png
```

현재 `textures.ini`는 109개 별칭이며 SHA-256은
`ac8b8a3a0eb7fefd83e356dbc821046cb42180f7c4812b316a44180e16a02369`다.
설치 전 파일은 `backups/demo_skip_current_hash_before_20260726`에 보존했다.
ISO는 생성하지 않았다.

## 26. 본편 + 개별 DLC xdelta 배포 (2026-08-02)

R2 직접 실행 트리의 998자 글꼴을 본편 ISO에 포함하고, DLC는 보유 파일마다 독립 적용하도록 패치 4개로 분리했다.

```powershell
python .\workspace\scripts\build_final_iso.py `
  --build-tree .\work\builds\dlc_kr_20260802_r2\direct_run `
  --supplemental-report .\work\builds\dlc_kr_20260802_r2\report.json `
  --output .\work\production\Prinny_ULJS00150_KR_Final_20260802.iso

python .\workspace\scripts\build_xdelta_release.py
```

배포 폴더는 `dist/Prinny_KR_Patch_20260802/`이다. 본편 ISO xdelta 1개와 `DL0000..2.EDAT` xdelta 3개, 적용 스크립트, xdelta3 3.2.0, 텍스처 팩만 포함한다. ISO·EDAT·PBP는 포함하지 않는다.

- 원본 ISO: `AF0D2873...A8B9D03`
- 최종 ISO: `9450547B...E42B558`, 500,465,664바이트
- 본편 xdelta: `9909BC7B...68B4CA`
- DL0000 xdelta: `9E2F5839...418EEF5`
- DL0001 xdelta: `B313B571...E3C0F`
- DL0002 xdelta: `8FBDF83E...7BA4E`

네 패치는 모두 원본에 역적용하여 목표 해시와 일치했다. 배포 복사본의 `apply_main.cmd`와 `apply_dlc.cmd`도 실제 실행해 본편 ISO 및 DLC 3개 출력을 재검증했다. xdelta 적용본은 `work/probes/final_xdelta_20260802_boot.json`에서 PPSSPP Headless 1.19.3의 8초 게임 루프를 통과했고, 정식판 GUI에서도 `ULJS00150`으로 기동했다.

DLC EDAT는 본편 패치에 포함된 998자 글꼴에 의존한다. 따라서 DLC 패치 사용자는 2026-08-02 본편 xdelta도 적용해야 한다.

공유용 `dist/Prinny_KR_Patch_20260802.zip`은 1,055,996바이트, SHA-256 `5D0A4619CC9DB8A3055B0EBBE4C0BA6CD3B9DF4992987C3001BC3D57E61B0CD3`이다. ZIP 25개 엔트리를 검사해 ISO·CSO·EDAT·PBP가 0개임을 확인했다.

## 27. 네이티브 스테이지 HUD + 결과 화면 R2 정식 배포 (2026-08-03)

사용자가 텍스처 교체 OFF 상태에서 월드 표지판·튜토리얼·타이머와 결과 화면 R2를 승인한 직접 실행 트리를 최종 입력으로 사용한다.

```powershell
python .\workspace\scripts\build_final_iso.py `
  --build-tree .\work\builds\stage_hud_native_result_spacing_r2_20260803\direct_run `
  --output .\work\production\Prinny_ULJS00150_KR_Final_20260803.iso

python .\workspace\scripts\ppsspp_boot_probe.py `
  'H:\ppsspp\PPSSPPHeadless.exe' `
  .\work\production\Prinny_ULJS00150_KR_Final_20260803.iso `
  .\work\probes\final_xdelta_20260803_boot.json --duration 8

python .\workspace\scripts\build_xdelta_release.py
```

- 최종 ISO: 500,465,664바이트, SHA-256 `AE53BC4B960B263A362756E801C21DA7224CE3DD735D2DA5882C04A0248622AC`
- 본편 xdelta: 723,171바이트, SHA-256 `357082CA2707240BD5DEFE59FAAD75C72E2CA44FE900380523FBD9C2846BBC89`
- DLC xdelta 3개는 이전 R7 배포와 바이트 동일하며 개별 적용 정책을 유지한다.
- 배포 xdelta 역적용본은 최종 ISO와 SHA-256이 동일하고 PPSSPP Headless 8초 부팅을 통과했다.
- 월드 표지판·튜토리얼·타이머는 ISO 내부 자산이므로 v2.3 배포에서 PPSSPP 텍스처 팩을 제거했다.
- DLC별 원본 EDAT·패치 후 EDAT·xdelta SHA-256을 README에 추가하고 본편 적용 후 기대 해시를 최종 R2 값으로 수정한 갱신 ZIP: 891,004바이트, SHA-256 `59CDF7C4D2F5545BD8A6C6A7CFEB7E1DDFFBE7B23207D31EBC4C36D0C601B348`
- 검증 뒤 `original` 밖의 ISO는 모두 삭제한다.
