# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the report_leases task."""

__all__ = []

from datetime import (
    datetime,
    timedelta,
)
import errno
import os
from textwrap import dedent

from maastesting.factory import factory
from maastesting.utils import (
    age_file,
    get_write_time,
)
from mock import Mock
from provisioningserver.dhcp import leases as leases_module
from provisioningserver.dhcp.leases import (
    cache,
    check_lease_changes,
    LEASES_CACHE_KEY,
    LEASES_TIME_CACHE_KEY,
    parse_leases_file,
    record_lease_state,
)
from provisioningserver.testing.testcase import PservTestCase


class TestHelpers(PservTestCase):

    def test_record_lease_state_records_time_and_leases(self):
        time = datetime.utcnow()
        leases = factory.make_random_leases()
        record_lease_state(time, leases)
        self.assertEqual(
            (time, leases), (
                cache.get(LEASES_TIME_CACHE_KEY),
                cache.get(LEASES_CACHE_KEY),
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
        self.patch(leases_module, 'get_leases_file').return_value = path

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

    def set_lease_state(self, time=None, leases=None):
        """Set the recorded state of DHCP leases.

        This is similar to record_lease_state, except it will patch() the
        state so that it gets reset at the end of the test.  Using this will
        prevent recorded lease state from leaking into other tests.
        """
        cache[LEASES_TIME_CACHE_KEY] = time
        cache[LEASES_CACHE_KEY] = leases

    def test_record_lease_state_sets_leases_and_timestamp(self):
        time = datetime.utcnow()
        leases = factory.make_random_leases()
        self.set_lease_state()
        record_lease_state(time, leases)
        self.assertEqual(
            (time, leases), (
                cache.get(LEASES_TIME_CACHE_KEY),
                cache.get(LEASES_CACHE_KEY),
                ))

    def test_check_lease_changes_returns_tuple_if_no_state_cached(self):
        self.set_lease_state()
        leases = factory.make_random_leases()
        leases_file = self.fake_leases_file(leases)
        self.assertEqual(
            (get_write_time(leases_file), leases),
            check_lease_changes())

    def test_check_lease_changes_returns_tuple_if_lease_changed(self):
        ip = factory.make_ipv4_address()
        leases = {ip: factory.make_mac_address()}
        self.set_lease_state(
            datetime.utcnow() - timedelta(seconds=10), leases.copy())
        leases[ip] = factory.make_mac_address()
        leases_file = self.fake_leases_file(leases)
        self.assertEqual(
            (get_write_time(leases_file), leases),
            check_lease_changes())

    def redirect_parser_to_non_existing_file(self):
        file_name = self.make_file()
        os.remove(file_name)
        self.redirect_parser(file_name)

    def test_parse_leases_file_returns_None_if_file_does_not_exist(self):
        self.redirect_parser_to_non_existing_file()
        self.assertIsNone(parse_leases_file())

    def test_get_leases_timestamp_returns_None_if_file_does_not_exist(self):
        self.redirect_parser_to_non_existing_file()
        self.assertIsNone(parse_leases_file())

    def test_parse_leases_file_errors_if_unexpected_exception(self):
        exception = IOError(errno.EBUSY, factory.make_string())
        self.patch(leases_module, 'open', Mock(side_effect=exception))
        self.assertRaises(IOError, parse_leases_file)

    def test_get_leases_timestamp_errors_if_unexpected_exception(self):
        exception = OSError(errno.EBUSY, factory.make_string())
        self.patch(leases_module, 'open', Mock(side_effect=exception))
        self.assertRaises(OSError, parse_leases_file)

    def test_check_lease_changes_returns_tuple_if_lease_added(self):
        leases = factory.make_random_leases()
        self.set_lease_state(
            datetime.utcnow() - timedelta(seconds=10), leases.copy())
        leases[factory.make_ipv4_address()] = factory.make_mac_address()
        leases_file = self.fake_leases_file(leases)
        self.assertEqual(
            (get_write_time(leases_file), leases),
            check_lease_changes())

    def test_check_lease_returns_None_if_lease_file_does_not_exist(self):
        self.redirect_parser_to_non_existing_file()
        self.assertIsNone(check_lease_changes())

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

    def test_parse_leases_file_parses_leases(self):
        params = {
            'ip': factory.make_ipv4_address(),
            'mac': factory.make_mac_address(),
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
            (get_write_time(leases_file), [(params['ip'], params['mac'])]),
            parse_leases_file())
