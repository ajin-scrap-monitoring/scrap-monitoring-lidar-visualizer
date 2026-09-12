# 검증 환경

## 의존성

현재 직접 의존성은 검증 실행 도구 7개와 GitHub Actions 3개다. Python 버전은 저장소 검사
도구의 실행 기준이며 애플리케이션의 런타임 선택은 개발 계획 P1을 따른다.

| 의존성 | 버전 | 목적 | 공식 출처 | 라이선스 |
| --- | --- | --- | --- | --- |
| Python | 3.14.4 | 저장소 검사와 표준 라이브러리 테스트 실행 | [Python](https://www.python.org/downloads/release/python-3144/) | PSF-2.0 |
| uv | 0.12.12 | 검증 환경 설치와 의존성 고정 | [uv](https://github.com/astral-sh/uv) | Apache-2.0 OR MIT |
| jsonschema | 4.26.0 | 고정 계약 schema 및 fixture 검사 | [PyPI](https://pypi.org/project/jsonschema/4.26.0/) | MIT |
| mypy | 2.3.1 | 검증 도구의 정적 타입 검사 | [PyPI](https://pypi.org/project/mypy/2.3.1/) | MIT |
| Ruff | 0.16.6 | Python 형식과 lint 검사 | [PyPI](https://pypi.org/project/ruff/0.16.6/) | MIT |
| rumdl | 0.2.70 | Markdown 검사 | [PyPI](https://pypi.org/project/rumdl/0.2.70/) | MIT |
| types-jsonschema | 4.26.0.20260518 | jsonschema 타입 정보 | [PyPI](https://pypi.org/project/types-jsonschema/4.26.0.20260518/) | Apache-2.0 |
| actions/checkout | v6.1.0 | 저장소와 tag 이력 조회 | [GitHub](https://github.com/actions/checkout) | MIT |
| actions/setup-python | v6.3.0 | 검사 Python 설치 | [GitHub](https://github.com/actions/setup-python) | MIT |
| astral-sh/setup-uv | v10.0.1 | uv 설치 | [GitHub](https://github.com/astral-sh/setup-uv) | MIT |

직접 Python 의존성은 `tools/requirements-ci.in`, 전이 의존성과 배포 파일 해시는
`tools/requirements-ci.txt`에 고정한다. GitHub Actions는 workflow에서 전체 commit 해시로
고정한다. 검증 환경은 라이브러리 배포 파일의 license 고지를 유지한다.

## 로컬 검증

저장소 루트에서 검증 환경을 설치한다.

```bash
uv venv --python 3.14.4 .venv
uv pip sync --python .venv/bin/python --require-hashes tools/requirements-ci.txt
```

검증은 다음 명령으로 실행한다.

```bash
.venv/bin/rumdl check --no-config --no-cache --disable MD013 .
.venv/bin/python tools/check_repository.py
.venv/bin/ruff format --check tools
.venv/bin/ruff check --select E4,E7,E9,F,I,B,UP tools
.venv/bin/mypy --strict --python-version 3.14 tools/check_repository.py tools/check_release.py
.venv/bin/python -m unittest discover -s tools/tests -v
.venv/bin/python -m compileall -q tools
```

CI(Continuous Integration)의 실행 정의는
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml)에 있다. 릴리스 tag 검사는 tag 대상
commit과 원격 `main` 이력을 비교하며 Release와 이미지를 게시하지 않는다.
