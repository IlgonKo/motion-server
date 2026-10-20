# RF-018 Gamepad Manual Multi-Axis Velocity Control

- 등록일: 2026-09-04
- 상태: `in_progress`
- 우선순위: 보통
- 선행 작업: TD-034, TD-036, TD-037, TD-038
- 구현 위치: `control_panel/gamepad_control_panel`
- Windows 실행: `scripts/windows/gamepad.ps1`

## 배경

DualSense 같은 gamepad를 사용하여 Motion Server 축을 수동으로 조작한다. 주 목적은
3축 + rotation을 사람이 스틱으로 동시에 움직이는 manual velocity pendant를 제공하는 것이다.
단축 수동 조작도 보조 모드로 함께 제공한다.

Gamepad 입력은 Motion Server core 기능이 아니라 Axis/IO Panel과 같은 독립 Control Panel로 구현한다. Motion Server와는
기존 TCP API만 사용하며, command authority, runtime/fault 상태, motion limit와 software limit는
기존 서버 계약을 그대로 따른다.

## 핵심 구조

```text
DualSense / Gamepad
→ control_panel/gamepad_control_panel
→ Motion Server TCP API
→ system/axes/move_vel
→ Axis velocity control
```

Motion Server core에는 OS별 HID/gamepad dependency를 추가하지 않는다.

Windows 입력 계층은 `pygame-ce`의 stable `pygame.joystick` API를 사용한다. Tkinter GUI와 입력 adapter를
분리하고, gamepad는 name + GUID로 선택하며 DualSense axis/button 번호는 GUID별 mapping profile로
관리한다. `pygame._sdl2.controller` experimental API, XInput/DS4Windows 의존과 직접 HID report 구현은
1차 범위에서 사용하지 않는다. pygame event queue는 GUI focus와 관계없이 주기적으로 pump한다.

## 운전 모드

### Multi-axis mode

기본 모드다. 설정에서 활성화한 X/Y/Z/Rotation role 1~4개를 동시에 velocity 제어한다.

```text
Left Stick X/Y  → X/Y velocity
Right Stick Y/X → Z/Rotation velocity
```

Motion Server에는 기존 `system/axes/move_vel`로 한 번에 전달한다.

### Single-axis mode

선택된 축 하나만 velocity 제어한다. 장비 setup, 단일 축 확인, 축별 방향 검증에 사용한다.

```text
D-pad left/right → selected axis 변경
Left Stick Y     → selected axis velocity
Homing button    → selected axis homing (기본 Cross)
```

Single-axis mode에서도 Enable trigger deadman, deadzone과 timeout 안전 정책은 동일하게 적용한다. Left Stick Y가
deadzone을 벗어나면 선택 Axis에 `system/axis/jog_start`, 중립으로 돌아오면 `system/axis/jog_stop`을
보낸다. 방향이 바뀌면 기존 Jog를 정지한 뒤 반대 방향으로 다시 시작한다. 1차 구현의 Jog speed는
안전하게 `slow`로 고정하며 D-pad up/down speed scale은 Multi-axis mode에만 적용한다.

`actions.mode_toggle`로 Multi-axis/Single-axis mode를 전환한다(기본 Touchpad click). mode 전환은 Disarmed, 모든 stick 중립과
모든 Axis Standstill 조건에서만 허용한다. Armed, Arming 또는 Releasing 상태의 전환 입력은 무시하고
상태 화면에 거부 이유를 표시한다.

## 1차 입력 매핑

### 공통

```yaml
Enable trigger press         : 정지·중립 조건 확인 후 mapped axes enable 및 Armed 진입
Enable trigger hold          : Deadman / Armed 유지
Enable trigger release       : mapped axes 즉시 disable(Quick Stop) 및 Disarmed 전환

speed_up/down    : speed scale 변경 (기본 D-pad up/down)
fault_reset      : mapped axes fault_reset (기본 Square)
stop             : mapped axes stop (기본 Triangle)
authority_toggle : authority request/release (기본 Options)
all_axes_stop    : all axes stop (기본 Create)
```

### Multi-axis mode

```yaml
Left stick X     : X velocity
Left stick Y     : Y velocity
Right stick Y    : Z velocity
Right stick X    : Rotation velocity
```

### Single-axis mode

