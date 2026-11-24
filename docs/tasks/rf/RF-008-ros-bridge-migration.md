# RF-008 ROS Bridge 후속 이관 및 테스트

## 상태 및 재개 조건

상태: `out_of_scope` (2026-11-24, DEC-053).

ROS/ROS2, ROS Bridge/Control Panel 및 MoveIt의 개발·이관·설정·배포·검증은 프로젝트 범위에서 제외한다.
API 안정화에 따른 자동 재개 계획은 폐기한다. 아래 목표와 구현·검증 계획은 과거 이력으로만 보존한다.
2026-11-24 후속 요청에 따라 기존 ROS/MoveIt 소스, Docker 정의와 실행 스크립트도 삭제했다.

## 목표

ROS Bridge, ROS Control Panel과 Docker 구성을 최신 Motion Server 계약에 맞춘다.

## 구현 범위

- TD-005-S09에서 공통 legacy/new response decoder의 수신 경계 적용은 완료했다.
- command namespace, authority, feedback와 axis/I/O status 변경을 반영한다.
- Motion Server mm/deg와 ROS SI unit 사이의 변환 경계를 확정한다.
- ROS Docker, Control Panel과 Bridge connection 설정을 공통 configuration model에 맞춘다.
- 축 구성과 bus 정보는 Motion Server 공통 configuration model을 사용하고, ROS에만
  필요한 이름·topic·action 설정은 별도 ROS 설정 파일로 분리한다.
- TD-006에서 남긴 임시 기본 축 이름을 제거하고 실제 서버 구성과 ROS 축 구성을
  일치시키는 시작 절차를 확정한다.
- trajectory action/topic behavior와 error propagation을 최신 API에 맞춘다.

## 검증 계획

- mock/virtual backend에서 command, feedback, authority와 reconnect를 자동 검증한다.
- 실장치에서 joint state 및 trajectory smoke test를 수행한다.
- clean Docker 환경에서 build/start/test 절차를 재현한다.

## 완료 증거

완료 시 API mapping 표, unit conversion test와 Docker/실장치 시험 결과를 기록한다.
