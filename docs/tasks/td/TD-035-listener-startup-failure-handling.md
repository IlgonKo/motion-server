# TD-035 TCP Listener 기동 실패 예외 처리

- 등록일: 2026-09-17
- 상태: `complete`
- 우선순위: 높음

## 배경

수동 Mock 시험 서버 기동 중 TCP bind에서 `PermissionError: [WinError 10013]`이 발생해
처리되지 않은 traceback이 application 진입점까지 전파되었다.
확인 당시 `.env`의 `MOTION_SERVER_PORT=62254`는 Windows TCP 제외 포트 범위
`62217~62316`에 포함되어 있었다. 예약 범위는 환경에 따라 변경될 수 있다.

이는 모션 명령 실패가 아니라 TCP listener 시작 실패다. OS 오류 자체는 발생할 수 있지만,
예상 가능한 시작 실패를 일반 런타임 traceback으로 노출해서는 안 된다.

## 확인된 지점

- `motion_server/server.py`의 `run_main_once()`에서 socket 생성/bind/listen 실패에 대한
  시작 오류 분류가 없다. 정상 runtime 및 장치 초기화 실패 후 degraded 경로가 이 listener를 공유한다.
- `run_configuration_degraded_once()`의 별도 listener도 같은 예외 경계 점검이 필요하다.
- `run_main_once()`에는 runtime 정리용 finally가 이미 있다. 자원 정리가 전혀 없다고
  단정하지 않고, listener 실패에서도 정리되는지 검증한다.

## 범위

- TCP listener 생성/bind/listen의 예상 가능한 OS 오류를 명시적인 기동 실패로 처리한다.
- 권한/예약 포트 거부와 포트 점유를 구별할 수 있도록 endpoint, 작업 단계,
  OS 오류 번호 및 원문 원인을 간결하게 남긴다.
- 정상 시작, runtime degraded 시작, configuration-error 시작에 동일한 실패 처리를 적용한다.
- 시작 실패 시 이미 획득한 runtime/bus/socket 자원의 정리를 검증한다.

## 처리 방향

- listener를 열지 못하면 TCP 서비스나 API Fail 응답은 제공할 수 없다.
  서버 온라인 유지로 표시하지 않고 명확한 실패 로그와 비정상 종료 코드로 통제된 종료를 한다.
- 예상 가능한 OS 시작 오류의 기본 로그에는 Python traceback 대신 원인과 조치 정보를 표시한다.
  원인 자체를 숨기지 않으며 예상하지 못한 프로그래밍 오류까지 일괄 은폐하지 않는다.
- 임의 포트 변경, 무한 재시도, 권한 상승, Windows 예약 포트 삭제는 수행하지 않는다.
- 기존 initialization 분류/최상위 종료 경계와의 정확한 연결 방식은 구현 전 확인한다.

## 제외 범위

- 현재 사용자 설정 자동 수정 및 OS/방화벽/Hyper-V 설정 변경
- API/Feedback 계약 확장, 클라이언트 자동 포트 탐색
- Node-RED 시험 및 실장비 동작 시험

## 완료 조건

- 접근 거부(Windows 10013 또는 대응 errno), 포트 점유, listen 실패 주입 시험에서
  처리되지 않은 traceback 없이 원인/endpoint가 출력되고 비정상 종료 코드가 반환된다.
- 정상/degraded/configuration-error 시작 경로 모두 같은 기준을 만족한다.
- 기동 실패 시 확보된 socket/runtime/bus가 정리되며 정상 listening/ready 상태로 오인시키지 않는다.
- 예약/점유 원인이 해소된 뒤 같은 설정으로 다시 시작할 수 있고 정상 기동 회귀가 통과한다.
- 예상하지 못한 예외의 진단 정보는 유지된다.

## 진행 상황

- 등록 당시 현상, OS 예약 포트 근거와 listener 예외 경계를 확인했다.

### 2026-11-24 구현 및 완료 검증

- `app/listener.py`의 공통 context manager가 socket/setsockopt/bind/listen을 수행한다.
  이 준비 구간의 OSError만 `ListenerStartupException`으로 분류하며 서버 loop 예외는 포함하지 않는다.
