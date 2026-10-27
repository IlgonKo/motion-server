# X/Y/Z Pick & Place 생성 프롬프트

[AI 안내](../README.md)와 연결 자료를 함께 제공한다. 역할·좌표·채널은 사용자가 바꾸는 예시이며 충돌 없는 이동 경로를 보장하지 않는다. 필요한 안전 높이/중간 이동점은 사용자가 지정한다.

```text
정상 기동된 Motion Server를 사용해 X/Y/Z Pick & Place를 1회 수행하는
Python 시퀀스 프로그램을 만들어 줘. docs/ai/README.md, configuration.md,
sequence_guide.md, API Schema, 공식 Python client를 먼저 읽어.
서버/하드웨어 정상 구동은 내가 담당한다. 설정 수정이나 자동 복구는 하지 마.

[사용자 수정 영역]
- 서버: 127.0.0.1:15000
- 실제 .env/config.txt: 첨부/지정된 파일 사용
- 역할: X=axis 0, Y=axis 1, Z=axis 2. 위치 단위는 실제 축 metadata 확인.
- Pick: X=10.0, Y=20.0, Z=5.0; 속도 X/Y/Z=5.0/5.0/2.0.
- Place: X=30.0, Y=40.0, Z=5.0; 속도 X/Y/Z=5.0/5.0/2.0.
- 중간 이동점: 미지정. 실제 적용 전 내가 이동 경로를 확인한다.
- 시퀀스 공통 가감속: 각 축 acceleration=100.0, deceleration=100.0.
- 파지: io0 slot 1 digital channel 0=true;
  io0 slot 2 analog channel 0=100 (raw 정수).
- 파지 확인: io0 slot 3 digital channel 0=true AND
  io0 slot 4 analog channel 0>=50 (raw 정수).
- 해제: 위 DO=false, AO=0.
- 해제 확인: 사용 안 함 (선택 시 DI/AI 조건을 여기에 지정).
- 허용치: 가이드 기본값. 요청 timeout 5초, 이동 timeout 30초,
  입력 timeout 10초, Feedback timeout 2초.
- 정상 종료: 사용 축 Stop/정지 확인, 해제 출력 유지, 완료.
- 중단/실패: 사용 축 Stop. I/O는 현재 출력 유지
  (부하 낙하 등 위험이 있어 해제를 자동으로 가정하지 말 것).
- Teaching: 아니오 (예로 변경 시 Pick/Place 명명 포인트 저장/호출).
- GUI: 아니오 (예로 변경 시 sequence_gui.md 추가 적용).
- 실장비 실행: 별도 요청 전 금지.

[정확한 순서]
1. 연결과 제어권 획득 후 공통 가감속 1회 적용.
2. Pick으로 세 축 이동, 모든 축 위치 근접 AND Target reached AND Standstill 대기.
3. 파지 DO/AO 설정, 각 요청 Success 확인.
4. 파지 DI/AI 조건 모두 충족 대기.
5. Place로 세 축 이동, 모든 축 완료 대기.
6. 해제 DO/AO 설정. 선택한 경우 해제 입력 조건 대기.
7. 지정한 정상 종료 상태로 정리한 뒤 완료 처리.

[구현 요구]
공식 client.request로 기존 API를 직접 써. 이동 속도는 profile_velocities,
가감속은 공통 설정으로만 적용해. 새 Sequence Helper/API wrapper를 만들지 마.
API Success와 동작 완료 대기를 구분하고 가이드의 자료 신선도 규칙을 지켜.
Homing/Enable/Fault/limit 사전 인터락은 복제하지 말고 서버 Fail을 표시하고 중단해.
Stop/Ctrl+C, timeout, 실행 중 Fault, 연결·제어권 상실 시 추가 단계 금지.
자동 Disable/재전송/재개/제어권 재획득 금지. cleanup 불가 시 미완료를 명시해.
Teaching 선택 시 동일 snapshot 캡처, 명시적 저장, Run snapshot 고정,
실행 중 편집/수동 이동 금지 등 가이드 계약을 적용해.
CLI는 1회 실행 후 해제/종료하며 GUI를 선택하면 동일 시퀀스 코드를 공유해.
사용자 수정이 쉬운 파일 구조, 사용 안내, 테스트와 실제 수행 결과를 제공해.
확인 못 한 장치/단위/경로는 추측하지 말고 표시해.
```
