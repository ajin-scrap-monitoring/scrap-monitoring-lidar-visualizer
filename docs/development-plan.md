# 개발 계획

## 문서 역할

이 문서는 현재 구현 상태, 작업 순서와 단계별 완료 조건의 정본이다. 초기 제품 범위는
[프로젝트 명세](project-spec.md), 구현 설계는 [아키텍처](architecture.md), 협업 절차와
저장소 설정의 작업 경계는 [프로젝트 지침](../.agents/AGENTS.md)을 따른다.

## 현재 상태

P0부터 P7까지 총 8개 단계의 구현과 검증이 완료됐다. 현재 제품은 Observation version 1을
수신해 고정 사선 3D 프레임 하나를 Browser에 실시간 제공한다. 관찰 기록, Replay와 MP4
출력은 제공하지 않는다.

`docs/project-spec.md`는 고정 입력이므로 수정하지 않는다. 해당 문서의 기록, Replay, MP4와
상면 camera 요구사항은 현재 제품 결정과 일치하지 않으며 완료 조건으로 사용하지 않는다.
이 범위를 다시 요구하려면 고정 입력의 새 version을 별도로 제공해야 한다.

고정 계약의 원본과 해시는 [provenance.json](../contracts/observation/v1/provenance.json)에
있다. Schema가 표현하지 않는 조건과 추가 수신 및 preview 요구사항도 검증 대상이다.

## 단계와 선행 관계

| 단계 | 작업 단위 | 선행 단계 | 현재 상태 |
| --- | --- | --- | --- |
| P0 | 에이전트 지침, 계약 기준과 구현 계획 | 없음 | 완료 |
| P1 | 실행 환경과 headless 렌더링 | P0 | 완료 |
| P2 | 계약 parser와 실행 상태 판정 | P1 | 완료 |
| P3 | TCP(Transmission Control Protocol) 수신 | P2 | 완료 |
| P4 | 결정론적인 mesh와 장면 렌더링 | P1, P2 | 완료 |
| P5 | Live CLI(Command-Line Interface)와 HTTP(Hypertext Transfer Protocol) preview | P3, P4 | 완료 |
| P6 | Container, CI(Continuous Integration)와 릴리스 | P5 | 완료 |
| P7 | 환경 변수와 사용자 배포 절차 | P6 | 완료 |

각 변경은 시작 시 조직 양식의 이슈로 정의한다. 단계가 여러 PR(Pull Request)을 필요로 하면
독립적으로 검증 가능한 산출물 단위로 나눈다.

## P0. 프로젝트 기준

| 구분 | 내용 |
| --- | --- |
| 산출물 | 에이전트 정본과 진입점, 문서, 계약 사본과 출처, 저장소 및 릴리스 규칙 검사 |
| 완료 조건 | 심링크 검사, 명세 원본 보존, 계약 byte 일치, schema와 문서 검사 |

## P1. 실행 환경과 headless 렌더링

| 구분 | 내용 |
| --- | --- |
| 산출물 | Python package, 고정 lockfile과 Mesa 기반 off-screen 렌더링 |
| 환경 검증 | Linux AMD64 비root Container의 1280 x 720 합성 프레임 생성 |
| 자원 측정 | 기본 및 최대 격자 rendering 시간과 최대 memory |
| 완료 조건 | GPU와 `DISPLAY` 없는 실제 PNG 생성 및 유한한 자원 사용 |

개발 검사 도구는 Ruff, mypy, pytest와 rumdl의 4개다. CI는 저장소 검사, 정적 검사, 전체
테스트와 실제 Container 검사를 `CI` job으로 집계한다. CodeQL은 Repository Default setup을
사용한다.

## P2. 계약 parser와 실행 상태 판정

| 구분 | 내용 |
| --- | --- |
| 산출물 | 불변 레코드 model, schema validator, 의미 검사와 실행 상태 전이 |
| 검증 사례 | 타입 및 field 오류, 중복 key, 비유한 수치, 좌표와 배열 shape, sensor와 투입구 제약 |
| 실행 검증 | Sequence 누락, 중복 및 역순, simulation 시각 감소, 같은 run 재접속과 정적 정보 불일치 |
| 완료 조건 | 설치 package와 고정 계약 사본을 사용하는 계약 및 상태 전이 검사 통과 |

## P3. TCP 수신

