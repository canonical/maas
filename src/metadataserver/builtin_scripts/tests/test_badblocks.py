# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test badblocks functions."""

__all__ = []


import io
import os
import random
import re
from subprocess import (
    DEVNULL,
    PIPE,
    STDOUT,
)
from textwrap import dedent
from unittest.mock import ANY

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from metadataserver.builtin_scripts import badblocks
import yaml


BADBLOCKS_OUTPUT = dedent("""
    Checking for bad blocks in non-destructive read-write mode
    From block 0 to 5242879
    Testing with random pattern:
    Pass completed, 19 bad blocks found. (0/0/19 errors)
    """)


class TestRunBadBlocks(MAASTestCase):

    def test_run_badblocks_nondestructive_and_writes_results_file(self):
        storage = factory.make_name('storage')
        self.patch(os, "environ", {
            "RESULT_PATH": factory.make_name()
        })
        mock_check_output = self.patch(badblocks, "check_output")
        blocksize = str(random.choice([1024, 2048, 4096]))
        mock_check_output.return_value = blocksize.encode('utf-8')
        cmd = [
            'sudo', '-n', 'badblocks', '-b', blocksize, '-v', '-f', '-n',
            storage]
        mock_popen = self.patch(badblocks, "Popen")
        proc = mock_popen.return_value
        proc.communicate.return_value = (
            BADBLOCKS_OUTPUT.encode('utf-8'), None)
        proc.returncode = 0
        match = re.search(badblocks.REGEX, BADBLOCKS_OUTPUT.encode('utf-8'))
        mock_open = self.patch(badblocks, "open")
        mock_open.return_value = io.StringIO()
        mock_yaml_safe_dump = self.patch(yaml, "safe_dump")
        results = {
            'results': {
                'badblocks': int(match.group(1).decode()),
            }
        }

        self.assertEquals(0, badblocks.run_badblocks(storage))
        self.assertThat(mock_check_output, MockCalledOnceWith(
            ['sudo', '-n', 'blockdev', '--getbsz', storage],
            stderr=DEVNULL))
        self.assertThat(mock_popen, MockCalledOnceWith(
            cmd, stdout=PIPE, stderr=STDOUT))
        self.assertThat(mock_open, MockCalledOnceWith(ANY, "w"))
        self.assertThat(mock_yaml_safe_dump, MockCalledOnceWith(
            results, mock_open.return_value))

    def test_run_badblocks_destructive(self):
        storage = factory.make_name('storage')
        mock_check_output = self.patch(badblocks, "check_output")
        blocksize = str(random.choice([1024, 2048, 4096]))
        mock_check_output.return_value = blocksize.encode('utf-8')
        cmd = [
            'sudo', '-n', 'badblocks', '-b', blocksize, '-v', '-f', '-w',
            storage]
        mock_popen = self.patch(badblocks, "Popen")
        proc = mock_popen.return_value
        proc.communicate.return_value = (
            BADBLOCKS_OUTPUT.encode('utf-8'), None)
        proc.returncode = 0

        self.assertEquals(
            0, badblocks.run_badblocks(storage, destructive=True))
        self.assertThat(mock_check_output, MockCalledOnceWith(
            ['sudo', '-n', 'blockdev', '--getbsz', storage],
            stderr=DEVNULL))
        self.assertThat(mock_popen, MockCalledOnceWith(
            cmd, stdout=PIPE, stderr=STDOUT))

    def test_run_badblocks_exits_if_no_regex_match_found(self):
        self.patch(os, "environ", {
            "RESULT_PATH": factory.make_name()
        })
        storage = factory.make_name('storage')
        mock_check_output = self.patch(badblocks, "check_output")
        blocksize = str(random.choice([1024, 2048, 4096]))
        mock_check_output.return_value = blocksize.encode('utf-8')
        cmd = [
            'sudo', '-n', 'badblocks', '-b', blocksize, '-v', '-f', '-n',
            storage]
        mock_popen = self.patch(badblocks, "Popen")
        proc = mock_popen.return_value
        proc.communicate.return_value = (
            BADBLOCKS_OUTPUT.encode('utf-8'), None)
        proc.returncode = 0
        mock_re_search = self.patch(re, "search")
        mock_re_search.return_value = None

        self.assertEquals(0, badblocks.run_badblocks(storage))
        self.assertThat(mock_popen, MockCalledOnceWith(
            cmd, stdout=PIPE, stderr=STDOUT))
        self.assertThat(mock_re_search, MockCalledOnceWith(
            badblocks.REGEX, BADBLOCKS_OUTPUT.encode('utf-8')))
