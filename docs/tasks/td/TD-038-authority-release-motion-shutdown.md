# TD-038 Command Authority 정상/비정상 해제의 전체 Axis Motion 종료

- 등록일: 2026-09-21
- 상태: `complete`
- 우선순위: 높음
- 후속 작업: TD-037, RF-018

## 배경

현재 explicit `system/authority/release`와 owner connection close는
`command_authority_owner`만 `None`으로 바꾼다. Axis Stop, Disable 또는 motion target 정리를 수행하지
않으므로 owner가 사라진 뒤에도 이전 PV target이나 다른 mode의 진행 중 motion이 유지될 수 있다. 새로운
client는 이 상태에서 authority를 획득할 수 있다.

정상적으로 authority를 반납하는 경우와 통신이 사라진 경우에는 필요한 정지 방식이 다르다. 정상적인
explicit release는 controlled Stop을 적용하고 Axis의 Enabled 상태를 유지한다. owner 연결이 예기치 않게
종료된 경우에는 후속 제어를 기대할 수 없으므로 전체 Axis를 즉시 Disable하여 Quick Stop해야 한다.

## 공개 계약

### 명시적 정상 해제

- owner가 `system/authority/release`를 호출하면 authority를 해제하기 전에 모든 구성 Axis에 mode별 Stop을
  적용한다.
- PV target velocity와 서버 내부 velocity command를 0으로 만들고 PP/CSP target을 현재 actual position
  기준 hold 상태로 동기화한다. active trajectory, Jog와 Homing도 종료한다.
- Stop은 Axis를 자동 Disable하지 않는다. Enabled Axis는 Enabled 상태를 유지하고 Disabled Axis는 Disabled
  상태를 유지한다.
- Enabled/Disabled 혼합 상태 때문에 전체 Stop을 거부하지 않고 모든 Axis에 target 정리를 시도한다.
- Stop을 적용한 뒤 authority를 `releasing` 상태로 유지하고 새 motion command를 거부한다.
- server cyclic/feedback 처리를 계속하면서 Feedback과 동일한 Standstill 판정으로 모든 구성 Axis의
  Standstill을 확인한다.
- 모든 Axis가 Standstill인 것을 확인한 뒤에만 command authority를 해제하고 release를 완료한다.
- Standstill 대기 timeout은 Stop 적용을 시작한 단조 시각부터 2초다.
- 일부 Axis의 Stop 적용이 실패하거나 2초 안에 모든 Axis Standstill을 확인하지 못하면 controlled Stop
  release를 중단하고 모든 구성 Axis의 target을 다시 정리한 뒤 Disable/Quick Stop을 적용한다.
- fallback Disable/Quick Stop이 모든 Axis에 적용되면 authority를 해제한다. release response는 정상
  controlled Stop이 아니었음과 `stop_failed` 또는 `standstill_timeout` 원인, fallback 결과를 보고하고
  Diagnostic에도 같은 내용을 남긴다.
- fallback Disable/Quick Stop도 일부 실패하면 authority를 유지하고 Failure/PartialFailure와 Diagnostic에
  실패 Axis와 단계를 기록한다. 새 client는 authority를 획득할 수 없다.
- Standstill 대기는 server cycle을 막는 동기 loop나 sleep으로 구현하지 않는다. pending release 상태를
  server loop에서 진행시키고 완료 response도 request correlation을 유지하여 비동기로 전송한다.
- Standstill 대기 중 owner 연결이 종료되면 pending 정상 release를 취소하고 아래 비정상 종료의 전체 Axis
  Disable/Quick Stop 경로를 수행한다.

### Owner 연결 비정상 종료

- Heartbeat timeout, EOF, TCP reset, 송수신 오류 또는 server-side close로 owner 연결이 종료되면 모든
  구성 Axis의 위 motion target을 정리한 뒤 controlword `0x0007` Disable을 적용하여 Quick Stop한다.
- 이미 Disabled인 Axis는 Disabled 상태를 유지하고 일부 Axis 상태나 실패 때문에 나머지 Axis 처리를
  건너뛰지 않는다.
