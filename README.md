# Scrap Monitoring LiDAR Visualizer

Scrap Monitoring LiDAR Generator가 전송하는 적재 모델 관찰 데이터를 Linux AMD64 server에서
검증하고 3D 프레임으로 렌더링하는 프로그램이다. 관찰 데이터는 원시 LiDAR scan이 아니라
Generator가 계산한 현재 적재물 표면과 시나리오 상태의 snapshot이다.

Visualizer는 모니터, `DISPLAY`와 GPU(Graphics Processing Unit)가 없는 Container에서
프레임을 생성한다. 개발 장비의 Browser는 HTTP(Hypertext Transfer Protocol)를 통해 최신
PNG 프레임과 수신 상태를 표시한다.

## 주요 기능

- TCP(Transmission Control Protocol) 기반 Observation version 1 수신과 계약 검증
- 적재 공간, 표면, sensor와 투입구의 결정론적인 3D mesh 렌더링
- 최신 PNG 프레임과 상태를 제공하는 Browser 기반 실시간 미리보기
- 상한이 있는 JSON Lines 관찰 기록
- 기록 구간 재생과 H.264 MP4 생성
- Linux AMD64 비root Container와 Public GHCR(GitHub Container Registry) 이미지

## 빠른 시작

사전 조건은 Linux AMD64, Docker Engine과 `curl`이다. 저장소를 Checkout한 뒤 Repository
루트에서 최신 Release가 제공하는 불변 digest 이미지로 공개 합성 관찰 데이터를 MP4로
변환한다.

```bash
IMAGE_REF="$(
  curl --fail --location --silent --show-error \
    https://github.com/ajin-scrap-monitoring/scrap-monitoring-lidar-visualizer/releases/latest/download/oci-image.txt
)"
docker image pull "$IMAGE_REF"

install -d -m 0777 artifacts/quick-start

docker run --rm \
  --platform linux/amd64 \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --mount "type=bind,source=$(pwd)/contracts/observation/v1/fixtures/observation.v1.jsonl,target=/input/observation.v1.jsonl,readonly" \
  --mount "type=bind,source=$(pwd)/artifacts/quick-start,target=/output" \
  --env LIDAR_VISUALIZER_OUTPUT_PATH=/output/replay.mp4 \
  "$IMAGE_REF" \
  replay /input/observation.v1.jsonl
```

첫 유효 결과는 `artifacts/quick-start/replay.mp4`다. `IMAGE_REF` 값은 tag가 아니라
`ghcr.io/...@sha256:<digest>` 형식이며 배포 설정에는 확인한 값을 그대로 고정한다.

## 설정

실행 설정은 CLI(Command-Line Interface) 인자, `LIDAR_VISUALIZER_` 환경 변수, 코드 기본값
순서로 결정한다. 실행 mode인 `live` 또는 `replay`와 Replay의 JSON Lines 입력 경로는
command로 지정한다. 환경 변수 17개는 공통 5개, Live 전용 5개와 Replay 전용 7개다.

공통 설정은 다음과 같다.

| 환경 변수 | CLI option | 기본값 |
| --- | --- | --- |
| `LIDAR_VISUALIZER_HTTP_HOST` | `--http-host` | Live 필수, Replay 없음 |
| `LIDAR_VISUALIZER_HTTP_PORT` | `--http-port` | Live 필수, Replay 없음 |
| `LIDAR_VISUALIZER_CAMERA` | `--camera` | `isometric` |
| `LIDAR_VISUALIZER_WIDTH` | `--width` | `640` |
| `LIDAR_VISUALIZER_HEIGHT` | `--height` | `360` |

Live 설정은 다음과 같다.

| 환경 변수 | CLI option | 기본값 |
| --- | --- | --- |
| `LIDAR_VISUALIZER_TCP_HOST` | `--tcp-host` | 필수 |
| `LIDAR_VISUALIZER_TCP_PORT` | `--tcp-port` | 필수 |
| `LIDAR_VISUALIZER_RECORD_PATH` | `--record` | 기록 사용 안 함 |
| `LIDAR_VISUALIZER_RECORD_MAX_RECORDS` | `--record-max-records` | 기록 사용 안 함 |
| `LIDAR_VISUALIZER_RECORD_MAX_BYTES` | `--record-max-bytes` | 기록 사용 안 함 |

