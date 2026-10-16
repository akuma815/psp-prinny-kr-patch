# 이미지 한글 초벌 검토표

최종 갱신: 2026-07-24

이 문서는 이미지에 직접 들어간 한글 문구를 ISO 빌드 전에 검토·수정하기 위한 목록이다. 화면에서 어색한 문구나 정렬을 발견하면 `화면 이름 / 현재 문구 / 수정 문구`와 스크린샷을 기록한다. 승인 전에는 PPSSPP replacement texture만 갱신한다.

## 2026-07-24 전수 초벌 완료 상태

- 복원·분류 모집단: 949개
- 이미지 내 고정 문구 대상: 66개
- 비대상: 883개
- 미분류: 0개
- 초벌 교체본 커버: 66/66, 누락 0개
- 중복 소비본을 합친 고유 교체 PNG: 39개
- 기존 승인 별칭까지 포함한 즉시 검수 가능 자산: 11개
- 이번 정확 덤프 대조에서 설치된 런타임 파일: 8개, 대응 논리 자산 6종
- 새 화면 덤프를 기다리는 staged 자산: 55개
- ISO 생성: 없음

전체 검수 시트는 `work/live/image_first_pass_review/all_first_pass_contact_sheet.png`, 자산별 상태와 출력 경로는 `work/live/image_first_pass_review/review_manifest.json`이 정본이다. 아직 만나지 않은 엔딩·크레딧·체험판 화면은 번역 PNG가 준비되어 있으며, 해당 화면을 PPSSPP에서 열어 새 덤프를 만든 뒤 아래 일괄 갱신 명령을 다시 실행하면 정확 일치 자산만 자동 설치된다.

`Push □`, `BEST RECORD`, `데모 스킵`, 오프닝 문장처럼 글자 조각을 조합하는 표시는 949개 정적 이미지의 미번역 누락으로 계산하지 않는다. 이들은 동적 문자열·공용 문자 아틀라스 소비자 후속 조사 대상으로 분리한다. 월드 `튜토리얼` 간판 윗부분 잔재도 사용자 요청대로 후속 보정에 남긴다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  .\workspace\scripts\refresh_all_baked_graphics_preview.ps1 `
  -PpssppRoot 'H:\ppsspp'
```

이 최신 절이 아래의 2026-07-22 중간 집계와 미완료 목록을 대체한다.

### 2026-07-24 갱신 명령 재실행

PPSSPP 덤프 폴더를 다시 전수 대조했다. target 66/66, 고유 교체본 39개, 누락 0개를 유지했다. 난이도 장식 `start.dat/anime00.dat/record-84/texture-1`의 새 덤프 `0918bd60671c5823a41a5f08.png`가 정확히 대응되어 설치 수치는 런타임 파일 8개·논리 자산 6종으로 증가했다. 즉시 검수 가능 11개, staged 55개이며 `iso_built=false`를 재확인했다.

## 현재 바로 확인할 화면

| 화면 | 현재 초벌 문구 | 교체 파일 | 상태 |
|---|---|---|---|
| 난이도 선택 | `스탠다드`, `베이비`, `마계 공식 룰`, `스탠다드`, `마계 공인` | `0918bd60611a54e7d55a5edf.png` | 설치 완료, 실제 화면 검토 대기 |
| 리플레이 저장 | `리플레이 저장`, `저장 중…` | `091cd1e0f54138b2af437712.png` | 설치 완료, 실제 화면 검토 대기 |
| 적·보스 명칭 아틀라스 | 적·보스·상태명 한국어 초벌 | `090d236071e5ca896f5b71d4.png` | 설치 완료, 등장 화면별 검토 대기 |
| 스테이지 결과 | `스테이지 결과`, `클리어 랭크` | `0916bd60671c58233aef5cd3.png` 및 별칭 2개 | 설치 완료, 결과 화면 검토 대기 |

PPSSPP를 완전히 종료한 뒤 다시 실행해야 캐시된 원본 대신 최신 PNG가 표시된다.

## 초벌 PNG 완료·런타임 해시 대기

| 화면 | 현재 초벌 문구 | 생성 PNG | 다음 조건 |
|---|---|---|---|
| 주인공 모집 간판 | `밝은 주인공 구함` | `protagonist_sign_anime20_r14_t00.png` | 해당 장면 진입 후 새 덤프와 소비자 매핑 |
| 엔딩 카드 | `끝` | `end_card_anime90_r02_t00.png` | 엔딩 진입 후 새 덤프와 소비자 매핑 |
| 스태프 크레딧 | 역할·제작진 한국어 초벌 6면 | `staff_credits_anime90_r03_t00.png` ~ `t05.png` | 크레딧 진입 후 각 화면 덤프와 매핑 |
| 에필로그 | 10줄 한국어 본문 | `epilogue_anime94_r00_t00.png` | 에필로그 진입 후 새 덤프와 소비자 매핑 |
| anime91 화면 라벨 | TV/뉴스 라벨 한국어 초벌 | `anime91_tv_labels_r00_t01.png` | 해당 이벤트 진입 후 덤프와 매핑 |
| anime91 종료 화면 | 제작진 종료 표기 한국어 초벌 | `anime91_staff_end_r00_t03.png` | 해당 이벤트 진입 후 덤프와 매핑 |

