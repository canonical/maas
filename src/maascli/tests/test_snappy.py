# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maascli.snappy`."""

__all__ = []

import os
import random
import signal
import subprocess
from textwrap import dedent
import time
from unittest.mock import MagicMock

from maascli import snappy
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
import netifaces
from testtools.matchers import (
    Contains,
    Not,
)
import yaml


class TestHelpers(MAASTestCase):

    def setUp(self):
        super(TestHelpers, self).setUp()
        snap_common = self.make_dir()
        snap_data = self.make_dir()
        self.environ = {
            'SNAP_COMMON': snap_common,
            'SNAP_DATA': snap_data,
        }
        self.patch(os, 'environ', self.environ)

    def test_get_default_gateway_ip_no_defaults(self):
        self.patch(netifaces, 'gateways').return_value = {}
        self.assertIsNone(snappy.get_default_gateway_ip())

    def test_get_default_gateway_ip_returns_ipv4(self):
        ipv4_address = factory.make_ipv4_address()
        self.patch(netifaces, 'gateways').return_value = {
            'default': {
                netifaces.AF_INET: (ipv4_address, factory.make_name('eth')),
            }
        }
        self.assertEqual(ipv4_address, snappy.get_default_gateway_ip())

    def test_get_default_gateway_ip_returns_ipv6(self):
        ipv6_address = factory.make_ipv6_address()
        self.patch(netifaces, 'gateways').return_value = {
            'default': {
                netifaces.AF_INET6: (ipv6_address, factory.make_name('eth')),
            }
        }
        self.assertEqual(ipv6_address, snappy.get_default_gateway_ip())

    def test_get_default_gateway_ip_returns_ipv4_over_ipv6(self):
        ipv4_address = factory.make_ipv4_address()
        ipv6_address = factory.make_ipv6_address()
        self.patch(netifaces, 'gateways').return_value = {
            'default': {
                netifaces.AF_INET: (ipv4_address, factory.make_name('eth')),
                netifaces.AF_INET6: (ipv6_address, factory.make_name('eth')),
            }
        }
        self.assertEqual(ipv4_address, snappy.get_default_gateway_ip())

    def test_get_default_url_uses_gateway_ip(self):
        ipv4_address = factory.make_ipv4_address()
        self.patch(
            snappy, 'get_default_gateway_ip').return_value = ipv4_address
        self.assertEqual(
            'http://%s:5240/MAAS' % ipv4_address, snappy.get_default_url())

    def test_get_default_url_fallsback_to_localhost(self):
        self.patch(
            snappy, 'get_default_gateway_ip').return_value = None
        self.assertEqual(
            'http://localhost:5240/MAAS', snappy.get_default_url())

    def test_get_mode_filepath(self):
        self.assertEqual(
            os.path.join(self.environ['SNAP_COMMON'], 'snap_mode'),
            snappy.get_mode_filepath())

    def test_get_current_mode_returns_none_when_missing(self):
        self.assertEqual('none', snappy.get_current_mode())

    def test_get_current_mode_returns_file_contents(self):
        snappy.set_current_mode('all')
        self.assertEqual('all', snappy.get_current_mode())

    def test_set_current_mode_creates_file(self):
        snappy.set_current_mode('all')
        self.assertTrue(os.path.exists(snappy.get_mode_filepath()))

    def test_set_current_mode_overwrites(self):
        snappy.set_current_mode('all')
        snappy.set_current_mode('none')
        self.assertEqual('none', snappy.get_current_mode())


