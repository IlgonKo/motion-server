# TD-009 API 문서와 구현 정합성

- 상태: `complete`
- 검증일: 2026-11-24

## 확정 범위

JSON Schema를 API 계약 원본으로 유지하고 specification·handler registry·공개 문서 목록을 비교한다.
서버 동작을 확장하거나 legacy 입력을 허용하지 않는다. 문서 검증은 네트워크 명령을 전송하지 않는다.

## 구현 및 결과

- `scripts/check_api_docs.py`가 57개 공개 command의 Schema/registry/문서 집합을 비교한다.
- JSON 예제 59개를 parse하고 request와 response를 실제 Schema로 검사한다.
- 오래된 ok/command_rejected 응답, 숫자 문자열 입력, axis status 및 AP response를 현행 형식으로 수정했다.
- Axis parameter catalog 누락, server status의 축 수 설명, authority/Heartbeat client 예제를 수정했다.
- README/architecture의 CMMT PRE-OP PDO mapping 기록과 CPX mapping 검증 정책을 실제 구현에 맞췄다.
- 문서 명령 삭제/미지원 명령 삽입과 숫자 문자열 예제 주입 시 실패하는 음성 테스트를 추가했다.
- CI workflow에서 동일 검사를 실행한다. 로컬 검사 및 테스트는 통과했으며 원격 CI 실행 증거는 TD-010에서 추적한다.

## 남은 범위와 연결

사용자 매뉴얼 갱신은 RF-010, 새 OS 배포 인수는 RF-006에서 관리한다.
Node-RED 테스트와 실장비 조작은 수행하지 않았다.

- 상세 검증 기록: [2026-11-24 배포 준비 검증](../../validation/2026-11-24-release-readiness.md)
