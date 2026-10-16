# 파일·포맷 조사

이 문서는 현재 리비전에서 직접 확인한 값만 ‘확정’으로 적고, 아직 소비 코드로 검증하지 않은 구조는 ‘관찰’ 또는 ‘가설’로 표시한다.

## 1. PSP 파일 트리

```text
extracted/
├─ UMD_DATA.BIN
└─ PSP_GAME/
   ├─ PARAM.SFO
   ├─ ICON0.PNG / PIC0.PNG / PIC1.PNG
   ├─ SYSDIR/
   │  ├─ BOOT.BIN            # 평문 MIPS ELF
   │  ├─ EBOOT.BIN           # ~PSP 컨테이너
   │  └─ UPDATE/
   └─ USRDIR/
      ├─ ANIME.DAT
      ├─ BG.DAT
      ├─ SCRIPT.DAT
      ├─ SOUND.DAT
      ├─ STAGE.DAT
      └─ SYSTEM.DAT
```

`BOOT.BIN`에서 `script.dat`, `system.dat`, `stage.dat`, `sound.dat`, `font.fnt`, `font.txp`, `demo.nsf`, `system.nsf` 등의 소비 파일명 문자열이 확인된다.

## 2. NISPACK

### 2.1 확인된 헤더와 엔트리

모든 값은 리틀엔디언이다.

```text
0x00  12 bytes  signature = "NISPACK\0\0\0\0\0"
0x0C   4 bytes  entry_count
0x10  entry_count × 44 bytes

entry:
+0x00  32 bytes  NUL 종료 ASCII 파일명
+0x20   4 bytes  data_offset
+0x24   4 bytes  data_size
+0x28   4 bytes  unknown
```

마지막 4바이트는 공개 도구도 건너뛰지만 원본에는 0이 아닌 값이 존재한다. 의미가 확정될 때까지 삭제·재계산·0 초기화하지 않는다.

### 2.2 아카이브 인벤토리

| 아카이브 | 크기 | 항목 수 | 내부 형식 |
| --- | ---: | ---: | --- |
| `ANIME.DAT` | 27,827,616 | 28 | `.dat` 28개 |
| `BG.DAT` | 20,573,200 | 155 | `.txp` 155개 |
| `SCRIPT.DAT` | 843,800 | 7 | `.nsf` 7개 |
| `STAGE.DAT` | 155,647,296 | 316 | `.dat` 159개, `.GM3` 157개 |
| `SYSTEM.DAT` | 4,127,307 | 7 | DAT, PNG, LZS |

총 513개 엔트리의 범위가 파일 안에 있고 서로 겹치지 않음을 확인했다.

### 2.3 SCRIPT.DAT

| 인덱스 | 이름 | 오프셋 | 크기 |
| ---: | --- | ---: | ---: |
| 0 | `debug.nsf` | `0x00000800` | 1,013 |
| 1 | `demo.nsf` | `0x00001000` | 211,840 |
| 2 | `DL000.nsf` | `0x00035000` | 310 |
| 3 | `effect.nsf` | `0x00035800` | 1,364 |
| 4 | `enemy.nsf` | `0x00036000` | 601,160 |
| 5 | `preview.nsf` | `0x000C9000` | 5,258 |
| 6 | `system.nsf` | `0x000CA800` | 14,360 |

NSF의 선두는 공통 파일 시그니처 문자열이 아니라 정수 필드처럼 보인다. 일반 Shift-JIS 스캔은 온전한 대사 표본을 만들지 못했다. 포맷과 소비 의미는 미확정이다.

### 2.4 SYSTEM.DAT

| 이름 | 오프셋 | 크기 | 선두 |
| --- | ---: | ---: | --- |
| `replay.dat` | `0x00000800` | 230,832 | 미확정 바이너리 |
| `REPLAY_ICON0.PNG` | `0x00039000` | 11,892 | PNG |
| `UMD_ICON0.PNG` | `0x0003C000` | 20,047 | PNG |
| `UMD_PIC0.PNG` | `0x00041000` | 60,594 | PNG |
| `start.lzs` | `0x00050000` | 3,630,771 | NIS LZS |
| `UMD_PIC1.PNG` | `0x003C6800` | 161,365 | PNG |
| `PRINNY_ICON0.PNG` | `0x003EE000` | 6,731 | PNG |

## 3. NIS LZS

확인한 `start.lzs` 헤더:

```text
0x00  4 bytes  output extension marker: "dat\0"
0x04  u32      decompressed size: 9,030,752
0x08  u32      stored size field: 3,630,767
0x0C  u32      escape flag: 0xD5
0x10  ...      encoded stream
```

저장 크기 필드는 실제 파일 크기보다 4 작다. 해제 스트림은 리터럴, 플래그 이스케이프, 거리·길이 역참조로 구성된다. `workspace/scripts/decompress_nis_lzs.py`는 입력 범위, 역참조 거리, 선언 출력 크기를 검증한다.

`compress_nis_lzs.py`는 최소 일치 4바이트, 거리·길이 최대 254, 비중첩 역참조(`length <= distance`), 플래그 리터럴 이중 기록 규칙으로 결정적 최장 일치를 수행한다. 원본 `start.dat` 재압축 결과는 3,630,771바이트와 SHA-256 `2242dee86aefd0a1ee91a9092ee9525986431027943a544622c5c5e50ab5a58c`가 원본 `start.lzs`와 바이트 단위로 동일하다. PoC `start.dat`은 3,630,811바이트의 `start.lzs`로 압축되며 다시 풀었을 때 SHA-256 `bf60516243264da1d221859e1315cbf8d5b2cf02c6bacbc0b209779e0c1c526e`가 복원된다.

