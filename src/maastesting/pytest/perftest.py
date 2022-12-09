# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Performance testing related classes and functions for MAAS and its applications"""


from contextlib import contextmanager, ExitStack
from cProfile import Profile
import json
import os
import sys
import time

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


@pytest.fixture(scope="session")
def perf(pytestconfig, request):
    # mark all tests so that the database is re-created after each one
    request.applymarker(pytest.mark.recreate_db)

    profiling_tag = pytestconfig.getoption("--perf-profiling-tag", None)
    perf_tester = PerfTester(
        os.environ.get("GIT_BRANCH"),
        os.environ.get("GIT_HASH"),
        profiling_tag,
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

    def __init__(self):
        self.start = time.monotonic()

    def stop(self):
        assert self.duration is None, "Can't call stop() twice."
        end = time.monotonic()
        self.duration = end - self.start


@contextmanager
def measure_time():
    timing = Timing()
    yield timing
    timing.stop()


class PerfTester:
    """PerfTester is responsible for recording performance tests"""

    def __init__(self, git_branch, git_hash, profiling_tag):
        self.results = {"branch": git_branch, "commit": git_hash, "tests": {}}
        self.profiling_tag = profiling_tag

    @contextmanager
    def record(self, name):
        with ExitStack() as stack:
            if self.profiling_tag:
                stack.enter_context(profile(name, self.profiling_tag))
            timing = stack.enter_context(measure_time())
            yield
        self.results["tests"][name] = {"duration": timing.duration}

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
    print(f"Dumped stats to {filename}")
