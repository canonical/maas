# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Performance testing related classes and functions for MAAS and its applications"""


from contextlib import contextmanager
from cProfile import Profile
from datetime import datetime
from functools import wraps
import json
import os
import random
import sys

from pytest import fixture
from pytest import main as pytest_main
from pytest import mark, skip

from maastesting.fixtures import MAASDataFixture, MAASRootFixture

DEFAULT_BRANCH = "master"


@fixture(scope="session")
def maas_root():
    if "MAAS_ROOT" in os.environ:
        return MAASRootFixture()
    return None


@fixture(scope="session")
def maas_data():
    if "MAAS_DATA" in os.environ:
        return MAASDataFixture()
    return None


perf_tester = None


class PerfTester:
    """PerfTester is responsible for recording performance tests"""

    def __init__(self, git_branch, git_hash):
        self.results = {"branch": git_branch, "commit": git_hash, "tests": {}}

    def _record(self, name, start, end):
        delta = (end - start).total_seconds()
        self.results["tests"][name] = {"duration": delta}

    @contextmanager
    def record(self, name):
        start = datetime.utcnow()
        try:
            yield
        finally:
            end = datetime.utcnow()
            self._record(name, start, end)

    def finish_build(self, output):
        json.dump(self.results, output)


def perf_test(commit_transaction=False, db_only=False):
    def inner(fn):
        @wraps(fn)
        @mark.django_db
        def wrapper(*args, **kwargs):
            from django.db import transaction

            django_loaded = (
                os.environ.get("DJANGO_SETTINGS_MODULE") is not None
            )

            if db_only and not django_loaded:
                skip("skipping database test")

            save_point = None
            if django_loaded:
                save_point = transaction.savepoint()

            with perf_tester.record(fn.__name__):
                fn(*args, **kwargs)

            if save_point and commit_transaction:
                transaction.savepoint_commit(save_point)
            elif save_point:
                transaction.savepoint_rollback(save_point)

        return wrapper

    return inner


def perf_test_finish(output):
    if output:
        with open(output, "w") as f:
            perf_tester.finish_build(f)
    else:
        perf_tester.finish_build(sys.stdout)


def run_perf_tests(env):
    global perf_tester

    rand_seed = os.environ.get("MAAS_RAND_SEED")
    random.seed(rand_seed)

    try:
        cmd_args = sys.argv[1:]
        perf_tester = PerfTester(env.get("GIT_BRANCH"), env.get("GIT_HASH"))

        pytest_main(
            args=["src/maasperf"] + cmd_args,
        )
    finally:
        perf_test_finish(env.get("OUTPUT_FILE"))


@contextmanager
def profile(testname: str):
    """Produces profiling info for tests

    This functions uses cProfile module to provide deterministic
    profiling data for tests. The overhead is reasonable, typically < 5%.

    When enabled (MAAS_PROFILING is set in the environment) the
    profiling data is written to a file called
    `<testname>.$MAAS_PROFILING.profile` in the current
    directory. This file can be analyzed with external tools like
    `snakeviz`.

    Args:
        testname (str): name of the output file

    Example:

        with perftest.profile("my_test_case"):
            <<block being profiled>>
    """
    if profiling_tag := os.environ.get("MAAS_PROFILING"):
        with Profile() as profiler:
            yield
        filename = f"{testname}.{profiling_tag}.profile"
        profiler.dump_stats(filename)
        print(f"Dumped stats to {filename}")
    else:
        yield
