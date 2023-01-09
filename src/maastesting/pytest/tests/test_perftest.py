# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import json
from time import sleep

from maastesting.factory import factory
from maastesting.pytest.perftest import PerfTester


class TestPerfTester:
    def test_record_adds_result(self):
        perf_tester = PerfTester(
            factory.make_name("branch"),
            factory.make_name("hash"),
            tracers=["timing"],
        )

        test_name = factory.make_name("test")

        with perf_tester.record(test_name):
            sleep(0.1)
        assert perf_tester.results["tests"][test_name]["duration"] > 0

    def test_write_results_outputs_results(self, capsys):
        perf_tester = PerfTester(
            factory.make_name("branch"),
            factory.make_name("hash"),
            tracers=["timing"],
        )

        test_name = factory.make_name("test")

        with perf_tester.record(test_name):
            sleep(0.1)

        perf_tester.write_results()
        results = json.loads(capsys.readouterr().out)
        assert results["tests"][test_name]["duration"] > 0
