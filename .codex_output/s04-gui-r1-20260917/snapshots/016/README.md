# X/Y/Z Pick & Place (CLI + Tkinter/ttk)

`sequence.json`을 수정하고 CLI와 GUI는 같은 `sequence.py`의 `Sequence.run()`을 사용합니다. Teaching은 구현/노출하지 않았습니다. 제공 문서, Schema, 공식 Python client와 예제의 직접 API 조합 방식을 읽고 이 작업에 맞게 작성했습니다. 제공 자료/서버 설정은 변경하지 않았습니다.

## 실행

작업 폴더에서 PowerShell로 실행합니다. 설치나 외부 패키지가 필요하지 않습니다. `generated/__init__.py`가 이 폴더에 제공된 공식 client를 불러옵니다.

```powershell
$python = 'C:/Users/Festo/AppData/Local/Python/pythoncore-3.14-64/python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'

# 지정 Mock 서버에서 딱 1회: 연결 → 제어권 → Run → Stop 확인 → 제어권 해제 → 종료
& $python -m generated --run

# GUI 진입점 (Tcl/Tk가 정상 설치된 경우)
& $python -m generated --gui
# 동일 GUI의 별도 모듈 진입점
& $python -m generated.gui
```

실제 시험 환경에서는 지정 Python의 Tcl/Tk가 `Can't find a usable init.tcl`로 초기화에 실패했습니다. 따라서 **실제 창 Run/Stop/닫기/OS 포커스 시험은 미수행**입니다. `gui_result.txt`에 실행 시도 오류가 있습니다. 외부 파일 탐색, 다운로드, Python/서버 설정 변경으로 보수하지 않았습니다. 사용 가능한 Tcl/Tk 환경이 제공되면 아래 실제 창 자동 시험을 실행할 수 있습니다.

현재 실행 허용 범위는 `127.0.0.1:52728` Mock 서버입니다. 실장비 실행은 별도 요청 전 수행하지 않습니다. 중간점이 없는 두 번의 다축 이동이며, 실제 장비의 경로/간섭/부하/배선은 확인하지 않았습니다. 사용자가 적용 전 경로를 검토해야 합니다.

## 파일과 수정 항목

| 파일 | 역할 |
| --- | --- |
| `sequence.json` | 주소, 역할/단위, 좌표, 단계별 속도, 공통 가감속, I/O, 허용치/timeout |
| `sequence.py` | 단일 Feedback 소비자, 대기/취소, 공유 실행 코드 |
| `settings.py` | 사용자 설정 및 서버 metadata 단위 일치 검사 |
| `__main__.py` | 1회 CLI와 Ctrl+C 처리, GUI 선택 |
| `gui.py` | Host/Port, 연결/제어권, Run/Stop, 실제 상태/단계/로그 |
| `probe.json` | 읽기 전용 조회로 확보한 실제 metadata와 초기 Feedback |
| `RESULTS.md` | 수행 결과와 미수행 시험 |

`--config generated/sequence.json`으로 설정 경로를 지정할 수 있습니다. GUI 실행 중 파일 편집은 현재 Run을 바꾸지 않습니다. 파일 변경을 반영하려면 GUI를 종료하고 다시 시작합니다. 각 Run은 설정을 복사해 고정합니다. `failure_outputs`는 반드시 빈 배열이며 중단 시 출력 유지 정책을 바꿀 수 없도록 검사합니다. `release_conditions`는 현재 빈 배열입니다. 필요하면 `grasp_conditions`와 같은 io/slot/kind/channel/op/value 형식으로 명시합니다.

## 확인한 구성

사용자가 실제 적용 설정으로 지정한 작업 폴더 `config.txt`: backend=mock, mode=basic, PP, cmmt_as 3축 + io0(CPX-AP-I-EC). 실제 `system/axes/status` metadata에서도 X/Y/Z API 단위가 확인됐습니다. 단위 환산은 하지 않습니다. metadata의 원시 `user_position_unit_name=m` 대신 공개 API 단위 `position_unit=mm`를 사용합니다.

| 역할 | axis | 위치 / 속도 / 가감속 단위 | Pick / Place | Pick / Place 속도 |
| --- | --- | --- | --- | --- |
| X | 0 | mm / mm/s / mm/s² | 50 / 100 | 50 / 50 |
| Y | 1 | mm / mm/s / mm/s² | 60 / 110 | 50 / 50 |
| Z | 2 | mm / mm/s / mm/s² | 70 / 120 | 40 / 20 |

각 축 acceleration=100.0, deceleration=100.0을 Run 시작에 한 번 적용합니다. 위치 허용치는 축마다 0.5 mm입니다. 속도 도달 대기는 이 시퀀스에 없으므로 가이드의 속도 허용치 1.0은 사용되지 않습니다. request=5초, 이동/Stop 대기=30초, 입력=10초, Feedback=2초입니다.

| I/O | 실제 설정 | 사용 |
| --- | --- | --- |
| io0 slot 1 | DO 8채널 | digital ch0: 파지 true / 해제 false |
| io0 slot 2 | AIO 입력4/출력4 | analog ch0: 파지 100 / 해제 0, raw 정수 |
| io0 slot 3 | DI 8채널 | digital ch0 == true |
| io0 slot 4 | AI 4채널 | analog ch0 >= 50, raw 정수 |

