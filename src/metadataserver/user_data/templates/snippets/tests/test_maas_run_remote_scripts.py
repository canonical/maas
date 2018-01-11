# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maas_run_remote_scripts.py."""

__all__ = []

import copy
from datetime import timedelta
import http.client
from io import BytesIO
import json
import os
import random
import stat
from subprocess import (
    DEVNULL,
    PIPE,
    TimeoutExpired,
)
import tarfile
import time
from unittest.mock import (
    ANY,
    call,
    MagicMock,
)
from zipfile import ZipFile

from maastesting.factory import factory
from maastesting.fixtures import TempDirectory
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from snippets import maas_run_remote_scripts
from snippets.maas_run_remote_scripts import (
    download_and_extract_tar,
    get_block_devices,
    install_dependencies,
    parse_parameters,
    run_and_check,
    run_script,
    run_scripts,
    run_scripts_from_metadata,
)

# Unused ScriptResult id, used to make sure number is always unique.
SCRIPT_RESULT_ID = 0


def make_script(
        scripts_dir=None, with_added_attribs=True, name=None,
        script_version_id=None, timeout_seconds=None, parallel=None,
        hardware_type=None, with_output=True):
    if name is None:
        name = factory.make_name('name')
    if script_version_id is None:
        script_version_id = random.randint(1, 1000)
    if timeout_seconds is None:
        timeout_seconds = random.randint(1, 1000)
    if parallel is None:
        parallel = random.randint(0, 2)
    if hardware_type is None:
        hardware_type = random.randint(0, 4)
    global SCRIPT_RESULT_ID
    script_result_id = SCRIPT_RESULT_ID
    SCRIPT_RESULT_ID += 1
    ret = {
        'name': name,
        'path': '%s/%s' % (random.choice(['commissioning', 'testing']), name),
        'script_result_id': script_result_id,
        'script_version_id': script_version_id,
        'timeout_seconds': timeout_seconds,
        'parallel': parallel,
        'hardware_type': hardware_type,
        'args': {},
        'has_started': factory.pick_bool(),
    }
    ret['msg_name'] = '%s (id: %s, script_version_id: %s)' % (
        name, script_result_id, script_version_id)
    if with_added_attribs:
        if scripts_dir is None:
            scripts_dir = factory.make_name('scripts_dir')
        out_dir = os.path.join(
            scripts_dir, 'out', '%s.%s' % (name, script_result_id))

        ret['combined_name'] = name
        ret['combined_path'] = os.path.join(out_dir, ret['combined_name'])
        ret['combined'] = factory.make_string()
        ret['stdout_name'] = '%s.out' % name
        ret['stdout_path'] = os.path.join(out_dir, ret['stdout_name'])
        ret['stdout'] = factory.make_string()
        ret['stderr_name'] = '%s.err' % name
        ret['stderr_path'] = os.path.join(out_dir, ret['stderr_name'])
        ret['stderr'] = factory.make_string()
        ret['result_name'] = '%s.yaml' % name
        ret['result_path'] = os.path.join(out_dir, ret['result_name'])
        ret['result'] = factory.make_string()
        ret['download_path'] = os.path.join(scripts_dir, 'downloads', name)

        if os.path.exists(scripts_dir):
            os.makedirs(out_dir, exist_ok=True)
            os.makedirs(ret['download_path'], exist_ok=True)
            script_path = os.path.join(scripts_dir, ret['path'])
            os.makedirs(os.path.dirname(script_path), exist_ok=True)
            with open(os.path.join(scripts_dir, ret['path']), 'w') as f:
                f.write('#!/bin/bash')
            st = os.stat(script_path)
            os.chmod(script_path, st.st_mode | stat.S_IEXEC)

            if with_output:
                open(ret['combined_path'], 'w').write(ret['combined'])
                open(ret['stdout_path'], 'w').write(ret['stdout'])
                open(ret['stderr_path'], 'w').write(ret['stderr'])
                open(ret['result_path'], 'w').write(ret['result'])

    return ret


def make_scripts(
        instance=True, count=3, scripts_dir=None, with_added_attribs=True,
        with_output=True, parallel=None, hardware_type=None):
    if instance:
        script = make_script(
            scripts_dir=scripts_dir, with_added_attribs=with_added_attribs,
            with_output=with_output, parallel=parallel,
            hardware_type=hardware_type)
        return [script] + [
            make_script(
                scripts_dir=scripts_dir, with_added_attribs=with_added_attribs,
                with_output=with_output, name=script['name'],
                script_version_id=script['script_version_id'],
                timeout_seconds=script['timeout_seconds'],
                parallel=script['parallel'],
                hardware_type=script['hardware_type'])
            for _ in range(count - 1)
        ]
    else:
        return [
            make_script(
                scripts_dir=scripts_dir, with_added_attribs=with_added_attribs,
                with_output=with_output, parallel=parallel)
            for _ in range(count)
        ]


