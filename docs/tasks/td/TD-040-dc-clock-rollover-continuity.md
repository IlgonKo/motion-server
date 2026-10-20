# TD-040 32 bit DC Clock Rollover 연속 시간 보정

- 등록일: 2026-10-20
- 상태: `complete`
- 우선순위: 높음
- 관련 작업: TD-018, TD-030, RF-005

## 배경

같은 2 ms cycle, 같은 명령과 drive 설정에서 PLC와 달리 Motion Server의 CSP 운전 중
축 소음이 발생한다는 사용자 보고를 바탕으로 EtherCAT capture와 DC scheduling 경로를 확인했다.
Motion Server의 velocity offset은 의도적으로 켜져 있으며, 초기화 후 PP mode와 실제 CSP 운전은
서로 다른 구간이다. 두 조건 자체를 설정 오류로 판단하지 않는다.

관련 capture는 다음과 같다.

- `Reference/MotionServer Packet/CSP_Repeat_2ms.pcapng`
- `Reference/MotionServer Packet/CSP_Initialize_2ms.pcapng`
- `Reference/PLC Packet/Moving.pcapng`
- `Reference/PLC Packet/Boot.pcapng`

## 확인된 원인

- 기준 CMMT slave `0x1001`의 ESC feature register `0x0008` 값은 `0x0407`로,
  DC는 지원하지만 시계 폭은 32 bit다. 뒤쪽 I/O slave의 64 bit 지원과 구분해야 한다.
- 32 bit ns 시각은 `4.294967296 s`마다 순환한다. raw 시각에 바로 2 ms modulo를
  적용하면 rollover에서 `2^32 % 2,000,000 = 967,296 ns`의 위상 불연속이 생긴다.
- 반복 운전 capture의 frame `456 → 458`에서 DC 경과가 약 `0.96631 ms`,
  송신 frame `455 → 457`에서 간격이 약 `1.1166 ms`로 짧아지는 현상을 관찰했다.
  같은 capture의 후속 rollover에서도 짧은 주기가 반복됐다.
- 기존 `get_dc_time_ns()`는 native raw 값을 반환했고 scheduler와 phase lock이 이를
  사용했다. rollover 시 scheduling 위상이 바뀌는 코드 경로를 수정 대상으로 확정했다.
- 이 관찰은 DC 시간 연속성 결함의 근거다. 축 소음의 단독 원인이나 수정 후 소음 해소를
  실장비 시험 없이 확정하지 않는다.

## 관련 위치

- `ethercat/distributed_clock.py`
- `ethercat/pysoem_master.py`
- `motion_server/server.py`
- `tests/test_dc_rollover.py`
- `tests/test_error_contract_static.py`

## 확정 설계 및 구현 경계

- `config_dc()` 후 SOEM이 선택하는 첫 DC 지원 slave의 ESC register `0x0008`을 읽는다.
  bit 2로 DC 지원, bit 3으로 64 bit 여부를 판별한다. 시각 값의 크기로 폭을 추측하지 않는다.
  기준 시계 부재나 feature 읽기 실패는 초기화 오류로 처리한다.
- startup/cyclic 수신에서 WKC가 양수일 때만 DC sample을 반영한다. 32 bit 시각은
  `(raw - previous_raw) & 0xffffffff`를 Python 정수에 누적하고 64 bit 시각은 원래 값을
  보존한다. Python 정수 누적에는 고정 64 bit 정수의 overflow 제한도 없다.
- getter는 마지막 수신의 정규화된 값을 반환한다. 반복 조회에서 sample을 중복 반영하지 않는다.
  수신/송신 timing field, 송신 시각 추정, scheduler와 phase lock은 같은 시간 기준을 사용한다.
- 정상 rollover에서는 누적값을 초기화하지 않는다. close/connect/DC 재구성 때 epoch를
  초기화하고 bus 복구 후 phase-lock 적분값과 보정값도 초기화한다.
