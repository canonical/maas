import json
import os
from pathlib import Path
from unittest.mock import ANY, call, MagicMock

import yaml

from maastesting.fixtures import TempDirectory
from maastesting.testcase import MAASTestCase
from provisioningserver.refresh.maas_api_helper import Credentials
from snippets import maas_run_scripts
from snippets.maas_run_scripts import (
    get_config,
    main,
    parse_args,
    Script,
    ScriptRunResult,
    ScriptsDir,
    write_token,
)


class TestScriptsDir(MAASTestCase):
    def test_paths(self):
        base_path = Path(self.useFixture(TempDirectory()).path)
        scripts_dir = ScriptsDir(base_path=base_path)
        self.assertEqual(scripts_dir.scripts, base_path / "scripts")
        self.assertEqual(scripts_dir.out, base_path / "out")
        self.assertEqual(scripts_dir.downloads, base_path / "downloads")

    def test_ensure(self):
        base_path = Path(self.useFixture(TempDirectory()).path)
        scripts_dir = ScriptsDir(base_path=base_path)
        scripts_dir.ensure()
        self.assertTrue(scripts_dir.scripts.exists())
        self.assertTrue(scripts_dir.out.exists())
        self.assertTrue(scripts_dir.downloads.exists())

    def test_ensure_clears_existing_content(self):
        base_path = Path(self.useFixture(TempDirectory()).path)
        scripts_dir = ScriptsDir(base_path=base_path)
        scripts_dir.scripts.mkdir()
        a_file = scripts_dir.scripts / "a-file"
        a_file.touch()
        scripts_dir.ensure()
        self.assertFalse(a_file.exists())


class TestScript(MAASTestCase):
    def test_properties(self):
        info = {
            "name": "myscript",
            "path": "commissioning-scripts/myscript",
        }
        dirs = ScriptsDir(base_path=Path("/base"))
        script = Script(info, "http://maas.example.com", dirs)
        self.assertEqual(script.name, "myscript")
        self.assertEqual(
            script.command,
            [str(dirs.scripts / "commissioning-scripts/myscript")],
        )
        self.assertEqual(script.stdout_path, dirs.out / "myscript.out")
        self.assertEqual(script.stderr_path, dirs.out / "myscript.err")
        self.assertEqual(script.combined_path, dirs.out / "myscript")
        self.assertEqual(script.result_path, dirs.out / "myscript.yaml")

    def test_environ(self):
        info = {
            "name": "myscript",
            "path": "commissioning-scripts/myscript",
            "timeout_seconds": 100,
            "bmc_config_path": "/bmc-config",
        }
        dirs = ScriptsDir(base_path=Path("/base"))
        script = Script(info, "http://maas.example.com", dirs)
        self.assertEqual(
            script.environ["MAAS_BASE_URL"], "http://maas.example.com"
        )
        self.assertEqual(script.environ["RUNTIME"], "100")
        self.assertEqual(script.environ["BMC_CONFIG_PATH"], "/bmc-config")
        self.assertEqual(script.environ["HAS_STARTED"], "False")
        # vars from the original environ are preserved
        self.assertEqual(script.environ["PATH"], os.environ["PATH"])

    def test_should_run(self):
        infos = [
            {
                "name": "myscript",
                "path": "commissioning-scripts/myscript",
                "default": True,
                "tags": ["node", "deploy-info"],
            },
            {
                "name": "myscript",
                "path": "commissioning-scripts/myscript",
                "default": False,
                "tags": ["node", "deploy-info"],
            },
            {
                "name": "myscript",
                "path": "commissioning-scripts/myscript",
                "default": True,
                "tags": ["node"],
            },
            {
                "name": "myscript",
                "path": "commissioning-scripts/myscript",
                "default": False,
                "tags": ["node"],
            },
        ]
        should_run = [
            Script(info, "http://maas.example.com", None).should_run()
            for info in infos
        ]
        self.assertEqual([True, False, False, False], should_run)

    def test_run(self):
        fake_process = self.patch(
            maas_run_scripts.subprocess, "Popen"
        ).return_value
        mock_capture_script_output = self.patch(
            maas_run_scripts, "capture_script_output"
        )
        info = {
            "name": "myscript",
            "path": "commissioning-scripts/myscript",
            "timeout_seconds": 100,
        }
        dirs = ScriptsDir(base_path=Path("/base"))
        script = Script(info, "http://maas.example.com", dirs)
        result = script.run()
        self.assertEqual(result.exit_status, 0)
        self.assertEqual(result.status, "WORKING")
        self.assertIsNone(result.error)
        self.assertGreater(result.runtime, 0.0)
        mock_capture_script_output.assert_called_once_with(
            fake_process,
            script.combined_path,
            script.stdout_path,
            script.stderr_path,
            timeout_seconds=100,
            console_output=False,
        )

    def test_run_failed(self):
        self.patch(maas_run_scripts.subprocess, "Popen")
        error = OSError("Fail!")
        error.errno = 10
        self.patch(
            maas_run_scripts, "capture_script_output"
        ).side_effect = error
        info = {
            "name": "myscript",
            "path": "commissioning-scripts/myscript",
            "timeout_seconds": 100,
        }
        dirs = ScriptsDir(base_path=Path("/base"))
        script = Script(info, "http://maas.example.com", dirs)
        result = script.run()
        self.assertEqual(result.exit_status, 10)
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error, "Failed to execute myscript: 10")

    def test_run_timedout(self):
        self.patch(maas_run_scripts.subprocess, "Popen")
        error = OSError("Timeout!")
        error.errno = 124
        self.patch(
            maas_run_scripts, "capture_script_output"
        ).side_effect = error
        info = {
            "name": "myscript",
            "path": "commissioning-scripts/myscript",
            "timeout_seconds": 100,
        }
        dirs = ScriptsDir(base_path=Path("/base"))
        script = Script(info, "http://maas.example.com", dirs)
        result = script.run()
        self.assertEqual(result.exit_status, 124)
        self.assertEqual(result.status, "TIMEDOUT")
        self.assertEqual(result.error, "Timeout(0:01:40) expired on myscript")


