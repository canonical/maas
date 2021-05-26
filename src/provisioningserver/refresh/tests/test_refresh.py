# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections import OrderedDict
import os
from pathlib import Path
import random
import stat
import subprocess
import sys
import tempfile
from textwrap import dedent
from unittest.mock import ANY, patch, sentinel

from testtools.matchers import Contains, DirExists, Not

from maastesting.factory import factory
from maastesting.matchers import MockAnyCall
from maastesting.testcase import MAASTestCase
from provisioningserver import refresh
from provisioningserver.refresh.maas_api_helper import (
    MD_VERSION,
    SignalException,
    TimeoutExpired,
)
from provisioningserver.refresh.node_info_scripts import LXD_OUTPUT_NAME


class TestGetArchitecture(MAASTestCase):
    def tearDown(self):
        super().tearDown()
        refresh.get_architecture.cache_clear()

    @patch("apt_pkg.get_architectures")
    def test_get_architecture_from_deb(self, mock_get_architectures):
        arch = random.choice(["i386", "amd64", "arm64", "ppc64el"])
        mock_get_architectures.return_value = [arch, "otherarch"]
        ret_arch = refresh.get_architecture()
        self.assertEqual(arch, ret_arch)

    @patch("apt_pkg.get_architectures")
    def test_get_architecture_from_snap_env(self, mock_get_architectures):
        arch = factory.make_name("arch")
        self.patch(os, "environ", {"SNAP_ARCH": arch})
        ret_arch = refresh.get_architecture()
        self.assertEqual(arch, ret_arch)
        mock_get_architectures.assert_not_called()


