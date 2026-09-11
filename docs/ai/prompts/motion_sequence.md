# Motion 시퀀스 생성 프롬프트

아래 블록을 AI에게 제공한다. 사용자 수정 영역을 채우고 [AI 안내](../README.md), [설정 해석](../configuration.md), [시퀀스 가이드](../sequence_guide.md), Schema, Python client, 실제 설정 파일을 함께 제공한다. 숫자는 예시이며 실장비 적용 전에 사용자 확인이 필요하다.

```text
정상 기동된 Motion Server를 사용하는 Python Motion 시퀀스 프로그램을 만들어 줘.
먼저 docs/ai/README.md, configuration.md, sequence_guide.md와 실제 API Schema,
공식 Python client를 읽어. 서버/장치 설정은 수정하지 마.

[사용자 수정 영역]
- 서버: 127.0.0.1:15000
- 실제 설정 파일: 내가 첨부/지정한 .env 또는 config.txt 묶음
- 역할: X=axis 0, Y=axis 1 (실제 구성과 단위 확인 필요)
- 순서: X를 10.0 위치로 속도 5.0 이동하고 완료 대기.
  다음 X/Y를 각각 20.0/30.0 위치로 속도 5.0/5.0 이동하고 모두 완료 대기.
- 가감속: 각 축 공통 acceleration=100.0, deceleration=100.0,
  시작 시 1회 적용. 단계별 변경 금지.
- 위치/속도 허용치: 가이드 기본값 사용.
- 요청 timeout 5초, 단계 timeout 30초, Feedback timeout 2초.
- 정상: Stop/정지 확인 후 완료. 중단/실패: 사용한 축 Stop, 자동 Disable 없음.
- Teaching: 아니오 (예로 변경하면 이름별 포인트·명시적 저장을 추가).
- GUI: 아니오 (예로 변경하면 sequence_gui.md도 적용).
- 실행 허가: 코드/자동 테스트 작성만. 실장비 실행은 별도 요청.

[구현 요구]
역할·단위·축 수를 설정과 metadata에서 확인하고 부족한 정보는 질문해.
기존 client.request로 API를 직접 조합하고 명령별 wrapper를 새로 만들지 마.
공통 가감속은 profile API, 이동별 속도는 move_abs의 profile_velocities를 사용해.
Success와 가이드의 완료 대기를 구분하고 모든 축의 조건을 확인해.
Homing/Enable/Fault/limit 사전 인터락은 서버에 맡겨. API Fail이면 중단하고 표시해.
Ctrl+C/Stop, timeout, 실행 중 Fault, 연결·제어권 상실 시 다음 단계로 진행하지 마.
자동 재전송·재개·Disable 없이 가이드 cleanup을 적용해.
CLI는 1회 실행 후 제어권 해제/종료. Teaching을 선택한 경우 가이드 전체 계약을 적용해.
실행 파일, 설치/사용 안내, 설정 항목, 테스트와 실제 수행 결과를 제공해.
시험하지 않은 실장비 동작을 검증 완료라고 쓰지 마.
```
