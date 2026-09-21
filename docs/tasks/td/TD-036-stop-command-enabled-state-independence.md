# TD-036 Stop Command의 Enabled 상태 독립성

- 등록일: 2026-09-21
- 상태: `complete`
- 우선순위: 높음
- 후속 작업: RF-018

## 배경

RF-018 gamepad client는 stick 중립에서 선택된 Axis에 Stop을 요청한다. L1 release와 공통 TCP Heartbeat
timeout은 Stop이나 Standstill 확인을 선행하지 않고 즉시 Quick Stop으로 전환하는 별도의 Disable
동작이다.
Stop은 현재 운전 상태를 안전하게 제거하는 명령이므로 대상 중 Disabled Axis가 있다는 이유로 전체
요청을 거부하면 안 된다.

현재 `system/axis/stop`과 `system/axes/stop`은 `reject_if_any_axis_disabled()`를 먼저 호출한다. 따라서
다축 요청에 Disabled Axis와 이동 중인 Enabled Axis가 섞여 있으면 이동 중인 Axis까지 Stop 처리를
받지 못할 수 있다. Disabled PV Axis의 이전 target velocity도 명시적으로 0으로 초기화되지 않는다.

## 공개 계약

- `system/axis/stop`과 `system/axes/stop`은 대상 Axis의 Operation Enabled 여부와 관계없이 허용한다.
- Stop은 선택된 모든 Axis의 pending motion target을 안전한 정지 상태로 초기화한다.
- PV Axis는 Enabled 여부와 관계없이 target velocity와 서버 내부 velocity command 상태를 0으로 만든다.
- Enabled PV Axis에는 0 velocity를 적용하여 controlled stop을 수행한다.
- Disabled Axis는 자동 enable하지 않고 Disabled 상태를 유지한다.
- PP/CSP Axis는 현재 위치를 기준으로 target/hold 상태를 동기화하고, Enabled Axis에는 기존 mode별
  controlled stop을 적용한다.
- Jog Axis는 진행 중인 Jog command를 제거한다.
- 대상에 Enabled/Disabled Axis가 섞여 있다는 이유로 요청 전체를 거부하지 않는다. 실제 장치 접근
  실패가 일부 Axis에 발생한 경우에만 기존 PartialFailure 계약을 사용한다.
- Stop 성공은 물리적인 Standstill 완료를 뜻하지 않는다. client는 후속 feedback에서 Standstill을
  확인한다.

## 제외 범위

- gamepad client 구현
- DEC-049와 TD-037의 TCP/network Heartbeat 및 timeout 안전 동작
- gamepad input freshness와 외부 입력 장치 단절 감지
- 자동 Disable 정책
- emergency stop 또는 safety-rated stop

## 완료 조건

- 단축 및 다축 Stop이 Enabled, Disabled와 혼합 Enabled/Disabled 대상에서 거부되지 않는다.
- Disabled PV Axis의 target velocity가 0으로 초기화되고 Disabled 상태는 유지된다.
- Enabled PV Axis는 0 velocity controlled stop으로 전환된다.
- PP/CSP/Jog mode의 기존 정지 의미가 유지된다.
- 일부 Axis 장치 접근 실패만 기존 PartialFailure로 보고된다.
- API 문서와 자동 테스트가 공개 계약과 일치한다.

## 구현 결과

- `stop_motion_axes()`가 선택 Axis별 target 정리와 mode별 Stop을 수행하며 Enabled/Disabled 혼합 상태를
  거부하지 않는다.
- PV는 Disabled 상태에서도 PDO target velocity와 내부 velocity command를 0으로 만들고 controlword를
  변경하지 않는다.
- PP/CSP Halt와 Jog command bit 제거, Axis별 `PartialFailure`를 자동 테스트로 검증했다.