PoC `start.lzs`는 원본보다 40바이트 크지만 `SYSTEM.DAT`의 다음 항목 `UMD_PIC1.PNG` 전까지 있던 333바이트 0 패딩에 들어간다. `build_system_poc.py`는 `start.lzs` 크기 필드 `0xE4..0xE7`과 고정 할당 영역 `0x50000..0x3C67FF`만 소유하고, 다른 6개 항목의 오프셋·메타데이터·내용과 전체 파일 크기 4,127,307바이트를 보존한다. 출력 SHA-256은 `41c9fbb6049e74fb28d1f8e429146a053bfd2e5ffa86f8b17a3b52c000cf9892`다.

원본 ISO의 Primary Volume Descriptor와 디렉터리 레코드를 따라가면 `/PSP_GAME/USRDIR/SYSTEM.DAT;1`은 LBA 218,144, 바이트 오프셋 `0x1AA10000`, 크기 4,127,307이다. PoC 파일이 같은 크기이므로 디렉터리 레코드와 모든 LBA를 유지한 채 이 extent만 바꾼다. 출력 ISO 크기는 500,465,664바이트, SHA-256은 `02883fd3c6fdfaac53be78a94975e8bfc3ee16ce689215146e5627b5b80b7a68`이다. PPSSPP Headless에서 이 ISO의 EBOOT·게임 모듈이 시작되고 `SYSTEM.DAT`가 열리는 것까지 확인했다. 내부 `font.txp`의 화면 소비는 별도 가시성 게이트다.

## 4. 해제된 start.dat

### 4.1 관찰된 인덱스

```text
0x00  u32      record_count = 182
0x04  u32      first_data_offset = 0x16D0
0x08  182 × 32-byte records

observed record:
+0x00  16 bytes  NUL 종료 ASCII 이름(종료자 뒤 잔여 바이트는 비정규)
+0x10  u32       unknown_0
+0x14  u32       unknown_1
+0x18  u32       unknown_2
+0x1C  u32       data_end (마지막 항목의 0은 EOF)
```

실제 파일 범위는 `start = 첫 항목이면 헤더 +0x04, 아니면 직전 항목의 data_end`, `end = 현재 항목의 data_end`다. 마지막 항목의 `data_end = 0`은 EOF `0x0089CC60`으로 해석한다. `BOOT.BIN`의 VA `0x0888B2D4` 부근 파일명 검색 루프가 항목 `i`의 이름을 `base + 8 + i×32`, 데이터 포인터를 `base + 4 + i×32`에서 읽어 이 한 칸 앞 경계를 직접 확인했다.

기존 조사기는 현재 항목의 `data_end`를 시작점으로 잘못 사용해 자산 이름을 한 항목씩 밀었다. 2026-07-17에 `inspect_start_dat.py`와 파생 자산을 정정했다. 세 `unknown_*` 필드와 정렬 패딩의 소유권은 여전히 미확정이다.

### 4.2 주요 항목

| 인덱스 | 이름 | 시작..끝 | 크기 |
| ---: | --- | --- | ---: |
| 1 | `font.fnt` | `0x0052DF20..0x005339E0` | 23,232 |
| 2 | `font.txp` | `0x005339E0..0x00583E40` | 328,800 |
| 34 | `WindowPos.dat` | `0x0078A270..0x0078A590` | 800 |
| 36 | `BaseTalk.dat` | `0x0078C260..0x0078C5B0` | 848 |
| 37 | `MusicShop.dat` | `0x0078C5B0..0x0078D080` | 2,768 |
| 45 | `PrinnyName.dat` | `0x0079EC30..0x0079F000` | 976 |
| 47 | `jis2ucs.bin` | `0x0079F210..0x007BF210` | 131,072 |
| 48 | `ucs2jis.bin` | `0x007BF210..0x007DF210` | 131,072 |

`start.dat`에는 전체적으로 `.txp` 157개, `.dat` 16개, `.bin` 2개, `.fnt` 1개, `.GM3` 1개와 일부 잘린/확장자 없는 이름이 관찰된다.

### 4.3 BaseTalk.dat

정정된 파일 크기는 848바이트, SHA-256은 `1275878dc82e86b152e8211dad040200a47faed50281b3a81fd6be58f14d1e6a`다. 전 파일을 다음 구조로 정확히 순회하고 `parse → serialize`가 바이트 단위로 동일함을 확인했다.

```text
0x0000  u16      record_count = 16
0x0002  u16      unknown_header = 0
0x0004  16 × 52-byte records
0x0344  12 bytes zero footer

record:
+0x00   u16      record_id
+0x02   u16      unknown (현재 모두 0)
+0x04   12 × u32 resource_key
```

레코드 ID는 `1..10, 22..27`이며 각 레코드의 12개 값은 `0x00C65D4A` 같은 리소스 키다. 소비 함수 `0x0883F844`, `0x0889EA60`은 이 값을 직접 역참조하지 않고 키 해석기 `0x08872558`에 전달한다. 해석기는 정렬된 키 배열을 이진 검색해 런타임 객체의 데이터 포인터를 설정한다.