class TestRenderSupervisord(MAASTestCase):

    TEST_TEMPLATE = dedent("""\
    {{if postgresql}}
    HAS_POSTGRESQL
    {{endif}}
    {{if regiond}}
    HAS_REGIOND
    {{endif}}
    {{if rackd}}
    HAS_RACKD
    {{endif}}
    """)

    scenarios = (
        ('all', {
            'mode': 'all',
            'postgresql': True,
            'regiond': True,
            'rackd': True,
        }),
        ('region+rack', {
            'mode': 'region+rack',
            'postgresql': False,
            'regiond': True,
            'rackd': True,
        }),
        ('region', {
            'mode': 'region',
            'postgresql': False,
            'regiond': True,
            'rackd': False,
        }),
        ('rack', {
            'mode': 'rack',
            'postgresql': False,
            'regiond': False,
            'rackd': True,
        }),
        ('none', {
            'mode': 'none',
            'postgresql': False,
            'regiond': False,
            'rackd': False,
        }),
    )

    def setUp(self):
        super(TestRenderSupervisord, self).setUp()
        snap = self.make_dir()
        maas_share = os.path.join(snap, 'usr', 'share', 'maas')
        os.makedirs(maas_share)
        with open(
                os.path.join(
                    maas_share, 'supervisord.conf.template'), 'w') as stream:
            stream.write(self.TEST_TEMPLATE)
        snap_data = self.make_dir()
        os.mkdir(os.path.join(snap_data, 'supervisord'))
        self.environ = {
            'SNAP': snap,
            'SNAP_DATA': snap_data,
        }
        self.patch(os, 'environ', self.environ)

    def get_rendered_config(self):
        with open(
                os.path.join(
                    self.environ['SNAP_DATA'],
                    'supervisord', 'supervisord.conf'), 'r') as stream:
            return stream.read()

    def test_template_rended_correctly(self):
        snappy.render_supervisord(self.mode)
        output = self.get_rendered_config()
        if self.postgresql:
            self.assertThat(output, Contains('HAS_POSTGRESQL'))
        else:
            self.assertThat(output, Not(Contains('HAS_POSTGRESQL')))
        if self.regiond:
            self.assertThat(output, Contains('HAS_REGIOND'))
        else:
            self.assertThat(output, Not(Contains('HAS_REGIOND')))
        if self.rackd:
            self.assertThat(output, Contains('HAS_RACKD'))
        else:
            self.assertThat(output, Not(Contains('HAS_RACKD')))


class TestSupervisordHelpers(MAASTestCase):

    def test_get_supervisord_pid_returns_None(self):
        snap_data = self.make_dir()
        self.patch(os, 'environ', {
            'SNAP_DATA': snap_data,
        })
        self.assertIsNone(snappy.get_supervisord_pid())

    def test_get_supervisord_pid_returns_pid(self):
        pid = random.randint(2, 99)
        snap_data = self.make_dir()
        supervisord_dir = os.path.join(snap_data, 'supervisord')
        os.makedirs(supervisord_dir)
        with open(
                os.path.join(
                    supervisord_dir, 'supervisord.pid'), 'w') as stream:
            stream.write('%s' % pid)
        self.patch(os, 'environ', {
            'SNAP_DATA': snap_data,
        })
        self.assertEqual(pid, snappy.get_supervisord_pid())

    def test_sighup_supervisord_sends_SIGHUP(self):
        pid = random.randint(2, 99)
        snap = self.make_dir()
        self.patch(os, 'environ', {
            'SNAP': snap,
        })
        self.patch(snappy, 'get_supervisord_pid').return_value = pid
        mock_kill = self.patch(os, 'kill')
        self.patch(time, 'sleep')  # Speed up the test.
        mock_process = MagicMock()
        mock_popen = self.patch(subprocess, 'Popen')
        mock_popen.return_value = mock_process
        snappy.sighup_supervisord()
        self.assertThat(mock_kill, MockCalledOnceWith(pid, signal.SIGHUP))
        self.assertThat(mock_popen, MockCalledOnceWith([
            os.path.join(snap, 'bin', 'run-supervisorctl'), 'status'
        ], stdout=subprocess.PIPE))
        self.assertThat(mock_process.wait, MockCalledOnceWith())

    def test_sighup_supervisord_waits_until_no_error(self):
        pid = random.randint(2, 99)
        snap = self.make_dir()
        self.patch(os, 'environ', {
            'SNAP': snap,
        })
        self.patch(snappy, 'get_supervisord_pid').return_value = pid
        mock_kill = self.patch(os, 'kill')
        self.patch(time, 'sleep')  # Speed up the test.
        mock_process = MagicMock()
        mock_process.stdout.read.side_effect = [
            b'error:',
            b'',
        ]
        mock_popen = self.patch(subprocess, 'Popen')
        mock_popen.return_value = mock_process
        snappy.sighup_supervisord()
        self.assertThat(mock_kill, MockCalledOnceWith(pid, signal.SIGHUP))
        self.assertEquals(2, mock_popen.call_count)


