import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.check_release import validate_release


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
        self.git("commit", "--allow-empty", "-m", "Initial fixture")
        self.base = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        self.git("tag", "v1.2.3", self.base)

    def test_version_tag_on_main(self):
        self.assertEqual(validate_release(self.root, "v1.2.3", self.base), "1.2.3")

    def test_annotated_tag_on_main(self):
        self.git("tag", "-a", "v1.2.4", "-m", "Annotated fixture", self.base)
        self.assertEqual(validate_release(self.root, "v1.2.4", "v1.2.4"), "1.2.4")

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


if __name__ == "__main__":
    unittest.main()
