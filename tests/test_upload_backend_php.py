import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PWSH = shutil.which("pwsh")


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@unittest.skipUnless(PWSH, "PowerShell 7 is required for PHP upload-script tests")
class BackendPhpUploadTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(
            dir=ROOT, prefix=".php-deploy-test-"
        )
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name).joinpath("repo with spaces")
        scripts = self.root.joinpath("scripts")
        scripts.mkdir(parents=True)
        self.script = scripts.joinpath("upload-backend-php.ps1")
        shutil.copyfile(ROOT.joinpath("scripts", self.script.name), self.script)
        scripts.joinpath("ftps.psm1").write_text(
            r"""
function Send-FtpsDirectory {
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [string] $SourcePath,
        [string] $FtpHost,
        [string] $RemotePath,
        [PSCredential] $Credential,
        [string] $PublishLast
    )
    $files = @{}
    Get-ChildItem -LiteralPath $SourcePath -File -Recurse -Force | ForEach-Object {
        $files[[IO.Path]::GetRelativePath($SourcePath, $_.FullName)] =
            [IO.File]::ReadAllText($_.FullName)
    }
    @{
        source = $SourcePath
        files = $files
        host = $FtpHost
        remote = $RemotePath
        publishLast = $PublishLast
        hasCredential = $PSBoundParameters.ContainsKey('Credential')
        username = if ($null -ne $Credential) { $Credential.UserName } else { $null }
        whatIf = [bool] $WhatIfPreference
        confirm = [bool] $PSBoundParameters['Confirm']
    } | ConvertTo-Json -Depth 5 -Compress |
        Set-Content -LiteralPath $env:KK67_PHP_TEST_UPLOAD_LOG -WhatIf:$false -Confirm:$false
    if ($env:KK67_PHP_TEST_UPLOAD_FAIL -eq '1') {
        throw 'Fixture upload failure.'
    }
}
Export-ModuleMember -Function Send-FtpsDirectory
""",
            encoding="utf-8",
        )
        self.app = self.root.joinpath("webroot", "kk67-backend-php")
        self.app.joinpath("src").mkdir(parents=True)
        self.app.joinpath("tests").mkdir()
        self.app.joinpath("src", "index.php").write_text(
            "<?php require 'loader.php';", encoding="utf-8"
        )
        self.app.joinpath("src", "loader.php").write_text(
            "<?php function fixture() {}", encoding="utf-8"
        )
        self.app.joinpath("tests", "smoke.php").write_text(
            "<?php /* test fixture */", encoding="utf-8"
        )
        self.upload_log = self.root.joinpath("upload.json")
        self.php_log = self.root.joinpath("php.jsonl")

    def invoke(self, arguments="", credential=True, **overrides):
        env = os.environ.copy()
        env.update(
            {
                "KK67_PHP_TEST_UPLOAD_LOG": str(self.upload_log),
                "KK67_PHP_TEST_PHP_LOG": str(self.php_log),
                "KK67_PHP_TEST_VERSION_EXIT": "0",
                "KK67_PHP_TEST_LINT_EXIT": "0",
                "KK67_PHP_TEST_SMOKE_EXIT": "0",
                "KK67_PHP_TEST_UPLOAD_FAIL": "0",
                "NO_COLOR": "1",
                "TERM": "dumb",
            }
        )
        env.update(overrides)
        harness = r"""
function php {
    @{ arguments = @($args) } | ConvertTo-Json -Compress |
        Add-Content -LiteralPath $env:KK67_PHP_TEST_PHP_LOG -WhatIf:$false -Confirm:$false
    $global:LASTEXITCODE = if ($args[0] -eq '-r') {
        [int] $env:KK67_PHP_TEST_VERSION_EXIT
    } elseif ($args[0] -eq '-l') {
        [int] $env:KK67_PHP_TEST_LINT_EXIT
    } else {
        [int] $env:KK67_PHP_TEST_SMOKE_EXIT
    }
}
$securePassword = ConvertTo-SecureString 'fixture-password' -AsPlainText -Force
$credential = [PSCredential]::new('fixture-user', $securePassword)
"""
        credential_argument = "-Credential $credential" if credential else ""
        return subprocess.run(
            [
                PWSH,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                harness
                + f"\n& {ps_quote(self.script)} {credential_argument} {arguments}",
            ],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )

    def upload(self):
        return json.loads(self.upload_log.read_text(encoding="utf-8-sig"))

    def php_calls(self):
        if not self.php_log.exists():
            return []
        return [
            json.loads(line)
            for line in self.php_log.read_text(encoding="utf-8-sig").splitlines()
        ]

    def assert_clean(self):
        self.assertEqual(list(self.app.glob("build/ftps-package-*")), [])

    def test_packages_only_the_two_runtime_files_and_preserves_server_data(self):
        for name in (
            ".env",
            ".env.backup",
            ".git/config",
            ".htaccess",
            ".user.ini",
            "composer.phar",
            "vendor/development-only.php",
            "src/index.php~",
            "src/cache.json",
            "logs/error.log",
            "cache/data.json",
            "uploads/photo.jpg",
            "README.md",
            "Dockerfile",
        ):
            path = self.app.joinpath(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("must not upload", encoding="utf-8")
        result = self.invoke("-Confirm:$false")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        upload = self.upload()
        self.assertEqual(upload["host"], "ftp.c9ry3m6by.service.one")
        self.assertEqual(upload["remote"], "webroots/r1058768")
        self.assertEqual(upload["publishLast"], "index.php")
        self.assertEqual(
            upload["files"],
            {
                "index.php": "<?php require 'loader.php';",
                "loader.php": "<?php function fixture() {}",
            },
        )
        self.assertTrue(upload["hasCredential"])
        self.assertEqual(upload["username"], "fixture-user")
        self.assertFalse(upload["confirm"])
        self.assertNotIn("fixture-password", result.stdout + result.stderr)
        self.assert_clean()

    def test_validates_the_actual_flat_package_before_uploading(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.php_calls()
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0]["arguments"][0], "-r")
        package = Path(self.upload()["source"])
        self.assertEqual(
            [call["arguments"] for call in calls[1:3]],
            [["-l", str(package / "index.php")], ["-l", str(package / "loader.php")]],
        )
        self.assertEqual(
            calls[3]["arguments"],
            [str(self.app / "tests" / "smoke.php"), str(package / "index.php")],
        )
        self.assert_clean()

    def test_whatif_reuses_the_helper_without_credentials_or_network(self):
        self.root.joinpath(".env").write_text(
            "FTP_USERNAME=incomplete\n", encoding="utf-8"
        )
        result = self.invoke("-WhatIf", credential=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        upload = self.upload()
        self.assertTrue(upload["whatIf"])
        self.assertFalse(upload["hasCredential"])
        self.assertEqual(set(upload["files"]), {"index.php", "loader.php"})
        self.assert_clean()

    def test_missing_runtime_or_smoke_file_prevents_upload(self):
        for relative in ("src/index.php", "src/loader.php", "tests/smoke.php"):
            with self.subTest(relative=relative):
                path = self.app.joinpath(relative)
                contents = path.read_text(encoding="utf-8")
                path.unlink()
                try:
                    result = self.invoke()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(self.upload_log.exists())
                    self.assertEqual(self.php_calls(), [])
                    self.assert_clean()
                finally:
                    path.write_text(contents, encoding="utf-8")

    def test_new_composer_dependencies_fail_closed_instead_of_omitting_vendor(self):
        for name in ("composer.json", "composer.lock"):
            with self.subTest(name=name):
                manifest = self.app.joinpath(name)
                manifest.write_text("{}", encoding="utf-8")
                try:
                    result = self.invoke()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("explicit production package", result.stderr)
                    self.assertFalse(self.upload_log.exists())
                    self.assertEqual(self.php_calls(), [])
                    self.assert_clean()
                finally:
                    manifest.unlink()

    def test_php_version_lint_and_smoke_failures_prevent_upload(self):
        for setting, message in (
            ("KK67_PHP_TEST_VERSION_EXIT", "PHP 8.3 or newer is required"),
            ("KK67_PHP_TEST_LINT_EXIT", "PHP syntax check failed"),
            ("KK67_PHP_TEST_SMOKE_EXIT", "PHP smoke check failed"),
        ):
            with self.subTest(setting=setting):
                result = self.invoke(**{setting: "1"})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse(self.upload_log.exists())
                self.assert_clean()

    def test_failed_upload_propagates_and_removes_local_package(self):
        result = self.invoke(KK67_PHP_TEST_UPLOAD_FAIL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Fixture upload failure", result.stderr)
        self.assert_clean()

    def test_non_directory_build_path_prevents_upload(self):
        self.app.joinpath("build").write_text("not a directory", encoding="utf-8")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unexpected file type", result.stderr)
        self.assertFalse(self.upload_log.exists())

    def test_symbolic_link_source_file_is_rejected(self):
        source = self.app.joinpath("src", "loader.php")
        original = self.app.joinpath("loader-original.php")
        source.rename(original)
        try:
            source.symlink_to(original)
        except OSError as error:
            self.skipTest(f"Creating symbolic links is unavailable: {error}")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Symbolic links and junctions", result.stderr)
        self.assertFalse(self.upload_log.exists())
        self.assertEqual(self.php_calls(), [])
        self.assert_clean()

    @unittest.skipUnless(os.name == "nt", "NTFS junctions are Windows-specific")
    def test_source_directory_junction_is_rejected(self):
        source = self.app.joinpath("src")
        original = self.app.joinpath("src-original")
        source.rename(original)
        junction = subprocess.run(
            [
                PWSH,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"New-Item -ItemType Junction -Path {ps_quote(source)} "
                f"-Target {ps_quote(original)} -ErrorAction Stop | Out-Null",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(junction.returncode, 0, junction.stdout + junction.stderr)
        try:
            result = self.invoke()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Symbolic links and junctions", result.stderr)
            self.assertFalse(self.upload_log.exists())
            self.assertEqual(self.php_calls(), [])
            self.assert_clean()
        finally:
            source.rmdir()


if __name__ == "__main__":
    unittest.main()
