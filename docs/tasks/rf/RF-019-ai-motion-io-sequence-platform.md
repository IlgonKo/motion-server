# RF-019 AI 기반 Motion/I/O 시퀀스 생성 플랫폼

- 등록일: 2026-09-09
- 상태: `in_progress`
- 우선순위: 높음
- 1차 생성 결과물: Python 시퀀스 프로그램

## 사용자 가치

사용자는 Motion Server API나 통신 코드를 직접 설계하지 않고, 제공된 예제 프롬프트를 자신의
장비와 목적에 맞게 수정하여 원하는 Motion/I/O 시퀀스를 자연어로 정의한다. AI는 Motion Server의
기능, 제약과 현재 장비 구성을 이해하고 기존 Python client로 Motion Server API block을 직접
조합하여 검토 및 시험 가능한 애플리케이션을 생성한다.

Motion Server는 단순히 user-friendly한 제어 화면을 제공하는 것을 넘어, AI가 장치 차이와 API
세부사항을 추측하지 않고 일관된 애플리케이션을 만들 수 있는 AI-friendly motion platform을
지향한다.

## 목표 사용자 흐름

하드웨어 설치·배선·commissioning, 설치된 장치에 맞는 config.txt/.env 설정과 Motion Server 정상 구동은
사용자 책임이다. Agent는 정상 구동된 서버를 이용해 사용자 시퀀스 프로그램을 생성·시험하는 역할이다.
설정 파일은 구성 파악을 위해 읽기만 하며 서버·장치 설정을 임의로 변경하지 않는다. 연결/설정 문제는
사용자에게 보고한다. 생성 프로그램의 연결·제어권·이동/I/O·Teaching·GUI는 합의된 범위에 포함된다.
S04에서는 평가자가 정상 구동된 Mock와 설정을 준비한다. Agent의 서버 설치/설정 능력을 평가하지 않는다.

```text
예제 프롬프트 선택 및 수정
→ 사용자가 Motion/I/O 요구사항을 자연어로 정의
→ AI가 Motion Server 지식과 현재 시스템 구성 확인
→ Python 시퀀스 생성
→ 정적 검증 및 Mock 시험
→ 사용자 검토
→ 실장비 실행
```

실장비에 대한 자동 배포·실행은 초기 범위에 포함하지 않는다. AI가 생성한 결과를 사용자가 검토하고
명시적으로 실행하는 경계를 유지한다.

## 사용자 예제 프롬프트 계약

예제 프롬프트는 단순 질문 예제가 아니라 사용자가 필요한 부분만 수정할 수 있는 요구사항 양식으로
제공한다. 최소한 다음 항목을 포함한다.

- 애플리케이션 목적
- 사용할 Axis와 I/O 및 각 장치의 역할
- 초기 조건과 초기 출력 상태
- 순차·동시 동작 단계
- 각 단계의 위치, 속도와 단위
- 다음 단계로 넘어가는 완료 조건
- 외부 입력 대기 조건과 timeout
- 사용자 Stop, 통신 단절과 Fault 발생 시 처리
- 전체 시퀀스 완료 조건과 종료 상태

사용자는 raw TCP request나 내부 API schema를 프롬프트에 직접 작성할 필요가 없다. Axis/I/O 번호와
역할을 알고 있으면 명시하고, 불명확하거나 현재 시스템과 맞지 않는 항목은 AI가 구현 전에 확인한다.

## AI에 제공할 Motion Server 지식

### 정적 플랫폼 지식

Motion Server 버전에 따라 고정되는 내용을 AI가 읽기 쉬우면서도 모호하지 않은 형태로 제공한다.

- Axis, I/O, Device, Bus, command authority와 Diagnostic 개념
- 단일축/다축 명령과 Linear/Rotary 단위 정책
- Feedback, 단발 status와 request/response의 차이
- API별 request/response 구조, 필수 인수와 데이터 타입
- 명령별 실행 전제조건과 실제 동작 완료 판정 방법
- Motion limit, Software limit와 velocity limit
- Failure code, Fault reset, restart와 bus reconnect 의미
- 시퀀스 생성 시 지켜야 할 안전 및 오류 처리 규칙
- 공식 Python client와 API block 직접 조합 방법 및 올바른/잘못된 패턴

설명 문서와 기계 판독 계약이 서로 다른 사실을 갖지 않도록 API 계약은 별도의 표준 JSON Schema
파일을 단일 원본으로 관리한다. Schema는 namespace별 파일로 분리하며, 서버의 API specification은
이 Schema를 읽어서 구성한다.

```text
axis/param_read      → axis.json
io/iol/param_read    → io.json
system/...           → system.json
bus/...              → bus.json
```

표준 JSON Schema 키워드로 request/response의 구조, 필수 필드와 데이터 타입을 정의한다. 표준 Schema가
표현하지 못하는 Motion Server 고유 의미는 `x-motion-server` 확장에 둔다. 여기에는 command authority,
실행 전제조건, 단위와 Feedback 필드의 의미 등 API 자체의 계약만 기록한다.
`sequence-transition`, `completion-condition`, 완료 허용치와 단계 timeout은 Schema에 넣지 않는다.

이 Schema는 Motion Server에 동작 완료 판단 기능을 추가하기 위한 설계가 아니다. Motion Server는 API로
받은 명령을 장치에 전달하고 장치 Feedback을 client에 전달하는 현재 책임을 유지한다. 실제 장치와
Virtual Device가 위치, 속도와 Statusword를 만들고, 생성된 Python/Node-RED 시퀀스가 시퀀스 작성 가이드를
바탕으로 Feedback을 해석하여 다음 단계 진행 여부와 전체 시퀀스 완료를 판단한다.

### Runtime 시스템 정보

AI가 존재하지 않는 축이나 I/O를 추측하지 않도록 현재 설정과 장치에서 다음 정보를 확인할 수 있어야
한다.

- Axis 개수, 이름, index와 역할
- Linear/Rotary 구분과 position/velocity 단위
- Motion limit와 Software position limit
- I/O station, AP module, DI/DO/AI/AO/IO-Link channel 구성
- 장치별 지원 기능과 현재 사용 가능 조건
- 현재 Server/Bus/Axis/I/O/Diagnostic 상태

