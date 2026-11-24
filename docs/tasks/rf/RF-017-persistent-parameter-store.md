# RF-017 Persistent Device Parameter Store

- 등록일: 2026-09-04
- 상태: `planned`
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
- 1차 구현은 별도 worker 없는 동기 저장을 우선한다. 성공은 commit 완료 후 반환한다.
  구현 전 Model_Update/PDO 주기 경로와 저장 지연 영향을 확인하고 주기를 막는 구조라면 근거를 제시하여 비동기 방식을 재논의한다.
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
- 저장 지연과 Model_Update/PDO 주기 영향을 확인한다. 동기 저장이 주기를 막는 구조라면 근거와 함께 재논의한다.
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
