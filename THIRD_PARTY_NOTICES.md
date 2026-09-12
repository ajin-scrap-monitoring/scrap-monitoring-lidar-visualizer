# Third-party notices

이 프로젝트 소스에는 별도 라이선스를 부여하지 않는다. 외부 의존성에는 각 저작권자와
배포자가 정한 라이선스를 적용한다.

Container에 설치된 Python distribution의 라이선스와 notice 원문은
`/app/.venv/lib/python3.14/site-packages/*-*.dist-info/` 아래의 `LICENSE`, `COPYING`,
`NOTICE` 계열 파일에 포함된다. Debian package의 저작권과 라이선스 원문은
`/usr/share/doc/<package>/copyright`에 포함된다.

Release asset의 `dependency-inventory.json`은 게시 image에서 읽은 CPython, Python
distribution 및 Debian package version과 각 라이선스 원문 경로를 기록한다. 직접
의존성의 version, 목적, 출처와 라이선스는 [의존성 문서](docs/dependencies.md)에서
관리한다.
