import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


def compose_config(**overrides):
    env = os.environ.copy()
    for name in (
        "BE_APP_PATH",
        "BE_PHP_APP_PATH",
        "FE_APP_PATH",
        "FE_PORT",
        "FE_PROXY_PORT",
        "BE_PHP_PORT",
    ):
        env.pop(name, None)
    env.update(overrides)
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--file",
            str(ROOT.joinpath("docker-compose.yml")),
            "--env-file",
            str(ROOT.joinpath(".env.example")),
            "--profile",
            "dev",
            "config",
            "--format",
            "json",
            "--no-env-resolution",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)["services"]


class ComposePortTests(unittest.TestCase):
    def assert_port(self, service, published, target):
        self.assertIn(
            (str(published), target),
            [(port["published"], port["target"]) for port in service["ports"]],
        )

    def test_frontend_launch_uses_the_published_container_port(self):
        service = compose_config()["kk67_fe"]
        self.assertEqual(service["command"][:2], ["sh", "-c"])
        self.assertIn(
            "yarn dev:host --port 3000 --strictPort", service["command"][2]
        )

    def test_default_service_ports(self):
        services = compose_config()
        self.assert_port(services["kk67_fe"], 3000, 3000)
        self.assert_port(services["kk67_fe"], 2000, 2000)
        self.assert_port(services["kk67_php"], 4000, 4000)
        self.assert_port(services["kk67_be"], 5000, 5000)
        self.assertEqual(services["kk67_be"]["profiles"], ["dev"])

    def test_host_port_overrides_keep_fixed_container_ports(self):
        services = compose_config(FE_PORT="3100", BE_PHP_PORT="4100")
        for name, published, target in (
            ("kk67_fe", 3100, 3000),
            ("kk67_php", 4100, 4000),
        ):
            with self.subTest(service=name):
                self.assert_port(services[name], published, target)


if __name__ == "__main__":
    unittest.main()
