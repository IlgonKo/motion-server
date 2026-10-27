# AI 레퍼런스 프로그램: Pick & Place

AI가 기존 Motion Server API를 직접 조합하는 방법을 보여 주는 Python 소스다.
API wrapper/범용 시퀀스 framework가 아니며 서버 설정·commissioning 도구도 아니다.
CLI와 Tkinter GUI 모두 `program.py`의 동일 `Sequence.run()`을 실행한다.

## 먼저 준비할 것

사용자가 서버를 정상 기동하고 실제 `config.txt` / `.env`에서 축과 I/O 구성을 확인해야 한다.
서버 설정은 이 프로그램이 읽어서 변경하지 않는다. [AI 설정 안내](../../../../docs/ai/configuration.md)에 따라
확인한 역할/axis index/단위/io ID/slot/channel을 **이 예제의 `sequence.json`**에 기재한다.
단위는 실제 Axis API 단위를 사용한다. IO analog 값은 PDO raw 정수다.

기본 파일의 axis 0/1/2, IO slot 1=DO / 2=AO / 3=DI / 4=AI는 설명용 가정이며
사용자의 실제 설정과 일치한다는 뜻이 아니다. 좌표·속도·가감속·직선 이동 경로는 안전한 실장비 기본값이 아니다.
실장비 구동 전에 배선·안전 기능·이동 경로와 숫자를 사용자가 검토해야 한다.
Software Stop은 비상정지의 대체물이 아니다. 필요 중간점/접근 경로는 시퀀스 소스를 요구에 맞게 수정한다.

## 설치와 실행

저장소 루트에서 공식 transport client를 설치한다.

```powershell
python -m pip install -e reference_clients/python
cd reference_clients/python
python -m examples.pick_place --help
```

GUI만 열기(연결/제어권/Run은 각각 명시적으로 조작):

```powershell
python -m examples.pick_place --gui
```

사용자가 설정과 동작을 확인한 뒤 CLI 1회 실행:

```powershell
python -m examples.pick_place --run
```

다른 설정 파일은 `--config PATH`, 포인트는 `--points PATH`로 지정한다.
기본 경로는 이 예제 폴더다. 인수 없이 시작하면 실행하지 않는다.
Tkinter는 Python 설치의 Tcl/Tk가 필요하다. 이 예제는 client wheel 내부가 아닌 소스 폴더로 제공한다.
실제 배포 패키지의 포함/독립 실행 검증은 RF-019 S04에서 수행한다.

## 파일별 역할

| 파일 | 역할 |
| --- | --- |
| `program.py` | Feedback 단일 소비자, 일반 대기/취소, Pick & Place API 직접 호출, 포인트 I/O |
| `__main__.py` | CLI 1회 실행 및 GUI 선택 |
| `gui.py` | worker 기반 GUI, 명시적 연결/제어권, Run/Stop, 선택적 Teaching |
| `sequence.json` | 사용자 역할·단위·공통 가감속·단계 속도·IO 조건/출력·timeout |
| `teaching_points.json` | 역할별 위치·단위의 명명 포인트 |

`sequence.json`의 `pick/place.velocities`는 **예제 내부 설정명**이다.
실제 move_abs 요청은 Schema대로 `profile_velocities`를 사용한다. 숫자를 문자열로 전송하지 않는다.

## 실행과 종료 계약

1. 공통 가감속을 profile API로 적용한다(단계마다 바꾸지 않음).
2. Pick 이동 → 모든 축 위치 근접 + Target reached + Standstill 대기.
3. 파지 DO/AO Success → DI/AI 조건을 같은 유효 Feedback에서 모두 확인.
4. Place 이동/대기 → 해제 DO/AO → 선택적 해제 입력 대기.
5. 사용 축 Stop/Standstill 확인 후 완료. 출력은 해제 상태 유지.

위치 허용치 기본 0.5는 해당 축 API 단위다. 입력 조건 `op`는 `eq/ge/le`이며
`release_conditions: []`이면 추가 해제 확인을 하지 않는다.
`failure_outputs: []`이면 중단/실패 시 기존 출력 상태를 유지한다. 자동 파지 해제는 부하 낙하 등을
유발할 수 있으므로 필요한 출력만 사용자가 명시한다.

