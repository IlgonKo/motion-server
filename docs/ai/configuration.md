# 설정을 읽고 시퀀스 대상을 정하는 방법

서버의 설정과 정상 기동은 사용자 책임이다. AI는 설정을 변경하거나 대신 commissioning하지 않는다. 파일이 없는 경우 예제 파일을 실제 설정으로 간주하지 않는다.

## 제공받을 파일

- 소스 실행: 프로젝트 루트 `.env`, 선택 장치의 `device/cmmt/.env`, `device/cpx_ap_i_ec/.env` 등 실제 사용 파일.
- Windows 패키지: 루트 `config.txt`, `device/cmmt/config.txt`, `device/cpx_ap_i_ec/config.txt` 등. 패키지는 `.env`와 다른 별도 문법이 아니라 동일 설정의 파일명 변형을 사용한다.
- 다른 device config root/파일명을 지정한 실행이라면 그 실제 경로와 시작 인수를 제공받는다.
- Control Panel 설정은 서버의 장치 구성 원본이 아니다. GUI host/port를 서버 장치 설정으로 혼동하지 않는다.

설정 parser는 [file_parser.py](../../configuration/file_parser.py), 합성은 [loader.py](../../configuration/loader.py), typed 모델은 [models.py](../../configuration/models.py), 최종 구성은 [builder.py](../../configuration/builder.py)를 따른다. 문법 예시는 [공통 예제](../../.env.example), [CMMT 예제](../../device/cmmt/.env.example), [CPX 예제](../../device/cpx_ap_i_ec/.env.example)를 참조하되 사용자 파일을 덮어쓰지 않는다.

## 우선순위

동일 키는 **장치 파일 기본값 < 프로젝트 공통 파일 < 인식되는 프로세스 환경변수** 순으로 우선한다. 지원되는 CLI override는 최종 구성에 적용되며 bus override는 장치 파일 선택에도 영향을 준다. `MOTION_SERVER_DEVICE_CONFIG_ROOT`로 장치 파일 위치가 달라질 수 있다. 파일만으로 실행 환경/CLI override를 알 수 없다면 사용자에게 확인하고, 임의의 우선순위 parser를 새로 만들지 않는다.

`config.txt`와 `.env`를 동시에 읽고 임의 병합하지 않는다. 실제 시작 방식에서 선택한 파일 묶음을 사용한다. 현재 서버 조회와 파일이 다르면 사용자에게 확인한다. 조회 API는 필요할 때 단위·현재 상태를 보완하는 수단이며 설정 파일 대신 별도 시스템 구성 파일을 생성할 필요는 없다.

## 축과 I/O 식별

- `MOTION_SERVER_BUS`는 물리 slave 순서다. **axis index와 slave index는 다르다.** 중간 IO slave가 있으면 axis 1을 slave 1로 해석하면 안 된다. 축 API에는 axis index를 사용한다.
- X/Y/Z/Rotation은 사용자 시퀀스 역할이다. 설정만으로 axis 0=X라고 단정하지 않는다. 역할 → axis index 표를 사용자와 확정한다.
- IO는 설정된 `io0` 등의 ID와 AP **slot**, 그 모듈 내부 channel로 지정한다. CPX slot 0은 EC interface, AP 모듈은 slot 1부터다. IO-Link port와 AP slot을 혼동하지 않는다.
- `MOTION_SERVER_IO_<id>_MODULES`에서 모듈 종류·채널 수를 확인하고 실제 slot 번호를 기준으로 정리한다. IO-Link binding/profile이 있으면 해당 설정과 IODD를 확인한다. 숫자 profile을 임의 이름으로 교체하지 않는다.
- [Feedback Schema](../../motion_server/api/schema/system.json)의 축 배열은 axis index로 접근한다. IO는 `io.devices`의 `id`, `modules`의 `slot`으로 찾고 모듈의 `inputs`/`outputs` 내 channel에 접근한다. 첫 번째 IO/모듈을 무조건 선택하지 않는다.

## 단위와 프로그램 설정

축의 API 위치 단위와 속도 단위는 해당 장치/축 metadata로 확인한다. 물리 단위를 count로 임의 환산하거나 모든 축을 mm로 간주하지 않는다. DI/DO는 Boolean, AI/AO는 기본적으로 PDO raw 정수다. 사용자 지정 센서 환산이 없으면 raw 값을 온도/압력 등으로 해석하지 않는다.

시퀀스 파일에는 역할 매핑, 목표 위치, 단계별 이동 속도, **시퀀스 공통 가감속**, 입력 조건과 timeout, 종료 시 출력 정책을 둔다. 이는 서버의 `.env`/`config.txt`를 수정하는 것이 아니다. Teaching 포인트에는 역할별 위치와 단위를 저장하고, 역할 매핑과 속도는 별도 시퀀스 설정에 둔다.

작성 전에 다음 표를 실제 자료로 채운다. 미확인 항목은 추측하지 않는다.

| 항목 | 확인할 내용 |
| --- | --- |
| 접속 | 사용자가 정상 기동한 서버 주소/port |
| 축 | 역할, axis index, 장치 종류, API 단위 |
| IO | io ID, slot, kind, channel/port, raw 단위 |
| 동작 | 위치·속도, 공통 가감속, 이동 경로/중간점 |
| 종료 | 정상/중단/실패 시 출력 유지 또는 명시적 변경 |

문서의 예제 좌표·속도·채널은 설명용이다. 실장비에 안전한 경로/값이라는 보장이 없으며 사용자가 확인해야 한다.
