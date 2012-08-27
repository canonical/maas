# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the report_leases task."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from datetime import (
    datetime,
    timedelta,
    )
import json
from textwrap import dedent

from apiclient.maas_client import MAASClient
from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.utils import (
    age_file,
    get_write_time,
    )
from mock import Mock
from provisioningserver import cache
from provisioningserver.auth import (
    MAAS_URL_CACHE_KEY,
    NODEGROUP_NAME_CACHE_KEY,
    )
from provisioningserver.dhcp import leases as leases_module
from provisioningserver.dhcp.leases import (
    check_lease_changes,
    LEASES_CACHE_KEY,
    LEASES_TIME_CACHE_KEY,
    parse_leases_file,
    process_leases,
    record_lease_state,
    send_leases,
    update_leases,
    upload_leases,
    )
from provisioningserver.omshell import Omshell
from provisioningserver.testing.testcase import PservTestCase


class TestHelpers(PservTestCase):

    def test_record_lease_state_records_time_and_leases(self):
        time = datetime.utcnow()
        leases = factory.make_random_leases()
        record_lease_state(time, leases)
        self.assertEqual(
            (time, leases), (
                cache.cache.get(LEASES_TIME_CACHE_KEY),
                cache.cache.get(LEASES_CACHE_KEY),
                ))


class StopExecuting(BaseException):
    """Exception class to stop execution at a desired point.

    This is deliberately not just an :class:`Exception`.  We want to
    interrupt the code that's being tested, not just exercise its
    error-handling capabilities.
    """