AI는 기존 `config.txt`, 관련 `.env`와 여기서 참조하는 장치 정의·카탈로그로 의도한 구성을 파악한다.
별도의 시스템 구성 snapshot 파일이나 신규 조회 API는 만들지 않는다. X/Y/Z와 센서·출력의 실제 역할은
사용자 프롬프트에서 지정한다. 실행 중 실제 상태는 기존 API로 확인하고 표시한다.

Homing, Enable, Fault와 limit 등 서버가 검증하는 전제조건은 생성 프로그램에서 중복 검증하거나
Run 버튼의 인터락으로 구현하지 않는다. API Fail을 받으면 이유를 표시하고 후속 단계를 중단한다.
기존 절대 이동의 referenced 검증을 그대로 사용하며, 이 RF에서 다른 명령으로 검증 범위를 넓히지 않는다.
포인트 누락·파일 형식·단위·역할 매핑 등 생성 프로그램 자체 데이터의 검증은 수행한다.

## AI 시퀀스 생성 규칙

- 동시에 움직여야 하는 축은 가능한 경우 기존 다축 API를 사용한다.
- API 요청의 Success와 시퀀스의 다음 단계 전환 조건을 구분한다. Success는 요청이 정상 처리되었다는
  의미이며 물리 동작 완료를 뜻하지 않는다.
- 생성된 시퀀스는 작성 가이드의 장치 Feedback 조건을 평가한 뒤 다음 단계로 진행한다. 이 판단을
  Motion Server core에 추가하지 않는다.
- 입력 대기와 동작 완료 대기에는 유한한 timeout을 둔다.
- Fault, command authority 상실 또는 연결 단절 시 후속 단계로 진행하지 않는다.
- 연결이 복구되어도 이전 motion command를 자동 재전송하지 않는다.
- Stop 요청은 진행 중인 motion과 대기 조건을 함께 중단한다.
- 종료, 사용자 중단과 예외 발생 모두에서 `finally` 안전 정리를 수행한다.
- AI는 Expert Mode나 safety bypass를 자동으로 활성화하지 않는다.
- 안전 제한의 최종 집행은 AI 코드가 아니라 기존 Motion Server가 담당한다.

## API 응답과 시퀀스 전환 조건

완료 조건과 허용치는 AI용 시퀀스 작성 가이드에서 관리한다. 생성 프로그램이 이를 평가한다.
사용자는 프롬프트에서 허용치를 재정의할 수 있다. API Schema에는 이 조건들을 포함하지 않는다.

- `position-tolerance` 기본값: `0.5`, 단위는 해당 Axis의 position API 단위(`mm` 또는 `deg`)
- `velocity-tolerance` 기본값: `1.0`, 단위는 해당 Axis의 velocity API 단위(`mm/s` 또는 `deg/s`)
- 적용 우선순위: 사용자 지정값 → 시퀀스 작성 가이드 기본값

명령별 기본 전환 조건은 다음과 같다.

| 명령 | 시퀀스의 다음 단계 전환 조건 |
| --- | --- |
| `move_abs` | 실제 위치가 목표 위치 허용 범위 안이고, Statusword `Target reached`와 `Standstill`을 모두 만족 |
| `move_rel` | 실제 위치가 계산된 최종 목표 위치 허용 범위 안이고, Statusword `Target reached`와 `Standstill`을 모두 만족 |
| `move_vel` | 요청 속도가 0이 아니면 실제 속도가 요청 속도 허용 범위 안이고, Statusword `Target reached`와 `Moving`을 모두 만족 |
| `move_vel`의 속도 0인 Axis | `Standstill` 만족 |
| `jog_start` | API Success만 확인. Moving/목표 속도 도달 Feedback 대기 없음 |
| `stop`, `jog_stop` | `Standstill` 만족 |
| `enable` | Statusword가 `Operation enabled` 상태 |
| `disable` | Statusword가 `Operation enabled` 상태가 아님 |
| `fault_reset` | 별도 Feedback 조건 없이 API 요청 Success로 해당 block 완료 |
| `home` | Homing 완료와 `Referenced` 상태를 모두 만족 |
| I/O write | 별도 Feedback 조건 없이 API 요청 Success로 해당 block 완료 |

`fault_reset`은 Fault 원인을 제거하거나 복구 완료를 보장하는 명령이 아니라 Fault Reset 신호를 장치에
전달하는 write 성격의 명령이다. Fault 조건이 남아 있으면 Fault bit가 해제되지 않을 수 있으므로 이를
기본 전환 조건으로 기다리지 않는다. 복구 상태 확인이 필요한 시퀀스는 별도의 명시적인 Feedback 대기
단계를 둔다.

다축 명령은 선택된 각 Axis에 위 조건을 개별 적용하고 모든 대상 Axis가 각자의 조건을 만족해야 다음
단계로 진행한다. 다축 `move_vel`에서 요청 속도가 0인 Axis에는 `Moving`을 요구하지 않고 `Standstill`을
적용한다.

요청과 응답은 기존 client의 unique `request_id`로 연결한다. 해당 요청의 Success를 확인한 뒤
Feedback 조건을 기다리며 신규 operation ID는 추가하지 않는다.
요청 응답 timeout은 client 설정, 단계/외부 입력 timeout은 예제 프롬프트와 시퀀스 설정에서 관리한다.
Fail, timeout은 후속 단계를 중단하며 응답 timeout은 실행 결과 불명으로 취급하고 자동 재전송하지 않는다.

## 제공 문서와 대표 예제

```text
docs/ai/
├─ README.md                 # 읽는 순서, 플랫폼 경계, Schema·설정·예제 링크
├─ configuration.md          # config.txt/.env 우선순위와 장치 정의 참조 방법
├─ sequence_guide.md         # 완료 조건, 허용치, 대기·중단·실패 처리
└─ prompts/
   ├─ motion_sequence.md
   ├─ io_sequence.md
   ├─ motion_io_sequence.md
   └─ sequence_gui.md
```

이는 생성 예정 산출물 목록이다. API Schema는 서버 코드 영역에 두고 Python 예제는 기존
`reference_clients/python/examples`에 둔다. AI는 안내 → 설정 → 사용자 역할/요구 → Schema/가이드
순서로 읽고 기존 client를 사용하는 프로그램을 생성한다.

대표 예제는 X/Y/Z 3축 Pick & Place이며 기본 1회 실행이다.

