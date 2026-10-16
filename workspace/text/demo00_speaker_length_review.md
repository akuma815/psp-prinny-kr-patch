# Demo00 화자명 길이 초과 검토 목록

- 영향 엔트리: 139개
- 중복을 묶은 수정 항목: 14개
- 판정 기준: 공백과 문장부호를 포함한 유니코드 글자 수가 원문보다 긴 화자명
- 실제 수정 파일: `workspace/text/demo00_speaker_length_review.json`의 `replacement_speaker`
- 아래 표는 확인용이며 원본 번역본에는 아직 반영되지 않음

| ID | 원문 | 원문 길이 | 현재 번역 | 번역 길이 | 초과 | 적용 건수 |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| SPEAKER-LEN-001 | 夜逃げ屋 | 4 | 야반도주 담당 | 7 | +3 | 2 |
| SPEAKER-LEN-002 | 満月の星陰 | 5 | 만월의 호시카게 | 8 | +3 | 2 |
| SPEAKER-LEN-003 | セーブ屋 | 4 | 세이브 담당 | 6 | +2 | 1 |
| SPEAKER-LEN-004 | リプレイ屋 | 5 | 리플레이 담당 | 7 | +2 | 2 |
| SPEAKER-LEN-005 | 星影 | 2 | 호시카게 | 4 | +2 | 47 |
| SPEAKER-LEN-006 | 記録屋 | 3 | 기록 담당 | 5 | +2 | 2 |
| SPEAKER-LEN-007 | 音楽屋 | 3 | 음악 담당 | 5 | +2 | 2 |
| SPEAKER-LEN-008 | プリニー隊 | 5 | 프리니 부대 | 6 | +1 | 27 |
| SPEAKER-LEN-009 | プリ一郎 | 4 | 프리이치로 | 5 | +1 | 3 |
| SPEAKER-LEN-010 | プリ和尚 | 4 | 프리 화상 | 5 | +1 | 2 |
| SPEAKER-LEN-011 | プリ将軍 | 4 | 프리 장군 | 5 | +1 | 2 |
| SPEAKER-LEN-012 | プリ山 | 3 | 프리야마 | 4 | +1 | 2 |
| SPEAKER-LEN-013 | モーブ兵 | 4 | 모브 병사 | 5 | +1 | 43 |
| SPEAKER-LEN-014 | 時空の渡し人 | 6 | 시공의 뱃사공 | 7 | +1 | 2 |

## 영향 엔트리

- `SPEAKER-LEN-001`: `demo00/017D`, `demo00/0208`
- `SPEAKER-LEN-002`: `demo00/31A6`, `demo00/31AA`
- `SPEAKER-LEN-003`: `demo00/023A`
- `SPEAKER-LEN-004`: `demo00/01AF`, `demo00/0226`
- `SPEAKER-LEN-005`: `demo00/283C`, `demo00/283E`, `demo00/2846`, `demo00/284A`, `demo00/284C`, `demo00/284E`, `demo00/29CC`, `demo00/29CE`, `demo00/29D2`, `demo00/29D4`, `demo00/29D6`, `demo00/29D8`, `demo00/29DC`, `demo00/29E0`, `demo00/29E2`, `demo00/2BC2`, `demo00/2BC6`, `demo00/2BC8`, `demo00/2BCE`, `demo00/2BD2`, `demo00/2BDA`, `demo00/2BDC`, `demo00/2BE0`, `demo00/2BE4`, `demo00/2BE6`, `demo00/2DB4`, `demo00/2DB6`, `demo00/2DBA`, `demo00/2DBE`, `demo00/2DC0`, `demo00/2DC2`, `demo00/2DC6`, `demo00/2DCC`, `demo00/2DCD`, `demo00/2DCE`, `demo00/2DD4`, `demo00/2FB0`, `demo00/2FB2`, `demo00/2FB4`, `demo00/2FB8`, `demo00/2FBA`, `demo00/31B0`, `demo00/31B6`, `demo00/31B8`, `demo00/3520`, `demo00/3526`, `demo00/3528`
- `SPEAKER-LEN-006`: `demo00/01F4`, `demo00/01F5`
- `SPEAKER-LEN-007`: `demo00/01FE`, `demo00/01FF`
- `SPEAKER-LEN-008`: `demo00/07E0`, `demo00/07E2`, `demo00/07E4`, `demo00/0804`, `demo00/0806`, `demo00/0808`, `demo00/0810`, `demo00/0812`, `demo00/0818`, `demo00/0834`, `demo00/0836`, `demo00/083A`, `demo00/083C`, `demo00/083E`, `demo00/32CA`, `demo00/32CE`, `demo00/32D0`, `demo00/32D2`, `demo00/32D6`, `demo00/32E0`, `demo00/32E2`, `demo00/365C`, `demo00/365E`, `demo00/3660`, `demo00/3662`, `demo00/3666`, `demo00/3668`
- `SPEAKER-LEN-009`: `demo00/0A28`, `demo00/0A2A`, `demo00/0A2E`
- `SPEAKER-LEN-010`: `demo00/0ABE`, `demo00/0AC2`
- `SPEAKER-LEN-011`: `demo00/09F6`, `demo00/09F8`
- `SPEAKER-LEN-012`: `demo00/0992`, `demo00/0996`
- `SPEAKER-LEN-013`: `demo00/2870`, `demo00/2874`, `demo00/2878`, `demo00/287C`, `demo00/2880`, `demo00/2882`, `demo00/2A00`, `demo00/2A02`, `demo00/2A04`, `demo00/2A08`, `demo00/2A0A`, `demo00/2A0C`, `demo00/2A0E`, `demo00/2A10`, `demo00/2A14`, `demo00/2A16`, `demo00/2A18`, `demo00/2A1A`, `demo00/2BF4`, `demo00/2BFA`, `demo00/2C02`, `demo00/2C06`, `demo00/2DE6`, `demo00/2DE8`, `demo00/2DEA`, `demo00/2DEE`, `demo00/2DF2`, `demo00/2DF4`, `demo00/2FE8`, `demo00/2FEA`, `demo00/2FF0`, `demo00/31CE`, `demo00/31D0`, `demo00/31D2`, `demo00/31D6`, `demo00/31D8`, `demo00/31DC`, `demo00/31DE`, `demo00/31E2`, `demo00/31E6`, `demo00/3552`, `demo00/3556`, `demo00/3558`
- `SPEAKER-LEN-014`: `demo00/0191`, `demo00/021C`