- 32 bit sample의 host monotonic 간격이 `2^31 ns` 이상이면 wrap 횟수 판별을 중단한다.
  DC 경과와 host 경과의 차이가 `max(100 ms, host 경과의 10%)`를 넘는 경우도
  `CommunicationException("dc_clock_discontinuity")`로 기존 연결 복구 경로에 전달한다.
  이 허용치는 작은 clock reset을 모두 검출하지는 못한다.
- WKC가 0 이하인 수신은 기존 DC 값과 수신 timestamp를 유지한다. 양수 WKC만으로 모든
  datagram의 유효성을 독립적으로 보장하는 것은 아니며 기존 WKC 진단은 계속 적용한다.
- 내부 helper 변경이며 공개 backend 메서드나 capability 요구사항을 추가하지 않는다.
  DEC-026/027과 RF-005의 명시적 bus reconnect 경계를 사용한다.

## 제외 범위

- CSP 궤적, velocity offset, PDO mapping 및 drive parameter 변경
- EtherCAT WKC 진단이나 recovery 정책의 전면 재설계
- 운영 서버 배포/재기동, 실장비 축 구동과 Node-RED 시험

## 완료 조건

- 기준 slave의 실제 시계 폭에 따라 32 bit rollover와 64 bit 시각을 처리한다.
- 1/2/4 ms cycle의 다중 rollover에서 위상과 송신 deadline이 연속적으로 유지된다.
- startup과 cyclic 수신이 같은 누적 시각을 사용하고 반복 조회는 값을 변경하지 않는다.
- 재연결/재구성 시 epoch가 초기화되고 불연속 sample은 기존 통신 오류 경로로 처리된다.
- 관련 PDO/backend/초기화/복구 회귀가 통과하고 실장비 미검증 범위를 기록한다.

## 진행 상황

### 2026-10-20 구현 및 자동 검증

- `_DcTimeUnwrapper`와 수신 시각 캐시를 구현하고 startup/cyclic 수신에 적용했다.
  bus 복구 후 phase-lock 상태를 초기화하도록 server loop를 보완했다.
- 캡처의 `4293473308 → 505822`를 `1,999,810 ns`의 정상 경과로 계산하는 것을 검증했다.
- 1/2/4 ms 각각 12,000 cycle의 다중 rollover, 64 bit 보존, 혼합 slave의 기준 시계 선택,
  startup→cyclic 연속성, 반복 조회, timeout, 재연결 및 불연속 실패를 자동 검증했다.
- rollover 전용 테스트 13개를 포함한 관련 unittest 80개가 통과했다. 마지막 timing field
  초기화 보완 후 전용 테스트 13개를 재실행해 통과했고 `git diff --check`도 통과했다.
- 기존 DC startup의 오류 변환/실패 진단 함수 두 곳을 정적 broad-catch 승인 목록에 동기화했다.
- 전용 검증 명령: `python -m unittest discover -s tests -p 'test_dc_rollover.py' -v`
- 회귀 검증 대상: `test_dc_rollover`, `test_pysoem_dc_startup`, `test_pdo_transport_parity`,
  `test_backend_capabilities`, `test_bus_recovery`, `test_recovery_refresh`,
  `test_staged_initialization`, `test_initialization_lifecycle`, `test_runtime_diagnostic`,
  `test_error_contract_static`.
- 실제 검증 환경은 Windows Python 3.14와 설치된 프로젝트 의존성이다. 처음 사용한 별도
  Python 환경의 `jsonschema` 누락은 프로젝트 실행 환경으로 전환해 해결했다.

## 후속 확인

- 구현 및 자동 검증 완료 상태이며 실장비에서 소음이 해소됐다는 의미는 아니다.
- 수정 버전의 2 ms CSP 운전을 재캡처해 여러 rollover 전후의 송신 간격, DC 경과,
  WKC와 target/actual position을 확인하고 같은 명령 조건에서 축 소음을 비교한다.
- 실장비 구동과 Node-RED 시험은 이번 작업에서 수행하지 않았다.
