from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    shutil.which("git") and ROOT.joinpath(".git").exists(),
    "A Git checkout is required for secret-file ignore checks",
)
class SecretFileIgnoreTests(unittest.TestCase):
    def test_local_credentials_and_editor_backups_are_ignored(self):
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--stdin", "-z"],
            input="\0".join((".env", ".env.local", ".env~", "..env.un~", ".env.example", "")),
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            set(result.stdout.rstrip("\0").split("\0")),
            {".env", ".env.local", ".env~", "..env.un~"},
        )


if __name__ == "__main__":
    unittest.main()
