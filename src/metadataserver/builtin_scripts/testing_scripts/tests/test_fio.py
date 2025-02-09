# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test builtin_script fio."""

import os
from pathlib import Path
import random
from subprocess import CalledProcessError
from textwrap import dedent
from unittest.mock import call

import yaml

from maastesting.factory import factory
from maastesting.fixtures import TempDirectory
from maastesting.testcase import MAASTestCase
from metadataserver.builtin_scripts.testing_scripts import fio

FIO_OLD_READ_OUTPUT = dedent(
    """
    ...
    Starting 1 process
    Jobs: 1 (f=1): [r] [100.0% done] [62135K/0K /s] [15.6K/0 iops]
    test: (groupid=0, jobs=1): err= 0: pid=31181: Fri May 9 15:38:57 2014
      read : io=1024.0MB, bw={bw}KB/s, iops={iops} , runt= 16711msec
      ...
    """
)

FIO_OLD_WRITE_OUTPUT = dedent(
    """
    ...
    Starting 1 process
    Jobs: 1 (f=1): [w] [100.0% done] [0K/26326K /s] [0 /6581 iops]
    test: (groupid=0, jobs=1): err= 0: pid=31235: Fri May 9 16:16:21 2014
      write: io=1024.0MB, bw={bw}KB/s, iops={iops} , runt= 35916msec
      ...
    """
)

FIO_NEW_READ_OUTPUT = dedent(
    """
fio-3.1
Starting 1 process
{{
    "jobs" : [
        {{
            "read" : {{
                "bw" : {bw},
                "iops" : {iops}
            }}
        }}
     ]
}}

fio_test: (groupid=0, jobs=1): err= 0: pid=2119: Tue Jul 17 17:00:41 2018
   read: IOPS=117k, BW=458MiB/s (480MB/s)(4096MiB/8951msec)
   bw (  KiB/s): min=427920, max=520120, per=100.00%, avg={bw}, stdev=27642.16
   iops        : min=106980, max=130030, avg={iops}, stdev=6910.54, samples=17
  cpu          : usr=11.64%, sys=39.18%, ctx=32963, majf=0, minf=75
  IO depths    : 1=0.1%, 2=0.1%, 4=0.1%, 8=0.1%, 16=0.1%, 32=0.1%, >=64=100.0%
     submit    : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.0%, >=64=0.0%
     complete  : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.1%, >=64=0.0%
     issued rwt: total=1048576,0,0, short=0,0,0, dropped=0,0,0
     latency   : target=0, window=0, percentile=100.00%, depth=64
"""
)

FIO_NEW_WRITE_OUTPUT = dedent(
    """
fio-3.1
Starting 1 process
{{
    "jobs" : [
        {{
            "write" : {{
                "bw" : {bw},
                "iops" : {iops}
            }}
        }}
     ]
}}

fio_test: (groupid=0, jobs=1): err= 0: pid=2235: Tue Jul 17 17:10:30 2018
  write: IOPS=123k, BW=480MiB/s (504MB/s)(4096MiB/8526msec)
   bw (  KiB/s): min=  512, max=1146456, per=100.00%, avg={bw}, stdev=376195.87
   iops        : min=  128, max=286614, avg={iops}, stdev=94048.97, samples=14
  cpu          : usr=10.84%, sys=32.75%, ctx=301, majf=0, minf=9
  IO depths    : 1=0.1%, 2=0.1%, 4=0.1%, 8=0.1%, 16=0.1%, 32=0.1%, >=64=100.0%
     submit    : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.0%, >=64=0.0%
     complete  : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.1%, >=64=0.0%
     issued rwt: total=0,1048576,0, short=0,0,0, dropped=0,0,0
     latency   : target=0, window=0, percentile=100.00%, depth=64
"""
)


class TestFioTestRunCmd(MAASTestCase):
    scenarios = [
        (
            "old_read",
            {
                "output_template": FIO_OLD_READ_OUTPUT,
                "readwrite": random.choice(["read", "randread"]),
            },
        ),
        (
            "old_write",
            {
                "output_template": FIO_OLD_WRITE_OUTPUT,
                "readwrite": random.choice(["write", "randwrite"]),
            },
        ),
        (
            "new_read",
            {
                "output_template": FIO_NEW_READ_OUTPUT,
                "readwrite": random.choice(["read", "randread"]),
            },
        ),
        (
            "new_write",
            {
                "output_template": FIO_NEW_WRITE_OUTPUT,
                "readwrite": random.choice(["write", "randwrite"]),
            },
        ),
    ]

    def setUp(self):
        super().setUp()
        self.mock_print = self.patch(fio, "print")
        self.mock_stdout_write = self.patch(fio.sys.stdout, "write")
        self.mock_stderr_write = self.patch(fio.sys.stderr, "write")
        self.mock_check_output = self.patch(fio, "check_output")
        self.bw = random.randint(1000, 1000000000)
        self.iops = random.randint(1000, 1000000000)

    def test_runs_command_outputs_and_returns_results(self):
        output = self.output_template.format(bw=self.bw, iops=self.iops)
        self.mock_check_output.return_value = output.encode()

        results = fio.run_cmd(self.readwrite)

        self.assertEqual(self.mock_print.call_count, 3)
        self.mock_print.assert_called_with(f"\n{'-' * 80}\n")
        self.assertEqual({"bw": self.bw, "iops": self.iops}, results)

    def test_run_cmd_runs_cmd_and_exits_on_error(self):
        stdout = factory.make_string()
        stderr = factory.make_string()
        self.mock_check_output.side_effect = CalledProcessError(
            output=stdout.encode(),
            stderr=stderr.encode(),
            cmd=["fio"],
            returncode=1,
        )

        self.assertRaises(SystemExit, fio.run_cmd, self.readwrite)
        self.mock_stderr_write.assert_has_calls(
            [call("fio failed to run!\n"), call(stderr)]
        )
        self.mock_stdout_write.assert_called_once_with(stdout)


