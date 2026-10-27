# X/Y/Z Pick & Place CLI

공식 `MotionServerClient.request()`를 직접 호출하는 1회 시퀀스입니다. Python 표준 라이브러리와 제공된 공식 client만 사용하며 pip 설치가 필요 없습니다. GUI/Teaching은 선택하지 않았으므로 구현하지 않았습니다.

## 파일과 실행

- `settings.json`: X/Y/Z 순서의 위치·속도, 역할, 공통 가감속, I/O 조건, timeout 수정 영역.
- `sequence.py`: 단일 Run과 Feedback 소비자, 실패/Stop cleanup. API wrapper 없음.
- `run_once.py`: CLI 진입점. Ctrl+C는 취소 Event를 설정합니다.
- `test_sequence.py`: 서버를 사용하지 않는 가짜 client 자체 테스트.
- `self-test-results.txt`: 실제 자체 테스트 출력.
- `mock-run-console.txt`, `run-*.json`: Mock 실행 시도 로그와 결과.
- `RESULTS.md`: 확인 결과와 미실행 항목.

작업 폴더에서 PowerShell로 실행합니다. 아래 첫 명령은 **새로운 1회 실행 요청**입니다. 반복 루프가 없습니다.

```powershell
& 'C:/Users/Festo/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B generated/run_once.py --run-mock
```

```powershell
& 'C:/Users/Festo/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B -m unittest discover -s generated -p 'test_*.py' -v
```

CLI는 명시적인 `--run-mock` 옵션을 요구하고 허용 주소를 `127.0.0.1:54786`으로 제한합니다. 종료 코드는 완료 0, 시퀀스 실패/취소 1입니다. 결과 JSON의 `state`, `failed_stage`, `error`, `cleanup_complete`, `cleanup_error`, `release_error`를 확인하십시오. 입력 파일 자체가 잘못되면 Python 오류로 종료할 수 있습니다. 실행 기록은 매번 별도 파일에 저장합니다. 제공 자료에 bytecode를 쓰지 않도록 `-B` 및 `sys.dont_write_bytecode`를 사용합니다.

## 확인한 장치와 값

실제 적용 파일은 작업 폴더 `config.txt`이며 읽기만 했습니다. 사용자가 이 파일을 Mock 서버의 실제 적용 설정으로 지정했습니다. 별도 환경변수 병합이나 설정 변경을 하지 않습니다.

|역할/대상|설정 및 서버에서 확인한 내용|
|---|---|
|X / Y / Z|각각 axis 0 / 1 / 2, 설정 장치 `cmmt_as`, 물리 slave 0 / 1 / 2|
|축 API 단위|세 축 실제 metadata: 위치 `mm`, 속도 `mm/s`, 가속/감속 `mm/s^2`|
|io0|설정 `cpx_ap_i_ec`, Feedback slave 3|
|파지 DO|slot 1 `do:8`, digital channel 0 = true|
|파지 AO|slot 2 `aio:4:4`, analog channel 0 = 100 raw 정수|
|파지 DI|slot 3 `di:8`, digital channel 0 = true|
|파지 AI|slot 4 `ai:4`, analog channel 0 >= 50 raw 정수|
|해제|동일 DO=false, AO=0. 해제 입력 확인 없음|

읽기 전용 조회 당시 DI=true, AI=100, DO=false, AO=0을 확인했습니다. Analog 모듈은 Feedback상 16-bit signed입니다. 센서 물리량으로 환산하지 않습니다. Metadata의 `user_position_unit_name=m` 대신 API용 `position_unit=mm`를 사용합니다. 시작할 때 각 축 metadata와 설정 단위를 비교하며 불일치하면 명령 실행 전에 실패합니다.

Pick=(0.5,0.6,0.7), Place=(1.0,1.1,1.2) mm. 두 단계 모두 속도=(5,5,2) mm/s. 공통 가속/감속은 각 축 100 mm/s²이며 Run 시작 시 축별 profile 요청을 한 번씩 보냅니다. 위치 허용치 0.5 mm, 속도 허용치 1 mm/s는 가이드 기본값입니다. 절대 위치 이동이므로 속도 허용치는 완료 판정에 사용하지 않습니다.

## 단계 전환과 중단

