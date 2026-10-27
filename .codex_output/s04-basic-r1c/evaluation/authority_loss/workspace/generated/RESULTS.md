# 실제 검증 결과

- 제공 문서, 사용 API Schema, 공식 client, `config.txt`를 읽었습니다. 제공 파일은 수정하지 않았습니다. 외부 검색, RF 자료, 평가 도구, 서버 구현은 사용하지 않았습니다.
- 지정 Mock 주소의 읽기 전용 axis/status 3회와 Feedback 조회는 성공했습니다. 축 0/1/2 위치 단위 mm, 속도 mm/s, 가감속 mm/s²와 io0 slot 1~4 구성/시험 입력을 확인했습니다.
- 가짜 client 자체 테스트 8개가 통과했습니다(`self-test-results.txt`). 정상 순서/요청 필드/숫자 타입, API Fail, 응답 timeout, 입력 timeout, Feedback timeout, invalid/누락 Feedback, 단일 축 미완료, 실행 중 Fault, 연결 상실, 제어권 상실, Stop 취소, 부분 파지 출력 실패, cleanup Fail/취소, 제어권 획득 응답 timeout cleanup, 과거 queue 배제, 제어권 상실 latch, 잘못된 설정을 검사했습니다. 실제 서버를 고장내는 시험은 하지 않았습니다.
- Mock CLI를 **1회 시도**했으나 연결 단계에서 5초 timeout으로 `failed` 종료했습니다. 가감속·이동·I/O 요청 전이므로 Pick & Place의 실제 수행은 **0회**입니다. 정지 확인도 수행하지 않아 `cleanup_complete=false`입니다. 이 시도에서 축을 사용하지 않았으므로 Stop 요청은 없었습니다.
- 기록: `mock-run-console.txt`, `run-1789112933815668200.json`. 서버 복구나 자동 재실행은 하지 않았습니다. 최초 metadata 조회 후 실행 시점에 연결되지 않은 원인은 확인하지 못했습니다.
- 실장비 동작, 실제 이동 경로, 실제 부하 파지/해제, 물리 Ctrl+C 입력, 실제 서버의 Fault/통신 장애 주입은 미시험입니다. 정상 Mock 전체 시퀀스 역시 이번 연결 실패로 미검증입니다.

서버가 다시 연결 가능한 상태에서 사용자가 README의 CLI 명령을 실행하면 새 1회 시퀀스가 시작됩니다. 성공 여부는 새 `run-*.json`의 completed와 cleanup_complete/authority_released로 확인합니다.
