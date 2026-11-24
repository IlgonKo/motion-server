# RF-020 DualSense Haptic and Lightbar Feedback

- 등록일: 2026-11-05
- 상태: `out_of_scope` (향후 개발은 DT Demo 상위 애플리케이션/프로젝트에서 진행)
- 범위 변경일: 2026-11-24
- 우선순위: Motion Server 내 해당 없음
- 선행 작업: RF-018
- 구현 위치: `control_panel/gamepad_control_panel`

## 현재 책임 경계 — 2026-11-24 확정

- RF-018의 방향 변경에 따라 DualSense/Gamepad는 DT Demo 상위 애플리케이션에 연결한다.
- 진동·라이트바·입력 장치 상태 표시와 외부 Warning/Alarm 연동 정책은 상위 애플리케이션의 책임이다.
- 상위 애플리케이션이 Motion Server의 기존 API로 명령을 보내고 응답/Feedback을 활용한다. Motion Server에 DualSense 출력 전용 API나 장치 제어 책임을 추가하지 않는다.
- 미결 정책과 USB/Bluetooth 인수 시험 등 후속 작업은 DT Demo 애플리케이션/프로젝트에서 추후 다룬다.
- 기존 구현 코드·설정·테스트·패키징과 관련 문서는 Motion Server 저장소에 그대로 유지한다. 이번에는 삭제·이동·기능 변경을 하지 않는다.
- 이 상태는 구현 완료나 코드 이관 완료가 아닌 향후 개발 범위의 변경이다.

아래 설계·미결 사항·완료 조건·구현 현황은 기존 구현의 참고 이력이다.
Motion Server에서 계속 진행할 작업으로 해석하지 않으며 DT Demo의 상세 범위는 해당 프로젝트에서 확정한다.

## 배경

Gamepad Control Panel로 축을 수동 운전할 때 DualSense의 진동과 라이트바로 실제 축 이동 상태를
사용자에게 전달한다. 이후 알람이 발생하면 이동 진동보다 강한 진동을 설정된 시간 동안 출력할 수 있어야 한다.

이 기능은 Gamepad 장치 출력에 관한 기능이다. Motion Server는 기존처럼 Motion 명령과 Feedback만
제공하며 DualSense, rumble, haptic 또는 lightbar 전용 API를 추가하지 않는다.

## 사용자 동작

### 이동 중 약한 진동

- 설정에서 활성화한 Axis 중 하나 이상이 Motion Server Feedback에서 Moving이면 약한 진동을 시작한다.
- 모든 활성 Axis가 Standstill이면 즉시 진동을 중지한다.
- Stick 입력이나 전송한 command가 아니라 서버 Feedback을 기준으로 하여 실제 운전 상태와 일치시킨다.
- 연결 종료, Gamepad 분리, 입력 adapter 종료와 앱 종료에서는 진동 중지를 best effort로 수행한다.
- Gamepad가 진동을 지원하지 않거나 출력 요청이 실패해도 Motion 명령, Stop, Disable과 Heartbeat 동작에는
  영향을 주지 않는다. 상태 화면에는 지원 여부 또는 마지막 출력 오류를 표시할 수 있다.

### 알람 강진동

- 알람 진동은 이동 중 약진동보다 우선한다.
- 알람 발생 시 설정된 세기와 시간 동안 강진동을 출력한다.
- 알람 시간이 끝났을 때 활성 Axis가 계속 Moving이면 약진동으로 돌아가고, 모두 Standstill이면 진동을 끈다.
- 알람 발생원과 Gamepad Control Panel 사이의 event 계약은 RF-020 구현 전에 이 문서에서 확정한다.
- 같은 알람의 중복 event 처리, 여러 알람의 우선순위와 재시작/연장 정책도 RF-020의 미결 사항으로
  관리한다.

```text
Alarm strong rumble
  > Motion weak rumble
  > Off
```

### DualSense 조명 제어 범위

- 터치패드 좌우의 RGB 라이트바는 RGB 각 채널 `0..255` 범위에서 임의 색상을 지정한다.
- 터치패드 아래 흰색 Player Indicator는 플레이어 번호 표시용이며 이 기능의 제어 대상이 아니다.
- 마이크 버튼의 주황색 LED도 이 기능의 제어 대상이 아니다.
- RGB `0 / 0 / 0`은 라이트바 끄기로 사용한다. Alpha 값은 사용하지 않는다.
- 라이트바는 상태를 알아보기 쉽게 하는 보조 표시일 뿐이며 안전 상태를 보증하는 표시 수단으로
  사용하지 않는다.