1. Pick 위치로 단계별 지정 속도와 시퀀스 공통 가감속을 사용하여 이동하고 완료 대기
2. DO/AO를 파지 설정값으로 변경
3. DI/AI 파지 완료 조건 대기
4. Place 위치로 이동하고 완료 대기
5. DO/AO를 해제 설정값으로 변경
6. 선택적으로 DI/AI 해제 완료 조건 대기
7. 지정된 종료 상태 적용 및 완료 처리

축과 channel, 위치, 단계별 속도, 전체 시퀀스 공통 가감속, 출력값, 입력 조건과 timeout은 프롬프트 수정 항목이다.
가감속은 실행 시작 시 지정값을 기존 설정 API로 적용하고 단계별 변경은 허용하지 않는다.
속도는 단계의 이동 API 파라미터로 전달한다. 별도 속도 설정 API를 단계마다 호출하지 않는다.
필요한 접근·후퇴 경로는 중간 포인트와 단계로 사용자가 지정한다.

## Teaching 선택 기능

Teaching은 시퀀스 생성 프롬프트의 선택 기능이다. 미사용 시 설정의 위치값을 사용하고, 사용 시
이름 있는 포인트를 참조한다. GUI는 동일한 시퀀스 코드와 티칭 데이터를 사용하는 조작 화면이다.

- 생성 프로그램 폴더의 `teaching_points.json`에 포인트 이름, 축 역할별 위치와 단위를 저장한다.
- X/Y/Z → 실제 axis index 매핑은 시퀀스 설정에 둔다. 속도는 단계, 가감속은 시퀀스 공통 설정에 둔다.
- 현재 위치 취득은 한 Feedback의 X/Y/Z를 편집값으로 가져오고, 명시적 저장 버튼으로 파일에 반영한다.
- 포인트 생성·수정·삭제를 지원하며 필요한 포인트가 없으면 Run을 막고 표시한다.
- Run 시 포인트 snapshot을 고정하고 실행 중 편집·수동 조작을 제한한다.
- 축별 +/- hold Jog, Slow/Fast를 제공하고 release, 포커스 상실 또는 버튼 이탈 시 Jog Stop을 요청한다.
- 별도 포인트 이동 버튼은 선택 포인트로 직접 이동하며 Teaching 이동 설정의 속도·가감속을 사용한다.
- Enable/Disable/Fault Reset/Homing은 선택 축에 명시적으로 요청하고 Stop은 시퀀스 사용 축에 적용한다.
- Homing 상태는 표시하되 Homing·Enable·Fault·limit 기반의 추가 Run 차단을 만들지 않는다.
  앞서 제안한 client 측 software limit 사전 차단도 철회하며 기존 API Fail 처리를 사용한다.

## 실행 방식과 GUI

- 터미널: 연결 → 제어권 요청 → 1회 실행 → 정리 → 제어권 해제 → 종료. Ctrl+C로 취소한다.
- GUI: 기존 Control Panel과 같은 Tkinter/ttk를 사용한다. 터미널과 동일한 시퀀스 코드를 공유한다.
- Host/Port, 연결/해제, 제어권 요청/해제, 연결·제어권 상태를 제공한다.
- GUI의 제어권은 사용자가 명시적으로 요청하며 Run 완료 후 유지하고 해제 버튼/종료 시 반환한다.
- Run/Stop, 대기/실행 중/정지 처리 중/완료/중단/실패, 현재 단계·설명과 로그를 표시한다.
- Run 중 중복 실행을 막는다. 수동 조작/Run은 제어권을 가진 연결에서 사용한다.
- 통신·대기가 GUI를 멈추지 않도록 하고 실행 중 창 닫기는 중단·정리 후 종료한다.
- 사용자 Stop/실패 시 사용 축 Stop과 지정된 I/O 정리를 수행한다. 지정이 없는 출력은 유지한다.
- 정상 완료는 프롬프트의 종료 상태를 적용한다. GUI에서는 제어권을 유지한다.
- 정상 완료·Stop·실패에서 자동 Disable하지 않는다. 명시적인 버튼 또는 사용자 종료 정책으로만
  Disable을 수행하며, 기본 정리 절차에는 사용 축 Stop을 적용한다.
- 통신 단절 시 전달하지 못한 정리 명령을 표시한다. 제어권 상실 시 재요청하지 않고 기존 권한 계약을
  따른다. 재연결·재실행에서 중간 단계 자동 재개는 하지 않는다.

## Python 우선 전략

첫 번째 공식 AI 생성 결과물은 Node-RED flow가 아니라 Python 프로그램으로 한다.

- 조건, 분기, 반복, 병렬 실행과 timeout을 명확하게 표현할 수 있다.
- 코드 리뷰, Git 변경 이력과 자동 테스트가 쉽다.
- AI가 Node-RED JSON의 node id, wiring과 dashboard version을 직접 관리하는 부담이 없다.
- 별도 Node-RED runtime 없이 Mock 환경에서 시퀀스를 검증할 수 있다.

Motion Server API는 이미 시퀀스를 구성하는 Motion/I/O block의 단일 계약이다. AI 생성 코드가
`move_axes_abs()`, `enable_axes()`, `set_digital_output()` 같은 Python wrapper로 같은 명령을 다시
정의하지 않고 기존 client의 일반 request 경로로 API block을 직접 조합한다.

AI가 socket, request id, feedback thread와 재연결 정책을 매번 새로 구현하지 않도록 기존 최소 Python
client는 재사용한다. 대표 예제를 먼저 작성하고 반복이 확인된 비도메인 실행 기능만 client 또는 작은
공통 utility로 추출한다.

```text
reference_clients/python/
├─ motion_server_reference_client/   # 기존 연결, request/response, Feedback client
└─ examples/               # 대표 AI 생성 및 사용자 수정 예제
```

정확한 package 구조와 기존 RF-002 reference client 재사용 경계는 구현 계획 수립 시 현재 코드를
검토하여 확정한다.

## 생성 프로그램의 공통 구조

```text
서버 연결
→ 시퀀스 자체 설정·포인트 데이터 확인
→ command authority 요청
→ 초기 조건 확인/설정
→ 시퀀스 실행
→ 완료 또는 중단
→ 안전 정리
→ authority 해제
→ 연결 종료
```

