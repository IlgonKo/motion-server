# DT Demo Linux 신규 환경 설정 — 2026-11-27

## 환경과 범위

- Ubuntu 24.04.4 LTS, festo@192.168.0.128, 저장소 /home/festo/Documents/motion-server.
- 소스 eff4d12, Docker 29.1.3, Compose 2.24.6, container Python 3.12 / PySOEM 1.1.14.
- Mock이 아닌 Soft ESC EtherCAT 연결. enp1s0, pysoem, basic/PP, 10 ms, DC off.
- slave 0~2 CMMT-AS, slave 3 CPX-AP-I-EC io0; slot 1 di:8, slot 2 do:8, PDO index stride 0x0010.
- 로컬 .env와 장치 .env는 예제에서 생성했으며 Git에 포함하지 않는다.
- 기존 Dockerfile/Compose/host start script 사용. 별도 systemd 서비스는 등록하지 않았다.

## 최초 설정 시 직접 확인 결과

- 새 환경 Docker 이미지 빌드와 컨테이너 생성 성공.
- 이미지 manifest list: sha256:9c47853cd9bd4b8147adda016e963ce755dfb5d59a7dcc12265dead586253b85.
- 앞의 CMMT-AS 3개 identity 및 PDO mapping 설정/readback 성공.
- slave 3에서 identity mismatch: CPX expected vendor 0x1D/product 0x007B6451,
  actual vendor 0x1D/product 0x007B1A95(CMMT-AS).
- 서버는 crash/restart 없이 initialization_error/degraded TCP 실행을 유지한다.
- Windows에서 192.168.0.128:15000 system/server/status 조회 성공.
  initialized=false, cause=device_identity_mismatch, SERVER_INITIALIZATION_FAILED Fault 확인.
- 축 Enable/이동 및 DO 출력 명령은 전송하지 않았다. 정상 주기 운전/WKC·I/O 기능은 미검증.

## 사용자 확인 및 종료 판단

- Soft ESC는 최초 서버 설정 당시 아직 구성 전이었다고 사용자가 확인했다.
  위 identity mismatch는 그 시점의 관찰이며 현재 장애로 단정하지 않는다.
- 이후 사용자로부터 새 환경 설정 검증 완료 및 관련 RF/TD 완료 처리 요청을 받았다.
- RF-006/RF-010은 내부용 1.0/DT Demo 범위에서 complete로 처리한다. TD-009/TD-010은 이미 complete이다.
- 소스는 이후 d546fdd로 fast-forward 업데이트했다. 로컬 설정과 검증 기록을 보존했다.
- 이번 종료 시 추가 motion/DO 명령, 재기동 또는 성능 시험을 수행하지 않았다.
  사용자 확인을 자동 시험 결과나 정상 WKC 실측값으로 바꾸어 기록하지 않는다.
- 새 Windows 환경·실제 Festo 장비·upgrade/rollback 등의 확대 인수와 최종 패키지 검증은 별도이다.
