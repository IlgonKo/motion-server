# X/Y/Z Pick & Place — Mock 전용 CLI

작업 폴더에서 아래 명령을 실행합니다. 외부 패키지 설치는 필요하지 않습니다.
제공된 `reference_clients/python`의 공식 client를 직접 import합니다.

```powershell
& 'C:/Users/Festo/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B generated/run.py --run-mock
```

**명령마다 실제 Mock 시퀀스를 새로 1회 수행합니다.** 이번 작업에서 이미 1회 수행했습니다.
종료 코드 0은 시퀀스·Stop 확인·제어권 해제가 모두 완료된 경우입니다. 그 외는 1입니다.
Ctrl+C는 취소 요청입니다. 진행 중 요청은 최대 요청 timeout 후 정리하며 추가 단계는 실행하지 않습니다.
다른 스레드에서 사용하는 경우 `Sequence.cancel.set()`이 Stop 요청입니다.

```powershell
& 'C:/Users/Festo/AppData/Local/Python/pythoncore-3.14-64/python.exe' -B -m unittest discover -s generated -p 'test_*.py' -v
```

자체 테스트는 네트워크를 사용하지 않는 가짜 client 시험입니다.
`-B`와 CLI의 `dont_write_bytecode`는 제공 client 폴더에 캐시를 쓰지 않게 합니다.

## 파일과 수정 위치

- `settings.json`: 사용자 수정 영역. 배열 순서는 `roles`에 적힌 X/Y/Z 순서입니다.
  좌표, 속도, 공통 가감속, 출력, 입력 AND 조건, 허용치, timeout을 수정합니다.
- `sequence.py`: 직접 API 호출 및 완료 대기, 취소, Stop 정리. API wrapper는 없습니다.
- `run.py`: 연결 → metadata 단위 확인 → 제어권 요청 → 1회 실행 → 제어권 해제 → 종료.
- `test_sequence.py`: 정상·실패·timeout·취소·자료 신선도 자체 테스트.
- `metadata.json`, `initial_feedback.json`: 실행 전 읽기 전용 API 조회 결과.
- `last_run.json`: 실제 1회 실행의 설정 snapshot, 단계 기록, 완료 판정 Feedback 증거.
  다음 CLI 실행 시 이 파일은 덮어씁니다.
- `RESULTS.md`, `test_results.txt`: 수행 결과와 최종 자체 테스트 기록.
- `inspect_metadata.py`: 읽기 전용 조회 도구. 실행하면 위 초기 조회 파일을 갱신합니다.

서버 config.txt와 제공 자료는 수정하지 않습니다. 가감속 profile은 사용자 요청대로
Run 시작 시 각 축에 한 번 적용합니다. 자동 복구/Homing/Enable/Disable/설정 저장 명령은 없습니다.
GUI와 Teaching은 선택되지 않았으므로 구현하지 않았습니다.

## 확인한 구성

사용자가 실제 적용 파일로 지정한 루트 `config.txt`는 backend=mock, mode=basic,
port=62554, bus=`cmmt_as,cmmt_as,cmmt_as,io:cpx_ap_i_ec:io0`, motion mode=pp입니다.
축 index 0/1/2는 사용자 역할 X/Y/Z이며 io0의 물리 slave index는 3입니다.
환경변수/CLI override를 추측하거나 별도 설정 parser로 병합하지 않습니다.

| 역할/채널 | 확인 결과 |
| --- | --- |
| X/Y/Z | axis 0/1/2, CMMT-AS; API metadata 위치 mm, 속도 mm/s, 가감속 mm/s² |
| Pick | (0.5, 0.6, 0.7) mm, 속도 (5, 5, 2) mm/s |
| Place | (1.0, 1.1, 1.2) mm, 속도 (5, 5, 2) mm/s |
| 공통 가감속 | 각 축 acceleration/deceleration=100 mm/s² |
| io0 slot 1 | DO 8채널, channel 0: 파지 true / 해제 false |
| io0 slot 2 | AIO 4AI/4AO, channel 0 AO: 파지 100 / 해제 0, raw 정수 |
| io0 slot 3 | DI 8채널, channel 0 == true |
| io0 slot 4 | AI 4채널, channel 0 >= 50, raw 정수 |

