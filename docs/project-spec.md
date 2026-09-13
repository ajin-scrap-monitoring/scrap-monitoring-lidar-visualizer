# 적재 모델 시각화 프로젝트 최소 명세

## 문서 역할

이 문서는 구현 요구사항의 고정 입력이다. 구현 과정에서 이 파일을 수정하지 않는다.
구현에 필요한 에이전트 지침, 의존성, 내부 디렉토리 구조, 기술 결정과 운영 문서는 이
문서를 제외한 Repository 파일로 자유롭게 추가하고 관리한다.

## 저장소

| 항목 | 결정 |
| --- | --- |
| 프로젝트 제목 | Scrap Monitoring Visualizer |
| 원격 저장소 | `ajin-scrap-monitoring/scrap-monitoring-visualizer` |
| 공개 범위 | Public |
| 소스 이용 조건 | 별도 라이선스 부여 없음 |

SSH 주소는 다음과 같다.

```text
git@github.com:ajin-scrap-monitoring/scrap-monitoring-visualizer.git
```

## 상위 컨텍스트

전체 실행 구조는 3개 구성 요소로 구분한다.

1. `scrap-monitoring-lidar-generator`는 ARM64 edge device에서 적재 모델 관찰 stream을
   생성하고 TCP client로 전송한다.
2. `scrap-monitoring-visualizer`는 Linux AMD64 시각화 server에서 TCP server로
   관찰 stream을 수신하고 현재 적재 모델을 headless 3D frame과 MP4로 rendering한다.
3. 개발 장비의 browser는 시각화 server가 HTTP로 제공하는 live preview와 상태를
   표시하며 3D mesh를 직접 계산하거나 rendering하지 않는다.

개발 환경과 배포 환경은 분리한다. 실제 장비 hostname, 사설 주소와 자격 증명은 Public
Repository에 기록하지 않고 배포 환경의 외부 설정으로 제공한다.

## 목적

LiDAR 생성기가 제공하는 적재 모델 관찰 데이터를 실시간으로 확인하고, 유효한 관찰
기록을 재생하거나 MP4 영상으로 생성할 수 있는 공학용 시각화 프로그램을 제공한다.

개별 scrap 조각의 물리 충돌과 사실적 rendering은 제공하지 않는다. 관찰 데이터의
표면 격자와 장면 정보를 사용하여 결정론적인 공학용 mesh를 구성한다.

## 입력 요구사항의 출처

초기 요구사항은 LiDAR Generator Repository의 다음 2개 입력을 기준으로 한다.

| 입력 | 역할 |
| --- | --- |
| `docs/visualizer-requirements.md` | 기능, 자원 제한과 자동 검증 요구사항 |
| `contracts/observation/v1/` | 전송 framing, schema, 좌표와 전달 의미의 정본 |

Observation version 1 계약의 기준 commit은
`bbf359391daff8a5c547ab341782c19a03ca0356`이다. 구현은 해당 commit의
`header.schema.json`, `observation.schema.json`과
`fixtures/observation.v1.jsonl`을 호환성 검증에 사용한다. Version 1의 field 의미나
framing을 호환되지 않게 변경하지 않는다.

Repository는 이 3개 파일의 byte가 같은 사본과 원본 Repository 및 commit 정보를
versioned contract fixture로 보관한다. 자동 검증은 network에서 계약 파일을 동적으로
받지 않고 이 고정 사본을 사용한다. 원본 계약이 새 version을 추가하면 별도 호환성 작업으로
사본과 parser를 갱신한다.

## 산출물

- TCP 관찰 수신기
- Version 1 레코드 parser와 validator
- 크기가 제한된 live 상태 및 관찰 기록 저장 기능
- 적재 공간과 표면 mesh renderer
- Browser 기반 live preview, 기록 재생과 MP4 생성을 위한 CLI(Command-Line Interface)
- Linux AMD64용 OCI(Open Container Initiative) 컨테이너 이미지
- 자동 검사와 테스트를 수행하는 CI(Continuous Integration) 구성

## 범위

### 포함 범위

- Observation version 1 stream 수신과 검증
- 실행 전환, sequence 누락, 중복과 역순 처리
- 현재 적재 공간, 표면, 센서와 투입구의 3D 표현
- Live 연결 상태와 주요 관찰 값 overlay
- 시각화 server가 rendering한 frame과 상태의 HTTP live preview
- 상한이 있는 원본 JSON Lines 기록
- 기록 구간 재생과 MP4 출력
- 고정 사선 camera와 상면 camera
- 연결 중단 후 같은 port에서 다음 연결 수신
- 구조 및 수치 속성 기반 자동 검증

