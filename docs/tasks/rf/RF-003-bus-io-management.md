# RF-003 I/O Reset, Restart 및 Parameter Storage API

## 배경

다음 I/O 관리 API name은 예약되어 있으나 장치별 의미와 lifecycle 계약이 확정되지 않았다.

- `system/io/reset`
- `system/io/restart`
- `system/io/param_storage`

`system/bus/rescan`은 현재 Motion Server 운용 모델에서 불필요하므로 RF-003 범위에서 제거한다.
현재 bus topology 복구는 `system/bus/reconnect`, process/runtime 전체 재구성은
`system/server/restart`가 담당한다.

## 선행 결정

- `system/io/reset`은 Motor Drive의 fault reset처럼 I/O 장치의 Fault acknowledge/clear 용도로 사용한다.
  장치가 별도 reset sequence를 지원하지 않거나 필요로 하지 않으면 `UNSUPPORTED_OPERATION`으로 응답한다.
- `system/io/restart`는 축 restart처럼 I/O 장치를 재기동해야 하는 경우를 위한 API로 유지한다.
  장치가 restart sequence를 지원하지 않으면 `UNSUPPORTED_OPERATION`으로 응답한다.
- `system/io/param_storage`는 I/O 장치의 parameter 저장 대상을 설정하는 명령이다.
  CPX-AP-I-EC는 EtherCAT object `0x27F1 Stored Parameters NV`를 사용하여 지원한다.
- RF-017은 RF-003의 `system/io/param_storage`와 별도로 virtual device persistent store와 변경 이력을 다루는
  별도 기능으로 한정한다.

## API 계약

### 공통 계약

- 세 명령 모두 command authority가 필요하다.
- 세 명령 모두 `io` selector를 명시적으로 받는다. 예: `"io": "io0"`
- 연결되지 않은 I/O, 지원하지 않는 device profile, unsupported capability는 Fail response로 반환한다.
- `system/io/reset`과 `system/io/restart`는 bus topology를 다시 scan하지 않는다.
  bus/process image 복구는 `system/bus/reconnect`의 책임이다.
- 실행 중 command가 실패하더라도 서버 process와 TCP server는 유지한다.

### `system/io/reset`

- 의미: 선택한 I/O device의 Fault acknowledge/clear 또는 device reset sequence.
- CPX-AP-I-EC 1차 구현: CPX에서 필요한 reset sequence가 확인되지 않으면
  `UNSUPPORTED_OPERATION`을 반환한다.
- Diagnostic clear는 장치 Fault 조건 해제 여부와 RF-005의 latching 계약을 따른다.

### `system/io/restart`

- 의미: 선택한 I/O device의 재기동 sequence.
- CPX-AP-I-EC 1차 구현: CPX에서 restart sequence가 확인되지 않으면
  `UNSUPPORTED_OPERATION`을 반환한다.
- restart가 지원되는 장치에서도 bus reconnect를 대신하지 않는다.

### `system/io/param_storage`

- 의미: 선택한 I/O device의 parameter 저장 대상을 설정한다.
- 요청 인수:
  - `io`: I/O selector. 예: `"io": "io0"`
  - `mode`: `"volatile"` 또는 `"non_volatile"`
- CPX-AP-I-EC 구현:
  - `mode="volatile"`은 `0x27F1:01 Mode` (`USINT`, rw)에 `0`을 쓴다.
  - `mode="non_volatile"`은 `0x27F1:01 Mode` (`USINT`, rw)에 `1`을 쓴다.
  - `0x27F1:01 Mode` 값은 `0=volatile memory`, `1=non-volatile memory`, `2=factory reset`으로
    취급한다.
  - `Mode=2` factory reset은 이 API에서 절대 사용하지 않는다.
  - 별도 저장 결과 확인 readback은 수행하지 않는다. `0x27F1:01 Mode` write가 성공하면
    `system/io/param_storage` 성공으로 처리한다.
  - 실장치에서는 storage mode 변경 직후 내부 반영 시간이 필요한 것으로 확인했다.
    `mode`를 연속으로 빠르게 변경하면 CPX가 SDO abort `0x08000000` (`General error`)로
    write를 거부할 수 있다. 이는 object/index 오류가 아니라 장치의 일시적 busy/reject로 취급하며,
    운용 시 mode 변경 사이에 짧은 간격을 둔다.
- 이 명령은 현재 parameter snapshot을 Motion Server의 Persistent Parameter Store에 저장하지 않는다.
  서버 측 persistent store, 변경 이력, virtual device 재시작 복원은 RF-017에서 다룬다.

## 구현 범위

- API specification에서 `system/bus/rescan`을 제거한다.
- `system/io/reset`, `system/io/restart`, `system/io/param_storage`의 validation, handler,
  Fail response와 공개 문서를 구현한다.
- CPX-AP-I-EC `system/io/param_storage`는 `0x27F1` 기반으로 구현한다.
- CPX-AP-I-EC에서 reset/restart가 지원되지 않으면 명확한 `UNSUPPORTED_OPERATION` 응답을 제공한다.

## 검증 계획

- authority 없음, 잘못된 `io` selector, unsupported reset/restart, 지원 장치의 param save 성공/실패를
  자동 테스트한다.
  - CPX-AP-I-EC 실장치에서 `system/io/param_storage` smoke test를 수행한다.
- unsupported reset/restart가 RuntimeError나 server crash로 이어지지 않는지 확인한다.

## 완료 증거

- 구현:
  - `system/bus/rescan`을 API specification과 command registry에서 제거했다.
  - `system/io/reset`과 `system/io/restart`는 device capability가 없으면 `UNSUPPORTED_OPERATION`을
    반환한다.
  - CPX-AP-I-EC는 `IO_PARAMETER_STORAGE` capability를 선언하고 `system/io/param_storage`에서
    `0x27F1:01 Mode=0/1`을 write하여 volatile/non-volatile storage mode로 설정한다.
  - `system/io/param_storage`는 transport가 필요하므로 bus disconnected 상태에서는 API 경계에서 거부된다.
- 자동 테스트:
  - `python -m unittest discover -s tests`: 428 tests OK
- 실장치 확인:
  - CPX-AP-I-EC에서 `system/io/param_storage`의 `volatile`/`non_volatile` mode write 동작을 확인했다.
  - mode를 연속으로 빠르게 변경하면 장치가 `DeviceRejectedException`
    (`operation=sdo_write`, `device_code=134217728` / `0x08000000`)으로 거부할 수 있음을 확인했다.
