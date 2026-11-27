# Motion Server 사용자 매뉴얼

개정 2.0 · 2026-11-24 · Basic mode

Motion Server와 Axis/IO Control Panel을 이용해 축과 I/O를 제어하는 방법을 설명한다.
장비 설치, 축 commissioning, 정상 서버 기동과 실제 이동 경로 확인은 사용자가 담당한다.
ROS/ROS2 및 MoveIt 연동은 지원 범위에서 제외한다. 기존 Rev. 1.0 Word 문서는 현재 API의 사용 안내로 사용하지 않는다.

Windows에서는 CSP를 포함한 동기 제어 기능을 공식 지원하지 않는다. Windows의 주기 성능과
실시간 동기 제어 성능은 보증하지 않으며, CI와 Mock 테스트는 기능 동작을 검증한다(DEC-057).

## 시작과 제어권

서버를 먼저 실행하고 Panel의 Host와 Port를 맞춘다. 같은 PC에서는 Host를 `127.0.0.1`로 설정한다.
서버는 `0.0.0.0`에 listen한다. 서버와 Panel의 포트가 같아야 하며 기본값은 15000이다.
연결과 제어권은 별개다. `Request Authority`로 제어권을 획득한 다음 조작한다.
다른 client가 소유하고 있으면 서버의 Fail 원인을 확인한다. 자동으로 소유권을 빼앗지 않는다.

정상 제어권 해제는 기존 motion을 Stop한다. 소유 client의 연결 유실은 기존 안전 종료 정책에 따라
전체 축 motion target을 제거하고 Disable/Quick Stop 및 제어권 회수를 수행한다.
재연결 후 제어권은 명시적으로 다시 요청한다. 이전 이동을 자동 재실행하지 않는다.

## Axis Control Panel

시작 화면에서 Host와 Port를 확인한 뒤 `Connect`를 누른다. 시작 시 기본 주소로 자동 연결하지 않는다.
선택한 서버의 첫 feedback으로 축 화면을 한 번 구성한다. 다른 축 구성의 서버로 바꿀 때는 Panel을
다시 실행하고 시작 화면에서 해당 서버 주소를 선택한다.

첫 feedback의 축 배열로 축 수를 확정해 화면을 구성한다. 설정의 물리 slave 순서와 API의 axis index는
다르다. 예를 들어 slave 0이 축, slave 1이 IO, slave 2가 축이면 축 index는 0과 1이다.

EtherCAT discovery 실패로 축 정보가 없어도 초기 연결 화면에서 제어권 요청/해제와
Bus Reconnect를 사용할 수 있다. 실제 축 feedback을 받은 뒤 본 화면으로 전환한다.

선택 축의 상태, 단위, position/velocity와 Fault 내용을 확인한다. Enable, Homing, 이동, Stop,
Disable은 서버 API의 상태·권한·리밋 검증을 따른다. Homing 미완료 이동은 서버가 거부한다.
Panel이나 외부 시퀀스에 서버와 다른 인터락을 중복 구현하지 않는다.

위치·속도·가감속 단위는 축 metadata에 따른다. 모든 축을 mm로 취급하거나 count를 직접 적용하지 않는다.
Profile velocity 설정은 SDO write 후 해당 OD가 RxPDO에 있으면 송신 값도 함께 갱신한다.
실제 장치 상태가 반영된 후 readback을 확인한다. 설정 실패 시 반환되는 Fail 정보를 확인한다.

Jog는 RxPDO의 mode/command 경로를 사용한다. 개별 Drive Fault가 발생하면 그 축의 motion을 중단하고
Enable을 요청하지 않는 상태로 이전 운전 모드를 복원한다. 다축 연계 복구는 별도 계약이며
한 축의 상태만으로 시퀀스 전체 완료를 판단하지 않는다.

## IO Control Panel

실제 구성의 station ID, module slot과 channel을 선택한다. DI/DO는 boolean이며 AI/AO는 기본적으로
PDO raw 정수다. 물리량 환산은 장치·센서 설정을 확인한 뒤 적용한다.

EtherCAT catalog는 `system/io/ethercat/param_catalog`로 본체와 구성 모듈을 함께 조회한다.
AP module parameter와 IO-Link ISDU parameter는 각각 AP/IOL 전용 API를 사용한다.
IO-Link port는 0부터 시작한다. IODD의 선택 process-data profile은 장치의 실제 설정과 같아야 한다.
서버의 profile 선택만으로 센서의 process-data mode가 변경되는 것은 아니다.

