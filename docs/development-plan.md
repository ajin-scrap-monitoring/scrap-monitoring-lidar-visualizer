# 개발 계획

## 문서 역할

이 문서는 현재 구현 상태, 작업 순서와 단계별 완료 조건의 정본이다. 제품 범위는
[프로젝트 명세](project-spec.md), 구현 설계는 [아키텍처](architecture.md), 협업 절차와
저장소 설정의 작업 경계는 [프로젝트 지침](../.agents/AGENTS.md)을 따른다.

## 현재 상태

P0부터 P7까지 구현과 검증이 완료됐다. [v0.1.0 Release](https://github.com/ajin-scrap-monitoring/scrap-monitoring-lidar-visualizer/releases/tag/v0.1.0)는
Linux AMD64 image, Python package, 의존성 inventory, 고지와 checksum을 제공한다. Public GHCR
image의 manifest digest는 `sha256:8573c8dea619dac0d7d18656695698abdace5eea93d653c15558bb289fa0301c`다.

고정 계약의 원본과 해시는 [provenance.json](../contracts/observation/v1/provenance.json)에
있다. 해당 사본은 로컬 생성기 저장소의 지정 commit에서 가져온 공개 합성 계약이다.
Schema가 표현하지 않는 조건과 명세의 추가 수신 및 preview 요구사항도 검증 대상이다.

## 단계와 선행 관계

개발 단계는 P0부터 P7까지 총 8개다. 각 단계의 작업은 시작 시 조직 양식의 이슈로 정의하며
단계가 여러 PR(Pull Request)을 필요로 하면 독립적으로 검증 가능한 산출물 단위로 나눈다.
선행 단계의 검증과 병합 완료를 후속 단계의 시작 조건으로 사용한다.

| 단계 | 작업 단위 | 선행 단계 | 현재 상태 |
| --- | --- | --- | --- |
| P0 | 에이전트 지침, 계약 기준과 구현 계획 | 없음 | 완료 |
| P1 | 실행 환경과 headless 렌더링 검증 | P0 | 완료 |
| P2 | 계약 parser와 실행 상태 판정 | P1 | 완료 |
| P3 | TCP(Transmission Control Protocol) 수신과 제한된 원본 기록 | P2 | 완료 |
| P4 | 결정론적인 mesh와 장면 렌더링 | P1, P2 | 완료 |
| P5 | Live CLI(Command-Line Interface)와 HTTP(Hypertext Transfer Protocol) preview 통합 | P3, P4 | 완료 |
| P6 | 기록 재생과 MP4 출력 | P3, P4, P5 | 완료 |
| P7 | 컨테이너 및 릴리스 검증 | P5, P6 | 완료 |

현재 단계의 구현 작업은 모두 완료됐다. P1에서 고정한 Python, OSMesa와 FFmpeg 조합 및
자원 기준은 [실행 환경](deployment.md)을 따른다.

## P0. 프로젝트 기준 구성

| 구분 | 내용 |
| --- | --- |
| 산출물 | 에이전트 정본과 진입점, 문서, 계약 사본 및 출처, `.gitignore`, 저장소 및 릴리스 규칙 검사 |
| 완료 조건 | 심링크 검사, 명세 원본 보존, 계약 byte 일치 및 schema 검증, 문서 링크 및 형식 검사 |

## P1. 실행 환경과 headless 렌더링 검증

| 구분 | 내용 |
| --- | --- |
| 산출물 | `pyproject.toml`, Python 버전 파일, `uv.lock`, 패키지 기본 구조와 개발 검사 설정 |
| 환경 검증 | Linux AMD64 비root 컨테이너의 단일 합성 프레임 및 짧은 MP4 생성 |
| 의존성 기록 | `docs/dependencies.md`의 직접 의존성 버전, 목적, 공식 출처, 라이선스와 포함 고지 |
| 운영 기록 | `docs/deployment.md`의 실제 빌드 및 실행 방법, writable 경로와 외부 설정 |
| 자원 측정 | 렌더링 시간과 최대 메모리, 격자 및 clipping 예산, 기본 해상도와 FPS(Frame Per Second) |
| 완료 조건 | GPU(Graphics Processing Unit)와 `DISPLAY` 없는 렌더링, ffprobe 결과 및 종료 code 확인 |

개발 검사 도구는 Ruff, mypy, pytest, rumdl의 4개다. 각 도구의 역할은 코드 lint 및 형식,
타입 검사, 자동 테스트, Markdown 검사다. 사용 버전은 lockfile과 의존성 문서에 기록한다.

CI(Continuous Integration)는 P0의 저장소 검증을 수행하고 P1부터 애플리케이션 검증을 추가한다.
공통 job 및 실행 조건과 CodeQL 설정 순서는 조직의
[CI 및 보호 규칙](https://github.com/ajin-scrap-monitoring/.github/blob/main/rulesets/README.md)을
따른다. 에이전트 심링크 검사는 사용자 홈의 도구 설치에 의존하지 않도록 workflow에서
저장소 내 실제 링크 대상을 확인한다.

## P2. 계약 parser와 실행 상태 판정

| 구분 | 내용 |
| --- | --- |
| 산출물 | 불변 레코드 모델, 원본 line 보관, schema validator와 의미 검사, 실행 상태 전이 |
| 검증 사례 | 타입 및 field 오류, 중복 key, 비유한 수치, 좌표와 배열 shape, sensor 및 투입구 제약 |
| 실행 검증 | Sequence 누락, 중복 및 역순, simulation 시각 감소, 같은 run 재접속과 정적 정보 불일치 |
| 완료 조건 | 고정 계약 파일만으로 실행되는 계약 검사와 상태 전이 단위 테스트 통과 |

계약 사본은 [계약 출처](../contracts/observation/v1/provenance.json)의 파일 해시와 대조한다.
실행 identity나 scene 비교를 JSON(JavaScript Object Notation) 문자열의 key 순서에
의존하지 않게 검증한다.

## P3. TCP 수신과 제한된 원본 기록

| 구분 | 내용 |
| --- | --- |
| 산출물 | 단일 producer 수신기, LF(Line Feed) 조립기, 재접속 처리, 기록 worker와 상태 보고 |
| 전송 검증 | Packet 분할 및 병합, LF 포함 한도 경계, 불완전 line 폐기, 추가 연결 거부, 응답 byte 부재 |
| 기록 검증 | Header부터 원본 byte 보존, 반복 header, byte 및 record 상한, queue 포화와 쓰기 실패 |
| 완료 조건 | 느린 renderer 및 저장 장치 상황에서도 제한된 메모리와 수신 진행 유지 |

기록 기능은 유효한 레코드의 prefix를 보존하는지 검증한다. 한도 도달 또는 queue 포화 뒤에도
live 상태가 갱신되는지 확인하며 부분 line과 무효 레코드가 기록에 포함되지 않게 검사한다.

## P4. Mesh와 장면 렌더링

| 구분 | 내용 |
| --- | --- |
| 산출물 | 표면과 바닥의 삼각형 mesh, 외벽, sensor, 투입구, 카메라와 overlay |
| 수치 검증 | 비대칭 Y-major 격자, 비영점 바닥 높이, concave 경계, 경계를 교차하는 cell, 퇴화 입력 |
| 결정론 검증 | 동일 입력의 vertex, face와 출력 순서 일치 |
| 장면 검증 | 사선 및 상면 카메라, filling 투입구, collecting의 비활성 투입구, 필수 overlay |
| 완료 조건 | 수치 및 구조 검증과 P1 컨테이너의 실제 프레임 생성 통과 |

격자 높이의 절대 Z 의미와 경계 교차점의 보간을 별도로 검증한다. 시각 검증은 투영 범위,
프레임 크기와 장면 요소의 상태를 사용하며 pixel 전체 snapshot을 고정하지 않는다.

## P5. Live CLI와 HTTP preview

| 구분 | 내용 |
| --- | --- |
| 산출물 | Live CLI, preview 경로, 최신 프레임 저장소와 브라우저 화면 |
| 상태 검증 | 프레임 준비 전 상태, 최신 frame revision, 수신 및 렌더링 sequence, 누락과 마지막 정상 시각 |
| 격리 검증 | 연결되지 않은 browser, 느린 browser, 요청 상한, 렌더링 지연 중 수신 진행 |
| 연결 검증 | 추가 관찰 없는 disconnect overlay 갱신, 재접속, 새 실행에서 이전 표면 제거 |
| 완료 조건 | 실제 TCP 및 HTTP 경계의 통합 검사와 live 인자 오류 검사 통과 |

공개 합성 레코드 전송기로 기본 검증을 수행한다. 로컬 생성기와의 연결 검증은 공개 합성
설정을 사용하며 생성기 내부 문서나 운영 설정을 테스트 입력으로 복사하지 않는다.

## P6. 기록 재생과 MP4

| 구분 | 내용 |
| --- | --- |
| 산출물 | Replay CLI, 실행 및 시간 구간 선택, 프레임 선택 함수와 FFmpeg 출력 경계 |
| 시각 검증 | 관찰 사이 frame 선택, 같은 시각의 관찰, 반복 header, 다중 run 선택, 빈 구간 |
| 상한 검증 | Duration 및 time scale 동시 지정, 총 frame 수, FPS 및 해상도 경계 |
| 파일 검증 | 기존 파일 보호, 출력 경로 실패, 인코딩 실패와 부분 파일 처리 |
| 완료 조건 | 같은 입력의 frame 선택 일치, replay preview 통합 검사와 ffprobe 영상 구조 검사 통과 |

예상 frame 수, 영상 길이, 해상도와 codec 정보를 검사한다. 영상 파일의 전체 byte나
pixel 값을 동일성 기준으로 사용하지 않는다.

## P7. 컨테이너와 릴리스 검증

| 구분 | 내용 |
| --- | --- |
| 산출물 | 최종 Dockerfile 및 `.dockerignore`, 배포 문서, 릴리스 workflow와 의존성 고지 |
| 실행 검증 | Linux AMD64, 비root 실행, 명시적 writable 경로, TCP 및 HTTP port별 노출 |
| 품질 검증 | 단위, 계약, 통합 및 컨테이너 검사의 CI 집계와 CodeQL 결과 |
| 공개 검증 | 전체 Git 이력 및 image의 운영 데이터 제외와 직접 및 전이 의존성 라이선스 확인 |
| 배포 검증 | Release 기준 이미지 tag, digest와 GHCR(GitHub Container Registry) Package 공개 범위 |
| 완료 조건 | 명세의 자동 검증 10개 범주 통과와 고정 digest 기반 합성 입력 수신, preview 및 영상 확인 |

Release와 Package 게시 시점은 조직 운영 절차를 따른다. 실제 장비 주소, 자격 증명과
배포 Repository의 환경값은 외부 설정으로 제공한다.

Release workflow는 tag 형식, package version과 원격 `main` 이력을 검사한다. 검사를 통과한
동일 commit으로 image와 Python package를 만들고 게시한 image digest를 다시 검증한 뒤
Release asset을 게시한다.

## 요구사항 검증 대응

명세의 자동 검증 10개 범주를 다음과 같이 배정한다.

| 명세 범주 | 담당 단계 | 검증 경계 |
| --- | --- | --- |
| 1. 계약 fixture와 schema | P2 | `tests/contract/` |
| 2. Framing과 최대 line | P3 | `tests/unit/`, `tests/integration/` |
| 3. Version, type과 field 오류 | P2 | `tests/contract/`, `tests/unit/` |
| 4. Sequence와 run 전환 | P2, P3 | `tests/unit/`, `tests/integration/` |
| 5. 표면 mesh와 clipping | P4 | `tests/unit/` |
| 6. Mesh 및 frame 선택 결정론 | P4, P6 | `tests/unit/` |
| 7. Queue와 입출력 상한 | P3, P5, P6 | `tests/unit/`, `tests/integration/` |
| 8. CLI option과 오류 종료 | P5, P6 | `tests/integration/` |
| 9. 재접속 header와 연속성 | P2, P3 | `tests/integration/` |
| 10. HTTP 최신 상태와 browser 격리 | P5 | `tests/integration/` |

컨테이너 검증은 `tests/container/`에서 위 경계의 실제 실행 조건을 확인한다. 단위 테스트가
외부 network나 형제 프로젝트 설치 상태에 의존하지 않게 구성한다.