`BOOT.BIN`의 `BaseTalk.dat` 직접 참조는 VA `0x0888B2D4` 한 곳에서 확인됐다. 공통 파일명 검색 호출 뒤 `0x0888B314`에서 `lhu`로 선두 16비트 수를 읽고, 본문 포인터를 데이터 시작 `+4`로 설정해 전역에 저장한다. 이 때문에 헤더는 `u32 count`가 아니라 `u16 count + u16 unknown_header`로 모델링한다.

두 전역을 읽는 코드 후보 VA `0x0883F92C`, `0x0889ED04`는 Capstone 5.0.7과 PPSSPP 양쪽에서 52바이트 보폭의 이진 검색으로 확인됐다. PPSSPP 1.20.4에서 로더 직후 전역 count는 16, 본문 포인터는 `0x0942DF24`였고, 포인터에서 읽은 844바이트는 디스크 `BaseTalk.dat`의 헤더 뒤 844바이트와 정확히 동일했다. 즉 92→52 런타임 변환은 없으며, 기존 충돌은 잘못 추출한 인접 파일을 `BaseTalk.dat`로 부른 데서 생겼다.

`demo.nsf`의 `+0x20`에는 531개의 정렬된 `<u32 key, u32 script_offset>` 쌍이 있다. 그 뒤에는 939개의 `<u32 start, u32 end>` 블록 레코드가 있으며 코드 영역은 파일 `+0x2E10`, 크기 `0x30D70`이다. 모든 키 오프셋은 선언된 블록 시작점과 일치한다. `script_offset`은 파일 절대 위치가 아니라 이 코드 영역 기준이다. BaseTalk의 고유 키 72개는 모두 이 표에서 해석되며, 예를 들어 `0x00C65D4A → logical 0x00029F28 → file 0x0002CD38`, `0x00C67C80 → logical 0x0002EC9C → file 0x00031AAC`다. 대상은 CP932 본문이 아니라 NSF 바이트코드다. `workspace/scripts/base_talk.py`와 `nsf_links.py`가 레이아웃과 전수 해석을 검증한다.

### 4.4 Demo00.dat 메시지 표

파일 크기는 207,520바이트, SHA-256은 `5db04fe85175e01e14d9abfef5a2817c85c3987c4b76ba33bad39651df60b01d`다.

```text
0x0000  u32      record_count = 1572
0x0004  1572 × 132-byte records
0x32A94 12 bytes zero footer

record:
+0x00   u16      message_id (오름차순)
+0x02   u8       layout_variant (BOOT 분기표 0..17, 관찰값 1..17)
+0x03   u8       reserved_3 (관찰값은 모두 0)
+0x04   s16      face_asset_signed (abs(value) = wf_%04d.txp ID)
+0x06   u8       speaker_box_style (0/200/201/202)
+0x07   17 bytes CP932/NUL 화자 슬롯
+0x18   35 bytes CP932/NUL 본문 1
+0x3B   35 bytes CP932/NUL 본문 2
+0x5E   35 bytes CP932/NUL 본문 3
+0x81   3 bytes  zero tail
```

`BOOT.BIN` 함수 `0x08862F90`은 두 메시지 표를 순서대로 이진 검색하며 `index × 132`를 계산한다. 표시 구성 시 본문 포인터 `record+0x18`, `+0x3B`, `+0x5E`를 직접 넘기고, `+0x06`이 0이 아니면 화자 포인터 `record+0x07`도 사용한다. `+0x02`는 18개 엔트리의 점프 테이블을 골라 대화창 좌표·크기를 구성하므로 레이아웃 변형 번호다. 관찰 분포는 1~17이며 0은 사용되지 않았다.

`+0x04`의 0이 아닌 절댓값 고유 120개는 모두 `start.dat`의 `wf_%04d.txp` 120개와 일치한다. 따라서 얼굴 자산 선택값으로 판정하지만 양수·음수의 정확한 방향 또는 반전 의미는 아직 미확정이다. 0은 324건이다. `+0x06`은 0이면 빈 화자 슬롯 182건이며, 200은 2~4자 1,048건, 201은 5~6자 310건, 202는 7~8자 32건으로 예외 없이 이름 길이 단계와 대응한다. 이는 명패 폭/스타일 단계다.

`workspace/scripts/demo00.py`는 엄격 CP932·NUL 패딩·정렬 ID·zero tail/footer를 검사하고 원본을 바이트 동일하게 왕복한다. `demo00_controls.py`는 위 분포와 얼굴 자산 대응을 검증한다. 번역 writer는 `layout_variant`, `reserved_3`, `face_asset_signed`, `speaker_box_style`을 기본적으로 원문 그대로 보존한다. 특히 한글 화자명은 글자 수가 아니라 실제 렌더 폭을 검증하기 전까지 명패 단계를 자동 재계산하지 않는다.

