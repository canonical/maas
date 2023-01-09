# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Performance testing related classes and functions for MAAS and its applications"""


from contextlib import contextmanager, ExitStack
from cProfile import Profile
import gc
import json
import os
import sys
import time
import tracemalloc

import pytest

from maastesting.fixtures import MAASDataFixture, MAASRootFixture

DEFAULT_BRANCH = "master"


@pytest.fixture(scope="session")
def maas_root():
    if "MAAS_ROOT" in os.environ:
        return MAASRootFixture()
    return None


@pytest.fixture(scope="session")
def maas_data():
    if "MAAS_DATA" in os.environ:
        return MAASDataFixture()
    return None


def pytest_addoption(parser):
    parser.addoption(
        "--perf-output-file",
        help="The file where to write the performance measurement as JSON.",
    )
    parser.addoption(
        "--perf-profiling-tag",
        help="If specified, create profiling dumps for the measured tests.",
    )
    parser.addoption(
        "--perf-memory-trace-tag",
        help="If specified, trace amount of allocated memory and dump stats.",
    )


@pytest.fixture(scope="session")
def perf(pytestconfig, request):
    # mark all tests so that the database is re-created after each one
    request.applymarker(pytest.mark.recreate_db)

    profiling_tag = pytestconfig.getoption("--perf-profiling-tag", None)
    memory_trace_tag = pytestconfig.getoption("--perf-memory-trace-tag", False)
    perf_tester = PerfTester(
        os.environ.get("GIT_BRANCH"),
        os.environ.get("GIT_HASH"),
        profiling_tag=profiling_tag,
        memory_trace_tag=memory_trace_tag,
    )
    yield perf_tester
    output = pytestconfig.getoption("--perf-output-file", None)
    if output:
        with open(output, "w") as f:
            perf_tester.finish_build(f)
    else:
        perf_tester.finish_build(sys.stdout, format=True)


class Timing:
    duration = None

    def __enter__(self):
        # Collect all the garbage before the timing begins, so that collection
        # of unrelated garbage won't slow things down.
        gc.collect()
        self.start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Collect the garbage that was created by the code that is being timed,
        # so that we get a more consistent timing.  Otherwise, a small change
        # to the code we time could cause a big change in time due to a new
        # garbage collection being triggered.
        gc.collect()
        end = time.monotonic()
        self.duration = end - self.start


class QueryCounter:

    count = 0
    time = 0.0

    def __enter__(self):
        from django.db import reset_queries

        reset_queries()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            return

        from django.db import connection

        self.count = len(connection.queries)
        self.time = sum((float(entry["time"]) for entry in connection.queries))


class MemoryTracer:
    _snapshot = None

    def __init__(self, testname, tag):
        self.testname = testname
        self.tag = tag

    def __enter__(self):
        tracemalloc.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            return

        self._snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()
        filename = f"{self.testname}.{self.tag}.memstat"
        self._snapshot.dump(filename)
        print(f"Dumped memory stats to {filename}")

    def allocated_total(self) -> int:
        if not self._snapshot:
            return 0
        stats = self._snapshot.statistics("lineno")
        return sum(stat.size for stat in stats)


class PerfTester:
    """PerfTester is responsible for recording performance tests"""

    def __init__(
        self, git_branch, git_hash, profiling_tag=None, memory_trace_tag=None
    ):
        self.results = {"branch": git_branch, "commit": git_hash, "tests": {}}
        self.profiling_tag = profiling_tag
        self.memory_trace_tag = memory_trace_tag

    @contextmanager
    def record(self, name):
        memory_tracer = None
        with ExitStack() as stack:
            if self.profiling_tag:
                stack.enter_context(profile(name, self.profiling_tag))
            if self.memory_trace_tag:
                memory_tracer = stack.enter_context(
                    MemoryTracer(name, self.memory_trace_tag)
                )
            query_counter = stack.enter_context(QueryCounter())
            timing = stack.enter_context(Timing())
            yield
        results = {
            "duration": timing.duration,
            "query_count": query_counter.count,
            "query_time": query_counter.time,
        }
        if memory_tracer:
            results["memory"] = memory_tracer.allocated_total()
        self.results["tests"][name] = results

    def finish_build(self, output, format=False):
        params = {"sort_keys": True, "indent": 4} if format else {}
        if format:
            output.write("\n")
        json.dump(self.results, output, **params)


@contextmanager
def profile(testname: str, profiling_tag: str):
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
    with Profile() as profiler:
        yield
    filename = f"{testname}.{profiling_tag}.profile"
    profiler.dump_stats(filename)
    print(f"Dumped profiler stats to {filename}")