class TestUpdateLeases(PservTestCase):

    def redirect_parser(self, path):
        """Make the leases parser read from a file at `path`."""
        self.patch(leases_module, 'DHCP_LEASES_FILE', path)

    def fake_leases_file(self, leases=None, age=None):
        """Fake the presence of a leases file.

        This does not go through the leases parser.  It patches out the
        leases parser with a fake that returns the lease data you pass in
        here.

        :param leases: Dict of leases (mapping IP addresses to MACs).
        :param age: Number of seconds since last modification to leases file.
        :return: Path/name of temporary file.
        """
        if leases is None:
            leases = {}
        leases = leases.copy()
        leases_file = self.make_file()
        if age is not None:
            age_file(leases_file, age)
        timestamp = get_write_time(leases_file)
        self.redirect_parser(leases_file)
        self.patch(
            leases_module, 'parse_leases_file', lambda: (timestamp, leases))
        return leases_file

    def write_leases_file(self, contents):
        """Create a leases file, and cause the parser to read from it.

        This patches out the leases parser to read from the new file.

        :param contents: Text contents for the leases file.
        :return: Path of temporary leases file.
        """
        leases_file = self.make_file(
            contents=dedent(contents).encode('utf-8'))
        self.redirect_parser(leases_file)
        return leases_file

    def set_nodegroup_name(self):
        """Set the recorded nodegroup name for the duration of this test."""
        name = factory.make_name('nodegroup')
        cache.cache.set(NODEGROUP_NAME_CACHE_KEY, name)
        return name

    def clear_nodegroup_name(self):
        """Clear the recorded nodegroup name."""
        cache.cache.set(NODEGROUP_NAME_CACHE_KEY, None)

    def set_maas_url(self):
        """Set the recorded MAAS URL for the duration of this test."""
        maas_url = 'http://%s.example.com/%s/' % (
            factory.make_name('host'),
            factory.getRandomString(),
            )
        cache.cache.set(MAAS_URL_CACHE_KEY, maas_url)

    def clear_maas_url(self):
        """Clear the recorded MAAS API URL."""
        cache.cache.set(MAAS_URL_CACHE_KEY, None)

    def set_api_credentials(self):
        """Set recorded API credentials for the duration of this test."""
        creds_string = ':'.join(
            factory.getRandomString() for counter in range(3))
        cache.cache.set('api_credentials', creds_string)

    def clear_api_credentials(self):
        """Clear recorded API credentials."""
        cache.cache.set('api_credentials', None)

    def set_items_needed_for_lease_update(self):
        """Set the recorded items required by `update_leases`."""
        self.set_maas_url()
        self.set_api_credentials()
        self.set_nodegroup_name()

    def set_lease_state(self, time=None, leases=None):
        """Set the recorded state of DHCP leases.

        This is similar to record_lease_state, except it will patch() the
        state so that it gets reset at the end of the test.  Using this will
        prevent recorded lease state from leaking into other tests.
        """
        cache.cache.set(LEASES_TIME_CACHE_KEY, time)
        cache.cache.set(LEASES_CACHE_KEY, leases)

    def test_record_lease_state_sets_leases_and_timestamp(self):
        time = datetime.utcnow()
        leases = factory.make_random_leases()
        self.set_lease_state()
        record_lease_state(time, leases)
        self.assertEqual(
            (time, leases), (
                cache.cache.get(LEASES_TIME_CACHE_KEY),
                cache.cache.get(LEASES_CACHE_KEY),
                ))

    def test_check_lease_changes_returns_tuple_if_no_state_cached(self):
        self.set_lease_state()
        leases = factory.make_random_leases()
        leases_file = self.fake_leases_file(leases)
        self.assertEqual(
            (get_write_time(leases_file), leases),
            check_lease_changes())

    def test_check_lease_changes_returns_tuple_if_lease_changed(self):
        ip = factory.getRandomIPAddress()
        leases = {ip: factory.getRandomMACAddress()}
        self.set_lease_state(
            datetime.utcnow() - timedelta(seconds=10), leases.copy())
        leases[ip] = factory.getRandomMACAddress()
        leases_file = self.fake_leases_file(leases)
        self.assertEqual(
            (get_write_time(leases_file), leases),
            check_lease_changes())

    def test_check_lease_changes_does_not_parse_unchanged_leases_file(self):
        parser = FakeMethod()
        leases_file = self.fake_leases_file()
        self.patch(leases_module, 'parse_leases_file', parser)
        self.set_lease_state(get_write_time(leases_file), {})
        update_leases()
        self.assertSequenceEqual([], parser.calls)

    def test_check_lease_changes_returns_tuple_if_lease_added(self):
        leases = factory.make_random_leases()
        self.set_lease_state(
            datetime.utcnow() - timedelta(seconds=10), leases.copy())
        leases[factory.getRandomIPAddress()] = factory.getRandomMACAddress()
        leases_file = self.fake_leases_file(leases)
        self.assertEqual(
            (get_write_time(leases_file), leases),
            check_lease_changes())

    def test_check_lease_changes_returns_tuple_if_leases_dropped(self):
        self.set_lease_state(
            datetime.utcnow() - timedelta(seconds=10),
            factory.make_random_leases())
        leases_file = self.fake_leases_file({})
        self.assertEqual(
            (get_write_time(leases_file), {}),
            check_lease_changes())

    def test_check_lease_changes_returns_None_if_no_change(self):
        leases = factory.make_random_leases()
        leases_file = self.fake_leases_file(leases)
        self.set_lease_state(get_write_time(leases_file), leases.copy())
        self.assertIsNone(check_lease_changes())

    def test_check_lease_changes_ignores_irrelevant_changes(self):
        leases = factory.make_random_leases()
        self.fake_leases_file(leases, age=10)
        self.set_lease_state(datetime.utcnow(), leases.copy())
        self.assertIsNone(check_lease_changes())

    def test_update_leases_processes_leases_if_changed(self):
        self.set_lease_state()
        self.patch(leases_module, 'send_leases', FakeMethod())
        leases = factory.make_random_leases()
        self.fake_leases_file(leases)
        self.patch(Omshell, 'create', FakeMethod())
        update_leases()
        self.assertEqual(
            [(leases, )],
            leases_module.send_leases.extract_args())

    def test_update_leases_does_nothing_without_lease_changes(self):
        fake_send_leases = FakeMethod()
        self.patch(leases_module, 'send_leases', fake_send_leases)
        leases = factory.make_random_leases()
        leases_file = self.fake_leases_file(leases)
        self.set_lease_state(get_write_time(leases_file), leases.copy())
        self.assertEqual([], leases_module.send_leases.calls)

    def test_process_leases_records_update(self):
        self.set_lease_state()
        self.patch(leases_module, 'send_leases', FakeMethod())
        new_leases = factory.make_random_leases()
        self.fake_leases_file(new_leases)
        process_leases(datetime.utcnow(), new_leases)
        self.assertIsNone(check_lease_changes())

    def test_process_leases_records_state_before_sending(self):
        self.set_lease_state()
        self.patch(Omshell, 'create', FakeMethod())
        self.fake_leases_file({})
        self.patch(
            leases_module, 'send_leases', FakeMethod(failure=StopExecuting()))
        new_leases = factory.make_random_leases()
        try:
            process_leases(datetime.utcnow(), new_leases)
        except StopExecuting:
            pass
        self.fake_leases_file(new_leases)
        self.assertIsNone(check_lease_changes())

    def test_upload_leases_processes_leases_unconditionally(self):
        leases = factory.make_random_leases()
        leases_file = self.fake_leases_file(leases)
        self.set_lease_state(get_write_time(leases_file), leases.copy())
        self.patch(leases_module, 'send_leases', FakeMethod())
        upload_leases()
        self.assertEqual(
            [(leases, )],
            leases_module.send_leases.extract_args())

    def test_parse_leases_file_parses_leases(self):
        params = {
            'ip': factory.getRandomIPAddress(),
            'mac': factory.getRandomMACAddress(),
        }
        leases_file = self.write_leases_file("""\
            lease %(ip)s {
                starts 5 2010/01/01 00:00:01;
                ends never;
                tstp 6 2010/01/02 05:00:00;
                tsfp 6 2010/01/02 05:00:00;
                binding state free;
                hardware ethernet %(mac)s;
            }
            """ % params)
        self.assertEqual(
            (get_write_time(leases_file), {params['ip']: params['mac']}),
            parse_leases_file())

    def test_send_leases_does_nothing_without_maas_url(self):
        self.patch(MAASClient, 'post', FakeMethod())
        self.set_lease_state()
        self.set_items_needed_for_lease_update()
        self.clear_maas_url()
        leases = factory.make_random_leases()
        send_leases(leases)
        self.assertEqual([], MAASClient.post.calls)

    def test_send_leases_does_nothing_without_credentials(self):
        self.patch(MAASClient, 'post', FakeMethod())
        self.set_items_needed_for_lease_update()
        self.clear_api_credentials()
        leases = factory.make_random_leases()
        send_leases(leases)
        self.assertEqual([], MAASClient.post.calls)

    def test_send_leases_does_nothing_without_nodegroup_name(self):
        self.patch(MAASClient, 'post', FakeMethod())
        self.set_lease_state()
        self.set_items_needed_for_lease_update()
        self.clear_nodegroup_name()
        leases = factory.make_random_leases()
        send_leases(leases)
        self.assertEqual([], MAASClient.post.calls)

    def test_send_leases_encodes_lease_data_with_json(self):
        self.patch(MAASClient, 'post', Mock())
        self.set_lease_state()
        self.set_items_needed_for_lease_update()
        leases = factory.make_random_leases()
        send_leases(leases)

        args, kwargs = MAASClient.post.call_args
        leases = kwargs['leases']
        decoded = json.loads(leases)
        self.assertIsInstance(decoded, dict)