생성 프로그램은 Motion/I/O 명령을 다음처럼 기존 API request로 직접 표현한다.

```python
client.request({
    "cmd": "system/axes/move_abs",
    "axes": [0, 1],
    "positions": [100.0, 30.0],
    "profile_velocities": [50.0, 20.0],
})

client.request({
    "cmd": "system/io/output_write",
    "io": "io0",
    "slot": 2,
    "kind": "digital",
    "channel": 0,
    "value": True,
})
```

API와 의미가 겹치지 않는 공통화 후보는 다음으로 제한한다.

- 최신 Feedback snapshot 접근과 Feedback 조건 대기
- 유한 timeout 계산
- 사용자 stop/cancellation을 대기 코드에 전달
- 연결/Fault/authority 상태 변화 감지
- 취소 가능한 시간 대기

이 기능도 처음부터 별도 sequence framework로 만들지 않는다. 대표 예제에서 같은 통신·대기 코드가
반복되는 것을 확인한 뒤 기존 client 보완을 우선하고, 필요한 경우에만 작은 공통 utility로 분리한다.
안전 stop, output 정리와 authority 해제는 API block을 직접 사용하는 표준 `try/finally` 예제 구조로
제공하며 장비별 종료 정책을 library가 임의로 결정하지 않는다.

## Mock 검증

AI가 생성한 대표 시퀀스는 실제 장비 실행 전에 Mock 환경에서 다음을 검증할 수 있어야 한다.

- 요청한 Axis, I/O, module과 channel 존재 여부
- position/velocity 단위 및 limit
- 순차·동시 명령과 Feedback 기반 완료 판정
- DI/AI 조건과 timeout
- 사용자 Stop에 의한 중단
- Fault 발생 시 후속 단계 차단
- 종료 후 Axis와 output의 안전 상태

Mock 통과가 실장비 안전 검증을 대체하지는 않는다. 실제 기구, 배선, 관성 및 외부 장비 동작은 별도
commissioning과 사용자 확인이 필요하다.

## Node-RED 후속 방향

Python 시퀀스로 대표 애플리케이션을 구현하면서 반복되는 motion, I/O, condition과 recovery 패턴을
먼저 안정화한다. 이후 같은 의미를 기존 Motion Server Node와 표준 Node-RED Node 조합으로 생성하는
두 번째 출력 형식을 제공한다.

초기 RF에서는 AI가 생성한 Python과 Node-RED flow 사이의 자동 변환이나 공통 sequence engine을
구현하지 않는다.

## 초기 제외 범위

- AI가 실장비에 생성 코드를 자동 배포하거나 승인 없이 실행하는 기능
- AI의 Expert Mode 및 protection bypass 자동 사용
- Motion Server core 내부의 범용 sequence engine
- Python과 Node-RED 사이의 자동 변환
- Node-RED를 첫 번째 공식 생성 결과물로 사용하는 것
- 특정 AI 제품에만 종속된 통합
- 복잡한 자연어 의미 검증을 Motion Server core가 직접 수행하는 기능

## 구현 쟁점 검토 이력

### 2026-09-10 구현 쟁점 점검

아래는 점검 당시의 쟁점 이력이다. 최종 적용 기준은 뒤의 후속 확정 계약과 단계별 구현 계획이다.

- Schema 전환 범위: 현재 specification은 CommandSpec metadata 중심이고 validator/handler가 별도로
  동작한다. Schema loader가 기존 metadata를 대체하는 범위와 request/response 구조 정의 범위를
  구현 계획에 명시해야 한다. 숫자 API 필드는 JSON number/integer로 통일하고 문자열 숫자는 거부한다.
  공식 client의 UI 문자열은 전송 전에 숫자로 변환하며, 예제·테스트도 함께 수정한다. OD index의
  16진수 표시는 UI에서 처리하고 전송은 JSON 숫자로 한다. Boolean은 숫자로 허용하지 않는다.
  기존 입력을 보존하기 위한 fallback/alias는 만들지 않는다(DEC-043). 변경을 합의하지 않은
  runtime 동작과 Failure 계약은 유지하며 검증 중복을 만들지 않는다.
- Feedback 의미 확인: Jog 요청은 slow/fast/two_phase이고 숫자 목표 속도가 없다. 기존 장치 정의와
  피드백에서 Jog 도달 상태를 어떻게 확인할지 점검해야 한다. Moving만으로 목표 속도 도달을 추정하지
  않는다. 모드별 Target reached/Moving 의미와 Standstill 허용치 적용도 가이드 작성 시 확인한다.
- Client 대기 구현: 기존 motion_server_reference_client는 request_id와 get_feedback 큐를 제공한다.
  최신 snapshot 취급, timeout·취소, GUI thread 전달은 이를 재사용하여 구현한다. 요청 ID는 응답을
  연결하며 무요청 주기 Feedback에는 ID가 없으므로 과거 큐 항목을 새 상태로 쓰지 않도록 점검한다.
  신규 서버 operation tracker는 추가하지 않는다.
- 값 반영: move_rel의 최종 목표 확인과 단계별 속도·가감속은 기존 API/응답으로 표현하는 방법을
  확인한다. Teaching 이동도 같은 API를 사용한다.
- 실제 디렉터리/Schema draft/공통 정의 참조/배포 포함, 예제의 구체적인 IO 채널·값과 timeout 기본값은
  구현 계획에서 제시한다. 현재 단계에서 자동 실행 가능한 실장비 기본값으로 확정하지 않는다.

위 점검의 후속 결정은 아래 확정 계약과 구현 계획으로 해소했다. 이력에 남긴 Jog 도달 대기와
단계별 가감속 제안은 채택하지 않는다. 구체적인 Schema draft, 라이브러리와 예제 기본값은 기존
의존성과 Mock 구성에 맞춰 구현 단계에서 선택·기록하며 별도 제품 기능 결정으로 취급하지 않는다.

## 2026-09-10 후속 확정 계약

- `motion_server/api/schema/`에 common.json, system.json, axis.json, io.json, bus.json,
  simulation.json을 둔다. axis는 axis/axes, io는 AP/IOL 하위 API를 포함한다. system은 서버·제어권·
  공통 Feedback 등 나머지 API를 담당한다. 공통 정의는 로컬 `$ref`로 재사용한다.
