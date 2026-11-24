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

## 원격 CI 결과

- 검증 commit: `d4d3fdf1477a0fff176109fa272637857671b0a7`, `main` push 완료.
- [GitHub Actions run 45324527718](https://github.com/IlgonKo/motion-server/actions/runs/45324527718): 전체 실패.
- 네 환경 모두 API 문서 검사를 통과했고 각각 598개 회귀 테스트를 실행했다.

| 환경 | 결과 |
| --- | --- |
| Ubuntu / Python 3.12 | 성공 |
| Ubuntu / Python 3.14 | 실패 2개, skip 3개 |
| Windows / Python 3.12 | error 7개 |
| Windows / Python 3.14 | 실패 1개, error 2개 |

Windows error는 mock TCP 테스트 준비 단계의 `system/axis/home` 요청 중
`ConnectionLostError: Motion Server Heartbeat timed out`이다. Windows 3.14의 추가 실패는
제어권 해제 시험에서 worker가 제한 시간 안에 끝나지 않은 것이다.
Ubuntu 3.14는 GUI Jog 조건 대기 timeout과 연결 해제 시험의 worker 종료 대기 실패다.
같은 로그에 Tk `Variable.__del__`의 `main thread is not in main loop`가 반복 기록되었다.
이 로그만으로 모든 실패의 근본 원인이 같거나 runner 부하만의 문제라고 단정하지 않는다.

최초 실패 당시 후속 작업은 Tk 객체의 스레드/수명 관리, homing 중 heartbeat 처리, 손실 시험의 종료 경로를
분리 재현하는 것이다. 제품 timeout 변경이나 실패 테스트 제외는 하지 않았다.
실패 traceback과 개별 시간은 해당 run의 `regression-*` artifacts에서 확인할 수 있다.
결과 기록만 추가한 후속 문서 commit은 `[skip ci]`로 중복 실행을 생략한다.

## 남은 인수

- TD-010: 아래 최종 원격 재검증으로 완료했다.
- RF-010: 새 DOCX/PDF 제작·렌더 검증 및 문서 기반 신규 환경 설치. 현재는 Markdown 2.0이며
  Word 1.0은 obsolete 이력으로 보존하고 배포에서 제외했다. 현 PC에 Word/LibreOffice가 없다.
- RF-006: 새 Windows/Linux PC, Npcap/NIC 및 실장비, catalog 선택, upgrade/rollback 인수.
  현 PC의 Docker daemon 연결이 실패하여 Linux container 실행은 검증하지 않았다.

TD-009와 TD-010은 complete, RF-010과 RF-006은 in_progress로 유지한다. 신규 환경 인수 항목을
로컬 자동 시험 결과만으로 완료 처리하지 않는다.

## 원격 CI 실패 수정 및 최종 재검증

- 검증 commit: `f169be3bde45f20a6ab09cb88b67dae6fa322e4d`.
- [최종 CI run 45327417682](https://github.com/IlgonKo/motion-server/actions/runs/45327417682): 모두 성공.

| 환경 | 실행 수 | 결과 | 시간 |
| --- | --- | --- | --- |
| Windows / Python 3.12 | 598 | 성공 | 129.124초 |
| Windows / Python 3.14 | 598 | 성공 | 57.623초 |
| Ubuntu / Python 3.12 | 598 | 성공, 플랫폼 skip 3개 | 100.787초 |
| Ubuntu / Python 3.14 | 598 | 성공, 플랫폼 skip 3개 | 76.136초 |

### 확인한 원인과 최종 변경

1. 닫힌 Tk 창의 Variable/callback 순환 참조가 이후 TCP worker의 자동 GC에서 정리됐다.
   `scripts/run_tests.py`는 시험 중 자동 GC를 일시 중지하고 메인 스레드의 시험 경계에서 수거한다.
   종료 시 기존 GC 설정을 복원한다. 수정 후 원격 Tk 스레드 오류 및 GUI/worker 대기 실패가 사라졌다.
2. Windows 공유 runner에서는 설정한 8ms 주기와 달리 loop 평균 약 14ms, 최대 약 125ms 지연이
   관찰됐다. 여러 cycle을 동기 처리하는 Homing 준비와 200ms heartbeat 예산이 충돌했다.
   기능 회귀 fixture의 Mock cycle을 2ms로 낮추고, 다음 축 준비 전 homing inactive와 PP 모드
   복원을 확인한다. 준비 실패 시 축과 서버 로그를 남긴다.
3. Nagle 지연 가능성을 조사해 TCP_NODELAY를 시험했으나 잔여 실패가 계속돼 제품 변경은 원복했다.
   최종 제품 server/client 코드와 heartbeat timeout은 변경하지 않았다. 임시 timer 측정 코드도 제거했다.

최종 코드 변경 파일은 `scripts/run_tests.py`, `tests/test_ai_pick_place_tcp.py`다.
로컬 전체 598개 통과 후, 최종 Mock 설정의 통합 13개 통과 및 위 원격 전체 회귀를 확인했다.
추가/삭제한 테스트는 없고 기존 실패를 skip하거나 retry하여 통과시키지 않았다.

DEC-057에 따라 Windows에서는 CSP를 포함한 동기 제어를 공식 지원하지 않으며 주기 성능을
검증하지 않는다. 2ms는 시험 fixture의 설정값으로, Windows의 실시간 성능 보증이 아니다.
Node-RED 시험, 실장비 제어 및 운영 서버 재시작은 하지 않았다.