### 상태별 라이트바

| 우선순위 | 상태 | 색상 | RGB | 출력 패턴 |
|---:|---|---|---:|---|
| 1 | Fault/Alarm | 빨강 | `255 / 0 / 0` | 500 ms 주기 점멸, 알람 강진동 병행 |
| 2 | Warning | 노랑 | `255 / 180 / 0` | 1,000 ms 주기 점멸 |
| 3 | Homing | 보라 | `160 / 60 / 255` | 1,000 ms 주기 점멸 |
| 4 | 활성 Axis Moving | Festo Blue | `0 / 145 / 220` | 연속 점등, 이동 약진동 병행 |
| 5 | Armed·운전 가능 | 초록 | `0 / 200 / 40` | 연속 점등 |
| 6 | 제어권 보유·Disarmed | 청록 | `0 / 180 / 180` | 연속 점등 |
| 7 | 서버 연결됨·제어권 없음 | 파랑 | `0 / 80 / 255` | 연속 점등 |
| 8 | 출력 Off | 꺼짐 | `0 / 0 / 0` | 소등 |

- 설정에서 활성화한 Axis 중 하나 이상이 Motion Server Feedback에서 Moving이면 이동 상태로 판단한다.
  Stick 입력이나 전송한 command만으로 Moving을 추정하지 않는다.