`workspace/text/demo00_translation.json`은 이 표의 전량 번역 아티팩트다. 논리 ID는 메시지 ID에 기반한 `demo00/XXXX`이며 인덱스·파일 오프셋은 별도 물리 좌표다. 각 항목의 `protected`에는 원본 132바이트, 네 제어값, tail, 원문 화자와 세 본문 슬롯을 저장하고 `translation`의 화자·본문·상태·메모·플래그만 편집한다. 상태는 `untranslated`, `in_progress`, `needs_review`, `needs_human_review`, `complete` 중 하나다. 고정 슬롯 정책은 유지하지만 생산용 한글 인코딩이 미승인인 현재는 역문을 바이너리에 쓰지 않는다. 원문 기준 재조립은 바이트 완전 동일해야 한다.

NSF VM 메시지 명령은 전체 opcode `42 01`, `42 02`, `42 03`이며 각각 핸들러 `0x08879060`, `0x08879100`, `0x08879238`에 대응한다. 공통 피연산자 해석기 `0x08872DBC`는 태그 `0=변수 참조`, `1=s8`, `2=s16 LE`, `3=s24 LE`, `4=u32 LE`를 소비한다. `42 01`은 태그형 메시지 ID를, `42 02/03`은 리터럴 u32 메시지 ID를 사용한다. 세 핸들러 모두 표시 래퍼 `0x08867CFC`를 거쳐 조회 함수 `0x08862F90`에 ID를 전달한다.

`workspace/scripts/nsf_messages.py`는 확정 코드 영역에서 이 세 명령의 소비 형식과 일치하는 후보를 카탈로그화한다. 현재 `Demo00` ID와 일치하는 정적 후보 1,481건(고유 ID 1,378개), 동적 ID 5건, 미해결 54건이다. 이는 전체 명령 경계와 분기 도달성을 아직 파싱하지 않은 **후보 모집단**이며, 전량 참조나 실행 도달을 뜻하지 않는다. 원시 명령 바이트와 논리/파일 오프셋을 보존하며 미해결·동적 항목은 번역 입력으로 승격하지 않는다.

`workspace/scripts/nsf_reachability.py`는 `BOOT.BIN`의 실제 디스패처 `0x088825B0`과 핸들러 테이블을 Unicorn MIPS로 실행해 각 블록에서 저장 PC가 다음 명령으로 전진하는지 검사한다. 400개 후보 포함 블록 중 282개를 오류 없이 순회했고 다음 명령 시작점을 증명했다.

- Demo00: 1,377건, 고유 ID 1,366개
- 동적 ID: 2건
- Demo00에 없는 리터럴: 52건
- 로컬 미증명: Demo00 104건, 동적 3건, 비정상 리터럴 패턴 2건

`unproven`은 거짓양성이 아니라 더미 외부 상태와 제한된 분기 시드로는 블록 안에서 도달하지 못했다는 뜻이다. 특히 리터럴 52건은 실제 명령 시작점으로 승격됐지만 대상 메시지 표는 미확정이다. 번역 참조 분모 승격에는 남은 항목의 PPSSPP 실행 PC 대조가 필요하다.

`workspace/scripts/ppsspp_nsf_trace.py`는 세 메시지 핸들러의 실제 적중을 수집한다. 핸들러 진입 시 `a1`은 VM 객체, `a3`은 런타임 NSF 코드 기준 주소이며 `u32[a1+0x48]`는 2바이트 opcode 직후의 저장 PC다. 따라서 논리 명령 시작점은 `saved_pc - 2`, 채널/메시지 피연산자는 `a3 + saved_pc`에서 읽는다. 이 관계로 런타임 주소 재배치와 무관하게 정적 후보 오프셋과 직접 대조할 수 있다.

`ppsspp_demo00_target_trace.py`는 같은 ABI를 이용하되 지정 ID만 보존하고, ID 적중과 예상 논리 오프셋 적중을 분리한다. `0x00E6`이 다른 오프셋에서 호출된 것과 `enemy.nsf + 0x1851C`에서 호출된 것을 같은 증거로 합치지 않는다. 주소가 읽히기만 한 경우도 메시지 소비로 세지 않으며, 세 핸들러가 실제로 피연산자를 해석한 시점만 기록한다.

부팅·타이틀 자동 진행 90초 관찰에서는 적중이 없었다. 런타임 추적은 양성 적중만 실행 증거로 취급하며, 미적중은 코드 미사용이나 거짓양성 판정에 사용하지 않는다.

#### 메시지 표 슬롯과 DLC DDEM

조회 함수의 표 배열은 전역 `0x08A2A15C`부터 8바이트씩 두 슬롯이다. 설정 함수 `0x08862B54`는 `slot × 8` 위치에 `u16 count`와 입력 `+4`의 레코드 포인터를 저장한다.

- 슬롯 0: 부팅 로더 `0x0888B864`가 `Demo00.dat`를 설정한다.
- 슬롯 1: 외부 컨테이너 파서 `0x088CF28C`가 `DDEM` 청크를 설정한다.
- 슬롯 1 해제: `0x088CF504`가 count와 포인터를 0으로 지운다.
- 컨테이너 경로: `ms0:/PSP/GAME/%s/DL%04d.EDAT`, `%s`의 지원 리비전 값은 `ULJS00150`이다.

블록 로컬 명령 시작점으로 증명된 Demo00 미일치 52건은 모두 `42 01`, 태그 4의 u32 ID다. ID 분포는 `0x53FC..0x5428`의 짝수 23개와 `0x55F0..0x5628`의 짝수 29개다. Demo00 검색 실패 뒤 슬롯 1을 검색하므로 실행 시 소유자는 DDEM이다. 기본 ISO에는 EDAT 입력이 없으므로 기본 ISO 번역 모집단에서 분리하고, DLC 지원 시 별도 입력·해시·추출·왕복 게이트를 연다.