- Schema는 API 계약의 단일 원본이며 시작 시 로딩·문법·참조·명령 중복을 확인한다.
  기존 specification은 이를 읽어 CommandSpec을 구성한다. Handler 연결은 Python registry에 유지한다.
- 기존 validator가 Schema 기반 요청 구조 검증과 기존 runtime 전제조건 검증을 담당한다.
  응답/Feedback은 기존 encoder/status 경로에서 계약을 사용한다. 값 취득·단위 변환은 Python에 유지한다.
  새 조립 계층, 실행 중 응답/Feedback 검증, client 응답 Schema 검증은 추가하지 않는다.
- Python client의 request_id/get_feedback를 재사용한다. 시퀀스가 조건·timeout·취소를 처리하며
  반복이 확인될 때만 `wait_for_feedback(predicate, timeout, cancel_event)` 같은 비도메인 utility를 둔다.
- GUI는 같은 시퀀스를 worker thread에서 실행하고 GUI thread가 상태·로그를 표시한다.
  대기는 짧은 간격으로 취소를 확인한다. 이미 전송한 요청은 취소된 것으로 간주하지 않으며 응답 또는
  기존 request timeout 이후 후속 단계 대신 정리한다. 자동 재전송하지 않는다.
- `jog_start`는 Success만 확인하고 `jog_stop`은 Success 이후 Standstill을 기다린다.
- 가감속은 시퀀스 공통 설정, 속도는 이동 API의 단계별 파라미터다. 종료 시 자동 Disable하지 않는다.

## 단계별 구현 계획

현재 상태: S01 코드 전환 및 자동 테스트 반영. 실제 패키지 빌드/실행 검증은 사용자 결정으로 S04 일괄 검증에 이관한다. 하위 번호를 계속 분할하지 않고 아래 단위를
완료할 때 상태·검증 결과·변경 파일·다음 작업을 갱신한다.

| 단계 | 상태 | 범위 | 완료 조건 |
| --- | --- | --- | --- |
| S01 | implemented | Schema와 서버·공식 client 동시 전환 | 요청 검증·공식 client·응답/Feedback 계약 테스트 반영. 실제 패키지 검증은 S04로 이관 |
| S02 | implemented | AI 안내·설정 가이드·시퀀스 가이드·프롬프트 | 책임 경계와 CLI/GUI/Teaching 문서화, 로컬 링크·JSON 예시 계약 검사. 독립 생성 평가는 S04 |
| S03 | implemented | Python AI 레퍼런스 프로그램: Pick & Place·Teaching·GUI | 공통 실행 코드·명시적 포인트 저장·Run/Stop 구현 및 기본 자동 검사. 통합 실행/전체 GUI 평가는 S04 |
| S04 | in_progress | 통합 검증·신규 AI 세션 다중 모델 평가·문서 정합화 | 공식 예제 Mock 시험과 제공 자료만 사용한 반복 생성·실행 검증 완료 |

### S01 Schema 및 공식 client 전환

2026-09-10 진행 기록:

- 반영: namespace Schema 6개와 로컬 전용 loader, 57개 명령 metadata를 읽는 기존 CommandSpec,
  jsonschema 의존성 및 Windows/Docker 설치·리소스 포함 경로.
- 기존 validator에 요청 구조 검증을 연결했다. 숫자 문자열·Boolean 숫자 대용·비유한 숫자는 거부하며
  기존 authority/initialization/runtime Fault 판정은 유지한다. 필수 selector·중첩 trajectory/IO 숫자와
  data_type별 parameter value를 Schema에서 검사한다.
- Axis/IO Panel과 Node-RED Axis/I/O Dashboard의 입력 문자열을 전송 전에 변환했다. Python transport는
  이미 숫자를 그대로 전송하므로 변환 계층을 추가하지 않고 wire test와 사용 안내를 보완했다.
- 명령별 응답 envelope와 Axis/서버/Bus/IO 상태, 파라미터·catalog·공통 Feedback 계약을 추가했다.
  실제 encoder/handler 출력과 비교하는 테스트용 validator만 제공하며 runtime 응답 검증은 하지 않는다.
  장치별 metadata/진단 상세 등 가변 object는 기존 출력의 확장 영역을 유지한다.
- 검증: Python 전체 443개, Node-RED 8개 통과. Mock Axis/IO 상태·Feedback, 요청 거부 전 handler 미실행,
  numeric wire type, 잘못된 참조·중복 명령·필수 metadata 누락을 검사했다.
- 실제 패키지 빌드/실행은 사용자 결정에 따라 나중에 일괄 수행한다. 현 테스트가 패키지/실장비 검증을
  대신하지 않는다. S02 구현 후 다음 단계는 S03 AI 레퍼런스 프로그램이다.

1. 기존 명령·요청·응답·Feedback 정의와 client 전송 경로를 대조하여 계약 목록을 만든다.
2. namespace별 Schema와 loader를 작성하고 기존 specification/validator/encoder/status 경로에 연결한다.
   형식 정의의 중복 하드코딩을 정리하되 값 계산·실행 책임은 유지한다.
3. 숫자 필드는 JSON number/integer로 통일한다. Python client, Axis/IO Control Panel, Node-RED node와
   sample flow의 전송값·관련 문서·테스트를 함께 수정한다. UI의 16진수 표시는 허용하되 숫자로 전송한다.
4. 설치/Windows 패키지에 Schema와 로컬 참조 파일을 포함하도록 구성한다. 실제 빌드/실행 검증은 S04에 이관한다.
5. 숫자 문자열/Boolean 거부, 필수값·허용값, 기존 runtime/Failure parity, 응답/Feedback 계약을
   자동 테스트로 확인한다. 호환성 제거로 의도한 차이는 테스트 기대값에 명시한다.

S01은 서버·공식 client·예제·테스트·패키지 설정을 함께 전환한다. 2026-09-10 후속 사용자 결정으로
실제 패키지 빌드 검증만 S04 일괄 검증에 이관했다. 서버만 전환된 상태를 완료 처리하지 않는다.
새 서버 모션 완료 판단, 중복 runtime 인터락, 응답 검증 계층은 없어야 한다.

### S02 AI 지식 및 프롬프트

2026-09-10 구현:

