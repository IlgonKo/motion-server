# TD-039 EtherCAT Slave 탐색 실패 예외 분류 및 로그 정리

- 등록일: 2026-09-22
- 상태: `complete`
- 우선순위: 높음
- 관련 작업: TD-018, TD-035

## 배경

실장치 서버 시작 중 다음 연결 실패가 일반 RuntimeError traceback으로 노출되었다.

```text
Motion Server initialization failed: stage=bus_connection cause=bus_connection_failed
RuntimeError: Expected 3 EtherCAT slaves, found -1.
```

예상 가능한 장치 탐색/연결 실패는 원인을 보존한 initialization failure로 안내해야 한다.
`-1`은 실제 장치 수로 표현할 값이 아니므로 탐색 반환값과 정상 탐색된 장치 수를 구분해야 한다.
반환값의 정확한 의미와 통신 실패 원인은 구현 시 사용 PySOEM/SOEM 계약을 확인한다.
이 로그만으로 케이블/인터페이스 문제나 서버 프로세스 종료를 단정하지 않는다.

## 확인된 원인

- `ethercat/pysoem_master.py`의 `connect()`가 `config_init()` 결과를 기대 slave 수와 비교하고
  부족하면 일반 `RuntimeError`를 발생시킨다. 음수 결과도 동일한 count mismatch 문구로 처리한다.
- `motion_server/app/initialization.py`의 `log_initialization_failure()`는 예상 예외에 속하지 않는
  `RuntimeError`에 `traceback.print_exception()`을 호출한다.
- 따라서 이번 traceback은 initialization failure 로깅 경로에서도 출력된다.
  TCP bind 실패를 다루는 TD-035와 달리, 연결 실패 분류 및 기본 로그 정책 문제로 별도 관리한다.

## 범위

- EtherCAT 탐색 실패 및 기대 장치 수 부족을 명시적인 예상 연결 실패로 분류한다.
- 음수 탐색 결과와 정상 탐색 후 장치 수 부족을 구분하여 설명한다.
- 기본 로그는 stage/cause와 상세 원인을 출력하되 예상 연결 실패의 Python traceback은 노출하지 않는다.
- 기대 장치 수, 탐색 원본 반환값 또는 실제 발견 수, 설정 인터페이스 등 확인에 필요한 정보를 보존한다.
- 기존 degraded 서버 유지, 상태 조회 및 recovery 계약과 실패 자원 정리를 유지한다.

## 제외 범위

- 모든 RuntimeError/예외 traceback을 일괄 숨기는 처리
- 실제 장치 구성/인터페이스 자동 변경, 임의 재시도 또는 recovery 정책 확장
- TCP listener 기동 실패 처리(TD-035), 실장비 동작 시험 및 Node-RED 시험

## 완료 조건

- `config_init()` 음수 반환과 0/기대 수 미만 정상 반환을 각각 시험하여 예상 연결 실패로 분류한다.
- 위 실패의 기본 출력에 Python traceback이 없고 원본 반환값/발견 수와 기대 수 등 상세 원인이 남는다.
- 음수 값을 실제 발견 장치 수처럼 안내하지 않는다.
- listener 기동이 가능한 조건에서 degraded TCP 상태 조회 및 기존 허용 recovery가 유지된다.
- 실패 중 열린 transport/runtime 자원이 정리되고 정상 탐색·연결 회귀가 통과한다.
- 예상하지 못한 프로그래밍 오류의 진단 정보는 유지한다.

## 등록 당시 진행 상황

- 사용자 로그 및 현재 예외 생성/로깅 경로를 확인해 등록했다.
- 실제 버스 재접속, 코드/설정 변경, 구현 시험은 수행하지 않았다.

### 2026-10-20 구현 및 자동 검증

- 음수 반환은 `EtherCATDiscoveryException` (`CommunicationException` 하위)으로 전달하고
  `result`로 기록한다. 특정 음수 값의 native 의미나 케이블 원인은 추정하지 않는다.
- 0 또는 기대 slave 수 미만의 정상 반환은 `ConfigurationException`으로 분류한다.
- 두 경로 모두 `BUS_CONNECTION_FAILED` initialization cause 및 기존 Initialization Fault로
  처리하고, 예상 실패의 기본 로그에는 traceback을 출력하지 않는다.
- 음수/0/부족/정상 반환, transport 정리, degraded API 및 recovery, 예상하지 못한 오류 로그를
  포함한 관련 자동 테스트 85개가 통과했다. 실장비 시험과 Node-RED 시험은 수행하지 않았다.

### 2026-11-24 재검증 및 완료 처리

- 기존 제품 코드에 음수 탐색 결과와 장치 수 부족의 typed exception 분류가 이미 반영되어 있음을 확인했다.
  추가 제품 코드 변경 없이 상단 및 Remaining Tasks의 누락된 완료 상태를 갱신했다.
- EtherCAT state transition logging, initialization model/lifecycle, bus recovery 및 TD-035 관련
  테스트 총 54개가 통과했다. 탐색 음수/0/부족/정상 반환, transport 정리, 예상 실패 traceback 제외,
  예상하지 못한 RuntimeError traceback 유지와 degraded/recovery 경로를 재검증했다.
- 이 자동 재검증 시점에는 실장비 연결과 Node-RED 테스트를 수행하지 않았다. 후속 실장비 결과는 아래에 기록한다.

### 2026-11-24 실장비 케이블 분리 기동 및 Bus 복구 확인

- 구성: pysoem, CMMT-AS 5축과 CPX-AP-I-EC 1대, 총 6 slave, TCP port 15000.
- EtherCAT cable을 분리한 상태에서 기동하여 `bus_connection / bus_connection_failed`를 확인했다.
  상세 로그는 `EtherCAT discovery failed: result=-1 expected_slaves=6`와 interface를 표시했고,
  Python traceback 없이 TCP listener 및 degraded server loop가 유지됐다.
- Axis Control Panel에서 TCP 연결과 `initialization error`, `initialized no`, Fault 1 / Alarm 0,
  `process data stale`, `SERVER_INITIALIZATION_FAILED` 표시를 확인했다.
- cable 연결 후 authority를 획득하고 `system/bus/reconnect`를 1회 전송했다. 동기 recovery 중
  시험 client에서 Heartbeat timeout으로 연결이 종료되어 reconnect의 직접 Success/Fail 응답은 받지 못했다.
- 새 읽기 전용 연결에서 확인한 결과:
  - server: `initialized=true`, `runtime_state=normal`, `initialization_failure=null`.
  - bus: `available=true`, `connected=true`, device 6 / axis 5, WKC `18/18`, `wkc_ok=true`.
  - server/bus diagnostic: `normal`, 활성 status 없음. Axis mode display는 모두 `1`.
- 판정: TD-039의 예상 탐색 실패 로그, degraded 상태 조회 및 이후 Bus 복구를 실장비에서 확인했다.
  복구 중 client 연결 단절은 DEC-056에 따라 허용하며, 복구 성공은 재접속 후 상태 조회로 확인했다.
- 이 시험에서 motion/enable/axis fault-reset, TD-035의 실제 포트 충돌·접근 거부 시험 및
  Node-RED 시험은 수행하지 않았다. owner 연결 종료 안전 처리 자체의 실장비 검증 결과로 확대하지 않는다.
