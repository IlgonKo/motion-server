# TD-042 Server Restart의 동일 프로세스 내 전체 재초기화

- 등록일: 2026-11-24
- 상태: `open`
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
- 이번 등록 작업에서의 TD-042 코드 구현.

## 완료 조건

- 실제 별도 Mock 프로세스에서 반복 Restart 전후 PID가 동일하고 child 서버가 추가되지 않는다.
- 설정 파일 변경이 반영되고 새 Diagnostic/runtime/listener가 생성된다.
- 기존 client 연결·제어권이 정리되며 장치/worker/thread/socket/file lock 누수가 없다.
- Bus 실패/degraded, 잘못된 설정 및 listener 실패가 기존 계약대로 처리된다.
- 서비스 Stop 등 외부 종료 중 재초기화가 서버를 되살리지 않는다.
- Windows 서비스 상태를 실행 중으로 유지한 채 API Restart가 동작하는 통합 검증이 통과한다.
- 프로그램 업데이트에는 실제 프로세스 재시작이 필요함을 문서화한다.

## 현재 상태

등록만 완료했다. 구현과 서비스 환경 Restart 시험은 아직 수행하지 않았다.
