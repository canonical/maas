# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test badblocks functions."""

__all__ = []

from subprocess import (
    CalledProcessError,
    DEVNULL,
    PIPE,
    Popen,
    STDOUT,
    TimeoutExpired,
)
from unittest.mock import call

from maasserver.testing.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
)
from maastesting.testcase import MAASTestCase
from metadataserver.builtin_scripts import badblocks


class TestRunBadBlocks(MAASTestCase):

    def make_drive(self, name=None, model=None, serial=None, with_path=False):
        if name is None:
            name = factory.make_name('NAME')
        if model is None:
            model = factory.make_name('MODEL')
        if serial is None:
            serial = factory.make_name('SERIAL')
        drive = {
            'NAME': name,
            'RO': '0',
            'MODEL': model,
            'SERIAL': serial,
        }
        if with_path:
            drive['PATH'] = '/dev/%s' % drive['NAME']
        return drive

    def make_iscsi_line(self, drive=None):
        if drive is None:
            drive = self.make_drive()
        line = (
            'Attached scsi disk %s        State: running' % drive['NAME'])
        return line.encode()

    def make_lsblk_line(self, drive=None):
        if drive is None:
            drive = self.make_drive()
        line = ' '.join(
            ['%s=%s' % (key, value) for key, value in drive.items()])
        return line.encode()

    def test_list_drives(self):
        mock_check_output = self.patch(badblocks, 'check_output')
        drive = self.make_drive()
        mock_check_output.side_effect = [
            self.make_iscsi_line(),
            self.make_lsblk_line(drive),
        ]
        self.assertDictEqual(
            {'PATH': '/dev/%s' % drive['NAME'], **drive},
            badblocks.list_drives()[0])
        self.assertThat(
            mock_check_output, MockCallsMatch(
                call(
                    ['sudo', '-n', 'iscsiadm', '-m', 'session', '-P', '3'],
                    timeout=badblocks.TIMEOUT, stderr=DEVNULL),
                call(
                    [
                        'lsblk', '--exclude', '1,2,7', '-d', '-P', '-o',
                        'NAME,RO,MODEL,SERIAL',
                    ],
                    timeout=badblocks.TIMEOUT)))

    def test_list_supported_drives_ignores_iscsiadm_timeout(self):
        mock_check_output = self.patch(badblocks, 'check_output')
        drive = self.make_drive()
        mock_check_output.side_effect = [
            TimeoutExpired('iscsiadm', 60),
            self.make_lsblk_line(drive)
        ]
        self.assertDictEqual(
            {'PATH': '/dev/%s' % drive['NAME'], **drive},
            badblocks.list_drives()[0])
        self.assertThat(
            mock_check_output, MockCallsMatch(
                call(
                    ['sudo', '-n', 'iscsiadm', '-m', 'session', '-P', '3'],
                    timeout=badblocks.TIMEOUT, stderr=DEVNULL),
                call(
                    [
                        'lsblk', '--exclude', '1,2,7', '-d', '-P', '-o',
                        'NAME,RO,MODEL,SERIAL',
                    ],
                    timeout=badblocks.TIMEOUT)))

    def test_list_supported_drives_ignores_iscsiadm_errors(self):
        mock_check_output = self.patch(badblocks, 'check_output')
        drive = self.make_drive()
        mock_check_output.side_effect = [
            CalledProcessError('iscsiadm', 60),
            self.make_lsblk_line(drive)
        ]
        self.assertDictEqual(
            {'PATH': '/dev/%s' % drive['NAME'], **drive},
            badblocks.list_drives()[0])
        self.assertThat(
            mock_check_output, MockCallsMatch(
                call(
                    ['sudo', '-n', 'iscsiadm', '-m', 'session', '-P', '3'],
                    timeout=badblocks.TIMEOUT, stderr=DEVNULL),
                call(
                    [
                        'lsblk', '--exclude', '1,2,7', '-d', '-P', '-o',
                        'NAME,RO,MODEL,SERIAL',
                    ],
                    timeout=badblocks.TIMEOUT)))

    def test_run_destructive(self):
        drive = self.make_drive(with_path=True)
        run_bad_blocks = badblocks.RunBadBlocks(drive, True)
        output = factory.make_string()
        self.patch(badblocks, 'check_output').return_value = '4096'
        mock_popen = self.patch(badblocks, 'Popen')
        mock_popen.return_value = Popen(['echo', '-n', output], stdout=PIPE)

        run_bad_blocks.run()

        self.assertEquals(output.encode(), run_bad_blocks.output)
        self.assertEquals(0, run_bad_blocks.returncode)
        self.assertThat(
            mock_popen,
            MockCalledOnceWith(
                [
                    'sudo', '-n', 'badblocks', '-b', '4096', '-v', '-w',
                    drive['PATH'],
                ], stdout=PIPE, stderr=STDOUT))

    def test_run_nondestructive(self):
        drive = self.make_drive(with_path=True)
        run_bad_blocks = badblocks.RunBadBlocks(drive, False)
        output = factory.make_string()
        self.patch(badblocks, 'check_output').return_value = '4096'
        mock_popen = self.patch(badblocks, 'Popen')
        mock_popen.return_value = Popen(['echo', '-n', output], stdout=PIPE)

        run_bad_blocks.run()

        self.assertEquals(output.encode(), run_bad_blocks.output)
        self.assertEquals(0, run_bad_blocks.returncode)
        self.assertThat(
            mock_popen,
            MockCalledOnceWith(
                [
                    'sudo', '-n', 'badblocks', '-b', '4096', '-v', '-n',
                    drive['PATH'],
                ], stdout=PIPE, stderr=STDOUT))

    def test_run_badblocks(self):
        drive = {
            'NAME': factory.make_name('NAME'),
            'PATH': factory.make_name('PATH'),
            'MODEL': factory.make_name('MODEL'),
            'SERIAL': factory.make_name('SERIAL'),
        }
        self.patch(badblocks, 'list_drives').return_value = [drive]
        output = factory.make_string()
        self.patch(badblocks, 'check_output').return_value = '4096'
        mock_popen = self.patch(badblocks, 'Popen')
        mock_popen.return_value = Popen(['echo', '-n', output], stdout=PIPE)
        mock_print = self.patch(badblocks, 'print')

        self.assertEquals(0, badblocks.run_badblocks())

        dashes = '-' * int((80.0 - (2 + len(drive['PATH']))) / 2)
        header = '%s %s %s' % (dashes, drive['PATH'], dashes)
        self.assertThat(
            mock_print,
            MockCallsMatch(
                call(header),
                call('Model:  %s' % drive['MODEL']),
                call('Serial: %s' % drive['SERIAL']),
                call(),
                call(output)))

    def test_run_badblocks_outputs_failure(self):
        drive = {
            'NAME': factory.make_name('NAME'),
            'PATH': factory.make_name('PATH'),
            'MODEL': factory.make_name('MODEL'),
            'SERIAL': factory.make_name('SERIAL'),
        }
        self.patch(badblocks, 'list_drives').return_value = [drive]
        output = factory.make_string()
        self.patch(badblocks, 'check_output').return_value = '4096'
        mock_popen = self.patch(badblocks, 'Popen')
        mock_popen.return_value = Popen(
            'echo -n %s; exit 1' % output, stdout=PIPE, shell=True)
        mock_print = self.patch(badblocks, 'print')

        self.assertEquals(1, badblocks.run_badblocks())

        dashes = '-' * int((80.0 - (2 + len(drive['PATH']))) / 2)
        header = '%s %s %s' % (dashes, drive['PATH'], dashes)
        self.assertThat(
            mock_print,
            MockCallsMatch(
                call(header),
                call('Model:  %s' % drive['MODEL']),
                call('Serial: %s' % drive['SERIAL']),
                call(),
                call('Badblocks exited with 1!'),
                call(),
                call(output)))
