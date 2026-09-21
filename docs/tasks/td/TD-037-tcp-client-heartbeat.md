# TD-037 모든 TCP Client 왕복 Heartbeat와 Authority Owner 연결 종료 감지

- 등록일: 2026-09-21
- 상태: `complete`
- 우선순위: 높음
- 선행 작업: TD-038
- 후속 작업: RF-018

## 배경

Motion Server는 TCP 연결의 peer가 Axis Control Panel, IO Control Panel, gamepad client, Python reference
client 또는 ROS adapter인지 구분하지 않는다. 따라서 연결 생존 감지를 특정 application에 종속시키지
않고 모든 TCP client가 따르는 transport 계약으로 정의해야 한다.

정상적인 socket close의 FIN/RST는 빠르게 감지할 수 있지만 cable 단선, 한 방향 packet 유실 또는
network blackhole은 즉시 close로 나타나지 않을 수 있다. feedback 수신만 client에서 감시하면
client-to-server 방향 단절과 client process 정지를 server가 판단할 수도 없다. command authority owner의
연결이 이런 상태가 되면 마지막 velocity target이 유지될 수 있으므로 server가 정해진 시간 안에
왕복 생존을 확인하고 안전 상태로 전환해야 한다.

현재 `motion_server/app/client_transport.py::close_client()`는 종료 client가 command authority owner이면
`command_authority_owner`만 `None`으로 변경한 뒤 socket을 닫는다. `service_client()`의 EOF,
ConnectionReset/OSError와 송신 실패는 이 경로로 들어오지만 velocity target 제거, Stop 또는 Disable은
수행하지 않는다. 따라서 현재 구현에서는 owner 연결이 동작 중 종료되어도 기존 motion target과
Operation Enabled 상태가 그대로 유지될 수 있다. 모든 motion mode의 안전 종료는 TD-038이 담당한다.

## 공개 계약

### Heartbeat sequence

- Motion Server는 연결된 모든 TCP client에 같은 Heartbeat 계약을 적용한다.
- sequence는 JSON integer로 표현하는 unsigned 32-bit 값 `0..4294967295`를 사용한다.
- 새 연결의 첫 challenge sequence는 `0`이며 server는 다음 connection control frame을 보낸다.

  ```json
  {"type": "system/heartbeat", "sequence": 0}
  ```

- client는 새 challenge `N`을 처리한 뒤 `(N + 1) mod 2^32`를 다음 control frame으로 보낸다.

  ```json
  {"type": "system/heartbeat/ack", "sequence": 1}
  ```

- sequence `4294967295`의 유효 ACK는 overflow 후 `0`이다. server가 이후 보내는 다음 challenge도 `0`이다.
- client별로 한 번에 하나의 challenge만 유효하다. server는 유효한 response를 받은 다음 Heartbeat
  주기에 다음 sequence를 challenge로 보낸다.
- server는 현재 outstanding challenge에서 기대하는 값과 정확히 일치하는 response만 인정한다.
  stale, duplicate, out-of-order 또는 잘못된 response는 Heartbeat deadline을 갱신하지 않는다.
- challenge와 ACK는 일반 application request/response가 아닌 connection control frame이다. ACK에는
  `cmd`와 `request_id`를 넣지 않으며 server는 별도의 Success response를 보내지 않는다. 다음 challenge가
  이전 ACK를 server가 수신했다는 암묵적 확인이다.
- Heartbeat ACK에는 command authority가 필요하지 않으며 command router보다 transport 계층에서 먼저
  처리한다.

### 주기와 timeout

- 기본 Heartbeat 주기는 50 ms다.
- server와 client의 기본 Heartbeat timeout은 200 ms다.
- 주기와 timeout은 양수 설정값이며 timeout은 Heartbeat 주기보다 커야 한다.
- deadline 계산에는 wall clock이 아니라 단조 시계를 사용한다.
- 새 TCP 연결은 이전 연결의 sequence와 deadline을 승계하지 않는다.
- client는 제한 시간 안에 새 challenge를 받지 못하면 server 연결 이상으로 판단한다.
- server는 제한 시간 안에 outstanding challenge의 유효 response를 받지 못하면 client 연결 이상으로
  판단한다.

### 연결 종료 처리

- Heartbeat timeout은 client 연결 종료 사유 중 하나로 취급한다. 정상 EOF, TCP reset, 송수신 오류와
  Heartbeat timeout은 모두 같은 connection close 경계로 모은다.