class TestInstallDependencies(MAASTestCase):

    def setUp(self):
        super().setUp()
        self.mock_output_and_send = self.patch(
            maas_run_remote_scripts, 'output_and_send')
        self.patch(maas_run_remote_scripts.sys.stdout, 'write')
        self.patch(maas_run_remote_scripts.sys.stderr, 'write')

    def test_run_and_check(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir, with_output=False)
        script = scripts[0]

        self.assertTrue(run_and_check(
            ['/bin/bash', '-c', 'echo %s;echo %s >&2' % (
                script['stdout'], script['stderr'])],
            scripts))
        self.assertEquals(
            '%s\n' % script['stdout'], open(script['stdout_path'], 'r').read())
        self.assertEquals(
            '%s\n' % script['stderr'], open(script['stderr_path'], 'r').read())
        self.assertEquals(
            '%s\n%s\n' % (script['stdout'], script['stderr']),
            open(script['combined_path'], 'r').read())

    def test_run_and_check_errors(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir, with_output=False)
        script = scripts[0]

        self.assertFalse(run_and_check(
            ['/bin/bash', '-c', 'echo %s;echo %s >&2;false' % (
                script['stdout'], script['stderr'])],
            scripts))
        self.assertEquals(
            '%s\n' % script['stdout'], open(script['stdout_path'], 'r').read())
        self.assertEquals(
            '%s\n' % script['stderr'], open(script['stderr_path'], 'r').read())
        self.assertEquals(
            '%s\n%s\n' % (script['stdout'], script['stderr']),
            open(script['combined_path'], 'r').read())
        for script in scripts:
            self.assertThat(
                self.mock_output_and_send, MockAnyCall(
                    'Failed installing package(s) for %s' % script['msg_name'],
                    exit_status=1, status='INSTALLING', files={
                        scripts[0]['combined_name']: ('%s\n%s\n' % (
                            scripts[0]['stdout'],
                            scripts[0]['stderr'])).encode(),
                        scripts[0]['stdout_name']: (
                            '%s\n' % scripts[0]['stdout']).encode(),
                        scripts[0]['stderr_name']: (
                            '%s\n' % scripts[0]['stderr']).encode(),
                    }))

    def test_run_and_check_ignores_errors(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir, with_output=False)
        script = scripts[0]

        self.assertTrue(run_and_check(
            ['/bin/bash', '-c', 'echo %s;echo %s >&2;false' % (
                script['stdout'], script['stderr'])],
            scripts, False))
        self.assertEquals(
            '%s\n' % script['stdout'], open(script['stdout_path'], 'r').read())
        self.assertEquals(
            '%s\n' % script['stderr'], open(script['stderr_path'], 'r').read())
        self.assertEquals(
            '%s\n%s\n' % (script['stdout'], script['stderr']),
            open(script['combined_path'], 'r').read())

    def test_sudo_run_and_check(self):
        mock_popen = self.patch(maas_run_remote_scripts, 'Popen')
        self.patch(maas_run_remote_scripts, 'capture_script_output')
        cmd = factory.make_name('cmd')

        run_and_check([cmd], MagicMock(), False, True)

        self.assertThat(mock_popen, MockCalledOnceWith(
            ['sudo', '-En', cmd], stdin=DEVNULL, stdout=PIPE, stderr=PIPE))

    def test_install_dependencies_does_nothing_when_empty(self):
        self.assertTrue(install_dependencies(make_scripts()))
        self.assertThat(self.mock_output_and_send, MockNotCalled())

    def test_install_dependencies_apt(self):
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir, with_output=False)
        packages = [factory.make_name('apt_pkg') for _ in range(3)]
        for script in scripts:
            script['packages'] = {'apt': packages}

        self.assertTrue(install_dependencies(scripts))
        for script in scripts:
            self.assertThat(self.mock_output_and_send, MockAnyCall(
                'Installing apt packages for %s' % script['msg_name'],
                True, status='INSTALLING'))
            self.assertThat(mock_run_and_check, MockCalledOnceWith(
                ['apt-get', '-qy', 'install'] + packages, scripts, True, True))
            # Verify cleanup
            self.assertFalse(os.path.exists(script['combined_path']))
            self.assertFalse(os.path.exists(script['stdout_path']))
            self.assertFalse(os.path.exists(script['stderr_path']))

    def test_install_dependencies_apt_errors(self):
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        mock_run_and_check.return_value = False
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir, with_output=False)
        packages = [factory.make_name('apt_pkg') for _ in range(3)]
        for script in scripts:
            script['packages'] = {'apt': packages}

        self.assertFalse(install_dependencies(scripts))
        for script in scripts:
            self.assertThat(self.mock_output_and_send, MockAnyCall(
                'Installing apt packages for %s' % script['msg_name'],
                True, status='INSTALLING'))
            self.assertThat(mock_run_and_check, MockCalledOnceWith(
                ['apt-get', '-qy', 'install'] + packages, scripts, True, True))

    def test_install_dependencies_snap_str_list(self):
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir, with_output=False)
        packages = [factory.make_name('snap_pkg') for _ in range(3)]
        for script in scripts:
            script['packages'] = {'snap': packages}

        self.assertTrue(install_dependencies(scripts))
        for script in scripts:
            self.assertThat(self.mock_output_and_send, MockAnyCall(
                'Installing snap packages for %s' % script['msg_name'],
                True, status='INSTALLING'))
            # Verify cleanup
            self.assertFalse(os.path.exists(script['combined_path']))
            self.assertFalse(os.path.exists(script['stdout_path']))
            self.assertFalse(os.path.exists(script['stderr_path']))

        for package in packages:
            self.assertThat(mock_run_and_check, MockAnyCall(
                ['snap', 'install', package], scripts, True, True))

    def test_install_dependencies_snap_str_dict(self):
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir, with_output=False)
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
        for script in scripts:
            script['packages'] = {'snap': packages}

        self.assertTrue(install_dependencies(scripts))
        for script in scripts:
            self.assertThat(self.mock_output_and_send, MockAnyCall(
                'Installing snap packages for %s' % script['msg_name'],
                True, status='INSTALLING'))
            # Verify cleanup
            self.assertFalse(os.path.exists(script['combined_path']))
            self.assertFalse(os.path.exists(script['stdout_path']))
            self.assertFalse(os.path.exists(script['stderr_path']))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['snap', 'install', packages[0]['name']], scripts, True, True))
        self.assertThat(mock_run_and_check, MockAnyCall(
            [
                'snap', 'install', packages[1]['name'],
                '--%s' % packages[1]['channel']
            ],
            scripts, True, True))
        self.assertThat(mock_run_and_check, MockAnyCall(
            [
                'snap', 'install', packages[2]['name'],
                '--%s' % packages[2]['channel'],
                '--%smode' % packages[2]['mode'],
            ],
            scripts, True, True))
        self.assertThat(mock_run_and_check, MockAnyCall(
            [
                'snap', 'install', packages[3]['name'],
                '--%s' % packages[3]['channel'],
                '--%smode' % packages[3]['mode'],
            ],
            scripts, True, True))

    def test_install_dependencies_snap_errors(self):
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        mock_run_and_check.return_value = False
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir, with_output=False)
        packages = [factory.make_name('snap_pkg') for _ in range(3)]
        for script in scripts:
            script['packages'] = {'snap': packages}

        self.assertFalse(install_dependencies(scripts))
        for script in scripts:
            self.assertThat(self.mock_output_and_send, MockAnyCall(
                'Installing snap packages for %s' % script['msg_name'],
                True, status='INSTALLING'))

        self.assertThat(mock_run_and_check, MockAnyCall(
            ['snap', 'install', packages[0]], scripts, True, True))

    def test_install_dependencies_url(self):
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir)
        packages = [factory.make_name('url') for _ in range(3)]
        for script in scripts:
            script['packages'] = {'url': packages}

        self.assertTrue(install_dependencies(scripts))
        for package in packages:
            self.assertThat(mock_run_and_check, MockAnyCall(
                ['wget', package, '-P', scripts[0]['download_path']],
                scripts, True))
        for script in scripts:
            self.assertThat(self.mock_output_and_send, MockAnyCall(
                'Downloading and extracting URLs for %s' % script['msg_name'],
                True, status='INSTALLING'))
        # Verify cleanup
        self.assertFalse(os.path.exists(scripts[0]['combined_path']))
        self.assertFalse(os.path.exists(scripts[0]['stdout_path']))
        self.assertFalse(os.path.exists(scripts[0]['stderr_path']))

    def test_install_dependencies_url_errors(self):
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        mock_run_and_check.return_value = False
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir)
        packages = [factory.make_name('url') for _ in range(3)]
        for script in scripts:
            script['packages'] = {'url': packages}

        self.assertFalse(install_dependencies(scripts))
        for script in scripts:
            self.assertThat(self.mock_output_and_send, MockAnyCall(
                'Downloading and extracting URLs for %s' % script['msg_name'],
                True, status='INSTALLING'))

    def test_install_dependencies_url_tar(self):
        self.patch(maas_run_remote_scripts, 'run_and_check')
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir, with_output=False)
        tar_file = os.path.join(scripts[0]['download_path'], 'file.tar.xz')
        file_content = factory.make_bytes()
        with tarfile.open(tar_file, 'w:xz') as tar:
            tarinfo = tarfile.TarInfo(name='test-file')
            tarinfo.size = len(file_content)
            tarinfo.mode = 0o755
            tar.addfile(tarinfo, BytesIO(file_content))
        with open(scripts[0]['combined_path'], 'w') as output:
            output.write("Saving to: '%s'" % tar_file)
        for script in scripts:
            script['packages'] = {'url': [tar_file]}

        self.assertTrue(install_dependencies(scripts))
        with open(
                os.path.join(scripts[0]['download_path'], 'test-file'),
                'rb') as f:
            self.assertEquals(file_content, f.read())

    def test_install_dependencies_url_zip(self):
        self.patch(maas_run_remote_scripts, 'run_and_check')
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir, with_output=False)
        zip_file = os.path.join(scripts[0]['download_path'], 'file.zip')
        file_content = factory.make_bytes()
        with ZipFile(zip_file, 'w') as z:
            z.writestr('test-file', file_content)
        with open(scripts[0]['combined_path'], 'w') as output:
            output.write("Saving to: '%s'" % zip_file)
        for script in scripts:
            script['packages'] = {'url': [zip_file]}

        self.assertTrue(install_dependencies(scripts))
        with open(
                os.path.join(scripts[0]['download_path'], 'test-file'),
                'rb') as f:
            self.assertEquals(file_content, f.read())

    def test_install_dependencies_url_deb(self):
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir, with_output=False)
        deb_file = os.path.join(scripts[0]['download_path'], 'file.deb')
        open(deb_file, 'w').close()
        with open(scripts[0]['combined_path'], 'w') as output:
            output.write("Saving to: '%s'" % deb_file)
        for script in scripts:
            script['packages'] = {'url': [deb_file]}

        self.assertTrue(install_dependencies(scripts))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['dpkg', '-i', deb_file], scripts, False, True))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['apt-get', 'install', '-qyf'], scripts, True, True))

    def test_install_dependencies_url_deb_errors(self):
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        mock_run_and_check.side_effect = (True, True, False)
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir, with_output=False)
        deb_file = os.path.join(scripts[0]['download_path'], 'file.deb')
        open(deb_file, 'w').close()
        with open(scripts[0]['combined_path'], 'w') as output:
            output.write("Saving to: '%s'" % deb_file)
        for script in scripts:
            script['packages'] = {'url': [deb_file]}

        self.assertFalse(install_dependencies(scripts))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['dpkg', '-i', deb_file], scripts, False, True))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['apt-get', 'install', '-qyf'], scripts, True, True))

    def test_install_dependencies_url_snap(self):
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir, with_output=False)
        snap_file = os.path.join(scripts[0]['download_path'], 'file.snap')
        open(snap_file, 'w').close()
        with open(scripts[0]['combined_path'], 'w') as output:
            output.write("Saving to: '%s'" % snap_file)
        for script in scripts:
            script['packages'] = {'url': [snap_file]}

        self.assertTrue(install_dependencies(scripts))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['snap', snap_file], scripts, True, True))

    def test_install_dependencies_url_snap_errors(self):
        mock_run_and_check = self.patch(
            maas_run_remote_scripts, 'run_and_check')
        mock_run_and_check.side_effect = (True, False)
        scripts_dir = self.useFixture(TempDirectory()).path
        scripts = make_scripts(scripts_dir=scripts_dir, with_output=False)
        snap_file = os.path.join(scripts[0]['download_path'], 'file.snap')
        open(snap_file, 'w').close()
        with open(scripts[0]['combined_path'], 'w') as output:
            output.write("Saving to: '%s'" % snap_file)
        for script in scripts:
            script['packages'] = {'url': [snap_file]}

        self.assertFalse(install_dependencies(scripts))
        self.assertThat(mock_run_and_check, MockAnyCall(
            ['snap', snap_file], scripts, True, True))


