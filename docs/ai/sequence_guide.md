# Python 시퀀스 작성 계약

이 가이드는 **클라이언트의 단계 전환 규칙**이다. API Schema나 Motion Server의 역할을 확장하지 않는다. 요청/응답 구조는 [Schema](../../motion_server/api/schema), 통신 기능은 [공식 client](../../reference_clients/python/README.md)를 따른다.

## 통신과 실패

`MotionServerClient(host, port)`의 `start()`, `wait_connected(timeout=...)`, `request(message, timeout=...)`, `get_feedback(timeout=...)`, `stop()`을 사용한다. `get_feedback`은 timeout 시 `queue.Empty`를 발생시킨다. `request`가 반환한 `result == "fail"`은 서버 Fail이며 Python 예외가 아니다. `failure.code/message/details`를 기록하고 다음 단계를 실행하지 않는다. 연결 상실/요청 timeout 등의 client 예외도 별도로 처리한다.

고유 `request_id`는 요청과 응답을 연결한다. 일반 Feedback은 명령 ID를 가지지 않는다. **API Success는 동작 완료가 아니다.** Success 이후 도착했다는 사실만으로 Feedback이 그 명령을 반영했다고 증명할 수 없다. 응답 timeout은 명령 미실행의 증거도 아니다. 자동 재전송하지 않는다.

Feedback queue는 유한하며 가득 차면 오래된 항목이 버려지지만, 읽은 항목이 언제나 최신인 것은 아니다. 하나의 수신 소비자가 latest snapshot과 로컬 수신 순서를 관리하고 GUI/시퀀스에 공유한다. 명령 전의 누적 자료로 완료 판정하지 않는다. Success 이후 새 자료에서 목표값·상태를 함께 확인한다. 동일 위치 재명령 등 이미 조건이 참인 경우 상태 조건 충족으로 전환할 수 있지만 새 물리 동작 발생을 증명했다고 기록하지 않는다. 엄격한 명령별 추적이 필요한 요구는 현재 API 한계로 보고하며 서버 operation ID를 임의 추가하지 않는다.

`process_data_valid == false`인 자료, 연결이 끊긴 뒤 남은 자료, 필요한 축/채널이 빠진 자료는 완료/입력 대기 조건을 만족시키지 못한다. 수신이 끊겨도 마지막 정상 snapshot으로 계속 진행하지 않도록 로컬 monotonic 수신 시각과 Feedback timeout을 사용한다. GUI와 시퀀스가 같은 queue를 경쟁적으로 읽지 않는다.

## 명령별 단계 전환

아래는 CMMT 기반 시퀀스 기본 조건이다. 다른 장치에는 statusword 의미를 확인해야 한다. CMMT는 Moving bit 8, Target reached bit 10, Referenced bit 15, Fault bit 3을 사용한다. Standstill은 Moving bit 해제다. Operation enabled는 `(statusword & 0x006F) == 0x0027`로 확인한다. [기존 Panel 해석](../../control_panel/axis_control_panel/statusword.py)을 참조한다.

| 명령 | Success 다음의 단계 전환 조건 |
| --- | --- |
| move_abs | 실제 위치가 목표 위치 허용치 이내 AND Target reached AND Standstill |
| move_rel | 실제 위치가 최종 절대 목표 허용치 이내 AND Target reached AND Standstill |
| move_vel, 속도 ≠ 0 | 실제 속도가 요청 속도 허용치 이내 AND Target reached AND Moving |
| move_vel, 속도 = 0 | Standstill |
| jog_start | API Success만 확인 |
| stop / jog_stop | Standstill |
| enable | Operation enabled |
| disable | Operation enabled 해제 |
| home | 공개 Homing 상태의 완료(`complete`)와 해당 축 Referenced 확인 |
| fault_reset | API Success만 확인. 원인 미해제 시 Fault가 남을 수 있음 |
| I/O 출력 쓰기 | API Success만 확인. 외부 동작 확인은 사용자가 지정한 DI/AI 대기로 별도 수행 |

다축은 **모든 지정 축**이 각자의 조건을 만족해야 한다. Homing 진행/결과는 기존 상태 조회 응답의 homing 정보와 Feedback을 사용한다. fault_reset 이후 별도 복구 대기는 사용자가 요청했을 때만 추가한다.

가이드 기본값: 위치 허용치 **0.5 API 위치 단위**, 속도 허용치 **1.0 API 속도 단위**. 사용자 지정이 우선하며 mm/deg 등 확인된 축 단위별로 적용한다. 이는 서버 안전 제한이나 API 기본값이 아니다.

move_rel의 서버 목표는 명령 처리 시점 실제 위치 + 이동량이다. 클라이언트가 요청 전 읽은 위치는 이 시점과 다를 수 있다. 기존 응답 또는 명령 이후 Feedback의 `target_positions`에서 해당 최종 목표를 확인해 대기하고, 이전 목표 snapshot을 새 목표로 간주하지 않는다. 단순히 로컬 사전 위치에 더해서 정확한 서버 목표라고 단정하지 않는다. 목표 귀속이 불명확한 연속 동작은 사용자 요구를 확인한다.

