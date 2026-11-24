# 배포 인수 검증

2026-11-24 검증 기준. 로컬 개발 PC의 성공과 새 Windows/Linux PC에서의 인수 완료를 구분한다.

Windows에서는 CSP를 포함한 동기 제어를 공식 지원하지 않는다(DEC-057).
Windows 인수는 기능 동작 검증이며 cycle 주기 성능·jitter 검증은 제외한다.
Mock 시험 주기와 CI 통과를 실제 장치의 실시간 성능 보증으로 사용하지 않는다.

## 자동 검증

```text
python -B -m scripts.check_api_docs
python -B -m scripts.run_tests --profile unit --report reports/unit.json
python -B -m scripts.run_tests --profile integration --report reports/integration.json
```

unit은 설정·ESI/IODD·PDO·API·Virtual 장치 및 Panel 회귀를 포함한다.
integration은 별도 임시 폴더·임시 포트의 mock 서버로 TCP/시퀀스·GUI·오류 주입을 확인한다.
운영 서버/실제 NIC에는 접근하지 않는다. Node-RED 테스트는 수행하지 않는다.
Linux의 Tk 검증은 `xvfb-run -a`로 실행한다. hardware profile은 위 suite와 분리한다.
보고서에는 Python/OS, 모듈, 테스트 수, 개별 소요 시간, 실패 traceback 및 skip 사유가 포함된다.

## Windows artifact

```powershell
pwsh -File scripts/windows/build_exe.ps1 -SkipLocalEnv -SkipNpcapDownload -PackageDirectory '<새 검증 폴더>'
python -B -m scripts.validate_package '<새 검증 폴더>'
```

기존 배포 폴더 대신 존재하지 않는 별도 경로를 사용한다. `SkipLocalEnv`는 운영 설정 유출을 막고,
`SkipNpcapDownload`는 driver installer를 제외한다. 실장비 배포 전 Npcap 준비를 별도로 확인한다.
manifest는 source commit, 미커밋 변경 여부, 경로·크기·SHA256과 누락 항목을 기록한다.
Node-RED package/flow는 존재 여부만 확인하며 실행 시험하지 않는다.

최신 매뉴얼은 Markdown/DOCX/PDF Rev. 2.0이며 `Manual`에 API 문서와 함께 포함한다.
사용자/설치 매뉴얼 각 3페이지의 DOCX→PDF 렌더 검증을 완료했다.
이 검증은 신규 PC 설치 및 실제 장비 인수를 대체하지 않는다.

## 새 환경 인수 체크리스트

상태: `pending`. 사용자 결정에 따라 DT Demo 제작 시 Windows/Linux 환경 인수를 함께 수행한다.
기존 자동 검증 및 DOCX/PDF 렌더 검증 결과는 유지하며, 아래 인수 항목은 아직 완료되지 않았다.

| 환경 | 확인 | 완료 증거 |
| --- | --- | --- |
| Windows | Python 미설치 환경에서 서버/Panel 기동 | OS, artifact hash, 콘솔 및 화면 기록 |
| Windows | Npcap 설치, NIC 선택, 실제 device 발견 | driver/version, server/bus status |
| Linux | Docker image build 및 mock 시작 | image digest, compose 설정, 로그 |
| Linux | 실제 NIC, CMMT/CPX 연결 및 WKC | OS/kernel/driver, 장치 firmware, status |
| 양쪽 | ESI/IODD 및 외부 IODD 선택 | 파일 hash, 선택 key/profile, 조회 결과 |
| 양쪽 | 잘못된 설정·누락 catalog·port 점유 | stage/cause/detail 및 종료 결과 |
| 양쪽 | 설정 보존 upgrade와 rollback | 이전/새 version, 실제 설정 비교 |

모든 행의 증거가 있어야 RF-006의 clean-system 인수를 완료한다. 운영 하드웨어의 이동 시험은
사용자와 축·경로·속도를 확정한 별도 절차로 수행하며 자동 CI에서 실행하지 않는다.

## 명시적 hardware 조회 profile

사용자가 정상 기동한 서버를 대상으로 아래 명령을 명시적으로 실행한다.
이 profile은 status만 조회하며 authority 요청, fault-reset, reconnect, enable 또는 motion을 전송하지 않는다.

```text
python -B -m scripts.hardware_status_check --host <서버IP> --port 15000 --report reports/hardware-status.json
```

status 통과는 실제 이동·정지·Homing·I/O 동작 시험을 대체하지 않는다.
기존 `diagnostics/pysoem_single_axis_smoke_test.py`는 과거 내부 API 기반 도구이므로 현행 인수 절차에 사용하지 않는다.

## Windows 서비스 인수

[서비스 및 파일 로그 안내](windows_service.md)에 따라 별도 시험 환경에서 등록·교체,
수동 시작/중지, LocalSystem 접근, 재부팅 및 장애 복구를 확인한다. 등록 스크립트는
자동 시작·중지를 수행하지 않는다. 현재 이 실제 서비스 인수는 미완료이며,
WinSW 시험 모드의 Mock 실행 결과로 대체하지 않는다.
`system/server/restart` 서비스 연동은 TD-042 구현 후 별도로 검증한다.