- [AI 진입 안내](../../ai/README.md), 설정 해석, 시퀀스 가이드와 Motion/I/O/Pick & Place/GUI 프롬프트 4개를 작성했다.
- 설정 읽기 전용·사용자 commissioning 경계, 기존 API 직접 조합, 공통 가감속/단계별 이동 속도,
  명령별 대기 조건, timeout/취소/cleanup, 선택적 Teaching과 공통 CLI/GUI 실행 계약을 포함했다.
- `tests/test_ai_documentation.py`가 자료 묶음/로컬 링크/JSON 요청 예시를 실제 Schema와 대조한다.
  이는 문서 정합성 검사이며 독립 모델 생성/실행 평가가 아니다. 실제 패키지 검증과 AI 평가는 S04에 남긴다.
- S03 명칭은 사용자 결정에 따라 “AI 레퍼런스 프로그램”으로 한다. 다음 구현은 S03이다.

- 앞서 정의한 docs/ai 파일을 작성하고 실제 Schema, 설정과 Python client 경로로 연결한다.
- API Schema에는 시퀀스 조건을 넣지 않고 가이드에 명령별 조건·허용치·실패 처리 방법을 둔다.
- 프롬프트에는 X/Y/Z 역할, 파지·해제 출력, 입력 조건, 단계 timeout과 공통 가감속을 수정 항목으로 둔다.
- Teaching과 GUI를 선택할 수 있도록 하고 중복 API wrapper나 서버 인터락 재구현을 요청하지 않는다.

### S03 AI 레퍼런스 프로그램

2026-09-10 구현:

- [Pick & Place AI 레퍼런스](../../../reference_clients/python/examples/pick_place/README.md)에
  `program.py`, CLI `__main__.py`, `gui.py`, `sequence.json`, `teaching_points.json`을 추가했다.
- 공식 client를 사용해 기존 API를 직접 호출한다. 서버/API/client transport는 변경하지 않았다.
  CLI/GUI가 동일 Sequence를 사용하고 Feedback 소비자는 하나로 공유한다.
- 공통 가감속, 단계별 속도, 다축 위치/Reached/Standstill 대기, DI/AI 조건, bounded 취소/cleanup,
  명시적 제어권, 선택적 Teaching 캡처/편집/저장/수동 Jog·포인트 이동을 구현했다.
- 추가 Run 운전 인터락은 두지 않았다. API Fail은 표시하고 중단하며, 첫 이동 Success 뒤 발생한
  Feedback Fault는 실행 중 실패로 처리한다. 자동 Disable/재전송/재개는 없다.
- `tests/test_ai_pick_place.py` 13개: 가짜 client 주기 Feedback과 실제 요청 Schema를 사용해 정상 순서,
  Fail/timeout/Stop/Fault/연결·권한 상실, 자료 신선도·다축 조건, Teaching snapshot/저장,
  네트워크 없는 Tk GUI 생성·Run 취소·Jog release를 검사했다.
- Python 전체 459개 통과. CLI `--help` 실행 확인. 실제 Mock 서버 TCP end-to-end, 전체 GUI 수동 조작,
  실장비, 독립 AI 평가와 실제 패키지 빌드는 수행하지 않았다. 통합 검증은 S04이며 다음 단계다.

- 기존 Python client로 API를 직접 조합한다. 필요성이 확인된 대기·취소 utility만 최소 추출한다.
- 공통 가감속 적용 후 단계별 속도로 Pick 이동 → 파지 → 확인 → Place 이동 → 해제 → 선택적 확인을 수행한다.
- teaching_points.json과 역할 매핑·단위, Run snapshot, 명시적 저장·편집·삭제를 구현한다.
- Tkinter GUI의 연결·제어권·Run/Stop·Teaching·상태/로그를 동일 실행 코드에 연결한다.
- server Fail로 실행을 중단하며 Homing/Enable/Fault/limit의 추가 Run 인터락을 두지 않는다.
  포인트 누락/잘못된 파일과 중복 실행 같은 프로그램 자체 상태는 검사한다.

### S04 검증 및 인계

2026-09-11 사용자 지시: 별도 명시적 지시가 있기 전까지 Node-RED 관련 테스트는 실행하지 않는다.
자동 회귀·Dashboard/수동 시험 모두 제외하며 일반적인 검증/계속 진행 요청으로 재개하지 않는다.
이미 수행한 결과는 과거 이력으로 보존하되 이후 S04 재검증 대상에는 포함하지 않는다.

2026-09-11: [진행/실패 이력 및 결과](RF-019-S04-validation-2026-09-11.md).
실제 Mock TCP 통합 시험과 Windows 빌드를 수행했고 authority 응답 Schema/AI 자료 패키징 누락을 보완했다.
Python 467개, Node-RED 8개 통과. 독립 AI 생성 24회와 전체 GUI 평가는 아직 미완료다.
후속 자동 확장 검증: Mock TCP에 연결한 GUI/Teaching/종료, WKC Fault 및 응답 지연 7개를 추가하고
관련 Python 회귀 47개를 통과했다. 이번 Node-RED 시험은 없으며 이전 결과는 이력이다.
GUI 수동 시각 확인 및 독립 생성 평가는 미완료다. 자세한 조건/한계는 위 검증 기록을 따른다.

- S01에서 이관한 실제 Windows 패키지 빌드 및 독립 폴더에서의 Mock 기동/API 검증을 일괄 수행한다.
  Schema 파일·로컬 참조·jsonschema 의존성 누락을 확인한다. 현재 미실행이며 실축 시험과 구분한다.

- Mock에서 정상 1회 완료, API Fail, 응답/조건 timeout, Stop, 연결·제어권 상실을 시험한다.
- Jog release/포커스 상실, GUI 중단·종료, 티칭 파일 재로딩과 Run snapshot을 확인한다.
- 자동 재전송·자동 재개·자동 Disable이 없고, 지정 없는 I/O 출력 유지 정책을 확인한다.
- 배포물에 Schema와 안내/예제 등 의도한 산출물이 포함되는지 검증한다.
- RF-019/remaining_tasks/worklog에 검증 결과와 변경 파일을 기록한다. 실장비 시험은 별도 명시적
  실행 요청에 따르며 Mock 결과와 구분한다. Node-RED 신규 시퀀스 생성은 후속 범위로 유지한다.

#### 사전 프로젝트 지식 없는 AI의 생성 검증

