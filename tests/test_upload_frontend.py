import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PWSH = shutil.which("pwsh")
NODE = shutil.which("node")
CURL = shutil.which("curl.exe") or shutil.which("curl")
DESTINATION = (
    "ftp://ftp.c9ry3m6by.service.one/"
    "webroots/r1058728/"
)


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


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


@unittest.skipUnless(PWSH, "PowerShell 7 is required for upload-script tests")
class FrontendUploadTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name).joinpath("repo with spaces")
        self.root.mkdir()
        self.script = self.root.joinpath("scripts", "upload-frontend.ps1")
        self.script.parent.mkdir()
        shutil.copyfile(ROOT.joinpath("scripts", self.script.name), self.script)
        shutil.copyfile(
            ROOT.joinpath("scripts", "ftps.psm1"),
            self.script.with_name("ftps.psm1"),
        )
        self.frontend = self.root.joinpath("webroot", "kk67-frontend")
        self.dist = self.frontend.joinpath("dist")
        self.dist.joinpath("assets").mkdir(parents=True)
        self.dist.joinpath("index.html").write_text("<html></html>", encoding="utf-8")
        self.dist.joinpath("assets", "app.js").write_text("app", encoding="utf-8")
        self.dist.joinpath("assets", "space # [name].txt").write_text(
            "asset", encoding="utf-8"
        )
        self.dist.joinpath(".well-known").mkdir()
        self.dist.joinpath(".well-known", "example.txt").write_text(
            "public", encoding="utf-8"
        )
        self.frontend.joinpath("package.json").write_text("{}", encoding="utf-8")
        self.frontend.joinpath(".env").write_text("NOT_FOR_UPLOAD=1", encoding="utf-8")
        self.frontend.joinpath(".htaccess").write_text("routing", encoding="utf-8")
        self.curl_log = self.root.joinpath("curl.jsonl")
        self.build_log = self.root.joinpath("build.json")
        self.prompt_log = self.root.joinpath("prompt.txt")
        self.env_file = self.root.joinpath(".env")
        self.password = 'pass "quoted" \\ : $value & end'

    def invoke_script(self, arguments="-SkipBuild", credential=True, **overrides):
        env = os.environ.copy()
        env.update(
            {
                "KK67_TEST_CURL_LOG": str(self.curl_log),
                "KK67_TEST_BUILD_LOG": str(self.build_log),
                "KK67_TEST_PROMPT_LOG": str(self.prompt_log),
                "KK67_TEST_ALLOW_PROMPT": "0",
                "KK67_TEST_BUILD_EXIT": "0",
                "KK67_TEST_PREFLIGHT_EXIT": "0",
                "KK67_TEST_UPLOAD_EXIT": "0",
                "KK67_TEST_PASSWORD": self.password,
                "NO_COLOR": "1",
                "TERM": "dumb",
            }
        )
        env.update(overrides)
        harness = r"""
function yarn {
    @{
        arguments = @($args)
        directory = (Get-Location).Path
    } | ConvertTo-Json -Compress |
        Set-Content -LiteralPath $env:KK67_TEST_BUILD_LOG -WhatIf:$false
    $global:LASTEXITCODE = [int] $env:KK67_TEST_BUILD_EXIT
}
function curl.exe {
    @{
        arguments = @($args)
        config = (@($input) -join "`n")
    } | ConvertTo-Json -Compress |
        Add-Content -LiteralPath $env:KK67_TEST_CURL_LOG -WhatIf:$false
    if ($args -contains '--list-only') {
        $global:LASTEXITCODE = [int] $env:KK67_TEST_PREFLIGHT_EXIT
    }
    else {
        $global:LASTEXITCODE = [int] $env:KK67_TEST_UPLOAD_EXIT
    }
}
function Get-Credential {
    if ($env:KK67_TEST_ALLOW_PROMPT -ne '1') {
        throw 'Unexpected interactive credential prompt.'
    }
    Set-Content -LiteralPath $env:KK67_TEST_PROMPT_LOG -Value 'prompted' -WhatIf:$false
    return $global:KK67TestCredential
}
$securePassword = ConvertTo-SecureString $env:KK67_TEST_PASSWORD -AsPlainText -Force
$credential = [PSCredential]::new('ftp-user', $securePassword)
$global:KK67TestCredential = $credential
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

    def curl_calls(self):
        if not self.curl_log.exists():
            return []
        return [
            json.loads(line)
            for line in self.curl_log.read_text(encoding="utf-8").splitlines()
        ]

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_whatif_never_connects_or_prompts_for_credentials(self):
        self.env_file.write_text("FTP_USERNAME=incomplete\n", encoding="utf-8")
        result = self.invoke_script("-SkipBuild -WhatIf", credential=False)
        self.assert_success(result)
        self.assertIn(DESTINATION, result.stdout)
        self.assertIn("4 files", result.stdout)
        self.assertNotIn("Upload complete", result.stdout)
        self.assertEqual(self.curl_calls(), [])
        self.assertFalse(self.build_log.exists())

    def test_default_build_runs_in_frontend_before_preview(self):
        result = self.invoke_script("-WhatIf", credential=False)
        self.assert_success(result)
        build = json.loads(self.build_log.read_text(encoding="utf-8"))
        self.assertEqual(build["arguments"], ["build"])
        self.assertEqual(Path(build["directory"]).resolve(), self.frontend.resolve())
        self.assertEqual(self.curl_calls(), [])

    @unittest.skipUnless(NODE, "Node.js 20.12+ is required for saved credentials")
    def test_reads_saved_credentials_with_real_dotenv_parser(self):
        self.password += " # = \u00f8"
        self.env_file.write_text(
            "FE_PORT=3000\n"
            "export FTP_USERNAME='saved-user'\n"
            f"FTP_PASSWORD='{self.password}' # outside the password\n"
            "NODE_OPTIONS='--require=does-not-exist'\n",
            encoding="utf-8",
        )
        result = self.invoke_script(credential=False)
        self.assert_success(result)
        escaped = self.password.replace("\\", "\\\\").replace('"', '\\"')
        calls = self.curl_calls()
        self.assertEqual(len(calls), 5)
        for call in calls:
            self.assertEqual(call["config"], f'user = "saved-user:{escaped}"')
            self.assertNotIn(self.password, " ".join(call["arguments"]))
        self.assertNotIn(self.password, result.stdout + result.stderr)
        self.assertFalse(self.prompt_log.exists())

    def test_explicit_credential_overrides_incomplete_env(self):
        self.env_file.write_text("FTP_USERNAME=ignored-user\n", encoding="utf-8")
        result = self.invoke_script()
        self.assert_success(result)
        self.assertTrue(self.curl_calls())
        for call in self.curl_calls():
            self.assertTrue(call["config"].startswith('user = "ftp-user:'))
            self.assertNotIn("ignored-user", call["config"])

    @unittest.skipUnless(NODE, "Node.js 20.12+ is required for saved credentials")
    def test_partial_saved_credentials_fail_without_prompting_or_uploading(self):
        for contents in (
            "FTP_USERNAME=saved-user\n",
            f"FTP_PASSWORD='{self.password}'\n",
        ):
            with self.subTest(contents=contents.split("=")[0]):
                self.env_file.write_text(contents, encoding="utf-8")
                result = self.invoke_script(credential=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Set both FTP_USERNAME and FTP_PASSWORD", result.stderr)
                self.assertEqual(self.curl_calls(), [])
                self.assertFalse(self.prompt_log.exists())
                self.assertNotIn(self.password, result.stdout + result.stderr)

    @unittest.skipUnless(NODE, "Node.js 20.12+ is required for saved credentials")
    def test_absent_or_empty_saved_credentials_keep_secure_prompt(self):
        for contents in (
            "FE_PORT=3000\n",
            "FTP_USERNAME=''\nFTP_PASSWORD=''\n",
        ):
            with self.subTest(contents=contents):
                self.curl_log.unlink(missing_ok=True)
                self.prompt_log.unlink(missing_ok=True)
                self.env_file.write_text(contents, encoding="utf-8")
                result = self.invoke_script(
                    credential=False, KK67_TEST_ALLOW_PROMPT="1"
                )
                self.assert_success(result)
                self.assertTrue(self.prompt_log.exists())
                self.assertEqual(len(self.curl_calls()), 5)

    def test_uploads_only_build_files_with_index_last_and_no_deletions(self):
        result = self.invoke_script()
        self.assert_success(result)
        calls = self.curl_calls()
        self.assertEqual(len(calls), 5)
        self.assertIn("--list-only", calls[0]["arguments"])
        self.assertNotIn("--ftp-create-dirs", calls[0]["arguments"])
        self.assertEqual(calls[0]["arguments"][-1], DESTINATION)
        uploads = calls[1:]
        self.assertEqual(uploads[-1]["arguments"][-1], DESTINATION + "index.html")
        self.assertEqual(
            {call["arguments"][-1] for call in uploads},
            {
                DESTINATION + "index.html",
                DESTINATION + "assets/app.js",
                DESTINATION + "assets/space%20%23%20%5Bname%5D.txt",
                DESTINATION + ".well-known/example.txt",
            },
        )
        for call in uploads:
            arguments = call["arguments"]
            self.assertIn("--ftp-create-dirs", arguments)
            source = Path(arguments[arguments.index("--upload-file") + 1])
            self.assertTrue(source.resolve().is_relative_to(self.dist.resolve()))
        for call in calls:
            arguments = call["arguments"]
            self.assertEqual(arguments[:3], ["--disable", "--config", "-"])
            self.assertIn("--ssl-reqd", arguments)
            self.assertIn("=ftp", arguments)
            self.assertNotIn("--insecure", arguments)
            self.assertNotIn("--quote", arguments)
            self.assertNotIn("--user", arguments)
            self.assertNotIn("ftp-user", " ".join(arguments))
            self.assertNotIn(self.password, " ".join(arguments))
            escaped = self.password.replace("\\", "\\\\").replace('"', '\\"')
            self.assertEqual(call["config"], f'user = "ftp-user:{escaped}"')
        self.assertNotIn(self.password, result.stdout + result.stderr)
        self.assertIn("Upload complete: 4", result.stdout)
        self.assertFalse(self.build_log.exists())

    @unittest.skipUnless(CURL, "curl is required for native option validation")
    def test_real_curl_accepts_upload_options_without_connecting(self):
        result = self.invoke_script()
        self.assert_success(result)
        for call in self.curl_calls():
            with self.subTest(operation=call["arguments"][-1]):
                native = subprocess.run(
                    [CURL, *call["arguments"], "--version"],
                    input=call["config"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(native.returncode, 0, native.stderr)
                self.assertTrue(native.stdout.startswith("curl "))
                self.assertNotIn(self.password, native.stdout + native.stderr)

    def test_failed_build_does_not_upload_an_existing_stale_build(self):
        result = self.invoke_script("", KK67_TEST_BUILD_EXIT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Frontend build failed", result.stderr)
        self.assertEqual(self.curl_calls(), [])

    def test_missing_index_prevents_upload(self):
        self.dist.joinpath("index.html").unlink()
        result = self.invoke_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No frontend build found", result.stderr)
        self.assertEqual(self.curl_calls(), [])

    def test_symbolic_link_in_build_prevents_upload(self):
        try:
            self.dist.joinpath("assets", "linked-env.txt").symlink_to(
                self.frontend.joinpath(".env")
            )
        except OSError as error:
            self.skipTest(f"Cannot create symbolic links on this host: {error}")
        result = self.invoke_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symbolic links or junctions", result.stderr)
        self.assertEqual(self.curl_calls(), [])

    def test_failed_login_or_destination_check_prevents_upload(self):
        result = self.invoke_script(KK67_TEST_PREFLIGHT_EXIT="67")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FTP login or destination check failed", result.stderr)
        self.assertEqual(len(self.curl_calls()), 1)
        self.assertNotIn("Upload complete", result.stdout)
        self.assertNotIn(self.password, result.stdout + result.stderr)

    def test_failed_asset_upload_stops_before_index(self):
        result = self.invoke_script(KK67_TEST_UPLOAD_EXIT="25")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Deployment stopped", result.stderr)
        calls = self.curl_calls()
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(calls[-1]["arguments"][-1], DESTINATION + "index.html")
        self.assertNotIn("Upload complete", result.stdout)

    def test_parent_directory_target_is_rejected_before_build(self):
        result = self.invoke_script("-RemotePath '../wrong'")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RemotePath must be", result.stderr)
        self.assertEqual(self.curl_calls(), [])
        self.assertFalse(self.build_log.exists())

    def test_invalid_host_is_rejected(self):
        result = self.invoke_script("-SkipBuild -FtpHost 'ftp://wrong/path'")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FtpHost must be", result.stderr)
        self.assertEqual(self.curl_calls(), [])

    def test_remote_directory_is_trimmed_and_url_encoded(self):
        result = self.invoke_script("-SkipBuild -RemotePath ' /site name/root/ '")
        self.assert_success(result)
        self.assertEqual(
            self.curl_calls()[0]["arguments"][-1],
            "ftp://ftp.c9ry3m6by.service.one/site%20name/root/",
        )


if __name__ == "__main__":
    unittest.main()
