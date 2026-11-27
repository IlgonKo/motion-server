# RF-006 배포 구성 최종 검증

## 현재 상태 — 2026-11-27

- 상태: `complete`.
- 사용자 보고: “새로운 환경에서 설정 검증이 되었음.” 완료 처리 요청에 따라 내부용 1.0/DT Demo 범위에서 종료한다.
- 증거: 기존 패키지/문서 검증 기록과 [DT Demo Linux 신규 환경 기록](../../validation/2026-11-27-dt-demo-linux-setup.md).
- 직접 확인: 새 Ubuntu 환경의 Git/설정 구성, Docker 이미지 빌드·컨테이너 기동, 실제 NIC 사용,
  Windows에서 원격 TCP 상태 조회. 이후 설정 검증 완료는 사용자 확인으로 기록한다.
- 이전 identity mismatch는 Soft ESC 설정 전 관찰이며 Motion Server 배포 설정 결함으로 확정하지 않는다.
- 이번 완료는 새 Windows PC, 실제 Festo 장비 운전, 모든 ESI/IODD 선택 조합,
  upgrade/rollback 및 모든 저장소 CLI 시나리오의 신규 검증 완료를 뜻하지 않는다.
  해당 확대 인수는 필요 시 후속 배포 검증으로 수행한다.
- 후속 Markdown 변경의 DOCX/PDF 재생성과 최종 배포 패키지 검증은 release_1.0의 잔여 작업으로 유지한다.
- 아래 2026-11-24 pending/미완료 내용은 당시 이력이며 현재 상태와 구분한다.


## 목표

새로운 Windows와 Linux system에서 배포 artifact와 설치 문서만으로 Basic mode를 재현한다.

## 구현 범위

- Windows package의 Motion Server, Axis/IO Control Panel, tools와 manual 포함 내용을 검증한다.
- Linux Docker `.env`와 Windows `config.txt`의 지원 설정을 비교한다.
- CMMT-AS/ST, CPX-AP-I-EC ESI와 IODD의 포함, 검색 및 version 선택 규칙을 확정한다.
- package version, log 위치와 진단 정보 수집 방법을 확인한다.

## 기술 제약

개발 PC의 기존 Python, Docker image, environment와 cached catalog에 의존하지 않는 clean-system 검증이 필요하다.

## 검증 계획

- 새 Windows PC에서 설치, NIC 선택, startup와 Basic mode smoke test를 수행한다.
- Windows CSP/동기 제어는 공식 미지원이며 cycle 주기 성능·jitter 검증을 제외한다(DEC-057).
- 새 Linux PC에서 Docker 설치, EtherCAT NIC 설정, startup와 Basic mode smoke test를 수행한다.
- 누락 catalog, 잘못된 설정과 upgrade scenario를 확인한다.

## 완료 증거

완료 시 artifact manifest, 환경별 checklist와 clean-system 시험 결과를 기록한다.

## 2026-11-24 진행 결과

- 상태: `pending`.
- 재개 시점: DT Demo 제작 시 새 Windows/Linux 환경 인수를 함께 검증한다. 완료된 검증 결과는 유지한다.
- 운영 배포 폴더를 덮어쓰지 않고 별도 경로에 Windows EXE 4종을 빌드했다.
  `SkipLocalEnv`/`SkipNpcapDownload`를 사용했으므로 사용자 설정과 Npcap installer는 제외했다.
- 최신 Markdown 매뉴얼/API 문서, 설정 예제, ESI/IODD, 외부 IODD 폴더,
  Python AI Reference 및 Node-RED reference/flow 파일을 포함한다.
- `scripts.validate_package`가 필수 artifact와 SHA256 manifest를 기록한다.
  Node-RED는 파일 포함만 검사하며 실행하지 않는다.
- 패키지 EXE를 별도 임시 설정·포트로 실행해 실제 TCP mock 이동 시퀀스 1개 통과.
- `docs/deployment_validation.md`에 환경별 인수 조건, hardware status profile,
  version/log/설정 차이 및 upgrade 확인 절차를 작성했다.
- 미완료: 새 Windows PC의 Python 미설치 실행·Npcap·NIC/실장비, 새 Linux Docker/실제 NIC,
  catalog 선택과 upgrade/rollback 인수. 현재 Docker client는 있으나 daemon 연결이 실패한다.
  운영 서버 재시작, 실제 축 이동 및 OS/service 설치 변경은 하지 않았다.

- RF-017 완료 후 추가 확인: 영구 저장이 포함된 패키지 재빌드, `motion_server.exe parameter-store`의
  history/show/factory-reset 실행, 재기동 복원 및 패키지 폴더 변경 후 외부 저장소 재사용을 확인한다.
  RF-017의 소스/Mock 자동 검증 및 사용자 수동 확인과 구분하며 아직 패키지 검증 완료로 기록하지 않는다.

- 상세 검증 기록: [2026-11-24 배포 준비 검증](../../validation/2026-11-24-release-readiness.md)

- 후속 RF-011 서비스 인수에서 RF-017 포함 패키지 재빌드 및 LocalSystem Mock param_save/재기동 복원을 확인했다. 위 추가 항목 중 CLI 전체 명령·폴더 변경/외부 저장소 재사용은 계속 별도 인수 대상으로 둔다.
