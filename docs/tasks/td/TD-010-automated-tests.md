# TD-010 회귀 검증 실행 및 보고 체계

- 상태: `in_progress`
- 갱신일: 2026-11-24

## 현재 구조

이미 존재하는 설정, ESI/IODD, PDO codec, API, Virtual CMMT/CPX 및 Panel 테스트를 공통 profile로 묶었다.
자동 테스트 부재라는 최초 제목은 현 상태를 반영하지 않아 실행·CI·보고 체계 정리로 갱신했다.

## 구현

- `python -m scripts.run_tests --profile unit|integration|all`로 실행한다.
- unit은 독립 회귀, integration은 임시 설정·포트의 mock TCP/GUI 시나리오다.
- JSON 보고서에 OS/Python, 대상 모듈, 개별 시간, 실패 traceback, skip 사유를 기록한다.
- Node-RED는 제외하며 실제 hardware에는 접근하지 않는다.
- `scripts.hardware_status_check`는 명시한 주소의 status만 조회하는 별도 profile이다.
  authority, reconnect, reset, enable 및 motion은 보내지 않는다. 실제 이동 시험은 수동 절차로 유지한다.
- `.github/workflows/regression.yml`: Windows/Linux × Python 3.12/3.14, Linux Xvfb,
  requirements 설치와 문서 검증, 테스트 보고서 artifact 업로드.
- 전체 실행에서 발견된 test import 경로 및 module reload 후 entrypoint patch 간섭을 수정했다.
- Windows subprocess 종료 직후 log handle의 일시 sharing violation은 한정된 재시도로 정리하고,
  지속 오류는 실패로 남긴다. 제품 오류를 무시하는 fallback이 아니다.

## 완료 증거

- 로컬 unit 583개, integration 13개 통과.
- 새 venv + requirements 설치 후 all 596개 통과(58.19초). 이후 문서 음성 테스트 2개 추가 및 해당 3개 재검증 통과.
- 실제 GUI 위젯 및 mock TCP 검증을 포함한다. AI 신규 생성 평가나 Node-RED 시험은 실행하지 않았다.

- 최종: 로컬 .env 없는 소스 복사본과 신규 venv에서 문서 음성 검사 포함 598개 통과(55.42초).

## 남은 완료 조건

- 변경을 push한 뒤 GitHub clean checkout의 Windows/Linux matrix 실행 결과를 확인한다.
  workflow 작성만으로 원격 CI가 통과했다고 표시하지 않는다.
- 새 실제 하드웨어 환경에서 smoke-test 증거를 RF-006 체크리스트에 기록한다.

- 상세 검증 기록: [2026-11-24 배포 준비 검증](../../validation/2026-11-24-release-readiness.md)
