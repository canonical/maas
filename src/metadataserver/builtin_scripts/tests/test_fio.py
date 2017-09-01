# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test builtin_script fio."""

__all__ = []

from copy import deepcopy
import io
import os
import re
from subprocess import (
    PIPE,
    Popen,
    STDOUT,
)
from textwrap import dedent
from unittest.mock import ANY

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from metadataserver.builtin_scripts import fio
import yaml


FIO_READ_OUTPUT = dedent("""
    ...
    Starting 1 process
    Jobs: 1 (f=1): [r] [100.0% done] [62135K/0K /s] [15.6K/0 iops]
    test: (groupid=0, jobs=1): err= 0: pid=31181: Fri May 9 15:38:57 2014
      read : io=1024.0MB, bw=62748KB/s, iops=15686 , runt= 16711msec
      ...
    """)

FIO_WRITE_OUTPUT = dedent("""
    ...
    Starting 1 process
    Jobs: 1 (f=1): [w] [100.0% done] [0K/26326K /s] [0 /6581 iops]
    test: (groupid=0, jobs=1): err= 0: pid=31235: Fri May 9 16:16:21 2014
      write: io=1024.0MB, bw=29195KB/s, iops=7298 , runt= 35916msec
      ...
    """)


class TestFioTest(MAASTestCase):

    def test_run_cmd_runs_cmd_and_returns_output(self):
        cmd = factory.make_string()
        output = factory.make_string()
        mock_popen = self.patch(fio, "Popen")
        mock_popen.return_value = Popen(
            ['echo', '-n', output], stdout=PIPE, stderr=PIPE)

        cmd_output = fio.run_cmd(cmd)

        self.assertEquals((output.encode(), 0), cmd_output)
        self.assertThat(mock_popen, MockCalledOnceWith(
            cmd, stdout=PIPE, stderr=STDOUT))

    def test_run_cmd_runs_cmd_and_exits_on_error(self):
        cmd = factory.make_string()
        mock_popen = self.patch(fio, "Popen")
        proc = mock_popen.return_value
        proc.communicate.return_value = (b"Output", None)
        proc.returncode = 1

        self.assertRaises(SystemExit, fio.run_cmd, cmd)
        self.assertThat(mock_popen, MockCalledOnceWith(
            cmd, stdout=PIPE, stderr=STDOUT))

    def test_run_fio_test_runs_test(self):
        result_path = factory.make_string()
        readwrite = factory.make_string()
        cmd = deepcopy(fio.CMD)
        cmd.append('--readwrite=%s' % readwrite)
        returncode = 0
        mock_run_cmd = self.patch(fio, "run_cmd")
        mock_run_cmd.return_value = (
            FIO_READ_OUTPUT.encode('utf-8'), returncode)
        mock_re_search = self.patch(re, "search")
        fio.run_fio_test(readwrite, result_path)

        self.assertThat(mock_run_cmd, MockCalledOnceWith(cmd))
        self.assertThat(mock_re_search, MockCalledOnceWith(
            fio.REGEX, FIO_READ_OUTPUT.encode('utf-8')))

    def test_run_fio_test_exits_if_no_match_found(self):
        result_path = factory.make_string()
        readwrite = factory.make_string()
        cmd = deepcopy(fio.CMD)
        cmd.append('--readwrite=%s' % readwrite)
        returncode = 0
        mock_run_cmd = self.patch(fio, "run_cmd")
        mock_run_cmd.return_value = (
            FIO_WRITE_OUTPUT.encode('utf-8'), returncode)
        mock_re_search = self.patch(re, "search")
        mock_re_search.return_value = None
        fio.run_fio_test(readwrite, result_path)

        self.assertThat(mock_run_cmd, MockCalledOnceWith(cmd))
        self.assertThat(mock_re_search, MockCalledOnceWith(
            fio.REGEX, FIO_WRITE_OUTPUT.encode('utf-8')))

    def test_run_fio_writes_yaml_file(self):
        self.patch(os, 'environ', {
            "RESULT_PATH": factory.make_name()
        })
        disk = factory.make_name('disk')
        read_match = re.search(fio.REGEX, FIO_READ_OUTPUT.encode('utf-8'))
        write_match = re.search(fio.REGEX, FIO_WRITE_OUTPUT.encode('utf-8'))
        mock_run_fio_test = self.patch(fio, "run_fio_test")
        mock_run_fio_test.side_effect = [
            read_match, read_match, write_match, write_match]
        mock_open = self.patch(fio, "open")
        mock_open.return_value = io.StringIO()
        mock_yaml_safe_dump = self.patch(yaml, "safe_dump")
        # For the test, we will just use the same fio result for both
        # random and sequential.
        results = {
            'status': "passed",
            'results': {
                'random_read': read_match.group(1).decode(),
                'random_read_iops': read_match.group(2).decode(),
                'sequential_read': read_match.group(1).decode(),
                'sequential_read_iops': read_match.group(2).decode(),
                'random_write': write_match.group(1).decode(),
                'random_write_iops': write_match.group(2).decode(),
                'sequential_write': write_match.group(1).decode(),
                'sequential_write_iops': write_match.group(2).decode(),
            }
        }
        fio.run_fio(disk)

        self.assertThat(mock_open, MockCalledOnceWith(ANY, "w"))
        self.assertThat(mock_yaml_safe_dump, MockCalledOnceWith(
            results, mock_open.return_value))