```yaml
D-pad left/right : selected axis 변경
Left stick Y     : selected axis velocity
Homing button    : selected axis homing (기본 Cross)
```

Motion Server 축 번호와 gamepad logical stick 할당은 각각 client 설정으로 매핑한다.
`server.axes`에는 X/Y/Z/Rotation 네 role을 모두 적고, 사용하지 않는 role의 축 번호는 JSON `null`로 둔다.
한 개 이상 네 개 이하의 role을 활성화할 수 있으며 활성 축 번호는 중복할 수 없다. 루트 `axes`와 `invert`는
네 role의 입력·방향 설정을 계속 유지하되, 비활성 role은 명령과 motion limit 검증에서 제외한다.
모든 서버 축 Standstill 확인과 `all_axes_stop`은 기존대로 전체 서버 축을 대상으로 한다.

```yaml
server:
  axes:
    x: 0
    y: 1
    z: 2
    rotation: 3
axes:
  x: left_x
  y: left_y
  z: right_y
  rotation: right_x
```

Single-axis mode에서는 선택된 Axis만 Enable하고 Jog command를 보낸다. D-pad left/right 선택 변경은
Disarmed, stick 중립과 모든 Axis Standstill에서만 허용하며 이전 선택 Axis의 Stop/Standstill 없이 선택을
바꾸지 않는다. 선택 가능 축 범위는 설정과 server feedback의 axis count로 제한한다.

`actions.homing`으로 설정한 button의 상승 edge는 Single-axis mode의 Armed 상태에서만 선택 Axis에
`system/axis/home`을 보낸다. 기본값은 Cross이며 L3 같은 미사용 digital button으로 변경할 수 있다. 모든
stick 중립, 진행 중인 Jog 없음과 모든 Axis Standstill을 시작 조건으로 확인한다. Homing 중에는 Jog 입력을
전송하지 않고 `system/axis/status`의 `homing` 상태를 확인한다. 완료되면 Enable trigger을 계속 누른 상태의 Armed로
복귀한다. Enable trigger release, authority/Enabled 상실, Axis Fault 또는 server 이상은 기존 deadman 정책대로 즉시
선택 Axis Disable/Quick Stop과 Disarmed 전환을 수행한다. Multi-axis mode의 Homing 입력은 거부한다.

## Velocity 계산

stick 입력은 role별 axis velocity로 변환한다.

```text
velocity[role] = stick_value * server_max_velocity[axis] * speed_scale
```

deadzone 밖의 입력은 남은 구간 전체가 `0.0..1.0`이 되도록 다시 정규화하고 기본 response curve는
linear로 한다. role별 `invert` 설정을 제공하며 기준 최대 속도는 server의 axis별 `motion_limits`에서
읽는다. client는
50 ms 주기로 최신 입력값을 전송하고 이전 전송이 밀리면 중간 command를 쌓지 않고 최신 값 하나만
유지한다. speed scale 변경은 다음 update부터 즉시 적용한다.

권장 설정 항목:

```yaml
deadzone: 0.08
update_period_ms: 50
speed_scale_default: 0.1
speed_scales: [0.05, 0.1, 0.25, 0.5, 1.0]
```

linear axis velocity는 mm/s, rotary axis velocity는 deg/s 기준으로 Motion Server API에 전달한다.

Multi-axis mode에서 모든 stick이 deadzone 안의 중립 위치로 돌아오면 mapped axes에 Stop을 요청한다. 이 Stop은 축을
자동 disable하지 않으며 Enable trigger을 계속 누르고 있으면 Armed 상태를 유지한다. 이후 stick이 deadzone을
벗어나면 현재 speed scale과 server max velocity를 적용한 velocity command를 다시 보낼 수 있다.

Single-axis mode에서는 모든 선택 Axis에 Left Stick Y 원시 입력의 부호를 반전한 같은 Jog 방향을 사용한다.
스틱 위쪽은 `positive`, 아래쪽은 `negative`를 전송한다. Multi-axis role별 `invert`는 Single Jog에 다시
적용하지 않는다. 중립 복귀는 `jog_stop`이며, 다른 stick의 입력은 선택 Axis를 움직이지 않는다.

## Safety 계약

- Enable trigger 상승 edge에서는 최신 server feedback을 기준으로 모든 Motion Server Axis가 Standstill이고,
  모든 stick이 deadzone 안의 중립 위치인지 확인한다.
