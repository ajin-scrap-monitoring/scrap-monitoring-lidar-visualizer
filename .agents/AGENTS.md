# 프로젝트 작업 지침

## 적용 범위

이 파일은 이 저장소의 프로젝트 지침 단일 소스다. 전역 행동 지침을 함께 적용하며,
프로젝트 컨텍스트는 이 파일과 Git으로 관리하는 프로젝트 문서에 기록한다.

현재 사용하는 Codex 진입점은 Repository 루트의 `AGENTS.md`이며 이 파일의 심링크다.
다른 도구의 진입점은 해당 도구를 실제로 사용할 때만 이 파일의 심링크로 추가한다.
진입점에 별도 지침을 작성하지 않는다.

## 문서 정본

프로젝트 입력과 설계의 정본은 다음 4개다.

| 문서 | 책임 |
| --- | --- |
| [프로젝트 명세](../docs/project-spec.md) | 제품 범위, 외부 계약과 최종 완료 조건 |
| [아키텍처](../docs/architecture.md) | 채택한 설계, 모듈 경계와 내부 처리 정책 |
| [개발 계획](../docs/development-plan.md) | 현재 구현 상태, 작업 순서와 단계별 검증 |
| [계약 출처](../contracts/observation/v1/provenance.json) | 고정 계약 사본의 원본, commit과 파일 해시 |

작업을 시작할 때 명세와 개발 계획을 읽고 해당 작업의 아키텍처 경계를 확인한다.
`docs/project-spec.md`는 고정 입력이므로 구현 과정에서 수정하지 않는다. 설계와 구현 상태가
달라지면 해당 정본만 갱신하며 같은 사실을 다른 문서에 복제하지 않는다.

## 조직 운영 규칙

조직 공통 절차의 원문은 다음 5개다.

