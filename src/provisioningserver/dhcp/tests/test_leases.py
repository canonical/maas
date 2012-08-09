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
from textwrap import dedent

from maastesting.factory import factory
from maastesting.fakemethod import FakeMethod
from maastesting.testcase import TestCase
from maastesting.utils import (
    age_file,
    get_write_time,
    )
from provisioningserver.dhcp import leases as leases_module
from provisioningserver.dhcp.leases import (
    check_lease_changes,
    identify_new_leases,
    parse_leases_file,
    process_leases,
    record_lease_state,
    record_omapi_shared_key,
    register_new_leases,
    update_leases,
    upload_leases,
    )
from provisioningserver.omshell import Omshell
from testtools.testcase import ExpectedException


class TestHelpers(TestCase):

    def test_record_omapi_shared_key_records_shared_key(self):
        key = factory.getRandomString()
        record_omapi_shared_key(key)
        self.assertEqual(key, leases_module.recorded_omapi_shared_key)


class StopExecuting(BaseException):
    """Exception class to stop execution at a desired point.

    This is deliberately not just an :class:`Exception`.  We want to
    interrupt the code that's being tested, not just exercise its
    error-handling capabilities.
    """


class TestUpdateLeases(TestCase):

    def make_lease(self):
        """Create a leases dict with one, arbitrary lease in it."""
        return {factory.getRandomIPAddress(): factory.getRandomMACAddress()}

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

    def test_check_lease_changes_returns_tuple_if_no_state_cached(self):
        record_lease_state(None, None)
        leases = self.make_lease()
        leases_file = self.fake_leases_file(leases)
        self.assertEqual(
            (get_write_time(leases_file), leases),
            check_lease_changes())

    def test_check_lease_changes_returns_tuple_if_lease_changed(self):
        ip = factory.getRandomIPAddress()
        leases = {ip: factory.getRandomMACAddress()}
        record_lease_state(
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
        record_lease_state(get_write_time(leases_file), {})
        update_leases()
        self.assertSequenceEqual([], parser.calls)

    def test_check_lease_changes_returns_tuple_if_lease_added(self):
        leases = self.make_lease()
        record_lease_state(
            datetime.utcnow() - timedelta(seconds=10), leases.copy())
        leases[factory.getRandomIPAddress()] = factory.getRandomMACAddress()
        leases_file = self.fake_leases_file(leases)
        self.assertEqual(
            (get_write_time(leases_file), leases),
            check_lease_changes())

    def test_check_lease_changes_returns_tuple_if_leases_dropped(self):
        record_lease_state(
            datetime.utcnow() - timedelta(seconds=10), self.make_lease())
        leases_file = self.fake_leases_file({})
        self.assertEqual(
            (get_write_time(leases_file), {}),
            check_lease_changes())

    def test_check_lease_changes_returns_None_if_no_change(self):
        leases = self.make_lease()
        leases_file = self.fake_leases_file(leases)
        record_lease_state(get_write_time(leases_file), leases.copy())
        self.assertIsNone(check_lease_changes())

    def test_check_lease_changes_ignores_irrelevant_changes(self):
        leases = self.make_lease()
        self.fake_leases_file(leases, age=10)
        record_lease_state(datetime.utcnow(), leases.copy())
        self.assertIsNone(check_lease_changes())

    def test_update_leases_processes_leases_if_changed(self):
        record_lease_state(None, None)
        send_leases = FakeMethod()
        self.patch(leases_module, 'send_leases', send_leases)
        leases = self.make_lease()
        self.fake_leases_file(leases)
        self.patch(Omshell, 'create', FakeMethod())
        update_leases()
        self.assertSequenceEqual([(leases, )], send_leases.extract_args())

    def test_update_leases_does_nothing_without_lease_changes(self):
        send_leases = FakeMethod()
        self.patch(leases_module, 'send_leases', send_leases)
        leases = self.make_lease()
        leases_file = self.fake_leases_file(leases)
        record_lease_state(get_write_time(leases_file), leases.copy())
        self.assertSequenceEqual([], send_leases.calls)

    def test_process_leases_records_update(self):
        record_lease_state(None, None)
        self.patch(leases_module, 'recorded_omapi_shared_key', None)
        self.patch(leases_module, 'send_leases', FakeMethod())
        new_leases = {
            factory.getRandomIPAddress(): factory.getRandomMACAddress(),
        }
        self.fake_leases_file(new_leases)
        process_leases(datetime.utcnow(), new_leases)
        self.assertIsNone(check_lease_changes())

    def test_process_leases_records_state_before_sending(self):
        record_lease_state(None, None)
        self.patch(Omshell, 'create', FakeMethod())
        self.fake_leases_file({})
        self.patch(
            leases_module, 'send_leases', FakeMethod(failure=StopExecuting()))
        new_leases = {
            factory.getRandomIPAddress(): factory.getRandomMACAddress(),
        }
        try:
            process_leases(datetime.utcnow(), new_leases)
        except StopExecuting:
            pass
        self.fake_leases_file(new_leases)
        self.assertIsNone(check_lease_changes())

    def test_process_leases_registers_new_leases(self):
        record_lease_state(None, None)
        self.patch(Omshell, 'create', FakeMethod())
        ip = factory.getRandomIPAddress()
        mac = factory.getRandomMACAddress()
        process_leases(datetime.utcnow(), {ip: mac})
        self.assertEqual([(ip, mac)], Omshell.create.extract_args())

    def test_process_leases_retries_failed_registrations(self):

        class OmshellFailure(Exception):
            pass

        record_lease_state(None, None)
        self.patch(Omshell, 'create', FakeMethod(failure=OmshellFailure()))
        ip = factory.getRandomIPAddress()
        mac = factory.getRandomMACAddress()
        with ExpectedException(OmshellFailure):
            process_leases(datetime.utcnow(), {ip: mac})
        # At this point {ip: mac} has not been successfully registered.
        # But if we re-run process_leases later, it will retry.
        self.patch(Omshell, 'create', FakeMethod())
        process_leases(datetime.utcnow(), {ip: mac})
        self.assertEqual([(ip, mac)], Omshell.create.extract_args())

    def test_upload_leases_processes_leases_unconditionally(self):
        send_leases = FakeMethod()
        leases = self.make_lease()
        leases_file = self.fake_leases_file(leases)
        record_lease_state(get_write_time(leases_file), leases.copy())
        self.patch(leases_module, 'send_leases', send_leases)
        upload_leases()
        self.assertSequenceEqual([(leases, )], send_leases.extract_args())

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

    def test_identify_new_leases_identifies_everything_first_time(self):
        self.patch(leases_module, 'recorded_leases', None)
        current_leases = {
            factory.getRandomIPAddress(): factory.getRandomMACAddress(),
            factory.getRandomIPAddress(): factory.getRandomMACAddress(),
        }
        self.assertEqual(current_leases, identify_new_leases(current_leases))

    def test_identify_new_leases_identifies_previously_unknown_leases(self):
        self.patch(leases_module, 'recorded_leases', {})
        current_leases = {
            factory.getRandomIPAddress(): factory.getRandomMACAddress(),
        }
        self.assertEqual(current_leases, identify_new_leases(current_leases))

    def test_identify_new_leases_leaves_out_previously_known_leases(self):
        old_leases = {
            factory.getRandomIPAddress(): factory.getRandomMACAddress(),
        }
        self.patch(leases_module, 'recorded_leases', old_leases)
        new_leases = {
            factory.getRandomIPAddress(): factory.getRandomMACAddress(),
        }
        current_leases = old_leases.copy()
        current_leases.update(new_leases)
        self.assertEqual(new_leases, identify_new_leases(current_leases))

    def test_register_new_leases_registers_new_leases(self):
        self.patch(Omshell, 'create', FakeMethod())
        self.patch(leases_module, 'recorded_leases', None)
        self.patch(leases_module, 'recorded_omapi_shared_key', 'omapi-key')
        ip = factory.getRandomIPAddress()
        mac = factory.getRandomMACAddress()
        register_new_leases({ip: mac})
        [create_args] = Omshell.create.extract_args()
        self.assertEqual((ip, mac), create_args)

    def test_register_new_leases_ignores_known_leases(self):
        self.patch(Omshell, 'create', FakeMethod())
        self.patch(leases_module, 'recorded_omapi_shared_key', 'omapi-key')
        old_leases = {
            factory.getRandomIPAddress(): factory.getRandomMACAddress(),
        }
        self.patch(leases_module, 'recorded_leases', old_leases)
        register_new_leases(old_leases)
        self.assertEqual([], Omshell.create.calls)

    def test_register_new_leases_does_nothing_without_omapi_key(self):
        self.patch(Omshell, 'create', FakeMethod())
        self.patch(leases_module, 'recorded_leases', None)
        self.patch(leases_module, 'recorded_omapi_shared_key', None)
        new_leases = {
            factory.getRandomIPAddress(): factory.getRandomMACAddress(),
        }
        register_new_leases(new_leases)
        self.assertEqual([], Omshell.create.calls)