- 모든 client는 Heartbeat timeout에서 해당 TCP 연결과 pending request를 종료한다.
- 종료 직전 command authority owner가 아닌 client는 Axis target, Enabled 상태와 다른 client가 가진
  command authority에 영향을 주지 않는다.
- 종료 직전 command authority owner인 client는 연결 종료 원인과 관계없이 TD-038의 공통 authority
  relinquishment 안전 종료를 호출하여 모든 Axis motion을 정리하고 authority를 해제한 뒤 연결과 pending
  request를 종료한다.
- 연결 종료 처리 뒤 도착한 Heartbeat response와 command는 폐기한다. 새 연결에서 이전 session의 sequence,
  pending request 또는 authority를 복원하지 않는다.
- client-side timeout은 pending request를 실패 처리하고 TCP 연결을 종료한다. client가 authority owner일
  가능성이 있으면 연결 종료 전에 Disable을 한 번 시도할 수 있지만, 이 best-effort 요청의 성공을 안전
  정지의 전제로 삼지 않는다.
- 재연결 후 application이 authority를 명시적으로 다시 요청해야 한다.

## 공식 Client 전환 범위

Heartbeat는 server protocol의 필수 계약이므로 server와 다음 공식 client를 같은 변경 단위에서 전환한다.

- `motion_server_client` 공통 client
- Axis Control Panel
- IO Control Panel
- Python reference client와 examples
- ROS/MoveIt adapter 및 repository에서 제공하는 기타 TCP adapter
- Node-RED 공통 connection client
- RF-018 Gamepad Control Panel

Axis/IO Control Panel은 각각 Heartbeat를 별도로 구현하지 않고 가능한 경우 공통 client transport의 구현을
사용한다. Panel은 Heartbeat timeout을 disconnected 상태로 표시하고, pending request를 실패 처리하며,
재연결 후 authority를 자동으로 다시 획득하지 않는다.

기존 Heartbeat 미지원 client를 위한 compatibility mode는 제공하지 않는다. server contract와 공식
client를 일괄 전환한다.

## 제외 범위

- DualSense 등 외부 입력 장치와 client application 사이의 USB/Bluetooth 단절 감지
- application input-loop freshness 또는 UI thread 생존 감시
- EtherCAT bus/device 연결 생존 감시
- authority 정상 해제의 전체 Axis Stop과 owner 연결 종료의 전체 Axis Disable 상세 구현(TD-038)
- emergency stop 또는 safety-rated communication

## 완료 조건

- 여러 client의 sequence와 deadline이 연결별로 독립 관리된다.
- 정상 client는 challenge `N`마다 `N + 1`을 응답하여 연결을 유지한다.
- uint32 최대값에서 ACK와 다음 challenge가 `0`으로 순환하며 JavaScript client에서도 정수 손실이 없다.
- Heartbeat ACK에 일반 command response를 생성하지 않고 request correlation/pending queue에 넣지 않는다.
- stale, duplicate, out-of-order와 잘못된 response가 deadline을 갱신하지 않는다.
- server-to-client, client-to-server와 양방향 blackhole이 200 ms 기본 timeout으로 감지된다.
- non-owner 연결 종료는 원인과 관계없이 다른 client, Axis와 authority에 영향을 주지 않고 해당 연결만
  정리한다.
- authority owner 연결 종료는 Heartbeat timeout, EOF, reset과 송수신 오류 모두에서 TD-038의 전체 Axis
  motion 안전 종료를 호출한 뒤 authority와 연결을 반드시 정리한다.
- timeout 후 늦은 frame과 이전 session command가 실행되지 않는다.
- 공통 client, Axis/IO Control Panel과 나머지 공식 adapter가 Heartbeat에 응답하고 단절 상태를 일관되게
  처리한다.
- API schema, 사용자 문서, 설정, 자동 테스트와 배포 artifact가 새 필수 계약과 일치한다.

## 구현 결과

- server의 normal, degraded, bus-disconnected loop가 연결별 challenge, outstanding ACK와 단조 deadline을
  관리한다. ACK는 router 전에 소비하고 일반 응답을 만들지 않는다.
- Python reference client, Axis/IO Panel, ROS bridge, Node-RED connection client와 RF-018 gamepad client를
  필수 Heartbeat 계약으로 전환했다.
- 기본 50 ms/200 ms 설정, strict `uint32` ACK, overflow, stale ACK 무시, client-side timeout과 pending
  request 실패를 구현했다. Node-RED 자동 시험은 저장소 지침에 따라 실행하지 않았다.