공식 예제의 실행 성공과 별도로, 제공 자료만으로 사용자가 원하는 프로그램을 생성할 수 있는지 검증한다.
프로젝트 대화 이력·메모리를 공유하지 않는 새 세션을 매 회차 사용한다. 사용자에게 배포할 문서,
API Schema, config.txt/.env와 참조 정의, 공식 client·예제만 동일하게 제공한다. 평가 전용 숨은 설명이나
기존 대화의 결정 요약을 추가하지 않는다. 여기서 사전 지식 없음은 프로젝트 세션 문맥이 없다는 의미이며
모델의 학습 데이터에 대한 보장을 뜻하지 않는다.

- 기준 모델과 다른 성격의 모델을 포함하여 최소 2개를 사용한다. 성능 중심과 비용·속도 중심 모델을
  포함하고, 필요하면 세 번째 모델을 추가한다. 구체 모델은 평가 시 사용 가능한 정확한 ID로 기록한다.
- 기본 Pick & Place, Teaching 선택, GUI 선택, 축·포인트·I/O 조건을 변경한 변형 시나리오를 시험한다.
  최소 2개 모델 × 4개 시나리오 × 3회 독립 생성으로 반복 편차를 확인한다.
- 같은 시나리오는 동일 프롬프트·자료를 제공하고 파일 접근·Python 실행·도구 및 Mock 환경을 맞춘다.
  맞출 수 없는 차이는 기록하여 모델 능력 차이로 단정하지 않는다.
- 요구 순서·속도·I/O 조건, API·숫자 타입·단위, Teaching·GUI, 정상 완료·Stop·실패 처리를 확인한다.
  서버 검증 중복, 임의 API, 자동 재전송·자동 Disable 같은 계약 위반도 평가한다.
- 최초 생성 결과와 실행 결과를 보존한다. 수동 수정이나 추가 설명을 받은 결과는 무보조 성공으로
  집계하지 않는다. 생성 세션 내 도구 실행·자체 수정 여부도 기록한다.
- 실패는 자료의 누락/모순, 모델의 계약 위반, 도구·환경 문제로 구분한다. 자료를 개선한 경우 해당
  최종 자료로 새 세션에서 재시험하며, 이전 실패 기록을 삭제하거나 성공 회차만 선별하지 않는다.

각 회차에 모델 ID/버전·추론 설정, 검증 날짜, Motion Server 릴리스와 자료 commit(미커밋 자료는 hash),
제공 파일 목록, 정확한 프롬프트, 사용 도구·환경, 생성 코드, 시험 로그와 합격/실패 이유,
추가 설명·수동 수정 필요 여부를 기록한다. 반복 결과는 시나리오별 무보조 성공 횟수/전체 횟수로 공개한다.

사용자에게 특정 모델의 '최소 버전 이상'을 보장하지 않고 실제 검증된 모델·설정·시나리오 목록을 제공한다.
미검증 모델 사용은 제한하지 않되 검증된 조합과 구분한다. 모델 갱신이나 문서·Schema·프롬프트 변경 시
관련 시험을 재수행한다. 아직 평가하지 않은 모델은 검증 목록에 넣지 않는다.

S04는 공식 예제 검증과 위 생성 평가를 모두 수행하고 계약 위반/실패 원인을 처리·기록한 뒤 완료한다.
'평가 수행'과 '특정 모델의 시나리오 통과'를 구분하고, 반복 실패한 조합은 검증 통과로 안내하지 않는다.

#### 시험 환경과 수행 절차

평가 대상은 모델 단독이 아니라 모델·Agent 프로그램·도구·실행 환경의 조합이다.

1. 평가 시작 전에 자료 버전, 요구사항별 합격 항목, 입력 조건, 예상 API 동작/상태, timeout,
   생성 시간·도구 호출 등 예산과 환경 오류 재시험 규칙을 고정한다. 모델별 임의 연장은 하지 않는다.
2. 각 회차는 새 세션과 초기화된 작업 폴더·Mock에서 시작한다. 이전 생성물, 티칭 파일, cache,
   Git 이력의 평가 정답과 다른 세션 메모리를 제공하지 않는다. 배포 대상 공식 예제는 제공해도 된다.
3. Agent에 파일 읽기·코드 작성·실행·자체 시험 및 수정을 허용한다. 서버와 독립 평가 도구는 수정
   불가능한 경계에 두고, 최종 생성물은 깨끗한 평가 환경에서 다시 실행한다.
4. 최초 실행 가능한 산출물과 최종 제출물을 별도로 보존한다. 정해진 예산 내 Agent 자체 수정은
   무보조 수행에 포함한다. 사람의 코드 수정·요구사항 추가 설명은 보조 수행으로 별도 분류한다.
5. 독립 시험으로 최종 결과를 판정한다. Agent가 작성한 테스트와 완료 선언은 보조 증거이며
   최종 합격 근거를 대체하지 않는다. 독립 시험은 정상 reference 예제가 통과하는지도 사전 확인한다.
6. 모델/자료 실패는 실패 회차로 보존한다. 외부 환경 오류는 근거와 함께 별도 집계하고 사전에 정한
   규칙으로만 재시험한다. 원본·재시험 ID를 연결하고 실패 기록을 삭제하지 않는다.

환경 기록에는 Agent 프로그램/버전·시스템 설정, 모델 ID/추론 설정, OS/Python/의존성,
CPU·메모리·시간/도구 예산, 인터넷·설치 허용 범위, Mock 초기 상태를 포함한다. 관측 가능한
대화·도구 호출·stdout/stderr와 생성 파일을 보존한다. 비교 환경이 다르면 결과를 다른 조합으로 표시한다.

#### 공개 예제와 최종 평가용 변형 분리

공개 예제 재현과 별도로 문서 개선에 사용하지 않은 변형을 최소 한 시나리오에 사용한다.
축 index/역할 재배치, 다른 I/O channel·포인트, 파지 입력 지연, 해제 확인 선택 등을 조합한다.
AI에는 요구사항을 모두 명확히 알려주되 독립 시험 코드·정답 구현은 별도로 보관한다.
사용자에게 알려주지 않은 요구사항으로 감점하지 않는다. 실패를 보고 문서 개선에 사용한 변형은
개발용으로 전환하고 최종 평가에는 새로운 변형을 준비한다.

#### 독립 평가 방법 및 회차 합격 기준