속도 도달은 계속 움직이는 동작의 단계 전환 조건이지 자동 Stop이 아니다. 다음 단계로 넘어가도 별도 stop까지 움직일 수 있다. dwell/대기는 사용자가 지정한 경우에만 둔다.

## 파라미터와 API 예시

가감속은 전체 시퀀스 공통 설정으로 시작 시 한 번 적용한다. 단계별 가감속 변경은 만들지 않는다. 이동 속도는 abs/rel 명령의 `profile_velocity` 또는 `profile_velocities`로 보낸다. `velocities`는 move_vel용이며 move_abs에 사용하지 않는다.

다음은 타입/필드 설명용 요청이며 실장비 실행 지시가 아니다.

```json
{"cmd":"system/axis/profile","axis":0,"profile_acceleration":100.0,"profile_deceleration":100.0}
```

```json
{"cmd":"system/axes/move_abs","axes":[0,1],"positions":[10.0,20.0],"profile_velocities":[5.0,5.0]}
```

```json
{"cmd":"system/axes/stop","axes":[0,1]}
```

```json
{"cmd":"system/io/output_write","io":"io0","slot":1,"kind":"digital","channel":0,"value":true}
```

## Timeout, Stop, cleanup

요청 timeout은 client 설정, 단계/입력 조건 timeout과 Feedback timeout은 **시퀀스 설정**에 둔다. Schema에 추가하지 않는다. 시간은 monotonic 기준으로 재고 무한 대기하지 않는다. blocking 대기는 짧은 bounded wait로 나누어 취소를 확인한다. 이미 전송한 요청은 로컬 취소로 회수되지 않으며 bounded 요청 종료 후 cleanup을 시도한다.

- 상태는 idle → running → completed, 또는 stopping → cancelled / failed로 표현한다. cleanup 실패를 완료로 덮어쓰지 않는다.
- Stop/Ctrl+C, API Fail, timeout, 실행 중 Fault, 연결·제어권 상실은 다음 단계 진입을 막는다. 마지막 상태와 실패한 명령/단계를 기록한다.
- 연결과 제어권이 유지되면 사용한 축들에 기존 Stop을 보내고 bounded Standstill 대기를 한다. I/O는 사용자 지정 cleanup만 적용한다. 지정 없는 출력은 유지한다. 자동 Disable하지 않는다.
- 연결/제어권이 없으면 전송 못 한 cleanup을 명시한다. 정지를 확인하지 못했는데 정지 완료라고 표시하지 않는다. 재접속 후 명령 재전송/시퀀스 자동 재개/제어권 자동 재획득을 하지 않는다.
- Python client 자체 재접속 기능과 시퀀스 재개는 다르다. 사용자가 명시적으로 제어권을 다시 요청하고 새 Run을 해야 한다.

CLI는 연결 → 제어권 요청 → 1회 Run → cleanup → 소유 중인 제어권 해제 → 종료다. GUI는 명시적인 연결/제어권 버튼을 제공하며 Run 종료 후 제어권을 유지한다. GUI 종료 시 실행 중이면 먼저 취소/cleanup하고 해제·닫는다.

Homing/Enable/Fault/limit의 Run 사전 인터락을 복제하지 않는다. API Fail로 중단한다. 실행 중 Fault 감시와 통신 상실 중단은 실행 중 실패 처리이며 별도 서버 안전 규칙을 만드는 것이 아니다.

## Teaching 선택 기능

Teaching은 **시퀀스 생성 프롬프트의 선택 항목**이다. 별도 필수 프로그램이 아니다. 선택 시 생성 프로그램 폴더의 `teaching_points.json`에 이름별 역할 위치와 단위를 저장한다. axis index 역할 매핑은 시퀀스 설정, 속도는 단계 설정, 가감속은 시퀀스 공통 설정에 둔다.

모든 역할 위치를 동일한 유효 Feedback snapshot에서 편집 버퍼로 캡처한다. 추가/편집/삭제와 명시적 저장을 제공한다. Run은 포인트/설정 snapshot을 고정하고 실행 중 편집·수동 이동을 금지한다. 필요한 포인트 누락/단위 불일치는 프로그램 입력 오류로 처리한다.

수동 +/- hold Jog는 Slow/Fast 선택, release/포인터 이탈/포커스 상실 시 jog_stop을 제공한다. 포인트 이동에는 Teaching 전용 이동 속도·가감속 설정을 사용하되 다음 Run은 시퀀스 공통 가감속을 다시 적용한다. 선택 축 Enable/Disable/Fault Reset/Homing은 명시적 사용자 조작으로 제공한다. Homing 상태는 표시하되 새 Run 인터락을 추가하지 않는다.

## 검증

생성 프로그램은 가짜 client/Mock 기반 정상·Fail·timeout·중단·통신/제어권 상실 시험을 제공한다. 알려진 invalid Feedback과 과거 queue 항목이 완료를 만족시키지 않는지, 다축 중 하나만 완료했을 때 대기하는지 확인한다. 테스트 편의를 위해 실제 서버 계약을 약화하지 않는다. 독립 AI 생성 평가/패키지 실행 검증은 [RF-019 S04](../tasks/rf/RF-019-ai-motion-io-sequence-platform.md) 범위다.