### 4.5 MusicShop.dat와 BGM 문자열

기존에 `BaseTalk.dat`로 기록했던 2,768바이트 CP932 표는 실제 `MusicShop.dat`다. SHA-256은 `9610d46931f27e732a7b28b5be4498ce16289ef87a84c03e9350a4d6786cc1f5`이며 구조는 `u16 count=30 + u16 unknown + 30 × 92-byte record + u32 zero footer`다. 각 레코드에는 21바이트 CP932 키와 65바이트 CP932 표시명이 있다. `workspace/scripts/music_shop.py`와 단위 테스트가 기존의 엄격한 NUL·0 패딩·CP932·바이트 동일 왕복 검증을 이어받는다. 화면 소비자는 아직 확인하지 않았다.

`jis2ucs.bin`과 `ucs2jis.bin`은 모두 131,072바이트이며 65,536개의 little-endian `u16` 엔트리다. `ucs2jis[Unicode]`는 JIS 행·점 코드를 반환하고 `jis2ucs[JIS]`는 Unicode를 반환한다. 전자는 7,766개, 후자는 7,769개의 0이 아닌 엔트리를 가지며 canonical UCS 왕복 7,766개가 전부 일치한다. 세 중복 JIS 별칭은 `U+FF5E`, `U+2225`, `U+FF0D`다. `U+AC00..U+D7A3` 한글 음절의 `ucs2jis` 배정은 0개다.

### 4.6 본문 폰트 맵과 텍스처

`font.fnt`는 다음 구조다.

```text
+0x0000  u16       map_count = 11615
+0x0002  u16[11615] dense CP932 index -> glyph_id
```

단일 바이트 `0x20..0x7E`는 `byte-0x20`으로 인덱싱한다. 2바이트 문자는 lead가 `0x81..0x9F`이면 `lead-0x81`, `0xE0..0xFC`이면 `lead-0xC1`로 정규화한 뒤 `lead_index×192 + trail + 0x1F`를 사용한다. 맵 값은 `0..2347`을 정확히 모두 포함하며 0이 아닌 매핑 2,347개와 0/빈 매핑 9,268개다. 0은 공백과 미할당 코드가 공유하므로 값 0만 보고 가용 코드로 판정하지 않는다.

`font.txp`는 16바이트 헤더, 16색 RGBA 팔레트 64바이트, `0x50`부터 시작하는 328,720바이트 픽셀 데이터다. 헤더의 폭 20과 높이 32,872는 2,348개의 20×14 셀을 세로로 이어 붙인 크기이며 픽셀은 4bpp, 바이트 안에서 low nibble이 왼쪽 픽셀이다. 글리프당 140바이트다. `render_font_glyphs.py`로 `A/あ/ア/国/プリニー`를 복원해 자형과 nibble 순서를 확인했다.

BOOT는 `0x08898C90`에서 맵을 초기화하고 본문 렌더러 `0x08899698`에서 위 CP932 조밀 인덱스를 계산한다. 선택한 글리프의 14개 행을 행당 10바이트씩 256×256·4bpp 캐시에 복사한다. 캐시는 0x8000바이트 두 장이며 현재 페이지당 12열×18행=216글리프를 제한한다. 단일 셀과 4셀 PoC의 ISO 반영·부팅·실제 화면 표시를 완료했다. `Demo00.dat` ID `0x07D0`의 명패 `プリニー`가 `가각뾰힣`로, 본문 `うわー、ちこくッスー！！`의 두 `ー`가 `힣`로 표시되어 UI·명패·본문이 이 글리프 경로를 공유한다는 런타임 증거를 얻었다.

문자 전진 폭은 셀 폭 20px과 별개다. 일반 2바이트 문자는 `0x088997C0`에서 13px을 설정하고 ASCII 공백 `0x20`은 `0x08899760`의 `addiu s5,s5,13`으로 별도 처리된다. ASCII 공백만 6px로 줄인 후보는 실기에서 붙은 한글 음절의 넓은 자간을 해결하지 못했다. 후속 시험은 공백 6px와 일반 2바이트 문자 9px를 함께 적용하며, 이는 일본어에도 영향을 주는 임시 검증값이다. 생산 패치는 CP932 사용자 정의 한글 리드 바이트 `F0–F9`만 9px로 분기해야 한다.

대사 타자 효과 `0x088653A0..0x088653FC`는 원본에서 `strlen/2`를 글자 수로 쓰고 공개 글자 수에 다시 2를 곱해 복사한다. 이 규칙은 전부 2바이트인 일본어 문자열에는 맞지만 ASCII 공백·쉼표가 섞인 한글에서는 2바이트 코드 중간을 자른다. 시험 패치는 `0x088D0DCC`의 0 패딩에 CP932 lead `0x81..0x9F`, `0xE0..0xFC`를 판별하는 논리 글자 수/완전 prefix 복사 함수를 두고, 기존 `count*2` 후행 종료 쓰기를 제거한다.

