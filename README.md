# 프리니 ~제가 주인공해도 되겠슴까?~ — PSP

PSP **프리니 ~제가 주인공해도 되겠슴까?~** 한글 번역 패치 프로젝트입니다. 프리니가 주인공으로 활약하는 횡스크롤 액션 게임입니다.

> **최종 배포 v2.3**

## 다운로드 및 적용 방법

1. 아래 체크섬 또는 상세 안내와 일치하는 원본을 준비합니다.
2. [최종 배포 패치 다운로드](https://github.com/akuma815/psp-prinny-kr-patch/releases/tag/v2.3)에서 ZIP을 받아 모두 압축 해제합니다.
3. Delta Patcher 등 xdelta 패처에서 원본 ISO와 `Prinny_ULJS00150_KR_20260803.xdelta`를 선택해 새 파일로 적용합니다.
4. 보유한 DLC에는 해당 DLC 전용 xdelta를 적용합니다. PARAM.PBP 적용과 설치 경로는 [상세 안내](docs/PATCH_GUIDE.txt)를 따르세요.

## 주의사항

- 일본판 ULJS00150 1.01 전용이며 본편과 DLC 3종 패치가 포함됩니다.
- DLC는 같은 배포본의 본편 패치가 적용된 한글 글꼴을 사용합니다.
- PSP 펌웨어의 세이브 목록 제목·설명 일부는 호환성을 위해 일본어로 유지됩니다.
- 원본 게임·BIOS 및 패치가 적용된 게임 이미지는 포함하지 않습니다.

## 체크섬

| 구분 | SHA-256 |
| --- | --- |
| 패치 파일 `Prinny_DLC_DL0000_KR_20260803.xdelta` | `0a4d662e671ddd5aa561a31678a8957f755dae15b5f7e4005cf4e3040f1c4f8a` |
| 패치 파일 `Prinny_DLC_DL0001_KR_20260803.xdelta` | `b79cf9e1ab0767b26e5c6ae3458846e5e33d42c9dad656a6a627addc86db41a6` |
| 패치 파일 `Prinny_DLC_DL0002_KR_20260803.xdelta` | `d837367e14d021256adf31d35a2b478aded7e149250f3889cabbc5a1d4c7d2b1` |
| 패치 파일 `Prinny_ULJS00150_KR_20260803.xdelta` | `357082ca2707240bd5defe59faad75c72e2ca44fe900380523fbd9c2846bbc89` |
| 원본 ISO | `af0d2873a96c5fe6f95b3fc2fb3e8702f98bba67e32f2f78c5c3d1bdaa8b9d03` |
| 패치 후 이미지 ISO | `ae53bc4b960b263a362756e801c21da7224ce3dd735d2da5882c04a0248622ac` |
| 원본 DL0000 | `a0209702de5210b2f35c57e7c12bfddbeb691200de06769b615ca50254d48c1b` |
| 패치 후 이미지 DL0000 | `2a2fb6a26ad40aa7ef2bfd46795657416e4d45723f7b04b3a30e76e715b83739` |
| 원본 DL0001 | `86b48d56b6ba853f09ffb0a524ccebf4f601c78cb0f4937cb885ec8815bdb7a7` |
| 패치 후 이미지 DL0001 | `4d3f0b113670c532cab6233c08309b000a34622673730cfd1b8d12dc6e503ccc` |
| 원본 DL0002 | `3fbc26ed99c1b3f474e50dd5290eb0497e61f0a7e8e9268fb82980a426079be9` |
| 패치 후 이미지 DL0002 | `fb6b75f3f60da7233eea63a229512a0762e3b789c7204c5e22d0d837677435ae` |
| 배포 압축 파일 | `59cdf7c4d2f5545bd8a6c6a7cfeb7e1ddffbe7b23207d31ebc4c36d0c601b348` |

지원 원본의 세트·리비전 및 해시는 [상세 패치 안내](docs/PATCH_GUIDE.txt)를 확인하세요.

## 소스 및 작업 기록

[공개 소스 구성과 빌드 전제](docs/SOURCE_GUIDE.md) · [상세 패치 안내](docs/PATCH_GUIDE.txt)