| 구분 | 내용 |
| --- | --- |
| 산출물 | 단일 producer 수신기, LF(Line Feed) 조립기와 재접속 처리 |
| 전송 검증 | Packet 분할 및 병합, framing 오류 전 완료 prefix, LF 포함 한도, 추가 연결 거부, 응답 byte 부재 |
| 상태 검증 | 최신 전체 Observation 교체, 무효 레코드 거부와 수신 통계 |
| 완료 조건 | 느린 renderer 상황에서도 제한된 메모리와 수신 진행 유지 |

## P4. Mesh와 장면 렌더링

| 구분 | 내용 |
| --- | --- |
| 산출물 | 표면, 닫힌 적재 체적, 바닥, 외벽, 투입구, 카메라와 overlay |
| 수치 검증 | 비대칭 Y-major 격자, 비영점 바닥 높이, concave 경계, 경계를 교차하는 cell, 퇴화 입력 |
| 장면 검증 | 직교 투영, 1280 x 720 기본값, smooth shading, 우측 외벽 높이 눈금과 격자 |
| 완료 조건 | 구조 및 수치 검사와 실제 사선 프레임 생성 통과 |

사선 화면은 우측 외벽 변에 바닥과 상단을 포함한 2 m 간격 높이 눈금을 표시한다. 눈금 숫자는
프레임 높이에 맞춰 16부터 28까지 조정한다. 프레임 overlay는 실행 식별자와 누락 수를
제외하고 연결과 관찰 상태를 표시한다.

## P5. Live CLI와 HTTP preview

| 구분 | 내용 |
| --- | --- |
| 산출물 | Live CLI, 최신 프레임 저장소, preview 경로와 Browser 화면 |
| 상태 검증 | 프레임 준비 전 상태, revision, 수신 및 렌더링 sequence, 누락과 마지막 정상 시각 |
| 격리 검증 | 연결되지 않은 Browser, 느린 Browser, 요청 상한, 최신 pending 1개와 수신 진행 |
| 연결 검증 | 추가 관찰 없는 disconnect overlay 갱신, 재접속, 새 실행에서 이전 표면 제거 |
| 완료 조건 | 실제 TCP 및 HTTP 경계의 통합 검사와 Live 인자 오류 검사 통과 |

## P6. Container, CI와 릴리스

| 구분 | 내용 |
| --- | --- |
| 산출물 | Linux AMD64 image, CI, Release workflow와 의존성 고지 |
| 실행 검증 | 비root, read-only root filesystem, TCP와 HTTP port, 환경 변수와 CLI 우선순위 |
| 품질 검증 | 단위, 계약, 통합 및 Container 검사의 CI 집계와 CodeQL 결과 |
| 배포 검증 | Version tag, source tag, digest, OCI label, SBOM과 build provenance |
| 완료 조건 | 고정 digest image의 Live 수신, Browser preview와 공개 Package 확인 |

## P7. 환경 변수와 사용자 배포 절차

| 구분 | 내용 |
| --- | --- |
| 산출물 | 6개 Live 환경 변수, `.env.example`, 자기완결적 README와 배포 문서 |
| 설정 검증 | 필수값, 숫자 변환, CLI override와 endpoint 충돌 |
| Container 검증 | 환경 변수 기반 Live 설정과 실제 TCP 및 HTTP 통합 |
| 문서 검증 | 불변 image 선택, 환경 변수 주입, Generator 연결과 상태 확인 |
| 완료 조건 | README의 실행 명령과 전체 자동 검사 통과 |

## 요구사항 검증 대응

현재 제품 검증은 다음 8개 범주로 구성한다.

| 범주 | 담당 단계 | 검증 경계 |
| --- | --- | --- |
| 계약 fixture와 schema | P2 | `tests/contract/` |
| Framing과 최대 line | P3 | `tests/unit/`, `tests/integration/` |
| Version, type과 field 오류 | P2 | `tests/contract/`, `tests/unit/` |
| Sequence와 run 전환 | P2, P3 | `tests/unit/`, `tests/integration/` |
| 표면 mesh와 clipping | P4 | `tests/unit/` |
| Queue, frame과 해상도 상한 | P4, P5 | `tests/unit/`, `tests/integration/` |
| Live CLI option과 오류 종료 | P5 | `tests/unit/` |
| HTTP 최신 상태와 Browser 격리 | P5 | `tests/integration/` |

Container 검증은 `scripts/check-headless-container.sh`에서 실제 실행 경계를 확인한다. 단위
테스트는 외부 network나 형제 프로젝트 설치 상태에 의존하지 않는다.
