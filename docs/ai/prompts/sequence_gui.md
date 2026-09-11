# 시퀀스 GUI 추가 프롬프트

독립 시퀀스 요구가 아니라 [Motion](motion_sequence.md), [I/O](io_sequence.md), [Pick & Place](motion_io_sequence.md) 중 선택한 프롬프트에 추가한다. Teaching 선택은 원래 시퀀스 프롬프트가 결정한다.

```text
앞서 지정한 Python 시퀀스에 Tkinter/ttk GUI를 함께 만들어 줘.
docs/ai/README.md와 sequence_guide.md를 따르고 CLI와 동일한 시퀀스 실행 코드를 써.

- Host/Port 입력, 연결/해제, 제어권 요청/해제 버튼.
- 실제 연결과 제어권 상태, 서버 상태, Run/Stop, 현재 단계/설명, 로그 표시.
- idle/running/stopping/completed/cancelled/failed 상태를 구분.
- 통신/대기는 worker에서 수행. Tkinter 위젯 갱신은 GUI thread에서 수행.
- Feedback은 한 소비자가 latest snapshot으로 공유하고 GUI와 실행기가 경쟁해 읽지 않도록.
- 중복 Run 금지. Homing/Enable/Fault/limit 사전 인터락은 추가하지 마.
- Stop은 취소 신호를 보내고 bounded cleanup 결과를 표시. GUI를 멈추거나
  강제로 thread를 죽여 전송된 명령이 취소되었다고 취급하지 마.
- 실행 중 창 닫기는 취소/cleanup 후 제어권 해제와 연결 종료.
- Run 종료 후 GUI는 제어권 유지. 연결 상실 후 자동 Run/제어권 재획득은 금지.
- Teaching이 선택되어 있으면 포인트 선택/캡처/추가/편집/삭제/명시적 저장,
  선택 축 Enable/Disable/Fault Reset/Homing, +/- hold Jog Slow/Fast,
  포인트 이동과 전용 이동 설정을 추가해. 미선택이면 추가하지 마.
- Jog release/포인터 이탈/포커스 상실 시 jog_stop. 실행 중 Teaching 편집/수동 이동 금지.
- 설정/포인트 누락은 표시하고 Run을 막되 서버의 운전 인터락을 재구현하지 마.
- 상태/통신 실패와 cleanup 미완료를 숨기지 마. 자동 Disable하지 마.
- GUI Stop/종료/포커스 상실 테스트와 실행 방법을 제공하고 수행하지 않은 시험을 명시해.
```