- Application 경계에서 endpoint, stage, errno/winerror와 원문을 출력하고 1을 반환한다.
  Python `__main__`과 Windows package 진입점은 반환값을 process exit code로 전달한다.
- socket은 실패·정상 종료 모두 정리하며 기존 runtime finally를 유지한다.
  cleanup OSError가 원래 시작 실패를 덮어쓰지 않도록 별도로 기록한다.
- 정상/degraded/configuration-error × 4개 실패 단계 × 접근 거부/포트 점유 조합,
  정상 loop 진입, 동일 endpoint 재시도, 예상 밖 오류 전파와 두 진입점 종료 코드를 검증했다.
- 관련 unittest 54개 통과 및 `git diff --check` 통과. OS 오류는 주입 시험이며
  실장비·Node-RED 시험과 실제 Windows 패키지 빌드는 수행하지 않았다.

### 2026-11-24 Windows 실제 포트 중복 기동 시험 — 보완 필요

- 기존 실장비 서버 PID 29500이 `0.0.0.0:15000`을 listen하는 상태에서
  `python -B -m motion_server --backend mock --port 15000`을 별도 실행했다.
- 예상: 두 번째 서버가 bind 실패 상세 로그와 종료 코드 1로 종료.
- 실제: mock 초기화 이후 `Motion Server listening on 0.0.0.0:15000`까지 진입했다.
  45초 시험 제한에서 시험용 mock 프로세스만 종료했다. 이는 정상적인 실패 종료가 아니므로 시험 불합격이다.
- 종료 후 기존 PID 29500의 listener가 계속 유지됨을 확인했다. 기존 서버에 제어 명령을 보내거나
  실장비 설정을 변경하지 않았다. 시험 중 기존 연결/운전 상태 전체에 대한 무영향을 검증한 것은 아니다.
- 원인: 공통 listener가 Windows에서도 `SO_REUSEADDR=1`을 사용한다. Windows에서는 이 옵션으로
  점유 중인 동일 포트에 두 번째 bind가 성공할 수 있어 OS 오류 분류 코드까지 도달하지 않는다.
- 후속 수정 방향: Windows에서 `SO_EXCLUSIVEADDRUSE`를 적용하는 등 포트 독점 정책을 보완하고,
  실제 두 listener 중복 기동 시험을 추가한다. 기존 OS 오류 분류 구현은 유지한다.
- TD-035를 in_progress로 재개한다. 이번 요청에서는 제품 코드를 수정하지 않았다.
- 근거: https://learn.microsoft.com/en-us/windows/win32/winsock/using-so-reuseaddr-and-so-exclusiveaddruse

### 2026-11-24 Windows 포트 독점 보완 및 재시험 완료

- Windows listener는 SO_REUSEADDR 대신 SO_EXCLUSIVEADDRUSE를 bind 전에 설정한다.
  다른 플랫폼은 기존 SO_REUSEADDR를 유지한다. 옵션 설정 실패도 기존 시작 오류 경계에서 처리한다.
- 실제 socket으로 중복 listener 거부, 다른 포트의 동시 listener 허용, 종료 후 동일 포트 재기동과
  Windows REUSEADDR 경쟁 socket 거부를 검증했다. 관련 테스트 총 56개 통과.
- 기존 실장비 서버 PID 29500의 15000 listener가 동작하는 상태에서 동일 명령으로 mock 재시험:
  `Endpoint: 0.0.0.0:15000`, `Stage: bind`, `errno/winerror: 10048` 출력 후 종료 코드 1.
  Python traceback과 mock listening 로그 없이 종료했다. 기존 PID 29500 listener는 유지됐다.
- TD-035를 complete로 복구했다. 현재 실행 중인 기존 서버는 재시작하지 않았으며,
  새 독점 옵션은 변경된 코드로 기동하는 서버부터 적용된다.
- 원본 실행 결과: `.codex_output/td035-port-collision-20261124/{stdout.log,stderr.log,result.json}`.
- Node-RED 시험과 Windows 실행 파일 패키지 빌드는 수행하지 않았다.
