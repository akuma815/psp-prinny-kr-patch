# DLC 한글화 조사 기준선

## 1. 범위와 현재 판정

- 대상: PSP 일본판 `ULJS00150`용 선택 DLC 3종
- 입력 위치: `original/Prinny DLC/`
- 입력 취급: 원본은 읽기 전용이며 모든 수정 결과는 `work/` 아래에서 생성한다.
- 현재 판정: **추출·재삽입 파이프라인 진행 가능**
- 아직 확정하지 않은 항목: `DCLT` 자리표시자의 실제 표시 여부, `DCHR` ASCII 이름의 화면 소비 여부, DLC 그래픽 내 베이크드 일본어의 전체 분모

## 2. 지원 입력

| 파일 | 크기 | SHA-256 |
| --- | ---: | --- |
| `DL0000.EDAT` | 1,624,784 | `a0209702de5210b2f35c57e7c12bfddbeb691200de06769b615ca50254d48c1b` |
| `DL0001.EDAT` | 1,540,688 | `86b48d56b6ba853f09ffb0a524ccebf4f601c78cb0f4937cb885ec8815bdb7a7` |
| `DL0002.EDAT` | 1,365,296 | `3fbc26ed99c1b3f474e50dd5290eb0497e61f0a7e8e9268fb82980a426079be9` |
| `PARAM.PBP` | 23,971 | `b4d52c1fd59d46ae9a9f6b0d4a01dbb95f79d51e78fe7901d6a3e8051fb62b16` |

`PARAM.PBP`의 SFO는 `CATEGORY=MG`, `DISC_ID=ULJS00150`, `TITLE=プリニー　追加配信データ`다. PSP 시스템 UI의 한글 글리프와 설치 호환성이 확인되지 않았으므로 배포 구현에서는 원본 유지 대상으로 둔다.

## 3. DIDT0 컨테이너

세 EDAT는 암호화된 NPDRM 블롭이 아니라 게임이 직접 읽는 평문 `DIDT0` 컨테이너다. `workspace/scripts/didt.py`가 다음 청크 체인을 파일 끝까지 엄격하게 파싱하고 무변경 바이트 동일 왕복을 검증한다.

```text
DSTI → DICO → DTZO → DAMM → DAMP → DABG
→ DBMM → DBMP → DBBG → DANM → DSCR
→ DCHR → DDEM → DCLT → NEND
```

각 청크는 `4-byte tag + u32 payload size + 8-byte reserved + payload` 구조다. `reserved`는 대부분 0이지만 `DTZO`에는 파일별 관측값이 있으므로 의미를 추측하거나 정규화하지 않고 원본 그대로 보존한다.

## 4. 텍스트 맵

### 4.1 DDEM

`DDEM`은 `u32 count` 뒤에 본편 `Demo00.dat`와 같은 132바이트 레코드가 이어진다. 레코드는 17바이트 화자 슬롯과 35바이트 본문 슬롯 3개를 가진다. 각 슬롯은 CP932 NUL 종료·0 패딩이며 최대 payload는 각각 16바이트와 34바이트다.

| 파일 | 레코드 | 비어 있지 않은 화자·본문 슬롯 | ID 범위 | 청크 꼬리 |
| --- | ---: | ---: | --- | ---: |
| `DL0000` | 29 | 83 | `55F0..5628` 짝수 | 8바이트 0 |
| `DL0001` | 23 | 68 | `53FC..5428` 짝수 | 없음 |
| `DL0002` | 15 | 31 | `C350..C36A` 계열 | 없음 |
| 합계 | **67** | **182** | — | — |

기본 ISO에서 확인했던 DDEM 참조 52개는 `DL0000` 29개와 `DL0001` 23개에 전부 존재한다. `DL0002`의 15개는 DLC 내부 모집단이다. `DSCR` 정적 스캔에서 `C35C`가 직접 잡히지 않았지만 동적 도달 가능성을 닫지 않았으므로 67개 전부를 번역 분모로 유지한다.

### 4.2 DSTI

`DSTI` payload는 384바이트이며 다음 경계를 가진다.

