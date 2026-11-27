# RF-010 사용자 문서 최신화

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

사용자 및 설치 매뉴얼을 최신 Motion Server, Control Panel, device profile과 Remote I/O 동작에 맞춘다.

## 구현 범위

- User Manual에 최신 API namespace, authority, axis/I/O feedback, parameter access와 Basic mode를 반영한다.
- Installation Manual에 Windows package와 Linux Docker 설치 및 설정 절차를 반영한다.
- `config.txt`/`.env`, ESI/IODD 배치, startup, log와 기본 troubleshooting을 설명한다.
- 문서 파일명, 내부 링크, version과 packaging 포함 규칙을 정리한다.

## 범위 제외

개발자용 상세 내부 구조는 architecture 문서에서 유지하고 사용자 매뉴얼에 중복하지 않는다.

## 검증 계획

- 최신 API/configuration과 문서 항목을 대조한다.
- Windows/Linux에서 문서만 사용해 Basic mode 설치와 smoke test를 수행한다.
- 최종 DOCX/PDF는 rendering 후 페이지 잘림, 표, 이미지와 링크를 확인한다.

## 완료 증거

완료 시 문서 version, review checklist, rendering 결과와 신규 환경 재현 기록을 추가한다.

## 2026-11-24 진행 결과

- 상태: `pending`.
- 재개 시점: DT Demo 제작 시 새 Windows/Linux 환경 인수를 함께 검증한다. 완료된 검증 결과는 유지한다.
- 사용자/설치 매뉴얼 Markdown Rev. 2.0을 작성했다. 현행 API, authority, feedback,
  parameter storage, Diagnostic/recovery, Windows/Linux 설정과 ESI/IODD 경계를 반영했다.
- 기존 Word Rev. 1.0은 최신 Markdown 기반 DOCX Rev. 2.0으로 교체했다. 이전 판은 Git 이력에 남는다.
  Markdown/DOCX/PDF와 API/배포 검증 문서를 package Manual에 포함하도록 변경했다.
- API 예제/명령 자동 검사는 TD-009로 연결했다. 개발 PC의 패키지 mock smoke는 통과했다.
- DOCX/PDF 제작·렌더 확인 완료: 사용자/설치 매뉴얼 각 3페이지, 총 6페이지를 이미지로 검토했다.
  한글 글꼴, 코드 예시, 페이지 번호와 페이지 경계를 확인하고 제목 스타일 및 코드 설명 분리를 수정했다.
  Markdown→DOCX 내용 일치 검사 및 PDF 추출 내용 대조를 수행했다.
- 미완료: 새 Windows/Linux 환경에서 문서만으로 설치하는 인수 검증. DT Demo 제작 시 검증할 때까지 `pending`으로 둔다.

- 상세 검증 기록: [2026-11-24 배포 준비 검증](../../validation/2026-11-24-release-readiness.md)