| 원문 | 적용 대상 |
| --- | --- |
| [개발 운영 규칙](https://github.com/ajin-scrap-monitoring/.github/blob/main/GOVERNANCE.md) | 공개 범위, 이슈, 브랜치, commit, 병합과 릴리스 |
| [기여 절차](https://github.com/ajin-scrap-monitoring/.github/blob/main/CONTRIBUTING.md) | 변경 작업의 진행 순서 |
| [보안 정책](https://github.com/ajin-scrap-monitoring/.github/blob/main/SECURITY.md) | 취약점과 자격 증명 노출 보고 |
| [PR 템플릿](https://github.com/ajin-scrap-monitoring/.github/blob/main/PULL_REQUEST_TEMPLATE.md) | PR(Pull Request) 본문과 이슈 연결 |
| [ruleset 적용 절차](https://github.com/ajin-scrap-monitoring/.github/blob/main/rulesets/README.md) | 저장소 보호 규칙과 검사 구성의 선행 관계 |

조직 문서는 이 Repository의 공통 운영 규칙 정본이다. GitHub 작업 전에 관련 원문의 최신
내용을 확인하고 프로젝트 지침과 충돌하면 조직 문서를 우선한다. 공통 운영 문서와
템플릿은 이 Repository에 복제하지 않는다.

모든 변경은 다음 작업 경계를 따른다.

1. 공통 Issue 양식으로 작업을 정의하고 담당자, 조직 Project와 상태를 설정한다.
2. 최신 `main`에서 `<type>/<issue-number>-<short-description>` 형식의 브랜치를 만든다.
3. Branch, commit과 PR(Pull Request)에 같은 type을 사용하고 commit 및 PR 제목은
   `<type>: <summary>` 형식으로 작성한다.
4. 검증한 브랜치를 Push하고 `main` 대상 PR 본문에 `Closes #<issue-number>`를 작성한다.
5. 대화와 필수 검사를 완료한 뒤 Squash 방식으로 병합한다.
6. Issue 종료와 조직 Project의 `Done` 상태를 확인한다.

`main` 직접 Push, force push, Merge commit과 Rebase merge를 사용하지 않는다. 명시적인
요청 없이 commit, Push, tag, Release와 PR 병합을 수행하지 않는다. 코딩 에이전트가
작성했다는 metadata를 commit과 PR에 추가하지 않는다.

Repository 설정과 ruleset은 조직 문서의 선행 관계를 따른다. 소스 코드와 CI가 구성된
시점부터 `protect-main`, `require-ci`, `require-codeql`을 함께 Active 상태로 유지하고
Release tag에는 `protect-release-tags`를 적용한다. CI job 이름은 `CI`이며 `main` 대상 PR과
`main` Push에서 전체 검사를 실행한다. CodeQL은 Default setup을 사용한다.

## Public과 보안 경계

이 Repository에는 Public 소스, 외부 배포가 허용된 설정, Public 사양으로 만든 합성
fixture, 기술 문서와 Release 산출물만 포함한다. 다음 정보는 Git 이력과 컨테이너 이미지를
포함한 Public 산출물에 넣지 않는다.

- 외부에서 제공받은 원본 문서와 파일
- 현장 사진, 내부 치수와 내부 측정값
- Private 원본에서 파생된 사실과 데이터
- 자격 증명, 비밀키, token과 password
- 실제 사설 IP 주소와 내부 network 세부 정보
- 실제 운영 로그, 영상과 sensor 원본 데이터
- 개인 프로젝트 관리 문서와 Private 회의 자료

보안 취약점과 자격 증명 노출은 Public Issue, Discussion 또는 PR로 보고하지 않고
Repository의 Private vulnerability reporting을 사용한다. 실제 주소, 운영 설정과 자격
증명은 실행 시 외부에서 제공한다.

## 의존성과 릴리스 경계

프로젝트 소스 코드에 별도 라이선스를 부여하지 않으며 `LICENSE` 파일을 만들지 않는다.
직접 의존성은 version, 목적, 공식 출처와 license를 Repository 문서에 기록한다. 외부
의존성의 license와 NOTICE 요구사항을 유지하고 Public Release 전에 직접 및 전이 의존성을
감사한다.

OCI(Open Container Initiative) 이미지는 Public GHCR(GitHub Container Registry)
Package로 게시한다. Release version에서 파생한 `MAJOR.MINOR.PATCH`와
`sha-<full-git-sha>` tag만 사용하고 `latest`를 게시하지 않는다. Version tag는 원격
`main` 이력에 포함된 commit을 가리키는 `vMAJOR.MINOR.PATCH` 형식만 사용한다. 배포
Repository는 `ghcr.io/<organization>/<image>@sha256:<digest>` 형식으로 이미지를 고정한다.

## 코드와 입력 경계

프로그램 구현 경로는 `src/scrap_monitoring_lidar_visualizer/`이고 자동 검증 경로는
`tests/`다. 코드와 테스트 디렉토리는 해당 구현 단계에서 생성한다.

`contracts/observation/v1/`의 계약 사본은 원본 byte를 보존한다. 형식 정리나 로컬 요구사항을
위한 schema 수정을 하지 않는다. 추가 검증 사례는 `tests/`에서 공개 합성 fixture를
기반으로 구성한다. 계약 검사는 저장소에 고정한 사본을 사용한다.

`~/scrap-monitoring-lidar-generator`는 계약과 publisher 동작을 확인하는 읽기 전용 참고
프로젝트다. 생성기 구현을 실행 의존성으로 추가하지 않는다. 참고 범위는 공개 계약,
`docs/visualizer-requirements.md`, `docs/observation.md`와 관련 공개 소스 및 테스트다.

운영 관찰 기록과 영상의 데이터 분류는 프로젝트 명세를 따르고, 제외 패턴은 `.gitignore`에서
관리한다. 생성기의 `docs/internal/`과 운영 산출물에서 공개 문서나 테스트 값을 만들지 않는다.

## 작업 검증

변경 범위에 해당하는 개발 계획의 완료 조건을 검증한다. 실행하지 않은 검사나 준비만 된
구현을 완료로 표시하지 않는다. 작업 결과에는 검증 결과와 남은 선행 조건을 포함한다.

에이전트 구조를 변경하면 `.agents/AGENTS.md`가 일반 파일인지 확인하고 현재 사용하는 각
도구의 진입점이 이 파일을 가리키는 심링크인지 검사한다. 사용하지 않는 도구의 진입점이
없는 상태는 오류가 아니다.