class TestParseParameters(MAASTestCase):

    def test_get_block_devices(self):
        expected_blockdevs = [
            {
                'NAME': factory.make_name('NAME'),
                'MODEL': factory.make_name('MODEL'),
                'SERIAL': factory.make_name('SERIAL'),
            } for _ in range(3)
        ]
        mock_check_output = self.patch(maas_run_remote_scripts, 'check_output')
        mock_check_output.return_value = ''.join([
            'NAME="{NAME}" MODEL="{MODEL}" SERIAL="{SERIAL}"\n'.format(
                **blockdev) for blockdev in expected_blockdevs]).encode()
        maas_run_remote_scripts._block_devices = None

        self.assertItemsEqual(expected_blockdevs, get_block_devices())

    def test_get_block_devices_cached(self):
        block_devices = factory.make_name('block_devices')
        mock_check_output = self.patch(maas_run_remote_scripts, 'check_output')
        maas_run_remote_scripts._block_devices = block_devices

        self.assertItemsEqual(block_devices, get_block_devices())
        self.assertThat(mock_check_output, MockNotCalled())

    def test_parse_parameters(self):
        scripts_dir = factory.make_name('scripts_dir')
        script = {
            'path': os.path.join('path_to', factory.make_name('script_name')),
            'parameters': {
                'runtime': {
                    'type': 'runtime',
                    'value': random.randint(0, 1000),
                },
                'storage_virtio': {
                    'type': 'storage',
                    'value': {
                        'name': factory.make_name('name'),
                        'model': '',
                        'serial': '',
                        'id_path': '/dev/%s' % factory.make_name('id_path'),
                    },
                },
                'storage': {
                    'type': 'storage',
                    'value': {
                        'name': factory.make_name('name'),
                        'model': factory.make_name('model'),
                        'serial': factory.make_name('serial'),
                        'id_path': '/dev/%s' % factory.make_name('id_path'),
                    },
                },
            },
        }
        mock_check_output = self.patch(maas_run_remote_scripts, 'check_output')
        mock_check_output.return_value = ''.join([
            'NAME="{name}" MODEL="{model}" SERIAL="{serial}"\n'.format(
                **param['value'])
            for param_name, param in script['parameters'].items()
            if 'storage' in param_name]).encode()
        maas_run_remote_scripts._block_devices = None

        self.assertItemsEqual(
            [
                os.path.join(scripts_dir, script['path']),
                '--runtime=%s' % script['parameters']['runtime']['value'],
                '--storage=%s' % script['parameters']['storage_virtio'][
                    'value']['id_path'],
                '--storage=/dev/%s' % script['parameters']['storage']['value'][
                    'name'],
            ], parse_parameters(script, scripts_dir))

    def test_parse_parameters_argument_format(self):
        scripts_dir = factory.make_name('scripts_dir')
        script = {
            'path': os.path.join('path_to', factory.make_name('script_name')),
            'parameters': {
                'runtime': {
                    'type': 'runtime',
                    'value': random.randint(0, 1000),
                    'argument_format': '--foo --timeout {input}',
                },
                'storage': {
                    'type': 'storage',
                    'value': {
                        'name': factory.make_name('name'),
                        'model': factory.make_name('model'),
                        'serial': factory.make_name('serial'),
                        'id_path': '/dev/%s' % factory.make_name('id_path'),
                    },
                    'argument_format': (
                        '--bar {name} {model} {serial} {path} {input}'),
                },
            },
        }
        mock_check_output = self.patch(maas_run_remote_scripts, 'check_output')
        mock_check_output.return_value = ''.join([
            'NAME="{name}" MODEL="{model}" SERIAL="{serial}"\n'.format(
                **param['value'])
            for param_name, param in script['parameters'].items()
            if 'storage' in param_name]).encode()
        maas_run_remote_scripts._block_devices = None

        self.assertItemsEqual(
            [
                os.path.join(scripts_dir, script['path']),
                '--foo', '--timeout',
                str(script['parameters']['runtime']['value']),
                '--bar', script['parameters']['storage']['value']['name'],
                script['parameters']['storage']['value']['model'],
                script['parameters']['storage']['value']['serial'],
                '/dev/%s' % script['parameters']['storage']['value']['name'],
                '/dev/%s' % script['parameters']['storage']['value']['name'],
            ], parse_parameters(script, scripts_dir))


