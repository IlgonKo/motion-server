# 실제 수행 결과

시험일: 2026-09-17. 허용된 `127.0.0.1:52728` Mock과 지정 Python 3.14만 사용했습니다. 실장비, 외부 검색, 평가 도구/서버 구현은 사용하지 않았습니다. 모든 산출물은 generated 아래입니다.

| 시험 | 결과 / 증거 |
| --- | --- |
| 서버/metadata 조회 | 성공. 세 축 위치 mm, 속도 mm/s, 가감속 mm/s². `probe.json` |
| CLI 1회 | completed → Stop/Standstill 확인 → authority release. `cli_result.txt` |
| 시퀀스 client double | 9 tests PASS, 내부 실패모드 11개 포함. `unit_result.txt` |
| 실제 Tk GUI 시작 시도 | 실패: usable init.tcl 없음. 실제 창 조작 시험은 미수행. `gui_result.txt` |
| 창 없는 GUI + 실제 Mock, 정상 Run | completed. 최종 위치 약 100/110/120, DO=false/AO=0, 정지 확인. `gui_headless_result.json` |
| 창 없는 GUI + 실제 Mock, Place 중 Stop | cancelled. Stop 확인, DO=true/AO=100 유지, Run 직후 제어권 유지, 창 종료 후 해제 |
| 창 없는 GUI + 실제 Mock, Place 중 창 닫기 콜백 | cancelled → Stop 확인 → 제어권 해제/연결 종료. DO=true/AO=100 유지 |
| 창 없는 GUI 중복 Run/포커스 콜백 | 중복 실행 차단, 포커스 변화 시 불필요한 Jog/Stop 없음, event loop 진행 확인 |
| 창 없는 GUI 실패/종료 client double | 2 tests PASS, cleanup Fail/연결·제어권 상실/요청 timeout subtests와 설정 누락. `gui_failure_result.txt` |

시퀀스 자체 시험은 정상 명령 순서 및 Schema의 required/허용 필드 대조, Fail, 요청 timeout(재전송 없음), 이동/입력 timeout, Feedback 중단/invalid/과거 snapshot/누락 축, 세 축 중 하나 미완료, 실행 중 Fault, 연결/제어권 상실, 파지 후 취소 출력 유지, 요청 중 취소(전송 취소로 오인하지 않음), 중복/재개 차단, 설정 snapshot 고정을 포함합니다. 전체 JSON Schema validator를 런타임에 도입하지 않았습니다.

실제 GUI 자동 시험 스크립트는 생성했지만 Tcl/Tk 초기화에서 실패하여 창을 생성하지 못했습니다. 동일 GUI 클래스를 시험용 위젯 대역으로 구동한 후 공식 client와 실제 Mock에 연결한 시험은 통과했습니다. 이를 실제 GUI 시험 통과로 표기하지 않습니다. Tk 환경 외부 탐색/설정 변경/설치는 수행하지 않았습니다.

처음 창 없는 정상 GUI 시험에서는 99.99999999999999 값을 100과 정확히 같다고 검사한 시험 assertion이 실패했습니다. 제품 실행은 completed였습니다. 시험을 가이드의 위치 허용치 0.5로 수정한 뒤 전체 세 경우를 재실행하여 통과했습니다.

마지막 실제 Mock 동작은 실행 중 종료 시험입니다. 관측 시 세 축 Standstill, 제어권 owner=null / available=true였고 DO=true, AO=100이었습니다. 자동 해제/Disable은 하지 않았습니다. 시험용 GUI/worker는 모두 종료했습니다. 서버는 종료하지 않았습니다.

미수행: 실제 Tk 창 렌더링/OS FocusOut·닫기 이벤트, 실제 키보드 Ctrl+C, 서버/네트워크 강제 고장 주입, 실장비의 충돌/이동 경로/부하/전기적 입출력 시험. 중간점은 사용자가 지정하지 않아 추가하지 않았습니다. 실장비 적용 전 이동 경로 확인은 사용자에게 남아 있습니다.
