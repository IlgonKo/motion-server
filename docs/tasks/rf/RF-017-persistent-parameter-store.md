# RF-017 Persistent Device Parameter Store

- 등록일: 2026-09-04
- 상태: `complete`
- 우선순위: 보통
- 관련 항목: TD-025, RF-003, RF-013, RF-016

## 배경

현재 virtual device parameter는 서버 프로세스 안의 OD/runtime state에만 존재한다.
따라서 서버를 다시 시작하면 virtual CMMT/CPX/IO-Link parameter는 기본 preset 또는 설정값으로
초기화된다. 앞으로는 가상장치에서 조정한 parameter를 저장하고 변경 이력을 관리하며 재시작 후 복원한다.
가상장치는 대응 실장치와 같은 OD 구조를 기반으로 파라미터를 관리한다. 가상/실장비 간 파라미터
이전은 Motion Server를 이용하는 애플리케이션의 책임이며 Motion Server 및 RF-017 범위에서 제외한다.

이 기능은 실행 중 제어용 cache인 TD-025와 성격이 다르다. TD-025의 Runtime Parameter Cache는
빠른 제어/status projection을 위한 현재값이고, RF-017의 Persistent Store는 장치 모델이 저장을
요청한 parameter snapshot과 변경 이력의 원본이다.

## 확정 책임 경계 (2026-11-24)

- 장치 profile: 저장 대상 파라미터와 해당 정의를 명시한다. writable 여부나 PDO mapping 여부만으로 자동 선정하지 않는다.
- 가상장치 모델: 장치별 동작에 따라 저장 시점을 결정하고 저장 대상의 일관된 현재값 묶음을 공통 저장소에 전달한다.
- 공통 Persistent Store: 전달받은 데이터를 저장하고 revision/이력 조회를 제공한다. CMMT Save나 CPX Mode 등의 장치 명령을 해석하지 않는다.
- 가상장치 초기화: 기본값 초기화 후 저장소에서 값을 읽어 장치의 OD/AP/ISDU 공간에 복원한다. Runtime Cache는 복원된 장치 상태로 갱신한다.
- CPX 저장 동작과 AP/IOL 적용 범위는 해당 가상장치 구현에서 다룬다. 공통 저장 구조 확정의 선행 조건으로 두지 않는다.
- 기존의 “모든 장치는 parameter_save 명령에서만 저장” 규칙은 위 장치별 저장 시점 계약으로 대체한다.

## 핵심 계약

```text
parameter write
→ Device OD / AP parameter / IO-Link ISDU 변경
→ Runtime Parameter Cache 갱신 또는 invalidation
→ 저장 필요 여부는 장치 모델이 장치별 동작으로 판단

장치 모델의 저장 요청
→ profile이 정의한 저장 대상의 일관된 현재값 묶음 전달
→ Persistent Store에 snapshot과 revision 저장
→ 성공 또는 실패를 장치 모델에 반환

가상장치 초기화
→ 기본 OD/AP/ISDU 초기화
→ Persistent Store 값 조회 및 정의와 호환성 확인
→ 가상장치 파라미터 공간에 저장값 복원
→ Runtime Parameter Cache 갱신
```

## 1차 구현 범위

- CMMT Axis OD, CPX station EtherCAT OD, CPX AP module parameter, IO-Link ISDU parameter를
  식별할 공통 persistent parameter address model
- 가상 CMMT-AS/ST의 확정된 20개 OD 저장 및 장치 재생성 시 복원
- CPX 저장 연결은 후속 단계, 가상 AP/IOL 파라미터 장치는 RF-013 재개 시 연결한다.
  공통 주소 모델의 지원과 실제 장치 저장 연결을 구분하며 RF-013을 RF-017에서 대신 구현하지 않는다.
- 별도 maintenance/commissioning tool을 통한 Virtual Device 초기화
- 변경 이력 revision 및 timestamp 관리 (선택 metadata의 세부 범위는 추가 결정)
- 관리 CLI의 list/history/show/factory-reset과 기본 출력 및 --json
- snapshot의 원자적 저장과 복원 실패 보고

## 제외 범위

- 실장비 parameter readback snapshot 저장 및 해당 백업·변경 이력 관리 (외부 애플리케이션 범위)

