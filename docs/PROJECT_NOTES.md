# 프리니 ~제가 주인공해도 되겠슴까?~ 한글 패치

PSP 일본판 `プリニー ～オレが主人公でイイんスか？～` (ULJS00150, disc 1.01) 한글화 프로젝트.

> **상태: 완료 (2026-08-02).** PPSSPP와 PSP 실기(6.61 PRO-C / Inferno) 양쪽에서
> 본편 전 구간 표시와 세이브·로드까지 검증했고, DLC 3종 한글 패치를 추가한
> 배포본 v2.1을 확정했다.

---

## 1. 배포물

`dist/Prinny_KR_Patch_20260802/`

| 파일 | 크기 | 설명 |
| --- | --- | --- |
| `Prinny_ULJS00150_KR_20260802.xdelta` | 680 KB | 원본 ISO에 적용하는 본편 패치 |
| `Prinny_DLC_DL0000_KR_20260802.xdelta` | 1.9 KB | 마왕성과 타천사 DLC 패치 |
| `Prinny_DLC_DL0001_KR_20260802.xdelta` | 1.7 KB | 유령섬의 마로네 DLC 패치 |
| `Prinny_DLC_DL0002_KR_20260802.xdelta` | 1.1 KB | 연무성의 아사기 인형 DLC 패치 |
| `textures/ULJS00150/` | 11개 | PPSSPP 텍스처 팩 (PNG 10 + `textures.ini`) |
| `README_적용방법.txt` | — | 적용·설치·제거 안내 |
| `SHA256.txt` | — | 전 파일 무결성 해시 |
| `../Prinny_KR_Patch_20260802.zip` | 1.01 MB | 위 배포 폴더의 공유용 압축본 |

```text
원본 ISO   SHA-256: af0d2873a96c5fe6f95b3fc2fb3e8702f98bba67e32f2f78c5c3d1bdaa8b9d03
한글판 ISO SHA-256: 9450547b4089df9b668adfffa0d8b21fed314e93d78dfe2631e018255e42b558
크기: 500,465,664 bytes (원본과 동일)
```

xdelta 왕복 검증(원본 → 패치 적용 → 해시 일치) 완료.
배포 폴더에는 ISO, EDAT, PBP 등 원본 또는 패치 완료 게임 파일이 없다.
ZIP SHA-256은 `5D0A4619CC9DB8A3055B0EBBE4C0BA6CD3B9DF4992987C3001BC3D57E61B0CD3`이다.

---

## 2. 번역 범위

| 대상 | 분량 | 저장 위치 |
| --- | --- | --- |
| 게임 대사 (Demo00) | 1,523건 | `Demo00.dat` |
| 시스템·설정 UI, 튜토리얼 설명 | 590슬롯 | `BOOT.BIN` 고정 슬롯 |
| 스테이지 정보 | 220행 | `StageInfo00.dat` |
| 럭키 돌 | 120레코드 | `LuckyDoll.dat` |
| 마물 도감 | 91종 / 1,386슬롯 | `PictureBook.dat` |
| 럭키 박사 보상 | 120행 | `LuckyItem.dat` |
| 컬렉션 아이템 | 60행 | `Collection.dat` |
| 마계 훈장 | 90행 | `Honor.dat` |
| 음악 상점 곡명 | 12곡(일본어 곡명만) | `MusicShop.dat` |
| 클리어 시간 | — | `ClearTime00.dat` |
| 번역 이미지 | 67종 | `ANIME.DAT`, `BG.DAT`, `start.dat` |
| DLC 3종 대사 | 67레코드 | 각 `DLxxxx.EDAT`의 `DDEM` |
| DLC 제목·설명 | 31문자열 | DIDT0 헤더 및 `DSTI` |

폰트는 한컴 말랑말랑 Regular 기반 비트맵으로 생성해 CP932 사용자 정의 영역에
배치했다. 본편 987자 코드를 유지하고 DLC용 11자를 추가한 최종 매핑은 998자다.

**게임을 실행한 뒤 보이는 텍스트는 전부 한글이다.**

---

## 3. 알려진 제약

### 3.1 PSP 세이브 목록 화면은 일본어

PSP 본체의 세이브/로드 목록에 표시되는 아래 항목만 일본어 원문이다.

```text
게임 제목    プリニー ～オレが主人公でイイんスか？～
항목명       システムデータ / ゲームデータ / リプレイデータ
설명문       残り○魔時間 / 残りプリニー数：○匹 / プレイ時間：…
```

이 화면은 게임이 아니라 **PSP 펌웨어가 그리며**, 게임이 넘긴 문자열을 그대로
쓴다. 한글로 넣으면 실기에서 **저장이 실패**하므로 원문을 유지했다
(자세한 원인은 6.3 참조). 게임 내부 표시에는 영향이 없다.