### 제외 범위

- LiDAR scan 생성
- 실제 LiDAR 장비와 SDK(Software Development Kit) 연동
- 일반 scan stream 수신과 point cloud 표면 추정
- 높이 계산 process
- 개별 scrap 조각의 물리 충돌 simulation
- 사실적 재질과 조명 rendering
- Observation version 1의 ACK(Acknowledgement), 인증, 압축과 broker
- 모든 중간 상태의 전달과 재전송 보장
- Dashboard의 일반 사용자 화면 구현
- Browser의 3D mesh 생성과 rendering

## 실행과 배포

프로그램은 Linux AMD64 시각화 server의 Docker Engine에서 비root container로 실행한다.
Observation TCP listen 주소와 port, preview HTTP listen 주소와 port, 기록 경로와 자원
상한은 실행 시 외부 설정으로 제공한다. ARM64 edge device와 Linux AMD64 시각화 server는
Docker Engine `29.8.0`, Docker Compose plugin `5.5.1`과 containerd `2.3.5`를 동일하게
사용한다.

컨테이너 이미지는 Public GHCR(GitHub Container Registry) Package로 게시한다. Release
version에서 파생한 `MAJOR.MINOR.PATCH` tag와 `sha-<full-git-sha>` tag를 사용하고
`latest`는 게시하지 않는다. 배포 Repository는 image tag가 아닌
`ghcr.io/ajin-scrap-monitoring/<image>@sha256:<digest>` 형식으로 이미지를 고정한다.

프로그램 로그는 표준 출력과 표준 오류로 기록하고 제한되지 않은 host 파일 로그를 만들지
않는다. 관찰 기록, frame과 MP4는 명시한 writable 경로에만 생성하며 image에 포함하지
않는다. 배포는 TCP 수신 port와 HTTP preview port를 각각 명시적으로 노출한다. 3D
renderer와 FFmpeg는 시각화 image에만 포함하며 version과 license를 의존성 문서에 기록한다.

## 전송 인터페이스

전송에는 생성기 producer와 시각화 receiver의 2개 구성 요소가 참여한다. 생성기는 TCP
(Transmission Control Protocol) client이고 receiver는 설정한 주소와 port에서 대기하는
TCP server다.

생성기는 UTF-8 JSON 객체 하나와 LF(Line Feed) 1 byte를 한 레코드로 전송한다. Receiver는
TCP packet 경계가 아닌 LF를 기준으로 레코드를 조립한다. Packet 분할과 여러 레코드의
packet 병합을 허용한다. 연결 종료 시 남은 불완전 레코드는 폐기한다.

한 레코드는 LF를 포함하여 최대 1,048,576 byte다. 연결의 첫 레코드는
`load_model_stream_header` 1개이고 이후 레코드는 `load_model_observation`이다. 연결이
바뀌면 생성기는 header를 다시 전송한다. Receiver는 생성기에 어떤 byte도 보내지 않는다.

`header.schema.json`과 `observation.schema.json`이 레코드 형식의 정본이다. Receiver는
알 수 없는 version, type과 field, 필수 field 누락 및 최대 line 크기를 넘는 입력을
거부한다.

Version 1 receiver는 동시에 연결된 producer 1개만 처리한다. 다른 producer가 연결된
상태의 추가 연결은 관찰 상태를 변경하지 않고 거부한다.

## 전달과 실행 식별

전송은 ACK가 없는 best-effort 방식이다. 생성기는 최신 대기 observation 1개만 유지하고
이전 대기 레코드를 재전송하지 않는다. Receiver는 중복 없는 전달이나 모든 중간 상태의
전달을 가정하지 않는다.

Receiver는 `run_id`, `environment_id`, `seed`와 `input_fingerprint_sha256`로 실행 묶음을
구분한다. `input_fingerprint_sha256`은 opaque lowercase SHA-256(Secure Hash Algorithm
256-bit) 값으로 취급한다.