렌더러 `0x08899948..0x08899968`에도 독립된 혼합 폭 결함이 있다. 원본은 ASCII 영문자·숫자와 일부 하드코딩 문장부호만 단일 바이트로 처리하고 나머지는 다음 바이트와 결합한다. v2는 모든 `0x00..0x7F`를 단일 바이트로 보내고 비 ASCII에 대해서만 기존 CP932 lead 범위를 계산하며, prefix 복사기는 0x29바이트 줄 버퍼를 먼저 0으로 채운다.

한글 렌더 프로파일 `workspace/config/font_profile.json`은 `HancomMalangMalang-Regular.ttf`의 고정 해시, 13px 래스터화, 가로 1.4배, 20×14 중앙 배치, 밝기 0~8 양자화와 low-nibble-first 패킹을 선언한다. TTF cmap 감사에서 modern Hangul `U+AC00..U+D7A3` 11,172개가 모두 존재한다. 같은 범위의 설정상 경계 감사 결과 최대 17×14, 셀 초과 0개다. 이 프로파일은 현재 본문 가시성 PoC용이며 다른 UI 경로나 최종 조판 승인으로 일반화하지 않는다.

2026-07-17 제공된 한컴 서체 사용범위 표는 게임기 등 디바이스 내 탑재와 폰트파일 임베딩을 모두 허용한다. 따라서 게임 데이터에 변환된 4bpp 비트맵을 넣는 경로는 허용 범위로 기록한다. 원본 TTF는 빌드 입력으로만 사용하고 패치 산출물에는 포함하지 않는다.

`POC-FONT-VIS-001`의 Expected Write는 원본 `font.txp`의 글리프 371 셀 `0xCB34..0xCBBF` 140바이트뿐이다. 실제 변경은 그 안의 79바이트이며 파일 크기 328,800바이트와 `font.fnt`는 그대로다. PoC 출력 `font.txp` SHA-256은 `06ef321b22d6c15d9adae9ded4851118cf36179d2515fda281976d4c76a6feaa`다.

`PrinnyName.dat`는 다음 고정 구조로 확인했다.

```text
+0x0000  u32            count = 48
+0x0004  record[48]     20 bytes each
           +0x00 u16    1-based ID
           +0x02 char[18] NUL-terminated, zero-padded CP932 name
+0x03C4  byte[12]       zero footer
```

`POC-FONT-MULTI-001`은 원본 텍스트를 바꾸지 않고 `font.txp`의 네 글리프 셀만 교체한다.

| CP932 | 원문 | dense index | glyph | 한글 | 셀 범위 |
| --- | --- | ---: | ---: | --- | --- |
| `8376` | `プ` | 533 | 371 | `가` | `0xCB34..0xCBBF` |
| `838A` | `リ` | 553 | 390 | `각` | `0xD598..0xD623` |
| `836A` | `ニ` | 521 | 359 | `뾰` | `0xC4A4..0xC52F` |
| `815B` | `ー` | 122 | 110 | `힣` | `0x3C78..0x3D03` |

네 셀은 겹치지 않으며 선언 560바이트 중 305바이트가 실제로 달라진다. 이는 시험 전용 전역 교체다. `audit_cp932_usage.py`가 보고한 제한 모집단 미사용 코드 1,176개는 전체 소비자 조사가 끝날 때까지 생산용 예약으로 간주하지 않는다.

`POC-DIALOG-E2E-001`은 인덱스 291, ID `0x07D0`, 파일 오프셋 `0x9610`의 레코드 하나만 편집한다. 화자 슬롯은 `0x9617..0x9627`, 본문 1 슬롯은 `0x9628..0x964A`이며 끝 위치는 포함하지 않는다. 본문 2·3은 빈 상태를 유지한다. 원문 132바이트와 제어 메타데이터를 고정한 뒤 화자 `프리니`, 본문 `우와、지각했다！！`를 아래 시험용 프록시로 인코딩한다.

| 원문 코드 문자 | 시험용 한글 |
| --- | --- |
| `プ/リ/ニ` | `프/리/니` |
| `う/わ` | `우/와` |
| `ち/こ/く/ッ` | `지/각/했/다` |

레코드에 기록되는 프록시는 `プリニ` / `うわ、ちこくッ！！`다. 이 방식은 원래 CP932 바이트 수와 고정 슬롯을 유지하지만 같은 일본어 문자의 다른 출현도 바꾸므로 시험 전용이다. `build_demo00_poc.py`는 화자·본문 슬롯 외 바이트가 달라지면 실패하고, `build_start_dialog_poc.py`는 `font.txp`와 `Demo00.dat` 엔트리 밖의 변경을 거부한다.

2026-07-17 PPSSPP 실제 화면에서 이 레코드의 명패 `프리니`와 본문 `우와、지각했다！！`가 정상 표시되고 대화가 진행됐다. 따라서 고정 레코드→CP932 프록시→`font.fnt` 맵→교체 글리프→본문 캐시의 단일 대화 소비 경로는 런타임 PASS다. 같은 코드가 들어간 다른 일본어 UI도 한글로 바뀌었으므로 공유 슬롯의 전역 치환은 생산용 인코딩으로 사용할 수 없다.

### 4.7 생산용 코드·글리프 후보 예산

렌더러의 단일 바이트 `0x20..0x7E`와 유효 CP932 lead/trail 조합을 `font.fnt` 범위 안에서 전수 순회하면 엔진 코드 후보는 11,375개다. 이 중 2,347개가 비공백 글리프에 연결되고 9,028개는 값 0의 빈 매핑이다. 새 한글 코드는 빈 매핑을 사용할 수 있지만 픽셀을 위해 별도 글리프 ID가 필요하다.

