# 실행 환경

## 현재 산출물

현재 package는 TCP 관찰 수신, 렌더링 자식 process와 HTTP preview를 연결하는 Live 전용
`scrap-monitoring-visualizer` CLI(Command-Line Interface)를 제공한다. Container 검증은 실제 loopback
TCP 입력, 사선 및 상면 PNG, HTTP 응답과 수신 상태를 확인한다. Image entrypoint는
`scrap-monitoring-visualizer`이고 TCP 17000과 HTTP 18000 port를 선언한다.

Container는 Linux AMD64에서 UID(User Identifier)와 GID(Group Identifier) 10001인 비root
사용자로 실행한다. 운영 실행은 root filesystem을 read-only로 두고 `/tmp`만 tmpfs로
제공한다. Runtime probe는 `DISPLAY` 환경 변수, `/dev/dri` GPU device와 root 권한이 있으면
실패한다. 운영 관찰과 렌더링 프레임을 host filesystem에 저장하지 않는다.

## 사용자 실행 절차

환경 변수 주입, Generator 연결, Browser 주소와 상태 확인 절차의 정본은
[README](../README.md)다.

## 빌드와 검증

저장소 루트에서 image를 빌드한다.

```bash
docker build \
  --platform linux/amd64 \
  --tag scrap-monitoring-visualizer:test \
  .
```

제한된 Container와 Live 경계를 한 번에 검증한다.

```bash
scripts/check-headless-container.sh
```

검사는 외부 network, Linux capability와 GPU device를 제공하지 않고 process 128개, CPU 2개,
memory 1 GiB로 Container를 제한한다. 출력 JSON의 실행 사용자, renderer, 프레임 해상도,
사선 및 상면 장면, TCP 무응답 계약, HTTP 최신 frame revision과 의존성 고지 경로를 검사한다.

## 릴리스

`vMAJOR.MINOR.PATCH` tag는 원격 `main`에 포함된 동일 version commit만 가리킨다. Release
workflow는 Linux AMD64 image를 GHCR(GitHub Container Registry)에 version tag와
`sha-<commit>` tag로 게시한다. 두 tag는 같은 manifest digest를 가리키며 `latest` tag를
게시하지 않는다.

Workflow는 image에 SBOM(Software Bill of Materials)과 build provenance를 첨부하고 게시된
digest를 전체 Container 검사에 사용한다. Package 공개 범위를 확인한 뒤 wheel, source
archive, image digest, release metadata, 의존성 inventory, 고지와 SHA-256 checksum을 draft
Release에 올리고 최종 게시한다.

[v0.5.0 Release](https://github.com/ajin-scrap-monitoring/scrap-monitoring-visualizer/releases/tag/v0.5.0)는
source commit `920723d38fd2ffc038b73e702ff2f7580b8daceb`에서 생성된 현재 최신 불변
Release다. Release asset 7개의 SHA-256 checksum, wheel version, SLSA(Supply-chain Levels
for Software Artifacts) provenance와 SPDX(Software Package Data Exchange) 2.3 SBOM을
검증했다. Package는 Public이며 인증 정보가 없는 Docker 설정으로 digest image를 가져올 수
있다.

현재 배포 image의 불변 참조는 다음과 같다.

```text
ghcr.io/ajin-scrap-monitoring/scrap-monitoring-lidar-visualizer@sha256:d21551b5a19054bc3f0d113d416034f126daf9c19d8e0c9529cfebf1c6a0571e
```

## 자원 기준

현재 기본 프레임과 최대 입력 예산은 다음 5개다.

| 항목 | 기준 |
| --- | --- |
| 기본 해상도 | 1280 x 720 |
| 최대 해상도 | 3840 x 2160 |
| 최대 격자 node | 262,144 |
| 최대 surface triangle | 1,048,576 |
| 최대 clipping edge 검사 | 16,777,216 |

경계 polygon은 최대 vertex 1,024개를 허용한다. 수치 상한의 정본은
[`limits.py`](../src/scrap_monitoring_visualizer/limits.py)다.

2026-09-13 Linux AMD64 host에서 Docker Engine 29.5.2로 측정한 결과는 다음과 같다.

| 입력 | Frame | Rendering | 최대 RSS |
| --- | --- | --- | --- |
| 격자 node 825개 | 1280 x 720, 1 frame | 0.527초 | 410.004 MiB |
| 격자 node 262,144개 | 1280 x 720, 1 frame | 0.974초 | 535.914 MiB |

현재 게시 image 크기는 290.865 MiB다. 측정값은 성능 보장이 아니라 동일 상한에서 회귀를
비교하기 위한 기준이다.