### 3.2 일부 스테이지 이미지는 텍스처 팩 담당

마왕성/스테이지 방향 표지판, 튜토리얼 푯말, 남은 시간 타이머는
`STAGE.DAT`의 미해석 포맷(GM3/NFG20) 안에 있어 ISO에 넣지 못했다.
PPSSPP 텍스처 팩이 이 항목들을 담당하며, 팩 없이도 게임 진행과 전체 텍스트
한글화에는 문제가 없다. **PSP 실기에서는 이 이미지들이 일본어로 남는다.**

### 3.3 권장 에뮬레이터

PPSSPP **정식판 1.19.3 이상**. 개발 빌드 v1.20.4-426 계열에는 설정 화면 설명문이
서로 섞여 보이는 텍스처 캐시 회귀 버그가 있다 (6.1 참조).

---

## 4. 검증 결과

| 게이트 | 결과 |
| --- | --- |
| BOOT UI 슬롯 전수 대조 | 590/590 PASS |
| 자동 테스트 | 110 PASS (2건은 삭제된 구 빌드 폴더 참조, 파이프라인 무관) |
| PPSSPP Headless 부팅 프로브 | PASS |
| PPSSPP 1.19.3 실사용 | 전 구간 표시 정상 |
| **PSP 실기 (6.61 PRO-C / Inferno)** | **세이브·로드 정상, 텍스트 정상** |

---

## 5. 재현 빌드

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH='workspace/scripts'

# 1) BOOT UI 폰트·슬롯 산출물
python .\workspace\scripts\build_boot_ui_runtime_patch.py `
  .\workspace\config\demo00_production_profile.json `
  .\workspace\text\boot_ui_translation.json `
  .\work\analysis\demo00_boot_ui_fixed_font_reclaim.json `
  '..\..\Font\HancomMalangMalang-Regular.ttf' `
  .\work\production\demo00\font.fnt .\work\production\demo00\font.txp `
  .\work\production\demo00\hangul_mapping.json `
  .\extracted\PSP_GAME\SYSDIR\BOOT.BIN `
  .\work\builds\direct_run_boot_ui_full_20260729 `
  --extra-text .\workspace\text\translation\stage_info.csv `
  --extra-text .\workspace\text\translation\lucky_doll.csv `
  --extra-text .\workspace\text\translation\clear_time.json `
  --extra-text .\workspace\text\translation\picture_book_ko_translated.csv `
  --extra-text .\workspace\text\translation\lucky_item_ko_translated.csv `
  --extra-text .\workspace\text\translation\collection_ko_translated.csv `
  --extra-text .\workspace\text\translation\honor_ko_translated.csv `
  --extra-text .\workspace\text\translation\music_shop_ko_translated.csv

# 2) 직접 실행 트리 (정식 모드: native_reveal)
python .\workspace\scripts\build_direct_run.py `
  --boot-ui-dir .\work\builds\direct_run_boot_ui_full_20260729 `
  --renderer-cache-mode native_reveal --replace

# 3) 최종 ISO
python .\workspace\scripts\build_final_iso.py `
  --output .\work\production\Prinny_ULJS00150_KR_Final_20260729.iso
```

`build_final_iso.py`는 원본 ISO 사본에 변경 파일 5개
(`BOOT.BIN`, `EBOOT.BIN`, `ANIME.DAT`, `BG.DAT`, `SYSTEM.DAT`)만 **제자리 치환**한다.
전부 원본 extent 안에 들어가므로 extent 이동이 없다.
`--only <NAME>`으로 일부 파일만 교체한 진단용 ISO를 만들 수 있다.

원본 ISO(`original/`)와 추출 트리(`extracted/`)가 모두 있어야 빌드된다.
추출 트리가 없으면 원본에서 다시 추출한다 (`build_iso_production`의 ISO9660 리더 사용).

---

## 6. 핵심 기술 기록

프로젝트 후반부에서 확인한, 재현하려면 반드시 알아야 하는 사항들.

### 6.1 PPSSPP 개발 빌드 회귀 (에뮬레이터 문제)

설정 화면 설명문이 항목과 어긋나 섞여 보이던 증상은 **패치가 아니라
PPSSPP v1.20.4-426-gae13b9b3e1의 회귀 버그**였다. 무패치 원본에서도,
Vulkan/OpenGL 양쪽에서도, 텍스처 교체 ON/OFF 양쪽에서도 재현되고
정식판 1.19.3에서는 재현되지 않는다.

GE 덤프 분석 결과 게임이 제출하는 문자열·atlas 비트맵·UV는 선택마다 정상적으로
바뀌므로, 원인은 백엔드 공통 텍스처 캐시 무효화 경로에 있다.

