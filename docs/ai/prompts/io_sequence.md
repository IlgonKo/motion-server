# I/O 시퀀스 생성 프롬프트

[AI 안내](../README.md)와 연결 자료를 함께 제공한다. 아래 slot/channel/raw 값은 설명용이므로 실제 구성에 맞춰 수정한다.

```text
정상 기동된 Motion Server를 사용하는 Python I/O 시퀀스 프로그램을 만들어 줘.
docs/ai/README.md, configuration.md, sequence_guide.md, API Schema와 공식
Python client를 먼저 읽어. 서버 설정/배선/장치 commissioning은 내 책임이며 수정하지 마.

[사용자 수정 영역]
- 서버: 127.0.0.1:15000
- 설정: 내가 첨부/지정한 실제 .env 또는 config.txt 묶음
- 출력: io0 slot 1 digital channel 0=true,
  io0 slot 2 analog channel 0=100 (PDO raw 정수).
- 입력: io0 slot 3 digital channel 0=true AND
  io0 slot 4 analog channel 0>=50 (PDO raw 정수), 모두 만족할 때 전환.
- 순서: 위 출력 적용 → 입력 조건 대기 → DO=false, AO=0 → 완료.
- 요청 timeout 5초, 입력 timeout 10초, Feedback timeout 2초.
- 중단/실패 cleanup: 위 DO=false, AO=0. 그 외 출력은 유지.
- GUI: 아니오 (예로 변경하면 sequence_gui.md 함께 적용).
- 실장비 실행: 허가하지 않음. 코드와 자동 테스트 작성만.

[구현 요구]
io ID/slot/kind/channel이 실제 구성에 존재하는지 읽어서 확인해.
없는 모듈은 만들거나 서버 설정을 변경하지 말고 내게 확인해.
API를 직접 조합해. output_write Success는 실제 외부 동작 완료가 아니야.
입력은 기존 Feedback 또는 input_read 응답의 모듈별 입력에서 확인해.
복수 조건은 같은 유효 snapshot에서 평가하고 오래된/invalid 자료는 사용하지 마.
API Fail, 조건/Feedback timeout, Stop, 연결·제어권 상실이면 이후 단계는 중단해.
연결/제어권이 없으면 cleanup 미전송을 표시하고 자동 재전송하지 마.
권한은 명시적으로 요청/해제하고 CLI는 1회 실행 후 종료해.
GUI가 있으면 같은 실행 코드를 써. 별도 API wrapper나 서버 인터락은 만들지 마.
설치/실행 방법, 사용자 설정, 정상/실패/중단 테스트와 실제 결과를 제공해.
```
