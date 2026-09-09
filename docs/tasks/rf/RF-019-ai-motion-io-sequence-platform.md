# RF-019 AI 기반 Motion/I/O 시퀀스 생성 플랫폼

- 등록일: 2026-09-09
- 상태: `planned`
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

설명 문서와 기계 판독 계약이 서로 다른 사실을 갖지 않도록 가능한 한 코드의 API specification 및
schema를 단일 원본으로 사용한다. 구체적인 파일 형식과 생성 방법은 구현 전에 확정한다.

### Runtime 시스템 정보

AI가 존재하지 않는 축이나 I/O를 추측하지 않도록 현재 설정과 장치에서 다음 정보를 확인할 수 있어야
한다.

- Axis 개수, 이름, index와 역할
- Linear/Rotary 구분과 position/velocity 단위
- Motion limit와 Software position limit
- I/O station, AP module, DI/DO/AI/AO/IO-Link channel 구성
- 장치별 지원 기능과 현재 사용 가능 조건
- 현재 Server/Bus/Axis/I/O/Diagnostic 상태

Runtime 정보는 `mock`/`pysoem` 같은 내부 구현 종류보다 현재 구성에서 사용할 수 있는 기능과 제약을
중심으로 표현한다. 기존 API를 조합할지 별도의 system model/capability snapshot을 제공할지는 구현
전에 결정한다.

## AI 시퀀스 생성 규칙

- 동시에 움직여야 하는 축은 가능한 경우 기존 다축 API를 사용한다.
- command 응답과 실제 동작 완료를 구분하고, 실제 완료는 Feedback으로 판정한다.
- 입력 대기와 동작 완료 대기에는 유한한 timeout을 둔다.
- Fault, command authority 상실 또는 연결 단절 시 후속 단계로 진행하지 않는다.
- 연결이 복구되어도 이전 motion command를 자동 재전송하지 않는다.
- Stop 요청은 진행 중인 motion과 대기 조건을 함께 중단한다.
- 종료, 사용자 중단과 예외 발생 모두에서 `finally` 안전 정리를 수행한다.
- AI는 Expert Mode나 safety bypass를 자동으로 활성화하지 않는다.
- 안전 제한의 최종 집행은 AI 코드가 아니라 기존 Motion Server가 담당한다.

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
├─ motion_server_client/   # 연결, request/response, Feedback, authority
└─ examples/               # 대표 AI 생성 및 사용자 수정 예제
```

정확한 package 구조와 기존 RF-002 reference client 재사용 경계는 구현 계획 수립 시 현재 코드를
검토하여 확정한다.

## 생성 프로그램의 공통 구조

```text
서버 연결
→ 시스템 구성 및 요구사항 preflight
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
    "velocities": [50.0, 20.0],
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

## 미결정 사항

- 기존 Python client에 추가할 Feedback 대기, timeout과 cancellation의 최소 범위
- 정적 AI 지식 패키지의 파일 구조와 schema 단일 원본
- 현재 시스템 model/capability를 기존 API로 조합할지 별도 snapshot API로 제공할지
- 사용자 Stop 입력 방식과 생성 프로그램의 실행/상태 표시 방법
- 예제 프롬프트의 대표 산업 시나리오와 난이도 단계

## 완료 조건

- 사용자 수정형 예제 프롬프트의 공통 형식과 대표 시나리오가 제공된다.
- AI용 정적 플랫폼 지식이 개념, API 계약, 시퀀스 규칙과 Failure/recovery를 포함한다.
- 현재 시스템 구성과 지원 기능을 확인하는 runtime 정보 경계가 확정된다.
- Motion Server API가 시퀀스 구성 block의 단일 계약으로 유지되고, AI 생성 코드와 예제가 기존
  Python client를 통해 API request를 직접 조합한다.
- 대표 예제에서 반복이 확인된 Feedback 대기, timeout과 cancellation만 기존 Python client 또는
  비도메인 utility로 최소 공통화한다.
- AI가 생성하는 Python 프로그램의 preflight, authority, timeout, Feedback 완료 판정, Stop/Fault 처리와
  안전 정리 구조가 일관된다.
- 단일축, 다축 동시 이동, I/O handshake와 Motion/I/O 복합 시퀀스 예제가 제공된다.
- 대표 생성 결과가 Mock에서 정상 완료, timeout, Stop과 Fault 시나리오를 자동 검증한다.
- Node-RED는 Python 패턴 안정화 이후의 후속 출력 형식으로 명시된다.
