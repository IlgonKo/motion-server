# Gamepad Control Panel Design Documents

이 폴더는 `control_panel/gamepad_control_panel`에만 적용되는 RF, TD와 검증 기록을 관리한다.
Gamepad 기능의 요구사항과 구현 부채는 이 폴더에 등록하고, Motion Server core나 모든 TCP client에
공통 적용되는 항목은 기존 `docs/tasks/rf` 또는 `docs/tasks/td`에 유지한다.

문서 분류 원칙:

- 아직 구현되지 않은 신규 기능과 그 기능을 구현하기 위한 설계·검증 항목은 `RF`에서 관리한다.
- 기존 구현의 버그, 임시 우회, 구조적 기술부채처럼 해결 또는 제거해야 하는 문제만 `TD`로 등록한다.
- RF 구현 세부 작업이라는 이유만으로 후속 TD를 만들지 않는다. 독립적으로 범위를 나눌 신규 기능이면
  별도 RF로 등록한다.

## RF

- [RF-018 Gamepad Manual Multi-Axis Velocity Control](RF-018-gamepad-manual-velocity-control.md)
- [RF-020 DualSense Haptic and Lightbar Feedback](RF-020-dualsense-haptic-feedback.md)

## 관련 공통 TD

다음 문서는 Gamepad 전용 문서가 아니므로 중앙 위치에서 관리한다.

- [TD-034 Linear/Rotary Velocity Command](../../../docs/tasks/td/TD-034-linear-rotary-velocity-command.md)
- [TD-036 Stop Command Enabled-state Independence](../../../docs/tasks/td/TD-036-stop-command-enabled-state-independence.md)
- [TD-037 TCP Client Heartbeat](../../../docs/tasks/td/TD-037-tcp-client-heartbeat.md)
- [TD-038 Authority Release Motion Shutdown](../../../docs/tasks/td/TD-038-authority-release-motion-shutdown.md)