Replay 설정은 다음과 같다.

| 환경 변수 | CLI option | 기본값 |
| --- | --- | --- |
| `LIDAR_VISUALIZER_OUTPUT_PATH` | `--output` | MP4 출력 없음 |
| `LIDAR_VISUALIZER_RUN_ID` | `--run-id` | 단일 실행 자동 선택 |
| `LIDAR_VISUALIZER_START_S` | `--start` | 첫 관찰 시각 |
| `LIDAR_VISUALIZER_END_S` | `--end` | 마지막 관찰 시각 |
| `LIDAR_VISUALIZER_DURATION_S` | `--duration` | 없음 |
| `LIDAR_VISUALIZER_TIME_SCALE` | `--time-scale` | `1` |
| `LIDAR_VISUALIZER_FPS` | `--fps` | `10` |

Live 기록 변수 3개는 모두 설정하거나 모두 생략한다. Replay는 MP4 출력 경로 또는 HTTP
endpoint 쌍 중 하나만 설정한다. `DURATION_S`와 `TIME_SCALE`은 함께 설정하지 않는다.
숫자 형식이나 설정 조합이 유효하지 않으면 프로그램은 오류를 출력하고 종료 code 2를
반환한다. 전체 범위와 자원 상한은 [실행 환경](docs/deployment.md)에 정의돼 있다.

## 개발 및 검증

사전 조건은 Python 3.14.7, uv 0.12.13과 Docker Engine이다. Repository 루트에서 고정된
개발 환경과 전체 검사를 실행한다.

```bash
uv sync --locked --all-groups
uv run --frozen rumdl check --no-config --no-cache --disable MD013 .
uv run --frozen python tools/check_repository.py
uv run --frozen ruff format --check src tests tools
uv run --frozen ruff check src tests tools
uv run --frozen mypy
uv run --frozen python -m pytest
uv run --frozen python -m compileall -q src tests tools
scripts/check-headless-container.sh
```

## 배포

Live Container는 TCP 7000에서 관찰 데이터를 받고 HTTP 8000에서 미리보기를 제공한다.
실제 사설 주소와 운영 설정은 이미지에 포함하지 않고 배포 환경에서 주입한다. 다음 명령은
기록 기능을 사용하지 않는 기본 배포다.

배포 host에 `/path/to/visualizer.env`를 준비한다.

```dotenv
LIDAR_VISUALIZER_TCP_HOST=0.0.0.0
LIDAR_VISUALIZER_TCP_PORT=7000
LIDAR_VISUALIZER_HTTP_HOST=0.0.0.0
LIDAR_VISUALIZER_HTTP_PORT=8000
```

```bash
IMAGE_REF="$(
  curl --fail --location --silent --show-error \
    https://github.com/ajin-scrap-monitoring/scrap-monitoring-lidar-visualizer/releases/latest/download/oci-image.txt
)"

docker run --detach \
  --name scrap-monitoring-lidar-visualizer \
  --restart unless-stopped \
  --platform linux/amd64 \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --pids-limit 128 \
  --memory 1g \
  --cpus 2 \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  --publish 7000:7000 \
  --publish 8000:8000 \
  --env-file /path/to/visualizer.env \
  "$IMAGE_REF" \
  live
```

Generator에는 Visualizer server에서 공개한 TCP endpoint를 지정한다.

```bash
uv run --locked scrap-monitoring-lidar-generator \
  --config /path/to/generator.v1.json \
  --observation-host <visualizer-host> \
  --observation-port 7000
```

Generator Container에서도 `<visualizer-host>`는 Container 내부에서 해석되고 접근 가능한
DNS(Domain Name System) 이름 또는 IP 주소여야 한다. 실제 주소는 Public Repository에
기록하지 않는다.

