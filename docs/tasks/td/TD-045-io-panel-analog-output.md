# TD-045 IO Control Panel 아날로그 출력 UI 누락

## 현재 상태

- 등록일: 2026-11-26
- 상태: `open`
- 이번 작업은 등록만 수행하며 구현하지 않는다.

## 문제와 확인 근거

- `control_panel/io_control_panel/control_panel.py`의 출력 조작 영역은 Digital Output이며
  `apply_digital_output()`만 연결되어 있다. 모듈 목록도 digital_outputs 기준이다.
- Virtual Input Simulation의 Analog는 `system/simulation/io/input_write`로 가상 AI 입력을
  주입하는 기능이며 AO 출력 UI가 아니다.
- 서버의 `system/io/output_write` Schema는 `kind="analog"`을 지원한다.
  `motion_server/handlers/command/io_output_write.py`에서
  `CPXRxPDO.set_module_analog_output()`으로 연결되어 모듈/채널과 raw 정수 범위를 검증한다.
- 따라서 서버 기능 추가가 아니라 Panel에서 기존 AO API를 사용할 수 없는 UI 누락이다.
- DO로 구동되는 실린더 시험 가능 여부는 실제 출력 모듈·배선·장치 구성에 달려 있다.
  Panel의 DO 지원 확인만으로 특정 실린더 운전 가능을 보장하지 않는다.

## 수정 방향과 공개 계약

- AO 조작에 IO, Module, Channel, 정수 출력값, Apply를 제공한다.
- Module 선택은 실제 구성에서 analog_outputs가 있는 모듈을 대상으로 한다.
  UI Module은 기존 API의 `slot`에 대응한다.
- 기존 `system/io/output_write`에 `io`, `slot`, `kind="analog"`, `channel`, `value`를 보낸다.
  slot/channel/value는 JSON 숫자로 전송하고 문자열 숫자에 의존하지 않는다.
- 값은 PDO raw 정수다. V/mA 등의 물리 단위 값으로 표시하거나 임의 변환하지 않는다.
- 기존 command authority·응답/Fail·연결 실패 처리 경로를 재사용한다.
- 명시적 Apply에서만 전송하며 화면 생성·선택 변경·재접속으로 출력하지 않는다.
- AO 미구성 상태와 입력 오류를 표시하고 DO 및 Virtual Input Simulation과 구분한다.
- 표시되는 출력 설정값을 실제 전압/전류 측정값으로 표현하지 않는다.

## 구현 전 확인할 사항

- 별도 Analog Output 영역을 추가할지 기존 출력 영역에 종류 선택을 둘지 결정한다.
- IO/모듈/채널 변경 시 값 표시 및 초기값 정책을 정한다. 선택만으로는 전송하지 않는다.
- 채널 범위와 모듈별 signed/bit-width 정보를 기존 구성에서 어떻게 안내할지 확인한다.
  서버 검증을 대체하는 별도 장치 제한 규칙을 만들지 않는다.

## 제외 범위

- 새 서버 API, 물리 단위 스케일 변환, 자동 출력 시퀀스.
- Virtual AI 입력 주입을 AO 출력으로 재사용하는 변경.
- TD-043 진단/유효성, TD-044 저장 명령 의미 변경.
- 별도 지시 없는 실장비 출력 조작 및 Node-RED 시험.

## 완료 조건

- AO 지원 모듈의 채널에 raw 정수 출력값을 지정하여 기존 API로 전송할 수 있다.
- IO/slot/channel/value 매핑과 JSON 숫자 형식, 명시적 Apply당 단일 전송을 검증한다.
- AO 미구성, 잘못된 입력/범위, 제어권 없음, API Fail과 연결 실패가 명확히 표시된다.
- Mock에서 지정 AO 값 반영과 다른 모듈/채널 값 보존을 확인한다.
- 화면 초기화·선택 변경·재접속이 출력을 변경하지 않음을 확인한다.
- 기존 DO 조작과 Virtual Input Simulation 회귀 및 사용 문서 갱신이 완료된다.
