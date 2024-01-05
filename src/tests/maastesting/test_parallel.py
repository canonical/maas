# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import os
import random
import re
from unittest.mock import ANY, Mock

import junitxml
import pytest
import subunit
import testtools
from testtools import MultiTestResult, TextTestResult

from maastesting import parallel


@pytest.fixture
def mock_parallel_test(monkeypatch):
    monkeypatch.setattr(parallel, "test", Mock(return_value=True))


class TestSelectorArguments:
    """Tests for arguments that select scripts."""

    def _get_script_args(self):
        return list(parallel.test.call_args[0][0])

    def test_all_scripts_are_selected_when_no_selectors(
        self, mock_parallel_test
    ):
        with pytest.raises(SystemExit) as sysexit:
            parallel.main([])
        assert sysexit.value.code == 0
        scripts = self._get_script_args()
        assert len(scripts) == 3
        legacy, rack, region = scripts
        assert isinstance(legacy, parallel.TestScriptUnselectable)
        assert legacy.script == "bin/test.region.legacy"
        assert isinstance(rack, parallel.TestScriptSelectable)
        assert rack.script == "bin/test.rack"
        assert isinstance(region, parallel.TestScriptSelectable)
        assert region.script == "bin/test.region"

    def test_scripts_can_be_selected_by_path(self, mock_parallel_test):
        with pytest.raises(SystemExit) as sysexit:
            parallel.main(
                [
                    "src/provisioningserver/002",
                    "src/maasserver/003",
                    "src/metadataserver/004",
                ]
            )
        assert sysexit.value.code == 0
        scripts = self._get_script_args()
        assert len(scripts) == 2
        rack, region = scripts
        assert isinstance(rack, parallel.TestScriptSelectable)
        assert rack.script == "bin/test.rack"
        assert rack.selectors == ("src/provisioningserver/002",)
        assert isinstance(region, parallel.TestScriptSelectable)
        assert region.script == "bin/test.region"
        assert region.selectors == (
            "src/maasserver/003",
            "src/metadataserver/004",
        )

    def test_scripts_can_be_selected_by_module(self, mock_parallel_test):
        with pytest.raises(SystemExit) as sysexit:
            parallel.main(
                [
                    "provisioningserver.002",
                    "maasserver.003",
                    "metadataserver.004",
                ],
            )
        assert sysexit.value.code == 0
        scripts = self._get_script_args()
        assert len(scripts) == 2
        rack, region = scripts
        assert isinstance(rack, parallel.TestScriptSelectable)
        assert rack.script == "bin/test.rack"
        assert rack.selectors == ("provisioningserver.002",)
        assert isinstance(region, parallel.TestScriptSelectable)
        assert region.script == "bin/test.region"
        assert region.selectors == (
            "maasserver.003",
            "metadataserver.004",
        )


class TestSubprocessArguments:
    """Tests for arguments that adjust subprocess behaviour."""

    def test_defaults(self, mock_parallel_test):
        with pytest.raises(SystemExit) as sysexit:
            parallel.main([])

        assert sysexit.value.code == 0
        parallel.test.assert_called_once_with(
            ANY, ANY, max(os.cpu_count() - 2, 2)
        )

    def test_subprocess_count_can_be_specified(self, mock_parallel_test):
        count = random.randrange(100, 1000)
        with pytest.raises(SystemExit) as sysexit:
            parallel.main(["--subprocesses", str(count)])
        assert sysexit.value.code == 0
        parallel.test.assert_called_once_with(ANY, ANY, count)

    def test_subprocess_count_of_less_than_1_is_rejected(
        self, mock_parallel_test, capsys
    ):
        with pytest.raises(SystemExit) as sysexit:
            parallel.main(["--subprocesses", "0"])
        assert sysexit.value.code == 2
        parallel.test.assert_not_called()
        captured = capsys.readouterr()
        error = captured.err
        assert re.search(
            r"(?ms)^usage: .* argument --subprocesses: 0 is not 1 or greater",
            error,
        )

    def test_subprocess_count_non_numeric_is_rejected(
        self, mock_parallel_test, capsys
    ):
        with pytest.raises(SystemExit) as sysexit:
            parallel.main(["--subprocesses", "foo"])
        assert sysexit.value.code == 2
        parallel.test.assert_not_called()
        captured = capsys.readouterr()
        error = captured.err
        assert re.search(
            r"(?ms)^usage: .* argument --subprocesses: 'foo' is not an integer",
            error,
        )

    def test_subprocess_per_core_can_be_specified(self, mock_parallel_test):
        with pytest.raises(SystemExit) as sysexit:
            parallel.main(["--subprocess-per-core"])
        assert sysexit.value.code == 0
        parallel.test.assert_called_once_with(ANY, ANY, os.cpu_count())

    def test_subprocess_count_and_per_core_cannot_both_be_specified(
        self, mock_parallel_test, capsys
    ):
        with pytest.raises(SystemExit) as sysexit:
            parallel.main(["--subprocesses", "3", "--subprocess-per-core"])
        assert sysexit.value.code == 2
        parallel.test.assert_not_called()
        captured = capsys.readouterr()
        error = captured.err
        assert re.search(
            r"(?ms)^usage: .* argument --subprocess-per-core: not allowed with argument --subprocesses",
            error,
        )


class TestEmissionArguments:
    """Tests for arguments that adjust result emission behaviour."""

    def test_results_are_human_readable_by_default(self, mock_parallel_test):
        with pytest.raises(SystemExit) as sysexit:
            parallel.main([])
        assert sysexit.value.code == 0
        parallel.test.assert_called_once_with(ANY, ANY, ANY)
        _, result, _ = parallel.test.call_args[0]
        assert isinstance(result, MultiTestResult)
        assert len(result._results) == 2
        text_result, test_result = result._results
        assert isinstance(text_result.decorated, TextTestResult)
        assert isinstance(test_result.decorated, testtools.TestByTestResult)

    def test_results_can_be_explicitly_specified_as_human_readable(
        self, mock_parallel_test
    ):
        with pytest.raises(SystemExit) as sysexit:
            parallel.main(["--emit-human"])
        assert sysexit.value.code == 0
        parallel.test.assert_called_once_with(ANY, ANY, ANY)
        _, result, _ = parallel.test.call_args[0]
        assert isinstance(result, MultiTestResult)
        assert len(result._results) == 2
        text_result, test_result = result._results
        assert isinstance(text_result.decorated, TextTestResult)
        assert isinstance(test_result.decorated, testtools.TestByTestResult)

    def test_results_can_be_specified_as_subunit(self, mock_parallel_test):
        with pytest.raises(SystemExit) as sysexit:
            parallel.main(["--emit-subunit"])
        assert sysexit.value.code == 0
        parallel.test.assert_called_once_with(ANY, ANY, ANY)
        _, result, _ = parallel.test.call_args[0]
        assert isinstance(result, subunit.TestProtocolClient)
        assert result._stream is parallel.sys.stdout.buffer

    def test_results_can_be_specified_as_junit(self, mock_parallel_test):
        with pytest.raises(SystemExit) as sysexit:
            parallel.main(["--emit-junit"])
        assert sysexit.value.code == 0
        parallel.test.assert_called_once_with(ANY, ANY, ANY)
        _, result, _ = parallel.test.call_args[0]
        assert isinstance(result, junitxml.JUnitXmlResult)
        assert result._stream is parallel.sys.stdout
