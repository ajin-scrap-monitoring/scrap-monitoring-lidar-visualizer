import argparse
import re
import subprocess
from pathlib import Path


def resolve_commit(root: Path, revision: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}"],
        cwd=root,
        text=True,
    ).strip()


def validate_release(root: Path, tag: str, revision: str) -> str:
    if re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag) is None:
        raise ValueError("Release tag must have the form vMAJOR.MINOR.PATCH")
    commit = resolve_commit(root, revision)
    if resolve_commit(root, f"refs/tags/{tag}") != commit:
        raise ValueError("Release tag does not identify the supplied commit")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "refs/remotes/origin/main"],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("Release commit must be part of origin/main")
    return tag[1:]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the release tag and main ancestry."
    )
    parser.add_argument("--tag", required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    version = validate_release(Path.cwd(), args.tag, args.revision)
    print(f"OK: release target {version}")


if __name__ == "__main__":
    main()
