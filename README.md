# Scrap Monitoring LiDAR Visualizer

Scrap Monitoring LiDAR Generator가 전송하는 적재 모델 관찰 데이터를 Linux AMD64 server에서
검증하고 3D 프레임으로 렌더링하는 프로그램이다. 관찰 데이터는 원시 LiDAR scan이 아니라
Generator가 계산한 현재 적재물 표면과 시나리오 상태의 전체 snapshot이다.

Visualizer는 모니터, `DISPLAY`와 GPU(Graphics Processing Unit)가 없는 Container에서
프레임을 생성한다. 개발 장비의 Browser는 HTTP(Hypertext Transfer Protocol)를 통해 최신
사선 프레임, 상면 높이 지도와 수신 상태를 확인한다. Visualizer는 관찰 이력이나 영상을
파일로 저장하지 않는다.

## 주요 기능

- TCP(Transmission Control Protocol) 기반 Observation version 1 수신과 계약 검증
- 적재 공간, 닫힌 적재 체적, sensor와 투입구의 결정론적인 3D mesh 렌더링
- 1280 x 720 기본 프레임, smooth shading과 중립색 형상 격자
- 제목과 눈금이 분리된 고정 높이 색상 범례
- 최신 사선 프레임, 상면 높이 지도와 상태를 제공하는 Browser 기반 Live preview
- Linux AMD64 비root Container와 Public GHCR(GitHub Container Registry) 이미지

## 빠른 시작

사전 조건은 Linux AMD64, Docker Engine과 `curl`이다. 저장소를 Checkout한 뒤 Repository
루트에서 최신 Release의 불변 digest 이미지를 실행한다.

```bash
cp .env.example .env

IMAGE_REF="$(
  curl --fail --location --silent --show-error \
    https://github.com/ajin-scrap-monitoring/scrap-monitoring-lidar-visualizer/releases/latest/download/oci-image.txt
)"
docker image pull "$IMAGE_REF"

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
  --publish 17000:17000 \
  --publish 18000:18000 \
  --env-file .env \
  "$IMAGE_REF" \
  live
```

상태 응답을 확인한다.

```bash
curl --fail http://127.0.0.1:18000/status
```

Browser에서 `http://127.0.0.1:18000/`을 열면 Live 화면이 표시된다. 첫 Observation을
받기 전에는 상태만 표시하고 프레임 경로는 HTTP 204를 반환한다.

## 설정

설정은 CLI(Command-Line Interface) 인자, `LIDAR_VISUALIZER_` 환경 변수, 코드 기본값
순서로 결정한다. Container 배포는 Repository 루트의 [`.env.example`](.env.example)을
복사한 `.env`로 환경 변수를 주입한다. 프로그램은 시작할 때 환경 변수를 한 번 읽는다.

환경 변수는 다음 7개다.

| 환경 변수 | CLI option | 기본값 |
| --- | --- | --- |
| `LIDAR_VISUALIZER_TCP_HOST` | `--tcp-host` | `0.0.0.0` |
| `LIDAR_VISUALIZER_TCP_PORT` | `--tcp-port` | `17000` |
| `LIDAR_VISUALIZER_HTTP_HOST` | `--http-host` | `0.0.0.0` |
| `LIDAR_VISUALIZER_HTTP_PORT` | `--http-port` | `18000` |
| `LIDAR_VISUALIZER_CAMERA` | `--camera` | `isometric` |
| `LIDAR_VISUALIZER_WIDTH` | `--width` | `1280` |
| `LIDAR_VISUALIZER_HEIGHT` | `--height` | `720` |

`CAMERA`는 `isometric` 또는 `top`이다. Browser는 설정한 camera 프레임과 상면 높이 지도를
나란히 표시한다. 해상도 상한은 3840 x 2160이다. TCP와 HTTP endpoint는 서로 달라야 하며,
유효하지 않은 설정은 종료 code 2로 보고한다.

Visualizer에는 자격 증명 설정이 없다. HTTP endpoint에는 인증과 TLS(Transport Layer
Security)가 없으므로 TCP 17000과 HTTP 18000은 접근이 제한된 개발 network에서만 제공한다.

## Generator 연결

Visualizer를 먼저 실행하면 TCP 수신 대기 상태가 된다. Generator를 먼저 실행해도 연결에
실패한 뒤 재시도하므로 시작 순서는 기능상 중요하지 않지만, 상태 확인을 위해 Visualizer를
먼저 실행하는 방식을 권장한다.

Generator에는 Visualizer server에서 공개한 TCP endpoint를 지정한다.

```bash
uv run --locked scrap-monitoring-lidar-generator \
  --config /path/to/generator.v1.json \
  --observation-host <visualizer-host> \
  --observation-port 17000
```

Generator Container에서 `<visualizer-host>`는 Container 내부에서 해석되고 접근 가능한
DNS(Domain Name System) 이름 또는 IP 주소여야 한다. 실제 사설 주소는 Public Repository에
기록하지 않는다.

수신과 렌더링 결과는 다음 경로에서 확인한다.

| 경로 | 응답 |
| --- | --- |
| `GET /` | 사선 화면, 상면 높이 지도와 상태를 표시하는 웹페이지 |
| `GET /frame.png` | 설정한 camera의 최신 PNG |
| `GET /frame-top.png` | 같은 revision의 최신 상면 PNG |
| `GET /status` | 연결, 수신, 누락과 렌더링 상태 JSON |

`/status`의 `received_sequence`와 `rendered_sequence`가 같은 값이면 최신 수신 관찰이 화면에
반영된 상태다. 연결이 끊기면 마지막 정상 관찰 화면에 disconnected 상태를 표시하고 같은
TCP port에서 다음 연결을 기다린다.

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

Visualizer Container는 영구 writable volume을 사용하지 않는다. Root filesystem은 read-only로
실행하고 런타임 cache에만 제한된 `/tmp` tmpfs를 제공한다. Image digest 선택, 자원 제한,
릴리스와 공급망 검증은 [실행 환경](docs/deployment.md)을 따른다.

## 문서

| 문서 | 역할 |
| --- | --- |
| [프로젝트 명세](docs/project-spec.md) | 초기 제품 범위와 외부 계약의 고정 입력 |
| [아키텍처](docs/architecture.md) | 현재 설계, 구현 범위와 내부 처리 정책 |
| [개발 계획](docs/development-plan.md) | 현재 구현 상태와 검증 대응 |
| [의존성](docs/dependencies.md) | 직접 의존성, 라이선스와 검증 환경 |
| [실행 환경](docs/deployment.md) | Container 제약, 릴리스 검증과 자원 기준 |
| [계약 출처](contracts/observation/v1/provenance.json) | Observation version 1 고정 사본의 출처와 hash |

## 이용 조건

이 Repository는 코드 검토와 참고를 위해 Public으로 제공하며 프로젝트 소스 코드에 별도 라이선스를 부여하지 않는다.
