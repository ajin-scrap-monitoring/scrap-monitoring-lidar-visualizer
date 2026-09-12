import hashlib
import json
import re
import subprocess
from pathlib import Path

from jsonschema import Draft202012Validator

SPEC_SHA256 = "e07b9ea9b2c8512fd30f8e8025c8fa9a85b9b3ed154a0a5c8120a440255216ed"
AGENT_LINKS = {
    "AGENTS.md": ".agents/AGENTS.md",
    "GEMINI.md": ".agents/AGENTS.md",
    ".claude/CLAUDE.md": "../.agents/AGENTS.md",
}
CONTRACT_FILES = {
    "header.schema.json",
    "observation.schema.json",
    "fixtures/observation.v1.jsonl",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def check_agent_links(root: Path) -> None:
    source = root / ".agents/AGENTS.md"
    require(
        source.is_file() and not source.is_symlink(),
        "Missing regular instruction source",
    )
    for name, target in AGENT_LINKS.items():
        entry = root / name
        require(entry.is_symlink(), f"Missing instruction symlink: {name}")
        require(
            str(entry.readlink()) == target, f"Unexpected instruction target: {name}"
        )
        require(
            entry.resolve() == source.resolve(),
            f"Unresolved instruction target: {name}",
        )
    rule = root / ".agents/rules/project.md"
    content = rule.read_text(encoding="utf-8")
    require(
        content.startswith("---\ntrigger: always_on\n---\n"), "Missing Always On rule"
    )
    require("\n@../AGENTS.md\n" in content, "Missing Antigravity instruction reference")


def check_contracts(root: Path) -> None:
    spec = (root / "docs/project-spec.md").read_bytes()
    require(
        hashlib.sha256(spec).hexdigest() == SPEC_SHA256, "Project specification changed"
    )
    base = root / "contracts/observation/v1"
    provenance = json.loads((base / "provenance.json").read_text(encoding="utf-8"))
    require(
        set(provenance["files"]) == CONTRACT_FILES, "Unexpected contract file manifest"
    )
    require(
        provenance["commit"].encode() in spec,
        "Contract commit differs from specification",
    )
    for name, metadata in provenance["files"].items():
        digest = hashlib.sha256((base / name).read_bytes()).hexdigest()
        require(digest == metadata["sha256"], f"Contract checksum mismatch: {name}")
    validators = []
    for name in ("header.schema.json", "observation.schema.json"):
        schema = json.loads((base / name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validators.append(Draft202012Validator(schema))
    fixture = (base / "fixtures/observation.v1.jsonl").read_bytes()
    require(fixture.endswith(b"\n"), "Contract fixture must end with LF")
    records = fixture.splitlines(keepends=True)
    require(
        len(records) == 2,
        "Expected one header and one observation in the fixed fixture",
    )
    for validator, raw in zip(validators, records, strict=True):
        require(len(raw) <= 1_048_576, "Contract record exceeds the framing limit")
        validator.validate(json.loads(raw))


def check_documents(root: Path) -> None:
    tracked = subprocess.check_output(["git", "ls-files", "-z", "--", "*.md"], cwd=root)
    for name in tracked.decode().split("\0"):
        if not name:
            continue
        document = root / name
        if document.is_symlink():
            continue
        content = document.read_text(encoding="utf-8")
        require("**" not in content, f"Unexpected bold formatting: {name}")
        require(
            re.search(r"[^\t\n\r\x20-\x7e\u3131-\u318e\uac00-\ud7a3]", content) is None,
            f"Unexpected document character: {name}",
        )
        for target in re.findall(r"\]\(([^)]+)\)", content):
            if target.startswith(("https://", "http://", "#")):
                continue
            destination = (document.parent / target.split("#")[0]).resolve()
            require(
                destination.is_relative_to(root.resolve()),
                f"Link leaves repository: {name}",
            )
            require(destination.exists(), f"Broken local link: {name}: {target}")


def check_ignored_outputs(root: Path) -> None:
    outputs = [
        "recordings/run.jsonl",
        "frames/frame.png",
        "videos/run.mp4",
        "runtime/state.json",
        "docs/internal/site.md",
        ".env",
        "scratch.ndjson",
        "render.partial",
        "run.log",
    ]
    fixture = "contracts/observation/v1/fixtures/observation.v1.jsonl"
    for name in [*outputs, fixture]:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", name],
            cwd=root,
            check=False,
        )
        expected = 1 if name == fixture else 0
        require(result.returncode == expected, f"Unexpected Git ignore policy: {name}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    for check in (
        check_agent_links,
        check_contracts,
        check_documents,
        check_ignored_outputs,
    ):
        check(root)
        print(f"OK: {check.__name__}")


if __name__ == "__main__":
    main()