| 필수 평가 항목 | 판정 방법 | 합격 기준 |
| --- | --- | --- |
| 실행 가능성·API 계약 | 실제 실행 및 요청 기록 | 공식 client/API 사용, 숫자 타입·단위·대상 일치, 서버/시험 파일 수정 없음 |
| 단계 순서·완료 대기 | API 기록과 Mock 상태 변화 대조 | Pick/파지/입력 확인/Place/해제 순서와 지정 속도 준수, 조건 충족 전 후속 동작 없음 |
| 외부 입력·timeout | DI/AI 지연·미충족 주입 | 지정 조건까지 대기, timeout 시 실패 표시와 후속 단계 중단 |
| Stop·Fail·연결/제어권 상실 | 각 상황 주입과 요청/상태 관측 | 기존 계약에 따른 중단·가능한 정리 수행, 자동 재전송·재개 없음 |
| 종료 정책 | 출력 및 API 기록 | 지정 I/O 정리 또는 미지정 출력 유지, 자동 Disable 없음, CLI/GUI별 제어권 정책 준수 |
| Teaching 선택 시 | 저장·재시작·편집 시험 | 위치/단위·매핑 일치, 명시적 저장, Run snapshot 유지, 누락 파일/포인트 설명 |
| GUI 선택 시 | 실제 Run/Stop·창 닫기·Jog 조작 | 상태/단계/실패 표시, 응답성, 중복 실행 방지, 합의된 중단/종료 및 Jog Stop 동작 |
| 책임 경계 | 코드 검토와 동작 시험 | API wrapper/서버 인터락 중복 및 임의 API 추가 없음, 공통 가감속·단계별 속도 준수 |

해당 시나리오의 필수 항목을 모두 만족해야 회차 합격이다. 비적용 항목은 시험 전에 명시한다.
단순 완료 로그·정상 exit만으로 합격하지 않는다. 코드 검토나 보조 AI 평가는 근거 위치와 함께
기록하고 애매한 판단은 사람이 확인한다. 실행 결과는 독립 관측으로 판정한다.
GUI 미관, 가독성, 생성 시간·비용은 별도 품질 지표이며 필수 동작 실패를 점수로 상쇄하지 않는다.

#### 결과 표시 및 완료 판정

- 시나리오별 최초 산출물 합격 수, 예산 내 최종 무보조 합격 수, 보조 후 합격 수,
  모델/자료 실패 수와 환경 오류 수를 분리한다. 전체 시도와 유효 평가 횟수를 모두 공개한다.
- 3회 반복은 초기 점검 규모다. 3/3 성공을 일반적인 성공률 100%나 신뢰성 보장으로 표현하지 않는다.
  여러 모델·시나리오의 회차를 하나의 동일 성공확률 표본처럼 합쳐 해석하지 않는다.
- 해당 조합/시나리오의 최종 자료 기준 3회 유효 시험이 모두 필수 항목을 만족한 경우에만
  '해당 시나리오 3/3 무보조 통과'로 표시한다. 1~2회 통과는 부분 성공 횟수 그대로 보고한다.
- 문서/평가 도구 결함을 처리한 최종 자료로 전체 최소 평가표를 수행하고 결과를 보고해야 S04를
  완료한다. 모델별 실패를 감추거나 모든 모델이 통과했다고 간주하지 않는다. 사용자 추천은 실제 통과
  범위로 제한한다. 모든 조합이 실패한 시나리오는 기능 검증 미달로 남기고 해결 전 완료하지 않는다.
- 추가 평가는 반복 횟수만 늘리기보다 실제 실패와 사용자 시나리오 다양성을 우선한다. 모델·자료 변경
  시 관련 회귀 시험을 수행하고, 높은 성공률 보장이 필요하면 별도 표본/신뢰구간 계획을 수립한다.
- Mock 통과는 생성 프로그램과 계약 검증 결과이며 실장비 동작 검증을 대신하지 않는다.

#### 평가 설계 참고 자료

- [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [Anthropic: Infrastructure noise](https://www.anthropic.com/engineering/infrastructure-noise)
- [OpenAI: SWE-bench Verified](https://openai.com/index/introducing-swe-bench-verified/)
- [NIST: 평가 환경의 정답 유출 사례](https://www.nist.gov/caisi/cheating-ai-agent-evaluations/2-examples-cheating-caisis-agent-evaluations)
- [EvalPlus 연구](https://arxiv.org/abs/2305.01210)
- [NIST: Exact binomial confidence limits](https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbici.htm)

위 자료를 참고해 Motion Server에 맞춰 정한 내부 시험 정책이다. 2개 모델·4개 시나리오·3회와
회차 합격 규칙은 외부 표준의 의무 수치가 아니다.

## 완료 조건

- 사용자 수정형 예제 프롬프트의 공통 형식과 대표 시나리오가 제공된다.
- AI용 정적 플랫폼 지식이 개념, API 계약, 시퀀스 규칙과 Failure/recovery를 포함한다.
- 현재 시스템 구성과 지원 기능을 확인하는 runtime 정보 경계가 확정된다.
- Motion Server API가 시퀀스 구성 block의 단일 계약으로 유지되고, AI 생성 코드와 예제가 기존
  Python client를 통해 API request를 직접 조합한다.
- 대표 예제에서 반복이 확인된 Feedback 대기, timeout과 cancellation만 기존 Python client 또는
  비도메인 utility로 최소 공통화한다.
- AI가 생성하는 Python 프로그램의 자체 데이터 검증, authority, timeout, Feedback 완료 판정, Stop/Fault 처리와
  안전 정리 구조가 일관된다.
- 단일축, 다축 동시 이동, I/O handshake와 Motion/I/O 복합 시퀀스 예제가 제공된다.
- 대표 생성 결과가 Mock에서 정상 완료, timeout, Stop과 Fault 시나리오를 자동 검증한다.
- 최소 2개 모델의 새 세션에서 4개 대표 시나리오를 각 3회 생성·시험하고, 최종 자료 기준 결과와
  무보조 성공 여부를 기록한다. 공식 예제 통과만으로 S04를 완료 처리하지 않는다.
- 사용자용 검증 모델 목록에 정확한 모델·설정·자료 버전·환경·날짜·시나리오별 결과를 제공한다.
- Node-RED는 Python 패턴 안정화 이후의 후속 출력 형식으로 명시된다.