> 교훈: 에뮬레이터 버전을 대조군으로 두지 않으면 패치 쪽을 무한히 의심하게 된다.

### 6.2 NISPACK 컨테이너는 섹터 정렬·크기 체인을 보존해야 한다

원본 `SYSTEM.DAT`은 모든 멤버가 2048바이트 UMD 섹터에 정렬돼 있고
`align(offset + size, 2048) == 다음 멤버 offset` 관계가 성립한다.
재압축으로 `start.lzs`가 작아지면 이 관계가 깨진다.

→ `replace_nispack_in_place()`로 **모든 멤버를 원본 오프셋에 고정**하고,
`start.lzs`는 **원본 압축 크기까지 0으로 패딩**해 저장 크기까지 일치시킨다
(LZS 헤더가 자체 압축 크기를 가지므로 뒤쪽 0은 디코딩되지 않는다).
결과적으로 `SYSTEM.DAT`은 원본과 크기·배치가 완전히 동일하다.

### 6.3 실기 세이브 실패의 진짜 원인 — SFO 문자열

PSP 세이브 목록의 제목·항목명·설명문은 게임이 만들어 펌웨어에 넘긴다.
이 문자열을 한글로 바꾸면 **실기에서 저장이 실패**한다
(로드는 기존 세이브의 SFO를 읽기만 하므로 정상 — 이 비대칭이 원인 특정의 결정타였다).

게임은 CP932 문자열을 `start.dat`의 `jis2ucs.bin`(JIS 코드로 인덱싱되는
65,536×2바이트 표)으로 유니코드 변환해 넘기는데, 우리 한글이 쓰는
CP932 사용자 정의 영역은 이 표에서 U+0000으로 떨어진다.

대응:

- `jis2ucs.bin` / `ucs2jis.bin`에 한글 987자 매핑을 추가 (해당 자리는 원본에서
  전부 0이라 충돌 0건, 일본어 매핑 불변)
- 그럼에도 실기 저장이 실패해, **세이브 SFO 소스 슬롯 21개는 일본어 원문 유지**
  (제목 `0x0ED324`, 설명문 포맷 `0x0F0AA4`/`0x0F0C54`,
  `残り○魔時間` 10종 `0x0F0ADC~0x0F0B6C`, 난이도 이름 2종, 항목명 6종)

관련 구조 (BOOT.BIN):

```text
savedata param 구조체 = 0x08938A68 (base.size = 1536, memset 1712)
  +0x5DC key[16]        게임이 0x08836E88에서 16바이트 memcpy
  +0x5EC secureVersion  0x08836E98에서 0으로 설정
InitStart 호출 0x08837390 / 스텁 0x088D03D4
이 게임은 암호화(보안) 세이브를 사용한다 (PARAM.SFO의 SAVEDATA_PARAMS 확인)
```

### 6.4 평문 EBOOT는 문제가 아니다

원본 `EBOOT.BIN`은 `~PSP` 암호화본이고 `BOOT.BIN`은 그 평문 ELF다.
패치는 두 파일 모두 평문 ELF로 교체하는데, **실기는 `EBOOT.BIN`을 로드한다**
(`BOOT.BIN`만 패치하면 게임이 전혀 바뀌지 않는다).

수정 없이 복호화만 한 ELF로 교체한 대조군에서 세이브가 정상이므로
**평문 EBOOT 자체는 무해하다.** PrxEncrypter·KIRK 재암호화·가짜 서명은 불필요하다.

### 6.5 코드 케이브와 대사 타자 효과

한글은 CP932에서 2바이트지만 번역문에는 1바이트 ASCII 공백·문장부호가 섞인다.
게임 원본의 점진 표시(타자 효과) 루프는 `strlen/2`로 글자 수를 세고
`글자수×2바이트`를 복사하는 순수 2바이트 전제라, 표시 도중 한글 문자가
반쪽만 그려져 엉뚱한 글자가 스친다.

`.rodata.sceNid` 끝 패딩(0x088D0DCC, NID 배열 끝과 정확히 접함)에 CP932 완전
문자 단위 카운트/복사 헬퍼를 넣어 해결한다(`--renderer-cache-mode native_reveal`).

⚠️ 이 헬퍼는 **복사할 바이트 외에는 아무것도 건드리면 안 된다.**
초기 구현이 목적지에서 41바이트를 무조건 0으로 지우고 있었고, 이것이 인접
메모리를 파괴해 실기 세이브를 깨뜨렸다. 현재는 복사 종료 지점에 NUL만 쓴다.

### 6.6 감사 도구의 함정

