# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timedelta
from unittest.mock import Mock

from maasserver.testing.testcase import MAASServerTestCase
from maastesting.factory import factory
from maastesting.models import PerfTestBuild
from maastesting.perftest import PerfTester


class TestPerfTester(MAASServerTestCase):
    def create_build(self, start, end=None, branch="master", release=None):
        if not end:
            end = start + timedelta(minutes=10)
        return PerfTestBuild.objects.create(
            git_branch=branch,
            git_hash=factory.make_name("hash"),
            start_ts=start,
            end_ts=end,
            release=release,
        )

    def test_build_is_zero_with_no_db(self):
        perf_tester = PerfTester(
            factory.make_name("branch"),
            factory.make_name("hash"),
        )
        self.assertIsNone(perf_tester.build)

    def test_load_previous_build_returns_zero_with_no_db(self):
        perf_tester = PerfTester(
            factory.make_name("branch"),
            factory.make_name("hash"),
        )
        self.assertIsNone(perf_tester.previous_build)

    def test_load_previous_build_returns_last_master_build_by_default(self):
        now = datetime.now()
        influx = Mock()
        self.create_build(now, branch=factory.make_name("branch"))
        self.create_build(now)
        perf_tester = PerfTester(
            factory.make_name("branch"),
            factory.make_name("hash"),
            influxdb=influx,
            postgres_enabled=True,
        )
        self.assertEqual(perf_tester.previous_build.git_branch, "master")

    def test_load_previous_build_returns_last_off_given_branch(self):
        now = datetime.now()
        influx = Mock()
        prev_branch = factory.make_name()
        self.create_build(now - timedelta(seconds=10), branch=prev_branch)
        prev_build = self.create_build(now, branch=prev_branch)
        perf_tester = PerfTester(
            factory.make_name("branch"),
            factory.make_name("hash"),
            influxdb=influx,
            postgres_enabled=True,
            previous_branch=prev_build.git_branch,
        )
        self.assertEqual(perf_tester.previous_build.id, prev_build.id)
        self.assertEqual(
            perf_tester.previous_build.git_hash, prev_build.git_hash
        )

    def test_load_previous_build_returns_build_of_given_hash(self):
        now = datetime.now()
        influx = Mock()
        first_build = self.create_build(now - timedelta(seconds=10))
        self.create_build(now)
        perf_tester = PerfTester(
            factory.make_name("branch"),
            factory.make_name("hash"),
            influxdb=influx,
            postgres_enabled=True,
            previous_hash=first_build.git_hash,
        )
        self.assertEqual(
            perf_tester.previous_build.git_hash, first_build.git_hash
        )

    def test_load_previous_build_returns_build_of_given_release(self):
        now = datetime.now()
        influx = Mock()
        prev_build = self.create_build(
            now - timedelta(seconds=10), release=factory.make_name("3.1.0")
        )
        perf_tester = PerfTester(
            factory.make_name("branch"),
            factory.make_name("hash"),
            influxdb=influx,
            postgres_enabled=True,
            previous_release=prev_build.release,
        )
        self.assertEqual(perf_tester.previous_build.id, prev_build.id)
        self.assertEqual(
            perf_tester.previous_build.release, prev_build.release
        )

    def test_finish_build_writes_end_ts(self):
        now = datetime.now()
        influx = Mock()
        self.create_build(now - timedelta(seconds=10))
        perf_tester = PerfTester(
            factory.make_name("branch"),
            factory.make_name("hash"),
            influxdb=influx,
            postgres_enabled=True,
        )
        self.assertIsNone(perf_tester.build.end_ts)
        perf_tester.finish_build()
        self.assertIsNotNone(perf_tester.build.end_ts)

    def test_clean_build_removes_build(self):
        now = datetime.now()
        influx = Mock()
        self.create_build(now - timedelta(seconds=10))
        perf_tester = PerfTester(
            factory.make_name("branch"),
            factory.make_name("hash"),
            influxdb=influx,
            postgres_enabled=True,
        )
        self.assertIsNotNone(perf_tester.build)
        perf_tester.clean_build()
        self.assertRaises(
            PerfTestBuild.DoesNotExist, perf_tester.build.refresh_from_db
        )

    def test_compare_previous(self):
        now = datetime.now()
        self.create_build(now)
        mock_table = Mock()
        mock_table.records = [Mock()]
        self.patch(mock_table.records[0], "get_value").return_value = 9.8
        tables = [mock_table]
        influx = Mock()
        perf_tester = PerfTester(
            factory.make_name("branch"),
            factory.make_name("hash"),
            influxdb=influx,
            postgres_enabled=True,
        )
        perf_tester.influx_read.query.return_value = tables
        test_name = factory.make_name("test")
        val = timedelta(seconds=10).total_seconds()
        self.assertRaises(
            AssertionError, perf_tester.compare_previous, test_name, val, 0
        )
        perf_tester.compare_previous(test_name, val, 1)

    def test_compare_and_record_compares_max_time(self):
        test_name = factory.make_name()
        perf_tester = PerfTester(
            factory.make_name("branch"),
            factory.make_name("hash"),
        )
        self.assertRaises(
            AssertionError, perf_tester.compare_and_record, test_name, 15, 10
        )

    def test_compare_and_record_writes_to_influx(self):
        now = datetime.now()
        self.create_build(now)
        test_name = factory.make_name()
        mock_table = Mock()
        mock_table.records = [Mock()]
        self.patch(mock_table.records[0], "get_value").return_value = 9.8
        tables = [mock_table]
        influx = Mock()
        perf_tester = PerfTester(
            factory.make_name("branch"),
            factory.make_name("hash"),
            influxdb=influx,
            postgres_enabled=True,
        )
        influx_write = self.patch(perf_tester.influx_write, "write")
        self.patch(perf_tester.influx_read, "query").return_value = tables
        perf_tester.compare_and_record(test_name, 10, 15, allowed_drift=1)
        influx_write.assert_called_once()

    def test_compare_and_record_compares_previous(self):
        now = datetime.now()
        self.create_build(now)
        test_name = factory.make_name()
        mock_table = Mock()
        mock_table.records = [Mock()]
        self.patch(mock_table.records[0], "get_value").return_value = 9.8
        tables = [mock_table]
        influx = Mock()
        perf_tester = PerfTester(
            factory.make_name("branch"),
            factory.make_name("hash"),
            influxdb=influx,
            postgres_enabled=True,
        )
        self.patch(perf_tester.influx_write, "write")
        self.patch(perf_tester.influx_read, "query").return_value = tables
        self.assertRaises(
            AssertionError,
            perf_tester.compare_and_record,
            test_name,
            10,
            15,
            allowed_drift=0,
        )