- 가상/실장비 간 파라미터 이전 및 이를 위한 target 매핑·호환성 판단·apply/verify 시퀀스

- Runtime cycle 중 SDO polling
- 공통 저장소가 parameter write를 감시하여 장치 정책과 무관하게 자동 저장하는 기능
- 서버 시작 시 Persistent Store 값을 실장비에 자동 적용
- 모든 device OD를 무조건 저장하는 full dump
- 외부 DB server 의존성
- 공개 Motion Server TCP API를 통한 Virtual Device 초기화

## CMMT 저장 대상 — 확정 20개 OD

기존 `device/cmmt/required_non_pdo_od.py`의 `NON_PDO_CONFIGURATION_OD_ROLES`에 대응하는
아래 20개 항목을 profile의 저장 대상으로 명시한다. 향후 해당 목록이 바뀌더라도 검토 없이
저장 대상을 자동 확대하지 않는다. 타입/주소의 기존 정의를 재사용한다.

| 분류 | OD | 항목 수 | 내용 |
| --- | --- | --- | --- |
| 위치 단위 | `0x216E:01` | 1 | 위치 단위 및 Linear/Rotary |
| 스케일 | `0x2194:01~04` | 4 | 위치·속도·가속도·Jerk exponent |
| Software limit | `0x607D:01~02` | 2 | 최소·최대 위치 |
| 위치 도달 판정 | `0x6067:00`, `0x6068:00` | 2 | Position window 및 유지 시간 |
| 속도 제한 | `0x607F:00`, `0x2183:0C` | 2 | 최대 Profile velocity 및 음의 방향 속도 제한 |
| Profile 가감속 | `0x6083:00`, `0x6084:00` | 2 | Profile acceleration/deceleration |
| Homing | `0x6098:00`, `0x6099:01~02`, `0x609A:00` | 4 | 방식·속도·가속도 |
| 가감속 제한 | `0x60C5:00`, `0x60C6:00` | 2 | 최대 가속도·감속도 |
| PP Jerk | `0x60A4:01` | 1 | 장치 PP Jerk |

- 사용자 결정에 따라 `0x6081:00 Profile velocity`는 저장/복원에서 제외한다. 실행 중 RxPDO 관리 계약을 유지한다.
- Controlword, 운전 모드, 목표값·현재값, Statusword·오류 상태, 저장/재시작 명령과 처리 결과는 제외한다.
- PDO mapping/assignment와 startup 설정으로 적용하는 CSP interpolation·동기화 OD는 제외한다.
- RO commissioning 항목을 내부적으로 복원하는 것은 일반 SDO write 권한을 확대하는 것이 아니다.
- CMMT 기본값은 현재 설정에서 선택한 `non_pdo_configuration` preset 값이다.
  Factory Reset 후 다음 기동도 이 기준을 사용하며 새 저장 요청 전 snapshot을 자동 생성하지 않는다.

## 저장 데이터 구조

- Device: `storage_id`, `profile_key`, `parameter_schema_version`.
- Snapshot: `storage_id`, `revision`, `saved_at`, `profile_key`, `parameter_schema_version`, `parameters`.
  한 장치의 profile이 지정한 저장 대상 전체를 포함하며 전체 OD dump는 아니다. 시각은 UTC로 기록한다.
- ParameterValue: 기존 TD-025 체계를 따르는 `address`, `data_type`, `raw_value`.
  OD는 index/subindex, AP는 module/parameter_id/instance, ISDU는 module/port/index/subindex로 식별한다.
  값은 장치 모델이 직렬화한 bytes로 저장하며 숫자 표현값을 중복 저장하지 않는다.
- 공통 저장소는 장치의 단위·byte order·명령 의미를 해석하지 않는다.
- SQL 주소 표현 등 내부 표현은 확정 계약에 맞춰 구현한다. actor/note는 필수 필드로 추가하지 않는다.

## 장치 식별과 저장 파일

```ini
MOTION_SERVER_VIRTUAL_DEVICE_PARAMETER_STORE_ENABLED=0
MOTION_SERVER_VIRTUAL_DEVICE_PARAMETER_STORE_PATH=
```

