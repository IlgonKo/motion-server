# Motion Server 설치 매뉴얼

개정 2.0 · 2026-11-24 · Windows 패키지 및 Linux Docker

설치 후 Basic mode로 서버를 기동하고 Panel에서 상태를 확인하는 절차다.
실장비 설치·commissioning 및 실제 배선에 맞는 서버 설정은 사용자 책임이다.
먼저 mock에서 배포 구성을 확인한 다음 실장치 설정으로 전환한다.
ROS/ROS2와 MoveIt은 설치하지 않는다. 기존 Rev. 1.0 Word 문서는 현행 설치 기준으로 사용하지 않는다.

## 설정 파일과 공통 규칙

소스/Linux에서는 루트 `.env`와 `device/cmmt/.env`, `device/cpx_ap_i_ec/.env`를 사용한다.
Windows 패키지는 같은 문법의 `config.txt`를 해당 위치에 둔다. 모든 장치 파일이 필요한 것은 아니며
BUS에서 선택한 profile의 파일을 준비한다. 예제 파일을 복사한 뒤 실제 구성에 맞게 수정한다.

장치 기본값보다 프로젝트 공통 설정이 우선하며, 지원 프로세스 환경변수와 CLI override가 추가로
우선한다. 두 환경의 이름·단위·값 의미는 동일하다. Windows NIC는 NPF device 경로이고 Linux는
`enp1s0` 같은 interface 이름이다. CPUSET은 실제 허용 CPU에 맞추며 모르면 빈 값 또는 `all`을 사용한다.

`MOTION_SERVER_BACKEND`는 `mock` 또는 `pysoem`이다. `MOTION_SERVER_BUS`는 물리 slave 순서로
선언한다. CPX 내부 모듈 slot과 전체 EtherCAT slave index를 혼동하지 않는다.
Windows와 Linux에서 실제 값이 다른 NIC·IP·장치 수를 그대로 복사하지 않는다.

## Windows 패키지 설치

1. `Motion Server` 폴더 전체를 압축 해제한다. EXE만 다른 폴더로 복사하지 않는다.
2. 루트와 필요한 device 폴더의 `config.example.txt`를 `config.txt`로 복사한다.
3. Panel별 `Tools/.../config.example.txt`를 `config.txt`로 복사해 Host/Port를 설정한다.
4. Mock 최초 확인에는 아래 구성을 사용한다. 시험 포트는 운영 서버와 다른 값으로 정한다.

루트 `config.txt` 예시:

```text
MOTION_SERVER_BACKEND=mock
MOTION_SERVER_MODE=basic
MOTION_SERVER_BUS=0:axis:cmmt-as
MOTION_SERVER_PORT=15001
```

`device/cmmt/config.txt`에는 가상 축 초기값 preset을 지정한다.

```text
MOTION_SERVER_CMMT_SLAVE_NON_PDO_CONFIGURATIONS=0:linear_mm
```

`motion_server.exe` 실행 후 initialization 실패가 없는지 확인한다.
`Tools/axis_control_panel/axis_control_panel.exe`로 같은 포트에 연결한다.
실장치 운전은 Npcap 설치와 EtherCAT NIC 선택 후 backend를 pysoem으로 변경한다.
Npcap installer가 포함되지 않은 배포본이면 별도 설치가 필요하다. 설치 여부를 manifest에서 확인한다.
같은 TCP 포트에 서버 두 개를 실행하지 않는다. 같은 물리 EtherCAT 버스를 두 Master로 제어하지 않는다.

패키지는 Python 설치 없이 실행하도록 구성된다. 개발 PC 시험만으로 새 PC 검증을 대신할 수는 없다.
Windows 자동 서비스와 파일 로그 옵션의 추가 개발은 RF-011에서 관리한다.

## Linux Docker 설치

Docker와 Compose plugin, 설정 합성에 필요한 host Python을 준비한다. 저장소의 requirements를
독립 Python 환경에 설치하고 scripts가 사용하는 `python3`에서 사용할 수 있는지 확인한다.
headless 서버 구동에는 그래픽 환경이 필요 없다. 로컬 Axis/IO Panel에는 Tk와 유효한 DISPLAY가 필요하다.

```bash
cp .env.example .env
cp device/cmmt/.env.example device/cmmt/.env
# CPX를 구성할 때만 추가
cp device/cpx_ap_i_ec/.env.example device/cpx_ap_i_ec/.env
```

각 파일에서 backend, BUS, NIC, port, CPUSET과 가상 CMMT preset을 설정한 뒤 실행한다.

```bash
bash scripts/host/start.sh --build
docker logs --tail 100 motion-server
```

호스트 service를 설치하려면 `sudo bash scripts/host/service.sh install`을 사용한다.
이 service는 Docker 컨테이너를 관리하는 wrapper이며 별도의 native Motion Server를 실행하는 것이 아니다.
수동 container와 service를 중복 운용하지 않는다. 변경 후 재기동·제거 절차는 `scripts/host/service.sh`를 따른다.
Linux NIC에 접근하는 실제 Docker 시험은 별도 장비 환경에서 수행한다.

## ESI와 IODD

CMMT-AS/ST와 CPX ESI 및 기본 IODD는 Windows `_internal/device/...`에 포함된다.
Windows 사용자 IODD는 외부 `device/io_link/iodd`에 저장한다. 외부 파일이 bundled 파일보다 우선 검색된다.
Linux 소스 배포는 `device/io_link/iodd`를 사용한다. 구성된 IODD key가 검색되는지 확인한다.
파일명·vendor/device version과 process-data profile을 임의로 서로 대체하지 않는다.

IO-Link binding은 `<port>:<iodd_key>[:<process_data_profile>]`를 사용한다.
profile은 1부터 시작하는 숫자이며 생략하면 첫 process-data profile을 선택한다.
장치 실제 profile과 서버 decoding profile이 일치해야 한다. 기존 설치의 ESI/IODD 변경 시 별도 회귀 검증한다.

## 시작 실패와 운영 로그

EtherCAT 초기화 실패에서는 TCP가 가능한 경우 degraded 상태를 유지한다.
Axis Panel 초기 화면에서 제어권 요청 후 Bus Reconnect를 사용할 수 있다.
복구 중 Heartbeat timeout으로 연결이 끊길 수 있으므로 새 연결에서 server/bus 상태를 확인한다.

TCP 포트를 열지 못하면 서비스 자체를 제공할 수 없어 상세 로그와 종료 코드 1로 종료한다.
port·stage·errno/winerror를 기록한다. 자동으로 다른 포트로 바꾸지 않는다.
소스/EXE는 콘솔 출력, Docker는 `docker logs`, service wrapper는 `journalctl -u motion-server`를 수집한다.
장치 Fault와 API Fail, initialization 실패를 서로 구분해 기록한다.

## 업그레이드와 인수 확인

기존 프로그램 폴더와 설정을 먼저 보관한다. 새 패키지는 별도 폴더에 풀고 예제와 실제 설정을 비교한다.
이전 버전의 비공개 API나 숫자 문자열 호환성을 가정하지 않는다. Schema와 공식 client를 함께 갱신한다.
동일 포트의 운영 서버를 유지한 채 새 서버를 실행하는 방식으로 업그레이드하지 않는다.

인수 확인은 Mock 기동, Panel 연결, authority, 상태·catalog 조회, 정상 종료 순으로 진행한다.
장치 제어·이동 시험은 실제 구성 및 안전 조건을 확인한 별도 실장치 시험 단계에서 수행한다.
`deployment_validation.md`에서 로컬 자동 검증과 새 Windows/Linux PC의 미검증 항목을 구분한다.