```text
6-byte protected header
11 × 33-byte CP932 fixed slots
15-byte zero footer
```

슬롯 0은 제목, 슬롯 1~10은 설명 줄이다. 전체 33슬롯 중 31개가 비어 있지 않다. 최대 payload는 슬롯당 32바이트다.

### 4.3 미확정 범위

- `DCHR`: 총 29레코드이며 확인된 문자열은 `Flonne`, `Marona`, `SmallAsagi` 같은 ASCII 내부 식별자다. 런타임 화면 증거 전에는 번역하지 않는다.
- `DCLT`: 세 파일 모두 개발용으로 보이는 `ここにステージの説明文が入ります。…`가 있다. 실제 소비 여부를 PPSSPP에서 확인한다.
- `DICO`, `DAMM` 계열: 그래픽 또는 애니메이션 자산 후보다. 화면에서 일본어가 확인되면 베이크드 텍스트 카탈로그를 별도로 연다.

## 5. 추출 산출물

`workspace/scripts/export_dlc_text.py`는 다음 파일을 생성한다.

```text
workspace/text/translation/dlc/
├─ dl0000_ddem.csv
├─ dl0001_ddem.csv
├─ dl0002_ddem.csv
└─ dlc_stage_info.csv

workspace/text/source/
└─ dlc_manifest.json
```

DDEM CSV는 대화 흐름을 읽을 수 있도록 1레코드=1행으로 구성한다. 사람이 수정할
수 있는 필드는 `ko_speaker`, `ko_line_1..3`, `status`, `notes`뿐이다. DSTI CSV의
수정 가능 필드는 `ko`, `status`, `notes`다. 재추출 시 이 필드만 기존 값에서
승계하며 ID·오프셋·원문·원본 바이트는 현재 지원 입력에서 다시 만든다. DDEM은
67행 안에 화자·본문 전체 268슬롯을 보존하고, DSTI는 빈 슬롯을 포함한 33행의
분모를 고정한다.

재생성 명령:

```powershell
$env:PYTHONIOENCODING='utf-8'
python .\workspace\scripts\export_dlc_text.py
```

## 6. 글리프와 빌드 위험

현재 본편 최종 매핑은 987자다. 기존 회수 보고서에는 289개 후보 글리프와 893개 사용자 정의 코드가 남아 있지만 DLC 소비 범위는 당시 감사 밖이었다. 따라서 이 수치를 DLC용 안전 공급량으로 바로 사용하지 않는다.

DLC 번역문이 확정되면 다음 순서로 판정한다.

1. v2.0의 987자 코드→글리프 매핑을 고정한다.
2. DLC 코퍼스에서 필요한 신규 한글만 뒤에 추가한다.
3. DLC의 남겨 둘 원문과 런타임 문자열이 회수 글리프를 소비하는지 다시 감사한다.
4. 신규 글리프 수가 재검증된 공급량 안에 있을 때만 폰트·EDAT PoC를 만든다.

기존 987자의 코드를 재배치하면 본편의 인코딩된 문자열과 폰트가 불일치하므로 허용하지 않는다.

## 7. 다음 게이트

1. 원문 DLC를 `PSP/GAME/ULJS00150/`에 설치한다.
2. PPSSPP 1.19.3에서 세 DLC의 진입·제목·설명·대사·종료·재진입을 확인한다.
3. `DCLT`와 `DCHR`의 실제 표시 여부 및 베이크드 일본어 화면을 캡처한다.
4. 장면·화자 순서를 확인한 뒤 CSV 번역을 시작한다.
5. 번역 코퍼스의 글리프·길이 예산을 통과한 뒤 고정 크기 EDAT PoC를 만든다.

정적 왕복이나 빌드 성공만으로 DLC 지원 완료를 선언하지 않는다. 최종 판정은 PPSSPP 직접 실행과 PSP 실기에서 수행한다.

### 7.1 현재 설치 기준선

2026-08-02 확인 시 다음 두 PPSSPP 환경에 네 원본 파일이 이미 설치돼 있었고, 크기와 SHA-256이 §2의 지원 입력과 모두 일치했다.

