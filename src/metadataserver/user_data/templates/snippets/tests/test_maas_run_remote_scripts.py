# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maas_run_remote_scripts.py."""

__all__ = []

from datetime import timedelta
from io import BytesIO
import json
import os
import random
from subprocess import TimeoutExpired
import tarfile
import time
from unittest.mock import ANY
from zipfile import ZipFile

from maastesting.factory import factory
from maastesting.fixtures import TempDirectory
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnce,
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from snippets import maas_run_remote_scripts
from snippets.maas_run_remote_scripts import (
    download_and_extract_tar,
    install_dependencies,
    run_and_check,
    run_scripts,
    run_scripts_from_metadata,
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
                'timeout_seconds': random.randint(1, 500),
            })
        return scripts

    def make_script_output(self, scripts, scripts_dir, with_result=False):
        for script in scripts:
            output = factory.make_string()
            stdout = factory.make_string()
            stderr = factory.make_string()
            script['output'] = output.encode()
            script['stdout'] = stdout.encode()
            script['stderr'] = stderr.encode()
            script['output_path'] = os.path.join(scripts_dir, script['name'])
            script['stdout_path'] = os.path.join(
                scripts_dir, '%s.out' % script['name'])
            script['stderr_path'] = os.path.join(
                scripts_dir, '%s.err' % script['name'])
            script['download_path'] = os.path.join(
                scripts_dir, 'downloads', script['name'])
            os.makedirs(script['download_path'], exist_ok=True)
            open(script['output_path'], 'w').write(output)
            open(script['stdout_path'], 'w').write(stdout)
            open(script['stderr_path'], 'w').write(stderr)
            if with_result:
                result = factory.make_string()
                script['result'] = result.encode()
                script['result_path'] = os.path.join(
                    scripts_dir, '%s.yaml' % script['name'])
                open(script['result_path'], 'w').write(result)

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

    def test_run_scripts_from_metadata_doesnt_run_tests_on_commiss_fail(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_run_scripts = self.patch(maas_run_remote_scripts, 'run_scripts')
        mock_run_scripts.return_value = random.randint(1, 100)
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        index_json = self.make_index_json(scripts_dir)

        # Don't need to give the url, creds, or out_dir as we're not running
        # the scripts and sending the results.
        run_scripts_from_metadata(None, None, scripts_dir, None)

        self.assertThat(
            mock_run_scripts,
            MockCalledOnceWith(
                None, None, scripts_dir, None,
                index_json['commissioning_scripts']))
        self.assertThat(mock_signal, MockNotCalled())

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

    def test_run_and_check(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = self.make_scripts()
        script = scripts[0]
        self.make_script_output(scripts, scripts_dir)
        stdout = factory.make_string()
        stderr = factory.make_string()
        self.assertTrue(run_and_check(
            ['/bin/bash', '-c', 'echo %s;echo %s >&2' % (stdout, stderr)],
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['name'], {}))
        self.assertEquals(
            '%s\n' % stdout, open(script['stdout_path'], 'r').read())
        self.assertEquals(
            '%s\n' % stderr, open(script['stderr_path'], 'r').read())
        self.assertEquals(
            '%s\n%s\n' % (stdout, stderr),
            open(script['output_path'], 'r').read())

    def test_run_and_check_errors(self):
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = self.make_scripts()
        script = scripts[0]
        self.make_script_output(scripts, scripts_dir)
        stdout = factory.make_string()
        stderr = factory.make_string()
        self.assertFalse(run_and_check(
            ['/bin/bash', '-c', 'echo %s;echo %s >&2;false' % (
                stdout, stderr)],
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['name'], {}))
        self.assertEquals(
            '%s\n' % stdout, open(script['stdout_path'], 'r').read())
        self.assertEquals(
            '%s\n' % stderr, open(script['stderr_path'], 'r').read())
        self.assertEquals(
            '%s\n%s\n' % (stdout, stderr),
            open(script['output_path'], 'r').read())
        self.assertThat(
            mock_signal, MockCalledOnceWith(
                error='Failed installing package(s) for %s' % script['name'],
                exit_status=1, files={
                    script['name']: ('%s\n%s\n' % (stdout, stderr)).encode(),
                    '%s.out' % script['name']: ('%s\n' % stdout).encode(),
                    '%s.err' % script['name']: ('%s\n' % stderr).encode(),
                }))

    def test_run_and_check_ignores_errors(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = self.make_scripts()
        script = scripts[0]
        self.make_script_output(scripts, scripts_dir)
        stdout = factory.make_string()
        stderr = factory.make_string()
        self.assertTrue(run_and_check(
            ['/bin/bash', '-c', 'echo %s;echo %s >&2;false' % (
                stdout, stderr)],
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['name'], {}, True))
        self.assertEquals(
            '%s\n' % stdout, open(script['stdout_path'], 'r').read())
        self.assertEquals(
            '%s\n' % stderr, open(script['stderr_path'], 'r').read())
        self.assertEquals(
            '%s\n%s\n' % (stdout, stderr),
            open(script['output_path'], 'r').read())

    def test_install_dependencies_does_nothing_when_empty(self):
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        combined_path = '/%s' % factory.make_name('combined_path')
        stdout_path = '/%s' % factory.make_name('stdout_path')
        stderr_path = '/%s' % factory.make_name('stderr_path')
        download_path = '/%s' % factory.make_name('download_path')
        self.assertTrue(install_dependencies(
            {}, {}, combined_path, stdout_path, stderr_path, download_path))

        self.assertThat(mock_signal, MockNotCalled())

    def test_install_dependencies_apt(self):
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        mock_run_and_check.return_value = True
        args = {'status': 'INSTALLING'}
        script_name = factory.make_name('name')
        packages = [factory.make_name('pkg') for _ in range(3)]
        combined_path = '/%s' % factory.make_name('combined_path')
        stdout_path = '/%s' % factory.make_name('stdout_path')
        stderr_path = '/%s' % factory.make_name('stderr_path')
        download_path = '/%s' % factory.make_name('download_path')
        self.assertTrue(install_dependencies(
            args, {'name': script_name, 'packages': {'apt': packages}},
            combined_path, stdout_path, stderr_path, download_path))
        self.assertThat(mock_signal, MockCalledOnceWith(
            error='Installing apt packages for %s' % script_name,
            status='INSTALLING'))
        self.assertThat(mock_run_and_check, MockCalledOnceWith(
            ['sudo', '-n', 'apt-get', '-qy', 'install'] + packages,
            combined_path, stdout_path, stderr_path, script_name, args))
        # Verify cleanup
        self.assertFalse(os.path.exists(combined_path))
        self.assertFalse(os.path.exists(stdout_path))
        self.assertFalse(os.path.exists(stderr_path))

    def test_install_dependencies_apt_errors(self):
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        mock_run_and_check.return_value = False
        args = {'status': 'INSTALLING'}
        script_name = factory.make_name('name')
        packages = [factory.make_name('pkg') for _ in range(3)]
        combined_path = '/%s' % factory.make_name('combined_path')
        stdout_path = '/%s' % factory.make_name('stdout_path')
        stderr_path = '/%s' % factory.make_name('stderr_path')
        download_path = '/%s' % factory.make_name('download_path')
        self.assertFalse(install_dependencies(
            args, {'name': script_name, 'packages': {'apt': packages}},
            combined_path, stdout_path, stderr_path, download_path))
        self.assertThat(mock_signal, MockCalledOnceWith(
            error='Installing apt packages for %s' % script_name,
            status='INSTALLING'))
        self.assertThat(mock_run_and_check, MockCalledOnceWith(
            ['sudo', '-n', 'apt-get', '-qy', 'install'] + packages,
            combined_path, stdout_path, stderr_path, script_name, args))

    def test_install_dependencies_snap_str_list(self):
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        mock_run_and_check.return_value = True
        args = {'status': 'INSTALLING'}
        script_name = factory.make_name('name')
        packages = [factory.make_name('pkg') for _ in range(3)]
        combined_path = '/%s' % factory.make_name('combined_path')
        stdout_path = '/%s' % factory.make_name('stdout_path')
        stderr_path = '/%s' % factory.make_name('stderr_path')
        download_path = '/%s' % factory.make_name('download_path')
        self.assertTrue(install_dependencies(
            args, {'name': script_name, 'packages': {'snap': packages}},
            combined_path, stdout_path, stderr_path, download_path))
        self.assertThat(mock_signal, MockCalledOnceWith(
            error='Installing snap packages for %s' % script_name,
            status='INSTALLING'))
        for package in packages:
            self.assertThat(mock_run_and_check, MockAnyCall(
                ['sudo', '-n', 'snap', 'install', package],
                combined_path, stdout_path, stderr_path, script_name, args))
        # Verify cleanup
        self.assertFalse(os.path.exists(combined_path))
        self.assertFalse(os.path.exists(stdout_path))
        self.assertFalse(os.path.exists(stderr_path))

    def test_install_dependencies_snap_str_dict(self):
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        mock_run_and_check.return_value = True
        args = {'status': 'INSTALLING'}
        script_name = factory.make_name('name')
        packages = [
            {'name': factory.make_name('pkg')},
            {
                'name': factory.make_name('pkg'),
                'channel': random.choice([
                    'edge', 'beta', 'candidate', 'stable']),
            },
            {
                'name': factory.make_name('pkg'),
                'channel': random.choice([
                    'edge', 'beta', 'candidate', 'stable']),
                'mode': random.choice(['dev', 'jail']),
            },
            {
                'name': factory.make_name('pkg'),
                'channel': random.choice([
                    'edge', 'beta', 'candidate', 'stable']),
                'mode': random.choice(['dev', 'jail']),
            },
        ]
        combined_path = '/%s' % factory.make_name('combined_path')
        stdout_path = '/%s' % factory.make_name('stdout_path')
        stderr_path = '/%s' % factory.make_name('stderr_path')
        download_path = '/%s' % factory.make_name('download_path')
        self.assertTrue(install_dependencies(
            args, {'name': script_name, 'packages': {'snap': packages}},
            combined_path, stdout_path, stderr_path, download_path))
        self.assertThat(mock_signal, MockCalledOnceWith(
            error='Installing snap packages for %s' % script_name,
            status='INSTALLING'))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['sudo', '-n', 'snap', 'install', packages[0]['name']],
            combined_path, stdout_path, stderr_path, script_name, args))
        self.assertThat(mock_run_and_check, MockAnyCall(
            [
                'sudo', '-n', 'snap', 'install', packages[1]['name'],
                '--%s' % packages[1]['channel']
            ],
            combined_path, stdout_path, stderr_path, script_name, args))
        self.assertThat(mock_run_and_check, MockAnyCall(
            [
                'sudo', '-n', 'snap', 'install', packages[2]['name'],
                '--%s' % packages[2]['channel'],
                '--%smode' % packages[2]['mode'],
            ],
            combined_path, stdout_path, stderr_path, script_name, args))
        self.assertThat(mock_run_and_check, MockAnyCall(
            [
                'sudo', '-n', 'snap', 'install', packages[3]['name'],
                '--%s' % packages[3]['channel'],
                '--%smode' % packages[3]['mode'],
            ],
            combined_path, stdout_path, stderr_path, script_name, args))
        # Verify cleanup
        self.assertFalse(os.path.exists(combined_path))
        self.assertFalse(os.path.exists(stdout_path))
        self.assertFalse(os.path.exists(stderr_path))

    def test_install_dependencies_snap_str_errors(self):
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        mock_run_and_check.return_value = False
        args = {'status': 'INSTALLING'}
        script_name = factory.make_name('name')
        packages = [factory.make_name('pkg') for _ in range(3)]
        combined_path = '/%s' % factory.make_name('combined_path')
        stdout_path = '/%s' % factory.make_name('stdout_path')
        stderr_path = '/%s' % factory.make_name('stderr_path')
        download_path = '/%s' % factory.make_name('download_path')
        self.assertFalse(install_dependencies(
            args, {'name': script_name, 'packages': {'snap': packages}},
            combined_path, stdout_path, stderr_path, download_path))
        self.assertThat(mock_signal, MockCalledOnceWith(
            error='Installing snap packages for %s' % script_name,
            status='INSTALLING'))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['sudo', '-n', 'snap', 'install', packages[0]],
            combined_path, stdout_path, stderr_path, script_name, args))

    def test_install_dependencies_url(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        self.patch(maas_run_remote_scripts, 'run_and_check')
        args = {'status': 'INSTALLING'}
        scripts = self.make_scripts()
        script = scripts[0]
        self.make_script_output(scripts, scripts_dir)
        self.assertTrue(install_dependencies(
            args, {'name': script['name'], 'packages': {
                'url': [factory.make_name('url')]}},
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['download_path']))
        self.assertThat(mock_signal, MockAnyCall(
            error='Downloading and extracting URLs for %s' % script['name'],
            **args))
        # Verify cleanup
        self.assertFalse(os.path.exists(script['output_path']))
        self.assertFalse(os.path.exists(script['stdout_path']))
        self.assertFalse(os.path.exists(script['stderr_path']))

    def test_install_dependencies_url_errors(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        mock_run_and_check.return_value = False
        args = {'status': 'INSTALLING'}
        scripts = self.make_scripts()
        script = scripts[0]
        self.make_script_output(scripts, scripts_dir)
        self.assertFalse(install_dependencies(
            args, {'name': script['name'], 'packages': {
                'url': [factory.make_name('url')]}},
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['download_path']))
        self.assertThat(mock_signal, MockAnyCall(
            error='Downloading and extracting URLs for %s' % script['name'],
            **args))

    def test_install_dependencies_url_tar(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        self.patch(maas_run_remote_scripts, 'run_and_check')
        args = {'status': 'INSTALLING'}
        scripts = self.make_scripts()
        script = scripts[0]
        self.make_script_output(scripts, scripts_dir)
        tar_file = os.path.join(script['download_path'], 'file.tar.xz')
        file_content = factory.make_bytes()
        with tarfile.open(tar_file, 'w:xz') as tar:
            tarinfo = tarfile.TarInfo(name='test-file')
            tarinfo.size = len(file_content)
            tarinfo.mode = 0o755
            tar.addfile(tarinfo, BytesIO(file_content))
        with open(script['output_path'], 'w') as output:
            output.write("Saving to: '%s'" % tar_file)

        self.assertTrue(install_dependencies(
            args, {'name': script['name'], 'packages': {
                'url': [tar_file]}},
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['download_path']))
        self.assertThat(mock_signal, MockAnyCall(
            error='Downloading and extracting URLs for %s' % script['name'],
            **args))
        with open(
                os.path.join(script['download_path'], 'test-file'), 'rb') as f:
            self.assertEquals(file_content, f.read())
        # Verify cleanup
        self.assertFalse(os.path.exists(script['output_path']))
        self.assertFalse(os.path.exists(script['stdout_path']))
        self.assertFalse(os.path.exists(script['stderr_path']))

    def test_install_dependencies_url_zip(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        self.patch(maas_run_remote_scripts, 'run_and_check')
        args = {'status': 'INSTALLING'}
        scripts = self.make_scripts()
        script = scripts[0]
        self.make_script_output(scripts, scripts_dir)
        zip_file = os.path.join(script['download_path'], 'file.zip')
        file_content = factory.make_bytes()
        with ZipFile(zip_file, 'w') as z:
            z.writestr('test-file', file_content)
        with open(script['output_path'], 'w') as output:
            output.write("Saving to: '%s'" % zip_file)

        self.assertTrue(install_dependencies(
            args, {'name': script['name'], 'packages': {
                'url': [zip_file]}},
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['download_path']))
        self.assertThat(mock_signal, MockAnyCall(
            error='Downloading and extracting URLs for %s' % script['name'],
            **args))
        with open(
                os.path.join(script['download_path'], 'test-file'), 'rb') as f:
            self.assertEquals(file_content, f.read())
        # Verify cleanup
        self.assertFalse(os.path.exists(script['output_path']))
        self.assertFalse(os.path.exists(script['stdout_path']))
        self.assertFalse(os.path.exists(script['stderr_path']))

    def test_install_dependencies_url_deb(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        args = {'status': 'INSTALLING'}
        scripts = self.make_scripts()
        script = scripts[0]
        self.make_script_output(scripts, scripts_dir)
        deb_file = os.path.join(script['download_path'], 'file.deb')
        open(deb_file, 'w').close()
        with open(script['output_path'], 'w') as output:
            output.write("Saving to: '%s'" % deb_file)

        self.assertTrue(install_dependencies(
            args, {'name': script['name'], 'packages': {
                'url': [deb_file]}},
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['download_path']))
        self.assertThat(mock_signal, MockAnyCall(
            error='Downloading and extracting URLs for %s' % script['name'],
            **args))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['wget', deb_file, '-P', script['download_path']],
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['name'], args))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['sudo', '-n', 'dpkg', '-i', deb_file], script['output_path'],
            script['stdout_path'], script['stderr_path'], script['name'], args,
            True))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['sudo', '-n', 'apt-get', 'install', '-qyf'],
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['name'], args))
        # Verify cleanup
        self.assertFalse(os.path.exists(script['output_path']))
        self.assertFalse(os.path.exists(script['stdout_path']))
        self.assertFalse(os.path.exists(script['stderr_path']))

    def test_install_dependencies_url_deb_errors(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        mock_run_and_check.side_effect = (True, True, False)
        args = {'status': 'INSTALLING'}
        scripts = self.make_scripts()
        script = scripts[0]
        self.make_script_output(scripts, scripts_dir)
        deb_file = os.path.join(script['download_path'], 'file.deb')
        open(deb_file, 'w').close()
        with open(script['output_path'], 'w') as output:
            output.write("Saving to: '%s'" % deb_file)

        self.assertFalse(install_dependencies(
            args, {'name': script['name'], 'packages': {
                'url': [deb_file]}},
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['download_path']))
        self.assertThat(mock_signal, MockAnyCall(
            error='Downloading and extracting URLs for %s' % script['name'],
            **args))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['wget', deb_file, '-P', script['download_path']],
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['name'], args))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['sudo', '-n', 'dpkg', '-i', deb_file], script['output_path'],
            script['stdout_path'], script['stderr_path'], script['name'], args,
            True))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['sudo', '-n', 'apt-get', 'install', '-qyf'],
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['name'], args))

    def test_install_dependencies_url_snap(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        args = {'status': 'INSTALLING'}
        scripts = self.make_scripts()
        script = scripts[0]
        self.make_script_output(scripts, scripts_dir)
        snap_file = os.path.join(script['download_path'], 'file.snap')
        open(snap_file, 'w').close()
        with open(script['output_path'], 'w') as output:
            output.write("Saving to: '%s'" % snap_file)

        self.assertTrue(install_dependencies(
            args, {'name': script['name'], 'packages': {
                'url': [snap_file]}},
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['download_path']))
        self.assertThat(mock_signal, MockAnyCall(
            error='Downloading and extracting URLs for %s' % script['name'],
            **args))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['wget', snap_file, '-P', script['download_path']],
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['name'], args))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['sudo', '-n', 'snap', snap_file],
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['name'], args))
        # Verify cleanup
        self.assertFalse(os.path.exists(script['output_path']))
        self.assertFalse(os.path.exists(script['stdout_path']))
        self.assertFalse(os.path.exists(script['stderr_path']))

    def test_install_dependencies_url_snap_errors(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        mock_run_and_check.side_effect = (True, False)
        args = {'status': 'INSTALLING'}
        scripts = self.make_scripts()
        script = scripts[0]
        self.make_script_output(scripts, scripts_dir)
        snap_file = os.path.join(script['download_path'], 'file.snap')
        open(snap_file, 'w').close()
        with open(script['output_path'], 'w') as output:
            output.write("Saving to: '%s'" % snap_file)

        self.assertFalse(install_dependencies(
            args, {'name': script['name'], 'packages': {
                'url': [snap_file]}},
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['download_path']))
        self.assertThat(mock_signal, MockAnyCall(
            error='Downloading and extracting URLs for %s' % script['name'],
            **args))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['wget', snap_file, '-P', script['download_path']],
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['name'], args))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['sudo', '-n', 'snap', snap_file],
            script['output_path'], script['stdout_path'],
            script['stderr_path'], script['name'], args))

    def test_run_scripts(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_popen = self.patch(maas_run_remote_scripts, 'Popen')
        mock_capture_script_output = self.patch(
            maas_run_remote_scripts, 'capture_script_output')
        self.patch(maas_run_remote_scripts, 'install_dependencies')
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

    def test_installs_dependencies(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_popen = self.patch(maas_run_remote_scripts, 'Popen')
        mock_capture_script_output = self.patch(
            maas_run_remote_scripts, 'capture_script_output')
        mock_install_deps = self.patch(
            maas_run_remote_scripts, 'install_dependencies')
        mock_install_deps.side_effect = (False, True)
        scripts = self.make_scripts(2)
        self.make_script_output(scripts, scripts_dir, with_result=True)

        # Don't need to give the url or creds as we're not running the scripts
        # and sending the result. The scripts_dir and out_dir are the same as
        # in the test environment there isn't anything in the scripts_dir.
        # Returns one due to mock_run.returncode returning a MagicMock which is
        # detected as a failed script run.
        self.assertEquals(
            2, run_scripts(None, None, scripts_dir, scripts_dir, scripts))

        # Only the second script will signal working since the first failed
        # to install dependencies.
        args = {
            'url': None, 'creds': None, 'status': 'WORKING',
            'script_result_id': scripts[1]['script_result_id'],
            'script_version_id': scripts[1]['script_version_id'],
            'error': 'Starting %s [2/2]' % scripts[1]['name'],
        }
        self.assertThat(mock_signal, MockAnyCall(**args))
        self.assertThat(mock_popen, MockCalledOnce())
        self.assertThat(mock_capture_script_output, MockCalledOnce())
        # This is a MagicMock
        args['exit_status'] = ANY
        args['files'] = {
            scripts[1]['name']: scripts[1]['output'],
            '%s.out' % scripts[1]['name']: scripts[1]['stdout'],
            '%s.err' % scripts[1]['name']: scripts[1]['stderr'],
            '%s.yaml' % scripts[1]['name']: scripts[1]['result'],
        }
        args['error'] = 'Finished %s [2/2]: 1' % scripts[1]['name']
        self.assertThat(mock_signal, MockAnyCall(**args))

    def test_run_scripts_sends_result_when_available(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_popen = self.patch(maas_run_remote_scripts, 'Popen')
        mock_capture_script_output = self.patch(
            maas_run_remote_scripts, 'capture_script_output')
        self.patch(maas_run_remote_scripts, 'install_dependencies')
        scripts = self.make_scripts()
        self.make_script_output(scripts, scripts_dir, with_result=True)

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
            '%s.yaml' % scripts[0]['name']: scripts[0]['result'],
        }
        args['error'] = 'Finished %s [1/1]: 1' % scripts[0]['name']
        self.assertThat(mock_signal, MockAnyCall(**args))

    def test_run_scripts_sets_env_vars(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        self.patch(maas_run_remote_scripts, 'signal')
        mock_popen = self.patch(maas_run_remote_scripts, 'Popen')
        self.patch(maas_run_remote_scripts, 'capture_script_output')
        self.patch(maas_run_remote_scripts, 'install_dependencies')
        scripts = self.make_scripts()
        self.make_script_output(scripts, scripts_dir, with_result=True)

        # Don't need to give the url or creds as we're not running the scripts
        # and sending the result. The scripts_dir and out_dir are the same as
        # in the test environment there isn't anything in the scripts_dir.
        # Returns one due to mock_run.returncode returning a MagicMock which is
        # detected as a failed script run.
        self.assertEquals(
            1, run_scripts(None, None, scripts_dir, scripts_dir, scripts))

        env = mock_popen.call_args[1]['env']
        base = os.path.join(scripts_dir, scripts[0]['name'])
        self.assertEquals(base, env['OUTPUT_COMBINED_PATH'])
        self.assertEquals('%s.out' % base, env['OUTPUT_STDOUT_PATH'])
        self.assertEquals('%s.err' % base, env['OUTPUT_STDERR_PATH'])
        self.assertEquals('%s.yaml' % base, env['RESULT_PATH'])
        self.assertEquals(
            os.path.join(scripts_dir, 'downloads', scripts[0]['name']),
            env['DOWNLOAD_PATH'])
        self.assertIn('PATH', env)

    def test_run_scripts_signals_failure(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        self.patch(maas_run_remote_scripts, 'Popen')
        self.patch(maas_run_remote_scripts, 'capture_script_output')
        self.patch(maas_run_remote_scripts, 'install_dependencies')
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

    def test_run_scripts_signals_failure_on_unexecutable_script(self):
        # Regression test for LP:1669246
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_popen = self.patch(maas_run_remote_scripts, 'Popen')
        mock_popen.side_effect = OSError(8, 'Exec format error')
        self.patch(maas_run_remote_scripts, 'capture_script_output')
        scripts = self.make_scripts()
        script = scripts[0]
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
                creds=None, url=None, status='WORKING', exit_status=8,
                error='Failed to execute %s [1/1]: 8' % script['name'],
                script_result_id=script['script_result_id'],
                script_version_id=script['script_version_id'],
                files={
                    script['name']: b'[Errno 8] Exec format error',
                    '%s.err' % script['name']: b'[Errno 8] Exec format error',
                }))
        self.assertThat(
            mock_signal,
            MockAnyCall(
                None, None, 'FAILED', '1 scripts failed to run'))

    def test_run_scripts_signals_failure_on_unexecutable_script_no_errno(self):
        # Regression test for LP:1669246
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_popen = self.patch(maas_run_remote_scripts, 'Popen')
        mock_popen.side_effect = OSError()
        self.patch(maas_run_remote_scripts, 'capture_script_output')
        scripts = self.make_scripts()
        script = scripts[0]
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
                creds=None, url=None, status='WORKING', exit_status=2,
                error='Failed to execute %s [1/1]: 2' % script['name'],
                script_result_id=script['script_result_id'],
                script_version_id=script['script_version_id'],
                files={
                    script['name']: b'Unable to execute script',
                    '%s.err' % script['name']: b'Unable to execute script',
                }))
        self.assertThat(
            mock_signal,
            MockAnyCall(
                None, None, 'FAILED', '1 scripts failed to run'))

    def test_run_scripts_signals_failure_on_unexecutable_script_baderrno(self):
        # Regression test for LP:1669246
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        mock_popen = self.patch(maas_run_remote_scripts, 'Popen')
        mock_popen.side_effect = OSError(0, 'Exec format error')
        self.patch(maas_run_remote_scripts, 'capture_script_output')
        scripts = self.make_scripts()
        script = scripts[0]
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
                creds=None, url=None, status='WORKING', exit_status=2,
                error='Failed to execute %s [1/1]: 2' % script['name'],
                script_result_id=script['script_result_id'],
                script_version_id=script['script_version_id'],
                files={
                    script['name']: b'[Errno 0] Exec format error',
                    '%s.err' % script['name']: b'[Errno 0] Exec format error',
                }))
        self.assertThat(
            mock_signal,
            MockAnyCall(
                None, None, 'FAILED', '1 scripts failed to run'))

    def test_run_scripts_signals_timeout(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        self.patch(maas_run_remote_scripts, 'Popen')
        scripts = self.make_scripts()
        self.make_script_output(scripts, scripts_dir)
        mock_cap = self.patch(maas_run_remote_scripts, 'capture_script_output')
        mock_cap.side_effect = TimeoutExpired(
            [factory.make_name('arg') for _ in range(3)],
            scripts[0]['timeout_seconds'])
        self.patch(maas_run_remote_scripts, 'install_dependencies')

        # Don't need to give the url or creds as we're not running the scripts
        # and sending the result. The scripts_dir and out_dir are the same as
        # in the test environment there isn't anything in the scripts_dir.
        self.assertEquals(
            1, run_scripts(None, None, scripts_dir, scripts_dir, scripts))

        self.assertThat(
            mock_signal,
            MockAnyCall(
                creds=None, url=None, status='TIMEDOUT',
                error='Timeout(%s) expired on %s [1/1]' % (
                    str(timedelta(seconds=scripts[0]['timeout_seconds'])),
                    scripts[0]['name']),
                script_result_id=scripts[0]['script_result_id'],
                script_version_id=scripts[0]['script_version_id'],
                files={
                    scripts[0]['name']: scripts[0]['output'],
                    '%s.out' % scripts[0]['name']: scripts[0]['stdout'],
                    '%s.err' % scripts[0]['name']: scripts[0]['stderr'],
                }))
        self.assertThat(
            mock_signal,
            MockAnyCall(
                None, None, 'FAILED', '1 scripts failed to run'))

    def test_heartbeat(self):
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        url = factory.make_url()
        creds = factory.make_name('creds')
        heart_beat = maas_run_remote_scripts.HeartBeat(url, creds)
        start_time = time.time()
        heart_beat.start()
        heart_beat.stop()
        self.assertLess(time.time() - start_time, 1)
        self.assertThat(mock_signal, MockCalledOnceWith(url, creds, 'WORKING'))

    def test_heartbeat_with_long_sleep(self):
        mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        self.patch(maas_run_remote_scripts.time, 'monotonic').side_effect = [
            time.monotonic(),
            time.monotonic(),
            time.monotonic() + 500,
        ]
        url = factory.make_url()
        creds = factory.make_name('creds')
        heart_beat = maas_run_remote_scripts.HeartBeat(url, creds)
        start_time = time.time()
        heart_beat.start()
        heart_beat.stop()
        self.assertLess(time.time() - start_time, 1)
        self.assertThat(mock_signal, MockCalledOnceWith(url, creds, 'WORKING'))