- 위 조건과 command authority가 충족된 경우에만 mapped axes enable을 요청한다. API Success와 이후
  feedback에서 mapped axes의 Operation Enabled를 확인한 뒤 Armed 상태로 진입한다.
- Enable trigger deadman이 눌린 Armed 상태에서만 velocity command를 보낸다.
- stick이 중립 위치로 돌아오면 mapped axes stop을 즉시 요청한다. Enable trigger을 계속 누르고 있으면 Axis는
  Enabled 상태와 Armed 상태를 유지한다.
- Enable trigger이 release되면 별도의 Stop 명령이나 Standstill 대기 없이 mapped axes disable을 즉시 요청하여
  Quick Stop으로 전환하고, client는 즉시 Disarmed 상태로 전환한다.
- 앱 시작, gamepad 재연결 또는 server 재연결 당시 Enable trigger이 이미 눌려 있으면 Armed로 진입하지 않는다.
  Enable trigger release와 stick 중립을 확인한 뒤 새로운 Enable trigger 상승 edge를 요구한다.
- Motion Server와 client 사이의 단절은 모든 TCP client에 공통 적용되는 왕복 Heartbeat 계약으로
  감지한다. server가 sequence `N`을 보내면 client는 이를 처리하여 `N + 1`을 응답하며, 양쪽은
  200 ms 안에 다음 유효 Heartbeat 진행이 없으면 연결 이상으로 판단한다. 상세 공통 계약은
  TD-037이 담당한다.
- gamepad client가 Heartbeat 단절을 감지하면 즉시 Disarmed 상태로 전환하고 mapped axes Disable을
  한 번 시도한 뒤 TCP 연결을 종료한다.
- Heartbeat는 모든 client 연결에서 확인하지만 server의 motion 안전 대응은 종료되는 연결이 command
  authority owner일 때만 수행한다. non-owner 연결 종료는 다른 client의 authority와 Axis 운전에 영향을
  주지 않는다. owner 연결은 Heartbeat timeout뿐 아니라 EOF, reset 또는 송수신 오류로 종료되어도 같은
  authority relinquishment 경로를 사용하여 모든 Axis motion target을 제거하고 전체 Axis를 즉시
  Disable/Quick Stop한 뒤 authority를 회수하고 TCP 연결을 종료한다.
- 재연결 후 command authority는 자동 요청하지 않고 사용자가 명시적으로 다시 요청한다.
- client가 `system/authority/release`로 제어권을 정상 반납하면 server는 모든 Axis에 Stop을 적용하고
  Enabled 상태를 유지한다. Feedback에서 모든 Axis Standstill을 확인한 뒤에만 authority를 해제한다.
  Standstill 대기 timeout은 2초이며 Stop 일부 실패나 timeout에서는 전체 Axis Disable/Quick Stop으로
  전환한다. owner 연결의 비정상 종료도 전체 Axis Disable/Quick Stop한다. 상세 계약은 TD-038이 담당한다.
- velocity command는 기존 Motion Server의 command authority, enabled state, fault state,
  motion limit, software limit와 timeout safety를 우회하지 않는다.
- `system/axis/stop`과 `system/axes/stop`은 대상 Axis의 Operation Enabled 여부와 관계없이 motion target을
  안전한 정지 상태로 초기화해야 한다. 혼합 Enabled/Disabled 대상 때문에 Stop 전체를 거부하지 않으며,
  Disabled Axis를 자동 enable하지 않고 그대로 유지한다. 상세 서버 계약은 TD-036이 담당한다.

## Client 상태와 명령 실패

- client 운전 상태는 `Disconnected`, `Disarmed`, `Arming`, `Armed`, `Homing`, `Releasing`을 구분한다.
- Enable 일부 실패 시 성공적으로 Enable된 mapped/selected Axis도 다시 Disable하고 Disarmed를 유지한다.
- Armed에서 `move_vel`/`jog_start`/`jog_stop` reject, authority 상실, Axis Fault, Operation Enabled 상실 또는 server
  runtime/bus 이상을 확인하면 즉시 Disarmed로 전환한다. 아직 authority를 가지고 있으면 대상 Axis에
  Disable을 best effort로 요청한다.
