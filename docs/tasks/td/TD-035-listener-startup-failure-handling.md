# TD-035 TCP Listener 기동 실패 예외 처리

- 등록일: 2026-09-17
- 상태: `open`
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

- 현상, OS 예약 포트 근거와 listener 예외 경계를 확인하고 TD만 등록했다.
- 제품 코드/설정 변경 및 구현 테스트는 수행하지 않았다.