metadata의 `user_position_unit_name=m`은 내부 단위 정보이며, API 단위는
`position_unit=mm`를 사용합니다. 임의 count 환산은 없습니다. 매 실행 metadata가
설정의 expected_units와 일치하는지 확인합니다. 장치 구성과 채널은 제공 config 및 조회
Feedback로 확인했습니다. 실제 배선, 부하, 물리 파지 성공, 충돌 없는 경로는 미확인입니다.
중간점 없이 Pick과 Place를 각각 다축 move_abs로 명령하며 동기 보간 경로를 보장하지 않습니다.
실장비 적용 전 사용자가 경로를 확인해야 합니다. 이 CLI는 허용된 Mock 주소로 제한되어 있습니다.
서버 status API에는 backend 식별 필드가 없으므로 Mock 확인은 사용자의 지정과 config.txt에 근거합니다.

## 단계와 실패 계약

`system/axes/status`, `system/authority/request`, `system/axis/profile`,
`system/axes/move_abs`, `system/io/output_write`, `system/authority/status`,
`system/axes/stop`, `system/authority/release`만 호출합니다.
이동 속도는 `profile_velocities`, 가감속은 시작 시 `profile_acceleration/deceleration`입니다.

각 요청의 `result=success`와 동작 완료는 별도로 확인합니다. API Fail은 전체 envelope의
code/message/details를 기록하고 중단합니다. 가감속 이후 Pick → 세 축 완료 → DO/AO 각각
Success → DI/AI 동일 snapshot AND → Place → 세 축 완료 → DO/AO 해제 각각 Success → Stop입니다.
해제 입력은 현재 비어 있습니다. 선택하려면 `release_conditions`에 grasp_conditions와 같은
io/slot/kind/channel/op/value 구조를 작성합니다. op는 eq/ge/le입니다.

단일 Feedback 소비자가 snapshot과 monotonic 수신 시각/순서를 관리합니다.
Success 후 소비자에게 누적 queue 폐기를 요청하고 그 이후 snapshot만 대기에 사용합니다.
실제 위치 허용치 0.5 API 단위, Target reached(bit 10), Standstill(bit 8 해제)를
모든 축에서 검사합니다. 이전 인접 목표가 넓은 허용치로 통과하지 않도록 target_positions는
요청 목표와 절대 오차 1e-9 이내인지 추가 확인합니다. 표현 불가능한 소수 좌표를 새로 지정하면
서버 양자화 때문에 보수적으로 timeout될 수 있으므로 실제 metadata/분해능을 확인해야 합니다.
속도 허용치 기본값 1.0은 설정에 보존했지만 이번 절대 위치 이동 완료 판정에는 사용하지 않습니다.

invalid process data, 필요한 축/입력 누락, 누적 자료는 완료 조건을 만족하지 못합니다.
수신 중단은 2초 Feedback timeout, 이동은 30초, 입력은 10초로 제한합니다. 요청 timeout은 5초입니다.
Feedback에는 명령 ID가 없으므로 동일 위치 명령에서 새 물리 동작 발생을 증명하지 않습니다.
로컬 수신 신선도와 목표/상태 조건의 충족만 확인하며, API가 보장하지 않는 명령 귀속을 주장하지 않습니다.

Run 사전 Homing/Enable/Fault/limit 인터락은 복제하지 않습니다. 실행 중 관측한 Fault는
별도로 latch하며, 요청 응답을 기다리는 동안에도 소비자가 이를 기록합니다.
실패/중단 시 연결과 소유권이 유지되면 Stop 후 새 유효 자료의 Standstill을 확인합니다.
Feedback가 멈춘 경우에도 소유권 조회 후 Stop을 시도하며, 정지 증거가 없으면 INCOMPLETE입니다.
실패 시 I/O 쓰기는 하지 않습니다. 일부 출력만 성공한 경우에도 현재 출력을 유지합니다.
정상 종료는 해제 출력을 유지합니다. cleanup 실패는 completed로 표시하지 않습니다.

자동 재전송/재개/제어권 재획득은 없습니다. 공식 client의 내부 재접속 기능은 그대로지만,
관측한 연결/제어권 상실은 latch하여 새 세션에서 시퀀스/Stop을 보내지 않습니다.
공개 client에 연결 epoch 콜백이 없으므로 짧은 단절은 연결 polling과 Feedback 소유권 및
요청 예외로 관측합니다. 관측할 수 없는 통신 구간을 안전 인증으로 해석하지 않습니다.
소프트웨어 Stop은 하드웨어 비상정지를 대체하지 않습니다.