class TestGetConfig(MAASTestCase):
    def test_read_from_config(self):
        conf = {
            "reporting": {
                "maas": {
                    "token_key": "token-key",
                    "token_secret": "token-secret",
                    "consumer_key": "consumer-key",
                    "consumer_secret": "consumer-secret",
                    "endpoint": "http://example.com",
                }
            }
        }
        tempdir = Path(self.useFixture(TempDirectory()).path)
        config_file = tempdir / "conf.yaml"
        with config_file.open("w") as fd:
            yaml.dump(conf, fd)
        ns = parse_args(["report-results", "--config", str(config_file)])
        config = get_config(ns)
        self.assertEqual(config.credentials.token_key, "token-key")
        self.assertEqual(config.credentials.token_secret, "token-secret")
        self.assertEqual(config.credentials.consumer_key, "consumer-key")
        self.assertEqual(config.credentials.consumer_secret, "consumer-secret")
        self.assertEqual(config.metadata_url, "http://example.com")

    def test_override_config(self):
        conf = {
            "reporting": {
                "maas": {
                    "token_key": "token-key",
                    "token_secret": "token-secret",
                    "consumer_key": "consumer-key",
                    "consumer_secret": "consumer-secret",
                    "endpoint": "http://example.com",
                }
            }
        }
        tempdir = Path(self.useFixture(TempDirectory()).path)
        config_file = tempdir / "conf.yaml"
        with config_file.open("w") as fd:
            yaml.dump(conf, fd)
        ns = parse_args(
            [
                "report-results",
                "--config",
                str(config_file),
                "--machine-token",
                "new-consumer-key:new-token-key:new-token-secret:new-consumer-secret",
                "--metadata-url",
                "http://new.example.com",
            ]
        )
        config = get_config(ns)
        self.assertEqual(config.credentials.token_key, "new-token-key")
        self.assertEqual(config.credentials.token_secret, "new-token-secret")
        self.assertEqual(config.credentials.consumer_key, "new-consumer-key")
        self.assertEqual(
            config.credentials.consumer_secret, "new-consumer-secret"
        )
        self.assertEqual(config.metadata_url, "http://new.example.com")


