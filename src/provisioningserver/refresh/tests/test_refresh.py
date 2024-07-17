# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections import OrderedDict
from pathlib import Path
import subprocess
import sys
from textwrap import dedent
from unittest.mock import ANY, patch, sentinel

from maastesting.factory import factory
from maastesting.fixtures import TempDirectory
from maastesting.testcase import MAASTestCase
from provisioningserver import refresh
from provisioningserver.path import get_maas_data_path
from provisioningserver.refresh import maas_api_helper
from provisioningserver.refresh.maas_api_helper import (
    MD_VERSION,
    TimeoutExpired,
)
from provisioningserver.refresh.node_info_scripts import (
    COMMISSIONING_OUTPUT_NAME,
)


class FakeResponse:
    status = 200


class TestRefresh(MAASTestCase):
    def setUp(self):
        super().setUp()
        # When running scripts in a tty MAAS outputs the results to help with
        # debug. Quiet the output when running in tests.
        self.patch(sys, "stdout")
        # by default, fake running in snap so sudo is not used
        self.mock_running_in_snap = self.patch(refresh, "running_in_snap")
        self.mock_running_in_snap.return_value = True
        self.urlopen_calls = []
        self.patch(maas_api_helper.urllib.request, "urlopen").side_effect = (
            self._fake_urlopen
        )

        self.tmpdir = self.useFixture(TempDirectory()).path
        self.patch(refresh, "SCRIPTS_BASE_PATH", self.tmpdir)

    def _fake_urlopen(self, request, post_data=None, data=None):
        self.urlopen_calls.append((request, post_data, data))
        return FakeResponse()

    def create_scripts_success(self, script_name=None, script_content=None):
        if script_content is None:
            script_content = dedent(
                """\
                #!/bin/bash
                echo 'test script'
                """
            )
        return self._create_scripts_content(script_name, script_content)

    def create_scripts_failure(self, script_name=None):
        content = dedent(
            """\
            #!/bin/bash
            echo 'test failed'
            exit 1
            """
        )
        return self._create_scripts_content(script_name, content)

    def _create_scripts_content(self, script_name, content):
        if script_name is None:
            script_name = factory.make_name("script_name")

        script_path = Path(self.tmpdir) / script_name
        script_path.write_text(content)
        script_path.chmod(0o755)
        return OrderedDict(
            [(script_name, {"name": script_name, "run_on_controller": True})]
        )

    def test_refresh_accepts_defined_url(self):
        script_name = factory.make_name("script_name")
        info_scripts = self.create_scripts_success(script_name)

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        base_url = factory.make_simple_http_url()

        with patch.dict(refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, base_url
            )
        requests = [call[0] for call in self.urlopen_calls]

        for request in requests:
            self.assertEqual(
                f"{base_url}/metadata/{MD_VERSION}/", request.full_url
            )
            auth_header = request.get_header("Authorization")
            self.assertTrue(
                auth_header.startswith("OAuth oauth_nonce="), auth_header
            )
            self.assertIn(f'oauth_consumer_key="{consumer_key}"', auth_header)
            self.assertIn(f'oauth_token="{token_key}"', auth_header)

        self.assertIn(
            f"Starting {script_name}", requests[0].data.decode("ascii")
        )
        self.assertIn(
            f'filename="{script_name}"', requests[1].data.decode("ascii")
        )
        self.assertIn(
            f"Finished refreshing {system_id}",
            requests[2].data.decode("ascii"),
        )

    def test_refresh_signals_results(self):
        signal = self.patch(refresh, "signal")
        script_name = factory.make_name("script_name")
        script_content = dedent(
            """\
        #!/bin/bash
        echo 'test script'
        echo '{status: skipped}' > $RESULT_PATH
        """
        )
        info_scripts = self.create_scripts_success(
            script_name, script_content=script_content
        )

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        url = factory.make_url()

        with patch.dict(refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, url
            )
        signal.assert_any_call(
            ANY,
            ANY,
            "WORKING",
            files={
                script_name: b"test script\n",
                f"{script_name}.out": b"test script\n",
                f"{script_name}.err": b"",
                f"{script_name}.yaml": b"{status: skipped}\n",
            },
            exit_status=0,
            error=f"Finished {script_name} [1/1]: 0",
            retry=False,
        )

    def test_refresh_sets_env_vars(self):
        self.patch(refresh, "signal")
        script_name = factory.make_name("script_name")
        info_scripts = self.create_scripts_failure(script_name)
        mock_popen = self.patch(refresh, "Popen")
        mock_popen.side_effect = OSError(8, "Exec format error")

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        url = factory.make_url()

        with patch.dict(refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, url
            )

        env = mock_popen.call_args[1]["env"]
        for name in [
            "OUTPUT_COMBINED_PATH",
            "OUTPUT_STDOUT_PATH",
            "OUTPUT_STDERR_PATH",
            "RESULT_PATH",
        ]:
            self.assertIn(name, env)
            self.assertIn(script_name, env[name])

    def test_refresh_signals_failure_on_unexecutable_script(self):
        signal = self.patch(refresh, "signal")
        script_name = factory.make_name("script_name")
        info_scripts = self.create_scripts_failure(script_name)
        mock_popen = self.patch(refresh, "Popen")
        mock_popen.side_effect = OSError(8, "Exec format error")

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        url = factory.make_url()

        with patch.dict(refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, url
            )
        signal.assert_any_call(
            ANY,
            ANY,
            "WORKING",
            files={
                script_name: b"[Errno 8] Exec format error",
                f"{script_name}.err": b"[Errno 8] Exec format error",
            },
            exit_status=8,
            error=f"Failed to execute {script_name} [1/1]: 8",
            retry=False,
        )

    def test_refresh_signals_failure_on_unexecutable_script_no_errno(self):
        signal = self.patch(refresh, "signal")
        script_name = factory.make_name("script_name")
        info_scripts = self.create_scripts_failure(script_name)
        mock_popen = self.patch(refresh, "Popen")
        mock_popen.side_effect = OSError()

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        url = factory.make_url()

        with patch.dict(refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, url
            )
        signal.mock_any_call(
            ANY,
            ANY,
            "WORKING",
            files={
                script_name: b"Unable to execute script",
                f"{script_name}.err": b"Unable to execute script",
            },
            exit_status=2,
            error=f"Failed to execute {script_name} [1/1]: 2",
            retry=False,
        )

    def test_refresh_signals_failure_on_unexecutable_script_baderrno(self):
        signal = self.patch(refresh, "signal")
        script_name = factory.make_name("script_name")
        info_scripts = self.create_scripts_failure(script_name)
        mock_popen = self.patch(refresh, "Popen")
        mock_popen.side_effect = OSError(0, "Exec format error")

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        url = factory.make_url()

        with patch.dict(refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, url
            )
        signal.assert_any_call(
            ANY,
            ANY,
            "WORKING",
            files={
                script_name: b"[Errno 0] Exec format error",
                f"{script_name}.err": b"[Errno 0] Exec format error",
            },
            exit_status=2,
            error=f"Failed to execute {script_name} [1/1]: 2",
            retry=False,
        )

    def test_refresh_signals_failure_on_timeout(self):
        signal = self.patch(refresh, "signal")
        script_name = factory.make_name("script_name")
        info_scripts = self.create_scripts_failure(script_name)

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        url = factory.make_url()

        def timeout_run(
            proc, combined_path, stdout_path, stderr_path, timeout_seconds
        ):
            # Contract of capture_script_output is to create these files
            for path in (stdout_path, stderr_path, combined_path):
                open(path, "w").close()
            raise TimeoutExpired(proc.args, timeout_seconds)

        mock_capture_script_output = self.patch(
            refresh, "capture_script_output"
        )
        mock_capture_script_output.side_effect = timeout_run
        with patch.dict(refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, url
            )

        signal.assert_any_call(
            ANY,
            ANY,
            "TIMEDOUT",
            files={
                script_name: b"",
                f"{script_name}.out": b"",
                f"{script_name}.err": b"",
            },
            error=f"Timeout(60) expired on {script_name} [1/1]",
            retry=False,
        )

    def test_refresh_signals_failure(self):
        signal = self.patch(refresh, "signal")
        info_scripts = self.create_scripts_failure()

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        url = factory.make_url()

        with patch.dict(refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, url
            )
        signal.assert_any_call(
            ANY,
            ANY,
            "FAILED",
            f"Failed refreshing {system_id}",
            retry=False,
        )

    def test_refresh_executes_lxd_binary_in_snap(self):
        signal = self.patch(refresh, "signal")
        script_name = COMMISSIONING_OUTPUT_NAME
        info_scripts = self.create_scripts_success(script_name)
        path = factory.make_name()

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        url = factory.make_url()

        with patch.dict("os.environ", {"SNAP": path}), patch.dict(
            refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True
        ):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, url
            )
        signal.assert_any_call(
            ANY,
            ANY,
            "WORKING",
            f"Starting {COMMISSIONING_OUTPUT_NAME} [1/1]",
            retry=False,
        )

    def test_refresh_clears_up_temporary_directory(self):
        ScriptsBroken = factory.make_exception_type()

        def find_temporary_directories():
            maas_data = Path(get_maas_data_path(""))
            return {
                str(entry) for entry in maas_data.iterdir() if entry.is_dir()
            }

        tmpdirs_during = set()
        tmpdir_during = None

        def runscripts(*args, tmpdir, **kwargs):
            self.assertTrue(Path(tmpdir).exists())
            nonlocal tmpdirs_during, tmpdir_during
            tmpdirs_during |= find_temporary_directories()
            tmpdir_during = tmpdir
            raise ScriptsBroken("Foom")

        self.patch(refresh, "runscripts", runscripts)

        tmpdirs_before = find_temporary_directories()
        self.assertRaises(
            ScriptsBroken,
            refresh.refresh,
            sentinel.system_id,
            sentinel.consumer_key,
            sentinel.token_key,
            sentinel.token_secret,
        )
        tmpdirs_after = find_temporary_directories()

        self.assertNotIn(tmpdir_during, tmpdirs_before)
        self.assertIn(tmpdir_during, tmpdirs_during)
        self.assertNotIn(tmpdir_during, tmpdirs_after)

    def test_refresh_runs_script_no_sudo_snap(self):
        mock_popen = self.patch(refresh, "Popen")
        mock_popen.side_effect = OSError()
        self.patch(refresh, "signal")
        script_name = factory.make_name("script_name")
        script_content = dedent(
            """\
        #!/bin/bash
        echo 'test script'
        """
        )
        info_scripts = self.create_scripts_success(
            script_name, script_content=script_content
        )

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        url = factory.make_url()

        with patch.dict(refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, url
            )
        script_path = Path(self.tmpdir) / script_name
        mock_popen.assert_called_once_with(
            [str(script_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=ANY,
        )

    def test_refresh_runs_script_sudo_if_no_snap(self):
        self.mock_running_in_snap.return_value = False
        mock_popen = self.patch(refresh, "Popen")
        mock_popen.side_effect = OSError()
        self.patch(refresh, "signal")
        script_name = factory.make_name("script_name")
        script_content = dedent(
            """\
        #!/bin/bash
        echo 'test script'
        echo '{status: skipped}' > $RESULT_PATH
        """
        )
        info_scripts = self.create_scripts_success(
            script_name, script_content=script_content
        )

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        url = factory.make_url()

        with patch.dict(refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, url
            )
        script_path = Path(self.tmpdir) / script_name
        mock_popen.assert_called_once_with(
            ["sudo", "-E", str(script_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=ANY,
        )