class TestFioTestRunFio(MAASTestCase):
    scenarios = [
        (
            "old",
            {
                "read_output_template": FIO_OLD_READ_OUTPUT,
                "write_output_template": FIO_OLD_WRITE_OUTPUT,
            },
        ),
        (
            "new",
            {
                "read_output_template": FIO_NEW_READ_OUTPUT,
                "write_output_template": FIO_NEW_WRITE_OUTPUT,
            },
        ),
    ]

    def setUp(self):
        super().setUp()
        self.mock_print = self.patch(fio, "print")
        self.mock_stdout_write = self.patch(fio.sys.stdout, "write")
        self.mock_stderr_write = self.patch(fio.sys.stderr, "write")
        self.mock_check_output = self.patch(fio, "check_output")
        self.mock_get_blocksize = self.patch(fio, "get_blocksize")
        self.mock_get_blocksize.return_value = 512

    def test_run_fio_writes_yaml_file(self):
        tmp_path = Path(self.useFixture(TempDirectory()).path)
        result_path = tmp_path.joinpath("results.yaml")
        self.patch(os, "environ", {"RESULT_PATH": result_path})
        rand_read_bw = random.randint(1000, 1000000000)
        rand_read_iops = random.randint(1000, 1000000000)
        rand_read_output = self.read_output_template.format(
            bw=rand_read_bw, iops=rand_read_iops
        ).encode()
        seq_read_bw = random.randint(1000, 1000000000)
        seq_read_iops = random.randint(1000, 1000000000)
        seq_read_output = self.read_output_template.format(
            bw=seq_read_bw, iops=seq_read_iops
        ).encode()
        rand_write_bw = random.randint(1000, 1000000000)
        rand_write_iops = random.randint(1000, 1000000000)
        rand_write_output = self.write_output_template.format(
            bw=rand_write_bw, iops=rand_write_iops
        ).encode()
        seq_write_bw = random.randint(1000, 1000000000)
        seq_write_iops = random.randint(1000, 1000000000)
        seq_write_output = self.write_output_template.format(
            bw=seq_write_bw, iops=seq_write_iops
        ).encode()
        self.mock_check_output.side_effect = [
            rand_read_output,
            seq_read_output,
            rand_write_output,
            seq_write_output,
        ]

        fio.run_fio(factory.make_name("blockdevice"))

        with open(result_path) as results_file:
            results = yaml.safe_load(results_file)

        self.assertEqual(
            {
                "results": {
                    "random_read": f"{rand_read_bw} KB/s",
                    "random_read_iops": rand_read_iops,
                    "sequential_read": f"{seq_read_bw} KB/s",
                    "sequential_read_iops": seq_read_iops,
                    "random_write": f"{rand_write_bw} KB/s",
                    "random_write_iops": rand_write_iops,
                    "sequential_write": f"{seq_write_bw} KB/s",
                    "sequential_write_iops": seq_write_iops,
                }
            },
            results,
        )

    def test_run_fio_doenst_write_yaml_file(self):
        mock_open = self.patch(fio, "open")
        rand_read_bw = random.randint(1000, 1000000000)
        rand_read_iops = random.randint(1000, 1000000000)
        rand_read_output = self.read_output_template.format(
            bw=rand_read_bw, iops=rand_read_iops
        ).encode()
        seq_read_bw = random.randint(1000, 1000000000)
        seq_read_iops = random.randint(1000, 1000000000)
        seq_read_output = self.read_output_template.format(
            bw=seq_read_bw, iops=seq_read_iops
        ).encode()
        rand_write_bw = random.randint(1000, 1000000000)
        rand_write_iops = random.randint(1000, 1000000000)
        rand_write_output = self.write_output_template.format(
            bw=rand_write_bw, iops=rand_write_iops
        ).encode()
        seq_write_bw = random.randint(1000, 1000000000)
        seq_write_iops = random.randint(1000, 1000000000)
        seq_write_output = self.write_output_template.format(
            bw=seq_write_bw, iops=seq_write_iops
        ).encode()
        self.mock_check_output.side_effect = [
            rand_read_output,
            seq_read_output,
            rand_write_output,
            seq_write_output,
        ]

        fio.run_fio(factory.make_name("blockdevice"))

        mock_open.assert_not_called()