확정 구조 텍스트 1,171코드, 12개 데이터 표와 `BOOT.BIN`의 보수적 후보, 런타임 UI 보호용 ASCII 95개를 예약하면 기존 비공백 글리프 중 회수 후보는 726개다. 따라서 `font.txp` 크기와 글리프 수를 유지하는 설계의 현재 신규 글리프 후보 상한은 726개다. 이는 코드→글리프 참조만 계산한 후보이며 비텍스트 참조·DLC·저장·미확정 소비자와 실제 한국어 코퍼스가 확정되기 전에는 생산 사양이 아니다.

## 5. 기타 아카이브

### 5.1 TXP와 ANIME 텍스처

독립 TXP 헤더는 16바이트 `<8H>`이며 관찰 필드는 `width, height, format, unknown, palette_width, palette_height, swizzled, flags` 순서다. `format=0x0010`은 4bpp indexed, `0x0100`은 8bpp indexed이고 팔레트는 RGBA8888이다. 4bpp 선형 픽셀은 왼쪽 픽셀이 low nibble이며, `swizzled=1`은 PSP의 16바이트×8행 블록 순서를 사용한다. `BG.DAT` 155개와 `start.dat` 157개에서 선언 크기와 실제 payload가 모두 일치했다.

ANIME 엔트리는 16바이트 외부 헤더 뒤에 가변 크기 레코드가 연속된다. 레코드 `+0x00`의 u32가 레코드 크기이고 `+0x24`의 세 u32는 팔레트 descriptor 시작, 텍스처 descriptor 시작, 텍스처 descriptor 끝이다. 팔레트 descriptor는 `<II>(offset, color_count)`, 텍스처 descriptor는 `<IHH4B>(offset, width, height, bpp, clut_width, clut_height, swizzled)`다. `ANIME.DAT` 156레코드·458텍스처와 `start.dat/anime00.dat` 89레코드·179텍스처에서 descriptor·팔레트·픽셀 span과 엔트리 끝이 정확히 닫혔다.

- `BG.DAT`: 각 TXP의 관찰 크기가 대부분 132,112바이트이며 선두가 공통적이다. 그래픽 텍스트 여부는 미조사다.
- `STAGE.DAT`: `mappack*.dat`은 `NFG20` 문자열로 시작하고 `st*.GM3`은 별도 바이너리 구조다.
- `ANIME.DAT`: 내부 `anime*.dat`은 각기 다른 크기와 작은 정수 선두를 가진다.
- `SOUND.DAT`: `NISPACK`이 아니며 선두 32-bit 값은 `4`다. 현 단계 한글화 핵심 경로가 아니므로 형식 판정을 보류한다.

## 6. 현재 도구의 신뢰 경계