같은 `run_id`에서 sequence 증가 폭이 1보다 크면 누락 상태를 기록하고 live 표시를
계속한다. 이전 sequence, 중복 sequence와 감소한 simulation 시각을 가진 레코드는
거부한다. TCP 재접속에서 같은 `run_id`와 같은 정적 정보를 가진 header를 받으면 기존
sequence 상태를 유지하고 연결 경계로 처리한다. 같은 `run_id`인데 `environment_id`,
`seed`, `input_fingerprint_sha256` 또는 `scene`이 다른 header는 거부한다. 새로운 `run_id`를
포함한 유효한 header는 새 실행으로 전환한다.

## 좌표와 장면

Header의 `scene.coordinate_system`은 오른손 좌표계이며 Z축이 위쪽이다. 모든 거리와
좌표의 단위는 meter이고 각도 단위는 degree다. `boundary_xy_m`은 적재 공간의 수평 경계
polygon이며 `floor_z_m`과 `top_z_m`은 바닥과 외벽 상단의 절대 Z 좌표다.

Sensor의 `p0_m`은 원점이고 `u0`과 `u90`은 서로 직교하는 단위 방향 벡터다. Degree 단위
각도를 radian으로 변환한 뒤 광선 방향을 계산한다.

```text
angle_rad = radians(angle_deg)
direction = cos(angle_rad) * u0 + sin(angle_rad) * u90
```

Renderer는 sensor 위치와 기본 방향을 표시한다. `inlet_positions_xy_m`의 배열 순서는
`scenario.current_inlet_index`가 참조하는 순서다. `current_inlet_index`는 filling 상태에서
현재 투입구를 가리키며 collecting 상태에서는 null이다.

## 적재 표면과 mesh

`surface.heights_m[y_index][x_index]`는 `x_coordinates_m[x_index]`와
`y_coordinates_m[y_index]`가 만나는 격자 node의 절대 Z 좌표다. 좌표 배열은 엄격히
증가하며 `heights_m` shape은 Y 좌표 수와 X 좌표 수의 순서다.

Renderer는 같은 index의 X, Y 좌표와 높이를 결합하여 표면 vertex를 만든다. 인접한 격자
node는 결정론적인 대각선 규칙으로 삼각형 2개를 만든다. 경계 polygon 밖의 표면은
표시하지 않으며 concave polygon도 처리한다. 바닥은 경계 polygon을 삼각분할하고 외벽은
각 경계 edge의 바닥부터 `top_z_m`까지 만든다.

동일한 유효 레코드와 camera 및 출력 설정은 같은 mesh vertex, face와 frame 선택 순서를
생성한다. Floating-point 표시 형식과 색상 차이로 인해 pixel 전체를 고정하는 snapshot
test는 사용하지 않는다.

## 실시간 동작

Live 경로는 수신, 기록과 rendering 사이에 크기가 제한된 queue를 사용한다. 느린
renderer는 생성기 연결 읽기를 무기한 막지 않는다. 화면 갱신 대기 상태는 오래된 frame을
폐기하고 최신 상태를 유지한다.

연결이 끊기면 화면에 disconnected 상태와 마지막 정상 레코드의 시각을 표시하고 같은
port에서 다음 연결을 계속 기다린다.

기본 화면은 고정 사선 camera에서 전체 경계, 바닥, 외벽, 투입구, sensor 위치와 방향,
현재 적재물 표면을 표시한다. 상면 camera도 선택할 수 있다. 화면 overlay는 `elapsed_s`,
`surface_fill_ratio`, `phase`, `cycle_index`, `sequence`와 연결 상태를 표시한다. Filling
상태에서는 현재 투입구를 구분해 표시한다.

시각화 server는 물리 화면과 GPU(Graphics Processing Unit)에 의존하지 않는 headless
rendering을 지원한다. Live mode는 server에서 3D frame을 rendering하고 browser 기반 HTTP
preview로 최신 frame과 상태를 제공한다. Browser는 server가 제공한 2D frame과 상태만
표시한다. HTTP 내부 frame 전달 방식과 web framework는 구현에서 결정한다.

Preview는 관찰 record를 받을 때 최신 상태를 rendering하며 과거 frame을 누적하지 않는다.
연결 중단, sequence 누락과 마지막 정상 record 시각은 frame overlay와 상태 응답에 함께
표시한다.

## 기록과 재생

기록 기능은 header부터 수신한 유효한 원본 JSON line을 순서대로 보존한다. TCP 재접속에서
받은 반복 header도 연결 경계로 보존한다. 기록은 명시적으로 켠 경우에만 수행하며 byte 또는
record 수 기준의 상한을 필수로 받는다. 상한에 도달하면 기록을 정상 종료하고 live 표시는
계속한다. 불완전 line과 무효 레코드는 기록하지 않는다.