- ENABLED 기본값은 0이다. 활성화와 경로를 분리하며 경로 존재만으로 활성화하지 않는다.
- 비활성화 시 서버는 저장소를 열거나 복원하지 않는다. 가상장치는 메모리에서 동작하고 기존 파일/이력은 유지한다.
- 비활성화 중 저장 명령은 영구 저장 성공으로 처리하지 않는다. 미지원/실패의 장치별 표현은 모델이 담당한다.
- 활성화 시 경로와 가상장치 storage_id를 검증한다. 경로 누락/접근 실패/ID 누락·중복은 초기화 실패다.
- 실장비의 저장 명령에는 영향을 주지 않는다. 다시 활성화하면 기존 저장본을 복원한다.

- 가상장치 설정에 `storage_id`를 명시한다. 영구 저장 사용 시 필수이며 같은 저장소 안에서 중복을 허용하지 않는다.
- 통신용 slave_index/API axis index와 분리한다. BUS 순서가 바뀌어도 같은 ID로 기존 저장값을 찾는다.
- ID 변경은 새 장치로 취급하며 이전 데이터는 보존한다. 자동 이전하지 않는다.
- 같은 ID라도 profile 또는 저장 정의 버전이 다르면 복원을 거부한다.
- 메인 설정 `MOTION_SERVER_VIRTUAL_DEVICE_PARAMETER_STORE_PATH`로 SQLite 파일 경로를 직접 지정한다.
  영구 저장을 사용할 때 명시적으로 지정하며 임의 기본 경로로 대체하지 않는다.
- 상대 경로는 메인 설정 파일 위치 기준으로 해석한다. 실행 cwd 기준이 아니다.
- 서버 인스턴스마다 파일 하나를 사용하며 다른 서버 인스턴스와 공유하지 않는다.
- 설치/업데이트 폴더와 분리된 사용자 데이터 경로를 사용한다. Docker에서는 저장 파일의 부모 폴더를 volume으로 연결한다.
- 부모 폴더가 없으면 생성한다. 생성·읽기·쓰기 실패 시 다른 위치로 대체하지 않고 오류를 보고한다.

### storage_id 설정 문법

메인 .env / config.txt에서 공통 목록으로 지정한다.

```ini
MOTION_SERVER_VIRTUAL_DEVICE_STORAGE_IDS=\
    0:gantry_x,\
    1:gantry_y,\
    4:remote_io_main
```

- 왼쪽은 BUS slave index이며 API axis index가 아니다. 오른쪽은 영구 저장 ID다.
- 가상장치 생성 시 매핑을 연결한다. BUS 순서 변경 시 index를 수정하고 ID는 유지한다.
- ID는 영문 소문자·숫자·밑줄·하이픈으로 구성한다.
- 동일 slave 중복 선언, ID 중복, 존재하지 않는 slave 지정은 설정 오류다.
- 기존 MOTION_SERVER_BUS 문법은 변경하지 않는다. CMMT/CPX에 공통 적용한다.
- AP/IO-Link 하위 장치의 독립 ID는 RF-013 연계 시 별도로 결정한다.

## 저장과 변경 이력

- SQLite의 devices, snapshots, snapshot_values로 장치·revision·파라미터 값을 관리한다.
- 장치 모델은 일관된 현재값 묶음을 수집하여 불변 데이터로 전달한다.
- 최초 저장 또는 저장 대상·타입·값·profile 정의 버전이 변경되면 새 revision을 생성한다.
- 항목 순서와 무관하게 주소·타입·저장값 및 정의 정보를 비교한다. 모두 같으면 기존 revision을 유지하고 성공을 반환한다.
- 저장 명령 호출 횟수·시각에 대한 별도 감사 이력은 이번 범위에 포함하지 않는다.
- 각 revision은 저장 대상 전체 값을 보관한다. 1차는 revision별 조회를 제공하고 diff 명령은 제외한다.
- 이력은 자동 삭제 없이 유지한다. 보존 기간/용량 제한은 추후 필요 시 논의한다.
- snapshot 전체 저장과 최신 활성 revision 변경은 한 transaction에서 commit한다. 일부 항목만 commit하지 않는다.
- 2026-11-24 확정: 저장은 전용 worker에서 비동기로 처리한다. PDO/Model_Update에서 SQLite 기록이나 commit 완료를 기다리지 않는다.
- Model_Update는 immutable snapshot을 전달하고 다음 주기에서 완료 여부만 확인한다. API Success는 commit 완료 후 반환한다.
- 저장 대기 중에는 서버가 PDO, feedback 및 다른 요청을 계속 처리한다. 같은 장치의 중복 저장은 거부하고, 공통 대기열은 제한한다.
- 저장 실패 시 이전 저장본과 가상장치 현재값을 유지한다. 자동 rollback이나 자동 재시도하지 않는다.
- 공통 저장소는 실패를 장치 모델에 반환한다. 장치 응답/오류 상태 변환은 모델 책임이며 저장 실패만으로 공통 Drive Fault를 생성하지 않는다.