- 잔여 일본어 감사가 `str.isprintable()`로 걸러 **전각 공백(U+3000)이 들어간
  문자열을 전부 놓치고 있었다.** 수정 후 숨어 있던 미번역 30건이 드러났다.
- 폰트 글리프 회수 감사는 데이터 구동 화면이 쓰는 **CP932 기호 행(0x81)**을
  보호하지 않아, 시간 구분 기호 `′`/`″`의 글리프를 한글이 차지해 기록 화면이
  깨졌다. 현재는 0x81 행 188코드를 회수 금지로 예약한다.
- `PictureBook.dat` 같은 표를 전량 교체할 때는 회수 감사에
  `--scan-override`로 "번역 후 사라질 원문"을 알려야 글리프가 부족하지 않다.

### 6.7 실기 디버깅 방법론

실기 테스트는 1회당 비용이 크므로 **분리 실험**으로 접근했다.
`build_final_iso.py --only`로 교체 파일을 조합한 진단 ISO를 만들어
`원본 → 실행파일만 → 데이터만 → 조합` 순으로 좁혔다.

주의할 점 두 가지:

1. **메모리스틱의 세이브 폴더를 매 테스트 전에 지워야 한다.** 남아 있으면
   이후 어떤 빌드로 실행해도 결과가 오염돼 논리적으로 모순된 결과가 나온다
   (실제로 이 때문에 여러 라운드를 낭비했다).
2. **진단 빌드가 검증하려는 변수를 실제로 포함하는지 확인해야 한다.**
   중반의 진단 빌드들이 한글 텍스트가 빠진 실행파일이라 "실행파일 무죄" 판정이
   실제로는 성립하지 않았고, 원인 특정이 늦어졌다.

---

## 7. 프로젝트 구조

```text
├─ docs/          결론·포맷·빌드·QA·결정 기록, 작업 인계서
├─ original/      원본 ISO (읽기 전용)
├─ extracted/     ISO 추출 트리 (읽기 전용)
├─ workspace/
│  ├─ scripts/    추출·번역 삽입·빌드·감사 도구
│  ├─ config/     지원 원본 기준선, 생산 프로파일
│  ├─ text/       번역 SSOT (JSON/CSV)
│  └─ tests/      자동 검증
├─ work/          재생성 가능한 중간 산출물·분석·백업
└─ dist/          배포 패키지
```

### 주요 문서

- [`docs/HANDOFF_2026-07-28.md`](docs/HANDOFF_2026-07-28.md) — **최종 작업 인계서.**
  PPSSPP 회귀 판정부터 실기 세이브 해결까지 전 과정의 실험·판정·수정 기록
- [`docs/HANDOFF_2026-07-26.md`](docs/HANDOFF_2026-07-26.md) — 그 이전 구간 인계서
- [`docs/build.md`](docs/build.md) — 빌드 명령과 파이프라인
- [`docs/format.md`](docs/format.md) — NISPACK/LZS/start.dat 실측 구조
- [`docs/graphics.md`](docs/graphics.md) — 화면 텍스트의 그래픽/동적 분류
- [`docs/qa.md`](docs/qa.md) — 검증 항목
- [`docs/decisions.md`](docs/decisions.md) — 구조·도구·증거 처리 결정
- [`docs/dlc-survey.md`](docs/dlc-survey.md) — DLC DIDT0/DDEM/DSTI 기준선과 후속 게이트

---

## 8. 남은 백로그 (선택 사항)

| 항목 | 내용 |
| --- | --- |
| GM3/NFG20 리버싱 | `STAGE.DAT` 포맷 해석 → 스테이지 HUD 완전 ISO화 (실기에서도 한글화). 수일 규모 |
| PPSSPP 업스트림 보고 | dev 빌드 텍스처 캐시 회귀 + 종료 시 멈춤 버그 |
| 테스트 경로 정리 | 삭제된 구 빌드 폴더를 참조하는 자동 테스트 2건 |
| 타이틀 선택지 배치 | 스프라이트 UV 테이블 리버싱으로 미세 정렬 |
| 용어 통일 잔여 | `星影`(호시카게 vs BOOT UI의 "별빛") |
| DLC | `ms0:/PSP/GAME/ULJS00150/DL%04d.EDAT`의 `DDEM` 메시지 52건은 별도 모집단 |

---

## 9. 원칙

- 원본 ISO와 `extracted` 트리는 수정하지 않는다.
- 정적 빌드 성공만으로 런타임 성공을 선언하지 않는다. 실기·에뮬레이터 화면 확인이 정본이다.
- 확인되지 않은 포맷 수치나 다른 NIS 게임의 구조를 이 게임의 사양으로 쓰지 않는다.
- 확정 사실 / 기각된 가설 / 미검증 가설을 문서에서 분리한다.
