# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test smartctl functions."""

__all__ = []

from subprocess import (
    CalledProcessError,
    DEVNULL,
    PIPE,
    Popen,
    TimeoutExpired,
)
from textwrap import dedent
from unittest.mock import call

from maasserver.testing.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from metadataserver.builtin_scripts import smartctl


SMARTCTL_OUTPUT = dedent("""
    ...
    === START OF INFORMATION SECTION ===
    Device Model:     QEMU HARDDISK
    Serial Number:    QM00001
    Firmware Version: 2.5+
    User Capacity:    42,949,672,960 bytes [42.9 GB]
    Sector Size:      512 bytes logical/physical
    Device is:        Not in smartctl database [for details use: -P showall]
    ATA Version is:   ATA/ATAPI-7, ATA/ATAPI-5 published, ANSI NCITS 340-2000
    Local Time is:    Wed Sep  6 14:07:42 2017 PDT
    SMART support is: Available - device has SMART capability.
    SMART support is: Enabled
    ...
    """)


class TestSmartCTL(MAASTestCase):

    def test_SMART_support_is_available(self):
        storage = factory.make_name('storage')
        mock_check_output = self.patch(smartctl, "check_output")
        mock_check_output.return_value = SMARTCTL_OUTPUT.encode('utf-8')
        smartctl.check_SMART_support(storage)

        self.assertThat(mock_check_output, MockCalledOnceWith(
            ['sudo', '-n', 'smartctl', '--all', storage],
            timeout=smartctl.TIMEOUT))

    def test_SMART_support_is_not_available(self):
        storage = factory.make_name('storage')
        mock_check_output = self.patch(smartctl, "check_output")
        mock_check_output.side_effect = CalledProcessError(1, 'smartctl')
        mock_print = self.patch(smartctl, "print")

        self.assertRaises(SystemExit, smartctl.check_SMART_support, storage)
        self.assertThat(mock_check_output, MockCalledOnceWith(
            ['sudo', '-n', 'smartctl', '--all', storage],
            timeout=smartctl.TIMEOUT))
        self.assertThat(
            mock_print, MockCalledOnceWith(
                'The following drive does not support SMART: %s\n' % storage))

    def test_SMART_support_no_match_found(self):
        storage = factory.make_name('storage')
        mock_check_output = self.patch(smartctl, "check_output")
        mock_check_output.return_value = b"SMART support is not available."
        mock_print = self.patch(smartctl, "print")

        self.assertRaises(SystemExit, smartctl.check_SMART_support, storage)
        self.assertThat(mock_check_output, MockCalledOnceWith(
            ['sudo', '-n', 'smartctl', '--all', storage],
            timeout=smartctl.TIMEOUT))
        self.assertThat(
            mock_print, MockCalledOnceWith(
                'The following drive does not support SMART: %s\n' % storage))

    def test_run_smartctl_selftest(self):
        storage = factory.make_name('storage')
        test = factory.make_name('test')
        mock_check_call = self.patch(smartctl, "check_call")
        mock_check_output = self.patch(smartctl, "check_output")
        mock_check_output.return_value = (
            b'Self-test execution status:      (   0)')

        self.assertTrue(smartctl.run_smartctl_selftest(storage, test))
        self.assertThat(
            mock_check_call, MockCalledOnceWith(
                ['sudo', '-n', 'smartctl', '-s', 'on', '-t', test, storage],
                timeout=smartctl.TIMEOUT, stdout=DEVNULL, stderr=DEVNULL))
        self.assertThat(
            mock_check_output, MockCalledOnceWith(
                ['sudo', '-n', 'smartctl', '-c', storage],
                timeout=smartctl.TIMEOUT))

    def test_run_smartctl_selftest_waits_for_finish(self):
        storage = factory.make_name('storage')
        test = factory.make_name('test')
        self.patch(smartctl, 'sleep')
        mock_check_call = self.patch(smartctl, "check_call")
        mock_check_output = self.patch(smartctl, "check_output")
        mock_check_output.side_effect = [
            b'Self-test execution status:      ( 249)',
            b'Self-test execution status:      ( 249)',
            b'Self-test execution status:      ( 249)',
            b'Self-test execution status:      (   0)',
        ]

        self.assertTrue(smartctl.run_smartctl_selftest(storage, test))
        self.assertThat(
            mock_check_call, MockCalledOnceWith(
                ['sudo', '-n', 'smartctl', '-s', 'on', '-t', test, storage],
                timeout=smartctl.TIMEOUT, stdout=DEVNULL, stderr=DEVNULL))
        self.assertThat(
            mock_check_output, MockCallsMatch(
                call(
                    ['sudo', '-n', 'smartctl', '-c', storage],
                    timeout=smartctl.TIMEOUT),
                call(
                    ['sudo', '-n', 'smartctl', '-c', storage],
                    timeout=smartctl.TIMEOUT),
                call(
                    ['sudo', '-n', 'smartctl', '-c', storage],
                    timeout=smartctl.TIMEOUT),
                call(
                    ['sudo', '-n', 'smartctl', '-c', storage],
                    timeout=smartctl.TIMEOUT)))

    def test_run_smartctl_selftest_sets_failure_on_timeout_of_test_start(self):
        storage = factory.make_name('storage')
        test = factory.make_name('test')
        mock_check_call = self.patch(smartctl, 'check_call')
        mock_check_call.side_effect = TimeoutExpired('smartctl', 60)
        mock_check_output = self.patch(smartctl, 'check_output')

        self.assertFalse(smartctl.run_smartctl_selftest(storage, test))
        self.assertThat(
            mock_check_call, MockCalledOnceWith(
                ['sudo', '-n', 'smartctl', '-s', 'on', '-t', test, storage],
                timeout=smartctl.TIMEOUT, stdout=DEVNULL, stderr=DEVNULL))
        self.assertThat(mock_check_output, MockNotCalled())

    def test_run_smartctl_selftest_sets_failure_on_exec_fail_test_start(self):
        storage = factory.make_name('storage')
        test = factory.make_name('test')
        mock_check_call = self.patch(smartctl, 'check_call')
        mock_check_call.side_effect = CalledProcessError(1, 'smartctl')
        mock_check_output = self.patch(smartctl, 'check_output')

        self.assertFalse(smartctl.run_smartctl_selftest(storage, test))
        self.assertThat(
            mock_check_call, MockCalledOnceWith(
                ['sudo', '-n', 'smartctl', '-s', 'on', '-t', test, storage],
                timeout=smartctl.TIMEOUT, stdout=DEVNULL, stderr=DEVNULL))
        self.assertThat(mock_check_output, MockNotCalled())

    def test_run_smartctl_selftest_sets_failure_on_timeout_status_check(self):
        storage = factory.make_name('storage')
        test = factory.make_name('test')
        mock_check_call = self.patch(smartctl, 'check_call')
        mock_check_output = self.patch(smartctl, 'check_output')
        mock_check_output.side_effect = TimeoutExpired('smartctl', 60)

        self.assertFalse(smartctl.run_smartctl_selftest(storage, test))
        self.assertThat(
            mock_check_call, MockCalledOnceWith(
                ['sudo', '-n', 'smartctl', '-s', 'on', '-t', test, storage],
                timeout=smartctl.TIMEOUT, stdout=DEVNULL, stderr=DEVNULL))
        self.assertThat(
            mock_check_output, MockCalledOnceWith(
                ['sudo', '-n', 'smartctl', '-c', storage],
                timeout=smartctl.TIMEOUT))

    def test_run_smartctl_selftest_sets_failure_on_exc_fail_status_check(self):
        storage = factory.make_name('storage')
        test = factory.make_name('test')
        mock_check_call = self.patch(smartctl, 'check_call')
        mock_check_output = self.patch(smartctl, 'check_output')
        mock_check_output.side_effect = CalledProcessError(1, 'smartctl')

        self.assertFalse(smartctl.run_smartctl_selftest(storage, test))
        self.assertThat(
            mock_check_call, MockCalledOnceWith(
                ['sudo', '-n', 'smartctl', '-s', 'on', '-t', test, storage],
                timeout=smartctl.TIMEOUT, stdout=DEVNULL, stderr=DEVNULL))
        self.assertThat(
            mock_check_output, MockCalledOnceWith(
                ['sudo', '-n', 'smartctl', '-c', storage],
                timeout=smartctl.TIMEOUT))

    def test_run_smartctl_with_success(self):
        output = factory.make_string().encode('utf-8')
        storage = factory.make_name('storage')
        cmd = ['sudo', '-n', 'smartctl', '--xall', storage]
        self.patch(smartctl, "check_SMART_support")
        self.patch(smartctl, "run_smartctl_selftest")
        mock_print = self.patch(smartctl, "print")
        mock_popen = self.patch(smartctl, "Popen")
        mock_popen.return_value = Popen(['echo', '-n', output], stdout=PIPE)

        self.assertEquals(0, smartctl.run_smartctl(storage))
        self.assertThat(mock_print, MockCallsMatch(
            call('Running command: %s\n' % ' '.join(cmd)),
            call(output.decode('utf-8'))))

    def test_run_smartctl_with_failure(self):
        output = factory.make_string().encode('utf-8')
        storage = factory.make_name('storage')
        cmd = ['sudo', '-n', 'smartctl', '--xall', storage]
        self.patch(smartctl, "check_SMART_support")
        self.patch(smartctl, "run_smartctl_selftest")
        mock_print = self.patch(smartctl, "print")
        mock_popen = self.patch(smartctl, "Popen")
        mock_popen.return_value = Popen(
            'echo -n %s; exit 1' % output.decode('utf-8'),
            stdout=PIPE, shell=True)

        self.assertEquals(1, smartctl.run_smartctl(storage))
        self.assertThat(mock_print, MockCallsMatch(
            call('Running command: %s\n' % ' '.join(cmd)),
            call(output.decode('utf-8')),
            call('Error, `smartctl --xall %s` returned %d!' % (
                storage, 1)),
            call('See the smartctl man page for return code meaning')))

    def test_run_smartctl_timedout(self):
        smartctl.TIMEOUT = 1
        storage = factory.make_name('storage')
        cmd = ['sudo', '-n', 'smartctl', '--xall', storage]
        self.patch(smartctl, "check_SMART_support")
        self.patch(smartctl, "run_smartctl_selftest")
        mock_print = self.patch(smartctl, "print")
        mock_popen = self.patch(smartctl, "Popen")
        mock_popen.return_value = Popen(['sleep', '60'], stdout=PIPE)

        self.assertEquals(1, smartctl.run_smartctl(storage))
        self.assertThat(mock_print, MockCallsMatch(
            call('Running command: %s\n' % ' '.join(cmd)),
            call('Running `smartctl --xall %s` timed out!' % storage)))
