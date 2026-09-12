# 의존성

## 직접 의존성

현재 직접 의존성은 런타임 9개, 빌드 및 개발 검사 6개와 GitHub Actions 3개로 총 18개다.

### 런타임

| 의존성 | 버전 | 목적 | 공식 출처 | 라이선스 |
| --- | --- | --- | --- | --- |
| Python | 3.14.7 | 애플리케이션 실행 | [Python](https://www.python.org/downloads/release/python-3147/) | PSF-2.0 |
| FastAPI | 0.141.1 | HTTP preview application | [PyPI](https://pypi.org/project/fastapi/0.141.1/) | MIT |
| jsonschema | 4.26.0 | 고정 계약 schema 검증 | [PyPI](https://pypi.org/project/jsonschema/4.26.0/) | MIT |
| NumPy | 2.5.3 | 격자와 frame 수치 배열 | [PyPI](https://pypi.org/project/numpy/2.5.3/) | BSD-3-Clause |
| PyVista | 0.49.0 | VTK 장면과 off-screen rendering 경계 | [PyPI](https://pypi.org/project/pyvista/0.49.0/) | MIT |
| Uvicorn | 0.52.4 | HTTP preview ASGI server | [PyPI](https://pypi.org/project/uvicorn/0.52.4/) | BSD-3-Clause |
| VTK | 9.7.0 | OSMesa 기반 3D rendering | [PyPI](https://pypi.org/project/vtk/9.7.0/) | BSD-3-Clause |
| FFmpeg 및 ffprobe | 5.1.9-0+deb12u1 | H.264 MP4 encoding과 구조 검사 | [Debian](https://packages.debian.org/bookworm/ffmpeg) | GPL-2.0-or-later |
| Mesa libosmesa6 | 22.3.6-1+deb12u2 | CPU 기반 OpenGL context | [Debian](https://packages.debian.org/bookworm/libosmesa6) | MIT 및 구성 요소별 라이선스 |

Debian FFmpeg package는 GPL 기능과 libx264를 활성화한 build다. Container 배포물은 FFmpeg와
Mesa package가 설치하는 전이 구성 요소의 저작권 및 라이선스 고지를 포함한다.

### 빌드와 개발 검사

| 의존성 | 버전 | 목적 | 공식 출처 | 라이선스 |
| --- | --- | --- | --- | --- |
| uv 및 uv_build | 0.12.13 | 환경 설치, lockfile과 Python package build | [GitHub](https://github.com/astral-sh/uv) | Apache-2.0 OR MIT |
| mypy | 2.3.1 | 정적 타입 검사 | [PyPI](https://pypi.org/project/mypy/2.3.1/) | MIT |
| pytest | 9.1.1 | 자동 테스트 실행 | [PyPI](https://pypi.org/project/pytest/9.1.1/) | MIT |
| Ruff | 0.16.6 | Python 형식과 lint 검사 | [PyPI](https://pypi.org/project/ruff/0.16.6/) | MIT |
| rumdl | 0.2.70 | Markdown 검사 | [PyPI](https://pypi.org/project/rumdl/0.2.70/) | MIT |
| types-jsonschema | 4.26.0.20260518 | jsonschema 타입 정보 | [PyPI](https://pypi.org/project/types-jsonschema/4.26.0.20260518/) | Apache-2.0 |

### GitHub Actions

| 의존성 | 버전 | 목적 | 공식 출처 | 라이선스 |
| --- | --- | --- | --- | --- |
| actions/checkout | v6.1.0 | 저장소와 tag 이력 조회 | [GitHub](https://github.com/actions/checkout) | MIT |
| actions/setup-python | v6.3.0 | 검사 Python 설치 | [GitHub](https://github.com/actions/setup-python) | MIT |
| astral-sh/setup-uv | v10.0.1 | uv 설치와 package cache | [GitHub](https://github.com/astral-sh/setup-uv) | MIT |

직접 및 전이 Python 의존성과 배포 파일 hash는 `uv.lock`에 고정한다. Container base image와
uv image는 `Dockerfile`에서 digest로 고정하고 GitHub Actions는 workflow에서 commit hash로
고정한다. 최종 배포물의 전이 의존성 라이선스 감사는 P7의 공개 검증에 포함한다.

## 로컬 검증

저장소 루트에서 고정 환경을 설치한다.

```bash
uv sync --locked --all-groups
```

CI(Continuous Integration)와 같은 검사를 실행한다.

```bash
uv run --frozen rumdl check --no-config --no-cache --disable MD013 .
uv run --frozen python tools/check_repository.py
uv run --frozen ruff format --check src tests tools
uv run --frozen ruff check src tests tools
uv run --frozen mypy
uv run --frozen python -m pytest
uv run --frozen python -m compileall -q src tests tools
scripts/check-headless-container.sh
```

CI 실행 정의는 [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)에 있다. Release tag
검사는 tag 대상 commit과 원격 `main` 이력을 비교하며 Release와 image를 게시하지 않는다.