파지 확인은 DI와 AI를 **동일한 유효 snapshot에서 AND**로 검사합니다. 설정 파일과 조회된 모듈/단위의 불일치는 관측되지 않았습니다. 실장비 장치, 실제 물리 경로 및 센서의 공학 단위는 검증하지 않았습니다.

## 실행 계약

기존 `client.request`로 `system/axis/profile`, `system/axes/move_abs`, `system/io/output_write`, `system/axes/stop`을 직접 호출합니다. 읽기는 `system/axes/status`, `system/authority/status`, 진단 probe의 `system/server/status`, 제어권은 `system/authority/request` / `release`입니다. 새 API, 명령 wrapper, Enable/Homing/Fault/limit 사전 운전 인터락은 없습니다.

- `result=success`는 요청 접수 결과입니다. 이동 완료는 별도 새 유효 Feedback에서 모든 사용 축의 실제 위치 근접 AND 목표값 일치 AND Target reached(bit10) AND Standstill(bit8 해제)을 확인합니다.
- 공식 client의 queue 크기는 1, 소비자는 `Feedback` 한 개입니다. Success 뒤 소비자에게 queue 배출 장벽을 요청하고 장벽 이후 수신 순서만 완료 판정에 씁니다. 배출 자료도 Fault/제어권 상실 감시에는 반영합니다. GUI는 snapshot 복사본만 봅니다.
- monotonic 수신 시각을 검사하며 오래된 마지막 자료, invalid 자료, 누락 축/채널로 완료하지 않습니다. Fault/연결/제어권 상실은 감시해 중단합니다. API 일반 Feedback은 operation ID/서버 생성 시각이 없으므로 엄격한 명령 귀속 증거가 아닙니다. 같은 위치 재명령은 상태 조건 충족을 뜻하며 새로운 물리 동작을 증명하지 않습니다.
- Stop/Ctrl+C는 취소 신호입니다. 이미 전송된 요청을 회수했다고 간주하지 않으며 요청 종료 후 다음 동작을 막고 cleanup합니다. 재전송/Disable/자동 복구/자동 재개/제어권 재획득은 하지 않습니다. 공식 client 자체의 연결 재시도는 그대로이며 새 제어권과 Run은 명시적 조작입니다.
- 정상: 해제 출력 Success 후 Stop/새 Standstill 확인 → completed. 취소: 출력 유지 + Stop 확인 → cancelled. 실패 또는 정지 확인 불가 → failed, `Stop NOT confirmed` 기록. cleanup이 불가능하면 정지됐다고 주장하지 않습니다.
- cleanup은 제어권 상태 조회(5초), Stop 요청(5초), Feedback 장벽(2초), Standstill 대기(최대30초)로 제한됩니다. Stop을 누를 때 진행 중이던 요청의 최대5초와 종료 시 제어권 조회/해제·client 종료 시간은 별도입니다. 마지막 Feedback가 이미 만료됐으면 더 일찍 미완료로 판정할 수 있습니다.

GUI는 `idle/running/stopping/completed/cancelled/failed`, 현재 단계, 연결/제어권/서버 상태/위치/자료 신선도, 정지 확인 여부를 표시합니다. 통신 및 대기는 worker, 위젯 갱신은 GUI thread에서 합니다. 중복 Run과 동작 중 연결/제어권 변경을 막습니다. Run이 끝나도 GUI는 제어권을 유지합니다. 창 닫기는 취소/cleanup 뒤 제어권을 해제하고 연결을 닫습니다. 종료 오류와 미완료 로그는 `generated/gui.log`에도 보존합니다. Teaching/Jog가 없으므로 포커스 이동은 자동 Run을 취소하거나 jog_stop을 보내지 않습니다.

## 시험 재실행

```powershell
# 서버 불필요: 9개 시퀀스 시험(실패 모드 subtest 포함)
& $python -m generated.test_sequence
# 서버 불필요: 창 없는 GUI 실패/cleanup/설정 누락 시험
& $python -m generated.test_gui_failures

# 지정 Mock에서 실제 움직임 발생: 정상/중단/종료 각각 자동 수행
# 실제 Tcl/Tk 창 시험 (현재 환경은 init.tcl 오류로 실행 불가)
& $python -m generated.test_gui_mock
# 창 없는 widget double + 실제 Mock + 실제 공식 client, 같은 GUI 콜백/worker 시험
& $python -m generated.test_gui_mock --headless
```

Mock GUI 시험은 정상 Run → Place 이동 중 Stop → Place 이동 중 창 닫기 세 경우를 각 연결에서 수행합니다. 중복 Run 차단, 포커스 콜백, Run 후 제어권 유지, 종료 후 제어권 해제, 정지/출력 상태를 검사하고 자동 종료합니다. 마지막 중단 시험 결과 DO=true/AO=100이 유지됩니다. 시험이 이를 자동으로 해제하지 않습니다.

`headless_widgets.py`는 시험 전용 위젯 대역입니다. 모든 위젯 접근이 주 thread인지 검사하지만 실제 Tk 렌더링, OS 창 닫기/포커스 이벤트 전달의 검증을 대신하지 않습니다. 물리 Ctrl+C 신호, 실제 서버 강제 연결 단절/제어권 탈취/Fault 주입은 하지 않았고 관련 로직은 client double로 검증했습니다. 실제 장비 시험은 전혀 수행하지 않았습니다.