class TestRefresh(MAASTestCase):
    def setUp(self):
        super().setUp()
        # When running scripts in a tty MAAS outputs the results to help with
        # debug. Quiet the output when running in tests.
        self.patch(sys, "stdout")
        # by default, fake running in snap so sudo is not used
        self.mock_running_in_snap = self.patch(refresh, "running_in_snap")
        self.mock_running_in_snap.return_value = True

    def _cleanup(self, path):
        if os.path.exists(path):
            os.remove(path)

    def create_scripts_success(self, script_name=None, script_content=None):
        if script_name is None:
            script_name = factory.make_name("script_name")
        if script_content is None:
            script_content = dedent(
                """\
                #!/bin/bash
                echo 'test script'
                """
            )
        script_path = os.path.join(
            os.path.dirname(__file__), "..", script_name
        )
        with open(script_path, "w") as f:
            f.write(script_content)
        st = os.stat(script_path)
        os.chmod(script_path, st.st_mode | stat.S_IEXEC)
        self.addCleanup(self._cleanup, script_path)

        return OrderedDict(
            [(script_name, {"name": script_name, "run_on_controller": True})]
        )

    def create_scripts_failure(self, script_name=None):
        if script_name is None:
            script_name = factory.make_name("script_name")
        TEST_SCRIPT = dedent(
            """\
            #!/bin/bash
            echo 'test failed'
            exit 1
            """
        )
        script_path = os.path.join(
            os.path.dirname(__file__), "..", script_name
        )
        with open(script_path, "w") as f:
            f.write(TEST_SCRIPT)
        st = os.stat(script_path)
        os.chmod(script_path, st.st_mode | stat.S_IEXEC)
        self.addCleanup(self._cleanup, script_path)

        return OrderedDict(
            [(script_name, {"name": script_name, "run_on_controller": True})]
        )

    def test_refresh_accepts_defined_url(self):
        signal = self.patch(refresh, "signal")
        script_name = factory.make_name("script_name")
        info_scripts = self.create_scripts_success(script_name)

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        url = factory.make_url()

        with patch.dict(refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, url
            )
        self.assertThat(
            signal,
            MockAnyCall(
                "%s/metadata/%s/" % (url, MD_VERSION),
                {
                    "consumer_secret": "",
                    "consumer_key": consumer_key,
                    "token_key": token_key,
                    "token_secret": token_secret,
                },
                "WORKING",
                "Starting %s [1/1]" % script_name,
            ),
        )

    def test_refresh_signals_starting(self):
        signal = self.patch(refresh, "signal")
        script_name = factory.make_name("script_name")
        info_scripts = self.create_scripts_success(script_name)

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        url = factory.make_url()

        with patch.dict(refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, url
            )
        self.assertThat(
            signal,
            MockAnyCall(
                "%s/metadata/%s/" % (url, MD_VERSION),
                {
                    "consumer_secret": "",
                    "consumer_key": consumer_key,
                    "token_key": token_key,
                    "token_secret": token_secret,
                },
                "WORKING",
                "Starting %s [1/1]" % script_name,
            ),
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
        self.assertThat(
            signal,
            MockAnyCall(
                "%s/metadata/%s/" % (url, MD_VERSION),
                {
                    "consumer_secret": "",
                    "consumer_key": consumer_key,
                    "token_key": token_key,
                    "token_secret": token_secret,
                },
                "WORKING",
                files={
                    script_name: b"test script\n",
                    "%s.out" % script_name: b"test script\n",
                    "%s.err" % script_name: b"",
                    "%s.yaml" % script_name: b"{status: skipped}\n",
                },
                exit_status=0,
                error="Finished %s [1/1]: 0" % script_name,
            ),
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
        self.assertThat(
            signal,
            MockAnyCall(
                "%s/metadata/%s/" % (url, MD_VERSION),
                {
                    "consumer_secret": "",
                    "consumer_key": consumer_key,
                    "token_key": token_key,
                    "token_secret": token_secret,
                },
                "WORKING",
                files={
                    script_name: b"[Errno 8] Exec format error",
                    "%s.err" % script_name: b"[Errno 8] Exec format error",
                },
                exit_status=8,
                error="Failed to execute %s [1/1]: 8" % script_name,
            ),
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
        self.assertThat(
            signal,
            MockAnyCall(
                "%s/metadata/%s/" % (url, MD_VERSION),
                {
                    "consumer_secret": "",
                    "consumer_key": consumer_key,
                    "token_key": token_key,
                    "token_secret": token_secret,
                },
                "WORKING",
                files={
                    script_name: b"Unable to execute script",
                    "%s.err" % script_name: b"Unable to execute script",
                },
                exit_status=2,
                error="Failed to execute %s [1/1]: 2" % script_name,
            ),
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
        self.assertThat(
            signal,
            MockAnyCall(
                "%s/metadata/%s/" % (url, MD_VERSION),
                {
                    "consumer_secret": "",
                    "consumer_key": consumer_key,
                    "token_key": token_key,
                    "token_secret": token_secret,
                },
                "WORKING",
                files={
                    script_name: b"[Errno 0] Exec format error",
                    "%s.err" % script_name: b"[Errno 0] Exec format error",
                },
                exit_status=2,
                error="Failed to execute %s [1/1]: 2" % script_name,
            ),
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

        self.assertThat(
            signal,
            MockAnyCall(
                "%s/metadata/%s/" % (url, MD_VERSION),
                {
                    "consumer_secret": "",
                    "consumer_key": consumer_key,
                    "token_key": token_key,
                    "token_secret": token_secret,
                },
                "TIMEDOUT",
                files={
                    script_name: b"",
                    "%s.out" % script_name: b"",
                    "%s.err" % script_name: b"",
                },
                error="Timeout(60) expired on %s [1/1]" % script_name,
            ),
        )

    def test_refresh_signals_finished(self):
        signal = self.patch(refresh, "signal")
        script_name = factory.make_name("script_name")
        info_scripts = self.create_scripts_success(script_name)

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        url = factory.make_url()

        with patch.dict(refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, url
            )
        self.assertThat(
            signal,
            MockAnyCall(
                "%s/metadata/%s/" % (url, MD_VERSION),
                {
                    "consumer_secret": "",
                    "consumer_key": consumer_key,
                    "token_key": token_key,
                    "token_secret": token_secret,
                },
                "OK",
                "Finished refreshing %s" % system_id,
            ),
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
        self.assertThat(
            signal,
            MockAnyCall(
                "%s/metadata/%s/" % (url, MD_VERSION),
                {
                    "consumer_secret": "",
                    "consumer_key": consumer_key,
                    "token_key": token_key,
                    "token_secret": token_secret,
                },
                "FAILED",
                "Failed refreshing %s" % system_id,
            ),
        )

    def test_refresh_executes_lxd_binary(self):
        signal = self.patch(refresh, "signal")
        script_name = LXD_OUTPUT_NAME
        info_scripts = self.create_scripts_success(script_name)

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        url = factory.make_url()

        with patch.dict(refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, url
            )
        self.assertThat(
            signal,
            MockAnyCall(
                "%s/metadata/%s/" % (url, MD_VERSION),
                {
                    "consumer_secret": "",
                    "consumer_key": consumer_key,
                    "token_key": token_key,
                    "token_secret": token_secret,
                },
                "WORKING",
                "Starting %s [1/1]" % script_name,
            ),
        )

    def test_refresh_executes_lxd_binary_in_snap(self):
        signal = self.patch(refresh, "signal")
        script_name = LXD_OUTPUT_NAME
        info_scripts = self.create_scripts_success(script_name)
        path = factory.make_name()
        self.patch(os, "environ", {"SNAP": path})

        system_id = factory.make_name("system_id")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        url = factory.make_url()

        with patch.dict(refresh.NODE_INFO_SCRIPTS, info_scripts, clear=True):
            refresh.refresh(
                system_id, consumer_key, token_key, token_secret, url
            )
        self.assertThat(
            signal,
            MockAnyCall(
                "%s/metadata/%s/" % (url, MD_VERSION),
                {
                    "consumer_secret": "",
                    "consumer_key": consumer_key,
                    "token_key": token_key,
                    "token_secret": token_secret,
                },
                "WORKING",
                "Starting %s [1/1]" % script_name,
            ),
        )

    def test_refresh_clears_up_temporary_directory(self):

        ScriptsBroken = factory.make_exception_type()

        def find_temporary_directories():
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir = Path(tmpdir).absolute()
                return {
                    str(entry)
                    for entry in tmpdir.parent.iterdir()
                    if entry.is_dir() and entry != tmpdir
                }

        tmpdirs_during = set()
        tmpdir_during = None

        def runscripts(*args, tmpdir, **kwargs):
            self.assertThat(tmpdir, DirExists())
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

        self.assertThat(tmpdirs_before, Not(Contains(tmpdir_during)))
        self.assertThat(tmpdirs_during, Contains(tmpdir_during))
        self.assertThat(tmpdirs_after, Not(Contains(tmpdir_during)))

    def test_refresh_logs_error(self):
        signal = self.patch(refresh, "signal")
        maaslog = self.patch(refresh.maaslog, "error")
        error = factory.make_string()
        signal.side_effect = SignalException(error)
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

        self.assertThat(
            maaslog, MockAnyCall("Error during controller refresh: %s" % error)
        )

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
        script_path = (Path(refresh.__file__) / ".." / script_name).resolve()
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
        script_path = (Path(refresh.__file__) / ".." / script_name).resolve()
        mock_popen.assert_called_once_with(
            ["sudo", "-E", str(script_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=ANY,
        )
