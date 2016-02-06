# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test refresh functions."""

__all__ = []

from collections import OrderedDict
import os
import random
import re
from textwrap import dedent

from maastesting.factory import factory
from maastesting.matchers import (
    MockAnyCall,
    MockCalledWith,
)
from maastesting.testcase import MAASTestCase
from provisioningserver import refresh
from provisioningserver.testing.config import ClusterConfigurationFixture


class TestHelpers(MAASTestCase):
    def test_get_architecture_returns_arch(self):
        architecture = refresh.get_architecture()
        self.assertIsInstance(architecture, str)
        self.assertIsNot('', architecture)

    def test_get_swap_size_proc_meminfo_exists(self):
        # This is a canary incase /proc/meminfo ever goes away
        self.assertTrue(os.path.exists('/proc/meminfo'))
        # Test that /proc/meminfo still provides SwapTotal
        regex = re.compile('^SwapTotal:\s+[0-9]+ kB\n$')
        with open('/proc/meminfo') as f:
            for line in f:
                result = regex.match(line)
                if result is not None:
                    return
        self.assertTrue(False, '/proc/meminfo does not contain SwapTotal')

    def test_get_os_release_etc_os_release_exists(self):
        # This is a canary incase /etc/os-release ever goes away
        self.assertTrue(os.path.exists('/etc/os-release'))
        os_release = refresh.get_os_release()
        # refresh() in src/provisioningserver/rpc/clusterservice.py tries 'ID'
        # first and falls back on 'NAME' if its not found. Both exist in
        # Ubuntu 16.04 (Xenial).
        self.assertIn('ID', os_release)
        self.assertIn('NAME', os_release)
        # refresh() in src/provisioningserver/rpc/clusterservice.py tries
        # 'UBUNTU_CODENAME' first and falls back on 'VERSION_ID' if its not
        # found. Both exist in Ubuntu 16.04 (Xenial).
        self.assertIn('UBUNTU_CODENAME', os_release)
        self.assertIn('VERSION_ID', os_release)


class TestSignal(MAASTestCase):
    def test_signal_formats_params(self):
        encode_multipart_data = self.patch(refresh, 'encode_multipart_data')
        encode_multipart_data.return_value = None, None
        self.patch(refresh, 'geturl')

        status = factory.make_name('status')
        message = factory.make_name('message')

        refresh.signal(None, None, status, message)
        self.assertThat(
            encode_multipart_data,
            MockCalledWith({
                b'op': b'signal',
                b'status': status.encode('utf-8'),
                b'error': message.encode('utf-8'),
            }, {}))

    def test_signal_formats_params_with_script_result(self):
        encode_multipart_data = self.patch(refresh, 'encode_multipart_data')
        encode_multipart_data.return_value = None, None
        self.patch(refresh, 'geturl')

        status = factory.make_name('status')
        message = factory.make_name('message')
        script_result = factory.make_name('script_result')

        refresh.signal(None, None, status, message, {}, script_result)
        self.assertThat(
            encode_multipart_data,
            MockCalledWith({
                b'op': b'signal',
                b'status': status.encode('utf-8'),
                b'error': message.encode('utf-8'),
                b'script_result': script_result.encode('utf-8'),
            }, {}))

    def test_signal_formats_params_with_ints(self):
        encode_multipart_data = self.patch(refresh, 'encode_multipart_data')
        encode_multipart_data.return_value = None, None
        self.patch(refresh, 'geturl')

        status = random.randint(1, 100)
        message = factory.make_name('message')
        script_result = random.randint(1, 100)

        refresh.signal(None, None, status, message, {}, script_result)
        self.assertThat(
            encode_multipart_data,
            MockCalledWith({
                b'op': b'signal',
                b'status': str(status).encode('utf-8'),
                b'error': message.encode('utf-8'),
                b'script_result': str(script_result).encode('utf-8'),
            }, {}))

    def test_not_ok_result_is_logged(self):
        encode_multipart_data = self.patch(refresh, 'encode_multipart_data')
        encode_multipart_data.return_value = None, None
        result = factory.make_name('result')
        self.patch(refresh, 'geturl').return_value = result
        self.patch(refresh, 'maaslog')

        status = factory.make_name('status')
        message = factory.make_name('message')

        refresh.signal(None, None, status, message)

        self.assertThat(
            refresh.maaslog.error,
            MockAnyCall(
                "Unexpected result sending region commissioning data: %s" %
                result))

    def test_exception_is_logged(self):
        encode_multipart_data = self.patch(refresh, 'encode_multipart_data')
        encode_multipart_data.return_value = None, None
        error_message = factory.make_name('error_message')
        self.patch(refresh, 'geturl').side_effect = Exception(error_message)
        self.patch(refresh, 'maaslog')

        status = factory.make_name('status')
        message = factory.make_name('message')

        refresh.signal(None, None, status, message)

        self.assertThat(
            refresh.maaslog.error,
            MockAnyCall(
                "unexpected error [%s]" % error_message))


