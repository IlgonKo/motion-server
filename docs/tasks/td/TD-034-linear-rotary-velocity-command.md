# TD-034 Linear/Rotary Velocity Command 허용 범위 정리

- 등록일: 2026-09-04
- 상태: `complete`
- 우선순위: 보통
- 후속 작업: RF-018

## 배경

RF-018은 DualSense 같은 gamepad의 stick 입력으로 X/Y/Z/Rotation을 동시에 수동 velocity 제어하는
reference client다. 이 client는 신규 gamepad API 대신 기존 `system/axes/move_vel`을 사용한다.

현재 Motion Server에는 `pv_allowed`라는 이름의 제한이 남아 있다. 이 제한은 원래
`Profile Velocity mode`를 rotary axis에서만 허용하려는 의도로 보이지만, RF-018에서 필요한 것은
CiA402 Profile Velocity mode라는 내부 운전 모드를 직접 사용자에게 노출하는 것이 아니라
`system/axis/move_vel`, `system/axes/move_vel` API를 통해 linear/rotary axis 모두에 속도 지령을
보내는 것이다.

따라서 TD-034에서는 다음 두 개념을 분리한다.

```text
API velocity command 허용 여부
  → linear/rotary 모두 허용

내부 drive mode 전환 방식
  → 현재 CMMT 구현은 Profile Velocity mode를 사용
  → 사용자는 internal PV mode 제한을 의식하지 않는다
```

command authority, enabled/fault 상태, motion/software limit와 timeout safety는 기존 계약으로
유지한다.

## 현재 확인된 제한 지점

- 서버 `command_profile_velocities()`에서 `reject_if_pv_not_allowed()`를 호출한다.
- `pv_allowed()`는 현재 user position unit이 `rad`, `degree`, `revolution`인 경우만 true다.
- 따라서 linear unit인 `m` 기반 axis는 `move_vel` 요청이 거부될 수 있다.
- Axis Control Panel도 `pv_allowed` metadata를 기준으로 PV mode 버튼과 multi-axis PV 선택을 제한한다.

이 제한은 “사용자 API로서의 velocity command” 기준에서는 과하다. RF-018 gamepad는 linear X/Y/Z와
rotary Rotation을 동시에 속도 지령해야 하므로, linear axis에서도 velocity command가 가능해야 한다.

## 범위

- `system/axis/move_vel`과 `system/axes/move_vel`의 현재 제한 조건 조사
- `pv_allowed`를 velocity command 허용 조건으로 사용하는 경계 제거 또는 재정의
- linear/rotary 모두 `move_vel` 허용
- linear mm/s, rotary deg/s 기준 unit conversion 확인
- axis별 max velocity/motion limit와 software limit 유지 확인
- 다축 `move_vel`을 RF-018의 X/Y/Z/Rotation 수동 velocity command에 사용할 수 있는지 검증
- Axis Control Panel에서 linear axis의 velocity command 경로가 불필요하게 막히지 않는지 확인

## 유지할 기존 안전 계약

- command authority 필요
- axis enabled 필요
- fault 없음
- motion limit 유지
- software limit 유지
- axis별 max velocity 이하 제한
- command timeout 또는 feedback timeout 시 stop

## 결정할 계약

### API 단위

`move_vel` API의 velocity 값은 axis 종류에 따라 다음 user-facing 단위를 사용한다.

```text
linear axis → mm/s
rotary axis → deg/s
```

이 단위는 기존 position/profile setting API와 동일한 axis metadata 변환 체계를 따른다.

### 허용 조건

`move_vel`은 다음 조건을 만족하면 linear/rotary 모두에서 허용한다.

- command authority를 보유한다.
- 대상 axis가 operation enabled 상태다.
- 대상 axis 또는 전체 runtime에 active fault가 없다.
- velocity command가 axis별 motion limit을 초과하지 않는다.
- software position limit 보호가 유지된다.
- runtime/feedback timeout 시 stop으로 수렴한다.

`pv_allowed`는 더 이상 `move_vel` API 허용 여부를 뜻하지 않는다. 필요한 경우 이름을
`profile_velocity_mode_selectable` 또는 유사한 내부/UI 개념으로 변경한다.

### 내부 구현

1차 구현은 신규 drive mode를 만들지 않고 기존 CMMT Profile Velocity mode 경로를 사용한다.
다만 이 내부 mode 사용 여부가 linear axis API 제한으로 노출되면 안 된다.

## 제외 범위

- 신규 gamepad 전용 API
- 신규 다축 jog API
- force/torque control
- trajectory generation
- safety guard 우회
- RF-018 gamepad client 구현

## 완료 조건

- linear axis와 rotary axis 모두 `system/axis/move_vel` 및 `system/axes/move_vel`에서 허용된다.
- 기존 safety validation과 runtime/fault/authority gating이 유지된다.
- mm/s와 deg/s 단위 변환이 axis role별로 회귀 테스트된다.
- 다축 velocity command가 일부 축 실패 시 기존 Fail/PartialFailure 계약과 일치한다.
- neutral/zero velocity 또는 stop 경계가 RF-018에서 안전하게 사용할 수 있도록 명확히 문서화된다.
- Axis Control Panel의 PV/velocity 관련 표시가 서버 계약과 일치한다.

## 구현 계획

1. 서버 velocity command gate 정리
   - `command_profile_velocities()`의 `reject_if_pv_not_allowed()` 의존성을 제거하거나
     velocity command 전용 조건으로 교체한다.
   - `pv_allowed` 이름이 계속 남을 경우 internal mode/UI 선택 의미인지 명확히 한다.

2. limit/unit 검증 보강
   - linear axis는 mm/s, rotary axis는 deg/s로 API 값을 drive value로 변환하는 회귀 테스트를 추가한다.
   - axis별 max velocity 초과가 기존 failure 계약으로 거부되는지 확인한다.

3. multi-axis velocity 검증
   - linear + rotary가 섞인 `system/axes/move_vel` 요청이 한 번에 처리되는지 테스트한다.
   - 일부 축 실패 시 기존 partial/fail 계약과 충돌하지 않는지 확인한다.

4. Control Panel 표시 정리
   - linear axis에서 수동 velocity command가 불필요하게 비활성화되지 않도록 UI 제한을 정리한다.
   - 단, RF-018 gamepad client 구현은 TD-034 범위에 포함하지 않는다.

5. 문서 정합화
   - API 문서의 `move_vel` 단위와 허용 조건을 업데이트한다.
   - RF-018의 선행 조건이 TD-034 완료 기준과 일치하는지 확인한다.

## 구현 결과

- `pv_allowed`를 rotary 전용 조건이 아니라 known linear/rotary axis velocity mode 사용 가능 조건으로
  정리했다.
- 서버 `move_vel` 경로에서 rotary 전용 `reject_if_pv_not_allowed()` gate를 제거했다.
- `move_vel` target velocity가 axis별 motion limit을 초과하면 `LIMIT_VIOLATION`으로 거부하도록
  명시 검증을 추가했다.
- Axis Control Panel의 PV/velocity mode 표시도 linear/rotary 모두 허용하는 서버 계약과 맞췄다.
- API 문서에 `move_vel` 단위와 linear/rotary 혼합 다축 velocity command 계약을 추가했다.
- Linear + rotary 혼합 `system/axes/move_vel`, velocity limit 초과, axis metadata 회귀 테스트를
  추가했다.
- 전체 unittest 418개가 통과했다.
