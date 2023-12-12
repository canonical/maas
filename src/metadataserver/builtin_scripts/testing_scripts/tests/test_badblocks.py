# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test badblocks functions."""


import io
import os
import random
from subprocess import PIPE, STDOUT
from textwrap import dedent
from unittest.mock import ANY

import yaml

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from metadataserver.builtin_scripts.testing_scripts import badblocks

BADBLOCKS = random.randint(0, 1000)
READ_ERRORS = random.randint(0, 1000)
WRITE_ERRORS = random.randint(0, 1000)
COMPARISON_ERRORS = random.randint(0, 1000)
BADBLOCKS_OUTPUT = dedent(
    """
    Checking for bad blocks in non-destructive read-write mode
    From block 0 to 5242879
    Testing with random pattern:
    Pass completed, %s bad blocks found. (%s/%s/%s errors)
    """
    % (BADBLOCKS, READ_ERRORS, WRITE_ERRORS, COMPARISON_ERRORS)
)


class TestRunBadBlocks(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.mock_check_output = self.patch(badblocks, "check_output")
        self.mock_print = self.patch(badblocks, "print")

    def test_get_block_size(self):
        block_size = random.randint(512, 4096)
        self.mock_check_output.return_value = ("%s\n" % block_size).encode()
        self.assertEqual(
            block_size, badblocks.get_block_size(factory.make_name("storage"))
        )

    def test_get_parallel_blocks(self):
        # Most systems will have more then enough more to test 5000
        # blocks at a time. Simulate that by reading test system memory
        # values and giving a block size of 1.
        self.mock_check_output.return_value = b"1\n"
        self.assertEqual(50000, badblocks.get_parallel_blocks(1))

    def test_get_parallel_blocks_limited(self):
        # Systems with a large amount of disks and not that much RAM will need
        # to throttle the amount of blocks tested at once. Simulate that by
        # reading test system memory values and giving a large block size.
        self.mock_check_output.return_value = b"1\n" * 1000
        self.assertGreaterEqual(50000, badblocks.get_parallel_blocks(1000))

    def test_run_badblocks_nondestructive_and_writes_results_file(self):
        storage = factory.make_name("storage")
        blocksize = random.randint(512, 4096)
        self.patch(badblocks, "get_block_size").return_value = blocksize
        parallel_blocks = random.randint(1, 50000)
        self.patch(
            badblocks, "get_parallel_blocks"
        ).return_value = parallel_blocks
        self.patch(os, "environ", {"RESULT_PATH": factory.make_name()})
        cmd = [
            "sudo",
            "-n",
            "badblocks",
            "-b",
            str(blocksize),
            "-c",
            str(parallel_blocks),
            "-v",
            "-f",
            "-s",
            "-n",
            storage,
        ]
        mock_popen = self.patch(badblocks, "Popen")
        proc = mock_popen.return_value
        proc.communicate.return_value = (
            BADBLOCKS_OUTPUT.encode("utf-8"),
            None,
        )
        proc.returncode = 0
        mock_open = self.patch(badblocks, "open")
        mock_open.return_value = io.StringIO()
        mock_yaml_safe_dump = self.patch(yaml, "safe_dump")
        results = {
            "results": {
                "badblocks": BADBLOCKS,
                "read_errors": READ_ERRORS,
                "write_errors": WRITE_ERRORS,
                "comparison_errors": COMPARISON_ERRORS,
            }
        }

        self.assertEqual(1, badblocks.run_badblocks(storage))
        mock_popen.assert_called_once_with(cmd, stdout=PIPE, stderr=STDOUT)
        mock_open.assert_called_once_with(ANY, "w")
        mock_yaml_safe_dump.assert_called_once_with(
            results, mock_open.return_value
        )

    def test_run_badblocks_destructive(self):
        storage = factory.make_name("storage")
        blocksize = random.randint(512, 4096)
        self.patch(badblocks, "get_block_size").return_value = blocksize
        parallel_blocks = random.randint(1, 50000)
        self.patch(
            badblocks, "get_parallel_blocks"
        ).return_value = parallel_blocks
        cmd = [
            "sudo",
            "-n",
            "badblocks",
            "-b",
            str(blocksize),
            "-c",
            str(parallel_blocks),
            "-v",
            "-f",
            "-s",
            "-w",
            storage,
        ]
        mock_popen = self.patch(badblocks, "Popen")
        proc = mock_popen.return_value
        proc.communicate.return_value = (
            BADBLOCKS_OUTPUT.encode("utf-8"),
            None,
        )
        proc.returncode = 0

        self.assertEqual(1, badblocks.run_badblocks(storage, destructive=True))
        mock_popen.assert_called_once_with(cmd, stdout=PIPE, stderr=STDOUT)