재생은 반복 header를 연결 경계로 처리하고 같은 run의 sequence 상태를 유지한다. 저장된
레코드의 simulation 시각을 기준으로 구간을 선택하며 영상 frame 시각에는 그 시각보다
늦지 않은 가장 최근 레코드를 사용한다. 사용자가 영상 재생 시간과 시간 가속률을 동시에
지정하면 오류로 종료한다.

## CLI 요구사항

CLI는 live와 replay의 2개 mode를 제공한다.

| Mode | 필수 입력 | 선택 입력 | 출력 |
| --- | --- | --- | --- |
| `live` | Observation TCP listen host와 port, preview HTTP listen host와 port | Camera, 기록 설정 | Browser preview, 선택적 JSON Lines |
| `replay` | JSON Lines 입력 | 구간, duration 또는 time scale, FPS, 해상도, camera | Browser preview 또는 MP4 |

기본 camera는 전체 공간이 보이는 고정 사선 시점이고 `top`을 추가로 제공한다. MP4 출력은
명시한 경로만 사용한다. 사용자가 지정한 입력 및 출력 경로 밖의 파일을 읽거나 생성하지
않는다. Live와 replay preview는 같은 HTTP preview 경계를 사용한다.

## 데이터와 접근 경계

Public Repository에는 generator의 공개 합성 계약 fixture만 포함한다. 실제 관찰 stream과
그로부터 만든 기록, frame 및 MP4는 운영 데이터로 취급하고 Git에 추가하지 않는다. 해당
산출물 경로와 확장자는 기본 `.gitignore`에 포함한다.

관찰 header와 기록에는 적재 공간, 투입구와 sensor 위치가 포함될 수 있다. 운영 기록
directory와 preview endpoint는 접근이 제한된 개발 network에서만 제공한다. Version 1은
application 수준의 인증과 TLS(Transport Layer Security)를 제공하지 않으며 Public
Internet에 직접 노출하지 않는다.

## 자원과 오류 처리

수신 line, live queue, 기록량, frame 수, FPS(Frame Per Second)와 해상도에 각각 유한한
상한을 둔다. 초기 최대 상한은 3,000 frame, 60 FPS와 3,840 x 2,160 해상도다.

Receiver 또는 renderer 장애는 엣지 생성기의 scan 생성과 기존 scan 전송 상태를 변경하지
않는다. 유효하지 않은 외부 입력, 사용할 수 없는 출력 경로와 상호 배타 option은 명확한
오류 메시지와 0이 아닌 종료 code로 보고한다.

Live 상태, rendering 대기 상태와 HTTP preview는 각각 bounded 정책을 사용한다. Receiver는
느린 browser나 연결되지 않은 browser 때문에 관찰 TCP 읽기를 중단하지 않는다.

## 자동 검증

자동 검증은 다음 10개 범주를 포함한다.

1. 계약 fixture와 schema validation.
2. 분할, 병합, 불완전 line과 최대 line 크기 처리.
3. Version, type, 필수 field와 알 수 없는 field 오류.
4. Sequence gap, 중복, 역순과 run 전환 처리.
5. Y-major 표면 mesh, 경계 clipping과 concave polygon 처리.
6. 동일 입력의 mesh 및 frame 선택 결정론.
7. Queue, 기록, frame, FPS와 해상도 상한.
8. Live 및 replay CLI의 상호 배타 option과 오류 종료 code.
9. 같은 run의 재접속 header, 정적 정보 불일치와 sequence 연속성.
10. HTTP preview의 최신 frame, 연결 상태와 느린 browser 격리.

공개 통합 fixture는 Observation version 1 계약의
`fixtures/observation.v1.jsonl`을 사용한다. 시각적 회귀는 구조 및 수치 속성을 검증하고
pixel 전체 snapshot을 사용하지 않는다.

## 구현 자율성

구현 언어, package 및 의존성 관리 도구, rendering engine, HTTP 내부 frame 전달 방식,
web framework, 내부 모듈과 디렉토리 구조는 이 명세에서 고정하지 않는다. 구현은 요구사항과
대상 환경을 만족하는 기술을 선택하고, 채택한 의존성의 version, 목적, 출처와 license를
Repository 문서에 기록한다.