class TestRunScript(MAASTestCase):

    def setUp(self):
        super().setUp()
        self.mock_output_and_send = self.patch(
            maas_run_remote_scripts, 'output_and_send')
        self.mock_capture_script_output = self.patch(
            maas_run_remote_scripts, 'capture_script_output')
        self.args = {
            'status': 'WORKING',
            'send_result': True,
        }
        self.patch(maas_run_remote_scripts.sys.stdout, 'write')

    def test_run_script(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        script = make_script(scripts_dir=scripts_dir)

        run_script(script, scripts_dir)

        self.assertThat(self.mock_output_and_send, MockCallsMatch(
            call('Starting %s' % script['msg_name'], **self.args),
            call(
                'Finished %s: None' % script['msg_name'], exit_status=None,
                files={
                    script['combined_name']: script['combined'].encode(),
                    script['stdout_name']: script['stdout'].encode(),
                    script['stderr_name']: script['stderr'].encode(),
                    script['result_name']: script['result'].encode(),
                }, **self.args),
        ))
        self.assertThat(self.mock_capture_script_output, MockCalledOnceWith(
            ANY, script['combined_path'], script['stdout_path'],
            script['stderr_path'], script['timeout_seconds']))

    def test_run_script_sets_env(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        script = make_script(scripts_dir=scripts_dir)
        mock_popen = self.patch(maas_run_remote_scripts, 'Popen')

        run_script(script, scripts_dir)

        env = mock_popen.call_args[1]['env']
        self.assertEquals(script['combined_path'], env['OUTPUT_COMBINED_PATH'])
        self.assertEquals(script['stdout_path'], env['OUTPUT_STDOUT_PATH'])
        self.assertEquals(script['stderr_path'], env['OUTPUT_STDERR_PATH'])
        self.assertEquals(script['result_path'], env['RESULT_PATH'])
        self.assertEquals(script['download_path'], env['DOWNLOAD_PATH'])
        self.assertEquals(str(script['timeout_seconds']), env['RUNTIME'])
        self.assertEquals(str(script['has_started']), env['HAS_STARTED'])
        self.assertIn('PATH', env)

    def test_run_script_only_sends_result_when_avail(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        script = make_script(scripts_dir=scripts_dir)
        os.remove(script['result_path'])

        run_script(script, scripts_dir)

        self.assertThat(self.mock_output_and_send, MockCallsMatch(
            call('Starting %s' % script['msg_name'], **self.args),
            call(
                'Finished %s: None' % script['msg_name'], exit_status=None,
                files={
                    script['combined_name']: script['combined'].encode(),
                    script['stdout_name']: script['stdout'].encode(),
                    script['stderr_name']: script['stderr'].encode(),
                }, **self.args),
        ))
        self.assertThat(self.mock_capture_script_output, MockCalledOnceWith(
            ANY, script['combined_path'], script['stdout_path'],
            script['stderr_path'], script['timeout_seconds']))

    def test_run_script_uses_timeout_from_parameter(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        script = make_script(scripts_dir=scripts_dir)
        script['parameters'] = {
            'runtime': {
                'type': 'runtime',
                'value': random.randint(0, 1000),
            }
        }

        run_script(script, scripts_dir)

        self.assertThat(self.mock_output_and_send, MockCallsMatch(
            call('Starting %s' % script['msg_name'], **self.args),
            call(
                'Finished %s: None' % script['msg_name'], exit_status=None,
                files={
                    script['combined_name']: script['combined'].encode(),
                    script['stdout_name']: script['stdout'].encode(),
                    script['stderr_name']: script['stderr'].encode(),
                    script['result_name']: script['result'].encode(),
                }, **self.args),
        ))
        self.assertThat(self.mock_capture_script_output, MockCalledOnceWith(
            ANY, script['combined_path'], script['stdout_path'],
            script['stderr_path'], script['parameters']['runtime']['value']))

    def test_run_script_errors_with_bad_param(self):
        fake_block_devices = [{
            'MODEL': factory.make_name('model'),
            'SERIAL': factory.make_name('serial'),
            } for _ in range(3)
        ]
        mock_get_block_devices = self.patch(
            maas_run_remote_scripts, 'get_block_devices')
        mock_get_block_devices.return_value = fake_block_devices
        testing_block_device_model = factory.make_name('model')
        testing_block_device_serial = factory.make_name('serial')
        scripts_dir = self.useFixture(TempDirectory()).path
        script = make_script(scripts_dir=scripts_dir)
        script['parameters'] = {'storage': {
            'type': 'storage',
            'argument_format': '{bad}',
            'value': {
                'model': testing_block_device_model,
                'serial': testing_block_device_serial,
            },
        }}

        self.assertFalse(run_script(script, scripts_dir))

        expected_output = (
            "Unable to run '%s': Storage device '%s' with serial '%s' not "
            'found!\n\n'
            "This indicates the storage device has been removed or "
            "the OS is unable to find it due to a hardware failure. "
            "Please re-commission this node to re-discover the "
            "storage devices, or delete this device manually.\n\n"
            'Given parameters:\n%s\n\n'
            'Discovered storage devices:\n%s\n' % (
                script['name'],
                testing_block_device_model, testing_block_device_serial,
                str(script['parameters']), str(fake_block_devices))
        )
        expected_output = expected_output.encode()
        self.assertThat(self.mock_output_and_send, MockCallsMatch(
            call('Starting %s' % script['msg_name'], **self.args),
            call(
                'Failed to execute %s: 2' % script['msg_name'], exit_status=2,
                files={
                    script['combined_name']: expected_output,
                    script['stderr_name']: expected_output,
                }, **self.args),
        ))

    def test_run_script_errors_bad_params_on_unexecutable_script(self):
        # Regression test for LP:1669246
        scripts_dir = self.useFixture(TempDirectory()).path
        script = make_script(scripts_dir=scripts_dir)
        self.mock_capture_script_output.side_effect = OSError(
            8, 'Exec format error')

        self.assertFalse(run_script(script, scripts_dir))

        self.assertThat(self.mock_output_and_send, MockCallsMatch(
            call('Starting %s' % script['msg_name'], **self.args),
            call(
                'Failed to execute %s: 8' % script['msg_name'], exit_status=8,
                files={
                    script['combined_name']: b'[Errno 8] Exec format error',
                    script['stderr_name']: b'[Errno 8] Exec format error',
                }, **self.args),
        ))

    def test_run_script_errors_bad_params_on_unexecutable_script_no_errno(
            self):
        # Regression test for LP:1669246
        scripts_dir = self.useFixture(TempDirectory()).path
        script = make_script(scripts_dir=scripts_dir)
        self.mock_capture_script_output.side_effect = OSError()

        self.assertFalse(run_script(script, scripts_dir))

        self.assertThat(self.mock_output_and_send, MockCallsMatch(
            call('Starting %s' % script['msg_name'], **self.args),
            call(
                'Failed to execute %s: 2' % script['msg_name'], exit_status=2,
                files={
                    script['combined_name']: b'Unable to execute script',
                    script['stderr_name']: b'Unable to execute script',
                }, **self.args),
        ))

    def test_run_script_errors_bad_params_on_unexecutable_script_baderrno(
            self):
        # Regression test for LP:1669246
        scripts_dir = self.useFixture(TempDirectory()).path
        script = make_script(scripts_dir=scripts_dir)
        self.mock_capture_script_output.side_effect = OSError(
            0, 'Exec format error')

        self.assertFalse(run_script(script, scripts_dir))

        self.assertThat(self.mock_output_and_send, MockCallsMatch(
            call('Starting %s' % script['msg_name'], **self.args),
            call(
                'Failed to execute %s: 2' % script['msg_name'], exit_status=2,
                files={
                    script['combined_name']: b'[Errno 0] Exec format error',
                    script['stderr_name']: b'[Errno 0] Exec format error',
                }, **self.args),
        ))

    def test_run_script_timed_out_script(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        script = make_script(scripts_dir=scripts_dir)
        self.mock_capture_script_output.side_effect = TimeoutExpired(
            [factory.make_name('arg') for _ in range(3)],
            script['timeout_seconds'])
        self.args.pop('status')

        self.assertFalse(run_script(script, scripts_dir))

        self.assertThat(self.mock_output_and_send, MockCallsMatch(
            call(
                'Starting %s' % script['msg_name'], status='WORKING',
                **self.args),
            call(
                'Timeout(%s) expired on %s' % (
                    str(timedelta(seconds=script['timeout_seconds'])),
                    script['msg_name']),
                files={
                    script['combined_name']: script['combined'].encode(),
                    script['stdout_name']: script['stdout'].encode(),
                    script['stderr_name']: script['stderr'].encode(),
                    script['result_name']: script['result'].encode(),
                }, status='TIMEDOUT', **self.args),
        ))


class TestRunScripts(MAASTestCase):

    def test_run_scripts(self):
        mock_install_deps = self.patch(
            maas_run_remote_scripts, 'install_dependencies')
        mock_run_script = self.patch(maas_run_remote_scripts, 'run_script')
        single_thread = make_scripts(instance=False, parallel=0)
        instance_thread = [
            make_scripts(parallel=1)
            for _ in range(3)
        ]
        any_thread = make_scripts(instance=False, parallel=2)
        scripts = copy.deepcopy(single_thread)
        for instance_thread_group in instance_thread:
            scripts += copy.deepcopy(instance_thread_group)
        scripts += copy.deepcopy(any_thread)
        url = factory.make_url()
        creds = factory.make_name('creds')
        scripts_dir = factory.make_name('scripts_dir')
        out_dir = os.path.join(scripts_dir, 'out')

        run_scripts(url, creds, scripts_dir, out_dir, scripts)

        self.assertEquals(
            len(single_thread) + len(instance_thread) + len(any_thread),
            mock_install_deps.call_count)

        expected_calls = [
            call(script=script, scripts_dir=scripts_dir, send_result=True)
            for script in sorted(scripts, key=lambda i: (
                99 if i['hardware_type'] == 0 else i['hardware_type'],
                i['name']))
            if script['parallel'] != 2
        ]
        expected_calls += [
            call(script=script, scripts_dir=scripts_dir, send_result=True)
            for script in sorted(scripts, key=lambda i: (
                len(i.get('packages', {}).keys()), i['name']))
            if script['parallel'] == 2
        ]
        self.assertThat(mock_run_script, MockCallsMatch(*expected_calls))

    def test_run_scripts_adds_data(self):
        scripts_dir = factory.make_name('scripts_dir')
        out_dir = os.path.join(scripts_dir, 'out')
        self.patch(maas_run_remote_scripts, 'install_dependencies')
        self.patch(maas_run_remote_scripts, 'run_script')
        url = factory.make_url()
        creds = factory.make_name('creds')
        script = make_script(scripts_dir=scripts_dir)
        script.pop('result', None)
        script.pop('combined', None)
        script.pop('stderr', None)
        script.pop('stdout', None)
        script['args'] = {
            'url': url,
            'creds': creds,
            'script_result_id': script['script_result_id'],
            'script_version_id': script['script_version_id'],
        }
        scripts = [{
            'name': script['name'],
            'path': script['path'],
            'script_result_id': script['script_result_id'],
            'script_version_id': script['script_version_id'],
            'timeout_seconds': script['timeout_seconds'],
            'parallel': script['parallel'],
            'hardware_type': script['hardware_type'],
            'has_started': script['has_started'],
        }]
        run_scripts(url, creds, scripts_dir, out_dir, scripts)
        scripts[0].pop('thread', None)
        self.assertDictEqual(script, scripts[0])


class TestRunScriptsFromMetadata(MAASTestCase):

    def setUp(self):
        super().setUp()
        self.mock_output_and_send = self.patch(
            maas_run_remote_scripts, 'output_and_send')
        self.mock_signal = self.patch(maas_run_remote_scripts, 'signal')
        self.mock_run_scripts = self.patch(
            maas_run_remote_scripts, 'run_scripts')
        self.patch(maas_run_remote_scripts.sys.stdout, 'write')

    def make_index_json(
            self, scripts_dir, with_commissioning=True, with_testing=True,
            commissioning_scripts=None, testing_scripts=None):
        index_json = {}
        if with_commissioning:
            if commissioning_scripts is None:
                index_json['commissioning_scripts'] = make_scripts()
            else:
                index_json['commissioning_scripts'] = commissioning_scripts
        if with_testing:
            if testing_scripts is None:
                index_json['testing_scripts'] = make_scripts()
            else:
                index_json['testing_scripts'] = testing_scripts
        with open(os.path.join(scripts_dir, 'index.json'), 'w') as f:
            f.write(json.dumps({'1.0': index_json}))
        return index_json

    def mock_download_and_extract_tar(self, url, creds, scripts_dir):
        """Simulate redownloading a scripts tarball after finishing commiss."""
        index_path = os.path.join(scripts_dir, 'index.json')
        with open(index_path, 'r') as f:
            index_json = json.loads(f.read())
        index_json['1.0'].pop('commissioning_scripts', None)
        os.remove(index_path)
        with open(index_path, 'w') as f:
            f.write(json.dumps(index_json))
        return True

    def test_run_scripts_from_metadata(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        self.mock_run_scripts.return_value = 0
        index_json = self.make_index_json(scripts_dir)
        mock_download_and_extract_tar = self.patch(
            maas_run_remote_scripts, 'download_and_extract_tar')
        mock_download_and_extract_tar.side_effect = (
            self.mock_download_and_extract_tar)

        # Don't need to give the url, creds, or out_dir as we're not running
        # the scripts and sending the results.
        run_scripts_from_metadata(None, None, scripts_dir, None)

        self.assertThat(
            self.mock_run_scripts,
            MockAnyCall(
                None, None, scripts_dir, None,
                index_json['commissioning_scripts'], True))
        self.assertThat(
            self.mock_run_scripts,
            MockAnyCall(
                None, None, scripts_dir, None,
                index_json['testing_scripts'], True))
        self.assertThat(self.mock_signal, MockAnyCall(None, None, 'TESTING'))
        self.assertThat(mock_download_and_extract_tar, MockCalledOnceWith(
            'None/maas-scripts/', None, scripts_dir))

    def test_run_scripts_from_metadata_doesnt_run_tests_on_commiss_fail(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        fail_count = random.randint(1, 100)
        self.mock_run_scripts.return_value = fail_count
        index_json = self.make_index_json(scripts_dir)

        # Don't need to give the url, creds, or out_dir as we're not running
        # the scripts and sending the results.
        run_scripts_from_metadata(None, None, scripts_dir, None)

        self.assertThat(
            self.mock_run_scripts,
            MockCalledOnceWith(
                None, None, scripts_dir, None,
                index_json['commissioning_scripts'], True))
        self.assertThat(self.mock_signal, MockNotCalled())
        self.assertThat(self.mock_output_and_send, MockCalledOnceWith(
            '%s commissioning scripts failed to run' % fail_count, True, None,
            None, 'FAILED'))

    def test_run_scripts_from_metadata_redownloads_after_commiss(self):
        scripts_dir = self.useFixture(TempDirectory()).path
        self.mock_run_scripts.return_value = 0
        testing_scripts = make_scripts()
        testing_scripts[0]['parameters'] = {'storage': {'type': 'storage'}}
        mock_download_and_extract_tar = self.patch(
            maas_run_remote_scripts, 'download_and_extract_tar')
        simple_dl_and_extract = lambda *args, **kwargs: self.make_index_json(
            scripts_dir, with_commissioning=False,
            testing_scripts=testing_scripts)
        mock_download_and_extract_tar.side_effect = simple_dl_and_extract
        index_json = self.make_index_json(
            scripts_dir, testing_scripts=testing_scripts)

        # Don't need to give the url, creds, or out_dir as we're not running
        # the scripts and sending the results.
        run_scripts_from_metadata(None, None, scripts_dir, None)

        self.assertThat(
            self.mock_run_scripts,
            MockAnyCall(
                None, None, scripts_dir, None,
                index_json['commissioning_scripts'], True))
        self.assertThat(self.mock_signal, MockAnyCall(None, None, 'TESTING'))
        self.assertThat(
            mock_download_and_extract_tar,
            MockCalledOnceWith('None/maas-scripts/', None, scripts_dir))
        self.assertThat(
            self.mock_run_scripts,
            MockAnyCall(
                None, None, scripts_dir, None,
                index_json['testing_scripts'], True))


class TestMaasRunRemoteScripts(MAASTestCase):

    def test_download_and_extract_tar(self):
        self.patch(maas_run_remote_scripts.sys.stdout, 'write')
        scripts_dir = self.useFixture(TempDirectory()).path
        binary = BytesIO()
        file_content = factory.make_bytes()
        with tarfile.open(mode='w', fileobj=binary) as tar:
            tarinfo = tarfile.TarInfo(name='test-file')
            tarinfo.size = len(file_content)
            tarinfo.mode = 0o755
            tar.addfile(tarinfo, BytesIO(file_content))
        mock_geturl = self.patch(maas_run_remote_scripts, 'geturl')
        mm = MagicMock()
        mm.status = 200
        mm.read.return_value = binary.getvalue()
        mock_geturl.return_value = mm

        # geturl is mocked out so we don't need to give a url or creds.
        self.assertTrue(download_and_extract_tar(None, None, scripts_dir))

        written_file_content = open(
            os.path.join(scripts_dir, 'test-file'), 'rb').read()
        self.assertEquals(file_content, written_file_content)

    def test_download_and_extract_tar_returns_false_on_no_content(self):
        self.patch(maas_run_remote_scripts.sys.stdout, 'write')
        scripts_dir = self.useFixture(TempDirectory()).path
        mock_geturl = self.patch(maas_run_remote_scripts, 'geturl')
        mm = MagicMock()
        mm.status = int(http.client.NO_CONTENT)
        mm.read.return_value = b'No content'
        mock_geturl.return_value = mm

        # geturl is mocked out so we don't need to give a url or creds.
        self.assertFalse(download_and_extract_tar(None, None, scripts_dir))

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

    def test_main_signals_success(self):
        self.patch(
            maas_run_remote_scripts.argparse.ArgumentParser,
            'parse_args')
        self.patch(maas_run_remote_scripts, 'read_config')
        self.patch(maas_run_remote_scripts, 'os')
        self.patch(maas_run_remote_scripts, 'open')
        self.patch(
            maas_run_remote_scripts,
            'download_and_extract_tar').return_value = True
        self.patch(
            maas_run_remote_scripts,
            'run_scripts_from_metadata').return_value = 0
        self.patch(maas_run_remote_scripts, 'signal')
        mock_output_and_send = self.patch(
            maas_run_remote_scripts, 'output_and_send')

        maas_run_remote_scripts.main()

        self.assertThat(mock_output_and_send, MockCalledOnceWith(
            'All scripts successfully ran', ANY, ANY, ANY, 'OK'))

    def test_main_signals_failure(self):
        failures = random.randint(1, 100)
        self.patch(
            maas_run_remote_scripts.argparse.ArgumentParser,
            'parse_args')
        self.patch(maas_run_remote_scripts, 'read_config')
        self.patch(maas_run_remote_scripts, 'os')
        self.patch(maas_run_remote_scripts, 'open')
        self.patch(
            maas_run_remote_scripts,
            'download_and_extract_tar').return_value = True
        self.patch(
            maas_run_remote_scripts,
            'run_scripts_from_metadata').return_value = failures
        self.patch(maas_run_remote_scripts, 'signal')
        mock_output_and_send = self.patch(
            maas_run_remote_scripts, 'output_and_send')

        maas_run_remote_scripts.main()

        self.assertThat(mock_output_and_send, MockCalledOnceWith(
            '%d test scripts failed to run' % failures, ANY, ANY, ANY,
            'FAILED'))