## 가상장치 초기화와 복원

- 기본값 초기화 → storage_id로 최신 활성 저장본 조회 → 전체 검증 → 저장값 복원 → 정상 초기화 순서다.
- 저장본이 없으면 기본값을 사용한다. 최초 저장본은 장치 모델의 저장 요청 전 자동 생성하지 않는다.
- 정상 저장본은 최신 revision을 복원한다. profile/정의 버전 불일치, 데이터 손상, 필수 저장 항목 누락,
  파일 읽기·접근 실패는 초기화 실패로 보고한다. 조용히 기본값으로 대체하지 않는다.
- 전체 검증 후 복원하고 일부 값만 적용된 장치를 운전하지 않는다. Runtime Cache는 복원된 장치 상태로 갱신한다.
- 서버 시작 및 Bus Reconnect 등 가상장치가 새로 생성되는 경로에 적용한다. 단순 Fault Reset에는 적용하지 않는다.

## Factory Reset

- 별도 관리 도구에서 대상 storage_id를 지정하여 Factory Reset 하나만 제공한다.
- 서버 종료 상태에서 CLI로 실행한다. 저장소를 서버가 사용 중이면 거부한다.
- Reset 이력을 기록하고 기존 저장값이 다음 기동에 복원되지 않도록 한다. 다음 기동 시 현재 설정에서
  선택한 non_pdo_configuration preset으로 가상 CMMT를 초기화한다. 자동 snapshot은 생성하지 않는다.
- Factory Reset 이력을 남기며 과거 revision은 유지한다. 이력 없는 상태로 만드는 기능이 아니다.
- 별도 Runtime reset / Store reset과 이력 삭제(purge)는 1차 기능으로 제공하지 않는다.
- 공개 Motion Server TCP API에는 추가하지 않는다.

## 관리 CLI 1차 범위

- list: 저장된 storage_id와 최신 revision 조회.
- history: 장치의 저장/Factory Reset 이력 조회.
- show: 지정 revision의 저장 파라미터 조회.
- list/history/show는 서버 실행 중에도 읽기 전용으로 허용한다. commit 완료된 revision만 읽으며
  미저장 runtime 값이나 부분 저장 데이터는 노출하지 않는다.
- factory-reset: 서버 종료 상태에서 지정 장치의 복원값 초기화.
- 사람이 읽는 기본 출력과 --json을 제공한다.
- 과거 revision 선택 복원, diff, export/import, purge는 1차에서 제외한다.

## 구현 시 확인 사항

공통 설계 및 1차 범위 논의는 완료했다. 다음은 구현 과정의 확인 항목이다.

- 서버/CLI 저장소 잠금, Factory Reset 실패 시 원자성, SQL 내부 표현을 확정 계약대로 구현한다.
- worker 저장 지연 주입 중 Model_Update 진행과 commit 이전 Success 금지를 검증한다.
- 저장 실패의 장치 응답 및 복원 실패의 기존 초기화 진단 전달 경계를 검증한다.
- CPX/AP/IOL 실제 저장 연결은 1차 완료 조건에 포함하지 않는다. 하위 장치 storage_id와 장치별 저장 동작은 후속 범위에서 다룬다.

## Motion Server와 애플리케이션의 책임 경계

- 가상장치는 대응 실장치와 같은 OD 구조 및 주소 체계를 바탕으로 파라미터를 관리한다.
  AP/IO-Link의 gateway OD와 그 뒤의 AP/ISDU 파라미터 공간 경계도 유지한다.