class TestRefresh(MAASTestCase):
    def patch_scripts_success(self):
        TEST_SCRIPT = dedent("""\
            #!/bin/sh
            echo 'test script'
            """)
        refresh.NODE_INFO_SCRIPTS = OrderedDict([
            ('test_script.out', {
                'content': TEST_SCRIPT.encode('ascii'),
                'name': 'test_script',
            })
        ])

    def patch_scripts_failure(self):
        TEST_SCRIPT = dedent("""\
            #!/bin/sh
            echo 'test failed'
            exit 1
            """)
        refresh.NODE_INFO_SCRIPTS = OrderedDict([
            ('test_script.out', {
                'content': TEST_SCRIPT.encode('ascii'),
                'name': 'test_script',
            })
        ])

    def test_refresh_signals_starting(self):
        signal = self.patch(refresh, 'signal')
        self.patch_scripts_success()

        system_id = factory.make_name('system_id')
        consumer_key = factory.make_name('consumer_key')
        token_key = factory.make_name('token_key')
        token_secret = factory.make_name('token_secret')

        refresh.refresh(system_id, consumer_key, token_key, token_secret)
        self.assertItemsEqual([
            "http://localhost:5240/MAAS/metadata/status/%s/latest" % system_id,
            {
                'consumer_secret': '',
                'consumer_key': consumer_key,
                'token_key': token_key,
                'token_secret': token_secret,
            },
            'WORKING',
            'Starting test_script [1/1]'],
            signal.call_args_list[0][0])

    def test_refresh_signals_results(self):
        signal = self.patch(refresh, 'signal')
        self.patch_scripts_success()

        system_id = factory.make_name('system_id')
        consumer_key = factory.make_name('consumer_key')
        token_key = factory.make_name('token_key')
        token_secret = factory.make_name('token_secret')

        refresh.refresh(system_id, consumer_key, token_key, token_secret)
        self.assertItemsEqual([
            "http://localhost:5240/MAAS/metadata/status/%s/latest" % system_id,
            {
                'consumer_secret': '',
                'consumer_key': consumer_key,
                'token_key': token_key,
                'token_secret': token_secret,
            },
            'WORKING',
            'Finished test_script [1/1]: 0',
            {
                'test_script.out': b'test script\n',
                'test_script.err': b'',
            },
            0],
            signal.call_args_list[1][0])

    def test_refresh_signals_finished(self):
        signal = self.patch(refresh, 'signal')
        self.patch_scripts_success()

        system_id = factory.make_name('system_id')
        consumer_key = factory.make_name('consumer_key')
        token_key = factory.make_name('token_key')
        token_secret = factory.make_name('token_secret')

        refresh.refresh(system_id, consumer_key, token_key, token_secret)
        self.assertItemsEqual([
            "http://localhost:5240/MAAS/metadata/status/%s/latest" % system_id,
            {
                'consumer_secret': '',
                'consumer_key': consumer_key,
                'token_key': token_key,
                'token_secret': token_secret,
            },
            'OK',
            "Finished refreshing %s" % system_id],
            signal.call_args_list[2][0])

    def test_refresh_signals_nodegroup_to_rack(self):
        signal = self.patch(refresh, 'signal')
        self.patch_scripts_success()
        cluster_uuid = factory.make_UUID()
        self.useFixture(ClusterConfigurationFixture(cluster_uuid=cluster_uuid))

        system_id = factory.make_name('system_id')
        consumer_key = factory.make_name('consumer_key')
        token_key = factory.make_name('token_key')
        token_secret = factory.make_name('token_secret')

        refresh.refresh(system_id, consumer_key, token_key, token_secret)
        self.assertItemsEqual([
            "http://localhost:5240/MAAS/metadata/status/%s/latest" % system_id,
            {
                'consumer_secret': '',
                'consumer_key': consumer_key,
                'token_key': token_key,
                'token_secret': token_secret,
            },
            'OK',
            "Finished refreshing %s" % system_id],
            signal.call_args_list[2][0])
        self.assertItemsEqual(
            {'extra_headers': {'X-NodeGroup-UUID': cluster_uuid}},
            signal.call_args_list[2][1]
        )

    def test_refresh_signals_failure(self):
        signal = self.patch(refresh, 'signal')
        self.patch_scripts_failure()

        system_id = factory.make_name('system_id')
        consumer_key = factory.make_name('consumer_key')
        token_key = factory.make_name('token_key')
        token_secret = factory.make_name('token_secret')

        refresh.refresh(system_id, consumer_key, token_key, token_secret)
        self.assertItemsEqual([
            "http://localhost:5240/MAAS/metadata/status/%s/latest" % system_id,
            {
                'consumer_secret': '',
                'consumer_key': consumer_key,
                'token_key': token_key,
                'token_secret': token_secret,
            },
            'FAILED',
            "Failed refreshing %s" % system_id],
            signal.call_args_list[2][0])
