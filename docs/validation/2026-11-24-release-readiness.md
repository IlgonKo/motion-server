# 2026-11-24 문서 회귀 배포 검증 결과

## 대상과 경계

TD-009, RF-010, TD-010, RF-006. 소스 기준 HEAD는 2ea5eb5이며 이번 미커밋 변경을 포함한다.
Windows 64 bit / Python 3.14.3에서 실행했다. Node-RED 실행 시험, 실제 EtherCAT 조작,
운영 서버 재시작과 신규 AI 생성 평가는 하지 않았다.

## 결과

| 검증 | 결과 |
| --- | --- |
| Schema·registry·문서 command 목록 | 57개 일치 |
| 공개 API JSON 예제 | 59개 parse/Schema 검사 통과 |
| 개발 환경 unit / integration | 583개 / 13개 통과 |
| 신규 venv 전체 회귀 | 596개 통과 |
| 로컬 .env 없는 소스 복사본 + 신규 venv | 598개 통과, 55.42초 |
| 문서 drift 음성 검사 | 미지원 명령·숫자 문자열을 실패로 검출 |
| Windows EXE 빌드 | server, Axis/IO/Gamepad Panel 4종 성공 |
| 패키지 파일 검사 | 3828개, 필수 항목 누락 없음 |
| 패키지 EXE mock TCP 이동 시퀀스 | 1개 통과 |
| PowerShell build script | 구문 검사 및 PySOEM import 확인 |
| git diff whitespace | 통과 |

새 venv에는 requirements.txt만 설치했다. 소스 복사본은 Git 관리 파일과 이번 신규 파일로
구성했으며 로컬 .env·운영 설정·캐시는 복사하지 않았다. 원격 GitHub checkout CI 성공과는 구분한다.

## 산출물

- `.codex_output/release-validation/clean-source.json`: 최종 전체 회귀 세부 결과
- `.codex_output/release-validation/requirements-resolved.txt`: 검증 venv 의존성 version
- `.codex_output/package-build.log`, `.codex_output/package-smoke.log`: EXE build/smoke
- `.codex_output/release-validation/Motion Server/artifact-manifest.json`: 파일 크기 및 SHA256
- `.github/workflows/regression.yml`: Windows/Linux × Python 3.12/3.14 workflow

패키지는 검증용으로 별도 생성했으며 운영 설정·Npcap installer를 포함하지 않는다.
server mock smoke 통과가 Panel EXE 전체 GUI 조작이나 실장비 driver 정상 동작을 의미하지 않는다.

## 남은 인수

- TD-010: push 후 GitHub CI matrix 실행 증거. 현재는 workflow 작성 및 로컬 clean-source 통과.
- RF-010: 새 DOCX/PDF 제작·렌더 검증 및 문서 기반 신규 환경 설치. 현재는 Markdown 2.0이며
  Word 1.0은 obsolete 이력으로 보존하고 배포에서 제외했다. 현 PC에 Word/LibreOffice가 없다.
- RF-006: 새 Windows/Linux PC, Npcap/NIC 및 실장비, catalog 선택, upgrade/rollback 인수.
  현 PC의 Docker daemon 연결이 실패하여 Linux container 실행은 검증하지 않았다.

TD-009는 complete, 나머지 3개는 in_progress로 유지한다. 신규 환경 인수 항목을
로컬 자동 시험 결과만으로 완료 처리하지 않는다.
