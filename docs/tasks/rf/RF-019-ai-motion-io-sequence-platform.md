# RF-019 AI 기반 Motion/I/O 시퀀스 생성 플랫폼

- 등록일: 2026-09-09
- 상태: `in_progress`
- 우선순위: 높음
- 1차 생성 결과물: Python 시퀀스 프로그램

## 배경

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

## 제외 범위

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

현재 상태: S01~S03 implemented, S04 in_progress. 통합·패키지 검증과 r1c 생성물 실행 시험을 수행했으며,
독립 AI 반복 평가와 GUI 수동 확인이 남아 있다. 하위 번호를 계속 분할하지 않고 아래 단위를
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

2026-09-11: [진행/실패 이력 및 결과](#s04-validation).
실제 Mock TCP 통합 시험과 Windows 빌드를 수행했고 authority 응답 Schema/AI 자료 패키징 누락을 보완했다.
Python 467개, Node-RED 8개 통과. 독립 AI 생성 24회와 전체 GUI 평가는 아직 미완료다.
후속 자동 확장 검증: Mock TCP에 연결한 GUI/Teaching/종료, WKC Fault 및 응답 지연 7개를 추가하고
관련 Python 회귀 47개를 통과했다. 이번 Node-RED 시험은 없으며 이전 결과는 이력이다.
GUI 수동 시각 확인 및 독립 생성 평가는 미완료다. 자세한 조건/한계는 위 검증 기록을 따른다.

- S01에서 이관한 실제 Windows 패키지 빌드 및 독립 폴더에서의 Mock 기동/API 검증을 일괄 수행한다.
  Schema 파일·로컬 참조·jsonschema 의존성 누락을 확인한다. 2026-09-11 수행 결과는 아래 검증 기록을 따르며 실축 시험과 구분한다.

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

2026-09-11 정정: 생성 시간 15분은 합의된 값이 아니다. r1c에는 별도 시간/토큰 제한을
부과하지 않았다. 아래 예산 기록 절차는 평가자가 임의 숫자를 합의 사항으로 추가할 권한이 아니다.
새 제한을 적용하려면 별도 합의한다. 요청/단계 timeout은 생성 예산과 구분한다.
[r1c 기록](#s04-basic-r1c): 생성물 8개 실행 시험 통과,
생성 중 수집기/서버 환경 오류로 정식 무보조 합격에는 미집계.

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

## 검증 기록

### 2026-09-17 GUI Pick & Place 독립 생성 r1

- 회차: `s04-gui-r1-20260917`. 새 독립 CLI 세션에 제공 문서/Schema/공식 client와
  Pick & Place 및 GUI 선택 프롬프트를 전달한다. 기존 대화, 이전 생성 코드, 평가 도구는 전달하지 않는다.
- 사용자 기본 CLI 수동 테스트 완료 보고를 기록한다. 구체적인 수동 시험 항목별 증거는 별도 수집하지 않았다.
- 후속 Pick & Place는 수동 시험 `manual-sequence-test/generated/settings.json` 기준으로
  Pick 위치 `[50,60,70]` mm / 속도 `[50,50,40]` mm/s,
  Place 위치 `[100,110,120]` mm / 속도 `[50,50,20]` mm/s,
  공통 가감속 각 축 `100` mm/s²를 사용한다. 이전 소거리 평가 원본/결과는 변경하지 않는다.
- 이번 범위: GUI 연결/제어권, Run/Stop/상태/실패 표시, 중복 Run 방지, 실행 중 종료,
  공통 시퀀스 정상/장애 처리. Teaching·Node-RED·실장비·다른 모델/추가 회차는 제외한다.
- 사용자 서버와 별도의 Mock 서버에서 진행한다. 무기한 사용자 조작 대기 GUI를 남기지 않는다.
- 산출물: `.codex_output/s04-gui-r1-20260917/`에 프롬프트, 자료 hash, 초기/중간/최종 코드,
  생성 이벤트, 사용량과 실행 결과를 보존한다. 생성 예산을 임의로 추가하지 않는다.
- 상태: **독립 생성 완료, 실제 Tk 이벤트 루프 + Mock TCP 기능 시험 9/9 통과**.
  GUI 수동 시각/마우스 확인은 남아 있어 GUI 회차 최종 승인 보류. 기존 확정 유효 평가 1/24에
  이번 GUI 자동 검증 완료 1회를 별도 표시하며 아직 2/24 최종 합격으로 합산하지 않는다.

#### 생성 및 환경 기록

- 모델 `gpt-6-astra`, CLI `0.153.4`, 독립 thread `01a0ad6a-2fda-7273-9135-4c054a9af0d0`.
  reasoning effort는 별도로 확정하지 않았다. 생성/자체 검증 시간 817.427초.
- 제공 파일 41개 hash 변경 없음, 중간 snapshot 19개와 최종 제출 코드 보존.
  공식 reference example은 제공 자료에 포함되어 있으므로 예제 없는 생성 시험으로 해석하지 않는다.
- 자체 시험: sequence 10개, GUI 실패 처리 2개 통과. CLI 실제 Mock 1회 정상 완료.
  위젯 대역 + 실제 Mock으로 GUI 정상/Stop/닫기 callback 시험 통과.
- 독립 생성 sandbox에서는 Tcl/Tk `init.tcl`을 로드하지 못해 실제 창 시험 실패.
  이 환경 실패는 생성물 실패와 구분하며, 평가 환경에서 제출 Python 수정 없이 실제 Tk 검증을 수행했다.
- 최초 평가기의 즉시 API Fail 시험은 관측 tick 수 부족으로 false negative였다.
  별도 관측 구간을 추가해 재확인했다. 평가기 자체 heartbeat가 창 종료 뒤 남아 발생한 Tcl 경고도
  평가기 소유 timer만 취소하도록 보완했다. 제출 코드는 변경하지 않았다.
- `evaluation/`에 최초 결과/재확인, `evaluation-recheck/`에 평가기 보완 후 전체 9개 결과를
  보존한다. 최종 판정 근거는 `evaluation-recheck-results.json`이다.

#### 독립 실행 결과 및 케이스별 토큰

| 케이스 | 결과 | 확인 내용 | 추가 모델 토큰 |
| --- | --- | --- | ---: |
| normal | 통과 | 확대 위치/속도, 입력 AND 대기, 출력 순서, 완료/Stop, Run 후 제어권 유지 | 0 |
| stop | 통과 | 입력 대기 중 Stop 버튼, cancelled, 후속 이동/출력 해제 없음 | 0 |
| close | 통과 | 실행 중 WM_DELETE_WINDOW callback, Stop 후 제어권 해제/창 종료 | 0 |
| input_timeout | 통과 | 10초 입력 timeout, failed, Stop 확인 및 후속 단계 금지 | 0 |
| api_fail | 통과 | Disable된 축의 실제 이동 Fail, Stop Fail도 정지 미확인으로 표시 | 0 |
| fault | 통과 | 시험 launcher WKC Fault 주입 후 failed, 후속 이동 금지 | 0 |
| connection_loss | 통과 | TCP proxy 단절 후 failed, cleanup 불가 명시, 자동 재개 없음 | 0 |
| authority_loss | 통과 | 같은 client의 실제 제어권 해제 후 failed, 재획득/후속 이동 없음 | 0 |
| response_timeout | 통과 | 응답 6초 지연으로 timeout, 늦은 Success 실제 전달 후에도 재개 없음 | 0 |

- 각 시험에서 중복 Run 거부, 공통 가감속 1회, 요청 Schema/JSON 숫자, 이동 완료 후 출력,
  자동 Enable/Homing/Disable/recovery 부재와 제출 Python hash 불변을 확인했다.
- 실제 Tk root는 숨긴 상태에서 버튼 invoke/등록된 창 닫기 callback과 event loop로 검사했다.
  OS 마우스/키보드 입력, 화면 레이아웃, 실제 창 포커스 전환은 검증하지 않았다.
- GUI event-loop 관측 최대 간격은 최종 9개 시험에서 약 0.211초 이내였다.
  하드 실시간 또는 즉시 비상정지 보장이 아니다.
- Fault 주입은 실제 케이블/실장비 고장이 아니다. API Fail/연결·제어권 상실의 Stop 미확인은
  성공으로 숨기지 않고 실패로 표시하는 것이 해당 시험의 기대 결과다.

| 사용량 범위 | 입력 | 캐시 입력(입력에 포함) | 출력 | 입력+출력 |
| --- | ---: | ---: | ---: | ---: |
| 독립 생성 전체(자체 검토/시험 포함) | 1,446,773 | 1,373,056 | 21,976 | 1,468,749 |
| 평가 환경 실행/재시험 | 0 | 0 | 0 | 0 |

- reasoning output 원본 값 4,813은 출력에 별도 가산하지 않는다. 평가 담당 대화 사용량은 제외한다.
- 원본 이벤트, `token-usage.json`, 실행 케이스별 `result.json`에 기록. 재시험도 모델 호출은 0이다.
- 생성용 및 평가용 Mock 서버는 정리했다. 사용자 수동 테스트 서버는 변경/종료하지 않았다.
- 다음 단계는 GUI 수동 확인. Teaching/다른 모델/추가 독립 생성은 이번에 수행하지 않았다.

### 2026-09-17 기본 Pick & Place 정식 회차 r2

- 회차: `s04-basic-r2-20260917`. 기본 CLI 1회 생성 후 정상/입력 timeout/API Fail/Stop/
  Fault/연결 상실/제어권 상실/응답 timeout을 검증한다. GUI·Teaching·다른 모델/반복 회차는 제외한다.
- 결과: **기본 CLI 정상/실패 처리 독립 실행 시험 8/8 통과, 첫 정식 회차 완료**.
  평가 환경 기준 Python TCP 시험 6개 통과(18.855초). 정식 유효 평가 1/24, 기본 시나리오 해당 모델 1회 통과.
- 새 세션 `01a0ad43-c45c-7d50-8662-552ed4c2386b`, 별도 Mock port 62554.
  기존 대화와 평가 코드는 제공하지 않았다. 최초/중간 산출물은 snapshots, 최종 제출은 submitted에 보관한다.
- 산출물/정확한 프롬프트/자료 manifest/이벤트 위치: `.codex_output/s04-basic-r2-20260917/`.
- 토큰 집계: 생성 회차의 CLI 원본 input/cached input/output usage를 기록하며 cached input을
  input에 다시 더하지 않는다. 생성 종료 전 사용량은 미확정으로 둔다.
- 실행 시험 8개는 별도 모델 호출이 없는 자동 시험이다. 케이스별 추가 모델 토큰은 0이며
  공유 생성 비용을 케이스마다 중복 집계하지 않는다. 평가 담당 대화 토큰과 생성 AI 토큰도 구분한다.
- 추가 AI 수정·재생성을 수행하면 별도 호출 사용량과 보조 여부를 기록한다.

#### 생성 및 독립 검증 결과

- 모델 `gpt-6-astra`, codex-cli 0.153.4, Python 3.14.3. effort는 로그에서 null이며 특정 수준으로 단정하지 않는다.
- 생성 CLI exit 0, 약 588.4초. 생성 시간 제한은 부과하지 않았다.
- 자체 테스트 11개 통과, Agent의 실제 Mock 정상 실행 1회 완료. 자체 수정은 같은 독립 세션 안에서 수행했다.
- 최종 제출 코드를 수정하지 않고 새로운 Mock 서버에서 실행했다. 사람의 코드 수정·추가 설명 없음.
- 제공 파일 42개 hash 변경 없음. 중간 snapshot 12개 및 submitted 원본 보존, 수집 오류 없음.
- 정상은 completed, Stop은 cancelled, 나머지는 failed. API Fail 시험의 Stop도 거부될 때와
  연결/제어권 상실 시에는 Stop 확인을 성공으로 표시하지 않았다. 가능할 때 제어권을 반환했다.
- JSON 숫자/요청 Schema, 공통 가감속 1회, 지정 축/목표/속도, 출력 이전 위치/Reached/Standstill,
  DI/AI 대기, 자동 Disable/복구/제어권 재획득 부재를 요청·Feedback trace로 확인했다.
- 생성 프로그램은 공식 client.request를 직접 사용한다. 생성 코드/입력 설정은 수정하지 않았고
  시험 도구는 제출 CLI 인수 형식에 맞춰 호출했다. 평가 기준은 생성 전에 보존했다.

| 케이스 | 결과 | 관측 | 추가 모델 토큰 |
| --- | --- | --- | ---: |
| 정상 | 통과 | Pick → 파지 → 입력 충족 → Place → 해제 → Stop/제어권 반환 | 0 |
| 입력 timeout | 통과 | 실패, Place 없음, 출력 유지·Stop | 0 |
| API Fail | 통과 | 이동 거부 후 출력/Place 없음, Stop 거부 시 미완료 표시 | 0 |
| Stop | 통과 | SIGINT handler로 cancelled, 출력 유지·Stop | 0 |
| Fault | 통과 | WKC 0 주입으로 서버 Fault, 실패·후속 단계 중단 | 0 |
| 연결 상실 | 통과 | 실패·정리 미완료, 재개/재전송 없음 | 0 |
| 제어권 상실 | 통과 | 실패·정리 미완료, 재획득 없음 | 0 |
| 응답 timeout | 통과 | 요청 결과 불명으로 실패·Stop, 파지/Place 없음 | 0 |

#### 토큰 사용량

| 집계 대상 | 입력 | 입력 중 캐시 | 출력 | 입력+출력 |
| --- | ---: | ---: | ---: | ---: |
| 독립 생성 세션 전체(자체 검토·시험 포함) | 586,552 | 522,624 | 14,855 | 601,407 |
| 독립 실행 시험 8개 합계 | 0 | 0 | 0 | 0 |

- CLI 원본은 reasoning_output_tokens 785도 별도 보고한다. 위 총합에 다시 가산하지 않았다.
- 캐시는 입력에 포함된다. 생성 비용은 8개 케이스에 중복 배분하지 않는다.
- 평가 담당 대화의 토큰은 위 독립 생성 세션 사용량에 포함되지 않는다. 금액/계정 사용률로 환산하지 않는다.
- 원본 `generation-events.jsonl`, 정리한 `token-usage.json`, 케이스별 `evaluation/*/result.json`에 기록했다.

#### 범위와 다음 단계

- 생성 코드: `.codex_output/s04-basic-r2-20260917/submitted/`의 run.py, sequence.py, settings.json,
  README.md, RESULTS.md, test_sequence.py 및 실행 기록. 시험 로그는 `evaluation/`에 보존한다.
- 이 결과는 해당 기본 시나리오 1회 관측이다. 모델 전반의 신뢰성 보장 또는 S04 완료가 아니다.
- 정식 평가 전 임의 수정 없는 최초 실행 가능 산출물 자체의 독립 합격 여부는 미평가다.
  중간 snapshot은 보존했으며 위 결과는 최종 제출물에 대한 판정이다.
- CLI에 시험용 endpoint 제한이 있어 일반 사용자 endpoint 재배포 가능성을 검증한 것은 아니다.
- Stop은 실제 키보드가 아닌 Python interrupt 주입, Fault는 실제 케이블 단절 아닌 WKC 주입이다.
- 지연 응답 시험은 timeout 후 프로그램이 종료했다. 실행 중 늦은 Success 수신 이후 경로는 별도 미검증이다.
- GUI·Teaching·실장비·Node-RED·다른 모델 및 추가 반복 회차는 수행하지 않았다.
- 사용자와 이번 결과를 확인한 뒤 다음 반복/시나리오를 결정한다. 이번 요청으로 다음 회차를 자동 시작하지 않는다.

### 2026-09-17 생성물 회수 권한 보완 및 재점검

- 회차: `s04-preflight-20260917-114100`. 새 시험 workspace 한 곳에만 현재 사용자 SID의
  `(OI)(CI)(RX)` 읽기·실행 권한을 추가했다. 기존 파일·시스템 전체 ACL·Sandbox 정책은 변경하지 않았다.
- 독립 AI의 파일 읽기·새 파일/하위 폴더 생성·Python 실행·Mock 상태 조회 성공.
  생성 파일 3개를 부모가 읽고 복사했으며 원본/복사본 byte 일치 및 AI 보고 SHA256 일치를 확인했다.
- 복사본 실행의 첫 시도는 평가 도구가 input.txt를 함께 복사하지 않아 FileNotFoundError.
  입력 파일을 보존·복사한 뒤 새 Mock에서 생성 코드 수정 없이 재실행해 exit 0/PREFLIGHT_OK 확인.
  최초 실패는 result.json, 후속 성공은 parent-recheck.json으로 각각 보존했다.
- 회수 이후에도 Mock status 정상 응답을 확인했고 각 점검 완료 후 해당 시험 서버만 종료했다.
- 결과: **평가 환경 사전 점검 통과**. 정식 시퀀스 생성 평가는 아직 시작하지 않았다.
- 코드·문서·hash·ACL·이벤트·실행 결과: `.codex_output/s04-preflight-20260917-114100/`.
  회수한 AI 코드는 해당 폴더의 `submitted/`에 보존한다.
- `.codex_output/s04_preflight.py`와 다음 평가 준비 도구 `s04_basic_prepare.py`에 동일한
  신규 workspace 권한 준비를 반영했다. 실장비·사용자 서버·Node-RED는 시험하지 않았다.

### 2026-09-17 평가 환경 사전 점검

- 회차: `s04-preflight-20260917-113641`, codex-cli 0.153.4의 새 elevated workspace-write 세션.
- 독립 세션의 입력 파일 읽기, apply_patch로 Python/Markdown/하위 폴더 파일 생성,
  Python 실행 및 별도 Mock `system/server/status` 조회 성공. 시퀀스 생성·이동 요청은 하지 않았다.
- 부모 평가 프로세스의 생성 파일 읽기/복사는 3개 모두 PermissionError로 실패했다.
  따라서 **사전 점검 미통과: 생성물 회수 경계 해결 필요**다. 정식 생성 평가는 시작하지 않았다.
- 파일 회수 실패 후에도 Mock 프로세스와 status 응답이 정상임을 확인했다.
  독립 세션 종료 및 회수 점검을 마친 뒤 시험용 Mock만 명시적으로 정리했다.
- 원본 코드와 문서는 `C:/Users/Festo/AppData/Local/Temp/s04-preflight-vdan70hk/generated/`에 보존한다.
  부모 프로세스에서 복사하지 못했으므로 정상 회수된 것으로 표시하지 않는다.
- 프롬프트·이벤트·독립 세션 결과·파일 hash·부모 측 판정·서버 로그는
  `.codex_output/s04-preflight-20260917-113641/`에 보존했다. 시험 도구는 `.codex_output/s04_preflight.py`다.
- ACL 변경, sandbox 완화, 설치, 실장비/사용자 서버 접근 및 Node-RED 시험은 수행하지 않았다.
- 권한 설정은 [공식 Windows sandbox 문서](https://learn.chatgpt.com/docs/windows/windows-sandbox)를
  확인했으며 이번 판정은 설명상의 추정이 아닌 실제 독립 세션·부모 프로세스 시험 결과다.

평가 시점별 기준 commit, 결과와 제약을 보존한다. 현재 정식 유효 평가 집계는 1/24(r2)이며,
r1c 생성물의 별도 실행 시험 8/8 통과와 구분한다. 아래 0/24 표기는 당시 이력이다.
과거 Node-RED 결과는 이력이며 신규 시험을 허용하지 않는다.

<a id="s04-validation"></a>

### 통합·패키지 및 GUI 검증

상태: **in_progress**. 공식 레퍼런스 통합/패키지 시험과 독립 AI 생성 평가는 별개다.
독립 AI 평가는 아직 0/24회이며 S04 전체 완료가 아니다.

최신 상태: [r1c 생성물 별도 실행 시험](#s04-basic-r1c) 8/8 통과.
생성 중 평가 도구 오류가 있어 정식 무보조 합격 집계와 구분한다. 아래 기존 시험 결과는 당시 이력이다.

#### 환경과 범위

- Windows 11 10.0.26100, Python 3.14.3, PyInstaller 6.21.0, jsonschema 4.26.0.
- 기준 HEAD: `6084863c4a7619e00dcf401c1e3f9388c91d33d4` + 미커밋 S01~S04 변경.
- `tests/test_ai_pick_place_tcp.py`는 매 시험 임시 폴더/미사용 TCP port/새 서버 프로세스를 생성한다.
  backend는 명시적으로 mock이며, 사용자 `.env`와 프로세스의 Motion Server 환경변수는 사용하지 않는다.
- 3개 linear CMMT + CPX DO/AIO/DI/AI 구성. Enable/Homing은 평가 환경 준비에서 수행하며
  레퍼런스 시퀀스가 사용자 대신 commissioning하는 기능을 추가하지 않았다.
- 패키지 시험은 EXE와 리소스를 새 임시 폴더로 복사하고 `PYTHONPATH` 없이 실행한다.
  실제 장비, 기존 15000 포트 서버, 사용자 설정에는 명령/변경을 가하지 않았다.

#### 발견 사항과 처리 이력

1. 첫 시험 환경의 `ao:4`는 기본 ESI 모듈 대응이 없어 device_layout_invalid로 실패했다.
   평가 환경을 실제 카탈로그에 있는 `aio:4:4`로 수정했다. 서버 동작을 우회하지 않았다.
2. 최초 패키지의 제어권 해제 시험에서 실제 응답의 `granted`, `message`가 응답 Schema에 없어 실패했다.
   request/release용 `authority_action` 정의로 실제 계약을 표현하고 handler 기반 회귀 시험을 추가했다.
   Feedback/authority status의 기존 구조나 서버 응답을 변경하지 않았다.
3. 패키징에 AI 문서·Schema·Python 레퍼런스 소스가 빠져 있었다. `AI Reference` 묶음을 추가했다.
   사용자 `.env`는 제외하고 상대 링크를 유지한다. 기존 Node-RED 패키지도 그대로 포함한다.
4. 기존 배포 폴더를 보존하기 위해 새 경로에만 생성 가능한 `-PackageDirectory` 검증 옵션을 추가했다.
   기본 배포 경로는 계속 `dist/Motion Server` 하나다.

#### 시험 결과

| 검사 | 결과 | 한계 |
| --- | --- | --- |
| 소스 전체 Python 회귀 | 467개 통과 | 가짜 transport/단위 시험과 실제 Mock TCP 시험 포함 |
| Node-RED 회귀 | 8개 통과 | 새 AI 생성 평가 아님 |
| 소스 실제 Mock TCP | 6개 통과 | 정상, 입력 timeout, Stop, API Fail/숫자 거부, 연결 상실, 제어권 상실 |
| Windows 서버/Axis Panel/IO Panel 빌드 | 통과 | Npcap 다운로드와 사용자 설정 복사는 생략 |
| AI bundle 링크/자료/설정 제외 | 통과 | 생성물은 Python 소스이며 별도 Python 필요 |
| 최종 EXE 독립 폴더 TCP | 6개 통과 (36.596초) | 동일 6개 시나리오, 소스 PYTHONPATH 없이 실행 |
| Tk GUI 기본 자동 시험 | 전체 회귀에 포함, 통과 | 생성, Run 취소, Jog release; 전체 수동 GUI 조작 평가 아님 |
| 독립 AI 생성 (통합 시험 당시) | 0/24, 미실행 | 이후 r1~r1c 이력은 아래 별도 회차 기록 참조 |

#### 패키지 위치와 식별

- 최초 빌드: `.codex_output/rf019-s04-20260911/Motion Server` (Schema 수정 전, 최종 배포용 아님).
- 수정 후 빌드: `.codex_output/rf019-s04-20260911-final/Motion Server`.
- 최종 서버 EXE SHA256: `F9623035BE8A6FEF390DB7612648DAD0A92AF553973F2B7EFF89836B1D6F94E7`.
- common.json SHA256: `62EC65DE9C010BDCB43E7613C3049DCDB7DE6A61E4CEF1CBF495AE3CD286C2AB`.
- system.json SHA256: `005994D14412982024BACAD7F1F17C3691559EBF90B5A59E7404DB9620398B31`.

위 hash는 이번 검사 파일 식별이며 독립 평가용 전체 자료 manifest를 대신하지 않는다.
검사 중 임시 서버 폴더/프로세스는 시험 종료 시 정리하고, 빌드 결과 폴더는 남겼다.

#### 남은 작업

- [기본 시퀀스 첫 생성 시도](#s04-basic-r1)는 독립 CLI 파일 읽기 정책 거부로
  생성 전에 종료했다. 환경 오류 1회, 유효 AI 생성 평가 0/24. 재시도 전 도구 권한 사전 점검 필요.
- GUI 화면 배치/실제 마우스·키보드 조작의 수동 확인은 미실행이다. 아래 자동 확장 시험과 구분한다.
- 독립 평가 실행 환경/모델/예산/자료 manifest 확정 및 평가 대상과 서버·시험 도구 격리.
- 신규 세션 2모델 × 4시나리오 × 3회 생성 및 독립 실행 판정. 최초/최종/보조/환경 실패 구분.
- 결과에 따른 자료 보완과 새 세션 재검증, 검증된 모델 목록 작성 후 S04 완료 판단.

#### 2026-09-11 GUI·장애 처리 자동 확장 시험

- 별도 임시 설정·TCP 포트의 소스 Mock 서버에서 실행했다. 사용자 설정/실장비/사용자 서버는 변경하지 않았다.
- Tk 창을 생성하고 숨긴 상태에서 실제 이벤트 루프와 Panel 조작 handler를 실행했다.
  화면 배치/OS 포커스 전달의 수동 검증이나 실제 마우스 클릭 시험을 대신하지 않는다.
- `tests/test_ai_pick_place_extended.py`: 새 7개 시험 통과.
  - Teaching Capture → Apply(메모리만 변경) → 명시적 Save → 파일 재읽기.
    실행 이후 원본 포인트 변경과 중복 Run에도 시작 시 고정한 좌표로 1회만 완료.
  - Jog release/포커스 이탈 handler 후 jog_stop 요청과 실제 Mock Standstill 확인.
  - 입력 대기 중 창 종료: UI 이벤트 응답, axes Stop → authority release → 연결 종료/창 파괴,
    후속 Place 없음, 자동 Disable 없음.
  - Teaching Move to point 완료 후 Run에서 시퀀스 공통 가감속을 다시 적용.
  - 시험 launcher에서 WKC 관측값을 0으로 주입: 기존 서버 진단 경로가 실제 Fault를 생성하고,
    시퀀스는 실패·후속 이동 중단, 서버는 살아 있고 status 요청에도 응답.
    실제 케이블 단절/드라이브 자체 Fault 시험은 아니다.
  - 시험 TCP proxy가 이동 응답만 1.5초 지연하고 Feedback은 계속 전달. 요청 timeout 0.5초 이후
    실패·Stop·Standstill 확인, 늦은 Success 이후 자동 재전송/Place/출력/재개 없음.
  - 같은 지연 중 GUI Stop 클릭 handler 및 예약 UI 이벤트 처리 확인. 실패 표시와 후속 동작 중단.
- `tests/sequence_tcp_proxy.py`와 기존 TCP 시험 launcher만 확장했다. 제품 서버/API/레퍼런스 실행
  코드는 이번 시험에서 수정하지 않았다. 패키지도 이번에는 다시 빌드하지 않았다.
- 최종 관련 회귀: `tests.test_ai_pick_place_extended`, `tests.test_ai_pick_place`,
  `tests.test_ai_pick_place_tcp`, `tests.test_api_schema`, `tests.test_ai_documentation`,
  `tests.test_ai_reference_bundle` **47개 통과, 48.347초**. Node-RED 관련 시험은 실행하지 않았다.

##### 시험 중 발견 및 해석

- 초기 지연 4초는 Sequence가 지정하는 요청 timeout 5초보다 짧아 정상 완료됐다.
  timeout 초과 시험의 설정 오류이므로 1.5초/0.5초로 수정하고 재검증했다. 제품 결함으로 집계하지 않는다.
- 초기 Tk 시험 종료가 예약 callback보다 빨라 Tcl 경고가 발생했다. 시험이 실제 창 파괴까지 기다리고
  잔여 예약을 정리하도록 수정했다. 최종 회귀에서는 해당 경고 없음.
- GUI는 API 응답을 기다리는 동안에도 반응하지만, Stop 전송은 진행 중 요청의 응답/timeout 이후다.
  GUI Stop은 즉시 실행되는 하드웨어 비상정지 기능이 아니다. 이를 숨기거나 응답 전 중단했다고 표시하지 않는다.
- 독립 AI 생성 평가는 여전히 **0/24**이며 S04 전체 완료로 처리하지 않는다.

<a id="s04-basic-r1"></a>

### 기본 Pick & Place r1·r1b

- 기준 commit: `dd0b3706a5e51bf44ecaefcefa9fff6742c8b1e6` (`origin/main` push 확인).
- 범위: 기본 CLI Pick & Place 1회, GUI/Teaching/Node-RED 제외.
- 결과: **환경 오류, 유효 생성 평가 0회**. 모델의 구현 실패 또는 통과로 집계하지 않는다.
- 실행 도구: codex-cli 0.153.4, 새 비대화형 세션, 사용자 config 제외, workspace-write 요청.
- 정확한 실행 모델/추론 설정은 수집한 JSON 이벤트에 없어 미확인. 검증 모델 목록에 추가하지 않는다.
- 자료는 별도 임시 작업 폴더에 복사: AI 안내/가이드/프롬프트, 공식 Python client·레퍼런스,
  API Schema, configuration 정의, API 설명, statusword 정의와 별도 Mock 서버의 config.txt.
  기존 대화와 평가 코드·제품 서버 구현은 제공하지 않았다. RF 평가계획 링크는 제공 제외로 명시했다.
- 정정: 첫 시도에 적용한 생성 시간 제한 15분은 사용자와 합의한 값이 아니라 평가자가 임의로
  설정한 값이었다. 합의된 예산으로 취급하지 않는다. 후속 r1c에서는 이 제한을 제거했다.
  CLI가 보고한 사용량은 input 89,696, cached input 73,856,
  output 435 tokens다. 실제 과금 또는 계정 사용량 환산값은 아니다.
- 별도 Mock 서버는 초기화/Enable/Homing 및 DI/AI 입력 준비를 완료하고 제어권을 반환했다.
  사용자 서버·실장비·실제 설정은 변경하지 않았다.

#### 발생 경위

새 세션이 자료 확인을 시도했으나 파일 목록 조회 및 `docs/ai/README.md` 읽기 명령이
`blocked by policy`로 거부됐다. 생성 AI는 정책 제한을 보고하고 종료했다.
코드 생성/자체 시험/독립 실행 판정은 수행되지 않았다.
명령에 요청한 workspace-write와 세션이 보고한 읽기 전용/실행 거부 상태가 불일치한다.
정확한 정책 적용 원인은 이 기록만으로 확정하지 않는다. 제한 우회나 sandbox 비활성화는 하지 않았다.

#### 보존 자료와 후속 조건

- 로컬 `.codex_output/s04-basic-r1/`: 정확한 prompt, 입력 파일 SHA256 manifest,
  environment.json, generation-events.jsonl, generation-stderr.txt, generation-final.txt,
  generation-server.log. 대용량 실행 로그는 Git에 포함하지 않았다.
- 시험용 Mock 프로세스는 종료하고 생성 AI용 입력 폴더와 실행 기록은 원인 확인을 위해 보존한다.
- 재시도 전에 별도 세션에서 자료 읽기·generated 폴더 쓰기·Python 실행·지정 Mock TCP 접속의
  사전 점검이 필요하다. 제품 서버/평가 도구 수정 금지 경계와 모델 ID·추론 설정도 확인한다.
- 재시험은 이번 환경 실패와 연결된 새 회차로 기록한다. 이번 실패를 삭제하거나 생성 성공으로 대체하지 않는다.
- S04는 계속 진행 중이며 24회 독립 평가 중 유효 평가 완료는 0회다.

#### 후속 시도

- r1b: 임의 시간 제한에 대한 사용자 이의 제기로 중단. 정식 평가에서 제외하고 기록은 보존했다.
- r1c: 제한 없이 생성 완료. 시험 도구의 파일 수집 오류로 자체 Mock 실행 환경이 중단됐다.
  생성 코드를 수정하지 않은 별도 실행 시험 8개는 통과했다. 환경 오류와 생성물 검증을 구분한
  [r1c 상세 기록](#s04-basic-r1c)을 따른다. 정식 무보조 합격으로 집계하지 않는다.

<a id="s04-basic-r1c"></a>

### 기본 Pick & Place r1c

#### 결과와 집계

- 기준 commit: `da0b0a3ae727ca9586bc27b6942c95fd88e670a7`.
- 기본 CLI Pick & Place 생성 완료. 생성 코드 수정 없이 별도 Mock TCP 실행 시험 **8/8 통과**.
- 생성 중 평가 도구 오류로 Mock 서버가 종료되어 Agent의 실제 서버 자체 시험이 실패했다.
  따라서 **환경 오류가 포함된 시도 / 생성물 실행 검증 완료**로 기록한다.
  정식 무보조 합격 또는 24회 평가 완료 수에는 더하지 않는다. S04는 계속 in_progress다.
- r1의 권한 실패, r1b의 임의 예산 적용·중단 기록을 삭제하거나 이번 성공으로 대체하지 않는다.

#### 생성 환경

- codex-cli 0.153.4, 신규 세션 `01a08f6b-1ef2-78d1-a5f1-efcadc65418b`.
- 모델: rollout의 `gpt-6-astra`. 추론 설정은 명시하지 않았고 기록의 effort는 null이므로 특정 수준으로 단정하지 않는다.
- Windows, Python 3.14.3. elevated workspace-write 및 지정 Python 읽기 권한 확인 후 실행.
- 기존 대화 없이 AI 문서/프롬프트, 공식 Python client와 레퍼런스, API Schema,
  설정 정의 및 시험 config.txt를 제공했다. 서버 구현과 독립 평가 코드는 제공하지 않았다.
- 별도 Mock의 3개 linear 축과 CPX DO/AIO/DI/AI. 초기 Enable/Homing은 평가자가 준비했다.
- 생성 시간/토큰 제한을 별도로 부과하지 않았다. 기존 900초 제한과 15분 지시를 제거했다.
  실행 중 요청·단계 timeout은 프로그램 동작 요구사항이며 생성 시간 제한과 다르다.
- 생성 CLI exit 0, 관측 시간 약 510.5초. CLI 사용량은 input 564,052,
  cached input 512,896, output 13,608 tokens. 과금액이나 계정 잔여 사용량으로 환산하지 않는다.

#### 환경 오류와 산출물 보존

1. Agent는 실제 axis metadata 조회에 성공했다. 자체 테스트 중 오류를 스스로 수정하고 8개 통과를 기록했다.
2. elevated sandbox가 생성한 파일을 부모 평가 프로세스가 읽지 못해 PermissionError가 발생했다.
   중간 산출물 수집기가 이 예외로 종료하면서 finally에서 Mock 서버까지 종료했다.
   Motion Server 자체 오류로 다운된 것이 아니라 평가 도구의 정리 절차가 종료한 것이다.
   사용자는 이를 서버 결함으로 보지 않기로 확인했다. 자체 실행 시험보다 먼저 종료되어 생긴
   연결 timeout은 평가 환경 이력으로 남긴다.
3. Agent의 이후 CLI 실행은 연결 timeout으로 종료했다. 자동 복구·재실행하지 않고 실패를 보고했다.
4. 최종 파일 복사도 같은 권한 문제로 실패했다. 생성 CLI 성공과 수집기 실패를 구분한다.
5. 이미 수집된 Agent의 apply_patch 기록을 순서대로 재적용하여 별도 폴더에 산출물을 복원했다.
   출력 경로만 변경했고 코드 수정은 하지 않았다. 원본 파일을 직접 hash 대조하지 못했으므로
   byte 단위 원본 동일성까지 확인했다고 표현하지 않는다. ACL 변경/권한 우회는 하지 않았다.

로컬 증거: `.codex_output/s04-basic-r1c/`의 prompt, manifest, environment,
generation-events, generation-final, invocation, `replayed/generated/`와 `evaluation/<case>/`.
각 시험에는 요청/Feedback trace, stdout/stderr, 최종 상태, 서버 로그와 판정 결과를 보존했다.
대용량 로그와 생성물은 Git에 포함하지 않는다.

#### 독립 실행 시험

시험마다 새 Mock 서버를 준비하고 원본 생성 Python 코드는 수정하지 않았다.
생성 코드가 시험 endpoint를 고정 검증하므로 proxy가 해당 port를 받아 새 Mock로 전달했다.
실장비/사용자 서버/설정/Node-RED는 사용하거나 변경하지 않았다.

| 시험 | 결과 | 관측 |
| --- | --- | --- |
| 정상 | 통과 | Pick → DO/AO 파지 → DI/AI 충족 대기 → Place → 해제 → Stop/제어권 반환 |
| 입력 timeout | 통과 | 실패 종료, Place 없음, 출력 유지, Stop/제어권 반환 |
| 이동 API Fail | 통과 | 비활성 축으로 Fail 유발, 후속 출력/Place 없음. Stop도 Fail일 때 정리 미완료 기록 |
| Stop | 통과 | 입력 대기 중 SIGINT handler 실행, cancelled, 출력 유지, Stop/제어권 반환 |
| Fault | 통과 | 시험용 WKC 0 주입으로 기존 서버 진단 경로의 Fault 발생, 실패·후속 단계 중단 |
| 연결 상실 | 통과 | TCP proxy 연결 종료, 실패 및 정리 미완료 표시, 재전송/재개/제어권 재요청 없음 |
| 제어권 상실 | 통과 | 시험 wrapper가 동일 client로 제어권 반환, 상실 감지·실패, 재획득 없음 |
| 응답 timeout | 통과 | 이동 응답을 요청 timeout보다 늦게 지연, 실패·Stop·제어권 반환, 파지/Place 없음 |

공통 검사: JSON 요청 Schema, 축/좌표/속도, 공통 가감속 1회 적용,
출력 전 actual position/target reached/standstill, 자동 Enable/Homing/Disable/복구 부재.
정지가 확인되지 않은 경우 성공으로 표시하지 않는지 생성 실행 기록도 확인했다.

#### 한계와 후속

- 위 8개는 1개 생성물의 시험 케이스이지 8회 독립 생성 성공이 아니다.
- GUI/Teaching/실제 키보드 조작·물리 Fault는 미시험. Stop은 Python interrupt 주입이다.
- 응답 timeout 시험에서는 프로그램이 지연 응답 전달 전에 종료했다.
  늦은 Success를 살아 있는 프로그램이 수신한 이후의 처리는 이 시험만으로 검증하지 않았다.
- 코드 검토상 시험 endpoint가 하드코딩되어 다른 endpoint 재사용에는 제약이 있다.
  허용 endpoint만 사용하라는 시험 지시의 영향이며, 일반 배포 구성 가능성 통과로 확대하지 않는다.
- 다음 정식 재시험 전에 새 세션의 생성 파일 회수와 자체 시험 종료·서버 정리 순서를 확인한다.
  서버 수명 분리 설계 변경은 이번 문서 통합의 범위에 포함하지 않는다.
- 이번에는 제품 코드/AI 제공 문서/생성 코드 보완이나 다음 독립 회차를 추가 수행하지 않았다.

### 평가 산출물 보관

- 평가 중 AI가 작성한 코드는 회차별로 저장한다. 최초 산출물·최종 제출물·설정·실행 안내·자체 테스트를 보존한다.
- 프롬프트, 모델 정보, 입력 자료 manifest, 평가 결과와 로그를 함께 보관한다.
- 실패·중단 회차도 덮어쓰거나 삭제하지 않는다. 문서 통합은 생성 코드와 원본 로그를 삭제하지 않는다.
- 현재 r1c 복원 코드 위치: `.codex_output/s04-basic-r1c/replayed/generated/`.

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