class TestConfigHelpers(MAASTestCase):

    def setUp(self):
        super(TestConfigHelpers, self).setUp()
        snap_data = self.make_dir()
        self.environ = {
            'SNAP_DATA': snap_data,
        }
        self.regiond_path = os.path.join(snap_data, 'regiond.conf')
        self.patch(os, 'environ', self.environ)

    def test_get_config_data_returns_empty_dict_when_no_config(self):
        self.assertEquals({}, snappy.get_config_data())

    def test_get_config_data_returns_empty_dict_when_config_empty(self):
        open(self.regiond_path, 'w').close()
        self.assertEquals({}, snappy.get_config_data())

    def test_get_config_data_loads_yaml_data(self):
        fake_config = {
            factory.make_name('key'): factory.make_name('value')
        }
        with open(self.regiond_path, 'w') as stream:
            stream.write(yaml.safe_dump(fake_config))
        self.assertEquals(fake_config, snappy.get_config_data())

    def test_get_config_value_returns_value_from_config(self):
        key = factory.make_name('key')
        value = factory.make_name('value')
        fake_config = {
            key: value
        }
        with open(self.regiond_path, 'w') as stream:
            stream.write(yaml.safe_dump(fake_config))
        self.assertEquals(value, snappy.get_config_value(key))

    def test_get_config_value_returns_None_when_missing(self):
        self.assertIsNone(snappy.get_config_value(factory.make_name('key')))

    def test_print_config_value(self):
        mock_print = self.patch(snappy, 'print_msg')
        key = factory.make_name('key')
        value = factory.make_name('value')
        self.patch(snappy, 'get_config_value').return_value = value
        snappy.print_config_value(key)
        self.assertThat(mock_print, MockCalledOnceWith("%s=%s" % (key, value)))

    def test_write_config_data(self):
        filename = factory.make_name('file')
        fake_config = {
            factory.make_name('key'): factory.make_name('value')
        }
        snappy.write_config_data(fake_config, filename)
        with open(
                os.path.join(
                    self.environ['SNAP_DATA'], filename), 'r') as stream:
            observed = yaml.safe_load(stream)
        self.assertEquals(fake_config, observed)

    def test_update_config_value_sets_value_in_config(self):
        key = factory.make_name('key')
        value = factory.make_name('value')
        snappy.update_config_value(key, value)
        self.assertEquals(value, snappy.get_config_value(key))

    def test_update_config_value_clears_value(self):
        key = factory.make_name('key')
        value = factory.make_name('value')
        snappy.update_config_value(key, value)
        snappy.update_config_value(key, None)
        self.assertIsNone(snappy.get_config_value(key))

    def test_update_config_value_maas_url_goes_into_rackd_conf(self):
        value = factory.make_name('value')
        snappy.update_config_value('maas_url', value)
        with open(
                os.path.join(
                    self.environ['SNAP_DATA'], 'rackd.conf'), 'r') as stream:
            observed = yaml.safe_load(stream)
        self.assertEquals({
            'maas_url': value,
        }, observed)

    def test_update_config_value_maas_url_clears_rackd_conf(self):
        value = factory.make_name('value')
        snappy.update_config_value('maas_url', value)
        snappy.update_config_value('maas_url', None)
        with open(
                os.path.join(
                    self.environ['SNAP_DATA'], 'rackd.conf'), 'r') as stream:
            observed = yaml.safe_load(stream)
        self.assertEquals({}, observed)

    def test_get_rpc_secret_returns_secret(self):
        maas_dir = os.path.join(
            self.environ['SNAP_DATA'], 'var', 'lib', 'maas')
        os.makedirs(maas_dir)
        secret_path = os.path.join(maas_dir, 'secret')
        secret = factory.make_string()
        with open(secret_path, 'w') as stream:
            stream.write(secret)
        self.assertEqual(secret, snappy.get_rpc_secret())

    def test_get_rpc_secret_returns_None_when_no_file(self):
        maas_dir = os.path.join(
            self.environ['SNAP_DATA'], 'var', 'lib', 'maas')
        os.makedirs(maas_dir)
        self.assertIsNone(snappy.get_rpc_secret())

    def test_get_rpc_secret_returns_None_when_empty_file(self):
        maas_dir = os.path.join(
            self.environ['SNAP_DATA'], 'var', 'lib', 'maas')
        os.makedirs(maas_dir)
        secret_path = os.path.join(maas_dir, 'secret')
        open(secret_path, 'w').close()
        self.assertIsNone(snappy.get_rpc_secret())

    def test_set_rpc_secret_sets_secret(self):
        maas_dir = os.path.join(
            self.environ['SNAP_DATA'], 'var', 'lib', 'maas')
        os.makedirs(maas_dir)
        secret = factory.make_string()
        snappy.set_rpc_secret(secret)
        self.assertEquals(secret, snappy.get_rpc_secret())

    def test_set_rpc_secret_clears_secret(self):
        maas_dir = os.path.join(
            self.environ['SNAP_DATA'], 'var', 'lib', 'maas')
        os.makedirs(maas_dir)
        secret = factory.make_string()
        snappy.set_rpc_secret(secret)
        snappy.set_rpc_secret(None)
        self.assertIsNone(snappy.get_rpc_secret())

    def test_print_msg_empty_message(self):
        mock_print = self.patch(snappy, 'print')
        snappy.print_msg()
        self.assertThat(
            mock_print, MockCalledOnceWith('', end='\n', flush=True))