연결 → metadata 확인 → 제어권 요청 → 공통 profile 3회 → Pick 다축 이동/완료 대기 → DO/AO 파지 요청 각각 Success → DI AND AI 대기 → Place 다축 이동/완료 대기 → DO/AO 해제 각각 Success → 선택한 해제 입력 대기 → Stop/모든 축 Standstill → 제어권 해제 → 연결 종료입니다.

이동에는 `profile_velocities`만 사용합니다. 세 축의 실제 위치 근접 AND Target reached(bit 10) AND Standstill(Moving bit 8 해제)을 모두 확인합니다. 과거 목표 혼동을 줄이기 위해 Feedback `target_positions`가 요청 목표와 일치하는 것도 확인합니다(부동소수점 비교 오차 1e-7 API 단위). 이는 경로 보간이나 동기 도착을 보장하지 않습니다.

Feedback은 전용 스레드 한 곳에서만 소비합니다. Success 뒤 소비자가 누적 queue를 비우고 barrier를 확인한 다음, 더 큰 로컬 수신 순서의 새 snapshot을 기다립니다. monotonic 수신 시각이 Feedback timeout 이내이고 `process_data_valid=true`, 사용 축 정보와 필요한 I/O channel이 있어야 조건을 충족합니다. 일반 Feedback에는 명령 ID가 없으므로 완료 조건 충족은 새 물리 동작 발생의 증명이 아닙니다. 같은 위치 재명령에서도 같은 규칙을 사용합니다.

Ctrl+C/외부 Stop Event, 서버 Fail, 요청/이동/입력/Feedback timeout, 실행 중 Fault, 연결/제어권 상실은 다음 단계 진입을 막습니다. 서버 Fail 응답 전체에 있는 code/message/details를 기록합니다. 요청은 최대 5초 bounded wait이고 이미 전송한 요청은 취소할 수 없습니다. 대기 루프는 짧게 나누어 취소를 확인합니다. 연결/제어권 상실과 Fault는 감지 후 정상 자료가 와도 실패를 유지합니다.

중단/실패 cleanup은 연결 및 제어권이 유지될 때 Stop과 Standstill 확인만 시도합니다. I/O는 성공/실행된 마지막 출력 그대로 두며, 부분 출력 실패도 롤백하지 않습니다. 정상 cleanup 역시 Stop으로 정지를 확인하고 해제 출력을 유지합니다. 정지 또는 제어권 해제를 확인할 수 없으면 `INCOMPLETE`를 기록하며 완료로 표시하지 않습니다. 제어권 요청 응답 timeout 때도 동일 연결의 authority/status로 소유 여부를 조회할 수 있으면 Stop/해제를 시도합니다.

공식 client 자체에는 재연결 기능이 있지만 프로그램은 상실 감지 후 Run을 재개하지 않으며 자동 재전송/제어권 재획득을 하지 않습니다. 자동 Homing/Enable/Disable/Fault reset/설정 수정/서버 복구는 없습니다. Run 사전 Homing/Enable/Fault/limit 인터락을 복제하지 않습니다.

`release_inputs`를 사용하려면 `grip_inputs`와 같은 구조의 조건을 설정하십시오(`eq`, analog의 `ge`). 모든 조건을 같은 snapshot에서 AND로 판정합니다. 실행 설정은 deepcopy로 고정합니다. Teaching/GUI를 추가로 선택할 때는 해당 가이드 계약에 맞는 별도 구현 작업이 필요합니다.

사용 API: `system/axis/status`, `system/authority/request`, `system/authority/status`, `system/authority/release`, `system/axis/profile`, `system/axes/move_abs`, `system/io/output_write`, `system/axes/stop`, 수신 `system/feedback`.

## 아직 확인하지 않은 사항

실장비 실행은 허가되지 않았으며 수행하지 않았습니다. 중간 이동점은 미지정입니다. 시작 위치에서 Pick으로, Pick에서 Place로 세 축을 함께 명령합니다. Z 선행 상승 등 임의 경로는 추가하지 않았습니다. 실제 경로·충돌 여유·파지 배선과 부하 거동은 사용자가 적용 전에 확인해야 합니다. 소프트웨어 Stop은 하드웨어 비상정지의 대체물이 아닙니다.

Mock backend 여부는 사용자 지정 실제 config와 접속 허용 범위에 근거합니다. 공개 status Schema에는 backend 식별 필드가 없으므로 같은 주소에 다른 서버가 배치되었는지 프로그램이 증명할 수는 없습니다.
