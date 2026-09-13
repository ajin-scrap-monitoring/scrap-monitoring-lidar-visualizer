import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from jsonschema.exceptions import ValidationError

from tools.check_repository import check_agent_links, check_contracts


class RepositoryChecksTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        source = Path(__file__).resolve().parents[2]
        for name in (".agents", "contracts", "docs"):
            shutil.copytree(source / name, self.root / name)
        packaged = "src/scrap_monitoring_visualizer/contracts/schema"
        shutil.copytree(source / packaged, self.root / packaged)
        for name, target in (
            ("AGENTS.md", ".agents/AGENTS.md"),
            ("GEMINI.md", ".agents/AGENTS.md"),
            (".claude/CLAUDE.md", "../.agents/AGENTS.md"),
        ):
            entry = self.root / name
            entry.parent.mkdir(parents=True, exist_ok=True)
            entry.symlink_to(target)

    def test_current_contract_and_agent_structure(self):
        check_agent_links(self.root)
        check_contracts(self.root)

    def test_missing_claude_entry_is_rejected(self):
        (self.root / ".claude/CLAUDE.md").unlink()
        with self.assertRaisesRegex(ValueError, "Missing instruction symlink"):
            check_agent_links(self.root)

    def test_copied_instruction_entry_is_rejected(self):
        entry = self.root / "GEMINI.md"
        entry.unlink()
        entry.write_text("# Separate instructions\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Missing instruction symlink"):
            check_agent_links(self.root)

    def test_contract_byte_change_is_rejected(self):
        fixture = self.root / "contracts/observation/v1/fixtures/observation.v1.jsonl"
        fixture.write_bytes(fixture.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Contract checksum mismatch"):
            check_contracts(self.root)

    def test_packaged_contract_change_is_rejected(self):
        schema = (
            self.root
            / "src/scrap_monitoring_visualizer/contracts/schema/v1/header.schema.json"
        )
        schema.write_bytes(schema.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Packaged contract differs"):
            check_contracts(self.root)

    def test_invalid_record_is_rejected_even_with_matching_checksum(self):
        base = self.root / "contracts/observation/v1"
        fixture = base / "fixtures/observation.v1.jsonl"
        lines = fixture.read_text(encoding="utf-8").splitlines()
        record = json.loads(lines[1])
        record["unexpected"] = True
        fixture.write_text(
            lines[0] + "\n" + json.dumps(record) + "\n", encoding="utf-8"
        )
        manifest = base / "provenance.json"
        provenance = json.loads(manifest.read_text(encoding="utf-8"))
        provenance["files"]["fixtures/observation.v1.jsonl"]["sha256"] = hashlib.sha256(
            fixture.read_bytes()
        ).hexdigest()
        manifest.write_text(json.dumps(provenance), encoding="utf-8")
        with self.assertRaises(ValidationError):
            check_contracts(self.root)


if __name__ == "__main__":
    unittest.main()
