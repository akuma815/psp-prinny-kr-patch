# 최종판 복원 및 후속 작업

2026-10-16에 공개 소스의 새 체크아웃과 외부 원본으로 v2.3 복원 경로를 점검했습니다. 본편 ISO와 DLC 3종은 공개 릴리즈의 최종 SHA-256과 일치합니다. 새 게임 실행이나 전체 플레이 검수는 이번 점검에 포함하지 않습니다.

## 준비물

- Python 3.11 이상. 검증 환경은 Python 3.12.10 및 Pillow 12.3.0입니다.
- 일본/한국판 ULJS00150 1.01 원본 ISO: 500,465,664바이트, SHA-256 `af0d2873a96c5fe6f95b3fc2fb3e8702f98bba67e32f2f78c5c3d1bdaa8b9d03`.
- DLC 원본 `DL0000.EDAT`, `DL0001.EDAT`, `DL0002.EDAT`. 각 해시는 README 표를 따릅니다. `PARAM.PBP`가 같은 폴더에 있으면 변경 없이 복사합니다.
- 별도 보관한 `HancomMalangMalang-Regular.ttf`: 7,396,036바이트, SHA-256 `f6682e2027b1a382d3e01546f7a7115cb26cc1245ded6b839686a069abc743b0`.
- xdelta3 실행 파일. 검증에는 공통 Tools 폴더의 3.2.0 Windows x64판을 사용했습니다.
- [v2.3 공개 ZIP](https://github.com/akuma815/psp-prinny-kr-patch/releases/tag/v2.3). 빌더가 자동으로 내려받거나 `--release-zip`으로 직접 지정할 수 있습니다. ZIP SHA-256은 `59cdf7c4d2f5545bd8a6c6a7cfeb7e1ddffbe7b23207d31ebc4c36d0c601b348`로 고정합니다.

원본과 폰트는 저장소에 포함하지 않습니다. 공통 Font와 Tools 폴더를 보관해야 합니다. 게임 폴더를 삭제한 뒤에는 위 해시의 원본 ISO와 DLC를 다시 준비해야 합니다.

## 실행

새로 복제한 저장소의 루트에서 경로를 실제 보관 위치로 바꿔 실행합니다. 출력은 비어 있는 새 폴더로 지정합니다.

```powershell
python -m pip install -r requirements-rebuild.txt
python -X utf8 workspace/scripts/rebuild_final.py `
  --original-iso "D:\Original\Prinny.iso" `
  --original-dlc-dir "D:\Original\Prinny_DLC" `
  --font "G:\Downloads\Korean Traslate Project\Font\HancomMalangMalang-Regular.ttf" `
  --xdelta "G:\Downloads\Korean Traslate Project\Tools\xdelta3-3.2.0-windows-x86_64\xdelta3.exe" `
  --output "D:\Build\Prinny_restore"
```

`Prinny_KR_final.iso`, `patched_dlc/ULJS00150`, 편집용 `editable_author_images`, 그리고 `rebuild_report.json`을 생성합니다. 출력 폴더에는 추출 원본과 게임 이미지도 있으므로 Git에 추가하지 않습니다. 보고서는 ISO 내부 16개 파일, 사전 지정한 쓰기 범위 밖의 바이트 불변, 최종 해시, 원본 불변, 편집 이미지 RGBA 해시를 검증합니다.

## 소스에서 만드는 부분과 고정 자산

- 원본 BOOT에 네이티브 한글 출력 코드를 적용하고 UI 590개 슬롯을 번역합니다. 같은 실행 파일을 BOOT/EBOOT에 넣습니다.
- Demo00 대사, 스테이지·행운 인형·도감·아이템·컬렉션·훈장·음악 상점·클리어 타임을 원장으로 재생성합니다. 글꼴 998자와 JIS/UCS 매핑을 원본 및 별도 TTF에서 만듭니다. start.dat의 13개 텍스트·폰트·테이블 멤버를 다시 만들고 압축합니다.
- DLC의 DDEM/DSTI 대사·스테이지 정보를 원본과 CSV에서 만듭니다.
- 최종 그래픽 `ANIME.DAT`, `BG.DAT`, `STAGE.DAT`, start.dat의 `anime00.dat`, `number.txp`는 해시가 고정된 공개 최종 패치에서 복원합니다. 최종 그래픽 전체를 새로 렌더링했다는 의미는 아닙니다. 이 ZIP은 복원 입력이므로 기존 v2.3 첨부를 교체하면 안 됩니다.
- 편집용 번역 PNG 67개의 RGBA 픽셀은 `workspace/graphics/restore/author_rgba_deltas.json`의 압축 XOR 차분과 원본 텍스처로 완전히 복원합니다. PNG 메타데이터·압축 바이트는 달라질 수 있으나 빌더가 읽는 RGBA 픽셀은 일치합니다. 픽셀 소스는 최종 네이티브 그래픽 후처리 전체와 구분합니다. 원래 PNG 전체나 원본 배경은 Git에 추가하지 않았습니다.

## 원장 보정 및 최종판 프로필

`dl0000_ddem.csv`에서 지수 표기로 손상된 보호 HEX 3개를 지원 원본의 해당 슬롯에서 복원했습니다. 번역문은 바꾸지 않았습니다. 변경 전후는 `workspace/config/dlc_protected_hex_repairs.json`에 기록했습니다.

현 원장의 DLC 화자 `프론` 17개 슬롯은 배포판에서 `플론`입니다. 기본 복원은 `frozen_dlc_overrides.json`의 17개 명시적 오버라이드를 메모리에서만 적용하여 v2.3을 재현합니다. CSV의 현재 번역을 유지합니다.

후속 번역 수정은 CSV/JSON을 편집한 뒤 같은 명령에 `--candidate`를 추가합니다. 이 모드는 위 17개 최종판 표기 오버라이드를 적용하지 않고, 최종판 해시 강제 검사를 생략하여 `Prinny_KR_candidate.iso`를 만듭니다. 결과는 미검증 후보입니다. 새 글자 추가에는 고정 매핑/글리프 할당 검토가 필요하며, 자동 글자 확장은 제공하지 않습니다. 네이티브 그래픽을 수정하려면 복원한 이미지와 기존 삽입 스크립트를 사용하고 별도 실행 검증을 수행합니다.

기존 `build_direct_run.py` 등은 과거 작업 경로를 사용하는 이력으로 남겼습니다. 이번 삭제 후 복원 진입점은 `rebuild_final.py`입니다.

## 확인 범위

통합 빌드 및 별도 새 원격 체크아웃의 복원 빌드, 원본 불변, 본편/DLC 해시 일치, 공개 ZIP의 실제 `apply_main.ps1`/`apply_dlc.ps1` 실행, 코덱·텍스처·네이티브 출력 패치 관련 12개 단위 검사를 수행했습니다. 이번 작업에서 새 에뮬레이터 실행·실기·전체 플레이 검수를 수행하지 않았습니다. 역사적 플레이 결과는 해당 버전의 기존 문서에 한정됩니다.