- 이동 색상은 Festo corporate color `Caerul`을 사용한다. 기준값은 RGB `0 / 145 / 220`,
  HEX `#0091DC`이다.
  ([Festo Corporate Colors](https://promotion.festo.shop/media/wysiwyg/bestellprozess/Farbposter.pdf))
- 상태가 동시에 성립하면 표의 우선순위가 높은 하나만 표시한다. 예를 들어 이동 중 Fault가 발생하면
  Festo Blue 연속 점등을 즉시 중단하고 빨간색 점멸로 전환한다.
- 상위 상태가 해제되면 최신 Feedback과 Controller 상태를 다시 평가하여 그 시점에 해당하는 가장 높은
  상태로 즉시 복귀한다. 이전 상태를 단순히 복원하지 않는다.
- 밝기는 색상과 별도 설정으로 둔다. 출력 RGB는 기준 색상의 채널 비율을 동일하게 축소하여 색조가
  바뀌지 않도록 한다.
- 모든 활성 Axis가 Standstill이면 Moving 표시를 해제하고 Armed, 제어권 보유 또는 연결 상태에 맞는
  하위 우선순위 색상으로 복귀한다.
- Gamepad가 분리되면 조명을 출력할 수 없다. 서버 연결 종료나 앱 종료처럼 Gamepad 출력이 아직 가능한
  종료 경로에서는 라이트바 소등을 best effort로 수행한다.
- 라이트바 미지원 또는 출력 실패는 Motion 명령, Stop, Disable과 Heartbeat 동작에 영향을 주지 않는다.
- Axis Fault는 Motion Server Feedback, Homing은 Gamepad Controller 상태를 사용한다. Warning과
  외부 Alarm을 전달하는 event 계약은 RF-020 구현 전에 확정하며, 상태가 전달된 이후의 색상·점멸·우선순위는
  이 RF의 표를 따른다.

### 점멸 동작

- DualSense에 점멸 패턴을 한 번에 설정하는 방식이 아니라 Gamepad Control Panel이 타이머에 따라
  `상태 색상 → Off → 상태 색상`을 반복하여 점멸을 만든다.
- `blink_period_ms`는 한 번의 On+Off 전체 주기다. 각 구간은 기본적으로 주기의 절반을 사용한다.
- 점멸 중에도 상태 평가는 계속한다. 우선순위가 바뀌면 남은 타이머를 기다리지 않고 새 상태를 즉시
  적용한다.
- 정상/대기, 제어권 보유, Armed와 Moving은 점멸하지 않는다. Warning, Fault/Alarm 및
  Homing만 점멸한다.

## 기술 방향

- 현재 의존성인 `pygame-ce`의 stable `pygame.joystick.Joystick.rumble()`과 `stop_rumble()`을 사용한다.
- 라이트바는 `pygame.joystick.Joystick.set_led()`를 사용하며, 이 API가 포함된 `pygame-ce >= 2.5.6`을
  최소 버전으로 사용한다.
- `set_led()`에는 RGB를 전달하고 반환값으로 장치의 LED 출력 지원 여부를 확인한다. Player Indicator와
  마이크 LED를 제어하기 위한 장치 고유 report는 추가하지 않는다.
- 이 범위의 haptic은 DualSense 고급 파형 생성이 아니라 SDL이 제공하는 일반 low/high-frequency rumble이다.
- `Joystick` 객체는 입력 adapter thread가 소유한다. Controller 상태기는 원하는 출력 상태만 전달하고,
  실제 `rumble()`/`stop_rumble()` 호출은 같은 adapter thread에서 수행한다.
- 출력 상태 전환은 edge 기반으로 처리하여 50 ms 입력 주기마다 동일한 rumble 명령을 반복하지 않는다.
- 라이트바 점등·소등과 향후 점멸도 같은 output adapter thread에서 edge/주기 기반으로 처리한다.
- 고정 점등 상태에서는 상태나 밝기가 변경될 때만 `set_led()`를 호출한다. 점멸 상태에서만 정해진
  deadline에 따라 On/Off를 전환하며 매 입력 주기마다 중복 호출하지 않는다.
- `rumble()` 반환값으로 럼블 지원 여부를 확인한다. USB/Bluetooth별 지원 차이는 실제 장치에서 검증한다.
- Bluetooth에서 SDL PS5 extended report 설정이 필요한지는 실장비 검증 결과로 결정하며 기본 동작에
  무조건 적용하지 않는다.

## 설정 방향

세기 범위는 `0.0..1.0`, 시간은 millisecond 양의 정수로 검증한다. 기본값은 실장비 검증 후 확정한다.

```json
"haptics": {
  "enabled": true,
  "motion": {
    "low_frequency": 0.05,
    "high_frequency": 0.10
  },
  "alarm": {
    "low_frequency": 0.80,
    "high_frequency": 1.00,
    "duration_ms": 2000
  }
},
"lightbar": {
  "enabled": true,
  "brightness": 0.35,
  "states": {
    "connected_disarmed": { "color": "#0050FF", "blink_period_ms": 0 },
    "authority_owned": { "color": "#00B4B4", "blink_period_ms": 0 },
    "armed": { "color": "#00C828", "blink_period_ms": 0 },
    "moving": { "color": "#0091DC", "blink_period_ms": 0 },
    "homing": { "color": "#A03CFF", "blink_period_ms": 1000 },
    "warning": { "color": "#FFB400", "blink_period_ms": 1000 },
    "fault_alarm": { "color": "#FF0000", "blink_period_ms": 500 },
    "off": { "color": "#000000", "blink_period_ms": 0 }
  }
}
```

`brightness`는 `0.0..1.0`, 색상은 `#RRGGBB`, 점멸 주기는 `0` 또는 양의 millisecond 정수로 검증한다.
`blink_period_ms: 0`은 연속 점등을 의미한다. Moving 기본색은 Festo CI 기준색 `#0091DC`로 고정한다.

## 범위

- 활성 Axis Moving/Standstill Feedback에 따른 약진동 시작과 중지
- 연결, 제어권, Armed, Moving, Homing, Warning과 Fault/Alarm에 따른 상태별 라이트바
- 라이트바 상태 우선순위, 상위 상태 해제 후 최신 상태 재평가와 점멸 timer
- Gamepad output adapter와 haptic/lightbar priority state 구현
- 시퀀서 또는 알람 발생원에서 Gamepad Control Panel로 전달하는 local event 계약
- 진동 출력 지원 여부와 실패 상태 표시
- 라이트바 출력 지원 여부와 실패 상태 표시
- 약진동/강진동/Off 우선순위 상태 관리
- 세기와 알람 지속 시간 설정 및 검증
- 종료·분리 경로의 best-effort 진동 중지 및 라이트바 소등
- USB와 Bluetooth 연결의 실제 DualSense 럼블·RGB 라이트바 검증

## 범위 제외

- Motion Server haptic/gamepad API 추가
- DualSense adaptive trigger 제어
- 오디오 기반 또는 장치 고유 고급 햅틱 파형 생성
- 햅틱을 안전 인터락이나 장비 상태의 신뢰 가능한 표시 수단으로 사용하는 것
- 라이트바를 안전 인터락이나 장비 상태의 신뢰 가능한 표시 수단으로 사용하는 것
- Player Indicator와 마이크 버튼 LED 제어
- 알람 정의, 알람 판정과 시퀀서 내부 알람 관리

## 완료 조건

- 활성 Axis가 Moving으로 전환되면 설정된 약진동이 한 번 시작되고 Standstill에서 중지된다.
- 활성 Axis가 Moving으로 전환되면 라이트바가 Festo Blue `#0091DC` 색조로 연속 점등되고
  Standstill에서 현재 Armed/제어권/연결 상태의 색상으로 복귀한다.
- 연결, 제어권 보유, Armed, Homing, Warning과 Fault/Alarm에서 정의된 색상과 점멸 패턴이
  적용된다.
- 여러 상태가 동시에 성립하면 `Fault/Alarm > Warning > Homing > Moving > Armed >
  Authority owned > Connected/Disarmed > Off` 우선순위를 따른다.
- 점멸 상태가 해제되면 최신 상태에 맞는 출력으로 즉시 복귀하며 이전 점멸 deadline이 남지 않는다.
- 비활성 Axis 이동은 이동 약진동을 시작하지 않는다.
- 강진동이 약진동을 덮어쓰고 지정 시간이 끝난 뒤 최신 이동 상태에 맞는 출력으로 복귀한다.
- 연결 종료와 앱 종료에서 `stop_rumble()`과 라이트바 소등을 시도한다.
- 럼블·라이트바 미지원 또는 실패가 Motion 운전 상태기계와 안전 명령을 변경하지 않는다.
- 설정 범위, 출력 우선순위와 thread ownership을 자동 테스트한다.
- 밝기 적용 전 기준색이 RGB `0 / 145 / 220`이며 밝기 조절 후에도 채널 비율이 유지되는지 자동 테스트한다.
- 실제 DualSense의 Windows USB 연결에서 약진동 시작/정지, 강진동 시간, RGB 색상과 점멸 주기를 확인한다.
- Bluetooth의 럼블·라이트바 지원 여부와 필요한 SDL 설정을 검증 결과에 기록한다.

## 구현 전 미결 사항

다음 항목은 기술부채가 아니라 RF-020을 완료하기 전에 확정하거나 검증해야 하는 기능 설계 항목이다.

- 시퀀서 또는 알람 발생원과 Gamepad Control Panel 사이의 local event 전달 방식
- 같은 알람의 중복 event 처리와 여러 알람의 우선순위
- 알람 재발생 시 강진동 지속 시간의 재시작 또는 연장 정책
- Windows USB/Bluetooth별 럼블·라이트바 지원 여부와 필요한 SDL hint

## 구현 진행 상황

- `machine_state.py`에 Feedback/Controller 상태 기반 출력 상태 판정과 우선순위를 구현했다.
- `PygameJoystickAdapter`가 소유 thread에서 RGB 라이트바, 점멸 timer, 약진동, Fault 강진동과
  종료 시 출력 정리를 수행하도록 구현했다.
- 설정 블록이 없는 기존 파일에는 기본값을 적용하고, 명시된 색상·밝기·세기·시간·상태 목록은
  시작 시 엄격하게 검증한다.
- `SDL_JOYSTICK_HIDAPI_PS5_RUMBLE=1`을 pygame 초기화 전에 기본 적용하며 사용자가 명시한 환경값은
  덮어쓰지 않는다.
- 현재 연결된 Windows DualSense에서 SDL hint 미적용 시 LED/rumble이 모두 `False`, 적용 후 모두
  `True`를 반환함을 확인했다. 실제 adapter 경로에서도 Moving 상태의 라이트바와 약진동 지원을 확인했다.
- Axis Fault는 강진동과 Fault/Alarm 라이트바에 연결했다. 외부 Warning/Alarm 전달 계약은 아직 미구현이다.
- 자동시험은 상태 우선순위, 활성 Axis 필터, Controller 연동, LED 밝기·점멸, 진동 전환과 설정 오류를
  포함한다.
