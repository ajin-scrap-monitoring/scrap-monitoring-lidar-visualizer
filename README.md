# Scrap Monitoring LiDAR Visualizer

LiDAR(Light Detection and Ranging) 적재 모델 관찰 데이터를 서버에서 시각화하는 프로젝트다.

## 프로젝트 문서

진입 문서는 다음 5개다.

| 문서 | 내용 |
| --- | --- |
| [프로젝트 명세](docs/project-spec.md) | 고정 요구사항과 완료 조건 |
| [개발 계획](docs/development-plan.md) | 현재 상태와 단계별 구현 작업 |
| [아키텍처](docs/architecture.md) | 채택한 구현 설계 |
| [프로젝트 작업 지침](.agents/AGENTS.md) | 에이전트 작업 경계와 조직 운영 문서 |
| [검증 환경](docs/dependencies.md) | 검증 의존성과 로컬 실행 방법 |

## 에이전트 디렉토리

에이전트 구성은 정본 1개, 심링크 3개와 Antigravity 참조 규칙 1개다.

```text
.agents/
  AGENTS.md
  rules/
    project.md
.claude/
  CLAUDE.md -> ../.agents/AGENTS.md
AGENTS.md -> .agents/AGENTS.md
GEMINI.md -> .agents/AGENTS.md
```

Antigravity는 [공식 프로젝트 규칙 경로](https://www.antigravity.google/docs/rules-workflows/)인
`.agents/rules/`에서 `project.md`를 읽는다. 해당 규칙은 Always On으로 공통 정본을 참조한다.

## 이용 조건

이 Repository는 코드 검토와 참고를 위해 Public으로 제공하며 프로젝트 소스 코드에 별도 라이선스를 부여하지 않는다.