API Fail, 요청/조건/Feedback timeout, 사용자 Stop, 실행 중 Fault, 연결·제어권 상실이면 다음 단계를 중단한다.
Stop 확인에 실패하면 `failed`와 `Stop NOT confirmed`를 표시하며 완료라고 보고하지 않는다.
I/O cleanup은 지정된 각 출력에 대해 별도 시도하고 실패를 표시한다. 자동 Disable하지 않는다.
Homing/Enable/Fault/limit Run 사전 인터락은 복제하지 않고 서버의 Fail을 처리한다.
실행 중 Fault 감시는 첫 이동 Success 이후의 새 Feedback부터 적용한다.

통신 요청은 이미 전송되었으면 취소할 수 없다. Stop은 pending 요청의 bounded timeout 후 cleanup을 한다.
소프트웨어 응답 지연을 실장비 정지 보장으로 해석하지 않는다.
transport가 재연결하더라도 시퀀스는 재개/재전송/제어권 재획득하지 않는다.
GUI에서는 사용자가 다시 제어권 요청 후 새 Run을 해야 한다. CLI는 제어권 해제 후 종료한다.

Feedback은 명령 ID가 없으며 로컬 수신 번호는 명령의 인과관계를 증명하지 않는다.
명령 Success 이전 snapshot, stale/invalid 자료로 완료 처리하지 않으며 목표 위치도 함께 대조한다.
같은 위치 재명령은 조건이 이미 만족될 수 있다. 자세한 한계는 [시퀀스 가이드](../../../../docs/ai/sequence_guide.md)를 따른다.

## Teaching

`sequence.json`의 `teaching`을 `true`로 하면 GUI에 Teaching 화면이 나타나고 Run은
`pick.point`/`place.point` 이름을 포인트 파일에서 찾는다. false이면 설정의 positions를 사용한다.

- Capture: 동일한 최신 유효 Feedback에서 역할별 위치를 **편집 버퍼에만** 가져온다.
- 이름 입력과 Add / Apply: 편집한 JSON 포인트를 메모리에 추가/변경한다.
- Delete: 메모리에서 삭제한다. **Save file**을 눌러야 파일에 저장된다.
- 포인트는 위치/단위만 포함한다. 축 역할 매핑, 단계별 속도, 시퀀스 가감속과 분리한다.
- Run 시 포인트/설정 deep copy를 고정하며 실행 중 편집과 수동 조작은 비활성화된다.
- 없는 필수 포인트나 단위 불일치는 Run 입력 오류다. 포인트가 없어도 수동 Teaching/Stop은 가능하다.
- Jog ±는 누르고 있는 동안만 동작한다. 놓기/버튼 이탈/포커스 상실/Stop/창 닫기는 jog_stop을 요청한다.
- Move to point는 별도 Teaching 속도/가감속을 사용한다. 다음 시퀀스 Run은 공통 가감속을 다시 적용한다.
- Enable/Disable/Fault Reset/Homing은 선택 축에 명시적으로 보낸다. Referenced 상태를 표시하지만 Run 인터락을 추가하지 않는다.
- GUI Run 이후 제어권은 유지한다. 종료 중에는 취소/cleanup을 기다린 뒤 제어권 해제와 연결 종료를 한다.

## 검증 범위

저장소 루트에서 `python -m unittest tests.test_ai_pick_place`를 실행한다.
가짜 client의 응답/주기 Feedback으로 요청을 **실제 요청 Schema**와 대조하고 정상 순서,
Fail/timeout/Stop/Fault/연결·제어권 상실, 다축/invalid/stale 자료, 포인트 snapshot/저장을 검사한다.
Tk 사용 가능한 환경에서는 네트워크에 연결하지 않고 GUI 생성/Run 취소/Jog release도 검사한다.
이 시험은 실제 Mock 서버 TCP end-to-end, 실장비 시험, GUI 전체 수동 시험 또는 독립 AI 생성 평가가 아니다.
그 통합 검증과 실제 패키지 빌드는 S04에 남아 있다.
