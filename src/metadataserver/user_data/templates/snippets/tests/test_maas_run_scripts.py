from io import BytesIO
import json
import os
from pathlib import Path
from unittest.mock import ANY, call, MagicMock
from urllib.error import HTTPError

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
    ScriptsPaths,
    write_token,
)


class TestScriptsPaths(MAASTestCase):
    def test_paths(self):
        base_path = Path(self.useFixture(TempDirectory()).path)
        scripts_paths = ScriptsPaths(base_path=base_path)
        self.assertEqual(scripts_paths.scripts, base_path / "scripts")
        self.assertEqual(scripts_paths.out, base_path / "out")
        self.assertEqual(scripts_paths.downloads, base_path / "downloads")
        self.assertEqual(
            scripts_paths.resources_file, base_path / "resources.json"
        )

    def test_ensure(self):
        base_path = Path(self.useFixture(TempDirectory()).path)
        scripts_paths = ScriptsPaths(base_path=base_path)
        scripts_paths.ensure()
        self.assertTrue(scripts_paths.scripts.exists())
        self.assertTrue(scripts_paths.out.exists())
        self.assertTrue(scripts_paths.downloads.exists())
        self.assertTrue(scripts_paths.resources_file.exists())

    def test_ensure_clears_existing_content(self):
        base_path = Path(self.useFixture(TempDirectory()).path)
        scripts_paths = ScriptsPaths(base_path=base_path)
        scripts_paths.scripts.mkdir()
        a_file = scripts_paths.scripts / "a-file"
        a_file.touch()
        scripts_paths.ensure()
        self.assertFalse(a_file.exists())


class TestScript(MAASTestCase):
    def test_properties(self):
        info = {
            "name": "myscript",
            "path": "commissioning-scripts/myscript",
        }
        paths = ScriptsPaths(base_path=Path("/base"))
        script = Script(info, "http://maas.example.com", paths)
        self.assertEqual(script.name, "myscript")
        self.assertEqual(
            script.command,
            [str(paths.scripts / "commissioning-scripts/myscript")],
        )
        self.assertEqual(script.stdout_path, paths.out / "myscript.out")
        self.assertEqual(script.stderr_path, paths.out / "myscript.err")
        self.assertEqual(script.combined_path, paths.out / "myscript")
        self.assertEqual(script.result_path, paths.out / "myscript.yaml")

    def test_environ(self):
        info = {
            "name": "myscript",
            "path": "commissioning-scripts/myscript",
            "timeout_seconds": 100,
            "bmc_config_path": "/bmc-config",
        }
        paths = ScriptsPaths(base_path=Path("/base"))
        script = Script(info, "http://maas.example.com", paths)
        self.assertEqual(
            script.environ["MAAS_BASE_URL"], "http://maas.example.com"
        )
        self.assertEqual(
            script.environ["MAAS_RESOURCES_FILE"], "/base/resources.json"
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
        paths = ScriptsPaths(base_path=Path("/base"))
        script = Script(info, "http://maas.example.com", paths)
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
        paths = ScriptsPaths(base_path=Path("/base"))
        script = Script(info, "http://maas.example.com", paths)
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
        paths = ScriptsPaths(base_path=Path("/base"))
        script = Script(info, "http://maas.example.com", paths)
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
    def setUp(self):
        self.patch(maas_run_scripts, "print")
        super().setUp()

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

    def make_http_error(self, code, reason, details):
        return HTTPError(
            "http://example.com",
            code,
            reason,
            {},
            BytesIO(details.encode("utf8")),
        )

    def test_register_machine(self):
        token_info = {
            "token_key": "tk",
            "token_secret": "ts",
            "consumer_key": "ck",
        }
        mock_geturl = self.mock_geturl([{"system_id": "abcde"}, token_info])
        mock_node = self.patch(maas_run_scripts.platform, "node")
        mock_node.return_value = "myhost"
        tempdir = self.useFixture(TempDirectory()).path

        main(
            [
                "register-machine",
                "--base-dir",
                tempdir,
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
        creds_yaml = yaml.safe_load(
            (Path(tempdir) / "myhost-creds.yaml").read_text()
        )
        info = creds_yaml["reporting"]["maas"]
        self.assertEqual("tk", info["token_key"])
        self.assertEqual("ts", info["token_secret"])
        self.assertEqual("ck", info["consumer_key"])
        self.assertEqual(
            "http://mymaas.example.com:5240/MAAS/metadata/status/abcde",
            info["endpoint"],
        )

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
        token = {
            "endpoint": "http://mymaas.example.com:5240/MAAS/metadata/status/abcde",
            **token_info,
        }
        mock_write_token.assert_called_once_with(
            token, path=Path("myhost-creds.yaml")
        )

    def test_get_machine_token(self):
        tempdir = self.useFixture(TempDirectory()).path
        token_info = {
            "token_key": "tk",
            "token_secret": "ts",
            "consumer_key": "ck",
        }
        mock_write_token = self.patch(maas_run_scripts, "write_token")
        mock_geturl = self.mock_geturl([token_info])
        main(
            [
                "get-machine-token",
                "http://mymaas.example.com:5240/MAAS",
                "foo:bar:baz",
                "abcde",
                f"{tempdir}/creds.yaml",
            ]
        )
        mock_geturl.assert_called_with(
            "http://mymaas.example.com:5240/MAAS/api/2.0/machines/abcde/?op=get_token",
            credentials=Credentials.from_string("foo:bar:baz"),
            retry=False,
        )
        token = {
            "endpoint": "http://mymaas.example.com:5240/MAAS/metadata/status/abcde",
            **token_info,
        }
        mock_write_token.assert_called_once_with(
            token, path=Path(f"{tempdir}/creds.yaml")
        )

    def test_get_machine_token_machine_not_found(self):
        tempdir = self.useFixture(TempDirectory()).path
        mock_exit = self.patch(maas_run_scripts.sys, "exit")
        self.patch(
            maas_run_scripts, "geturl"
        ).side_effect = self.make_http_error(
            404,
            "Not found",
            "Machine not found",
        )
        main(
            [
                "get-machine-token",
                "http://mymaas.example.com:5240/MAAS",
                "foo:bar:baz",
                "abcde",
                f"{tempdir}/creds.yaml",
            ]
        )
        mock_exit.assert_called_with(
            "Failed getting machine credentials: Not found: Machine not found"
        )

    def test_get_machine_token_token_not_found(self):
        tempdir = self.useFixture(TempDirectory()).path
        mock_exit = self.patch(maas_run_scripts.sys, "exit")
        self.mock_geturl([None])
        main(
            [
                "get-machine-token",
                "http://mymaas.example.com:5240/MAAS",
                "foo:bar:baz",
                "abcde",
                f"{tempdir}creds.yaml",
            ]
        )
        mock_exit.assert_called_with(
            "Failed getting machine credentials: Credentials not found"
        )


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
            yaml.safe_load(path),
            {"reporting": {"maas": token_info}},
        )