CPX의 `system/io/param_storage`는 저장 명령이 아니라 저장 모드 선택이다.
`volatile`은 0x27F1:01에 0, `non_volatile`은 1을 쓴다. Factory reset은 이 API 범위에 없다.
연속 모드 변경이 장치에서 거부되면 Fail 내용을 확인하고 장치 처리 시간을 둔다. 자동 재시도하지 않는다.
CPX가 지원하지 않는 `system/io/reset`, `system/io/restart`는 Unsupported로 응답한다.

Virtual IO 입력 조작 UI는 항상 표시한다. 현재 입력 조회는 `system/io/input_read`를 사용한다.
Virtual 입력 write/reset은 기존 simulation API를 사용하며 실장치 backend에서는 Unsupported가 반환된다.
별도 simulation enabled 설정이나 backend 판별용 feedback 필드는 없다.

## Diagnostic과 복구

운전 진단은 NORMAL/ALARM/FAULT이며 API 결과 success/fail과 구분한다. 명령 Success가 Fault 해제나
이동 완료를 뜻하지 않는다. Latching Fault는 조건 해제와 fault-reset에 따른 acknowledge 계약을 따른다.
이력은 현재 서버의 Diagnostic 저장소에서 관리한다. 서버 restart를 넘는 영구 이력 검색은 보장하지 않는다.

Bus Reconnect는 Bus/프로세스 데이터 복구를 확인하는 명령이다. 남아 있는 Drive Fault는 축별로 확인한다.
복구 후 자동 Enable이나 motion 재개는 없다. 동기 복구 중 다른 API/Heartbeat 처리가 지연되어
TCP가 끊길 수 있다. 재연결 후 `system/server/status`, `system/bus/status`로 결과를 확인하고
필요한 제어권을 다시 요청한다. 응답을 받지 못했다고 reconnect를 자동 재전송하지 않는다.

## 외부 프로그램의 API 사용

API는 TCP에서 newline으로 구분된 JSON이다. 모든 client는 transport Heartbeat에 응답해야 한다.
공식 Python reference client를 사용하면 수신과 Heartbeat 처리를 재사용할 수 있다.
요청·응답은 `request_id`로 연결한다. `system/feedback`은 개별 요청 완료 응답이 아니다.

숫자 필드는 JSON 숫자를 사용한다. `axis: 0`, `index: 24641`은 가능하지만 숫자 문자열이나
JSON 안의 `0x6081` 표기는 사용하지 않는다. Panel 입력의 hex 문자열 변환과 wire 형식을 혼동하지 않는다.

```json
{"cmd":"system/authority/request","request_id":"authority-1"}
{"cmd":"system/server/status","request_id":"status-1"}
{"cmd":"system/bus/status","request_id":"bus-1"}
```

성공은 `{"type":"...","result":"success","data":{...}}`, 실패는
`{"type":"...","result":"fail","failure":{"code":"...","message":"..."}}` 형식이다.
각 명령의 정확한 필드와 단위는 함께 제공하는 `motion_server_api_basic.md` 및 JSON Schema를 따른다.
이동 완료를 기다리는 기준과 시퀀스 timeout은 사용자 시퀀스 책임이며 API Schema의 범위가 아니다.

## 문제 확인 순서

1. Panel TCP 연결과 서버 initialization 상태를 구분한다.
2. 시작 실패의 stage, cause, 상세 원인을 보관한다.
3. EtherCAT discovery 실패면 NIC, 케이블, 전원과 실제 slave 수를 확인한다.
4. Identity/PDO mismatch면 profile·module·stride 설정을 확인한다. 오류를 무시하고 운전하지 않는다.
5. TCP bind 실패면 다른 서버의 포트 점유 또는 OS 접근 거부를 확인한다. 두 번째 서버는 종료 코드 1로 종료한다.
6. 서버 설정 변경은 서버 재시작 후 반영한다. Panel 코드 변경만 적용할 때는 Panel을 다시 실행한다.

지원 요청에는 서버/Panel 로그, 사용 설정, artifact manifest, OS와 장치 firmware 정보를 제공한다.
실제 검증 완료 범위는 `deployment_validation.md`를 확인한다.
