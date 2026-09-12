# Scrap Monitoring LiDAR Visualizer

Scrap Monitoring LiDAR Generator가 전송하는 Observation version 1 stream을 Linux AMD64
server에서 검증하고 headless 3D frame으로 렌더링하는 시각화 프로그램이다. 개발 장비의
browser에는 server가 만든 최신 frame과 수신 상태를 HTTP로 제공한다.

유효한 관찰 stream을 제한된 JSON Lines 파일로 기록하고, 기록의 실행 및 simulation 구간을
재생하거나 H.264 MP4로 출력한다. LiDAR scan 생성, 높이 계산과 browser의 3D 렌더링은 이
프로젝트의 범위가 아니다.

## 주요 기능

- TCP 기반 Observation version 1 수신과 계약 검증
- 실행 전환, 재접속과 sequence 연속성 판정
- 적재 공간, 표면, 센서와 투입구의 결정론적인 3D mesh 렌더링
- 최신 frame과 상태의 HTTP preview
- 상한이 있는 원본 기록, 구간 재생과 MP4 출력
- GPU와 물리 화면이 필요 없는 Mesa 기반 Linux AMD64 container

## 빠른 시작

사전 조건은 Linux AMD64와 Docker Engine이다. 저장소를 Checkout한 뒤 저장소 루트에서
공개 합성 계약 fixture를 MP4로 렌더링한다.

```bash
docker build \
  --platform linux/amd64 \
  --tag scrap-monitoring-lidar-visualizer:quick-start \
  .

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
  scrap-monitoring-lidar-visualizer:quick-start \
  replay /input/observation.v1.jsonl \
  --output /output/replay.mp4
```

첫 유효 결과는 `artifacts/quick-start/replay.mp4`다.

## 설정

Live mode는 Observation TCP listen 주소와 port, preview HTTP listen 주소와 port를 필수로
받는다. 기록을 활성화하면 출력 경로와 byte 및 record 상한을 함께 지정한다. Replay mode는
JSON Lines 입력과 MP4 출력 또는 HTTP preview 중 하나를 선택한다. 전체 CLI option과 실행
예시는 [실행 환경](docs/deployment.md)에서 확인한다.

## 개발 및 검증

사전 조건은 Python 3.14.7, uv 0.12.13과 Docker Engine이다. 저장소 루트에서 고정된 개발
환경과 전체 검사를 실행한다.

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

Release workflow의 배포 산출물은 Linux AMD64용 Public GHCR(GitHub Container Registry)
image와 GitHub Release의 Python package, image digest, 의존성 inventory, 고지 및
checksum이다. 배포 환경은 Release의 digest를 사용하며 tag를 직접 사용하지 않는다.
Container 실행 경계와 자원 기준은 [실행 환경](docs/deployment.md)을 따른다.

## 문서

| 문서 | 역할 |
| --- | --- |
| [프로젝트 명세](docs/project-spec.md) | 제품 범위, 외부 계약과 최종 완료 조건 |
| [아키텍처](docs/architecture.md) | 채택한 설계, 모듈 경계와 내부 처리 정책 |
| [개발 계획](docs/development-plan.md) | 현재 구현 상태와 검증 대응 |
| [의존성](docs/dependencies.md) | 직접 의존성, 라이선스와 검증 환경 |
| [실행 환경](docs/deployment.md) | CLI, container 실행 경계와 릴리스 산출물 |
| [계약 출처](contracts/observation/v1/provenance.json) | Observation version 1 고정 사본의 출처와 hash |

## 이용 조건

이 Repository는 코드 검토와 참고를 위해 Public으로 제공하며 프로젝트 소스 코드에 별도 라이선스를 부여하지 않는다.