- `H:/ppsspp_stable_1.19.3/memstick/PSP/GAME/ULJS00150`
- `H:/ppsspp/memstick/PSP/GAME/ULJS00150`

정본 런타임 기준은 격리된 정식판 `H:/ppsspp_stable_1.19.3`이다. 설치 동일성은 다음 명령으로 다시 검증한다.

```powershell
python .\workspace\scripts\verify_dlc_install.py
```

보고서는 `work/analysis/dlc_install_baseline.json`에 생성된다. 이 PASS는 파일 설치만 증명하며 DLC가 실제로 적재·표시됐다는 증거는 아니다.

## 8. 한국어 DLC PoC 빌드 (2026-08-02)

번역 CSV 감사와 고정 슬롯 재삽입을 완료했다.

- DDEM: `DL0000` 29개, `DL0001` 23개, `DL0002` 15개, 합계 67개 전부 완료
- DSTI: 실제 문자열 31개 완료, 원래 빈 슬롯 2개 유지
- 보호 필드·원문 바이트 불일치: 0
- 고정 슬롯 초과: 0
- 기존 987자 매핑 유지, 신규 11자 `꺼땡씌얍얽쭈창쿵팝핑혔` 추가
- 최종 매핑 998자, 후보 글리프 여유 278개

재현 빌드:

```powershell
python .\workspace\scripts\build_dlc_kr.py
```

산출물은 `work/builds/dlc_kr_20260802/`에 있으며, `report.json`이 입력 CSV 해시와 출력 해시를 기록한다. PPSSPP 설치본은 다음 명령으로 설치하거나 원본으로 복구한다. PPSSPP가 실행 중이면 안전을 위해 스크립트가 중단된다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\workspace\scripts\install_dlc_kr.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\workspace\scripts\install_dlc_kr.ps1 -RestoreOriginal
```

원본 백업은 `backups/ppsspp_stable_dlc_original_20260802/`에 보존했다. 2026-08-02 설치 후 PPSSPP 1.19.3이 직접 실행 빌드를 `ULJS00150`으로 인식하고 게임 창을 연 것까지 확인했다. DLC 선택 화면과 스테이지 내 대사의 실제 표시·줄바꿈·종료 진행은 사용자 런타임 확인 대기 상태다.

### 8.1 R2 제목 경로 및 대사 갱신

첫 PoC에서 `DSTI` 슬롯 0은 번역됐지만 DLC 선택 목록의 제목은 일본어로 남았다. 원인은 각 EDAT의 DIDT0 파일 헤더 `0x20..0x3F`에 제목 사본이 별도로 존재하고, 목록 화면이 이 헤더 사본을 사용하기 때문이다. R2 빌더는 다음 두 위치를 같은 CSV 제목으로 함께 갱신한다.

- DIDT0 헤더 제목: 파일 오프셋 `0x20`, 32바이트 고정 슬롯
- `DSTI` 제목: 슬롯 0, 33바이트 고정 슬롯

R2 산출물은 `work/builds/dlc_kr_20260802_r2/`이다. 수정된 `dl0000_ddem.csv` 대사도 재삽입됐으며, Excel이 보호용 16진수 열 3개를 과학 표기법으로 바꾼 문제는 번역 필드를 보존하는 재내보내기로 원본에서 복구했다. 작업 전 CSV는 `backups/dlc_translation_before_r2_reexport_20260802/`에 보존했다.

R2 설치 해시:

- `DL0000.EDAT`: `2A2FB6A26AD40AA7EF2BFD46795657416E4D45723F7B04B3A30E76E715B83739`
- `DL0001.EDAT`: `4D3F0B113670C532CAB6233C08309B000A34622673730CFD1B8D12DC6E503CCC`
- `DL0002.EDAT`: `FB6B75F3F60DA7233EEA63A229512A0762E3B789C7204C5E22D0D837677435AE`

PPSSPP 1.19.3에서 R2 직접 실행 빌드가 `ULJS00150`으로 기동한 것까지 확인했다. 제목과 수정 대사의 실제 화면 확인은 사용자 QA 대기 상태다.
