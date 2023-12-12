# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test builtin_script 7z."""


import io
import os
import re
from subprocess import PIPE
import sys
from textwrap import dedent
from unittest.mock import ANY

import yaml

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from metadataserver.builtin_scripts.testing_scripts import seven_z

SEVEN_Z_OUTPUT = dedent(
    """
    7-Zip [64] 9.20  Copyright (c) 1999-2010 Igor Pavlov  2010-11-18
    p7zip Version 9.20 (locale=en_US.UTF-8,Utf16=on,HugeFiles=on,8 CPUs)

    RAM size:   15923 MB,  # CPU hardware threads:   8
    RAM usage:   1701 MB,  # Benchmark threads:      8

    Dict        Compressing          |        Decompressing
          Speed Usage    R/U Rating  |    Speed Usage    R/U Rating
           KB/s     %   MIPS   MIPS  |     KB/s     %   MIPS   MIPS

    22:   17176   623   2681  16709  |   200683   772   2343  18099
    23:   17252   625   2813  17577  |   198810   774   2349  18188
    24:   16387   626   2813  17619  |   193728   763   2356  17970
    25:   18067   665   3099  20628  |   195692   777   2369  18402
    ----------------------------------------------------------------
    Avr:          635   2852  18134               771   2354  18165
    Tot:          703   2603  18149
    """
)


class TestSevenZTest(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.patch(seven_z, "print")

    def test_run_7z_executes_cmd_and_writes_results_file(self):
        self.patch(os, "environ", {"RESULT_PATH": factory.make_name()})
        cmd = ["7z", "b"]
        mock_popen = self.patch(seven_z, "Popen")
        proc = mock_popen.return_value
        proc.communicate.return_value = (SEVEN_Z_OUTPUT.encode("utf-8"), None)
        proc.returncode = 0
        match = re.search(seven_z.REGEX, SEVEN_Z_OUTPUT.encode("utf-8"))
        averages = match.group(1).split()
        mock_open = self.patch(seven_z, "open")
        mock_open.return_value = io.StringIO()
        mock_yaml_safe_dump = self.patch(yaml, "safe_dump")
        results = {
            "status": "passed",
            "results": {
                "compression_ru_mips": averages[1].decode(),
                "compression_rating_mips": averages[2].decode(),
                "decompression_ru_mips": averages[4].decode(),
                "decompression_rating_mips": averages[5].decode(),
            },
        }
        returncode = seven_z.run_7z()

        mock_popen.assert_called_once_with(cmd, stdout=PIPE, stderr=PIPE)
        mock_open.assert_called_once_with(ANY, "w")
        mock_yaml_safe_dump.assert_called_once_with(
            results, mock_open.return_value
        )
        self.assertEqual(returncode, 0)

    def test_run_7z_exits_if_returncode_non_zero(self):
        cmd = ["7z", "b"]
        mock_popen = self.patch(seven_z, "Popen")
        mock_stderr = self.patch(sys, "stderr")
        proc = mock_popen.return_value
        proc.communicate.return_value = (None, b"Error")
        proc.returncode = 1

        self.assertRaises(SystemExit, seven_z.run_7z)
        mock_popen.assert_called_once_with(cmd, stdout=PIPE, stderr=PIPE)
        mock_stderr.write.assert_called_once_with("Error")

    def test_run_7z_exits_if_no_regex_match_found(self):
        self.patch(os, "environ", {"RESULT_PATH": factory.make_name()})
        stderr = factory.make_string()
        cmd = ["7z", "b"]
        mock_popen = self.patch(seven_z, "Popen")
        proc = mock_popen.return_value
        proc.communicate.return_value = (
            SEVEN_Z_OUTPUT.encode("utf-8"),
            stderr.encode("utf-8"),
        )
        proc.returncode = 0

        mock_re_search = self.patch(re, "search")
        mock_re_search.return_value = None
        mock_sys_stderr = self.patch(sys, "stderr")

        self.assertRaises(SystemExit, seven_z.run_7z)
        mock_popen.assert_called_once_with(cmd, stdout=PIPE, stderr=PIPE)
        mock_re_search.assert_called_once_with(
            seven_z.REGEX, SEVEN_Z_OUTPUT.encode("utf-8")
        )
        mock_sys_stderr.write.assert_called_once_with(stderr)
