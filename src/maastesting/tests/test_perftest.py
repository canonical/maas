# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from io import StringIO
import json
from time import sleep

from maastesting.factory import factory
from maastesting.perftest import PerfTester
from maastesting.testcase import MAASTestCase


class TestPerfTester(MAASTestCase):
    def test_record_adds_result(self):
        perf_tester = PerfTester(
            factory.make_name("branch"), factory.make_name("hash")
        )

        test_name = factory.make_name("test")

        with perf_tester.record(test_name):
            sleep(0.1)

        self.assertIsNotNone(perf_tester.results["tests"][test_name])
        self.assertTrue(
            perf_tester.results["tests"][test_name]["duration"] > 0
        )

    def test_finish_build_outputs_results(self):
        buf = StringIO()
        perf_tester = PerfTester(
            factory.make_name("branch"), factory.make_name("hash")
        )

        test_name = factory.make_name("test")

        with perf_tester.record(test_name):
            sleep(0.1)

        perf_tester.finish_build(buf)

        out = json.loads(buf.getvalue())

        self.assertIsNotNone(out["tests"][test_name])
        self.assertTrue(out["tests"][test_name]["duration"] > 0)