- Motion Server는 파라미터 접근, runtime/cache 관리, 가상장치 snapshot 영구 저장·이력 및 복원을 담당한다.
- 실장비와 가상장비 간 이전은 Motion Server를 이용하는 애플리케이션이 구현한다.
  대상 선택, 파라미터 대응·호환성 판단, 읽기/쓰기 순서와 적용 결과 확인은 애플리케이션 책임이다.
- Motion Server에 이전 전용 API나 자동 apply/verify 시퀀스를 추가하지 않는다.
  애플리케이션은 기존 파라미터 접근 API를 사용한다.
- 저장 profile export/import는 1차 범위에서 제외한다. 향후 추가해도 실장비 적용을 포함하지 않는다.
- 실장비 내부 non-volatile save와 서버 Persistent Store 저장은 별도 동작·결과로 유지한다.
- Virtual Device 초기화 tool은 실장비에 적용하지 않는다.
- 2026-11-24 사용자 결정으로 실장비 이전과 실장비 snapshot 저장을 RF-017에서 제외했다.
  실장비 파라미터 백업·이력 관리는 기존 파라미터 접근 API를 이용하는 외부 애플리케이션이 담당한다.

## TD-025와의 경계

- TD-025는 실행 중 현재값, validity, refresh와 control/status projection을 담당한다.
- RF-017은 저장된 snapshot, 변경 이력, virtual restart restore를 담당한다.
- 저장 대상은 가상장치 파라미터로 한정한다. TD-025의 실장비 runtime cache/readback 지원은
  유지하지만 해당 값을 RF-017의 영구 snapshot으로 저장하지 않는다.
- Persistent Store 값은 주기 제어에 직접 사용하지 않는다. restore 후 Runtime Cache가 device
  state readback으로 다시 구성된 뒤 제어에 사용된다.

## 완료 조건

- persistent address/record/schema와 저장 위치가 확정된다.
- 공통 저장소/CLI와 가상 CMMT 20개 OD의 저장·장치 재생성 시 복원이 동작한다.
- Profile velocity 0x6081은 저장/복원되지 않으며 CPX/AP/IOL 실제 저장 연결은 1차 완료 조건에서 제외한다.
- Virtual Device Factory Reset 하나를 별도 관리 도구로 제공하고 과거 이력은 유지한다.
- Virtual Device 초기화 기능은 공개 Motion Server TCP API에 노출되지 않는다.
- 저장 대상은 장치 profile이 정의하고 저장 시점은 가상장치 모델이 결정한다. 공통 저장소는 장치 명령을 해석하지 않는다.
- list/history/show/factory-reset CLI의 기본 출력 및 --json을 제공한다. Factory Reset은 서버 종료 상태에서만 허용한다.
- 가상장치는 대응 실장치와 같은 OD 구조로 파라미터를 관리하며, 장비 간 이전 기능은 서버에 추가하지 않는다.
- 저장 실패 시 이전 저장본과 현재값을 유지하며, 복원 실패 시 부분 복원 상태로 운전하지 않는다.
- 실장비 snapshot 저장 및 장비 간 이전 기능은 포함하지 않으며 기존 실장비 parameter save 동작을 유지한다.
- storage_id 및 저장 경로, 동일 값 재저장, 원자적 저장, 이력 조회, 복원 검증과 Factory Reset 테스트가 통과한다.

## 구현 전 경로 점검 — 2026-11-24

- 설계 문서 커밋: `4359e7b`.
- `MockSlave.write_sdo()`는 OD write 직후 동기적으로 model_update를 호출한다.
- `VirtualCiA402Servo._apply_od_commands()`가 저장 command edge를 처리한다.
- `MockMaster.receive_processdata()`도 exchange_processdata → model_update를 동기 호출한다.
- 서버 루프는 PDO 교환과 client 처리를 같은 실행 흐름에서 수행한다. 현재 저장 command 경로에
  SQLite commit을 추가하면 디스크 작업 시간만큼 PDO/Heartbeat 처리가 지연되는 구조다.
- `CMMTDeviceProfile.save_parameters()`는 command write 직후 status/result를 읽고 command를 clear한다.
  worker만 추가하면 commit 전에 결과를 읽을 수 있으므로 완료 대기/응답 경계도 검토해야 한다.
