# Motion Server AI 작성 안내

이 문서 묶음은 Motion Server 사전 지식이 없는 AI가 사용자 요구에 맞는 **Python Motion/I/O 시퀀스 프로그램**을 작성하기 위한 입력이다. 특정 AI 제품이나 모델에 종속되지 않는다. API를 다시 감싸는 Sequence Helper/framework를 만드는 작업이 아니다.

## 먼저 확인할 책임 경계

- 사용자는 하드웨어 설치·배선·commissioning, 서버 설치, `config.txt` / `.env` 설정과 정상 기동을 완료한다.
- AI는 제공된 설정을 **읽기만** 하고, 정상 기동된 서버의 기존 API로 시퀀스 프로그램을 만든다.
- 서버가 준비되지 않았거나 설정/축/채널 정보가 부족하면 사용자에게 알려 해결을 요청한다. 설정 수정, 자동 Homing·복구·Expert Mode 활성화로 해결하지 않는다.
- 실장비 실행은 별도 명시적 요청이 있을 때만 한다. 코드 생성 요청을 실장비 구동 허가로 해석하지 않는다. 소프트웨어 Stop은 비상정지나 하드웨어 안전 기능의 대체물이 아니다.

## 읽는 순서와 단일 원본

1. 이 문서와 [설정 해석](configuration.md): 사용자 제공 파일에서 장치와 역할 매핑을 확인한다.
2. [시퀀스 작성 가이드](sequence_guide.md): 완료 대기, 실패·중단, 단위와 Teaching 계약을 읽는다.
3. [API Schema 디렉터리](../../motion_server/api/schema): `common.json` 및 사용할 namespace 파일의 요청·응답·Feedback 정의와 `x-motion-server` metadata를 읽는다. `axis.json`은 axis/axes, `io.json`은 IO/AP/IO-Link를 함께 다룬다.
4. [공식 Python client 안내](../../reference_clients/python/README.md)와 [client 구현](../../reference_clients/python/motion_server_reference_client/client.py): 설치와 실제 사용 가능한 메서드를 확인한다.
5. 아래에서 하나의 시퀀스 프롬프트를 고르고 사용자 수정 영역을 채운다. GUI가 필요하면 GUI 프롬프트를 **함께** 제공한다.

| 목적 | 프롬프트 |
| --- | --- |
| 축 이동 | [Motion](prompts/motion_sequence.md) |
| 출력과 입력 조건 대기 | [I/O](prompts/io_sequence.md) |
| X/Y/Z Pick & Place | [Motion + I/O](prompts/motion_io_sequence.md) |
| 같은 시퀀스에 Run/Stop/모니터링 GUI 추가 | [GUI](prompts/sequence_gui.md) |

AI에게 이 README만 전달하지 말고 **연결된 문서·Schema·Python client와 사용자 설정 파일에 접근할 수 있게 제공**한다. 파일 접근이 불가능하면 필요한 파일을 요청한다. 모델의 기억으로 API를 추측하지 않는다. 실행 중 환경변수/CLI override가 있으면 사용자에게 별도로 제공받는다.

## 구현 원칙

- `MotionServerClient.request({...})`로 기존 API를 직접 사용한다. 명령마다 `move_axes_abs()` 같은 새 wrapper를 만들지 않는다. 실제 반복이 확인된 일반 대기·취소 코드만 최소한으로 공유한다.
- API 구조의 원본은 Schema다. 설명과 Schema가 다르면 불일치를 보고한다. API에 없는 명령이나 필드, 서버 completion tracker를 추가하지 않는다.
- 숫자 필드는 JSON 숫자다. `"1"`, `"0x6081"`, Boolean을 숫자 대용으로 보내지 않는다. hex 표현이 필요한 숫자는 Python에서 정수로 변환한다. 문자열/Boolean/raw payload 필드는 해당 타입을 유지한다. 이전 입력 형식 fallback은 만들지 않는다.
- 요청은 서버 validator가 검증한다. 응답/Feedback은 정의를 따라 소비하며 새 runtime Schema 검증 계층은 만들지 않는다. 계약 검증은 테스트에서 한다.
- Homing/Enable/Fault/limit의 Run 사전 인터락은 API에 맡긴다. 프로그램은 Fail을 표시하고 이후 단계를 중단한다. 프로그램 자체의 잘못된 입력·없는 포인트·중복 Run은 검사한다.
- [AI 레퍼런스 프로그램](../../reference_clients/python/examples/pick_place/README.md)은 S03 산출물이다. API 직접 조합과 CLI/GUI/Teaching 구현을 참고하되 사용자 설정에 맞게 작성한다. 문서나 공식 레퍼런스가 독립 AI 생성 품질 검증 결과를 대신하지 않는다. 평가 계획은 [RF-019](../tasks/rf/RF-019-ai-motion-io-sequence-platform.md)에 있다.

## 인계 시 반드시 제시할 것

생성 파일, 설치/실행 방법, 사용한 API, 설정에서 확인한 역할/단위/채널, 실행하지 않은 시험과 남은 사용자 확인 사항을 제시한다. 정상 완료 외에 API Fail, 응답/조건 timeout, Stop, 연결·제어권 상실을 테스트한다. Mock 시험과 실장비 시험을 구분하고 실제 실행하지 않은 시험을 통과했다고 쓰지 않는다.
