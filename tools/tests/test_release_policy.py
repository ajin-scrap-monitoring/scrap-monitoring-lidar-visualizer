import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.check_release import project_version, validate_release


class ReleasePolicyTest(unittest.TestCase):
    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "tag.gpgsign", "false")
        (self.root / "src/scrap_monitoring_lidar_visualizer").mkdir(parents=True)
        (self.root / "pyproject.toml").write_text(
            '[project]\nversion = "1.2.3"\n', encoding="utf-8"
        )
        (self.root / "src/scrap_monitoring_lidar_visualizer/__init__.py").write_text(
            '__version__ = "1.2.3"\n', encoding="utf-8"
        )
        self.git("add", ".")
        self.git("commit", "--allow-empty", "-m", "Initial fixture")
        self.base = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        self.git("tag", "v1.2.3", self.base)

    def test_version_tag_on_main(self):
        self.assertEqual(validate_release(self.root, "v1.2.3", self.base), "1.2.3")

    def test_annotated_tag_on_main(self):
        self.git("tag", "-d", "v1.2.3")
        self.git("tag", "-a", "v1.2.3", "-m", "Annotated fixture", self.base)
        self.assertEqual(validate_release(self.root, "v1.2.3", "v1.2.3"), "1.2.3")

    def test_invalid_tag_names(self):
        for tag in ("latest", "1.2.3", "v1.2", "v1.2.3-rc1", "v1.2.3\n"):
            with self.subTest(tag=tag), self.assertRaisesRegex(ValueError, "tag must"):
                validate_release(self.root, tag, self.base)

    def test_tag_outside_main_is_rejected(self):
        self.git("commit", "--allow-empty", "-m", "Unmerged fixture")
        commit = self.git("rev-parse", "HEAD")
        self.git("tag", "v2.0.0", commit)
        with self.assertRaisesRegex(ValueError, "part of origin/main"):
            validate_release(self.root, "v2.0.0", commit)

    def test_tag_revision_mismatch_is_rejected(self):
        self.git("commit", "--allow-empty", "-m", "Another fixture")
        with self.assertRaisesRegex(ValueError, "does not identify"):
            validate_release(self.root, "v1.2.3", "HEAD")

    def test_tag_must_match_package_version(self):
        self.git("tag", "v1.2.4", self.base)
        with self.assertRaisesRegex(ValueError, "package version"):
            validate_release(self.root, "v1.2.4", self.base)

    def test_version_declarations_must_match(self):
        (self.root / "src/scrap_monitoring_lidar_visualizer/__init__.py").write_text(
            '__version__ = "2.0.0"\n', encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "do not match"):
            project_version(self.root)


if __name__ == "__main__":
    unittest.main()