| 도구 | 가능한 것 | 아직 주장하지 않는 것 |
| --- | --- | --- |
| `inspect_nispack.py` | 시그니처·테이블·범위·겹침 검증, 엔트리 추출 | 마지막 필드 의미, 원본 동등 재패킹 |
| `decompress_nis_lzs.py` | 엄격한 LZS 해제와 크기 검증 | 게임 소비 호환성 |
| `compress_nis_lzs.py` | 결정적 LZS 압축·자기 왕복, 원본 스트림 바이트 동일 재현 | 물리 PSP 호환성 |
| `inspect_start_dat.py` | 로더와 일치하는 시작/끝 경계 검증·추출 | 세 미확정 필드 의미, 재패킹 |
| `find_sjis_candidates.py` | Shift-JIS처럼 보이는 바이트열 후보 생성 | 실제 텍스트 소비, 모집단 완전성 |
| `base_talk.py` | `BaseTalk.dat` 16 × 52바이트 엄격 파싱·JSON·왕복 | 키 슬롯 의미, 재삽입 |
| `nsf_links.py` | BaseTalk 키를 NSF 정렬 키 맵으로 전수 해석 | opcode 의미, 스크립트 재삽입 |
| `nsf_messages.py` | NSF 메시지 명령 형식 후보와 원시 바이트·ID 카탈로그 | 전체 명령 도달성, 동적·미해결 참조 소유자 |
| `nsf_reachability.py` | BOOT 디스패처 에뮬레이션으로 블록 로컬 명령 시작점 검증 | 실제 플레이 분기·외부 상태의 전수 도달성 |
| `demo00.py` | `Demo00.dat` 1,572 × 132바이트 CP932 슬롯 엄격 파싱·왕복 | 가변 길이·포인터 재배치 |
| `demo00_artifact.py` | Demo00 전량 번역 JSON 추출, 보호 필드·상태 검증, 원문 바이트 동일 재조립과 한글 수요 보고 | 생산용 한글 인코딩·다중 레코드 쓰기·슬롯 확장 |
| `demo00_batches.py` | 안정 ID 배치 추출, 보호 스냅샷·번역 충돌 검증, 편집 필드만 병합, 2바이트 한글 가정 슬롯 위험 보고 | 의미 검토·문체 승인, 생산용 인코딩 적합성, 실제 화면 조판 |
| `audit_demo00_population.py` | Demo00 반복 템플릿 패턴·7개 NSF·BOOT와 키 공급 증거를 교차 감사해 기본 ISO 대상 1,523/제외 49/미확정 0 보고 | DLC 입력이 추가될 때 별도 모집단 재개 |
| `build_demo00_poc.py` | 승인된 SSOT와 원본 레코드 지문을 검증하고 `0x07D0` 고정 슬롯만 재삽입 | 여러 레코드·슬롯 확장·생산용 인코딩 |
| `demo00_controls.py` | 레이아웃·얼굴 자산·명패 폭 단계 분포와 보존 정책 검증 | 얼굴 ID 부호의 화면 방향, 한글 명패 폭 재계산 |
| `music_shop.py` | `MusicShop.dat` 30 × 92바이트 CP932 슬롯 엄격 파싱·왕복 | 화면 소비, 번역 재삽입 |
| `ppsspp_basetalk_probe.py` | 로더 중단점·count·포인터·844바이트 런타임 덤프 | PPSSPP 실행/설정 자동화, 실기 동작 |
| `ppsspp_nsf_trace.py` | 메시지 핸들러 적중 시 NSF 논리 오프셋·채널·ID 복원 | 관찰하지 않은 분기의 미사용 판정, 동적 ID의 실행 후 평가값 |
| `ppsspp_demo00_target_trace.py` | 지정 Demo00 ID와 예상 NSF 논리 오프셋의 런타임 결합 판정 | 미적중 후보의 미사용·자유 공간 판정 |
| `audit_enemy_orphan_key.py` | Character 실제 레코드 구조와 BOOT 기본/DLC 슬롯·정확 ID 조회·`+0x3C` 루트 소비 계약을 검증해 기본 ISO 도달성 판정 | 적법한 DLC Character 입력이 추가될 때 슬롯 1 모집단 감사 |
| `message_table_owners.py` | 고정 BOOT 지문으로 Demo00/DDEM 슬롯 적재 경계 검증, 미해결 후보 분류 | EDAT 복호화·DDEM 본문 추출, DLC 배포 지원 |
| `font_assets.py` | 폰트 맵·TXP·JIS/UCS 표·BOOT 렌더 경로 지문 검증 | 전체 코퍼스의 안전한 재사용 코드와 한글 레퍼토리 예산 |
| `render_font_glyphs.py` | 20×14·4bpp 원본 글리프를 CP932 문자 기준 PNG로 복원 | 게임 화면 도달과 다른 렌더 경로의 동일성 |
| `build_font_poc.py` | 고정 TTF 해시·cmap·셀 경계를 검증하고 단일 Expected Write PoC 자산 생성 | ISO 반영과 PPSSPP 화면 판정 |
| `audit_cp932_usage.py` | Demo00·MusicShop·PrinnyName의 엄격 CP932 코드 사용량과 제한 모집단 미사용 후보 보고 | 전 게임·DLC·실행 파일을 포함한 생산용 안전 코드 확정 |
| `audit_cp932_allocation.py` | 확정 구조 코드, 데이터 표·BOOT 휴리스틱 예약, ASCII 정책 예약을 분리해 빈 코드와 회수 글리프의 보수적 예산 보고 | 휴리스틱 후보의 실제 소비, DLC·저장·비텍스트 참조, 생산용 매핑 승인 |
| `build_font_multi_poc.py` | 고정 프로파일의 서로 다른 복수 글리프 셀만 동일 크기로 교체하고 preview·Expected Write 보고 | 생산용 인코딩과 코드 충돌 부재 |
| `build_start_poc.py` | 고정 원본 해시·엔트리 경계를 검증하고 동일 크기 `font.txp`를 `start.dat`에 단일 소유자 diff로 주입 | 가변 크기 start.dat 재패킹 |
| `build_start_dialog_poc.py` | 고정 해시·경계의 `font.txp`와 `Demo00.dat` 두 엔트리만 결합 주입하고 전체 diff 소유권 검증 | 임의 엔트리 수와 가변 크기 재패킹 |
| `build_system_poc.py` | 고정 원본·대체 LZS 해시와 0 패딩을 검증하고 `SYSTEM.DAT` 고정 extent에 주입 | PPSSPP 대화 화면 판정 |
| `build_iso_poc.py` | ISO9660 경로·LBA·크기·해시를 검증하고 같은 크기 `SYSTEM.DAT`만 별도 ISO에 주입 | 가변 크기 ISO 재배치, 물리 PSP |
| `ppsspp_boot_probe.py` | Headless 로그에서 게임 ID·EBOOT·모듈·SYSTEM.DAT 열기·메인 루프 증거를 제한 수집 | 대화 글리프 캐시와 화면 가시성 |

### 6.4 생산 재패킹 결론

가변 `start.dat`·NISPACK·ISO 재패커는 인덱스·미확정 필드·비대상 payload를 보존하고 이동 컨테이너 대조군의 PPSSPP 부팅까지 통과했다. 그러나 해제된 `start.dat`가 원본 9,030,752바이트를 넘는 경우 게임 코드 `0x0881DB60`에서 실패했다. 따라서 Demo00 생산안은 글리프 830개를 기존 셀에 재배치해 `font.txp`와 `start.dat` 크기를 유지한다. 최종 LZS는 원본보다 작아 `SYSTEM.DAT`의 원래 `start.lzs` extent 안에서 치환되며 ISO 파일 오프셋도 모두 보존된다.
