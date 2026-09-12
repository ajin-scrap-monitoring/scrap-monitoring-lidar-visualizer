# 실행 환경

## 현재 산출물

현재 package는 TCP 수신, 제한된 기록, 기록 재생, 렌더링 자식 process, HTTP preview와
H.264 MP4 출력을 연결하는 `lidar-visualizer` CLI를 제공한다. Container 검증은 실제
loopback TCP 입력, live 및 replay HTTP 응답, 제품 PNG와 ffprobe 영상 구조를 확인한다.
최종 image entrypoint와 port 선언은 P7에서 적용한다.

Container는 Linux AMD64에서 UID와 GID 10001인 비root 사용자로 실행한다. Root filesystem은
read-only이고 `/tmp`와 `/output`만 writable 경로다. Runtime probe는 `DISPLAY` 환경 변수,
`/dev/dri` GPU device와 root 권한이 있으면 실패한다.

## Live 실행

TCP 수신과 HTTP preview를 함께 실행한다.

```bash
uv run lidar-visualizer live \
  --tcp-host 127.0.0.1 \
  --tcp-port 7000 \
  --http-host 127.0.0.1 \
  --http-port 8000
```

원본 기록을 활성화할 때는 출력 경로와 byte 및 record 한도를 모두 지정한다.

```bash
uv run lidar-visualizer live \
  --tcp-host 127.0.0.1 \
  --tcp-port 7000 \
  --http-host 127.0.0.1 \
  --http-port 8000 \
  --record observations.ndjson \
  --record-max-bytes 104857600 \
  --record-max-records 100000
```

Browser는 `/`에서 화면, `/frame.png`에서 최신 frame, `/status`에서 수신 및 렌더링 상태를
조회한다. HTTP 경계에는 인증과 TLS(Transport Layer Security)가 없으므로 제한된 개발
network에서만 노출한다.

## Replay 실행

단일 실행 기록은 `--run-id` 없이 MP4로 출력할 수 있다. 여러 실행이 포함된 기록은
`--run-id`를 지정한다.

```bash
uv run lidar-visualizer replay observations.jsonl \
  --output replay.mp4 \
  --start 10 \
  --end 40 \
  --time-scale 2 \
  --fps 10
```

같은 HTTP 경계에서 기록을 재생한다.

```bash
uv run lidar-visualizer replay observations.jsonl \
  --http-host 127.0.0.1 \
  --http-port 8000 \
  --duration 30
```

`--duration`과 `--time-scale`은 함께 지정하지 않는다. MP4는 기존 파일을 덮어쓰지 않으며
같은 출력 directory의 부분 파일을 FFmpeg 및 ffprobe 검증 뒤 최종 경로에 연결한다.

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
검사하고 ffprobe로 H.264 codec과 영상 해상도를 확인한다.

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

2026-09-12 Linux AMD64 host에서 Docker Engine 29.5.2로 측정한 결과는 다음과 같다. 배포
환경의 Docker Engine 29.8.0 검증은 P7 container 검증에 포함한다.

| 입력 | Frame | 총 rendering | 최대 RSS |
| --- | --- | --- | --- |
| 격자 node 825개 | 640 x 360, 10 frame | 0.580초 | 367.535 MiB |
| 격자 node 262,144개 | 640 x 360, 1 frame | 0.575초 | 457.273 MiB |

현재 image 크기는 391.865 MiB다. 측정값은 성능 보장이 아니라 동일 상한에서 회귀를 비교하기
위한 기준이다.
