# RF-006 배포 구성 최종 검증

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
- 새 Linux PC에서 Docker 설치, EtherCAT NIC 설정, startup와 Basic mode smoke test를 수행한다.
- 누락 catalog, 잘못된 설정과 upgrade scenario를 확인한다.

## 완료 증거

완료 시 artifact manifest, 환경별 checklist와 clean-system 시험 결과를 기록한다.

## 2026-11-24 진행 결과

- 상태: `in_progress`.
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

- 상세 검증 기록: [2026-11-24 배포 준비 검증](../../validation/2026-11-24-release-readiness.md)
