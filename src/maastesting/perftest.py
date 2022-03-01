# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Performance testing related classes and functions for MAAS and its applications"""


from datetime import datetime, timedelta
from functools import wraps
import os
import sys

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client import write_api
from pytest import fixture
from pytest import main as pytest_main
from pytest import mark, skip

from maastesting.fixtures import MAASDataFixture, MAASRootFixture

INFLUXDB_BUCKET = "maas-perf"
INFLUXDB_SECOND = 1000000000
DEFAULT_BRANCH = "master"


@fixture
def maas_root():
    if "MAAS_ROOT" in os.environ:
        return MAASRootFixture()
    return None


@fixture
def maas_data():
    if "MAAS_DATA" in os.environ:
        return MAASDataFixture()
    return None


perf_tester = None


class PerfTester:
    """PerfTester is responsible for recording and comparing performance tests"""

    def __init__(
        self,
        git_branch,
        git_hash,
        previous_hash=None,
        influxdb=None,
        postgres_enabled=False,
        **kwargs,
    ):
        self.influxdb = influxdb
        if self.influxdb:
            self.influx_write = self.influxdb.write_api(
                write_options=write_api.SYNCHRONOUS
            )
            self.influx_read = self.influxdb.query_api()

        self.postgres_enabled = postgres_enabled

        self.build = None
        try:
            self.previous_build = self._load_previous_build(
                previous_hash,
                kwargs.get("previous_branch", DEFAULT_BRANCH),
                kwargs.get("previous_release"),
            )
            self.build = self._create_build(
                git_branch, git_hash, release=kwargs.get("release")
            )
        except Exception as e:
            self.clean_build()
            raise e

    def _create_build(self, branch, git_hash, release=None):
        if not self.postgres_enabled:
            return None

        from maastesting.models import PerfTestBuild

        return PerfTestBuild.objects.create(
            git_branch=branch, git_hash=git_hash, release=release
        )

    def _load_previous_build(
        self, previous_hash, previous_branch, previous_release
    ):
        if not self.postgres_enabled:
            return None

        from maastesting.models import PerfTestBuild

        if not (previous_hash or previous_release):
            try:
                return (
                    PerfTestBuild.objects.filter(git_branch=previous_branch)
                    .order_by("-id")
                    .first()
                )
            except PerfTestBuild.DoesNotExist:
                return None
        if previous_release:
            return PerfTestBuild.objects.get(release=previous_release)
        if previous_hash:
            return PerfTestBuild.objects.get(git_hash=previous_hash)

    def finish_build(self):
        """finish_build is called when all tests for a build is done. It will update the build entry with its end timestamp."""
        if self.build:
            self.build.end_ts = datetime.utcnow()
            self.build.save()

    def clean_build(self):
        """clean_build deletes the current build in the event of an error preventing tests from finishing"""
        if self.build:
            self.build.delete()

    def record(self, test_name, delta):
        """record records a test in influxdb"""
        point = (
            Point(test_name)
            .tag("build_id", self.build.id)
            .field("operation_time", delta)
        )
        self.influx_write.write(bucket=INFLUXDB_BUCKET, record=point)

    def compare_previous(
        self, test_name: str, curr_val: float, allowed_drift: float
    ):
        """compare_previous fetches the influxdb entry for the previous build and compares it against the current values"""

        # |> filter(fn: (r) => r["build_id"] == {self.previous_build.id})
        tables = self.influx_read.query(
            f"""from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: duration(v: {int((self.previous_build.start_ts - self.build.start_ts).total_seconds() * INFLUXDB_SECOND)}))
            |> filter(fn: (r) => r["_measurement"] == "{test_name}")
            |> filter(fn: (r) => r["_field"] == "operation_time")
            """
        )
        previous_val = tables[0].records[0].get_value()
        diff = abs(previous_val - curr_val)
        assert (
            curr_val <= previous_val or diff <= allowed_drift
        ), f"{curr_val}s > {previous_val}s and not within a {allowed_drift}s difference"

    def compare_and_record(
        self,
        test_name: str,
        delta: float,
        max_time: float,
        allowed_drift: float = 0,
    ):
        """compare_and_record will compare a build to its max time, as well as record it and compare it to a previous build if one has been given"""
        if self.influxdb:
            self.record(test_name, delta)

        if self.previous_build:
            self.compare_previous(test_name, delta, allowed_drift)

        assert (
            delta <= max_time
        ), f"{delta} > the max time for this operation: {max_time}"


def perf_test(
    max_time, db_only=False, allowed_drift=0, commit_transaction=False
):
    if type(max_time) is not timedelta:
        max_time = timedelta(seconds=max_time)

    def inner(fn):
        @wraps(fn)
        @mark.perftest
        def wrapper(*args, **kwargs):
            from django.db import transaction

            save_point = None
            if perf_tester.postgres_enabled:
                save_point = transaction.savepoint()
            elif db_only:
                skip("test requires databases to be configured")

            start = datetime.now()
            try:
                fn(*args, **kwargs)
            finally:
                end = datetime.now()

                if save_point and commit_transaction:
                    transaction.savepoint_commit(save_point)
                elif save_point:
                    transaction.savepoint_rollback(save_point)

                delta = (end - start).total_seconds()
                if perf_tester:
                    perf_tester.compare_and_record(
                        fn.__name__,
                        delta,
                        max_time.total_seconds(),
                        allowed_drift=allowed_drift,
                    )

        return wrapper

    return inner


def perf_test_clean():
    if perf_tester:
        perf_tester.clean_build()


def perf_test_finish():
    perf_tester.finish_build()


def run_perf_tests(env):
    global perf_tester
    try:
        influx_url = env.get("INFLUXDB_URL")
        influx = None
        if influx_url:
            influx_token = env.get("INFLUXDB_TOKEN")
            influx_org = env.get("INFLUXDB_ORG")
            influx = InfluxDBClient(
                url=influx_url, token=influx_token, org=influx_org
            )
        perf_tester = PerfTester(
            env.get("GIT_BRANCH"),
            env.get("GIT_HASH"),
            previous_hash=env.get("PREV_HASH"),
            previous_branch=env.get("PREV_BRANCH"),
            previous_release=env.get("PREV_RELEASE"),
            release=env.get("RELEASE"),
            influxdb=influx,
            postgres_enabled=env.get("DJANGO_SETTINGS_MODULE") is not None,
        )
        cmd_args = []
        if len(sys.argv) > 1:
            cmd_args = sys.argv[1:]
        pytest_main(args=["-m", "perftest"] + cmd_args)
    except Exception as e:
        perf_test_clean()
        raise e
    else:
        perf_test_finish()
