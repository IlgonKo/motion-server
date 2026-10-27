# 실제 수행 결과

2026-09-17, 사용자 지정 `127.0.0.1:62554` Mock 서버에서 CLI 1회 실행.
지정 Python 3.14 실행 경로 사용. 프로세스 종료 코드 0.

| 확인 | 결과 |
| --- | --- |
| CLI 결과 | completed |
| 공통 가감속 | axis 0/1/2 각각 profile 요청 1회 Success |
| Pick 실제 위치 | 약 [0.5, 0.6, 0.7] mm |
| Pick 완료 | 세 축 statusword 33831 (0x8427): Target reached, Standstill |
| 파지 출력 | DO=true, AO=100 raw; 각각 요청 Success |
| 파지 입력 AND | DI=true 및 AI=100 raw (>=50), 동일 유효 snapshot |
| Place 실제 위치 | 약 [1.0, 1.1, 1.2] mm |
| Place 완료 | 세 축 statusword 33831, 파지 출력 유지 |
| 정상 정리 | Stop Success + 새 유효 snapshot 세 축 Standstill |
| 최종 출력 | DO=false, AO=0 raw |
| 제어권 | 해제 확인 후 연결 종료 |

전체 수치와 단계별 Feedback는 `last_run.json`에 저장했습니다. 부동소수 표현에 의한
0.49999999999999994 등의 값은 해당 파일에 원문 그대로 남아 있습니다.

실행 뒤 두 방어 처리를 보강했습니다: 입력 대기에서도 필요한 축 statusword 누락 시 진행 금지,
초기화 도중 Stop 정리 실패 시에도 연결/소유권이 남아 있으면 제어권 해제 시도.
보강 후에는 자체 테스트만 수행했고 Mock 이동을 추가 실행하지 않았습니다.

자체 테스트는 정상 명령 순서/Schema 필드 계약, Fail 및 상세 기록, 요청 timeout,
입력/이동/Feedback timeout, Stop 이벤트, Fault, 연결·제어권 상실 및 재접속 후 진행 금지,
출력 유지, cleanup 실패, invalid/누락/과거 자료, 세 축 AND, 동일 snapshot 입력 AND,
설정 snapshot과 숫자/Boolean 구분을 검사합니다. 최종 결과는 `test_results.txt`를 참조하십시오.

실제 Mock에서는 정상 경로만 실행했습니다. 서버 Fault/단절/제어권 탈취/입력 변경을
주입하지 않았으며 해당 실패 경로는 가짜 client 자체 테스트 결과입니다.
Ctrl+C의 OS 신호 전달과 초기화 중 cleanup 실패 시 제어권 해제 보강은 실제 서버에서
시험하지 않았습니다. Stop 이벤트 경로는 자체 테스트했습니다.
실장비 구동, 물리 배선/하중/충돌 경로, GUI/Teaching, 해제 입력 확인은 수행하지 않았습니다.
