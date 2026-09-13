# 구현 아키텍처

## 문서 역할

이 문서는 채택한 구현 설계의 정본이다. 초기 제품 요구사항은
[프로젝트 명세](project-spec.md), 현재 구현 상태와 검증 순서는
[개발 계획](development-plan.md)에서 관리한다.

현재 제품 실행 경계는 TCP 관찰 수신과 Browser 기반 Live preview다. 관찰 기록, Replay와
영상 출력은 제공하지 않는다. 고정 입력인 프로젝트 명세에는 해당 기능이 남아 있으므로 현재
구현 범위와 다른 항목은 개발 계획에 명시한다.

## 모듈 경계

프로그램은 `src/scrap_monitoring_lidar_visualizer/` 아래의 다음 8개 경계로 구성한다.

| 경계 | 책임 |
| --- | --- |
| `cli.py` | 환경 변수와 CLI(Command-Line Interface) 인자, 설정 검증과 실행 수명 관리 |
| `contracts/` | 원본 레코드 해석, schema 및 의미 검증, 내부 불변 자료형 |
| `receiver/` | TCP(Transmission Control Protocol) 연결 소유권과 LF(Line Feed) 레코드 조립 |
| `state/` | 실행 식별, sequence 판정, 연결 상태와 최신 관찰 상태 |
| `geometry/` | 경계 삼각분할, 격자 표면 clipping과 결정론적인 mesh |
| `rendering/` | 카메라, 장면, overlay와 2D 프레임 렌더링 |
| `preview/` | HTTP(Hypertext Transfer Protocol) 프레임 및 상태 응답과 브라우저 화면 |
| `dependency_audit.py` | 실행 image의 의존성 version과 라이선스 고지 경로 inventory |

`contracts/`의 자료형을 나머지 모듈이 공유한다. `geometry/`는 mesh 수치 배열을 반환하고
렌더링 엔진을 호출하지 않는다. 네트워크와 렌더링 엔진 호출은 각각 `receiver/`와
`rendering/`에 격리하며 `cli.py`가 실행 경계를 연결한다.

Parser는 package 내부의 Observation version 1 schema를 기본 입력으로 사용한다. 저장소
검사는 package schema가 `contracts/observation/v1/`의 고정 사본과 byte 단위로 같은지
확인하고 wheel 검사는 두 schema가 배포 산출물에 포함되는지 확인한다.

## 실행 설정

실행 설정은 CLI 인자, `LIDAR_VISUALIZER_` 접두사의 환경 변수, 코드 기본값 순서로 결정한다.
실행 mode는 `live` 하나다. CLI 인자는 로컬 실행의 명시적 변경에 사용하고 환경 변수는
Container 배포 환경의 설정 주입에 사용한다.

환경 변수와 CLI가 제공한 값은 같은 `LiveConfig` 검증을 거친다. 필수 endpoint, port와
렌더링 해상도는 설정 출처와 관계없이 같은 오류 조건을 적용한다. 프로그램은 환경 변수를
시작할 때 한 번 읽으며 실행 중 변경을 반영하지 않는다.

## 기술 선택

구현에 사용하는 기술 묶음은 다음 5개다. Version은 [의존성](dependencies.md)에서 관리한다.