- client가 더 이상 복구 조치를 수행할 수 없으므로 target 정리나 Disable 일부가 실패해도 command
  authority와 connection을 반드시 정리하고 실패 Axis와 단계를 Diagnostic에 남긴다.

### 공통 조건

- 안전 종료를 시작할 때의 owner identity를 고정하고 처리 중 다른 client에 authority를 부여하지 않는다.
- authority가 `releasing`인 동안 owner를 포함한 모든 client의 새 motion command를 거부한다. status와
  feedback, Heartbeat 및 안전 종료 진행에 필요한 내부 처리는 계속 허용한다.
- command authority owner가 아닌 client의 연결 종료는 Axis motion에 영향을 주지 않는다.
- authority가 없거나 다른 client가 owner인 상태의 `system/authority/release`는 기존 authority rejection을
  유지하며 Axis motion에 영향을 주지 않는다.

## 구현 경계

- 모든 motion mode의 target 정리를 공통 내부 helper로 제공한다.
- `handlers/authority/registry.py::release_authority()`는 공통 target 정리 후 전체 Axis Stop 경로를 사용한다.
- explicit release handler는 socket 처리나 EtherCAT cyclic exchange를 block하지 않고 pending release를
  등록한다. server loop가 feedback 상태를 평가하여 response와 authority 해제를 완료한다.
- `app/client_transport.py::close_client()`의 owner branch는 공통 target 정리 후 전체 Axis
  Disable/Quick Stop 경로를 사용한다.
- `close_client()`는 owner 여부를 authority 해제 전에 판정하고, 안전 종료가 실패해도 socket과 authority
  정리를 완료한다.
- TD-037의 Heartbeat timeout은 별도 motion 로직을 구현하지 않고 owner connection close를 통해 비정상
  종료 경로를 사용한다.

## 제외 범위

- non-owner client 종료에 따른 Axis 상태 변경
- I/O output reset
- EtherCAT bus/device disconnect 복구
- emergency stop 또는 safety-rated stop

## 완료 조건

- explicit release가 모든 Axis motion target을 정리하고 mode별 Stop을 적용한 뒤 Enabled 상태를 유지한다.
- release 중에는 authority와 owner identity를 유지하고 새 motion command를 거부하며, 모든 Axis Standstill
  Feedback을 확인한 뒤에만 authority 해제와 correlated response를 완료한다.
- Standstill을 2초 안에 확인하지 못하거나 Stop 일부가 실패하면 전체 Axis Disable/Quick Stop fallback을
  수행한다.
- owner connection close가 모든 Axis motion target을 정리하고 전체 Axis를 Disable/Quick Stop한다.
- PV/PP/CSP, trajectory, Jog와 Homing이 active인 각 경우에 pending target이 남지 않는다.
- Enabled, Disabled와 혼합 Axis 구성에서 모든 Axis 처리를 시도한다.
- fallback 성공 시 authority를 해제하고 원인과 fallback을 response/Diagnostic에 보고한다. fallback 일부
  실패 시 authority를 유지하고 새 authority 획득을 차단한다.
- owner connection close 일부 실패는 나머지 Axis 처리를 계속하고 authority와 connection을 정리한다.
- non-owner disconnect와 authority rejection이 motion state를 변경하지 않는다.
- motion 종료 처리가 끝나기 전에 다른 client가 authority를 획득할 수 없다.
- API 문서와 자동 테스트가 공개 계약과 일치한다.

## 구현 결과

- explicit release는 correlated response를 보류하고 server cycle에서 전체 Axis Moving bit 해제를 확인한
  뒤 authority를 해제한다.
- 2초 timeout 또는 Stop 실패는 전체 Axis target 정리와 `0x0007` Disable/Quick Stop으로 전환하며,
  response와 Diagnostic에 fallback 원인을 남긴다.
- fallback 일부 실패는 owner와 failed release 상태를 유지하고, owner disconnect는 실패 여부와 관계없이
  전체 Axis 처리를 시도한 뒤 authority와 socket을 정리한다.
