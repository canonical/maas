# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maas_run_remote_scripts.py."""

__all__ = []

from io import BytesIO
import json
import os
from pathlib import Path
import random
from subprocess import (
    PIPE,
    Popen,
)
import tarfile
import time
from unittest.mock import ANY

from lxml import etree
from maastesting.factory import factory
from maastesting.fixtures import TempDirectory
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnce,
    MockCalledOnceWith,
)
from maastesting.testcase import MAASTestCase
from snippets import maas_run_remote_scripts
from snippets.maas_run_remote_scripts import (
    capture_script_output,
    download_and_extract_tar,
    run_scripts,
    run_scripts_from_metadata,
)
from testtools.matchers import (
    Equals,
    MatchesAny,
    MatchesListwise,
)


class TestMaasRunRemoteScripts(MAASTestCase):

    def make_scripts(self, count=1):
        scripts = []
        for _ in range(count):
            name = factory.make_name('name')
            scripts.append({
                'name': name,
                'path': '%s/%s' % (factory.make_name('dir'), name),
                'script_result_id': random.randint(1, 1000),
                'script_version_id': random.randint(1, 1000),
            })
        return scripts

    def make_script_output(self, scripts, scripts_dir):
        for script in scripts:
            output = factory.make_string()
            stdout = factory.make_string()
            stderr = factory.make_string()
            script['output'] = output.encode()
            script['stdout'] = stdout.encode()
            script['stderr'] = stderr.encode()
            output_path = os.path.join(scripts_dir, script['name'])
            stdout_path = os.path.join(scripts_dir, '%s.out' % script['name'])
            stderr_path = os.path.join(scripts_dir, '%s.err' % script['name'])
            open(output_path, 'w').write(output)
            open(stdout_path, 'w').write(stdout)
            open(stderr_path, 'w').write(stderr)

    def make_index_json(
            self, scripts_dir, with_commissioning=True, with_testing=True):
        index_json = {}
        if with_commissioning:
            index_json['commissioning_scripts'] = self.make_scripts()
        if with_testing:
            index_json['testing_scripts'] = self.make_scripts()
        with open(os.path.join(scripts_dir, 'index.json'), 'w') as f:
            f.write(json.dumps({'1.0': index_json}))
        return index_json

    def test_download_and_extract_tar(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        binary = BytesIO()
        file_content = factory.make_bytes()
        with tarfile.open(mode='w', fileobj=binary) as tar:
            tarinfo = tarfile.TarInfo(name='test-file')
            tarinfo.size = len(file_content)
            tarinfo.mode = 0o755
            tar.addfile(tarinfo, BytesIO(file_content))
        mock_geturl = self.patch(maas_run_remote_scripts, 'geturl')
        mock_geturl.return_value = binary.getvalue()

        # geturl is mocked out so we don't need to give a url or creds.
        download_and_extract_tar(None, None, scripts_dir)

        written_file_content = open(
            os.path.join(scripts_dir, 'test-file'), 'rb').read()
        self.assertEquals(file_content, written_file_content)

    def test_run_scripts_from_metadata(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_run_scripts = self.patch(maas_run_remote_scripts, 'run_scripts')
        mock_run_scripts.return_value = 0
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        index_json = self.make_index_json(scripts_dir)

        # Don't need to give the url, creds, or out_dir as we're not running
        # the scripts and sending the results.
        run_scripts_from_metadata(None, None, scripts_dir, None)

        self.assertThat(
            mock_run_scripts,
            MockAnyCall(
                None, None, scripts_dir, None,
                index_json['commissioning_scripts']))
        self.assertThat(
            mock_run_scripts,
            MockAnyCall(
                None, None, scripts_dir, None,
                index_json['testing_scripts']))
        self.assertThat(mock_signal, MockAnyCall(None, None, 'TESTING'))
        self.assertThat(
            mock_signal,
            MockAnyCall(None, None, 'OK', 'All scripts successfully ran'))

    def test_run_scripts_from_metadata_does_nothing_on_empty(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        self.patch(maas_run_remote_scripts, 'run_scripts')
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        self.make_index_json(scripts_dir, False, False)

        # Don't need to give the url, creds, or out_dir as we're not running
        # the scripts and sending the results.
        run_scripts_from_metadata(None, None, scripts_dir, None)

        self.assertThat(
            mock_signal,
            MockCalledOnceWith(
                None, None, 'OK', 'All scripts successfully ran'))

    def test_run_scripts(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_popen = self.patch(maas_run_remote_scripts, 'Popen')
        mock_capture_script_output = self.patch(
            maas_run_remote_scripts, 'capture_script_output')
        scripts = self.make_scripts()
        self.make_script_output(scripts, scripts_dir)

        # Don't need to give the url or creds as we're not running the scripts
        # and sending the result. The scripts_dir and out_dir are the same as
        # in the test environment there isn't anything in the scripts_dir.
        # Returns one due to mock_run.returncode returning a MagicMock which is
        # detected as a failed script run.
        self.assertEquals(
            1, run_scripts(None, None, scripts_dir, scripts_dir, scripts))

        args = {
            'url': None, 'creds': None, 'status': 'WORKING',
            'script_result_id': scripts[0]['script_result_id'],
            'script_version_id': scripts[0]['script_version_id'],
            'error': 'Starting %s [1/1]' % scripts[0]['name'],
        }
        self.assertThat(mock_signal, MockAnyCall(**args))
        self.assertThat(mock_popen, MockCalledOnce())
        self.assertThat(mock_capture_script_output, MockCalledOnce())
        # This is a MagicMock
        args['exit_status'] = ANY
        args['files'] = {
            scripts[0]['name']: scripts[0]['output'],
            '%s.out' % scripts[0]['name']: scripts[0]['stdout'],
            '%s.err' % scripts[0]['name']: scripts[0]['stderr'],
        }
        args['error'] = 'Finished %s [1/1]: 1' % scripts[0]['name']
        self.assertThat(mock_signal, MockAnyCall(**args))

    def test_run_scripts_signals_failure(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        self.patch(maas_run_remote_scripts, 'Popen')
        self.patch(maas_run_remote_scripts, 'capture_script_output')
        scripts = self.make_scripts()
        self.make_script_output(scripts, scripts_dir)

        # Don't need to give the url or creds as we're not running the scripts
        # and sending the result. The scripts_dir and out_dir are the same as
        # in the test environment there isn't anything in the scripts_dir.
        # Returns one due to mock_run.returncode returning a MagicMock which is
        # detected as a failed script run.
        self.assertEquals(
            1, run_scripts(None, None, scripts_dir, scripts_dir, scripts))

        self.assertThat(
            mock_signal,
            MockAnyCall(
                None, None, 'FAILED', '1 scripts failed to run'))


class TestCaptureScriptOutput(MAASTestCase):

    # Iterate multiple times to shake out spurious failures.
    scenarios = [
        ("iteration %d" % iteration, {})
        for iteration in range(1, 21)
    ]

    def capture(self, proc):
        scripts_dir = Path(self.useFixture(TempDirectory()).path)
        combined_path = scripts_dir.joinpath("combined")
        stdout_path = scripts_dir.joinpath("stdout")
        stderr_path = scripts_dir.joinpath("stderr")

        returncode = capture_script_output(
            proc, str(combined_path), str(stdout_path), str(stderr_path))

        return (
            returncode,
            stdout_path.read_text(),
            stderr_path.read_text(),
            combined_path.read_text(),
        )

    def test__captures_script_output(self):
        proc = Popen(
            'echo "stdout"; echo "stderr" 1>&2', stdout=PIPE, stderr=PIPE,
            shell=True)
        self.assertThat(
            self.capture(proc), MatchesListwise((
                Equals(0), Equals("stdout\n"), Equals("stderr\n"),
                # The writes to stdout and stderr occur so close in time that
                # they may be received in any order.
                MatchesAny(
                    Equals("stdout\nstderr\n"),
                    Equals("stderr\nstdout\n"),
                ),
            )))

    def test__does_not_wait_for_forked_process(self):
        start_time = time.time()
        proc = Popen('sleep 6 &', stdout=PIPE, stderr=PIPE, shell=True)
        self.assertThat(
            self.capture(proc), MatchesListwise((
                Equals(0), Equals(""), Equals(""), Equals(""),
            )))
        # A forked process should continue running after capture_script_output
        # returns. capture_script_output should not block on the forked call.
        self.assertLess(time.time() - start_time, 3)

    def test__captures_output_from_completed_process(self):
        # Write to both stdout and stderr.
        proc = Popen(
            'echo -n foo >&1 && echo -n bar >&2',
            stdout=PIPE, stderr=PIPE, shell=True)
        # Wait for it to finish before capturing.
        self.assertEquals(0, proc.wait())
        # Capturing now still gets foo and bar.
        self.assertThat(
            self.capture(proc), MatchesListwise((
                Equals(0), Equals("foo"), Equals("bar"),
                # The writes to stdout and stderr occur so close in time that
                # they may be received in any order.
                MatchesAny(Equals("foobar"), Equals("barfoo")),
            )))

    def test__captures_stderr_after_stdout_closes(self):
        # Write to stdout, close stdout, then write to stderr.
        proc = Popen(
            'echo -n foo >&1 && exec 1>&- && echo -n bar >&2',
            stdout=PIPE, stderr=PIPE, shell=True)
        # Capturing gets the bar even after stdout is closed.
        self.assertThat(
            self.capture(proc), MatchesListwise((
                Equals(0), Equals("foo"), Equals("bar"),
                # The writes to stdout and stderr occur so close in time that
                # they may be received in any order.
                MatchesAny(Equals("foobar"), Equals("barfoo")),
            )))

    def test__captures_stdout_after_stderr_closes(self):
        # Write to stderr, close stderr, then write to stdout.
        proc = Popen(
            'echo -n bar >&2 && exec 2>&- && echo -n foo >&1',
            stdout=PIPE, stderr=PIPE, shell=True)
        # Capturing gets the foo even after stderr is closed.
        self.assertThat(
            self.capture(proc), MatchesListwise((
                Equals(0), Equals("foo"), Equals("bar"),
                # The writes to stdout and stderr occur so close in time that
                # they may be received in any order.
                MatchesAny(Equals("foobar"), Equals("barfoo")),
            )))

    def test__captures_all_output(self):
        proc = Popen(("lshw", "-xml"), stdout=PIPE, stderr=PIPE)
        returncode, stdout, stderr, combined = self.capture(proc)
        self.assertThat(returncode, Equals(0), stderr)
        # This is a complete XML document; we've captured all output.
        self.assertThat(etree.fromstring(stdout).tag, Equals("list"))
