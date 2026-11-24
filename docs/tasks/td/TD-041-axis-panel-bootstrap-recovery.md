# TD-041 Axis Control Panel 초기 연결 화면의 Bus Reconnect

- 등록일: 2026-11-24
- 상태: `complete`
- 우선순위: 보통
- 관련 작업: RF-005, TD-024, TD-039

## 배경

EtherCAT discovery 실패 시 축 feedback이 없어 AxisPanelBootstrap 초기 연결 화면에 머무른다.
기존 제어권 및 Bus Reconnect 버튼은 축 수 확정 후 생성되는 본 화면에만 있어,
초기화 실패 상태에서 Panel로 복구를 요청할 수 없었다.

## 확정 범위

- 초기 연결 화면에 명시적 제어권 요청/해제 및 Bus Reconnect 버튼만 추가한다.
- 기존 client의 authority 및 `system/bus/reconnect` 메서드를 사용한다.
- 요청 결과, 전송 실패 및 복구 중 연결 단절을 초기 화면에 표시한다.
- 축 feedback으로 topology가 확정된 후 본 화면으로 전환하는 기존 동작을 유지한다.
- authority 자동 획득, 명령 자동 재전송, 임의 축 수 생성 및 서버 계약 변경은 하지 않는다.

## 재평가 및 원복

- 최초 Bus Fault Reset 버튼 정리로 등록했으나 사용자 요청에 따라 실제 초기 화면 복구 문제로 범위를 정정했다.
- 본 화면의 Bus Fault Reset 버튼, diagnosis callback, client 전송/응답 처리 추가를 모두 원복했다.
- 초기 화면에 추가했던 Bus Fault Reset, Server Fault Reset, Server Restart도 제거했다.
- Bus Fault Reset 전용 신규 테스트를 삭제했다. 기존 서버 Fault Reset API는 변경하지 않았다.

## 완료 조건 및 검증

- 축 수 0인 초기 화면에서도 제어권 요청과 Bus Reconnect 버튼을 사용할 수 있다.
- 한 번 조작에 한 번 요청하며 reconnect가 authority를 자동 요청하지 않는다.
- 응답/Fail/전송 실패 및 연결 단절을 표시하고 명령을 자동 재전송하지 않는다.
- 축 feedback 수신 후 본 화면으로 정상 전환한다.
- 초기 화면의 실제 Tk 버튼을 숨김 창에서 생성하여 invoke 및 상태 전환을 검증했다.
  관련 테스트 41개 통과. 실장비 제어 명령은 전송하지 않았다.

## 변경 파일

- `control_panel/axis_control_panel/control_panel.py`
- `tests/test_axis_bootstrap_recovery.py`
- TD-041 목록/상세 문서 및 Worklog
