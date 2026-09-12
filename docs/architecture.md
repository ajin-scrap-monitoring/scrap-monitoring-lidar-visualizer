# 구현 아키텍처

## 문서 역할

이 문서는 채택한 구현 설계의 정본이다. 제품 요구사항은 [프로젝트 명세](project-spec.md),
현재 구현 상태와 구현 순서는 [개발 계획](development-plan.md)에서 관리한다.

## 모듈 경계

프로그램은 `src/scrap_monitoring_lidar_visualizer/` 아래의 다음 10개 경계로 구성한다.

| 경계 | 책임 |
| --- | --- |
| `cli.py` | CLI(Command-Line Interface) 인자, 설정 검증과 실행 수명 관리 |
| `contracts/` | 원본 레코드 해석, schema 및 의미 검증, 내부 불변 자료형 |
| `receiver/` | TCP(Transmission Control Protocol) 연결 소유권과 LF(Line Feed) 레코드 조립 |
| `state/` | 실행 식별, sequence 판정, 연결 상태와 최신 관찰 상태 |
| `recording/` | 크기가 제한된 원본 레코드 기록과 종료 사유 |
| `geometry/` | 경계 삼각분할, 격자 표면 clipping과 결정론적인 mesh |
| `rendering/` | 카메라, 장면, overlay와 2D 프레임 렌더링 |
| `preview/` | HTTP(Hypertext Transfer Protocol) 프레임 및 상태 응답과 브라우저 화면 |
| `replay/` | 기록 순회, 실행 및 구간 선택과 프레임 시각 계산 |
| `export/` | FFmpeg 실행, MP4 출력과 종료 검증 |

`contracts/`의 자료형을 나머지 모듈이 공유한다. `geometry/`는 mesh 수치 배열을 반환하고
렌더링 엔진을 호출하지 않는다. `receiver/`와 `replay/`는 같은 validator와 `state/`의
실행 판정 로직을 사용한다. `cli.py`가 각 모듈을 연결한다.

외부 라이브러리는 해당 기능의 경계 안에서 사용한다. 네트워크와 파일 입출력,
렌더링 엔진 호출을 mesh 계산과 프레임 선택 함수에 포함하지 않는다.

## 기술 선택

구현에 사용하는 기술 묶음은 다음 6개다. P1에 필요한 Python, NumPy, PyVista, VTK, Mesa와
FFmpeg 조합은 설치 및 검증됐으며 버전은 [의존성](dependencies.md)에서 관리한다.
FastAPI와 Uvicorn은 P5에서 설치한다.