class TestMain(MAASTestCase):
    def test_run_report_results(self):
        conf = {
            "reporting": {
                "maas": {
                    "token_key": "token-key",
                    "token_secret": "token-secret",
                    "consumer_key": "consumer-key",
                    "consumer_secret": "consumer-secret",
                    "endpoint": "http://maas",
                }
            }
        }
        tempdir = Path(self.useFixture(TempDirectory()).path)
        config_file = tempdir / "conf.yaml"
        with config_file.open("w") as fd:
            yaml.dump(conf, fd)
        scripts_info = [
            {
                "name": "myscript1",
                "path": "commissioning-scripts/myscript1",
                "script_result_id": 1,
                "script_version_id": 10,
                "default": True,
                "tags": ["node", "deploy-info"],
            },
            {
                "name": "myscript2",
                "path": "commissioning-scripts/myscript2",
                "script_result_id": 2,
                "script_version_id": 20,
                "default": True,
                "tags": ["node", "deploy-info"],
            },
            {
                "name": "myscript3",
                "path": "commissioning-scripts/myscript3",
                "script_result_id": 3,
                "script_version_id": 30,
                "default": False,
                "tags": ["node", "deploy-info"],
            },
            {
                "name": "myscript4",
                "path": "commissioning-scripts/myscript4",
                "script_result_id": 4,
                "script_version_id": 40,
                "default": True,
                "tags": ["node"],
            },
        ]
        self.patch(maas_run_scripts, "fetch_scripts").return_value = [
            Script(info, "http://maas", None) for info in scripts_info
        ]
        self.patch(maas_run_scripts, "signal")

        ran_scripts = []

        def run_script(script, console_output=False):
            ran_scripts.append(script.name)
            return ScriptRunResult(0, "WORKING", None, 10, {})

        self.patch(maas_run_scripts.Script, "run", run_script)

        main(["report-results", "--config", str(config_file)])
        # only default scripts tagged as "deploy-info" are run
        self.assertEqual(ran_scripts, ["myscript1", "myscript2"])

    def mock_geturl(self, results):
        mock_geturl = self.patch(maas_run_scripts, "geturl")
        # fake returning a json result from the API call
        mock_result = MagicMock()
        mock_result.read.return_value.decode.side_effect = [
            json.dumps(result) for result in results
        ]
        mock_geturl.return_value = mock_result
        return mock_geturl

    def test_register_machine(self):
        token_info = {
            "token_key": "tk",
            "token_secret": "ts",
            "consumer_key": "ck",
        }
        mock_geturl = self.mock_geturl([{"system_id": "abcde"}, token_info])
        mock_node = self.patch(maas_run_scripts.platform, "node")
        mock_node.return_value = "myhost"
        mock_write_token = self.patch(maas_run_scripts, "write_token")

        main(
            [
                "register-machine",
                "http://mymaas.example.com:5240/MAAS",
                "foo:bar:baz",
            ]
        )
        mock_geturl.assert_has_calls(
            [
                call(
                    "http://mymaas.example.com:5240/MAAS/api/2.0/machines/",
                    credentials=Credentials.from_string("foo:bar:baz"),
                    data=ANY,
                    headers=ANY,
                    retry=False,
                ),
                call(
                    "http://mymaas.example.com:5240/MAAS/api/2.0/machines/abcde/?op=get_token",
                    credentials=Credentials.from_string("foo:bar:baz"),
                    retry=False,
                ),
            ],
            any_order=True,
        )
        mock_node.assert_called_once()
        mock_write_token.assert_called_once_with("myhost", token_info)

    def test_register_machine_with_hostname(self):
        token_info = {
            "token_key": "tk",
            "token_secret": "ts",
            "consumer_key": "ck",
        }
        mock_geturl = self.mock_geturl([{"system_id": "abcde"}, token_info])
        mock_node = self.patch(maas_run_scripts.platform, "node")
        mock_write_token = self.patch(maas_run_scripts, "write_token")

        main(
            [
                "register-machine",
                "http://mymaas.example.com:5240/MAAS",
                "foo:bar:baz",
                "--hostname",
                "myhost",
            ]
        )
        mock_geturl.assert_has_calls(
            [
                call(
                    "http://mymaas.example.com:5240/MAAS/api/2.0/machines/",
                    credentials=Credentials.from_string("foo:bar:baz"),
                    data=ANY,
                    headers=ANY,
                    retry=False,
                ),
                call(
                    "http://mymaas.example.com:5240/MAAS/api/2.0/machines/abcde/?op=get_token",
                    credentials=Credentials.from_string("foo:bar:baz"),
                    retry=False,
                ),
            ],
            any_order=True,
        )
        mock_node.assert_not_called()
        mock_write_token.assert_called_once_with("myhost", token_info)


class TestWriteToken(MAASTestCase):
    def writes_file(self):
        tempdir = Path(self.useFixture(TempDirectory()).path)
        token_info = {
            "token_key": "tk",
            "token_secret": "ts",
            "consumer_key": "ck",
        }
        path = write_token("myhost", token_info, basedir=tempdir)
        self.assertEqual(
            yaml.load(path),
            {"reporting": {"maas": token_info}},
        )
