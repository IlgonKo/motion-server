# RF-010 사용자 문서 최신화

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

- 상태: `in_progress`.
- 사용자/설치 매뉴얼 Markdown Rev. 2.0을 작성했다. 현행 API, authority, feedback,
  parameter storage, Diagnostic/recovery, Windows/Linux 설정과 ESI/IODD 경계를 반영했다.
- 기존 Word Rev. 1.0에는 폐기된 API가 광범위하게 남아 있어 이력으로 보존하고 패키지 복사에서 제외했다.
  최신 Markdown 매뉴얼과 API/배포 검증 문서를 package Manual에 포함한다.
- API 예제/명령 자동 검사는 TD-009로 연결했다. 개발 PC의 패키지 mock smoke는 통과했다.
- 미완료: 최신 DOCX/PDF 생성·렌더 확인(현재 Word/LibreOffice 없음), 새 Windows/Linux 환경에서
  문서만으로 설치하는 인수 검증. 기존 DOCX를 최신판으로 표시하지 않는다.

- 상세 검증 기록: [2026-11-24 배포 준비 검증](../../validation/2026-11-24-release-readiness.md)
