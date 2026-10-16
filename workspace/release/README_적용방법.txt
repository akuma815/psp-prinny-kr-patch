========================================================================
 프리니 ~제가 주인공해도 되겠슴까?~ PSP 한글 패치 v2.3 + DLC
 대상: ULJS00150 일본판 1.01
========================================================================

■ 구성

  Prinny_ULJS00150_KR_20260803.xdelta       본편 ISO 패치
  Prinny_DLC_DL0000_KR_20260803.xdelta      마왕성과 타천사 DLC 패치
  Prinny_DLC_DL0001_KR_20260803.xdelta      유령섬의 마로네 DLC 패치
  Prinny_DLC_DL0002_KR_20260803.xdelta      연무성의 아사기 인형 DLC 패치
  apply_main.cmd                             본편 적용 도우미
  apply_dlc.cmd                              보유 DLC 적용 도우미
  tools\xdelta3.exe                          xdelta 3.2.0
  SHA256.txt                                 배포 파일 무결성 목록

ISO, EDAT와 같은 원본 또는 패치 완료 게임 파일은 배포물에 포함되지 않습니다.


■ 1. 본편 패치

원본 ISO를 apply_main.cmd 위로 끌어다 놓거나 다음처럼 실행합니다.

  apply_main.cmd "원본.iso"

지원 원본:

  크기:    500,465,664 바이트
  SHA-256: AF0D2873A96C5FE6F95B3FC2FB3E8702F98BBA67E32F2F78C5C3D1BDAA8B9D03

출력은 원본 옆의 `<원본 이름>_KR.iso`입니다.

  SHA-256: AE53BC4B960B263A362756E801C21DA7224CE3DD735D2DA5882C04A0248622AC


■ 2. DLC 패치 — 보유한 DLC만 선택 적용

원본 DLC 폴더를 apply_dlc.cmd 위로 끌어다 놓거나 다음처럼 실행합니다.

  apply_dlc.cmd "원본 DLC 폴더"

폴더에 존재하는 DL0000.EDAT, DL0001.EDAT, DL0002.EDAT만 각각 패치됩니다.
출력은 배포 폴더 안의 `patched_dlc\ULJS00150\`에 생성됩니다. 원본
PARAM.PBP가 입력 폴더에 있으면 함께 복사됩니다.

출력 폴더의 파일을 다음 위치에 설치합니다.

  (PPSSPP 폴더)\memstick\PSP\GAME\ULJS00150\

개별 DLC SHA-256:

  DL0000.EDAT (마왕성과 타천사)
    원본:   A0209702DE5210B2F35C57E7C12BFDDBEB691200DE06769B615CA50254D48C1B
    패치 후: 2A2FB6A26AD40AA7EF2BFD46795657416E4D45723F7B04B3A30E76E715B83739
    xdelta:  0A4D662E671DDD5AA561A31678A8957F755DAE15B5F7E4005CF4E3040F1C4F8A

  DL0001.EDAT (유령섬의 마로네)
    원본:   86B48D56B6BA853F09FFB0A524CCEBF4F601C78CB0F4937CB885EC8815BDB7A7
    패치 후: 4D3F0B113670C532CAB6233C08309B000A34622673730CFD1B8D12DC6E503CCC
    xdelta:  B79CF9E1AB0767B26E5C6AE3458846E5E33D42C9DAD656A6A627ADDC86DB41A6

  DL0002.EDAT (연무성의 아사기 인형)
    원본:   3FBC26ED99C1B3F474E50DD5290EB0497E61F0A7E8E9268FB82980A426079BE9
    패치 후: FB6B75F3F60DA7233EEA63A229512A0762E3B789C7204C5E22D0D837677435AE
    xdelta:  D837367E14D021256ADF31D35A2B478ADED7E149250F3889CABBC5A1D4C7D2B1

중요: DLC 한글은 본편 패치에 추가된 998자 글꼴을 사용합니다. DLC xdelta만
적용하고 본편을 패치하지 않으면 한글이 깨질 수 있습니다.

DLC를 보유하지 않았다면 DLC 패치는 전부 건너뛰어도 됩니다.


■ 3. 실행 환경

스테이지 방향 표지판, 튜토리얼 푯말, 남은 시간 타이머를 포함한 한글 자산은
ISO에 내장되어 있습니다. PPSSPP의 `텍스처 교체(Replace textures)` 기능이나
별도 텍스처 팩은 필요하지 않습니다.

권장 에뮬레이터는 PPSSPP 정식판 1.19.3입니다.


■ 4. 알려진 제약

PSP 실기 저장 호환성을 위해 PSP 펌웨어의 세이브 목록에 표시되는 제목과
일부 설명은 일본어 원문을 유지합니다. 게임 내부 텍스트와는 별도입니다.


■ 5. 제거

본편은 원본 ISO를 다시 사용합니다. DLC는 원본 EDAT/PARAM.PBP로 복원합니다.


■ 6. 주의

패치 적용이 끝난 ISO 또는 EDAT 파일을 배포하지 마세요. xdelta 파일만 공유할
수 있습니다. SHA256.txt로 다운로드한 배포 파일의 무결성을 확인할 수 있습니다.

xdelta3 3.2.0은 Apache License 2.0 조건의 도구이며, 도구 설명은
`tools\README_xdelta3.md`에 포함돼 있습니다.
