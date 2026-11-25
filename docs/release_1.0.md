# Motion Server 1.0 — 내부·DT Demo 배포

## 마무리 상태

2026-11-25 내부용 1.0 개발을 마무리한다. `v1.0.0`은 내부 개발 기준 소스 태그이며,
최종 배포 패키지 검증 또는 고객 환경 인수 완료를 의미하지 않는다.
이후 DT Demo에서 발견되는 문제는 1.0 후속 수정으로 관리한다.

## 배포 범위

2026-11-25 사용자 결정: 1.0은 내부·DT Demo용이다. 고객 환경 인수가 완료된
배포로 표시하지 않는다. RF-006/RF-010의 새 Windows/Linux 환경 인수는 DT Demo
제작 시 진행하며 pending을 유지한다.

- Windows: 기존 실행 파일, Control Panel, 설정 예제, 카탈로그와 서비스 등록 스크립트.
- Linux: 소스와 기존 Docker 구성. 현재 구성은 소스를 mount하는 방식이며 독립 이미지가 아니다.
- Windows CSP를 포함한 동기 제어 및 주기 성능은 공식 지원 범위 밖이다(DEC-057).
- Gamepad 향후 개발은 DT Demo 영역이며 기존 코드/패키지는 유지한다.
- AI sequence의 독립 생성 평가는 RF-019에서 계속 관리하며 1.0 완료 기능으로 표시하지 않는다.

## 최근 반영된 동작

- RF-011: 선택적 파일 로그, Windows 서비스 등록. 서비스 실행/중지는 사용자 담당.
- RF-017: 가상 CMMT 파라미터의 비동기 영구 저장·이력·복원과 오프라인 Factory Reset.
  실장비 snapshot/파라미터 이전 및 CPX/AP/IOL 저장 확장은 포함하지 않는다.
- TD-042: `system/server/restart`는 PID를 유지하며 설정과 서버 세션을 재생성한다.
  TCP/제어권은 해제되며 자동 복구하지 않는다. 실행 파일 교체에는 외부 재시작이 필요하다.

## 빌드 및 검증

- 제품 버전 원본은 `motion_server/version.py`. `--version`으로 확인한다.
- 기존 출력 폴더에는 빌드하지 않는다. 새 `-PackageDirectory`를 지정한다.
  기존 config.txt, IODD, SQLite와 로그는 자동 삭제하지 않는다.
- `build-info.json`은 빌드 시작 시 버전·커밋·변경 여부·Python·설치 의존성을 기록한다.
  빌드 중 추적 소스 변경은 실패 처리한다. 검증 도구가 다른 커밋으로 정보를 덮어쓰지 않는다.
- `artifact-manifest.json`은 검증 시점의 파일 SHA256과 원래 빌드 정보를 담는다.
- 최종 배포용은 clean commit에서 `-SkipLocalEnv`로 빌드하며 시험 데이터·로컬 설정을 포함하지 않는다.
- Windows 직접 빌드 의존성은 `requirements-build.txt`에 검증 환경 버전으로 고정한다.
  전이 의존성 전체 고정이나 Linux 환경 검증을 의미하지 않으며 실제 설치 목록은 build-info에 남긴다.

## 남은 배포 준비

- 최종 빌드 환경 기록과 Linux 의존성 재현 범위 확인.
- 사용자/설치 DOCX·PDF의 최신 기능 반영과 렌더 검증.
- clean commit 기반 최종 패키지 생성·검사·실행 시험 및 배포 파일 checksum.
- 최종 패키지 검증 후 배포 산출물 확정. 내부 개발 기준 태그와 패키지 검증 완료를 구분한다.
- 새 환경 인수, 재부팅 시험, Windows 동기 성능 시험은 이번 검증 완료로 기록하지 않는다.