| 기술 | 채택 목적 | 공식 출처 |
| --- | --- | --- |
| Python과 uv | 수신, 검증과 수치 처리의 단일 언어 구현 및 의존성 고정 | [Python](https://www.python.org/), [uv](https://docs.astral.sh/uv/) |
| jsonschema | 고정 JSON(JavaScript Object Notation) Schema의 직접 검증 | [jsonschema](https://python-jsonschema.readthedocs.io/) |
| NumPy | 격자와 mesh의 수치 배열 처리 | [NumPy](https://numpy.org/doc/stable/) |
| PyVista, VTK(Visualization Toolkit), Mesa | 서버의 소프트웨어 3D 렌더링 | [PyVista](https://docs.pyvista.org/getting-started/installation.html), [VTK](https://docs.vtk.org/en/latest/advanced/runtime_settings.html), [Mesa](https://docs.mesa3d.org/) |
| FastAPI와 Uvicorn | 최신 프레임과 상태의 제한된 HTTP 서비스 | [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/) |
| FFmpeg와 ffprobe | 영상 인코딩과 출력 영상의 구조 검증 | [FFmpeg](https://ffmpeg.org/documentation.html) |

PyVista의 off-screen rendering은 VTK의 `vtkOSOpenGLRenderWindow`와 Mesa `libosmesa6`를
사용한다. Container는 `VTK_DEFAULT_OPENGL_WINDOW`로 renderer를 고정하고
`LIBGL_ALWAYS_SOFTWARE`로 CPU(Central Processing Unit) 경로를 요구한다. Linux AMD64
비root container가 GPU(Graphics Processing Unit), `DISPLAY`와 network 없이 frame과
MP4를 생성하는지 CI에서 검사한다.

## 실행 경계

실행 경계는 다음 4개다.

| 실행 단위 | 담당 작업 |
| --- | --- |
| 주 프로세스 | CLI, 비동기 수신, 실행 상태, preview와 replay 조정 |
| 기록 worker | 기록 대기열 순서에 따른 파일 쓰기 |
| 렌더링 자식 프로세스 | mesh와 장면의 프레임 생성 |
| FFmpeg 자식 프로세스 | replay 프레임의 순차 인코딩 |

생성기가 observation을 전송하면 주 프로세스가 레코드를 검증하고 실행 상태를 갱신한다.
주 프로세스는 유효한 원본 line을 기록 worker에 전달하고 최신 snapshot을 렌더링 대기
상태에 보관한다. 렌더링 자식 프로세스가 반환한 프레임은 preview의 최신 프레임을 교체한다.

```text
Generator -> Receiver -> Validator -> State -> Latest snapshot -> Renderer
                              |                                     |
                              v                                     v
                         Record queue                         Latest frame
                              |                                     |
                              v                                     v
                          Recorder                            HTTP preview -> Browser

Recording -> Replay -> Validator -> Frame selection -> Renderer -> FFmpeg -> MP4
                                                          |
                                                          v
                                                     HTTP preview -> Browser
```

렌더링 자식 프로세스는 한 번에 snapshot 1개를 처리한다. 주 프로세스는 처리 중 도착한
관찰 중 최신 1개만 보관하고 자식 프로세스가 다음 작업을 받을 수 있을 때 전달한다.
이 방식으로 수신 event loop에서 렌더링 작업과 대기 시간을 분리한다.

## 자원 정책

크기 제한을 가진 내부 보관 지점은 다음 4개다. 제품 전체의 최대 입력 및 출력 제한은
프로젝트 명세를 따른다.

| 보관 지점 | 초기 구현 기준 | 상한 처리 |
| --- | --- | --- |
| 렌더링 대기 snapshot | 최신 1개 | 새 관찰로 교체 |
| 기록 대기열 | 최대 128개 레코드 및 총 8 MiB(Mebibyte) | 수락한 prefix를 기록하고 기록 종료 |
| preview 프레임 | 최신 완성 프레임 1개 | 프레임과 식별 정보를 함께 교체 |
| HTTP 요청 | 동시 처리 최대 16개, 요청 제한 시간 5초 | 초과 요청 거부와 지연 연결 종료 |

주 프로세스는 기록 대기열 포화 시 이후 레코드의 기록을 중단하고 `queue_full` 사유를
상태에 표시한다. 기록 worker는 이미 수락한 prefix를 순서대로 기록하고 파일을 닫는다.
기록 한도는 LF를 포함한 원본 byte와 반복 header를 포함한 레코드 수로 계산한다.
어떤 한도든 다음 line 전체를 수락할 수 없으면 해당 line 전에 기록을 종료한다.

기록 경로의 사전 검증 오류는 시작 실패로 처리한다. 실행 중 기록 쓰기 오류는 기록을
중단하고 상태 및 로그에 표시하며 live 수신을 계속한다. 최종 프로세스 종료 code에도
실행 중 기록 실패를 반영한다. 사용자 한도 도달은 정상적인 기록 종료다.

FFmpeg에는 프레임을 순서대로 전달하고 모든 프레임을 메모리에 누적하지 않는다.
FFmpeg 처리 제한 시간과 종료 code를 검사한다. Mesh 생성에는 node 및 face 수와 clipping
연산량의 유한한 예산을 두고, 실제 한도와 기본 프레임 설정은 P1 측정 결과로 고정한다.

## 수신과 실행 상태

Receiver는 연결별 byte buffer에서 LF로 끝난 레코드만 validator에 전달한다. Parser는
중복 JSON key와 유한하지 않은 수치를 거부하며 원본 byte는 기록을 위해 별도로 유지한다.
Schema 검사 뒤에는 좌표 증가, 높이 배열 shape, 투입구 index, sensor 방향과 경계 형상처럼
schema가 표현하지 않는 의미 제약을 검사한다.

유효한 header를 수락한 뒤에만 현재 장면을 교체한다. 같은 실행의 재접속 header는 정적
정보를 비교하고 기존 sequence 상태에 연결한다. 새 실행으로 전환하면 새 실행의 관찰을
받기 전까지 이전 실행의 표면을 새 장면에 표시하지 않는다.

완성된 무효 레코드는 상태와 기록을 변경하지 않고 거부한다. Header 실패, framing 한도
초과와 연결 시작 제한 시간 초과는 해당 연결을 종료한다. 정상 header 이후의 무효
observation은 거부 건수를 표시하고 다음 레코드를 처리한다. 생성기에는 응답 byte를
전송하지 않는다. 수신 프로세스는 오류 사유를 상태와 로그에 표시하고 계속 재접속을 받는다.

주 프로세스는 연결 및 누락 상태 변경도 렌더링 요청으로 전달한다. 관찰이 추가로 오지
않아도 마지막 장면의 연결 상태 overlay를 갱신한다. 실행 식별과 sequence 판정의 세부
조건은 프로젝트 명세를 그대로 적용한다.

## Mesh 계산

Geometry는 polygon의 방향과 시작 vertex를 정규화하고 고정 순서의 ear clipping으로 바닥을
삼각분할한다. Self-intersection과 퇴화 경계는 의미 검증 오류로 처리한다.

격자는 `index = y_index * x_count + x_index` 순서로 vertex를 구성한다. 각 cell은
`(y, x)`와 `(y + 1, x + 1)`을 잇는 대각선으로 분할한다. 경계 삼각형과 표면 삼각형의
교집합을 계산하고 교차점의 Z 값은 원래 표면 삼각형에서 선형 보간한다. 교집합 polygon은
고정 순서로 삼각분할하며 vertex와 face의 출력 순서를 정규화한다.

이 계산은 concave 경계와 경계를 가로지르는 cell을 처리한다. 경계 안에 중심점이 있는
cell만 선택하는 방식으로 clipping을 대체하지 않는다. 외벽, sensor와 투입구는 header의
정적 장면에서 구성하고 filling 상태의 활성 투입구는 observation에 맞춰 표시한다.

## Preview 인터페이스

Preview 경로는 다음 3개다. Live와 replay는 같은 경로를 사용한다.

| 경로 | 응답 |
| --- | --- |
| `GET /` | 서버 프레임과 상태를 표시하는 브라우저 화면 |
| `GET /frame.png` | 최신 프레임 및 frame revision, 프레임 준비 전 204 |
| `GET /status` | 연결, 실행, 수신 및 렌더링 sequence, 누락, 마지막 정상 수신 시각과 기록 상태 |

브라우저는 이전 요청이 끝난 뒤 다음 요청을 보낸다. HTTP 요청은 보관된 프레임과 상태를
읽으며 렌더링을 직접 시작하지 않는다. 상태에는 최신 수신 sequence와 화면에 반영된
sequence를 구분하여 렌더링 지연을 표시한다. 프레임 응답은 해당 프레임의 식별 정보를
함께 제공하고 캐시로 이전 프레임을 재사용하지 않게 한다.

## Replay와 영상

Replay는 파일을 순차 검증하고 실행별 구간과 byte offset을 제한된 메모리로 확인한다.
여러 실행이 포함된 기록은 `--run-id`를 필수로 받으며, 실행을 선택하지 않은 모호한 입력은
오류로 종료한다. 같은 실행의 반복 header는 연결 경계로 처리한다.

선택 구간은 simulation 시각의 `[start, end]`이고 출력 프레임 시각은 영상 길이보다 작은
`k / fps`로 정의한다. Frame selector는 그 시각에 대응하는 simulation 시각까지의 레코드를
순서대로 적용하고 가장 최근의 유효 상태를 선택한다. 같은 simulation 시각의 레코드는
sequence가 큰 상태를 사용한다. 첫 관찰보다 이른 시작 구간과 관찰이 없는 구간은 거부한다.

Duration과 time scale의 상호 배타 검증 및 총 프레임 수 계산은 렌더링 전에 수행한다.
기존 출력 파일은 덮어쓰지 않는다. 부분 MP4는 사용자가 지정한 출력 디렉토리 안에 생성하고
FFmpeg 성공과 ffprobe 검증 뒤 최종 경로로 옮긴다. 쓰기 경로, 로그와 접근 범위는
프로젝트 명세의 배포 경계를 따른다.