- 사용자 확인 결과 동기 저장은 주기성을 방해하므로 비동기 저장으로 변경했다. worker와 완료 응답 경계를 함께 구현한다.
- 이는 코드 경로 분석 결과이며 실제 DB 저장 지연 측정이나 실장비 시험 결과는 아니다.

## 구현 결과 — 2026-11-24

### 리뷰 보완 및 재검증

- 기존 0바이트/미초기화 DB를 신규 저장소로 재생성하지 않고 StoreError로 거부한다. 파일이 없는 경우에만 최초 schema 생성을 허용한다.
- snapshot 이력이 남아 있는데 활성 장치/revision 정보가 없는 경우 기본값 복원과 재저장을 모두 거부한다. 기존 이력은 변경하지 않는다.
- 관련 회귀 테스트 4개를 추가했다: 기존 빈 파일, 저장 후 truncate, 활성 연결 유실, 정상 신규 storage_id.
- 수정 후 단위/Mock 회귀 607개, RF-017 집중/TCP 검증 23개 통과(집중 검증의 단위 항목은 전체 회귀와 중복).
- 저장·복원, 비동기 완료 응답, 실패 및 종료 경계를 다시 검토했으며 이번 검토 범위에서 추가 수정 사항은 발견하지 못했다.
- 이후 사용자 수동 확인을 반영하여 1차 범위를 완료 처리했다. 실제 패키지 실행 검증은 RF-006 배포 통합 검증에서 추적한다.

- [x] S01: main configuration의 enable/path/storage_id와 상대 경로 기준 검증.
- [x] S02: SQLite snapshot/revision, 단일 writer worker, OS 잠금, 읽기 전용 이력 조회와 offline Factory Reset.
- [x] S03: 가상 CMMT-AS/ST 20개 OD 저장·복원 및 기존 param_save API의 비동기 완료 응답 연결.
- [x] S04: 지연/실패/손상 주입, Mock PDO 지속 처리, 실제 TCP 연결 및 서버 재기동 복원 자동 검증.
- [x] 사용자 수동 확인 및 1차 범위 완료 승인.
- 실제 패키지 실행 확인은 RF-006에서 추적한다. CPX/AP/IOL 실제 저장 연결은 후속 범위다.

검증 결과: `python -B -m scripts.run_tests --profile unit` 603개 통과.
`python -B -m unittest tests.test_virtual_parameter_store_tcp` 1개 통과.
후자는 0.5초 디스크 지연 주입 중 별도 client 상태 응답·연결 유지와 서버 재기동 복원을 검증했다.
Windows 주기 성능 보증 시험이 아닌 기능 검증이며 Node-RED/실장비 시험은 제외했다.

### 동작 경계

- DB 파일 작업은 전용 worker 한 개에서 직렬화한다. 요청 순간 복사한 bytes snapshot을 사용한다.
- 공통 저장 대기열은 실행 중 항목을 포함하여 최대 16개다. 초과 요청은 기다리지 않고 실패한다.
- 가상 CMMT는 저장 중 status를 busy로 유지한다. 동일 장치에 대한 중복 API 저장 요청은 conflict로 거부한다.
- 서버는 응답을 보류하고 다음 루프에서 완료를 확인한다. 기존 request_id를 유지하며 commit 완료 전 Success를 보내지 않는다.
- 가상 저장 완료 대기는 10초로 제한한다. timeout/연결 해제는 이미 접수한 디스크 쓰기를 취소하거나 rollback하는 명령이 아니다.
  응답을 받지 못한 경우 실제 저장 결과는 CLI history/show로 확인한다. 자동 재시도하지 않는다.
- 저장 실패는 장치 저장 결과 및 API Fail로 변환한다. 현재 OD를 이전 저장값으로 되돌리거나 Drive Fault를 생성하지 않는다.
- 실장비 CMMT parameter save 경로는 변경하지 않는다. 비동기 SDO 완료 확인은 Mock 장치에 한정한다.
- Bus close/reconnect 동안 worker와 OS 잠금은 유지한다. 서버의 최종 runtime 폐기 때 접수한 저장을 마친 뒤 잠금을 해제한다.
- 장치 restart는 메모리에 보관한 마지막 commit 값을 복원한다. PDO 경로에서 DB를 다시 읽지 않는다.
- 신규 가상장치 생성은 SQLite 최신 활성 snapshot을 전체 검증 후 적용한다. 저장본 손상은 초기화 실패 상세로 보고한다.
- `device/cmmt/persistent_parameters.py`의 명시적 20개 주소와 버전을 사용한다. Non-PDO 목록에 항목이 추가돼도 저장 범위는 자동 확대하지 않는다.

