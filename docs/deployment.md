# 실행 환경

## 현재 산출물

현재 package는 TCP 수신, 제한된 기록, 기록 재생, 렌더링 자식 process, HTTP preview와
H.264 MP4 출력을 연결하는 `lidar-visualizer` CLI를 제공한다. Container 검증은 실제
loopback TCP 입력, live 및 replay HTTP 응답, 제품 PNG와 ffprobe 영상 구조를 확인한다.
Image entrypoint는 `lidar-visualizer`이고 TCP 17000과 HTTP 18000 port를 선언한다.

Container는 Linux AMD64에서 UID와 GID 10001인 비root 사용자로 실행한다. 운영 실행은 root
filesystem을 read-only로 두고 `/tmp`와 기록 또는 영상 출력 volume만 writable 경로로
제공한다. Runtime probe는 `DISPLAY` 환경 변수, `/dev/dri` GPU device와 root 권한이 있으면
실패한다.

## 사용자 실행 절차

사용자 실행, 환경 변수 주입, Generator 연결, 기록과 MP4 생성 절차의 정본은
[README](../README.md)다.

## 빌드와 검증

저장소 루트에서 image를 빌드한다.

```bash
docker build \
  --platform linux/amd64 \
  --tag scrap-monitoring-lidar-visualizer:test \
  .
```

제한된 container와 산출물 구조를 한 번에 검증한다.

```bash
scripts/check-headless-container.sh
```

검사는 network, Linux capability와 GPU device를 제공하지 않고 process 128개, CPU 2개,
memory 1 GiB로 container를 제한한다. 출력 JSON의 실행 사용자, renderer, frame 수와 해상도를
검사하고 ffprobe로 H.264 codec과 영상 해상도를 확인한다. 같은 검사에서 CLI entrypoint와
CPython, Python distribution 및 Debian package의 라이선스 고지 경로를 확인한다.

## 릴리스

`vMAJOR.MINOR.PATCH` tag는 원격 `main`에 포함된 동일 version commit만 가리킨다. Release
workflow는 Linux AMD64 image를 GHCR(GitHub Container Registry)에 version tag와
`sha-<commit>` tag로 게시한다. 두 tag는 같은 manifest digest를 가리키며 `latest` tag를
게시하지 않는다.

Workflow는 image에 SBOM(Software Bill of Materials)과 build provenance를 첨부하고 게시된
digest를 전체 컨테이너 검사에 사용한다. Package 공개 범위를 확인한 뒤 wheel, source
archive, image digest, release metadata, 의존성 inventory, 고지와 SHA-256 checksum을 draft
Release에 올리고 최종 게시한다.

[v0.4.0 Release](https://github.com/ajin-scrap-monitoring/scrap-monitoring-lidar-visualizer/releases/tag/v0.4.0)는
source commit `dbbc89c746f90c4b90a3e066c1c5cd5da8bd3482`에서 생성됐다. Release asset 7개의
SHA-256 checksum, wheel version, SLSA(Supply-chain Levels for Software
Artifacts) provenance와 SPDX(Software Package Data Exchange) 2.3 SBOM을 검증했다.
Package는 Public이며 인증 정보가 없는 Docker 설정으로 digest image를 가져올 수 있다.

현재 배포 image의 불변 참조는 Release asset `oci-image.txt`와 다음 값이다.

```text
ghcr.io/ajin-scrap-monitoring/scrap-monitoring-lidar-visualizer@sha256:b87a96bb147fbf78bae957ab6f50ee437ddd4757611de048857fa3ea19fb53a7
```

## 자원 기준

현재 기본 frame 설정과 최대 입력 예산은 다음 8개다.

| 항목 | 기준 |
| --- | --- |
| 기본 해상도 | 640 x 360 |
| 기본 FPS(Frame Per Second) | 10 |
| 최대 해상도 | 3,840 x 2,160 |
| 최대 FPS | 60 |
| 최대 frame 수 | 3,000 |
| 최대 격자 node | 262,144 |
| 최대 surface triangle | 1,048,576 |
| 최대 clipping edge 검사 | 16,777,216 |

경계 polygon은 최대 vertex 1,024개를 허용한다. 수치 상한의 정본은
[`limits.py`](../src/scrap_monitoring_lidar_visualizer/limits.py)다.

2026-09-13 Linux AMD64 host에서 Docker Engine 29.5.2로 측정한 결과는 다음과 같다.

| 입력 | Frame | 총 rendering | 최대 RSS |
| --- | --- | --- | --- |
| 격자 node 825개 | 640 x 360, 10 frame | 0.573초 | 367.945 MiB |
| 격자 node 262,144개 | 640 x 360, 1 frame | 0.583초 | 457.062 MiB |

현재 image 크기는 395.360 MiB다. 측정값은 성능 보장이 아니라 동일 상한에서 회귀를 비교하기
위한 기준이다.