수신과 렌더링 상태를 확인한다.

```bash
docker container ps --filter name=scrap-monitoring-lidar-visualizer
docker container logs scrap-monitoring-lidar-visualizer
curl --fail http://<visualizer-host>:8000/status
curl --fail --output frame.png http://<visualizer-host>:8000/frame.png
```

Browser에서 `http://<visualizer-host>:8000/`을 열면 최신 프레임과 상태를 확인할 수 있다.
첫 유효 관찰 전에는 `/frame.png`가 204를 반환한다. `/status`의 `received_sequence`와
`rendered_sequence`가 값으로 채워지면 수신과 렌더링이 완료된 상태다.

관찰 기록을 활성화하려면 UID(User Identifier)와 GID(Group Identifier) 10001이 쓸 수 있는
host directory를 준비하고 Live 명령에 기록 mount와 환경 변수를 추가한다.

배포 host에 `/path/to/visualizer-recording.env`를 준비한다.

```dotenv
LIDAR_VISUALIZER_TCP_HOST=0.0.0.0
LIDAR_VISUALIZER_TCP_PORT=7000
LIDAR_VISUALIZER_HTTP_HOST=0.0.0.0
LIDAR_VISUALIZER_HTTP_PORT=8000
LIDAR_VISUALIZER_RECORD_PATH=/data/observations.ndjson
LIDAR_VISUALIZER_RECORD_MAX_BYTES=104857600
LIDAR_VISUALIZER_RECORD_MAX_RECORDS=100000
```

```bash
sudo install -d -o 10001 -g 10001 -m 0770 /path/to/visualizer-recordings

docker run --detach \
  --name scrap-monitoring-lidar-visualizer-recording \
  --restart unless-stopped \
  --platform linux/amd64 \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --pids-limit 128 \
  --memory 1g \
  --cpus 2 \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  --publish 7000:7000 \
  --publish 8000:8000 \
  --mount type=bind,src=/path/to/visualizer-recordings,dst=/data \
  --env-file /path/to/visualizer-recording.env \
  "$IMAGE_REF" \
  live
```

기록을 MP4로 변환할 때는 Live Container를 중단한 뒤 별도 출력 directory를 준비하고 같은
digest 이미지를 Replay mode로 실행한다.

```bash
sudo install -d -o 10001 -g 10001 -m 0770 /path/to/visualizer-output

docker run --rm \
  --platform linux/amd64 \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --mount type=bind,src=/path/to/visualizer-recordings,dst=/input,readonly \
  --mount type=bind,src=/path/to/visualizer-output,dst=/output \
  --env LIDAR_VISUALIZER_OUTPUT_PATH=/output/replay.mp4 \
  --env LIDAR_VISUALIZER_FPS=10 \
  "$IMAGE_REF" \
  replay /input/observations.ndjson
```

HTTP endpoint에는 인증과 TLS(Transport Layer Security)가 없다. TCP 7000, HTTP 8000과 기록
directory는 접근이 제한된 개발 network에서만 제공한다.

## 문서

| 문서 | 역할 |
| --- | --- |
| [프로젝트 명세](docs/project-spec.md) | 제품 범위, 외부 계약과 최종 완료 조건 |
| [아키텍처](docs/architecture.md) | 채택한 설계, 모듈 경계와 내부 처리 정책 |
| [개발 계획](docs/development-plan.md) | 현재 구현 상태와 검증 대응 |
| [의존성](docs/dependencies.md) | 직접 의존성, 라이선스와 검증 환경 |
| [실행 환경](docs/deployment.md) | Container 제약, 릴리스 검증과 자원 기준 |
| [계약 출처](contracts/observation/v1/provenance.json) | Observation version 1 고정 사본의 출처와 hash |

## 이용 조건

이 Repository는 코드 검토와 참고를 위해 Public으로 제공하며 프로젝트 소스 코드에 별도 라이선스를 부여하지 않는다.