### 설정 및 CLI 사용

```ini
MOTION_SERVER_VIRTUAL_DEVICE_PARAMETER_STORE_ENABLED=1
MOTION_SERVER_VIRTUAL_DEVICE_PARAMETER_STORE_PATH=C:/MotionServerData/virtual-parameters.sqlite
MOTION_SERVER_VIRTUAL_DEVICE_STORAGE_IDS=0:gantry_x,1:gantry_y
```

위 slave index는 실제 사용 중인 mock BUS에 맞춰 지정한다. 기존 `system/axis/param_save`로 저장한다.
아래 CLI는 `--path`에 명시한 파일을 직접 사용하며 서버를 시작하지 않는다.

```powershell
python -m motion_server parameter-store --path C:/MotionServerData/virtual-parameters.sqlite list
python -m motion_server parameter-store --path C:/MotionServerData/virtual-parameters.sqlite --json history --storage-id gantry_x
python -m motion_server parameter-store --path C:/MotionServerData/virtual-parameters.sqlite show --storage-id gantry_x --revision 1
# 해당 저장소를 사용하는 서버를 종료한 후 실행
python -m motion_server parameter-store --path C:/MotionServerData/virtual-parameters.sqlite factory-reset --storage-id gantry_x
```

Windows 패키지는 `python -m motion_server` 대신 `motion_server.exe`를 사용한다. CLI 진입 경로는 연결했으나
실제 패키지 재빌드/실행 검증은 아직 수행하지 않았다. Docker에서는 SQLite 파일과 WAL/잠금 파일을 함께 유지하도록 부모 폴더를 volume으로 연결한다.

### 수동 확인 절차

1. 별도 mock 설정에서 저장소를 활성화하고 가상축 Profile acceleration 등 저장 대상 값을 바꾼다.
2. Axis Panel에서 Parameter Save 성공을 확인하고 CLI history에서 revision을 조회한다.
3. 서버를 재기동하여 값이 유지되는지 확인한다. 저장하지 않은 변경 및 Profile velocity 0x6081은 복원 대상이 아니다.
4. 동일 값으로 재저장하여 revision이 늘지 않는지 확인한다.
5. 서버 종료 후 Factory Reset을 실행하고, 재기동 시 현재 preset 기본값으로 초기화되며 과거 이력이 남는지 확인한다.

## 수동 확인 및 완료 — 2026-11-24

- 사용자 보고: CLI history를 이용한 동일 값 재저장/revision 확인 완료.
- 사용자 보고: Factory Reset 정상 동작 확인 완료.
- 위 수동 확인과 기존 자동 검증 결과를 근거로 사용자 지시에 따라 RF-017 1차 범위를 complete로 변경했다.
- 수동 확인은 사용자 수행 결과이며, 모든 제안 시험 항목이나 패키지 EXE 검증을 수행했다고 확대 기록하지 않는다.
- RF-017 반영 패키지의 재빌드/실행 및 CLI 검증은 아직 미수행이며 RF-006의 배포 통합 검증에 포함한다.
- CPX/AP/IOL 실제 영구 저장 연결과 실장비 파라미터 이전은 이번 완료 범위에 포함하지 않는다.

### 후속 Windows 패키지 검증 — 2026-11-24

- RF-011 실제 서비스 시험에서 영구 저장이 포함된 패키지를 LocalSystem으로 실행했다.
- Mock 가상축 0x6083=2233 변경과 param_save 성공, 서비스 재기동 후 동일 값 복원을 확인했다.
- 패키지 CLI 전체 명령 및 설치 폴더 변경 시 외부 저장소 재사용 인수까지 수행한 것은 아니다.
- 결과는 [RF-011 검증 기록](../../validation/2026-11-24-rf011-review.md)의 추가 장애·권한 검증에 포함한다.