| 기술 | 채택 목적 | 공식 출처 |
| --- | --- | --- |
| Python과 uv | 수신, 검증과 수치 처리의 단일 언어 구현 및 의존성 고정 | [Python](https://www.python.org/), [uv](https://docs.astral.sh/uv/) |
| jsonschema | 고정 JSON(JavaScript Object Notation) Schema의 직접 검증 | [jsonschema](https://python-jsonschema.readthedocs.io/) |
| NumPy | 격자와 mesh의 수치 배열 처리 | [NumPy](https://numpy.org/doc/stable/) |
| PyVista, VTK(Visualization Toolkit), Mesa와 Pillow | 서버의 소프트웨어 3D 렌더링과 메모리 PNG encoding | [PyVista](https://docs.pyvista.org/getting-started/installation.html), [VTK](https://docs.vtk.org/en/latest/advanced/runtime_settings.html), [Mesa](https://docs.mesa3d.org/), [Pillow](https://python-pillow.github.io/) |
| FastAPI와 Uvicorn | 최신 프레임과 상태의 제한된 HTTP 서비스 | [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/) |

PyVista의 off-screen rendering은 VTK의 `vtkOSOpenGLRenderWindow`와 Mesa `libosmesa6`를
사용한다. Container는 `VTK_DEFAULT_OPENGL_WINDOW`로 renderer를 고정하고
`LIBGL_ALWAYS_SOFTWARE`로 CPU(Central Processing Unit) 경로를 요구한다. Linux AMD64
비root Container가 GPU와 `DISPLAY` 없이 Live 프레임을 생성하는지 CI에서 검사한다.

## 실행 경계

실행 단위는 다음 2개다.

| 실행 단위 | 담당 작업 |
| --- | --- |
| 주 process | CLI, 비동기 수신, 실행 상태와 HTTP preview 관리 |
| 렌더링 자식 process | Mesh와 장면의 사선 및 상면 프레임 생성 |

생성기가 Observation을 전송하면 주 process가 레코드를 검증하고 최신 실행 상태를 갱신한다.
렌더링 자식 process가 완성한 사선 프레임과 상면 프레임은 하나의 revision으로 교체된다.

```text
Generator -> Receiver -> Validator -> State -> Latest snapshot -> Renderer
                                                                    |
                                                                    v
                                                              Latest frames
                                                                    |
                                                                    v
Browser <- HTTP preview <--------------------------------------------+
```

렌더링 자식 process는 한 번에 snapshot 1개를 처리한다. 주 process는 처리 중 도착한 관찰 중
최신 1개만 대기 상태에 둔다. 렌더링이 끝나면 최신 대기 snapshot을 전달하므로 오래된 중간
관찰이 수신 event loop와 화면 갱신을 막지 않는다.

## 메모리 상태와 상한

메모리에 유지하는 상태는 다음 3개다. 운영 데이터를 영구 저장하는 경로는 없다.

| 보관 지점 | 상한 | 상한 처리 |
| --- | --- | --- |
| 실행 상태 | Header와 최신 Observation 각 1개 | 새 실행 또는 최신 Observation으로 교체 |
| 렌더링 처리 및 대기 snapshot | 처리 중 1개와 대기 1개 | 대기 상태를 새 관찰로 교체 |
| Preview 프레임 묶음 | 설정 camera와 상면 PNG 각 1개 | 두 프레임과 식별 정보를 함께 교체 |

HTTP 요청은 동시에 최대 16개를 처리하고 요청 제한 시간은 5초다. 초과 요청은 거부하고
지연 연결은 종료한다. Mesh 생성에는 node, face와 clipping 연산량의 유한한 예산을 둔다.
실제 상한과 기본 프레임 설정은 [실행 환경](deployment.md)에서 관리한다.

렌더링 자식 process는 렌더 결과를 메모리에서 PNG byte로 인코딩한다. 운영 프레임은
Container filesystem, host volume이나 image layer에 기록하지 않는다.

## 수신과 실행 상태

Receiver는 연결별 byte buffer에서 LF로 끝난 레코드만 validator에 전달한다. Parser는
중복 JSON key와 유한하지 않은 수치를 거부한다. Schema 검사 뒤에는 좌표 증가, 높이 배열
shape, 투입구 index, sensor 방향과 경계 형상처럼 schema가 표현하지 않는 의미 제약을
검사한다.

한 입력 chunk에서 framing 한도 오류가 발생해도 오류 앞에서 완성된 레코드는 순서대로
처리한다. 한도를 초과한 레코드와 남은 buffer는 폐기하고 해당 연결을 종료한다.

유효한 Header를 수락한 뒤에만 현재 장면을 교체한다. 같은 실행의 재접속 Header는 정적
정보를 비교하고 기존 sequence 상태에 연결한다. 새 실행으로 전환하면 새 실행의 관찰을
받기 전까지 이전 실행의 표면을 표시하지 않는다.

완성된 무효 레코드는 상태를 변경하지 않고 거부한다. Header 실패, framing 한도 초과와
연결 시작 제한 시간 초과는 해당 연결을 종료한다. 정상 Header 이후의 무효 Observation은
거부 건수를 표시하고 다음 레코드를 처리한다. 생성기에는 응답 byte를 전송하지 않는다.

주 process는 연결 및 누락 상태 변경도 렌더링 요청으로 전달한다. 관찰이 추가로 오지 않아도
마지막 장면의 연결 상태 overlay를 갱신한다. 각 Observation은 전체 표면 snapshot이며 이전
표면에 적용하는 변경분으로 처리하지 않는다.

## Mesh와 장면

Geometry는 polygon의 방향과 시작 vertex를 정규화하고 고정 순서의 ear clipping으로 바닥을
삼각분할한다. Self-intersection과 퇴화 경계는 의미 검증 오류로 처리한다.

격자는 `index = y_index * x_count + x_index` 순서로 vertex를 구성한다. 각 cell은
`(y, x)`와 `(y + 1, x + 1)`을 잇는 대각선으로 분할한다. 경계 삼각형과 표면 삼각형의
교집합을 계산하고 교차점의 Z 값은 원래 표면 삼각형에서 선형 보간한다. 교집합 polygon은
고정 순서로 삼각분할하며 vertex와 face의 출력 순서를 정규화한다.

표면 mesh의 외곽 edge는 각 꼭짓점에서 `floor_z_m`까지 내려 적재 체적의 옆면을 구성한다.
수거가 끝나 모든 표면 높이가 바닥 높이와 같으면 퇴화한 옆면은 생성하지 않는다. Sensor는
`p0_m`에서 시작해 오른손 좌표계의 `u0 x u90` 회전축 방향을 향하는 arrow 하나로 표시한다.

사선과 상면 camera는 거리에 따른 크기 변화를 제거한 직교 투영을 사용한다. 기본 프레임은
1280 x 720이다. 적재 표면은 smooth shading과 회색 mesh edge를 함께 적용한다. 적재 표면과
체적 옆면은 `floor_z_m`부터 `top_z_m`까지 고정한 노랑-주황-적색 높이 범례를 사용한다.
범례 제목은 화면 오른쪽 위에 두고 세로 범례는 그 아래에서 끝나게 배치한다.

## Preview 인터페이스

Preview 경로는 다음 4개다.

| 경로 | 응답 |
| --- | --- |
| `GET /` | 서버 프레임과 상태를 표시하는 브라우저 화면 |
| `GET /frame.png` | 최신 설정 camera 프레임 및 revision, 프레임 준비 전 204 |
| `GET /frame-top.png` | 같은 revision의 최신 상면 높이 지도, 프레임 준비 전 204 |
| `GET /status` | 연결, 실행, 수신 및 렌더링 sequence, 누락과 마지막 정상 수신 시각 |

렌더링 worker는 설정한 camera 프레임과 상면 높이 지도를 순서대로 만든 뒤 하나의 revision으로
교체한다. Browser는 두 프레임을 나란히 표시하고 이전 요청이 끝난 뒤 다음 요청을 보낸다.
HTTP 요청은 보관된 최신 프레임과 상태를 읽으며 렌더링을 직접 시작하지 않는다. 상태에는
최신 수신 sequence와 화면에 반영된 sequence를 구분하여 렌더링 지연을 표시한다.

## 배포 경계

Release workflow는 원격 `main`의 version tag를 입력으로 Linux AMD64 OCI(Open Container
Initiative) image와 Python package를 생성한다. Image는 version과 source commit tag를 같은
manifest digest에 연결하고 source commit, version 및 저장소를 OCI label로 기록한다.

GHCR image에는 SBOM(Software Bill of Materials)과 build provenance를 첨부한다. 게시 후
workflow가 image를 digest로 가져와 Live CLI, TCP 수신, HTTP preview, headless rendering과
의존성 고지를 검사한다. 공개 Package 확인까지 통과한 산출물만 GitHub Release에 게시한다.
