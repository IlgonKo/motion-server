# TD-042 Server Restart의 동일 프로세스 내 전체 재초기화

- 등록일: 2026-11-24
- 상태: `complete`
- 우선순위: 높음
- 관련 작업: RF-011, TD-018, TD-035, RF-017

## 배경

현재 `system/server/restart`는 Windows에서 새 서버 프로세스를 실행하고 기존 프로세스를
종료한다. Linux에서는 exec로 프로그램을 다시 실행한다. WinSW는 자신이 시작한 프로세스의
종료를 서비스 종료로 처리하므로 Windows의 새 서버가 서비스 관리 밖에 남을 수 있다.

이 문제는 서비스 등록 스크립트가 아니라 공통 서버의 Restart 수명주기에서 해결한다.
RF-011의 서비스 설치·운영 검증과 분리하며, 서비스 환경의 Restart API 정상 지원은
이 TD 구현 이후 통합 검증한다.

## 확정 범위

- 공개 명령 이름과 요청 형식은 `system/server/restart`로 유지한다.
- 콘솔·Linux·Windows 서비스 모두 동일 프로세스 내 전체 재초기화로 통일하고 PID를 유지한다.
- 기존 안전 종료 절차로 장치·Bus·TCP 연결·worker와 소유 자원을 정리한다.
- TCP 연결 종료 및 제어권 해제를 유지한다. 재접속 시 제어권을 자동 복원하지 않는다.
- 원래 configuration source에서 설정을 다시 읽는다. `.env`/패키지 `config.txt` 경계와 기존 CLI override 적용 원칙을 유지한다.
- Diagnostic·session·runtime·listener를 새로 생성한다. 단순 Bus reconnect로 축소하지 않는다.
- Bus 초기화 실패는 degraded 실행, TCP listener 기동 실패는 오류 기록 후 종료하는 기존 실패 정책을 유지한다.
- 로그/가상장치 저장 worker를 정리하고 잠금을 해제한 뒤 새 설정으로 재생성한다.
  영구 저장 데이터는 삭제하지 않으며 기존 RF-017 저장·복원 계약을 따른다.

## 구현 방향

1. application의 configuration source와 재초기화 루프 소유권을 정리한다.
2. 새 프로세스 실행/exec 대신 기존 세션 종료 후 설정 로드와 초기화를 반복한다.
3. 기존 Restart 응답 전송·연결 종료 순서를 확인하고 유지한다. Success를 재초기화 완료 보장으로 바꾸지 않는다.
4. 반복 Restart, 설정 변경, worker 정리, 초기화 실패와 종료 경합을 검증한다.
5. API Schema 설명·사용 문서·RF-011 제약 안내를 새 의미에 맞춰 갱신한다.

## 제외 범위

- 코드·실행 파일 업데이트 적용 또는 모듈 hot reload.
- Windows 전용 서버 진입점, WinSW 전용 API 또는 Manager/PID 인계 기능.
- 연결/제어권 자동 복원, 모션 자동 재실행, 영구 저장소 Factory Reset.

## 완료 조건

- 실제 별도 Mock 프로세스에서 반복 Restart 전후 PID가 동일하고 child 서버가 추가되지 않는다.
- 설정 파일 변경이 반영되고 새 Diagnostic/runtime/listener가 생성된다.
- 기존 client 연결·제어권이 정리되며 장치/worker/thread/socket/file lock 누수가 없다.
- Bus 실패/degraded, 잘못된 설정 및 listener 실패가 기존 계약대로 처리된다.
- 서비스 Stop 등 외부 종료 중 재초기화가 서버를 되살리지 않는다.
- Windows 서비스 상태를 실행 중으로 유지한 채 API Restart가 동작하는 통합 검증이 통과한다.
- 프로그램 업데이트에는 실제 프로세스 재시작이 필요함을 문서화한다.

## 현재 상태

2026-11-24 구현, 단위/Mock 및 실제 Windows 서비스 Restart 검증 완료.

## 구현 전 확정 — 2026-11-24

- 메인/장치 설정을 모두 재로드하며 Port·Backend·Bus·로그 변경을 반영한다. 최초 CLI 인수와 프로세스 환경변수 입력 및 우선순위를 유지한다.
- API Success는 재초기화 요청 수락이다. 완료 응답/API는 추가하지 않고 새 연결의 system/server/status로 확인한다.
- 재초기화 실패는 기존 degraded/listener 실패 계약을 따른다. 이전 설정으로 자동 복귀하지 않는다. bootstrap 자체가 유효하지 않아 listener를 정할 수 없으면 오류 기록 후 종료한다.
- 접수된 영구 저장은 완료 후 정리한다. Restart가 자동 저장을 수행하지 않으며 미저장 값은 기존 RF-017 계약을 따른다.
- 정리가 실패하면 새 runtime을 겹쳐 실행하지 않는다. 외부 Stop/종료는 Restart보다 우선한다.
- 구현 순서: 공통 재초기화 경로 → 반복·실패·자원 정리 검증 → Windows 서비스 PID 유지 검증.

## 구현 및 검증 결과 — 2026-11-24

- Application이 최초 ConfigurationSource·CLI·환경변수 입력을 보관하고 세션 종료 후 새 설정으로 같은 프로세스에서 재초기화한다. Popen/exec 기반 Restart는 제거했다.
- 정상/degraded/Bus 단절 경로의 TCP client와 runtime 정리를 최종 소유 세션에 연결했다. 정리 실패 또는 종료되지 않은 로그 worker가 있으면 새 세션을 시작하지 않는다.
- 접수된 비동기 저장 완료·저장소 잠금 해제 후 재생성하고 로그는 process가 아닌 session 시작/종료로 표시한다.
- 회귀: 단위/Mock 628개 통과. Restart TCP 통합 1개와 기존 영구 저장 TCP 1개 통과. Node-RED 시험은 제외했다.
- TCP 시험: 반복 Restart, 저장 중 Restart/복원, 제어권 초기화, 설정/Bus 실패의 degraded 및 복구, listener 충돌 시 종료 코드 1, PID와 worker/잠금 정리를 검증했다.
- 새 Windows 패키지 빌드 및 최초 manifest 검사 3,846개 파일/오류 0개.
- 실제 LocalSystem 서비스 16개 검사 통과: 연속 Restart 5회, 매회 제어권 해제, 설정 오류와 복구, Port 변경, Restart 직후 Stop. wrapper PID 21216 / 서버 PID 33032 유지. 종료 후 서버 PID 잔존 0개.
- 외부 Stop 시 재실행하지 않으며 시험 종료 후 서비스는 새 시험 패키지의 Automatic/Stopped 상태다. 재부팅 및 실장비 이동은 수행하지 않았다.
- 근거: [TD-042 검증 기록](../../validation/2026-11-24-td042-restart.md).