생성본은 `work/live/baked_graphics_bulk/generated`에 있다. 런타임 해시가 확인되기 전에는 임의의 PPSSPP 파일명에 복사하지 않는다.

## 2026-07-22 일괄 초벌 결과

- 생성 PNG: 15개
- PPSSPP 즉시 교체 설치: 4개 논리 자산, `textures.ini` 별칭 68개 유지
- 전체 미리보기: `work/live/baked_graphics_bulk/first_pass_contact_sheet.png`
- 생성 보고서: `work/live/baked_graphics_bulk/build_report.json`
- ISO 생성: 없음 (`iso_built=false`)

`생성 완료`는 원본 텍스처와 같은 크기의 한글 초벌 PNG가 있다는 뜻이다. `게임 적용 완료`는 런타임 덤프 해시가 확인되어 PPSSPP가 실제로 그 PNG를 소비하는 상태를 뜻하므로 둘을 혼동하지 않는다.

## 아직 매핑 또는 초벌 번역이 필요한 이미지

- anime92/93 엔딩 몽타주: 승인 대사와 개별 프레임의 대응 관계 확정 필요
- `Push □`, `데모 스킵`, 게이지 명칭처럼 별도 이미지인지 동적 스프라이트 조합인지 미확정인 표시
- 거점 메뉴 후속 화면
- 월드 `튜토리얼` 간판 윗부분 일본어 잔재

## 재생성 명령

```powershell
python .\workspace\scripts\build_baked_graphics_bulk_preview.py `
  --project-root . `
  --ppsspp-textures 'H:\ppsspp\memstick\PSP\TEXTURES\ULJS00150'
```

이 명령은 ISO를 만들지 않는다. `work/live/baked_graphics_bulk/build_report.json`에서 `iso_built=false`, 설치 항목, 런타임 해시 대기 항목을 확인한다.
## 2026-07-26 런타임에서 추가 식별된 이미지 텍스트

- 데모 스킵은 단일 이미지가 아니라 동일한 인덱스 데이터와 서로 다른 CLUT 상태를 사용하는 exact Hashfile 3종으로 관리한다.
- `리플레이 저장`, `데모 스킵`이 포함된 3개 상태를 PPSSPP replacement texture에 설치했다.
- 기한 타이머 아틀라스 4개 상태의 일본어를 `궁극의 디저트 완성까지`, `남은 시간`으로 초벌 번역했다.
- 두 항목 모두 정적 검사는 완료했으며 실제 화면 검수는 대기 중이다.

## 2026-07-26 GE 디버거 누락 아틀라스 검수 묶음

- 입력: 사용자가 제공한 GE/Graphics Debugger 화면 17장
- 고유 exact Hashfile: 16개
- 초벌 교체 생성·설치: 15개
- 번역 제외: `0939d9b0b3dddb901557c943.png` 1개 — 공용 숫자·HUD 아틀라스
- 정적 검증: 크기 유지, 파일 해시 일치, 텍스트 영역 밖 변경 0픽셀
- 실기 검수 대기: 대화·저장 안내, 튜토리얼 설명, 거점 안내
- 스테이지 설명 6계열은 런타임 문자열로 판명되어 임시 PNG와 `textures.ini` 연결을 제거했다. 후속 검수는 `workspace/text/translation/stage_info.csv` 번역·재삽입 후 진행한다.
- 결과 위치: `work/live/runtime_text_atlas_preview/generated`
- 상세 보고서: `work/live/runtime_text_atlas_preview/report.json`

## 2026-07-26 설정·타이틀 3종 검수 대기

| exact Hashfile | 초벌 문구 | 상태 |
|---|---|---|
| `09564140a841f78dfc7541a2.png` | 설정·타이틀 복귀 확인 | 정적 검증 PASS / 실기 PENDING |
| `09564140a841f78d1f59463c.png` | BGM·음성·효과음 음량 안내 | 정적 검증 PASS / 실기 PENDING |
| `09564140a841f78dc872c67b.png` | 타이틀 복귀 경고 | 정적 검증 PASS / 실기 PENDING |

현재 생성본과 PPSSPP 설치본은 18종, `textures.ini` 별칭은 101개다. 세 파일 모두 텍스트 영역 밖 변경은 0픽셀이며, 실제 화면 문구와 정렬은 PPSSPP 재로딩 후 검수한다.
