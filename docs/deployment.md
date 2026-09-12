# 실행 환경

## 현재 산출물

현재 container는 합성 표면의 PNG 및 H.264 MP4와 고정 계약 fixture의 제품 장면을 OSMesa로
rendering한다. 제품 장면 검증은 사선 및 상면 camera, 경계 clipping mesh, 장면 요소와 상태
overlay를 포함한다. TCP 수신 port와 HTTP preview port는 아직 제공하지 않는다.

Container는 Linux AMD64에서 UID와 GID 10001인 비root 사용자로 실행한다. Root filesystem은
read-only이고 `/tmp`와 `/output`만 writable 경로다. Runtime probe는 `DISPLAY` 환경 변수,
`/dev/dri` GPU device와 root 권한이 있으면 실패한다.

## 빌드와 검증

저장소 루트에서 image를 빌드한다.

```bash
docker build \
  --platform linux/amd64 \
  --tag scrap-monitoring-lidar-visualizer:p1 \
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