- stick 중립 Stop이 실패하면 대상 Axis Disable/Quick Stop으로 전환하고 Disarmed 상태가 된다.
- Disable 실패는 자동 재무장하지 않고 오류 상태와 실패 Axis를 화면에 표시한다.
- `actions.authority_toggle` 입력에서 authority가 없으면 request한다. authority owner이면 client를 즉시 Disarmed 및
  Releasing 상태로 전환하고 `system/authority/release`를 요청한다. release가 완료되거나 실패할 때까지
  Enable trigger과 motion 입력을 무시한다.
- server 재연결 후 authority request와 arming은 자동 수행하지 않는다.

## Windows 상태 화면

1차 client는 console-only가 아니라 작은 Windows GUI를 제공한다. 다음 상태를 상시 표시한다.

- Motion Server 연결과 Heartbeat 상태
- 초기 gamepad open/선택 상태
- command authority와 `Disarmed`/`Arming`/`Armed`/`Releasing` 상태
- Multi-axis/Single-axis mode와 selected Axis
- speed scale
- Axis별 Enabled, Standstill과 Fault
- 마지막 command 실패 및 mode/axis 전환 거부 이유
- 선택한 device profile의 전체 logical button, trigger, D-pad 입력과 물리 SDL 번호, 할당된 기능 또는 미할당 상태

DualSense lightbar, haptic feedback과 controller 자체 출력 기능은 1차 GUI 범위에 포함하지 않는다.

## 설정 검증

- 물리 SDL axis/button 번호는 운전용 `config.json`에 두지 않고 별도 `device_profiles.json`에서 profile별로
  관리한다. DualSense profile은 L1/R1을 button 9/10, L3/R3을 button 7/8, L2/R2를 axis 4/5로 구분한다.
  `config.json`은 device name/GUID와 profile 이름만 선택한다. 루트 `actions.enable.control`에서 profile이
  제공하는 이름 중 하나를 Enable/Deadman 기능에 할당한다. 아날로그 trigger는 threshold와
  `pressed_when: above|below`를 함께 설정한다. 기본값은 L2,
  `threshold: 0.5`, `pressed_when: above`이다.
- authority, fault reset, stop, all-Axis stop, mode toggle, Homing, speed up/down과 axis 이전/다음은
  모두 루트 `actions`에서 profile의 digital control 이름으로 할당한다. 기본값은 기존 DualSense 배치를
  유지하며 Enable을 포함한 모든 action control은 중복할 수 없다.
- axis role index가 중복되거나 server axis count 범위를 벗어나면 시작 단계에서 거부한다.
- server가 제공하는 axis kind와 X/Y/Z linear, Rotation rotary role이 일치하지 않으면 arm을 허용하지 않는다.
- server의 axis별 max velocity가 누락되거나 유효하지 않으면 arm을 허용하지 않는다.
- 여러 gamepad가 있으면 설정된 device name/GUID와 정확히 일치하는 하나만 선택한다. 일치하지 않거나
  여러 장치가 동시에 일치하면 arm을 허용하지 않는다.
- 일치하는 장치를 찾은 뒤 profile의 모든 axis, trigger, button, D-pad index가 장치가 보고한 입력 수의
  범위 안에 있는지 검사한다. 미할당 입력도 검사하며 범위를 벗어나면 장치를 열지 않고 오류를 표시한다.

## 추가 결정 필요

- Heartbeat 기본 주기 50 ms와 timeout 200 ms를 장비의 최대 속도·감속거리와 Windows/network 지연을
  기준으로 조정할 필요가 있는지 실장비 검증에서 확인한다.

## Motion Server API 사용

1차 구현은 신규 gamepad 전용 API를 만들지 않는다. Multi-axis mode는 기존 `system/axes/move_vel`,
Single-axis mode는 `system/axis/jog_start`, `system/axis/jog_stop`, `system/axis/home`과
`system/axis/status`를 사용한다.

예:

```json
{
  "cmd": "system/axes/move_vel",
  "axes": [0, 1, 2, 3],
  "velocities": [10.0, 0.0, -2.0, 5.0]
}
```

Linear/rotary axis 모두에서 `move_vel`을 사용할 수 있도록 하는 서버 측 계약 정리는
[TD-034](../td/TD-034-linear-rotary-velocity-command.md)가 담당한다.

## 제외 범위

- absolute move
- relative move
- sequence start
- parameter write
- safety bypass
- force/torque control
- trajectory generation
- Motion Server core의 gamepad/HID dependency
- 신규 Motion Server gamepad 전용 API
- DualSense와 gamepad client 사이의 USB/Bluetooth 단절 감지
- gamepad input-loop timeout과 입력 freshness 감시
- DualSense lightbar, haptic과 adaptive trigger 출력
- `pygame._sdl2.controller` experimental API와 직접 HID report 구현

## 완료 조건

- `control_panel/gamepad_control_panel`에 gamepad manual velocity client가 구현된다.
- DualSense 기준 Enable trigger 상승 edge의 정지·중립 확인, mapped axes enable, Armed 유지와 stick/button mapping이
  동작한다.
- `server.axes`의 axis role-to-index와 루트 `axes`의 role-to-logical-stick, single-axis 선택 범위, deadzone,
  update period와 speed scale이 설정 가능하다. 기준 max velocity는 server `motion_limits`를 사용한다.
- Multi-axis mapped axes에 대해 `system/axes/move_vel`, enable/disable/fault_reset/stop/authority request/release를 호출한다.
- Single-axis mode에서 선택 축 변경과 선택 축 `jog_start`/`jog_stop`이 동작하며 `move_vel`을 사용하지 않는다.
- Single-axis Armed·stick 중립·모든 Axis Standstill에서 설정된 Homing button으로 선택 축 Homing을
  시작하고 완료까지 Jog를 억제하며, Multi-axis mode에서는 Homing 입력을 거부한다.
- 설정된 mode toggle과 previous/next Axis action은 Disarmed, stick 중립과 모든 Axis Standstill에서만
  동작하며 Single-axis mode에서는 선택 Axis만 Enable한다.
- scaled deadzone, linear curve, role별 invert, command coalescing과 strict 설정 검증이 적용된다.
- Windows GUI가 연결, Heartbeat, authority, client 운전 상태, mode/axis, scale과 Axis 오류를 표시한다.
- `pygame-ce / pygame.joystick` adapter가 name/GUID와 mapping profile로 DualSense 입력을 읽고 Windows
  배포 artifact에 SDL runtime을 포함한다.
- 운전 중 명령 reject, authority/Enabled 상실, Axis Fault와 runtime/bus 이상에서 Disarmed 및 안전 동작이
  검증된다.
- stick 중립에서 mapped axes를 Stop하고 Enabled/Armed 상태를 유지한다.
- Enable trigger release에서 Stop/Standstill 대기 없이 mapped axes를 즉시 Disable하여 Quick Stop으로 전환하고
  Disarmed 상태로 전환한다.
- TD-037의 공통 Heartbeat를 사용하고, server/client Heartbeat timeout에서 즉시 Disarmed 및
  Quick Stop/Disable, velocity target 제거, authority 회수와 TCP session 종료가 검증된다.
- DualSense와 gamepad client 사이의 단절 및 input-loop timeout은 이 RF의 완료 조건에 포함하지 않는다.
- Linear/rotary velocity command 계약은 TD-034, Enable 상태와 무관한 Stop 계약은 TD-036 완료 상태를
  전제로 하며 공통 TCP Heartbeat 계약은 TD-037, authority 해제 안전 종료 계약은 TD-038 완료 상태를
  전제로 한다.

## 구현 현황

- `control_panel/gamepad_control_panel`에 strict JSON 설정, `pygame.joystick` background adapter, 안전 상태기계와
  Tkinter 상태 화면을 구현했다.
- Multi PV/Single Jog mode, GUID mapping, scaled deadzone, role별 invert, speed scale, Enable trigger arming/release,
  neutral Stop, authority와 안전 명령 동작을 자동 테스트로 검증했다.
- Python wheel과 pygame SDL runtime을 포함한 Windows PyInstaller artifact 빌드를 확인했다.
- Windows Python에 pygame-ce를 설치한 뒤 SDL에서 `DualSense Wireless Controller`와 GUID를 확인했고,
  실제 joystick을 열어 4개 stick axis, 공통 button과 button 기반 D-pad 중립 입력을 읽었다.
- 물리 버튼/축을 직접 조작한 전체 mapping 검증과 실장비 motion 검증은 남아 있다. 해당 검증 전까지
  RF 상태는 `in_progress`로 유지한다.
